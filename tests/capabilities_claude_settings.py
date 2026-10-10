from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shlex
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def filtered_settings(data, home):
    result = copy.deepcopy(data)
    kit = home / '.config/mrcall-ai-kit'
    installed = {str(kit / rel): str((kit / rel).resolve()) for rel in ('router-hook.py', 'scope-guard/claude/scope-guard.py')}
    identities = set(installed.values())
    removed = []
    for event, groups in data.get('hooks', {}).items():
        kept_groups = []
        for group in groups:
            kept = []
            for hook in group['hooks']:
                command = hook.get('command', '')
                if hook.get('type') != 'command':
                    assert 'mrcall-ai-kit' not in json.dumps(hook), 'Unknown kit hook type'
                    kept.append(copy.deepcopy(hook))
                    continue
                words = shlex.split(command)
                paths = [str(Path(word).expanduser().resolve()) for word in words if word.startswith(('/', '~'))]
                suspected = 'mrcall-ai-kit' in command or any(path in identities for path in paths)
                if not suspected:
                    kept.append(copy.deepcopy(hook))
                    continue
                assert len(words) == 2 and words[0] == 'python3', 'Ambiguous kit hook command'
                path = Path(words[1]).expanduser()
                assert path.is_absolute() and str(path.resolve()) in identities, 'Unknown kit hook script'
                assert str(path) in installed, 'Unidentified kit hook alias'
                removed.append({'event': event, 'matcher': group.get('matcher'), 'script': str(path), 'resolved_script': str(path.resolve()), 'script_sha256': sha(path), 'command_sha256': hashlib.sha256(command.encode()).hexdigest()})
            if kept:
                kept_groups.append({**copy.deepcopy(group), 'hooks': kept})
        if kept_groups:
            result['hooks'][event] = kept_groups
        else:
            result['hooks'].pop(event)
    assert result.get('permissions') == data.get('permissions')
    assert {k: v for k, v in result.items() if k != 'hooks'} == {k: v for k, v in data.items() if k != 'hooks'}
    return result, removed


def prepare_profile(root, clone, home=None):
    home = home or Path.home()
    source = home / '.claude/settings.json'
    original = source.read_bytes()
    data = json.loads(original)
    filtered, removed = filtered_settings(data, home)
    assert removed, 'No identified kit hooks found in current user settings'
    assert not filtered.get('disableAllHooks'), 'All-hook disabling is not permitted'
    required = {'datetime': home / '.claude/hooks/inject-datetime.sh', 'send_gate': home / '.claude/hooks/cs-send-gate.py'}
    commands = {(event, group.get('matcher'), hook.get('command')) for event, groups in filtered.get('hooks', {}).items() for group in groups for hook in group['hooks'] if hook.get('type') == 'command'}
    assert ('UserPromptSubmit', None, str(required['datetime'])) in commands, 'Datetime hook missing'
    assert ('PreToolUse', 'Bash', str(required['send_gate'])) in commands, 'Bash send gate missing'
    overlay = root / 'standalone-user-settings.json'
    with os.fdopen(os.open(overlay, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(filtered, stream, indent=2)
    for path in required.values():
        assert path.is_file(), 'Required non-kit hook script missing'
    for name in ('settings.json', 'settings.local.json'):
        path = clone / '.claude' / name
        if path.is_file():
            project = json.loads(path.read_text())
            assert not project.get('disableAllHooks'), 'Project disables hooks'
            _, project_removed = filtered_settings(project, home)
            assert not project_removed, 'Project source reintroduces kit hooks'
    tracer = shutil.which('strace')
    assert tracer, 'Required hook process tracer unavailable'
    paths = {'tracer': Path(tracer).resolve(), 'user': source, 'overlay': overlay, 'project': clone / '.claude/settings.json', 'local': clone / '.claude/settings.local.json', **required}
    receipt = {'trace_method': 'strace execve filtered to retained datetime/send-gate script paths; successful process exit required', 'profile': 'standalone-clone', 'setting_sources': 'project,local', 'paths': {key: str(path) for key, path in paths.items()}, 'hashes': {key: sha(path) for key, path in paths.items()}, 'removed': removed, 'permissions_equal': True, 'other_settings_equal': True, 'nonkit_hooks_equal': True}
    assert sha(source) == hashlib.sha256(original).hexdigest(), 'User settings changed while preparing overlay'
    verify_profile(receipt)
    return receipt


def verify_profile(receipt):
    assert receipt['hashes'] == {key: sha(Path(path)) for key, path in receipt['paths'].items()}, 'Claude runtime profile drift'
    assert Path(receipt['paths']['overlay']).stat().st_mode & 0o777 == 0o600, 'Private overlay permissions changed'
    return {'hashes': receipt['hashes'], 'overlay_mode': '0600', 'unchanged': True}


def traced_command(argv, receipt, trace):
    return [receipt['paths']['tracer'], '-f', '-e', 'trace=execve', '-P', receipt['paths']['datetime'], '-P', receipt['paths']['send_gate'], '-o', str(trace), '--', *argv]


def require_hook_execution(receipt, debug, trace, bash_required):
    assert not any(value in debug for value in ('Session memory:', 'router-hook.py', 'scope-guard.py')), 'Kit injection or execution remains present'
    assert 'Hook UserPromptSubmit (UserPromptSubmit) success:' in debug and 'Now:' in debug, 'Datetime hook output missing'
    evidence = {}
    for key in ('datetime', 'send_gate') if bash_required else ('datetime',):
        path = re.escape(receipt['paths'][key])
        matches = re.findall(r'(?m)^(\d+)\s+execve\("' + path + r'", .*\)\s+= 0$', trace)
        assert matches, f'Retained {key} hook was not executed'
        for pid in matches:
            assert re.search(r'(?m)^' + pid + r'\s+\+\+\+ exited with 0 \+\+\+$', trace), f'Retained {key} hook did not exit successfully'
        evidence[key] = {'path': receipt['paths'][key], 'pids': [int(pid) for pid in matches], 'exit': 0}
    return evidence
