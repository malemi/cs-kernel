"""Strict whole-header identity decoding through Gmail discovery, offline."""
import base64
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cs import draft_state, gmail_drafts, operator_workset
from cs.thread_key import normalize_key, thread_key


ROOT = '<' + 'a' * 61 + '@example.test>'
OTHER = '<distinct@example.test>'


def encoded(value, charset='utf-8'):
    return '=?' + charset + '?B?' + base64.b64encode(value.encode()).decode() + '?='


class IdentityHeaders(unittest.TestCase):
    def test_complete_header_before_tokenization(self):
        raw = encoded(ROOT[:50]) + '\r\n ' + encoded(ROOT[50:])
        for source in ('references', 'in_reply_to'):
            self.assertEqual(thread_key(None, **{source: raw}), ROOT)
        self.assertEqual(normalize_key(raw), ROOT)

    def test_normal_html_and_ordered_distinct_ids(self):
        for root in (ROOT, ROOT.replace('<', '&lt;').replace('>', '&gt;'), encoded(ROOT)):
            self.assertEqual(thread_key(None, root + ' ' + OTHER), ROOT)
            self.assertEqual(thread_key(None, OTHER + ' ' + root), OTHER)
        self.assertEqual(thread_key(None, encoded(ROOT + ' ' + OTHER)), ROOT)
        self.assertEqual(thread_key(None, None, encoded(ROOT + ' ' + OTHER)), ROOT + ' ' + OTHER)
        self.assertNotEqual(thread_key(None, encoded(ROOT)), thread_key(None, encoded(ROOT.replace('aaa', 'aab', 1))))
        self.assertEqual(thread_key(None, '=?us-ascii?Q?=3Croot=40example.test=3E?='), '<root@example.test>')

    def test_malformed_partial_unknown_and_ambiguous_fail_closed(self):
        bad = [encoded(ROOT[:50]), encoded(ROOT[1:]), encoded(ROOT[:-1]),
               encoded(ROOT, 'unknown-identity-charset'), '=?utf-8?B?%%%%?=',
               encoded(ROOT)[:-2], '=?utf-8?Q?=GG?=',
               encoded(ROOT) + ' =?broken', encoded(ROOT) + ' suffix',
               '<prefix' + encoded(ROOT), encoded(ROOT + OTHER),
               '=?utf-8?B?/w==?=', '=?utf-8?B?Zh==?=',
               encoded(ROOT) + ' ' * 16384,
               encoded(ROOT[:30]) + encoded(ROOT[30:]),
               encoded(ROOT) + '\x00', '=?utf-8?B??=']
        for raw in bad:
            for source in ('references', 'in_reply_to'):
                with self.subTest(source=source, shape=bad.index(raw)):
                    self.assertEqual(thread_key(OTHER, **{source: raw}), '')
                    self.assertEqual(normalize_key(raw), '')

    def discover(self, references):
        raw = ('To: person@example.test\r\nDate: Mon, 26 Oct 2026 00:00:00 +0000\r\n'
               'Subject: Identity fixture\r\nReferences: ' + references + '\r\n\r\nBody\r\n').encode()
        class Session:
            untagged_responses = {'UIDVALIDITY': [b'6']}
            def list(self):
                return 'OK', [b'(\\Drafts) "/" "Drafts"']
            def select(self, folder, readonly):
                return 'OK', [b'1']
            def uid(self, method, *args):
                if method == 'SEARCH':
                    return 'OK', [b'1']
                return 'OK', [(b'1 (FLAGS (\\Draft) RFC822.SIZE ' + str(len(raw)).encode() + b')', raw)]
            def logout(self):
                pass
        observation = {}
        with patch.object(gmail_drafts, '_imap', return_value=Session()):
            rows = gmail_drafts.list_drafts(None, observation=observation)
        return rows, observation

    def test_real_discovery_and_fail_closed_inventory_retention(self):
        for raw, expected in ((encoded(ROOT[:50]) + ' ' + encoded(ROOT[50:]), ROOT),
                              (encoded(ROOT[:50]), '')):
            rows, observation = self.discover(raw)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['thread_key'], expected)
            reconciled, _ = draft_state.reconcile(SimpleNamespace(engine_owner_uid='owner'), rows, [],
                inbound=lambda *a, **kw: [], sent=lambda *a, **kw: [], settled=lambda *a: ({}, None))
            self.assertEqual(reconciled[0]['thread_key'], expected)
            self.assertEqual('root_missing' in reconciled[0]['workset_hold_reasons'], not bool(expected))
            proof = draft_state.inventory_proof(rows, [], reconciled, observation)
            self.assertTrue(proof['complete'])
            if not expected:
                payload = dict(gmail_drafts=rows, engine_drafts=[], drafts=reconciled,
                               gmail_drafts_observation=observation, drafts_inventory=proof)
                discovery = dict(read_incomplete=None, assignment_incomplete=False,
                                 open=[], resumed=[], human_work=[], assignment_audit=[])
                candidates, held = operator_workset._inventory(discovery, {'review': payload, 'tasks': []}, 'owner')
                self.assertEqual(candidates, {})
                self.assertEqual(held, [dict(thread_key=None, reason='review_evidence_incomplete', source='review')])

    def test_foreign_owner_conflict_is_not_repaired(self):
        rows, _ = self.discover(encoded(ROOT))
        rows[0].update(engine_draft_id='draft-one', engine_owner_uid='foreign')
        reconciled, _ = draft_state.reconcile(SimpleNamespace(engine_owner_uid='owner'), rows, [],
            inbound=lambda *a, **kw: [], sent=lambda *a, **kw: [], settled=lambda *a: ({}, None))
        self.assertIn('identity_conflict', reconciled[0]['workset_hold_reasons'])
        self.assertEqual(len(reconciled), 1)


if __name__ == '__main__':
    unittest.main()
