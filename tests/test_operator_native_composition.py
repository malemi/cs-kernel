"""Constructed complete compositions and separately retained genuine captures."""

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs.operator_native_composition import composition, rejection
from cs.operator_discovery_receipt import CLAUDE_SHA256, CLAUDE_VERSION, COMMAND
from cs.operator_native_lifecycle import continuation


ROOT = Path('/home/mal/.local/share/ordinary-assignment-recovery-resume')


def producer():
    return dict(path='/fixture/versions/' + CLAUDE_VERSION, version=CLAUDE_VERSION,
                sha256=CLAUDE_SHA256, file_identity=[1, 2, 3, 4, 5],
                child_identity=dict(pid=123, started_ticks=456))


def seal(events):
    for index, event in enumerate(events):
        event.update(uuid='constructed-' + str(index), session_id='session')
    return events


def init():
    return dict(type='system', subtype='init', claude_code_version=CLAUDE_VERSION, model='fixed')


def terminal(index=0):
    return dict(type='result', subtype='success', result_index=index, is_error=False,
                terminal_reason='completed', num_turns=1, safety_stops=0, origin=None)


def constructed(kind='foreground', callback=False, held=False):
    use = dict(type='assistant', message={'content': [dict(type='tool_use', id='tool',
        name='Bash', input=dict(command=COMMAND if held else 'true', description='fixture'))]})
    start = dict(type='system', subtype='task_started', task_id='task', run_id='run',
                 tool_use_id='tool', task_type='local_bash', is_backgrounded=kind == 'background')
    listing = dict(type='system', subtype='background_tasks_changed', tasks=[
        dict(task_id='task', run_id='run', task_type='local_bash')])
    notification = dict(type='system', subtype='task_notification', task_id='task', run_id='run',
        tool_use_id='tool', status='failed' if held else 'completed',
        summary='Background command "fixture" ' + ('failed with exit code 3' if held else 'completed (exit code 0)'))
    result = dict(type='user', message={'content': [dict(type='tool_result', tool_use_id='tool', is_error=False)]},
                  tool_use_result=dict(interrupted=False))
    events = [init(), use]
    if kind == 'background':
        events += [listing, start]
    else:
        events += [start]
    if kind == 'foreground':
        if held:
            result['message']['content'][0].update(is_error=True, content='Exit code 3\n{}\n')
            result['tool_use_result'] = 'Error: Exit code 3\n{}\n'
        events += [notification, result, terminal()]
    else:
        if kind == 'automatic':
            events += [listing, dict(type='system', subtype='task_updated', task_id='task',
                                    run_id='run', patch={'is_backgrounded': True})]
        result['tool_use_result']['backgroundTaskId'] = 'task'
        events += [result]
        if callback:
            events += [terminal()]
        events += [dict(type='system', subtype='task_updated', task_id='task', run_id='run',
                        patch=dict(status=notification['status'], end_time=123)), notification,
                   dict(type='system', subtype='background_tasks_changed', tasks=[])]
        if callback:
            final = terminal(1)
            final['origin'] = dict(kind='task-notification', producer='session-task', runId='run')
            events += [init(), final]
        else:
            events += [terminal()]
    return seal(events)


