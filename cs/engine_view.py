"""What the ENGINE already knows about a conversation — the kernel's one door to it.

The engine syncs the mail, classifies every message, keeps entity memory and a
task ledger. Two of those judgements are asked for here and neither is
re-derived: whether a message is an autoresponder, and whether a message still
needs a reply from us. Both are the engine's, both have an owner there
(`zylch/utils/auto_reply_detector.py` and `zylch/utils/reply_need.py`), and the
charter rule (`CLAUDE.md`, "the engine is authoritative for what it owns") is
what this module exists to obey; when a classification is wrong, the fix is a
change in the engine, never a second opinion here.

What this module deliberately does NOT take from the engine is the EXISTENCE of
a message. Dedup truth stays Gmail's own Sent folder, because the engine
archive was measured over-reporting sends — it asserts a 2026-07-28 send that
Gmail Sent does not contain. So the split is:

    does this message exist?      -> Gmail (cs/gmail_archive.py)
    what KIND of message is it?   -> the engine (here)

A message the engine has never seen is simply unclassified; it keeps whatever
the caller's default is. That is the safe direction for this sweep: unclassified
outbound counts as a real answer only in the sense the sweep always assumed, and
unclassified inbound is never quietly labelled noise.

Degradation is a first-class result, never an exception: a sweep whose engine is
asleep must still list the queue and must SAY that the classification is
missing. `classify` returns `(views, note)` and never raises.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _parse(raw) -> datetime | None:
    """Engine ISO timestamp -> tz-aware UTC datetime, or None.

    The engine stores UTC and serialises it without an offset, so a naive value
    is read as UTC. This is the same convention as `cs/_time.py`; getting it
    wrong would shift every comparison by the local offset.
    """
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class ThreadView:
    """The engine's reading of one conversation, reduced to what the sweep needs.

    `auto_at` is the set of whole-second UTC timestamps of the messages the
    engine classified as automatic — both directions, because both matter: an
    inbound autoresponder is not a customer waiting, and an OUTBOUND one of ours
    is not an answer. The join back to a Gmail message is by timestamp because
    the engine's per-message ids are its own UUIDs and it does not return the
    `Message-ID` header; a whole second is precise enough (a mailbox does not
    hold two messages of the same conversation in the same second and only one
    of them automatic) and it needs no engine change to work today.
    """

    __slots__ = ("thread_id", "auto_at", "count")

    def __init__(self, thread_id: str, auto_at: set[int], count: int) -> None:
        self.thread_id = thread_id
        self.auto_at = auto_at
        self.count = count

    def is_auto(self, when: datetime | None) -> bool:
        """True when the engine classified the message sent at `when` as automatic."""
        if when is None:
            return False
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return int(when.astimezone(timezone.utc).timestamp()) in self.auto_at


def classify(settings, thread_ids, timeout: int = 60) -> tuple[dict[str, ThreadView], str | None]:
    """Ask the engine to classify each conversation. `(views, degradation note)`.

    One `emails.list_by_thread` per thread. That is a local SQLite read behind a
    unix socket, not an LLM call — the sweep stays deterministic, which is the
    property the whole module was built for (a non-deterministic discovery loop
    is the incident `cs/unanswered.py` opens with).

    A thread the engine cannot answer for is ABSENT from the returned mapping
    rather than present-and-empty, so a caller can tell "the engine says nothing
    here is automatic" from "the engine could not be asked". The note names the
    first failure and how many threads it cost, once — a line per thread would
    bury the queue it is supposed to annotate.
    """
    from . import rpc

    views: dict[str, ThreadView] = {}
    note: str | None = None
    failures = 0
    for tid in thread_ids:
        if not tid or tid in views:
            continue
        try:
            res = rpc.call_sync(settings, "emails.list_by_thread", {"thread_id": tid},
                                timeout=timeout)
        except Exception as e:  # noqa: BLE001 — degradation is the contract
            failures += 1
            if note is None:
                note = f"{type(e).__name__}: {e}"
            continue
        msgs = (res or {}).get("emails") or []
        auto_at: set[int] = set()
        for m in msgs:
            if not m.get("is_auto_reply"):
                continue
            when = _parse(m.get("date"))
            if when is not None:
                auto_at.add(int(when.timestamp()))
        views[tid] = ThreadView(tid, auto_at, len(msgs))
    if failures and note:
        note = f"{note} ({failures} thread(s) unclassified)"
    return views, note


class SettledView:
    """The engine's answer that ONE message on this conversation owes nothing.

    Only the settled case is carried. "Needs a reply" is the default everywhere
    in this kernel, so a thread the engine did not settle — because it says a
    reply is owed, because it has never synced the conversation, because the
    method does not exist on that build, because the engine is asleep — needs no
    representation at all: its absence already means the safe thing.

    `at` is the whole-second UTC timestamp of the message the verdict is about,
    and `needs_reply` refuses to apply the verdict to any other one. The engine's
    archive can be BEHIND Gmail: it may have judged the courtesy that was the
    newest message at sync time while a real request has since arrived, and
    carrying a thread-level "settled" flag would silence that request. Matching
    the timestamp costs nothing and makes the stale case fall back to "needs a
    reply" by itself.
    """

    __slots__ = ("thread_id", "at", "reason")

    def __init__(self, thread_id: str, at: int, reason: str = "") -> None:
        self.thread_id = thread_id
        self.at = at
        self.reason = reason

    def needs_reply(self, when: datetime | None) -> bool:
        """False only for the exact message the engine settled; True otherwise."""
        if when is None:
            return True
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return int(when.astimezone(timezone.utc).timestamp()) != self.at


def settled(settings, thread_ids, timeout: int = 120) -> tuple[dict[str, SettledView], str | None]:
    """Ask the engine which conversations owe nothing. `(views, degradation note)`.

    ONE `emails.needs_reply` call for the whole sweep, not one per thread: the
    engine screens the structural cases itself for free and adjudicates only the
    residue, in a single batch, so asking about forty conversations costs one
    round trip and at most one model call. Splitting it per thread would put a
    model call inside a loop.

    Every failure returns an EMPTY mapping and a note, which is not a detail:
    empty means every conversation needs a reply, which is exactly how this sweep
    read the queue before the engine could be asked. An engine that predates the
    method answers "Method not found" and lands here too, so a clone pinned to a
    new kernel against an old engine degrades to the old output rather than
    breaking — and SAYS it degraded, because a silently shorter queue is the one
    failure nobody would report.
    """
    from . import rpc

    ids = [t for t in (thread_ids or []) if t]
    if not ids:
        return {}, None
    try:
        res = rpc.call_sync(settings, "emails.needs_reply", {"thread_ids": ids},
                            timeout=timeout)
    except Exception as e:  # noqa: BLE001 — degradation is the contract
        return {}, f"{type(e).__name__}: {e}"
    out: dict[str, SettledView] = {}
    for tid, row in ((res or {}).get("threads") or {}).items():
        if not isinstance(row, dict) or row.get("needs_reply") is not False:
            continue
        when = _parse(row.get("date"))
        if when is None:
            # A verdict we cannot pin to a message is a verdict we cannot use.
            continue
        out[str(tid)] = SettledView(str(tid), int(when.timestamp()),
                                    str(row.get("reason") or ""))
    return out, (res or {}).get("note") or None
