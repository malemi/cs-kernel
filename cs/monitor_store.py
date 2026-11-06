"""Private, bounded incident and observer state; diagnostics never authorize effects."""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import math
import re
from pathlib import Path
from typing import Iterator

from .observability_store import _check, _open

MAX_BYTES = 64 * 1024**2
RETENTION = 30 * 86400


class MonitorStore:
    """One owner-scoped SQLite observer, with bounded lock time and retention."""

    def __init__(self, root: str | Path, owner_uid: str):
        self.root, self.owner_uid = Path(root).absolute(), owner_uid
        for parent in (self.root, *self.root.parents):
            if parent.is_symlink():
                raise ValueError("Unsafe monitoring state path")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        _check(self.root, directory=True)
        self.path = self.root / "monitor.sqlite3"
        fd = _open(self.path, os.O_RDWR | os.O_CREAT)
        os.close(fd)
        if self.path.stat().st_size:
            # Configuration mistakes must not migrate or rewrite another owner's store.
            existing = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.1)
            try:
                if existing.execute("SELECT owner FROM identity").fetchone() != (owner_uid,):
                    raise ValueError("Monitoring owner mismatch")
            finally:
                existing.close()
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=DELETE;
                PRAGMA max_page_count=8192;
                CREATE TABLE IF NOT EXISTS identity (owner TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, component TEXT, cause TEXT, first REAL, last REAL,
                    active INTEGER, revision INTEGER, acknowledged REAL DEFAULT 0,
                    last_sent REAL DEFAULT 0, sends INTEGER DEFAULT 0, detail TEXT,
                    accepted_revision INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, stamp REAL);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, component TEXT,
                    stamp REAL, payload TEXT, trace TEXT);
                CREATE INDEX IF NOT EXISTS trace_events ON events(trace,stamp);
                CREATE TABLE IF NOT EXISTS reservations (
                    day INTEGER, incident TEXT, revision INTEGER, usd REAL,
                    PRIMARY KEY(day, incident, revision));
                CREATE UNIQUE INDEX IF NOT EXISTS one_analysis ON reservations(incident,revision);
                CREATE TABLE IF NOT EXISTS alerts (
                    day INTEGER, incident TEXT, attempts INTEGER, PRIMARY KEY(day,incident));
            """)
            row = db.execute("SELECT owner FROM identity").fetchone()
            if row is None:
                db.execute("INSERT INTO identity VALUES (?)", (owner_uid,))
            elif row[0] != owner_uid:
                raise ValueError("Monitoring owner mismatch")

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        _check(self.path)
        for suffix in ("-journal", "-wal", "-shm"):
            extra = Path(str(self.path) + suffix)
            if extra.exists() or extra.is_symlink():
                _check(extra)
        db = sqlite3.connect(self.path, timeout=0.1)
        os.chmod(self.path, 0o600)
        try:
            with db:
                yield db
        finally:
            db.close()
            journal = Path(str(self.path) + "-journal")
            if journal.exists():
                os.chmod(journal, 0o600)

    def get(self, key: str, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set(self, key: str, value) -> None:
        raw = json.dumps(value, allow_nan=False, separators=(",", ":"))
        if len(raw.encode()) > 262144:
            raise ValueError("Monitoring state limit")
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, raw))

    def next_sequence(self) -> int:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM kv WHERE key='sequence'").fetchone()
            value = int(row[0]) + 1 if row else 1
            db.execute("INSERT OR REPLACE INTO kv VALUES ('sequence',?)", (str(value),))
            return value

    def remember(self, component: str, event: dict, now: float) -> bool:
        """Deduplicate original event IDs without rewriting hashes or ownership."""
        raw = json.dumps(event, separators=(",", ":"), allow_nan=False)
        if len(raw.encode()) > 8192:
            raise ValueError("Observer event limit")
        with self.connect() as db:
            changed = db.execute(
                "INSERT OR IGNORE INTO seen VALUES (?,?)", (event["event_id"], now)
            ).rowcount
            if changed:
                db.execute(
                    "INSERT INTO events(id,component,stamp,payload,trace) VALUES (?,?,?,?,?)",
                    (event["event_id"], component, now, raw, event["trace_id"]),
                )
            return bool(changed)

    def recent(self, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM events ORDER BY stamp DESC,id DESC LIMIT ?",
                (min(200, max(1, limit)),),
            ).fetchall()
            return [json.loads(row[0]) for row in rows]

    def mirror_page(self, cursor: int) -> dict:
        """Return the next unacknowledged originals without rewriting identities."""
        with self.connect() as db:
            rows = db.execute(
                "SELECT seq,payload FROM events WHERE seq>? ORDER BY seq LIMIT 200", (cursor,)
            ).fetchall()
            first = db.execute("SELECT MIN(seq) FROM events").fetchone()[0]
            pending = db.execute("SELECT count(*) FROM events WHERE seq>?", (cursor,)).fetchone()[0]
        from types import SimpleNamespace
        from .observability_store import _validate_event

        decoded = [(row[0], json.loads(row[1])) for row in rows]
        if not all(
            _validate_event(event, SimpleNamespace(owner_uid=self.owner_uid))
            for _, event in decoded
        ):
            raise ValueError("Invalid mirrored observation")
        return {
            "rows": decoded,
            "pending": pending,
            "gap": first is not None and first > cursor + 1,
        }

    def incidents(self, *, active_only: bool = False, due_at: float | None = None) -> list[dict]:
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            query = "SELECT * FROM incidents" + (" WHERE active=1" if active_only else "")
            args = ()
            if due_at is not None:
                query = (
                    "SELECT * FROM incidents WHERE active=1 AND acknowledged<=? AND sends<3 "
                    "AND (last_sent=0 OR last_sent+CASE WHEN sends=1 THEN 3600 ELSE 86400 END<=?)"
                )
                args = (due_at, due_at)
            rows = db.execute(query + " ORDER BY last_sent,first LIMIT 200", args).fetchall()
            result = [dict(row) for row in rows]
        for row in result:
            if (
                not isinstance(row["id"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", row["id"])
                or row["cause"]
                not in {
                    "coverage",
                    "missing-launch",
                    "stalled-stage",
                    "stale-observation",
                    "overdue-work",
                    "unresolved-expectation",
                    "engine-liveness-unconfirmed",
                    "operation-failure",
                    "alert-delivery-unconfirmed",
                    "watchdog-unavailable",
                }
                or not isinstance(row["component"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", row["component"])
                or type(row["first"]) not in {int, float}
                or not math.isfinite(row["first"])
            ):
                raise ValueError("Invalid incident metadata")
            from .monitor_details import safe_detail

            row["detail"] = safe_detail(json.loads(row["detail"]))
        return result

    def counts(self) -> dict:
        with self.connect() as db:
            active = db.execute("SELECT count(*) FROM incidents WHERE active=1").fetchone()[0]
            unconfirmed = db.execute(
                "SELECT count(*) FROM incidents WHERE active=1 AND accepted_revision<revision"
            ).fetchone()[0]
        return {"active": active, "unconfirmed": unconfirmed}

    def ack(self, incident_id: str, now: float, seconds: int = 86400) -> bool:
        if not 1 <= seconds <= 86400:
            raise ValueError("Acknowledgement expires within 24 hours")
        with self.connect() as db:
            return bool(
                db.execute(
                    "UPDATE incidents SET acknowledged=? WHERE id=? AND active=1",
                    (now + seconds, incident_id),
                ).rowcount
            )

    def prune(self, now: float) -> None:
        with self.connect() as db:
            for table, field in (("events", "stamp"), ("seen", "stamp")):
                db.execute(f"DELETE FROM {table} WHERE {field}<?", (now - RETENTION,))
            db.execute("DELETE FROM incidents WHERE active=0 AND last<?", (now - RETENTION,))
            db.execute("DELETE FROM reservations WHERE day<?", (int(now // 86400) - 30,))
            db.execute("DELETE FROM alerts WHERE day<?", (int(now // 86400) - 30,))
            count = db.execute("SELECT count(*) FROM events").fetchone()[0]
            if count > 10000:
                db.execute(
                    "DELETE FROM events WHERE id IN (SELECT id FROM events ORDER BY stamp LIMIT ?)",
                    (count - 10000,),
                )
                db.execute("INSERT OR REPLACE INTO kv VALUES ('observer_eviction',?)", (str(now),))
        if self.path.stat().st_size > MAX_BYTES:
            raise ValueError("Monitoring store capacity exhausted")


def snapshot(
    root: str | Path,
    owner_uid: str,
    *,
    limit: int = 100,
    trace_id: str | None = None,
    incident_id: str | None = None,
    incident_offset: int = 0,
) -> dict:
    """Read without creating, migrating, pruning or acknowledging observer state."""
    from types import SimpleNamespace
    from .observability_store import _validate_event

    if type(incident_offset) is not int or not 0 <= incident_offset <= 10000000:
        raise ValueError("Invalid incident offset")
    directory = Path(root).absolute()
    if not directory.exists():
        return {"status": "absent", "events": [], "incidents": []}
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError("Unsafe monitoring state path")
    _check(directory, directory=True)
    path = directory / "monitor.sqlite3"
    _check(path)
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.1)
    try:
        if db.execute("SELECT owner FROM identity").fetchone() != (owner_uid,):
            raise ValueError("Monitoring owner mismatch")
        row = db.execute("SELECT value FROM kv WHERE key='last_scan'").fetchone()
        scan = json.loads(row[0]) if row else None
        if scan is not None:
            if (
                not isinstance(scan, dict)
                or scan.get("status") not in {"observed", "degraded"}
                or type(scan.get("scan_at")) not in {int, float}
                or not math.isfinite(scan["scan_at"])
                or type(scan.get("sequence")) is not int
                or scan["sequence"] < 1
                or type(scan.get("open_incidents")) is not int
                or scan["open_incidents"] < 0
                or type(scan.get("alert_delivery_ok")) is not bool
            ):
                raise ValueError("Invalid observer summary")
            scan = {
                key: scan[key]
                for key in ("status", "scan_at", "sequence", "open_incidents", "alert_delivery_ok")
            }
        events = []
        query = "SELECT payload FROM events"
        args = ()
        if trace_id is not None:
            query += " WHERE trace=?"
            args = (trace_id,)
        for row in db.execute(query + " ORDER BY stamp DESC,id DESC LIMIT 200", args):
            event = json.loads(row[0])
            if not _validate_event(event, SimpleNamespace(owner_uid=owner_uid)):
                raise ValueError("Invalid mirrored observation")
            if trace_id is None or event["trace_id"] == trace_id:
                events.append(event)
            if len(events) >= min(200, max(1, limit)):
                break
        query = "SELECT id,cause,component,first,last,active,revision,acknowledged,detail FROM incidents"
        arguments = ()
        if incident_id is not None:
            if not re.fullmatch(r"[a-f0-9]{64}", incident_id):
                raise ValueError("Invalid incident identity")
            query += " WHERE id=?"
            arguments = (incident_id,)
        rows = db.execute(query + " ORDER BY first DESC,id LIMIT 200 OFFSET ?",
                          (*arguments, incident_offset)).fetchall()
        total_incidents = db.execute("SELECT count(*) FROM incidents").fetchone()[0]
        # No free-form incident details enter the read-only summary.
        incidents = [
            dict(
                zip(
                    (
                        "id",
                        "cause",
                        "component",
                        "first",
                        "last",
                        "active",
                        "revision",
                        "acknowledged",
                        "detail",
                    ),
                    row,
                )
            )
            for row in rows
        ]
        for incident in incidents:
            from .monitor_details import safe_detail

            incident["detail"] = safe_detail(json.loads(incident["detail"]))
            if (
                not re.fullmatch(r"[a-f0-9]{64}", incident["id"])
                or incident["cause"]
                not in {
                    "coverage",
                    "missing-launch",
                    "stalled-stage",
                    "stale-observation",
                    "overdue-work",
                    "unresolved-expectation",
                    "engine-liveness-unconfirmed",
                    "operation-failure",
                    "alert-delivery-unconfirmed",
                    "watchdog-unavailable",
                }
                or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", incident["component"])
                or incident["active"] not in (0, 1)
                or type(incident["revision"]) is not int
                or incident["revision"] < 1
                or any(
                    type(incident[key]) not in {int, float}
                    or not math.isfinite(incident[key])
                    or incident[key] < 0
                    for key in ("first", "last", "acknowledged")
                )
            ):
                raise ValueError("Invalid incident summary")
        result = {
            "status": "observed" if scan else "unobserved",
            "events": events,
            "incidents": incidents,
            "scan": scan,
            "incident_count": total_incidents,
            "incidents_truncated": incident_id is None and total_incidents > incident_offset + len(incidents),
            "incident_offset": incident_offset,
            "next_incident_offset": (incident_offset + len(incidents))
            if incident_id is None and total_incidents > incident_offset + len(incidents) else None,
        }
        count, oldest, newest = db.execute(
            "SELECT count(*),MIN(stamp),MAX(stamp) FROM events"
        ).fetchone()
        row = db.execute("SELECT value FROM kv WHERE key='observer_eviction'").fetchone()
        evicted = json.loads(row[0]) if row else None
        if any(
            value is not None
            and (type(value) not in {int, float} or not math.isfinite(value) or value < 0)
            for value in (oldest, newest, evicted)
        ):
            raise ValueError("Invalid observer retention metadata")
        result["event_retention"] = {
            "count": count,
            "received_from": oldest,
            "received_to": newest,
            "last_eviction_at": evicted,
            "maximum_events": 10000,
        }
        if len(json.dumps(result, allow_nan=False).encode()) > 240000:
            result["events"] = []
            result["coverage"] = "response-limit-query-fewer-events"
        while len(json.dumps(result, allow_nan=False).encode()) > 240000 and result["incidents"]:
            result["incidents"].pop()
            result["incidents_truncated"] = True
            result["next_incident_offset"] = incident_offset + len(result["incidents"])
        return result
    finally:
        db.close()


def read_key(root: str | Path, owner_uid: str, key: str) -> dict:
    """Read fixed watchdog metadata with a read-only SQLite connection."""
    if key not in {"received", "watchdog_check"}:
        raise ValueError("Invalid observer metadata")
    directory = Path(root).absolute()
    _check(directory, directory=True)
    for parent in (directory, *directory.parents):
        if parent.is_symlink():
            raise ValueError("Unsafe observer metadata path")
    target = directory / "monitor.sqlite3"
    _check(target)
    db = sqlite3.connect(target.as_uri() + "?mode=ro", uri=True, timeout=0.1)
    try:
        if db.execute("SELECT owner FROM identity").fetchone() != (owner_uid,):
            raise ValueError("Observer owner mismatch")
        row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        result = json.loads(row[0]) if row else {}
        if not isinstance(result, dict) or len(json.dumps(result).encode()) > 8192:
            raise ValueError("Invalid observer metadata")
        return result
    finally:
        db.close()
