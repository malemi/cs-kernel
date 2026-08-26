#!/usr/bin/env python3
"""The sweep reads CONVERSATIONS, and asks the engine what kind of message it is.

Every case here is a real row off the live support queue on 2026-08-26, reduced
to plain dicts. They are the four ways the address-keyed sweep was wrong:

  1. answered in the thread, to somebody else  — a colleague only in Cc sat on
     the queue 28 days while the thread's principal had been answered;
  2. answered on a DIFFERENT thread             — a later helpful reply closed an
     older, untouched conversation that nobody had ever answered;
  3. our own autoresponder counted as an answer — 17 seconds after four product
     questions, hiding them for 70 days;
  4. a closing courtesy read as open work       — "Va bene, la ringrazio tanto"
     raised as something needing an answer.

(1) and (2) are the thread key. (3) is the engine's `is_auto_reply` on OUR
message. (4) is not intent-detection at all — it is "a human of ours already
answered in this conversation", which the sweep can see without reading a word.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cs.engine_view import ThreadView
from cs.unanswered import (
    compute_automatic,
    compute_handled,
    compute_open,
    compute_resumed,
)

NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _dt(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


def _view(*auto_dates: datetime) -> ThreadView:
    """The engine's reading of a thread: these messages are machine-generated."""
    return ThreadView("t", {int(d.timestamp()) for d in auto_dates}, 0)


def _in(email, date, thread, subject="s", name="N"):
    return {"email": email, "name": name, "date": date, "subject": subject,
            "thread_key": thread}


def _out(to, date, thread):
    return {"to": list(to), "date": date, "thread_key": thread}


def _emails(rows):
    return [r["email"] for r in rows]


def answered_in_thread_to_someone_else() -> None:
    """A reply to the thread's principal answers the colleague who was in Cc."""
    inbound = [_in("cc@example.com", _dt(28), "<T1>", "R: numero")]
    # Our answer went to the principal only — the Cc address is nowhere in `to`.
    sent = [_out(["principal@example.com"], _dt(27), "<T1>")]

    assert compute_open(inbound, sent, set(), set(), NOW) == [], \
        "an answer in the thread must close a participant it was not addressed to"
    # Without the thread key it is the old behaviour, and the row stays open —
    # pinned so a regression that drops the key is loud instead of silent.
    bare = [{k: v for k, v in inbound[0].items() if k != "thread_key"}]
    bare_sent = [{k: v for k, v in sent[0].items() if k != "thread_key"}]
    assert _emails(compute_open(bare, bare_sent, set(), set(), NOW)) == ["cc@example.com"]
    print("OK: answered in the thread closes the participant who was only Cc'd")


def a_later_thread_does_not_close_an_older_one() -> None:
    """Helping somebody today does not answer what they asked in June."""
    inbound = [
        _in("cust@example.com", _dt(72), "<JUNE>", "quattro domande"),
        _in("cust@example.com", _dt(22), "<AUG>", "assistente KO"),
    ]
    sent = [_out(["cust@example.com"], _dt(22), "<AUG>")]

    rows = compute_open(inbound, sent, set(), set(), NOW)
    assert _emails(rows) == ["cust@example.com"], rows
    assert rows[0]["days_waiting"] == 72, rows[0]
    assert rows[0]["thread_key"] == "<JUNE>", rows[0]
    print("OK: an answer on a new thread leaves the old conversation open, at its own age")


def our_autoresponder_is_not_an_answer() -> None:
    """The engine says that Sent message is automatic, so it does not close."""
    asked = _dt(72)
    acked = asked + timedelta(seconds=17)
    inbound = [_in("cust@example.com", asked, "<JUNE>", "quattro domande")]
    sent = [_out(["cust@example.com"], acked, "<JUNE>")]

    # Engine silent (or unreachable): the acknowledgement counts, exactly as it
    # did before this module could ask. Degradation must be the OLD behaviour.
    assert compute_open(inbound, sent, set(), set(), NOW) == [], \
        "with no engine view the sweep must behave exactly as it did before"

    rows = compute_open(inbound, sent, set(), set(), NOW,
                        views={"<JUNE>": _view(acked)})
    assert _emails(rows) == ["cust@example.com"], rows
    assert rows[0]["days_waiting"] == 72 and rows[0]["state"] == "open", rows[0]
    # Nobody human ever wrote here, so it is the HEADLINE queue, not `resumed`.
    assert compute_resumed(inbound, sent, set(), set(), NOW,
                           views={"<JUNE>": _view(acked)}) == []
    print("OK: our own auto-acknowledgement does not close a conversation")


def a_closing_courtesy_is_not_the_queue() -> None:
    """Their message, our real answer, their thank-you — answered, they replied."""
    inbound = [
        _in("cust@example.com", _dt(2), "<T>", "Support"),
        _in("cust@example.com", _dt(0.1), "<T>", "Re: Support"),
    ]
    sent = [_out(["cust@example.com"], _dt(0.2), "<T>")]

    assert compute_open(inbound, sent, set(), set(), NOW) == [], \
        "a thank-you after our answer must not head the queue"
    resumed = compute_resumed(inbound, sent, set(), set(), NOW)
    assert _emails(resumed) == ["cust@example.com"], resumed
    assert resumed[0]["state"] == "resumed", resumed[0]
    # Re-labelled, never deleted: the row is still reachable with its age.
    assert resumed[0]["days_waiting"] == 0, resumed[0]
    print("OK: a closing courtesy is re-labelled, not raised and not dropped")