class CompositionTests(unittest.TestCase):
    def test_each_foreground_hold_requires_its_own_joined_phase(self):
        from cs import operator_recovery as recovery
        from cs import operator_discovery_receipt as receipt
        first = constructed('foreground', held=True)
        second = copy.deepcopy(first[1:5])
        for event in second:
            for key in ('task_id', 'run_id', 'tool_use_id'):
                if key in event:event[key] += '-second'
            for block in event.get('message', {}).get('content', []):
                for key in ('id', 'tool_use_id'):
                    if key in block:block[key] += '-second'
        events = seal(first[:-1] + second + [first[-1]])
        self.assertEqual(len(composition(events, producer())['proof']['tasks']), 2)
        for both in (False, True):
            with self.subTest(both_joined=both), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / 'receipt.json'
                def constructed_join(uses, phases, *args, **kwargs):
                    for phase in phases:
                        phase.update(discovery_complete=both or phase['tool_use_id'] == 'tool',
                                     transport={'exit_code': 3})
                attempt = recovery.Attempt(0, events, ordinary_native=True, native_producer=producer())
                with patch.dict(os.environ, {'CS_OPERATOR_ACCEPTANCE_RECEIPT': str(destination),
                        'CS_OPERATOR_ACCEPTANCE_NONCE': 'a' * 32}), patch.object(
                        recovery.config, 'load', return_value=SimpleNamespace(engine_owner_uid='owner')), patch.object(
                        receipt, 'join', side_effect=constructed_join):
                    recovery._write_acceptance_receipt(attempt, producer()['child_identity'])
                actual = json.loads(destination.read_text())[-1]
                self.assertIs(actual['clean_terminal'], both)
                self.assertEqual(attempt.health_failure, '' if both else 'discovery_transport_invalid')

    def test_structured_interruption_remains_rejected_without_summary_inference(self):
        from cs import operator_recovery as recovery
        for status, expected in [('killed', 'native_task_killed'), ('unknown', 'native_composition_invalid')]:
            events = constructed('automatic')
            events[1]['message']['content'][0]['input']['command'] = '.venv/bin/python -m cs review --json'
            updated = next(e for e in events if e.get('patch', {}).get('status') == 'completed')
            updated['patch']['status'] = status
            notification = next(e for e in events if e.get('subtype') == 'task_notification')
            notification.update(status='stopped', summary='PRIVATE timeout text')
            self.assertIsNone(composition(events, producer()))
            self.assertEqual(rejection(events, producer())['reason'], expected)
            attempt = recovery.Attempt(0, events, native_producer=producer(), ordinary_native=True)
            self.assertFalse(recovery._successful(attempt))
            self.assertEqual(attempt.causal['cause'], expected if status == 'killed' else 'terminal_unavailable')
            self.assertNotIn('PRIVATE', json.dumps(attempt.causal))
            foreign = producer(); foreign['sha256'] = '0' * 64
            self.assertNotEqual(rejection(events, foreign)['reason'], 'native_task_killed')
        events = constructed('foreground')
        events[3].update(status='stopped', summary='time limit')
        self.assertEqual(rejection(events, producer())['reason'], 'native_task_stopped')
        events = constructed('automatic')
        next(e for e in events if e.get('subtype') == 'task_notification')['summary'] = 'killed by timeout'
        self.assertNotIn(rejection(events, producer())['reason'], ('native_task_killed', 'native_task_stopped'))

    def test_rejection_reports_predicate_without_event_values(self):
        events = constructed()
        events[3]['status'] = 'failed'
        events[3]['summary'] = 'PRIVATE_SENTINEL'
        before = copy.deepcopy(events)
        self.assertIsNone(composition(events, producer()))
        self.assertEqual(rejection(events, producer()), {
            'reason': 'foreground_failure_not_canonical_discovery', 'event_index': 3,
            'event_type': 'system', 'event_subtype': 'task_notification'})
        self.assertEqual(events, before)
        events[3]['type'] = 'PRIVATE_SENTINEL'
        events[3]['subtype'] = 'PRIVATE_SENTINEL'
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(rejection(events, producer())))
        self.assertIsNone(rejection(constructed(), producer()))

    def test_constructed_complete_shapes_and_literal_projection(self):
        for kind, callback in [('foreground', False), ('automatic', False), ('automatic', True),
                               ('background', True)]:
            with self.subTest(kind=kind, callback=callback):
                events = constructed(kind, callback)
                before = copy.deepcopy(events)
                actual = composition(events, producer())
                self.assertIsNotNone(actual)
                self.assertIs(actual['terminal'], events[-1])
                proof = actual['proof']
                self.assertEqual(proof['version'], 2)
                self.assertEqual(proof['init_count'], 2 if callback else 1)
                self.assertEqual(len(proof['completed_tasks']), int(callback))
                self.assertEqual(proof['tasks'][0]['kind'], kind)
                indices = {row['index'] for row in proof['removed']}
                projected = [e for i, e in enumerate(events) if i not in indices]
                encoded = json.dumps(projected, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
                self.assertEqual(proof['projected_event_sha256'], hashlib.sha256(encoded).hexdigest())
                self.assertEqual(events, before)
                self.assertEqual(sum(e['type'] == 'result' for e in projected), proof['result_count'])

    def test_constructed_held3_is_only_canonical_automatic(self):
        events = constructed('automatic', held=True)
        self.assertEqual(composition(events, producer())['proof']['tasks'][0]['exit_code'], 3)
        events[1]['message']['content'][0]['input']['command'] = 'false'
        self.assertIsNone(composition(events, producer()))
        self.assertIsNone(composition(constructed('background', held=True), producer()))

    def test_foreground_canonical3_requires_matching_original_error_envelope(self):
        events = constructed('foreground', held=True)
        before = copy.deepcopy(events)
        actual = composition(events, producer())
        self.assertEqual(actual['proof']['tasks'][0]['exit_code'], 3)
        self.assertIs(actual['terminal'], events[-1])
        self.assertEqual(events, before)
        for field, value in [('tool_use_result', {'interrupted': False}),
                             ('tool_use_result', 'Error: Exit code 1\n{}\n')]:
            changed = copy.deepcopy(events)
            changed[4][field] = value
            self.assertIsNone(composition(changed, producer()))
        for code in ['1', '03', 'true']:
            changed = copy.deepcopy(events)
            output = 'Exit code ' + code + '\n{}\n'
            changed[4]['message']['content'][0]['content'] = output
            changed[4]['tool_use_result'] = 'Error: ' + output
            self.assertIsNone(composition(changed, producer()))
        changed = copy.deepcopy(events)
        changed[1]['message']['content'][0]['input']['command'] = '.venv/bin/python -m cs review --json'
        self.assertIsNone(composition(changed, producer()))
        changed = copy.deepcopy(events)
        changed[4]['message']['content'][0]['is_error'] = False
        self.assertIsNone(composition(changed, producer()))

    def test_producer_refusals(self):
        for key, value in [('path', '/wrong'), ('version', 'other'), ('sha256', '0' * 64),
                           ('file_identity', [True] * 5), ('child_identity', dict(pid=1, started_ticks=False))]:
            p = producer()
            p[key] = value
            self.assertIsNone(composition(constructed(), p))
        for p in [None, {}, dict(producer(), extra=1)]:
            self.assertIsNone(composition(constructed(), p))

    def test_bound_task_results_require_explicit_noninterruption(self):
        for kind, callback in [('foreground', False), ('automatic', False), ('background', True)]:
            for value in [True, None, 0, 'false']:
                events = constructed(kind, callback)
                result = next(e for e in events if e['type'] == 'user')
                result['tool_use_result']['interrupted'] = value
                with self.subTest(kind=kind, interrupted=value):
                    self.assertIsNone(composition(events, producer()))
            events = constructed(kind, callback)
            result = next(e for e in events if e['type'] == 'user')
            del result['tool_use_result']['interrupted']
            self.assertIsNone(composition(events, producer()))

    def test_producer_path_and_positive_file_identity(self):
        for path in ['/fixture/../versions/' + CLAUDE_VERSION, 'fixture/versions/' + CLAUDE_VERSION]:
            value = producer()
            value['path'] = path
            self.assertIsNone(composition(constructed(), value))
        for index in range(1, 5):
            for invalid in [0, -1, False, '1']:
                value = producer()
                value['file_identity'][index] = invalid
                self.assertIsNone(composition(constructed(), value))
        value = producer()
        value['file_identity'] = [0] * 5
        self.assertIsNone(composition(constructed(), value))
        value['file_identity'] = [0, 1, 1, 1, 1]
        self.assertIsNotNone(composition(constructed(), value))

    def test_strict_field_mutations(self):
        events = constructed('automatic', True)
        cases = []
        for i, event in enumerate(events):
            cases += [(i, 'session_id', 'foreign'), (i, 'uuid', events[0]['uuid'])] if i else []
            if event.get('subtype') == 'task_started':
                cases += [(i, 'task_type', x) for x in ['local_agent', 'local_workflow', 'unknown']]
                cases += [(i, 'tool_use_id', 'foreign'), (i, 'is_backgrounded', True)]
            if event.get('subtype') == 'task_notification':
                cases += [(i, 'status', 'failed'), (i, 'run_id', 'foreign'), (i, 'summary', 'wrong')]
            if event['type'] == 'result':
                cases += [(i, k, v) for k, v in [('result_index', True), ('num_turns', False),
                    ('safety_stops', False), ('is_error', True), ('terminal_reason', 'max_turns')]]
        for i, key, value in cases:
            changed = copy.deepcopy(events)
            changed[i][key] = value
            with self.subTest(index=i, key=key, value=value):
                self.assertIsNone(composition(changed, producer()))
        for name in ['Agent', 'Task']:
            changed = constructed()
            changed[1]['message']['content'][0]['name'] = name
            self.assertIsNone(composition(changed, producer()))

    def test_missing_replayed_reordered_and_zero_results(self):
        for kind, callback in [('foreground', False), ('automatic', True), ('background', True)]:
            events = constructed(kind, callback)
            for index in range(len(events)):
                changed = copy.deepcopy(events)
                del changed[index]
                with self.subTest(kind=kind, missing=index):
                    self.assertIsNone(composition(changed, producer()))
                changed = copy.deepcopy(events)
                repeated = copy.deepcopy(changed[index])
                repeated['uuid'] = 'fresh-duplicate'
                changed.insert(index, repeated)
                self.assertIsNone(composition(changed, producer()))
            for index in range(len(events) - 1):
                if (events[index]['type'] == 'result' and events[index + 1].get('subtype') == 'task_updated') or (kind == 'background' and index == 1):
                    continue
                changed = copy.deepcopy(events)
                changed[index], changed[index + 1] = changed[index + 1], changed[index]
                self.assertIsNone(composition(changed, producer()))
            self.assertIsNone(composition([e for e in events if e['type'] != 'result'], producer()))

    def test_constructed_telemetry_is_literal_and_retained(self):
        telemetry = [
            dict(type='system', subtype='thinking_tokens', estimated_tokens=50, estimated_tokens_delta=50),
            dict(type='tool_progress', tool_name='Bash', parent_tool_use_id='tool',
                 tool_use_id='tool-heartbeat-0', heartbeat=True, elapsed_time_seconds=30),
            dict(type='system', subtype='permission_check_status', tool_use_id='tool', status='checking'),
            dict(type='system', subtype='permission_check_status', tool_use_id='tool', status='done'),
            dict(type='rate_limit_event', rate_limit_info=dict(status='allowed', resetsAt=123,
                 rateLimitType='five_hour', overageStatus='rejected', overageDisabledReason='org_level_disabled',
                 isUsingOverage=False, unifiedWindows=dict(five_hour=dict(utilization=0.1, resetsAt=123),
                                                         seven_day=dict(utilization=0.2, resetsAt=456)))),
        ]
        events = constructed('automatic', True)
        events[2:2] = copy.deepcopy(telemetry)
        seal(events)
        before = copy.deepcopy(events)
        proof = composition(events, producer())['proof']
        removed = {r['index'] for r in proof['removed']}
        self.assertTrue(all(i not in removed for i in range(2, 7)))
        projected = [e for i, e in enumerate(events) if i not in removed]
        encoded = json.dumps(projected, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
        self.assertEqual(proof['projected_event_sha256'], hashlib.sha256(encoded).hexdigest())
        self.assertEqual(events, before)
        mutations = [(2, 'estimated_tokens', True), (2, 'estimated_tokens_delta', -1),
            (3, 'heartbeat', False), (3, 'tool_name', 'Read'), (3, 'elapsed_time_seconds', float('inf')),
            (3, 'elapsed_time_seconds', -1), (3, 'elapsed_time_seconds', False),
            (3, 'elapsed_time_seconds', float('nan')), (3, 'parent_tool_use_id', 'foreign'),
            (3, 'tool_use_id', 'foreign-heartbeat-1'), (4, 'agent_id', 'agent'),
            (4, 'tool_use_id', 'foreign'), (5, 'status', 'checking'), (5, 'status', 'granted'),
            (2, 'unknown', True), (6, 'unknown', True)]
        for index, key, value in mutations:
            changed = copy.deepcopy(events)
            changed[index][key] = value
            with self.subTest(index=index, key=key):
                self.assertIsNone(composition(changed, producer()))
        for index in range(2, 7):
            changed = copy.deepcopy(events)
            changed[index]['session_id'] = 'foreign'
            self.assertIsNone(composition(changed, producer()))
        for status in ['rejected', 'allowed_warning', None]:
            changed = copy.deepcopy(events)
            changed[6]['rate_limit_info']['status'] = status
            self.assertIsNone(composition(changed, producer()))
        for key, value in [('unknown', True), ('isUsingOverage', True), ('resetsAt', False),
                           ('unifiedWindows', {'five_hour': {}})]:
            changed = copy.deepcopy(events)
            changed[6]['rate_limit_info'][key] = value
            self.assertIsNone(composition(changed, producer()))
        for position in [0, len(events)]:
            changed = copy.deepcopy(events)
            sample = copy.deepcopy(changed[2])
            sample['uuid'] = 'outside-active-telemetry'
            changed.insert(position, sample)
            self.assertIsNone(composition(changed, producer()))
        for index in [4, 5]:
            changed = copy.deepcopy(events)
            del changed[index]
            self.assertIsNone(composition(changed, producer()))
        changed = constructed()
        changed.insert(2, dict(type='system', subtype='task_progress'))
        self.assertIsNone(composition(seal(changed), producer()))
        changed = copy.deepcopy(events)
        heartbeat = changed.pop(3)
        changed.insert(-1, heartbeat)
        self.assertIsNone(composition(changed, producer()))

    def test_retained_telemetry_shapes_in_constructed_complete_context(self):
        path = Path('/home/mal/.local/share/mrcall-operational-evidence/2026-10-17/ordinary-assignment-recovery-v18/free-diagnosis/cafe-native-stream.jsonl')
        if not path.exists():
            self.skipTest('Private V18 capture unavailable')
        captured = [json.loads(line) for line in path.read_bytes().splitlines()]
        selected = [e for e in captured if e.get('subtype') == 'thinking_tokens' or
                    e.get('type') in ('tool_progress', 'rate_limit_event')]
        self.assertEqual(len(selected), 145)
        events = constructed('automatic', True)
        rebound = copy.deepcopy(selected)
        for event in rebound:
            if event['type'] == 'tool_progress':
                suffix = event['tool_use_id'].rsplit('-heartbeat-', 1)[1]
                event['parent_tool_use_id'] = 'tool'
                event['tool_use_id'] = 'tool-heartbeat-' + suffix
        permission_shapes = [e for e in captured if e.get('subtype') == 'permission_check_status'
                             and 'agent_id' not in e]
        checking = copy.deepcopy(next(e for e in permission_shapes if e['status'] == 'checking'))
        done = copy.deepcopy(next(e for e in permission_shapes if e['status'] == 'done'))
        checking['tool_use_id'] = done['tool_use_id'] = 'tool'
        rebound += [checking, done]
        events[2:2] = rebound
        seal(events)
        proof = composition(events, producer())['proof']
        removed = {r['index'] for r in proof['removed']}
        self.assertTrue(all(i not in removed for i in range(2, 2 + len(rebound))))
        self.assertEqual(proof['init_count'], 2)
        self.assertEqual(proof['result_count'], 2)

    def test_retained_v18_zero_results_refuses(self):
        path = Path('/home/mal/.local/share/mrcall-operational-evidence/2026-10-17/ordinary-assignment-recovery-v18/free-diagnosis/cafe-native-stream.jsonl')
        if not path.exists():
            self.skipTest('Private V18 capture unavailable')
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '5bfbb004d94a932df0bcc9a74922ac8aad8c947b948e68757185985b0a36506f')
        events = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(sum(e.get('type') == 'result' for e in events), 0)
        self.assertIsNone(composition(events, producer()))
        next_init = next((i for i, e in enumerate(events[1:], 1)
                          if e.get('type') == 'system' and e.get('subtype') == 'init'), len(events))
        self.assertIsNone(composition(events[:next_init], producer()))

    def test_retained_genuine_old_probe(self):
        manifest = ROOT / 'native-stream-retention-20261018/native-lifecycle-sequence.json'
        if not manifest.exists():
            self.skipTest('Private genuine capture unavailable')
        record = json.loads(manifest.read_text())
        raw = Path(record['stream']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'b6e93b4bc22951b166937f089a27475d796dc5285dcabf9ae8474d357fa155e5')
        events = [json.loads(line) for line in raw.splitlines()]
        self.assertIsNotNone(continuation(events))
        self.assertIsNotNone(composition(events, producer()))


if __name__ == '__main__':
    unittest.main()
