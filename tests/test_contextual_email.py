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

    async def test_campaign_send_calls_only_the_named_native_draft(self):
        outcome = {"request_key":"campaign-send:"+DRAFT_ID, "ok":True,"state":"sent","effect_certainty":"verified","draft_id":DRAFT_ID,"message_id":"<sent@example.test>"}
        with patch.object(rpc,"call_sync",return_value=outcome) as call:
            self.assertEqual(contextual_email.campaign_delivery(settings(), DRAFT_ID),outcome["message_id"])
            self.assertEqual(call.call_args.args[1:],("drafts.send",{"draft_id":DRAFT_ID,"request_key":"campaign-send:"+DRAFT_ID}))


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






    def test_campaign_recovery_precedes_archive_dedup_and_never_dispatches(self):
        import tempfile
        from pathlib import Path
        from cs.state import State
        key = "campaign-send:native"
        contact = {"id":"contact","email":"contact@example.test","state":"drafted",
                   "dossier":{"mailbox_draft_id":"native"}}
        def rpc_call(selected, method, params):
            if method == "drafts.send_status":
                self.assertEqual(params, {"draft_id":"native", "request_key":key})
                return {"ok":True, "state":"sent","effect_certainty":"verified","draft_id":"native",
                        "request_key":key,"message_id":"<receipt@example.test>"}
            self.assertEqual(method, "campaign.update_contact")
            contact.update(state="sent",message_id=params["message_id"])
            return {"ok":True,"contact":dict(contact)}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{},clear=True):
            selected = settings().model_copy(update={"cs_triage_mode":"send","db_path":str(Path(directory)/"local.db")})
            with patch.object(campaign,"_get_contact",return_value=contact), patch.object(campaign,"_sent_threads_to",side_effect=AssertionError("fresh admission during receipt recovery")), patch.object(rpc,"call_sync",side_effect=rpc_call):
                for _ in range(2):
                    self.assertEqual(campaign.send_draft(selected,"contact",commit=True)["message_id"],"<receipt@example.test>")
            local = State(selected.db_path)
            try:
                self.assertEqual(local.conn.execute("SELECT COUNT(*) FROM sends").fetchone()[0],1)
            finally:
                local.conn.close()

    def test_fresh_fixed_template_queue_preserves_html_cc_and_native_binding(self):
        selected = settings()
        contact_id = "pack-contact"
        with patch.object(rpc, "call_sync", return_value={"ok":True,"contact":{
                "id":contact_id, "dossier":{"mailbox_draft_id":"current-native"}}}) as call:
            result = campaign._queue_pack(selected, contact_id, "contact@example.test", "Pack", "plain",
                                          {"pack_context":"fixture"}, html="<p>Pack</p>", cc="cc@example.test")
            self.assertEqual(result["draft_id"], "current-native")
            call.assert_called_once_with(selected,"campaign.update_contact",{
                "contact_id":contact_id,"draft_subject":"Pack","draft_body":"<p>Pack</p>","draft_body_format":"html",
                "draft_cc":["cc@example.test"],"draft_request_key":"campaign-pack:"+contact_id,
                "dossier":{"pack_context":"fixture","mailbox_draft_kind":"fixed-template"}})

    def test_fixed_template_pending_after_creation_never_enters_smtp(self):
        selected = settings().model_copy(update={"cs_triage_mode":"send"})
        cid, key = "contact-fixture", "campaign-pack:contact-fixture"
        dossier = {"mailbox_draft_kind":"fixed-template","mailbox_draft_request":{"request_key":key,"state":"reserved"}}
        row = {"id":cid, "email":"customer@example.test", "state":"queued", "_campaign_name":"fixture","dossier":dossier}
        from unittest.mock import Mock
        pack = Mock()
        pack.build.return_value = ("Subject", "body", "<p>body</p>")
        calls = []
        def dispatch(settings, method, params):
            self.assertEqual(method, "campaign.update_contact")
            self.assertEqual(params["draft_request_key"],key)
            calls.append(method)
            return {"ok":True,"contact":{"id":cid,"dossier":{"mailbox_draft_id":"recovered"}}}
        with patch.object(campaign,"_get_contact",return_value=row), patch.object(campaign,"_resolve_pack",return_value=(pack,None)), patch.object(campaign,"_finished_refusal",return_value=None), patch.object(campaign,"_escalation_block",return_value=None), patch.object(campaign,"_pause_active",return_value=False), patch.object(rpc,"call_sync",side_effect=dispatch), patch("cs.send_mail.send") as smtp:
            self.assertEqual(campaign.send_first(selected, cid, commit=True)["draft_id"],"recovered")
            dossier["mailbox_draft_request"]["request_key"] = "previous-contextual-key"
            self.assertFalse(campaign.send_first(selected, cid, commit=True)["ok"])
            self.assertEqual(calls, ["campaign.update_contact"])
            smtp.assert_not_called()

    def test_campaign_queue_uses_native_draft_after_text_retirement(self):
        selected = settings()
        handle = "gmail:" + "a"*64 + ":campaign"
        contact = {"id":"contact","email":"customer@example.test","state":"drafted",
                   "draft_subject":None,"draft_body":None,"dossier":{"mailbox_draft_id":handle}}
        row = {"id":handle,"owner_id":selected.email_address,"status":"draft",
               "to_addresses":[contact["email"]],"subject":"Edited","body":"Current saved reply"}
        def call(s, method, params):
            if method == "system.capabilities":return {"mailbox_drafts":1}
            if method == "drafts.get" and params == {"draft_id":handle}:return {"ok":True,"draft":row}
            raise AssertionError(method)
        with patch.object(campaign,"_get_contact",return_value=contact), patch.object(campaign,"_finished_send_refusal",return_value=None), patch.object(campaign,"_sent_threads_to",return_value=([],[])), patch.object(campaign,"_escalation_block",return_value=None), patch.object(campaign,"_pause_active",return_value=False), patch.object(rpc,"call_sync",side_effect=call):
            self.assertEqual(campaign.queue_draft(selected,"contact",commit=True)["draft_id"],handle)
            contact.update(dossier={},draft_body="Legacy private content")
            self.assertFalse(campaign.send_draft(selected,"contact",commit=True)["ok"])


