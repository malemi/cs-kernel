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
class ExactOperationJourney(unittest.TestCase):
    def test_send_confirmation_recovers_only_matching_uncertainty(self):
        import hashlib
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME":home}, clear=True):
            selected = config.Settings(engine_owner_uid="fixture-owner")
            store = store_for(selected)
            confirmed = set()
            def call(settings, method, params, **kwargs):
                if method == "system.capabilities":
                    return {"mailbox_drafts": 1}
                self.assertEqual(method, "drafts.send")
                key = params["request_key"]
                if key not in confirmed:
                    raise TimeoutError("CANARY_BODY")
                return {"ok":True, "request_key":key, "draft_id":params["draft_id"], "state":"sent",
                        "message_id":"<sent@example.test>", "effect_certainty":"verified"}
            monitor = MonitorConfig(monitor_id="a"*32, owner_uid="fixture-owner", state_dir=str(Path(home)/"collector"),
                expected_start_utc=int(time.time()), mode="filesystem", components=[Component(id="operator",kind="kernel",local_root=str(store.root))])
            def run(key):
                with patch.object(config, "load", return_value=selected), patch.object(rpc,"call_sync",call), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    return cli.main(["draft-send","native-"+key,"--request-key",key])
            def uncertain():
                scan(monitor, now=time.time()+1)
                problems=json.loads((Path(monitor.state_dir)/"problems.json").read_text())["problems"]
                self.assertNotIn("CANARY_BODY",json.dumps(problems))
                return {p["evidence"].get("operation_id") for p in problems if p["evidence"].get("uncertain")}
            def digest(key):
                return hashlib.sha256(key.encode()).hexdigest()
            self.assertEqual(run("selected"),5)
            self.assertEqual(run("unrelated"),5)
            self.assertEqual(uncertain(), {digest("selected"), digest("unrelated")})
            confirmed.add("selected")
            self.assertEqual(run("selected"),0)
            self.assertEqual(uncertain(), {digest("unrelated")})
            self.assertEqual(uncertain(), {digest("unrelated")})
            self.assertNotIn("CANARY_BODY", json.dumps(store.events()))

    def test_broken_log_sink_preserves_verified_receipt(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME":home}, clear=True):
            selected=config.Settings(engine_owner_uid="fixture-owner")
            result={"ok":True, "state":"trashed", "draft_id":"named", "request_key":"operation","effect_certainty":"verified"}
            with patch.object(config,"load",return_value=selected), patch.object(rpc,"call_sync",side_effect=[{"mailbox_drafts":1},result]), patch("cs.observability_store.append",side_effect=OSError("offline")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["draft-delete","named","--commit","--request-key","operation"]),0)

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
