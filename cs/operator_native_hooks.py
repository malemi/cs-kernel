"""Strict observed native hook lifecycle; validation grants no inventory coverage."""
import re


def hook_indices(events):
    inits = [e for e in events if e.get('type') == 'system' and e.get('subtype') == 'init']
    if not inits:
        raise ValueError('hook stream has no native init')
    session = inits[0]['session_id']
    pending, completed, indices = {}, set(), set()
    progress, identities = {}, set()
    base = {'type', 'subtype', 'hook_id', 'hook_name', 'hook_event', 'uuid', 'session_id'}
    for index, e in enumerate(events):
        subtype = e.get('subtype')
        if e.get('type') != 'system' or not str(subtype).startswith('hook_'):
            continue
        if (subtype not in ('hook_started', 'hook_progress', 'hook_response') or e.get('session_id') != session
                or any(not isinstance(e.get(k), str) or not e[k] for k in ('hook_id', 'hook_name', 'hook_event', 'uuid'))):
            raise ValueError('unsupported hook event')
        if e['uuid'] in identities:
            raise ValueError('duplicate hook identity')
        identities.add(e['uuid'])
        kind = e['hook_event']
        if (kind not in ('UserPromptSubmit', 'MessageDisplay', 'PreToolUse', 'PostToolUse')
                or (e['hook_name'] != kind if kind in ('UserPromptSubmit', 'MessageDisplay')
                    else re.fullmatch(re.escape(kind) + r':[A-Za-z][A-Za-z0-9_]*', e['hook_name']) is None)):
            raise ValueError('unsupported hook boundary')
        token, binding = e['hook_id'], (e['hook_name'], kind)
        if subtype == 'hook_started':
            if set(e) != base or token in pending or token in completed:
                raise ValueError('ambiguous hook start')
            pending[token] = binding
        elif subtype == 'hook_progress':
            if (set(e) != base | {'output', 'stdout', 'stderr'}
                    or pending.get(token) != binding or token in progress or token in completed
                    or any(not isinstance(e[k], str) or len(e[k]) > 65536 for k in ('output', 'stdout', 'stderr'))
                    or not e['stdout'] or e['stderr'] != '' or e['output'] != e['stdout']):
                raise ValueError('invalid hook progress')
            progress[token] = (e['stdout'], e['stderr'])
        else:
            if (set(e) != base | {'output', 'stdout', 'stderr', 'exit_code', 'outcome'}
                    or pending.pop(token, None) != binding or token in completed
                    or type(e['exit_code']) is not int or e['exit_code'] != 0
                    or e['outcome'] != 'success' or e['output'] != e['stdout']
                    or (token in progress and progress[token] != (e['stdout'], e['stderr']))
                    or any(not isinstance(e[k], str) or len(e[k]) > 65536 for k in ('output', 'stdout', 'stderr'))):
                raise ValueError('invalid hook response')
            completed.add(token)
        indices.add(index)
    if pending:
        raise ValueError('unfinished hook lifecycle')
    return indices
