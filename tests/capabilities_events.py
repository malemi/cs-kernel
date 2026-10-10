from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from live_instructions_skill import events, final_text, nodes
from capabilities_shell import checked_tree, command_targets as shell_targets, shell_parts, validate_cli_args


def final_text(transcript, _shared=final_text):
    records = list(strict_events(transcript))
    kinds = {'step_start', 'step_finish', 'text', 'tool_use'}
    if not any(event['type'] in kinds for event in records):
        return _shared(transcript)
    assert all(event['type'] in kinds for event in records), 'Mixed native answer envelopes'
    last_tool = max((index for index, event in enumerate(records) if event['type'] == 'tool_use'), default=-1)
    terminal = [event for event in records[last_tool + 1:] if event['type'] == 'text']
    assert terminal, 'Missing terminal OpenCode answer'
    identities, part_ids, chunks = set(), set(), []
    for event in terminal:
        part = event.get('part')
        assert isinstance(part, dict) and part.get('type') == 'text' and native_envelope(event, part), 'Malformed terminal OpenCode text'
        session = event.get('sessionID')
        assert native_identity(session, 'ses') and part.get('sessionID') == session, 'Invalid terminal session identity'
        assert native_identity(part.get('messageID'), 'msg') and native_identity(part.get('id'), 'prt'), 'Invalid terminal message identity'
        assert part['id'] not in part_ids, 'Repeated terminal text part'
        part_ids.add(part['id'])
        identities.add((session, part['messageID']))
        chunks.append(part['text'])
    assert len(identities) == 1, 'Ambiguous terminal OpenCode answer'
    answer = ''.join(chunks)
    assert answer.strip(), 'Empty terminal OpenCode answer'
    return answer


def strict_events(transcript):
    kinds = {'assistant', 'user', 'system', 'result', 'rate_limit_event', 'error',
             'thread.started', 'turn.started', 'turn.completed', 'turn.failed',
             'item.started', 'item.updated', 'item.completed',
             'step_start', 'step_finish', 'text', 'tool_use'}
    for line in transcript.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise AssertionError('Malformed native event line') from exc
        assert isinstance(event, dict) and event.get('type') in kinds, 'Unknown native event envelope'
        yield event


def tool_events(transcript):
    pending, completed, records, commands, inflight = {}, {}, [], {}, {}
    for event in strict_events(transcript):
        if event.get('type') in ('item.started', 'item.updated', 'item.completed'):
            item = event.get('item')
            assert isinstance(item, dict), 'Missing Codex item'
            kind = item.get('type')
            assert kind in ('command_execution', 'agent_message', 'reasoning', 'todo_list', 'plan'), f'Forbidden or unknown Codex item: {kind}'
            if kind == 'command_execution':
                assert isinstance(item.get('id'), str) and item['id'], 'Missing Codex command identifier'
                if item.get('status') in ('completed', 'failed'):
                    commands.pop(item['id'], None)
                else:
                    commands[item['id']] = item
        if event.get('type') in ('assistant', 'user'):
            message = event.get('message', {})
            blocks = message.get('content', []) if isinstance(message, dict) else []
            for block in blocks if isinstance(blocks, list) else []:
                assert isinstance(block, dict) and block.get('type') in ('text', 'thinking', 'redacted_thinking', 'tool_use', 'tool_result'), 'Unknown Claude content block'
        for node in nodes(event):
            kind = node.get('type')
            if kind == 'tool_use' and node.get('id') and node.get('name'):
                pending[node['id']] = node
            elif kind == 'tool_result':
                call = pending.pop(node.get('tool_use_id'), None)
                assert call is not None, 'Unmatched tool result'
                if call:
                    records.append({'name': call['name'].lower(), 'input': call.get('input', {}),
                                    'output': node.get('content', ''), 'success': not node.get('is_error', False)})
            elif kind == 'command_execution' and node.get('status') in ('completed', 'failed'):
                records.append({'name': 'bash', 'input': {'command': node.get('command', '')},
                                'output': node.get('aggregated_output', ''),
                                'success': node.get('status') == 'completed' and node.get('exit_code') == 0})
            elif kind == 'tool' and isinstance(node.get('state'), dict):
                state = node['state']
                call_id = node.get('callID')
                if state.get('status') not in ('completed', 'error'):
                    assert state.get('status') in ('pending', 'running') and call_id, 'Unknown tool lifecycle state'
                    inflight[call_id] = node
                    continue
                inflight.pop(call_id, None)
                if node.get('tool') == 'unknown' and call_id in completed:
                    prior = completed[call_id]
                    assert state.get('status') == 'error' and state.get('error') == 'Tool execution aborted' and state.get('input') == {} and state.get('raw', '') == '', 'Malformed duplicate terminal event'
                    assert prior['success'], 'Aborted call had no completed output'
                    prior.setdefault('duplicate_terminal_events', []).append(node)
                    continue
                record = {'name': node.get('tool', '').lower(), 'input': state.get('input', {}),
                          'output': state.get('output', state.get('error', '')),
                          'success': state.get('status') == 'completed', 'call_id': call_id}
                if call_id:
                    assert call_id not in completed, 'Conflicting repeated call identifier'
                    completed[call_id] = record
                records.append(record)
    records.extend({'name': call['name'].lower(), 'input': call.get('input', {}), 'output': '', 'success': False}
                   for call in pending.values())
    records.extend({'name': 'bash', 'input': {'command': item.get('command', '')}, 'output': '', 'success': False} for item in commands.values())
    records.extend({'name': node.get('tool', '').lower(), 'input': node['state'].get('input', {}), 'output': '', 'success': False} for node in inflight.values())
    yield from records


