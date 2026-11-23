"""Exercise real private workset persistence without provider calls."""
import copy
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from cs.config import Settings
from cs.operator_health import identity
from cs.operator_workset import WorksetError, observe, reserve, require_root, require_contact, _inventory, _timestamp, _stable, _hash


class WorksetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {'HOME': str(self.home)}, clear=False)
        self.environment.start()
        self.settings = Settings(_env_file=None, slug='workset-test', engine_owner_uid='owner')
        self.number = 0
        self.new_run()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def new_run(self):
        self.number += 1
        directory = self.home / ('run-' + str(self.number))
        directory.mkdir(mode=0o700)
        os.environ['CS_OPERATOR_HEALTH_CONTEXT'] = json.dumps({'directory': str(directory),
            'nonce': 'run-' + str(self.number), 'supervisor': identity(os.getpid())[0],
            'workset_enabled': True, 'owner_uid': 'owner'})
        self.directory = directory

    def discovery(self, *names):
        return {'open': [{'thread_key': '<' + name + '@example.test>', '_workset_revision': name[0] * 64,
                          'last_inbound_date': '2026-10-' + str(index + 10)} for index, name in enumerate(names)],
                'resumed': [], 'human_work': [], 'assignment_audit': [], 'escalated': [],
                'read_incomplete': None, 'assignment_incomplete': False}

    def observe(self, tasks=None, drafts=None):
        observe(self.settings, 'tasks', tasks or [])
        observe(self.settings, 'review', {'drafts': drafts or [], 'drafts_notes': []})

    def selected(self, value):
        return [row['thread_key'] for row in value['selected']]

    def test_shared_cap_dedup_idempotence_and_no_payload_cursor(self):
        self.observe([{'id': 't', 'sources': {'thread_id': '<b@example.test>'}, 'updated_at': '2026-10-20'}],
                     [{'id': 'd', 'thread_id': '<c@example.test>', 'verdict': 'replace', 'composed_at': '2026-10-21'},
                      {'id': 'duplicate', 'thread_id': '<a@example.test>', 'verdict': 'replace'}])
        discovery = self.discovery('a')
        result = reserve(self.settings, discovery)
        self.assertEqual(len(result['selected']), 2)
        self.assertEqual(self.selected(result)[0], '<c@example.test>')
        self.assertEqual(len(result['deferred']), 1)
        self.assertEqual(result, reserve(self.settings, discovery))
        observe(self.settings, 'tasks', [], complete=False)
        self.assertEqual(result, reserve(self.settings, discovery))
        self.assertEqual(len(discovery['open']), 1)
        cursor = self.settings.state_dir / 'operator-workset' / 'cursor.json'
        self.assertNotIn('example.test', cursor.read_text())
        self.assertEqual(cursor.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.settings.state_dir / 'cs.db').exists())
        discovery['open'][0]['last_inbound_date'] = 'changed'
        with self.assertRaises(WorksetError):
            reserve(self.settings, discovery)

    def test_rotation_and_new_revision(self):
        discovery = self.discovery('a', 'b', 'c', 'd')
        self.observe()
        first = self.selected(reserve(self.settings, discovery))
        self.new_run()
        self.observe()
        second = self.selected(reserve(self.settings, discovery))
        self.assertEqual(set(first + second), {'<' + name + '@example.test>' for name in 'abcd'})
        self.new_run()
        self.observe()
        discovery['open'][0]['_workset_revision'] = 'e' * 64
        discovery['open'][0]['last_inbound_date'] = '2026-12-01'
        self.assertEqual(self.selected(reserve(self.settings, discovery))[0], '<a@example.test>')

    def test_new_ready_mailbox_draft_reserves_same_inbound_on_next_tick(self):
        discovery = self.discovery('a', 'b', 'c', 'd')
        self.observe()
        first = self.selected(reserve(self.settings, discovery))
        root = first[0]
        self.new_run()
        self.observe(drafts=[dict(draft_id='native-handle', mailbox_id='box', thread_key=root,
                                  verdict='ready', composed_at='2026-11-23T00:00:00Z')])
        second = self.selected(reserve(self.settings, discovery))
        self.assertIn(root, second)
        self.assertEqual(len(set(first) | set(second)), 3)

    def test_held_roots_and_address_takeover(self):
        self.observe([{'id': 't', 'thread_id': '<b@example.test>', 'contact_email': 'taken@example.test'},
                      {'id': 'missing'}], [{'id': 'd', 'thread_id': '<a@example.test>', 'verdict': 'replace'}])
        discovery = self.discovery('a')
        discovery['human_work'] = [{'thread_key': '<a@example.test>'}]
        discovery['escalated'] = [{'email': 'taken@example.test'}]
        result = reserve(self.settings, discovery)
        self.assertEqual(result['selected'], [])
        self.assertEqual(len(result['held']), 6)
        self.assertTrue(any(row.get('identity') == 'missing' for row in result['held']))

    def test_context_owner_privacy_corruption_and_incomplete(self):
        with self.assertRaises(WorksetError):
            reserve(self.settings, self.discovery('a'))
        with self.assertRaises(WorksetError):
            observe(self.settings, 'tasks', [], complete=False)
        with self.assertRaises(WorksetError):
            observe(self.settings, 'review', {'drafts': [], 'drafts_notes': ['unreadable']})
        self.observe()
        reserve(self.settings, self.discovery('a'))
        self.new_run()
        self.observe()
        foreign = Settings(_env_file=None, slug='workset-test', engine_owner_uid='foreign')
        with self.assertRaises(WorksetError):
            reserve(foreign, self.discovery('a'))
        cursor = self.settings.state_dir / 'operator-workset' / 'cursor.json'
        cursor.chmod(0o644)
        with self.assertRaises(WorksetError):
            reserve(self.settings, self.discovery('a'))
        cursor.chmod(0o600)
        cursor.write_text('{}')
        with self.assertRaises(WorksetError):
            reserve(self.settings, self.discovery('a'))
        context = json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
        context['supervisor']['started_ticks'] += 1
        os.environ['CS_OPERATOR_HEALTH_CONTEXT'] = json.dumps(context)
        with self.assertRaises(WorksetError):
            observe(self.settings, 'tasks', [])

    def test_independent_root_survives_same_contact_unknown_hold(self):
        self.observe()
        discovery = self.discovery('a', 'b')
        discovery['assignment_incomplete'] = True
        discovery['open'][0]['email'] = 'shared@example.test'
        discovery['open'][1]['email'] = 'shared@example.test'
        discovery['human_work'] = [{'thread_key': '<a@example.test>', 'email': 'shared@example.test',
            'assignment': {'actor_uid': 'owner', 'source_owner_uid': 'owner', 'complete': False}}]
        result = reserve(self.settings, discovery)
        self.assertEqual(self.selected(result), ['<b@example.test>'])
        self.new_run()
        self.observe()
        discovery['human_work'][0]['assignment']['actor_uid'] = 'foreign'
        with self.assertRaises(WorksetError):
            reserve(self.settings, discovery)

    def test_guards_and_real_subprocess(self):
        with self.assertRaises(WorksetError):
            require_root(self.settings, '<a@example.test>')
        self.observe()
        discovery = self.discovery('a', 'b', 'c')
        for row in discovery['open']:
            row['email'] = row['thread_key'][1:-1]
        result = reserve(self.settings, discovery)
        for row in result['selected']:
            require_root(self.settings, row['thread_key'])
            require_contact(self.settings, row['thread_key'][1:-1].upper())
        deferred = result['deferred'][0]['thread_key']
        with self.assertRaises(WorksetError):
            require_root(self.settings, deferred)
        with self.assertRaises(WorksetError):
            require_contact(self.settings, deferred[1:-1])
        foreign = Settings(_env_file=None, slug='workset-test', engine_owner_uid='foreign')
        with self.assertRaises(WorksetError):
            require_root(foreign, result['selected'][0]['thread_key'])
        code = "from cs.config import Settings; from cs.operator_workset import require_root; import sys; require_root(Settings(_env_file=None, slug='workset-test', engine_owner_uid='owner'),sys.argv[1])"
        child = subprocess.run([sys.executable, '-c', code, result['selected'][0]['thread_key']], capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        child = subprocess.run([sys.executable, '-c', code, deferred], capture_output=True, text=True)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn('outside the scheduled workset', child.stderr)
        receipt = self.directory / 'workset-reserved.json'
        receipt.unlink()
        with self.assertRaises(WorksetError):
            require_contact(self.settings, result['selected'][0]['thread_key'][1:-1])

    def task_row(self, name, signal=None, created='2026-01-01'):
        return {'id': name, 'event_type': 'email', 'event_id': name,
                'sources': {'emails': [name], 'blobs': [], 'calendar_events': []},
                'status': 'pending', 'thread_key': '<' + name + '@example.test>',
                'last_signal_at': signal, 'created_at': created}

    def task_inventory(self, rows, discovery=None, drafts=None):
        return _inventory(discovery or self.discovery(),
            {'tasks': rows, 'review': {'drafts': drafts or [], 'drafts_notes': []}}, 'owner')

    def test_task_source_state_holds_preserve_observation(self):
        from cs.operator_inventory_view import check
        for state in ['unresolved', 'unknown', 'Resolved', '', True, False, None, 1, [], {}, ['resolved']]:
            with self.subTest(state=state):
                row = dict(self.task_row('a', '2099-01-01'), source_root_state=state)
                before = copy.deepcopy(row)
                candidates, held = self.task_inventory([row])
                self.assertEqual(candidates, {})
                self.assertEqual(held, [{'thread_key': row['thread_key'],
                    'reason': 'unresolved_task_source_root', 'source': 'tasks', 'identity': 'a'}])
                self.assertEqual(row, before)
                discovery = self.discovery()
                discovery['triage_workset'] = dict(complete=True, limit=2, selected=[], deferred=[], held=held)
                check(dict(nonce='test', owner_uid='owner', ancestry=[], exit_code=0,
                           output_sha256='a' * 64, discovery=discovery))
        row = dict(self.task_row('a'), source_root_state='unresolved', thread_key='malformed')
        candidates, held = self.task_inventory([row])
        self.assertEqual(candidates, {})
        self.assertEqual(held[0]['reason'], 'unresolved_task_source_root')

    def test_task_source_state_legacy_resolved_and_revision(self):
        row = self.task_row('a', '2026-10-19')
        legacy, held = self.task_inventory([row])
        resolved = dict(row, source_root_state='resolved')
        admitted, resolved_held = self.task_inventory([resolved])
        self.assertEqual(held, [])
        self.assertEqual(resolved_held, [])
        self.assertEqual(set(legacy), set(admitted))
        self.assertEqual(legacy[row['thread_key']]['date'], admitted[row['thread_key']]['date'])
        states = [dict(row), resolved, dict(row, source_root_state='unresolved'),
                  dict(row, source_root_state=None), dict(row, source_root_state=False)]
        self.assertEqual(len({_hash(_stable(item, 'tasks')) for item in states}), len(states))
        self.assertEqual(_stable(row, 'review'), _stable(resolved, 'review'))
        for fields in [{'thread_key': None}, {'thread_id': '<other@example.test>'}]:
            candidates, held = self.task_inventory([dict(resolved, **fields)])
            self.assertEqual(candidates, {})
            self.assertEqual(held[0]['reason'], 'missing_exact_root')

    def test_unresolved_task_does_not_block_independent_discovery(self):
        row = dict(self.task_row('a', '2099-01-01'), source_root_state='unresolved')
        discovery = self.discovery('a', 'b')
        expected, _ = self.task_inventory([], discovery)
        actual, held = self.task_inventory([row], discovery)
        self.assertEqual(actual, expected)
        self.assertEqual(held[0]['reason'], 'unresolved_task_source_root')
        self.observe([row])
        result = reserve(self.settings, discovery)
        self.assertEqual(set(self.selected(result)), set(expected))
        self.assertTrue(all(item['sources'] == ['discovery'] for item in result['selected']))

    def test_task_signal_fresh_slot_and_old_round_robin(self):
        rows = [self.task_row(name, '2026-01-0' + str(index + 1))
                for index, name in enumerate('abc')]
        self.observe(rows)
        first = self.selected(reserve(self.settings, self.discovery()))
        self.assertEqual(first, ['<c@example.test>', '<a@example.test>'])
        self.new_run()
        rows.append(self.task_row('new', '2026-10-19'))
        self.observe(rows)
        second = self.selected(reserve(self.settings, self.discovery()))
        self.assertEqual(second, ['<new@example.test>', '<b@example.test>'])
        self.new_run()
        self.observe(rows)
        third = self.selected(reserve(self.settings, self.discovery()))
        self.assertEqual(third, ['<a@example.test>', '<c@example.test>'])
        with self.assertRaises(WorksetError):
            require_root(self.settings, '<new@example.test>')

    def test_task_same_root_new_signal_changes_revision(self):
        rows = [self.task_row('a', '2026-01-01'), self.task_row('b', '2026-02-01')]
        before, _ = self.task_inventory(rows)
        self.observe(rows)
        reserve(self.settings, self.discovery())
        self.new_run()
        rows[0]['last_signal_at'] = '2026-10-19'
        after, _ = self.task_inventory(rows)
        self.assertNotEqual(before['<a@example.test>']['revision'], after['<a@example.test>']['revision'])
        self.assertEqual(before['<b@example.test>']['revision'], after['<b@example.test>']['revision'])
        self.observe(rows)
        self.assertEqual(self.selected(reserve(self.settings, self.discovery()))[0], '<a@example.test>')
        rows[0]['created_at'] = '2025-01-01'
        changed, _ = self.task_inventory(rows)
        self.assertNotEqual(after['<a@example.test>']['revision'], changed['<a@example.test>']['revision'])

    def test_task_date_precedence_invalid_and_other_sources(self):
        row = self.task_row('a', '2026-10-19', '2026-11-01')
        for fields, expected in [({}, '2026-10-19'),
                ({'last_signal_at': None}, '2026-11-01'),
                ({'last_signal_at': None, 'created_at': None}, None),
                ({'last_signal_at': 'malformed'}, None),
                ({'last_signal_at': None, 'created_at': 'malformed'}, None),
                ({'composed_at': '2026-02-01'}, '2026-02-01'),
                ({'updated_at': '2026-03-01', 'composed_at': '2026-02-01'}, '2026-03-01'),
                ({'last_inbound_date': '2026-04-01', 'updated_at': '2026-03-01'}, '2026-04-01'),
                ({'updated_at': 'malformed'}, None)]:
            with self.subTest(fields=fields):
                candidates, _ = self.task_inventory([dict(row, **fields)])
                self.assertEqual(candidates[row['thread_key']]['date'], _timestamp(expected))
        missing = dict(row)
        missing.pop('last_signal_at')
        candidates, _ = self.task_inventory([missing])
        self.assertEqual(candidates[row['thread_key']]['date'], _timestamp(row['created_at']))
        missing.pop('created_at')
        candidates, _ = self.task_inventory([missing])
        self.assertEqual(candidates[row['thread_key']]['date'], 0)
        draft = dict(row, verdict='replace')
        before, _ = self.task_inventory([], drafts=[draft])
        draft['last_signal_at'] = '2027-01-01'
        draft['created_at'] = '2028-01-01'
        after, _ = self.task_inventory([], drafts=[draft])
        self.assertEqual(before, after)
        self.assertEqual(after[row['thread_key']]['date'], 0)

    def test_task_dates_do_not_bypass_holds_or_completion(self):
        rows = [self.task_row('a', '2099-01-01'), self.task_row('b', '2099-01-01'),
                dict(self.task_row('c', '2099-01-01'), status='completed'),
                {'id': 'missing', 'last_signal_at': '2099-01-01'}]
        discovery = self.discovery()
        discovery['human_work'] = [{'thread_key': '<a@example.test>',
            'assignment': {'actor_uid': 'owner', 'source_owner_uid': 'owner', 'complete': False}}]
        candidates, held = self.task_inventory(rows, discovery)
        self.assertEqual(set(candidates), {'<b@example.test>'})
        self.assertEqual({row['reason'] for row in held},
                         {'human_work', 'fresh_discovery_hold', 'missing_exact_root'})
        discovery['read_incomplete'] = 'missing'
        with self.assertRaises(ValueError):
            self.task_inventory(rows, discovery)

    def test_interactive_and_symlink_source(self):
        os.environ.pop('CS_OPERATOR_HEALTH_CONTEXT')
        self.assertIsNone(reserve(self.settings, {}))
        self.assertIsNone(observe(self.settings, 'tasks', []))
        self.new_run()
        target = self.home / 'other'
        target.write_text('{}')
        target.chmod(0o600)
        (self.directory / 'workset-tasks.json').symlink_to(target)
        with self.assertRaises(WorksetError):
            observe(self.settings, 'tasks', [])


if __name__ == '__main__':
    unittest.main()
