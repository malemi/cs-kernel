"""Local SQLite state at settings.db_path (~/.<slug>-cs/cs.db; PII — never in the repo).

- `sends`: one row per send attempt (real or dry-run), for audit + dedup.
- `do_not_contact`: suppression list.
- `handled_out_of_band`: "resolved, just not by email" — a DATED per-contact
  record (see `handled_out_of_band()` for why it is not a second suppression
  list).

Dedup counts only real sends (status='sent'): repeated dry-runs never
suppress, so a preview always shows the full would-send list.

Schema changes are additive `CREATE TABLE IF NOT EXISTS` statements replayed by
`executescript` on every open, so an existing clone's db picks up a new table on
its next command — there is no migration step to forget."""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sends (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  category   TEXT NOT NULL,          -- lead | signup | cancellation
  key        TEXT NOT NULL,          -- firebase uid (lead) | business_id (signup/cancellation)
  email      TEXT,
  subject    TEXT,
  message_id TEXT,
  status     TEXT NOT NULL,          -- sent | dry_run | failed
  dry_run    INTEGER NOT NULL,
  sent_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sends_key_cat ON sends(key, category, sent_at);
CREATE TABLE IF NOT EXISTS do_not_contact (
  email    TEXT PRIMARY KEY,
  reason   TEXT,
  added_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS handled_out_of_band (
  email       TEXT PRIMARY KEY,   -- lowercased on write
  handled_at  REAL NOT NULL,      -- the moment it was resolved; anything they
                                  -- sent BEFORE it is settled, later is not
  reason      TEXT,               -- how/where ("chiamato, risolto")
  recorded_at REAL NOT NULL       -- when the operator typed it (audit)
);
"""


class State:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def already_contacted(self, key: str, category: str, within_days: int) -> bool:
        cutoff = time.time() - within_days * 86400
        cur = self.conn.execute(
            "SELECT 1 FROM sends WHERE key=? AND category=? AND status='sent' "
            "AND sent_at>=? LIMIT 1",
            (key, category, cutoff),
        )
        return cur.fetchone() is not None

    def sent_today(self) -> int:
        cutoff = time.time() - 86400
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM sends WHERE status='sent' AND sent_at>=?", (cutoff,)
        )
        return int(cur.fetchone()[0])

    def do_not_contact_set(self) -> set[str]:
        return {
            r["email"].strip().lower()
            for r in self.conn.execute("SELECT email FROM do_not_contact")
            if r["email"]
        }

    def record(
        self,
        *,
        category: str,
        key: str,
        email: str | None,
        subject: str | None,
        message_id: str | None,
        status: str,
        dry_run: bool,
    ) -> None:
        self.conn.execute(
            "INSERT INTO sends(category,key,email,subject,message_id,status,dry_run,sent_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (category, key, email, subject, message_id, status, 1 if dry_run else 0, time.time()),
        )
        self.conn.commit()

    def suppress(self, email: str, reason: str = "") -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO do_not_contact(email,reason,added_at) VALUES(?,?,?)",
            (email.strip().lower(), reason, time.time()),
        )
        self.conn.commit()

    # ------------------------------------------------- handled out of band
    #
    # A phone call, a WhatsApp message, a conversation at a trade fair: the
    # thread is resolved and Gmail Sent — the dedup ground truth — knows
    # nothing about it. Without this record the open-work sweeps re-raise that
    # contact on every tick, for ever (they did: one customer wrote on 17 July,
    # the owner phoned him back the same week, and every daily tick until late
    # August told the owner to write to him).
    #
    # Deliberately NOT `do_not_contact`: that means "never write to them", and
    # this is a customer we very much want to keep talking to. What is settled
    # is their mail UP TO `handled_at` and nothing else — a later message makes
    # them open again by itself, with no second command to remember.

    def handled_out_of_band(self) -> dict[str, dict]:
        """email -> {handled_at, reason, recorded_at}; the two timestamps are
        tz-aware UTC datetimes (the open-work sweeps compare them against
        message dates, which are tz-aware too)."""
        out: dict[str, dict] = {}
        for r in self.conn.execute(
            "SELECT email, handled_at, reason, recorded_at FROM handled_out_of_band"
        ):
            e = (r["email"] or "").strip().lower()
            if not e:
                continue
            out[e] = {
                "handled_at": datetime.fromtimestamp(r["handled_at"], timezone.utc),
                "reason": r["reason"] or "",
                "recorded_at": datetime.fromtimestamp(r["recorded_at"], timezone.utc),
            }
        return out

    def handled_at_map(self) -> dict[str, datetime]:
        """Just email -> handled_at — the shape `unanswered.compute_open` takes."""
        return {e: r["handled_at"] for e, r in self.handled_out_of_band().items()}

    def mark_handled(
        self, email: str, *, reason: str = "", handled_at: datetime | None = None
    ) -> None:
        """Record (or re-record) an out-of-band resolution. REPLACE, so running
        it twice is not an error and the latest moment wins."""
        moment = (handled_at or datetime.now(timezone.utc)).timestamp()
        self.conn.execute(
            "INSERT OR REPLACE INTO handled_out_of_band"
            "(email,handled_at,reason,recorded_at) VALUES(?,?,?,?)",
            (email.strip().lower(), moment, reason, time.time()),
        )
        self.conn.commit()

    def unmark_handled(self, email: str) -> bool:
        """Remove the record; True when there was one (the inverse verb reports
        honestly instead of claiming an undo that undid nothing)."""
        cur = self.conn.execute(
            "DELETE FROM handled_out_of_band WHERE email=?", (email.strip().lower(),)
        )
        self.conn.commit()
        return cur.rowcount > 0
