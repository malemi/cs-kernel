"""Operator send CLI retains scheduled, pause, suppression and exact response boundaries."""

import io
import json
import os
from contextlib import redirect_stdout
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from cs import cli, config, operator_send, task_assignment


class OperatorSendTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        environment = patch.dict(os.environ, {"HOME": self.directory.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.settings = config.Settings(
            email_address="owner@example.test", engine_owner_uid="owner"
        )
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.calls = []
        self.bound = {
            "root": "<root@example.test>",
            "target": "<root@example.test>",
            "recipients": ["customer@example.test"],
            "cc": [],
        }
        self.proof = {
            "complete": True,
            "folder": "Sent",
            "uidvalidity": "1",
            "message_id": "<sent@example.test>",
            "mime_digest": "b" * 64,
            "handle": {
                "folder": "Sent",
                "uidvalidity": "1",
                "uid": "1",
                "raw_fingerprint": "c" * 64,
            },
        }

    def rpc(self, settings, method, params, **kw):
        self.calls.append(method)
        if method == "system.capabilities":
            return {"interactive_exact_send": 1}
        if method == "drafts.operator_send_inspect":
            return {
                "ok": True,
                "owner_id": settings.email_address,
                "owner_uid": "owner",
                "draft_id": "draft",
                "draft": {"status": "draft"},
                "binding": self.bound,
                "expected_snapshot": "a" * 64,
            }
        if method == "drafts.operation_status":
            return {"ok": False, "operation": None}
        assert method == "drafts.send_operator"
        return {
            "version": 1,
            "ok": True,
            "effect_certainty": "verified",
            "cleanup_certainty": "not-dispatched",
            "audit_reason": "explicit_operator_request",
            "achieved_stages": ["engine-saved", "sent"],
            "provider_handles": self.proof,
            "draft_id": "draft",
            "operation_id": params["operation_id"],
            "owner_id": settings.email_address,
            "owner_uid": "owner",
            "expected_snapshot": "a" * 64,
            "root": self.bound["root"],
            "state": "sent-with-cleanup-pending",
            "cause": "exact_sent_verified",
            "next_action": "retire-sent-mirror",
        }

    def run_cli(self, args):
        with patch.object(cli.config, "load", return_value=self.settings), patch.object(
            operator_send.rpc, "call_sync", self.rpc
        ), patch.object(task_assignment, "operator_guard") as guard, redirect_stdout(
            io.StringIO()
        ) as out:
            code = cli.main(args)
        return code, out.getvalue(), guard

    def test_exact_cli_no_chat_or_generation(self):
        code, out, guard = self.run_cli(
            ["draft-send", "draft", "--operator-request", "--json"]
        )
        self.assertEqual(code, 5)
        self.assertEqual(json.loads(out)["cause"], "exact_sent_verified")
        self.assertEqual(self.calls[-1], "drafts.send_operator")
        guard.assert_called_once()

    def test_all_scheduled_markers_refuse_even_abbreviated_flag(self):
        for key in (
            "CS_OPERATOR_HEADLESS",
            "CS_HEADLESS_SEND",
            "CS_OPERATOR_HEALTH_CONTEXT",
        ):
            with patch.dict(os.environ, {key: "1"}, clear=True):
                code, out, _ = self.run_cli(
                    ["draft-send", "draft", "--operator-req", "--json"]
                )
                self.assertEqual(code, 3)
                self.assertEqual(
                    json.loads(out)["cause"], "operator_request_not_interactive"
                )
        self.assertFalse(self.calls)

    def test_pause_and_suppression(self):
        self.settings.pause_path.touch()
        code, out, _ = self.run_cli(
            ["draft-send", "draft", "--operator-request", "--json"]
        )
        self.assertEqual(json.loads(out)["cause"], "paused")
        self.settings.pause_path.unlink()
        from cs.state import State

        local = State(self.settings.db_path)
        local.conn.execute(
            "INSERT INTO do_not_contact(email,reason,added_at) VALUES ('customer@example.test','fixture','2026-11-05')"
        )
        local.conn.commit()
        local.conn.close()
        code, out, _ = self.run_cli(
            ["draft-send", "draft", "--operator-request", "--json"]
        )
        self.assertEqual(json.loads(out)["cause"], "suppressed_recipient")
        self.assertNotIn("drafts.send_operator", self.calls)

    def existing(self, stage="dispatch_possible"):
        return {
            "owner_uid": "owner",
            "draft_id": "draft",
            "operation_id": "existing",
            "operation_type": "send",
            "canonical_root": self.bound["root"],
            "expected_snapshot": "a" * 64,
            "binding": {
                **self.bound,
                "transport": {
                    "message_id": self.proof["message_id"],
                    "mime_digest": self.proof["mime_digest"],
                },
            },
            "stage": stage,
            "active": stage not in {"completed", "not_dispatched"},
            "version": 2,
        }

    def test_existing_operation_bypasses_only_fresh_guards(self):
        original = self.rpc
        for guard_name in ("pause", "self", "suppression", "assignment"):
            with self.subTest(guard=guard_name):
                self.calls.clear()

                def call(settings, method, params, **kw):
                    if method == "drafts.operation_status":
                        self.calls.append(method)
                        return {"ok": True, "operation": self.existing()}
                    return original(settings, method, params, **kw)

                with patch.object(self, "rpc", call), patch.object(
                    task_assignment,
                    "operator_guard",
                    side_effect=AssertionError("fresh guard"),
                ), patch.object(
                    operator_send.state,
                    "State",
                    side_effect=AssertionError("fresh suppression"),
                ):
                    self.settings.pause_path.touch()
                    code, out, guard = self.run_cli(
                        [
                            "draft-send",
                            "draft",
                            "--operator-request",
                            "--operation-id",
                            "existing",
                            "--json",
                        ]
                    )
                    self.assertEqual(code, 5, out)
                    guard.assert_not_called()
                    self.assertLess(
                        self.calls.index("drafts.operation_status"),
                        self.calls.index("drafts.operator_send_inspect"),
                    )
                self.settings.pause_path.unlink()

    def test_unknown_existing_lookup_errors_preserve_uncertainty(self):
        original = self.rpc
        for method in (
            "system.capabilities",
            "drafts.operation_status",
            "drafts.operator_send_inspect",
        ):

            def call(settings, name, params, **kw):
                if name == method:
                    raise TimeoutError()
                if name == "drafts.operation_status":
                    return {"ok": True, "operation": self.existing()}
                return original(settings, name, params, **kw)

            with patch.object(self, "rpc", call):
                code, out, _ = self.run_cli(
                    [
                        "draft-send",
                        "draft",
                        "--operator-request",
                        "--operation-id",
                        "existing",
                        "--json",
                    ]
                )
                self.assertEqual(code, 3)
                self.assertEqual(json.loads(out)["effect_certainty"], "unknown")

    def test_foreign_existing_identity_never_reconciles(self):
        original = self.rpc
        for key, value in (
            ("owner_uid", "other"),
            ("draft_id", "other"),
            ("operation_type", "publish"),
            ("canonical_root", "<other@example.test>"),
            ("expected_snapshot", True),
            ("version", True),
            ("binding", {}),
        ):
            self.calls.clear()

            def call(settings, method, params, **kw):
                if method == "drafts.operation_status":
                    return {"ok": True, "operation": {**self.existing(), key: value}}
                return original(settings, method, params, **kw)

            with patch.object(self, "rpc", call):
                code, out, _ = self.run_cli(
                    [
                        "draft-send",
                        "draft",
                        "--operator-request",
                        "--operation-id",
                        "existing",
                        "--json",
                    ]
                )
                self.assertEqual(code, 3)
                self.assertEqual(json.loads(out)["effect_certainty"], "unknown")
                self.assertNotIn("drafts.send_operator", self.calls)

    def test_contradictory_and_untyped_outcomes_are_unknown(self):
        original = self.rpc
        for change in (
            {"version": True},
            {"ok": 1},
            {"state": "delivery-unknown", "effect_certainty": "unknown"},
            {"achieved_stages": []},
            {"provider_handles": {}},
            {"cleanup_certainty": "verified"},
            {"effect_certainty": "unknown"},
        ):

            def call(settings, method, params, **kw):
                result = original(settings, method, params, **kw)
                return (
                    {**result, **change} if method == "drafts.send_operator" else result
                )

            with patch.object(self, "rpc", call):
                code, out, _ = self.run_cli(
                    ["draft-send", "draft", "--operator-request", "--json"]
                )
                self.assertEqual(code, 3)
                self.assertEqual(json.loads(out)["effect_certainty"], "unknown")

    def test_cancelled_operation_retains_not_dispatched(self):
        original = self.rpc

        def call(settings, method, params, **kw):
            if method == "drafts.operation_status":
                return {"ok": True, "operation": self.existing("not_dispatched")}
            result = original(settings, method, params, **kw)
            if method == "drafts.send_operator":
                result.update(
                    ok=False,
                    state="send-held",
                    effect_certainty="not-dispatched",
                    achieved_stages=["engine-saved"],
                    next_action="new-explicit-operation",
                    cause="exact_send_not_dispatched",
                )
                result.pop("provider_handles")
            return result

        self.settings.pause_path.touch()
        with patch.object(self, "rpc", call):
            code, out, guard = self.run_cli(
                [
                    "draft-send",
                    "draft",
                    "--operator-request",
                    "--operation-id",
                    "existing",
                    "--json",
                ]
            )
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out)["effect_certainty"], "not-dispatched")
        guard.assert_not_called()

    def test_manual_exception_preserves_automatic_hold(self):
        value = dict(
            actor_uid="owner",
            source_owner_uid="owner",
            thread_key=self.bound["root"],
            task=None,
            state="needs-assignment",
            reason="NEEDS_HUMAN_VERIFICATION",
            hold_auto_reply=True,
            current_message_ids=[self.bound["target"]],
            reply_evidence=[
                dict(
                    complete=True,
                    judgement="MEMBER_ACTIVITY_REQUIRES_HUMAN_VERIFICATION",
                )
            ],
        )
        with patch.object(task_assignment, "project", return_value=value):
            self.assertIs(
                task_assignment.operator_guard(
                    self.settings, self.bound["root"], self.bound["target"]
                ),
                value,
            )
            with self.assertRaises(task_assignment.AssignmentUnavailable):
                task_assignment.guard(self.settings, self.bound["root"])
            value["task"] = {
                "id": "task",
                "revision": 1,
                "state": "assigned",
                "assignee_uid": "other",
            }
            with self.assertRaises(task_assignment.AssignmentUnavailable):
                task_assignment.operator_guard(
                    self.settings, self.bound["root"], self.bound["target"]
                )
        self.assertTrue(value["hold_auto_reply"])


if __name__ == "__main__":
    unittest.main()
