from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
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


def malformed_observation():
    return projection("needs-assignment", complete=False) | {"authoritative_thread_key": KEY,
        "component_thread_keys": [KEY], "component_scope_present": False, "source_owner_uid": "operator",
        "authority_complete": False, "hold_scope": "exact_observed_message", "reply_evidence": [{
            "version": 1, "actor_uid": "operator", "space_id": "company", "source_id": "source-id",
            "thread_key": KEY, "complete": True, "judgement": "MALFORMED_OWN_SENT_REQUIRES_HUMAN_VERIFICATION",
            "reason": "NEEDS_HUMAN_VERIFICATION", "source": {"actor_uid": "operator", "mailbox_id": "mailbox-id",
                "message_id": KEY, "thread_key": KEY, "provider": {"folder": "Sent", "uidvalidity": 5, "uid": 123},
                "route_digest": "a" * 64, "raw_header_digest": "b" * 64, "observation_only": True}, "digest": "c" * 64}]}


def captured_partial_component():
    requested = "<CAJ1mzbGNjyvm+m8FyFTiCLO0bnxgwk-w77VvMzLA9Bppiw0SeA@mail.gmail.com>"
    canonical = "<CAK0A7__rTwERFKyhQZfU6XcNgmerb-XRwT4Vb4Kg=wtAFVfX+g@mail.gmail.com>"
    component = sorted([requested, canonical,
        "<49227237-5E25-4892-818E-8E5B953D9BA5@gmail.com>",
        "<CAG1bvutnbQcuWwfhKB6=V-b3_39jw+NQMnFRSC77jQhRGYB9HQ@mail.gmail.com>",
        "<CAJ1mzbEwB10-d=kUeaGvhcDQMJJ1yJ-bJcUNuzot9Bi=ysgryQ@mail.gmail.com>",
        "<CAJ1mzbFrPc4yJU0uLhe3KNDz0Di=sY2ks5q5bjZX20RauXpZeA@mail.gmail.com>",
        "<CAJ1mzbHEYW=6f-ugmw827uMg8Yz5o+0WLHfOCRDAz7Sn8pd2HA@mail.gmail.com>"])
    local = sorted([requested, component[0], component[1],
        "<CAJ1mzbFrPc4yJU0uLhe3KNDz0Di=sY2ks5q5bjZX20RauXpZeA@mail.gmail.com>"])
    primary = projection() | {"thread_key": requested, "authoritative_thread_key": canonical,
        "component_thread_keys": component, "component_scope_present": True,
        "reply_evidence": [{"scope": "primary"}]}
    peer = projection() | {"actor_uid": "peer", "thread_key": requested, "authoritative_thread_key": requested,
        "component_thread_keys": local, "component_scope_present": True,
        "reply_evidence": [{"scope": "original-peer"}]}
    fallback = projection() | {"actor_uid": "peer", "thread_key": canonical, "authoritative_thread_key": canonical,
        "component_thread_keys": [canonical], "component_scope_present": False,
        "reply_evidence": [{"scope": "canonical-peer"}]}
    return requested, canonical, primary, peer, fallback


def inbound(key=KEY, *, mid="<in@customer.example>", date=NOW):
    return {"email": EMAIL, "name": "Customer", "date": date, "subject": key,
            "message_id": mid, "thread_key": key}


