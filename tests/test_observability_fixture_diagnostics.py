"""Admission decisions retain safe evidence through real diagnostic consumers."""
import copy
import imaplib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from cs import operational_fixture as fixture, observability_causal as causal
from cs.observability import EventStore, context, store_for
from test_operational_fixture import SETTINGS, NOW, Provider, message, payload, record


class FixtureDiagnostics(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = EventStore(self.root / 'events', 'owner1')
        self.addCleanup(patch.stopall)
        patch('cs.observability_producers.store_for', return_value=self.store).start()

    def events(self):
        events = self.store.events(limit=200)['events']
        for event in events:
            self.assertIsNotNone(event.get('causal'))
            causal.validate(event['causal'])
        raw = json.dumps(events)
        for secret in ('peer@example.org', 'receiver@example.org', '<original@example.org>', 'INBOX', 'synthetic', 'private-error'):
            self.assertNotIn(secret, raw)
        return events

    def run_admission(self, inbound, provider=None, registry=None):
        with patch.object(fixture, '_read', return_value=payload() if registry is None else registry), patch.object(
            fixture.imaplib, 'IMAP4_SSL', return_value=provider or Provider()
        ) as connect, context(), causal.scope():
            discovery = []
            result = fixture.admit_originals(SETTINGS, inbound, {'peer@example.org'}, NOW, discovery)
        return result, discovery, connect

    def test_cardinality_and_provider_failure_controls(self):
        for rows, provider, expected in (([], Provider(), (0, 0, 0)),
                ([message(), message()], Provider(), (2, 0, 0)),
                ([message()], Provider(validity='124'), (1, 1, 0)),
                ([message()], Provider(), (1, 1, 1))):
            result, proof, connect = self.run_admission(rows, provider)
            event = self.events()[-1]
            facts = event['causal']['facts']
            self.assertEqual((facts['match_count'], facts['candidate_count'], facts['confirmed_count']), expected)
            self.assertEqual(len(proof), expected[-1])
            self.assertEqual(connect.call_count, int(expected[1] > 0))
            if expected[1]:
                self.assertEqual(connect.call_args.kwargs, {'timeout': 15})
            self.assertEqual(len(result[0]), expected[-1])

    def test_each_first_binding_predicate(self):
        fields = {'email': 'sender', 'message_id': 'message', 'subject': 'subject', 'thread_key': 'thread',
                  'provider_folder': 'folder', 'provider_uid': 'uid', 'provider_uidvalidity': 'uidvalidity'}
        for key, name in fields.items():
            self.run_admission([{**message(), key: 'private-error'}])
            failed = [e for e in self.events() if e['causal']['check'] == 'fixture_binding'][-1]
            self.assertEqual(failed['causal']['cause'], 'source_absent' if key == 'message_id' else 'binding_' + name)

    def test_unrelated_inbound_is_absence_and_same_identity_keeps_first_predicate(self):
        unrelated = {**message(), 'message_id': '<unrelated@example.org>', 'email': 'customer@example.org'}
        self.run_admission([unrelated])
        failed = [e for e in self.events() if e['causal']['check'] == 'fixture_binding'][-1]
        self.assertEqual(failed['causal']['cause'], 'source_absent')
        changed = {**message(), 'provider_uid': '999'}
        self.run_admission([unrelated, changed])
        failed = [e for e in self.events() if e['causal']['check'] == 'fixture_binding'][-1]
        self.assertEqual(failed['causal']['cause'], 'binding_uid')
        class LazyMessage:
            def get(self, key):
                if key != 'email':
                    raise AssertionError('Later predicates must remain unevaluated')
                return 'different@example.org'
        self.assertFalse(fixture._matches(LazyMessage(), record()))

    def test_registry_expired_invalid_and_actual_missing(self):
        expired = record(); expired['expires_at'] = NOW - 1
        self.run_admission([message()], registry=payload(expired))
        self.assertIn('registry_expired', [e['causal']['cause'] for e in self.events()])
        self.run_admission([message()], registry={})
        self.assertIn('registry_invalid', [e['causal']['cause'] for e in self.events()])
        with patch.object(fixture, 'REGISTRY_ROOT', Path('/missing-fixture-registry')):
            self.assertEqual(fixture.enrollments(SETTINGS, NOW), [])
        event = self.events()[-1]
        self.assertEqual(event['causal']['cause'], 'registry_absent')
        self.assertEqual((event['status'], event['level']), ('result', 'DEBUG'))
        self.assertNotEqual(event['causal']['outcome'], 'failed')

    def test_cleanup_does_not_replace_initiating_failure_and_sink_failure(self):
        provider = Provider()
        provider.select = lambda *a, **k: (_ for _ in ()).throw(TimeoutError('private-error'))
        provider.logout = lambda: (_ for _ in ()).throw(OSError('private-error'))
        self.run_admission([message()], provider)
        failed = [e for e in self.events() if e['causal']['cause'] == 'provider_exception']
        self.assertEqual([e['method'] for e in failed], ['fixture.select', 'fixture.logout'])
        self.assertEqual([e['error_class'] for e in failed], ['TimeoutError', 'OSError'])
        original = message()
        with patch('cs.observability_producers.emit', side_effect=RuntimeError('private-error')):
            result, proof, connect = self.run_admission([original])
        self.assertEqual(len(proof), 1)
        self.assertEqual(result[0], [original])
        self.assertEqual(connect.call_count, 1)

    def test_provider_rejections_and_exception_classes_preserve_calls(self):
        from cs.monitor_details import safe_detail
        from cs.observability import safe_metadata
        for exc in (imaplib.IMAP4.error('private-error'), imaplib.IMAP4.abort('private-error'),
                    imaplib.IMAP4.readonly('private-error'), TypeError('private-error'),
                    AttributeError('private-error'), LookupError('private-error')):
            provider = Provider()
            provider.select = lambda *a, **k: (_ for _ in ()).throw(exc)
            with patch.object(provider, 'login', wraps=provider.login) as login, patch.object(
                    provider, 'logout', wraps=provider.logout) as logout, patch.object(
                    provider, 'uid', wraps=provider.uid) as fetch:
                result, proof, connect = self.run_admission([message()], provider)
                self.assertEqual(result[0], [])
                self.assertEqual(proof, [])
                self.assertEqual((connect.call_count, login.call_count, fetch.call_count, logout.call_count), (1, 1, 0, 1))
            event = [e for e in self.events() if e['causal']['cause'] == 'provider_exception'][-1]
            expected = 'IMAP4.' + type(exc).__name__ if isinstance(exc, imaplib.IMAP4.error) else type(exc).__name__
            self.assertEqual(event['error_class'], expected)
            self.assertEqual(safe_metadata({'error_class': expected})['error_class'], expected)
            self.assertEqual(safe_detail({'error_class': expected})['error_class'], expected)
        for phase in ('login', 'select', 'fetch', 'mime'):
            provider = Provider()
            name = {'fetch': 'uid', 'mime': '_original_digest'}.get(phase, phase)
            target = fixture if phase == 'mime' else provider
            with patch.object(target, name, side_effect=TimeoutError('private-error')):
                result, proof, _ = self.run_admission([message()], provider)
            self.assertEqual(result[0], [])
            self.assertEqual(proof, [])
            event = [e for e in self.events() if e['causal']['cause'] == 'provider_exception'][-1]
            self.assertEqual(event['method'], 'fixture.' + phase)
        with patch.object(fixture.imaplib, 'IMAP4_SSL', side_effect=TimeoutError('private-error')):
            self.assertEqual(fixture._confirmed(SETTINGS, [record()]), [])
        self.assertEqual(self.events()[-1]['method'], 'fixture.connect')
        provider = Provider()
        with patch.object(provider, 'logout', side_effect=OSError('private-error')):
            result, proof, _ = self.run_admission([message()], provider)
        self.assertEqual(len(proof), 1)
        self.assertEqual(len(result[0]), 1)
        value = copy.deepcopy(self.events()[-1]['causal'])
        for invalid in ({**value, 'cause': 'private-error'}, {**value, 'facts': {'private-error': 1}},
                        {**value, 'method': 'fixture.private-error'}):
            with self.assertRaises(ValueError):
                causal.validate(invalid)

    def test_real_local_imap_selected_operation_timeout(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0)); listener.listen(1)
        stop = threading.Event()
        commands = []
        clients = []
        def serve():
            with listener.accept()[0] as conn:
                stream = conn.makefile('rwb', buffering=0)
                stream.write(b'* OK local peer\r\n')
                while line := stream.readline():
                    tag, command, *_ = line.split()
                    commands.append(command.decode())
                    if command == b'CAPABILITY':
                        stream.write(b'* CAPABILITY IMAP4rev1\r\n' + tag + b' OK capability\r\n')
                    elif command == b'LOGIN':
                        stream.write(tag + b' OK login\r\n')
                    elif command == b'EXAMINE':
                        stop.wait(2)
                        break
        thread = threading.Thread(target=serve, daemon=True); thread.start()
        def connect(host, port, timeout):
            self.assertEqual(timeout, 15)
            client = imaplib.IMAP4('127.0.0.1', listener.getsockname()[1], timeout=timeout)
            clients.append(client)
            client.sock.settimeout(0.08)
            return client
        try:
            with patch.object(fixture.imaplib, 'IMAP4_SSL', side_effect=connect):
                self.assertEqual(fixture._confirmed(SETTINGS, [record()]), [])
        finally:
            stop.set(); thread.join(3); listener.close()
            for client in clients:
                client.shutdown()
        self.assertFalse(thread.is_alive())
        self.assertEqual(commands, ['CAPABILITY', 'LOGIN', 'EXAMINE'])
        failed = [e for e in self.events() if e['causal']['cause'] == 'provider_exception']
        self.assertEqual(failed[0]['method'], 'fixture.select')
        self.assertEqual(failed[0]['error_class'], 'TimeoutError')
        self.assertGreaterEqual(failed[0]['causal']['facts']['elapsed_ms'], 70)

    def test_actual_cli_and_filesystem_collector_inbox_propagation(self):
        from cs.config import Settings
        from cs.monitor import scan
        from cs.monitor_config import Component, MonitorConfig
        with patch.dict(os.environ, {'HOME': str(self.root)}):
            settings = Settings(_env_file=None, slug='trial', engine_owner_uid='owner1')
            source = store_for(settings)
            with patch('cs.observability_producers.store_for', return_value=source):
                self.run_admission([message()], Provider(validity='124'))
            env = {k: v for k, v in os.environ.items() if not k.startswith(('CS_', 'ENGINE_', 'EMAIL_'))}
            manifest = self.root / 'manifest.toml'
            manifest.write_text('[company]\nslug="trial"\n[engine]\nowner_uid="owner1"\n')
            env.update(HOME=str(self.root), CS_MANIFEST=str(manifest), CS_ENGINE_OWNER_UID='owner1')
            process = subprocess.run([sys.executable, '-m', 'cs', 'logs', 'events', '--local', '--json', '--limit', '100'],
                                     env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr)
            local = json.loads(process.stdout)['local']['events']
            rejected = next(e for e in local if e['causal']['cause'] == 'provider_rejected')
            config = MonitorConfig(monitor_id='a' * 32, owner_uid='owner1', state_dir=str(self.root / 'monitor'),
                                   expected_start_utc=int(time.time()), mode='filesystem', components=[
                                       Component(id='operator', kind='kernel', local_root=str(source.root))])
            scan(config)
            problems = json.loads((Path(config.state_dir) / 'problems.json').read_text())['problems']
            self.assertTrue(any(p['evidence'].get('causal') == rejected['causal'] for p in problems), problems)
            raw = json.dumps(problems)
            self.assertNotIn('peer@example.org', raw)
            self.assertNotIn('INBOX', raw)


if __name__ == '__main__':
    unittest.main()