def output_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(output_text(item) for item in value)
    if isinstance(value, dict):
        return str(value.get('text', value.get('content', '')))
    return ''


def source_snapshot(root):
    selected = [root / 'pyproject.toml', root / 'requirements.txt', root / 'tests/run.sh']
    selected += list((root / 'cs').rglob('*')) + list((root / 'tests').glob('*.py'))
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(selected) if p.is_file() and '__pycache__' not in p.parts}


def require_unchanged(before, after, label='fixture'):
    assert before == after, f'{label} changed during native run'


def resolve_prose(root, value, listing=False):
    assert isinstance(value, str) and value, 'Unresolved file target'
    assert not any(c in value for c in ('$', '`', '~', '\n')), f'Unresolved file target: {value}'
    path = Path(value)
    path = path if path.is_absolute() else root / path
    resolved = path.resolve()
    assert resolved.is_relative_to(root.resolve()), f'Outside-clone target: {value}'
    rel = resolved.relative_to(root.resolve())
    approved = str(rel) in ('AGENTS.md', 'CLAUDE.md', 'README.md')
    approved |= bool(rel.parts and rel.parts[0] == 'company')
    approved |= len(rel.parts) >= 2 and rel.parts[:2] in (('.claude', 'skills'), ('.agents', 'skills'), ('.opencode', 'skills'))
    approved |= str(rel) in ('docs/ARCHITECTURE.md', 'docs/active-context.md', 'docs/project-memory.md', 'docs/project-meeting-template.md')
    approved |= len(rel.parts) == 3 and rel.parts[:2] == ('docs', 'sessions') and rel.suffix == '.md' and not resolved.exists()
    approved |= listing and str(rel) in ('.', '.claude', '.agents', '.opencode', 'docs', 'docs/sessions')
    assert listing or resolved.is_dir() or resolved.suffix == '.md', f'Non-prose file target: {value}'
    assert approved, f'Forbidden source/config target: {value}'
    return resolved


def command_targets(command, root):
    return shell_targets(command, root, resolve_prose)


def audit_tools(transcript, root):
    evidence = []
    for call in tool_events(transcript):
        name, inputs = call['name'], call['input']
        paths = []
        if name in ('bash', 'exec_command', 'shell'):
            paths = command_targets(inputs.get('command', inputs.get('cmd', '')), root)
        elif name in ('read', 'read_file'):
            paths = [resolve_prose(root, inputs.get('file_path', inputs.get('filePath', inputs.get('path'))))]
        elif name in ('glob', 'grep', 'list', 'ls'):
            target = inputs.get('path', '.')
            base = resolve_prose(root, target, listing=True)
            paths = [base]
            pattern = inputs.get('pattern', '')
            if name == 'grep':
                assert base != root.resolve(), f'Unbounded clone search: {inputs}'
                checked_tree(root, base, resolve_prose)
            if name in ('list', 'ls'):
                checked_tree(root, base, resolve_prose)
            if name == 'glob':
                assert not any(term in pattern for term in ('../', '.venv', 'bin/', 'tests/', 'cs/')), f'Forbidden search: {inputs}'
                matches = list(base.glob(pattern))
                paths += [resolve_prose(root, str(path), listing=True) for path in matches]
                if not matches:
                    prefix = re.split(r'[*?\[]', pattern, 1)[0].rsplit('/', 1)[0]
                    assert prefix, f'Unresolved broad glob: {inputs}'
                    resolve_prose(root, str(base / prefix), listing=True)
        elif name == 'skill':
            selected = inputs.get('skill', inputs.get('name', ''))
            assert re.fullmatch(r'cs-[a-z-]+', selected), f'External skill: {selected}'
            paths = [resolve_prose(root, f'.claude/skills/{selected}/SKILL.md')]
        elif name in ('todowrite', 'todoread', 'update_plan'):
            pass
        else:
            raise AssertionError(f'Forbidden or unknown tool: {name}')
        evidence.append({**call, 'paths': [str(p) for p in paths]})
    return evidence


