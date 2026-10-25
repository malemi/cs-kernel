"""Severity filtering and legacy evidence through ordinary diagnostic paths."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cs import config, manifest
from cs.logs_cli import _validate_remote
from cs.observability import EventStore, LEVELS, event_level, owner_root, store_for


class SeverityTests(unittest.TestCase):
    def test_all_levels_threshold_and_meaningful_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp) / 'events', 'owner')
            start = store.emit('rpc', 'start', reason='none', method='emails.search')
            self.assertEqual(start['level'], 'DEBUG')
            self.assertEqual(start['method'], 'emails.search')
            for level in LEVELS:
                store.emit('rpc', 'result', reason='none', level=level)
            events = store.events()['events']
            self.assertEqual([e['level'] for e in events], ['DEBUG', *LEVELS])
            filtered = EventStore(Path(temp) / 'filtered', 'owner', log_level='WARNING')
            for level in LEVELS:
                filtered.emit('rpc', 'result', reason='none', level=level)
            self.assertEqual([e['level'] for e in filtered.events()['events']], ['WARNING', 'ERROR', 'CRITICAL'])
            self.assertEqual(filtered.failed_writes, 0)
            self.assertEqual(filtered.dropped_events, 0)
            self.assertEqual(filtered.locations()['log_level'], 'WARNING')

    def test_filtering_is_not_a_logging_failure_or_an_outcome_change(self):
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp) / 'events', 'owner', log_level='ERROR')
            self.assertIsNone(store.emit('cli', 'start', reason='none'))
            self.assertFalse(store.root.exists())
            event = store.emit('authority', 'held', reason='policy-hold', level='ERROR')
            self.assertEqual(event['status'], 'held')
            self.assertEqual(event['reason'], 'policy-hold')
            self.assertEqual(store.failed_writes, 0)

    def test_legacy_levels_are_inferred_without_rewriting_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp) / 'events', 'owner')
            expected = [('start', 'DEBUG'), ('result', 'INFO'), ('held', 'WARNING'), ('failed', 'ERROR')]
            originals = []
            for status, level in expected:
                event = store.emit('rpc', status)
                self.assertEqual(event['level'], level)
                originals.append({key: value for key, value in event.items() if key != 'level'})
            path = next(store.root.glob('events-*'))
            path.write_text(''.join(json.dumps(event) + '\n' for event in originals))
            before = path.read_bytes()
            page = store.events()
            self.assertEqual([e['level'] for e in page['events']], [level for _, level in expected])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([e['level'] for e in store.recent()['events']], ['ERROR', 'WARNING'])

    def test_generic_status_error_is_recent_and_remote_validation_is_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp) / 'events', 'owner', component='engine')
            event = store.emit('rpc', 'result', reason='none', level='ERROR', password='CANARY_SECRET')
            self.assertEqual(store.recent()['events'][0]['event_id'], event['event_id'])
            settings = config.Settings(_env_file=None, engine_owner_uid='owner')
            page = store.events()
            self.assertEqual(_validate_remote(settings, 'events', page)['events'][0]['level'], 'ERROR')
            legacy = copy.deepcopy(page)
            legacy['events'][0].pop('level')
            self.assertEqual(_validate_remote(settings, 'events', legacy)['events'][0]['level'], 'INFO')
            bad = copy.deepcopy(page)
            bad['events'][0]['level'] = {'secret': 'CANARY_SECRET'}
            with self.assertRaises(ValueError):
                _validate_remote(settings, 'events', bad)
            self.assertNotIn('CANARY_SECRET', json.dumps(page))

    def test_manifest_threshold_is_validated_and_used_by_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'manifest.toml'
            path.write_text('[observability]\nlog_level="ERROR"\n')
            with patch.dict(os.environ, {'HOME': temp, 'CS_MANIFEST': str(path)}):
                settings = config.load()
                self.assertEqual(store_for(settings).log_level, 'ERROR')
            for value in ('debug', 'CANARY_SECRET'):
                path.write_text('[observability]\nlog_level="' + value + '"\n')
                with self.assertRaises(manifest.ManifestError) as raised:
                    manifest.load_manifest(path)
                self.assertNotIn(value, str(raised.exception))
            with self.assertRaises(ValueError):
                EventStore(Path(temp) / 'bad', 'owner', log_level='debug')
            with self.assertRaises(ValueError):
                event_level({'level': ['ERROR']})

    def test_actual_cli_produces_debug_and_error_without_special_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            path = base / 'manifest.toml'
            path.write_text('[company]\nslug="trial"\n[engine]\nowner_uid="owner"\n')
            env = {key: value for key, value in os.environ.items() if not key.startswith(('CS_', 'ENGINE_', 'EMAIL_', 'SHOPIFY_')) and key not in {'SLUG', 'ACCOUNTS'}}
            env.update(HOME=temp, CS_MANIFEST=str(path), PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            good = subprocess.run([sys.executable, '-m', 'cs', 'config', '--json'], cwd=temp, env=env, capture_output=True, text=True, timeout=10)
            bad = subprocess.run([sys.executable, '-m', 'cs', 'not-a-command'], cwd=temp, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(bad.returncode, 2, bad.stderr)
            store = EventStore(owner_root(base / '.trial-cs', 'owner'), 'owner')
            events = store.events()['events']
            self.assertEqual([e['level'] for e in events], ['DEBUG', 'INFO', 'DEBUG', 'ERROR'])
            self.assertEqual(events[0]['command'], 'config')
            self.assertEqual(events[-1]['status'], 'failed')
            self.assertEqual(events[-1]['exit_code'], 2)


if __name__ == '__main__':
    unittest.main()
