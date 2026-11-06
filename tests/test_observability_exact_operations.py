"""Actual exact CLI producers through logs, collection and private problem projection."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cs import cli, config, rpc, task_assignment
from cs.observability import store_for
from cs.monitor import scan
from cs.monitor_config import Component, MonitorConfig
from cs.monitor_store import MonitorStore
from test_interactive_draft_continuity import DRAFT, ROOT, TARGET


def execute_case(home, mode):
    with patch.dict(os.environ, {"HOME": str(home)}, clear=True):
        settings = config.Settings(email_address=DRAFT["owner_id"], engine_owner_uid="fixture-owner")
        calls = []

        def call(settings, method, params, **kwargs):
            calls.append(method)
            if method == "system.capabilities":
                return {} if mode == "unpublished" else {"exact_draft_publication": 1}
            if method == "drafts.inspect":
                draft = {**DRAFT, "body": "changed body"} if mode == "changed" and calls.count(method) > 1 else DRAFT
                return {"ok": True, "draft": draft, "expected_snapshot": "a" * 64}
            if method == "drafts.list":
                return [DRAFT]
            if method == "drafts.publish_review":
                if mode == "conflict":
                    return {"version":1, "ok":False, "cause":"thread_copy_conflict", "draft_id":DRAFT["id"], "operation_id":params["operation_id"], "state":"publication-failed", "achieved_stages":["engine-saved"], "effect_certainty":"not-dispatched", "next_action":"inspect-thread-copies"}
                raise TimeoutError("CANARY_BODY recipient@example.test token=secret")
            raise AssertionError(method)

        projection = dict(actor_uid="fixture-owner", source_owner_uid="fixture-owner", thread_key=ROOT,
            task=None, state="needs-assignment", reason="NEEDS_HUMAN_VERIFICATION", hold_auto_reply=True,
            current_message_ids=[TARGET], reply_evidence=[dict(complete=True, judgement="MEMBER_ACTIVITY_REQUIRES_HUMAN_VERIFICATION")])
        args = ["draft-reply", "--resume-draft", DRAFT["id"], "--thread-id", ROOT, "--json"]
        if mode == "hold":
            args = ["draft-send", DRAFT["id"]]
        if mode == "healthy":
            args = ["config", "--json"]
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(config, "load", return_value=settings), patch.object(rpc, "call_sync", call), patch.object(task_assignment, "project", return_value=projection), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = cli.main(args)
            logs = io.StringIO()
            with contextlib.redirect_stdout(logs):
                log_code = cli.main(["logs", "events", "--local", "--json"])
        store = store_for(settings)
        now = int(time.time()) + 1
        monitor = MonitorConfig(monitor_id="a" * 32, owner_uid=settings.engine_owner_uid, state_dir=str(Path(home) / "collector"), expected_start_utc=now, mode="filesystem", components=[Component(id="operator", kind="kernel", local_root=str(store.root))])
        first = scan(monitor, now=now)
        first_inbox = json.loads((Path(monitor.state_dir) / "problems.json").read_text())
        second = scan(monitor, now=now + 60)
        inbox = json.loads((Path(monitor.state_dir) / "problems.json").read_text())
        return dict(code=code, log_code=log_code, calls=calls, logs=json.loads(logs.getvalue()), events=store.events()["events"], inbox=inbox, first_inbox=first_inbox, first=first, second=second, incidents=MonitorStore(monitor.state_dir, settings.engine_owner_uid).incidents())


class ExactOperationJourney(unittest.TestCase):
    def test_actual_producers_collector_inbox_and_redaction(self):
        for mode, cause in (("unpublished", "saved_unpublished"), ("hold", "automatic_manual_hold"), ("healthy", None), ("unknown", "unknown")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as home:
                result = execute_case(home, mode)
                events = result["events"]
                self.assertEqual(result["log_code"], 0)
                self.assertEqual(result["code"], 0 if mode == "healthy" else 3)
                self.assertEqual(result["first"]["open_incidents"], result["second"]["open_incidents"])
                for inbox in (result["first_inbox"], result["inbox"]):
                    for problem in inbox["problems"]:
                        if problem["evidence"].get("effect_certainty") == "unknown":
                            self.assertIs(problem["evidence"]["uncertain"], True)
                raw = json.dumps([result["logs"], result["inbox"]])
                for secret in (DRAFT["body"], DRAFT["id"], ROOT, "CANARY_BODY", "recipient@example.test", "token=secret"):
                    self.assertNotIn(secret, raw)
                if cause:
                    selected = [e for e in events if e.get("causal")]
                    self.assertTrue(selected)
                    self.assertEqual({e["causal"]["cause"] for e in selected}, {cause})
                    ids = {e["event_id"] for e in events}
                    for event in selected:
                        ref = event["causal"]["refs"]["cause_event_id"]
                        self.assertTrue(ref is None or ref in ids)
                    if mode != "hold":
                        self.assertTrue(result["inbox"]["problems"])
                        self.assertTrue(all(p["evidence"]["causal"]["cause"] == cause for p in result["inbox"]["problems"]))
                    else:
                        self.assertEqual(result["inbox"]["problem_count"], 0)
                else:
                    self.assertEqual(result["inbox"]["problem_count"], 0)

    def test_changed_snapshot_and_conflicting_publication_keep_first_cause(self):
        for mode,cause in (("changed","changed_snapshot"),("conflict","thread_conflict")):
            with tempfile.TemporaryDirectory() as home:
                result=execute_case(home,mode)
                self.assertEqual(result["code"],3)
                events=[event for event in result["events"] if event.get("causal")]
                self.assertTrue(events)
                self.assertEqual({event["causal"]["cause"] for event in events},{cause})
                self.assertEqual(events[-1]["effect_certainty"],"none")

    def test_failed_sink_does_not_change_business_outcome(self):
        with tempfile.TemporaryDirectory() as home, patch("cs.observability_store.append", side_effect=OSError("CANARY_BODY")):
            result = execute_case(home, "unpublished")
            self.assertEqual(result["code"], 3)
            self.assertNotIn("drafts.publish_review", result["calls"])

    def test_actual_move_timeout_keeps_cause_and_operation(self):
        from cs import draft_lifecycle
        from cs.observability import context
        from cs.observability_causal import scope
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME":home}, clear=True):
            settings = config.Settings(email_address=DRAFT["owner_id"], engine_owner_uid="fixture-owner")
            def call(settings, method, params, **kwargs):
                if method == "system.capabilities": return {"sent_mirror_recovery":1}
                if method == "drafts.inspect": return dict(ok=True,draft_id=DRAFT["id"],owner_id=settings.email_address,engine_owner_uid=settings.engine_owner_uid,expected_snapshot="a"*64)
                raise TimeoutError("CANARY_BODY")
            with scope(), context(), patch.object(rpc,"call_sync",call):
                result=draft_lifecycle.retire_sent_mirror(settings,DRAFT["id"],"1","2",thread_id=ROOT,commit=True,gmail_fingerprint="b"*64,engine_snapshot="a"*64,gmail_folder="Drafts",operation_id="move-case")
            self.assertEqual(result["effect_certainty"],"unknown")
            events=store_for(settings).events()["events"]
            observed=[e for e in events if e.get("causal")]
            self.assertTrue(observed)
            self.assertEqual({e["causal"]["cause"] for e in observed},{"uncertain_provider_outcome"})
            self.assertTrue(all(e["effect_certainty"]=="unknown" for e in observed))
            self.assertNotIn("CANARY_BODY",json.dumps(events))

    def test_exact_claim_unknown_survives_admission_and_exit_wrapper(self):
        from test_operator_send import OperatorSendTests
        fixture=OperatorSendTests()
        fixture.setUp()
        try:
            original=fixture.rpc
            def call(settings,method,params,**kwargs):
                result=original(settings,method,params,**kwargs)
                if method=="drafts.send_operator":
                    result.update(ok=False,state="delivery-unknown",effect_certainty="unknown",achieved_stages=["engine-saved"],cause="exact_send_unconfirmed",next_action="inspect-operation")
                    result.pop("provider_handles")
                return result
            with patch.object(fixture,"rpc",call):
                code,_,_=fixture.run_cli(["draft-send","draft","--operator-request","--json"])
            self.assertEqual(code,3)
            selected=[e for e in store_for(fixture.settings).events()["events"] if e.get("causal")]
            self.assertTrue(selected)
            self.assertEqual({e["causal"]["cause"] for e in selected},{"uncertain_provider_outcome"})
            self.assertEqual(selected[-1]["stage"],"cli")
        finally:
            fixture.doCleanups()

    def test_verified_cli_delivery_clears_only_matching_uncertainty(self):
        import hashlib
        from test_operator_send import OperatorSendTests
        for ending in ("verified", "other-operation", "incomplete-proof"):
            with self.subTest(ending=ending):
                fixture = OperatorSendTests()
                fixture.setUp()
                try:
                    original = fixture.rpc
                    phase = ["unknown"]
                    def call(settings, method, params, **kwargs):
                        answer = original(settings, method, params, **kwargs)
                        if method == "drafts.send_operator":
                            if phase[0] == "unknown":
                                answer.update(ok=False,state="delivery-unknown",effect_certainty="unknown",achieved_stages=["engine-saved"],cause="exact_send_unconfirmed",next_action="inspect-operation")
                                answer.pop("provider_handles")
                            elif ending == "incomplete-proof":
                                answer["provider_handles"] = {}
                        return answer
                    store = store_for(fixture.settings)
                    now = int(time.time())
                    monitor = MonitorConfig(monitor_id="a"*32,owner_uid="owner",state_dir=str(Path(fixture.directory.name)/"collector"),expected_start_utc=now,mode="filesystem",components=[Component(id="operator",kind="kernel",local_root=str(store.root))])
                    def inbox():
                        scan(monitor, now=time.time()+1)
                        return json.loads((Path(monitor.state_dir)/"problems.json").read_text())["problems"]
                    def run(operation):
                        with patch.object(fixture,"rpc",call):
                            return fixture.run_cli(["draft-send","draft","--operator-request","--operation-id",operation,"--json"])[0]
                    self.assertEqual(run("selected"),3)
                    self.assertEqual(run("unrelated"),3)
                    initial = inbox()
                    selected_hash = hashlib.sha256(b"selected").hexdigest()
                    unrelated_hash = hashlib.sha256(b"unrelated").hexdigest()
                    self.assertTrue(any(row["evidence"].get("operation_id")==selected_hash and row["evidence"]["uncertain"] for row in initial))
                    phase[0] = "verified"
                    target = "different" if ending == "other-operation" else "selected"
                    self.assertEqual(run(target),3 if ending == "incomplete-proof" else 5)
                    final = inbox()
                    for problems in (final, inbox()):
                        details = [row["evidence"] for row in problems]
                        self.assertTrue(any(row.get("operation_id")==unrelated_hash and row["uncertain"] for row in details))
                        selected = [row for row in details if row.get("operation_id")==selected_hash]
                        self.assertTrue(selected)
                        if ending == "verified":
                            self.assertTrue(all(row["effect_certainty"]=="verified" and not row["uncertain"] for row in selected))
                            self.assertTrue(all(row["causal"]["cause"]=="sent_verified_cleanup_pending" for row in selected))
                        else:
                            self.assertTrue(any(row["uncertain"] for row in selected))
                    self.assertEqual(len(final),len(inbox()))
                finally:
                    fixture.doCleanups()

    def test_retained_first_cause_keeps_original_trace_and_reference(self):
        from cs.observability import context
        from cs.observability_causal import scope
        from cs.observability_operations import record
        from cs.monitor_evaluate import initial_state, observe
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ,{"HOME":home},clear=True):
            settings=config.Settings(engine_owner_uid="owner")
            common=dict(ok=False,draft_id="draft",root="root",operation_id="same",expected_snapshot="a"*64,effect_certainty="unknown",achieved_stages=["engine-saved"])
            for cause in ("exact_send_unconfirmed","unknown"):
                with scope(), context():
                    record(settings,{**common,"cause":cause},command="draft-send")
            events=store_for(settings).events()["events"]
            state=initial_state()
            for event in events: observe(state,event,time.time()+1)
            self.assertEqual(len(state["failures"]),1)
            retained=next(iter(state["failures"].values()))
            self.assertEqual(retained["causal"],events[0]["causal"])
            self.assertEqual(retained["event_id"],events[0]["event_id"])
            self.assertEqual(retained["trace_id"],events[0]["trace_id"])
            self.assertNotEqual(events[0]["trace_id"],events[1]["trace_id"])

    def test_safe_metadata_rejects_unbounded_stages(self):
        from cs.observability import safe_metadata
        self.assertNotIn("achieved_stages", safe_metadata({"achieved_stages": ["CANARY_BODY"]}))
        self.assertNotEqual(safe_metadata({"operation_id": "private"})["operation_id"], "private")


if __name__ == "__main__":
    unittest.main()
