"""Internal scheduled executor child using an explicit Pydantic AI model loop.

Production selection is owned by operator_recovery. This module does not alter
engine, mail or business guards, and never emits native Claude evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import os
import re
import signal
import stat
import sys
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .operator_executor_config import ExecutorConfig, Admission, AdmissionError, cache_request_matches
from .operator_executor_protocol import (Journal, RunStart, RunEnd, Diagnostic,
    ModelRequest, ModelResponse, ProviderSubmission, Artifact, canonical, decode, sha256)
from .operator_executor_tools import ToolRuntime, Refusal, identity


def decimal_string(value):
    return format(value, 'f')


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(v) for v in value)
    if value is None or type(value) in (str, int, float, bool):
        return value
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    raise Refusal('unsupported_request_serialization')


def build_model(config, runtime):
    # Imported lazily; normal cs commands do not initialize provider clients.
    from anthropic import AsyncAnthropic
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider
    key = os.environ.get(config.api_key_env)
    if not key:
        raise Refusal('executor_credential_unavailable')
    import httpx2
    async def bound_submission(request):
        if (str(request.url) != config.messages_endpoint
                or request.headers.get('authorization') != 'Bearer ' + key
                or request.headers.get('x-api-key')):
            raise Refusal('provider_endpoint_or_auth_binding_differs')
        await runtime.provider_submission(request)
    client = AsyncAnthropic(**({'api_key': key} if config.provider == 'anthropic' else {'auth_token': key}),
                            max_retries=0,
                            http_client=httpx2.AsyncClient(event_hooks={"request": [bound_submission],
                                "response": [runtime.provider_response]}, trust_env=False),
                            base_url=config.endpoint)
    from pydantic_ai.profiles.anthropic import AnthropicModelProfile
    return AnthropicModel(config.model, provider=AnthropicProvider(anthropic_client=client),
        **({'profile':AnthropicModelProfile(supports_auto_cache=True)} if config.cache_mode == '5m' else {}))


def executor_model_settings(config):
    settings = {'max_tokens':config.max_output_tokens,'parallel_tool_calls':False}
    if config.cache_mode == '5m':
        settings.update(anthropic_cache='5m',anthropic_cache_instructions='5m',anthropic_cache_tool_definitions='5m')
    return settings


def validate_usage(usage, raw, *, fixture=False):
    names = ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','cache_write_1h_tokens')
    values = {name:getattr(usage,name,None) for name in names}
    if any(type(value) is not int or value < 0 for value in values.values()):
        raise AdmissionError('usage_unavailable')
    if (values['cache_read_tokens']+values['cache_write_tokens'] > values['input_tokens']
            or values['cache_write_1h_tokens'] or getattr(usage,'unmeasured_requests',0)
            or any(getattr(usage,name,0) for name in ('input_audio_tokens','cache_audio_read_tokens','output_audio_tokens','audio_seconds'))
            or getattr(usage,'output_reasoning_tokens',0) > values['output_tokens']):
        raise AdmissionError('unsupported_usage_buckets')
    if not fixture:
        raw = raw if raw is not None else getattr(usage,'details',None)
        if not isinstance(raw,dict):
            raise AdmissionError('wire_usage_unavailable')
        raw_values = {name:raw.get(name,0) for name in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens')}
        if (not {'input_tokens','output_tokens'} <= raw.keys()
                or any(type(value) is not int or value < 0 for value in raw_values.values())
                or values['input_tokens'] != raw_values['input_tokens']+raw_values['cache_read_input_tokens']+raw_values['cache_creation_input_tokens']
                or values['output_tokens'] != raw_values['output_tokens']
                or values['cache_read_tokens'] != raw_values['cache_read_input_tokens']
                or values['cache_write_tokens'] != raw_values['cache_creation_input_tokens']):
            raise AdmissionError('wire_usage_bucket_binding_differs')
        creation = raw.get('cache_creation')
        if creation is not None:
            if (not isinstance(creation,dict) or set(creation)-{'ephemeral_5m_input_tokens','ephemeral_1h_input_tokens'}
                    or any(type(value) is not int or value < 0 for value in creation.values())
                    or creation.get('ephemeral_1h_input_tokens',0)
                    or sum(creation.values()) != values['cache_write_tokens']):
                raise AdmissionError('unsupported_cache_write_split')
        if 'ephemeral_5m_input_tokens' in raw or 'ephemeral_1h_input_tokens' in raw:
            split = [raw.get(name,0) for name in ('ephemeral_5m_input_tokens','ephemeral_1h_input_tokens')]
            if any(type(value) is not int or value < 0 for value in split) or split[1] or sum(split) != values['cache_write_tokens']:
                raise AdmissionError('unsupported_cache_write_split')
        if any(raw.get(name,0) for name in ('ephemeral_1h_input_tokens','web_search_requests','compaction_input_tokens','compaction_output_tokens','compaction_cache_creation_input_tokens','compaction_cache_read_input_tokens')):
            raise AdmissionError('unsupported_usage_charge')
    return {name:values[name] for name in names[2:]}


def instrument_model(model, runtime):
    from pydantic_ai.models.wrapper import WrapperModel
    from pydantic_ai.messages import ModelMessagesTypeAdapter

    class InstrumentedModel(WrapperModel):
        async def request(self, messages, model_settings, model_request_parameters):
            runtime.tools.assert_context()
            # This is the actual supported Model.request call boundary. Retain
            # the full submitted messages, schemas/settings and page references;
            # prompt assembly or tool reads alone never grant delivery coverage.
            message_values = ModelMessagesTypeAdapter.dump_python(messages, mode='json')
            payload = {'messages': message_values, 'settings': model_settings,
                       'parameters': _jsonable(asdict(model_request_parameters))}
            raw = canonical(payload)
            artifact = runtime.tools.persist(raw, required=False)
            pages = runtime.request_pages(message_values)
            # UTF-8 bytes bound input tokens conservatively (including schemas),
            # plus fixed framing overhead; unsupported oversized contexts refuse.
            input_bound = len(raw) + 4096
            bound = runtime.admission.reserve(input_bound)
            rid = str(uuid4())
            runtime.requests.add(rid)
            from pydantic_ai.models.function import FunctionModel
            fixture = isinstance(self.wrapped, FunctionModel)
            runtime.input_bound = input_bound
            runtime.active_request = rid
            runtime.wire_pages = None
            runtime.response_facts = None
            runtime.response_usage = None
            runtime.journal.append(ModelRequest(request_id=rid, transport='function-test' if fixture else 'anthropic-boundary', messages=artifact,
                payload_sha256=sha256(raw), page_ids=pages, phase=runtime.current_phase(),
                input_token_estimate=input_bound, reserved_maximum_usd=decimal_string(bound)))
            try:
                response = await self.wrapped.request(messages, model_settings, model_request_parameters)
            except BaseException as exc:
                status = 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'error'
                facts = runtime.response_facts or {}
                from anthropic import APIConnectionError, APITimeoutError
                kind = ('cancelled' if status == 'cancelled' else 'timeout' if isinstance(exc, APITimeoutError)
                        else 'connection' if isinstance(exc, APIConnectionError) else 'unknown')
                runtime.journal.append(ModelResponse(request_id=rid, provider_request_id=facts.get('provider_request_id'),
                    model=None, input_tokens=None, output_tokens=None, accounted_cost_usd=None,
                    status=status, finish_reason=None, http_status=facts.get('http_status'),
                    error_kind=facts.get('error_kind') or kind))
                # Request remains outstanding: an error is not proof that the
                # provider did no work. Retain its cost reservation.
                raise
            try:
                usage = response.usage
                if response.failed_attempts or response.state != 'complete' or response.finish_reason in ('length', 'content_filter', 'error'):
                    raise AdmissionError('response_incomplete_or_retried')
                if not fixture and not runtime.config.pricing.accepts(response.model_name):
                    raise AdmissionError('response_model_pricing_binding_differs')
                buckets = validate_usage(usage,runtime.response_usage,fixture=fixture)
                if usage.input_tokens > input_bound or usage.output_tokens > runtime.config.max_output_tokens:
                    raise AdmissionError('usage_exceeds_admitted_token_bounds')
                cost = runtime.admission.reconcile(usage.input_tokens, usage.output_tokens, **buckets)
            except (AttributeError, AdmissionError):
                runtime.journal.append(ModelResponse(request_id=rid,
                    provider_request_id=response.provider_response_id, model=response.model_name,
                    input_tokens=None, output_tokens=None, accounted_cost_usd=None,
                    status='unknown', finish_reason=response.finish_reason))
                raise AdmissionError('usage_unavailable_or_unsupported')
            runtime.journal.append(ModelResponse(request_id=rid,
                provider_request_id=response.provider_response_id, model=response.model_name,
                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                accounted_cost_usd=decimal_string(cost), status='ok', finish_reason=response.finish_reason,
                normal_input_tokens=usage.input_tokens-buckets['cache_read_tokens']-buckets['cache_write_tokens'],
                cost_basis=runtime.config.pricing.cost_basis, **buckets))
            runtime.requests.remove(rid)
            if not fixture and runtime.wire_pages is None:
                raise Refusal('provider_submission_evidence_missing')
            runtime.tools.covered.update(pages if fixture else runtime.wire_pages)
            runtime.tools.parent_request_id = rid
            return response

    return InstrumentedModel(model)


class ExecutorRuntime:
    def __init__(self, config: ExecutorConfig):
        self.config = config
        directory = Path(config.journal_path).parent
        meta = directory.lstat()
        if (meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700
                or not stat.S_ISDIR(meta.st_mode)):
            raise Refusal('journal_directory_not_private')
        if config.supervisor.pid == os.getpid() or identity(config.supervisor.pid) != config.supervisor:
            raise Refusal('supervisor_identity_differs')
        # The supervisor must really be an ancestor, not merely a live process.
        pid = os.getpid()
        for _ in range(64):
            if identity(pid) == config.supervisor:
                break
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            pid = int(fields[1])
            if pid <= 0:
                raise Refusal('supervisor_not_ancestor')
        else:
            raise Refusal('supervisor_not_ancestor')
        self.journal = Journal(Path(config.journal_path), config.run_id, config.attempt_id)
        self.tools = ToolRuntime(config, self.journal)
        self.admission = Admission(config)
        self.requests = set()
        self.active_request = None
        self.wire_pages = None
        self.response_facts = None
        self.response_usage = None

    async def provider_response(self, response):
        await response.aread()
        request_id = response.headers.get('request-id') or response.headers.get('x-request-id')
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', request_id):
            request_id = None
        error_kind = None
        if response.status_code == 200:
            try:
                value = decode(response.content)
                self.response_usage = value.get('usage') if isinstance(value,dict) else None
            except (ValueError,UnicodeError):
                self.response_usage = None
        if response.status_code >= 400:
            try:
                body = decode(response.content)
                error = body.get('error') if isinstance(body, dict) else None
                remote_kind = error.get('type') if isinstance(error, dict) else None
            except (ValueError, UnicodeError):
                remote_kind = None
            error_kind = {'billing_error':'billing', 'rate_limit_error':'rate_limit',
                'authentication_error':'authentication', 'permission_error':'permission',
                'invalid_request_error':'request', 'overloaded_error':'overloaded'}.get(remote_kind, 'unknown')
        self.response_facts = dict(http_status=response.status_code, error_kind=error_kind,
            provider_request_id=request_id)

    async def provider_submission(self, request):
        if self.active_request is None or self.wire_pages is not None:
            raise Refusal('unbound_or_repeated_provider_submission')
        raw = await request.aread()
        if len(raw) + 1024 > self.input_bound:
            raise Refusal('provider_wire_exceeds_admitted_input_bound')
        body = decode(raw)
        if body.get('model') != self.config.model:
            raise Refusal('provider_wire_model_differs')
        if not cache_request_matches(self.config,body):
            raise Refusal('provider_cache_mode_binding_differs')
        pages = self.request_pages(body)
        artifact = self.tools.persist(raw, required=False)
        # Headers (including credentials) are deliberately never persisted.
        self.journal.append(ProviderSubmission(request_id=self.active_request,
            body=artifact, page_ids=pages, endpoint=str(request.url.copy_with(query=None))))
        self.wire_pages = pages

    def current_phase(self):
        for phase in ('identity', 'config', 'memory', 'tasks', 'review', 'discovery', 'authority',
                      'campaign_list', 'campaign_pending', 'founder'):
            if phase not in self.tools.phases:
                return phase
        return 'execution'

    def request_pages(self, value):
        found = []
        def visit(item):
            if isinstance(item, dict):
                if 'executor_page' in item:
                    page = item['executor_page']
                    pid = page.get('page_id') if isinstance(page, dict) else None
                    expected = self.tools.pages.get(pid)
                    if expected is None or item != expected:
                        raise Refusal('foreign_or_modified_request_page')
                    if pid not in found:
                        found.append(pid)
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
            elif isinstance(item, str) and item.lstrip().startswith('{'):
                # Bootstrap is an actual user-message string supplied below;
                # parse only this infrastructure envelope, never arbitrary prose.
                try:
                    nested = decode(item)
                except ValueError:
                    return
                visit(nested)
        visit(value)
        return found

    async def run(self, prompt: str, *, model=None):
        from pydantic_ai import Agent, Tool
        from pydantic_ai.usage import UsageLimits
        from .operator_inventory_view import source_identity
        terminal, diagnostic, completed = 'failed', None, False
        bootstrap = None
        try:
            # Validate/load context before provider initialization or business
            # tools. A start is emitted even when authoritative context fails.
            self.tools.context_hashes = self.tools.context_closure()
            context_digest = sha256(canonical(self.tools.context_hashes))
        except (ValueError, OSError) as exc:
            context_digest = sha256(b'')
            diagnostic = Diagnostic(stage='context', cause=type(exc).__name__, expected='complete authoritative workflow',
                observed=str(exc), run_id=self.config.run_id, tool_id=None)
        executable = Path(sys.executable).resolve()
        raw_interpreter = executable.read_bytes()
        interpreter = Artifact(artifact_id=str(uuid4()), path=str(executable), bytes=len(raw_interpreter), sha256=sha256(raw_interpreter))
        c = self.config
        self.journal.append(RunStart(owner=c.owner, nonce=c.nonce, clone_root=c.clone_root,
            supervisor=c.supervisor, executor=identity(), interpreter=interpreter,
            kernel_version=__import__('cs._version', fromlist=['kernel_version']).kernel_version(), kernel_source_digest=source_identity(),
            executor_module_digest=sha256(Path(__file__).read_bytes()), dependency_version=importlib.metadata.version('pydantic-ai-slim'),
            policy_digest=sha256(canonical(c.model_dump(mode='json'))), context_digest=context_digest,
            provider=c.provider, model=c.model, endpoint=c.base_url, soft_budget_usd=c.soft_budget_usd,
            admitted_ceiling_usd=c.admitted_ceiling_usd, max_requests=c.max_requests,
            max_output_tokens=c.max_output_tokens, deadline_seconds=c.deadline_seconds))
        try:
            if diagnostic:
                raise Refusal('authoritative_context_unavailable')
            if source_identity() != c.kernel_source_digest:
                raise Refusal('kernel_source_identity_differs')
            if c.additional_denied:
                raise Refusal('unsupported_launcher_policy')
            if self.tools.pause():
                raise Refusal('paused')
            bootstrap = self.tools.bootstrap()
            c.remaining_seconds()
            actual_model = build_model(c, self) if model is None else model
            wrapped = instrument_model(actual_model, self)
            tools = [Tool(getattr(self.tools, name), sequential=True, max_retries=0) for name in (
                'run_cs', 'read_context', 'load_workflow', 'read_artifact', 'pause_status')]
            agent = Agent(wrapped, tools=tools, retries=0,
                instructions='Execute the supplied authoritative rendered workflows using the finite typed tools. '
                'Use structured whoami --json, config --json, tasks --json, review --json, then canonical unanswered. '
                'Read standing-instructions --json before effects. Run global campaign list/pending after discovery. '
                'Use read_artifact with byte offsets until every required artifact reaches EOF. '
                'Model completion is separate from workflow, health and acceptance outcomes.',
                model_settings=executor_model_settings(c))
            initial = canonical({'executor_bootstrap': bootstrap, 'operator_prompt': prompt}).decode()
            async with asyncio.timeout(c.remaining_seconds()):
                await agent.run(initial, usage_limits=UsageLimits(request_limit=c.max_requests), retries=0)
            completed = True
            self.tools.effects_allowed(final=True)
            terminal = 'completed'
        except asyncio.TimeoutError:
            terminal = 'timeout'
            diagnostic = Diagnostic(stage='deadline', cause='executor_deadline', expected='completion within deadline', observed='deadline elapsed; child groups reaped', run_id=c.run_id, tool_id=None)
        except asyncio.CancelledError:
            terminal = 'cancelled'
            diagnostic = Diagnostic(stage='cancellation', cause='executor_cancelled', expected='complete workflow', observed='cancelled; child groups reaped', run_id=c.run_id, tool_id=None)
        except AdmissionError as exc:
            terminal = 'capacity' if 'capacity' in str(exc) else 'budget_exhausted'
            diagnostic = Diagnostic(stage='admission', cause=str(exc), expected='known funded request bounds',
                observed='request refused or usage unavailable', run_id=c.run_id, tool_id=None)
        except Exception as exc:
            terminal = 'held' if isinstance(exc, Refusal) else 'failed'
            if diagnostic is None:
                diagnostic = Diagnostic(stage='execution', cause=type(exc).__name__, expected='complete verified workflow',
                    observed=str(exc) if isinstance(exc, Refusal) else type(exc).__name__, run_id=c.run_id, tool_id=None)
        finally:
            for proc in list(self.tools.processes):
                await self.tools._reap(proc)
            if self.tools.poisoned:
                terminal = 'unknown'
            if self.requests and terminal == 'completed':
                terminal = 'unknown'
            self.journal.append(RunEnd(terminal=terminal,
                outstanding_tool_ids=sorted(self.tools.outstanding), outstanding_request_ids=sorted(self.requests),
                phase_outcomes=self.tools.phases, input_tokens=self.admission.input_tokens,
                output_tokens=self.admission.output_tokens, accounted_cost_usd=decimal_string(self.admission.accounted),
                uncertain_cost_usd=decimal_string(self.admission.uncertain), model_completed=completed,
                final_journal_digest=self.journal.digest, diagnostic=diagnostic))
            self.journal.close()
        return terminal


def main(argv=None):
    parser = argparse.ArgumentParser(description='Internal scheduled Python executor')
    parser.add_argument('--config', required=True)
    parser.add_argument('--prompt', required=True)
    args = parser.parse_args(argv)
    try:
        path = Path(args.config)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise Refusal('launch_config_not_private')
            raw = stream.read(262145)
        if len(raw) > 262144:
            raise Refusal('launch_config_capacity')
        config = ExecutorConfig.model_validate(decode(raw))
        async def run():
            task = asyncio.current_task()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, task.cancel)
            return await ExecutorRuntime(config).run(args.prompt)
        terminal = asyncio.run(run())
        return 0 if terminal == 'completed' else 3
    except Exception as exc:
        print('executor startup refused: ' + type(exc).__name__, file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
