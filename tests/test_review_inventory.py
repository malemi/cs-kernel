"""Complete draft inventory and per-root evidence contracts, without network calls."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cs import draft_state


class Inventory(unittest.TestCase):
    def setUp(self):
        self.raw = [dict(id='draft-one',mailbox_id='mailbox')]
        self.rows = [dict(draft_id='draft-one',mailbox_id='mailbox',workset_hold_reasons=[])]

    def proof(self):
        return draft_state.inventory_proof(self.raw,self.rows)

    def test_exact_identity_inventory(self):
        self.assertTrue(self.proof()['complete'])
        self.assertEqual(len(self.proof()['identity_sha256']), 64)
        self.rows[0]['workset_hold_reasons'] = ['mailbox_unreadable']
        self.assertTrue(self.proof()['complete'])

    def test_coverage_failures(self):
        for raw,reviewed in ((self.raw,[]),(self.raw*2,self.rows),(self.raw,self.rows*2),
                (self.raw,[dict(self.rows[0],mailbox_id='foreign')]),
                (self.raw,[dict(self.rows[0],workset_hold_reasons=['unknown'])])):
            self.assertFalse(draft_state.inventory_proof(raw,reviewed)['complete'])
        self.assertTrue(draft_state.inventory_proof([],[])['complete'])

    def test_actual_reconcile_holds_failures_without_parsing_notes(self):
        settings = SimpleNamespace(engine_owner_uid='owner')
        engine = [dict(id='one', mailbox_id='mailbox', to_addresses=['person@example.test'], thread_id='<root@test>',
                       created_at='Sun, 18 Oct 2026 00:00:00 +0000', body='A sufficiently long authored response that must be compared against Sent.')]
        def delivered(*args):
            return None, 'opaque failure without a recognized keyword'
        rows, notes = draft_state.reconcile(settings, engine, inbound=lambda *a, **kw: [],
            sent=lambda *a, **kw: [], settled=lambda *a: ({}, None), delivered=delivered)
        self.assertEqual(rows[0]['workset_hold_reasons'], ['sent_body_unavailable'])
        self.assertTrue(notes)
        rows, notes = draft_state.reconcile(settings, engine, inbound=lambda *a, **kw: [],
            sent=lambda *a, **kw: [], settled=lambda *a: ({}, 'opaque error'), delivered=lambda *a: (None, None))
        self.assertIn('verdict_unavailable', rows[0]['workset_hold_reasons'])


    def test_policy_notes_do_not_create_read_failures(self):
        settings = SimpleNamespace(engine_owner_uid='owner')
        engine = [dict(id='one', mailbox_id='mailbox', to_addresses=['person@example.test'], thread_id='<root@test>',
                       created_at='Sun, 18 Oct 2026 00:00:00 +0000', body='Short reply')]
        def bulk(unreadable, skipped, notes):
            def read(*args):
                skipped['self'] = 'deliberate policy skip'
                notes.append('BCC-only match reported and not counted')
                return {}, {}
            return read
        with patch.object(draft_state, '_bulk_across', bulk):
            rows, notes = draft_state.reconcile(settings, engine,
                settled=lambda *a: ({}, None), delivered=lambda *a: (None, None))
        self.assertTrue(notes)
        self.assertEqual(rows[0]['workset_hold_reasons'], [])

    def test_missing_context_and_body_remain_visible_and_held(self):
        rows, _ = draft_state.reconcile(SimpleNamespace(engine_owner_uid='owner'), [dict(id='one', mailbox_id='mailbox')],
            inbound=lambda *a, **kw: [], sent=lambda *a, **kw: [], settled=lambda *a: ({}, None))
        self.assertEqual(set(rows[0]['workset_hold_reasons']),
                         {'body_unavailable', 'date_missing', 'recipient_missing', 'root_missing'})




if __name__ == '__main__':
    unittest.main()
