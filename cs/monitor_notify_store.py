"""Private bounded subscriber inbox and durable, shared notification admission."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from .observability_store import _check, _open


class Inbox:
    def __init__(self, root: str | Path, owner: str, monitor: str):
        self.root = Path(root).absolute()
        for parent in (self.root, *self.root.parents):
            if parent.is_symlink():
                raise ValueError("Unsafe notification directory")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        _check(self.root, directory=True)
        self.path = self.root / "notifications.sqlite3"
        fd = _open(self.path, os.O_RDWR | os.O_CREAT)
        os.close(fd)
        if self.path.stat().st_size:
            with self.connect() as db:
                if db.execute("SELECT owner,monitor FROM identity").fetchone() != (owner, monitor):
                    raise ValueError("Notification owner differs")
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=DELETE;
                PRAGMA max_page_count=480;
                PRAGMA journal_size_limit=0;
                CREATE TABLE IF NOT EXISTS identity(owner TEXT,monitor TEXT);
                CREATE TABLE IF NOT EXISTS jobs(fp TEXT,nonce TEXT PRIMARY KEY,stamp REAL,digest TEXT,provider TEXT);
                CREATE INDEX IF NOT EXISTS jobs_fingerprint ON jobs(fp,stamp);
                CREATE TABLE IF NOT EXISTS attempts(day INTEGER PRIMARY KEY,count INTEGER);
                CREATE TABLE IF NOT EXISTS receipts(nonce TEXT,provider TEXT,stamp REAL,kind TEXT,count INTEGER,reference TEXT,PRIMARY KEY(nonce,provider));
                CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT);
            """)
            if not db.execute("SELECT 1 FROM identity").fetchone():
                db.execute("INSERT INTO identity VALUES (?,?)", (owner, monitor))

    @contextlib.contextmanager
    def connect(self):
        _check(self.path)
        db = sqlite3.connect(self.path, timeout=0.05)
        try:
            db.execute("PRAGMA max_page_count=480")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, fingerprint: str, limit: int, now: float) -> tuple[str, bool]:
        self.prune(now)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT nonce,stamp FROM jobs WHERE fp=? ORDER BY stamp DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
            if prior:
                # Deduplicate transport retries, not the monitor's hour/day escalation.
                if now - prior[1] < 60:
                    return prior[0], False
            day = int(now // 86400)
            row = db.execute("SELECT count FROM attempts WHERE day=?", (day,)).fetchone()
            count = row[0] if row else 0
            if count >= limit:
                raise ValueError("Notification admission exhausted")
            nonce = uuid.uuid4().hex
            db.execute("INSERT OR REPLACE INTO attempts VALUES (?,?)", (day, count + 1))
            db.execute("INSERT INTO jobs VALUES (?,?,?,NULL,NULL)", (fingerprint, nonce, now))
            return nonce, True

    def bind(self, nonce: str, raw: bytes) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET digest=? WHERE nonce=? AND digest IS NULL",
                (hashlib.sha256(raw).hexdigest(), nonce),
            )

    def provider(self, nonce: str, identity: str) -> None:
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identity):
            raise ValueError("Invalid notification provider reference")
        with self.connect() as db:
            db.execute("UPDATE jobs SET provider=? WHERE nonce=?", (identity, nonce))

    def received(self, body: dict, provider: str, raw: bytes, now: float) -> bool:
        if not isinstance(provider, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", provider):
            raise ValueError("Invalid subscriber reference")
        with self.connect() as db:
            row = db.execute(
                "SELECT digest,provider FROM jobs WHERE nonce=?", (body["nonce"],)
            ).fetchone()
            if (
                not row
                or row[0] != hashlib.sha256(raw).hexdigest()
                or (row[1] is not None and row[1] != provider)
            ):
                return False
            db.execute(
                "INSERT OR IGNORE INTO receipts VALUES (?,?,?,?,?,?)",
                (body["nonce"], provider, now, body["kind"], body["count"], body["reference"]),
            )
            db.execute("INSERT OR REPLACE INTO kv VALUES ('last_id',?)", (provider,))
            db.execute("DELETE FROM kv WHERE key='last_failure'")
        self.prune(now)
        return True

    def receipt(self, nonce: str) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT r.provider,r.stamp,r.kind,r.count,r.reference FROM receipts r JOIN jobs j ON r.nonce=j.nonce WHERE r.nonce=? AND r.stamp>=? AND (j.provider IS NULL OR j.provider=r.provider) ORDER BY r.stamp LIMIT 1",
                (nonce, time.time() - 30 * 86400),
            ).fetchone()
        return (
            {
                "nonce": nonce,
                "provider_id": row[0],
                "received_at": row[1],
                "kind": row[2],
                "count": row[3],
                "reference": row[4],
            }
            if row
            else None
        )

    def last_id(self) -> str:
        with self.connect() as db:
            row = db.execute("SELECT value FROM kv WHERE key='last_id'").fetchone()
        return row[0] if row else "all"

    def view(self, nonce: str | None = None) -> dict:
        if nonce is not None:
            if not re.fullmatch(r"[a-f0-9]{32}", nonce):
                raise ValueError("Invalid notification nonce")
            value = self.receipt(nonce)
            return {"receipts": [value] if value else []}
        with self.connect() as db:
            rows = db.execute(
                "SELECT nonce,provider,stamp,kind,count,reference FROM receipts WHERE stamp>=? ORDER BY stamp DESC LIMIT 100",
                (time.time() - 30 * 86400,),
            ).fetchall()
            failure = db.execute("SELECT value FROM kv WHERE key='last_failure'").fetchone()
        return {
            "receipts": [
                dict(
                    zip(("nonce", "provider_id", "received_at", "kind", "count", "reference"), row)
                )
                for row in rows
            ],
            "last_failure": json.loads(failure[0]) if failure else None,
        }

    def failure(self, value: dict) -> None:
        from .monitor_details import safe_detail

        safe_detail(value)
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO kv VALUES ('last_failure',?)", (json.dumps(value),))

    def prune(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute("DELETE FROM receipts WHERE stamp<?", (now - 30 * 86400,))
            db.execute("DELETE FROM jobs WHERE stamp<?", (now - 30 * 86400,))
            db.execute("DELETE FROM attempts WHERE day<?", (int(now // 86400) - 30,))
            db.execute(
                "DELETE FROM receipts WHERE rowid NOT IN (SELECT rowid FROM receipts ORDER BY stamp DESC LIMIT 1000)"
            )
            db.execute(
                "DELETE FROM jobs WHERE rowid NOT IN (SELECT rowid FROM jobs ORDER BY stamp DESC LIMIT 1000)"
            )
        if self.path.stat().st_size > 2 * 1024**2:
            raise ValueError("Notification storage exhausted")
