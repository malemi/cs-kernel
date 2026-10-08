from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs import assignment_cli, cli, config, gmail_archive, rpc, task_assignment as assignment, unanswered

NOW = datetime.now(timezone.utc)
KEY = "<root@customer.example>"
OTHER = "<other@customer.example>"
EMAIL = "customer@customer.example"


def settings():
    return config.Settings(_env_file=(), engine_owner_uid="operator", accounts="", email_address="support@company.example", db_path=":memory:")


def projection(state="normal", *, complete=True, task=None):
    return {"version": 1, "actor_uid": "operator", "space_id": "company", "complete": complete,
            "thread_key": KEY, "state": state, "hold_auto_reply": state in assignment.HOLD_STATES or state == "closed",
            "task": task, "events": [], "covered_inbound": [], "covered_message_ids": [],
            "current_inbound": [], "current_message_ids": [], "reply_evidence": [], "reason": "fixture"}


def task(state="assigned"):
    return {"id": "task-id", "space_id": "company", "thread_key": KEY, "revision": 1,
            "state": state, "assignee_uid": "human", "covered_inbound": [], "source_confirmation": None}


def inbound(key=KEY, *, mid="<in@customer.example>", date=NOW):
    return {"email": EMAIL, "name": "Customer", "date": date, "subject": key,
            "message_id": mid, "thread_key": key}


