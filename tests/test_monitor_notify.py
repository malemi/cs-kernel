"""Real local publication/subscription controls; never contact a provider or mailbox."""

import concurrent.futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

from cs.monitor_notify import NotifyServer
from cs.monitor_notify_config import NotifyConfig
from cs.monitor_notify_io import DISPLAY_PREFIX, Subscriber, _publish, _worker, ingest, publish
from cs.monitor_notify_protocol import canonical, signed, summary
from cs.monitor_notify_store import Inbox


class LocalProvider(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        self.stop_event = threading.Event()
        self.listeners = []
        self.messages = []
        self.deliver = True
        self.trickle = False
        self.guard = threading.Lock()
        super().__init__(("127.0.0.1", 0), ProviderHandler)


class ProviderHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        listener = queue.Queue()
        self.server.listeners.append(listener)
        since = parse_qs(urlsplit(self.path).query).get("since", ["all"])[0]
        past = list(self.server.messages)
        offset = next((i + 1 for i, event in enumerate(past) if event["id"] == since), 0)
        for event in past[offset:]:
            listener.put(event)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        try:
            self.wfile.write(b'{"event":"open"}\n')
            self.wfile.flush()
            while not self.server.stop_event.is_set():
                try:
                    item = listener.get(timeout=0.1)
                except queue.Empty:
                    item = {"event": "keepalive"}
                self.wfile.write(json.dumps(item).encode() + b"\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.server.listeners.remove(listener)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        with self.server.guard:
            identity = "notification" + str(len(self.server.messages))
            event = {"event": "message", "id": identity, "message": raw.decode()}
            self.server.messages.append(event)
        if self.server.deliver:
            for listener in list(self.server.listeners):
                listener.put(event)
        raw = json.dumps(event).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if self.server.trickle:
            try:
                for byte in raw:
                    if self.server.stop_event.is_set():
                        break
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.3)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.wfile.write(raw)


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {
                "NOTIFY_TOKEN": "t" * 64,
                "NOTIFY_TOPIC": "private_topic_" + "a" * 40,
                "NOTIFY_SIGN": "s" * 64,
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.config = NotifyConfig(
            backend="ntfy",
            monitor_id="a" * 32,
            owner_uid="OWNER_CANARY",
            state_dir=str(self.root / "inbox"),
            token_env="NOTIFY_TOKEN",
            topic_env="NOTIFY_TOPIC",
            signing_key_env="NOTIFY_SIGN",
            port=0,
        )
        self.provider = LocalProvider()
        self.provider_thread = threading.Thread(target=self.provider.serve_forever, daemon=True)
        self.provider_thread.start()
        self.base = f"http://127.0.0.1:{self.provider.server_port}"
        self.addCleanup(self.stop_provider)

    def stop_provider(self):
        self.provider.stop_event.set()
        self.provider.shutdown()
        self.provider.server_close()

    def item(self):
        return summary(
            self.config,
            {
                "schema_version": 1,
                "monitor_id": self.config.monitor_id,
                "owner_uid": self.config.owner_uid,
                "causes": ["monitor-absent"],
                "last_received_at": 100,
                "action": "Inspect independent monitor, logging and alert-delivery health",
            },
        )

    def subscriber(self):
        sub = Subscriber(self.config, base=self.base)
        sub.start()
        self.assertTrue(sub.connected.wait(2))
        self.addCleanup(sub.stop_event.set)
        return sub

    def test_actual_provider_admission_without_subscriber_never_accepts(self):
        result = publish(self.config, self.item(), base=self.base)
        self.assertFalse(result["accepted"])
        self.assertEqual(len(self.provider.messages), 1)
        self.assertFalse(
            Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id).view()[
                "receipts"
            ]
        )

    def test_actual_stream_receipt_restart_dedup_and_safe_export(self):
        self.subscriber()
        result = publish(self.config, self.item(), base=self.base)
        self.assertTrue(result["accepted"])
        receipt = result["receipt"]
        self.assertEqual(receipt["provider_id"], "notification0")
        # A new publisher/store instance has the same durable receipt and sends nothing.
        again = publish(self.config, self.item(), base=self.base)
        self.assertEqual(again, result)
        self.assertEqual(len(self.provider.messages), 1)
        inbox = Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id)
        self.assertEqual(inbox.view(receipt["nonce"])["receipts"], [receipt])
        wire = self.provider.messages[0]["message"]
        for secret in (
            "OWNER_CANARY",
            os.environ["NOTIFY_TOKEN"],
            os.environ["NOTIFY_TOPIC"],
            os.environ["NOTIFY_SIGN"],
        ):
            self.assertNotIn(secret, wire)
        self.assertTrue(wire.startswith(DISPLAY_PREFIX))
        value = json.loads(wire[len(DISPLAY_PREFIX) :])
        self.assertEqual(
            set(value), {"v", "monitor", "kind", "count", "nonce", "reference", "signature"}
        )

    def test_tampered_foreign_and_unrequested_notifications_are_not_receipts(self):
        inbox = Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id)
        nonce, _ = inbox.reserve(self.item()["fingerprint"], 100, time.time())
        value = signed(self.config, self.item(), nonce)
        inbox.bind(nonce, canonical(value))
        for mutate in (
            lambda v: v.update(monitor="b" * 32),
            lambda v: v.update(count=9),
            lambda v: v.update(nonce="f" * 32),
        ):
            changed = dict(value)
            mutate(changed)
            self.assertFalse(
                ingest(
                    self.config,
                    inbox,
                    {"event": "message", "id": "foreign", "message": json.dumps(changed)},
                )
            )
        self.assertFalse(inbox.view()["receipts"])
        self.assertTrue(
            ingest(
                self.config,
                inbox,
                {"event": "message", "id": "correct", "message": json.dumps(value)},
            )
        )
        with self.assertRaises(ValueError):
            Inbox(self.config.state_dir, "foreign-owner", self.config.monitor_id)

    def test_real_subscriber_reconnect_replays_missed_publication_into_durable_inbox(self):
        first = self.subscriber()
        self.assertTrue(publish(self.config, self.item(), base=self.base)["accepted"])
        first.stop_event.set()
        first.join(1)
        self.assertFalse(first.is_alive())
        other = summary(
            self.config,
            {
                "schema_version": 1,
                "monitor_id": self.config.monitor_id,
                "owner_uid": self.config.owner_uid,
                "causes": ["monitor-degraded"],
                "last_received_at": 101,
            },
        )
        self.provider.deliver = False
        self.assertFalse(
            _publish(self.config, other, self.base, time.monotonic() + 0.2)["accepted"]
        )
        self.provider.deliver = True
        second = self.subscriber()
        deadline = time.monotonic() + 2
        inbox = Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id)
        while len(inbox.view()["receipts"]) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(len(inbox.view()["receipts"]), 2)
        self.assertTrue(publish(self.config, other, base=self.base)["accepted"])
        self.assertTrue(second.connected.is_set())
        self.assertEqual(len(self.provider.messages), 2)

    def test_admission_is_atomic_bounded_and_uncertainty_survives_restart(self):
        inbox = Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id)
        now = time.time()

        def reserve(i):
            try:
                return Inbox(
                    self.config.state_dir, self.config.owner_uid, self.config.monitor_id
                ).reserve(f"{i:064x}", 3, now)[0]
            except Exception as error:
                return type(error).__name__

        # Independent objects/connections reserve the same finite shared budget.
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(reserve, range(12)))
        self.assertEqual(sum(len(v) == 32 for v in results), 3)
        with self.assertRaises(ValueError):
            inbox.reserve("z" * 64, 3, now)
        with inbox.connect() as db:
            existing = db.execute("SELECT fp FROM jobs LIMIT 1").fetchone()[0]
        nonce, fresh = inbox.reserve(existing, 3, now + 1)
        self.assertFalse(fresh)
        self.assertEqual(len(nonce), 32)
        with self.assertRaises(ValueError):
            inbox.reserve(existing, 3, now + 61)

    def test_confirmed_delivery_does_not_disable_hourly_escalation(self):
        inbox = Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id)
        item = self.item()
        now = time.time()
        nonce, fresh = inbox.reserve(item["fingerprint"], 100, now)
        body = signed(self.config, item, nonce)
        inbox.bind(nonce, canonical(body))
        self.assertTrue(
            ingest(
                self.config,
                inbox,
                {"event": "message", "id": "receipt", "message": json.dumps(body)},
                now=now,
            )
        )
        self.assertEqual(inbox.reserve(item["fingerprint"], 100, now + 1), (nonce, False))
        later, fresh = inbox.reserve(item["fingerprint"], 100, now + 3600)
        self.assertTrue(fresh)
        self.assertNotEqual(later, nonce)

    def test_absolute_deadline_stops_trickling_provider(self):
        self.provider.trickle = True
        started = time.monotonic()
        self.assertFalse(publish(self.config, self.item(), base=self.base)["accepted"])
        self.assertLess(time.monotonic() - started, 3.3)

    def test_operational_notice_never_opens_smtp_socket(self):
        from cs.send_mail import send_operational_notice

        settings = SimpleNamespace(state_dir=self.root / "notice-local", engine_owner_uid="owner", slug="neutral")
        with patch("cs.send_mail.smtplib.SMTP", side_effect=AssertionError("no SMTP")):
            identity = send_operational_notice(settings, "a" * 32, "watchdog", 1)
        self.assertEqual(len(identity), 64)

    def test_retention_is_bounded_and_expired_receipts_are_not_exported(self):
        inbox = Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id)
        now = time.time()
        with inbox.connect() as db:
            db.executemany(
                "INSERT INTO jobs VALUES (?,?,?,NULL,NULL)",
                [(f"{i:064x}", f"{i:032x}", now) for i in range(1005)],
            )
            db.executemany(
                "INSERT INTO receipts VALUES (?,?,?,?,?,?)",
                [(f"{i:032x}", f"provider{i}", now, "incident", 1, "a" * 64) for i in range(1005)],
            )
        inbox.prune(now)
        with inbox.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM receipts").fetchone()[0], 1000)
            self.assertEqual(db.execute("SELECT count(*) FROM jobs").fetchone()[0], 1000)
        self.assertLess(inbox.path.stat().st_size, 2 * 1024**2)
        with patch("cs.monitor_notify_store.time.time", return_value=now + 31 * 86400):
            self.assertEqual(inbox.view()["receipts"], [])

    def test_http_fixed_owner_authentication_and_durable_inbox(self):
        server = NotifyServer(self.config, base=self.base)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.assertTrue(server.subscriber.connected.wait(2))
        root = f"http://127.0.0.1:{server.server_port}"
        payload = {
            "schema_version": 1,
            "monitor_id": self.config.monitor_id,
            "owner_uid": self.config.owner_uid,
            "causes": ["monitor-absent"],
            "last_received_at": None,
        }

        def request(value, token="t" * 64):
            return urllib.request.urlopen(
                urllib.request.Request(
                    root + "/alerts",
                    data=json.dumps(value).encode(),
                    headers={"Authorization": "Bearer " + token},
                ),
                timeout=4,
            )

        with self.assertRaises(urllib.error.HTTPError) as raised:
            request(payload, "wrong")
        self.assertEqual(raised.exception.code, 401)
        with self.assertRaises(urllib.error.HTTPError) as raised:
            request({**payload, "owner_uid": "foreign"})
        self.assertEqual(raised.exception.code, 400)
        with request(payload) as response:
            result = json.load(response)
        self.assertTrue(result["accepted"])
        with urllib.request.urlopen(
            urllib.request.Request(root + "/inbox", headers={"Authorization": "Bearer " + "t" * 64})
        ) as response:
            self.assertEqual(len(json.load(response)["receipts"]), 1)

    def test_operational_notice_retains_owner_evidence_without_mail(self):
        from cs.send_mail import send_operational_notice
        from cs.operational_inbox import location

        settings = SimpleNamespace(state_dir=self.root / "notice-local", engine_owner_uid="owner", slug="neutral")
        with patch("cs.send_mail.smtplib.SMTP", side_effect=AssertionError("no SMTP")), \
             patch("cs.send_mail._mirror_to_sent") as mirror:
            result = send_operational_notice(settings, "a" * 32, "incident", 2)
        root, _, _ = location(settings)
        document = json.loads((root / "problems.json").read_text())
        self.assertEqual(document["owner_uid"], "owner")
        self.assertEqual(document["problems"][0]["id"], result)
        mirror.assert_not_called()
        with self.assertRaises(ValueError):
            send_operational_notice(settings, "customer@example.test", "incident", 2)

    def test_input_canary_never_enters_summary(self):
        payload = {
            "schema_version": 1,
            "monitor_id": self.config.monitor_id,
            "owner_uid": self.config.owner_uid,
            "incident_count": 1,
            "incidents": [
                {
                    "id": "a" * 64,
                    "revision": 1,
                    "component": "kernel",
                    "cause": "coverage",
                    "first": 1,
                    "last": 2,
                    "detail": {"body": "CANARY_SECRET"},
                }
            ],
        }
        with self.assertRaises(ValueError):
            summary(self.config, payload)

    def test_wrapped_smtp_authentication_failure_keeps_safe_cause(self):
        import smtplib

        delivered = []

        class Pipe:
            def send(self, value):
                delivered.append(value)

            def close(self):
                pass

        with patch(
            "cs.monitor_notify_io._publish",
            side_effect=smtplib.SMTPAuthenticationError(535, b"CANARY_PASSWORD"),
        ):
            _worker(Pipe(), self.config, self.item(), self.base, time.monotonic() + 1)
        self.assertFalse(delivered[0]["accepted"])
        self.assertEqual(delivered[0]["failure"]["reason"], "auth")
        self.assertEqual(delivered[0]["failure"]["error_code"], 535)
        self.assertNotIn("CANARY_PASSWORD", json.dumps(delivered))
        self.assertEqual(
            Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id).view()[
                "last_failure"
            ]["reason"],
            "auth",
        )
