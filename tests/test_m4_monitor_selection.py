"""Real observer state, independent watchdog and negative business controls."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs.monitor import _read_component, scan
from cs.monitor_config import Component, Endpoint, MonitorConfig, Schedule, WatchdogConfig
from cs.monitor_evaluate import evaluate, initial_state, last_due, observe
from cs.monitor_store import MonitorStore, snapshot
from cs.observability import EventStore, context, owner_root


def accepted(endpoint, payload):
    return {"accepted": True}


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = int(time.time())
        self.events = EventStore(self.root / "events", "owner")
        self.endpoint = Endpoint(url="https://alerts.invalid/events", token_env="ALERT_TEST_TOKEN")
        self.config = MonitorConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "monitor"),
            expected_start_utc=self.now,
            alert=self.endpoint,
            watchdog=Endpoint(url="https://watch.invalid/heartbeat", token_env="WATCH_TEST_TOKEN"),
            components=[
                Component(id="operator", kind="kernel", local_root=str(self.root / "events"))
            ],
        )

    def tearDown(self):
        self.temp.cleanup()









    def test_real_cli_headless_ack_denied_and_query_absence_no_files(self):
        path = self.root / "config.json"
        path.write_text(self.config.model_dump_json())
        path.chmod(0o600)
        env = {**os.environ, "CS_OPERATOR_HEADLESS": "1"}
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "cs",
                "monitor",
                "ack",
                "--config",
                str(path),
                "--incident",
                "a" * 64,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(process.returncode, 2)
        self.assertFalse(Path(self.config.state_dir).exists())
        process = subprocess.run(
            [sys.executable, "-m", "cs", "monitor", "status", "--config", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "absent")
        self.assertFalse(Path(self.config.state_dir).exists())




    def test_real_legacy_notice_failure_is_observed_without_copying_account_data(self):
        state = self.root / "clone"
        (state / "observability").mkdir(parents=True, mode=0o700)
        (state / "operator-route-notices.json").write_text(
            json.dumps({"pending": [{"diagnostic": {"credential": "CANARY_SECRET"}}]})
        )
        (state / "operator-route-notices.json").chmod(0o600)
        self.config.components = [
            Component(
                id="operator",
                kind="kernel",
                local_root=str(owner_root(state, "owner")),
                legacy_state_dir=str(state),
            )
        ]
        EventStore(owner_root(state, "owner"), "owner").emit("cli", "result", reason="none")
        result = scan(self.config, now=self.now, reader=_read_component, sender=accepted)
        rows = MonitorStore(self.config.state_dir, "owner").incidents()
        self.assertIn("alert-delivery-unconfirmed", {row["cause"] for row in rows})
        self.assertNotIn("CANARY_SECRET", json.dumps(result) + json.dumps(rows))


    def test_indexed_trace_lookup_survives_more_than_one_query_page(self):
        store = MonitorStore(self.config.state_dir, "owner")
        with context() as first:
            first_event = self.events.emit("rpc", "failed", reason="permission")
        store.remember("operator", first_event, self.now)
        for index in range(220):
            event = self.events.emit("cli", "result", reason="none")
            store.remember("operator", event, self.now + index + 1)
        result = snapshot(self.config.state_dir, "owner", trace_id=first["trace_id"])
        self.assertEqual(
            [event["event_id"] for event in result["events"]], [first_event["event_id"]]
        )



if __name__ == "__main__":
    unittest.main()
