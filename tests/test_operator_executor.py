"""Free executor controls; no provider requests or production clone files.

FunctionModel exercises the actual controller boundary, not Anthropic delivery.
The canonical CLI subprocess uses a disposable clone; the sleep/fork handler is
an explicitly substituted test service behind real argparse/module dispatch.
"""
from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from pydantic_ai import models
models.ALLOW_MODEL_REQUESTS = False
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from cs.operator_executor import ExecutorRuntime, instrument_model
from cs.operator_executor_config import ExecutorConfig, Admission, AdmissionError
from cs.operator_executor_protocol import canonical, decode, parse_journal, Record
from cs.operator_executor_tools import (identity, validate_argv, Refusal, DENIED_RPC,
    DENIED, PREFIXES, safe_context_path)
from cs.operator_inventory_view import source_identity

SOURCE = Path(os.environ.get('CS_EXECUTOR_TEST_SOURCE_ROOT')
              or Path(__file__).resolve().parents[1]).resolve()
# Use the environment running the checks, including a clean installed candidate.
CLI_PYTHON = Path(sys.executable)


def launch_config(root, journal, **overrides):
    value = dict(run_id=str(uuid4()), attempt_id=str(uuid4()), nonce=__import__('secrets').token_hex(16),
        owner='fixture-owner', clone_root=str(root), journal_path=str(journal),
        supervisor=identity(os.getppid()).model_dump(), kernel_source_digest=source_identity(),
        model='fixture-model', api_key_env='CS_TEST_EXECUTOR_API_KEY', admitted_ceiling_usd='20',
        pricing=dict(provider='anthropic', model='fixture-model', source='fixture worst-case rates',
            input_upper_usd_per_million='1', output_upper_usd_per_million='1', maximum_context_tokens=1000000),
        max_output_tokens=100, campaign_enabled=False)
    value.update(overrides)
    return ExecutorConfig.model_validate(value)


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'clone'
        self.root.mkdir()
        self.private = self.base / 'private'
        self.private.mkdir(mode=0o700)
        (self.root / '.venv').symlink_to(CLI_PYTHON.parent.parent, target_is_directory=True)
        for relative in ('AGENTS.md', '.claude/skills/cs-operator/SKILL.md',
                         '.claude/skills/cs-triage-mail/SKILL.md', '.claude/skills/cs-campaign-tick/SKILL.md'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Fixture authority: inspect all supplied pages. Ω\n')
        for name in ('operator-out-of-scope', 'triage-domain-examples', 'team-conventions', 'campaign-product-notes'):
            path = self.root / 'company' / (name + '.md')
            path.parent.mkdir(exist_ok=True)
            path.write_text('Fixture required company context.\n')
        self.home = self.base / 'home'
        self.home.mkdir()
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'CS_ENGINE_OWNER_UID': 'fixture-owner',
            'PYTHONPATH': str(SOURCE)}, clear=True)
        self.env.start()
        self.config = launch_config(self.root, self.private / 'journal.jsonl')

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def run_async(self, coro):
        return asyncio.run(coro)

    def runtime(self, **overrides):
        c = self.config.model_copy(update=overrides)
        return ExecutorRuntime(c)

    def test_permission_equivalence_denied_spellings(self):
        count = 0
        for prefix in ((),) + PREFIXES:
            for command in DENIED:
                with self.assertRaises(Refusal):
                    validate_argv(list(prefix) + [command], self.config)
                count += 1
            for method in DENIED_RPC:
                with self.assertRaises(Refusal):
                    validate_argv(list(prefix) + ['rpc', method, '{}'], self.config)
                count += 1
            for argv in (['campaign', 'send-draft', 'id'], ['connection', 'vonage', 'provision'],
                         ['connection', 'vonage', 'allow-ip'], ['assignment', 'preview'],
                         ['assignment', 'export'], ['assignment', 'commit'], ['draft-send', 'id']):
                with self.assertRaises(Refusal):
                    validate_argv(list(prefix) + argv, self.config)
                count += 1
        self.assertGreater(count, 200)
        for argv in (['rpc','settings.get_secret','{}'], ['rpc','emails.list_by_thread','{"thread_id":"t","owner":"x"}'],
                     ['catchup'], ['whoami','--account','foreign'], ['whoami','&&','rm'],
                     ['python','evil.py'], ['git','push']):
            with self.assertRaises(Refusal):
                validate_argv(argv, self.config)
        self.assertEqual(validate_argv(['cs','catchup','--check'], self.config)[0], ['catchup','--check'])
        self.assertFalse(validate_argv(['rpc','tasks.list','{"include_completed":true}'], self.config)[1])

    def test_secrets_symlinks_and_traversal(self):
        for relative in ('../AGENTS.md', '/etc/passwd', '.env', 'manifest.toml', 'company/secret.md'):
            with self.assertRaises(Refusal):
                safe_context_path(self.root, relative)
        (self.root / 'company').mkdir(exist_ok=True)
        (self.root / 'company/escape.md').symlink_to(self.root / 'AGENTS.md')
        with self.assertRaises(Refusal):
            safe_context_path(self.root, 'company/escape.md')

    def test_document_relative_context_links_keep_read_boundaries(self):
        docs=self.root/'docs'
        docs.mkdir()
        (self.root/'AGENTS.md').write_text('[Index](docs/index.md)\n')
        index=docs/'index.md'
        index.write_text('[Charter](../AGENTS.md)\n')
        runtime=self.runtime()
        hashes=runtime.tools.context_closure()
        self.assertIn('AGENTS.md',hashes)
        self.assertIn('docs/index.md',hashes)
        self.assertFalse(any('..' in Path(name).parts for name in hashes))
        with self.assertRaisesRegex(Refusal,'context_path_outside_scope'):
            safe_context_path(self.root,'docs/../AGENTS.md')
        outside=self.base/'outside.md'
        outside.write_text('Outside clone authority.\n')
        (self.root/'company/secret.md').write_text('Excluded fixture.\n')
        (self.root/'company/escape.md').symlink_to(outside)
        index.write_text('[External](../../outside.md)\n[Charter](../AGENTS.md)\n')
        with patch('cs.operator_executor_tools.read_context_bytes',wraps=__import__('cs.operator_executor_tools',fromlist=['read_context_bytes']).read_context_bytes) as read:
            hashes=runtime.tools.context_closure()
        self.assertNotIn('../outside.md',hashes)
        self.assertFalse(any('outside.md' in call.args[1] for call in read.call_args_list))
        for link,cause in [('../company/secret.md','context_path_secret_or_unsupported'),
                           ('../company/escape.md','context_path_symlink_or_missing')]:
            with self.subTest(link=link):
                index.write_text('[Target]('+link+')\n')
                with self.assertRaisesRegex(Refusal,cause):
                    runtime.tools.context_closure()
        runtime.journal.close()

    def test_campaign_context_documents_keep_read_boundaries(self):
        campaigns=self.root/'campaigns'
        campaigns.mkdir()
        public=campaigns/'public.md'
        public.write_text('Public campaign workflow authority.\n')
        (self.root/'AGENTS.md').write_text('[Campaign](campaigns/public.md)\n')
        runtime=self.runtime()
        self.assertIn('campaigns/public.md',runtime.tools.context_closure())
        outside=self.base/'outside.md'
        outside.write_text('Outside clone authority.\n')
        (campaigns/'secret.md').write_text('Excluded fixture.\n')
        (self.root/'AGENTS.md').write_text('[External](campaigns/../../outside.md)\n')
        self.assertNotIn('../outside.md',runtime.tools.context_closure())
        with self.assertRaisesRegex(Refusal,'context_path_outside_scope'):
            safe_context_path(self.root,'campaigns/../../outside.md')
        for link,cause in [('campaigns/secret.md','context_path_secret_or_unsupported')]:
            with self.subTest(link=link):
                (self.root/'AGENTS.md').write_text('[Target]('+link+')\n')
                with self.assertRaisesRegex(Refusal,cause):
                    runtime.tools.context_closure()
        runtime.journal.close()

    def test_actual_function_model_loop_and_cli_subprocess(self):
        async def function(messages, info):
            if not any(part.part_kind == 'tool-return' for m in messages for part in m.parts):
                return ModelResponse(parts=[ToolCallPart('run_cs', {'argv': ['--version']}, tool_call_id='fixture')])
            return ModelResponse(parts=[TextPart('Fixture complete')])
        runtime = self.runtime()
        self.assertEqual(self.run_async(runtime.run('Inspect fixture', model=FunctionModel(function))), 'held')
        records = parse_journal(Path(self.config.journal_path))
        events = [r.payload for r in records]
        self.assertTrue(any(r.kind == 'tool_spawn' for r in events))
        ends = [r for r in events if r.kind == 'tool_end']
        self.assertEqual(ends[0].exit_code, 0, Path(ends[0].stderr.path).read_text()[:1000])
        self.assertIn(b'cs-kernel', Path(ends[0].stdout.path).read_bytes())
        requests = [r for r in events if r.kind == 'model_request']
        self.assertTrue(all(r.transport == 'function-test' for r in requests))
        self.assertGreater(len(requests[0].page_ids), 0)
        self.assertEqual(events[-1].acceptance, 'unassessed')
        self.assertTrue(events[-1].model_completed)
        self.assertEqual(events[-1].terminal, 'held')

    def test_denial_has_no_spawn_and_context_change_invalidates(self):
        runtime = self.runtime()
        runtime.tools.bootstrap()
        result = self.run_async(runtime.tools.run_cs(['draft-send', 'full-id']))
        self.assertEqual(result['status'], 'denied')
        (self.root / 'AGENTS.md').write_text('Changed authority')
        result = self.run_async(runtime.tools.run_cs(['--version']))
        self.assertEqual(result['cause'], 'authoritative_context_changed')
        runtime.journal.close()
        events = [decode(r)['payload'] for r in Path(self.config.journal_path).read_bytes().splitlines()]
        self.assertFalse(any(r['kind'] == 'tool_spawn' for r in events))

    def test_exact_paging_partial_and_oversize(self):
        runtime = self.runtime(page_bytes=5, max_artifact_bytes=40)
        artifact = runtime.tools.persist('Ωoriginal body\n'.encode())
        split = [runtime.tools.page(artifact.artifact_id, offset, 1) for offset in (0, 1)]
        self.assertTrue(all(page['executor_page']['decoding'] == 'base64' for page in split))
        self.assertEqual(b''.join(__import__('base64').b64decode(page['content']) for page in split), 'Ω'.encode())
        p1 = runtime.tools.page(artifact.artifact_id, 0, 5)
        runtime.tools.covered.add(p1['executor_page']['page_id'])
        self.assertFalse(runtime.tools.full_coverage(artifact.artifact_id))
        for offset in range(5, artifact.bytes, 5):
            page = runtime.tools.page(artifact.artifact_id, offset, 5)
            runtime.tools.covered.add(page['executor_page']['page_id'])
        self.assertTrue(runtime.tools.full_coverage(artifact.artifact_id))
        foreign = copy.deepcopy(p1)
        foreign['content'] = 'forged'
        with self.assertRaises(Refusal):
            runtime.request_pages(foreign)
        large = runtime.tools.persist(b'x' * 41)
        with self.assertRaises(Refusal):
            runtime.tools.page(large.artifact_id, 0, 5)
        self.assertEqual(Path(large.path).read_bytes(), b'x' * 41)
        runtime.journal.close()

    def test_separate_soft_and_admitted_bounds_unknown_cost(self):
        config = self.config.model_copy(update={'soft_budget_usd': '0.00001', 'admitted_ceiling_usd': '1'})
        admission = Admission(config)
        bound = admission.reserve(10)
        self.assertGreater(bound, 0)
        admission.reconcile(10, 10)
        with self.assertRaisesRegex(AdmissionError, 'soft_target'):
            admission.reserve(10)
        admission = Admission(config.model_copy(update={'admitted_ceiling_usd': '0.000001'}))
        with self.assertRaisesRegex(AdmissionError, 'admitted_ceiling'):
            admission.reserve(10)
        admission = Admission(self.config)
        admission.reserve(100)
        with self.assertRaisesRegex(AdmissionError, 'unknown_previous_cost'):
            admission.reserve(100)

    def test_first_phase_failure_survives_later_admission_refusal(self):
        from decimal import Decimal
        cases = (('context_capacity', True), ('admitted_ceiling', True), ('context_capacity', False))
        for index, (cause, prior_failure) in enumerate(cases):
            with self.subTest(cause=cause, prior_failure=prior_failure):
                overrides = dict(journal_path=str(self.private / f'diagnostic-{index}.jsonl'))
                if cause == 'context_capacity':
                    overrides['pricing'] = self.config.pricing.model_copy(update={'maximum_context_tokens': 100})
                else:
                    overrides['admitted_ceiling_usd'] = '0.000001'
                runtime = self.runtime(**overrides)
                tool_id = str(uuid4())
                original_bootstrap = runtime.tools.bootstrap
                def bootstrap():
                    pages = original_bootstrap()
                    if prior_failure:
                        runtime.tools.parent_request_id = str(uuid4())
                        runtime.tools.inventory_artifacts = [str(uuid4())]
                        os.environ['CS_OPERATOR_HEALTH_CONTEXT'] = '{}'
                        with patch('cs.operator_health.assess', return_value='discovery_inventory_missing'):
                            runtime.tools.complete_phase(['unanswered','--days','14','--json','--all-buckets'], tool_id, 3, b'{}')
                        runtime.tools.complete_phase(['tasks','--json'], str(uuid4()), 1, b'[]')
                    return pages
                async def sentinel(messages, info):
                    self.fail('refused request reached wrapped model')
                with patch.object(runtime.tools, 'bootstrap', side_effect=bootstrap):
                    terminal = self.run_async(runtime.run('Fixture refusal', model=FunctionModel(sentinel)))
                self.assertEqual(terminal, 'capacity' if cause == 'context_capacity' else 'budget_exhausted')
                parse_journal(Path(runtime.config.journal_path))
                raw_rows = [decode(raw) for raw in Path(runtime.config.journal_path).read_bytes().splitlines()]
                end = raw_rows[-1]['payload']
                diagnostic = end['diagnostic']
                self.assertEqual((diagnostic['stage'], diagnostic['cause']), ('admission', cause))
                observed = decode(diagnostic['observed'])
                self.assertEqual(observed['schema'], 'cs.executor.diagnostic.v1')
                if prior_failure:
                    self.assertEqual(observed['first_failure'], dict(phase='discovery', cause='discovery_inventory_missing',
                        tool_id=tool_id, run_id=runtime.config.run_id))
                    self.assertEqual(end['phase_outcomes']['discovery'], 'held')
                else:
                    self.assertNotIn('first_failure', observed)
                failure = observed['terminal_failure']
                self.assertFalse(failure['refused_request_submitted'])
                artifact = failure['rejected_history_artifact']
                self.assertEqual(len(Path(artifact['path']).read_bytes()), artifact['bytes'])
                self.assertEqual(artifact, runtime.tools.artifacts[artifact['artifact_id']].model_dump())
                if cause == 'context_capacity':
                    self.assertEqual(failure['required_bound'], artifact['bytes'] + 4096 + runtime.config.max_output_tokens)
                    self.assertEqual(failure['available_bound'], 100)
                    self.assertEqual(failure['bound_unit'], 'conservative_token_upper_bound')
                else:
                    self.assertNotIn('required_bound', failure)
                self.assertEqual((runtime.admission.requests, runtime.admission.uncertain), (0, Decimal(0)))
                self.assertEqual(runtime.requests, set())
                self.assertFalse(any(row['payload']['kind'] in ('model_request','provider_submission') for row in raw_rows))

    def test_discovery_technical_failure_stops_controller_and_latched_boundaries(self):
        self.install_services()
        site = self.base / 'fixture-services/sitecustomize.py'
        site.write_text(site.read_text().replace("'human_work':[]", "'human_work':[{'thread_key':'<fixture@fixture.test>','assignment':{'actor_uid':'fixture-owner','source_owner_uid':'fixture-owner','complete':False,'state':'unknown','hold_auto_reply':True,'reason':'SOURCE_UNAVAILABLE'}}]").replace("'assignment_incomplete':False", "'assignment_incomplete':True").replace('operator_health.capture(raw,value,0,settings.engine_owner_uid)', 'operator_health.capture(raw,value,3,settings.engine_owner_uid)').replace('return 0\nunanswered.scheduled_command', 'return 3\nunanswered.scheduled_command'))
        runtime = self.runtime()
        queue = [['whoami','--json'], ['config','--json'], ['tasks','--json'], ['review','--json'],
                 ['unanswered','--days','14','--json','--all-buckets']]
        calls = []
        async def sentinel(messages, info):
            self.assertFalse(runtime.tools.discovery_failed, 'model invoked after technical discovery failure')
            calls.append(1)
            self.assertTrue(queue, 'unexpected model continuation')
            return ModelResponse(parts=[ToolCallPart('run_cs', {'argv':queue.pop(0)}, tool_call_id='fixture-' + str(len(calls)))])
        terminal = self.run_async(runtime.run('Technical discovery failure', model=FunctionModel(sentinel)))
        self.assertEqual(terminal, 'held', Path(runtime.config.journal_path).read_text()[-3000:])
        rows = [r.payload for r in parse_journal(Path(runtime.config.journal_path))]
        end = rows[-1]
        self.assertEqual(end.phase_outcomes['discovery'], 'held')
        self.assertFalse(end.model_completed)
        self.assertEqual((end.outstanding_tool_ids, end.outstanding_request_ids), ([], []))
        self.assertEqual((len(calls), runtime.admission.requests), (5, 5))
        self.assertEqual((runtime.admission.uncertain, runtime.tools.processes), (0, set()))
        phase = next(r for r in rows if r.kind == 'phase' and r.name == 'discovery')
        failure = decode(end.diagnostic.observed)
        self.assertEqual(failure['first_failure'], dict(phase='discovery', cause='assignment_read_incomplete', tool_id=phase.tool_ids[0], run_id=runtime.config.run_id))
        self.assertEqual(failure['terminal_failure']['reason'], 'assignment_read_incomplete')
        before = (runtime.admission.requests, runtime.admission.uncertain, runtime.admission.accounted)
        from pydantic_ai.models import ModelRequestParameters
        with self.assertRaisesRegex(Refusal, 'assignment_read_incomplete'):
            self.run_async(instrument_model(FunctionModel(sentinel), runtime).request([], {}, ModelRequestParameters()))
        with self.assertRaisesRegex(Refusal, 'assignment_read_incomplete'):
            runtime.tools.effects_allowed()
        self.assertEqual(before, (runtime.admission.requests, runtime.admission.uncertain, runtime.admission.accounted))
        self.assertFalse(any(r.kind == 'tool_end' and r.effect for r in rows))
        for row in rows:
            if row.kind == 'tool_spawn':
                self.assertFalse(Path(f'/proc/{row.child.pid}').exists())

    def test_discovery_fail_fast_requires_normal_command_and_phase_joins(self):
        argv = ['unanswered','--days','14','--json','--all-buckets']
        for index, mode in enumerate(('tool', 'argv', 'exit', 'stdout', 'prerequisite', 'unsupported_exit', 'request', 'inventory', 'payload_exit')):
            with self.subTest(mode=mode):
                runtime = self.runtime(journal_path=str(self.private / f'join-{index}.jsonl'))
                tool_id = str(uuid4())
                runtime.tools.parent_request_id = str(uuid4())
                runtime.tools.inventory_artifacts = [str(uuid4())]
                runtime.tools.phases['review'] = 'completed'
                row = dict(tool_id=tool_id, argv=argv, exit_code=3, stdout=b'{"assignment_incomplete":true}')
                code = 3
                if mode == 'tool': row['tool_id'] = str(uuid4())
                if mode == 'argv': row['argv'] = ['tasks','--json']
                if mode == 'exit': row['exit_code'] = 0
                if mode == 'stdout': row['stdout'] = b'[]'
                if mode == 'prerequisite': runtime.tools.phases['review'] = 'held'
                if mode == 'unsupported_exit': code = row['exit_code'] = 1
                if mode == 'request': runtime.tools.parent_request_id = None
                if mode == 'inventory': runtime.tools.inventory_artifacts = []
                if mode == 'payload_exit': code = row['exit_code'] = 0
                runtime.tools.command_results.append(row)
                os.environ['CS_OPERATOR_HEALTH_CONTEXT'] = '{}'
                with patch('cs.operator_health.assess', return_value='assignment_read_incomplete'):
                    runtime.tools.complete_phase(argv, tool_id, code, b'{"assignment_incomplete":true}')
                self.assertFalse(runtime.tools.discovery_failed)
                runtime.journal.close()

    def test_runtime_refusal_reason_uses_only_known_codes(self):
        for index, (message, reason) in enumerate((
            ('customer_secret_value', None),
            ('customer_secret_value:private details', None),
            ('required_workflow_context_missing:company/private-context.md', 'required_workflow_context_missing'),
        )):
            with self.subTest(reason=reason):
                runtime = self.runtime(journal_path=str(self.private / f'reason-{index}.jsonl'))
                async def sentinel(messages, info):
                    self.fail('bootstrap refusal reached wrapped model')
                with patch.object(runtime.tools, 'bootstrap', side_effect=Refusal(message)):
                    terminal = self.run_async(runtime.run('Fixture reason control', model=FunctionModel(sentinel)))
                self.assertEqual(terminal, 'held')
                diagnostic = parse_journal(Path(runtime.config.journal_path))[-1].payload.diagnostic
                self.assertEqual((diagnostic.stage, diagnostic.cause), ('execution', 'Refusal'))
                failure = decode(diagnostic.observed)['terminal_failure']
                self.assertEqual(failure.get('reason'), reason)
                self.assertNotIn('customer_secret_value', diagnostic.observed)
                self.assertNotIn('private details', diagnostic.observed)
                self.assertNotIn('company/private-context.md', diagnostic.observed)
                self.assertEqual((runtime.admission.requests, runtime.admission.uncertain), (0, 0))

    def test_phase_failure_cause_controls(self):
        for index, (argv, code, raw, cause) in enumerate((
            (['tasks','--json'], 1, b'[]', 'phase_exit_nonzero'),
            (['tasks','--json'], 0, b'[]', 'phase_prerequisite_incomplete'),
            (['tasks','--json'], 0, b'{', 'phase_response_invalid'),
        )):
            with self.subTest(cause=cause):
                runtime = self.runtime(journal_path=str(self.private / f'phase-{index}.jsonl'))
                runtime.tools.parent_request_id = str(uuid4())
                runtime.tools.complete_phase(argv, str(uuid4()), code, raw)
                self.assertEqual(runtime.tools.first_failure['cause'], cause)
                self.assertEqual(runtime.tools.phases['tasks'], 'held')
                runtime.journal.close()

    def test_real_module_startup_holds_without_credentials(self):
        path = self.private / 'config.json'
        path.write_bytes(canonical(self.config.model_dump(mode='json')))
        path.chmod(0o600)
        result = subprocess.run([sys.executable, '-m', 'cs.operator_executor', '--config', str(path),
            '--prompt', 'Fixture only'], env=dict(os.environ), capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 3)
        terminal = parse_journal(Path(self.config.journal_path))[-1].payload
        self.assertEqual(terminal.terminal, 'held')
        self.assertIn('executor_credential_unavailable', terminal.diagnostic.observed)

    def test_cancellation_reaps_cli_process_group(self):
        fixture = self.base / 'fixture-services'
        fixture.mkdir()
        marker = self.base / 'spawned.json'
        # Explicit service substitution only: the actual kernel module and its
        # argparse dispatcher select the ask handler. No fake cs package exists.
        (fixture / 'sitecustomize.py').write_text(
            'import cs.cli, os, time, subprocess, sys, json\n'
            'def fixture_ask(args):\n'
            ' child = subprocess.Popen([sys.executable,"-c","import time; time.sleep(90)"])\n'
            ' open(os.environ["FIXTURE_PROCESS_MARKER"],"w").write(json.dumps([os.getpid(),child.pid]))\n'
            ' time.sleep(90)\n'
            ' return 0\n'
            'cs.cli.cmd_ask = fixture_ask\n')
        os.environ['PYTHONPATH'] = str(fixture) + os.pathsep + str(SOURCE)
        os.environ['FIXTURE_PROCESS_MARKER'] = str(marker)
        runtime = self.runtime()
        async def control():
            task = asyncio.create_task(runtime.tools.run_cs(['ask', 'fixture sleep']))
            for _ in range(200):
                if marker.exists():
                    break
                await asyncio.sleep(.02)
            self.assertTrue(marker.exists(), 'fixture CLI did not reach real ask dispatch')
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.run_async(control())
        pids = json.loads(marker.read_text())
        for pid in pids:
            path = Path(f'/proc/{pid}/stat')
            if path.exists():
                # A reparented zombie is terminated, never a running process.
                self.assertEqual(path.read_text().rsplit(')', 1)[1].split()[0], 'Z')
        runtime.journal.close()
        rows = [decode(r)['payload'] for r in Path(self.config.journal_path).read_bytes().splitlines()]
        self.assertEqual([r for r in rows if r['kind'] == 'tool_end'][-1]['status'], 'cancelled')
        self.assertEqual(len([r for r in rows if r['kind'] == 'tool_spawn']), 1)

    def test_sdk_wire_serialization_unicode_pages_without_network(self):
        import httpx2
        from anthropic import AsyncAnthropic
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        from pydantic_ai.models import ModelRequestParameters
        from pydantic_ai.messages import ModelRequest as PAIRequest, UserPromptPart
        runtime = self.runtime()
        pages = runtime.tools.bootstrap()
        runtime.active_request, runtime.conservative_input_bound = str(uuid4()), 1000000
        bodies = []
        async def transport(request):
            bodies.append(bytes(request.content))
            return httpx2.Response(200, json={'id':'fixture-response', 'type':'message',
                'role':'assistant', 'model':'fixture-model', 'content':[{'type':'text','text':'done'}],
                'stop_reason':'end_turn', 'usage':{'input_tokens':10,'output_tokens':1}})
        async def control():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(transport),
                    event_hooks={'request':[runtime.provider_submission]}) as http:
                client = AsyncAnthropic(api_key='fixture-nonsecret', http_client=http, max_retries=0,
                                        base_url='https://fixture.invalid')
                model = AnthropicModel('fixture-model', provider=AnthropicProvider(anthropic_client=client))
                messages = [PAIRequest(parts=[UserPromptPart(canonical({'executor_bootstrap':pages}).decode())])]
                settings, params = model.prepare_request({'max_tokens':100}, ModelRequestParameters())
                # Version-pinned serialization helper, not Model.request; global
                # ALLOW_MODEL_REQUESTS remains False. The SDK transport is fully
                # in-memory, and no network/provider route is available here.
                prepared = await model._prepare_messages_create(messages, settings, params)
                await client.beta.messages.create(model='fixture-model', max_tokens=100,
                                                  messages=prepared.anthropic_messages)
                self.assertEqual(set(runtime.wire_pages), {p['executor_page']['page_id'] for p in pages})
                self.assertEqual(runtime.tools.covered, set(), 'serialization alone grants no coverage')
                bad = copy.deepcopy(pages[0]); bad['content'] = 'changed'
                request = httpx2.Request('POST', 'https://fixture.invalid/v1/messages',
                    json={'model':'fixture-model','messages':[{'role':'user','content':canonical(bad).decode()}]})
                runtime.wire_pages = None
                with self.assertRaises(Refusal):
                    await runtime.provider_submission(request)
        self.run_async(control())
        self.assertEqual(len(bodies), 1)
        runtime.journal.close()
        journal = Path(self.config.journal_path).read_bytes()
        self.assertNotIn(b'fixture-nonsecret', journal)
        rows = [decode(r)['payload'] for r in journal.splitlines()]
        submission = next(r for r in rows if r['kind'] == 'provider_submission')
        self.assertEqual(Path(submission['body']['path']).read_bytes(), bodies[0])

    def install_services(self, *, fail_effect=False):
        fixture = self.base / 'fixture-services'
        fixture.mkdir(exist_ok=True)
        review = {'gmail_drafts': [], 'engine_drafts': [], 'drafts': [],
            'gmail_drafts_observation': {'version':1, 'complete':True, 'search_complete':True,
                'expected_uids':[], 'observed_uids':[], 'uidvalidity':'1'},
            'drafts_inventory': {'version':1, 'complete':True, 'gmail_count':0, 'engine_count':0,
                'row_count':0, 'identity_sha256':__import__('hashlib').sha256(b'[]').hexdigest()}}
        code = '''import json, os, sys, hashlib
import cs.cli as cli
from cs import config, operator_health, operator_workset, unanswered, review, campaign, standing_instructions
REVIEW = __REVIEW__
def call(settings, method, params=None, **kw):
 if method == 'tasks.list': return []
 if method == 'account.who_am_i': return dict(signed_in=True,uid=settings.engine_owner_uid,email=settings.email_address)
 raise RuntimeError('unexpected fixture RPC '+method)
cli.rpc.call_sync = call
async def chat(settings, message, **kw):
 assert kw.get('read_only') is True and kw.get('allow_tools') == set()
 return {'result':{'response':'Fixture founder read-only list.'}}
cli.rpc.chat = chat
review.gather = lambda settings: REVIEW
campaign.list_campaigns = lambda settings: []
campaign.pending = lambda settings, **kw: {'campaigns':[]}
def instructions(settings, **kw):
 docs=[]
 for path in ('procedures.md', 'mail/'+settings.email_address+'.md'):
  text='Fixture published current rule.'
  docs.append(dict(path=path,revision=1,text=text,sha256=hashlib.sha256(text.encode()).hexdigest()))
 return dict(authority='managed',space_id='fixture-space',mailbox=settings.email_address,documents=docs)
standing_instructions.read = instructions
def discovery():
 settings = config.load()
 value = {'open':[], 'resumed':[], 'automatic':[], 'courtesy':[], 'handled':[], 'escalated':[], 'human_work':[], 'assignment_audit':[], 'operational_fixture_discovery':[], 'read_incomplete':None, 'assignment_incomplete':False}
 value['triage_workset'] = operator_workset.reserve(settings, value)
 raw = (json.dumps(value,ensure_ascii=False,indent=2)+'\\n').encode()
 operator_health.capture(raw,value,0,settings.engine_owner_uid)
 print(raw.decode(),end='')
 return 0
unanswered.scheduled_command = discovery
def effect(args):
 with open(os.environ['FIXTURE_EFFECT_COUNT'],'a') as out: out.write('attempt\\n')
 if os.environ.get('FIXTURE_EFFECT_FAIL'): return 3
 import time
 time.sleep(90)
 return 0
cli.cmd_tasks_create = effect
'''.replace('__REVIEW__', repr(review))
        (fixture / 'sitecustomize.py').write_text(code)
        os.environ['PYTHONPATH'] = str(fixture) + os.pathsep + str(SOURCE)
        os.environ['EMAIL_ADDRESS'] = 'owner@fixture.test'
        os.environ['CS_OPERATOR_HEADLESS'] = '1'
        os.environ['CS_OPERATOR_HEALTH_CONTEXT'] = json.dumps(dict(directory=str(self.private),
            nonce=self.config.nonce, owner_uid=self.config.owner, supervisor=self.config.supervisor.model_dump(), workset_enabled=True))
        os.environ['FIXTURE_EFFECT_COUNT'] = str(self.base / 'effects.txt')
        if fail_effect:
            os.environ['FIXTURE_EFFECT_FAIL'] = '1'

    def exercise_full_controller(self, effect_mode=None, founder=False):
        import httpx2
        from anthropic import AsyncAnthropic
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        self.install_services(fail_effect=effect_mode == 'failed')
        overrides = dict(campaign_enabled=True, tool_timeout_seconds=1 if effect_mode == 'timeout' else 2730)
        if founder:
            os.environ.update(FOUNDER_SWEEP_ENABLED='true', FOUNDER_SWEEP_ACCOUNT='founder', CS_ACCOUNTS='founder:fixture-founder')
            overrides.update(founder_enabled=True, founder_account='founder', founder_question='List fixture mailbox')
            path=self.root/'.claude/skills/cs-operator/SKILL.md'
            path.write_text(path.read_text()+'\n--account founder ask "List fixture mailbox"\n')
        runtime = self.runtime(**overrides)
        queue = [['whoami','--json'], ['config','--json'], ['tasks','--json'], ['review','--json'],
            ['unanswered','--days','14','--json','--all-buckets'], ['standing-instructions','--json'],
            ['campaign','list'], ['campaign','pending']]
        if founder:
            queue += [['--account','founder','tasks','--json'], ['--account','founder','ask','List fixture mailbox']]
        reads = []
        response_count = 0
        effect_count = 0
        async def transport(request):
            nonlocal response_count, effect_count
            body = decode(request.content)
            # Model-independent fake service supplies the next finite tool call;
            # production Agent/AnthropicModel/SDK/body hook/response code runs.
            def scan(value):
                if isinstance(value, dict):
                    for art in value.get('required_inventory_artifacts', []):
                        if art['artifact_id'] not in {a[0] for a in reads}:
                            reads.append((art['artifact_id'], art['bytes']))
                    for item in value.values(): scan(item)
                elif isinstance(value, list):
                    for item in value: scan(item)
                elif isinstance(value, str) and value.startswith('{'):
                    try: scan(decode(value))
                    except ValueError: pass
            scan(body)
            if queue:
                content = [{'type':'tool_use','id':'fixture-'+str(response_count), 'name':'run_cs','input':{'argv':queue.pop(0)}}]
            elif reads:
                aid, size = reads.pop(0)
                content = [{'type':'tool_use','id':'fixture-'+str(response_count),'name':'read_artifact',
                    'input':{'artifact_id':aid,'offset':0,'length':16384}}]
                # Avoid re-adding completed refs from historical tool results.
                seen.add(aid)
            elif effect_mode and effect_count < 2:
                effect_count += 1
                content = [{'type':'tool_use','id':'fixture-effect-'+str(effect_count),'name':'run_cs','input':{'argv':
                    ['tasks','create','--email','contact@fixture.test','--title','Fixture','--event-id','fixture-'+str(effect_count)]}}]
            else:
                content = [{'type':'text','text':'Complete fixture workflow'}]
            response_count += 1
            return httpx2.Response(200, json={'id':'fixture-response-'+str(response_count), 'type':'message',
                'role':'assistant','model':'fixture-model','content':content,
                'stop_reason':'tool_use' if content[0]['type']=='tool_use' else 'end_turn',
                'usage':{'input_tokens':100,'output_tokens':10}})
        seen = set()
        # Alter scan dedup via a minimal list wrapper that remembers references.
        class ReadQueue(list):
            def append(self, item):
                if item[0] not in seen and item not in self: super().append(item)
        reads = ReadQueue()
        async def control():
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(transport),
                    event_hooks={'request':[runtime.provider_submission]}) as http:
                model = AnthropicModel('fixture-model', provider=AnthropicProvider(anthropic_client=
                    AsyncAnthropic(api_key='fixture-nonsecret',http_client=http,max_retries=0,base_url='https://fixture.invalid')))
                # Only this check is bypassed for the in-memory MockTransport.
                # Global ALLOW_MODEL_REQUESTS=False remains set; no real network
                # transport or production endpoint exists in this control.
                with patch('pydantic_ai.models.anthropic.check_allow_model_requests', lambda: None):
                    return await runtime.run('Complete fixture', model=model)
        terminal = self.run_async(control())
        end = parse_journal(Path(self.config.journal_path))[-1].payload
        self.assertEqual(terminal, 'unknown' if effect_mode else 'completed', str(end.diagnostic) + ' phases=' + str(end.phase_outcomes) + ' errors=' + str([Path(r.payload.stderr.path).read_text()[-2000:] for r in parse_journal(Path(self.config.journal_path)) if r.payload.kind == 'tool_end' and r.payload.stderr and r.payload.exit_code not in (0,)] ))
        rows = [r.payload for r in parse_journal(Path(self.config.journal_path))]
        requests = [r for r in rows if r.kind=='model_request']
        submissions = [r for r in rows if r.kind=='provider_submission']
        responses = [r for r in rows if r.kind=='model_response']
        self.assertEqual([r.request_id for r in requests], [r.request_id for r in submissions])
        self.assertEqual([r.request_id for r in requests], [r.request_id for r in responses])
        self.assertEqual(runtime.admission.uncertain, 0)
        self.assertGreater(runtime.admission.accounted, 0)
        raw_ids = set(runtime.tools.material_stdout.values())
        self.assertTrue(raw_ids.isdisjoint(runtime.tools.required))
        self.assertTrue(all(runtime.tools.full_coverage(aid) for aid in runtime.tools.inventory_artifacts))
        self.assertEqual(rows[-1].acceptance, 'unassessed')
        if effect_mode:
            self.assertEqual((self.base/'effects.txt').read_text().splitlines(), ['attempt'])
            effects = [r for r in rows if r.kind == 'tool_end' and r.effect]
            self.assertEqual(len(effects), 1)
            self.assertTrue(effects[0].unknown_effect)
            self.assertEqual(effects[0].status, 'timeout' if effect_mode == 'timeout' else 'error')
            self.assertIsNotNone(rows[-1].diagnostic)
            self.assertEqual(rows[-1].outstanding_tool_ids, [])

    def test_full_controller_actual_wire_and_no_duplicate_raw_coverage(self):
        self.exercise_full_controller()

    def test_enabled_founder_reads_are_real_and_complete(self):
        self.exercise_full_controller(founder=True)
        end=parse_journal(Path(self.config.journal_path))[-1].payload
        self.assertEqual(end.phase_outcomes['founder_tasks'],'completed')
        self.assertEqual(end.phase_outcomes['founder_mail'],'completed')

    def test_failed_effect_not_retried(self):
        self.exercise_full_controller('failed')

    def test_timed_out_effect_reaped_not_retried(self):
        self.exercise_full_controller('timeout')

    def test_real_controller_failed_or_foreign_wire_grants_no_coverage(self):
        import httpx2
        from anthropic import AsyncAnthropic
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        for mode in ('failed', 'foreign'):
            with self.subTest(mode=mode):
                journal = self.private / (mode+'.jsonl')
                runtime = self.runtime(journal_path=str(journal))
                requests = []
                async def transport(request):
                    requests.append(1)
                    return httpx2.Response(503, json={'type':'error','error':{'type':'overloaded_error','message':'fixture'}})
                async def mutate(request):
                    if mode == 'foreign':
                        raw = await request.aread()
                        self.assertIn(b'Fixture authority', raw)
                        request._content = raw.replace(b'Fixture authority', b'Forged authority', 1)
                async def control():
                    async with httpx2.AsyncClient(transport=httpx2.MockTransport(transport),
                            event_hooks={'request':[mutate, runtime.provider_submission]}) as http:
                        model = AnthropicModel('fixture-model',provider=AnthropicProvider(anthropic_client=
                            AsyncAnthropic(api_key='fixture-nonsecret',http_client=http,max_retries=0,base_url='https://fixture.invalid')))
                        with patch('pydantic_ai.models.anthropic.check_allow_model_requests', lambda: None):
                            return await runtime.run('Fixture failure only',model=model)
                self.assertNotEqual(self.run_async(control()),'completed')
                self.assertEqual(runtime.tools.covered,set())
                self.assertGreater(runtime.admission.uncertain,0)
                self.assertEqual(len(requests),1 if mode=='failed' else 0)
                end = parse_journal(journal)[-1].payload
                self.assertEqual(len(end.outstanding_request_ids),1)

    def test_executor_deadline_has_finite_diagnostic_and_reaps_child(self):
        self.install_services()
        site = self.base/'fixture-services/sitecustomize.py'
        site.write_text(site.read_text() + '\nimport time\ndef sleeping_ask(args):\n open(os.environ["FIXTURE_EFFECT_COUNT"],"w").write("read-started")\n time.sleep(90)\n return 0\ncli.cmd_ask = sleeping_ask\n')
        runtime = self.runtime(deadline_seconds=2)
        async def function(messages, info):
            return ModelResponse(parts=[ToolCallPart('run_cs',{'argv':['ask','fixture sleep']},tool_call_id='fixture')])
        terminal = self.run_async(runtime.run('Fixture deadline',model=FunctionModel(function)))
        self.assertEqual(terminal,'timeout')
        rows = [r.payload for r in parse_journal(Path(self.config.journal_path))]
        self.assertEqual(rows[-1].diagnostic.cause,'executor_deadline')
        self.assertEqual((self.base/'effects.txt').read_text(),'read-started')
        self.assertEqual([r for r in rows if r.kind=='tool_end'][-1].status,'cancelled')
        self.assertEqual(rows[-1].outstanding_tool_ids,[])
        for row in rows:
            if row.kind=='tool_spawn':
                path=Path(f'/proc/{row.child.pid}/stat')
                self.assertFalse(path.exists(),'deadline child was not reaped')

    def test_missing_required_workflow_notes_prevent_effect_spawn(self):
        cases = (
            ('cs-campaign-tick', 'company/campaign-product-notes.md',
             ['campaign','queue-draft','fixture-contact','--commit']),
            ('cs-campaign-tick', 'company/campaign-product-notes.md',
             ['tasks','create','--email','contact@fixture.test','--title','Fixture','--event-id','fixture']),
            ('cs-triage-mail', 'company/team-conventions.md',
             ['tasks','create','--email','contact@fixture.test','--title','Fixture','--event-id','fixture']),
        )
        for index, (workflow, relative, argv) in enumerate(cases):
            with self.subTest(workflow=workflow):
                instruction=self.root/f'.claude/skills/{workflow}/SKILL.md'
                instruction.write_text(instruction.read_text()+f'\nRead `{relative}` before judgement/effects.\n')
                path=self.root/relative
                original=path.read_bytes()
                path.unlink()
                journal=self.private/f'missing-notes-{index}.jsonl'
                runtime=self.runtime(journal_path=str(journal),campaign_enabled=True)
                runtime.tools.bootstrap()
                result=self.run_async(runtime.tools.run_cs(argv))
                self.assertEqual(result['status'],'denied')
                self.assertEqual(result['cause'],'required_workflow_context_missing:'+relative)
                runtime.journal.close()
                rows=[decode(raw)['payload'] for raw in journal.read_bytes().splitlines()]
                self.assertFalse(any(row['kind']=='tool_spawn' for row in rows))
                self.assertTrue(any(row['kind']=='tool_start' and row['decision']=='deny' for row in rows))
                path.write_bytes(original)

    def test_required_notes_delivery_and_optional_irrelevant_positive(self):
        operator=self.root/'.claude/skills/cs-operator/SKILL.md'
        operator.write_text(operator.read_text()+'\nOptional background: company/absent-example.md\n')
        triage=self.root/'.claude/skills/cs-triage-mail/SKILL.md'
        triage.write_text(triage.read_text()+'\nRead company/team-conventions.md before judging handled.\n')
        campaign=self.root/'.claude/skills/cs-campaign-tick/SKILL.md'
        campaign.write_text(campaign.read_text()+'\nRead company/campaign-product-notes.md before campaign work.\n')
        runtime=self.runtime(journal_path=str(self.private/'undelivered.jsonl'))
        runtime.tools.bootstrap()
        result=self.run_async(runtime.tools.run_cs(['campaign','list']))
        self.assertEqual(result['cause'],'required_workflow_context_undelivered:company/campaign-product-notes.md')
        runtime.journal.close()
        self.assertNotIn('company/absent-example.md',runtime.tools.context_hashes)
        # Existing production-path fixture proves present notes actually enter
        # successful HTTP-body-linked requests before the real CLI phases run.
        self.exercise_full_controller()

    def test_disabled_campaign_missing_notes_is_irrelevant(self):
        campaign=self.root/'.claude/skills/cs-campaign-tick/SKILL.md'
        campaign.write_text(campaign.read_text()+'\nRead company/campaign-product-notes.md before campaign work.\n')
        (self.root/'company/campaign-product-notes.md').unlink()
        runtime=self.runtime(campaign_enabled=False)
        hashes=runtime.tools.context_closure()
        self.assertIn('company/operator-out-of-scope.md',hashes)
        self.assertNotIn('company/campaign-product-notes.md',hashes)
        # No campaign phase/effect is invoked: missing campaign notes do not
        # create a universal startup requirement for disabled campaign work.
        runtime.journal.close()

    def test_required_exclusion_reference_and_exact_phase_negatives(self):
        runtime = self.runtime()
        runtime.tools.parent_request_id = str(uuid4())
        runtime.tools.complete_phase(['tasks','--limit','1'], str(uuid4()), 0, b'[]')
        self.assertNotIn('tasks', runtime.tools.phases)
        runtime.tools.complete_phase(['tasks','--json'], str(uuid4()), 0, b'[]')
        self.assertEqual(runtime.tools.phases['tasks'], 'held', 'out-of-order phase cannot complete')
        path = self.root/'company/operator-out-of-scope.md'
        path.write_text('Read [current limits](company/current-limits.md).')
        with self.assertRaises(Refusal): runtime.tools.bootstrap()
        path.unlink()
        with self.assertRaises(Refusal): runtime.tools.effects_allowed()
        result = self.run_async(runtime.tools.run_cs(['tasks','create','--email','a@fixture.test','--title','t','--event-id','id']))
        self.assertEqual(result['status'],'denied')
        runtime.journal.close()

    def test_uuid_and_interval_constraints(self):
        from cs.operator_executor_protocol import ToolStart, ContextPage
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ToolStart(tool_id='bad',parent_request_id='bad',name='run_cs',argv=['whoami'],
                path=None,offset=None,length=None,decision='allow',cause=None,producer=identity())
        with self.assertRaises(ValidationError):
            ContextPage(page_id=str(uuid4()),artifact_id=str(uuid4()),source_path='private',
                source_sha256='0'*64,owner='o',start=1,end=3,total_bytes=2,eof=True,sha256='0'*64,decoding='utf-8')

    def test_duplicate_keys_foreign_chain_and_extra_trust_fields(self):
        with self.assertRaises(ValueError):
            decode('{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            decode('{"a":NaN}')
        async def function(messages, info):
            return ModelResponse(parts=[TextPart('done')])
        runtime = self.runtime()
        self.run_async(runtime.run('fixture', model=FunctionModel(function)))
        rows = Path(self.config.journal_path).read_bytes().splitlines()
        value = decode(rows[0])
        value['trusted'] = True
        with self.assertRaises(ValueError):
            Record.model_validate(value)
        rows[1] = rows[1].replace(b'"sequence":1', b'"sequence":9')
        Path(self.config.journal_path).write_bytes(b'\n'.join(rows) + b'\n')
        with self.assertRaises(ValueError):
            parse_journal(Path(self.config.journal_path))


if __name__ == '__main__':
    unittest.main()
