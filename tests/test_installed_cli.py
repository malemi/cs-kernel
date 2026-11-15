"""Installed CLI child-process argument and uncertainty contracts with synthetic transport."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = '<root@example.test>'
DRAFT_ID = '452ddb83-69c9-479c-98ab-b6f690eab2a7'


class InstalledCLI(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.journal = self.home / 'synthetic-operation.json'
        self.environment = {'PATH': '/usr/bin:/bin', 'HOME': str(self.home),
            'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': os.environ.get('CLI_TEST_HELPERS', str(HERE))}

    def command(self, mode, arguments, expected):
        previous_count = len(json.loads(self.journal.read_text())['calls']) if self.journal.exists() else 0
        result = subprocess.run([sys.executable, str(HERE / 'installed_cli_adapter.py'), mode, str(self.journal), *arguments],
                                cwd=self.home, env=self.environment, capture_output=True, text=True, timeout=20)
        self.assertIn(result.returncode, (0, 3), result.stderr)
        value = json.loads(result.stdout)
        state = json.loads(self.journal.read_text())
        self.assertTrue(state['package_root'].startswith(str(Path(sys.prefix) / 'lib')))
        self.assertEqual(state['calls'][previous_count:], expected)
        self.assertEqual(state['generation'], 0)
        self.assertFalse(any(call['method'].startswith('chat.') for call in state['calls']))
        return result.returncode, value, state

    def test_resume_publication_keeps_exact_operation_after_uncertainty(self):
        arguments = ['draft-reply', '--resume-draft', DRAFT_ID, '--thread-id', ROOT,
                     '--operation-id', 'resume-fixture', '--json']
        for attempt in range(2):
            expected = [
                {'method': 'system.capabilities', 'params': {}, 'scripted_reply': 'capabilities'},
                {'method': 'drafts.inspect', 'params': {'draft_id': DRAFT_ID}, 'scripted_reply': 'draft-inspection'},
                {'method': 'drafts.inspect', 'params': {'draft_id': DRAFT_ID}, 'scripted_reply': 'draft-inspection'},
                {'method': 'drafts.publish_review', 'params': {'draft_id': DRAFT_ID, 'expected_snapshot': 'a' * 64,
                    'thread_id': ROOT, 'operation_id': 'resume-fixture'},
                 'scripted_reply': 'dispatch-timeout' if attempt == 0 else 'publication-unknown'}]
            code, value, state = self.command('resume', arguments, expected)
            self.assertEqual(value['state'], 'publication-failed')
            self.assertEqual(value['cause'], 'publication-or-generation-incomplete' if attempt == 0 else 'publication_outcome_unresolved')
            self.assertEqual(code, 3)
            self.assertEqual(value['draft_id'], DRAFT_ID)
            self.assertEqual(value['operation_id'], 'resume-fixture')
            self.assertEqual(value['effect_certainty'], 'unknown')
            self.assertEqual(value['next_action'], 'inspect-operation')
            self.assertEqual(state['dispatches'], 1)
        self.assertEqual(sum(call['method'] == 'drafts.publish_review' for call in state['calls']), 2)

    def test_retire_preview_bindings_survive_uncertain_commit(self):
        arguments = ['draft-retire', DRAFT_ID, '--gmail-uid', '17', '--uidvalidity', '9',
                     '--sent-mirror', '--thread-id', ROOT, '--operation-id', 'retire-fixture']
        expected_preview = [
            {'method': 'system.capabilities', 'params': {}, 'scripted_reply': 'capabilities'},
            {'method': 'drafts.inspect', 'params': {'draft_id': DRAFT_ID}, 'scripted_reply': 'draft-inspection'},
            {'method': 'drafts.retire_sent_mirror', 'params': {'draft_id': DRAFT_ID, 'expected_snapshot': 'a' * 64,
                'thread_id': ROOT, 'operation_id': 'retire-fixture', 'target': {'uid': '17', 'uidvalidity': '9'},
                'commit': False}, 'scripted_reply': 'retirement-preview'}]
        code, preview, state = self.command('retire', arguments, expected_preview)
        self.assertEqual(preview['cause'], 'preview')
        self.assertEqual(preview['expected_snapshot'], 'a' * 64)
        self.assertEqual(preview['target'], {'folder': 'Drafts', 'uid': '17', 'uidvalidity': '9', 'raw_fingerprint': 'b' * 64})
        self.assertEqual(code, 0)
        self.assertTrue(preview['dry_run'])
        self.assertEqual(state['dispatches'], 0)
        commit = arguments + ['--commit', '--gmail-folder', preview['target']['folder'],
            '--gmail-fingerprint', preview['target']['raw_fingerprint'], '--engine-snapshot', preview['expected_snapshot']]
        for attempt in range(2):
            expected_commit = [
                {'method': 'system.capabilities', 'params': {}, 'scripted_reply': 'capabilities'},
                {'method': 'drafts.inspect', 'params': {'draft_id': DRAFT_ID}, 'scripted_reply': 'draft-inspection'},
                {'method': 'drafts.retire_sent_mirror', 'params': {'draft_id': DRAFT_ID, 'expected_snapshot': 'a' * 64,
                    'thread_id': ROOT, 'operation_id': 'retire-fixture', 'target': {'folder': 'Drafts', 'uid': '17',
                    'uidvalidity': '9', 'raw_fingerprint': 'b' * 64}, 'commit': True},
                 'scripted_reply': 'dispatch-timeout' if attempt == 0 else 'retirement-unknown'}]
            code, value, state = self.command('retire', commit, expected_commit)
            self.assertEqual(value['cause'], 'sent_mirror_recovery_unavailable' if attempt == 0 else 'retirement_unconfirmed')
            self.assertNotIn('state', value)
            if attempt == 1:
                self.assertEqual(value, {'version': 1, 'ok': False, 'draft_id': DRAFT_ID,
                    'operation_id': 'retire-fixture', 'owner_uid': 'fixture-owner',
                    'owner_id': 'support@fixture.example', 'root': ROOT, 'expected_snapshot': 'a' * 64,
                    'effect_certainty': 'unknown', 'achieved_stages': ['engine-saved'],
                    'next_action': 'inspect-operation', 'cause': 'retirement_unconfirmed', 'engine_discarded': False})
            self.assertEqual(code, 3)
            self.assertEqual(value['operation_id'], 'retire-fixture')
            self.assertEqual(value['effect_certainty'], 'unknown')
            self.assertEqual(state['dispatches'], 1)
            self.assertFalse(value['engine_discarded'])
        self.assertFalse(any(call['method'] == 'drafts.discard_exact' for call in state['calls']))

    def test_operator_send_failure_preserves_operation_and_no_generation(self):
        arguments = ['draft-send', DRAFT_ID, '--operator-request', '--operation-id', 'send-fixture', '--json']
        for attempt in range(2):
            expected_send = [
                {'method': 'system.capabilities', 'params': {}, 'scripted_reply': 'capabilities'},
                {'method': 'drafts.operation_status', 'params': {'operation_id': 'send-fixture'},
                 'scripted_reply': 'operation-absent' if attempt == 0 else 'operation-active'},
                {'method': 'drafts.operator_send_inspect', 'params': {'draft_id': DRAFT_ID}, 'scripted_reply': 'operator-inspection'}]
            if attempt == 0:
                expected_send.append({'method': 'tasks.assignment.project', 'params': {'thread_key': ROOT}, 'scripted_reply': 'normal-assignment'})
            expected_send.append({'method': 'drafts.send_operator', 'params': {'draft_id': DRAFT_ID,
                'expected_snapshot': 'a' * 64, 'operation_id': 'send-fixture', 'binding': {'root': ROOT,
                'target': '<latest@example.test>', 'recipients': ['customer@example.test'], 'cc': []},
                'version': 1, 'reason': 'explicit_operator_request'},
                'scripted_reply': 'dispatch-timeout' if attempt == 0 else 'send-unknown'})
            code, value, state = self.command('send', arguments, expected_send)
            self.assertEqual(value['state'], 'delivery-unknown')
            self.assertEqual(value['cause'], 'exact_send_unavailable' if attempt == 0 else 'exact_send_unconfirmed')
            self.assertEqual(code, 3)
            self.assertEqual(value['draft_id'], DRAFT_ID)
            self.assertEqual(value['operation_id'], 'send-fixture')
            self.assertEqual(value['effect_certainty'], 'unknown')
            self.assertEqual(value['next_action'], 'inspect-operation')
            self.assertEqual(state['dispatches'], 1)
        self.assertEqual(sum(call['method'] == 'drafts.send_operator' for call in state['calls']), 2)


if __name__ == '__main__':
    unittest.main()
