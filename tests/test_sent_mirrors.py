#!/usr/bin/env python3
"""Sending a draft retires its Gmail mirror — the other half of the send.

A contextual reply is composed by the engine, mirrored into Gmail Drafts so a
human can read it where they read everything else, and then SENT from the
engine's own copy. Nothing retracted the mirror, so every reply left one
behind: 78 drafts on the live queue on 2026-09-22, the oldest from 19 June,
seven of them mirrors of mail sent minutes earlier. A review queue that is
mostly answered mail no longer says what needs a decision.

Asserted here, on plain dicts — no IMAP, no engine:

  1. the mirror of a sent draft is an orphan, paired on recipient + thread;
  2. a compose (no thread key on either side) pairs on recipient + subject;
  3. a draft composed AFTER the send is a new draft and is left alone, with
     the reason said out loud rather than silently skipped;
  4. another recipient's draft on the same thread is never touched;
  5. without comparable timestamps nothing is retired — "probably sent" is not
     a reason to delete somebody's draft;
  6. an engine copy whose `thread_id` is HTML-escaped still pairs, because the
     key normalises (see test_thread_key_escaped.py).
"""
from __future__ import annotations

from cs.draft_state import sent_orphans

SENT_AT = "2026-09-22T10:00:00"
BEFORE = "Tue, 22 Sep 2026 09:00:00 +0000"
AFTER = "Tue, 22 Sep 2026 11:00:00 +0000"


def _sent(engine_id="E1", to="cliente@example.test", subject="Re: assistenza",
          thread="<T1@mrcall.ai>", sent_at=SENT_AT):
    return {"id": engine_id, "to_addresses": [to], "subject": subject,
            "thread_id": thread, "sent_at": sent_at}


def _mirror(uid="10", to="Cliente <cliente@example.test>",
            subject="Re: assistenza", date=BEFORE, thread="<T1@mrcall.ai>"):
    return {"uid": uid, "to": to, "subject": subject, "date": date,
            "thread_key": thread}


def _by_uid(rows):
    return {r["gmail_uid"]: r for r in rows}


def the_mirror_of_a_sent_draft_is_an_orphan() -> None:
    rows = _by_uid(sent_orphans([_sent()], [_mirror()]))
    assert set(rows) == {"10"}, rows
    assert rows["10"]["retire"] is True, rows["10"]
    assert rows["10"]["engine_id"] == "E1", rows["10"]
    print("OK: a sent draft's mirror is reported for retirement")


def a_compose_pairs_on_subject() -> None:
    """Neither side is a reply, so the subject is the strongest thing left."""
    rows = _by_uid(sent_orphans(
        [_sent(thread="")], [_mirror(thread="")]
    ))
    assert rows["10"]["retire"] is True, rows
    # ...and a different subject is a different mail.
    assert sent_orphans([_sent(thread="")],
                        [_mirror(thread="", subject="altro")]) == []
    print("OK: a compose pairs on recipient and subject")


def a_newer_draft_is_left_alone() -> None:
    rows = _by_uid(sent_orphans([_sent()], [_mirror(date=AFTER)]))
    assert rows["10"]["retire"] is False, rows["10"]
    assert "AFTER the send" in rows["10"]["reason"], rows["10"]
    print("OK: a draft composed after the send survives, and says why")


def another_recipient_is_never_touched() -> None:
    assert sent_orphans([_sent()], [_mirror(to="altro@example.test")]) == [], \
        "a draft to somebody else is not a mirror of this send"
    print("OK: only the recipient of the send is matched")


def unknown_times_retire_nothing() -> None:
    no_date = _by_uid(sent_orphans([_sent()], [_mirror(date=None)]))
    assert no_date["10"]["retire"] is False, no_date["10"]
    assert "no comparable timestamps" in no_date["10"]["reason"], no_date["10"]
    no_send = _by_uid(sent_orphans([{"id": "E1",
                                     "to_addresses": ["cliente@example.test"],
                                     "subject": "Re: assistenza",
                                     "thread_id": "<T1@mrcall.ai>"}],
                                   [_mirror()]))
    assert no_send["10"]["retire"] is False, no_send["10"]
    print("OK: without both timestamps nothing is retired")


def an_escaped_engine_thread_still_pairs() -> None:
    """The engine stored the id the send path gave it — escaped brackets and
    all. The mirror is still the mirror of that mail."""
    rows = _by_uid(sent_orphans(
        [_sent(thread="&lt;T1@mrcall.ai&gt;")], [_mirror()]
    ))
    assert rows["10"]["retire"] is True, rows["10"]
    print("OK: an escaped engine thread id still pairs with its mirror")


def run() -> None:
    the_mirror_of_a_sent_draft_is_an_orphan()
    a_compose_pairs_on_subject()
    a_newer_draft_is_left_alone()
    another_recipient_is_never_touched()
    unknown_times_retire_nothing()
    an_escaped_engine_thread_still_pairs()


if __name__ == "__main__":
    run()