class CampaignMailboxRecovery(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def receipt(self, draft_id=DRAFT_ID, **changes):
        return {"ok": True, "state": "sent", "effect_certainty": "verified",
                "draft_id": draft_id, "request_key": "campaign-send:" + draft_id,
                "message_id": "<receipt@example.test>", **changes}

    def pending(self, **changes):
        return self.receipt(ok=False, cause="draft_retirement_unconfirmed",
                            draft_cleanup={"state": "pending"}, **changes)

    def test_send_keys_preserve_existing_receipts_and_bound_full_handles(self):
        keys = []
        for size in (242, 243, 256):
            handle = "imap:" + "a" * (size - 5)
            calls = []
            def dispatch(selected, method, params):
                calls.append((method, params))
                return self.receipt(handle, request_key=params["request_key"])
            with patch.object(rpc, "call_sync", side_effect=dispatch):
                contextual_email.campaign_delivery(settings(), handle, status_only=True)
                contextual_email.campaign_delivery(settings(), handle)
            self.assertEqual([method for method, _ in calls], ["drafts.send_status", "drafts.send"])
            self.assertEqual(calls[0][1], calls[1][1])
            key = calls[0][1]["request_key"]
            self.assertEqual(calls[0][1]["draft_id"], handle)
            self.assertLessEqual(len(key), 256)
            self.assertEqual(key == "campaign-send:" + handle, size == 242)
            keys.append(key)
        self.assertEqual(len(set(keys)), 3)

    def test_pending_sent_status_is_read_only_and_requires_exact_proof(self):
        with patch.object(rpc, "call_sync", return_value=self.pending()) as call:
            with self.assertRaises(contextual_email.CampaignDraftRetirementPending) as caught:
                contextual_email.campaign_delivery(settings(), DRAFT_ID, status_only=True)
            self.assertEqual(caught.exception.message_id, "<receipt@example.test>")
            self.assertEqual(call.call_args.args[1], "drafts.send_status")
            self.assertEqual(call.call_count, 1)
        invalid = ({"draft_id": "another"}, {"request_key": "another"},
                   {"state": "unconfirmed"}, {"effect_certainty": "unknown"},
                   {"message_id": None}, {"cause": "another"},
                   {"draft_cleanup": None}, {"draft_cleanup": {"state": "unknown"}})
        for changed in invalid:
            with self.subTest(changed=changed), patch.object(rpc, "call_sync", return_value={**self.pending(), **changed}) as call:
                with self.assertRaises(RuntimeError) as caught:
                    contextual_email.campaign_delivery(settings(), DRAFT_ID, status_only=True)
                self.assertNotIsInstance(caught.exception, contextual_email.CampaignDraftRetirementPending)
                self.assertEqual(call.call_count, 1)

    def test_explicit_campaign_cli_finishes_original_send_before_marking(self):
        import tempfile
        from pathlib import Path
        from cs.state import State
        contact = {"id": "contact", "email": "customer@example.test", "state": "drafted",
                   "dossier": {"mailbox_draft_id": DRAFT_ID}}
        calls = []
        def dispatch(selected, method, params):
            calls.append((method, params))
            if method == "drafts.send_status":
                return self.receipt() if contact["state"] == "sent" else self.pending()
            if method == "drafts.send":
                self.assertEqual(params, calls[0][1])
                return self.receipt(draft_cleanup={"state": "completed"})
            self.assertEqual(method, "campaign.update_contact")
            self.assertEqual([method for method, _ in calls[:-1]], ["drafts.send_status", "drafts.send"])
            contact.update(state="sent", message_id=params["message_id"])
            return {"ok": True, "contact": dict(contact)}
        with tempfile.TemporaryDirectory() as directory:
            selected = settings().model_copy(update={"db_path": str(Path(directory) / "local.db")})
            with patch.object(config, "load", return_value=selected), \
                 patch.object(campaign, "_get_contact", return_value=contact), \
                 patch.object(campaign, "_sent_threads_to", side_effect=AssertionError("new admission during send recovery")), \
                 patch.object(rpc, "call_sync", side_effect=dispatch):
                for _ in range(2):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        self.assertEqual(cli.main(["campaign", "send-draft", "contact", "--commit"]), 0)
                    self.assertTrue(json.loads(output.getvalue())["ok"])
            self.assertEqual([method for method, _ in calls],
                             ["drafts.send_status", "drafts.send", "campaign.update_contact", "drafts.send_status"])
            local = State(selected.db_path)
            try:
                self.assertEqual(local.conn.execute("SELECT COUNT(*) FROM sends").fetchone()[0], 1)
            finally:
                local.conn.close()

    def test_failed_cleanup_or_changed_receipt_never_marks_contact(self):
        contact = {"id": "contact", "email": "customer@example.test", "state": "drafted",
                   "dossier": {"mailbox_draft_id": DRAFT_ID}}
        for result in (self.pending(), self.receipt(message_id="<different@example.test>"),
                       self.receipt(request_key="another")):
            with self.subTest(result=result), \
                 patch.object(campaign, "_get_contact", return_value=contact), \
                 patch.object(campaign, "_mark_mailbox_delivery") as mark, \
                 patch.object(rpc, "call_sync", side_effect=[self.pending(), result]) as call:
                outcome = campaign.send_draft(settings(), "contact", commit=True)
                self.assertFalse(outcome["ok"])
                self.assertEqual([item.args[1] for item in call.call_args_list], ["drafts.send_status", "drafts.send"])
                self.assertEqual(call.call_args_list[0].args[2], call.call_args_list[1].args[2])
                mark.assert_not_called()

    def test_noncommitting_and_scheduled_campaigns_never_resume_cleanup(self):
        contact = {"id": "contact", "email": "customer@example.test", "state": "drafted",
                   "dossier": {"mailbox_draft_id": DRAFT_ID}}
        for commit, mode, queue_only, headless in ((False, "send", False, False),
                (True, "draft", False, False), (True, "send", True, False),
                (True, "send", False, True)):
            with self.subTest(commit=commit, mode=mode, queue_only=queue_only, headless=headless), \
                 patch.object(contextual_email, "scheduled", return_value=headless), \
                 patch.object(contextual_email, "campaign_draft", return_value={"id": DRAFT_ID}), \
                 patch.object(campaign, "_get_contact", return_value=contact), \
                 patch.object(campaign, "_finished_send_refusal", return_value=None), \
                 patch.object(campaign, "_sent_threads_to", return_value=([], [])), \
                 patch.object(campaign, "_escalation_block", return_value=None), \
                 patch.object(campaign, "_pause_active", return_value=False), \
                 patch.object(rpc, "call_sync") as call:
                outcome = campaign.send_draft(settings().model_copy(update={"cs_triage_mode": mode}),
                                              "contact", commit=commit, queue_only=queue_only)
                self.assertTrue(outcome["ok"])
                call.assert_not_called()


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
