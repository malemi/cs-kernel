from __future__ import annotations

import hashlib
import json
import os
import shlex
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from capabilities_events import strict_events


def requested_directory(value, clone):
    assert isinstance(value, str) and value, 'Missing Codex command cwd'
    assert not any(char in value for char in ('$', '`', '~', '\n')), 'Unresolved Codex command cwd'
    parsed = urlsplit(value)
    if parsed.scheme:
        assert parsed.scheme == 'file' and not parsed.netloc and not parsed.query and not parsed.fragment, 'Unknown Codex cwd URI'
        path = Path(unquote(parsed.path))
    else:
        path = Path(value)
    path = path if path.is_absolute() else clone / path
    assert path.is_dir(), f'Nonexistent Codex command cwd: {value}'
    resolved = path.resolve()
    assert resolved.is_relative_to(clone.resolve()), f'Outside-clone Codex command cwd: {value}'
    return resolved


def capture_command_context(transcript, clone, destination, launched_at, session_root=None):
    events = list(strict_events(transcript))
    threads = [event.get('thread_id') for event in events if event['type'] == 'thread.started']
    assert len(threads) == 1 and isinstance(threads[0], str) and threads[0], 'Missing or ambiguous Codex thread identity'
    thread = threads[0]
    assert all(char.isalnum() or char == '-' for char in thread), 'Malformed Codex thread identity'
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    sessions = Path(session_root) if session_root is not None else home / 'sessions'
    dates = {launched_at.astimezone(timezone.utc).strftime('%Y/%m/%d'), datetime.now(timezone.utc).strftime('%Y/%m/%d')}
    paths = [path for date in sorted(dates) for path in (sessions / date).glob(f'rollout-*-{thread}.jsonl')]
    assert len(paths) == 1, 'Missing or ambiguous Codex rollout evidence'
    source = paths[0]
    raw = source.read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    metadata = [row['payload'] for row in rows if row.get('type') == 'session_meta']
    commands = [row['payload']['item'] for row in rows if row.get('type') == 'event_msg'
                and row.get('payload', {}).get('item', {}).get('type') == 'CommandExecution']
    turns = [{key: row['payload'].get(key) for key in ('turn_id', 'model', 'effort')}
             for row in rows if row.get('type') == 'turn_context']
    receipt = {'thread_id': thread, 'source': str(source), 'source_sha256': hashlib.sha256(raw).hexdigest(),
               'session': [{key: row.get(key) for key in ('id', 'cwd', 'timestamp')} for row in metadata],
               'turns': turns,
               'commands': [{key: row.get(key) for key in ('id', 'cwd')} for row in commands]}
    destination.write_text(json.dumps(receipt, indent=2))
    assert len(metadata) == 1 and metadata[0].get('id') == thread, 'Mismatched Codex rollout session'
    assert turns and all(isinstance(turn['model'], str) and turn['model'] for turn in turns), 'Missing Codex session model evidence'
    assert requested_directory(metadata[0].get('cwd'), clone) == clone.resolve(), 'Mismatched Codex session launch cwd'
    terminal = [event['item'] for event in events if event['type'] == 'item.completed'
                and event.get('item', {}).get('type') == 'command_execution']
    identifiers = [row.get('id') for row in commands]
    assert all(isinstance(ident, str) and ident for ident in identifiers), 'Missing Codex rollout command identifier'
    assert len(set(identifiers)) == len(identifiers) and len(commands) == len(terminal), 'Mismatched Codex rollout command evidence'
    for row, item in zip(commands, terminal):
        assert shlex.split(item.get('command', '')) == row.get('command') and item.get('exit_code') == row.get('exit_code'), 'Mismatched Codex rollout command evidence'
    for row, item in zip(receipt['commands'], terminal):
        row['stdout_id'] = item.get('id')
    destination.write_text(json.dumps(receipt, indent=2))
    for row in commands:
        cwd = requested_directory(row.get('cwd'), clone)
        assert cwd == clone.resolve(), 'UNVERIFIABLE: clone-contained subdirectory cwd requires a cwd-aware relative-path audit'
    return receipt
