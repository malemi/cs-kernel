"""Validate complete known-producer Bash metadata without rewriting native events."""

import hashlib
import json
import math
import re
import shlex


_DENIAL_MESSAGE = "Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Auto-Mode Bypass]. If you have other tasks that don't depend on this action, continue working on those. IMPORTANT: You *may* attempt to accomplish this action using other tools that might naturally be used to accomplish this goal, e.g. using head instead of cat. But you *should not* attempt to work around this denial in malicious ways, e.g. do not use your ability to run tests to execute non-test actions. You should only try to work around this restriction in reasonable ways that do not attempt to bypass the intent behind this denial. If you believe this capability is essential to complete the user's request, first try a safer method. Get as much of the rest of the task done as you can, then STOP and explain to the user what you were trying to do and why you need this permission. Let the user decide how to proceed. To allow this type of action in the future, the user can add a permission rule for Bash to their settings."


class _Refusal(ValueError):
    def __init__(self, reason):
        super().__init__('Unsupported native composition')
        self.reason = reason


def rejection(events, producer):
    """Explain a refusal using bounded codes, never event values or payloads."""
    try:
        _composition(events, producer)
        return None
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        index, kind, subtype = None, 'unknown', None
        trace = exc.__traceback__
        while trace:
            if trace.tb_frame.f_code.co_name == '_composition':
                local = trace.tb_frame.f_locals
                index = local.get('index')
                event = local.get('event')
                if isinstance(event, dict):
                    if event.get('type') in ('system', 'assistant', 'user', 'result',
                                             'tool_progress', 'rate_limit_event'):
                        kind = event['type']
                    if event.get('subtype') in ('init', 'thinking_tokens', 'permission_check_status',
                            'task_started', 'task_updated', 'task_notification',
                            'background_tasks_changed', 'success'):
                        subtype = event['subtype']
            trace = trace.tb_next
        return {'reason': exc.reason if isinstance(exc, _Refusal) else 'native_shape_invalid',
                'event_index': index if type(index) is int else None,
                'event_type': kind, 'event_subtype': subtype}


def composition(events, producer):
    """Return original terminal and bounded version-two evidence, or refuse."""
    try:
        return _composition(events, producer)
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return None


