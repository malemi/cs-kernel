"""Logging recovery retains history without clearing independent monitoring faults."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cs.monitor import _read_component, _sync, scan
from cs.monitor_config import Component, MonitorConfig
from cs.monitor_evaluate import evaluate, initial_state
from cs.monitor_store import MonitorStore
from cs.observability import EventStore


def logging_health(state="recovered"):
    value = {
        "schema_version": 1,
        "current_state": state,
        "history_retained": True,
        "observed_failures": 0,
        "lost_events_unknown": True,
        "first_failure_at": None,
        "last_failure": None,
        "recovery": {
            "event_id": "a" * 32,
            "timestamp": "2026-10-24T10:00:01+00:00",
            "pid": 42,
            "process_start": "123",
        } if state == "recovered" else None,
    }
    if state == "failed":
        value.update(observed_failures=1, first_failure_at="2026-10-24T10:00:00+00:00", last_failure={
            "timestamp": "2026-10-24T10:00:00+00:00", "pid": 42, "process_start": "123",
            "error_class": "OSError", "error_code": 28, "error_file": "observability.py", "error_line": 1,
        })
    return value


class LoggingCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.component = Component(id="operator", kind="kernel", local_root=str(self.root / "source"))
        self.state = initial_state()

    def finding(self, logging=None, extra=(), **updates):
        health = {"available": True, "status": "degraded", "gaps": [{"reason": "logging"}, *extra]}
        if logging is not None:
            health["logging"] = logging
        health.update(updates)
        return next(f for f in evaluate(self.component, self.state, health, time.time()) if f["cause"] == "coverage")

    def test_only_explicit_valid_recovery_downgrades_retained_loss(self):
        for state in (None, "failed", "unknown", "recovered"):
            with self.subTest(state=state):
                finding = self.finding(None if state is None else logging_health(state))
                self.assertEqual(finding["detail"]["level"], "WARNING" if state == "recovered" else "ERROR")
                self.assertEqual(finding["detail"]["gaps"], ["logging"])
                if state is not None:
                    self.assertTrue(finding["detail"]["logging"]["lost_events_unknown"])
                    self.assertEqual(finding["detail"]["logging"]["observed_failures"], 1 if state == "failed" else 0)
        invalid = logging_health()
        invalid["recovery"] = None
        self.assertEqual(self.finding(invalid)["detail"]["level"], "ERROR")
        self.assertNotIn("logging", self.finding(invalid)["detail"])

    def test_unrelated_coverage_faults_remain_error(self):
        for reason in ("unreadable", "malformed-event", "cursor-evicted", "response-limit"):
            with self.subTest(reason=reason):
                finding = self.finding(logging_health(), ({"reason": reason},))
                self.assertEqual(finding["detail"]["level"], "ERROR")
                self.assertIn(reason, finding["detail"]["gaps"])
        self.assertEqual(self.finding(logging_health(), available=False)["detail"]["level"], "ERROR")
        self.assertEqual(self.finding(logging_health(), status="unavailable")["detail"]["level"], "ERROR")
        self.state["gaps"] = ["collector-lag"]
        self.assertEqual(self.finding(logging_health())["detail"]["level"], "ERROR")
        self.state["gaps"] = []
        self.assertEqual(self.finding(logging_health(), ({"reason": "retention"},))["detail"]["level"], "WARNING")

    def test_incident_id_revision_investigation_and_renewed_failure(self):
        store = MonitorStore(self.root / "monitor", "owner")
        before = self.finding(logging_health("unknown"))
        _sync(store, self.component.id, [before], 1, allow_recovery=True)
        investigation = store.root / "investigations"
        investigation.mkdir(mode=0o700)
        path = investigation / (before["id"] + ".md")
        path.write_text("Retained original investigation\n")
        path.chmod(0o600)
        recovered = self.finding(logging_health())
        self.assertEqual(before["id"], recovered["id"])
        _sync(store, self.component.id, [recovered], 2, allow_recovery=True)
        row = store.incidents()[0]
        self.assertEqual(row["revision"], 2)
        for now in (3, 4):
            store = MonitorStore(self.root / "monitor", "owner")
            _sync(store, self.component.id, [copy.deepcopy(recovered)], now, allow_recovery=True)
        self.assertEqual(store.incidents()[0]["revision"], 2)
        self.assertEqual(path.read_text(), "Retained original investigation\n")
        _sync(store, self.component.id, [self.finding(logging_health("failed"))], 5, allow_recovery=True)
        self.assertEqual(store.incidents()[0]["revision"], 3)
        self.assertEqual(store.incidents()[0]["detail"]["level"], "ERROR")

    def test_actual_append_collection_projection_and_restart(self):
        source = EventStore(self.component.local_root, "owner")
        source.emit("cli", "result", reason="none")
        marker = source.root / ".logging-failed"
        marker.write_text("Legacy loss with unknown count\n")
        marker.chmod(0o600)
        config = MonitorConfig(monitor_id="a" * 32, owner_uid="owner", state_dir=str(self.root / "monitor"),
                               expected_start_utc=int(time.time()), components=[self.component], mode="filesystem")
        config_path = self.root / "monitor-config.json"
        config_path.write_text(config.model_dump_json())
        config_path.chmod(0o600)

        def collect_cli():
            process = subprocess.run([sys.executable, "-m", "cs", "monitor", "once", "--config", str(config_path)],
                capture_output=True, text=True, timeout=15,
                env={k: v for k, v in os.environ.items() if k not in {"CS_OPERATOR_HEADLESS", "CS_HEADLESS_SEND"}})
            self.assertEqual(process.returncode, 1, process.stderr)
            self.assertTrue(json.loads(process.stdout)["alert_delivery_ok"])

        collect_cli()
        problem_path = Path(config.state_dir) / "problems.json"
        first = json.loads(problem_path.read_text())["problems"][0]
        self.assertEqual(first["severity"], "ERROR")
        investigation = Path(first["investigation_path"])
        investigation.write_text("Original evidence remains unknown\n")
        investigation.chmod(0o600)
        event = source.emit("cli", "result", reason="none")
        for _ in range(2):
            collect_cli()
            problem = json.loads(problem_path.read_text())["problems"][0]
            self.assertEqual(problem["id"], first["id"])
            self.assertEqual(problem["severity"], "WARNING")
            self.assertEqual(problem["investigation_status"], "findings-retained")
            self.assertEqual(problem["evidence"]["logging"]["recovery"]["event_id"], event["event_id"])
            self.assertTrue(problem["evidence"]["logging"]["lost_events_unknown"])
        self.assertEqual(problem["revision"], first["revision"] + 1)
        self.assertEqual(investigation.read_text(), "Original evidence remains unknown\n")
        marker.write_text("Renewed legacy failure\n")
        collect_cli()
        renewed = json.loads(problem_path.read_text())["problems"][0]
        self.assertEqual(renewed["id"], first["id"])
        self.assertEqual(renewed["severity"], "ERROR")

    def test_prune_failure_cannot_hide_behind_recovered_logging(self):
        source = EventStore(self.component.local_root, "owner")
        source.emit("cli", "result", reason="none")
        with patch.object(EventStore, "prune", return_value={"complete": False}), patch.object(
            EventStore, "events", return_value={"events": [], "next_cursor": None,
                "coverage": {"available": True, "status": "degraded", "gaps": [{"reason": "logging"}], "logging": logging_health()}}
        ):
            page = _read_component(self.component, "owner", None)
        finding = evaluate(self.component, self.state, page["coverage"], time.time())[0]
        self.assertEqual(finding["detail"]["level"], "ERROR")
        self.assertIn("unreadable", finding["detail"]["gaps"])
