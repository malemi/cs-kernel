"""Read-time verdicts on current mailbox drafts, based on correspondence and Sent."""
from __future__ import annotations

import hashlib
import json

from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, getaddresses

from .gmail_archive import _parse_date as parse_mail_date
from .thread_key import normalize_key, thread_key

#: Strongest first. `ready` is the absence of every signal.
VERDICT_RANK = {"duplicate": 0, "overtaken": 1, "superseded": 2, "settled": 3,
                "ready": 4}

#: Verdicts that mean "read this again before sending".
RE_DECIDE = ("duplicate", "overtaken", "superseded", "settled")

WORKSET_HOLD_REASONS = frozenset({"identity_conflict", "body_unavailable",
    "uidvalidity_unknown", "root_missing", "recipient_missing", "date_missing",
    "verdict_unavailable", "mailbox_unreadable", "sent_body_unavailable"})

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


def _recipient_set(raw) -> tuple[str, ...]:
    values = raw if isinstance(raw, (list, tuple)) else [str(raw or "")]
    return tuple(sorted({addr.strip().lower() for _, addr in getaddresses(values) if addr.strip()}))


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


def mailbox_row(row: dict) -> dict:
    key = normalize_key(row.get("thread_id")) or thread_key(
        None, _refs(row.get("references")), row.get("in_reply_to"))
    return {
        "draft_id": row["id"],
        "mailbox_id": row["mailbox_id"],
        "to": next(iter(_recipient_set(row.get("to_addresses"))), ""),
        "to_display": _first(row.get("to_addresses")),
        "recipients": _recipient_set(row.get("to_addresses")),
        "cc_recipients": _recipient_set(row.get("cc_addresses")),
        "subject": row.get("subject") or "",
        "thread_key": key or "",
        "composed_at": parse_mail_date(row.get("created_at")),
        "body": row.get("body") or "",
    }


def _after(rows, composed_at: datetime) -> list[dict]:
    """Only the messages strictly newer than this draft.

    Every verdict here answers "did anything happen AFTER this draft was
    composed", and the bulk read is deliberately wider than any one draft's
    window, so the per-row test is what keeps one row's evidence from leaking
    into another's."""
    out = []
    for m in rows or []:
        d = parse_mail_date(m.get("date"))
        if d is not None and d > composed_at:
            out.append(m)
    return out


def _lookback_days(composed_at: datetime, now: datetime) -> int:
    return max(1, min(MAX_LOOKBACK_DAYS, (now - composed_at).days + 2))


def _bulk_across(unreadable: dict[str, str], skipped: dict[str, str],
                 notes: list[str]):
    """The default bulk read: ONE search + chunked FETCH per (mailbox, folder)
    for ALL contacts at once, bucketed by address in memory.

    Replaces a per-contact fan-out that issued one FETCH round trip per matching
    message. On the reference clone that was >25 minutes and never finished;
    this shape measures 7.2s over the same four mailboxes.

    Returns `(sent_by_addr, inbound_by_addr)`. Both collectors belong to ONE
    reconcile run, which is why this is a closure — and the injection contract
    for `inbound`/`sent` is unchanged, so every fixture that stands in for those
    reads keeps working."""

    def read(settings, addrs, since):
        from . import mailboxes

        out = {}
        for key in ("TO", "FROM"):
            fan = mailboxes.headers_since_across(settings, addrs, key, since=since)
            for u in fan.unreadable:
                unreadable.setdefault(u.address or u.account, u.describe())
            for k in fan.skipped:
                skipped.setdefault(k.address or k.account, k.describe())
            bucket: dict[str, list[dict]] = {}
            bcc_only: dict[tuple[str, str], int] = {}
            for row in fan.rows:
                if row.get("bcc_only"):
                    # Reported, never counted. Whether the server matched a
                    # Bcc is unknown, and a row counted here would mint
                    # `superseded` on evidence nobody established.
                    k = (row["matched"], row.get("mailbox") or "?")
                    bcc_only[k] = bcc_only.get(k, 0) + 1
                    continue
                bucket.setdefault(row["matched"], []).append(row)
            for (addr, mailbox), n in sorted(bcc_only.items()):
                notes.append(
                    f"{n} message(s) in {mailbox} carry {addr} only in Bcc — "
                    f"whether the server matched them is unknown, so they were "
                    f"reported and not counted"
                )
            out[key] = bucket
        return out["TO"], out["FROM"]

    return read


