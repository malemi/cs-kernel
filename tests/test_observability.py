"""Diagnostic persistence fault and isolation checks without upstream services."""
import contextlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs.observability import EventStore, context, current_context


def writer(root, count):
    store = EventStore(root, 'owner', segment_bytes=8192, max_bytes=1024*1024)
    for _ in range(count):
        assert store.emit('rpc', 'result', method='emails.search')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'events'
        self.store = EventStore(self.root, 'owner')

    def tearDown(self):
        self.temp.cleanup()

    def test_real_multiprocess_pagination_and_reopen(self):
        workers = [multiprocessing.Process(target=writer, args=(self.root, 20)) for _ in range(3)]
        for process in workers:
            process.start()
        for process in workers:
            process.join(5)
            self.assertEqual(process.exitcode, 0)
        result = EventStore(self.root, 'owner')
        events, cursor = [], None
        while True:
            page = result.events(cursor=cursor, limit=7)
            events.extend(page['events'])
            cursor = page['next_cursor']
            if not cursor:
                break
        self.assertEqual(len(events), 60)
        self.assertEqual(len({e['event_id'] for e in events}), 60)
        self.assertTrue(all(e['source_digest_scope'] == 'observability-module' for e in events))
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)

    def test_metadata_export_and_context_reset(self):
        with context() as scoped:
            event = self.store.emit('cli', 'start', body='CANARY_SECRET', password='CANARY_SECRET', error_class='ValueError')
            self.assertEqual(event['trace_id'], scoped['trace_id'])
        self.assertFalse(current_context())
        self.assertNotIn('CANARY_SECRET', json.dumps(self.store.events()))
        path = next(self.root.glob('events-*'))
        event['body'] = 'CANARY_SECRET'
        with path.open('a') as stream:
            stream.write(json.dumps(event)+'\n')
        page = self.store.events()
        self.assertEqual(len(page['events']), 1)
        self.assertNotIn('CANARY_SECRET', json.dumps(page))
        self.assertTrue(any(g['reason'] == 'malformed-event' for g in page['coverage']['gaps']))

    def test_symlink_and_unwritable_stderr_do_not_raise(self):
        target = Path(self.temp.name) / 'elsewhere'
        target.mkdir()
        self.root.symlink_to(target, target_is_directory=True)
        with patch('sys.stderr.write', side_effect=OSError('CANARY_SECRET')):
            self.assertIsNone(self.store.emit('cli', 'start'))
        self.assertFalse(list(target.iterdir()))
        self.assertEqual(self.store.health()['status'], 'unavailable')

    def test_retention_reports_evicted_cursor(self):
        self.store = EventStore(self.root, 'owner', max_bytes=8192, segment_bytes=8192)
        for _ in range(10):
            self.store.emit('cli', 'result')
        cursor = self.store.events(limit=1)['next_cursor']
        for _ in range(30):
            self.store.emit('cli', 'result')
        self.assertLessEqual(sum(p.stat().st_size for p in self.root.glob('events-*')), 8192)
        self.assertTrue(self.store.health()['gaps'])
        self.assertTrue(any(g['reason'] == 'cursor-evicted' for g in self.store.events(cursor=cursor)['coverage']['gaps']))

    def test_disk_failure_persists_degraded_state(self):
        self.store.emit('cli', 'start')
        with contextlib.redirect_stderr(io.StringIO()) as captured, patch('cs.observability_store.append', side_effect=OSError('CANARY_SECRET')):
            self.assertIsNone(self.store.emit('cli', 'result'))
        self.assertNotIn('CANARY_SECRET', captured.getvalue())
        self.assertEqual(EventStore(self.root, 'owner').health()['status'], 'degraded')

    def test_absent_read_has_no_side_effects(self):
        self.assertFalse(self.store.events()['coverage']['available'])
        self.assertFalse(self.root.exists())
        with self.assertRaises(ValueError):
            self.store.events(cursor='../token', limit=3)
        with self.assertRaises(ValueError):
            self.store.events(limit=201)

    def test_wire_fixture_matches_constants(self):
        from cs.observability import STAGES, STATUSES, REASONS, CERTAINTY
        fixture = json.loads((Path(__file__).parent/'fixtures/observability-v1.json').read_text())
        self.assertEqual(fixture['stages'], sorted(STAGES))
        self.assertEqual(fixture['statuses'], sorted(STATUSES))
        self.assertEqual(fixture['reasons'], sorted(REASONS))
        self.assertEqual(fixture['effect_certainty'], sorted(CERTAINTY))
        event = self.store.emit('rpc', 'result')
        self.assertTrue(set(fixture['required_event_keys']) <= event.keys())

    def test_forged_safe_field_values_never_export(self):
        event = self.store.emit('cli', 'result')
        path = next(self.root.glob('events-*'))
        for key in ('draft_id', 'process_start', 'timestamp'):
            forged = {**event, key: 'CANARY_SECRET'}
            with path.open('a') as stream:
                stream.write(json.dumps(forged)+'\n')
        self.assertNotIn('CANARY_SECRET', json.dumps(self.store.events()))

    def test_expired_read_excludes_events_without_changing_bytes(self):
        import hashlib
        import time
        self.store = EventStore(self.root, 'owner', retention_days=1)
        self.store.emit('rpc', 'start')
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        future = time.time()+3*86400
        with patch('cs.observability_store.time.time', return_value=future):
            page = self.store.events()
            health = self.store.health()
        self.assertEqual(page['events'], [])
        self.assertFalse(page['coverage']['available'])
        self.assertEqual(page['coverage']['status'], 'degraded')
        self.assertEqual(health['status'], 'degraded')
        self.assertGreater(health['bytes'], 0)
        self.assertTrue(any(g['reason'] == 'retention-expired' for g in health['gaps']))
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        self.assertEqual(before, after)

    def test_selected_owners_share_base_without_sharing_records(self):
        from types import SimpleNamespace
        from cs.observability import store_for, owner_root
        state = Path(self.temp.name)/'clone-state'
        first = store_for(SimpleNamespace(state_dir=state, engine_owner_uid='owner-a'))
        second = store_for(SimpleNamespace(state_dir=state, engine_owner_uid='owner-b'))
        self.assertNotEqual(first.root, second.root)
        self.assertFalse(state.exists())
        a = first.emit('cli', 'result')
        b = second.emit('cli', 'result')
        self.assertEqual([e['event_id'] for e in first.events()['events']], [a['event_id']])
        self.assertEqual([e['event_id'] for e in second.events()['events']], [b['event_id']])
        self.assertEqual(first.events()['coverage']['gaps'], [])
        self.assertEqual(second.events()['coverage']['gaps'], [])
        self.assertEqual((state/'observability').stat().st_mode & 0o777, 0o700)
        self.assertEqual(first.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(second.root.stat().st_mode & 0o777, 0o700)
        direct = EventStore(owner_root(state, 'owner-a'), 'owner-a')
        self.assertEqual(direct.locations()['legacy_log'], str(state/'cs_operator.log'))
        wrong = EventStore(owner_root(state, 'owner-a'), 'owner-b')
        self.assertEqual(wrong.events()['events'], [])
        self.assertFalse(wrong.health()['available'])
        self.assertEqual(wrong.health()['status'], 'unavailable')

    def test_flat_prototype_is_referenced_without_migration(self):
        from types import SimpleNamespace
        from cs.observability import store_for
        state = Path(self.temp.name)/'clone-state'
        base = state/'observability'
        prototype = EventStore(base, 'old-owner')
        prototype.emit('cli', 'result')
        original = {p.name:p.read_bytes() for p in base.glob('events-*')}
        selected = store_for(SimpleNamespace(state_dir=state, engine_owner_uid='new-owner'))
        selected.emit('cli', 'result')
        self.assertEqual(original, {p.name:p.read_bytes() for p in base.glob('events-*')})
        locations = selected.locations()
        self.assertEqual(locations['legacy_flat_root'], str(base))
        self.assertEqual(locations['legacy_log'], str(state/'cs_operator.log'))
        self.assertEqual(locations['native_log_root'], str(state/'operator-runs'))
        self.assertEqual(len(selected.events()['events']), 1)

    def test_public_namespace_base_is_refused_without_chmod_or_child_write(self):
        from types import SimpleNamespace
        from cs.observability import store_for
        state = Path(self.temp.name)/'clone-state'
        base = state/'observability'
        base.mkdir(parents=True, mode=0o755)
        base.chmod(0o755)
        selected = store_for(SimpleNamespace(state_dir=state, engine_owner_uid='owner'))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(selected.emit('cli', 'start'))
        self.assertEqual(base.stat().st_mode & 0o777, 0o755)
        self.assertFalse(selected.root.exists())