class Consumer(unittest.TestCase):
    def test_unavailable_and_malformed_scope_never_empty_success(self):
        for response in (None, {}, [], projection() | {"version": 2}, projection() | {"actor_uid": "forged"},
                         projection() | {"thread_key": OTHER}, projection("assigned", task=task()) | {"hold_auto_reply": False}):
            with self.subTest(response=response), patch.object(rpc, "call_sync", return_value=response):
                result = assignment.project(settings(), KEY)
                self.assertEqual(result["state"], "unknown")
                self.assertFalse(result["complete"])
                self.assertTrue(result["hold_auto_reply"])

    def test_candidate_pending_confirmation_remains_named_candidate(self):
        with patch.object(rpc, "call_sync", return_value=projection("needs-assignment", complete=False)):
            result = assignment.project(settings(), KEY)
        self.assertEqual(result["state"], "needs-assignment")
        self.assertFalse(result["complete"])
        self.assertTrue(result["hold_auto_reply"])

    def test_candidate_survives_positive_reply_and_local_handled(self):
        rows = [inbound(), inbound(OTHER)]
        authority = {KEY: projection("needs-assignment"), OTHER: projection() | {"thread_key": OTHER}}
        normal, held, audit, reopened = assignment.split_inbound(rows, authority, {}, set(), set(), NOW)
        self.assertEqual([r["thread_key"] for r in normal], [OTHER])
        self.assertEqual([r["thread_key"] for r in held], [KEY])
        self.assertEqual(audit + reopened, [])
        sent = [{"to": [EMAIL], "date": NOW + timedelta(minutes=1), "thread_key": KEY}]
        machine = unanswered.compute_open(normal, sent, set(), set(), NOW)
        self.assertEqual([r["thread_key"] for r in machine], [OTHER])

    def test_new_inbound_identity_reopens_despite_old_date(self):
        p = projection("closed", task=task("closed")) | {"covered_message_ids": ["<covered@customer.example>"]}
        for date in (NOW, NOW - timedelta(days=1)):
            messages = [inbound(mid="<covered@customer.example>"), inbound(mid="<new@customer.example>", date=date)]
            normal, held, audit, reopened = assignment.split_inbound(messages, {KEY: p}, {}, set(), set(), NOW)
            self.assertEqual(normal + held + audit, [])
            self.assertEqual(len(reopened), 1)
            self.assertEqual(reopened[0]["assignment"]["state"], "later-inbound")
            self.assertEqual(reopened[0]["last_inbound_date"], date)
            self.assertEqual(reopened[0]["assignment"]["task"]["state"], "closed")

    def test_exact_closed_coverage_and_active_new_inbound(self):
        p = projection("closed", task=task("closed")) | {"covered_message_ids": ["<in@customer.example>"]}
        normal, held, audit, reopened = assignment.split_inbound([inbound()], {KEY: p}, {}, set(), set(), NOW)
        self.assertEqual(len(audit), 1)
        self.assertEqual(normal + held + reopened, [])
        p = projection("assigned", task=task())
        normal, held, audit, reopened = assignment.split_inbound([inbound(mid="<new@customer.example>")], {KEY: p}, {}, set(), set(), NOW)
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["assignment"]["task"]["assignee_uid"], "human")
        self.assertEqual(normal + audit + reopened, [])

    def test_agreeing_provenance_once_and_conflict_hold(self):
        p = projection("assigned", task=task())
        agreed = assignment.provenance(p, {"owner": "human", "reason": "phone handoff"})
        self.assertEqual(agreed["state"], "assigned")
        self.assertEqual(len(agreed["provenance"]), 2)
        self.assertEqual(assignment.provenance(p, {"owner": "someone else"})["state"], "conflict")

    def test_positive_peer_and_unreadable_peer_is_unknown(self):
        s = settings().model_copy(update={"accounts": "peer:peer,unreadable:unreadable"})
        def call(selected, method, params, timeout):
            if selected.engine_owner_uid == "unreadable":
                raise ConnectionError("fixture offline")
            p = projection("needs-assignment" if selected.engine_owner_uid == "peer" else "normal")
            p["actor_uid"] = selected.engine_owner_uid
            p["reply_evidence"] = [{"judgement": "NONAUTOMATIC_MEMBER_REPLY_CANDIDATE"}] if selected.engine_owner_uid == "peer" else []
            return p
        with patch.object(config, "load", side_effect=lambda engine_owner_uid: s.model_copy(update={"engine_owner_uid": engine_owner_uid})), patch.object(rpc, "call_sync", side_effect=call):
            result = assignment.project(s, KEY)
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["reply_evidence"]), 1)
        self.assertIn("unreadable", result["reason"])

    def test_closed_creator_scope_resolves_only_nonowner_coverage_refusal(self):
        s = settings().model_copy(update={"accounts": "creator:creator"})
        closed = task("closed") | {"creator_uid": "creator"}
        for state in ("closed", "later-inbound"):
            def call(selected, method, params, timeout):
                if selected.engine_owner_uid == "operator":
                    return projection("unknown", complete=False, task=closed) | {
                        "reason": "SOURCE_OWNER_REQUIRED", "source_owner_uid": "creator"}
                return projection(state, task=closed) | {"actor_uid": "creator"}
            with patch.object(config, "load", return_value=s.model_copy(update={"engine_owner_uid": "creator"})), patch.object(rpc, "call_sync", side_effect=call):
                result = assignment.project(s, KEY)
            self.assertEqual(result["state"], state)
            self.assertTrue(result["complete"])
        with patch.object(rpc, "call_sync", return_value=projection("unknown", complete=False, task=closed) | {
                "reason": "SOURCE_OWNER_REQUIRED", "source_owner_uid": "creator"}):
            self.assertEqual(assignment.project(settings(), KEY)["state"], "unknown")

    def test_contradictory_projection_never_reaches_compose(self):
        invalid = [projection("closed", task=task("closed")) | {"hold_auto_reply": False},
                   projection("closed"), projection("later-inbound"), projection("assigned"),
                   projection("assigned", task=task("closed")), projection(task=task()),
                   projection() | {"reason": None}, projection() | {"covered_message_ids": None}]
        for response in invalid:
            with self.subTest(response=response), patch.object(config, "load", return_value=settings()), patch.object(rpc, "call_sync", return_value=response), patch.object(rpc, "chat") as chat, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["draft-reply", "reply", "--thread-id", KEY]), 3)
                chat.assert_not_called()

    def test_candidate_peer_keeps_incomplete_status(self):
        s = settings().model_copy(update={"accounts": "peer:peer"})
        def call(selected, method, params, timeout):
            p = projection("needs-assignment", complete=False) if selected.engine_owner_uid == "peer" else projection()
            return p | {"actor_uid": selected.engine_owner_uid}
        with patch.object(config, "load", side_effect=lambda **kw: s.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call):
            result = assignment.project(s, KEY)
            self.assertEqual(result["state"], "needs-assignment")
            self.assertFalse(result["complete"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["assignment", "status", KEY]), 3)

    def test_dossier_reopened_never_overrides_takeover_or_unreadable_scope(self):
        from cs import mailboxes, state
        for takeover, unreadable in ((True, False), (False, True)):
            with self.subTest(takeover=takeover, unreadable=unreadable), tempfile.TemporaryDirectory() as td:
                s = settings().model_copy(update={"db_path": str(Path(td) / "state.db")})
                if takeover:
                    state.State(s.db_path).mark_escalated(EMAIL, owner="Human", reason="Personally answering")
                fan = mailboxes.Fanout([], [s.email_address],
                    [mailboxes.Unreadable("peer", "peer@company.example", "offline")] if unreadable else [])
                corr = [inbound() | {"direction": "in", "date": NOW.isoformat()}]
                output = io.StringIO()
                with patch.object(config, "load", return_value=s), patch.object(gmail_archive, "correspondence", return_value=corr), patch.object(mailboxes, "sent_to_across", return_value=fan), patch.object(mailboxes, "close_sessions"), patch.object(assignment, "projections", return_value={KEY: projection("later-inbound", task=task("closed"))}), patch.object(rpc, "call_sync", return_value=[]), patch.object(cli, "_print_crm_section"), contextlib.redirect_stdout(output):
                    self.assertEqual(cli.main(["dossier", EMAIL]), 0)
                verdict = output.getvalue().split("verdict: ")[-1]
                self.assertTrue(verdict.startswith("STOP"), verdict)
                self.assertIn("HELD" if takeover else "evidence incomplete", verdict)

    def test_sweep_reopened_and_same_address_thread_keep_address_takeover(self):
        from cs import engine_view, state
        for takeover in (False, True):
            for closed_state in ("closed", "later-inbound"):
                with self.subTest(takeover=takeover, closed_state=closed_state), tempfile.TemporaryDirectory() as td:
                    s = settings().model_copy(update={"db_path": str(Path(td) / "state.db")})
                    if takeover:
                        state.State(s.db_path).mark_escalated(EMAIL, owner="Human", reason="Personally answering")
                    authority = {KEY: projection(closed_state, task=task("closed")), OTHER: projection() | {"thread_key": OTHER}}
                    with patch.object(gmail_archive, "inbound_recent", return_value=[inbound(), inbound(OTHER)]), patch.object(gmail_archive, "sent_recent", return_value=[]), patch.object(engine_view, "classify", return_value=({}, None)), patch.object(engine_view, "settled", return_value=({}, None)), patch.object(assignment, "projections", return_value=authority):
                        result = unanswered.sweep(s, 30)
                    if takeover:
                        self.assertEqual(result["open"], [])
                        self.assertEqual({row["thread_key"] for row in result["human_work"]}, {KEY})
                        self.assertEqual({row["thread_key"] for row in result["escalated"]}, {OTHER})
                        for row in result["human_work"]:
                            self.assertTrue(row["assignment"]["hold_auto_reply"])
                            self.assertIn("address_escalation", [origin["basis"] for origin in row["assignment"]["provenance"]])
                    else:
                        self.assertEqual({row["thread_key"] for row in result["open"]}, {KEY, OTHER})
                        self.assertEqual(result["human_work"], [])

    def test_outsider_peer_scope_holds(self):
        s = settings().model_copy(update={"accounts": "peer:peer"})
        def call(selected, method, params, timeout):
            return projection() | {"actor_uid": selected.engine_owner_uid, "space_id": "outsider" if selected.engine_owner_uid == "peer" else "company"}
        with patch.object(config, "load", return_value=s.model_copy(update={"engine_owner_uid": "peer"})), patch.object(rpc, "call_sync", side_effect=call):
            self.assertEqual(assignment.project(s, KEY)["state"], "unknown")

    def test_draft_guard_precedes_every_write(self):
        for p in [projection(state, task=task() if state == "assigned" else None) for state in assignment.HOLD_STATES]:
            with patch.object(config, "load", return_value=settings()), patch.object(rpc, "call_sync", return_value=p) as calls, patch.object(rpc, "chat") as chat, contextlib.redirect_stderr(io.StringIO()):
                rc = cli.main(["draft-reply", "reply", "--thread-id", KEY])
                self.assertEqual(rc, 3)
                chat.assert_not_called()
                self.assertEqual([c.args[1] for c in calls.call_args_list], ["tasks.assignment.project"])
        with patch.object(config, "load", return_value=settings()), patch.object(rpc, "call_sync") as calls, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["draft-reply", "reply"]), 3)
            calls.assert_not_called()

    def test_gmail_mirror_rechecks_live_authority_and_exact_composed_thread(self):
        async def chat(*args, **kwargs):
            return {"result": {"response": "composed"}}
        for foreign in (False, True):
            calls = {"projection": 0, "drafts": 0}
            def call(selected, method, params, timeout):
                if method == "tasks.assignment.project":
                    calls["projection"] += 1
                    return projection() if calls["projection"] == 1 else projection("assigned", task=task())
                self.assertEqual(method, "drafts.list")
                calls["drafts"] += 1
                return [] if calls["drafts"] == 1 else [{"id": "fresh", "to_addresses": [EMAIL], "body": "Reply",
                    "references": [OTHER if foreign else KEY], "created_at": "2026-10-08T12:00:00"}]
            from cs import gmail_drafts
            with patch.object(config, "load", return_value=settings()), patch.object(rpc, "call_sync", side_effect=call), patch.object(rpc, "chat", side_effect=chat), patch.object(gmail_drafts, "append_draft") as append, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["draft-reply", "reply", "--thread-id", KEY]), 3)
                append.assert_not_called()
            self.assertEqual(calls["projection"], 1 if foreign else 2)

    def test_review_keeps_escalation_age_and_local_handled_hold(self):
        from cs import review
        p = assignment.provenance(projection("assigned", task=task()), {"owner": "human", "reason": "Personally writing"})
        text = review.render({"human_work": [{"email": EMAIL, "thread_key": KEY, "assignment": p}],
            "escalated": [{"email": EMAIL, "owner": "human", "days": 12, "escalated_on": "2026-09-26"}],
            "handled_out_of_band": [{"email": EMAIL, "handled_on": "2026-10-08", "reason": "Local gesture"}]})
        self.assertIn("with human for 12d", text)
        self.assertIn("--undo --commit", text)
        self.assertEqual(text.count("explicit_manual=human"), 1)
        self.assertIn("engine assignment remains HELD / unconfirmed", text)
        self.assertNotIn("no longer raised", text)

    def test_acknowledgement_is_exact_and_unicode_digest_matches_engine(self):
        intent = {"version": 1, "actor_uid": "operator", "operation": "close", "operation_id": "op",
                  "task_id": "task-id", "space_id": "company", "expected_revision": 1,
                  "covered_inbound": ["a"], "reason": "téléphone"}
        digest = hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
        receipt = {"version": 1, "acknowledged": True, "operation_id": "op", "task_id": "task-id",
                   "space_id": "company", "revision": 2, "state": "closed", "covered_inbound": ["a"], "payload_digest": digest}
        with patch.object(rpc, "call_sync", return_value=receipt):
            self.assertEqual(assignment.commit(settings(), intent, {}), receipt)
        for key, bad in (("acknowledged", False), ("task_id", "other"), ("revision", 3), ("covered_inbound", []), ("payload_digest", "wrong")):
            with patch.object(rpc, "call_sync", return_value=receipt | {key: bad}):
                with self.assertRaises(assignment.AssignmentUnavailable):
                    assignment.commit(settings(), intent, {})

    def test_scoped_compose_negotiates_server_policy_before_chat(self):
        import asyncio
        calls = []
        class Client:
            def __init__(self, *args, **kwargs):
                self.notifications = []
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def call(self, method, params, timeout=60):
                calls.append((method, params))
                return {"assignment_draft_policy": 1} if method == "system.capabilities" else {"response": "composed"}
        with patch.object(rpc, "EngineClient", Client):
            result = asyncio.run(rpc.chat(settings(), "compose", assignment_thread_key=KEY))
        self.assertEqual(result["result"]["response"], "composed")
        self.assertEqual(calls[0], ("system.capabilities", {}))
        self.assertEqual(calls[1][1]["assignment_thread_key"], KEY)
        self.assertEqual(calls[1][1]["assignment_policy_version"], 1)
        class OldClient(Client):
            async def call(self, method, params, timeout=60):
                calls.append((method, params))
                return {}
        calls.clear()
        with patch.object(rpc, "EngineClient", OldClient), self.assertRaises(RuntimeError):
            asyncio.run(rpc.chat(settings(), "compose", assignment_thread_key=KEY))
        self.assertEqual([c[0] for c in calls], ["system.capabilities"])

    def test_json_input_bounded_duplicate_rejected_and_export_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            filename = Path(td) / "intent.json"
            filename.write_text('{"version":1,"version":2}')
            with self.assertRaises(ValueError):
                assignment_cli.read_object(str(filename))
            filename.write_bytes(b" " * (assignment_cli.MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                assignment_cli.read_object(str(filename))
            filename.unlink()
            assignment_cli.write_object(str(filename), {"version": 1})
            self.assertEqual(filename.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                assignment_cli.write_object(str(filename), {})

    def test_optional_correspondence_projection_reuses_batch_and_preserves_default_rows(self):
        import test_bounded_header_readers as readers
        raw = readers.headers(450)
        m = readers.IMAP(sent=raw, inbound=raw)
        with patch.object(gmail_archive, "_imap", return_value=m):
            projected = gmail_archive.correspondence(readers.settings(), readers.CONTACT, assignment_metadata=True)
        self.assertEqual(m.fetches, {"Sent": 3, "All": 3})
        self.assertEqual(len(projected), 900)
        for row in projected:
            self.assertEqual(row["message_id"], row["thread_key"])
            self.assertNotIn("body", row)
        stripped = [{k: v for k, v in row.items() if k not in {"message_id", "thread_key"}} for row in projected]
        self.assertEqual(readers.typed(stripped), readers.typed(readers.expected(raw, "sent") + readers.expected(raw, "in")))


if __name__ == "__main__":
    unittest.main()
