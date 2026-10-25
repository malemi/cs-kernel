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

SLOTS = 16
CHARS = 7000
SCHEMA = 'cs.inventory.context.v1'


def parts(view, envelope_raw, envelope, session):
    """Visible lossless UTF-8 chunks with explicit immutable reconstruction keys."""
    combined = envelope_raw.decode('utf-8') + view.decode('utf-8')
    if '<system-reminder>' in combined or '</system-reminder>' in combined:
        raise ValueError('reserved native context marker')
    chunks = [combined[i:i + CHARS] for i in range(0, len(combined), CHARS)]
    if not chunks or len(chunks) > SLOTS:
        raise ValueError('context capacity exceeded; literal paging required')
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
            raise ValueError('context part exceeds native limit')
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
    return path, parts(view, inventory.read_private(path / 'inventory-view-envelope.json'), envelope, session)


def overlay(directory, python):
    """Add only hooks; native settings layering preserves all other settings."""
    from .operator_inventory_view import exclusive
    hooks = [{'type': 'command', 'command': shlex.join([python, '-B', '-m',
        'cs.operator_context_delivery', str(index)]), 'timeout': 10}
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
        return False  # Unsupported compact payload keeps valid literal paging.
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
