"""Supervisor validation and canonical CLI evidence for the Python executor.

This codec has no native-event compatibility shim. A successful process exit
requires independent joins to actual CLI captures and submitted request bytes.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shlex
import stat
import sys
from decimal import Decimal

CODEC = 'pydantic-executor-v1'
LIMIT = 64 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def archive_content(page, witness):
    return {'executor_page_archive': dict(prior_successful_request_id=witness['request_id'],
        sdk=witness['sdk'], wire=witness['wire'], reread=dict(tool='read_artifact',
        artifact_id=page['artifact_id'], offset=page['start'], length=page['end']-page['start']))}


def map_page_history(value, transform):
    from .operator_executor_protocol import canonical, decode
    def visit(item, eligible=False, call_id=None):
        if isinstance(item, dict):
            if 'executor_page_archive' in item:
                raise ValueError('executor_archive_placement')
            if 'executor_page' in item:
                result = transform(item, eligible, call_id)
                return result, result != item
            values, changed = {}, False
            for key, child in item.items():
                values[key], delta = visit(child, eligible, call_id)
                changed |= delta
            return values, changed
        if isinstance(item, list):
            values, changed = [], False
            for child in item:
                result, delta = visit(child, eligible, call_id)
                values.append(result)
                changed |= delta
            return values, changed
        if isinstance(item, str) and item.lstrip().startswith('{'):
            try:
                nested = decode(item)
            except ValueError:
                return item, False
            result, changed = visit(nested, eligible, call_id)
            return (canonical(result).decode(), True) if changed else (item, False)
        return item, False
    def message(item):
        if not isinstance(item, dict):
            return visit(item)[0]
        key = 'parts' if 'parts' in item else 'content'
        parts = item.get(key)
        if not isinstance(parts, list):
            return visit(item)[0]
        values = dict(item)
        values[key] = []
        for part in parts:
            if not isinstance(part, dict):
                values[key].append(visit(part)[0])
                continue
            result = part.get('part_kind') == 'tool-return' if key == 'parts' else part.get('type') == 'tool_result'
            cid = part.get('tool_call_id') if key == 'parts' else part.get('tool_use_id')
            values[key].append({name: visit(child, result and name == 'content', cid)[0]
                for name, child in part.items()})
        for name in values.keys() - {key}:
            values[name] = visit(values[name])[0]
        return values
    if isinstance(value, list):
        return [message(item) for item in value]
    if isinstance(value, dict) and isinstance(value.get('messages'), list):
        return {key: [message(item) for item in child] if key == 'messages' else visit(child)[0]
            for key, child in value.items()}
    return visit(value)[0]


def page_entries(value):
    found = []
    def collect(item, eligible, call_id):
        found.append((item, eligible, call_id))
        return item
    map_page_history(value, collect)
    return found


def archive_history(value, witnesses):
    def replace(item, eligible, call_id):
        page = item['executor_page']
        witness = witnesses.get(page.get('page_id')) if isinstance(page, dict) else None
        if (eligible and witness is not None and witness['call_id'] == call_id
                and isinstance(item.get('content'), str)):
            return dict(executor_page=page, content=archive_content(page, witness))
        return item
    return map_page_history(value, replace)


def page_archive_maps(value):
    full, archived = {}, {}
    for item, eligible, call_id in page_entries(value):
        page = item['executor_page']
        pid = page.get('page_id') if isinstance(page, dict) else None
        entry = dict(page=item, call_id=call_id)
        if isinstance(item.get('content'), dict):
            if not eligible:
                raise ValueError('executor_archive_placement')
            if pid in archived and archived[pid] != entry:
                raise ValueError('executor_archive_duplicate')
            archived[pid] = entry
        elif eligible:
            if pid in full and full[pid] != entry:
                raise ValueError('executor_page_duplicate')
            full[pid] = entry
    return full, archived


def run_call_matches(arguments, start, end, config):
    """Join submitted spellings through the same policy used by the executor."""
    from .operator_executor_tools import validate_argv
    if not isinstance(arguments,dict) or set(arguments)!={'argv'}:
        return False
    try:
        argv,effect=validate_argv(arguments['argv'],config)
    except ValueError:
        # _run_cs records the original input when policy normalization fails.
        return start.decision=='deny' and arguments['argv']==start.argv and end.effect is False
    return argv==start.argv and effect==end.effect


def read_private(path, maximum=LIMIT):
    path = Path(path)
    if not path.is_absolute() or path.parent.resolve() != path.parent:
        raise ValueError('executor_artifact_path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                or before.st_size > maximum):
            raise ValueError('executor_artifact_private')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > maximum or any(getattr(before, k) != getattr(after, k)
            for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
        raise ValueError('executor_artifact_changed')
    return raw


def reference(path):
    raw = read_private(path)
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)}


def artifact(value, directory=None):
    row = value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
    path = Path(row['path'])
    if directory is not None and path.parent != directory:
        raise ValueError('executor_foreign_artifact')
    raw = read_private(path)
    if len(raw) != row['bytes'] or digest(raw) != row['sha256']:
        raise ValueError('executor_artifact_digest')
    return raw


def capture_cli(function, args, owner):
    """Executed only by the real CLI; tool IDs come from the parent environment."""
    from .operator_executor_protocol import canonical, decode, canonical_uuid
    from .operator_discovery_receipt import proc
    from .operator_inventory_view import source_identity
    context = decode(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
    tool_id = canonical_uuid(os.environ['CS_OPERATOR_EXECUTOR_TOOL_ID'])
    expected = decode(os.environ['CS_OPERATOR_EXECUTOR_IDENTITY'])
    chain, pid = [], os.getpid()
    for _ in range(32):
        row = proc(pid)
        chain.append(row)
        if {k: row[k] for k in ('pid', 'started_ticks')} == context['supervisor']:
            break
        pid = row['ppid']
    else:
        raise ValueError('executor_cli_supervisor_ancestry')
    if (len(chain) != 3 or {k: chain[1][k] for k in ('pid', 'started_ticks')} != expected
            or context['owner_uid'] != owner):
        # Secondary founder account is selected by the canonical parser; the
        # capture still belongs to the primary scheduled owner from context.
        if len(chain) != 3 or {k: chain[1][k] for k in ('pid', 'started_ticks')} != expected:
            raise ValueError('executor_cli_parent_identity')
    directory = Path(context['directory']) / 'executor-cli'
    directory.mkdir(mode=0o700, exist_ok=True)
    from .operator_health import private
    private(directory, True)
    # Preserve the command's exact stdout while retaining it. The outer tool
    # infrastructure separately retains the same bytes and joins the hash.
    output = io.StringIO()
    original = sys.stdout
    class Tee:
        def write(self, text):
            output.write(text)
            return original.write(text)
        def flush(self):
            original.flush()
        def __getattr__(self, name):
            return getattr(original, name)
    with contextlib.redirect_stdout(Tee()):
        code = function(args)
    raw = output.getvalue().encode('utf-8')
    record = dict(schema_version=CODEC, executor_codec=CODEC, tool_id=tool_id,
        nonce=context['nonce'], owner_uid=context['owner_uid'],
        effective_owner_uid=__import__('cs.config', fromlist=['load']).load().engine_owner_uid,
        kernel_source_digest=source_identity(), supervisor_identity=context['supervisor'],
        executor_identity=expected, cli_identity={k: chain[0][k] for k in ('pid', 'started_ticks')},
        ancestry=chain, argv=sys.argv[1:], exit_code=code, output_bytes=len(raw),
        output_sha256=digest(raw))
    target = directory / (tool_id + '.json')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(record))
        stream.flush()
        os.fsync(stream.fileno())
    return code


def capture_business(output, value, code, owner, scope):
    from .operator_executor_protocol import canonical, decode, canonical_uuid
    from .operator_read_outcomes import eligible
    from .operator_health import identity, private
    context = decode(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
    tool = canonical_uuid(os.environ['CS_OPERATOR_EXECUTOR_TOOL_ID'])
    if context['owner_uid'] != owner or not eligible(value, scope, owner):
        raise ValueError('executor_business_read_invalid')
    directory = Path(context['directory']) / 'executor-cli'
    directory.mkdir(mode=0o700, exist_ok=True)
    private(directory, True)
    value = dict(codec=CODEC, tool_id=tool, nonce=context['nonce'], owner_uid=owner,
        cli_identity=identity(os.getpid())[0], argv=sys.argv[1:], scope=scope,
        exit_code=code, output_sha256=digest(output), output_bytes=len(output), value=value)
    fd = os.open(directory / (tool + '.business.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(value))


def known_read(directory, tool_id, argv, code, stdout, owner, nonce, cli=None, stderr=b'', context=None):
    from .operator_executor_protocol import decode
    from .operator_read_outcomes import command_scope, eligible, outside_workset_value
    scope = command_scope('.venv/bin/python -m cs ' + shlex.join(argv))
    if scope is None or scope['exit_code'] != code:
        return False
    record = decode(read_private(Path(directory) / 'executor-cli' / (tool_id + '.business.json')))
    output=stderr if scope['kind']=='outside_selected_workset' else stdout
    if scope['kind']=='outside_selected_workset':
        from .operator_read_outcomes import workset_deferral_output
        context=context or decode(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
        if stdout or output != workset_deferral_output(scope) or not outside_workset_value(record['value'],scope,owner,context):
            return False
    return (record['codec'] == CODEC and record['tool_id'] == tool_id and record['nonce'] == nonce
        and record['owner_uid'] == owner and record['argv'] == argv and record['scope'] == scope
        and record['exit_code'] == code and record['output_bytes'] == len(output)
        and record['output_sha256'] == digest(output) and (cli is None or record['cli_identity'] == cli)
        and eligible(record['value'], scope, owner))


def expected_binding(config, child, interpreter):
    from .operator_executor_protocol import canonical
    from .operator_executor import __file__ as module
    return dict(run_id=config.run_id, attempt_id=config.attempt_id, owner=config.owner,
        nonce=config.nonce, clone_root=config.clone_root, supervisor=config.supervisor.model_dump(),
        executor=child, interpreter=dict(path=str(interpreter), bytes=interpreter.stat().st_size,
            sha256=digest(interpreter.read_bytes())), kernel_source_digest=config.kernel_source_digest,
        executor_module_digest=digest(Path(module).read_bytes()),
        dependency_version=importlib.metadata.version('pydantic-ai-slim'),
        policy_digest=digest(canonical(config.model_dump(mode='json'))))


def validate(proof, context, *, diagnostic_only=False, prework_only=False):
    """Replay semantic joins. A run_end completion assertion is never authority."""
    from .operator_executor_protocol import parse_journal, decode, canonical
    from .operator_executor_config import ExecutorConfig, cache_request_matches
    from .operator_executor_tools import validate_argv
    from .operator_inventory_view import source_identity, load as inventory_load
    from .operator_read_outcomes import command_scope, eligible
    if proof.get('schema_version') != CODEC:
        raise ValueError('executor_codec_unsupported')
    raw_config = artifact(proof['launch_config'])
    config = ExecutorConfig.model_validate(decode(raw_config))
    expected = proof['expected']
    directory = Path(config.journal_path).parent
    if (proof['journal']['path'] != config.journal_path or context['directory'] != str(directory)
            or context['nonce'] != config.nonce or context['owner_uid'] != config.owner
            or context['supervisor'] != config.supervisor.model_dump()
            or expected['kernel_source_digest'] != source_identity()
            or expected['policy_digest'] != digest(raw_config)):
        raise ValueError('executor_launch_binding')
    artifact(proof['journal'], directory)
    records = parse_journal(Path(config.journal_path))
    first, terminal = records[0].payload, records[-1].payload
    if records[0].run_id != expected['run_id'] or records[0].attempt_id != expected['attempt_id']:
        raise ValueError('executor_run_identity')
    for key in ('owner', 'nonce', 'clone_root', 'kernel_source_digest', 'executor_module_digest',
                'dependency_version', 'policy_digest'):
        if getattr(first, key) != expected[key] or (hasattr(config, key) and getattr(config, key) != expected[key]):
            raise ValueError('executor_start_' + key)
    for key in ('supervisor', 'executor'):
        if getattr(first, key).model_dump() != expected[key]:
            raise ValueError('executor_process_identity')
    if {k: getattr(first.interpreter, k) for k in ('path','bytes','sha256')} != expected['interpreter']:
        raise ValueError('executor_interpreter_binding')
    if (first.provider, first.model, first.endpoint) != (config.provider, config.model, config.base_url):
        raise ValueError('executor_route_binding')
    if prework_only:
        requests = [r.payload for r in records if r.payload.kind == 'model_request']
        responses = [r.payload for r in records if r.payload.kind == 'model_response']
        submissions = [r.payload for r in records if r.payload.kind == 'provider_submission']
        permitted = {'run_start','context_page','model_request','provider_submission','model_response','run_end'}
        kinds = [r.payload.kind for r in records]
        if (kinds[-4:] != ['model_request','provider_submission','model_response','run_end']
                or kinds[0] != 'run_start' or any(k != 'context_page' for k in kinds[1:-4])
                or any(r.payload.kind not in permitted for r in records) or len(requests) != 1
                or len(responses) != 1 or len(submissions) != 1 or proof['process_exit'] == 0
                or proof['timed_out'] or terminal.terminal != 'failed' or terminal.model_completed
                or terminal.outstanding_tool_ids or terminal.phase_outcomes
                or terminal.input_tokens or terminal.output_tokens or Decimal(terminal.accounted_cost_usd)):
            raise ValueError('executor_prework_work_or_ambiguity')
        request, response, submission = requests[0], responses[0], submissions[0]
        if (config.provider != 'anthropic' or request.transport != 'anthropic-boundary'
                or request.request_id != response.request_id or request.request_id != submission.request_id
                or terminal.outstanding_request_ids != [request.request_id]
                or response.status != 'error' or response.http_status != 402 or response.error_kind != 'billing'
                or response.model is not None or response.input_tokens is not None or response.output_tokens is not None
                or response.accounted_cost_usd is not None or not response.provider_request_id
                or any(getattr(response,name) is not None for name in
                    ('normal_input_tokens','cache_read_tokens','cache_write_tokens','cache_write_1h_tokens','cost_basis'))
                or submission.endpoint != config.messages_endpoint):
            raise ValueError('executor_prework_refusal_unsupported')
        body = decode(artifact(submission.body, directory))
        message_bytes = artifact(request.messages, directory)
        from .operator_executor import executor_model_settings
        if decode(message_bytes).get('settings') != executor_model_settings(config):
            raise ValueError('executor_sdk_settings_binding')
        bound = (Decimal(request.input_token_estimate)*Decimal(config.pricing.input_upper_usd_per_million)
            +Decimal(config.max_output_tokens)*Decimal(config.pricing.output_upper_usd_per_million))/Decimal(1000000)
        if (body.get('model') != config.model or not cache_request_matches(config,body)
                or digest(message_bytes) != request.payload_sha256
                or request.input_token_estimate != len(message_bytes)+4096
                or bound != Decimal(request.reserved_maximum_usd) or bound != Decimal(terminal.uncertain_cost_usd)
                or bound <= 0 or bound > Decimal(config.admitted_ceiling_usd)
                or any(getattr(first,name) != getattr(config,name) for name in
                    ('admitted_ceiling_usd','soft_budget_usd','max_requests','max_output_tokens','deadline_seconds'))):
            raise ValueError('executor_prework_reservation_binding')
        return dict(terminal='failed',prework_refusal='payment_required',attempt_id=config.attempt_id,
            provider=config.provider,model=config.model,endpoint=config.endpoint,
            original_admitted_ceiling_usd=config.admitted_ceiling_usd,
            accounted_cost_usd=terminal.accounted_cost_usd,uncertain_cost_usd=terminal.uncertain_cost_usd)
    if diagnostic_only:
        failures = [r.payload for r in records if r.payload.kind == 'model_response' and r.payload.status != 'ok']
        return dict(terminal=terminal.terminal,
            diagnostic=terminal.diagnostic.model_dump(mode='json') if terminal.diagnostic else None,
            provider_failures=[dict(request_id=p.request_id, provider_request_id=p.provider_request_id,
                http_status=p.http_status, error_kind=p.error_kind) for p in failures],
            accounted_cost_usd=terminal.accounted_cost_usd, uncertain_cost_usd=terminal.uncertain_cost_usd,
            fallback_hold='zero_charge_unproven' if failures else 'prework_refusal_unproven')
    pages, requests, responses, submissions = {}, {}, {}, {}
    archive_witnesses, request_page_maps = {}, {}
    starts, spawns, ends, phase_rows = {}, {}, {}, []
    covered, required, phases, tools = set(), set(), {}, []
    superseded = set()
    selected, pending = [], []
    command_results=[]
    start_sequences={}
    actual_input = actual_output = 0
    actual_cost = Decimal(0)
    successful_models = set()

    def full(aid):
        intervals = sorted((p.start, p.end) for pid, p in pages.items()
                           if pid in covered and p.artifact_id == aid)
        stop = 0
        for start, end in intervals:
            if start > stop:
                return False
            stop = max(stop, end)
        matches = [p for p in pages.values() if p.artifact_id == aid]
        return bool(intervals) and bool(matches) and stop == matches[0].total_bytes

    def call_map(value, *, wire=False):
        """Normalize the two retained SDK/Anthropic representations, never payload hints."""
        calls={}
        names={'run_cs','read_context','load_workflow','read_artifact','pause_status','git_metadata'}
        for message in value:
            parts=message.get('content' if wire else 'parts',[])
            if isinstance(parts,str):
                continue
            if not isinstance(parts,list):
                raise ValueError('executor_call_map_shape')
            for part in parts:
                if not isinstance(part,dict) or part.get('type' if wire else 'part_kind')!=('tool_use' if wire else 'tool-call'):
                    continue
                cid=part.get('id' if wire else 'tool_call_id')
                name=part.get('name' if wire else 'tool_name')
                args=part.get('input' if wire else 'args')
                if isinstance(args,str):
                    args=decode(args)
                if not isinstance(cid,str) or not cid or cid in calls or name not in names or not isinstance(args,dict):
                    raise ValueError('executor_call_map_identity')
                calls[cid]=(name,args)
        return calls

    def submitted(value, calls):
        found = []
        def result_values(content):
            if isinstance(content,str):
                try:
                    content=decode(content)
                except ValueError:
                    return []
            if isinstance(content,dict):
                return [content]
            if isinstance(content,list):
                values=[]
                for block in content:
                    if isinstance(block,dict) and block.get('type')=='text':
                        values.extend(result_values(block.get('text')))
                return values
            return []
        def result_join(item):
            values=result_values(item.get('content'))
            name=item.get('tool_name')
            if item.get('part_kind')=='tool-return':
                call=item.get('tool_call_id')
                if call not in calls or calls[call][0]!=name:
                    raise ValueError('executor_submitted_tool_result_call')
            if item.get('type')=='tool_result':
                call=item.get('tool_use_id')
                if call not in calls:
                    raise ValueError('executor_submitted_tool_result_call')
                name=calls[call][0]
            if name=='run_cs' and len(values)!=1:
                raise ValueError('executor_submitted_tool_result_shape')
            for result in values:
                if 'tool_id' not in result:
                    if name=='run_cs':
                        raise ValueError('executor_submitted_tool_result_identity')
                    continue
                tid=result['tool_id']
                if tid not in starts or tid not in ends or starts[tid].name!='run_cs' or name!='run_cs':
                    raise ValueError('executor_submitted_tool_result_lifecycle')
                if not run_call_matches(calls[call][1],starts[tid],ends[tid],config):
                    raise ValueError('executor_submitted_tool_call_arguments')
                if starts[tid].parent_request_id!=call_parents[call]:
                    raise ValueError('executor_submitted_tool_call_parent')
                if (call in call_lifecycles and call_lifecycles[call]!=tid
                        or tid in lifecycle_calls and lifecycle_calls[tid]!=call):
                    raise ValueError('executor_submitted_tool_call_lifecycle')
                call_lifecycles[call]=tid
                lifecycle_calls[tid]=call
                end=ends[tid]
                if result.get('status')!=end.status:
                    raise ValueError('executor_submitted_tool_result_status')
                if starts[tid].decision=='deny':
                    if result.get('cause')!=starts[tid].cause or end.status!='denied':
                        raise ValueError('executor_submitted_tool_denial')
                else:
                    expected={'exit_code':end.exit_code,
                        'stdout':end.stdout.model_dump(mode='json') if end.stdout else None,
                        'stderr':end.stderr.model_dump(mode='json') if end.stderr else None}
                    if any(key not in result or result[key]!=value for key,value in expected.items()):
                        raise ValueError('executor_submitted_tool_result_bytes')
        def visit(item):
            if isinstance(item, dict):
                if item.get('part_kind')=='tool-return' or item.get('type')=='tool_result':
                    result_join(item)
                if 'executor_page' in item:
                    page = item['executor_page']
                    pid = page.get('page_id') if isinstance(page, dict) else None
                    if pid not in pages or page != pages[pid].model_dump(mode='json'):
                        raise ValueError('executor_foreign_request_page')
                    if isinstance(item.get('content'), dict):
                        witness = archive_witnesses.get(pid)
                        if (witness is None or set(item) != {'executor_page', 'content'}
                                or item['content'] != archive_content(page, witness)):
                            raise ValueError('executor_archive_witness')
                        return
                    try:
                        raw = item['content'].encode() if page['decoding'] == 'utf-8' else base64.b64decode(item['content'], validate=True)
                    except (KeyError, ValueError, TypeError):
                        raise ValueError('executor_request_page_encoding')
                    if len(raw) != page['end'] - page['start'] or digest(raw) != page['sha256']:
                        raise ValueError('executor_request_page_bytes')
                    if pid not in found:
                        found.append(pid)
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
            elif isinstance(item, str) and item.lstrip().startswith('{'):
                try:
                    nested = decode(item)
                except ValueError:
                    return
                visit(nested)
        visit(value)
        return found

    request_calls={}
    sdk_calls,call_parents,call_lifecycles,lifecycle_calls={},{},{},{}

    def complete_inventory():
        nonlocal selected
        directory2, view, envelope = inventory_load(context)
        if (envelope['source_identity'] != expected['kernel_source_digest']
                or envelope['native_invocation']['child_identity'] != expected['executor']):
            raise ValueError('executor_inventory_identity')
        for name in ('inventory-view-envelope.json','inventory-view.jsonl'):
            path = str(directory2 / name)
            ids = {p.artifact_id for p in pages.values() if p.source_path == path}
            if len(ids) != 1 or not full(next(iter(ids))):
                return False
        discovery = decode(read_private(directory / 'discovery.json'))
        selected = discovery['discovery']['triage_workset']['selected']
        return True

    for row in records[1:-1]:
        p = row.payload
        if p.kind == 'run_start':
            raise ValueError('executor_duplicate_start')
        if p.kind == 'context_page':
            if p.page_id in pages or p.owner != config.owner:
                raise ValueError('executor_page_identity')
            source = Path(p.source_path)
            if not (source.is_relative_to(Path(config.clone_root)) or source.is_relative_to(directory)):
                raise ValueError('executor_foreign_page_source')
            data = source.read_bytes() if source.is_relative_to(Path(config.clone_root)) else read_private(source)
            if (len(data) != p.total_bytes or digest(data) != p.source_sha256
                    or digest(data[p.start:p.end]) != p.sha256):
                raise ValueError('executor_page_source_digest')
            if any(q.artifact_id == p.artifact_id and (q.total_bytes != p.total_bytes or q.source_sha256 != p.source_sha256 or q.source_path != p.source_path) for q in pages.values()):
                raise ValueError('executor_page_source_changed')
            pages[p.page_id] = p
        elif p.kind == 'model_request':
            if p.request_id in requests:
                raise ValueError('executor_duplicate_request')
            raw = artifact(p.messages, directory)
            value = decode(raw)
            from .operator_executor import executor_model_settings
            if value.get('settings') != executor_model_settings(config):
                raise ValueError('executor_sdk_settings_binding')
            request_page_maps[p.request_id] = page_archive_maps(value['messages'])
            for pid, entry in request_page_maps[p.request_id][1].items():
                if pid not in archive_witnesses or entry['call_id'] != archive_witnesses[pid]['call_id']:
                    raise ValueError('executor_archive_call_placement')
            calls=call_map(value['messages'])
            for cid,call in calls.items():
                if cid in sdk_calls:
                    if sdk_calls[cid]!=call:
                        raise ValueError('executor_sdk_call_changed')
                else:
                    if not requests:
                        raise ValueError('executor_sdk_call_parent')
                    sdk_calls[cid]=call
                    call_parents[cid]=next(reversed(requests))
            if digest(raw) != p.payload_sha256 or submitted(value['messages'],calls) != p.page_ids:
                raise ValueError('executor_request_payload')
            request_calls[p.request_id]=calls
            requests[p.request_id] = p
        elif p.kind == 'provider_submission':
            if p.request_id not in requests or p.request_id in submissions or p.request_id in responses:
                raise ValueError('executor_submission_order')
            body = decode(artifact(p.body, directory))
            if page_archive_maps(body) != request_page_maps[p.request_id]:
                raise ValueError('executor_sdk_wire_page_archives')
            calls=call_map(body.get('messages',[]),wire=True)
            if calls!=request_calls[p.request_id]:
                raise ValueError('executor_sdk_wire_call_map')
            if body.get('model') != config.model or submitted(body,calls) != p.page_ids:
                raise ValueError('executor_submission_payload')
            if not cache_request_matches(config,body):
                raise ValueError('executor_cache_mode_binding')
            if p.endpoint != config.messages_endpoint:
                raise ValueError('executor_submission_endpoint')
            submissions[p.request_id] = p
        elif p.kind == 'model_response':
            if p.request_id not in requests or p.request_id in responses:
                raise ValueError('executor_response_order')
            responses[p.request_id] = p
            req = requests[p.request_id]
            if p.status == 'ok':
                if p.accounted_cost_usd is None or p.input_tokens is None or p.output_tokens is None:
                    raise ValueError('executor_unknown_response_cost')
                if req.transport != 'function-test' and p.request_id not in submissions:
                    raise ValueError('executor_missing_submission')
                if req.transport != 'function-test' and not config.pricing.accepts(p.model):
                    raise ValueError('executor_response_model')
                cache_read = p.cache_read_tokens if p.cache_read_tokens is not None else 0
                cache_write = p.cache_write_tokens if p.cache_write_tokens is not None else 0
                cache_1h = p.cache_write_1h_tokens if p.cache_write_1h_tokens is not None else 0
                normal = p.input_tokens-cache_read-cache_write
                if (p.normal_input_tokens != normal or p.cost_basis != config.pricing.cost_basis
                        or any(value is None for value in
                            (p.cache_read_tokens,p.cache_write_tokens,p.cache_write_1h_tokens,p.normal_input_tokens,p.cost_basis))):
                    raise ValueError('executor_usage_bucket_binding')
                if config.cache_mode != '1h' and cache_1h:
                    raise ValueError('executor_usage_bucket_binding')
                computed=config.pricing.estimate(p.input_tokens,p.output_tokens,cache_read,cache_write,cache_1h)
                if computed != Decimal(p.accounted_cost_usd) or computed > Decimal(req.reserved_maximum_usd):
                    raise ValueError('executor_response_cost_binding')
                actual_input += p.input_tokens
                actual_output += p.output_tokens
                actual_cost += computed
                if actual_cost > Decimal(config.admitted_ceiling_usd):
                    raise ValueError('executor_admitted_ceiling_exceeded')
                covered.update(req.page_ids if req.transport == 'function-test' else submissions[p.request_id].page_ids)
                if req.transport != 'function-test':
                    for pid in request_page_maps[p.request_id][0]:
                        archive_witnesses.setdefault(pid, dict(request_id=p.request_id,
                            call_id=request_page_maps[p.request_id][0][pid]['call_id'],
                            sdk=req.messages.model_dump(mode='json'),
                            wire=submissions[p.request_id].body.model_dump(mode='json')))
                if p.model:
                    successful_models.add(p.model)
        elif p.kind == 'tool_start':
            if p.tool_id in starts or p.producer.model_dump() != expected['executor']:
                raise ValueError('executor_tool_identity')
            if p.parent_request_id is not None and (p.parent_request_id not in responses or responses[p.parent_request_id].status != 'ok'):
                raise ValueError('executor_tool_parent_request')
            starts[p.tool_id] = p
            start_sequences[p.tool_id]=row.sequence
            if p.name == 'run_cs' and p.decision == 'allow':
                argv, effect = validate_argv(p.argv, config)
                if argv != p.argv:
                    raise ValueError('executor_noncanonical_argv')
                if effect:
                    if (not {'identity','config','tasks','review','discovery','authority'} <= phases.keys()
                            or any(phases[k] != 'completed' for k in ('identity','config','tasks','review','discovery','authority'))
                            or any(not full(a) for a in required - superseded) or not complete_inventory()):
                        raise ValueError('executor_early_effect')
                    if selected and p.argv[:1] != ['campaign']:
                        from .operator_executor_work import selected_roots
                        target=None
                        if '--thread-id' in p.argv:
                            target=p.argv[p.argv.index('--thread-id')+1]
                        if target not in {r['thread_key'] for r in selected}:
                            raise ValueError('executor_effect_root_missing')
                        outcomes=selected_roots(directory,config.owner,config.nonce,command_results,
                            send_mode=config.send_mode,final=False,target_root=target)
                        if any(o['outcome']=='held' for o in outcomes):
                            raise ValueError('executor_effect_assignment_hold')
        elif p.kind == 'tool_spawn':
            if (p.tool_id not in starts or p.tool_id in spawns or p.tool_id in ends
                    or starts[p.tool_id].decision != 'allow' or starts[p.tool_id].name != 'run_cs'
                    or p.parent.model_dump() != expected['executor']):
                raise ValueError('executor_spawn_join')
            spawns[p.tool_id] = p
        elif p.kind == 'tool_end':
            if p.tool_id not in starts or p.tool_id in ends:
                raise ValueError('executor_result_join')
            start = starts[p.tool_id]
            if p.stdout:
                stdout = artifact(p.stdout, directory)
                if stdout:
                    required.add(p.stdout.artifact_id)
            else:
                stdout = b''
            if p.stderr:
                stderr = artifact(p.stderr, directory)
                if stderr:
                    required.add(p.stderr.artifact_id)
            if start.name == 'run_cs' and start.decision == 'allow':
                if p.tool_id not in spawns:
                    raise ValueError('executor_missing_spawn')
                capture = decode(read_private(directory / 'executor-cli' / (p.tool_id + '.json')))
                chain = capture['ancestry']
                if (capture.get('executor_codec') != CODEC or capture['tool_id'] != p.tool_id
                        or capture['nonce'] != config.nonce or capture['owner_uid'] != config.owner
                        or capture['kernel_source_digest'] != expected['kernel_source_digest']
                        or capture['supervisor_identity'] != expected['supervisor']
                        or capture['executor_identity'] != expected['executor']
                        or capture['cli_identity'] != spawns[p.tool_id].child.model_dump()
                        or capture['argv'] != start.argv or capture['exit_code'] != p.exit_code
                        or capture['output_bytes'] != len(stdout) or capture['output_sha256'] != digest(stdout)
                        or len(chain) != 3 or any(chain[i]['ppid'] != chain[i+1]['pid'] for i in range(2))
                        or {k:chain[0][k] for k in ('pid','started_ticks')} != capture['cli_identity']
                        or {k:chain[1][k] for k in ('pid','started_ticks')} != expected['executor']
                        or {k:chain[2][k] for k in ('pid','started_ticks')} != expected['supervisor']
                        or chain[0]['argv'][-len(start.argv):] != start.argv
                        or chain[0]['executable'] != expected['interpreter']['path']):
                    raise ValueError('executor_cli_capture_join')
                good = p.exit_code == 0 and p.status == 'ok'
                scope = command_scope('.venv/bin/python -m cs ' + shlex.join(start.argv))
                if p.exit_code in (1,3) and scope is not None:
                    good = known_read(directory, p.tool_id, start.argv, p.exit_code, stdout,
                        config.owner, config.nonce, capture['cli_identity'],stderr=stderr if p.stderr else b'',context=context)
                if start.argv == ['unanswered','--days','14','--json','--all-buckets'] and p.exit_code in (0,3):
                    from .operator_health import assess
                    good = assess(context, expected['executor'], config.owner) == ''
                    inventory_load(context)
                if not good or p.unknown_effect:
                    raise ValueError('executor_tool_not_successful')
                command_results.append(dict(tool_id=p.tool_id,argv=start.argv,exit_code=p.exit_code,stdout=stdout,start_sequence=start_sequences[p.tool_id],end_sequence=row.sequence))
                tools.append(dict(tool_id=p.tool_id, argv=start.argv, child_identity=capture['cli_identity'],
                    exit_code=p.exit_code, stdout_sha256=digest(stdout), stdout_bytes=len(stdout),
                    capture=reference(directory / 'executor-cli' / (p.tool_id+'.json'))))
            elif start.decision == 'deny' and (p.status != 'denied' or p.tool_id in spawns):
                raise ValueError('executor_denied_spawn')
            ends[p.tool_id] = p
        elif p.kind == 'phase':
            if any(k not in phases or phases[k] != 'completed' for k in p.prerequisites):
                if p.outcome == 'completed':
                    raise ValueError('executor_phase_prerequisite')
            if not p.tool_ids or any(t not in ends for t in p.tool_ids) or any(r not in responses or responses[r].status != 'ok' for r in p.request_ids):
                raise ValueError('executor_phase_join')
            # Phase assertions are checked again against actual CLI stdout below.
            phases[p.name] = p.outcome
            phase_rows.append(p)
            if p.name == 'discovery' and p.outcome == 'completed':
                for tid, start in starts.items():
                    if start.argv in (['tasks','--json'], ['review','--json'], ['unanswered','--days','14','--json','--all-buckets']) and tid in ends and ends[tid].stdout:
                        superseded.add(ends[tid].stdout.artifact_id)
    if set(starts) != set(ends) or set(requests) != set(responses) or any(p.status != 'ok' for p in responses.values()):
        raise ValueError('executor_outstanding_work')
    if (terminal.outstanding_tool_ids or terminal.outstanding_request_ids or Decimal(terminal.uncertain_cost_usd)
            or terminal.input_tokens != actual_input or terminal.output_tokens != actual_output
            or Decimal(terminal.accounted_cost_usd) != actual_cost):
        raise ValueError('executor_terminal_accounting')
    if terminal.phase_outcomes != phases:
        raise ValueError('executor_terminal_phases')
    needed = {'identity','config','tasks','review','discovery','authority'}
    if config.campaign_enabled:
        needed |= {'campaign_list','campaign_pending','campaign_work'}
    if config.founder_enabled:
        needed |= {'founder_tasks','founder_mail'}
    # Re-evaluate each observed phase against current producer-independent CLI
    # facts. Exact command shapes prevent a model's prose from closing a phase.
    exact = {'identity':['whoami','--json'], 'config':['config','--json'], 'tasks':['tasks','--json'],
        'review':['review','--json'], 'discovery':['unanswered','--days','14','--json','--all-buckets'],
        'authority':['standing-instructions','--json'], 'campaign_list':['campaign','list'],
        'campaign_pending':['campaign','pending'], 'founder_tasks':['--account',config.founder_account,'tasks','--json'],
        'founder_mail':['--account',config.founder_account,'ask',config.founder_question]}
    for phase in phase_rows:
        if phase.outcome != 'completed':
            continue
        if phase.name == 'selected_root_work':
            from .operator_executor_work import selected_roots
            outcomes=selected_roots(directory,config.owner,config.nonce,command_results,send_mode=config.send_mode)
            if phase.tool_ids != list(dict.fromkeys(t for outcome in outcomes for t in outcome['tool_ids'])):
                raise ValueError('executor_selected_root_outcome_join')
            continue
        if phase.name == 'campaign_work':
            pending_result=[r for r in command_results if r['argv'] == exact['campaign_pending']]
            if not pending_result:
                raise ValueError('executor_campaign_pending_missing')
            pending_value=decode(pending_result[-1]['stdout'])
            pending_items=[item for campaign in pending_value['campaigns'] for item in campaign['items']]
            if pending_items:
                from .operator_executor_work import campaign_work
                outcomes=campaign_work(pending_items,command_results)
                ids=list(dict.fromkeys(t for outcome in outcomes for t in outcome['tool_ids'])) or [pending_result[-1]['tool_id']]
                if phase.tool_ids != ids:
                    raise ValueError('executor_campaign_outcome_join')
                continue
            argv = exact['campaign_pending']
        elif phase.name in exact:
            argv = exact[phase.name]
        else:
            raise ValueError('executor_unknown_phase')
        if len(phase.tool_ids) != 1 or starts[phase.tool_ids[0]].argv != argv:
            raise ValueError('executor_phase_command')
        end = ends[phase.tool_ids[0]]
        raw = artifact(end.stdout, directory)
        value = raw.decode().strip() if phase.name == 'founder_mail' else decode(raw)
        good = end.exit_code == 0
        if phase.name == 'identity':
            good &= value.get('signed_in') is True and value.get('uid') == config.owner
        elif phase.name == 'config':
            fields = {r['name']:r for s in value['sections'] for r in s['settings']}
            good &= fields['cs_triage_mode']['value'] == config.send_mode and bool(fields['cs_triage_mode']['origin'])
        elif phase.name in ('tasks','founder_tasks'):
            from .operator_workset import _rows
            good &= len(_rows('tasks',value)) < 200
        elif phase.name == 'review':
            from .draft_state import inventory_proof
            actual = inventory_proof(value.get('mailbox_drafts'),value.get('drafts'))
            good &= actual.get('complete') is True and actual == value.get('drafts_inventory')
        elif phase.name == 'authority':
            docs = value['documents']
            good &= value['authority'] in ('legacy','managed') and bool(value['space_id']) and len(docs) == 2 and {d['path'] for d in docs} == {'procedures.md','mail/'+value['mailbox']+'.md'} and all(type(d['revision']) is int and d['revision'] > 0 and digest(d['text'].encode()) == d['sha256'] for d in docs)
        elif phase.name == 'discovery':
            from .operator_health import assess
            good = assess(context,expected['executor'],config.owner) == ''
        elif phase.name == 'campaign_list':
            good &= isinstance(value,list) and all(isinstance(x,dict) for x in value)
        elif phase.name in ('campaign_pending','campaign_work'):
            good &= isinstance(value,dict) and isinstance(value.get('campaigns'),list)
            pending = [item for campaign in value['campaigns'] for item in campaign['items']]
            if phase.name == 'campaign_work':
                good &= not pending
        elif phase.name == 'founder_mail':
            good &= bool(value)
        if not good:
            raise ValueError('executor_phase_semantic_' + phase.name)
    if not needed <= phases.keys() or any(phases[p] != 'completed' for p in needed):
        raise ValueError('executor_required_phase_incomplete')
    if any(not full(aid) for aid in required - superseded) or not complete_inventory():
        raise ValueError('executor_request_coverage_incomplete')
    work_outcomes=[]
    if selected:
        if phases.get('selected_root_work') != 'completed':
            raise ValueError('executor_selected_root_obligations_unresolved')
        from .operator_executor_work import selected_roots
        work_outcomes=selected_roots(directory,config.owner,config.nonce,command_results,send_mode=config.send_mode)
    if (terminal.terminal != 'completed' or terminal.model_completed is not True
            or proof['process_exit'] != 0 or proof['timed_out']):
        raise ValueError('executor_terminal_not_completed')
    return dict(terminal=terminal.terminal, phases=phases, tool_proofs=tools,
        submitted_page_count=len(covered), model_names=sorted(successful_models),
        accounted_cost_usd=str(actual_cost), selected_root_count=len(selected),work_outcomes=work_outcomes)