class Consumer(unittest.TestCase):
    def test_account_failure_diagnostics_preserve_business_projection_and_read_counts(self):
        from cs import observability_producers, rpc_reads
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        for failed_uid in ("operator", "peer"):
            for mode in ("SOURCE_UNAVAILABLE", "REPLY_SOURCE_UNAVAILABLE", "SOURCE_OWNER_REQUIRED",
                         "unknown", "transport", "invalid", "remote"):
                calls, events = [], []
                def call(account, method, params, timeout=60):
                    uid = account.engine_owner_uid
                    calls.append(uid)
                    if uid != failed_uid:
                        return projection() | {"actor_uid": uid}
                    if mode == "transport":
                        raise ConnectionError("PRIVATE_EXCEPTION")
                    if mode == "remote":
                        raise rpc.EngineError(-32602, "PRIVATE_EXCEPTION")
                    if mode == "invalid":
                        return {"private": "PRIVATE_RESPONSE"}
                    return projection("unknown", complete=False) | {"actor_uid": uid,
                        "reason": "PRIVATE_REASON" if mode == "unknown" else mode}
                def many(account, method, requests, **kwargs):
                    outcomes = {}
                    for key, params in requests.items():
                        try:
                            outcomes[key] = rpc_reads.ReadOutcome(value=call(account, method, params))
                        except Exception as exc:
                            outcomes[key] = rpc_reads.ReadOutcome(error=exc)
                    return outcomes
                with self.subTest(account=failed_uid, mode=mode), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call), patch.object(rpc_reads, "read_many", side_effect=many), patch.object(observability_producers, "emit", side_effect=lambda *args, **kw: events.append(kw)):
                    for batched in (False, True):
                        calls.clear()
                        events.clear()
                        actual = assignment.projections(selected, [KEY])[KEY] if batched else assignment.project(selected, KEY)
                        invalid_primary = failed_uid == "operator" and mode in {"transport", "invalid", "remote"}
                        expected = assignment._unknown(KEY, "ignored", owner_uid="operator") if invalid_primary else projection("unknown", complete=False)
                        if failed_uid == "peer" and not invalid_primary:
                            expected["actor_uid"] = "operator"
                        expected.pop("reason")
                        self.assertEqual({k: v for k, v in actual.items() if k != "reason"}, expected)
                        account = "primary account" if failed_uid == "operator" else "peer account 'peer'"
                        cause = {"transport": "transport_unavailable", "invalid": "projection_invalid",
                                 "remote": "remote_invalid_params", "unknown": "unknown (upstream detail unavailable)"}.get(mode, mode)
                        self.assertIn(account, actual["reason"])
                        self.assertIn(cause, actual["reason"])
                        self.assertNotIn("PRIVATE_", actual["reason"])
                        self.assertIn(cause, assignment.render(actual))
                        expected_reads = 2 if batched and mode == "SOURCE_UNAVAILABLE" else 1
                        self.assertEqual(calls.count(failed_uid), expected_reads)
                        observations = [event for event in events if event.get("causal", {}).get("check") == "assignment_peer_projection"]
                        self.assertEqual(len(observations), expected_reads)

    def test_render_reuses_safe_root_fingerprint_and_only_existing_valid_references(self):
        from cs import observability, observability_producers
        row = projection("unknown", complete=False) | {"reason": "SOURCE_UNAVAILABLE"}
        original = copy.deepcopy(row)
        trace, run = "a" * 32, "b" * 32
        with patch.object(observability, "current_context", return_value={"trace_id": trace, "run_id": run}), patch.object(observability_producers, "emit") as emit:
            rendered = assignment.render(row)
            self.assertIn(f"root_sha256={observability.safe_metadata({'root_id': KEY})['root_id']}", rendered)
            self.assertIn(f"trace_id={trace} run_id={run}", rendered)
            self.assertNotIn(KEY, rendered.split("; diagnostic refs: ", 1)[1])
            self.assertNotEqual(rendered, assignment.render(row | {"thread_key": OTHER}))
            emit.assert_not_called()
        with patch.object(observability, "current_context", return_value={"trace_id": "PRIVATE_REFERENCE"}):
            rendered = assignment.render(row)
            self.assertIn("trace_id=unavailable run_id=unavailable", rendered)
            self.assertNotIn("PRIVATE_REFERENCE", rendered)
            self.assertIn("root_sha256=unavailable", assignment.render(row | {"thread_key": None}))
        self.assertEqual(row, original)
        self.assertEqual(assignment._account_context("operator", "peer", "peer"), "peer account 'peer'")

    def test_named_business_hold_reason_survives_account_aggregation(self):
        row = projection("needs-assignment", complete=False) | {"reason": "NEEDS_HUMAN_VERIFICATION"}
        with patch.object(rpc, "call_sync", return_value=row):
            self.assertEqual(assignment.project(settings(), KEY), row)

    def test_direct_rpc_errors_retain_typed_cause_identity_and_privacy(self):
        from cs import observability, observability_producers
        for error, expected in ((rpc.EngineError(-32602, "PRIVATE_MESSAGE", {"secret": "PRIVATE_DATA"}), "remote_invalid_params"),
                                (rpc.EngineError(-32001, "PRIVATE_MESSAGE", {"secret": "PRIVATE_DATA"}), "remote_error"),
                                (ConnectionError("PRIVATE_MESSAGE"), "transport_unavailable")):
            events = []
            with self.subTest(expected=expected), patch.object(rpc, "call_sync", side_effect=error) as called, patch.object(observability_producers, "emit", side_effect=lambda *args, **kw: events.append(observability.safe_metadata(kw))):
                with self.assertRaises(type(error)) as raised:
                    assignment._project_one(settings(), KEY)
                self.assertIs(raised.exception, error)
                called.assert_called_once_with(settings(), "tasks.assignment.project", {"thread_key": KEY}, timeout=150)
            self.assertEqual(events[0]["causal"]["cause"], expected)
            self.assertNotIn("PRIVATE_MESSAGE", json.dumps(events))
            self.assertNotIn("PRIVATE_DATA", json.dumps(events))

    def test_peer_failure_diagnostics_preserve_typed_causes_before_merge(self):
        from cs import observability, observability_producers
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        rows = {"operator": projection("unknown", complete=False) | {"reason": "REPLY_SOURCE_UNAVAILABLE",
            "reply_evidence": [{"version": 1, "actor_uid": "operator", "space_id": "company", "thread_key": KEY,
                "complete": False, "judgement": "UNKNOWN", "reason": "SENT_REPLY_NOT_SYNCED"}]},
            "peer": projection("unknown", complete=False) | {"actor_uid": "peer", "reason": "SECRET_SENTINEL"}}
        emitted = []
        def emit(*args, **kwargs):
            emitted.append(observability.safe_metadata(kwargs))
        with patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=lambda s, *a, **kw: rows[s.engine_owner_uid]), patch.object(observability_producers, "emit", side_effect=emit):
            result = assignment.project(selected, KEY)
        causes = [event["causal"]["cause"] for event in emitted if "causal" in event]
        self.assertIn("REPLY_SOURCE_UNAVAILABLE", causes)
        self.assertIn("SENT_REPLY_NOT_SYNCED", causes)
        self.assertIn("unknown", causes)
        self.assertEqual(result["state"], "unknown")
        self.assertNotIn("SECRET_SENTINEL", json.dumps(emitted))
        self.assertTrue(all(event["error_file"] == "cs/task_assignment.py" for event in emitted))

    def test_peer_reply_diagnostics_refuse_foreign_and_malformed_metadata(self):
        from cs import observability_producers
        for evidence, expected in [
            ({"complete": False, "judgement": "UNKNOWN", "reason": "SENT_REPLY_NOT_SYNCED"}, True),
            ({"complete": False, "judgement": "UNKNOWN", "reason": "SENT_REPLY_NOT_SYNCED", "actor_uid": "foreign"}, False),
            ({"complete": False, "judgement": "UNKNOWN", "reason": ["PRIVATE_SENTINEL"]}, False)]:
            events = []
            row = projection("unknown", complete=False) | {"reason": "REPLY_SOURCE_UNAVAILABLE", "reply_evidence": [evidence]}
            with patch.object(rpc, "call_sync", return_value=row), patch.object(observability_producers, "emit", side_effect=lambda *args, **kw: events.append(kw)):
                assignment.project(settings(), KEY)
            self.assertEqual(any(e["causal"]["cause"] == "SENT_REPLY_NOT_SYNCED" for e in events), expected)
            self.assertNotIn("PRIVATE_SENTINEL", json.dumps(events))
            self.assertEqual(events[0]["causal"]["cause"], "REPLY_SOURCE_UNAVAILABLE")
        for raw in (None, projection() | {"actor_uid": "foreign"}):
            events = []
            with patch.object(rpc, "call_sync", return_value=raw), patch.object(observability_producers, "emit", side_effect=lambda *args, **kw: events.append(kw)):
                self.assertEqual(assignment.project(settings(), KEY)["state"], "unknown")
            self.assertEqual(events[0]["causal"]["cause"], "projection_invalid")

    def test_batched_peer_failure_retains_first_cause_and_additional_observations(self):
        from cs import observability_causal as causal, observability_producers, rpc_reads
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        def read(s, method, requests, **kwargs):
            return {key: rpc_reads.ReadOutcome(value=projection("unknown", complete=False) | {
                "actor_uid": s.engine_owner_uid, "reason": "REPLY_SOURCE_UNAVAILABLE",
                "reply_evidence": [{"complete": False, "judgement": "UNKNOWN", "reason": "SENT_REPLY_NOT_SYNCED"}]}) for key in requests}
        events = []
        with causal.scope(), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc_reads, "read_many", side_effect=read), patch.object(observability_producers, "emit", side_effect=lambda *args, **kw: events.append((args[0].engine_owner_uid, kw))):
            result = assignment.projections(selected, [KEY])
            self.assertEqual(causal.selected()["cause"], "REPLY_SOURCE_UNAVAILABLE")
        self.assertEqual(result[KEY]["state"], "unknown")
        for uid in ("operator", "peer"):
            causes = [e["causal"]["cause"] for owner, e in events if owner == uid and e.get("causal")]
            self.assertIn("REPLY_SOURCE_UNAVAILABLE", causes)
            self.assertIn("SENT_REPLY_NOT_SYNCED", causes)
        with patch.object(rpc, "call_sync", return_value=projection("unknown", complete=False)), patch.object(observability_producers, "emit", side_effect=OSError("PRIVATE_SENTINEL")):
            self.assertEqual(assignment.project(settings(), KEY)["state"], "unknown")

    def test_alias_failure_is_observed_before_early_return(self):
        requested, canonical, primary, peer, fallback = captured_partial_component()
        peer = peer | {"component_thread_keys": sorted([*peer["component_thread_keys"], "<outside@example.test>"])}
        seen = []
        responses, unknown = assignment._resolve_account_aliases(requested, [("operator", primary), ("peer", peer)], [],
            lambda *args: self.fail("contradictory authority must not read"), observe=lambda response, code: seen.append(code))
        self.assertEqual(seen, ["alias_authority_conflict", "alias_authority_conflict"])
        self.assertEqual(unknown, ["contradictory component authority"])

    def test_typed_ancestry_conflict_exact_shape(self):
        raw = projection("conflict", complete=False) | {"reason": "RFC_ANCESTRY_CONFLICT",
            "authoritative_thread_key": KEY, "component_thread_keys": [KEY],
            "component_scope_present": False, "source_owner_uid": "operator"}
        self.assertEqual(assignment._validate_projection(settings(), KEY, raw), raw)
        changes = [("version", True), ("actor_uid", "peer"), ("space_id", ""),
            ("complete", True), ("state", "normal"), ("hold_auto_reply", False), ("task", task()),
            ("component_scope_present", True), ("component_scope_present", 0),
            ("authoritative_thread_key", OTHER), ("component_thread_keys", sorted([KEY, OTHER])),
            ("source_owner_uid", "peer"), ("authority_complete", True), ("hold_scope", "exact_observed_message")]
        changes += [(key, ["forged"]) for key in ("events", "covered_inbound", "current_inbound",
            "covered_message_ids", "current_message_ids", "reply_evidence")]
        malformed = [raw | {key: value} for key, value in changes]
        malformed += [{k: v for k, v in raw.items() if k != key} for key in raw]
        for changed in malformed:
            with self.subTest(changed=changed), self.assertRaises(assignment.AssignmentUnavailable):
                assignment._validate_projection(settings(), KEY, changed)

    def test_typed_ancestry_conflict_merge_guards_and_uncertainty(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        for conflict_actor in ("operator", "peer"):
            for mode in ("normal", "unknown", "offline", "assigned", "canonical", "untyped"):
                def call(account, method, params, timeout=60):
                    uid = account.engine_owner_uid
                    if uid == conflict_actor:
                        return projection("conflict", complete=False) | {"actor_uid": uid,
                            "source_owner_uid": uid, "reason": "fixture" if mode == "untyped" else "RFC_ANCESTRY_CONFLICT",
                            "authoritative_thread_key": KEY, "component_thread_keys": [KEY], "component_scope_present": False}
                    if mode == "offline":
                        raise ConnectionError("fixture")
                    result = projection("unknown", complete=False) if mode == "unknown" else projection("assigned", task=task()) if mode == "assigned" else projection()
                    result["actor_uid"] = uid
                    if mode == "canonical":
                        result.update(authoritative_thread_key=OTHER, component_thread_keys=sorted([KEY, OTHER]), component_scope_present=True)
                    return result
                def many(account, method, requests, **kwargs):
                    values = {}
                    for key, params in requests.items():
                        try:
                            values[key] = assignment.rpc_reads.ReadOutcome(value=call(account, method, params))
                        except Exception as exc:
                            values[key] = assignment.rpc_reads.ReadOutcome(error=exc)
                    return values
                with self.subTest(actor=conflict_actor, mode=mode), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call), patch.object(assignment.rpc_reads, "read_many", side_effect=many):
                    single = assignment.project(selected, KEY)
                    self.assertEqual(single, assignment.projections(selected, [KEY])[KEY])
                    self.assertEqual(single["state"], "conflict" if mode == "normal" else "unknown")
                    self.assertFalse(single["complete"])
                    self.assertTrue(single["hold_auto_reply"])
                    self.assertIsNone(single["task"])
                    self.assertIsNot(single.get("component_scope_present"), True)
                    self.assertEqual(single.get("component_thread_keys", [KEY]), [KEY])
                    if mode == "normal":
                        self.assertEqual(single["actor_uid"], conflict_actor)
                        self.assertEqual(single["reason"], "RFC_ANCESTRY_CONFLICT")
                    with self.assertRaises(assignment.AssignmentUnavailable):
                        assignment.guard(selected, KEY)
                    with patch.object(rpc, "chat") as chat, contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(cli.main(["draft-reply", "reply", "--thread-id", KEY]), 3)
                        chat.assert_not_called()

    def test_unavailable_and_malformed_scope_never_empty_success(self):
        for response in (None, {}, [], projection() | {"version": 2}, projection() | {"actor_uid": "forged"},
                         projection() | {"thread_key": OTHER}, projection("assigned", task=task()) | {"hold_auto_reply": False}):
            with self.subTest(response=response), patch.object(rpc, "call_sync", return_value=response):
                result = assignment.project(settings(), KEY)
                self.assertEqual(result["state"], "unknown")
                self.assertFalse(result["complete"])
                self.assertTrue(result["hold_auto_reply"])

    def test_observation_only_hold_validates_bound_evidence_without_inventing_authority(self):
        raw = malformed_observation()
        self.assertEqual(assignment._validate_projection(settings(), KEY, raw), raw)
        mutations = []
        for key, value in (("authority_complete", True), ("authority_complete", 0), ("hold_scope", "thread"),
                           ("complete", True), ("state", "normal"), ("hold_auto_reply", False), ("task", task()),
                           ("component_scope_present", True), ("source_owner_uid", "peer"), ("covered_inbound", ["forged"]),
                           ("current_inbound", ["forged"]), ("current_message_ids", [KEY]), ("covered_message_ids", [KEY])):
            mutations.append(raw | {key: value})
        for key in ("authority_complete", "hold_scope"):
            mutations.append({name: value for name, value in raw.items() if name != key})
        mutations.append(raw | {"reply_evidence": []})
        mutations.append(raw | {"reply_evidence": raw["reply_evidence"] * 2})
        for path, value in (("version", True), ("actor_uid", "peer"), ("space_id", "foreign"), ("source_id", ""),
                            ("thread_key", OTHER), ("complete", False), ("digest", "bad"), ("judgement", "AUTOMATIC"),
                            ("source.actor_uid", "peer"), ("source.mailbox_id", ""), ("source.message_id", OTHER),
                            ("source.thread_key", OTHER), ("source.observation_only", False), ("source.raw_header_digest", "bad"),
                            ("source.route_digest", "bad"), ("source.provider.uid", True), ("source.provider.uidvalidity", 0),
                            ("source.provider.folder", "")):
            changed = copy.deepcopy(raw)
            target = changed["reply_evidence"][0]
            fields = path.split(".")
            for field in fields[:-1]:
                target = target[field]
            target[fields[-1]] = value
            mutations.append(changed)
        mutations.append(raw | {"state": "normal", "complete": True, "hold_auto_reply": False})
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(assignment.AssignmentUnavailable):
                assignment._validate_projection(settings(), KEY, changed)
        with patch.object(rpc, "call_sync", return_value=raw | {"state": "normal", "complete": True, "hold_auto_reply": False}):
            with self.assertRaises(assignment.AssignmentUnavailable):
                assignment.guard(settings(), KEY)

    def test_observed_message_hold_cannot_clear_peer_failure_or_assignment(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        for mode in ("healthy", "unknown", "offline", "assigned", "company", "actor", "malformed-peer"):
            primary = malformed_observation() if mode != "malformed-peer" else projection()
            peer = malformed_observation() if mode == "malformed-peer" else projection("unknown", complete=False) if mode == "unknown" else projection("assigned", task=task()) if mode == "assigned" else projection()
            peer |= {"actor_uid": "peer"}
            if mode == "malformed-peer":
                peer["source_owner_uid"] = "peer"
                peer["reply_evidence"][0]["actor_uid"] = "peer"
                peer["reply_evidence"][0]["source"]["actor_uid"] = "peer"
            if mode == "company":
                peer["space_id"] = "foreign"
            if mode == "actor":
                peer["actor_uid"] = "forged"
            def call(account, method, params, timeout=60):
                if mode == "offline" and account.engine_owner_uid == "peer":
                    raise ConnectionError("fixture peer unavailable")
                return copy.deepcopy(primary if account.engine_owner_uid == "operator" else peer)
            def many(account, method, requests, **kwargs):
                result = {}
                for key, params in requests.items():
                    try:
                        result[key] = assignment.rpc_reads.ReadOutcome(value=call(account, method, params))
                    except Exception as exc:
                        result[key] = assignment.rpc_reads.ReadOutcome(error=exc)
                return result
            with self.subTest(mode=mode), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call), patch.object(assignment.rpc_reads, "read_many", side_effect=many):
                single = assignment.project(selected, KEY)
                bulk = assignment.projections(selected, [KEY])[KEY]
                self.assertEqual(single, bulk)
                self.assertFalse(single["complete"])
                self.assertTrue(single["hold_auto_reply"])
                self.assertEqual(single["state"], "needs-assignment" if mode in {"healthy", "malformed-peer"} else "conflict" if mode in {"assigned", "ancestry"} else "unknown")
                self.assertIn("MALFORMED_OWN_SENT_REQUIRES_HUMAN_VERIFICATION", [item.get("judgement") for item in single["reply_evidence"]])
                self.assertEqual(single["current_inbound"], [])
                self.assertEqual(single["covered_inbound"], [])
                self.assertIsNot(single.get("authority_complete"), True)
                with self.assertRaises(assignment.AssignmentUnavailable):
                    assignment.guard(selected, KEY)

    def test_observation_cannot_be_promoted_by_closed_creator_or_alias_assignment(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        for state in ("closed", "later-inbound", "assigned"):
            for failed_peer in (False, True):
                current = selected.model_copy(update={"accounts": "peer:peer,offline:offline"}) if failed_peer else selected
                shared = task("assigned" if state == "assigned" else "closed") | {"thread_key": OTHER, "creator_uid": "peer"}
                def call(account, method, params, timeout=60):
                    if account.engine_owner_uid == "offline":
                        raise ConnectionError("fixture peer unavailable")
                    key = params["thread_key"]
                    if account.engine_owner_uid == "operator" and key == KEY:
                        return malformed_observation()
                    if account.engine_owner_uid == "operator":
                        return projection("assigned" if state == "assigned" else "unknown", complete=state == "assigned", task=shared) | {
                            "thread_key": key, "authoritative_thread_key": key, "component_thread_keys": [key],
                            "component_scope_present": False, "reason": "HUMAN_ASSIGNMENT_ACTIVE" if state == "assigned" else "SOURCE_OWNER_REQUIRED", "source_owner_uid": "peer"}
                    return projection(state, task=shared) | {"actor_uid": "peer", "thread_key": key,
                        "authoritative_thread_key": OTHER, "component_thread_keys": sorted([KEY, OTHER]), "component_scope_present": True}
                def many(account, method, requests, **kwargs):
                    result = {}
                    for key, params in requests.items():
                        try:
                            result[key] = assignment.rpc_reads.ReadOutcome(value=call(account, method, params))
                        except Exception as exc:
                            result[key] = assignment.rpc_reads.ReadOutcome(error=exc)
                    return result
                with self.subTest(state=state, failed_peer=failed_peer), patch.object(config, "load", side_effect=lambda **kw: current.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call), patch.object(assignment.rpc_reads, "read_many", side_effect=many):
                    single = assignment.project(current, KEY)
                    bulk = assignment.projections(current, [KEY])[KEY]
                    self.assertEqual(single, bulk)
                    self.assertEqual(single["state"], "unknown")
                    self.assertFalse(single["complete"])
                    self.assertIs(single["authority_complete"], False)
                    self.assertTrue(single["hold_auto_reply"])
                    self.assertEqual(single["task"], shared)
                    self.assertIn("MALFORMED_OWN_SENT_REQUIRES_HUMAN_VERIFICATION", [item.get("judgement") for item in single["reply_evidence"]])
                    if failed_peer:
                        self.assertIn("offline", single["reason"])
                    with self.assertRaises(assignment.AssignmentUnavailable):
                        assignment.guard(current, KEY)

    def test_component_metadata_requires_exact_bound_shape(self):
        valid = projection("assigned", task=task() | {"thread_key": OTHER}) | {
            "authoritative_thread_key": OTHER, "component_thread_keys": sorted([KEY, OTHER]),
            "component_scope_present": True}
        self.assertEqual(assignment._validate_projection(settings(), KEY, valid)["task"]["thread_key"], OTHER)
        for changes in ({"component_scope_present": False}, {"component_scope_present": 1},
                        {"component_thread_keys": [OTHER]}, {"component_thread_keys": [KEY, KEY, OTHER]},
                        {"component_thread_keys": ["bad", KEY, OTHER]}, {"authoritative_thread_key": KEY},
                        {"component_thread_keys": None}):
            with self.subTest(changes=changes), self.assertRaises(assignment.AssignmentUnavailable):
                assignment._validate_projection(settings(), KEY, valid | changes)
        for field in ("authoritative_thread_key", "component_thread_keys", "component_scope_present"):
            with self.assertRaises(assignment.AssignmentUnavailable):
                assignment._validate_projection(settings(), KEY, {k: v for k, v in valid.items() if k != field})

    def test_sparse_peer_canonical_fallback_preserves_original_hold_and_evidence(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        shared = task() | {"thread_key": OTHER}
        primary = projection("assigned", task=shared) | {"authoritative_thread_key": OTHER,
            "component_thread_keys": sorted([KEY, OTHER]), "component_scope_present": True}
        for original_state in ("normal", "needs-assignment", "unknown"):
            calls = []
            def call(account, method, params, timeout):
                calls.append((account.engine_owner_uid, params["thread_key"]))
                if account.engine_owner_uid == "operator":
                    return primary
                key = params["thread_key"]
                result = projection("assigned", task=shared) if key == OTHER else projection(original_state,
                    complete=original_state != "unknown")
                return result | {"actor_uid": "peer", "thread_key": key, "authoritative_thread_key": key,
                    "component_thread_keys": [key], "component_scope_present": False,
                    "reply_evidence": [{"original": True}] if key == KEY else []}
            with patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call):
                result = assignment.project(selected, KEY)
            self.assertEqual(result["thread_key"], KEY)
            self.assertTrue(result["hold_auto_reply"])
            self.assertEqual(result["task"], shared)
            self.assertIn({"original": True}, result["reply_evidence"])
            self.assertEqual(result["state"], "unknown" if original_state == "unknown" else "assigned")
            self.assertIn(("peer", OTHER), calls)

    def test_sparse_alias_fallback_cannot_clear_original_candidate_or_bad_peer(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        primary = projection() | {"authoritative_thread_key": OTHER,
            "component_thread_keys": sorted([KEY, OTHER]), "component_scope_present": True}
        for mode in ("candidate", "unknown", "conflict", "normal-held", "company", "actor", "task", "authority", "offline"):
            def call(account, method, params, timeout=60):
                if account.engine_owner_uid == "operator":
                    return primary
                key = params["thread_key"]
                result = projection("needs-assignment" if key == KEY and mode == "candidate" else "unknown"
                    if key == KEY and mode == "unknown" else "normal", complete=not (key == KEY and mode == "unknown"))
                if key == KEY and mode in {"conflict", "normal-held"}:
                    result.update(state="conflict" if mode == "conflict" else "normal", hold_auto_reply=True)
                result |= {"actor_uid": "peer", "thread_key": key, "authoritative_thread_key": key,
                    "component_thread_keys": [key], "component_scope_present": False,
                    "reply_evidence": [{"original": True}] if key == KEY else []}
                if key == OTHER:
                    if mode == "offline":
                        raise ConnectionError("fixture")
                    if mode == "company":
                        result["space_id"] = "foreign"
                    if mode == "actor":
                        result["actor_uid"] = "forged"
                    if mode == "task":
                        result.update(state="assigned", hold_auto_reply=True, task=task() | {"thread_key": OTHER})
                if key == KEY and mode == "authority":
                    result["component_scope_present"] = True
                    result["component_thread_keys"] = sorted([KEY, OTHER])
                return result
            def many(account, method, requests, **kwargs):
                outcomes = {}
                for key, params in requests.items():
                    try:
                        outcomes[key] = assignment.rpc_reads.ReadOutcome(value=call(account, method, params))
                    except Exception as exc:
                        outcomes[key] = assignment.rpc_reads.ReadOutcome(error=exc)
                return outcomes
            with self.subTest(mode=mode), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call), patch.object(assignment.rpc_reads, "read_many", side_effect=many):
                single = assignment.project(selected, KEY)
                bulk = assignment.projections(selected, [KEY])[KEY]
                self.assertEqual(single, bulk)
                self.assertTrue(single["hold_auto_reply"])
                self.assertIn(single["state"], {"needs-assignment", "unknown", "conflict"})
                self.assertIn({"original": True}, single["reply_evidence"])

    def test_captured_partial_component_requires_canonical_scope_and_keeps_every_hold(self):
        selected = settings().model_copy(update={"accounts": "peer:peer"})
        for mode in ("normal", "primary-candidate", "primary-unknown", "original-conflict", "original-unknown",
                     "original-candidate", "canonical-unknown", "canonical-conflict", "canonical-candidate",
                     "non-subset", "canonical-known", "equal-components", "canonical-authority",
                     "canonical-company", "canonical-actor", "canonical-offline", "task-race", "shared-task", "original-task"):
            requested, canonical, primary, peer, fallback = captured_partial_component()
            if mode.startswith("primary-") and mode != "primary-sparse":
                state = "needs-assignment" if mode == "primary-candidate" else "unknown"
                primary.update(state=state, complete=False, hold_auto_reply=True)
            if mode.startswith("original-") and mode != "original-task":
                state = {"original-conflict": "conflict", "original-unknown": "unknown", "original-candidate": "needs-assignment"}[mode]
                peer.update(state=state, complete=state == "conflict", hold_auto_reply=True)
            if mode in {"canonical-unknown", "canonical-conflict", "canonical-candidate"}:
                state = {"canonical-unknown": "unknown", "canonical-conflict": "conflict", "canonical-candidate": "needs-assignment"}[mode]
                fallback.update(state=state, complete=state == "conflict", hold_auto_reply=True)
            if mode == "non-subset":
                peer["component_thread_keys"] = sorted([*peer["component_thread_keys"], "<outside@example.test>"])
            if mode == "canonical-known":
                peer["component_thread_keys"] = sorted([*peer["component_thread_keys"], canonical])
            if mode == "equal-components":
                peer["component_thread_keys"] = primary["component_thread_keys"]
            if mode == "canonical-authority":
                fallback.update(authoritative_thread_key=requested, component_thread_keys=sorted([requested, canonical]), component_scope_present=True)
            if mode == "canonical-company":
                fallback["space_id"] = "foreign"
            if mode == "canonical-actor":
                fallback["actor_uid"] = "forged"
            if mode in {"task-race", "shared-task"}:
                primary.update(state="assigned", hold_auto_reply=True, task=task() | {"thread_key": canonical})
                fallback.update(state="assigned", hold_auto_reply=True, task=task() | {"thread_key": canonical,
                    "revision": 2 if mode == "task-race" else 1})
            if mode == "original-task":
                peer.update(state="assigned", hold_auto_reply=True, task=task() | {"thread_key": requested})
            calls = []
            deadlines = []
            def call(account, method, params, timeout=60):
                key = params["thread_key"]
                calls.append((account.engine_owner_uid, key))
                if account.engine_owner_uid == "operator":
                    self.assertEqual(key, requested)
                    return copy.deepcopy(primary)
                if key == requested:
                    return copy.deepcopy(peer)
                self.assertEqual(key, canonical)
                if mode == "canonical-offline":
                    raise ConnectionError("fixture canonical scope unavailable")
                return copy.deepcopy(fallback)
            def many(account, method, requests, **kwargs):
                self.assertEqual(kwargs["request_timeout"], 150)
                self.assertEqual(kwargs["batch_timeout"], 180)
                deadlines.append(kwargs["deadline"])
                outcomes = {}
                for key, params in requests.items():
                    try:
                        outcomes[key] = assignment.rpc_reads.ReadOutcome(value=call(account, method, params))
                    except Exception as exc:
                        outcomes[key] = assignment.rpc_reads.ReadOutcome(error=exc)
                return outcomes
            with self.subTest(mode=mode), patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call), patch.object(assignment.rpc_reads, "read_many", side_effect=many):
                single = assignment.project(selected, requested)
                with patch.object(assignment.time, "monotonic", return_value=10):
                    bulk = assignment.projections(selected, [requested])[requested]
                self.assertEqual(single, bulk)
                self.assertEqual(single["thread_key"], requested)
                self.assertEqual(set(deadlines), {3610 - 2 * assignment.rpc_reads.CLOSE_SECONDS})
                if mode == "normal":
                    self.assertEqual(single["state"], "normal")
                    self.assertTrue(single["complete"])
                    self.assertFalse(single["hold_auto_reply"])
                else:
                    self.assertTrue(single["hold_auto_reply"])
                    self.assertIn(single["state"], {"unknown", "conflict", "needs-assignment", "assigned"})
                if mode in {"non-subset", "canonical-known", "equal-components"}:
                    self.assertNotIn(("peer", canonical), calls)
                else:
                    self.assertIn(("peer", canonical), calls)
                expected_state = {"normal": "normal", "primary-candidate": "needs-assignment", "original-candidate": "needs-assignment",
                    "canonical-candidate": "needs-assignment", "original-conflict": "conflict", "canonical-conflict": "conflict",
                    "task-race": "conflict", "original-task": "conflict", "shared-task": "assigned"}.get(mode, "unknown")
                self.assertEqual(single["state"], expected_state)
                if mode == "shared-task":
                    self.assertEqual(single["task"], primary["task"])
                if mode == "primary-unknown":
                    self.assertEqual(single["state"], "unknown")
                    self.assertNotIn("contradictory component authority", single["reason"])
                self.assertIn({"scope": "primary"}, single["reply_evidence"])
                self.assertIn({"scope": "original-peer"}, single["reply_evidence"])
                if mode not in {"non-subset", "canonical-known", "equal-components", "canonical-company", "canonical-actor", "canonical-offline"}:
                    self.assertIn({"scope": "canonical-peer"}, single["reply_evidence"])

    def test_partial_component_requires_primary_proof_before_selecting_between_peer_authorities(self):
        requested, canonical, primary, peer, fallback = captured_partial_component()
        selected = settings().model_copy(update={"accounts": "peer:peer,second:second"})
        sparse = projection() | {"thread_key": requested, "authoritative_thread_key": requested,
            "component_thread_keys": [requested], "component_scope_present": False}
        values = {"operator": sparse, "peer": primary | {"actor_uid": "peer"}, "second": peer | {"actor_uid": "second"}}
        def call(account, method, params, timeout=60):
            self.assertEqual(params["thread_key"], requested)
            return copy.deepcopy(values[account.engine_owner_uid])
        def many(account, method, requests, **kwargs):
            return {key: assignment.rpc_reads.ReadOutcome(value=call(account, method, params)) for key, params in requests.items()}
        with patch.object(config, "load", side_effect=lambda **kw: selected.model_copy(update=kw)), patch.object(rpc, "call_sync", side_effect=call), patch.object(assignment.rpc_reads, "read_many", side_effect=many):
            single = assignment.project(selected, requested)
            bulk = assignment.projections(selected, [requested])[requested]
        self.assertEqual(single, bulk)
        self.assertEqual(single["state"], "unknown")
        self.assertTrue(single["hold_auto_reply"])
        self.assertIn("contradictory component authority", single["reason"])

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

    @patch.dict(os.environ, {"CS_OPERATOR_HEADLESS": "1"})
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