def read_coverage(evidence, path):
    source = path.read_text()
    lines = [line for line in source.splitlines() if line.strip()]
    covered = set()
    body_complete = False
    for call in evidence:
        if not call['success'] or str(path.resolve()) not in call['paths']:
            continue
        if call['name'] not in ('read', 'read_file', 'bash', 'shell', 'exec_command', 'skill'):
            continue
        output = output_text(call['output'])
        for index, line in enumerate(lines):
            if line in output:
                covered.add(index)
        if call['name'] != 'skill':
            continue
        canonical = path.resolve()
        selected = call['input'].get('skill', call['input'].get('name', ''))
        if canonical.parts[-4:] != ('.claude', 'skills', selected, 'SKILL.md'):
            continue
        frontmatter = re.fullmatch(r'---\nname: ([a-z-]+)\ndescription: ([^\n]+)\n---\n([\s\S]+)', source)
        if not frontmatter or frontmatter[1] != selected or not frontmatter[2].strip():
            continue
        prefix = f'<skill_content name="{selected}">\n# Skill: {selected}\n'
        boundary = '\nBase directory for this skill: '
        if not output.startswith(prefix) or not output.endswith('</skill_content>'):
            continue
        if output.count('<skill_content') != 1 or output.count('</skill_content>') != 1 or output.count(boundary) != 1:
            continue
        returned, remainder = output[len(prefix):].split(boundary)
        base = remainder.split('\n', 1)[0]
        if not Path(base).is_absolute() or Path(base).resolve() != canonical.parent:
            continue
        if returned.strip('\n') != frontmatter[3].strip('\n'):
            continue
        body_complete = True
        body_total = sum(bool(line.strip()) for line in frontmatter[3].splitlines())
    if body_complete and len(covered) != len(lines):
        return {'covered': body_total, 'total': body_total, 'complete': True,
                'scope': 'canonical-skill-body', 'file_covered': len(covered), 'file_total': len(lines)}
    return {'covered': len(covered), 'total': len(lines), 'complete': len(covered) == len(lines)}


def loaded(evidence, root, skill):
    path = (root / '.claude/skills' / skill / 'SKILL.md').resolve()
    return any(call['success'] and call['name'] == 'skill' and str(path) in call['paths'] for call in evidence) or read_coverage(evidence, path)['complete']


def require_debug_file(host, path):
    if host != 'claude':
        return path.read_text() if path.exists() else ''
    assert path.is_file() and path.stat().st_size > 0, 'Claude debug evidence missing or empty'
    return path.read_text()


def require_host_success(transcript, exit_code, stderr='', debug=''):
    assert exit_code == 0, f'Host exit {exit_code}'
    assert 'Skill listing over budget' not in debug, 'Host truncated skill descriptions'
    failures = []
    for event in strict_events(transcript):
        if event.get('type') in ('error', 'turn.failed') or (event.get('type') == 'result' and event.get('is_error')):
            failures.append(event)
    assert not failures, f'Host error events: {failures}'
    answer = final_text(transcript)
    assert answer.strip(), 'Missing final answer'
    assert not re.search(r'usage limit|quota exceeded|rate.limit|out of credits|timed? out', answer + stderr, re.I), 'Quota or timeout failure'
    return answer


