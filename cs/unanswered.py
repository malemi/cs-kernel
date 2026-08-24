"""Deterministic 'still awaiting a human reply' sweep — Sent-anchored.

WHY THIS EXISTS: the triage skill used to discover open customer mail by asking
the engine LLM ("elenca la posta ancora senza risposta"). That is
NON-DETERMINISTIC — two runs of the same query returned different sets and
missed real unanswered customer mail 6–13 days old that had no engine task
(incident 2026-07-16). This module answers the binary deterministically:
enumerate recent inbound, subtract every sender we've since written to (Gmail
Sent = the dedup ground truth), no LLM in the discovery loop.

Sent is the ground truth deliberately, and it has ONE blind spot: a thread
resolved OUT OF BAND — by phone, WhatsApp, or face to face — leaves no Sent
message, so the sender stayed open for ever and every tick re-raised them
(a month of daily false alarms, 2026-07/08). The fix is a dated record per
contact (`State.handled_out_of_band`, written by `cs handled`): a sender whose
latest inbound PREDATES their handled moment is not open work, and a later
message re-opens them with no further action. The record is passed IN, so the
open-logic stays pure and unit-testable.

Scope is intentionally narrow: it answers ONLY "did we send them anything after
their last message". It does NOT classify intent or detect autoresponders — that
stays the LLM's job downstream. Over-including an autoresponder sender is
acceptable; the skill filters those with judgment.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .config import Settings


def _partition(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None,
) -> tuple[list[dict], list[dict]]:
    """(open rows, rows held back by an out-of-band record) — one pass, so the
    two public views below never disagree about who is where."""
    self_addrs = {a.strip().lower() for a in self_addrs if a}
    ignore = {a.strip().lower() for a in ignore if a}
    handled_at: dict[str, datetime] = {}
    for a, d in (handled or {}).items():
        a = (a or "").strip().lower()
        if not a or d is None:
            continue
        # A naive record is read as UTC (same convention as cs/_time.py):
        # comparing it with a tz-aware message date would otherwise raise.
        handled_at[a] = d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    latest: dict[str, dict] = {}
    for m in inbound:
        e = (m.get("email") or "").strip().lower()
        if not e or e in self_addrs or e in ignore:
            continue
        cur = latest.get(e)
        if cur is None or m["date"] > cur["date"]:
            latest[e] = m

    sent_max: dict[str, datetime] = {}
    for s in sent:
        d = s.get("date")
        if d is None:
            continue
        for a in s.get("to", []):
            a = (a or "").strip().lower()
            if not a:
                continue
            if a not in sent_max or d > sent_max[a]:
                sent_max[a] = d

    out: list[dict] = []
    held: list[dict] = []
    for e, m in latest.items():
        last = m["date"]
        if e in sent_max and sent_max[e] > last:
            continue  # we replied after their last inbound → answered
        row = {
            "email": e,
            "name": m.get("name") or "",
            "last_inbound_date": last,
            "subject": m.get("subject") or "",
            "days_waiting": (now - last).days,
        }
        h = handled_at.get(e)
        if h is not None and last <= h:
            # Resolved off-email BEFORE they last wrote → not open work. Note
            # the comparison is against their LATEST message: one sent after
            # the call is new, and lands in `out` on its own.
            held.append({**row, "handled_at": h})
            continue
        out.append(row)
    out.sort(key=lambda r: r["last_inbound_date"])  # oldest first
    held.sort(key=lambda r: r["last_inbound_date"])
    return out, held


def compute_open(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
) -> list[dict]:
    """Pure open-logic — no IMAP, unit-testable on plain dicts.

    - group `inbound` by `email`, keep each sender's LATEST message (max date);
    - a sender is OPEN if NO `sent` message addressed to that email has
      date > that latest inbound date;
    - drop any sender whose email is in `self_addrs` or `ignore`;
    - drop any sender whose latest inbound is at or before their `handled`
      moment (resolved out of band — see the module docstring);
    - return OPEN senders oldest-first (by latest_inbound date), each row
      {email, name, last_inbound_date, subject, days_waiting}.
    """
    return _partition(inbound, sent, self_addrs, ignore, now, handled)[0]


def compute_handled(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
) -> list[dict]:
    """The senders `compute_open` held back BECAUSE of an out-of-band record —
    the same rows plus `handled_at`. The other half of the pair, so a caller
    can SAY why somebody is missing from the open list: silence that looks like
    a bug gets reported as one. (`sweep()` returns both in one pass; this is
    for a caller that already has the plain dicts.)"""
    return _partition(inbound, sent, self_addrs, ignore, now, handled)[1]


def sweep(settings: Settings, days: int) -> dict:
    """IMAP-backed sweep, ONE mailbox round trip: {"open": [...],
    "handled": [...]}. `handled` rows carry `handled_at` + `handled_reason`."""
    from . import gmail_archive

    inbound = gmail_archive.inbound_recent(settings, days)
    sent = gmail_archive.sent_recent(settings, days)

    self_addrs = set(settings.self_email_set)
    if settings.email_address:
        self_addrs.add(settings.email_address.strip().lower())

    ignore = set(settings.system_sender_set)
    records: dict[str, dict] = {}
    try:
        from .state import State

        st = State(settings.db_path)
        ignore |= st.do_not_contact_set()
        records = st.handled_out_of_band()
    except Exception:
        pass  # suppression is best-effort; a missing db must not break discovery

    open_rows, held = _partition(
        inbound,
        sent,
        self_addrs,
        ignore,
        datetime.now(timezone.utc),
        {e: r["handled_at"] for e, r in records.items()},
    )
    for row in held:
        row["handled_reason"] = (records.get(row["email"]) or {}).get("reason", "")
    return {"open": open_rows, "handled": held}


def open_threads(settings: Settings, days: int) -> list[dict]:
    """Just the open senders (the sweep's headline list)."""
    return sweep(settings, days)["open"]
