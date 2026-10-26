"""Provider diagnostics retain exact safe failure evidence through ordinary access."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs.logs_cli import _validate_remote
from cs.monitor_details import safe_detail
from cs.observability import EventStore, context, owner_root, safe_metadata
from cs.observability_provider import validate


def snapshot(**changes):
    value = {
        'version': 1, 'connection_id': 'a' * 32, 'generation': 1,
        'sequence': 5, 'operation_id': 2, 'operation': 'examine', 'phase': 'failed',
        'command': 'EXAMINE', 'socket_state': 'open', 'imap_state': 'AUTH',
        'tls_state': 'established', 'pin_match': True, 'deadline_match': True,
        'inbound_progress_count': 1, 'last_inbound_progress_offset_ms': 12.5,
        'pending_tags': 1, 'pending_commands': 1, 'offset_ms': 60,
        'duration_ms': 50.5, 'remaining_ms': 0, 'socket_timeout_ms': 50,
        'cause': 'deadline', 'overflow': False,
    }
    return {**value, **changes}


class ProviderContract(unittest.TestCase):
    def test_strict_closed_shape_rejects_unsafe_inputs_without_echo(self):
        original = snapshot()
        for key in original:
            missing = dict(original)
            del missing[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate(missing)
        invalid = [None, [], {**original, 'password': 'SECRET_SENTINEL'},
                   snapshot(connection_id='SECRET_SENTINEL'), snapshot(command='LOGIN SECRET_SENTINEL'),
                   snapshot(cause='SECRET_SENTINEL'), snapshot(operation='SECRET_SENTINEL' * 500)]
        for key in ('version', 'sequence', 'generation', 'operation_id', 'inbound_progress_count', 'pending_tags', 'pending_commands'):
            invalid.extend({**original, key: item} for item in (True, 1.5, -1, 2**53))
        for key in ('offset_ms', 'duration_ms', 'remaining_ms', 'socket_timeout_ms', 'last_inbound_progress_offset_ms'):
            invalid.extend({**original, key: item} for item in (True, float('nan'), float('inf'), -1, 3600001, 10**500))
        invalid.extend(snapshot(**{key: 1}) for key in ('pin_match', 'deadline_match', 'overflow'))
        for value in invalid:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError) as caught:
                validate(value)
            self.assertNotIn('SECRET_SENTINEL', str(caught.exception))
        for key in ('operation', 'phase', 'command', 'socket_state', 'imap_state', 'tls_state', 'cause'):
            for item in (None, [], 'SECRET_SENTINEL'):
                if key == 'command' and item is None:
                    continue
                with self.subTest(key=key, item=repr(item)), self.assertRaises(ValueError):
                    validate({**original, key: item})
        self.assertEqual(validate(original), original)
        self.assertIsNot(validate(original), original)

    def test_null_unknown_and_numeric_bounds_are_preserved_without_coercion(self):
        value = snapshot(connection_id=None, generation=None, operation_id=None, command=None,
                         pin_match=None, deadline_match=None, inbound_progress_count=None,
                         last_inbound_progress_offset_ms=None, pending_tags=None,
                         pending_commands=None, duration_ms=None, remaining_ms=None,
                         socket_timeout_ms=None, socket_state='unknown', imap_state='UNKNOWN',
                         tls_state='unknown', cause='unknown')
        self.assertEqual(validate(value), value)
        for key in ('sequence', 'generation', 'operation_id', 'inbound_progress_count'):
            self.assertEqual(validate(snapshot(**{key: 2147483647}))[key], 2147483647)
        for key in ('pending_tags', 'pending_commands'):
            self.assertEqual(validate(snapshot(**{key: 65535}))[key], 65535)
        self.assertEqual(validate(snapshot(offset_ms=3600000))['offset_ms'], 3600000)
        self.assertEqual(safe_metadata({'elapsed_ms': 1}), {'elapsed_ms': 1})
        self.assertEqual(safe_detail({'provider_diagnostic': value}), {'provider_diagnostic': value})

    def test_remote_validation_rejects_malformed_persisted_object(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / 'events', 'operator', 'engine')
            self.assertIsNotNone(store.emit('provider', 'failed', reason='timeout', provider_diagnostic=snapshot()))
            page = store.events()
            selected = SimpleNamespace(engine_owner_uid='operator')
            self.assertEqual(_validate_remote(selected, 'events', page), page)
            bad = copy.deepcopy(page)
            bad['events'][0]['provider_diagnostic']['remaining_ms'] = 'SECRET_SENTINEL'
            with self.assertRaises(ValueError):
                _validate_remote(selected, 'events', bad)
            segment = next(store.root.glob('events-*.jsonl'))
            segment.write_text(json.dumps(bad['events'][0]) + '\n')
            reread = store.events()
            self.assertEqual(reread['events'], [])
            self.assertIn('malformed-event', {gap['reason'] for gap in reread['coverage']['gaps']})

    def test_actual_emitter_cli_collector_and_private_inbox_preserve_first_fault(self):
        from cs.monitor_config import MonitorConfig, Component
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.toml'
            manifest.write_text('[company]\nslug="provider"\n[engine]\nowner_uid="operator"\n')
            env = {**os.environ, 'HOME': directory, 'CS_MANIFEST': str(manifest),
                   'CS_ENGINE_OWNER_UID': 'operator', 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
            with patch.dict(os.environ, env):
                from cs import config
                selected = config.load()
                store = EventStore(owner_root(selected.state_dir, 'operator'), 'operator', 'engine', state_dir=selected.state_dir)
                first = snapshot()
                with context() as active:
                    emitted = store.emit('provider', 'failed', reason='timeout', method='tasks.assignment.project', provider_diagnostic=first)
                    self.assertIsNotNone(emitted)
                    store.emit('cleanup', 'failed', reason='timeout', method='tasks.assignment.project', provider_diagnostic=snapshot(operation='dispose', sequence=6, cause='cleanup', socket_state='closed'))
                    store.emit('acquisition', 'failed', reason='timeout', method='assignment.projection.terminal', provider_diagnostic=first)
                first['operation'] = 'unknown'
                trace = subprocess.run([sys.executable, '-m', 'cs', 'logs', 'trace', '--trace-id', active['trace_id'], '--local', '--json'], capture_output=True, text=True, env=env)
                self.assertEqual(trace.returncode, 0, trace.stderr)
                observed = json.loads(trace.stdout)['local']['events']
                retained = [event['provider_diagnostic'] for event in observed if event.get('provider_diagnostic', {}).get('operation') == 'examine']
                self.assertEqual(len(retained), 2)
                self.assertEqual(retained[0], snapshot())
                cfg = MonitorConfig(mode='filesystem', clone_label='provider', scan_seconds=600,
                    monitor_id='b' * 32, owner_uid='operator', state_dir=str(root / 'monitor'), expected_start_utc=int(time.time()),
                    components=[Component(id='engine', kind='engine', local_root=str(store.root))])
                cfgpath = root / 'monitor.json'
                cfgpath.write_text(cfg.model_dump_json())
                cfgpath.chmod(0o600)
                result = subprocess.run([sys.executable, '-m', 'cs', 'monitor', 'once', '--config', str(cfgpath)], capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode, 1, result.stderr)
                inboxpath = root / 'monitor/problems.json'
                inbox = json.loads(inboxpath.read_text())
                details = [row['evidence']['provider_diagnostic'] for row in inbox['problems'] if 'provider_diagnostic' in row['evidence']]
                self.assertEqual(details.count(snapshot()), 2)
                self.assertTrue(any(item['cause'] == 'cleanup' for item in details))
                self.assertEqual(inboxpath.stat().st_mode & 0o777, 0o600)
                if destination := os.environ.get('PROVIDER_DIAGNOSTIC_CORPUS'):
                    target = Path(destination)
                    target.mkdir(parents=True, exist_ok=True, mode=0o700)
                    for name, raw in (('ordinary-trace.json', trace.stdout), ('ordinary-inbox.json', inboxpath.read_text())):
                        output = target / name
                        output.write_text(raw)
                        output.chmod(0o600)
                for sentinel in ('SECRET_SENTINEL', 'password', '<mail@example.test>'):
                    self.assertNotIn(sentinel, trace.stdout + inboxpath.read_text())


if __name__ == '__main__':
    unittest.main()