def strict_json(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = item
        return result
    def invalid_constant(value):
        raise ValueError('Nonfinite JSON constant')
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Nonfinite JSON number')
        return result
    return json.loads(value, object_pairs_hook=unique, parse_constant=invalid_constant, parse_float=finite_float)


def decoded_value_text(value):
    if isinstance(value, dict):
        return '\n'.join(key + '\n' + decoded_value_text(item) for key, item in value.items())
    if isinstance(value, list):
        return '\n'.join(decoded_value_text(item) for item in value)
    return value if isinstance(value, str) else str(value)


def decoded_audit_text(value, required=False):
    decoded = []
    for line in value.splitlines():
        if not line.strip():
            continue
        try:
            decoded.append(decoded_value_text(strict_json(line)))
        except ValueError:
            assert not required, 'Malformed or ambiguous native privacy event'
        # Preserve every string value even when a diagnostic/business JSON line
        # is malformed or repeats a key; a duplicate cannot erase a secret.
        for literal in re.findall(r'"(?:[^"\\]|\\.)*"', line):
            try:
                decoded.append(decoded_value_text(strict_json(literal)))
            except ValueError:
                pass
    return value + '\n' + '\n'.join(decoded)


def native_identity(value, prefix, length=26):
    return isinstance(value, str) and re.fullmatch(prefix + r'_[A-Za-z0-9]{' + str(length) + '}', value) is not None


def native_clock(value):
    return type(value) is int and 10**12 <= value < 10**13


def native_time(value):
    return (isinstance(value, dict) and set(value) == {'start', 'end'}
            and all(native_clock(item) for item in value.values()))


def native_envelope(event, part):
    if set(event) != {'type', 'timestamp', 'sessionID', 'part'} or not native_clock(event['timestamp']):
        return False
    common = {'id', 'messageID', 'sessionID', 'type'}
    kind = event['type']
    if kind == 'text':
        return set(part) == common | {'text', 'time'} and isinstance(part['text'], str) and native_time(part['time'])
    if kind == 'tool_use':
        if not (set(part) <= common | {'tool', 'callID', 'state', 'metadata'}
                and all(key in part for key in ('tool', 'callID', 'state'))
                and isinstance(part['tool'], str) and part['tool']
                and isinstance(part.get('metadata', {}), dict)):
            return False
        state = part['state']
        if not (isinstance(state, dict) and set(state) <= {'status', 'input', 'output', 'error', 'raw', 'metadata', 'title', 'time'}
                and state.get('status') in ('completed', 'error')
                and isinstance(state.get('input'), dict) and native_time(state.get('time'))
                and isinstance(state.get('metadata', {}), dict)
                and all(isinstance(state[key], str) for key in ('output', 'error', 'raw', 'title') if key in state)):
            return False
        return isinstance(state.get('output' if state['status'] == 'completed' else 'error'), str)
    if kind == 'step_start':
        return set(part) <= common | {'snapshot'} and isinstance(part.get('snapshot', ''), str)
    if kind == 'step_finish':
        tokens = part.get('tokens', {})
        if not (isinstance(tokens, dict) and set(tokens) <= {'total', 'input', 'output', 'reasoning', 'cache'}
                and all(type(value) is int and value >= 0 for key, value in tokens.items() if key != 'cache')
                and isinstance(tokens.get('cache', {}), dict)
                and set(tokens.get('cache', {})) <= {'write', 'read'}
                and all(type(value) is int and value >= 0 for value in tokens.get('cache', {}).values())):
            return False
        return (set(part) <= common | {'reason', 'snapshot', 'tokens', 'cost'}
                and all(isinstance(part.get(key, ''), str) for key in ('reason', 'snapshot'))
                and isinstance(part.get('tokens', {}), dict)
                and type(part.get('cost', 0)) in (int, float))
    return False


def secret_audit_text(transcript, host, metadata_pairs=None):
    """Normalize known host metadata only for nonsecret short-marker checks."""
    if host != 'opencode':
        return transcript
    pairs = {'step_start': 'step-start', 'step_finish': 'step-finish',
             'text': 'text', 'tool_use': 'tool'}
    result = []
    for line in transcript.splitlines(keepends=True):
        try:
            event = strict_json(line)
        except ValueError:
            result.append(line)
            continue
        part = event.get('part') if isinstance(event, dict) else None
        session = event.get('sessionID') if isinstance(event, dict) else None
        if not (isinstance(part, dict) and native_identity(session, 'ses')
                and part.get('sessionID') == session
                and native_identity(part.get('id'), 'prt')
                and native_identity(part.get('messageID'), 'msg')
                and ('callID' not in part or native_identity(part['callID'], 'call', 24))
                and event.get('type') in pairs
                and part.get('type') == pairs[event['type']]
                and native_envelope(event, part)):
            result.append(line + '\n' + decoded_value_text(event) + '\n')
            continue
        clocks = [(event, 'timestamp')]
        if event['type'] == 'text' and isinstance(part.get('time'), dict):
            clocks += [(part['time'], key) for key in ('start', 'end')]
        state = part.get('state')
        if event['type'] == 'tool_use' and isinstance(state, dict) and isinstance(state.get('time'), dict):
            clocks += [(state['time'], key) for key in ('start', 'end')]
        changed = False
        if metadata_pairs is not None:
            metadata_pairs.add((session, part['messageID']))
        event['sessionID'] = '<native session>'
        for key in ('sessionID', 'id', 'messageID', 'callID'):
            if key in part:
                part[key] = '<native identity>'
                changed = True
        for parent, key in clocks:
            value = parent.get(key)
            if type(value) is int and 10**12 <= value < 10**13:
                parent[key] = '<native timestamp>'
                changed = True
        result.append(json.dumps(event, ensure_ascii=False) + '\n' + decoded_value_text(event) + '\n'
                      if changed else line)
    return ''.join(result)


def require_private_channels(host, transcript, stderr='', raw_channels=(), secrets=(), prohibited=()):
    """Always scan raw full secrets; narrow metadata exclusion applies only to short nonsecrets."""
    raw = transcript + stderr + ''.join(raw_channels)
    require_safe_requests([], [], raw, secrets)
    decoded = decoded_audit_text(transcript, required=True) + decoded_audit_text(stderr)
    decoded += ''.join(decoded_audit_text(channel) for channel in raw_channels)
    require_safe_requests([], [], decoded, secrets)
    short = tuple(value for value in prohibited if isinstance(value, str)
                  and re.fullmatch(r'[0-9]{4}', value) and value not in secrets)
    require_safe_requests([], [], raw + decoded, tuple(value for value in prohibited if value not in short))
    pairs = set()
    normalized = secret_audit_text(transcript, host, pairs)
    if host == 'opencode':
        pattern = re.compile(r'(timestamp=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z level=INFO run=[0-9a-f]{8} message=process session\.id=)(ses_[A-Za-z0-9]{26})( messageID=)(msg_[A-Za-z0-9]{26})(\r?\n)?')
        lines = []
        for line in stderr.splitlines(keepends=True):
            match = pattern.fullmatch(line)
            if match and (match[2], match[4]) in pairs:
                line = match[1] + '<native session>' + match[3] + '<native message>' + (match[5] or '')
            lines.append(line)
        stderr = ''.join(lines)
    require_safe_requests([], [], decoded_audit_text(normalized) + decoded_audit_text(stderr)
                          + ''.join(decoded_audit_text(channel) for channel in raw_channels), short)


def require_safe_requests(frames, provider_requests, transcript, secrets=()):
    assert not provider_requests, 'Provider was contacted'
    assert all(frame.get('method') in ('system.capabilities', 'system.catalog') for frame in frames), 'Non-discovery RPC attempted'
    assert all(secret not in transcript for secret in secrets if secret), 'Seeded secret leaked'


def require_no_mcp(host, transcript, config):
    if host == 'claude':
        initial = [event for event in events(transcript) if event.get('type') == 'system' and event.get('subtype') == 'init']
        assert initial and initial[0].get('mcp_servers') == [], 'MCP initialization was not empty'
        assert initial[0].get('permissionMode') in ('manual', 'default'), 'Claude effective permission mode was not manual'
        return initial[0]
    assert config.get('mcp_disabled') is True and 'effective_mcp' in config, 'Effective no-MCP config missing'
    effective = config['effective_mcp']
    assert isinstance(effective, list if host == 'codex' else dict), 'Malformed effective MCP config'
    rows = effective if isinstance(effective, list) else effective.values()
    assert all(isinstance(row, dict) and row.get('enabled') is False for row in rows), 'MCP server remains enabled'
    assert not any('mcp' in call['name'] for call in tool_events(transcript)), 'MCP tool called'
    return config


def require_scheduled(evidence, frames, answer, root):
    assert not loaded(evidence, root, 'cs-capabilities'), 'Scheduled run loaded interactive bootstrap'
    assert not frames, 'Scheduled run called discovery'
    assert re.search(r'bank|banc', answer, re.I), 'Scheduled run did not address queued question'
    assert not re.search(r'whoami|quota|permission.*(?:denied|required)|cannot start|unable to start', answer, re.I), 'Scheduled run stopped before task consideration'