def _across_inbound(unreadable: dict[str, str]):
    """Injected `inbound` default: configured fan-out with the fixed self-owner skip,
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
    mailbox_drafts: list[dict],
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
    `composed_iso`, `mailbox_id`, `draft_id`, `verdict`, `signal`, `signal_at`,
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
    # Mailboxes DELIBERATELY not asked, address -> reason. Kept apart from
    # `unreadable` because they mean opposite things: unreadable is a failure
    # that must qualify every `ready` row, a skip is a mailbox that could not
    # have answered. Both are printed; neither is silent.
    skipped: dict[str, str] = {}
    # Whether the caller injected the reads. Injected seams keep the old
    # per-contact call shape (that is what every fixture speaks); the real path
    # takes the bulk read below.
    injected = inbound is not None or sent is not None
    inbound = inbound or _across_inbound(unreadable)
    sent = sent or _across_sent(unreadable)
    settled = settled or engine_view.settled
    delivered = delivered or (lambda settings, addr, body: gmail_archive.sent_body_match(settings, addr, body, authored=True))
    now = now or datetime.now(timezone.utc)

    rows = [mailbox_row(draft) for draft in mailbox_drafts]
    notes = []
    for row in rows:
        row["workset_hold_reasons"] = [reason for missing, reason in (
            (not row["body"], "body_unavailable"),
            (not row["thread_key"], "root_missing"),
            (not row["to"], "recipient_missing"),
            (row["composed_at"] is None, "date_missing"),
        ) if missing]

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
            for row in rows:
                if row["thread_key"]:
                    row["workset_hold_reasons"].append("verdict_unavailable")

    # Gmail is read once per contact, not once per draft: two drafts to the
    # same person are the common case (a reply and a follow-up), and the
    # answer to "did anything happen since" is a property of the CONTACT.
    # ONE read for the whole run, bucketed by address — not one per contact.
    #
    # The window is derived, not configured: every question here is strictly
    # "did anything happen AFTER this draft was composed", so the union over all
    # rows is `min(composed_at) - 3d`. It is deliberately UNCAPPED.
    # `MAX_LOOKBACK_DAYS` is legitimate as a POST-filter — the per-message Date
    # test recovers anything the window over-reads — and illegitimate here,
    # because a SINCE the server applies can never give back what it excluded:
    # a 200-day-old draft compared over 120 days turns a real `overtaken` into
    # `ready`.
    stamps = [r["composed_at"] for r in rows if r["composed_at"]]
    since = (min(stamps) - timedelta(days=3)) if stamps else None
    addrs = sorted({r["to"] for r in rows if r["to"]})

    inbound_cache: dict[str, list[dict]] = {}
    sent_cache: dict[str, list[dict]] = {}
    if addrs and not injected:
        try:
            sent_cache, inbound_cache = _bulk_across(unreadable, skipped, notes)(
                settings, addrs, since)
        except Exception as e:  # noqa: BLE001 — degradation is the contract
            # Nothing was read, so no absence was established: the whole
            # scope is unreadable for this run, and every `ready` row below
            # carries that gap on the row, not only in a note.
            unreadable.setdefault(
                "configured mailbox scope",
                f"the cross-mailbox read failed: {type(e).__name__}: {e}")
    # Keyed by (contact, body): two rows carrying the same text to the same
    # person ask the identical question, and that pair is precisely the
    # duplicate case, so it must cost ONE read and not two.
    delivered_cache: dict[tuple, dict | None] = {}
    delivered_gaps = set()
    inbound_gaps = set()
    sent_gaps = set()

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
        from .authored_mail import authored_plain
        body, body_note = authored_plain(row.get("body") or "")
        if body_note or row.get("body_note"):
            body = ""
            row["workset_hold_reasons"].append("body_unavailable")
        if len(body) >= MIN_DUPLICATE_BODY:
            cache_key = (addr, body)
            if cache_key not in delivered_cache:
                try:
                    hit, note = delivered(settings, addr, body)
                    delivered_cache[cache_key] = hit
                    if note:
                        notes.append(note)
                        delivered_gaps.add(cache_key)
                except Exception as e:  # noqa: BLE001 — degradation is the contract
                    delivered_cache[cache_key] = None
                    delivered_gaps.add(cache_key)
                    notes.append(f"could not compare {addr}'s Sent bodies: "
                                 f"{type(e).__name__}: {e}")
            if cache_key in delivered_gaps:
                row["workset_hold_reasons"].append("sent_body_unavailable")
            hit = delivered_cache[cache_key]
            if hit:
                row["verdict"] = "duplicate"
                row["signal"] = (f"this exact text was already delivered to "
                                 f"{addr}")
                row["signal_at"] = _iso(parse_mail_date(hit.get("date")))
                continue

        if injected and addr not in inbound_cache:
            try:
                inbound_cache[addr] = inbound(settings, addr, after=composed_at)
            except Exception as e:  # noqa: BLE001
                inbound_cache[addr] = []
                inbound_gaps.add(addr)
                notes.append(f"could not read All Mail for {addr}: "
                             f"{type(e).__name__}: {e}")
        # THE DATE TEST LIVES HERE NOW, and it is not optional.
        #
        # It used to live inside the per-contact read, which filtered on the
        # parsed Date before returning — which is why this consumer was a bare
        # `if later_in:`. The bulk read spans `min(composed_at) - 3d`, wider
        # than any single row's own date, so without this test every row would
        # see every other row's later mail and read `overtaken` unconditionally.
        later_in = _after(inbound_cache.get(addr), composed_at)
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

        if injected and addr not in sent_cache:
            try:
                sent_cache[addr] = sent(settings, addr, days=days)
            except Exception as e:  # noqa: BLE001
                sent_cache[addr] = []
                sent_gaps.add(addr)
                notes.append(f"could not read Sent for {addr}: "
                             f"{type(e).__name__}: {e}")
        later_out = [
            d for d in (
                parse_mail_date(m.get("date"))
                for m in (sent_cache.get(addr) or [])
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
        if gaps or row["to"] in inbound_gaps or row["to"] in sent_gaps:
            row["workset_hold_reasons"].append("mailbox_unreadable")
        row["workset_hold_reasons"] = sorted(set(row["workset_hold_reasons"]))
        row["evidence_incomplete"] = list(gaps) if (gaps and row["verdict"] == "ready") else []
    if skipped:
        # ON THE PAGE, not only in `Fanout.scope_line()` — reconcile never
        # calls that, so without this line a colleague's draft would flip from
        # `overtaken` to `ready` with nothing saying a mailbox was skipped.
        notes.append(
            "not every mailbox was asked about every contact — "
            + "; ".join(skipped.values())
            + ". A mailbox is never asked about its own owner: its outbox "
              "cannot say whether that person wrote TO US."
        )
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


def inventory_proof(mailbox_rows, reviewed) -> dict:
    result = {"version": 2, "complete": False, "mailbox_count": 0,
              "row_count": 0, "identity_sha256": None}
    if not isinstance(mailbox_rows, list) or not isinstance(reviewed, list):
        return result
    result.update(mailbox_count=len(mailbox_rows), row_count=len(reviewed))
    def identities(rows, key):
        pairs = []
        for row in rows:
            if not isinstance(row, dict):
                return None
            pair = row.get("mailbox_id"), row.get(key)
            if not all(isinstance(field, str) and field for field in pair):
                return None
            pairs.append(pair)
        return sorted(pairs) if len(set(pairs)) == len(pairs) else None
    ids = identities(mailbox_rows, "id")
    if ids is None or ids != identities(reviewed, "draft_id"):
        return result
    for row in reviewed:
        holds = row.get("workset_hold_reasons")
        if not isinstance(holds, list) or any(not isinstance(item, str) or item not in WORKSET_HOLD_REASONS for item in holds):
            return result
    result["identity_sha256"] = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
    result["complete"] = True
    return result
