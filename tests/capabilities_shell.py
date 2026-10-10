from __future__ import annotations

import json
import re
import shlex
from pathlib import Path


def validate_cli_args(args, *, local=False, scheduled=False):
    assert isinstance(args, list) and args and all(isinstance(arg, str) for arg in args), 'Unresolved CLI arguments'
    assert not any(arg in ('-h', '--help') for arg in args), 'CLI help exploration attempted'
    if args == ['whoami']:
        return
    assert not local, 'Local case explored CLI or attempted publication'
    if args == ['config']:
        return
    assert not scheduled, 'Scheduled case attempted remote discovery or another CLI operation'
    assert len(args) in (2, 3) and args[0] == 'rpc' and args[1] in ('system.capabilities', 'system.catalog'), 'Non-discovery or unsupported CLI operation attempted'
    params = json.loads(args[2]) if len(args) == 3 else {}
    assert isinstance(params, dict), 'RPC parameters must be an object'
    if args[1] == 'system.capabilities':
        assert not params, 'Unexpected capabilities parameters'
    else:
        assert not params or (set(params) == {'system'} and isinstance(params['system'], str) and params['system']), 'Unexpected catalog parameters'


def status_diagnostic(words):
    if not words or words[0] not in ('echo', '/bin/echo', '/usr/bin/echo'):
        return False
    if len(words) == 2 and words[1] in ('$?', '--- exit $?', 'EXIT=$?', 'EXIT=${PIPESTATUS[0]}'):
        return True
    return all(re.fullmatch(r'[A-Za-z0-9 _=:/.,-]*', word)
               and (not word.startswith('-') or word.startswith('---'))
               for word in words[1:])


def shell_parts(command):
    assert isinstance(command, str) and command.strip(), 'Missing shell command'
    plain = shlex.split(command)
    if len(plain) == 3 and plain[0] in ('bash', '/bin/bash', '/usr/bin/bash', 'sh', '/bin/sh') and plain[1] in ('-c', '-lc'):
        command = plain[2]
    guarded = re.fullmatch(r'if \[ -f docs/\.doc-profile \]; then (.+); fi', command)
    if guarded:
        command = 'test -f docs/.doc-profile && ' + guarded.group(1)
    assert not any(char in command for char in ('`', '\n', '\r')), 'Unsupported shell expansion or multiline command'
    command = re.sub(r'(?<!\S)2>&1(?=$|\s|[;&|])|(?<!\S)2>/dev/null(?=$|\s|[;&|])', '', command)
    assert '<' not in command and '>' not in command, 'Unsupported shell redirection'
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
    lexer.commenters = ''
    lexer.whitespace_split = True
    groups, group, preceding = [], [], None
    for token in lexer:
        if token in ('&&', ';', '|', '||'):
            assert group, 'Empty shell command or unsupported separator'
            groups.append((preceding, group))
            group, preceding = [], token
        else:
            assert token != '&', 'Background command is not auditable'
            group.append(token)
    if group:
        groups.append((preceding, group))
    else:
        assert preceding == ';', 'Incomplete shell command'
    for index, (separator, words) in enumerate(groups):
        diagnostic = status_diagnostic(words)
        assert diagnostic or not any('$' in word for word in words), 'Unsupported shell expansion'
        if diagnostic:
            assert separator != '|' and (index + 1 == len(groups) or groups[index + 1][0] != '|'), 'Piped exit-status diagnostic'
    return groups


def checked_tree(root, path, resolve):
    if not path.exists():
        return
    for child in path.rglob('*') if path.is_dir() else (path,):
        resolve(root, str(child), listing=child.is_dir())


def git_targets(words, root, resolve):
    assert len(words) >= 2, 'Missing Git subcommand'
    verb, args = words[1], words[2:]
    allowed = {
        'status': {'-s', '--short', '--porcelain', '--porcelain=v1', '-b', '--branch', '--untracked-files=all'},
        'log': {'--oneline', '--all', '--decorate', '--no-decorate'},
        'diff': {'--stat', '--name-only', '--name-status', '--shortstat', '--cached', '--staged', '--no-ext-diff'},
        'ls-files': {'-v', '--stage', '--error-unmatch'},
        'check-ignore': {'-v', '--verbose'},
    }
    if verb == 'rev-parse':
        assert args in (['HEAD'], ['--verify', 'HEAD'], ['--show-toplevel'], ['--is-inside-work-tree']), 'Unsupported Git revision query'
        return []
    assert verb in allowed, 'Unsupported Git operation'
    paths = []
    while args:
        value, args = args[0], args[1:]
        if value == '--':
            paths.extend(args)
            break
        if value.startswith('-'):
            if verb == 'log' and (re.fullmatch(r'-[1-9][0-9]*|--max-count=[1-9][0-9]*', value)):
                continue
            if verb == 'log' and value == '-n':
                assert args and re.fullmatch(r'[1-9][0-9]*', args[0]), 'Unsupported Git count'
                args = args[1:]
                continue
            assert value in allowed[verb], f'Unsupported Git option: {value}'
        else:
            assert verb in ('ls-files', 'check-ignore'), 'Git paths require explicit -- separator'
            paths.append(value)
    assert paths or verb in ('status', 'log'), 'Unscoped Git file/content query'
    resolved = []
    for path in paths:
        assert not any(char in path for char in '*?[]:'), 'Unsupported Git pathspec'
        target = resolve(root, path, listing=True)
        checked_tree(root, target, resolve)
        resolved.append(target)
    return resolved


