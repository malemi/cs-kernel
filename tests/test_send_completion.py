import contextlib
import copy
import io
import os
import unittest
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import patch

from cs import cli, config, gmail_drafts, interactive_draft, rpc, send_completion, task_assignment
import test_interactive_draft_continuity as continuity
from test_interactive_draft_continuity import DRAFT, ROOT, TARGET, DRAFT_ID
from test_contextual_email import settings
from mirror_fixture import mirror_evidence, mirror_message


class SentIMAP:
    def __init__(self, draft, mode='ok'):
        self.mode = mode
        self.message = EmailMessage()
        for key, value in {'From':'support@fixture.example', 'To':'customer@example.test',
                'Subject':draft['subject'], 'Message-ID':'<sent@example.test>',
                'References':ROOT, 'In-Reply-To':TARGET}.items():
            self.message[key] = value
        self.message.set_content(draft['body'])
    def list(self):
        return 'OK', [b'(\\Sent) "/" "Sent"']
    def select(self, *a, **kw):
        assert kw['readonly'] is True
        return 'OK', [b'1']
    def uid(self, command, *args):
        if command == 'SEARCH':
            return 'OK', [{'missing':b'', 'duplicate':b'1 2'}.get(self.mode,b'1')]
        raw = self.message.as_bytes()
        return 'OK', [(b'1 (UID 1 RFC822.SIZE '+str(len(raw)).encode()+b')',raw)]
    def logout(self):
        pass


