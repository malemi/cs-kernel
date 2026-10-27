"""Finite source-owned read observations; these receipts grant no action authority."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import stat

from . import operator_discovery_receipt as transport


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate business read key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite business read value')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=invalid)


def command_scope(command):
    if not isinstance(command, str) or any(char in command for char in ('\n', '\r', '$', '`')):
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if words[:3] != ['.venv/bin/python', '-m', 'cs']:
        return None
    argv = words[3:]
    if (len(argv) == 4 and argv[:2] == ['assignment', 'status'] and argv[3] == '--json'
            and re.fullmatch(r'<[^<>\s@]+@[^<>\s@]+>', argv[2])):
        return {'kind': 'assignment_hold', 'thread_key': argv[2], 'argv': argv, 'exit_code': 3}
    if (len(argv) == 2 and argv[0] == 'dossier'
            and re.fullmatch(r'[^@\s<>;&|$`]+@[^@\s<>;&|$`]+\.[^@\s<>;&|$`]+', argv[1])):
        return {'kind':'outside_selected_workset','contact':argv[1].lower(),'argv':argv,'exit_code':3}
    if len(argv) == 3 and argv[:2] == ['rpc', 'emails.search']:
        if any(char in command for char in (';', '&', '|', '<', '>')):
            return None
        try:
            params = _json(argv[2])
        except (ValueError, TypeError):
            return None
        if (isinstance(params, dict) and set(params) == {'query', 'limit'}
                and isinstance(params['query'], str)
                and re.fullmatch(r"[A-Za-z0-9.!#%'+/=?^_{}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", params['query'])
                and not params['query'].startswith('.') and '.@' not in params['query']
                and '..' not in params['query']
                and type(params['limit']) is int and 1 <= params['limit'] <= 100):
            return {'kind':'outside_selected_workset','contact':params['query'].lower(),
                    'argv':argv,'exit_code':3}
        return None
    if len(argv) >= 2 and re.fullmatch(r'[^@\s<>;&|$`]+@[^@\s<>;&|$`]+\.[^@\s<>;&|$`]+', argv[1]):
        if argv[0] == 'contacted':
            if len(argv) == 2:
                days = 30
            elif len(argv) == 4 and argv[2] == '--days' and re.fullmatch('[1-9][0-9]{0,3}', argv[3]):
                days = int(argv[3])
            else:
                return None
            return {'kind':'contacted_absent','contact':argv[1], 'window':{'days':days},
                    'query':{'contact':argv[1],'directions':['sent'],'days':days},
                    'rendering':'prose','argv':argv,'exit_code':1}
        if argv[0] == 'history' and (len(argv) == 2 or len(argv) == 3 and argv[2] == '--json'):
            return {'kind':'history_absent','contact':argv[1],'window':None,
                    'query':{'contact':argv[1],'directions':['sent','in'],'days':None},
                    'rendering':'json' if len(argv) == 3 else 'prose','argv':argv,'exit_code':1}
    return None


def absence(value, scope, owner):
    try:
        if (not isinstance(value, dict) or set(value) != {'owner_uid','kind','contact','window','query','fanout','configured'}
                or value['owner_uid'] != owner
                or any(value[key] != scope[key] for key in ('kind','contact','window','query'))):
            return False
        fan = value['fanout']
        if (not isinstance(fan, dict) or set(fan) != {'rows','scope','note'}
                or fan['rows'] != [] or fan['note'] is not None):
            return False
        observed = fan['scope']
        if (not isinstance(observed, dict) or set(observed) != {'read','unreadable','skipped','complete'}
                or observed['complete'] is not True or observed['unreadable'] != []
                or not isinstance(observed['read'], list) or not isinstance(observed['skipped'], list)
                or any(not isinstance(address,str) or not address.strip() for address in observed['read'])):
            return False
        read = [address.strip().lower() for address in observed['read']]
        if len(set(read)) != len(read):
            return False
        skipped = []
        for row in observed['skipped']:
            if (not isinstance(row,dict) or set(row) != {'account','address','reason'}
                    or any(not isinstance(row[key],str) or not row[key] for key in row)
                    or row['address'].strip().lower() != scope['contact'].strip().lower()):
                return False
            skipped.append(row['address'].strip().lower())
        if len(set(skipped)) != len(skipped) or set(read).intersection(skipped):
            return False
        configured = value['configured']
        if (not isinstance(configured,dict) or set(configured) != {'operator_mailbox','account_map','read_mailboxes'}
                or not isinstance(configured['operator_mailbox'],str) or not configured['operator_mailbox'].strip()
                or not isinstance(configured['account_map'],dict)
                or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v
                       for k,v in configured['account_map'].items())
                or not isinstance(configured['read_mailboxes'],list)
                or any(not isinstance(v,str) or not v.strip() for v in configured['read_mailboxes'])):
            return False
        named = set(read + skipped)
        required = {configured['operator_mailbox'].strip().lower()}
        if scope['kind'] == 'history_absent':
            required.update(address.strip().lower() for address in configured['read_mailboxes'])
        elif scope['kind'] != 'contacted_absent' or named != required:
            return False
        return required <= named
    except (KeyError,TypeError,ValueError):
        return False


def outside_workset_value(value, scope, owner, context=None):
    """Validate a finite exclusion, then correlate it with private current state."""
    import hashlib
    import stat
    try:
        def hashed(v):
            return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':'),
                ensure_ascii=False).encode()).hexdigest()
        def digest(v):
            return isinstance(v, str) and re.fullmatch('[a-f0-9]{64}', v) is not None
        if (not isinstance(value, dict) or set(value) != {'version', 'kind', 'reason', 'owner_uid',
                'nonce', 'contact', 'reservation', 'reservation_sha256', 'cursor_run'}
                or type(value['version']) is not int or value['version'] != 1
                or value['kind'] != 'outside_selected_workset'
                or value['reason'] != 'OUTSIDE_SELECTED_WORKSET' or value['owner_uid'] != owner
                or scope.get('kind') != value['kind'] or scope.get('contact') != value['contact']
                or not re.fullmatch('[a-f0-9]{32}', value['nonce'])
                or not digest(value['reservation_sha256'])):
            return False
        reservation, run = value['reservation'], value['cursor_run']
        if (not isinstance(reservation, dict) or set(reservation) != {'nonce','owner_uid','digest','selected','contacts'}
                or reservation['owner_uid'] != owner or reservation['nonce'] != value['nonce']
                or not digest(reservation['digest']) or not isinstance(run, dict)
                or set(run) != {'digest','selected','contacts'}
                or any(run[k] != reservation[k] for k in run)):
            return False
        for key in ('selected', 'contacts'):
            rows = reservation[key]
            if (not isinstance(rows, list) or len(rows) > (2 if key == 'selected' else 10000)
                    or any(not digest(v) for v in rows) or len(rows) != len(set(rows))):
                return False
        if (not isinstance(value['contact'], str) or value['contact'] != value['contact'].lower()
                or not re.fullmatch(r'[^@\s<>;&|$`]+@[^@\s<>;&|$`]+\.[^@\s<>;&|$`]+', value['contact'])
                or hashed(value['contact']) in reservation['contacts']):
            return False
        if context is None:
            return True
        if (context.get('owner_uid') != owner or context.get('nonce') != value['nonce']
                or context.get('workset_enabled') is not True):
            return False
        directory = Path(context['directory'])
        if (not directory.is_absolute() or directory.resolve() != directory
                or directory.parent.name != 'operator-runs'
                or re.fullmatch(r'run-[A-Za-z0-9_-]+', directory.name) is None):
            return False
        state = directory.parent.parent
        def safe_dir(path):
            s = path.lstat()
            if (path.resolve() != path or not stat.S_ISDIR(s.st_mode)
                    or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o700):
                raise ValueError('unsafe deferral directory')
        safe_dir(directory); safe_dir(directory.parent); safe_dir(state / 'operator-workset')
        st = state.lstat()
        if state.resolve() != state or not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
            return False
        def read(path):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                        or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                        or before.st_size > 4 * 1024 * 1024):
                    raise ValueError('unsafe deferral record')
                raw = stream.read(4 * 1024 * 1024 + 1); after = os.fstat(stream.fileno())
            if len(raw) > 4 * 1024 * 1024 or any(getattr(before,k) != getattr(after,k)
                    for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
                raise ValueError('changed deferral record')
            def unique(pairs):
                result = {}
                for key, item in pairs:
                    if key in result: raise ValueError('duplicate deferral key')
                    result[key] = item
                return result
            def invalid(v): raise ValueError('nonfinite deferral value')
            return raw, json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
        raw, current = read(directory / 'workset-reserved.json')
        _, cursor = read(state / 'operator-workset' / 'cursor.json')
        if (not isinstance(cursor, dict) or set(cursor) != {'version','owner','order','roots','runs'}
                or type(cursor['version']) is not int or cursor['version'] != 1
                or cursor['owner'] != hashed(owner) or type(cursor['order']) is not int or cursor['order'] < 0
                or not isinstance(cursor['roots'], dict) or not isinstance(cursor['runs'], dict)
                or len(cursor['roots']) > 10000 or len(cursor['runs']) > 10000):
            return False
        for key, item in cursor['roots'].items():
            if (not digest(key) or not isinstance(item, dict) or set(item) != {'revision','order'}
                    or not digest(item['revision']) or type(item['order']) is not int
                    or not 0 < item['order'] <= cursor['order']):
                return False
        for key, item in cursor['runs'].items():
            if (not digest(key) or not isinstance(item, dict) or set(item) != {'digest','selected','contacts'}
                    or not digest(item['digest'])):
                return False
            for field in ('selected','contacts'):
                rows = item[field]
                if (not isinstance(rows, list) or len(rows) > (2 if field == 'selected' else 10000)
                        or any(not digest(v) for v in rows) or len(rows) != len(set(rows))):
                    return False
        return (hashlib.sha256(raw).hexdigest() == value['reservation_sha256']
                and current == reservation and type(cursor['version']) is int and cursor['version'] == 1
                and cursor['owner'] == hashed(owner) and cursor['runs'][hashed(value['nonce'])] == run)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def eligible(value, scope, owner):
    if scope.get('kind') == 'outside_selected_workset':
        return outside_workset_value(value, scope, owner)
    if scope.get('kind') == 'assignment_hold':
        return (isinstance(value,dict) and set(value) == {'projection','configured_account_map'}
                and assignment_hold(value['projection'],owner,scope['thread_key'],value['configured_account_map']))
    return absence(value,scope,owner)


def capture_absence(output, fanout, settings, contact, *, days=None, history=False, rendering='prose'):
    import sys
    if not os.environ.get('CS_OPERATOR_HEALTH_CONTEXT'):
        return
    try:
        scope = command_scope('.venv/bin/python -m cs ' + shlex.join(sys.argv[1:]))
        if (scope is None or scope['kind'] != ('history_absent' if history else 'contacted_absent')
                or scope['contact'] != contact or scope['rendering'] != rendering
                or scope['window'] != (None if history else {'days':days})):
            return
        value = {'owner_uid':settings.engine_owner_uid,'kind':scope['kind'],'contact':contact,
                 'window':scope['window'],'query':scope['query'],'fanout':fanout,
                 'configured':{'operator_mailbox':settings.email_address,'account_map':settings.account_map,
                               'read_mailboxes':settings.read_mailbox_list}}
        if absence(value,scope,settings.engine_owner_uid):
            transport.capture(output,value,1,settings.engine_owner_uid,business=scope)
    except Exception:
        return


def assignment_hold(value, owner, root, configured_accounts=None):
    from types import SimpleNamespace
    from . import task_assignment as authority
    try:
        accounts = {} if configured_accounts is None else configured_accounts
        if (not isinstance(accounts,dict) or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v
                                               for k,v in accounts.items())):
            return False
        actors = {owner,*accounts.values()}
        authority._validate_projection(SimpleNamespace(engine_owner_uid=owner), root, value)
        if (value['complete'] is not False or value['hold_auto_reply'] is not True
                or value.get('source_owner_uid') != owner):
            return False
        if value.get('reason') == 'RFC_ANCESTRY_CONFLICT':
            from .operator_health import _ancestry_conflict
            return _ancestry_conflict(value, root)
        if (value['state'] != 'needs-assignment' or value.get('task') is not None
                or value.get('reason') not in ('NEEDS_HUMAN_VERIFICATION',
                    'peer reply requires explicit human verification and assignment')
                or not value.get('reply_evidence')):
            return False
        component = value.get('component_thread_keys')
        if not isinstance(component, list) or root not in component:
            return False
        for item in value['reply_evidence']:
            if (not isinstance(item, dict) or type(item.get('version')) is not int or item['version'] != 1
                    or item.get('actor_uid') not in actors or item.get('space_id') != value['space_id']
                    or item.get('thread_key') != root or item.get('complete') is not True
                    or item.get('judgement') not in ('MEMBER_ACTIVITY_REQUIRES_HUMAN_VERIFICATION',
                        'MALFORMED_OWN_SENT_REQUIRES_HUMAN_VERIFICATION')
                    or item.get('reason') != 'NEEDS_HUMAN_VERIFICATION'
                    or not isinstance(item.get('source_id'), str) or not item['source_id']):
                return False
            source = item.get('source')
            if (not isinstance(source, dict) or source.get('actor_uid') != item['actor_uid']
                    or source.get('thread_key') != root or source.get('message_id') not in component
                    or source.get('observation_only') is not True
                    or not isinstance(source.get('mailbox_id'), str) or not source['mailbox_id']):
                return False
            provider = source.get('provider')
            if (not isinstance(provider, dict) or not isinstance(provider.get('folder'), str)
                    or not provider['folder'] or any(type(provider.get(k)) is not int or provider[k] < 1
                                                    for k in ('uid', 'uidvalidity'))):
                return False
            if any(not isinstance(digest, str) or re.fullmatch('[a-f0-9]{64}', digest) is None
                   for digest in (item.get('digest'), source.get('route_digest'), source.get('raw_header_digest'))):
                return False
        if (value['reason'] == 'peer reply requires explicit human verification and assignment'
                and not any(item['actor_uid'] != owner for item in value['reply_evidence'])):
            return False
        return True
    except (ValueError, TypeError, KeyError, authority.AssignmentUnavailable):
        return False


def context(value=None):
    if value is None:
        value = _json(os.environ.get('CS_OPERATOR_HEALTH_CONTEXT', ''))
    if (not isinstance(value, dict) or not re.fullmatch('[a-f0-9]{32}', value.get('nonce', ''))
            or not isinstance(value.get('owner_uid'), str) or not value['owner_uid']):
        raise ValueError('business read context invalid')
    path = Path(value['directory'])
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('business read directory invalid')
    from .operator_health import private
    private(path, True)
    return value


def directory_path(value=None):
    return Path(context(value)['directory']) / 'business-reads'


def capture(output, value, code, owner, configured_accounts=None):
    import sys
    command = '.venv/bin/python -m cs ' + shlex.join(sys.argv[1:])
    scope = command_scope(command)
    if (scope is None or type(code) is not int or code != scope['exit_code']
            or not assignment_hold(value, owner, scope['thread_key'], configured_accounts)
            or output != (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()):
        return
    typed = {'projection':value,'configured_account_map':configured_accounts or {}}
    transport.capture(output, typed, code, owner, business=scope)


def join(events, child, owner, producer=None, lifecycle=None, context_value=None):
    proofs = []
    try:
        ctx = context(context_value)
        supervisor = transport.proc(os.getpid())
        if (ctx['supervisor'] != {k:supervisor[k] for k in ('pid','started_ticks')}
                or ctx['owner_uid'] != owner or producer is None or producer.get('child_identity') != child):
            return []
        from .operator_native_composition import composition
        if lifecycle is not None and composition(events, producer) != lifecycle:
            return []
        sessions = {event.get('session_id') for event in events}
        if len(sessions) != 1 or not next(iter(sessions)):
            return []
        session = next(iter(sessions))
        uuids = [event.get('uuid') for event in events]
        if (any(not isinstance(value,str) or not value for value in uuids)
                or len(set(uuids)) != len(uuids)):
            return []
        if lifecycle is None:
            terminal = events[-1]
            if (events[0].get('type') != 'system' or events[0].get('subtype') != 'init'
                    or events[0].get('claude_code_version') != transport.CLAUDE_VERSION
                    or any(event.get('type') == 'system' and event.get('subtype') != 'init' for event in events)
                    or sum(event.get('type') == 'result' for event in events) != 1
                    or sum(event.get('type') == 'system' and event.get('subtype') == 'init' for event in events) != 1
                    or terminal.get('type') != 'result' or terminal.get('is_error') is not False
                    or terminal.get('terminal_reason') != 'completed'):
                return []
        fd = transport.private_dir(directory_path(ctx))
        records = []
        try:
            names = os.listdir(fd)
            if not names or len(names) > 8:
                return []
            for name in names:
                if re.fullmatch(r'\d+-\d+\.json', name) is None:
                    return []
                handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                with os.fdopen(handle, 'rb') as stream:
                    before = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                            or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                            or before.st_size > transport.LIMIT * 3):
                        return []
                    raw = stream.read(transport.LIMIT * 3 + 1)
                    after = os.fstat(stream.fileno())
                if len(raw) > transport.LIMIT * 3 or any(getattr(before, k) != getattr(after, k)
                        for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
                    return []
                records.append((name, raw, _json(raw)))
        finally:
            os.close(fd)
        used = set()
        for name, raw, record in records:
            scope = record.get('business')
            argv = record.get('argv')
            if not isinstance(scope, dict) or not isinstance(argv, list):
                return []
            command = record.get('wrapper', {}).get('payload')
            if command_scope(command) != scope or scope['argv'] != argv:
                return []
            if scope['kind'] == 'outside_selected_workset' and not outside_workset_value(
                    record.get('discovery'), scope, owner, ctx):
                return []
            worker = record.get('capture_worker_identity')
            if (type(record.get('schema_version')) is not int or record['schema_version'] != 1
                    or not isinstance(worker,dict) or set(worker) != {'pid','started_ticks'}
                    or any(type(v) is not int or v <= 0 for v in worker.values())
                    or record.get('nonce') != ctx['nonce'] or record.get('owner_uid') != owner
                    or record.get('kernel_source_digest') != transport.package_digest()
                    or record.get('native_identity') != child
                    or record.get('supervisor_identity') != ctx['supervisor']
                    or record.get('claude_sha256') != transport.CLAUDE_SHA256
                    or record.get('claude_version') != transport.CLAUDE_VERSION):
                return []
            chain = record.get('ancestry')
            if (not isinstance(chain, list) or not 4 <= len(chain) <= 32
                    or any(not isinstance(row, dict) for row in chain)
                    or any(chain[i]['ppid'] != chain[i+1]['pid'] for i in range(len(chain)-1))
                    or {k:chain[0][k] for k in ('pid','started_ticks')} != record.get('cli_identity')
                    or {k:chain[2][k] for k in ('pid','started_ticks')} != child
                    or {k:chain[-1][k] for k in ('pid','started_ticks')} != ctx['supervisor']
                    or name != str(chain[0]['pid']) + '-' + str(chain[0]['started_ticks']) + '.json'):
                return []
            if (chain[0]['argv'][-len(argv):] != argv
                    or chain[1]['executable'] != str(Path('/bin/bash').resolve())
                    or transport.sha(Path('/bin/bash').read_bytes()) != record.get('shell_executable_sha256')
                    or chain[2]['executable'] != producer.get('path')
                    or transport.pin_native(chain[2]['executable']) != {k:v for k,v in producer.items() if k != 'child_identity'}
                    or transport.extract_wrapper(chain[1]['argv'], command=command) != record['wrapper']):
                return []
            payload = record.get('output', '').encode()
            if scope['kind'] == 'outside_selected_workset' and payload != workset_deferral_output(scope):
                return []
            value = record.get('discovery')
            if scope['kind'] == 'assignment_hold' and _json(payload) != value.get('projection'):
                return []
            if (value != record.get('discovery') or len(payload) > transport.LIMIT or len(payload) != record.get('output_length')
                    or transport.sha(payload) != record.get('output_sha256')
                    or type(record.get('exit_code')) is not int or record['exit_code'] != scope['exit_code']
                    or not eligible(value, scope, owner)):
                return []
            uses, results = [], []
            for event in events:
                message = event.get('message')
                blocks = message.get('content', []) if isinstance(message, dict) else []
                for block in blocks if isinstance(blocks, list) else []:
                    if not isinstance(block, dict):
                        continue
                    if (block.get('type') == 'tool_use' and block.get('name') == 'Bash'
                            and block.get('input', {}).get('command') == command):
                        uses.append(block)
                    if block.get('type') == 'tool_result':
                        results.append((event, block))
            if len(uses) != 1 or uses[0].get('input', {}).get('run_in_background', False) is not False:
                return []
            tool = uses[0]['id']
            matches = [(event, block) for event, block in results if block.get('tool_use_id') == tool]
            if tool in used or len(matches) != 1:
                return []
            event, result = matches[0]
            expected = 'Exit code ' + str(scope['exit_code']) + '\n' + payload.decode()
            if scope['kind'] == 'outside_selected_workset':
                # Pinned native rendering omits exactly the source's final LF.
                expected = 'Exit code 3\n' + workset_deferral_output(scope).decode().removesuffix('\n')
            if (scope['kind'] == 'assignment_hold' and expected.endswith('\n')
                    and result.get('content') == expected[:-1]):
                expected = expected[:-1]
            if (result.get('is_error') is not True or result.get('content') != expected
                    or event.get('tool_use_result') != 'Error: ' + expected):
                return []
            tasks = [task for task in (lifecycle or {}).get('proof', {}).get('tasks', [])
                     if task['tool_use_id'] == tool]
            if tasks and (len(tasks) != 1 or tasks[0]['kind'] != 'foreground' or tasks[0]['exit_code'] != scope['exit_code']):
                return []
            proof = {'kind':scope['kind'], 'tool_use_id':tool, 'session_id':session,
                     'exit_code':scope['exit_code'], 'receipt_id':name, 'receipt_sha256':transport.sha(raw),
                     'output_sha256':transport.sha(payload), 'command_digest':transport.sha(command.encode()),
                     'scope':scope, 'transport':record, 'native_use':uses[0],
                     'native_result':result, 'native_result_metadata':event.get('tool_use_result'),
                     'native_result_uuid':event.get('uuid'),
                     'native_use_uuid':next(e.get('uuid') for e in events
                        if isinstance(e.get('message'),dict) and isinstance(e['message'].get('content'),list)
                        and uses[0] in e['message']['content'])}
            if tasks:
                proof.update({k:tasks[0][k] for k in ('task_id','run_id')})
            used.add(tool)
            proofs.append(proof)
        return proofs
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return []


def capture_workset_deferral(settings, value):
    import sys
    scope = command_scope('.venv/bin/python -m cs ' + shlex.join(sys.argv[1:]))
    ctx = context()
    if scope is None or not outside_workset_value(value, scope, settings.engine_owner_uid, ctx):
        return
    transport.capture(workset_deferral_output(scope), value, 3,
                      settings.engine_owner_uid, business=scope)


def workset_deferral_output(scope):
    if scope['argv'][:2] == ['rpc', 'emails.search']:
        return b'Scheduled deep mail read deferred outside selected workset\n'
    return b'Scheduled work deferred outside selected workset\n'
