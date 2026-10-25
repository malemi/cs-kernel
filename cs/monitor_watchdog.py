"""Independent-host watchdog and bounded off-host evidence receiver."""

from __future__ import annotations

import hmac
import json
import math
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from .monitor_config import WatchdogConfig
from .monitor_store import MonitorStore, read_key, snapshot
from .monitor_transport import post
from .observability_store import _validate_event


def receive(config: WatchdogConfig, payload: dict, *, now: float | None = None) -> dict:
    """Authenticate outside this function; bind schema, owner and replay state here."""
    now = time.time() if now is None else now
    allowed = {
        "schema_version",
        "monitor_id",
        "owner_uid",
        "sequence",
        "scan_at",
        "status",
        "alert_delivery_ok",
        "open_incidents",
        "events",
        "copy_truncated",
        "copy_gap",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) - allowed
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("owner_uid") != config.owner_uid
        or payload.get("monitor_id") != config.monitor_id
        or type(payload.get("sequence")) is not int
        or not 1 <= payload["sequence"] < 2**53
        or payload.get("status") not in {"observed", "degraded"}
        or type(payload.get("alert_delivery_ok")) is not bool
        or type(payload.get("open_incidents")) is not int
        or not 0 <= payload["open_incidents"] <= 100000
        or type(payload.get("scan_at")) not in {int, float}
        or not math.isfinite(payload["scan_at"])
        or not 0 <= payload["scan_at"] <= now + 60
        or not isinstance(payload.get("events"), list)
        or len(payload["events"]) > 200
        or type(payload.get("copy_truncated", False)) is not bool
        or type(payload.get("copy_gap", False)) is not bool
    ):
        raise ValueError("Invalid observer heartbeat")
    if not all(
        _validate_event(event, SimpleNamespace(owner_uid=config.owner_uid))
        for event in payload["events"]
    ):
        raise ValueError("Invalid mirrored observation")
    store = MonitorStore(config.state_dir, config.owner_uid)
    # Serialize admission and sequence commit with event copies; replay cannot reset time.
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM kv WHERE key='received'").fetchone()
        previous = json.loads(row[0]) if row else {}
        if payload["sequence"] <= previous.get("sequence", 0):
            raise ValueError("Observer replay refused")
        for event in payload["events"]:
            db.execute(
                "INSERT OR IGNORE INTO events(id,component,stamp,payload,trace) VALUES (?,?,?,?,?)",
                (
                    event["event_id"],
                    event["component"],
                    now,
                    json.dumps(event, separators=(",", ":"), allow_nan=False),
                    event["trace_id"],
                ),
            )
        record = {key: value for key, value in payload.items() if key != "events"}
        record["received_at"] = now
        db.execute("INSERT OR REPLACE INTO kv VALUES ('received',?)", (json.dumps(record),))
    store.prune(now)
    return {"accepted": True}


def check(config: WatchdogConfig, *, now: float | None = None, sender=post) -> dict:
    """Detect absence even before the first heartbeat, using receiver time."""
    now = time.time() if now is None else now
    store = MonitorStore(config.state_dir, config.owner_uid)
    record = store.get("received", {})
    last = record.get("received_at", config.expected_start_utc)
    reasons = []
    if now > last + config.grace_seconds:
        reasons.append("monitor-absent")
    if record and now > record.get("scan_at", 0) + config.grace_seconds:
        reasons.append("monitor-scan-stale")
    if record.get("alert_delivery_ok") is False:
        reasons.append("primary-alert-unconfirmed")
    if record.get("status") == "degraded":
        reasons.append("monitor-degraded")
    prior = store.get("watchdog_alert", {})
    if not reasons and prior:
        # A fresh healthy receipt ends this outage, not the UTC-day attempt budget.
        # The next outage must obtain its own acknowledgement.
        store.set("watchdog_alert", {})
        prior = {}
    signature = ",".join(reasons)
    if reasons and (
        prior.get("signature") != signature
        or now - prior.get("at", 0) >= 86400
        or not prior.get("accepted", False) and now - prior.get("at", 0) >= 60
    ):
        day = int(now // 86400)
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT attempts FROM alerts WHERE day=? AND incident='watchdog'", (day,)
            ).fetchone()
            attempts = row[0] if row else 0
            if attempts >= config.daily_alert_limit:
                result = {
                    "schema_version": 1,
                    "monitor_id": config.monitor_id,
                    "owner_uid": config.owner_uid,
                    "checked_at": now,
                    "status": "degraded",
                    "causes": reasons,
                    "alert_accepted": False,
                    "alert_budget_exhausted": True,
                }
                db.execute(
                    "INSERT OR REPLACE INTO kv VALUES ('watchdog_check',?)",
                    (json.dumps(result),),
                )
                return result
            db.execute("INSERT OR REPLACE INTO alerts VALUES (?,'watchdog',?)", (day, attempts + 1))
        # Persist attempt before transport; watch alerts do not loop on broken routes.
        prior = {"signature": signature, "at": now, "accepted": False}
        store.set("watchdog_alert", prior)
        try:
            acknowledged = sender(
                config.alert,
                {
                    "schema_version": 1,
                    "monitor_id": config.monitor_id,
                    "owner_uid": config.owner_uid,
                    "causes": reasons,
                    "last_received_at": record.get("received_at"),
                    "action": "Inspect independent monitor, logging and alert-delivery health",
                },
            )
            if acknowledged.get("accepted") is not True:
                raise ValueError("Watchdog escalation unacknowledged")
            prior["accepted"] = True
            store.set("watchdog_alert", prior)
        except Exception:
            pass
    result = {
        "schema_version": 1,
        "monitor_id": config.monitor_id,
        "owner_uid": config.owner_uid,
        "checked_at": now,
        "status": "degraded" if reasons else "observed",
        "causes": reasons,
        "alert_accepted": prior.get("accepted", False),
        "last_received_at": record.get("received_at"),
        "copy_truncated": record.get("copy_truncated", False),
    }
    store.set("watchdog_check", result)
    return result


