"""Complete draft inventory and per-root evidence contracts, without network calls."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cs import draft_state, gmail_drafts


class Inventory(unittest.TestCase):
    def setUp(self):
        self.obs = dict(version=1, complete=True, search_complete=True,
                        expected_uids=['1'], observed_uids=['1'], uidvalidity='6')
        self.gmail = [dict(uid='1', uidvalidity='6')]
        self.engine = [dict(id='draft-one')]
        self.rows = [dict(gmail_uid='1', gmail_uidvalidity='6', engine_id='draft-one', workset_hold_reasons=[])]

    def proof(self):
        return draft_state.inventory_proof(self.gmail, self.engine, self.rows, self.obs)

    def test_exact_identity_inventory(self):
        self.assertTrue(self.proof()['complete'])
        self.assertEqual(len(self.proof()['identity_sha256']), 64)
        self.rows[0]['workset_hold_reasons'] = ['mailbox_unreadable']
        self.assertTrue(self.proof()['complete'])

    def test_coverage_failures(self):
        for key, value in [('complete', False), ('search_complete', False), ('uidvalidity', None), ('observed_uids', [])]:
            with self.subTest(key=key):
                obs = dict(self.obs, **{key: value})
                self.assertFalse(draft_state.inventory_proof(self.gmail, self.engine, self.rows, obs)['complete'])

    def test_no_drop_duplicate_or_foreign_identity(self):
        variants = [[], self.rows * 2, [dict(self.rows[0], engine_id='foreign')],
                    [dict(self.rows[0], gmail_uid='9')], [dict(self.rows[0], gmail_uidvalidity='7')],
                    [dict(self.rows[0], workset_hold_reasons=['unknown'])]]
        for rows in variants:
            with self.subTest(rows=rows):
                self.assertFalse(draft_state.inventory_proof(self.gmail, self.engine, rows, self.obs)['complete'])
        self.assertFalse(draft_state.inventory_proof(self.gmail * 2, self.engine, self.rows, self.obs)['complete'])
        self.assertFalse(draft_state.inventory_proof(self.gmail, self.engine * 2, self.rows, self.obs)['complete'])

    def test_empty_inventory(self):
        obs = dict(self.obs, expected_uids=[], observed_uids=[])
        self.assertTrue(draft_state.inventory_proof([], [], [], obs)['complete'])

    def test_actual_reconcile_holds_failures_without_parsing_notes(self):
        settings = SimpleNamespace(engine_owner_uid='owner')
        engine = [dict(id='one', to_addresses=['person@example.test'], thread_id='<root@test>',
                       created_at='2026-10-18T00:00:00Z', body='A sufficiently long authored response that must be compared against Sent.')]
        def delivered(*args):
            return None, 'opaque failure without a recognized keyword'
        rows, notes = draft_state.reconcile(settings, [], engine, inbound=lambda *a, **kw: [],
            sent=lambda *a, **kw: [], settled=lambda *a: ({}, None), delivered=delivered)
        self.assertEqual(rows[0]['workset_hold_reasons'], ['sent_body_unavailable'])
        self.assertTrue(notes)
        rows, notes = draft_state.reconcile(settings, [], engine, inbound=lambda *a, **kw: [],
            sent=lambda *a, **kw: [], settled=lambda *a: ({}, 'opaque error'), delivered=lambda *a: (None, None))
        self.assertIn('verdict_unavailable', rows[0]['workset_hold_reasons'])


    def test_policy_notes_do_not_create_read_failures(self):
        settings = SimpleNamespace(engine_owner_uid='owner')
        engine = [dict(id='one', to_addresses=['person@example.test'], thread_id='<root@test>',
                       created_at='2026-10-18T00:00:00Z', body='Short reply')]
        def bulk(unreadable, skipped, notes):
            def read(*args):
                skipped['self'] = 'deliberate policy skip'
                notes.append('BCC-only match reported and not counted')
                return {}, {}
            return read
        with patch.object(draft_state, '_bulk_across', bulk):
            rows, notes = draft_state.reconcile(settings, [], engine,
                settled=lambda *a: ({}, None), delivered=lambda *a: (None, None))
        self.assertTrue(notes)
        self.assertEqual(rows[0]['workset_hold_reasons'], [])

    def test_missing_context_and_body_remain_visible_and_held(self):
        rows, _ = draft_state.reconcile(SimpleNamespace(engine_owner_uid='owner'), [], [dict(id='one')],
            inbound=lambda *a, **kw: [], sent=lambda *a, **kw: [], settled=lambda *a: ({}, None))
        self.assertEqual(set(rows[0]['workset_hold_reasons']),
                         {'body_unavailable', 'date_missing', 'recipient_missing', 'root_missing'})


class MailboxProtocol(unittest.TestCase):
    class Session:
        untagged_responses = {'UIDVALIDITY': [b'6']}
        def __init__(self, search=('OK', [b'']), fetch_ok=True):
            self.search = search
            self.fetch_ok = fetch_ok
        def list(self):
            return 'OK', [b'(\\Drafts) "/" "Drafts"']
        def select(self, folder, readonly):
            assert readonly
            return 'OK', [b'0']
        def uid(self, method, *args):
            if method == 'SEARCH':
                return self.search
            if not self.fetch_ok:
                return 'NO', []
            raw = b'To: person@example.test\r\nSubject: A\r\n\r\nHello\r\n'
            return 'OK', [(b'1 (RFC822.SIZE ' + str(len(raw)).encode() + b')', raw)]
        def logout(self):
            pass

    def test_empty_and_full_search_and_failed_reads(self):
        for search, fetch_ok, expected in [(('OK', [b'']), True, True),
                (('OK', [b'1']), True, True), (('NO', [b'']), True, False),
                (('OK', [b'1']), False, False)]:
            with self.subTest(search=search, fetch_ok=fetch_ok):
                observation = {}
                with patch.object(gmail_drafts, '_imap', return_value=self.Session(search, fetch_ok)):
                    gmail_drafts.list_drafts(None, observation=observation)
                self.assertEqual(observation['complete'], expected)

    def test_body_fetch_failure_cannot_prove_complete_inventory(self):
        session = self.Session(('OK', [b'1']))
        original = session.uid
        def uid(method, *args):
            if method == 'FETCH' and 'RFC822.SIZE' in args[-1]:
                return 'NO', []
            return original(method, *args)
        session.uid = uid
        observation = {}
        with patch.object(gmail_drafts, '_imap', return_value=session):
            rows = gmail_drafts.list_drafts(None, observation=observation)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['body_complete'])
        self.assertFalse(observation['complete'])


if __name__ == '__main__':
    unittest.main()
