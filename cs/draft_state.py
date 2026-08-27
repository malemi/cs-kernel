"""Does this draft still answer the conversation it was written for?

A draft has no lifecycle. Gmail Drafts is a folder, the engine's draft store is
a `status='draft'` filter, and neither of them knows that the customer wrote
again an hour after the draft was composed, or that somebody already answered
by hand. `cs review` used to list both stores raw, so a reply written for a
question that has since been withdrawn was presented as ready to send.

This module gives every draft a VERDICT, computed at review time and stored
nowhere. Two of the three signals are Gmail-anchored, need no engine and cannot
degrade:

    overtaken   — the contact has a message in All Mail dated AFTER the draft
                  was composed: the draft answers a state of the conversation
                  that no longer holds.
    superseded  — the operator mailbox has a message in Sent to that contact
                  dated after the draft was composed: somebody answered another
                  way, and sending the draft would answer twice.

The engine adds one enrichment on top, never a substitute:

    settled     — `emails.needs_reply` (via `cs/engine_view.py`) says the newest
                  inbound on that conversation owes nothing. That is meaning,
                  and meaning is the engine's (charter invariant 4). When the
                  engine cannot be asked the label is simply absent and the
                  caller gets a note; the two Gmail comparisons still fire.

The split is the charter's: *does this message exist* → Gmail;
*what kind of message is it* → the engine.

A draft with no signal is `ready`. Precedence when several fire is
overtaken > superseded > settled: the customer having spoken since is the
strongest reason to re-read before sending.

**Nothing here deletes anything.** Retiring a draft is a silencing action in the
class of `cs handled` — a named, per-draft, human instruction — so this module
computes and reports, and the operator decides. Verdicts are recomputed every
run: a persisted "stale" flag would be a second piece of state to keep true
against a mailbox that keeps moving.

One logical draft can exist TWICE — `cs draft-reply` lets the engine compose and
mirrors the result into Gmail Drafts — so copies are paired by thread key plus
recipient and reported as ONE row carrying both handles, the Gmail `uid` and the
engine draft `id`. Retiring it takes both.

Degradation is a note, never an exception: a mailbox hiccup on one contact must
not cost the operator the whole digest.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parseaddr

from .gmail_archive import _parse_date as parse_mail_date
from .thread_key import thread_key

#: Strongest first. `ready` is the absence of every signal.
VERDICT_RANK = {"overtaken": 0, "superseded": 1, "settled": 2, "ready": 3}

#: Verdicts that mean "read this again before sending".
RE_DECIDE = ("overtaken", "superseded", "settled")

#: Widest Sent/All-Mail window a single draft may ask for, in days. A draft
#: older than this is compared over the cap: the question is only ever "did
#: anything happen AFTER the draft", and the per-message Date filter answers it
#: exactly, so the cap costs recall on nothing but ancient drafts.
MAX_LOOKBACK_DAYS = 120


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _addr(raw: str | None) -> str:
    """Bare lowercased address out of a To header (or a plain address)."""
    return (parseaddr(str(raw or ""))[1] or "").strip().lower()


def _first(value) -> str:
    """First element of an engine list field, or the value itself."""
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return str(value or "")


def _refs(value) -> str:
    """`references` as the whitespace-joined string `thread_key` expects.

    The engine stores it as a JSON list; Gmail hands it over as a header
    string. Both reach the same key.
    """
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value if v)
    return str(value or "")


def _engine_composed_at(row: dict) -> datetime | None:
    """When the engine says it composed this draft (UTC, tz-aware).

    The engine serialises UTC without an offset, so a naive value is read as
    UTC — the same convention as `cs/_time.py` and `cs/engine_view.py`.
    """
    for key in ("created_at", "updated_at"):
        raw = row.get(key)
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _gmail_row(row: dict) -> dict:
    """One Gmail Drafts header row → the shape this module reconciles."""
    key = row.get("thread_key")
    if not key:
        key = thread_key(row.get("message_id"), row.get("references"),
                         row.get("in_reply_to"))
    return {
        "source": "gmail",
        "gmail_uid": row.get("uid"),
        "engine_id": None,
        "to": _addr(row.get("to")),
        "to_display": row.get("to") or "",
        "subject": row.get("subject") or "",
        "thread_key": key or "",
        "composed_at": parse_mail_date(row.get("date")),
    }


def _engine_row(row: dict) -> dict:
    """One `drafts.list` row → the shape this module reconciles."""
    to = _first(row.get("to_addresses"))
    key = row.get("thread_id") or thread_key(
        None, _refs(row.get("references")), row.get("in_reply_to")
    )
    return {
        "source": "engine",
        "gmail_uid": None,
        "engine_id": row.get("id"),
        "to": _addr(to),
        "to_display": to,
        "subject": row.get("subject") or "",
        "thread_key": key or "",
        "composed_at": _engine_composed_at(row),
    }


def _pair(rows: list[dict]) -> list[dict]:
    """Merge the two copies of one logical draft into a single row.

    The key is (thread key, recipient) — the two properties both stores agree
    on. A thread key is only present when the draft is a REPLY; a compose has
    none, so those pair on the recipient plus the subject instead, which is the
    strongest thing left that is true of both copies. When one side holds more
    copies than the other the extras stay their own rows: two handles are
    better merged, but a draft without a handle cannot be retired.
    """
    buckets: dict[tuple, dict[str, list[dict]]] = {}
    order: list[tuple] = []
    for row in rows:
        key = (row["thread_key"] or f"subject:{row['subject'].strip().lower()}",
               row["to"])
        if key not in buckets:
            buckets[key] = {"gmail": [], "engine": []}
            order.append(key)
        buckets[key][row["source"]].append(row)

    out: list[dict] = []
    for key in order:
        gmail, engine = buckets[key]["gmail"], buckets[key]["engine"]
        for i in range(max(len(gmail), len(engine))):
            g = gmail[i] if i < len(gmail) else None
            e = engine[i] if i < len(engine) else None
            base = dict(g or e)  # type: ignore[arg-type]
            if g is not None and e is not None:
                base["engine_id"] = e["engine_id"]
                # The engine composed it; Gmail received the mirror moments
                # later. The earlier stamp is the one every comparison below
                # must use, or a message that arrived in between reads as older
                # than the draft and no signal fires.
                stamps = [s for s in (g["composed_at"], e["composed_at"]) if s]
                base["composed_at"] = min(stamps) if stamps else None
                base["to_display"] = g["to_display"] or e["to_display"]
                base["subject"] = g["subject"] or e["subject"]
                base["thread_key"] = g["thread_key"] or e["thread_key"]
            base.pop("source", None)
            out.append(base)
    return out


def _lookback_days(composed_at: datetime, now: datetime) -> int:
    return max(1, min(MAX_LOOKBACK_DAYS, (now - composed_at).days + 2))


def reconcile(
    settings,
    gmail_drafts: list[dict],
    engine_drafts: list[dict],
    *,
    inbound=None,
    sent=None,
    settled=None,
    now: datetime | None = None,
) -> tuple[list[dict], list[str]]:
    """`(rows, notes)` — one row per LOGICAL draft, each carrying its verdict.

    `inbound`, `sent` and `settled` are the three reads, injected so the logic
    is testable over fixture dicts (the shape `cs/unanswered.py`'s tests use).
    Their defaults are the real ones: `gmail_archive.inbound_since`,
    `gmail_archive.sent_to` and `engine_view.settled`.

    Every row: `to`, `to_display`, `subject`, `thread_key`, `composed_at`,
    `composed_iso`, `gmail_uid`, `engine_id`, `verdict`, `signal`, `signal_at`.
    `notes` holds one line per degradation, never an exception.
    """
    from . import engine_view, gmail_archive

    inbound = inbound or gmail_archive.inbound_since
    sent = sent or gmail_archive.sent_to
    settled = settled or engine_view.settled
    now = now or datetime.now(timezone.utc)

    rows = _pair(
        [_gmail_row(d) for d in (gmail_drafts or [])]
        + [_engine_row(d) for d in (engine_drafts or [])]
    )
    notes: list[str] = []

    # One engine call for every thread at once (`emails.needs_reply` batches);
    # an engine that is asleep, or that predates the method, costs a note and
    # nothing else.
    settled_views: dict = {}
    keys = [r["thread_key"] for r in rows if r["thread_key"]]
    if keys:
        try:
            settled_views, note = settled(settings, keys)
        except Exception as e:  # noqa: BLE001 — degradation is the contract
            settled_views, note = {}, f"{type(e).__name__}: {e}"
        if note:
            notes.append(f"engine verdicts unavailable: {note}")

    # Gmail is read once per contact, not once per draft: two drafts to the
    # same person are the common case (a reply and a follow-up), and the
    # answer to "did anything happen since" is a property of the CONTACT.
    inbound_cache: dict[str, list[dict]] = {}
    sent_cache: dict[str, list[dict]] = {}

    for row in rows:
        row["composed_iso"] = _iso(row["composed_at"])
        row["verdict"] = "ready"
        row["signal"] = None
        row["signal_at"] = None
        addr, composed_at = row["to"], row["composed_at"]

        if not addr:
            notes.append("a draft carries no recipient — no verdict computed "
                         "for it")
            continue
        if composed_at is None:
            notes.append(f"draft to {addr} carries no usable date — the Gmail "
                         f"comparisons need one, so no verdict was computed")
            continue

        days = _lookback_days(composed_at, now)

        if addr not in inbound_cache:
            try:
                inbound_cache[addr] = inbound(settings, addr, after=composed_at)
            except Exception as e:  # noqa: BLE001
                inbound_cache[addr] = []
                notes.append(f"could not read All Mail for {addr}: "
                             f"{type(e).__name__}: {e}")
        later_in = inbound_cache[addr]
        if later_in:
            newest = max(
                (parse_mail_date(m.get("date")) for m in later_in),
                key=lambda d: d or datetime.min.replace(tzinfo=timezone.utc),
                default=None,
            )
            row["verdict"] = "overtaken"
            row["signal"] = f"{addr} wrote again after this draft was composed"
            row["signal_at"] = _iso(newest)
            continue

        if addr not in sent_cache:
            try:
                sent_cache[addr] = sent(settings, addr, days=days)
            except Exception as e:  # noqa: BLE001
                sent_cache[addr] = []
                notes.append(f"could not read Sent for {addr}: "
                             f"{type(e).__name__}: {e}")
        later_out = [
            d for d in (
                parse_mail_date(m.get("date")) for m in sent_cache[addr]
            )
            if d is not None and d > composed_at
        ]
        if later_out:
            row["verdict"] = "superseded"
            row["signal"] = (f"we already wrote to {addr} after this draft was "
                             f"composed")
            row["signal_at"] = _iso(max(later_out))
            continue

        view = settled_views.get(row["thread_key"]) if row["thread_key"] else None
        if view is not None:
            reason = getattr(view, "reason", "") or "nothing left to answer"
            row["verdict"] = "settled"
            row["signal"] = f"the engine reads this conversation as settled: {reason}"
            row["signal_at"] = _iso(
                datetime.fromtimestamp(getattr(view, "at", 0), tz=timezone.utc)
            ) if getattr(view, "at", None) else None

    rows.sort(key=lambda r: (VERDICT_RANK.get(r["verdict"], 9),
                             r["composed_at"] or datetime.min.replace(
                                 tzinfo=timezone.utc)))
    return rows, notes


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """`(ready, re_decide)` — the two blocks the review prints."""
    ready = [r for r in rows if r.get("verdict") == "ready"]
    re_decide = [r for r in rows if r.get("verdict") in RE_DECIDE]
    return ready, re_decide
