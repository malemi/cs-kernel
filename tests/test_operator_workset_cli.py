"""Scheduled workset composition and refusals before expensive mail work."""
import argparse
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cs import cli, assignment_cli, task_assignment
from cs.config import Settings
from cs.operator_health import identity
from cs.operator_workset import observe, reserve
try:
    from .assignment_fixture import normal_projection
except ImportError:
    from assignment_fixture import normal_projection


class CliWorksetTests(unittest.TestCase):
    def typed_review(self, *, hold=False):
        from cs.draft_state import inventory_proof
        row = {'draft_id':'draft-a','mailbox_id':'box','thread_key':'<a@example.test>',
               'to':'a@example.test','verdict':'ready',
               'workset_hold_reasons':['mailbox_unreadable'] if hold else []}
        raw=[{'id':'draft-a','mailbox_id':'box'}]
        return {'drafts':[row],'mailbox_drafts':raw,'drafts_inventory':inventory_proof(raw,[row]),
                'drafts_notes':['A deliberately skipped mailbox remains reported.']}

    def test_typed_complete_review_preserves_policy_notes_and_allows_unrelated_work(self):
        payload = self.typed_review(hold=True)
        out = io.StringIO()
        with patch('cs.review.gather', return_value=payload), contextlib.redirect_stdout(out):
            self.assertEqual(cli.cmd_review(argparse.Namespace(json=True)), 0)
        self.assertEqual(json.loads(out.getvalue()), payload)
        observe(self.settings, 'tasks', [
            {'id': 'task-a', 'thread_key': '<a@example.test>', 'status': 'open'},
            {'id': 'task-c', 'thread_key': '<c@example.test>', 'status': 'open'}])
        discovery = copy.deepcopy(self.discovery)
        discovery['open'].append({'thread_key': '<b@example.test>', 'email': 'b@example.test',
                                 '_workset_revision': 'b' * 64})
        result = reserve(self.settings, discovery)
        self.assertEqual({r['thread_key'] for r in result['selected']},
                         {'<b@example.test>', '<c@example.test>'})
        self.assertTrue(any(r['thread_key'] == '<a@example.test>' and
                            r['reason'] == 'review_evidence_incomplete' for r in result['held']))

    def test_typed_inventory_cannot_hide_missing_reads_or_changed_identities(self):
        from cs.operator_workset import WorksetError
        for fault in ('proof', 'foreign-id', 'read-error', 'missing-fetch', 'unknown-hold'):
            payload = self.typed_review()
            if fault == 'proof':payload['drafts_inventory']['mailbox_count'] = 99
            if fault == 'foreign-id':payload['drafts'][0]['draft_id'] = 'foreign'
            if fault == 'read-error':payload['drafts_error'] = 'unavailable'
            if fault == 'missing-fetch':payload['mailbox_drafts'] = []
            if fault == 'unknown-hold':payload['drafts'][0]['workset_hold_reasons'] = ['UNKNOWN_PRIVATE_SENTINEL']
            with self.subTest(fault=fault), self.assertRaises(WorksetError):
                observe(self.settings, 'review', payload)

    def test_missing_root_hold_blocks_supported_recipient_representations(self):
        from cs.draft_state import inventory_proof
        for index, (field, value) in enumerate([('to_addresses', ['A Person <a@example.test>']),
                             ('to_display', 'A Person <a@example.test>'),
                             ('to', 'A Person <a@example.test>')], 1):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                context = {**self.context, 'directory': directory, 'nonce': str(index) * 32}
                with patch.dict(os.environ, {'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(context)}):
                    payload = self.typed_review()
                    payload['drafts'][0].update(thread_key=None, workset_hold_reasons=['root_missing'])
                    payload['drafts_inventory'] = inventory_proof(payload['mailbox_drafts'],payload['drafts'])
                    observe(self.settings, 'review', payload)
                    observe(self.settings, 'tasks', [
                        {'thread_key': '<new@example.test>', field: value},
                        {'thread_key': '<safe@example.test>', 'to_addresses': ['safe@example.test']}])
                    discovery = copy.deepcopy(self.discovery)
                    discovery['open'] = []
                    selected = reserve(self.settings, discovery)['selected']
                    self.assertEqual([row['thread_key'] for row in selected], ['<safe@example.test>'])

    def test_actual_reconciliation_missing_root_holds_all_to_and_cc_recipients(self):
        from cs import draft_state
        raw = [{'id': 'multiple', 'mailbox_id':'box', 'to_addresses': ['a@example.test', 'z@example.test'],
                'cc_addresses': ['cc@example.test'], 'body': 'Short reply',
                'created_at': '2026-10-18T00:00:00Z'}]
        rows, notes = draft_state.reconcile(self.settings, raw,
            inbound=lambda *a, **kw: [], sent=lambda *a, **kw: [],
            settled=lambda *a: ({}, None), delivered=lambda *a: (None, None))
        self.assertIn('root_missing', rows[0]['workset_hold_reasons'])
        self.assertEqual(set(rows[0]['recipients']), {'a@example.test', 'z@example.test'})
        self.assertEqual(set(rows[0]['cc_recipients']), {'cc@example.test'})
        payload = self.typed_review()
        payload.update(mailbox_drafts=raw, drafts=rows, drafts_notes=notes)
        payload['drafts_inventory'] = draft_state.inventory_proof(raw, rows)
        self.assertIs(payload['drafts_inventory']['complete'], True)
        observe(self.settings, 'review', payload)
        observe(self.settings, 'tasks', [
            {'thread_key': '<second@example.test>', 'contact_email': 'z@example.test'},
            {'thread_key': '<cc@example.test>', 'to_addresses': ['CC Person <cc@example.test>']},
            {'thread_key': '<safe@example.test>', 'to_addresses': ['safe@example.test']}])
        discovery = copy.deepcopy(self.discovery)
        discovery['open'] = []
        self.assertEqual([r['thread_key'] for r in reserve(self.settings, discovery)['selected']],
                         ['<safe@example.test>'])

    def test_observation_rejection_is_symbolic_and_stderr_only(self):
        sentinel = 'PRIVATE_CUSTOMER_AND_CREDENTIAL_SENTINEL'
        for payload, reason, key in [
                ({'drafts': [], 'drafts_notes': [sentinel]}, 'source_marked_incomplete', 'drafts_notes'),
                ({'drafts': [], 'drafts_error': sentinel}, 'review_inventory_incomplete', 'drafts_error'),
                ({'drafts': 'invalid'}, 'source_shape_invalid', None),
                ({'drafts': [], 'total': 1}, 'source_total_mismatch', None)]:
            with self.subTest(reason=reason, key=key):
                failure = self.directory / 'workset-review-failure.json'
                failure.unlink(missing_ok=True)
                out, err = io.StringIO(), io.StringIO()
                with patch('cs.review.gather', return_value=payload), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(cli.cmd_review(argparse.Namespace(json=True)), 3)
                self.assertEqual(json.loads(out.getvalue()), payload)
                diagnostic = json.loads(err.getvalue().splitlines()[0])
                self.assertEqual((diagnostic['reason'], diagnostic['key']), (reason, key))
                self.assertNotIn(sentinel, err.getvalue())
                self.assertEqual(json.loads(failure.read_text()), diagnostic)
                self.assertFalse((self.directory / 'workset-review.json').exists())

    def test_observation_write_failure_retains_safe_reason(self):
        with patch('cs.operator_workset._write_new', side_effect=OSError('PRIVATE_SENTINEL')), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertFalse(cli._observe_scheduled_workset(self.settings, 'review', {'drafts': []}))
        diagnostic = json.loads(err.getvalue().splitlines()[0])
        self.assertEqual(diagnostic['reason'], 'observation_write_failed')
        self.assertNotIn('PRIVATE_SENTINEL', err.getvalue())

    def test_changed_observation_and_foreign_context_keep_refusing(self):
        observe(self.settings, 'review', {'drafts': []})
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertFalse(cli._observe_scheduled_workset(self.settings, 'review', {'drafts': [{'id': 'changed'}]}))
        self.assertEqual(json.loads(err.getvalue().splitlines()[0])['reason'], 'observation_changed')
        context = {**self.context, 'owner_uid': 'FOREIGN_PRIVATE_SENTINEL'}
        with patch.dict(os.environ, {'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(context)}), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertFalse(cli._observe_scheduled_workset(self.settings, 'review', {'drafts': []}))
        self.assertEqual(json.loads(err.getvalue().splitlines()[0])['reason'], 'context_invalid')
        self.assertNotIn('FOREIGN_PRIVATE_SENTINEL', err.getvalue())

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.directory = self.home / 'run'
        self.directory.mkdir(mode=0o700)
        self.context = {'directory': str(self.directory), 'nonce': 'a' * 32,
                        'supervisor': identity(os.getpid())[0], 'workset_enabled': True, 'owner_uid': 'owner'}
        self.environment = patch.dict(os.environ, {'HOME': str(self.home),
            'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(self.context)})
        self.environment.start()
        self.settings = Settings(_env_file=None, slug='workset', engine_owner_uid='owner')
        self.configuration = patch.object(cli.config, 'load', return_value=self.settings)
        self.configuration.start()
        self.discovery = {'open': [{'thread_key': '<a@example.test>', 'email': 'a@example.test',
            '_workset_revision': 'a' * 64, 'last_inbound_date': '2026-10-18T12:00:00Z'}],
            'resumed': [], 'handled': [], 'human_work': [], 'assignment_audit': [], 'escalated': [],
            'read_incomplete': None, 'assignment_incomplete': False}

    def tearDown(self):
        self.configuration.stop()
        self.environment.stop()
        self.temporary.cleanup()

    def prepare(self):
        observe(self.settings, 'tasks', [])
        observe(self.settings, 'review', {'drafts': []})
        return reserve(self.settings, self.discovery)

    def test_unselected_deep_reads_and_effects_never_reach_upstream(self):
        self.prepare()
        args = argparse.Namespace(email='other@example.test', json=True, full=False,
                                  thread_id='<other@example.test>')
        with contextlib.redirect_stderr(io.StringIO()), patch.object(
                cli.rpc, 'call_sync', side_effect=AssertionError('upstream forbidden')), patch.object(
                cli.rpc, 'chat', side_effect=AssertionError('model forbidden')), patch.object(
                task_assignment, 'project', side_effect=AssertionError('projection forbidden')):
            for command in (cli.cmd_thread, cli.cmd_dossier, cli.cmd_history,
                            cli.cmd_contacted, cli.cmd_draft_reply, cli.cmd_chat):
                self.assertEqual(command(args), 3)
            self.assertEqual(cli.cmd_rpc(argparse.Namespace(
                method='emails.list_by_thread', params=json.dumps({'thread_id': args.thread_id}), timeout=30)), 3)
            self.assertEqual(cli.cmd_rpc(argparse.Namespace(
                method='emails.search', params='{}', timeout=30)), 3)
            for method in ('drafts.create', 'drafts.update', 'chat.send'):
                self.assertEqual(cli.cmd_rpc(argparse.Namespace(
                    method=method, params='{}', timeout=30)), 3)
            self.assertEqual(assignment_cli.run(argparse.Namespace(
                assignment_action='status', thread_key=args.thread_id, json=True)), 3)

    def test_selected_root_keeps_live_assignment_guard(self):
        self.prepare()
        with contextlib.redirect_stderr(io.StringIO()), patch.object(
                task_assignment, 'guard', side_effect=task_assignment.AssignmentUnavailable('held now')) as guard, patch.object(
                cli.rpc, 'chat', side_effect=AssertionError('generation forbidden')):
            self.assertEqual(cli.cmd_draft_reply(argparse.Namespace(thread_id='<a@example.test>')), 3)
            guard.assert_called_once_with(self.settings, '<a@example.test>')
        with contextlib.redirect_stdout(io.StringIO()), patch.object(cli.rpc, 'call_sync', return_value=[]) as rpc:
            self.assertEqual(cli.cmd_rpc(argparse.Namespace(method='emails.list_by_thread',
                params='{"thread_id":"<a@example.test>"}', timeout=30)), 0)
            rpc.assert_called_once()

    def test_custom_prompt_context_keeps_its_independent_scope(self):
        context = {**self.context, 'workset_enabled': False}
        with patch.dict(os.environ, {'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(context)}), contextlib.redirect_stdout(
                io.StringIO()), patch.object(cli.rpc, 'call_sync', return_value=[]) as rpc:
            self.assertEqual(cli.cmd_rpc(argparse.Namespace(
                method='emails.search', params='{}', timeout=30)), 0)
            rpc.assert_called_once()

    def test_secondary_tasks_do_not_replace_primary_workset_observation(self):
        observe(self.settings, 'tasks', [])
        path = self.directory / 'workset-tasks.json'
        original = path.read_bytes()
        secondary = Settings(_env_file=None, slug='workset', engine_owner_uid='secondary')
        with patch.object(cli.config, 'load', return_value=secondary), contextlib.redirect_stdout(
                io.StringIO()), patch.object(cli.rpc, 'call_sync', return_value=[]) as rpc:
            self.assertEqual(cli.cmd_tasks(argparse.Namespace(
                all=False, limit=200, json=True, account_switched=True)), 0)
            rpc.assert_called_once()
        self.assertEqual(path.read_bytes(), original)
        observe(self.settings, 'review', {'drafts': []})
        self.assertTrue(reserve(self.settings, self.discovery)['complete'])

    def test_actual_inventory_hooks_and_full_discovery_capture_in_subprocess(self):
        # A genuine three-process ancestry lets the unchanged ordinary artifact
        # producer validate its context. Only remote reads are local fixtures.
        code = r'''
import argparse, contextlib, copy, io, json, os, sys
from unittest.mock import patch
from cs import cli, operator_health
from cs.config import Settings
s=Settings(_env_file=None,slug='workset',engine_owner_uid='owner')
tasks=[{'id':'task','sources':{'thread_id':'<b@example.test>'},'contact_email':'b@example.test','updated_at':'2026-10-17T12:00:00Z'}]
review={'drafts':[{'id':'draft','thread_key':'<c@example.test>','to':'c@example.test','verdict':'overtaken','composed_at':'2026-10-16T12:00:00Z'}]}
d=json.loads(os.environ['WORKSET_TEST_DISCOVERY'])
sys.argv=['cs',*operator_health.ARGV]
with patch.object(cli.config,'load',return_value=s), patch.object(cli.rpc,'call_sync',return_value=tasks), patch('cs.review.gather',return_value=review), patch('cs.unanswered.sweep',return_value=copy.deepcopy(d)):
    outputs=[]
    for f,args in [(cli.cmd_tasks,argparse.Namespace(all=False,limit=200,json=True)),(cli.cmd_review,argparse.Namespace(json=True)),(cli.cmd_unanswered,argparse.Namespace(days=14,json=True,all_buckets=True,crm=False))]:
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream): rc=f(args)
        assert rc==0,(f.__name__,rc)
        outputs.append(stream.getvalue())
    actual=json.JSONDecoder().raw_decode(outputs[-1])[0]
    assert actual['open']==d['open'] and actual['human_work']==d['human_work']
    w=actual['triage_workset'];assert len(w['selected'])==2 and len(w['deferred'])==1
    roots={r['thread_key'] for r in w['selected']+w['deferred']}
    assert roots=={'<a@example.test>','<b@example.test>','<c@example.test>'}
    print(json.dumps({'selected':len(w['selected']),'deferred':len(w['deferred']),'full_inventory_preserved':True}))
'''
        runner = 'import subprocess,sys;raise SystemExit(subprocess.run([sys.executable,"-c",sys.argv[1]]).returncode)'
        env = dict(os.environ, WORKSET_TEST_DISCOVERY=json.dumps(self.discovery))
        result = subprocess.run([sys.executable, '-c', runner, code], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        captured = json.loads((self.directory / 'discovery.json').read_text())
        self.assertEqual(captured['owner_uid'], 'owner')
        self.assertEqual(captured['nonce'], self.context['nonce'])
        self.assertEqual(captured['discovery']['open'], self.discovery['open'])
        self.assertTrue(captured['discovery']['triage_workset']['complete'])

    def test_truncated_inventory_cannot_reserve_unrestricted_work(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), patch.object(
                cli.rpc, 'call_sync', return_value=[{'id': 'only-page'}]):
            self.assertEqual(cli.cmd_tasks(argparse.Namespace(all=False, limit=1, json=True)), 3)
        with self.assertRaises(RuntimeError):
            reserve(self.settings, self.discovery)

    def test_review_assignment_unknown_keeps_independent_work_and_warning(self):
        observe(self.settings, 'tasks', [])
        warning = 'Assignment authority UNKNOWN in current thread scope; held work stays visible'
        review = {'drafts': [], 'assignments_error': warning}
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), patch('cs.review.gather', return_value=review):
            self.assertEqual(cli.cmd_review(argparse.Namespace(json=True)), 0)
        self.assertEqual(json.loads(stream.getvalue())['assignments_error'], warning)
        discovery = copy.deepcopy(self.discovery)
        discovery['assignment_incomplete'] = True
        discovery['human_work'] = [{'thread_key': '<held@example.test>',
            'email': 'a@example.test', 'assignment': {'actor_uid': 'owner',
                'source_owner_uid': 'owner', 'state': 'unknown', 'complete': False,
                'hold_auto_reply': True}}]
        before = copy.deepcopy(discovery)
        actual = reserve(self.settings, discovery)
        self.assertTrue(actual['complete'])
        self.assertEqual([r['thread_key'] for r in actual['selected']], ['<a@example.test>'])
        self.assertEqual(discovery, before)
        self.assertTrue(any(r['thread_key'] == '<held@example.test>' for r in actual['held']))

    def test_scheduled_native_process_denies_evidence_agents(self):
        from cs import operator_recovery
        executable = self.home / 'native'
        arguments = self.home / 'arguments.json'
        executable.write_text('#!' + sys.executable + '\nimport json,os,sys\n'
            'open(os.environ["WORKSET_ARGV"],"w").write(json.dumps(sys.argv[1:]))\n'
            'print(json.dumps({"type":"result","is_error":False}))\n')
        executable.chmod(0o700)
        with patch.dict(os.environ, {'WORKSET_ARGV': str(arguments)}):
            operator_recovery._run(str(executable), ['Write'])
        actual = json.loads(arguments.read_text())
        denied = actual[actual.index('--disallowed-tools') + 1:]
        self.assertIn('Agent', denied)
        self.assertIn('Task', denied)
        self.assertIn('Write', denied)


if __name__ == '__main__':
    unittest.main()
