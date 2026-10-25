"""Constructed protocol mutations and a separately supplied genuine native stream."""

import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from cs.operator_native_lifecycle import continuation


GENUINE_SHA256 = 'b6e93b4bc22951b166937f089a27475d796dc5285dcabf9ae8474d357fa155e5'


def constructed_events():
    events = [
        dict(type='system', subtype='init', model='fixed'),
        dict(type='assistant', message={'content': [dict(type='tool_use', id='tool', name='Bash')]}),
        dict(type='system', subtype='background_tasks_changed', tasks=[
            dict(task_id='task', run_id='run', task_type='local_bash')]),
        dict(type='system', subtype='task_started', task_id='task', run_id='run',
             tool_use_id='tool', task_type='local_bash', is_backgrounded=True),
        dict(type='user', message={'content': [dict(type='tool_result', tool_use_id='tool', is_error=False)]},
             tool_use_result={'backgroundTaskId': 'task'}),
        dict(type='result', subtype='success', is_error=False, terminal_reason='completed', result_index=0, num_turns=2, safety_stops=0),
        dict(type='system', subtype='task_updated', task_id='task', run_id='run', patch={'status': 'completed'}),
        dict(type='system', subtype='task_notification', task_id='task', run_id='run',
             tool_use_id='tool', status='completed'),
        dict(type='system', subtype='background_tasks_changed', tasks=[]),
        dict(type='system', subtype='init', model='fixed'),
        dict(type='assistant', message={'content': [dict(type='text', text='done')]}),
        dict(type='result', subtype='success', is_error=False, terminal_reason='completed', result_index=1, num_turns=1, safety_stops=0,
             origin={'kind': 'task-notification', 'producer': 'session-task', 'runId': 'run'}),
    ]
    for index, event in enumerate(events):
        event.update(session_id='session', uuid=f'uuid-{index}')
    return events


