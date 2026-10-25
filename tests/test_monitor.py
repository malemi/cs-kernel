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
from cs.monitor_analyst import reserve
from cs.monitor_config import Component, Endpoint, MonitorConfig, Schedule, WatchdogConfig
from cs.monitor_evaluate import evaluate, initial_state, last_due, observe
from cs.monitor_store import MonitorStore, snapshot
from cs.monitor_watchdog import check, receive
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

    def test_missing_launch_without_any_log_and_pause_no_work_controls(self):
        component = Component(
            id="operator",
            kind="kernel",
            local_root=str(self.root / "absent"),
            schedule=Schedule(every_seconds=3600, anchor_utc=self.now - 3600),
        )
        state = initial_state()
        health = {"available": True, "status": "observed", "gaps": []}
        causes = {f["cause"] for f in evaluate(component, state, health, self.now)}
        self.assertEqual(causes, {"missing-launch"})
        self.assertEqual(evaluate(component, state, health, self.now, paused=True), [])
        component.schedule.disabled = True
        self.assertEqual(evaluate(component, state, health, self.now), [])

    def test_scan_phase_fits_five_minute_detection_bound(self):
        component=Component(id="operator",kind="kernel",local_root=str(self.root/"absent"),
                            schedule=Schedule(every_seconds=3600,anchor_utc=self.now))
        state=initial_state()
        health={"available":True,"status":"observed","gaps":[]}
        causes=lambda at:{f['cause'] for f in evaluate(component,state,health,at)}
        self.assertNotIn('missing-launch',causes(self.now+229))
        self.assertIn('missing-launch',causes(self.now+230))
        # A scan just before eligibility is followed within 60 seconds, with
        # ten seconds still available for the bounded read and processing.
        self.assertIn('missing-launch',causes(self.now+289))
        component.schedule=None
        state['spans']['test']={'at':self.now,'deadline':600,'stage':'rpc'}
        self.assertNotIn('stalled-stage',causes(self.now+830))
        self.assertIn('stalled-stage',causes(self.now+831))
        self.assertIn('stalled-stage',causes(self.now+890))

    def test_real_event_failure_dedup_ack_and_no_resend(self):
        calls = []

        def sender(endpoint, payload):
            calls.append((endpoint.url, payload))
            return {"accepted": True}

        with context():
            self.events.emit(
                "provider",
                "unknown-effect",
                reason="timeout",
                root_id="root",
                request_revision="revision",
            )
        first = scan(self.config, now=self.now, reader=_read_component, sender=sender)
        self.assertEqual(first["open_incidents"], 1)
        self.assertTrue(first["alert_delivery_ok"])
        self.assertEqual(len([c for c in calls if "alerts" in c[0]]), 1)
        again = scan(self.config, now=self.now + 60, reader=_read_component, sender=sender)
        self.assertEqual(again["open_incidents"], 1)
        self.assertEqual(len([c for c in calls if "alerts" in c[0]]), 1)
        store = MonitorStore(self.config.state_dir, "owner")
        incident = store.incidents()[0]
        self.assertTrue(store.ack(incident["id"], self.now + 60, seconds=120))
        scan(self.config, now=self.now + 3700, reader=_read_component, sender=sender)
        self.assertGreaterEqual(len([c for c in calls if "alerts" in c[0]]), 2)
        self.assertEqual(len(self.events.events()["events"]), 1)  # no business replay

    def test_held_and_overdue_revision_then_exact_verification(self):
        state = initial_state()
        with context():
            held = self.events.emit(
                "selection", "held", reason="policy-hold", root_id="held", request_revision="r"
            )
            owed = self.events.emit(
                "selection", "deferred", reason="none", root_id="owed", request_revision="r"
            )
        observe(state, held, self.now)
        observe(state, owed, self.now)
        component = self.config.components[0]
        health = {"available": True, "status": "observed", "gaps": []}
        findings = evaluate(component, state, health, self.now + 1900)
        overdue = [f for f in findings if f["cause"] == "unresolved-expectation"]
        self.assertEqual(len(overdue), 1)
        with context():
            accepted_event = self.events.emit(
                "provider",
                "accepted",
                reason="none",
                effect_certainty="accepted",
                root_id="owed",
                request_revision="r",
            )
            verified = self.events.emit(
                "verification",
                "verified",
                reason="none",
                effect_certainty="verified",
                root_id="owed",
                request_revision="r",
            )
        observe(state, accepted_event, self.now + 1900)
        self.assertEqual(len(state["work"]), 2)
        observe(state, verified, self.now + 1900)
        self.assertEqual(len(state["work"]), 1)

    def test_failed_logging_and_dead_monitor_alert_independently(self):
        notices = []
        watchdog = WatchdogConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "watch"),
            token_env="WATCH_TEST_TOKEN",
            expected_start_utc=self.now,
            alert=self.endpoint,
        )
        before = check(
            watchdog,
            now=self.now + 301,
            sender=lambda e, p: notices.append(p) or {"accepted": True},
        )
        self.assertIn("monitor-absent", before["causes"])
        heartbeat = {
            "schema_version": 1,
            "monitor_id": "a" * 32,
            "owner_uid": "owner",
            "sequence": 1,
            "scan_at": self.now + 302,
            "status": "degraded",
            "alert_delivery_ok": False,
            "open_incidents": 2,
            "events": [],
        }
        receive(watchdog, heartbeat, now=self.now + 302)
        result = check(
            watchdog,
            now=self.now + 303,
            sender=lambda e, p: notices.append(p) or {"accepted": True},
        )
        self.assertIn("primary-alert-unconfirmed", result["causes"])
        self.assertGreaterEqual(len(notices), 2)
        with self.assertRaises(ValueError):
            receive(watchdog, heartbeat, now=self.now + 304)
        self.assertEqual(
            MonitorStore(watchdog.state_dir, "owner").get("received")["received_at"], self.now + 302
        )

    def test_wrong_owner_and_private_canary_never_mirrored(self):
        watchdog = WatchdogConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "watch"),
            token_env="WATCH_TEST_TOKEN",
            expected_start_utc=self.now,
            alert=self.endpoint,
        )
        event = self.events.emit("rpc", "failed", body="CANARY_SECRET")
        self.assertNotIn("CANARY_SECRET", json.dumps(event))
        payload = {
            "schema_version": 1,
            "monitor_id": "a" * 32,
            "owner_uid": "foreign",
            "sequence": 1,
            "scan_at": self.now,
            "status": "observed",
            "alert_delivery_ok": True,
            "open_incidents": 0,
            "events": [event],
        }
        with self.assertRaises(ValueError):
            receive(watchdog, payload, now=self.now)
        payload["owner_uid"] = "owner"
        payload["events"][0]["body"] = "CANARY_SECRET"
        with self.assertRaises(ValueError):
            receive(watchdog, payload, now=self.now)

    def test_persistent_analyst_caps_uncertainty_and_readonly_snapshot(self):
        store = MonitorStore(self.config.state_dir, "owner")
        for number in range(20):
            self.assertTrue(
                reserve(
                    store, hashlib.sha256(str(number).encode()).hexdigest(), 1, 0.05, now=self.now
                )
            )
        self.assertFalse(reserve(store, "f" * 64, 1, 0.05, now=self.now))
        self.assertFalse(
            reserve(store, hashlib.sha256(b"0").hexdigest(), 1, 0.05, now=self.now + 86400)
        )
        before = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(self.config.state_dir).iterdir()
        }
        snapshot(self.config.state_dir, "owner")
        after = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(self.config.state_dir).iterdir()
        }
        self.assertEqual(before, after)
        with self.assertRaises(ValueError):
            snapshot(self.config.state_dir, "foreign")

    def test_cron_weekend_timezone_and_dom_dow_semantics(self):
        from datetime import datetime, timezone

        now = int(datetime(2026, 10, 26, 8, 6, tzinfo=timezone.utc).timestamp())
        schedule = Schedule(
            every_seconds=7200, anchor_utc=now - 7 * 86400, cron="0 8-18/2 * * 1-5", timezone="UTC"
        )
        self.assertEqual(last_due(schedule, now), now - 360)
        with self.assertRaises(ValueError):
            Schedule(every_seconds=60, anchor_utc=now, cron="0 99 * * *")

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

    def test_actual_watchdog_subprocess_auth_replay_and_offhost_copy(self):
        config = WatchdogConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "watch"),
            token_env="WATCH_TEST_TOKEN",
            expected_start_utc=self.now + 10000,
            alert=self.endpoint,
            port=0,
        )
        path = self.root / "watch.json"
        path.write_text(config.model_dump_json())
        path.chmod(0o600)
        token = "diagnostic-test-token-" + "x" * 32
        process = subprocess.Popen(
            [sys.executable, "-m", "cs.monitor_cli", "watchdog", "--config", str(path)],
            env={**os.environ, "WATCH_TEST_TOKEN": token},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            import select

            self.assertTrue(select.select([process.stdout], [], [], 10)[0])
            address = "http://127.0.0.1:" + str(json.loads(process.stdout.readline())["port"])
            with self.assertRaises(HTTPError) as error:
                urlopen(address + "/status", timeout=3)
            self.assertEqual(error.exception.code, 401)
            event = self.events.emit("rpc", "failed", reason="permission")
            payload = {
                "schema_version": 1,
                "monitor_id": "a" * 32,
                "owner_uid": "owner",
                "sequence": 1,
                "scan_at": self.now,
                "status": "observed",
                "alert_delivery_ok": True,
                "open_incidents": 0,
                "events": [event],
            }
            request = Request(
                address + "/heartbeat",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            )
            self.assertTrue(json.load(urlopen(request, timeout=3))["accepted"])
            with self.assertRaises(HTTPError):
                urlopen(request, timeout=3)
            query = Request(address + "/events", headers={"Authorization": "Bearer " + token})
            received = json.load(urlopen(query, timeout=3))
            self.assertEqual(received["events"][0]["event_id"], event["event_id"])
        finally:
            process.terminate()
            process.communicate(timeout=5)

    def test_engine_idle_service_uses_heartbeat_not_operation_deadline(self):
        engine = EventStore(self.root / "engine", "owner", "engine")
        component = Component(id="engine", kind="engine", local_root=str(self.root / "engine"))
        state = initial_state()
        with context():
            start = engine.emit("launch", "start", reason="none", method="engine.ws")
            connection = engine.emit("context", "start", reason="none", method="engine.connection")
            beat = engine.emit("launch", "running", reason="none", method="engine.heartbeat")
        observe(state, start, self.now)
        observe(state, connection, self.now)
        observe(state, beat, self.now)
        self.assertEqual(state["spans"], {})
        health = {"available": True, "status": "observed", "gaps": []}
        self.assertEqual(evaluate(component, state, health, self.now + 120), [])
        self.assertIn(
            "engine-liveness-unconfirmed",
            {f["cause"] for f in evaluate(component, state, health, self.now + 301)},
        )

    def test_quiet_scheduled_weekend_and_paused_absence_do_not_page(self):
        component = self.config.components[0]
        state = initial_state()
        state["last_event"] = self.now - 86400
        health = {"available": True, "status": "observed", "gaps": []}
        self.assertEqual(evaluate(component, state, health, self.now), [])
        self.assertEqual(
            evaluate(
                component,
                state,
                {"available": False, "status": "absent", "gaps": []},
                self.now,
                paused=True,
            ),
            [],
        )
        # Actual inaccessible evidence still warns during a pause.
        self.assertEqual(
            evaluate(
                component,
                state,
                {"available": False, "status": "unavailable", "gaps": [{"reason": "unreadable"}]},
                self.now,
                paused=True,
            )[0]["cause"],
            "coverage",
        )

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

    def test_primary_alert_failure_reaches_watchdog_with_no_model_or_mail_call(self):
        self.events.emit("rpc", "failed", reason="quota")
        heartbeats = []

        def sender(endpoint, payload):
            if endpoint == self.config.alert:
                raise ValueError("unreachable")
            heartbeats.append(payload)
            return {"accepted": True}

        result = scan(self.config, now=self.now, reader=_read_component, sender=sender)
        self.assertFalse(result["alert_delivery_ok"])
        self.assertFalse(heartbeats[0]["alert_delivery_ok"])
        self.assertEqual(result["analyst"], "disabled-no-priced-route")
        # A false acknowledgement cannot become a delivered alert.
        other = self.config.model_copy(update={"state_dir": str(self.root / "other")})
        result = scan(
            other, now=self.now, reader=_read_component, sender=lambda e, p: {"accepted": False}
        )
        self.assertFalse(result["alert_delivery_ok"])

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

    def test_real_transport_absolute_deadline_against_trickling_response(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from cs.monitor_transport import post

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.15)
                except OSError:
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        os.environ["TRICKLE_TEST_TOKEN"] = "x" * 40
        # Only the controlled test bypasses the production HTTPS validator.
        endpoint = Endpoint.model_construct(
            url=f"http://127.0.0.1:{server.server_port}", token_env="TRICKLE_TEST_TOKEN"
        )
        started = time.monotonic()
        try:
            with self.assertRaises(ValueError):
                post(endpoint, {"incident_id": "a" * 64})
            self.assertLess(time.monotonic() - started, 6)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
            del os.environ["TRICKLE_TEST_TOKEN"]


if __name__ == "__main__":
    unittest.main()
