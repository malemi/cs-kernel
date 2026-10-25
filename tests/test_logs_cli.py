"""Read-only log entry point and strict diagnostic configuration checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cs import config, manifest
from cs.logs_cli import collect, remote_read


class LogsTests(unittest.TestCase):
    def test_actual_independent_reader_accepts_recent_boolean(self):
        import threading
        from types import SimpleNamespace
        from cs.logs_cli import reader_read

        engine_source = Path(__file__).resolve().parents[2]/'mrcall-desktop'/'engine'
        if not (engine_source/'zylch'/'observability_reader.py').exists():
            self.skipTest('Cross-repository reader source unavailable')
        with patch.object(sys, 'path', [str(engine_source), *sys.path]):
            from zylch.observability import EventStore
            from zylch.observability_reader import ReaderServer
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp)/'observability', 'owner')
            store.emit('rpc', 'failed', reason='auth')
            store.emit('rpc', 'result', reason='none')
            server = ReaderServer(('127.0.0.1', 0), store, 'x'*32)
            self.addCleanup(server.server_close)
            settings = SimpleNamespace(engine_owner_uid='owner', observability=SimpleNamespace(
                reader_url=f'http://127.0.0.1:{server.server_port}'))
            for recent, expected in ((True, 1), (False, 2)):
                thread = threading.Thread(target=server.handle_request, daemon=True)
                thread.start()
                with patch('cs.config.observability_credential', return_value='x'*32):
                    result = reader_read(settings, 'events', {'recent': recent, 'limit': 100})
                thread.join(3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(len(result['events']), expected)

    def test_actual_independent_reader_exports_retained_logging_health(self):
        import threading
        from types import SimpleNamespace
        from cs.logs_cli import reader_read

        engine_source = Path(__file__).resolve().parents[2]/'mrcall-desktop'/'engine'
        if not (engine_source/'zylch'/'observability_reader.py').exists():
            self.skipTest('Cross-repository reader source unavailable')
        with patch.object(sys, 'path', [str(engine_source), *sys.path]):
            from zylch.observability import EventStore
            from zylch.observability_reader import ReaderServer
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp)/'observability', 'owner')
            store.emit('rpc', 'result', reason='none')
            marker = store.root / '.logging-failed'
            marker.write_text('Legacy unknown loss')
            marker.chmod(0o600)
            server = ReaderServer(('127.0.0.1', 0), store, 'x'*32)
            self.addCleanup(server.server_close)
            settings = SimpleNamespace(engine_owner_uid='owner', observability=SimpleNamespace(
                reader_url=f'http://127.0.0.1:{server.server_port}'))
            for state in ('unknown', 'recovered'):
                if state == 'recovered':
                    store.emit('rpc', 'result', reason='none')
                for view, params in (('health', {}), ('locations', {}), ('events', {}), ('events', {'recent': True})):
                    thread = threading.Thread(target=server.handle_request, daemon=True)
                    thread.start()
                    with patch('cs.config.observability_credential', return_value='x'*32):
                        result = reader_read(settings, view, params)
                    thread.join(3)
                    self.assertFalse(thread.is_alive())
                    coverage = result if view == 'health' else result['coverage']
                    self.assertEqual(coverage['logging']['current_state'], state)
                    self.assertTrue(coverage['logging']['lost_events_unknown'])
                    self.assertIn('logging', [gap['reason'] for gap in coverage['gaps']])

    def test_actual_cli_locations_without_engine(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, 'HOME': home, 'CS_MANIFEST': '', 'CS_ENGINE_OWNER_UID': 'owner'}
            process = subprocess.run([sys.executable, '-m', 'cs', 'logs', 'locations', '--local', '--json'], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr)
            data = json.loads(process.stdout)
            self.assertEqual(data['local']['component'], 'kernel')
            self.assertEqual(data['local']['coverage']['status'], 'absent')
            self.assertFalse((Path(home)/'.cs/observability').exists())

    def test_secret_pasted_into_config_never_reaches_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'manifest.toml'
            for content in ('[observability]\nreader_token_env="CANARY-secret-value"', '[observability]\nreader_url="https://user:CANARY-secret-value@example.invalid"'):
                path.write_text(content)
                with self.assertRaises(manifest.ManifestError) as raised:
                    manifest.load_manifest(path)
                self.assertNotIn('CANARY-secret-value', str(raised.exception))

    def test_manifest_only_binding_and_remote_failure(self):
        with patch.dict(os.environ, {'OBSERVABILITY': '{"reader_url":"https://wrong.invalid"}'}, clear=False):
            settings = config.Settings(_env_file=None)
        self.assertFalse(settings.observability.reader_url)
        result = remote_read(settings, 'health', {})
        self.assertFalse(result['coverage']['available'])
        self.assertEqual(result['coverage']['status'], 'unsupported')

    def test_rpc_metadata_is_top_level_and_only_after_capability(self):
        import asyncio
        from cs.rpc import EngineClient
        from cs.observability import context
        async def exercise():
            settings = config.Settings(_env_file=None)
            client = EngineClient(settings)
            frames = []
            class Socket:
                async def send(self, raw):
                    frame = json.loads(raw)
                    frames.append(frame)
                    result = {'observability': 1} if frame['method'] == 'system.capabilities' else {'ok': True}
                    client._pending[frame['id']].set_result(result)
            client._ws = Socket()
            with context():
                await client.call('system.capabilities')
                result = await client.call('emails.search', {'query': 'private'})
            self.assertEqual(result, {'ok': True})
            self.assertNotIn('diagnostics', frames[0])
            self.assertEqual(frames[1]['diagnostics']['version'], 1)
            self.assertEqual(frames[1]['params'], {'query': 'private'})
            self.assertNotIn('owner_uid', frames[1]['diagnostics'])
        asyncio.run(exercise())

    def test_remote_wrong_profile_and_payload_are_rejected(self):
        from cs.logs_cli import _validate_remote
        settings = config.Settings(_env_file=None, engine_owner_uid='owner')
        with self.assertRaises(ValueError):
            _validate_remote(settings, 'health', {'schema_version':1, 'component':'engine', 'owner_uid':'foreign', 'status':'observed'})
        with self.assertRaises(ValueError):
            _validate_remote(settings, 'health', {'schema_version':1, 'component':'engine', 'owner_uid':'owner', 'body':'CANARY_SECRET'})

    def test_remote_nested_values_are_typed_before_export(self):
        import copy
        from cs.logs_cli import _validate_remote
        from cs.observability import EventStore
        settings = config.Settings(_env_file=None, engine_owner_uid='owner')
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp)/'engine', 'owner', component='engine')
            store.emit('rpc', 'result')
            valid = {'locations': store.locations(), 'events': store.events(), 'health': store.health()}
            for view, payload in valid.items():
                _validate_remote(settings, view, payload)
            attacks = [
                ('health', ('status',), {'body':'CANARY_SECRET'}),
                ('events', ('coverage','failed_writes'), {'token':'CANARY_SECRET'}),
                ('events', ('coverage','gaps'), [{'reason':'logging','count':'CANARY_SECRET'}]),
                ('locations', ('package_root',), {'body':'CANARY_SECRET'}),
                ('locations', ('process_start',), 'CANARY_SECRET'),
                ('health', ('newest_at',), float('nan')),
            ]
            for view, names, attack in attacks:
                payload = copy.deepcopy(valid[view])
                cursor = payload
                for key in names[:-1]:
                    cursor = cursor[key]
                cursor[names[-1]] = attack
                with self.subTest(view=view, names=names), self.assertRaises(ValueError):
                    _validate_remote(settings, view, payload)

    def test_logging_health_strict_validation_and_legacy_compatibility(self):
        import copy
        from cs.logs_cli import _validate_remote
        from cs.observability import EventStore
        from test_monitor_logging_health import logging_health

        settings = config.Settings(_env_file=None, engine_owner_uid='owner')
        with tempfile.TemporaryDirectory() as temp:
            store = EventStore(Path(temp)/'engine', 'owner', component='engine')
            store.emit('rpc', 'result')
            for view, base in (('health', store.health()), ('locations', store.locations()),
                               ('events', store.events()), ('events', store.recent())):
                _validate_remote(settings, view, copy.deepcopy(base))
                payload = copy.deepcopy(base)
                coverage = payload if view == 'health' else payload['coverage']
                coverage['logging'] = logging_health()
                _validate_remote(settings, view, payload)
                attacks = [
                    {'current_state': 'healthy'}, {'observed_failures': True},
                    {'observed_failures': -1}, {'lost_events_unknown': 'CANARY_SECRET'},
                    {'history_retained': False}, {'extra': 'CANARY_SECRET'},
                    {'recovery': None},
                    {'recovery': {**logging_health()['recovery'], 'timestamp': 'yesterday'}},
                    {'recovery': {**logging_health()['recovery'], 'event_id': 'CANARY_SECRET'}},
                    {'last_failure': {'timestamp': '2026-10-24T10:00:02+00:00', 'pid': 42,
                         'process_start': '123', 'error_class': 'OSError', 'error_code': 28,
                         'error_file': 'observability.py', 'error_line': 1}},
                ]
                for attack in attacks:
                    poisoned = copy.deepcopy(payload)
                    value = poisoned if view == 'health' else poisoned['coverage']
                    value['logging'].update(attack)
                    with self.subTest(view=view, attack=attack), self.assertRaises(ValueError):
                        _validate_remote(settings, view, poisoned)
                for key, unsafe in (('error_class', 'CANARY_SECRET'), ('error_class', {'secret': 'CANARY_SECRET'}), ('error_file', '/tmp/secret.py'),
                                    ('error_file', '../secret.py'), ('error_code', 'CANARY_SECRET'),
                                    ('error_line', True), ('message', 'CANARY_SECRET')):
                    poisoned = copy.deepcopy(payload)
                    value = poisoned if view == 'health' else poisoned['coverage']
                    value['logging']['last_failure'] = {
                        'timestamp': '2026-10-24T10:00:00+00:00', 'pid': 42, 'process_start': '123',
                        'error_class': 'OSError', 'error_code': 28, 'error_file': 'observability.py',
                        'error_line': 1, key: unsafe,
                    }
                    value['logging']['first_failure_at'] = '2026-10-24T10:00:00+00:00'
                    value['logging']['observed_failures'] = 1
                    with self.subTest(view=view, key=key), self.assertRaises(ValueError):
                        _validate_remote(settings, view, poisoned)

    def test_actual_global_account_attributes_only_selected_owner(self):
        from cs.observability import owner_root, EventStore
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);repo=base/'repo';repo.mkdir()
            manifest_path=repo/'manifest.toml'
            manifest_path.write_text('[company]\nslug="trial"\n[engine]\nowner_uid="uid-primary"\n')
            env={k:v for k,v in os.environ.items() if not k.startswith(('CS_','ENGINE_','EMAIL_','SHOPIFY_')) and k not in {'SLUG','ACCOUNTS'}}
            env.update(HOME=str(base),PYTHONPATH=str(Path.cwd()),CS_MANIFEST=str(manifest_path),CS_ACCOUNTS='primary:uid-primary,secondary:uid-secondary')
            for account_args in (['--account','secondary'],['--account=secondary']):
                process=subprocess.run([sys.executable,'-m','cs',*account_args,'config','--json'],cwd=repo,env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(process.returncode,0,process.stderr)
            state=base/'.trial-cs'
            selected=EventStore(owner_root(state,'uid-secondary'),'uid-secondary')
            events=selected.events()['events']
            self.assertEqual([e['status'] for e in events],['start','result','start','result'])
            self.assertTrue(all(e['owner_uid']=='uid-secondary' for e in events))
            self.assertFalse(owner_root(state,'uid-primary').exists())