def their_autoresponder_is_the_engines_call() -> None:
    """`automatic` is what the ENGINE flagged, not an address rule."""
    ooo = _dt(29)
    inbound = [_in("lawyer@example.com", ooo, "<T>", "Chiusura feriale")]
    sent = [_out(["lawyer@example.com"], ooo - timedelta(hours=1), "<T>")]

    assert compute_open(inbound, sent, set(), set(), NOW,
                        views={"<T>": _view(ooo)}) == []
    auto = compute_automatic(inbound, sent, set(), set(), NOW,
                             views={"<T>": _view(ooo)})
    assert _emails(auto) == ["lawyer@example.com"], auto
    # No engine view -> not automatic. The kernel never guesses this by itself.
    assert compute_automatic(inbound, sent, set(), set(), NOW) == []
    assert _emails(compute_resumed(inbound, sent, set(), set(), NOW)) == \
        ["lawyer@example.com"], "unclassified, it is merely a reply after ours"
    print("OK: 'automatic' is the engine's classification, and only the engine's")


def a_vacation_notice_never_buries_a_real_request() -> None:
    """TAG, never drop: an auto reply on one thread cannot hide another thread."""
    ooo = _dt(3)
    inbound = [
        _in("cust@example.com", ooo, "<VACATION>", "Out of office"),
        _in("cust@example.com", _dt(9), "<REAL>", "non funziona niente"),
    ]
    rows = compute_open(inbound, [], set(), set(), NOW,
                        views={"<VACATION>": _view(ooo)})
    assert _emails(rows) == ["cust@example.com"], rows
    assert rows[0]["thread_key"] == "<REAL>" and rows[0]["days_waiting"] == 9, rows[0]
    # ...and the address is reported ONCE, in the strongest bucket it earns.
    assert compute_automatic(inbound, [], set(), set(), NOW,
                             views={"<VACATION>": _view(ooo)}) == []
    print("OK: an autoresponder on one thread cannot bury a real request on another")


def the_operators_own_records_still_win() -> None:
    """`handled` outranks every derived bucket — a human record beats a heuristic."""
    last = _dt(1)
    inbound = [_in("cust@example.com", last, "<T>", "grazie")]
    sent = [_out(["cust@example.com"], _dt(2), "<T>")]
    handled = {"cust@example.com": _dt(0.5)}

    # Without the record it is `resumed`; with it, it is HELD, and says why.
    assert _emails(compute_resumed(inbound, sent, set(), set(), NOW)) == \
        ["cust@example.com"]
    held = compute_handled(inbound, sent, set(), set(), NOW, handled)
    assert _emails(held) == ["cust@example.com"], held
    assert compute_resumed(inbound, sent, set(), set(), NOW, handled) == []
    assert compute_open(inbound, sent, set(), set(), NOW, handled) == []
    print("OK: an out-of-band record still outranks every derived bucket")


def a_ledger_record_is_dated_by_the_newest_message_anywhere() -> None:
    """A record written last night cannot hold back somebody who wrote today.

    Caught on the live queue, not reasoned about: the first version of the
    conversation split dated the `handled` test by the OLDEST open thread, so a
    customer who had been phoned yesterday and mailed again at 09:10 this
    morning vanished into "handled out of band". `handled` means "resolved, and
    a later message re-opens them" — and the later message may land on any
    thread, so the test is against the contact's newest message anywhere.
    """
    inbound = [
        _in("cust@example.com", _dt(9), "<OLD>", "vecchia domanda"),
        _in("cust@example.com", _dt(0.1), "<NEW>", "sono di nuovo io"),
    ]
    phoned = {"cust@example.com": _dt(0.5)}   # the call: after OLD, before NEW

    rows = compute_open(inbound, [], set(), set(), NOW, phoned)
    assert _emails(rows) == ["cust@example.com"], \
        "a message after the call must re-open the contact, on whatever thread"
    assert compute_handled(inbound, [], set(), set(), NOW, phoned) == []

    # ...and when nothing arrived after the call, the record still holds, dated
    # by the newest message rather than by the thread the split happened to pick.
    only_old = [inbound[0]]
    held = compute_handled(only_old, [], set(), set(), NOW, phoned)
    assert _emails(held) == ["cust@example.com"], held
    assert held[0]["days_waiting"] == 9, held[0]
    print("OK: an out-of-band record is dated by the contact's newest message, anywhere")


def run() -> None:
    answered_in_thread_to_someone_else()
    a_later_thread_does_not_close_an_older_one()
    our_autoresponder_is_not_an_answer()
    a_closing_courtesy_is_not_the_queue()
    their_autoresponder_is_the_engines_call()
    a_vacation_notice_never_buries_a_real_request()
    the_operators_own_records_still_win()
    a_ledger_record_is_dated_by_the_newest_message_anywhere()


if __name__ == "__main__":
    run()