class ConstructedLifecycleTests(unittest.TestCase):
    def test_constructed_success_and_exact_digest(self):
        events = constructed_events()
        before = copy.deepcopy(events)
        actual = continuation(events)
        self.assertIs(actual['terminal'], events[-1])
        self.assertEqual(actual['proof'], dict(version=1, session_id='session', init_count=2,
            result_count=2, event_sha256=hashlib.sha256(json.dumps(events, sort_keys=True,
            separators=(',', ':'), ensure_ascii=True).encode()).hexdigest(),
            completed_tasks=[dict(task_id='task', run_id='run', tool_use_id='tool')]))
        self.assertEqual(events, before)

    def test_constructed_negative_field_mutations(self):
        mutations = [
            (9, 'session_id', 'foreign'), (9, 'model', 'changed'),
            (9, 'uuid', 'uuid-0'), (3, 'run_id', 'foreign'),
            (3, 'tool_use_id', 'foreign'), (3, 'task_type', 'agent'),
            (3, 'is_backgrounded', False), (6, 'task_id', 'foreign'),
            (6, 'run_id', 'foreign'), (6, 'patch', {'status': 'failed'}),
            (7, 'status', 'pending'), (7, 'tool_use_id', 'foreign'),
            (7, 'run_id', 'foreign'), (7, 'task_id', 'foreign'),
            (11, 'result_index', 0), (11, 'result_index', True),
            (11, 'is_error', True), (11, 'subtype', 'error'),
            (11, 'terminal_reason', 'max_turns'),
            (11, 'safety_stops', 1), (11, 'origin', None),
            (11, 'origin', {'kind': 'task-notification', 'producer': 'unknown', 'runId': 'run'}),
            (11, 'origin', {'kind': 'task-notification', 'producer': 'session-task', 'runId': 'other'}),
            (5, 'is_error', True), (2, 'subtype', 'unknown'),
            (4, 'tool_use_result', {'backgroundTaskId': 'other'}),
        ]
        for index, key, value in mutations:
            with self.subTest(index=index, key=key, value=value):
                events = constructed_events()
                events[index][key] = value
                self.assertIsNone(continuation(events))

    def test_constructed_missing_duplicate_and_reordered_events(self):
        for index in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11]:
            with self.subTest(missing=index):
                events = constructed_events()
                del events[index]
                self.assertIsNone(continuation(events))
        for index in range(12):
            with self.subTest(duplicate=index):
                events = constructed_events()
                events.insert(index, copy.deepcopy(events[index]))
                self.assertIsNone(continuation(events))
        for left, right in [(6, 7), (7, 9), (3, 4), (5, 6)]:
            with self.subTest(order=(left, right)):
                events = constructed_events()
                events[left], events[right] = events[right], events[left]
                self.assertIsNone(continuation(events))

    def test_constructed_three_ordered_segments(self):
        first = constructed_events()
        second = constructed_events()
        encoded = json.dumps(second).replace('"tool"', '"tool2"').replace('"task"', '"task2"').replace('"run"', '"run2"')
        second = json.loads(encoded)
        combined = first[:10] + second[1:]
        combined[14]['result_index'] = 1
        combined[14]['origin'] = first[-1]['origin']
        combined[-1]['result_index'] = 2
        for index, event in enumerate(combined):
            event['uuid'] = f'three-{index}'
        actual = continuation(combined)
        self.assertIsNotNone(actual)
        self.assertEqual(actual['proof']['init_count'], 3)
        self.assertEqual(len(actual['proof']['completed_tasks']), 2)

    def test_constructed_replayed_callback_with_fresh_uuid(self):
        for index in [3, 6, 7, 8]:
            events = constructed_events()
            duplicate = copy.deepcopy(events[index])
            duplicate['uuid'] = 'fresh-replay'
            events.insert(index + 1, duplicate)
            self.assertIsNone(continuation(events))

    def test_constructed_foreground_error_is_left_to_phase_validators(self):
        events = constructed_events()
        foreground = [
            dict(type='assistant', message={'content': [dict(type='tool_use', id='discovery',
                 name='Bash', input={'command': 'cs tasks unanswered --json'})]}),
            dict(type='user', message={'content': [dict(type='tool_result', tool_use_id='discovery',
                 is_error=True, content='{"exit_code":3,"status":"human_holds"}')]}),
        ]
        for index, event in enumerate(foreground):
            event.update(session_id='session', uuid=f'foreground-{index}')
        events[1:1] = foreground
        self.assertIsNotNone(continuation(events))
        events[2]['message']['content'][0]['is_error'] = 'false'
        self.assertIsNone(continuation(events))
        background_error = constructed_events()
        background_error[4]['message']['content'][0]['is_error'] = True
        self.assertIsNone(continuation(background_error))

    def test_constructed_optional_denial_preserves_terminal_evidence(self):
        events = constructed_events()
        denial = {'tool_name': 'Bash', 'tool_use_id': 'optional',
                  'tool_input': {'command': 'python3 read_optional.py'}}
        foreground = [
            dict(type='assistant', message={'content': [dict(type='tool_use', id='optional',
                 name='Bash', input=denial['tool_input'])]}),
            dict(type='user', message={'content': [dict(type='tool_result', tool_use_id='optional',
                 is_error=True, content='Permission denied')]}),
            dict(type='assistant', message={'content': [dict(type='tool_use', id='read',
                 name='Read', input={'file_path': '/tmp/optional-output'})]}),
            dict(type='user', message={'content': [dict(type='tool_result', tool_use_id='read',
                 is_error=False, content='Optional output')]}),
        ]
        for index, event in enumerate(foreground):
            event.update(session_id='session', uuid=f'optional-{index}')
        events[1:1] = foreground
        events[9]['permission_denials'] = [denial]
        events[-1]['permission_denials'] = [denial]
        actual = continuation(events)
        self.assertIsNotNone(actual)
        self.assertIs(actual['terminal'], events[-1])
        self.assertEqual(actual['terminal']['permission_denials'], [denial])
        self.assertNotIn('permission_grant', actual['proof'])

    def test_constructed_every_terminal_requires_typed_counts(self):
        for index in [5, 11]:
            for key, values in [('num_turns', ['bad', False, 0, -1, None]),
                                ('safety_stops', [{}, '', False, 1, None])]:
                for value in values:
                    with self.subTest(index=index, key=key, value=value):
                        events = constructed_events()
                        events[index][key] = value
                        self.assertIsNone(continuation(events))
                events = constructed_events()
                del events[index][key]
                self.assertIsNone(continuation(events))

    def test_single_result_is_left_to_existing_validator(self):
        self.assertIsNone(continuation(constructed_events()[:6]))
        self.assertIsNone(continuation([]))
        self.assertIsNone(continuation(None))


class GenuineCapturedLifecycleTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('CS_NATIVE_LIFECYCLE_STREAM'), 'Private genuine stream not supplied')
    def test_original_capture_and_negative_mutations(self):
        raw = Path(os.environ['CS_NATIVE_LIFECYCLE_STREAM']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), GENUINE_SHA256)
        events = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(len(events), 13)
        self.assertIsNotNone(continuation(events))
        for index in [6, 12]:
            for key, values in [('num_turns', ['bad', False, 0, -1, None]),
                                ('safety_stops', [{}, '', False, 1, None])]:
                for value in values:
                    with self.subTest(actual_index=index, key=key, value=value):
                        changed = copy.deepcopy(events)
                        changed[index][key] = value
                        self.assertIsNone(continuation(changed))
                changed = copy.deepcopy(events)
                del changed[index][key]
                self.assertIsNone(continuation(changed))
        for index, key, value in [(10, 'model', 'foreign'), (8, 'status', 'failed'),
                                  (12, 'origin', None), (12, 'result_index', 3)]:
            with self.subTest(index=index, key=key):
                changed = copy.deepcopy(events)
                changed[index][key] = value
                self.assertIsNone(continuation(changed))


if __name__ == '__main__':
    unittest.main()
