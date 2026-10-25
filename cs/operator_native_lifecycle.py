"""Validate the evidenced ordered native background-task continuation protocol."""

import hashlib
import json


def continuation(events):
    """Return a complete multi-segment lifecycle proof, or None when unsupported."""
    if not isinstance(events, list) or sum(
        isinstance(e, dict) and e.get('type') == 'result' for e in events
    ) < 2:
        return None
    try:
        return _continuation(events)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _continuation(events):
    def require(condition):
        if not condition:
            raise ValueError('Unsupported native lifecycle')

    def identity(value):
        require(isinstance(value, str) and bool(value))
        return value

    require(bool(events))
    first = events[0]
    require(first.get('type') == 'system' and first.get('subtype') == 'init')
    session = identity(first['session_id'])
    configuration = {k: v for k, v in first.items() if k != 'uuid'}
    uuids, tools, tool_results, tasks, runs = set(), {}, set(), {}, set()
    advertised, callbacks, completed = {}, [], []
    active, init_count, result_count, origin_run, terminal = False, 0, 0, None, None
    for event in events:
        require(isinstance(event, dict) and event.get('session_id') == session)
        uuid = identity(event['uuid'])
        require(uuid not in uuids)
        uuids.add(uuid)
        kind = event.get('type')
        if kind == 'system':
            subtype = event.get('subtype')
            if subtype == 'init':
                require(not active)
                require({k: v for k, v in event.items() if k != 'uuid'} == configuration)
                if init_count:
                    require(bool(callbacks) and not advertised)
                    origin_run = callbacks.pop(0)
                active = True
                init_count += 1
            elif subtype == 'background_tasks_changed':
                require(init_count > 0)
                listing = event['tasks']
                require(isinstance(listing, list))
                next_advertised = {}
                for item in listing:
                    task_id, run_id = identity(item['task_id']), identity(item['run_id'])
                    require(item.get('task_type') == 'local_bash')
                    require(task_id not in next_advertised)
                    require(run_id not in next_advertised.values())
                    if task_id in tasks:
                        require(tasks[task_id]['run_id'] == run_id)
                        require(tasks[task_id]['state'] != 'notified')
                    else:
                        require(active and run_id not in runs)
                    next_advertised[task_id] = run_id
                require(all(
                    t['state'] == 'notified' or next_advertised.get(tid) == t['run_id']
                    for tid, t in tasks.items()
                ))
                require(all(tid in tasks for tid in advertised))
                require(next_advertised != advertised)
                advertised = next_advertised
            elif subtype == 'task_started':
                require(active and event.get('is_backgrounded') is True)
                require(event.get('task_type') == 'local_bash')
                task_id, run_id = identity(event['task_id']), identity(event['run_id'])
                tool_id = identity(event['tool_use_id'])
                require(task_id not in tasks and run_id not in runs)
                require(tools.get(tool_id) == 'Bash' and tool_id not in tool_results)
                require(not any(t['tool_use_id'] == tool_id for t in tasks.values()))
                require(advertised.get(task_id) == run_id)
                tasks[task_id] = dict(run_id=run_id, tool_use_id=tool_id, state='started')
                runs.add(run_id)
            elif subtype in ('task_updated', 'task_notification'):
                require(not active and result_count > 0)
                task_id = identity(event['task_id'])
                task = tasks[task_id]
                require(event.get('run_id') == task['run_id'])
                if subtype == 'task_updated':
                    require(task['state'] == 'started')
                    require(event['patch'].get('status') == 'completed')
                    task['state'] = 'updated'
                else:
                    require(task['state'] == 'updated')
                    require(event.get('status') == 'completed')
                    require(event.get('tool_use_id') == task['tool_use_id'])
                    require(task['tool_use_id'] in tool_results)
                    task['state'] = 'notified'
                    callbacks.append(task['run_id'])
                    completed.append(dict(task_id=task_id, run_id=task['run_id'],
                                          tool_use_id=task['tool_use_id']))
            else:
                require(False)
        elif kind in ('assistant', 'user'):
            require(active)
            blocks = event['message']['content']
            require(isinstance(blocks, list))
            for block in blocks:
                block_type = block.get('type')
                if block_type == 'tool_use':
                    require(kind == 'assistant')
                    tool_id = identity(block['id'])
                    require(tool_id not in tools)
                    tools[tool_id] = identity(block['name'])
                elif block_type == 'tool_result':
                    require(kind == 'user')
                    tool_id = identity(block['tool_use_id'])
                    require(tool_id in tools and tool_id not in tool_results)
                    require(type(block.get('is_error', False)) is bool)
                    tool_results.add(tool_id)
                    matching = [tid for tid, t in tasks.items() if t['tool_use_id'] == tool_id]
                    if matching:
                        require(block.get('is_error', False) is False)
                        require(event['tool_use_result'].get('backgroundTaskId') == matching[0])
                else:
                    require(block_type in ('text', 'thinking', 'redacted_thinking'))
        elif kind == 'result':
            require(active and init_count == result_count + 1)
            require(type(event.get('result_index')) is int and event['result_index'] == result_count)
            require(event.get('subtype') == 'success' and event.get('is_error') is False)
            require(event.get('terminal_reason') == 'completed')
            require(type(event.get('num_turns')) is int and event['num_turns'] > 0)
            require(type(event.get('safety_stops')) is int and event['safety_stops'] == 0)
            require(event.get('api_error_status') is None)
            require(set(tools) == tool_results)
            if result_count:
                require(event.get('origin') == dict(kind='task-notification',
                                                  producer='session-task', runId=origin_run))
            else:
                require(event.get('origin') is None)
            result_count += 1
            active, terminal = False, event
        else:
            require(False)
    require(not active and events[-1] is terminal)
    require(init_count == result_count and init_count > 1)
    require(not callbacks and not advertised)
    require(bool(tasks) and all(t['state'] == 'notified' for t in tasks.values()))
    require(len(completed) == init_count - 1)
    digest = hashlib.sha256(json.dumps(events, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    return {'terminal': terminal, 'proof': {'version': 1, 'session_id': session,
            'init_count': init_count, 'result_count': result_count,
            'event_sha256': digest, 'completed_tasks': completed}}
