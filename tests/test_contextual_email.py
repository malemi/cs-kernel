#!/usr/bin/env python3
"""Actual CLI/EngineClient authenticated frames bind known contextual effects."""

import asyncio
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from cs import cli, config, rpc, campaign, contextual_email

ROOT = "<original@customer.example>"
TARGET = "<latest@customer.example>"
DRAFT_ID = "452ddb83-69c9-479c-98ab-b6f690eab2a7"


def settings():
    return config.Settings(email_address="support@fixture.example", engine_owner_uid="fixture-owner",
                           engine_ws_url="wss://engine.example", cs_triage_mode="send")


class Wire:
    def __init__(self, capability=True):
        self.frames = []
        self.capability = capability
        self.handshakes = []
    async def connect(self, url, **kwargs):
        self.handshakes.append((url, kwargs))
        assert kwargs["additional_headers"] == {"Authorization": "Bearer fixture-id-token"}
        assert url.endswith("/ws/fixture-owner")
        self.queue = asyncio.Queue()
        return self
    def __aiter__(self):
        return self
    async def __anext__(self):
        return await self.queue.get()
    async def emit(self, payload):
        await self.queue.put(json.dumps(payload))
    async def send(self, raw):
        frame = json.loads(raw)
        self.frames.append(frame)
        method = frame["method"]
        if method == "system.capabilities":
            result = {"assignment_draft_policy": 1}
            if self.capability:
                result["contextual_email_policy"] = 1
            await self.emit({"id": frame["id"], "result": result})
        elif method == "drafts.list":
            await self.emit({"id": frame["id"], "result": [{"id": DRAFT_ID,
                "status": frame["params"]["status"], "thread_id": ROOT, "in_reply_to": TARGET,
                "references": [ROOT], "to_addresses": ["customer@example.test"], "subject": "Reply",
                "sent_message_id": "<sent@example.test>"}]})
        elif method == "tasks.assignment.project":
            from assignment_fixture import normal_projection
            await self.emit({"id": frame["id"], "result": normal_projection(settings(), frame["params"])})
        elif method == "chat.send":
            self.chat_id = frame["id"]
            await self.emit({"method": "chat.pending_approval", "params": {
                "name": "send_draft", "tool_use_id": "send-one", "input": {"draft_id": DRAFT_ID}}})
        elif method == "chat.approve":
            assert frame["params"] == {"tool_use_id": "send-one", "mode": "once"}
            await self.emit({"id": frame["id"], "result": {"ok": True}})
            await self.emit({"id": self.chat_id, "result": {"response": "checked"}})
        else:
            raise AssertionError(method)
    async def close(self):
        pass
    def patches(self):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(rpc.websockets, "connect", self.connect))
        stack.enter_context(patch.object(rpc.auth, "get_id_token", return_value="fixture-id-token"))
        stack.enter_context(patch.object(config, "load", return_value=settings()))
        stack.enter_context(patch.object(cli, "_retire_sent_mirrors", return_value={"retired": [], "skipped": []}))
        return stack


