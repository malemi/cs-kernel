"""What the ENGINE already knows about a conversation — the kernel's one door to it.

The engine syncs the mail, classifies every message, keeps entity memory and a
task ledger. Auto-reply classification is one of those judgements: it is the
engine's, it has been the engine's since the auto-ack incidents of 2026-06/07,
and the kernel must ASK for it rather than re-derive it from headers. The
charter rule (`CLAUDE.md`, "the engine is authoritative for what it owns") is
what this module exists to obey; when the classification is wrong, the fix is a
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
