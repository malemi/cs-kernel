"""Local SQLite state at settings.db_path (~/.<slug>-cs/cs.db; PII — never in the repo).

- `sends`: one row per send attempt (real or dry-run), for audit + dedup.
- `do_not_contact`: suppression list.
- `handled_out_of_band`: "resolved, just not by email" — a DATED per-contact
  record (see `handled_out_of_band()` for why it is not a second suppression
  list).
- `escalated_to_human`: "NOT resolved — a named human has personally taken
  this contact over" (see `escalated_to_human()` for why it is neither of the
  two above, and why it never expires by itself).

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
CREATE TABLE IF NOT EXISTS escalated_to_human (
  email        TEXT PRIMARY KEY,  -- lowercased on write
  owner        TEXT,              -- who took it over; "" = the operator himself
  reason       TEXT,              -- their own words ("sto scrivendo io")
  escalated_at REAL NOT NULL      -- when the record was made; the AGE the
                                  -- surfaces print, so it has no back-dating
                                  -- twin the way handled_out_of_band does
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
        # A contact cannot be both "resolved" and "a human is still writing to
        # them": resolving it IS the end of the taking-over. Enforced here
        # rather than in the verb so no caller can leave a "with you" label on
        # a thread that is over — that label would age for ever and read as
        # work still owed.
        self.conn.execute(
            "DELETE FROM escalated_to_human WHERE email=?", (email.strip().lower(),)
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

    # ------------------------------------------------- escalated to a human
    #
    # The sibling of `handled_out_of_band`, and the difference is the whole
    # point. `handled` says RESOLVED: the thread is over, and their mail up to
    # that moment stops being work. This one says the opposite — still open,
    # still owed an answer — but a named human is personally writing it. The
    # operator must stop being offered the contact as work to hand to the
    # machine, and the machine must stop drafting into a conversation a human
    # is already having. Two hands writing to the same customer is the
    # tone-deaf failure this operator exists to avoid.
    #
    # THREE properties follow from "still open", and each is a decision:
    #
    # 1. NO EXPIRY DATE. `handled` is scoped by a timestamp because a later
    #    message means a NEW conversation. Here a later message is the SAME
    #    conversation — the customer replying to the human who took it over —
    #    so an expiry would re-arm the exact collision on the exact event that
    #    triggers it. The record holds until a human releases it (`--undo`, or
    #    `mark_handled`, which clears it because the thread is then over).
    # 2. Because it never expires, it may NEVER become invisible. The
    #    open-work surfaces print the row itself, re-labelled and AGED (`cs
    #    unanswered`, `cs review`, `cs dossier`); the outreach worklist and the
    #    campaign runner, which report skips as counts per reason, count it
    #    under its own name. A record that suppresses for ever and says nothing
    #    is the silent drop this whole ledger was built to end.
    # 3. It is NOT `do_not_contact`: we want to keep talking to them — just
    #    with one mouth.

    def escalated_to_human(self) -> dict[str, dict]:
        """email -> {owner, reason, escalated_at}; `escalated_at` is a tz-aware
        UTC datetime and `owner` is "" when the operator took it himself."""
        out: dict[str, dict] = {}
        for r in self.conn.execute(
            "SELECT email, owner, reason, escalated_at FROM escalated_to_human"
        ):
            e = (r["email"] or "").strip().lower()
            if not e:
                continue
            out[e] = {
                "owner": r["owner"] or "",
                "reason": r["reason"] or "",
                "escalated_at": datetime.fromtimestamp(r["escalated_at"], timezone.utc),
            }
        return out

    def escalated_set(self) -> set[str]:
        """Just the addresses — the shape the outreach worklist filter takes."""
        return set(self.escalated_to_human())

    def mark_escalated(
        self, email: str, *, owner: str = "", reason: str = "",
        escalated_at: datetime | None = None
    ) -> None:
        """Record (or re-record) that a human owns this contact. REPLACE, so
        re-running is not an error; the moment moves, which is right — the
        human confirming today is on it today."""
        moment = (escalated_at or datetime.now(timezone.utc)).timestamp()
        self.conn.execute(
            "INSERT OR REPLACE INTO escalated_to_human"
            "(email,owner,reason,escalated_at) VALUES(?,?,?,?)",
            (email.strip().lower(), owner, reason, moment),
        )
        self.conn.commit()

    def unmark_escalated(self, email: str) -> bool:
        """Release the contact back to the machine; True when there was a
        record (so the inverse verb never claims an undo that undid nothing)."""
        cur = self.conn.execute(
            "DELETE FROM escalated_to_human WHERE email=?", (email.strip().lower(),)
        )
        self.conn.commit()
        return cur.rowcount > 0
