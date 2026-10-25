"""Additional observer failure controls using real stores and local HTTP only."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs.monitor import _read_component, scan
from cs.monitor_config import Component, Endpoint, MonitorConfig, WatchdogConfig
from cs.monitor_evaluate import evaluate, initial_state, observe
from cs.monitor_store import MonitorStore
from cs.monitor_watchdog import receive
from cs.observability import EventStore, context, store_for


class FaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = int(time.time())

    def tearDown(self):
        self.temp.cleanup()

    def test_lost_ack_replays_only_diagnostics_and_drains_originals_after_restart(self):
        source = EventStore(self.root / "source", "owner")
        produced = {source.emit("cli", "result", reason="none")["event_id"] for _ in range(301)}
        config = MonitorConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "monitor"),
            expected_start_utc=self.now,
            alert=Endpoint(url="https://alerts.invalid/events", token_env="ALERT"),
            watchdog=Endpoint(url="https://watch.invalid/heartbeat", token_env="WATCH"),
            components=[Component(id="operator", kind="kernel", local_root=str(source.root))],
        )
        remote = WatchdogConfig(
            monitor_id=config.monitor_id,
            owner_uid="owner",
            state_dir=str(self.root / "remote"),
            token_env="WATCH",
            expected_start_utc=self.now,
            alert=config.alert,
        )
        lost = [False]

        def sender(endpoint, payload):
            if endpoint == config.watchdog:
                receive(remote, payload, now=payload["scan_at"])
                if not lost[0]:
                    lost[0] = True
                    raise ValueError("Response lost after diagnostic acceptance")
            return {"accepted": True}

        for index in range(4):
            # Every call opens durable state afresh; no in-memory delivery cursor.
            scan(config, now=self.now + index * 60, reader=_read_component, sender=sender)
        store = MonitorStore(remote.state_dir, "owner")
        with store.connect() as db:
            received = {row[0] for row in db.execute("SELECT id FROM events")}
        self.assertEqual(received, produced)
        self.assertEqual(len(source.events(limit=200)["events"]), 200)
        self.assertEqual(MonitorStore(config.state_dir, "owner").get("mirroring")["pending"], 0)

    def test_actual_authority_hold_without_revision_suppresses_false_overdue_work(self):
        source = EventStore(self.root / "source", "owner")
        state = initial_state()
        with context():
            work = source.emit(
                "selection", "deferred", reason="none", root_id="root", request_revision="revision"
            )
            hold = source.emit("authority", "held", reason="policy-hold", root_id="root")
        observe(state, work, self.now)
        observe(state, hold, self.now)
        component = Component(id="operator", kind="kernel", local_root=str(source.root))
        findings = evaluate(
            component, state, {"available": True, "status": "observed", "gaps": []}, self.now + 1900
        )
        self.assertFalse(
            any(f["cause"] in {"overdue-work", "unresolved-expectation"} for f in findings)
        )

    def test_existing_notice_recording_failure_keeps_queue_and_exports_only_safe_cause(self):
        from cs import operator_recovery

        settings = SimpleNamespace(
            state_dir=self.root, engine_owner_uid="owner", email_address="owner@example.test"
        )
        pending = {"pending": [{"status": "failed"}]}
        failure = PermissionError("CANARY_SECRET")
        with (
            context() as trace,
            patch.object(
                operator_recovery.operator_notices,
                "render",
                return_value=("subject", "plain", "html"),
            ),
            patch("cs.operational_inbox.record_notice", side_effect=failure) as send,
        ):
            self.assertFalse(operator_recovery._deliver_pending(settings, pending))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(len(pending["pending"]), 1)
        events = store_for(settings).events()["events"]
        self.assertEqual(events[0]["stage"], "alert")
        self.assertEqual(events[0]["reason"], "permission")
        self.assertEqual(events[0]["trace_id"], trace["trace_id"])
        self.assertNotIn("CANARY_SECRET", json.dumps(events))

    def test_exact_request_handle_resolves_trace_without_logging_original(self):
        from cs import config
        from cs.logs_cli import collect
        from cs.observability import store_for
        import os

        with patch.dict(os.environ, {"HOME": str(self.root)}, clear=False):
            settings = config.Settings(_env_file=None, engine_owner_uid="owner", slug="neutral")
            with context() as trace:
                store_for(settings).emit("cli", "failed", root_id="<request@example.test>")
            result = collect(settings, "events", local=True, request_id="<request@example.test>")
        self.assertEqual(result["request_lookup"]["related_trace_ids"], [trace["trace_id"]])
        self.assertEqual(len(result["local"]["events"]), 1)
        self.assertNotIn("<request@example.test>", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
