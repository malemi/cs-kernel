"""Hosted-schema continuity, exact source/output checks and authenticated denial."""
import asyncio
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import patch

from cs import cli, config, gmail_archive, interactive_draft, rpc, state, task_assignment
from test_contextual_email import Wire, settings

ROOT = '<root@example.test>'
TARGET = '<latest@example.test>'
SOURCE_ID = '8ac7571d-778b-46a2-a55b-a08e703149f7'
DRAFT_ID = '452ddb83-69c9-479c-98ab-b6f690eab2a7'
SOURCE = dict(id=SOURCE_ID, from_email='customer@example.test', from_name='Customer',
              to_email='support@fixture.example', cc_email='', date='2026-10-22T08:36:44',
              subject='Question', body_plain='Please answer.', body_html=None, is_auto_reply=False,
              is_user_sent=False, has_attachments=False, attachment_filenames=[],
              mailbox_id='8ac7571d-778b-46a2-a55b-a08e703149f8',
              mailbox_address='support@fixture.example', original_message_id=None, pec_markers=None)
GMAIL = dict(date=datetime(2026, 10, 22, 8, 36, 44, tzinfo=timezone.utc),
             from_addr='customer@example.test', outbound=False, subject='Question',
             message_id=TARGET, references=ROOT, body='Please answer.', attachments=[])
GMAIL['body_complete'] = True
GMAIL['provider_uid'] = '1'


def header_batches(cls):
    """Adapt older focused message fakes to the newly explicit UID/header wire."""
    original = cls.uid
    def uid(self,command,*args):
        if command=='FETCH' and 'HEADER.FIELDS' in str(args[-1]):
            combined=[]
            for value in args[0].split(b','):
                typ,items=uid(self,'FETCH',value,'(UID X-GM-LABELS BODY.PEEK[])')
                if typ!='OK':
                    return typ,items
                combined.extend(items)
            return 'OK',combined
        typ,items=original(self,command,*args)
        if command=='FETCH' and typ=='OK':
            items=[(metadata+b' UID '+args[0],raw) if isinstance(item,tuple)
                   else item for item in items for metadata,raw in ([item] if isinstance(item,tuple) else [(b'',b'')])]
        return typ,items
    cls.uid=uid
    return cls


class WindowIMAP:
    """Literal SINCE and UID batch transport; intentionally broken References index."""
    def __init__(self,mode='ordinary'):
        self.mode=mode
        self.body_uids=[]
        self.searches=[]
        self.messages={}
        for uid,root,sender,when,body in (
                (b'1',ROOT,'customer@example.test','08:36:44','Please answer.'),
                (b'2','<unrelated@example.test>','unrelated@example.test','09:00:00','Unrelated history.')):
            self.messages[uid]=self.message(uid,root,sender,when,body)
        if mode in ('participant','older-date'):
            self.messages[b'3']=self.message(b'3',ROOT,'colleague@example.test',
                '08:30:00' if mode=='older-date' else '09:36:44','Cancel prior request.')
        if mode=='html':
            self.messages[b'1'].add_alternative('<p>Please answer.</p><p>Additional HTML request.</p>'
                '<a href="https://example.test/account">Account</a>',subtype='html')
        if mode=='overflow':
            for text in ('x'*40000,'y'*40000):
                self.messages[b'1'].add_alternative(text,subtype='html')
    @staticmethod
    def message(uid,root,sender,when,body):
        msg=EmailMessage()
        msg['From']=sender
        msg['To']='support@fixture.example'
        msg['Subject']='Question'
        msg['Message-ID']=TARGET if uid==b'1' else '<'+uid.decode()+'@example.test>'
        msg['References']=root+' <long-other-ancestor@example.test>'
        msg['Date']='Thu, 22 Oct 2026 '+when+' +0000'
        msg.set_content(body)
        return msg
    def select(self,*args,**kw):
        return 'OK',[str(len(self.messages)).encode()]
    def uid(self,command,*args):
        if command=='SEARCH':
            self.searches.append(args)
            return 'OK',[b' '.join(self.messages) if 'SINCE' in args else b'']
        is_header='HEADER.FIELDS' in args[-1]
        ids=args[0].split(b',')
        if is_header and self.mode=='uidgap':
            ids=ids[:-1]
        result=[]
        for uid in ids:
            if not is_header:
                self.body_uids.append(uid)
            metadata=b'1 (UID '+uid+(b' BODY[HEADER.FIELDS] {99}' if is_header else b' X-GM-LABELS () BODY[] {99}')
            result.append((metadata,self.messages[uid].as_bytes()))
        return 'OK',result
    def logout(self):
        pass
