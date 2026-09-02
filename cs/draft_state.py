"""Does this draft still answer the conversation it was written for?

A draft has no lifecycle. Gmail Drafts is a folder, the engine's draft store is
a `status='draft'` filter, and neither of them knows that the customer wrote
again an hour after the draft was composed, or that somebody already answered
by hand. `cs review` used to list both stores raw, so a reply written for a
question that has since been withdrawn was presented as ready to send.

This module gives every draft a VERDICT, computed at review time and stored
nowhere. Three of the four signals are Gmail-anchored, need no engine and
cannot degrade:

    duplicate   — the same text is already in Sent to that contact: this draft
                  is a SECOND COPY of a mail they already have, and sending it
                  mails them the same thing twice. Ranked strongest, because
                  it is the only signal about the draft's CONTENT rather than
                  about the conversation around it. It needs a body to
                  compare, so it fires on engine drafts (and on a Gmail draft
                  paired with its engine copy); a Gmail-only row carries
                  headers alone and keeps the other verdicts.
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
duplicate > overtaken > superseded > settled. A copy of mail already delivered
outranks everything: on a thread where the customer has since replied, both
`duplicate` and `overtaken` are true, and "they already have this text" is the
more actionable of the two.

No verdict blocks anything. `RE_DECIDE` GROUPS the drafts the digest asks the
operator to read again before sending; a deliberate re-send is flagged, never
skipped, and nothing here can refuse one.

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
VERDICT_RANK = {"duplicate": 0, "overtaken": 1, "superseded": 2, "settled": 3,
                "ready": 4}

#: Verdicts that mean "read this again before sending".
RE_DECIDE = ("duplicate", "overtaken", "superseded", "settled")

#: Shortest body the duplicate check will compare. A one-line courtesy
#: ("Grazie!") repeats honestly across unrelated conversations, so matching it
#: would call every second thank-you a duplicate; below this the other
#: verdicts decide.
MIN_DUPLICATE_BODY = 40

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
        # `list_drafts` fetches headers only, so a Gmail-only draft has no
        # text to compare and simply skips the duplicate check.
        "body": row.get("body") or "",
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
        "body": row.get("body") or "",
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
                # Only the engine copy carries text; the Gmail side is
                # headers. Keep it, or the pair loses the duplicate check the
                # engine-only row would have had.
                base["body"] = g["body"] or e["body"]
            base.pop("source", None)
            out.append(base)
    return out


def _lookback_days(composed_at: datetime, now: datetime) -> int:
    return max(1, min(MAX_LOOKBACK_DAYS, (now - composed_at).days + 2))


def _across_inbound(unreadable: dict[str, str]):
    """The default `inbound` read: the fan-out over every mailbox in scope,
    recording what it could not open into `unreadable` instead of raising.

    A closure rather than a module-level function because the collector belongs
    to ONE reconcile run — and because the injection contract stays exactly what
    it was (a callable returning a list of message dicts), so every fixture that
    stands in for this read keeps working unchanged."""

    def read(settings, addr, after=None):
        from . import mailboxes

        fan = mailboxes.inbound_since_across(settings, addr, after=after)
        for u in fan.unreadable:
            unreadable.setdefault(u.address or u.account, u.describe())
        return fan.rows

    return read


def _across_sent(unreadable: dict[str, str]):
    """The default `sent` read — same shape, same collector, Sent folders."""

    def read(settings, addr, days=None):
        from . import mailboxes

        fan = mailboxes.sent_to_across(settings, addr, days=days)
        for u in fan.unreadable:
            unreadable.setdefault(u.address or u.account, u.describe())
        return fan.rows

    return read


def reconcile(
    settings,
    gmail_drafts: list[dict],
    engine_drafts: list[dict],
    *,
    inbound=None,
    sent=None,
    settled=None,
    delivered=None,
    now: datetime | None = None,
) -> tuple[list[dict], list[str]]:
    """`(rows, notes)` — one row per LOGICAL draft, each carrying its verdict.

    `inbound`, `sent`, `settled` and `delivered` are the four reads, injected
    so the logic is testable over fixture dicts (the shape `cs/unanswered.py`'s
    tests use). Their defaults are the real ones: the CROSS-MAILBOX fan-out
    (`cs/mailboxes.py`) for `inbound` and `sent`, `engine_view.settled`, and
    `gmail_archive.sent_body_match`.

    Why the fan-out for two of them: `overtaken` and `superseded` are claims
    about the CONVERSATION, not about one mailbox. A customer who wrote again
    to a colleague has written again, and a colleague who answered has answered
    — a draft still marked `ready` because the only mailbox consulted saw
    nothing is the queue presenting a stale answer as fresh. A mailbox that
    could not be read becomes a NOTE, not a retired row: this is the review
    surface, and its contract is that no degradation ever removes a draft from
    the operator's eyes. (`delivered` stays single-mailbox: "was this exact
    text already delivered" is about our own copy of the body, and widening it
    is a different question.)

    Every row: `to`, `to_display`, `subject`, `thread_key`, `composed_at`,
    `composed_iso`, `gmail_uid`, `engine_id`, `verdict`, `signal`, `signal_at`,
    `evidence_incomplete`. The last one is the mailboxes that could not be read
    while this row's verdict was computed — empty unless the verdict is `ready`,
    which is the only one that rests on an absence. `notes` holds one line per
    degradation, never an exception.
    """
    from . import engine_view, gmail_archive

    # Mailboxes that failed a read during THIS reconcile, address -> reason.
    # Collected by the default readers below and reported once at the end: the
    # same mailbox fails for every contact, and one note per row would bury the
    # rows themselves.
    unreadable: dict[str, str] = {}
    inbound = inbound or _across_inbound(unreadable)
    sent = sent or _across_sent(unreadable)
    settled = settled or engine_view.settled
    delivered = delivered or gmail_archive.sent_body_match
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
    # Keyed by (contact, body): two rows carrying the same text to the same
    # person ask the identical question, and that pair is precisely the
    # duplicate case, so it must cost ONE read and not two.
    delivered_cache: dict[tuple, dict | None] = {}

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

        # Is this draft a second copy of a mail they already have? Asked
        # first, because it outranks every signal about the conversation: a
        # duplicate on a thread the customer has since replied to is BOTH
        # `duplicate` and `overtaken`, and only the first says "do not send
        # this text again". No date bound — a copy of something delivered is
        # a copy whenever it was delivered.
        body = (row.get("body") or "").strip()
        if len(body) >= MIN_DUPLICATE_BODY:
            cache_key = (addr, body)
            if cache_key not in delivered_cache:
                try:
                    hit, note = delivered(settings, addr, body)
                    delivered_cache[cache_key] = hit
                    if note:
                        notes.append(note)
                except Exception as e:  # noqa: BLE001 — degradation is the contract
                    delivered_cache[cache_key] = None
                    notes.append(f"could not compare {addr}'s Sent bodies: "
                                 f"{type(e).__name__}: {e}")
            hit = delivered_cache[cache_key]
            if hit:
                row["verdict"] = "duplicate"
                row["signal"] = (f"this exact text was already delivered to "
                                 f"{addr}")
                row["signal_at"] = _iso(parse_mail_date(hit.get("date")))
                continue

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

    gaps = list(unreadable.values())
    for row in rows:
        # ON THE ROW, not only in a note. `ready` is the one verdict that rests
        # on an ABSENCE — nothing overtook this draft, nobody answered since —
        # and an absence read from a mailbox that could not be opened is
        # precisely what this workstream exists to stop. The reviewer acts row
        # by row, so the qualification has to travel with the row it qualifies;
        # a footer under two blocks is read after the decision, if at all.
        #
        # The other verdicts rest on something FOUND (a later inbound, a later
        # send, a delivered body, the engine's own reading), and a positive is
        # a positive whatever else could not be read — so they carry no gap.
        # The key is always present, so a machine reader can trust its absence
        # to mean "complete".
        row["evidence_incomplete"] = list(gaps) if (gaps and row["verdict"] == "ready") else []
    if unreadable:
        # The run-level note stays as well: it names the mailbox ONCE for a
        # reader scanning the digest, and it is what says the scope narrowed at
        # all when every row happens to be re-decided anyway.
        notes.append(
            "verdicts below are computed from an INCOMPLETE scope — "
            + "; ".join(gaps)
            + ". A draft can read as `ready` here because a mailbox that would "
              "have overtaken it could not be opened."
        )
    rows.sort(key=lambda r: (VERDICT_RANK.get(r["verdict"], 9),
                             r["composed_at"] or datetime.min.replace(
                                 tzinfo=timezone.utc)))
    return rows, notes


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """`(ready, re_decide)` — the two blocks the review prints."""
    ready = [r for r in rows if r.get("verdict") == "ready"]
    re_decide = [r for r in rows if r.get("verdict") in RE_DECIDE]
    return ready, re_decide
