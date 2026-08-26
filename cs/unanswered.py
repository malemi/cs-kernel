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

The second blind spot is a thread a HUMAN has personally taken over while it is
still open (`State.escalated_to_human`, written by `cs escalated`). Sent cannot
know that either, so the sweep kept handing the owner two customers he was
mid-conversation with — and the headless operator, which answers customers
itself, kept preparing a second reply to them. Those senders come back in their
OWN bucket, never merged into `open` and never dropped: they are real work, they
are simply not the machine's to do. Unlike a handled record this one does NOT
expire on a newer message — the customer replying to the human who took the
thread over is that same conversation continuing, so expiring there would re-arm
the collision on the very event that causes it.

Scope is intentionally narrow: it answers ONLY "did we send them anything after
their last message". It does NOT classify intent or detect autoresponders — that
stays the LLM's job downstream. Over-including an autoresponder sender is
acceptable; the skill filters those with judgment.

The ignore list is matched as LITERALS PLUS fnmatch PATTERNS (`cs/addr_match.py`,
shared with the suppression list), because the loudest robots cannot be
enumerated: a bounce daemon's sending host rotates per message, so one customer's
undeliverable address produced seven distinct `mail-daemon@<host-NN>.<domain>`
senders in six days and an exact list was stale on the next bounce. `fnmatch`
keeps the decision deterministic and offline — no LLM decides who is a person.
What it must never do is widen: a pattern is a pattern only when the entry
carries a wildcard, so an address written before patterns existed still takes the
exact-match path.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .addr_match import AddrSet
from .config import Settings


def _partition(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None,
    escalated: dict[str, dict] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """(open rows, rows held by an out-of-band record, rows a human has taken
    over) — one pass, so the public views below never disagree about who is
    where. Every inbound sender lands in exactly one of the three."""
    self_addrs = {a.strip().lower() for a in self_addrs if a}
    # `self_addrs` stays exact on purpose: it is a list of identities we own,
    # not of robots we recognise, and a wildcard there would silently hide a
    # customer whose address resembles one of ours.
    # Idempotent: callers that already hold an AddrSet re-split a set of the
    # same entries, and a plain set (every unit test, every older caller) is
    # upgraded here rather than at each call site.
    ignore = AddrSet(ignore)
    handled_at: dict[str, datetime] = {}
    for a, d in (handled or {}).items():
        a = (a or "").strip().lower()
        if not a or d is None:
            continue
        # A naive record is read as UTC (same convention as cs/_time.py):
        # comparing it with a tz-aware message date would otherwise raise.
        handled_at[a] = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    taken: dict[str, dict] = {
        (a or "").strip().lower(): (r or {})
        for a, r in (escalated or {}).items()
        if (a or "").strip()
    }

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
    mine: list[dict] = []
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
        # Checked AFTER handled, and the order is a decision: "resolved" beats
        # "somebody is on it", so closing a thread you had taken over settles
        # it here even if the release was forgotten. The reverse order would
        # keep printing "with you" on a thread that is over.
        rec = taken.get(e)
        if rec is not None:
            at = rec.get("escalated_at")
            if at is not None and at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            mine.append({
                **row,
                "escalated_at": at,
                "escalated_owner": rec.get("owner") or "",
                "escalated_reason": rec.get("reason") or "",
                # Days the HUMAN has had it, which is the number that decides
                # whether an escalation has quietly rotted; `days_waiting` is
                # the customer's wait and answers a different question.
                "days_escalated": (now - at).days if at is not None else None,
            })
            continue
        out.append(row)
    out.sort(key=lambda r: r["last_inbound_date"])  # oldest first
    held.sort(key=lambda r: r["last_inbound_date"])
    mine.sort(key=lambda r: r["last_inbound_date"])
    return out, held, mine


def compute_open(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
) -> list[dict]:
    """Pure open-logic — no IMAP, unit-testable on plain dicts.

    - group `inbound` by `email`, keep each sender's LATEST message (max date);
    - a sender is OPEN if NO `sent` message addressed to that email has
      date > that latest inbound date;
    - drop any sender whose email is in `self_addrs`, or matches `ignore` —
      whose entries are literal addresses AND fnmatch patterns such as
      `mail-daemon@*` (an entry without a wildcard is matched exactly, as it
      always was);
    - drop any sender whose latest inbound is at or before their `handled`
      moment (resolved out of band — see the module docstring);
    - drop any sender in `escalated` (a human took the thread over; the row
      comes back from `compute_escalated`, never merged in here);
    - return OPEN senders oldest-first (by latest_inbound date), each row
      {email, name, last_inbound_date, subject, days_waiting}.
    """
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated)[0]


