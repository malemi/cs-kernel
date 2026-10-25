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
    @contextlib.contextmanager
    def send_sequence(self, compose_argv=None, *, mode='send'):
        """Real argparse/reservation with a stateful local engine protocol."""
        from datetime import datetime, timezone
        self.settings.cs_triage_mode = mode
        self.settings.email_address = 'owner@example.test'
        if not any(row['thread_key'] == '<b@example.test>' for row in self.discovery['open']):
            self.discovery['open'].append({'thread_key': '<b@example.test>', 'email': 'b@example.test',
                                         '_workset_revision': 'b' * 64})
        selected = self.prepare()
        self.assertEqual(len(selected['selected']), 2)
        reservation = (self.directory / 'workset-reserved.json').read_bytes()
        state = {'draft': None, 'calls': [], 'mirrors': [], 'retired': [], 'retirement_error': False}
        full_id = '452ddb83-69c9-479c-98ab-b6f690eab2a7'

        def call(settings, method, params, **kwargs):
            state['calls'].append((method, copy.deepcopy(params)))
            if method == 'tasks.assignment.project':
                return normal_projection(settings, params)
            if method == 'emails.list_by_thread':
                return {'emails': [{'id': '8ac7571d-778b-46a2-a55b-a08e703149f7'}]}
            self.assertEqual(method, 'drafts.list')
            row = state['draft']
            return [copy.deepcopy(row)] if row and row['status'] == params.get('status', 'draft') else []

        async def chat(settings, message, **kwargs):
            state['calls'].append(('chat', copy.copy(kwargs)))
            if kwargs['allow_tools'] == set():
                self.assertEqual(kwargs['assignment_thread_key'], '<a@example.test>')
                self.assertIsNone(kwargs.get('email_context'))
                now = datetime.now(timezone.utc).isoformat()
                state['draft'] = {'id': full_id, 'owner_id': settings.email_address,
                    'thread_id': '<a@example.test>', 'to_addresses': ['a@example.test'],
                    'cc_addresses': [], 'bcc_addresses': [], 'subject': 'Re: request',
                    'body': 'Confirmed.', 'body_format': 'plain', 'in_reply_to': '<a@example.test>',
                    'references': ['<a@example.test>'], 'original_message_id': '<a@example.test>',
                    'attachment_paths': [], 'status': 'draft', 'created_at': now, 'updated_at': now}
                return {'result': {'response': 'Composed.'}, 'approvals': [], 'notifications': []}
            self.assertEqual(kwargs['allow_tools'], {'send_draft'})
            self.assertNotIn('email_context', kwargs)
            self.assertIn(full_id, message)
            approve = kwargs['approval_predicate']
            self.assertFalse(approve('send_draft', {'draft_id': 'wrong'}))
            self.assertTrue(approve('send_draft', {'draft_id': full_id}))
            self.assertFalse(approve('send_draft', {'draft_id': full_id}))
            state['draft']['status'] = 'sent'
            return {'result': {'response': 'Sent.'}, 'notifications': [], 'approvals': [
                {'tool': 'send_draft', 'mode': 'once', 'input': {'draft_id': full_id}}]}

        def mirror(settings, **kwargs):
            state['mirrors'].append(kwargs['engine_draft_id'])
            return 'Drafts', []

        def retire(settings, *, commit, timeout, only_ids):
            self.assertTrue(commit)
            self.assertEqual(only_ids, {full_id})
            self.assertEqual(state['draft']['status'], 'sent')
            if state['retirement_error']:
                raise OSError('unavailable')
            state['retired'].extend(only_ids)
            return {'ok': True, 'retired': [{}], 'skipped': [], 'failed': []}

        with patch.dict(os.environ, {'CS_HEADLESS_SEND': '1'}), \
                patch.object(cli.rpc, 'call_sync', side_effect=call), \
                patch.object(cli.rpc, 'chat', side_effect=chat), \
                patch('cs.gmail_drafts.append_draft', side_effect=mirror), \
                patch.object(cli, '_retire_sent_mirrors', side_effect=retire), \
                contextlib.redirect_stdout(io.StringIO()) as output, \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            argv = compose_argv or ['draft-reply', 'reply in the thread with a@example.test: confirm',
                                    '--thread-id', '<a@example.test>']
            self.assertEqual(cli.main(argv), 0)
            self.assertIn('engine draft ready: ' + full_id, output.getvalue())
            state.update(full_id=full_id, output=output, errors=errors)
            yield state
            self.assertEqual((self.directory / 'workset-reserved.json').read_bytes(), reservation)

    def test_stateful_selected_compose_then_exact_send(self):
        with self.send_sequence() as state:
            self.assertEqual(cli.main(['draft-send', state['full_id']]), 0)
            self.assertEqual(state['draft']['status'], 'sent')
            self.assertEqual(state['mirrors'], [state['full_id']])
            self.assertEqual(state['retired'], [state['full_id']])
            self.assertEqual(sum(c[0] == 'chat' for c in state['calls']), 2)

    def test_stateful_send_rejects_changed_actual_draft_and_foreign_journal(self):
        faults = ('recipient', 'cc', 'bcc', 'body', 'root', 'unknown-root', 'owner',
                  'unknown-owner', 'reply', 'references', 'attachment', 'nonce', 'journal-owner', 'prefix')
        for fault in faults:
            with self.subTest(fault=fault):
                # Independent run/context for each mutation; do not reuse quota or observations.
                with tempfile.TemporaryDirectory() as directory:
                    self.directory = Path(directory)
                    self.directory.chmod(0o700)
                    self.context['directory'] = directory
                    self.context['nonce'] = fault * 3
                    self.discovery['open'] = self.discovery['open'][:1]
                    with patch.dict(os.environ, {'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(self.context)}):
                        with self.send_sequence() as state:
                            row = state['draft']
                            if fault == 'recipient':row['to_addresses'] = ['b@example.test']
                            if fault == 'cc':row['cc_addresses'] = ['b@example.test']
                            if fault == 'bcc':row['bcc_addresses'] = ['b@example.test']
                            if fault == 'body':row['body'] = 'Changed.'
                            if fault == 'root':row['thread_id'] = '<b@example.test>'
                            if fault == 'unknown-root':
                                row.update(thread_id=None, in_reply_to=None, references=[])
                            if fault == 'owner':row['owner_id'] = 'foreign@example.test'
                            if fault == 'unknown-owner':row.pop('owner_id')
                            if fault == 'reply':row['in_reply_to'] = '<b@example.test>'
                            if fault == 'references':row['references'] = ['<b@example.test>']
                            if fault == 'attachment':row['attachment_paths'] = ['changed.pdf']
                            if fault in ('nonce', 'journal-owner'):
                                journal = next(self.directory.glob('workset-draft-*.json'))
                                value = json.loads(journal.read_text())
                                value['nonce' if fault == 'nonce' else 'owner_uid'] = 'foreign'
                                journal.write_text(json.dumps(value))
                            before = len(state['calls'])
                            supplied = state['full_id'][:8] if fault == 'prefix' else state['full_id']
                            self.assertIn(cli.main(['draft-send', supplied]), (1, 3))
                            self.assertEqual(state['calls'][before:], [('drafts.list', {'status': 'draft'})])
                            self.assertEqual(state['retired'], [])

    def test_draft_mode_and_absent_marker_never_send(self):
        for mode, marker in (('draft', '1'), ('send', '')):
            with self.subTest(mode=mode, marker=marker), self.send_sequence(mode=mode) as state:
                before = len(state['calls'])
                with patch.dict(os.environ, {'CS_HEADLESS_SEND': marker}):
                    self.assertEqual(cli.main(['draft-send', state['full_id']]), 3)
                self.assertEqual(state['calls'][before:], [])
                self.assertEqual(state['retired'], [])

    def test_recorded_send_retirement_failure_never_retries_delivery(self):
        with self.send_sequence() as state:
            state['retirement_error'] = True
            self.assertEqual(cli.main(['draft-send', state['full_id']]), 5)
            self.assertEqual(state['draft']['status'], 'sent')
            self.assertIn('Do not retry sending', state['errors'].getvalue())
            self.assertEqual(sum(c[0] == 'chat' for c in state['calls']), 2)

    def test_existing_ready_draft_uses_actual_typed_review_snapshot(self):
        self.existing_ready_draft('<a@example.test>')

    def test_ready_decision_for_another_root_cannot_authorize_send(self):
        self.existing_ready_draft('<b@example.test>')

    def existing_ready_draft(self, reviewed_root):
        from cs.draft_state import inventory_proof
        self.settings.cs_triage_mode = 'send'
        self.settings.email_address = 'owner@example.test'
        draft = {'id': 'ready-draft-full-id', 'owner_id': self.settings.email_address,
                 'thread_id': '<a@example.test>', 'to_addresses': ['a@example.test'],
                 'body': 'Ready reply.', 'status': 'draft'}
        payload = self.typed_review()
        payload['engine_drafts'] = [copy.deepcopy(draft)]
        payload['drafts'][0]['engine_id'] = draft['id']
        payload['drafts'][0]['thread_key'] = reviewed_root
        payload['drafts_inventory'] = inventory_proof([], payload['engine_drafts'],
            payload['drafts'], payload['gmail_drafts_observation'])
        observe(self.settings, 'tasks', [])
        observe(self.settings, 'review', payload)
        reserve(self.settings, self.discovery)
        sent = []

        def call(settings, method, params, **kwargs):
            if method == 'tasks.assignment.project':return normal_projection(settings, params)
            self.assertEqual(method, 'drafts.list')
            return [dict(draft, status='sent' if sent else 'draft')] if params['status'] == ('sent' if sent else 'draft') else []

        async def chat(settings, message, **kwargs):
            self.assertTrue(kwargs['approval_predicate']('send_draft', {'draft_id': draft['id']}))
            sent.append(draft['id'])
            return {'result': {'response': 'Sent.'}, 'notifications': [], 'approvals': [
                {'tool': 'send_draft', 'mode': 'once', 'input': {'draft_id': draft['id']}}]}

        with patch.dict(os.environ, {'CS_HEADLESS_SEND': '1'}), \
                patch.object(cli.rpc, 'call_sync', side_effect=call), \
                patch.object(cli.rpc, 'chat', side_effect=chat), \
                patch.object(cli, '_retire_sent_mirrors', return_value={'ok': True}) as retire, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if reviewed_root == '<a@example.test>':
                self.assertEqual(cli.main(['draft-send', draft['id']]), 0)
                self.assertEqual(sent, [draft['id']])
                self.assertEqual(retire.call_args.kwargs['only_ids'], {draft['id']})
            else:
                self.assertEqual(cli.main(['draft-send', draft['id']]), 3)
                self.assertEqual(sent, [])
                retire.assert_not_called()

    def typed_review(self, *, hold=False):
        from cs.draft_state import inventory_proof
        row = {'engine_id': 'draft-a', 'gmail_uid': None, 'gmail_uidvalidity': None,
               'thread_key': '<a@example.test>', 'to': 'a@example.test', 'verdict': 'ready',
               'workset_hold_reasons': ['mailbox_unreadable'] if hold else []}
        payload = {'drafts': [row], 'gmail_drafts': [], 'engine_drafts': [{'id': 'draft-a'}],
                   'gmail_drafts_observation': {'version': 1, 'complete': True,
                       'search_complete': True, 'expected_uids': [], 'observed_uids': [], 'uidvalidity': '7'},
                   'drafts_notes': ['A deliberately skipped mailbox remains reported.']}
        payload['drafts_inventory'] = inventory_proof(payload['gmail_drafts'], payload['engine_drafts'],
            payload['drafts'], payload['gmail_drafts_observation'])
        self.assertIs(payload['drafts_inventory']['complete'], True)
        return payload

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
            if fault == 'proof':payload['drafts_inventory']['gmail_count'] = 99
            if fault == 'foreign-id':payload['drafts'][0]['engine_id'] = 'foreign'
            if fault == 'read-error':payload['gmail_drafts_error'] = 'unavailable'
            if fault == 'missing-fetch':payload['gmail_drafts_observation']['expected_uids'] = ['1']
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
                    payload['drafts_inventory'] = inventory_proof(payload['gmail_drafts'], payload['engine_drafts'],
                        payload['drafts'], payload['gmail_drafts_observation'])
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
        raw = [{'id': 'multiple', 'to_addresses': ['a@example.test', 'z@example.test'],
                'cc_addresses': ['cc@example.test'], 'body': 'Short reply',
                'created_at': '2026-10-18T00:00:00Z'}]
        rows, notes = draft_state.reconcile(self.settings, [], raw,
            inbound=lambda *a, **kw: [], sent=lambda *a, **kw: [],
            settled=lambda *a: ({}, None), delivered=lambda *a: (None, None))
        self.assertIn('root_missing', rows[0]['workset_hold_reasons'])
        self.assertEqual(set(rows[0]['recipients']), {'a@example.test', 'z@example.test'})
        self.assertEqual(set(rows[0]['cc_recipients']), {'cc@example.test'})
        payload = self.typed_review()
        payload.update(engine_drafts=raw, drafts=rows, drafts_notes=notes)
        payload['drafts_inventory'] = draft_state.inventory_proof([], raw, rows,
            payload['gmail_drafts_observation'])
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
                ({'drafts': [], 'engine_drafts_error': sentinel}, 'review_inventory_incomplete', 'engine_drafts_error'),
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
