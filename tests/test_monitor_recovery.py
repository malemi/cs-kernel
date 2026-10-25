"""Recovery must concern the failed operation; diagnostic retries preserve acknowledgement."""

import tempfile
import time
import json
from pathlib import Path
import unittest

from cs.monitor import _sync, _read_component, scan
from cs.monitor_config import Component
from cs.monitor_config import Endpoint, WatchdogConfig, MonitorConfig
from cs.monitor_evaluate import evaluate, initial_state, observe
from cs.monitor_store import MonitorStore
from cs.observability import EventStore, context
from cs.monitor_watchdog import check, receive


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = EventStore(self.root / "source", "owner")
        self.component = Component(id="kernel", kind="kernel", local_root=str(self.source.root))
        self.state = initial_state()

    def emit(self, stage, status, **metadata):
        with context():
            event = self.source.emit(stage, status, **metadata)
        observe(self.state, event, time.time())
        return event

    def findings(self):
        return evaluate(self.component, self.state, self.source.health(), time.time())

    def test_other_draft_success_cannot_clear_unknown_effect(self):
        self.emit("provider", "unknown-effect", reason="timeout", method="draft.send", draft_id="A")
        self.emit(
            "provider",
            "verified",
            reason="none",
            effect_certainty="verified",
            method="draft.send",
            draft_id="B",
        )
        self.assertEqual(sum(f["cause"] == "operation-failure" for f in self.findings()), 1)
        self.emit(
            "verification",
            "verified",
            reason="none",
            effect_certainty="verified",
            method="draft.verify",
            draft_id="A",
        )
        self.assertFalse(any(f["cause"] == "operation-failure" for f in self.findings()))

    def test_later_refused_attempt_does_not_downgrade_prior_unknown_effect(self):
        self.emit("provider", "failed", reason="timeout", effect_certainty="unknown", draft_id="A")
        self.emit("provider", "failed", reason="permission", effect_certainty="none", draft_id="A")
        self.emit("provider", "accepted", reason="none", effect_certainty="accepted", draft_id="A")
        pending = list(self.state["failures"].values())
        self.assertEqual(len(pending), 1)
        self.assertTrue(pending[0]["uncertain"])
        self.assertEqual(pending[0]["effect_certainty"], "unknown")
        self.emit(
            "verification", "verified", reason="none", effect_certainty="verified", draft_id="A"
        )
        self.assertEqual(len(self.state["failures"]), 0)

    def test_repeated_same_request_failure_keeps_ack_and_revision(self):
        event = dict(reason="quota", method="draft.generate", root_id="A", request_revision="v1")
        self.emit("rpc", "failed", **event)
        store = MonitorStore(self.root / "monitor", "owner")
        now = time.time()
        _sync(store, self.component.id, self.findings(), now, allow_recovery=True)
        incident = next(i for i in store.incidents() if i["cause"] == "operation-failure")
        self.assertTrue(store.ack(incident["id"], now, 86400))
        before = next(i for i in store.incidents() if i["id"] == incident["id"])
        self.emit("rpc", "failed", **event)
        _sync(store, self.component.id, self.findings(), now + 60, allow_recovery=True)
        after = next(i for i in store.incidents() if i["id"] == incident["id"])
        self.assertEqual(after["acknowledged"], before["acknowledged"])
        self.assertEqual(after["revision"], before["revision"])
        self.assertFalse(
            any(
                i["id"] == incident["id"]
                for i in store.incidents(active_only=True, due_at=now + 60)
            )
        )

    def test_scan_enforces_copy_capacity_after_new_ingestion(self):
        now = time.time()
        config = MonitorConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "observer"),
            expected_start_utc=int(now),
            components=[self.component],
        )
        store = MonitorStore(config.state_dir, "owner")
        event = self.source.emit("cli", "result", reason="none")
        with store.connect() as db:
            db.executemany(
                "INSERT INTO events(id,component,stamp,payload,trace) VALUES (?,?,?,?,?)",
                [
                    (
                        f"{i:032x}",
                        "kernel",
                        now - 1,
                        json.dumps({**event, "event_id": f"{i:032x}"}),
                        event["trace_id"],
                    )
                    for i in range(10000)
                ],
            )
        scan(config, now=now, reader=_read_component)
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], 10000)
        self.assertEqual(store.get("observer_eviction"), now)

    def test_verified_other_method_cannot_clear_unscoped_auth_failure(self):
        self.emit("rpc", "failed", reason="auth", method="draft.generate")
        self.emit(
            "provider",
            "verified",
            reason="none",
            effect_certainty="verified",
            method="draft.send",
            draft_id="B",
        )
        self.assertEqual(len(self.state["failures"]), 1)
        self.emit("rpc", "result", reason="none", method="draft.generate")
        self.assertEqual(len(self.state["failures"]), 0)

    def test_unrelated_cli_command_cannot_clear_draft_send_error(self):
        self.emit("cli", "result", reason="unknown", level="ERROR", command="draft-send")
        self.emit("cli", "result", reason="none", command="config")
        failures = [finding for finding in self.findings() if finding["cause"] == "operation-failure"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["detail"]["command"], "draft-send")
        store = MonitorStore(self.root / "monitor", "owner")
        _sync(store, self.component.id, failures, time.time(), allow_recovery=True)
        self.assertEqual(store.incidents()[0]["detail"]["command"], "draft-send")

    def test_matching_cli_command_recovery_retains_other_command_failure(self):
        binding = {"root_id": "root", "request_revision": "v1", "effect_certainty": "none"}
        self.emit("cli", "failed", reason="permission", command="draft-send", **binding)
        self.emit("cli", "failed", reason="permission", command="config", **binding)
        self.assertEqual(len(self.state["failures"]), 2)
        self.emit("cli", "result", reason="none", command="draft-send", **binding)
        pending = list(self.state["failures"].values())
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["command"], "config")
        self.emit("cli", "result", reason="none", command="config", **binding)
        self.assertFalse(self.state["failures"])

    def test_unknown_cli_command_requires_exact_attempt_recovery(self):
        for command in (None, "unknown"):
            with self.subTest(command=command):
                self.state = initial_state()
                metadata = {} if command is None else {"command": command}
                failed = self.emit("cli", "failed", reason="unknown", **metadata)
                self.emit("cli", "result", reason="none", **metadata)
                self.assertEqual(len(self.state["failures"]), 1)
                with context({"trace_id": failed["trace_id"], "span_id": failed["span_id"]}):
                    recovered = self.source.emit("cli", "result", reason="none", **metadata)
                observe(self.state, recovered, time.time())
                self.assertFalse(self.state["failures"])

    def test_uncertain_effectful_cli_requires_verified_exact_attempt(self):
        for command in ("draft-send", "chat", "campaign"):
            for status in ("unknown-effect", "failed"):
                with self.subTest(command=command, status=status):
                    self.state = initial_state()
                    failed = self.emit("cli", status, reason="unknown", command=command,
                                       effect_certainty="unknown")
                    self.emit("cli", "result", reason="none", command=command)
                    self.assertEqual(len(self.state["failures"]), 1)
                    self.emit("cli", "verified", reason="none", command=command,
                              effect_certainty="verified")
                    self.assertEqual(len(self.state["failures"]), 1)
                    with context({"trace_id": failed["trace_id"], "span_id": failed["span_id"]}):
                        verified = self.source.emit("cli", "verified", reason="none", command=command,
                                                    effect_certainty="verified")
                    observe(self.state, verified, time.time())
                    self.assertFalse(self.state["failures"])

    def test_terminal_idle_and_held_outcomes_close_started_span(self):
        for status in ("held", "deferred", "not-attempted", "paused", "disabled", "lock-skipped"):
            with self.subTest(status=status), context():
                start = self.source.emit("cli", "start")
                result = self.source.emit("cli", status, reason="policy-hold")
                self.assertEqual(start["span_id"], result["span_id"])
                state = initial_state()
                observe(state, start, time.time())
                observe(state, result, time.time())
                self.assertFalse(state["spans"])
                findings = evaluate(self.component, state, self.source.health(), time.time() + 2100)
                self.assertFalse(any(f["cause"] == "stalled-stage" for f in findings))

    def test_unknown_terminal_observation_keeps_logging_failure_visible(self):
        with context():
            start = self.source.emit("rpc", "start")
            result = self.source.emit("rpc", "unknown", reason="logging")
        observe(self.state, start, time.time())
        observe(self.state, result, time.time())
        self.assertFalse(self.state["spans"])
        failures = [f for f in self.findings() if f["cause"] == "operation-failure"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["detail"]["reason"], "logging")

    def test_watchdog_daily_cap_preserves_checks_receives_and_read_access(self):
        now = 1700000000
        config = WatchdogConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "remote"),
            token_env="WATCH",
            expected_start_utc=now - 301,
            alert=Endpoint(url="https://alerts.invalid/events", token_env="ALERT"),
        )
        deliveries = []

        def refused(*args):
            deliveries.append(args)
            return {"accepted": False}

        check(config, now=now, sender=refused)
        for sequence, status in ((1, "degraded"), (2, "observed"), (3, "degraded")):
            receive(
                config,
                dict(
                    schema_version=1,
                    monitor_id=config.monitor_id,
                    owner_uid="owner",
                    sequence=sequence,
                    scan_at=now + sequence,
                    status=status,
                    alert_delivery_ok=False,
                    open_incidents=1,
                    events=[],
                ),
                now=now + sequence,
            )
            result = check(config, now=now + sequence, sender=refused)
        self.assertTrue(result["alert_budget_exhausted"])
        self.assertEqual(len(deliveries), 3)
        self.assertTrue(check(config, now=now + 4, sender=refused)["alert_budget_exhausted"])
        receive(
            config,
            dict(
                schema_version=1,
                monitor_id=config.monitor_id,
                owner_uid="owner",
                sequence=4,
                scan_at=now + 5,
                status="observed",
                alert_delivery_ok=True,
                open_incidents=0,
                events=[],
            ),
            now=now + 5,
        )
        self.assertEqual(check(config, now=now + 5, sender=refused)["status"], "observed")
        self.assertEqual(MonitorStore(config.state_dir, "owner").get("received")["sequence"], 4)

    def test_watchdog_rearms_after_evidenced_recovery_with_same_day_budget(self):
        now = 1700000000
        config = WatchdogConfig(
            monitor_id="a" * 32,
            owner_uid="owner",
            state_dir=str(self.root / "remote"),
            token_env="WATCH",
            expected_start_utc=now,
            alert=Endpoint(url="https://alerts.invalid/events", token_env="ALERT"),
        )
        deliveries = []

        def sender(*args):
            deliveries.append(args)
            return {"accepted": len(deliveries) == 1}

        def healthy(sequence, at):
            receive(
                config,
                dict(
                    schema_version=1,
                    monitor_id=config.monitor_id,
                    owner_uid="owner",
                    sequence=sequence,
                    scan_at=at,
                    status="observed",
                    alert_delivery_ok=True,
                    open_incidents=0,
                    events=[],
                ),
                now=at,
            )
            self.assertEqual(check(config, now=at, sender=sender)["status"], "observed")

        healthy(1, now)
        self.assertTrue(check(config, now=now + 301, sender=sender)["alert_accepted"])
        healthy(2, now + 302)
        self.assertFalse(check(config, now=now + 603, sender=sender)["alert_accepted"])
        self.assertEqual(len(deliveries), 2)
        healthy(3, now + 604)
        check(config, now=now + 905, sender=sender)
        healthy(4, now + 906)
        self.assertTrue(check(config, now=now + 1207, sender=sender)["alert_budget_exhausted"])
        self.assertEqual(len(deliveries), 3)

    def test_refused_watchdog_delivery_retries_after_minute_with_persisted_cap(self):
        now = 1700000000
        config = WatchdogConfig(
            monitor_id="a" * 32, owner_uid="owner", state_dir=str(self.root / "retry"),
            token_env="WATCH", expected_start_utc=now, daily_alert_limit=6,
            alert=Endpoint(url="https://alerts.invalid/alerts", token_env="ALERT"),
        )
        attempts=[]
        def refused(*args):
            attempts.append(args)
            return {"accepted":False}
        for i in range(6):
            self.assertFalse(check(config,now=now+301+i*60,sender=refused)['alert_accepted'])
            check(config,now=now+302+i*60,sender=refused)
        self.assertEqual(len(attempts),6)
        # Reconstruct configuration/store, as a service restart does.
        restarted=WatchdogConfig.model_validate(config.model_dump())
        self.assertTrue(check(restarted,now=now+701,sender=refused)['alert_budget_exhausted'])
        self.assertEqual(len(attempts),6)
