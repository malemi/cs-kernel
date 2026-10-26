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
from cs.operational_inbox import _atomic, location, publish, record_notice


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

    def test_queue_migration_never_calls_smtp_and_retains_restricted_evidence(self):
        from cs import operator_recovery
        settings = SimpleNamespace(state_dir=self.root, engine_owner_uid="owner", slug="example")
        item = {"status": "stopped", "reason": "auth", "diagnostic": {"private": "CANARY_PRIVATE"}}
        pending = {"pending": [item]}
        with patch("smtplib.SMTP", side_effect=AssertionError("no mail")):
            self.assertTrue(operator_recovery._deliver_pending(settings, pending))
        self.assertEqual(pending["pending"], [])
        root, _, _ = location(settings)
        public = (root / "problems.json").read_text()
        self.assertNotIn("CANARY_PRIVATE", public)
        problem = json.loads(public)["problems"][0]
        self.assertEqual(json.loads(Path(problem["restricted_evidence_path"]).read_text()), item)
        record_notice(settings, item)
        self.assertEqual(json.loads((root / "problems.json").read_text())["problem_count"], 1)

    def test_failed_recording_retains_queue_and_has_no_mail_fallback(self):
        from cs import operator_recovery
        settings = SimpleNamespace(state_dir=self.root, engine_owner_uid="owner", slug="example")
        pending = {"pending": [{"status": "stopped", "reason": "logging"}]}
        with patch("cs.operational_inbox.record_notice", side_effect=PermissionError("CANARY")), \
             patch("smtplib.SMTP", side_effect=AssertionError("no mail")):
            self.assertFalse(operator_recovery._deliver_pending(settings, pending))
        self.assertEqual(len(pending["pending"]), 1)
        self.assertTrue(pending["_delivery_failed"])

    def test_notice_endpoint_helper_records_without_smtp(self):
        from cs.send_mail import send_operational_notice
        settings = SimpleNamespace(state_dir=self.root, engine_owner_uid="owner", slug="example")
        with patch("smtplib.SMTP", side_effect=AssertionError("no mail")):
            identity = send_operational_notice(settings, "a" * 32, "incident", 1)
        self.assertEqual(len(identity), 64)
        root, _, _ = location(settings)
        self.assertEqual(json.loads((root / "problems.json").read_text())["problem_count"], 1)

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


    def populated_notice_store(self, owner="owner", state_dir=None):
        settings = SimpleNamespace(state_dir=self.root if state_dir is None else state_dir, engine_owner_uid=owner, slug="example")
        root, owner, _ = location(settings)
        root.mkdir(parents=True, mode=0o700)
        store = MonitorStore(root, owner)
        detail = {"stage": "rpc", "reason": "unknown", "level": "ERROR",
                  "event_id": "a" * 32, "trace_id": "b" * 32, "span_id": "c" * 32,
                  "root_id": "d" * 64, "request_revision": "e" * 64,
                  "draft_id": "f" * 64, "provider_id": "1" * 64, "job_id": "2" * 64,
                  "at": 123.0, "first": 123.0, "last": 123.0, "last_progress": 123.0,
                  "expected_at": 123.0, "deadline": 123.0, "elapsed_ms": 123.0,
                  "deadline_seconds": 123, "held": False, "deferred": False,
                  "uncertain": True, "pending_count": 123, "error_code": 123,
                  "error_line": 123, "error_class": "TimeoutError", "method": "system.read",
                  "gaps": ["collector-lag", "retention", "clock-skew"]}
        with store.connect() as db:
            db.executemany(
                "INSERT INTO incidents(id,component,cause,first,last,active,revision,detail) "
                "VALUES (?, 'operator', 'operation-failure', ?, ?, 1, 1, ?)",
                [(f"{index:064x}", index, index, json.dumps(detail)) for index in range(205)])
        return settings, store

    def test_compact_backlog_publish_and_reloaded_notice_retry(self):
        from cs import operator_recovery
        settings, store = self.populated_notice_store()
        notice = {"status": "stopped", "reason": "auth",
                  "diagnostic": {"private": "CANARY_PRIVATE", "nested": ["café", {"ok": True}]}}
        pending = {"pending": [notice]}
        operator_recovery._write_state(settings, pending)
        original = _atomic
        def old_writer(path, value):
            if len(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n") > 262144:
                raise ValueError("Problem file size limit")
            original(path, value)
        with patch("smtplib.SMTP", side_effect=AssertionError("no mail")), \
             patch("cs.operational_inbox._atomic", side_effect=old_writer):
            self.assertFalse(operator_recovery._deliver_pending(settings, pending))
        self.assertTrue(pending["_delivery_failed"])
        self.assertEqual(pending["pending"], [notice])
        self.assertEqual(store.counts()["active"], 206)
        evidence = list((store.root / "notice-evidence").glob("*.json"))
        self.assertEqual(len(evidence), 1)
        self.assertEqual(json.loads(evidence[0].read_text()), notice)
        findings = store.root / "investigations" / ("0" * 64 + ".md")
        findings.write_text("Retained synthetic findings.\n")
        findings.chmod(0o600)
        reloaded = operator_recovery._read_state(settings)
        self.assertNotIn("_delivery_failed", reloaded)
        with patch("smtplib.SMTP", side_effect=AssertionError("no mail")):
            self.assertTrue(operator_recovery._deliver_pending(settings, reloaded))
            identity = record_notice(settings, notice)
            publish(store, clone_label="x" * 80)
        self.assertEqual(operator_recovery._read_state(settings)["pending"], [])
        self.assertEqual(store.counts()["active"], 206)
        self.assertEqual(list((store.root / "notice-evidence").glob("*.json")), evidence)
        self.assertEqual(evidence[0].stem, identity)
        raw = (store.root / "problems.json").read_bytes()
        value = json.loads(raw)
        selected_bytes = len(json.dumps(value["problems"]).encode())
        self.assertGreater(selected_bytes, 215000)
        self.assertLessEqual(selected_bytes, 220000)
        self.assertGreater(len(json.dumps(value, indent=2).encode()), 262144)
        self.assertLessEqual(len(raw), 262144)
        self.assertEqual(value["remaining_count"], 206 - len(value["problems"]))
        self.assertEqual(value["retrieval"], "cs monitor events --config <private-config> --offset 0; follow next_incident_offset")
        self.assertNotIn(b"CANARY_PRIVATE", raw)
        self.assertEqual(findings.read_text(), "Retained synthetic findings.\n")
        for path in [store.root / "problems.json", evidence[0]]:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_exact_atomic_wire_limits_and_value_preservation(self):
        path = self.root / "bounded.json"
        value = {"nested": ["café", {"ok": True, "empty": None}], "padding": ""}
        overhead = len(json.dumps(value, sort_keys=True, allow_nan=False).encode() + b"\n")
        value["padding"] = "x" * (262144 - overhead)
        _atomic(path, value)
        before = path.read_bytes()
        self.assertEqual(len(before), 262144)
        self.assertEqual(json.loads(before), value)
        value["padding"] += "x"
        with self.assertRaisesRegex(ValueError, "Problem file size limit"):
            _atomic(path, value)
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(ValueError):
            _atomic(path, {"number": float("nan")})
        self.assertEqual(path.read_bytes(), before)
        alias = self.root / "alias.json"
        alias.symlink_to(path)
        with self.assertRaises((PermissionError, ValueError)):
            _atomic(alias, {})
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list(self.root.glob(".problem-*")))

    def test_selection_exact_boundary_skips_and_complete_envelope(self):
        store = MonitorStore(self.config.state_dir, "o" * 128)
        row = {"id": "a" * 64, "component": "operator", "first": 1.0, "last": 1.0,
               "cause": "operation-failure", "revision": 1, "detail": {"padding": ""}}
        with patch.object(store, "incidents", return_value=[row]), \
             patch.object(store, "counts", return_value={"active": 3}):
            publish(store, clone_label="x" * 80, now=1.0)
            first = json.loads((store.root / "problems.json").read_text())["problems"][0]
            padding = 220000 - len(json.dumps([first]).encode())
            row["detail"]["padding"] = "x" * padding
            publish(store, clone_label="x" * 80, now=1.0)
            value = json.loads((store.root / "problems.json").read_text())
            self.assertEqual(len(json.dumps(value["problems"]).encode()), 220000)
            self.assertEqual(value["remaining_count"], 2)
            value["investigations_path"] = "\x01" * 4095
            value["generated_at"] = 1.7976931348623157e308
            value["problem_count"] = 2**63 - 1
            value["remaining_count"] = 2**63 - 1
            self.assertLessEqual(len(json.dumps(value, sort_keys=True).encode()) + 1, 262144)
            oversized = {**row, "detail": {"padding": "x" * (padding + 1)}}
            small = {**row, "id": "b" * 64, "detail": {}}
            with patch.object(store, "incidents", return_value=[oversized, small]):
                publish(store, clone_label="x" * 80, now=1.0)
            value = json.loads((store.root / "problems.json").read_text())
            self.assertEqual([item["id"] for item in value["problems"]], [small["id"]])
            self.assertEqual(value["remaining_count"], 2)

    @patch.object(Path, "home")
    def test_real_fallback_large_owner_accounts_for_complete_envelope(self, home):
        from cs.config import Settings
        home.return_value = self.root
        settings = Settings(engine_owner_uid="o" * 50000, slug="example")
        self.assertTrue(location(settings)[0].is_relative_to(self.root))
        _, store = self.populated_notice_store(owner=settings.engine_owner_uid, state_dir=settings.state_dir)
        identity = record_notice(settings, {"status": "stopped", "reason": "auth"})
        raw = (store.root / "problems.json").read_bytes()
        value = json.loads(raw)
        self.assertEqual(value["owner_uid"], settings.engine_owner_uid)
        self.assertLessEqual(len(raw), 262144)
        self.assertLessEqual(len(json.dumps(value["problems"]).encode()), 220000)
        self.assertLess(len(value["problems"]), 130)
        self.assertEqual(value["remaining_count"], 206 - len(value["problems"]))
        self.assertEqual(store.counts()["active"], 206)
        self.assertTrue((store.root / "notice-evidence" / (identity + ".json")).is_file())

    @patch.object(Path, "home")
    def test_real_fallback_no_room_for_base_retains_prior_projection_and_queue(self, home):
        from cs import operator_recovery
        from cs.config import Settings
        home.return_value = self.root
        settings = Settings(engine_owner_uid="o" * 270000, slug="example")
        self.assertTrue(location(settings)[0].is_relative_to(self.root))
        root, owner, _ = location(settings)
        store = MonitorStore(root, owner)
        target = root / "problems.json"
        _atomic(target, {"prior": "preserved"})
        before = target.read_bytes()
        state = {"pending": [{"status": "stopped", "reason": "auth"}]}
        operator_recovery._write_state(settings, state)
        with patch("smtplib.SMTP", side_effect=AssertionError("no mail")):
            self.assertFalse(operator_recovery._deliver_pending(settings, state))
        self.assertTrue(state["_delivery_failed"])
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(operator_recovery._read_state(settings)["pending"], state["pending"])
        self.assertEqual(store.counts()["active"], 1)
        self.assertEqual(len(list((root / "notice-evidence").glob("*.json"))), 1)

    def test_exact_canonical_notice_admission(self):
        settings = SimpleNamespace(state_dir=self.root, engine_owner_uid="owner", slug="example")
        notice = {"status": "stopped", "reason": "auth", "private": ""}
        overhead = len(json.dumps(notice, sort_keys=True, separators=(",", ":")).encode())
        notice["private"] = "x" * (65536 - overhead)
        identity = record_notice(settings, notice)
        root, _, _ = location(settings)
        target = root / "notice-evidence" / (identity + ".json")
        self.assertEqual(json.loads(target.read_text()), notice)
        notice["private"] += "x"
        with self.assertRaisesRegex(ValueError, "Technical evidence limit"):
            record_notice(settings, notice)
        self.assertEqual(len(list((root / "notice-evidence").iterdir())), 1)
        with self.assertRaises(ValueError):
            record_notice(settings, {"value": float("nan")})


if __name__ == "__main__":
    unittest.main()