class ContextualEmail(unittest.TestCase):
    def test_launcher_equivalent_cli_payload_and_approval(self):
        wire = Wire()
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()):
            rc = cli.main(["chat", "Reply to this exact inbound", "--allow", "send_draft",
                           "--thread-id", ROOT, "--reply-to", TARGET, "--source-id", "engine-source-id"])
        self.assertEqual(rc, 0)
        self.assertEqual([f["method"] for f in wire.frames], ["system.capabilities", "chat.send", "chat.approve"])
        payload = wire.frames[1]["params"]
        self.assertEqual(payload["email_context"], {"thread_key": ROOT, "target_message_id": TARGET,
                                                   "source_email_id": "engine-source-id"})
        self.assertEqual(payload["contextual_email_policy_version"], 1)
        print(json.dumps({"case": "launcher-equivalent", "handshakes": wire.handshakes, "frames": wire.frames}))

    def test_old_scoped_capability_does_not_admit_changed_generic_workflow(self):
        wire = Wire(False)
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = cli.main(["chat", "Reply", "--allow", "send_draft", "--thread-id", ROOT, "--reply-to", TARGET])
        self.assertEqual(rc, 3)
        self.assertEqual([f["method"] for f in wire.frames], ["system.capabilities"])

    def test_sourcefree_generic_chat_keeps_separate_composition(self):
        wire = Wire()
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["chat", "Compose a new independent message", "--allow", "send_draft"]), 0)
        self.assertNotIn("email_context", wire.frames[1]["params"])

    def test_exact_draft_send_payload_is_structurally_bound(self):
        wire = Wire()
        with wire.patches():
            result = asyncio.run(rpc.chat(settings(), "Send exact", allow_tools={"send_draft"},
                                          email_context={"draft_id": DRAFT_ID}))
        self.assertEqual(wire.frames[1]["params"]["email_context"], {"draft_id": DRAFT_ID})
        self.assertEqual(result["approvals"][0]["mode"], "once")

    def test_actual_exact_draft_cli_binds_authenticated_chat_and_verifies_sent(self):
        wire = Wire()
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["draft-send", DRAFT_ID]), 0)
        chat = next(frame for frame in wire.frames if frame["method"] == "chat.send")
        self.assertEqual(chat["params"]["email_context"], {"draft_id": DRAFT_ID})
        self.assertEqual(wire.frames[-1]["method"], "drafts.list")
        self.assertEqual(wire.frames[-1]["params"], {"status": "sent"})
        self.assertTrue(all(handshake[1]["additional_headers"]["Authorization"] == "Bearer fixture-id-token"
                            for handshake in wire.handshakes))

    def test_context_cannot_be_routed_to_direct_classifier(self):
        with self.assertRaises(ValueError):
            asyncio.run(rpc.chat(settings(), "classify", role="triage", email_context={"thread_key": ROOT}))

    def test_contextual_campaign_uses_exact_engine_lifecycle(self):
        contact = {"id": "contact", "email": "customer@example.test", "state": "drafted",
                   "draft_subject": "Reply", "draft_body": "body", "dossier": {
                       "thread_id": ROOT, "target_message_id": TARGET, "engine_draft_id": DRAFT_ID}}
        draft = {"id": DRAFT_ID, "thread_id": ROOT, "in_reply_to": TARGET, "references": [ROOT],
                 "to_addresses": [contact["email"]], "subject": "Reply", "body": "body"}
        updates = []
        def call(s, method, params):
            if method == "system.capabilities":
                return {"contextual_email_policy": 1}
            if method == "drafts.list":
                return [{**draft, "status": params["status"], "sent_message_id": "<sent@example.test>"}]
            if method == "campaign.update_contact":
                updates.append(params)
                return {"ok": True}
            raise AssertionError(method)
        wire = Wire()
        with wire.patches(), patch.object(rpc, "call_sync", side_effect=call), \
             patch.object(campaign, "_get_contact", return_value=contact), \
             patch.object(campaign, "_finished_send_refusal", return_value=None), \
             patch.object(campaign, "_sent_threads_to", return_value=([], [])), \
             patch.object(campaign, "_escalation_block", return_value=None), \
             patch.object(campaign, "_pause_active", return_value=False), \
             patch.object(campaign, "_record_send") as record, \
             patch("cs.send_mail.send", side_effect=AssertionError("contextual cs SMTP bypass")):
            result = campaign.send_draft(settings(), "contact", commit=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["message_id"], "<sent@example.test>")
        self.assertEqual(wire.frames[1]["params"]["email_context"], {
            "draft_id": DRAFT_ID, "thread_key": ROOT, "target_message_id": TARGET})
        self.assertEqual(updates, [{"contact_id": "contact", "state": "sent", "message_id": "<sent@example.test>"}])
        record.assert_called_once()

    def test_actual_contextual_queue_cli_refuses_provider_append_and_dossier_update(self):
        contact = {"id": "contact", "email": "customer@example.test", "state": "drafted",
                   "draft_subject": "Reply", "draft_body": "body", "dossier": {
                       "thread_id": ROOT, "target_message_id": TARGET, "engine_draft_id": DRAFT_ID}}
        draft = {"id": DRAFT_ID, "thread_id": ROOT, "in_reply_to": TARGET, "references": [ROOT],
                 "to_addresses": [contact["email"]], "status": "draft"}
        for commit, already_pushed in ((False, False), (True, False), (True, True)):
            with self.subTest(commit=commit, already_pushed=already_pushed):
                row = {**contact, "dossier": {**contact["dossier"], "gmail_draft_pushed": already_pushed}}
                original = json.dumps(row, sort_keys=True)
                calls = []
                def call(s, method, params):
                    calls.append(method)
                    if method == "system.capabilities":
                        return {"contextual_email_policy": 1}
                    if method == "drafts.list":
                        return [draft]
                    raise AssertionError("contextual queue must not mutate: " + method)
                with patch.object(config, "load", return_value=settings()), \
                     patch.object(rpc, "call_sync", side_effect=call), \
                     patch.object(campaign, "_get_contact", return_value=row), \
                     patch.object(campaign, "_finished_send_refusal", return_value=None), \
                     patch.object(campaign, "_sent_threads_to", return_value=([], [])), \
                     patch.object(campaign, "_escalation_block", return_value=None), \
                     patch.object(campaign, "_pause_active", return_value=False), \
                     patch("cs.gmail_drafts.append_draft") as append, \
                     contextlib.redirect_stdout(io.StringIO()) as stdout:
                    rc = cli.main(["campaign", "queue-draft", "contact"] + (["--commit"] if commit else []))
                output = json.loads(stdout.getvalue())
                self.assertEqual(rc, 0)  # Campaign CLI reports refusal in its JSON envelope.
                self.assertFalse(output["ok"])
                self.assertEqual(output["refused"], "contextual_email")
                self.assertEqual(output["engine_draft_id"], DRAFT_ID)
                self.assertEqual(output["next"], "review the existing engine draft")
                self.assertEqual(calls, ["system.capabilities", "drafts.list"])
                self.assertEqual(json.dumps(row, sort_keys=True), original)
                append.assert_not_called()

    def test_actual_sourcefree_queue_cli_preserves_provider_mirror(self):
        contact = {"id": "contact", "email": "new@example.test", "state": "drafted",
                   "draft_subject": "Independent", "draft_body": "Independent body", "dossier": {}}
        with patch.object(config, "load", return_value=settings()), \
             patch.object(rpc, "call_sync", return_value={"ok": True}) as call, \
             patch.object(campaign, "_get_contact", return_value=contact), \
             patch.object(campaign, "_finished_send_refusal", return_value=None), \
             patch.object(campaign, "_sent_threads_to", return_value=([], [])), \
             patch.object(campaign, "_escalation_block", return_value=None), \
             patch.object(campaign, "_pause_active", return_value=False), \
             patch("cs.gmail_drafts.append_draft", return_value=("Drafts", [])) as append, \
             contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(cli.main(["campaign", "queue-draft", "contact", "--commit"]), 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])
        append.assert_called_once_with(settings(), "new@example.test", "Independent", "Independent body", body_md=True)
        self.assertEqual(call.call_args.args[1], "campaign.update_contact")
        self.assertTrue(call.call_args.args[2]["dossier"]["gmail_draft_pushed"])

    def test_contextual_campaign_missing_exact_id_or_old_engine_refuses(self):
        contact = {"email": "customer@example.test", "dossier": {"thread_id": ROOT}}
        for capability in ({}, {"assignment_draft_policy": 1}, {"contextual_email_policy": 1}):
            with patch.object(rpc, "call_sync", return_value=capability):
                with self.assertRaises(RuntimeError):
                    contextual_email.campaign_draft(settings(), contact)
        self.assertIsNone(contextual_email.campaign_draft(settings(), {"email": "new@example.test", "dossier": {}}))


if __name__ == "__main__":
    import hashlib
    from pathlib import Path
    import cs
    print(json.dumps({"package_import_proof": {"cs": cs.__file__, "rpc": rpc.__file__,
        "rpc_sha256": hashlib.sha256(Path(rpc.__file__).read_bytes()).hexdigest(),
        "campaign": campaign.__file__, "campaign_sha256": hashlib.sha256(Path(campaign.__file__).read_bytes()).hexdigest(),
        "contextual_email": contextual_email.__file__,
        "contextual_email_sha256": hashlib.sha256(Path(contextual_email.__file__).read_bytes()).hexdigest()}}))
    unittest.main()