def compute_handled(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
) -> list[dict]:
    """The senders `compute_open` held back BECAUSE of an out-of-band record —
    the same rows plus `handled_at`. The other half of the pair, so a caller
    can SAY why somebody is missing from the open list: silence that looks like
    a bug gets reported as one. (`sweep()` returns both in one pass; this is
    for a caller that already has the plain dicts.)"""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated)[1]


def compute_escalated(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
) -> list[dict]:
    """The senders a HUMAN has taken over — the same rows plus `escalated_at`,
    `escalated_owner`, `escalated_reason` and `days_escalated`. Still open work,
    still owed an answer; just not the machine's to answer. A caller that
    prints `compute_open` and not this one has re-created the silent drop."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated)[2]


def sweep(settings: Settings, days: int) -> dict:
    """IMAP-backed sweep, ONE mailbox round trip: {"open": [...],
    "handled": [...], "escalated": [...]}. `handled` rows carry `handled_at` +
    `handled_reason`; `escalated` rows carry `escalated_at`, `escalated_owner`,
    `escalated_reason` and `days_escalated`."""
    from . import gmail_archive

    inbound = gmail_archive.inbound_recent(settings, days)
    sent = gmail_archive.sent_recent(settings, days)

    self_addrs = set(settings.self_email_set)
    if settings.email_address:
        self_addrs.add(settings.email_address.strip().lower())

    ignore = set(settings.system_sender_set)
    records: dict[str, dict] = {}
    taken: dict[str, dict] = {}
    try:
        from .state import State

        st = State(settings.db_path)
        # Suppression joins the ignore list, and both halves read a typed entry
        # the same way (`cs/addr_match.py`): a wildcard suppression that quietens
        # this sweep also blocks the outreach runner, which is the only version
        # of "do not contact" worth having.
        ignore |= st.do_not_contact_set()
        records = st.handled_out_of_band()
        taken = st.escalated_to_human()
    except Exception:
        pass  # suppression is best-effort; a missing db must not break discovery

    open_rows, held, mine = _partition(
        inbound,
        sent,
        self_addrs,
        ignore,
        datetime.now(timezone.utc),
        {e: r["handled_at"] for e, r in records.items()},
        taken,
    )
    for row in held:
        row["handled_reason"] = (records.get(row["email"]) or {}).get("reason", "")
    return {"open": open_rows, "handled": held, "escalated": mine}


def open_threads(settings: Settings, days: int) -> list[dict]:
    """Just the open senders (the sweep's headline list)."""
    return sweep(settings, days)["open"]


def crm_annotate(settings, rows: list[dict], lookup=None) -> str | None:
    """Attach a compact CRM label to each row, IN PLACE, and return the first
    degradation note (or None).

    WHY: the queue's size is not its workload. A sweep that prints a paying
    customer's outage next to a conference invitation and a bounce gives the
    same weight to both, and the operator re-does that separation by hand every
    morning. The CRM already knows which sender is a customer, so the sweep can
    say it — through the port (`cs/crm`), never a company switch, so a clone on
    a different backend gets the same column from its own adapter.

    Each row gains `crm` (the adapter's own facts for that address, rendered
    through its `render_hints` — never a lowest-common-denominator label the
    kernel invents) and `crm_known` (a record exists). No record and a degraded
    backend both leave `crm` empty, but only the second sets `crm_known` False
    for a reason worth printing — hence the returned note: ONE line in the
    caller, not one per address.

    `lookup` is injectable so the grouping is testable without a backend; the
    default is the port's own, which NEVER raises.
    """
    if lookup is None:
        from . import crm as _crm

        lookup = _crm.lookup
    note: str | None = None
    for row in rows:
        try:
            res = lookup(settings, row["email"])
        except Exception as e:  # noqa: BLE001 — the port promises not to, belt and braces
            row["crm"], row["crm_known"] = "", False
            note = note or f"{type(e).__name__}: {e}"
            continue
        if not res.ok and note is None and res.note:
            note = res.note
        if not res.rows:
            row["crm"], row["crm_known"] = "", False
            continue
        first = res.rows[0]
        facts = [str(first.facts.get(k, "")).strip() for k in (res.render_hints or [])]
        label = "/".join(f for f in facts if f) or (first.label or res.source)
        if len(res.rows) > 1:
            label = f"{label} (+{len(res.rows) - 1})"
        row["crm"], row["crm_known"] = label, True
    return note
