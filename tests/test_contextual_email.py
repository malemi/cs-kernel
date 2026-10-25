#!/usr/bin/env python3
"""Actual CLI/EngineClient authenticated frames bind known contextual effects."""

import asyncio
import contextlib
import io
import json
import os
from types import SimpleNamespace

import websockets
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
    def __init__(self, capability=True, assignment=True, approve=True, provenance=None):
        self.frames = []
        self.capability = capability
        self.assignment = assignment
        self.approve = approve
        self.provenance = provenance
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
            result = {"assignment_draft_policy": 1} if self.assignment else {}
            if self.capability:
                result["contextual_email_policy"] = 1
            if self.provenance is not None:
                result["operator_reply_provenance"] = self.provenance
            await self.emit({"id": frame["id"], "result": result})
        elif method == "drafts.list":
            await self.emit({"id": frame["id"], "result": [{"id": DRAFT_ID,
                "status": frame["params"].get("status", "draft"), "thread_id": ROOT, "in_reply_to": TARGET,
                "references": [ROOT], "to_addresses": ["customer@example.test"], "subject": "Reply",
                "sent_message_id": "<sent@example.test>"}]})
        elif method == "tasks.assignment.project":
            from assignment_fixture import normal_projection
            await self.emit({"id": frame["id"], "result": normal_projection(settings(), frame["params"])})
        elif method == "emails.list_by_thread":
            assert frame["params"] == {"thread_id": ROOT}
            assert hasattr(self, "source_email_ids")
            await self.emit({"id": frame["id"], "result": {
                "emails": [{"id": value} for value in self.source_email_ids]}})
        elif method == "chat.send":
            self.chat_id = frame["id"]
            if not self.approve:
                await self.emit({"id": self.chat_id, "result": {"response": "checked"}})
                return
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


