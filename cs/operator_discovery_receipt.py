"""Optional private transport of unchanged canonical discovery output."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import warnings
import shlex
import stat
import sys
import time
import threading

CLAUDE_SHA256 = 'f1f6e96e0d8342b9dbf41d7e88255397a6a52ce3d8736ad6a4c6b59c9b62fefa'
CLAUDE_VERSION = '2.1.296'
COMMAND = '.venv/bin/python -m cs unanswered --days 14 --json --all-buckets'
ARGV = ['unanswered', '--days', '14', '--json', '--all-buckets']
LIMIT = 2 * 1024 * 1024
CAPTURE_SECONDS = 5
CLEANUP = r"{ \builtin unalias -- 'unsetenv'; \builtin unset -f -- 'unsetenv'; } >/dev/null 2>&1 || true"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def package_digest():
    root = Path(__file__).parent
    rows = [[str(p.relative_to(root)), sha(p.read_bytes())] for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    return sha(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode())


def proc(pid):
    root = Path('/proc') / str(pid)
    before = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    argv = [p.decode() for p in (root / 'cmdline').read_bytes().split(b'\0') if p]
    executable = str((root / 'exe').resolve())
    after = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    if before[1] != after[1] or before[19] != after[19]:
        raise ValueError('process identity changed')
    return {'pid': pid, 'ppid': int(before[1]), 'started_ticks': int(before[19]),
            'argv': argv, 'executable': executable}


def extract_wrapper(argv, *, command=COMMAND):
    if len(argv) not in (3, 4) or argv[1:-1] not in (['-c'], ['-c', '-l']):
        raise ValueError('unsupported shell argv')
    text = argv[-1]
    prefix = ''
    if text.startswith('source '):
        end = text.find(' 2>/dev/null || true && ')
        if end < 0:
            raise ValueError('unsupported source prefix')
        source = shlex.split(text[7:end])
        if len(source) != 1 or not re.fullmatch(r'/home/[^/\s]+/\.claude/shell-snapshots/snapshot-bash-[A-Za-z0-9_.-]+\.sh', source[0]):
            raise ValueError('unsupported snapshot path')
        prefix = text[:end + len(' 2>/dev/null || true && ')]
        text = text[len(prefix):]
    if text.startswith('shopt -u extglob 2>/dev/null || true && '):
        text = text[len('shopt -u extglob 2>/dev/null || true && '):]
    if not text.startswith(CLEANUP + ' && eval '):
        raise ValueError('unsupported cleanup prefix')
    text = text[len(CLEANUP + ' && eval '):]
    match = re.fullmatch(r"('(?:[^']|'\"'\"')*')( < /dev/null)? && pwd -P >\| (/tmp/claude-[A-Za-z0-9-]+-cwd)", text)
    if not match:
        raise ValueError('unsupported eval or cwd suffix')
    payload = shlex.split(match[1])
    if len(payload) != 1 or command is not None and payload[0] != command:
        raise ValueError('eval payload differs from canonical native input')
    return {'payload': payload[0], 'snapshot_prefix': bool(prefix),
            'platform_stdin_redirect': bool(match[2]), 'cwd_file': match[3],
            'shell_argv_digest': sha(json.dumps(argv, separators=(',', ':')).encode())}


def directory_path():
    value = os.environ.get('CS_OPERATOR_ACCEPTANCE_RECEIPT', '')
    nonce = os.environ.get('CS_OPERATOR_ACCEPTANCE_NONCE', '')
    if not value or not re.fullmatch('[a-f0-9]{32}', nonce):
        raise ValueError('invalid optional discovery context')
    path = Path(value)
    if not path.is_absolute() or path.parent.resolve() != path.parent or path.is_symlink():
        raise ValueError('invalid receipt destination')
    return path.parent / (path.name + '.discovery')


def private_dir(path, create=False):
    parent = path.parent
    if parent.resolve() != parent:
        raise ValueError('symlink parent')
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700:
            raise ValueError('receipt parent is not private')
        if create:
            try: os.mkdir(path.name, mode=0o700, dir_fd=fd)
            except FileExistsError: pass
        child = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
    finally:
        os.close(fd)
    meta = os.fstat(child)
    if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700:
        os.close(child)
        raise ValueError('receipt directory is not private')
    return child


def _capture(output, value, code, owner, cli_pid, deadline, status_fd, business=None):
    temporary = None
    fd = None
    partial_created = False
    try:
        if business is None:
            context = json.loads(os.environ.get('CS_OPERATOR_DISCOVERY_SUPERVISOR', ''))
            destination = directory_path()
            nonce = os.environ.get('CS_OPERATOR_ACCEPTANCE_NONCE', '')
            expected_argv = ARGV
            command = COMMAND
        else:
            from . import operator_read_outcomes as outcomes
            health = outcomes.context()
            context = health['supervisor']
            destination = outcomes.directory_path()
            nonce = health['nonce']
            expected_argv = business['argv']
            command = '.venv/bin/python -m cs ' + shlex.join(expected_argv)
            if (outcomes.command_scope(command) != business or health['owner_uid'] != owner
                    or not outcomes.eligible(value, business, owner) or code != business['exit_code']):
                return
        if not isinstance(context, dict) or set(context) != {'pid', 'started_ticks'} or any(type(context[k]) is not int for k in context):
            return
        fd = private_dir(destination, create=True)
        stage = 'canonical_argv_and_size'
        if len(output) > LIMIT or sys.argv[1:] != expected_argv:
            raise ValueError('capture guard')
        chain = []
        stage = 'ancestry'
        pid = cli_pid
        for _ in range(32):
            if time.monotonic() >= deadline:
                raise ValueError("capture deadline")
            row = proc(pid)
            chain.append(row)
            if row['pid'] == context['pid']:
                if row['started_ticks'] != context['started_ticks']:
                    raise ValueError('capture guard')
                break
            pid = row['ppid']
        else: raise ValueError('capture guard')
        if len(chain) < 4 or chain[-1]['pid'] != context['pid']:
            raise ValueError('capture guard')
        stage = 'shell_identity'
        shell = chain[1]
        if shell['executable'] != str(Path('/bin/bash').resolve()):
            raise ValueError('capture guard')
        stage = 'wrapper'
        structure = extract_wrapper(shell['argv'], command=command if business is None else None)
        if business is not None and outcomes.command_scope(structure['payload']) != business:
            raise ValueError('business wrapper scope differs')
        stage = 'native_identity'
        native = chain[2]
        if not native['executable'].endswith('/versions/' + CLAUDE_VERSION) or sha(Path(native['executable']).read_bytes()) != CLAUDE_SHA256:
            raise ValueError('capture guard')
        stage = 'private_record'
        record = {'schema_version': 1, 'nonce': nonce,
                  'owner_uid': owner, 'kernel_source_digest': package_digest(),
                  'kernel_package_root': str(Path(__file__).parent),
                  'pythonpath': os.environ.get('PYTHONPATH', ''),
                  'capture_worker_identity': {'pid': os.getpid(), 'started_ticks': int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])},
                  'argv': sys.argv[1:], 'cli_identity': {k:chain[0][k] for k in ('pid','started_ticks')},
                  'native_identity': {k:native[k] for k in ('pid','started_ticks')},
                  'supervisor_identity': context, 'ancestry': chain, 'wrapper': structure,
                  'claude_version': CLAUDE_VERSION, 'claude_sha256': CLAUDE_SHA256,
                  'shell_executable_sha256': sha(Path(shell['executable']).read_bytes()),
                  'exit_code': code, 'output_length': len(output), 'output_sha256': sha(output),
                  'output': output.decode(), 'discovery': json.loads(output) if business is None else value}
        if business is not None:
            record['business'] = business
        if time.monotonic() > deadline: raise ValueError('capture deadline')
        encoded = json.dumps(record, sort_keys=True).encode()
        if len(encoded) > LIMIT * 3: return
        if len(os.listdir(fd)) >= 8: return
        name = str(chain[0]['pid']) + '-' + str(chain[0]['started_ticks']) + '.json'
        temporary = name + '.partial'
        file = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        partial_created = True
        os.write(status_fd, temporary.encode())
        with os.fdopen(file, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if time.monotonic() > deadline: raise ValueError('capture deadline')
        os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
    except Exception as error:
        if fd is not None and len(os.listdir(fd)) < 8:
            try:
                name = 'failure-' + str(cli_pid) + '.json'
                failure = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                with os.fdopen(failure, 'w') as stream:
                    json.dump({'stage': stage, 'error_class': type(error).__name__, 'phase_proof': False}, stream)
            except Exception:
                pass
        return
    finally:
        if fd is not None:
            if temporary is not None and partial_created:
                try: os.unlink(temporary, dir_fd=fd)
                except FileNotFoundError: pass
            os.close(fd)


def _fork(target, args):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        pid = os.fork()
    if pid == 0:
        try:
            target(*args)
        except BaseException:
            pass
        finally:
            os._exit(0)
    return pid


def _wait(pid, deadline):
    while True:
        try:
            if os.waitpid(pid, os.WNOHANG)[0]: return True
        except ChildProcessError:
            return True
        if time.monotonic() >= deadline: return False
        time.sleep(min(.005, max(0, deadline - time.monotonic())))


def _remove_partial(name, destination=None):
    fd = private_dir(destination if destination is not None else directory_path())
    try:
        meta = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISREG(meta.st_mode) and meta.st_uid == os.getuid() and stat.S_IMODE(meta.st_mode) == 0o600:
            os.unlink(name, dir_fd=fd)
    except FileNotFoundError:
        pass
    finally:
        os.close(fd)


def _reap_later(pid):
    def reap():
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
    threading.Thread(target=reap, daemon=True).start()


def _cancel(pid, deadline):
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if not _wait(pid, deadline):
        _reap_later(pid)


def capture(output, value, code, owner, *, business=None):
    if business is None and not os.environ.get('CS_OPERATOR_ACCEPTANCE_RECEIPT'):
        return
    if business is not None and not os.environ.get('CS_OPERATOR_HEALTH_CONTEXT'):
        return
    deadline = time.monotonic() + CAPTURE_SECONDS
    reserve = min(.5, CAPTURE_SECONDS / 4)
    read_fd = write_fd = None
    worker = cleaner = None
    try:
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        cli_pid = os.getpid()
        worker = _fork(_capture, (output, value, code, owner, cli_pid, deadline - reserve, write_fd, business))
        os.close(write_fd)
        write_fd = None
        if _wait(worker, deadline - reserve):
            worker = None
        else:
            _cancel(worker, deadline - reserve / 2)
            worker = None
        message = os.read(read_fd, 256).decode()
        if re.fullmatch(str(cli_pid) + r'-\d+\.json\.partial', message) and time.monotonic() < deadline:
            if business is None:
                destination = None
            else:
                from .operator_read_outcomes import directory_path as business_directory
                destination = business_directory()
            cleaner = _fork(_remove_partial, (message, destination))
            if _wait(cleaner, deadline - reserve / 4):
                cleaner = None
            else:
                _cancel(cleaner, deadline)
                cleaner = None
    except Exception:
        for pid in (worker, cleaner):
            if pid is not None:
                _cancel(pid, deadline)
    finally:
        for fd in (read_fd, write_fd):
            if fd is not None:
                os.close(fd)


def pin_native(binary):
    """Identify the reviewed emitter before launch; unknown emitters stay unsupported."""
    try:
        path = Path(shutil.which(binary) or binary).resolve(strict=True)
        meta = path.stat()
        digest = sha(path.read_bytes())
        after = path.stat()
        keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if (not stat.S_ISREG(meta.st_mode) or
                any(getattr(meta, k) != getattr(after, k) for k in keys) or
                not str(path).endswith('/versions/' + CLAUDE_VERSION) or digest != CLAUDE_SHA256):
            return None
        return {'path': str(path), 'sha256': digest, 'version': CLAUDE_VERSION,
                'file_identity': [getattr(meta, k) for k in keys]}
    except (OSError, ValueError):
        return None


def bind_native(pinned, child):
    """Bind a prelaunch fingerprint to the live executable that emits the stream."""
    if not pinned:
        return None
    try:
        live = proc(child['pid'])
        if {k: live[k] for k in ('pid', 'started_ticks')} != child:
            return None
        current = pin_native(live['executable'])
        if current != pinned:
            return None
        return {**pinned, 'child_identity': child}
    except (OSError, KeyError, ValueError):
        return None


def _native_exit_file(path, session, task, code):
    """Check the pinned emitter's task trailer beneath its owner-private root."""
    root = Path('/tmp') / ('claude-' + str(os.getuid()))
    target = Path(path)
    parts = target.relative_to(root).parts
    if (len(parts) != 4 or parts[1:] != (session, 'tasks', task + '.output') or
            any(part in ('', '.', '..') for part in parts)):
        raise ValueError('unsupported native output path')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700:
            raise ValueError('native output root is not private')
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            if os.fstat(fd).st_uid != os.getuid():
                raise ValueError('foreign native directory')
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or
                    before.st_nlink != 1 or before.st_size > LIMIT * 3):
                raise ValueError('unsafe native output')
            raw = stream.read(LIMIT * 3 + 1)
            after = os.fstat(stream.fileno())
        if (len(raw) > LIMIT * 3 or any(getattr(before, k) != getattr(after, k)
                for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')) or
                not raw.endswith(('\n[exited with code ' + str(code) + ']\n').encode())):
            raise ValueError('native output exit mismatch')
        return {'path': str(target), 'sha256': sha(raw), 'bytes': len(raw)}
    finally:
        os.close(fd)


def _automatic_completion(events, use, raw_use, raw_result, child, producer):
    """Accept only the evidenced single-segment foreground-to-background task."""
    def require(value):
        if not value:
            raise ValueError('unsupported automatic discovery')
    require(isinstance(producer, dict) and producer.get('child_identity') == child and
            producer.get('sha256') == CLAUDE_SHA256 and producer.get('version') == CLAUDE_VERSION)
    require(isinstance(producer.get('path'), str) and
            producer['path'].endswith('/versions/' + CLAUDE_VERSION) and
            isinstance(producer.get('file_identity'), list) and len(producer['file_identity']) == 5)
    from .operator_native_hooks import hook_indices
    hooks = hook_indices(events)
    first = next(e for i, e in enumerate(events) if i not in hooks)
    require(first.get('type') == 'system' and first.get('subtype') == 'init')
    session = first.get('session_id')
    require(isinstance(session, str) and re.fullmatch(r'[A-Za-z0-9-]+', session))
    require(first.get('claude_code_version') == CLAUDE_VERSION)
    require(sum(e.get('type') == 'system' and e.get('subtype') == 'init' for e in events) == 1)
    require(sum(e.get('type') == 'result' for e in events) == 1)
    terminal = events[-1]
    require(terminal.get('type') == 'result' and terminal.get('subtype') == 'success' and
            terminal.get('is_error') is False and terminal.get('terminal_reason') == 'completed' and
            type(terminal.get('num_turns')) is int and terminal['num_turns'] > 0 and
            type(terminal.get('safety_stops')) is int and terminal['safety_stops'] == 0 and
            terminal.get('api_error_status') is None)
    require(type(terminal.get('result_index')) is int and terminal['result_index'] == 0 and
            terminal.get('origin') is None)
    ids = [e.get('uuid') for e in events]
    require(all(isinstance(v, str) and v for v in ids) and len(ids) == len(set(ids)))
    require(all(e.get('session_id') == session for e in events))
    starts = [(i, e) for i, e in enumerate(events) if e.get('type') == 'system' and
              e.get('subtype') == 'task_started' and e.get('tool_use_id') == use['tool_use_id']]
    require(len(starts) == 1)
    start_index, start = starts[0]
    tool_indices = [i for i, e in enumerate(events) if e.get('type') == 'assistant' and
                    raw_use in e.get('message', {}).get('content', [])]
    require(len(tool_indices) == 1 and tool_indices[0] < start_index)
    task, run = start.get('task_id'), start.get('run_id')
    require(isinstance(task, str) and re.fullmatch(r'[A-Za-z0-9_-]+', task) and
            isinstance(run, str) and bool(run))
    require(start.get('task_type') == 'local_bash' and start.get('is_backgrounded') is False)
    require(sum(e.get('type') == 'system' and e.get('subtype') == 'task_started' and
                (e.get('task_id') == task or e.get('run_id') == run) for e in events) == 1)
    require(sum(e.get('type') == 'system' and e.get('subtype') == 'task_notification' and
                e.get('tool_use_id') == use['tool_use_id'] for e in events) == 1)
    state, advertised, result_index, code, output = 'started', False, None, None, None
    last_listing = None
    description = raw_use.get('input', {}).get('description')
    require(isinstance(description, str) and description and '\n' not in description)
    for index, event in enumerate(events):
        message = event.get('message', {})
        blocks = message.get('content', []) if isinstance(message, dict) else []
        if raw_result in blocks:
            require(event.get('type') == 'user' and state == 'backgrounded' and result_index is None and
                    raw_result.get('is_error', False) is False)
            metadata = event.get('tool_use_result', {})
            require(metadata.get('backgroundTaskId') == task and metadata.get('interrupted') is False)
            result_index = index
        if event.get('type') != 'system':
            continue
        subtype = event.get('subtype')
        if index in hooks:
            continue
        require(subtype in ('init', 'background_tasks_changed', 'task_started',
                            'task_updated', 'task_notification'))
        if subtype == 'background_tasks_changed':
            listing = event.get('tasks')
            require(isinstance(listing, list))
            last_listing = listing
            matches = [row for row in listing if row.get('task_id') == task]
            require(len(matches) <= 1 and all(row.get('task_id') != task and
                    row.get('run_id') != run for row in listing if row not in matches))
            if matches:
                require(index > start_index and state != 'notified' and
                        matches[0].get('run_id') == run and matches[0].get('task_type') == 'local_bash')
                advertised = True
            elif advertised:
                require(state == 'notified')
                advertised = False
        elif event.get('task_id') == task and subtype != 'task_started':
            require(event.get('run_id') == run and index > start_index)
            if subtype == 'task_updated':
                patch = event.get('patch')
                if state == 'started':
                    require(advertised and patch == {'is_backgrounded': True})
                    state = 'backgrounded'
                else:
                    require(state == 'backgrounded' and result_index is not None and
                            isinstance(patch, dict) and set(patch) == {'status', 'end_time'} and
                            patch['status'] in ('completed', 'failed') and type(patch['end_time']) is int)
                    state = patch['status']
            elif subtype == 'task_notification':
                require(state in ('completed', 'failed') and event.get('status') == state and
                        event.get('tool_use_id') == use['tool_use_id'])
                summary = event.get('summary', '')
                if state == 'completed':
                    require(summary == 'Background command "' + description + '" completed (exit code 0)')
                    code = 0
                else:
                    require(summary == 'Background command "' + description + '" failed with exit code 3')
                    code = 3
                output = _native_exit_file(event.get('output_file'), session, task, code)
                state = 'notified'
            else:
                require(False)
    require(state == 'notified' and not advertised and result_index is not None and last_listing == [])
    return {'task_id': task, 'run_id': run, 'tool_use_id': use['tool_use_id'],
            'exit_code': code, 'native_output': output, 'producer': producer}


def join(native_uses, phases, events, child, owner, producer=None, *, lifecycle=None):
    for row in phases:
        if isinstance(row, dict) and row.get('phase') == 'discovery':
            row['discovery_complete'] = False
            row['discovery'] = []
            row['held_count'] = 0
    try:
        selected = [row for row in native_uses if row['phase'] == 'discovery']
        results = [row for row in phases if row['phase'] == 'discovery']
        sessions = [e.get('session_id') for e in events if e.get('type') == 'system' and e.get('subtype') == 'init']
        terminals = [e for e in events if e.get('type') == 'result']
        if lifecycle is not None and lifecycle.get('proof', {}).get('version') == 2:
            from .operator_native_composition import composition
            if producer is None or producer.get('child_identity') != child or composition(events, producer) != lifecycle:
                return
            sessions = [lifecycle['proof']['session_id']]
            terminals = [lifecycle['terminal']]
        elif len(sessions) != 1 or len(terminals) != 1:
            from .operator_native_lifecycle import continuation
            lifecycle = continuation(events)
            if lifecycle is None: return
            sessions = [lifecycle['proof']['session_id']]
            terminals = [lifecycle['terminal']]
        if len(selected) != 1 or len(results) != 1 or len(sessions) != 1 or not sessions[0] or len(terminals) != 1:
            return
        use, result = selected[0], results[0]
        if lifecycle is not None and lifecycle['proof']['version'] == 1 and any(task['tool_use_id'] == use['tool_use_id']
                                         for task in lifecycle['proof']['completed_tasks']): return
        if use['tool_use_id'] != result['tool_use_id'] or any(row.get('session_id') != sessions[0] for row in (use,result,terminals[0])):
            return
        if use['command_digest'] != sha(COMMAND.encode()): return
        raw_uses = []
        raw_results = []
        for event in events:
            message = event.get('message')
            content = message.get('content', []) if isinstance(message, dict) else []
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict): continue
                if block.get('type') == 'tool_use' and block.get('id') == use['tool_use_id']:
                    raw_uses.append(block)
                if block.get('type') == 'tool_result' and block.get('tool_use_id') == use['tool_use_id']:
                    raw_results.append(block)
        if len(raw_uses) != 1 or len(raw_results) != 1: return
        if raw_uses[0].get('name') != 'Bash' or raw_results[0].get('is_error', False) != result.get('is_error'): return
        native_input = raw_uses[0].get('input')
        if not isinstance(native_input, dict) or native_input.get('command') != COMMAND or native_input.get('run_in_background', False) is not False: return
        native_output = raw_results[0].get('content', '')
        if isinstance(native_output, list): native_output = '\n'.join(row.get('text', '') for row in native_output if isinstance(row, dict))
        if not isinstance(native_output, str): return
        automatic = None
        if re.match(r'(?:(?:Command (?:is )?running|Running) in background\b|Command did not complete within its \d+s timeout and was moved to the background\b)', native_output):
            if lifecycle is not None and lifecycle['proof']['version'] == 2:
                matching = [task for task in lifecycle['proof']['tasks']
                            if task['tool_use_id'] == use['tool_use_id'] and task['kind'] == 'automatic']
                if len(matching) != 1: return
                task = matching[0]
                notification = events[task['notification_index']]
                output = _native_exit_file(notification.get('output_file'), sessions[0], task['task_id'], task['exit_code'])
                automatic = {key: task[key] for key in ('task_id', 'run_id', 'tool_use_id', 'exit_code')}
                automatic.update(native_output=output, producer=producer)
            else:
                automatic = _automatic_completion(events, use, raw_uses[0], raw_results[0], child, producer)
        fd = private_dir(directory_path())
        try:
            names = os.listdir(fd)
            if len(names) != 1 or not re.fullmatch(r'\d+-\d+\.json', names[0]): return
            file = os.open(names[0], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(file, 'rb') as stream:
                meta = os.fstat(stream.fileno())
                if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_nlink != 1 or meta.st_size > LIMIT * 3: return
                raw = stream.read(LIMIT * 3 + 1)
        finally: os.close(fd)
        record = json.loads(raw)
        if not isinstance(record, dict) or record.get('nonce') != os.environ['CS_OPERATOR_ACCEPTANCE_NONCE'] or record.get('owner_uid') != owner or record.get('kernel_source_digest') != package_digest(): return
        if ('kernel_package_root' in record and (not isinstance(record['kernel_package_root'], str) or not Path(record['kernel_package_root']).is_absolute())) or ('pythonpath' in record and not isinstance(record['pythonpath'], str)): return
        supervisor = proc(os.getpid())
        if record.get('native_identity') != child or record.get('supervisor_identity') != {k:supervisor[k] for k in ('pid','started_ticks')} or record.get('argv') != ARGV: return
        chain = record.get('ancestry')
        if not isinstance(chain,list) or not 4 <= len(chain) <= 32 or any(not isinstance(r,dict) for r in chain): return
        if {k:chain[0].get(k) for k in ('pid','started_ticks')} != record.get('cli_identity') or names[0] != str(chain[0]['pid']) + '-' + str(chain[0]['started_ticks']) + '.json': return
        if {k:chain[-1].get(k) for k in ('pid','started_ticks')} != record.get('supervisor_identity'): return
        if chain[0]['pid'] != record['cli_identity']['pid'] or chain[-1]['pid'] != supervisor['pid'] or any(chain[i]['ppid'] != chain[i+1]['pid'] for i in range(len(chain)-1)): return
        if {k:chain[2][k] for k in ('pid','started_ticks')} != child: return
        if chain[1].get('executable') != str(Path('/bin/bash').resolve()) or record.get('shell_executable_sha256') != sha(Path('/bin/bash').read_bytes()): return
        if not chain[2].get('executable', '').endswith('/versions/' + CLAUDE_VERSION) or sha(Path(chain[2]['executable']).read_bytes()) != CLAUDE_SHA256: return
        if record.get('wrapper') != extract_wrapper(chain[1]['argv']) or record.get('claude_sha256') != CLAUDE_SHA256 or record.get('claude_version') != CLAUDE_VERSION: return
        payload = record.get('output','').encode()
        if len(payload) > LIMIT or len(payload) != record.get('output_length') or sha(payload) != record.get('output_sha256'): return
        if automatic is not None:
            native_bytes = payload + ('\n[exited with code ' + str(automatic['exit_code']) + ']\n').encode()
            if (automatic['native_output']['bytes'] != len(native_bytes) or
                    automatic['native_output']['sha256'] != sha(native_bytes)): return
        value = json.loads(payload)
        if value != record.get('discovery') or payload != (json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n').encode(): return
        if not isinstance(value,dict) or 'read_incomplete' not in value or type(value.get('assignment_incomplete')) is not bool or any(not isinstance(value.get(k),list) for k in ('open','human_work','assignment_audit','operational_fixture_discovery')): return
        held = sum(isinstance(r,dict) and isinstance(r.get('assignment'),dict) and r['assignment'].get('complete') is False and r['assignment'].get('hold_auto_reply') is True for r in value['human_work'])
        code = 3 if value.get('read_incomplete') or value.get('assignment_incomplete') else 0
        if value.get('read_incomplete') is not None or record.get('exit_code') != code: return
        if automatic is not None:
            if automatic['exit_code'] != code: return
            if code == 3 and (value.get('assignment_incomplete') is not True or held <= 0): return
        else:
            if code == 0 and result.get('is_error') is not False: return
            if code == 3 and (result.get('is_error') is not True or result.get('error_status') != 3 or value.get('assignment_incomplete') is not True or held <= 0): return
        result.update(discovery_complete=True, held_count=held, discovery=[{k:r.get(k) for k in ('message_id','provider_folder','provider_uid','provider_uidvalidity','owner_uid','body_sha256')} for r in value['operational_fixture_discovery'] if isinstance(r,dict)], transport={'receipt_id':names[0],'receipt_sha256':sha(raw),'output_sha256':sha(payload),'output_length':len(payload),'cli_identity':record['cli_identity'],'native_identity':child,'wrapper_digest':record['wrapper']['shell_argv_digest'],'kernel_source_digest':record['kernel_source_digest'],'exit_code':code,**{key:record[key] for key in ('kernel_package_root','pythonpath') if key in record}})
        if automatic is not None:
            result['automatic_completion'] = automatic
    except Exception:
        return