class ObservationTransport(unittest.IsolatedAsyncioTestCase):
    async def test_direct_observer_uses_actual_rpc_error_response(self):
        import asyncio
        from cs import observability_producers
        class Response:
            async def __aiter__(self):
                yield json.dumps({"id": 1, "error": {"code": -32602, "message": "PRIVATE_MESSAGE", "data": {"secret": "PRIVATE_DATA"}}})
        client = rpc.EngineClient(settings())
        client._ws = Response()
        future = asyncio.get_running_loop().create_future()
        client._pending[1] = future
        await client._recv_loop()
        with self.assertRaises(rpc.EngineError) as received:
            await future
        error = received.exception
        self.assertEqual(error.code, -32602)
        events = []
        with patch.object(rpc, "call_sync", side_effect=error), patch.object(observability_producers, "emit", side_effect=lambda *args, **kw: events.append(kw)):
            with self.assertRaises(rpc.EngineError) as raised:
                assignment._project_one(settings(), KEY)
        self.assertIs(raised.exception, error)
        self.assertEqual(events[0]["causal"]["cause"], "remote_invalid_params")
        self.assertNotIn("PRIVATE_MESSAGE", json.dumps(events))
        self.assertNotIn("PRIVATE_DATA", json.dumps(events))

    async def test_real_cli_and_health_preserve_observed_hold_and_other_peer_failures(self):
        import asyncio
        import base64
        import os
        import time
        import websockets
        from cs import engine_view, operator_health
        current = {"mode": "healthy"}
        dispatch = []
        async def handler(ws):
            uid = ws.request.path.rsplit("/", 1)[-1]
            async for raw in ws:
                frame = json.loads(raw)
                if frame["method"] == "system.capabilities":
                    self.assertEqual(frame["params"], {})
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": {}}))
                    continue
                self.assertEqual(frame["method"], "tasks.assignment.project")
                self.assertEqual(frame["params"], {"thread_key": KEY})
                dispatch.append((current["mode"], uid))
                if uid == "peer" and current["mode"] == "offline":
                    await ws.close()
                    continue
                response = malformed_observation() if uid == "operator" else projection("assigned", task=task()) if current["mode"] == "assigned" else projection("unknown", complete=False) if current["mode"] == "unknown" else projection()
                if current["mode"] in {"ancestry", "ancestry-unknown"}:
                    response = (projection("conflict", complete=False) | {"reason": "RFC_ANCESTRY_CONFLICT",
                        "authoritative_thread_key": KEY, "component_thread_keys": [KEY],
                        "component_scope_present": False, "source_owner_uid": "operator"}) if uid == "operator" else projection("unknown", complete=False) if current["mode"] == "ancestry-unknown" else projection()
                response["actor_uid"] = uid
                if uid == "operator" and current["mode"] == "contradictory":
                    response.update(state="normal", complete=True, hold_auto_reply=False)
                await ws.send(json.dumps({"jsonrpc": "2.0", "id": frame["id"], "result": response}))
        token = "fixture." + base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + 3600}).encode()).decode().rstrip("=") + ".fixture"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for uid in ("operator", "peer"):
                (root / (uid + ".json")).write_text(json.dumps({"uid": uid, "id_token": token}))
            async with websockets.serve(handler, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                selected = settings().model_copy(update={"accounts": "peer:peer", "db_path": str(root / "state.db"),
                    "engine_ws_url": f"ws://127.0.0.1:{port}", "firebase_web_api_key": "fixture-public-key"})
                def load(**kwargs):
                    uid = kwargs.get("engine_owner_uid", "operator")
                    return selected.model_copy(update={**kwargs, "token_cache_path": str(root / (uid + ".json"))})
                for mode in ("healthy", "offline", "unknown", "assigned", "contradictory", "ancestry", "ancestry-unknown"):
                    current["mode"] = mode
                    output = io.StringIO()
                    with patch.object(config, "load", side_effect=load), patch.object(gmail_archive, "inbound_recent", return_value=[inbound()]), patch.object(gmail_archive, "sent_recent", return_value=[]), patch.object(engine_view, "classify", return_value=({}, None)), patch.object(engine_view, "settled", return_value=({}, None)), patch.dict(os.environ, {}, clear=False), contextlib.redirect_stdout(output):
                        os.environ.pop("CS_OPERATOR_HEALTH_CONTEXT", None)
                        os.environ.pop("CS_OPERATOR_ACCEPTANCE_RECEIPT", None)
                        code = await asyncio.to_thread(cli.main, ["unanswered", "--json", "--all-buckets"])
                    discovery = json.loads(output.getvalue())
                    self.assertEqual(code, 3)
                    self.assertEqual(discovery["open"], [])
                    self.assertTrue(discovery["assignment_incomplete"])
                    held = discovery["human_work"][0]["assignment"]
                    self.assertEqual(held["state"], "needs-assignment" if mode == "healthy" else "conflict" if mode in {"assigned", "ancestry"} else "unknown")
                    self.assertFalse(held["complete"])
                    self.assertTrue(held["hold_auto_reply"])
                    if mode not in {"contradictory", "ancestry", "ancestry-unknown"}:
                        self.assertIs(held["authority_complete"], False)
                        self.assertEqual(held["hold_scope"], "exact_observed_message")
                    health_dir = root / mode
                    health_dir.mkdir(mode=0o700)
                    context = {"directory": str(health_dir), "nonce": "fixture-" + mode,
                        "supervisor": {"pid": 100, "started_ticks": 1}}
                    child = {"pid": 101, "started_ticks": 2}
                    payload = (json.dumps(discovery, ensure_ascii=False, indent=2, default=str) + "\n").encode()
                    record = {"nonce": context["nonce"], "owner_uid": "operator", "ancestry": [child, {"pid": 102, "started_ticks": 3}, context["supervisor"]],
                        "exit_code": code, "output_sha256": hashlib.sha256(payload).hexdigest(), "discovery": discovery}
                    artifact = health_dir / "discovery.json"
                    artifact.write_text(json.dumps(record))
                    artifact.chmod(0o600)
                    self.assertEqual(operator_health.assess(context, child, "operator"), "" if mode in {"healthy", "ancestry"} else "assignment_read_incomplete")
                    self.assertEqual({uid for case, uid in dispatch if case == mode}, {"operator", "peer"})


if __name__ == "__main__":
    unittest.main()