def _composition(events, producer):
    from .operator_discovery_receipt import CLAUDE_SHA256, CLAUDE_VERSION, COMMAND
    from .operator_native_lifecycle import continuation
    from .operator_read_outcomes import command_scope

    def require(value, reason='native_composition_invalid'):
        if not value:
            raise _Refusal(reason)

    def identity(value):
        require(isinstance(value, str) and bool(value))
        return value

    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
            ensure_ascii=True, allow_nan=False).encode()).hexdigest()

    require(isinstance(producer, dict) and set(producer) == {
        'path', 'version', 'sha256', 'file_identity', 'child_identity'})
    require(producer['version'] == CLAUDE_VERSION and producer['sha256'] == CLAUDE_SHA256)
    require(identity(producer['path']).startswith('/') and
            producer['path'].endswith('/versions/' + CLAUDE_VERSION) and
            '..' not in producer['path'].split('/'))
    require(isinstance(producer['file_identity'], list) and len(producer['file_identity']) == 5 and
            all(type(v) is int and v >= 0 for v in producer['file_identity']) and
            all(v > 0 for v in producer['file_identity'][1:]))
    child = producer['child_identity']
    require(isinstance(child, dict) and set(child) == {'pid', 'started_ticks'} and
            all(type(v) is int and v > 0 for v in child.values()))
    require(isinstance(events, list) and bool(events))
    from .operator_native_hooks import hook_indices
    hooks = hook_indices(events)
    first = next(e for i, e in enumerate(events) if i not in hooks)
    require(first.get('type') == 'system' and first.get('subtype') == 'init')
    require(first.get('claude_code_version') == CLAUDE_VERSION)
    session = identity(first['session_id'])
    configuration = {k: v for k, v in first.items() if k != 'uuid'}
    uuids, tools, results, tasks, runs = set(), {}, set(), {}, set()
    advertised, callbacks, completed, removed = {}, [], [], []
    active, inits, terminals, origin, terminal = False, 0, 0, None, None
    old_schema = True
    permissions = set()
    checked, denials, tool_indices = {}, {}, {}
    progressing = set()
    permission_counts = {}
    for index, event in enumerate(events):
        require(isinstance(event, dict) and event.get('session_id') == session)
        uuid = identity(event['uuid'])
        require(uuid not in uuids)
        uuids.add(uuid)
        kind = event.get('type')
        subtype = event.get('subtype')
        if index in hooks:
            removed.append({'index': index, 'kind': subtype})
            old_schema = False
            continue
        telemetry = (kind in ('tool_progress', 'rate_limit_event') or
                     kind == 'system' and subtype in ('thinking_tokens', 'permission_check_status'))
        if telemetry:
            require(active)
            envelope = {'type', 'session_id', 'uuid'}
            if subtype == 'thinking_tokens':
                require(kind == 'system' and set(event) == envelope | {
                    'subtype', 'estimated_tokens', 'estimated_tokens_delta'})
                require(all(type(event[k]) is int and event[k] >= 0
                            for k in ('estimated_tokens', 'estimated_tokens_delta')))
            elif subtype == 'permission_check_status':
                require(kind == 'system' and set(event) == envelope | {'subtype', 'status', 'tool_use_id'})
                tool = identity(event['tool_use_id'])
                require(tool in tools and tool not in results and tool not in denials)
                if event['status'] == 'checking':
                    require(tool not in permissions)
                    permissions.add(tool)
                    checked[tool] = {'checking': index}
                    permission_counts[tool] = permission_counts.get(tool, 0) + 1
                else:
                    require(event['status'] == 'done' and tool in permissions)
                    permissions.remove(tool)
                    checked[tool]['done'] = index
            elif kind == 'tool_progress':
                require(set(event) == envelope | {'tool_use_id', 'tool_name', 'parent_tool_use_id',
                                                  'elapsed_time_seconds', 'heartbeat'})
                parent = identity(event['parent_tool_use_id'])
                require(parent in tools and parent not in results and tools[parent]['name'] == 'Bash')
                require(event['tool_name'] == 'Bash' and event['heartbeat'] is True and
                        re.fullmatch(re.escape(parent) + r'-heartbeat-[0-9]+', identity(event['tool_use_id'])))
                require(parent not in denials)
                progressing.add(parent)
                elapsed = event['elapsed_time_seconds']
                require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0)
            else:
                require(set(event) == envelope | {'rate_limit_info'})
                info = event['rate_limit_info']
                require(isinstance(info, dict) and set(info) == {'status', 'resetsAt', 'rateLimitType',
                    'overageStatus', 'overageDisabledReason', 'isUsingOverage', 'unifiedWindows'})
                require(info['status'] == 'allowed' and info['rateLimitType'] == 'five_hour' and
                        info['overageStatus'] == 'rejected' and
                        info['overageDisabledReason'] == 'org_level_disabled' and info['isUsingOverage'] is False)
                require(type(info['resetsAt']) is int and info['resetsAt'] >= 0)
                windows = info['unifiedWindows']
                require(isinstance(windows, dict) and set(windows) == {'five_hour', 'seven_day'})
                for window in windows.values():
                    require(isinstance(window, dict) and set(window) == {'utilization', 'resetsAt'})
                    require(type(window['resetsAt']) is int and window['resetsAt'] >= 0)
                    utilization = window['utilization']
                    require(type(utilization) in (int, float) and math.isfinite(utilization) and
                            0 <= utilization <= 1)
            old_schema = False
            continue
        if kind == 'system':
            subtype = event.get('subtype')
            if subtype == 'init':
                require(not active and {k: v for k, v in event.items() if k != 'uuid'} == configuration)
                if inits:
                    require(callbacks and not advertised)
                    origin = callbacks.pop(0)
                active = True
                inits += 1
                continue
            require(inits > 0)
            removal = {'index': index, 'kind': subtype}
            if subtype == 'permission_denied':
                require(active and len(denials) < 16, 'nonexecution_denial_limit')
                require(set(event) == {'type', 'subtype', 'tool_name', 'tool_use_id',
                    'decision_reason_type', 'decision_reason', 'message', 'uuid', 'session_id'})
                tool = identity(event['tool_use_id'])
                require(tool in tools and tool not in results and tool not in permissions)
                use = tools[tool]
                arguments = use.get('input')
                require(use.get('name') == event['tool_name'] == 'Bash' and
                        isinstance(arguments, dict) and set(arguments) == {'command', 'description'})
                require(re.fullmatch(r'[A-Za-z0-9-]+', session) is not None)
                require(isinstance(arguments['description'], str) and bool(arguments['description']) and
                        '\n' not in arguments['description'])
                command = arguments['command']
                require(isinstance(command, str) and bool(command), 'nonexecution_command_invalid')
                try:
                    words = shlex.split(command)
                except ValueError:
                    words = []
                canonical = (words[:3] in (['.venv/bin/python', '-m', 'cs'],
                    ['.venv/bin/python3', '-m', 'cs']) or words[:1] in (['.venv/bin/cs'], ['cs']))
                require(not canonical, 'canonical_business_denial')
                require(tool not in denials and tool in checked and
                        permission_counts[tool] == 1 and set(checked[tool]) == {'checking', 'done'},
                        'nonexecution_permission_cycle_invalid')
                require(tool_indices[tool] < checked[tool]['checking'] < checked[tool]['done'] < index,
                        'nonexecution_permission_order_invalid')
                require(tool not in progressing and not any(t['tool_use_id'] == tool for t in tasks.values()))
                require(event['decision_reason_type'] == 'classifier' and
                        event['decision_reason'] == '[Auto-Mode Bypass]' and event['message'] == _DENIAL_MESSAGE)
                denials[tool] = dict(tool_use_id=tool, command_sha256=hashlib.sha256(command.encode()).hexdigest(),
                    checking_index=checked[tool]['checking'],
                    done_index=checked[tool]['done'], denial_index=index, result_index=None,
                    non_execution_kind='automode-blocked', execution_credit=False)
                continue
            if subtype == 'background_tasks_changed':
                listing = event['tasks']
                require(isinstance(listing, list))
                next_listing = {}
                for row in listing:
                    tid, run = identity(row['task_id']), identity(row['run_id'])
                    require(row.get('task_type') == 'local_bash' and tid not in next_listing and
                            run not in next_listing.values())
                    if tid in tasks:
                        require(tasks[tid]['run_id'] == run and tasks[tid]['state'] != 'notified')
                    else:
                        require(active and run not in runs)
                    next_listing[tid] = run
                require(next_listing != advertised)
                require(all(tid in tasks for tid in advertised))
                require(all(t['state'] == 'notified' or next_listing.get(tid) == t['run_id']
                            for tid, t in tasks.items() if t['kind'] != 'foreground' or tid in advertised))
                advertised = next_listing
            elif subtype == 'task_started':
                require(active and event.get('task_type') == 'local_bash')
                tid, run, tool = (identity(event[k]) for k in ('task_id', 'run_id', 'tool_use_id'))
                require(tid not in tasks and run not in runs and tool in tools and tool not in results)
                require(tool not in denials and tools[tool]['name'] == 'Bash' and
                        not any(t['tool_use_id'] == tool for t in tasks.values()))
                require(type(event.get('is_backgrounded')) is bool)
                background = event['is_backgrounded']
                require(not background or advertised.get(tid) == run)
                require(background or tid not in advertised)
                tasks[tid] = dict(task_id=tid, run_id=run, tool_use_id=tool,
                    kind='background' if background else 'foreground', state='started',
                    start_index=index, result_index=None, notification_index=None, exit_code=None)
                runs.add(run)
                if not background:
                    old_schema = False
                removal['task_id'] = tid
            elif subtype in ('task_updated', 'task_notification'):
                tid = identity(event['task_id'])
                task = tasks[tid]
                require(event.get('run_id') == task['run_id'])
                removal['task_id'] = tid
                if subtype == 'task_updated':
                    patch = event['patch']
                    require(isinstance(patch, dict))
                    if patch == {'is_backgrounded': True}:
                        require(active and task['kind'] == 'foreground' and task['state'] == 'started' and
                                task['result_index'] is None and advertised.get(tid) == task['run_id'])
                        task.update(kind='automatic', background_index=index)
                    else:
                        require((task['kind'] != 'background' or not active) and
                                task['kind'] != 'foreground' and task['state'] == 'started' and
                                task['result_index'] is not None)
                        if task['kind'] == 'automatic':
                            require(set(patch) == {'status', 'end_time'} and type(patch['end_time']) is int)
                        else:
                            require(set(patch) in ({'status'}, {'status', 'end_time'}))
                            require('end_time' not in patch or type(patch['end_time']) is int)
                        require(patch.get('status') in ('completed', 'failed'),
                                'native_task_killed' if patch.get('status') == 'killed' else 'native_composition_invalid')
                        task['state'] = patch['status']
                else:
                    require(event.get('tool_use_id') == task['tool_use_id'])
                    status = event.get('status')
                    require(status != 'stopped', 'native_task_stopped')
                    if task['kind'] == 'foreground':
                        require(active and task['state'] == 'started' and status in ('completed', 'failed') and
                                task['result_index'] is None, 'foreground_notification_invalid')
                        code = 0 if status == 'completed' else None
                        if status == 'failed':
                            command = tools[task['tool_use_id']].get('input', {}).get('command')
                            require(command == COMMAND or command_scope(command) is not None,
                                    'foreground_failure_not_canonical_discovery')
                            task['failure_pending'] = True
                    else:
                        require(task['state'] in ('completed', 'failed') and status == task['state'])
                        code = 0 if status == 'completed' else 3
                        use = tools[task['tool_use_id']].get('input', {})
                        if task['kind'] != 'foreground':
                            description = identity(use.get('description'))
                            require('\n' not in description)
                            expected = ('Background command "' + description + '" ' +
                                ('completed (exit code 0)' if code == 0 else 'failed with exit code 3'))
                            require(event.get('summary') == expected)
                        if code:
                            require(use.get('command') == COMMAND and task['kind'] == 'automatic')
                    task.update(state='notified', notification_index=index, exit_code=code)
                    if not active:
                        require(terminals > 0 and task['kind'] != 'foreground')
                        callback = {k: task[k] for k in ('task_id', 'run_id', 'tool_use_id')}
                        callbacks.append(task['run_id'])
                        completed.append(callback)
                        task['callback'] = callback.copy()
                    else:
                        old_schema = False
            else:
                require(False)
            removed.append(removal)
        elif kind in ('assistant', 'user'):
            require(active)
            blocks = event['message']['content']
            require(isinstance(blocks, list))
            for block in blocks:
                block_type = block.get('type')
                if block_type == 'tool_use':
                    require(kind == 'assistant')
                    tool = identity(block['id'])
                    name = identity(block['name'])
                    require(tool not in tools and name not in ('Agent', 'Task'))
                    tools[tool] = block
                    tool_indices[tool] = index
                elif block_type == 'tool_result':
                    require(kind == 'user')
                    tool = identity(block['tool_use_id'])
                    require(tool in tools and tool not in results and tool not in permissions and
                            type(block.get('is_error', False)) is bool)
                    results.add(tool)
                    if tool in denials:
                        require(len(blocks) == 1 and set(block) == {'type', 'content', 'is_error', 'tool_use_id'} and
                                block['is_error'] is True and block['content'] == _DENIAL_MESSAGE and
                                event.get('tool_use_result') == 'Error: ' + _DENIAL_MESSAGE and
                                event.get('tool_result_meta') == [dict(id=tool, non_execution_kind='automode-blocked',
                                    permission_decision=dict(decision='reject', source='config', reason_type='classifier'))])
                        denials[tool]['result_index'] = index
                    elif any(row.get('id') == tool and row.get('non_execution_kind') for row in event.get('tool_result_meta', [])):
                        require(False, 'unrecognized_nonexecution')
                    matching = [t for t in tasks.values() if t['tool_use_id'] == tool]
                    if matching:
                        task = matching[0]
                        metadata = event['tool_use_result']
                        if task['kind'] == 'foreground' and task.get('failure_pending') is True:
                            output = block.get('content')
                            match = re.match(r'Exit code ([13])\n', output) if isinstance(output, str) else None
                            command = tools[tool].get('input', {}).get('command')
                            scope = command_scope(command)
                            expected = 3 if command == COMMAND else scope['exit_code']
                            require(match is not None and int(match[1]) == expected and
                                    block.get('is_error') is True and
                                    isinstance(metadata, str) and metadata == 'Error: ' + output,
                                    'foreground_discovery_exit_mismatch')
                            task['exit_code'] = int(match[1])
                            del task['failure_pending']
                        else:
                            require(isinstance(metadata, dict) and block.get('is_error', False) is False and
                                    metadata.get('interrupted') is False, 'task_result_invalid')
                        if task['kind'] == 'foreground':
                            require(task['state'] == 'notified' and
                                    (isinstance(metadata, str) or not metadata.get('backgroundTaskId')))
                        else:
                            require(task['state'] == 'started' and
                                    metadata.get('backgroundTaskId') == task['task_id'])
                        task['result_index'] = index
                else:
                    require(block_type in ('text', 'thinking', 'redacted_thinking'))
        elif kind == 'result':
            require(active and not permissions and inits == terminals + 1 and type(event.get('result_index')) is int and
                    event['result_index'] == terminals)
            require(event.get('subtype') == 'success' and event.get('is_error') is False and
                    event.get('terminal_reason') == 'completed' and
                    type(event.get('num_turns')) is int and event['num_turns'] > 0 and
                    type(event.get('safety_stops')) is int and event['safety_stops'] == 0 and
                    event.get('api_error_status') is None and set(tools) == results)
            expected_denials = [dict(tool_name='Bash', tool_use_id=tool, tool_input=tools[tool]['input']) for tool in denials]
            require(event.get('permission_denials', []) == expected_denials, 'terminal_denials_mismatch')
            require(all(row['result_index'] is not None for row in denials.values()))
            expected = None if not terminals else dict(kind='task-notification', producer='session-task', runId=origin)
            require(event.get('origin') == expected)
            terminals += 1
            active, terminal = False, event
        else:
            require(False)
    require(not active and terminal is not None and events[-1] is terminal and inits == terminals)
    require(not callbacks and not advertised and bool(tasks))
    require(all(t['state'] == 'notified' and t['result_index'] is not None for t in tasks.values()))
    require(len(completed) == inits - 1)
    if old_schema and inits > 1:
        require(continuation(events) is not None)
    indices = {row['index'] for row in removed}
    projected = [event for i, event in enumerate(events) if i not in indices]
    records = [{k: v for k, v in task.items() if k != 'state'} for task in tasks.values()]
    return {'terminal': terminal, 'proof': dict(version=2, session_id=session,
        init_count=inits, result_count=terminals, event_sha256=digest(events),
        projected_event_sha256=digest(projected), removed=removed, tasks=records,
        completed_tasks=completed, optional_nonexecution_denials=list(denials.values()),
        denied_tool_count=len(denials))}