def read_arguments(verb, args):
    if verb == 'sed':
        assert len(args) >= 3 and args[0] == '-n' and re.fullmatch(r'[1-9][0-9]*(?:,[1-9][0-9]*)?p', args[1]), 'Only numeric sed print ranges are auditable'
        assert all(not arg.startswith('-') for arg in args[2:]), 'Unsupported sed option'
        return args[2:]
    flags = {
        'cat': re.compile(r'-[nbs]+'),
        'ls': re.compile(r'-[aldFh]+'),
        'wc': re.compile(r'-[lcwm]+'),
        'head': re.compile(r'-[1-9][0-9]*|-[nc][1-9][0-9]*'),
        'tail': re.compile(r'-[1-9][0-9]*|-[nc][1-9][0-9]*'),
        'grep': re.compile(r'-[nlcivEFH]+'),
        'rg': re.compile(r'-[nlcivFH]+'),
        'stat': re.compile(r'(?!)'),
    }
    assert verb in flags, f'Unsupported file command: {verb}'
    paths, pattern, ended = [], verb not in ('grep', 'rg'), False
    while args:
        value, args = args[0], args[1:]
        if value == '--' and not ended:
            ended = True
            continue
        if not ended and value.startswith('-'):
            if verb in ('head', 'tail') and value in ('-n', '-c'):
                assert args and re.fullmatch(r'[1-9][0-9]*', args[0]), 'Unsupported head/tail count'
                args = args[1:]
                continue
            if verb == 'rg' and value == '--files':
                pattern = True
                continue
            assert flags[verb].fullmatch(value), f'Unsupported {verb} option: {value}'
            continue
        if not pattern:
            pattern = True
        else:
            paths.append(value)
    assert pattern, 'Missing search pattern'
    return paths


def command_targets(command, root, resolve):
    targets, previous = [], None
    for separator, words in shell_parts(command):
        if separator in ('&&', '||'):
            if (separator == '&&' and previous is False) or (separator == '||' and previous is True):
                continue
        executable, args = words[0], words[1:]
        verb = Path(executable).name
        previous = None
        if status_diagnostic(words):
            continue
        if executable in ('cs', '.venv/bin/cs') or (executable in ('python', 'python3', '.venv/bin/python', '.venv/bin/python3') and args[:2] == ['-m', 'cs']):
            validate_cli_args(args[2:] if verb in ('python', 'python3') else args)
            continue
        assert executable in (verb, '/bin/' + verb, '/usr/bin/' + verb), 'Unknown executable path'
        if verb == 'test':
            negate = args[:1] == ['!']
            args = args[1:] if negate else args
            assert len(args) == 2 and args[0] in ('-f', '-d', '-e'), 'Unsupported file existence test'
            path = (root / args[1]).resolve()
            if path != (root / 'docs/.doc-profile').resolve():
                resolve(root, str(path), listing=True)
            previous = path.is_file() if args[0] == '-f' else path.is_dir() if args[0] == '-d' else path.exists()
            previous = not previous if negate else previous
            continue
        if verb in ('pwd', 'whoami'):
            assert not args, 'Unsupported session-check options'
            continue
        if verb == 'git':
            targets.extend(git_targets(words, root, resolve))
            continue
        assert not (separator == '|' and verb == 'rg' and '--files' in args), 'Piped filesystem listing is not a stdin filter'
        if separator == '|' and verb in ('grep', 'rg'):
            assert not any(char in arg for arg in args for char in '*?[]{}~()'), 'Expansion-capable stdin filter argument'
        paths = read_arguments(verb, args)
        if not paths and separator == '|' and verb in ('head', 'tail', 'wc', 'grep', 'rg'):
            continue
        assert paths or verb == 'ls', 'Unresolved read target'
        current = []
        for raw in paths or ['.']:
            if any(char in raw for char in '*?[]'):
                assert not Path(raw).is_absolute() and '..' not in Path(raw).parts, 'Unsupported wildcard path'
                prefix = re.split(r'[*?\[]', raw, 1)[0].rsplit('/', 1)[0]
                base = resolve(root, prefix or '.', listing=True)
                assert base != root.resolve(), 'Unbounded wildcard listing'
                checked_tree(root, base, resolve)
                expanded = [str(path) for path in root.glob(raw)]
            else:
                expanded = [raw]
            for value in expanded:
                target = resolve(root, value, listing=verb in ('ls', 'rg', 'grep', 'wc', 'stat'))
                if verb in ('grep', 'rg'):
                    assert target != root.resolve(), 'Unbounded clone search'
                    checked_tree(root, target, resolve)
                current.append(target)
        targets.extend(current)
    return targets
