"""Bounded synchronous context delivery from current private inventory artifacts.

Hook execution is not inspection authority. Auditors require the complete actual
native payload before effects; an unavailable/oversized snapshot keeps paging.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

SLOTS = 64
# Every slot is one hook process that verifies the whole view before it prints
# its part, and the native client runs them together: 64 of them on a view of
# 400,000 bytes take about 11 seconds on six cores. A hook the client cancels at
# its timeout invalidates the run's stream.
HOOK_TIMEOUT = 60
CHARS = 8000
LEGACY_CHARS = 7000
SCHEMA = 'cs.inventory.context.v1'


class CapacityError(ValueError):
    def __init__(self, required):
        super().__init__('context capacity exceeded; literal paging required')
        self.required = required
        self.path = None
        self.snapshot_digest = None
        self.event_id = None


def capacity_failure(exc, *, emit=False):
    from .observability_causal import decision
    value = decision('discovery_context_capacity', 'context_slots_exhausted',
        layer='source', phase='discovery', command='unanswered',
        method='operator.discovery.context', required=exc.required, available=SLOTS)
    if emit:
        try:
            from .config import load
            from .observability_producers import emit as record, inherited_context
            from .observability import context
            with context(inherited_context()):
                event = record(load(), 'discovery', 'failed', reason='incomplete-input',
                    command='unanswered', method='operator.discovery.context', causal=value,
                    error_file='cs/operator_context_delivery.py')
                if isinstance(event, dict):
                    from .observability import diagnostic_id
                    exc.event_id = diagnostic_id(event.get('event_id'))
        except Exception:
            pass
    return value


def parts(view, envelope_raw, envelope, session):
    """Visible lossless UTF-8 chunks with explicit immutable reconstruction keys."""
    combined = envelope_raw.decode('utf-8') + view.decode('utf-8')
    if '<system-reminder>' in combined or '</system-reminder>' in combined:
        raise ValueError('reserved native context marker')
    result = _parts(combined, view, envelope_raw, envelope, session, CHARS)
    if result is None:
        # Keep the complete old partition for Unicode-heavy input. Mixing
        # partitions would change the exact reconstruction expected by auditors.
        result = _parts(combined, view, envelope_raw, envelope, session, LEGACY_CHARS)
    if result is None:
        raise ValueError('context part exceeds native limit')
    return result


def _parts(combined, view, envelope_raw, envelope, session, chars):
    chunks = [combined[i:i + chars] for i in range(0, len(combined), chars)]
    if not chunks or len(chunks) > SLOTS:
        raise CapacityError(len(chunks))
    binding = {k: envelope[k] for k in ('owner_uid', 'nonce', 'source_identity',
        'supervisor', 'native_invocation', 'raw_sha256', 'view_sha256')}
    result = []
    for index, chunk in enumerate(chunks):
        header = {'schema': SCHEMA, **binding, 'session_id': session,
                  'index': index, 'count': len(chunks),
                  'envelope_bytes': len(envelope_raw), 'view_bytes': len(view),
                  'envelope_sha256': hashlib.sha256(envelope_raw).hexdigest(),
                  'payload_sha256': hashlib.sha256(combined.encode()).hexdigest(),
                  'part_sha256': hashlib.sha256(chunk.encode()).hexdigest()}
        value = json.dumps(header, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n' + chunk
        if len(value.encode('utf-16-le')) // 2 >= 10000:
            return None
        result.append(value)
    return result


def current_snapshot(context, session):
    from . import operator_health as health
    from . import operator_inventory_view as inventory
    if not isinstance(session, str) or not session or len(session) > 128:
        raise ValueError('invalid native session')
    path, view, envelope = inventory.load(context)
    native = envelope['native_invocation']['child_identity']
    chain, pid = [], os.getpid()
    for _ in range(32):
        row, pid = health.identity(pid)
        chain.append(row)
        if row == context['supervisor']:
            break
    else:
        raise ValueError('hook supervisor ancestry differs')
    if native not in chain[:-1] or health.identity(native['pid'])[0] != native:
        raise ValueError('hook native process differs')
    envelope_raw = inventory.read_private(path / 'inventory-view-envelope.json')
    try:
        return path, parts(view, envelope_raw, envelope, session)
    except CapacityError as exc:
        exc.path = path
        exc.snapshot_digest = hashlib.sha256(envelope_raw + view).hexdigest()
        raise


def overlay(directory, python):
    """Add only hooks; native settings layering preserves all other settings."""
    from .operator_inventory_view import exclusive
    hooks = [{'type': 'command', 'command': shlex.join([python, '-B', '-m',
        'cs.operator_context_delivery', str(index)]), 'timeout': HOOK_TIMEOUT}
        for index in range(SLOTS)]
    value = {'hooks': {'PostToolUse': [{'matcher': '.*', 'hooks': hooks}],
                       'UserPromptSubmit': [{'hooks': hooks}]}}
    path = Path(directory) / 'inventory-context-settings.json'
    exclusive(path, json.dumps(value, separators=(',', ':')).encode())
    return path


def main():
    try:
        index = int(sys.argv[1])
        if not 0 <= index < SLOTS:
            raise ValueError('invalid context slot')
        incoming = sys.stdin.buffer.read(4 * 1024 * 1024 + 1)
        if len(incoming) > 4 * 1024 * 1024:
            raise ValueError('oversized hook input')
        event = json.loads(incoming)
        if event.get('hook_event_name') not in ('PostToolUse', 'UserPromptSubmit'):
            raise ValueError('unsupported context boundary')
        session = event['session_id']
        context = json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
        path, values = current_snapshot(context, session)
        if index >= len(values):
            return
        token = hashlib.sha256((session + '\0' + values[index]).encode()).hexdigest()
        from .operator_inventory_view import exclusive
        exclusive(path / ('context-delivered-' + token), b'')
        print(json.dumps({'hookSpecificOutput': {'hookEventName': event['hook_event_name'],
            'additionalContext': values[index]}}, ensure_ascii=False))
    except CapacityError as exc:
        if index != 0 or exc.path is None or exc.snapshot_digest is None:
            return
        try:
            from .operator_inventory_view import exclusive
            token = hashlib.sha256((session + '\0' + exc.snapshot_digest).encode()).hexdigest()
            exclusive(exc.path / ('context-capacity-notice-' + token), b'')
            from .observability import context as diagnostic_context
            from .observability_producers import inherited_context
            with diagnostic_context(inherited_context()):
                cause = capacity_failure(exc, emit=True)
            refs = cause['refs'] if cause else {}
            notice = {'notice': 'context_slots_exhausted', 'required': exc.required,
                'available': SLOTS, 'snapshot_sha256': exc.snapshot_digest,
                'run_id': refs.get('run_id'), 'attempt_id': refs.get('attempt_id'),
                'event_id': exc.event_id, 'directory': str(exc.path),
                'envelope_path': 'inventory-view-envelope.json',
                'progress_path': 'inventory-view-progress.json',
                'instruction': 'Paths are relative to directory. Read the entire envelope, paging its bytes '
                    'if needed, then execute its complete literal view page_plan through EOF. '
                    'Progress is advisory. '
                    'This notice grants no inspection credit. Never select from a prefix or perform '
                    'effects before complete inspection. If full paging cannot finish within existing '
                    'bounds, stop with context_slots_exhausted and these counts/references. '
                    'Do not retry an identical run.'}
            value = json.dumps(notice, ensure_ascii=False, separators=(',', ':'))
            if len(value.encode('utf-16-le')) // 2 >= 10000:
                raise ValueError('capacity notice exceeds native limit')
            print(json.dumps({'hookSpecificOutput': {'hookEventName': event['hook_event_name'],
                'additionalContext': value}}, ensure_ascii=False))
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            pass
        return
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError):
        # No artifact yet (including initial background Bash) is not delivery.
        # Missing/invalid/late content receives no audit coverage or replay.
        return


if __name__ == '__main__':
    main()


def delivered(events, view, envelope_raw, envelope):
    """Require genuine paired native responses and complete payload before effects."""
    from .operator_native_hooks import hook_indices
    from .operator_inventory_view import effect_words
    if not any(e.get('type') == 'system' and str(e.get('subtype', '')).startswith('hook_') for e in events):
        return False
    indices = hook_indices(events)
    sessions = {e['session_id'] for e in events if e.get('type') == 'system' and e.get('subtype') == 'init'}
    if len(sessions) != 1:
        raise ValueError('ambiguous context session')
    try:
        expected = parts(view, envelope_raw, envelope, sessions.pop())
    except ValueError:
        return False
    seen, early = set(), False
    for index, event in enumerate(events):
        if index in indices and event.get('subtype') == 'hook_response' and event.get('hook_event') in ('PostToolUse', 'UserPromptSubmit'):
            try:
                output = json.loads(event['stdout'])
            except ValueError:
                output = {}
            specific = output.get('hookSpecificOutput', {}) if isinstance(output, dict) else {}
            value = specific.get('additionalContext') if isinstance(specific, dict) else None
            if isinstance(value, str) and value.startswith('{') and SCHEMA in value.split('\n', 1)[0]:
                if specific.get('hookEventName') != event['hook_event'] or value not in expected:
                    raise ValueError('foreign or transformed native context')
                part = expected.index(value)
                if part in seen:
                    raise ValueError('duplicate native context')
                seen.add(part)
        message = event.get('message')
        blocks = message.get('content', []) if isinstance(message, dict) else []
        for block in blocks if isinstance(blocks, list) else []:
            if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                try:
                    words = shlex.split(block.get('input', {}).get('command', ''))
                except (ValueError, TypeError, AttributeError):
                    continue
                if effect_words(words):
                    early = early or len(seen) != len(expected)
    return len(seen) == len(expected) and not early