class CompletionTests(unittest.TestCase):
    def invoke(self, mode='ok'):
        draft = copy.deepcopy(DRAFT)
        draft['subject'] = 'Re: Fatture — Francesco Zuccaro / Smash Arena'
        sent = dict(draft, status='sent', sent_message_id='<sent@example.test>')
        provider = SentIMAP(draft, mode)
        mirror = dict(engine_draft_id=DRAFT_ID, engine_owner_uid='fixture-owner', thread_key=ROOT,
            in_reply_to=TARGET, references=ROOT, to='customer@example.test', cc=None, bcc=None,
            **{'from':'support@fixture.example'}, subject=draft['subject'], body=draft['body'],
            identity_headers_valid=True, body_complete=True, is_draft=True, uid='99', uidvalidity='5', fingerprint='abc')
        mirror.update(mirror_evidence(draft,'fixture-owner'))
        if mode == 'mirror-pdf':
            from mirror_fixture import IMAP
            raw_provider = IMAP()
            edited = mirror_message(draft,'fixture-owner')
            edited.add_attachment(b'Human revised invoice',maintype='application',subtype='pdf',filename='invoice.pdf')
            raw_provider.raw = edited.as_bytes()
            with patch.object(gmail_drafts,'_imap',return_value=raw_provider):
                mirror = gmail_drafts.list_drafts(settings())[0]
        if mode == 'wrong-body':
            provider.message.set_content('Different sent body')
        if mode == 'wrong-header':
            provider.message['Bcc'] = 'hidden@example.test'
        if mode == 'duplicate-header':
            provider.message._headers.append(('From','other@example.test'))
        if mode == 'changed-engine':
            sent['body'] = 'Edited while sending'
        if mode == 'edited':
            mirror['subject'] = 'Human edit'
        if mode == 'edited-bcc':
            mirror['bcc'] = 'human@example.test'
        human = dict(engine_draft_id=None, uid='1000', body='Unrelated human draft')
        mirrors = [human] if mode == 'missing-mirror' else [human,mirror]
        if mode == 'duplicate-mirror':
            mirrors.append(dict(mirror, uid='100'))
        sends = []
        moves = []
        def call(s, method, params, **kwargs):
            assert method == 'drafts.list'
            return [draft] if params['status'] == 'draft' else [sent]
        async def chat(s, message, **kwargs):
            predicate = kwargs['approval_predicate']
            self.assertTrue(predicate('send_draft', {'draft_id':DRAFT_ID}))
            self.assertFalse(predicate('send_draft', {'draft_id':DRAFT_ID}))
            sends.append(DRAFT_ID)
            return {'result':{}, 'approvals':[{'tool':'send_draft', 'mode':'once', 'input':{'draft_id':DRAFT_ID}}]}
        def inventory(s, *, observation):
            observation['complete'] = not (mode == 'post-unknown' and moves)
            return list(mirrors)
        def delete(s, **kwargs):
            moves.append(kwargs)
            if mode == 'cleanup-failure':
                return {'ok':False}
            if mode != 'move-no-effect':
                mirrors[:] = [row for row in mirrors if row['uid'] != kwargs['uid']]
            return {'ok':True}
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch.object(config, 'load', return_value=settings()), \
             patch.object(rpc, 'call_sync', side_effect=call), patch.object(rpc, 'chat', side_effect=chat), \
             patch.object(task_assignment, 'guard'), patch.object(gmail_drafts, '_imap', return_value=provider), \
             patch.object(gmail_drafts, 'list_drafts', side_effect=inventory), \
             patch.object(gmail_drafts, 'delete_draft', side_effect=delete), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            rc = cli.cmd_draft_send(SimpleNamespace(draft_id=DRAFT_ID, timeout=10))
        self.assertEqual(sends,[DRAFT_ID])
        return rc, mirrors, moves, output.getvalue()

    def test_actual_exact_send_cleans_only_unchanged_copy(self):
        rc, mirrors, moves, output = self.invoke()
        self.assertEqual(rc,0,output)
        self.assertEqual(mirrors,[dict(engine_draft_id=None,uid='1000',body='Unrelated human draft')])
        self.assertEqual(len(moves),1)
        self.assertEqual(len(moves[0]['expected_fingerprint']),64)

    def test_delivered_incomplete_never_repeats_send_or_moves_unproven_copy(self):
        for mode in ('missing','duplicate','wrong-body','wrong-header','duplicate-header','changed-engine',
                     'edited','edited-bcc','mirror-pdf','missing-mirror','duplicate-mirror','cleanup-failure'):
            rc, mirrors, moves, output = self.invoke(mode)
            self.assertEqual(rc,5,(mode,output))
            self.assertIn('Do not retry sending',output)
            self.assertEqual(len(moves),int(mode == 'cleanup-failure'),mode)
            if mode != 'missing-mirror':
                self.assertTrue(mirrors,mode)

    def test_move_acknowledgement_requires_independent_complete_absence_readback(self):
        for mode in ('move-no-effect','post-unknown'):
            rc, mirrors, moves, output = self.invoke(mode)
            self.assertEqual(rc,5,(mode,output))
            self.assertIn('Do not retry sending',output)
            self.assertEqual(len(moves),1)
            self.assertTrue(any(row.get('engine_draft_id') is None for row in mirrors))
            self.assertEqual(any(row.get('engine_draft_id') == DRAFT_ID for row in mirrors),mode == 'move-no-effect')

    def test_real_mime_human_edits_refuse_reuse_and_cleanup(self):
        from mirror_fixture import IMAP
        from cs import review_draft
        draft = copy.deepcopy(DRAFT)
        sent = dict(draft,status='sent',sent_message_id='<sent@example.test>')
        for mode in ('pdf','filename','bcc','from','extra-part','html-link','ambiguous-header'):
            message = mirror_message(draft,'fixture-owner')
            if mode == 'pdf':
                message.add_attachment(b'Human revised invoice',maintype='application',subtype='pdf',filename='invoice.pdf')
            elif mode == 'filename':
                message['Content-Disposition'] = 'inline; filename="notes.txt"'
            elif mode == 'bcc':
                message['Bcc'] = 'human@example.test'
            elif mode == 'from':
                message.replace_header('From','foreign@example.test')
            elif mode == 'extra-part':
                message.add_alternative('Additional calendar instructions',subtype='calendar')
            elif mode == 'html-link':
                message.add_alternative('<p>'+draft['body']+'</p><a href="https://changed.example">Pay</a>',subtype='html')
            else:
                message._headers.append(('From','other@example.test'))
            provider = IMAP()
            provider.raw = message.as_bytes()
            with patch.object(gmail_drafts,'_imap',return_value=provider), patch.object(gmail_drafts,'append_draft') as append:
                row = gmail_drafts.list_drafts(settings())[0]
                self.assertFalse(review_draft._matches(row,draft,ROOT,'fixture-owner'))
                append.assert_not_called()
            with patch.object(gmail_drafts,'_imap',side_effect=[SentIMAP(draft),provider]):
                with self.assertRaisesRegex(ValueError,'changed or is unverifiable'):
                    send_completion.complete(settings(),draft,[sent])
            self.assertEqual(provider.moves,[],mode)

    def test_sent_additional_mime_or_changed_html_link_is_unverified(self):
        draft = copy.deepcopy(DRAFT)
        for mode in ('pdf','extra-part','html-link'):
            provider = SentIMAP(draft)
            if mode == 'pdf':
                provider.message.add_attachment(b'Attachment',maintype='application',subtype='pdf',filename='new.pdf')
            elif mode == 'extra-part':
                provider.message.add_alternative('Hidden instructions',subtype='calendar')
            else:
                provider.message.add_alternative('<p>'+draft['body']+'</p><a href="https://changed.example">Pay</a>',subtype='html')
            with patch.object(gmail_drafts,'_imap',return_value=provider), patch.object(gmail_drafts,'delete_draft') as delete:
                with self.assertRaises(ValueError):
                    send_completion._sent(settings(),draft,'<sent@example.test>')
                delete.assert_not_called()
        html = dict(draft,body_format='html',body='<p>Answer.</p><a href="https://original.example">Pay</a>')
        provider = SentIMAP(html)
        provider.message.set_content(html['body'],subtype='html')
        with patch.object(gmail_drafts,'_imap',return_value=provider):
            self.assertEqual(send_completion._sent(settings(),html,'<sent@example.test>'),ROOT)
            provider.message.set_content(html['body'].replace('original.example','changed.example'),subtype='html')
            with self.assertRaisesRegex(ValueError,'HTML content or links differ'):
                send_completion._sent(settings(),html,'<sent@example.test>')

    def test_plain_sent_exact_engine_content_ignores_stale_html_format_label(self):
        draft = dict(DRAFT,body_format='html')
        provider = SentIMAP(draft)
        with patch.object(gmail_drafts,'_imap',return_value=provider):
            self.assertEqual(send_completion._sent(settings(),draft,'<sent@example.test>'),ROOT)
        html = dict(draft,body='<p>Answer.</p><a href="https://original.example">Pay</a>')
        provider = SentIMAP(html)
        provider.message.set_content('Answer. Pay')
        with patch.object(gmail_drafts,'_imap',return_value=provider):
            with self.assertRaisesRegex(ValueError,'complete plain content differs'):
                send_completion._sent(settings(),html,'<sent@example.test>')

    def test_existing_edit_without_timestamp_is_selected_once(self):
        before = copy.deepcopy(DRAFT)
        before['body'] = 'Old text'
        with patch.object(interactive_draft, '_drafts', side_effect=[[before],[DRAFT]]):
            rc, calls, _ = continuity.Continuity().invoke()
        self.assertEqual(rc,0)
        self.assertEqual(calls.count('append'),1)
        self.assertEqual(sum(isinstance(c,tuple) for c in calls),1)

    def test_existing_edit_preserves_conflicting_provider_copy_without_replay(self):
        before = dict(DRAFT, body='Old text')
        with patch.object(interactive_draft, '_drafts', side_effect=[[before],[DRAFT]]):
            rc, calls, _ = continuity.Continuity().invoke(copies=[dict(continuity.COPY,body='Human edit')])
        self.assertEqual(rc,3)
        self.assertNotIn('append',calls)
        self.assertEqual(sum(isinstance(c,tuple) for c in calls),1)

    def test_changed_and_new_union_or_no_change_refuses_without_replay(self):
        for after in ([DRAFT], [dict(DRAFT,body='Changed'),dict(DRAFT,id='8ac7571d-778b-46a2-a55b-a08e703149f8')]):
            with patch.object(interactive_draft, '_drafts', side_effect=[[copy.deepcopy(DRAFT)],after]):
                rc, calls, _ = continuity.Continuity().invoke()
            self.assertEqual(rc,3)
            self.assertNotIn('append',calls)
            self.assertEqual(sum(isinstance(c,tuple) for c in calls),1)

    def test_real_rfc2047_append_readback_and_different_subject_preserved(self):
        from mirror_fixture import IMAP
        from cs import review_draft
        draft = dict(DRAFT,subject='Re: Fatture — Francesco Zuccaro / Smash Arena')
        client = IMAP()
        appended = []
        def append(*args):
            appended.append(args[-1])
            client.raw = args[-1]
            return 'OK', []
        client.append = append
        with patch.dict(os.environ,{},clear=True), patch.object(gmail_drafts,'_imap',return_value=client):
            gmail_drafts.append_draft(settings(), to=', '.join(draft['to_addresses']),
                subject=draft['subject'], body=draft['body'], in_reply_to=draft['in_reply_to'],
                references=draft['references'], body_md=True, engine_draft_id=DRAFT_ID,
                engine_owner_uid='fixture-owner')
            self.assertEqual(len(appended),1)
            self.assertIn(b'=?utf-8?',appended[0])
            row = gmail_drafts.list_drafts(settings())[0]
            self.assertFalse(review_draft._matches(row,dict(draft,subject='Different subject'),ROOT,'fixture-owner'))
            self.assertEqual(len(appended),1)
            row = gmail_drafts.list_drafts(settings())[0]
            result = gmail_drafts.delete_draft(settings(), uid=row['uid'], commit=True,
                expected_engine_draft_id=DRAFT_ID, expected_owner_uid='fixture-owner',
                expected_uidvalidity=row['uidvalidity'], expected_fingerprint=row['fingerprint'])
            self.assertTrue(result['ok'],result)
            self.assertEqual(len(client.moves),1)

    def test_predispatch_snapshot_survives_mutating_rpc_rows(self):
        selected=settings()
        draft=copy.deepcopy(DRAFT)
        original=copy.deepcopy(draft)
        async def chat(*a,**kw):
            draft['body']='Changed in flight'
            draft['to_addresses'].append('other@example.test')
            return {'result':{},'approvals':[{'tool':'send_draft','mode':'once','input':{'draft_id':DRAFT_ID}}]}
        sent=[dict(draft,status='sent')]
        def call(s,method,params,**kw):
            self.assertEqual(method,'drafts.list')
            return [draft] if params['status']=='draft' else sent
        with patch.dict(os.environ,{},clear=True),patch.object(config,'load',return_value=selected), \
             patch.object(rpc,'call_sync',side_effect=call),patch.object(rpc,'chat',side_effect=chat), \
             patch.object(task_assignment,'guard'),patch.object(send_completion,'complete') as complete, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.cmd_draft_send(SimpleNamespace(draft_id=DRAFT_ID,timeout=10)),0)
        complete.assert_called_once_with(selected,original,sent)
        self.assertNotEqual(draft,original)

    def test_scheduled_send_bypasses_interactive_completion(self):
        for marker in ('CS_OPERATOR_HEADLESS','CS_HEADLESS_SEND','CS_OPERATOR_HEALTH_CONTEXT'):
            async def chat(*a,**kw):
                return {'result':{},'approvals':[{'tool':'send_draft','mode':'once','input':{'draft_id':DRAFT_ID}}]}
            def call(s,method,params,**kw):
                self.assertEqual(method,'drafts.list')
                return [dict(DRAFT,status=params['status'])]
            with patch.dict(os.environ,{marker:'1'},clear=True),patch.object(config,'load',return_value=settings()), \
                 patch.object(rpc,'call_sync',side_effect=call),patch.object(rpc,'chat',side_effect=chat), \
                 patch.object(task_assignment,'guard'),patch.object(send_completion,'complete') as complete, \
                 patch.object(cli,'_retire_sent_mirrors',side_effect=AssertionError('bulk retirement')), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_draft_send(SimpleNamespace(draft_id=DRAFT_ID,timeout=10)),0)
            complete.assert_not_called()


if __name__ == '__main__':
    unittest.main()