class WatchdogServer(ThreadingHTTPServer):
    """Loopback TLS upstream, with finite concurrent and total request lifetimes."""

    daemon_threads = True

    def __init__(self, config: WatchdogConfig):
        self.config = config
        self.slots = threading.BoundedSemaphore(16)
        self.last_check = 0.0
        value = os.environ.get(config.token_env, "")
        if not 32 <= len(value) <= 256 or not value.isascii() or any(c.isspace() for c in value):
            raise ValueError("Watchdog credential unavailable")
        self.token = value
        super().__init__(("127.0.0.1", config.port), WatchdogHandler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def service_actions(self) -> None:
        now = time.time()
        if now - self.last_check >= 10:
            self.last_check = now
            check(self.config, now=now)


class WatchdogHandler(BaseHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(1)
        self.timer = threading.Timer(3, self._expire)
        self.timer.daemon = True
        self.timer.start()

    def _expire(self):
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def finish(self) -> None:
        self.timer.cancel()
        try:
            super().finish()
        except OSError:
            pass

    def log_message(self, format, *args):
        pass

    def _reply(self, status: int, value: dict) -> None:
        raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > 262144:
            status, raw = 503, b'{"error":"response_limit"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def _authenticated(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        valid = len(supplied) <= 300 and hmac.compare_digest(
            supplied.encode(), ("Bearer " + self.server.token).encode()
        )
        if not valid:
            self._reply(401, {"error": "authentication_required"})
        return valid

    def do_POST(self) -> None:
        if not self._authenticated():
            return
        if self.path != "/heartbeat" or self.headers.get("Transfer-Encoding"):
            self._reply(400, {"error": "invalid_route"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 262144:
                raise ValueError("limit")
            result = receive(self.server.config, json.loads(self.rfile.read(length)))
            self._reply(200, result)
        except Exception:
            self._reply(400, {"error": "heartbeat_refused"})

    def do_GET(self) -> None:
        if not self._authenticated():
            return
        route = urlsplit(self.path)
        if len(self.path) > 1024 or route.path not in {"/status", "/events"}:
            self._reply(404, {"error": "unknown_route"})
            return
        try:
            query = parse_qs(route.query, max_num_fields=2)
            if set(query) - {"limit", "trace_id"} or any(len(v) != 1 for v in query.values()):
                raise ValueError("query")
            if route.path == "/status":
                if query:
                    raise ValueError("query")
                record = read_key(
                    self.server.config.state_dir, self.server.config.owner_uid, "watchdog_check"
                )
                result = {
                    "schema_version": 1,
                    "owner_uid": self.server.config.owner_uid,
                    "monitor_id": self.server.config.monitor_id,
                    "status": record.get("status", "unobserved"),
                }
                if result["status"] not in {"degraded", "observed", "unobserved"}:
                    raise ValueError("invalid observer status")
            else:
                limit = int(query.get("limit", ["100"])[0])
                if not 1 <= limit <= 200:
                    raise ValueError("limit")
                trace = query.get("trace_id", [None])[0]
                if trace is not None:
                    from .observability import diagnostic_id

                    if diagnostic_id(trace) != trace:
                        raise ValueError("trace")
                source = snapshot(
                    self.server.config.state_dir,
                    self.server.config.owner_uid,
                    limit=limit,
                    trace_id=trace,
                )
                record = read_key(
                    self.server.config.state_dir, self.server.config.owner_uid, "received"
                )
                truncated = record.get("copy_truncated", False)
                copy_gap = record.get("copy_gap", False)
                if type(truncated) is not bool or type(copy_gap) is not bool:
                    raise ValueError("invalid mirror coverage")
                result = {
                    "schema_version": 1,
                    "owner_uid": self.server.config.owner_uid,
                    "events": source["events"],
                    "coverage": "partial-off-host-copy",
                    "copy_truncated": truncated,
                    "copy_gap": copy_gap,
                }
                while len(json.dumps(result).encode()) > 240000 and result["events"]:
                    result["events"].pop()
                    result["copy_truncated"] = True
            self._reply(200, result)
        except Exception:
            self._reply(400, {"error": "invalid_query"})
