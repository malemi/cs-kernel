"""Repeated observations retain the original cause and require later recovery."""
import copy
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cs.monitor import _sync
from cs.monitor_config import Component
from cs.monitor_details import safe_detail
from cs.monitor_evaluate import evaluate, initial_state, observe
from cs.monitor_store import MonitorStore
from cs.observability import EventStore, context


class PrimaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = EventStore(self.root / 'source', 'owner')
        self.state = initial_state()
        self.now = time.time()
        self.component = Component(id='kernel', kind='kernel', local_root=str(self.source.root))

    def event(self, offset, status='failed', **metadata):
        with context():
            event = self.source.emit('rpc', status, reason='timeout' if status == 'failed' else 'none',
                                     method='draft.generate', root_id='root', request_revision='v1',
                                     **metadata)
        event['timestamp'] = datetime.fromtimestamp(self.now + offset, timezone.utc).isoformat()
        observe(self.state, event, self.now + 100)
        return event

    def test_original_payload_and_latest_refs_survive_restart_and_ack(self):
        first = self.event(0, error_class='TimeoutError', error_file='cs/rpc.py', error_line=1)
        original = copy.deepcopy(next(iter(self.state['failures'].values())))
        store = MonitorStore(self.root / 'monitor', 'owner')
        def sync():
            _sync(store, 'kernel', evaluate(self.component, self.state, self.source.health(), self.now + 100),
                  self.now + 100, allow_recovery=True)
        sync()
        incident = store.incidents()[0]
        store.ack(incident['id'], self.now + 100, 86400)
        before = store.incidents()[0]
        self.state = json.loads(json.dumps(self.state))
        latest = self.event(10, error_class='ConnectionError')
        detail = next(iter(self.state['failures'].values()))
        for key, value in original.items():
            if key != 'last':
                self.assertEqual(detail[key], value)
        self.assertNotEqual(first['trace_id'], latest['trace_id'])
        for key in ('event_id', 'trace_id', 'span_id'):
            self.assertEqual(detail['last_' + key], latest[key])
        self.assertEqual(safe_detail(detail), detail)
        sync()
        after = store.incidents()[0]
        self.assertEqual(before['revision'], after['revision'])
        self.assertEqual(before['acknowledged'], after['acknowledged'])
        self.assertEqual(after['detail'], detail)
        self.event(5, status='result')
        self.assertTrue(self.state['failures'])
        self.event(20, status='result')
        self.assertFalse(self.state['failures'])
        fresh = self.event(30, error_class='ConnectionError')
        self.assertEqual(next(iter(self.state['failures'].values()))['event_id'], fresh['event_id'])

    def test_severity_escalates_without_replacing_primary_and_old_repeat_cannot_rewind(self):
        self.event(0, error_class='TimeoutError')
        first = copy.deepcopy(next(iter(self.state['failures'].values())))
        latest = self.event(10, level='CRITICAL', error_class='ConnectionError')
        self.event(5, level='ERROR')
        detail = next(iter(self.state['failures'].values()))
        self.assertEqual(detail['level'], 'CRITICAL')
        self.assertEqual(detail['event_id'], first['event_id'])
        self.assertEqual(detail['error_class'], 'TimeoutError')
        self.assertEqual(detail['last_event_id'], latest['event_id'])
        self.assertAlmostEqual(detail['last'], self.now + 10, places=5)

    def test_legacy_and_duplicate_primary_preserved(self):
        first = self.event(0)
        detail = next(iter(self.state['failures'].values()))
        detail.pop('last')
        self.event(10)
        self.assertEqual(detail['event_id'], first['event_id'])
        observe(self.state, first, self.now + 100)
        self.assertAlmostEqual(detail['last'], self.now + 10, places=5)
        self.event(5, status='result')
        self.assertTrue(self.state['failures'])

    def test_latest_refs_closed_validation(self):
        valid = {'last_event_id': 'a' * 32, 'last_trace_id': 'b' * 32, 'last_span_id': 'c' * 32}
        self.assertEqual(safe_detail(valid), valid)
        for bad in ({'last_event_id': 'a' * 32}, {**valid, 'last_trace_id': 'bad'},
                    {**valid, 'last_span_id': None}, {**valid, 'last_other': 'x'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                safe_detail(bad)
