"""Real filesystem collection and technical-notice migration, without mail or models."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs.monitor import _read_component, scan
from cs.monitor_config import Component, MonitorConfig
from cs.monitor_store import MonitorStore
from cs.observability import EventStore, context
from cs.operational_inbox import location, record_notice


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = EventStore(self.root / "source", "owner")
        self.config = MonitorConfig(
            mode="filesystem", clone_label="example-cs", scan_seconds=600,
            monitor_id="a" * 32, owner_uid="owner", state_dir=str(self.root / "monitor"),
            expected_start_utc=int(time.time()),
            components=[Component(id="operator", kind="kernel", local_root=str(self.source.root))],
        )

    def read(self):
        return json.loads((Path(self.config.state_dir) / "problems.json").read_text())

    def test_errors_beyond_first_page_and_findings_survive_restart(self):
        for _ in range(205):
            self.source.emit("cli", "start")
            self.source.emit("cli", "result", reason="none")
        event = self.source.emit("rpc", "result", reason="unknown", level="ERROR", method="system.read")
        with patch("smtplib.SMTP", side_effect=AssertionError("no mail")):
            first = scan(self.config, reader=_read_component, sender=lambda *args: self.fail("no network"))
        self.assertEqual(first["analyst"], "manual-only")
        self.assertGreater(first["components"]["operator"]["pages_read"], 1)
        problem = next(p for p in self.read()["problems"] if p["symptom"] == "operation-failure")
        self.assertEqual(problem["severity"], "ERROR")
        self.assertEqual(problem["evidence"]["event_id"], event["event_id"])
        self.assertEqual(problem["clone"], "example-cs")
        findings = Path(problem["investigation_path"])
        findings.write_text("Observed evidence; cause remains unknown.\n")
        findings.chmod(0o600)
        scan(MonitorConfig.model_validate(self.config.model_dump()), reader=_read_component)
        again = next(p for p in self.read()["problems"] if p["id"] == problem["id"])
        self.assertEqual(again["revision"], problem["revision"])
        self.assertEqual(again["investigation_status"], "findings-retained")
        self.assertEqual(findings.read_text(), "Observed evidence; cause remains unknown.\n")
        self.assertEqual((Path(self.config.state_dir) / "problems.json").stat().st_mode & 0o777, 0o600)

    def test_healthy_filesystem_collection_needs_no_transports(self):
        self.source.emit("cli", "result", reason="none")
        result = scan(self.config, reader=_read_component, sender=lambda *args: self.fail("no network"))
        self.assertEqual(result["status"], "observed")
        self.assertTrue(result["alert_delivery_ok"])
        self.assertEqual(self.read()["problem_count"], 0)

    def test_lag_is_persistent_and_no_cursor_progress_is_not_silence(self):
        event = self.source.emit("cli", "result", reason="none")
        pages = []
        def endless(component, owner, cursor):
            pages.append(cursor)
            return {"events": [event], "next_cursor": str(len(pages)),
                    "coverage": {"available": True, "status": "observed", "gaps": [],
                                 "continuation_required": True}}
        result = scan(self.config, reader=endless)
        self.assertEqual(len(pages), 20)
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(any("collector-lag" in p["evidence"].get("gaps", []) for p in self.read()["problems"]))
        self.assertEqual(MonitorStore(self.config.state_dir, "owner").get("cursor:operator"), "20")

    def test_scan_deadline_preserves_unread_cursor_and_resumes(self):
        events = [self.source.emit("rpc", "result", reason="unknown", level="ERROR") for _ in range(10)]
        ticks = [0]
        def monotonic():
            ticks[0] += 1
            return ticks[0]
        def delayed(component, owner, cursor):
            ticks[0] = 118
            return {"events": events, "next_cursor": "complete",
                    "coverage": {"available": True, "status": "observed", "gaps": []}}
        with patch("cs.monitor.time.monotonic", side_effect=monotonic):
            first = scan(self.config, reader=delayed)
        store = MonitorStore(self.config.state_dir, "owner")
        self.assertIsNone(store.get("cursor:operator"))
        self.assertEqual(first["status"], "degraded")
        with store.connect() as db:
            self.assertLess(db.execute("SELECT count(*) FROM events").fetchone()[0], len(events))
        scan(self.config, reader=lambda *args: {"events": events, "next_cursor": "complete",
             "coverage": {"available": True, "status": "observed", "gaps": []}})
        self.assertEqual(store.get("cursor:operator"), "complete")
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], len(events))

    def test_repeated_slow_backlogs_make_progress_for_every_component(self):
        import threading

        components = [Component(id="source" + str(i), kind="kernel",
                                local_root=str(self.root / ("source" + str(i)))) for i in range(16)]
        config = self.config.model_copy(update={"components": components})
        events = {}
        for component in components:
            source = EventStore(component.local_root, "owner")
            events[component.id] = [source.emit("rpc", "result", reason="unknown", level="ERROR",
                                                method="system.read") for _ in range(20)]
        clock = [0.0]
        lock = threading.Lock()
        def monotonic():
            with lock:
                return clock[0]
        def slow(component, owner, cursor):
            with lock:
                clock[0] += 0.8
            index = int(cursor or "0")
            return {"events": events[component.id][index:index + 1], "next_cursor": str(index + 1),
                    "coverage": {"available": True, "status": "observed", "gaps": [],
                                 "continuation_required": index + 1 < 20}}
        store = MonitorStore(config.state_dir, "owner")
        with patch("cs.monitor.time.monotonic", side_effect=monotonic):
            for index in range(16):
                started = clock[0]
                scan(config, reader=slow)
                self.assertLess(clock[0] - started, 120)
                if index == 1:
                    with store.connect() as db:
                        self.assertGreater(db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
                    self.assertTrue(any(p["symptom"] == "operation-failure" for p in self.read()["problems"]))
        self.assertTrue(all(store.get("cursor:" + component.id) is not None for component in components))
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT count(DISTINCT component) FROM events").fetchone()[0], 16)

    def test_completed_page_cursor_survives_processing_deadline_and_reaches_tail_error(self):
        template = self.source.emit("rpc", "result", reason="none", method="system.read")
        events = [{**template, "event_id": f"{index:032x}", "sequence": index + 1}
                  for index in range(3999)]
        tail = {**template, "event_id": f"{3999:032x}", "sequence": 4000,
                "reason": "unknown", "level": "ERROR"}
        events.append(tail)
        clock = [0.0]
        remember = MonitorStore.remember
        def slow_remember(store, component, event, now):
            clock[0] += 0.05
            return remember(store, component, event, now)
        def read(component, owner, cursor):
            start = int(cursor or "0")
            end = min(len(events), start + 200)
            return {"events": events[start:end], "next_cursor": str(end),
                    "coverage": {"available": True, "status": "observed", "gaps": [],
                                 "continuation_required": end < len(events)}}
        store = MonitorStore(self.config.state_dir, "owner")
        with patch("cs.monitor.time.monotonic", side_effect=lambda: clock[0]), \
             patch.object(MonitorStore, "remember", slow_remember):
            scan(self.config, reader=read)
            committed = int(store.get("cursor:operator"))
            self.assertGreater(committed, 0)
            self.assertLess(committed, len(events))
            self.assertEqual(committed % 200, 0)
            scan(self.config, reader=read)
        self.assertEqual(store.get("cursor:operator"), str(len(events)))
        self.assertTrue(any(p["evidence"].get("event_id") == tail["event_id"] for p in self.read()["problems"]))
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], len(events))

    def test_high_level_policy_hold_does_not_become_business_failure(self):
        self.source.emit("authority", "held", reason="policy-hold", level="ERROR")
        scan(self.config, reader=_read_component)
        self.assertFalse(any(p["symptom"] == "operation-failure" for p in self.read()["problems"]))

    def test_more_than_two_hundred_incidents_have_discoverable_pages(self):
        import hashlib
        from cs.monitor import _sync
        from cs.monitor_store import snapshot
        from cs.operational_inbox import publish

        store = MonitorStore(self.config.state_dir, "owner")
        expected = {hashlib.sha256(str(i).encode()).hexdigest() for i in range(205)}
        findings = [{"id": identity, "cause": "operation-failure",
                     "detail": {"stage": "rpc", "reason": "unknown"}} for identity in expected]
        _sync(store, "operator", findings, time.time(), allow_recovery=False)
        publish(store, clone_label="example-cs")
        self.assertGreater(self.read()["remaining_count"], 0)
        observed = set()
        offset = self.read()["incident_index_offset"]
        while offset is not None:
            page = snapshot(store.root, "owner", incident_offset=offset)
            self.assertLessEqual(len(json.dumps(page).encode()), 240000)
            observed.update(row["id"] for row in page["incidents"])
            offset = page["next_incident_offset"]
        self.assertEqual(observed, expected)




    def test_unwritable_or_symlink_projection_is_failure(self):
        self.source.emit("cli", "failed", reason="auth")
        root = Path(self.config.state_dir)
        MonitorStore(root, "owner")
        (root / "problems.json").symlink_to(self.root / "foreign")
        result = scan(self.config, reader=_read_component)
        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["alert_delivery_ok"])
        self.assertIsNotNone(result["inbox_write_failure"])
        self.assertFalse((self.root / "foreign").exists())

    def test_actual_cli_once_and_status_expose_readable_file(self):
        self.source.emit("rpc", "failed", reason="auth", method="system.read")
        config_path = self.root / "config.json"
        config_path.write_text(self.config.model_dump_json())
        config_path.chmod(0o600)
        env = dict(os.environ, CS_OPERATOR_HEADLESS="", CS_HEADLESS_SEND="")
        command = [sys.executable, "-m", "cs", "monitor"]
        done = subprocess.run(command + ["once", "--config", str(config_path)], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertEqual(json.loads(done.stdout)["problems_path"], str(Path(self.config.state_dir) / "problems.json"))
        status = subprocess.run(command + ["status", "--config", str(config_path)], capture_output=True, text=True, env=env)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["mode"], "filesystem")
        self.assertTrue(self.read()["problems"])


if __name__ == "__main__":
    unittest.main()
