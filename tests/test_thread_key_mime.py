"""Strict whole-header identity decoding through Gmail discovery, offline."""
import base64
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cs import draft_state, operator_workset
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

    def test_mailbox_draft_retains_malformed_root_hold(self):
        for references, expected in ((encoded(ROOT[:50]) + ' ' + encoded(ROOT[50:]), ROOT),
                                     (encoded(ROOT[:50]), '')):
            rows = [dict(id='native', mailbox_id='box', references=references,
                         created_at='Mon, 26 Oct 2026 00:00:00 +0000',
                         to_addresses=['person@example.test'], body='Body')]
            reviewed, _ = draft_state.reconcile(SimpleNamespace(engine_owner_uid='owner'), rows,
                inbound=lambda *a, **kw: [], sent=lambda *a, **kw: [], settled=lambda *a: ({}, None))
            self.assertEqual(reviewed[0]['thread_key'], expected)
            self.assertEqual('root_missing' in reviewed[0]['workset_hold_reasons'], not bool(expected))
            self.assertTrue(draft_state.inventory_proof(rows, reviewed)['complete'])


if __name__ == '__main__':
    unittest.main()