class ScheduledReplyTransport(unittest.IsolatedAsyncioTestCase):
    async def exchange(self, marker, capability, *, inputs=(), **kwargs):
        frames, handshakes = [], []
        approvals = iter(enumerate(inputs))
        chat_id = None

        async def handler(ws):
            nonlocal chat_id
            handshakes.append((ws.request.path, ws.request.headers["Authorization"]))

            async def pending():
                item = next(approvals, None)
                if item is None:
                    await ws.send(json.dumps({"id": chat_id, "result": {"response": "checked"}}))
                else:
                    index, inputs = item
                    await ws.send(json.dumps({"method": "chat.pending_approval", "params": {
                        "name": "send_draft", "tool_use_id": str(index), "input": inputs}}))

            async for raw in ws:
                frame = json.loads(raw)
                frames.append(frame)
                if frame["method"] == "system.capabilities":
                    await ws.send(json.dumps({"id": frame["id"], "result": capability}))
                elif frame["method"] == "chat.send":
                    chat_id = frame["id"]
                    await pending()
                elif frame["method"] == "chat.approve":
                    await ws.send(json.dumps({"id": frame["id"], "result": {"ok": True}}))
                    await pending()
                else:
                    raise AssertionError(frame)

        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            selected = settings().model_copy(update={
                "engine_ws_url": f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"})
            environment = dict(os.environ)
            environment.pop("CS_HEADLESS_SEND", None)
            if marker is not None:
                environment["CS_HEADLESS_SEND"] = marker
            with patch.dict(os.environ, environment, clear=True), \
                 patch.object(rpc.auth, "get_id_token", return_value="local-test-token"):
                try:
                    result = await rpc.chat(selected, "Reply", conversation_id="local-provenance",
                                            echo=lambda value: None, **kwargs)
                except RuntimeError as error:
                    result = error
        self.assertEqual(handshakes, [("/ws/fixture-owner", "Bearer local-test-token")])
        return frames, result

    async def test_exact_opt_in_and_combined_context_query(self):
        context = {"draft_id": DRAFT_ID, "thread_key": ROOT}
        frames, result = await self.exchange("1", {
            "operator_reply_provenance": 1, "contextual_email_policy": 1},
            allow_tools={"send_draft"}, email_context=context)
        self.assertEqual([f["method"] for f in frames], ["system.capabilities", "chat.send"])
        self.assertEqual(frames[1]["params"], {"message": "Reply", "conversation_id": "local-provenance",
            "email_context": context, "contextual_email_policy_version": 1,
            "operator_origin": "scheduled_operator", "operator_origin_version": 1})
        self.assertEqual(result["result"], {"response": "checked"})

    async def test_missing_malformed_unsupported_refuse_before_chat(self):
        for capability in (None, [], {}, *({"operator_reply_provenance": value}
                for value in (True, 1.0, "1", 0, 2))):
            with self.subTest(capability=capability):
                frames, result = await self.exchange("1", capability, allow_tools={"send_draft"})
                self.assertIsInstance(result, RuntimeError)
                self.assertIn("operator reply provenance", str(result))
                self.assertEqual([f["method"] for f in frames], ["system.capabilities"])

    async def test_manual_nonexact_marker_and_no_send_keep_frame(self):
        for marker, allow in ((None, {"send_draft"}), ("", {"send_draft"}),
                ("true", {"send_draft"}), ("01", {"send_draft"}), ("1 ", {"send_draft"}),
                ("1", None), ("1", set()), ("1", {"update_memory"})):
            with self.subTest(marker=marker, allow=allow):
                frames, result = await self.exchange(marker, {}, allow_tools=allow)
                self.assertEqual([f["method"] for f in frames], ["chat.send"])
                self.assertEqual(frames[0]["params"], {
                    "message": "Reply", "conversation_id": "local-provenance"})
                self.assertEqual(result["approvals"], [])

    async def test_readonly_and_assignment_keep_existing_policy_frames(self):
        frames, _ = await self.exchange("1", {"chat_read_only_policy": 1},
                                       read_only=True, allow_tools={"send_draft"})
        self.assertEqual(frames[1]["params"], {"message": "Reply", "conversation_id": "local-provenance",
            "mutation_policy": "read_only", "policy_version": 1})
        frames, _ = await self.exchange("1", {"assignment_draft_policy": 1,
            "contextual_email_policy": 1}, assignment_thread_key=ROOT, email_context={"thread_key": ROOT})
        self.assertEqual([f["method"] for f in frames], ["system.capabilities", "chat.send"])
        self.assertEqual(frames[1]["params"], {"message": "Reply", "conversation_id": "local-provenance",
            "assignment_thread_key": ROOT, "assignment_policy_version": 1,
            "email_context": {"thread_key": ROOT}, "contextual_email_policy_version": 1})

    async def test_direct_classifier_returns_before_provenance_or_transport(self):
        from cs import model_config, worker_llm
        done = SimpleNamespace(model="fixture", output_tokens=1, latency_ms=1, cost_usd=None, text="classified")
        with patch.dict(os.environ, {"CS_HEADLESS_SEND": "1"}), \
             patch.object(model_config, "route_direct", return_value=True), \
             patch.object(worker_llm, "call", return_value=done) as call, \
             patch.object(rpc, "EngineClient") as client:
            result = await rpc.chat(settings(), "classify", role="triage", allow_tools={"send_draft"},
                                    echo=lambda value: None)
        self.assertEqual(result, {"result": {"response": "classified"}, "approvals": [], "notifications": []})
        call.assert_called_once_with("classify", role="triage", timeout=600)
        client.assert_not_called()

    async def test_marker_preserves_actual_exact_campaign_approval_predicate(self):
        captured = []
        original = rpc.chat
        async def capture(*args, **kwargs):
            captured.append(kwargs["approval_predicate"])
            return {"result": {}, "approvals": [{"tool": "send_draft", "mode": "once",
                                                  "input": {"draft_id": DRAFT_ID}}]}
        with patch.object(rpc, "chat", capture), patch.object(rpc, "call_sync", return_value=[{
                "id": DRAFT_ID, "sent_message_id": "<sent@example.test>"}]):
            await asyncio.to_thread(contextual_email.send_campaign_draft, settings(), {"id": DRAFT_ID},
                                    {"draft_id": DRAFT_ID})
        self.assertIs(rpc.chat, original)
        frames, result = await self.exchange("1", {"operator_reply_provenance": 1},
            allow_tools={"send_draft"}, approval_predicate=captured[0],
            inputs=({"draft_id": "wrong"}, {"draft_id": DRAFT_ID}, {"draft_id": DRAFT_ID}))
        self.assertEqual([f["params"]["mode"] for f in frames if f["method"] == "chat.approve"],
                         ["deny", "once", "deny"])
        self.assertEqual([a["mode"] for a in result["approvals"]], ["deny", "once", "deny"])
        self.assertEqual(frames[1]["params"]["operator_origin"], "scheduled_operator")


class ContextualEmail(unittest.TestCase):
    def setUp(self):
        # Retain legacy scheduled transport coverage; review negotiation has its own suite.
        marker = patch.dict(os.environ, {"CS_OPERATOR_HEADLESS": "1"})
        marker.start()
        self.addCleanup(marker.stop)

    def test_scheduled_cli_actual_engineclient_wire_fields(self):
        wire = Wire(provenance=1)
        with wire.patches(), patch.dict(os.environ, {"CS_HEADLESS_SEND": "1"}), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["chat", "Reply", "--allow", "send_draft",
                                       "--thread-id", ROOT, "--reply-to", TARGET]), 0)
        self.assertEqual([f["method"] for f in wire.frames], ["system.capabilities", "chat.send", "chat.approve"])
        payload = wire.frames[1]["params"]
        self.assertEqual(payload["operator_origin"], "scheduled_operator")
        self.assertEqual(payload["operator_origin_version"], 1)
        self.assertIs(type(payload["operator_origin_version"]), int)
        self.assertEqual(payload["email_context"], {"thread_key": ROOT, "target_message_id": TARGET})
        self.assertEqual(payload["contextual_email_policy_version"], 1)

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
        wire = Wire(False)
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["chat", "Compose a new independent message", "--allow", "send_draft"]), 0)
        self.assertEqual([f["method"] for f in wire.frames], ["system.capabilities", "chat.send", "chat.approve"])
        self.assertEqual(set(next(f for f in wire.frames if f["method"] == "chat.send")["params"]), {"message", "conversation_id"})

    def test_exact_draft_send_payload_is_structurally_bound(self):
        wire = Wire()
        with wire.patches():
            result = asyncio.run(rpc.chat(settings(), "Send exact", allow_tools={"send_draft"},
                                          email_context={"draft_id": DRAFT_ID}))
        self.assertEqual(wire.frames[1]["params"]["email_context"], {"draft_id": DRAFT_ID})
        self.assertEqual(result["approvals"][0]["mode"], "once")

    def test_actual_exact_draft_cli_uses_legacy_guard_and_verifies_sent(self):
        wire = Wire(False)
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(cli.main(["draft-send", DRAFT_ID]), 5)
        self.assertIn("Do not retry sending", stderr.getvalue())
        chat = next(frame for frame in wire.frames if frame["method"] == "chat.send")
        self.assertEqual(set(chat["params"]), {"message", "conversation_id"})
        self.assertEqual([f["method"] for f in wire.frames].count("system.capabilities"), len(wire.handshakes))
        self.assertEqual([f["params"]["thread_key"] for f in wire.frames if f["method"] == "tasks.assignment.project"], [ROOT])
        self.assertEqual(wire.frames[-1]["method"], "drafts.list")
        self.assertEqual(wire.frames[-1]["params"], {"status": "sent"})
        self.assertTrue(all(handshake[1]["additional_headers"]["Authorization"] == "Bearer fixture-id-token"
                            for handshake in wire.handshakes))

    def test_legacy_draft_reply_actual_assignment_only_frame(self):
        wire = Wire(False, approve=False)
        wire.source_email_ids = ["8ac7571d-778b-46a2-a55b-a08e703149f7"]
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["draft-reply", "Compose scoped reply", "--thread-id", ROOT]), 0)
        payload = next(f["params"] for f in wire.frames if f["method"] == "chat.send")
        self.assertEqual(set(payload), {"message", "conversation_id", "assignment_thread_key", "assignment_policy_version"})
        self.assertEqual(payload["assignment_thread_key"], ROOT)
        self.assertEqual(payload["assignment_policy_version"], 1)
        self.assertEqual([f["method"] for f in wire.frames].count("system.capabilities"), len(wire.handshakes))
        self.assertEqual([frame["params"] for frame in wire.frames if frame["method"] == "emails.list_by_thread"],
                         [{"thread_id": ROOT}])
        self.assertIn(wire.source_email_ids[0], payload["message"])
        self.assertIn("Use read_email with these email_id handles", payload["message"])
        self.assertTrue(payload["message"].endswith("Compose scoped reply"))

    def test_legacy_assignment_capability_absence_refuses_before_chat(self):
        wire = Wire(False, assignment=False, approve=False)
        with wire.patches(), self.assertRaisesRegex(RuntimeError, "assignment draft policy"):
            asyncio.run(rpc.chat(settings(), "Compose", assignment_thread_key=ROOT))
        self.assertEqual([f["method"] for f in wire.frames], ["system.capabilities"])

    def test_explicit_draft_source_refuses_old_engine_without_unbound_retry(self):
        wire = Wire(False, approve=False)
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["draft-reply", "Compose", "--thread-id", ROOT, "--source-id", "source"]), 3)
        self.assertNotIn("chat.send", [f["method"] for f in wire.frames])
        self.assertEqual([f["method"] for f in wire.frames].count("system.capabilities"), len(wire.handshakes))

    def test_explicit_draft_source_keeps_both_full_policy_bindings(self):
        wire = Wire(approve=False)
        with wire.patches(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["draft-reply", "Compose", "--thread-id", ROOT, "--source-id", "source"]), 0)
        payload = next(f["params"] for f in wire.frames if f["method"] == "chat.send")
        self.assertEqual(payload["email_context"], {"thread_key": ROOT, "source_email_id": "source"})
        self.assertEqual(payload["contextual_email_policy_version"], 1)
        self.assertEqual(payload["assignment_thread_key"], ROOT)
        self.assertEqual(payload["assignment_policy_version"], 1)

    def test_all_explicit_chat_flags_and_direct_requirement_refuse_old_engine(self):
        for flag, value in (("--thread-id", ROOT), ("--source-id", "source"), ("--reply-to", TARGET), ("--draft-id", DRAFT_ID)):
            with self.subTest(flag=flag):
                wire = Wire(False)
                with wire.patches(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main(["chat", "Bound", flag, value]), 3)
                self.assertEqual([f["method"] for f in wire.frames], ["system.capabilities"])
        for kwargs in ({"require_contextual_email_policy": True}, {"email_context": {"draft_id": DRAFT_ID}}):
            wire = Wire(False)
            with wire.patches(), self.assertRaisesRegex(RuntimeError, "contextual email policy"):
                asyncio.run(rpc.chat(settings(), "Bound", **kwargs))
            self.assertEqual([f["method"] for f in wire.frames], ["system.capabilities"])

    def test_context_cannot_be_routed_to_direct_classifier(self):
        with self.assertRaises(ValueError):
            asyncio.run(rpc.chat(settings(), "classify", role="triage", email_context={"thread_key": ROOT}))
        for routing in ({"role": "triage"}, {"read_only": True}):
            with self.subTest(routing=routing), self.assertRaises(ValueError):
                asyncio.run(rpc.chat(settings(), "classify", require_contextual_email_policy=True, **routing))

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
