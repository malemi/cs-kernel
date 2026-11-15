"""Actual command/transport integration with controlled provider boundaries."""
import asyncio
import contextlib
import io
import os
import unittest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cs import cli, config, gmail_archive, gmail_drafts, rpc, review_draft, task_assignment
from test_contextual_email import Wire, settings

ROOT = '<original@customer.example>'
DRAFT_ID = '452ddb83-69c9-479c-98ab-b6f690eab2a7'
DRAFT = dict(id=DRAFT_ID, owner_id='support@fixture.example', status='draft',
             thread_id=ROOT, in_reply_to=ROOT, references=[ROOT],
             to_addresses=['customer@example.test'], cc_addresses=[], body='Answer one. Answer two.',
             subject='Reply', reply_binding={'root': ROOT, 'target': ROOT}, created_at='2026-10-21')
COPY = dict(engine_draft_id=DRAFT_ID, engine_owner_uid='fixture-owner', thread_key=ROOT,
            in_reply_to=ROOT, references=ROOT, to='customer@example.test', cc=None,
            body=DRAFT['body'], body_complete=True, is_draft=True, subject='Reply', uid='99')

from mirror_fixture import mirror_evidence
COPY.update(mirror_evidence(DRAFT, 'fixture-owner'))

class ReviewTests(unittest.TestCase):
    def invoke(self, *, after=None, copies=None, complete=True, chat_error=None, edited=False):
        calls = []
        current = [] if copies is None else list(copies)
        def rpc_call(s, method, params, timeout=None):
            calls.append(method)
            if method == 'system.capabilities':
                return {'assignment_draft_policy': 1, 'supervised_review_draft_policy': 1, 'exact_draft_publication': 1}
            if method == 'emails.list_by_thread':
                return {'emails': [{'id': '8ac7571d-778b-46a2-a55b-a08e703149f7',
                    'mailbox_address': 'support@fixture.example',
                    'mailbox_id': '8ac7571d-778b-46a2-a55b-a08e703149f8',
                    'from_email': 'customer@example.test', 'to_email': 'support@fixture.example',
                    'cc_email': '', 'date': '2026-10-21T08:36:44',
                    'subject': 'Question', 'body_plain': 'Please answer both questions.',
                    'is_user_sent': False, 'original_message_id': None}]}
            if method == 'drafts.list':
                return [] if calls.count(method) == 1 else ([DRAFT] if after is None else after)
            if method == 'drafts.inspect':
                return {'ok':True,'draft':DRAFT,'expected_snapshot':'snapshot'}
            if method == 'drafts.publish_review':
                observed={}; read(s,observation=observed)
                if not observed['complete']:
                    ok=False
                elif current:
                    ok=len(current)==1 and current[0].get('engine_draft_id')==DRAFT_ID and review_draft._matches(current[0],DRAFT,ROOT,'fixture-owner')
                else:
                    append(engine_draft_id=DRAFT_ID)
                    read(s,observation={})
                    ok=not edited
                return {'version':1,'ok':ok,'draft_id':DRAFT_ID,'cause':'published' if ok else 'publication-failed',
                        'achieved_stages':['engine-saved'],'next_action':'inspect-operation'}
            raise AssertionError(method)
        async def chat(s, message, **kw):
            calls.append('chat')
            self.assertTrue(kw['supervised_review'])
            self.assertEqual(kw['assignment_thread_key'], ROOT)
            self.assertEqual(kw['allow_tools'], set())
            if chat_error:
                raise RuntimeError(chat_error)
            return {'result': {'response': 'Prepared'}}
        def read(s, *, observation):
            calls.append('provider-read')
            observation['complete'] = complete
            return current
        def append(*a, **kw):
            calls.append('append')
            self.assertEqual(kw['engine_draft_id'], DRAFT_ID)
            current.append({**COPY, **({'body':'Human edit'} if edited else {})})
            return 'Drafts', []
        def source_read(s, addr, *, observation, **kwargs):
            observation['complete'] = True
            observation['inventory_complete'] = True
            return [{'date': datetime(2026, 10, 21, 8, 36, 44, tzinfo=timezone.utc),
                     'from_addr': 'customer@example.test', 'outbound': False,
                     'subject': 'Question', 'message_id': ROOT, 'references': '',
                     'body': 'Please answer both questions.', 'body_complete': True, 'provider_uid':'1'}]
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME":home}, clear=True), patch.object(config, 'load', return_value=settings()), \
             patch.object(rpc, 'call_sync', side_effect=rpc_call), patch.object(rpc, 'chat', side_effect=chat), \
             patch.object(gmail_archive, 'thread_with', side_effect=source_read), \
             patch.object(gmail_drafts, 'list_drafts', side_effect=read), patch.object(gmail_drafts, 'append_draft', side_effect=append), \
             patch.object(task_assignment, 'guard', side_effect=AssertionError('draft incorrectly assignment-held')), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc=cli.cmd_draft_reply(SimpleNamespace(thread_id=ROOT, message='Answer both questions', timeout=10, source_id=None))
        return rc, calls

    def test_held_request_prepares_one_verified_copy(self):
        rc,calls=self.invoke()
        self.assertEqual(rc,0)
        self.assertEqual(calls.count('append'),1)
        self.assertEqual(calls.count('provider-read'),2)

    def test_root_reply_without_references_checks_the_actual_emitted_header(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertTrue(review_draft._matches(COPY,{**DRAFT,'references':[]},ROOT,'fixture-owner'))

    def test_existing_copy_reused_without_append(self):
        rc,calls=self.invoke(copies=[COPY])
        self.assertEqual(rc,0)
        self.assertNotIn('append',calls)

    def test_human_copy_and_incomplete_read_do_not_duplicate(self):
        for copies,complete in [([{**COPY,'body':'Human edit'}],True),([{**COPY,'is_draft':False}],True),([COPY,COPY],True),([],False),([{**COPY,'engine_draft_id':None}],True)]:
            rc,calls=self.invoke(copies=copies,complete=complete)
            self.assertEqual(rc,3)
            self.assertNotIn('append',calls)

    def test_wrong_owner_thread_or_multiple_engine_rows_refuse(self):
        for after in [[],[DRAFT,DRAFT],[{**DRAFT,'owner_id':'foreign@example.test'}],[{**DRAFT,'thread_id':'<other@example.test>'}],[{**DRAFT,'reply_binding':None}]]:
            rc,calls=self.invoke(after=after)
            self.assertEqual(rc,3)
            self.assertNotIn('append',calls)

    def test_uncertain_readback_and_engine_error_are_explicit(self):
        self.assertEqual(self.invoke(edited=True)[0],3)
        rc,calls=self.invoke(chat_error='unsupported')
        self.assertEqual(rc,3)
        self.assertNotIn('append',calls)

    def test_real_mime_inventory_exposes_draft_state(self):
        from mirror_fixture import IMAP
        for expected in (True, False):
            client=IMAP()
            original=client.uid
            def uid(cmd,*args):
                typ,data=original(cmd,*args)
                if cmd=='FETCH' and not expected:
                    data=[(metadata.replace(b'\\Draft',b'\\Seen'),body) for metadata,body in data]
                return typ,data
            client.uid=uid
            observed={}
            with patch.object(gmail_drafts,'_imap',return_value=client):
                row=gmail_drafts.list_drafts(None,observation=observed)[0]
            self.assertTrue(observed['complete'])
            self.assertEqual(row['is_draft'],expected)

    def test_publication_calls_engine_and_never_local_append(self):
        calls=[]
        def call(settings,method,params,timeout=None):
            calls.append(method)
            if method=='drafts.inspect':
                return {'ok':True,'draft':DRAFT,'expected_snapshot':'native-snapshot'}
            self.assertEqual(method,'drafts.publish_review')
            self.assertEqual(params['expected_snapshot'],'native-snapshot')
            return {'version':1,'ok':True,'draft_id':DRAFT_ID}
        with patch.object(rpc,'call_sync',side_effect=call), patch.object(gmail_drafts,'append_draft') as append:
            self.assertTrue(review_draft.mirror(settings(),ROOT,DRAFT)['ok'])
            append.assert_not_called()
        self.assertEqual(calls,['drafts.inspect','drafts.publish_review'])

    def test_launcher_markers_preserve_scheduled_policy(self):
        for marker in ('CS_OPERATOR_HEADLESS','CS_HEADLESS_SEND','CS_OPERATOR_HEALTH_CONTEXT'):
            with patch.dict(os.environ,{marker:'1'},clear=True):
                self.assertFalse(review_draft.interactive())

    def test_real_authenticated_wire_negotiates_or_refuses(self):
        for version in (None, True, '1', 2, 1):
            wire=Wire(approve=False)
            original_send=wire.send
            async def send(raw):
                import json
                frame=json.loads(raw)
                if frame['method']=='system.capabilities':
                    wire.frames.append(frame)
                    await wire.emit({'id':frame['id'],'result':{'assignment_draft_policy':1,'supervised_review_draft_policy':version}})
                else:
                    await original_send(raw)
            wire.send=send
            with wire.patches(),patch.dict(os.environ,{},clear=True):
                if type(version) is int and version==1:
                    asyncio.run(rpc.chat(settings(),'Draft',assignment_thread_key=ROOT,supervised_review=True))
                    params=wire.frames[-1]['params']
                    self.assertEqual(params['supervised_review_draft_policy_version'],1)
                    self.assertEqual(params['assignment_policy_version'],1)
                else:
                    with self.assertRaises(RuntimeError):
                        asyncio.run(rpc.chat(settings(),'Draft',assignment_thread_key=ROOT,supervised_review=True))
                    self.assertEqual([f['method'] for f in wire.frames],['system.capabilities'])

    def test_send_and_scheduled_cannot_request_review(self):
        for kw in ({'allow_tools':{'send_draft'}},{'read_only':True},{'role':'triage'}):
            with patch.dict(os.environ,{},clear=True),self.assertRaises(ValueError):
                asyncio.run(rpc.chat(settings(),'Draft',assignment_thread_key=ROOT,supervised_review=True,**kw))
        with patch.dict(os.environ,{'CS_OPERATOR_HEADLESS':'1'},clear=True),self.assertRaises(ValueError):
            asyncio.run(rpc.chat(settings(),'Draft',assignment_thread_key=ROOT,supervised_review=True))


if __name__=='__main__':
    unittest.main()
