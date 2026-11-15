"""Explicit sent recovery never falls back to local deletion or engine discard."""

import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs import draft_lifecycle as lifecycle


class SentMirrorRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(email_address="owner@example.test", engine_owner_uid="owner")
        self.args = dict(thread_id="<root@example.test>", commit=True,
                         engine_snapshot="a" * 64, gmail_fingerprint="b" * 64,
                         gmail_folder="Drafts", operation_id="operation")
        self.calls = []

    def rpc(self, settings, method, params, **kwargs):
        self.calls.append((method, params))
        if method == "system.capabilities":
            return {"sent_mirror_recovery": 1}
        if method == "drafts.inspect":
            return dict(ok=True, draft_id="draft", owner_id=settings.email_address,
                        engine_owner_uid=settings.engine_owner_uid, expected_snapshot="a" * 64)
        assert method == "drafts.retire_sent_mirror"
        raise TimeoutError()

    def test_timeout_retains_operation_and_uncertainty(self):
        with patch.object(lifecycle.rpc, "call_sync", self.rpc):
            answer = lifecycle.retire_sent_mirror(self.settings, "draft", "1", "7", **self.args)
        self.assertEqual(answer["effect_certainty"], "unknown")
        self.assertEqual(answer["operation_id"], "operation")
        self.assertEqual(answer["draft_id"], "draft")
        self.assertFalse(answer["engine_discarded"])
        self.assertEqual(self.calls[-1][1]["target"], dict(folder="Drafts", uid="1", uidvalidity="7", raw_fingerprint="b" * 64))

    def test_old_engine_is_precisely_unsupported(self):
        with patch.object(lifecycle.rpc, "call_sync", return_value={"sent_mirror_recovery": True}) as rpc:
            answer = lifecycle.retire_sent_mirror(self.settings, "draft", "1", "7", **self.args)
        self.assertEqual(answer["cause"], "sent_mirror_recovery_unsupported")
        self.assertEqual(rpc.call_count, 1)

    def test_missing_preview_or_headless_has_no_rpc(self):
        for environment, changes in (({}, {"operation_id": None}), ({"CS_OPERATOR_HEADLESS": "1"}, {}), ({"CS_HEADLESS_SEND": "1"}, {}), ({"CS_OPERATOR_HEALTH_CONTEXT": "{}"}, {})):
            with patch.dict(os.environ, environment, clear=True), patch.object(lifecycle.rpc, "call_sync") as rpc:
                answer = lifecycle.retire_sent_mirror(self.settings, "draft", "1", "7", **dict(self.args, **changes))
            self.assertFalse(answer["ok"])
            rpc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