class Continuity(unittest.TestCase):
    def invoke(self, *, source=None, gmail=None, source_id=None, self_email=False,
               suppressed=False, real_reader=False, observation_complete=True, expected_material=()):
        calls = []
        def call(settings, method, params, timeout=None):
            calls.append(method)
            if method == "system.capabilities":
                return {"mailbox_reply": 1}
            if method == "emails.list_by_thread":
                return {"emails": source if isinstance(source, list) else [source or SOURCE]}
            if method == "drafts.compose_reply":
                self.assertEqual(params["source_email_id"], SOURCE_ID)
                self.assertEqual(params["thread_key"], ROOT)
                return {"ok": True, "state": "completed", "request_key": params["request_key"],
                        "draft_id": "native", "current_draft": {"exists":True}}
            raise AssertionError(method)
        original_reader = gmail_archive.thread_with
        def provider(s, addr, **kwargs):
            if real_reader:
                return original_reader(s, addr, **kwargs)
            kwargs["observation"]["inventory_complete"] = observation_complete
            return [gmail or GMAIL]
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME": home}, clear=True):
            selected = settings().model_copy(update={"self_emails":"customer@example.test" if self_email else ""})
            if suppressed:
                local = state.State(selected.db_path)
                local.suppress("*@example.test" if suppressed == "wildcard" else "customer@example.test")
                local.conn.close()
            with patch.object(config, "load", return_value=selected), patch.object(rpc, "call_sync", side_effect=call), patch.object(gmail_archive, "thread_with", side_effect=provider) as reader, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = cli.cmd_draft_reply(SimpleNamespace(thread_id=ROOT, message="Answer", timeout=10, source_id=source_id))
        return rc, calls, reader

    def test_lost_source_recovers_only_admitted_operation(self):
        key = "fixture-recover-original"
        requests = []
        def call(selected, method, params, **kwargs):
            if method == "system.capabilities":
                return {"mailbox_reply":1}
            self.assertEqual(method, "drafts.compose_reply")
            requests.append(dict(params))
            if params.get("recover_only") and len(requests) == 1:
                raise RuntimeError("reply_operation_not_found")
            return {"ok":True,"state":"completed","request_key":key,"draft_id":"native","current_draft":{"exists":True}}
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ,{"HOME":home},clear=True):
            selected = settings()
            args = SimpleNamespace(thread_id=ROOT, source_id=SOURCE_ID, operation_id=key, timeout=10, message="Answer")
            with patch.object(rpc,"call_sync",side_effect=call), patch.object(interactive_draft,"source",side_effect=ValueError("missing")):
                self.assertEqual(interactive_draft.prepare(selected,args),3)
                self.assertTrue(requests[-1]["recover_only"])
            with patch.object(rpc,"call_sync",side_effect=call), patch.object(interactive_draft,"source",return_value={"id":SOURCE_ID}):
                self.assertEqual(interactive_draft.prepare(selected,args),0)
                self.assertNotIn("recover_only",requests[-1])
            args.source_id=None
            with patch.object(rpc,"call_sync",side_effect=call), patch.object(interactive_draft,"source",side_effect=ValueError("missing")):
                self.assertEqual(interactive_draft.prepare(selected,args),0)
            self.assertEqual(requests[-1], {**requests[-2], "recover_only":True})

    def test_wrong_source_fails_before_generation(self):
        for source,source_id,gmail in (
                ({**SOURCE,'mailbox_address':'foreign@example.test'},None,None),
                (SOURCE,'8ac7571d-778b-46a2-a55b-a08e703149f8',None),
                ({**SOURCE,'is_user_sent':True},None,None),
                (SOURCE,None,{**GMAIL,'from_addr':'foreign@example.test'}),
                (SOURCE,None,{**GMAIL,'references':'<wrong@example.test>'}),
                (SOURCE,None,{**GMAIL,'body':'Different question'}),
                (SOURCE,None,{**GMAIL,'subject':'Different subject'})):
            rc,calls,_=self.invoke(source=source,source_id=source_id,gmail=gmail)
            self.assertEqual(rc,3)
            self.assertNotIn('drafts.compose_reply',calls)

    def test_explicit_old_source_and_ambiguous_latest_are_rejected(self):
        old={**SOURCE,'id':'8ac7571d-778b-46a2-a55b-a08e703149f8','date':'2026-10-21T08:36:44'}
        for sources,source_id in (([old,SOURCE],old['id']),
                                  ([SOURCE,{**old,'date':SOURCE['date']}],None)):
            rc,calls,_=self.invoke(source=sources,source_id=source_id)
            self.assertEqual(rc,3)
            self.assertNotIn('drafts.compose_reply',calls)

    def test_authored_source_comparison_handles_quoted_history(self):
        gmail={**GMAIL,'body':'Please answer.\n\nOn Tuesday someone wrote:\n> Old request'}
        self.assertEqual(self.invoke(gmail=gmail)[0],0)

    def test_incomplete_newer_inbound_never_falls_back_to_older_source(self):
        newer={**SOURCE,'id':'8ac7571d-778b-46a2-a55b-a08e703149f8',
               'date':'2026-10-22T09:36:44'}
        for change in ({'body_plain':''},{'body_plain':None},{'date':None},
                       {'date':'invalid'},{'is_user_sent':None},{'is_user_sent':0},
                       {'from_email':''}):
            rc,calls,reader=self.invoke(source=[SOURCE,{**newer,**change}])
            self.assertEqual(rc,3,change)
            self.assertNotIn('drafts.compose_reply',calls)
            self.assertFalse(any(isinstance(item,tuple) for item in calls))
            reader.assert_not_called()

    def test_exact_archive_quote_cut_retains_complete_provider_tail_in_prompt(self):
        source={**SOURCE,'body_plain':'Please answer.\n\n-----Messaggio originale-----'}
        full=('Please answer.\n\n-----Messaggio originale-----\n'
              'Da: support@fixture.example\nInviato: Yesterday\n'
              'A: customer@example.test\nOggetto: Previous reply\n\n'
              'Prior quoted response.\nAdditional material retained for engine review.')
        gmail={**GMAIL,'body':full}
        self.assertEqual(self.invoke(source=source,gmail=gmail)[0],0)
        for kwargs in ({'observation_complete':False},
                       {'gmail':{**gmail,'body_complete':False}},
                       {'gmail':{**gmail,'body':full.replace('Da: support@fixture.example','Da: foreign@example.test')}},
                       {'gmail':{**gmail,'body':full.replace('Please answer.','Different question.')}}):
            rc,calls,_=self.invoke(source=source,gmail=kwargs.get('gmail',gmail),
                                   observation_complete=kwargs.get('observation_complete',True))
            self.assertEqual(rc,3)
            self.assertNotIn('drafts.compose_reply',calls)

    def test_archive_quote_known_duplicate_email_display_name_is_narrowly_accepted(self):
        source={**SOURCE,'body_plain':'Please answer.\n\n-----Messaggio originale-----'}
        full=('Please answer.\n\n-----Messaggio originale-----\n'
              'Da: support@fixture.example <support@fixture.example>\nInviato: Yesterday\n'
              'A: customer@example.test\nOggetto: Previous reply\n\nPrior quoted response.')
        # Exercise the stricter parser behavior introduced in newer Python.
        original=interactive_draft.parseaddr
        def strict(value):
            return ('','') if value=='support@fixture.example <support@fixture.example>' else original(value)
        with patch.object(interactive_draft,'parseaddr',side_effect=strict):
            self.assertEqual(self.invoke(source=source,gmail={**GMAIL,'body':full})[0],0)
            for bad in ('foreign@example.test <foreign@example.test>',
                        'support@fixture.example <foreign@example.test>',
                        'foreign@example.test <support@fixture.example>'):
                changed=full.replace('support@fixture.example <support@fixture.example>',bad)
                # Simulate strict refusal of malformed duplicated email names.
                with patch.object(interactive_draft,'parseaddr',side_effect=lambda value: ('','') if value==bad else strict(value)):
                    rc,calls,_=self.invoke(source=source,gmail={**GMAIL,'body':changed})
                self.assertEqual(rc,3,bad)
                self.assertNotIn('drafts.compose_reply',calls)

    def test_self_and_suppression_fail_before_generation(self):
        for kwargs in ({'self_email':True},{'suppressed':True},{'suppressed':'wildcard'}):
            rc,calls,reader=self.invoke(**kwargs)
            self.assertEqual(rc,3)
            self.assertNotIn('drafts.compose_reply',calls)
            reader.assert_not_called()

    def test_real_reader_fetch_gap_or_material_body_tail_prevents_generation(self):
        @header_batches
        class IMAP:
            def __init__(self, body, fail_newest=False, divergent=False):
                self.body, self.fail_newest, self.divergent = body, fail_newest, divergent
            def select(self, *a, **kw):
                return 'OK', [b'2']
            def uid(self, command, *args):
                if command == 'SEARCH':
                    return 'OK', [b'1 2' if self.fail_newest else b'1']
                if self.fail_newest and args[0] == b'2':
                    return 'NO', [None]
                msg=EmailMessage()
                msg['From']='customer@example.test'
                msg['To']='support@fixture.example'
                msg['Subject']='Question'
                msg['Message-ID']=TARGET
                msg['References']=ROOT
                msg['Date']='Thu, 22 Oct 2026 08:36:44 +0000'
                msg.set_content(self.body)
                if self.divergent:
                    msg.add_alternative('<p>Please answer.</p><p>Additional material request.</p>',subtype='html')
                return 'OK', [(b'1 (X-GM-LABELS () BODY[] {99}',msg.as_bytes()), b')']
            def logout(self):
                pass
        for body,failed,divergent in (('Please answer.',True,False),
                            ('a'*4000+' New material request after clipped prefix.',False,False),
                            ('a'*65537,False,False)):
            source={**SOURCE,'body_plain':body[:4000] if len(body)>4000 else body}
            with patch.object(gmail_archive,'_imap',return_value=IMAP(body,failed,divergent)), \
                 patch.object(gmail_archive,'_find_folder',return_value='All Mail'):
                rc,calls,_=self.invoke(source=source,real_reader=True)
            self.assertEqual(rc,3)
            self.assertNotIn('drafts.compose_reply',calls)

    def test_real_reader_default_body_and_rows_remain_unchanged(self):
        msg=EmailMessage()
        msg.set_content('a'*5000)
        default,_=gmail_archive._body_and_attachments(msg)
        observed={}
        full,_=gmail_archive._body_and_attachments(msg,limit=65536,observation=observed)
        self.assertEqual(default,'a'*4000)
        self.assertEqual(full,'a'*5000)
        self.assertTrue(observed['body_complete'])

    def test_equivalent_mime_alternatives_and_html_only_are_complete(self):
        for plain,html in (('Please answer.\nSecond question.',
                            '<p>Please answer.</p> <p>Second question.</p>'),
                           (None,'<p>HTML only request.</p>')):
            msg=EmailMessage()
            if plain is None:
                msg.set_content(html,subtype='html')
            else:
                msg.set_content(plain)
                msg.add_alternative(html,subtype='html')
            observed={}
            body,_=gmail_archive._body_and_attachments(msg,limit=65536,observation=observed)
            self.assertTrue(observed['body_complete'])
            self.assertTrue(body)

    def test_real_reader_newer_reply_with_only_in_reply_to_blocks_stale_source(self):
        @header_batches
        class IMAP:
            def select(self,*a,**kw):
                return 'OK',[b'2']
            def uid(self,command,*args):
                if command=='SEARCH':
                    return 'OK',[b'1 2']
                newer=args[0]==b'2'
                msg=EmailMessage()
                msg['From']='customer@example.test'
                msg['To']='support@fixture.example'
                msg['Subject']='Question'
                msg['Message-ID']='<newest@example.test>' if newer else TARGET
                msg['In-Reply-To']=ROOT
                msg['Date']='Thu, 22 Oct 2026 09:36:44 +0000' if newer else 'Thu, 22 Oct 2026 08:36:44 +0000'
                msg.set_content('New request.' if newer else 'Please answer.')
                return 'OK',[(b'1 (X-GM-LABELS () BODY[] {99}',msg.as_bytes()),b')']
            def logout(self):
                pass
        with patch.object(gmail_archive,'_imap',side_effect=lambda s:IMAP()), \
             patch.object(gmail_archive,'_find_folder',return_value='All Mail'):
            observed={}
            rows=gmail_archive.thread_with(settings(),'customer@example.test',observation=observed)
            self.assertTrue(observed['complete'])
            self.assertEqual(rows[0]['in_reply_to'],ROOT)
            default=gmail_archive.thread_with(settings(),'customer@example.test')
            self.assertNotIn('in_reply_to',default[0])
            rc,calls,_=self.invoke(real_reader=True)
        self.assertEqual(rc,3)
        self.assertNotIn('drafts.compose_reply',calls)
        self.assertNotIn('drafts.compose_reply',calls)

    def test_real_root_inventory_covers_other_participants_and_ignores_unrelated_body_defects(self):
        test=self
        @header_batches
        class IMAP:
            def __init__(self,historical):
                self.historical=historical
            def select(self,*a,**kw):
                return 'OK',[b'2']
            def uid(self,command,*args):
                if command=='SEARCH':
                    # Address search alone cannot discover a reply to support
                    # from another participant who omitted the initial sender.
                    test.assertTrue('HEADER' in args or 'SINCE' in args)
                    test.assertNotIn('FROM',args)
                    if 'HEADER' in args:
                        test.assertIn('IN-REPLY-TO',args)
                    return 'OK',[b'1 2']
                second=args[0]==b'2'
                msg=EmailMessage()
                msg['From']='colleague@example.test' if second and not self.historical else 'customer@example.test'
                msg['To']='support@fixture.example'
                msg['Subject']='Question'
                msg['Message-ID']='<other@example.test>' if second else TARGET
                msg['References']=('<unrelated@example.test> '+ROOT) if second and self.historical else ROOT
                msg['Date']=('Wed, 21 Oct 2026 08:36:44 +0000' if self.historical else 'Thu, 22 Oct 2026 09:36:44 +0000') if second else 'Thu, 22 Oct 2026 08:36:44 +0000'
                msg.set_content('Historical response.' if second and self.historical else ('Cancel request.' if second else 'Please answer.'))
                if second and self.historical:
                    msg.add_alternative('<p>Divergent old HTML body.</p>',subtype='html')
                return 'OK',[(b'1 (X-GM-LABELS () BODY[] {99}',msg.as_bytes()),b')']
            def logout(self):
                pass
        for historical in (False,True):
            with patch.object(gmail_archive,'_imap',side_effect=lambda s:IMAP(historical)), \
                 patch.object(gmail_archive,'_find_folder',return_value='All Mail'):
                observed={}
                rows=gmail_archive.thread_with(settings(),'customer@example.test',thread_root=ROOT,
                                               observation=observed,body_limit=65536)
                self.assertTrue(observed['inventory_complete'])
                self.assertTrue(observed['complete'])
                self.assertEqual(len(rows),2)
                rc,calls,_=self.invoke(real_reader=True)
            self.assertEqual(rc,0 if historical else 3)
            if historical:
                self.assertIn('drafts.compose_reply',calls)
            else:
                self.assertNotIn('drafts.compose_reply',calls)
                self.assertNotIn('drafts.compose_reply',calls)

    def test_real_literal_header_search_finds_escaped_newer_reply(self):
        from html import escape
        from cs.thread_key import thread_key
        test=self
        @header_batches
        class IMAP:
            def __init__(self,root):
                self.messages={}
                for uid,newer in ((b'1',False),(b'2',True)):
                    msg=EmailMessage()
                    msg['From']='customer@example.test'
                    msg['To']='support@fixture.example'
                    msg['Subject']='Question'
                    msg['Message-ID']='<newest@example.test>' if newer else TARGET
                    msg['References']=escape(root,quote=True) if newer else root
                    msg['Date']='Thu, 22 Oct 2026 09:36:44 +0000' if newer else 'Thu, 22 Oct 2026 08:36:44 +0000'
                    msg.set_content('Changed request.' if newer else 'Please answer.')
                    self.messages[uid]=msg
            def select(self,*a,**kw):
                return 'OK',[b'2']
            def uid(self,command,*args):
                if command=='SEARCH':
                    if 'SINCE' in args:
                        return 'OK',[b' '.join(self.messages)]
                    tokens=[arg[1:-1] for arg in args if isinstance(arg,str) and arg.startswith('"')]
                    test.assertTrue(tokens)
                    matches=[uid for uid,msg in self.messages.items() if any(
                        token.lower() in str(msg.get(header) or '').lower()
                        for token in tokens for header in ('Message-ID','References','In-Reply-To'))]
                    return 'OK',[b' '.join(matches)]
                return 'OK',[(b'1 (X-GM-LABELS () BODY[] {99}',self.messages[args[0]].as_bytes()),b')']
            def logout(self):
                pass
        for root in (ROOT,'<a&b\'"@example.test>'):
            with patch.object(gmail_archive,'_imap',side_effect=lambda s:IMAP(root)), \
                 patch.object(gmail_archive,'_find_folder',return_value='All Mail'):
                observed={}
                rows=gmail_archive.thread_with(settings(),'customer@example.test',thread_root=root,
                                               observation=observed,body_limit=65536)
                self.assertEqual(len(rows),2)
                self.assertEqual(thread_key(rows[0]['message_id'],rows[0]['references']),root)
                if root==ROOT:
                    rc,calls,_=self.invoke(real_reader=True)
                    self.assertEqual(rc,3)
                    self.assertNotIn('drafts.compose_reply',calls)
                    self.assertNotIn('drafts.compose_reply',calls)

    def test_real_reader_ambiguous_identity_headers_stop_before_generation(self):
        @header_batches
        class IMAP:
            def __init__(self,ambiguous):
                self.ambiguous=ambiguous
            def select(self,*a,**kw):
                return 'OK',[b'2']
            def uid(self,command,*args):
                if command=='SEARCH':
                    # Header search sees every field occurrence, unlike get().
                    return 'OK',[b'1 2']
                newer=args[0]==b'2'
                msg=EmailMessage()
                msg['From']='customer@example.test'
                msg['To']='support@fixture.example'
                msg['Subject']='Question'
                msg['Message-ID']='<newest@example.test>' if newer else TARGET
                msg['References']=ROOT
                msg['Date']='Thu, 22 Oct 2026 09:36:44 +0000' if newer else 'Thu, 22 Oct 2026 08:36:44 +0000'
                msg.set_content('Changed request.' if newer else 'Please answer.')
                raw=msg.as_bytes()
                if newer:
                    if self.ambiguous=='multiple-from':
                        raw=raw.replace(b'From: customer@example.test',b'From: customer@example.test, other@example.test',1)
                    else:
                        values={'References':'<unrelated@example.test>',
                                'Message-ID':'<different@example.test>',
                                'In-Reply-To':'<other@example.test>',
                                'From':'other@example.test','Date':'Wed, 21 Oct 2026 08:36:44 +0000',
                                'Subject':'Other subject'}
                        header=self.ambiguous.encode()+b': '
                        extra=header+values[self.ambiguous].encode()+b'\n'
                        if self.ambiguous=='In-Reply-To':
                            raw=b'In-Reply-To: '+ROOT.encode()+b'\n'+raw
                        raw=extra+raw
                return 'OK',[(b'1 (X-GM-LABELS () BODY[] {99}',raw),b')']
            def logout(self):
                pass
        for header in ('References','Message-ID','In-Reply-To','From','Date','Subject','multiple-from'):
            with patch.object(gmail_archive,'_imap',side_effect=lambda s:IMAP(header)), \
                 patch.object(gmail_archive,'_find_folder',return_value='All Mail'):
                observed={}
                gmail_archive.thread_with(settings(),'customer@example.test',thread_root=ROOT,
                                          observation=observed,body_limit=65536)
                self.assertFalse(observed['inventory_complete'],header)
                rc,calls,_=self.invoke(real_reader=True)
            self.assertEqual(rc,3,header)
            self.assertNotIn('drafts.compose_reply',calls)

    def window_invoke(self,mode,**kwargs):
        imap=WindowIMAP(mode)
        with patch.object(gmail_archive,'_imap',return_value=imap), \
             patch.object(gmail_archive,'_find_folder',return_value='All Mail'):
            result=self.invoke(real_reader=True,**kwargs)
        return result,imap

    def test_real_date_window_inventory_ignores_broken_reference_index(self):
        (rc,calls,_),imap=self.window_invoke('ordinary')
        self.assertEqual(rc,0)
        self.assertTrue(imap.searches)
        self.assertTrue(all('SINCE' in query for query in imap.searches))
        self.assertTrue(all(query[-1]=='21-Oct-2026' for query in imap.searches))
        self.assertEqual(imap.body_uids,[b'1'])
        self.assertIn('drafts.compose_reply',calls)

    def test_real_date_window_catches_new_participant_and_later_arrival_with_older_date(self):
        for mode in ('participant','older-date'):
            (rc,calls,_),imap=self.window_invoke(mode)
            self.assertEqual(rc,3,mode)
            self.assertEqual(set(imap.body_uids),{b'1',b'3'})
            self.assertNotIn('drafts.compose_reply',calls)

    def test_real_date_window_requires_exact_batch_uid_coverage(self):
        (rc,calls,_),imap=self.window_invoke('uidgap')
        self.assertEqual(rc,3)
        self.assertEqual(imap.body_uids,[])
        self.assertNotIn('drafts.compose_reply',calls)
        self.assertNotIn('drafts.compose_reply',calls)

    def test_complete_divergent_html_reaches_prompt_and_total_material_is_bounded(self):
        (rc,calls,_),_=self.window_invoke('html',expected_material=(
            'Please answer.','Additional HTML request.','href="https://example.test/account"'))
        self.assertEqual(rc,0)
        self.assertEqual(calls.count('drafts.compose_reply'), 1)
        (rc,calls,_),_=self.window_invoke('overflow')
        self.assertEqual(rc,3)
        self.assertNotIn('drafts.compose_reply',calls)
        self.assertNotIn('drafts.compose_reply',calls)


if __name__=='__main__':
    unittest.main()
