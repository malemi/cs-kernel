#!/usr/bin/env python3
"""A closing courtesy is the engine's call, and the kernel only files the answer.

The owner's words, looking at a queue of twenty-two rows he was expected to read:
"l'ultimo messaggio suo è 'Va bene, la ringrazio tanto'. Da quando si risponde
ai ringraziamenti per un task completato?" The sweep could see that we had
already answered in that conversation; it could not see that nothing was left to
say, because that is a judgement about what a person MEANT and this repo is not
where meaning is decided.

So it asks — `emails.needs_reply`, engine `zylch/utils/reply_need.py`,
`cs/engine_view.settled` — and every case below is about what the kernel does
with the answer, or refuses to do without one. The direction that matters is
always the same: nothing here may make a row quieter than the engine made it,
and no absence of an engine may make a row quieter at all.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from cs.engine_view import SettledView, ThreadView
from cs.unanswered import (
    _partition,
    compute_automatic,
    compute_courtesy,
    compute_handled,
    compute_open,
    compute_resumed,
)

NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _dt(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


def _in(email, date, thread, subject="s", name="N"):
    return {"email": email, "name": name, "date": date, "subject": subject,
            "thread_key": thread}


def _out(to, date, thread):
    return {"to": list(to), "date": date, "thread_key": thread}


def _settled(thread, when, reason="closing_courtesy: pure thanks"):
    """The engine's verdict that the message sent at `when` owes nothing."""
    return {thread: SettledView(thread, int(when.timestamp()), reason)}


def _emails(rows):
    return [r["email"] for r in rows]


def _args(inbound, sent, settled=None, handled=None, views=None):
    return dict(inbound=inbound, sent=sent, self_addrs=set(), ignore=set(),
                now=NOW, handled=handled, escalated=None, views=views,
                settled=settled)


def a_settled_courtesy_leaves_the_queue_but_not_the_page() -> None:
    """"Va bene, la ringrazio tanto", four minutes after our answer."""
    thanks = _dt(0.1)
    inbound = [_in("cliente@example.com", _dt(1), "<T>", "Re: Support"),
               _in("cliente@example.com", thanks, "<T>", "Re: Support")]
    sent = [_out(["cliente@example.com"], _dt(0.2), "<T>")]
    settled = _settled("<T>", thanks)

    assert _emails(compute_open(**_args(inbound, sent, settled))) == []
    assert _emails(compute_resumed(**_args(inbound, sent, settled))) == []
    rows = compute_courtesy(**_args(inbound, sent, settled))
    assert _emails(rows) == ["cliente@example.com"]
    # The engine's own words ride on the row: a verdict the operator disagrees
    # with has to be visible AND traceable to where it can be fixed.
    assert "pure thanks" in rows[0]["reason"]
    assert rows[0]["state"] == "courtesy"
    print("OK: a courtesy the engine settled leaves the queue and keeps printing")


def with_no_engine_answer_the_row_reads_exactly_as_before() -> None:
    """Asleep engine, older build, unclassifiable thread — same reading as ever."""
    thanks = _dt(0.1)
    inbound = [_in("cliente@example.com", _dt(1), "<T>"),
               _in("cliente@example.com", thanks, "<T>")]
    sent = [_out(["cliente@example.com"], _dt(0.2), "<T>")]
    for settled in (None, {}):
        assert _emails(compute_courtesy(**_args(inbound, sent, settled))) == []
        assert _emails(compute_resumed(**_args(inbound, sent, settled))) == \
            ["cliente@example.com"]
    print("OK: no engine answer degrades to the pre-change reading, never to silence")


def a_verdict_cannot_promote_a_conversation_nobody_answered() -> None:
    """Two independent preconditions, and the kernel keeps its own.

    The engine has its own `answered_before`; this asserts the kernel does not
    lean on it. A conversation with no message of ours stays in the headline
    queue even if a verdict arrives saying nothing is owed.
    """
    msg = _dt(3)
    inbound = [_in("cliente@example.com", msg, "<T>")]
    settled = _settled("<T>", msg)
    assert _emails(compute_open(**_args(inbound, [], settled))) == ["cliente@example.com"]
    assert _emails(compute_courtesy(**_args(inbound, [], settled))) == []
    print("OK: a verdict cannot settle a conversation we never answered")


def a_stale_verdict_does_not_reach_the_newer_message() -> None:
    """The engine's archive can be BEHIND Gmail.

    It judged the thank-you that was newest when it synced; a real request has
    since arrived on the same conversation. A thread-level "settled" flag would
    silence that request — the timestamp join is what stops it.
    """
    thanks, question = _dt(2), _dt(1)
    inbound = [_in("cliente@example.com", thanks, "<T>"),
               _in("cliente@example.com", question, "<T>", "Re: e adesso?")]
    sent = [_out(["cliente@example.com"], _dt(3), "<T>")]
    settled = _settled("<T>", thanks)  # the OLD message
    assert _emails(compute_courtesy(**_args(inbound, sent, settled))) == []
    assert _emails(compute_resumed(**_args(inbound, sent, settled))) == \
        ["cliente@example.com"]
    print("OK: a verdict applies to its own message and to no later one")


def one_real_thread_outranks_five_courtesies() -> None:
    """The roll-up's safety property, restated for the new bucket."""
    thanks = _dt(0.5)
    inbound = [_in("cliente@example.com", _dt(30), "<OLD>", "Re: il preventivo"),
               _in("cliente@example.com", _dt(1), "<T>"),
               _in("cliente@example.com", thanks, "<T>")]
    sent = [_out(["cliente@example.com"], _dt(0.7), "<T>")]
    settled = _settled("<T>", thanks)
    rows = compute_open(**_args(inbound, sent, settled))
    assert _emails(rows) == ["cliente@example.com"]
    assert rows[0]["subject"] == "Re: il preventivo"
    assert _emails(compute_courtesy(**_args(inbound, sent, settled))) == []

    # And one rank down: a conversation we DID answer and they came back to
    # still outranks the same contact's thank-you on another thread.
    sent_both = sent + [_out(["cliente@example.com"], _dt(31), "<OLD>")]
    rows = compute_resumed(**_args(inbound, sent_both, settled))
    assert _emails(rows) == ["cliente@example.com"]
    assert rows[0]["subject"] == "Re: il preventivo"
    assert _emails(compute_courtesy(**_args(inbound, sent_both, settled))) == []
    print("OK: an unanswered conversation still outranks the same contact's thank-you")


def an_autoresponder_is_still_the_engines_other_answer() -> None:
    """Two engine judgements, and they do not collide.

    A machine-generated last message stays in `automatic` — the bucket named
    after the classification that produced it — rather than being re-labelled a
    courtesy because a second verdict also says nothing is owed.
    """
    robot = _dt(2)
    inbound = [_in("cliente@example.com", _dt(4), "<T>"),
               _in("cliente@example.com", robot, "<T>", "Casella disabilitata")]
    sent = [_out(["cliente@example.com"], _dt(3), "<T>")]
    views = {"<T>": ThreadView("<T>", {int(robot.timestamp())}, 2)}
    settled = _settled("<T>", robot)
    assert _emails(compute_automatic(**_args(inbound, sent, settled, views=views))) == \
        ["cliente@example.com"]
    assert _emails(compute_courtesy(**_args(inbound, sent, settled, views=views))) == []
    print("OK: an autoresponder stays the engine's 'automatic', not a courtesy")


def a_thank_you_does_not_re_open_a_contact_closed_by_phone() -> None:
    """The same bug in its other costume, and the one that cost a month.

    The operator phoned the customer and recorded it. She then wrote "Va bene,
    la ringrazio tanto" — and the record, which expires on any later message,
    expired on a thank-you. A record is a statement about the CONTACT, so only a
    message that actually asks for something may overturn it.
    """
    call = _dt(1)
    thanks = _dt(0.5)
    inbound = [_in("cliente@example.com", _dt(2), "<T>"),
               _in("cliente@example.com", thanks, "<T>")]
    sent = [_out(["cliente@example.com"], _dt(0.6), "<T>")]
    settled = _settled("<T>", thanks)
    handled = {"cliente@example.com": call}

    assert _emails(compute_open(**_args(inbound, sent, settled, handled))) == []
    assert _emails(compute_courtesy(**_args(inbound, sent, settled, handled))) == []
    held = compute_handled(**_args(inbound, sent, settled, handled))
    assert _emails(held) == ["cliente@example.com"]
    # Dated by the newest message that actually owed something — the one the
    # phone call was about — not by the thank-you that came after it.
    assert held[0]["last_inbound_date"] == _dt(2)
    print("OK: a thank-you leaves an out-of-band record standing")


def a_real_request_still_re_opens_a_closed_contact() -> None:
    """The other direction, which is the one that must never regress."""
    call = _dt(1)
    ask = _dt(0.5)
    inbound = [_in("cliente@example.com", _dt(2), "<T>"),
               _in("cliente@example.com", ask, "<T>", "Re: non funziona ancora")]
    sent = [_out(["cliente@example.com"], _dt(0.6), "<T>")]
    handled = {"cliente@example.com": call}
    for settled in (None, {}, _settled("<T>", _dt(9))):  # no verdict, or a stale one
        rows = compute_resumed(**_args(inbound, sent, settled, handled))
        assert _emails(rows) == ["cliente@example.com"], settled
        assert _emails(compute_handled(**_args(inbound, sent, settled, handled))) == []
    print("OK: a message that owes something still re-opens a handled contact")


def nothing_is_dropped() -> None:
    """Every sender with an open conversation lands in exactly one bucket."""
    thanks = _dt(0.5)
    inbound = [
        _in("nuovo@example.com", _dt(5), "<A>"),  # nobody answered
        _in("cortese@example.com", _dt(2), "<B>"),
        _in("cortese@example.com", thanks, "<B>"),  # courtesy
        _in("insiste@example.com", _dt(2), "<C>"),
        _in("insiste@example.com", _dt(1), "<C>", "Re: allora?"),  # resumed
    ]
    sent = [_out(["cortese@example.com"], _dt(1.5), "<B>"),
            _out(["insiste@example.com"], _dt(1.5), "<C>")]
    settled = _settled("<B>", thanks)
    buckets = _partition(**_args(inbound, sent, settled))
    seen = [r["email"] for b in buckets for r in b]
    assert sorted(seen) == ["cortese@example.com", "insiste@example.com",
                            "nuovo@example.com"], seen
    assert len(seen) == len(set(seen)), seen
    print("OK: three senders, three buckets, none merged and none dropped")


def _main() -> int:
    a_settled_courtesy_leaves_the_queue_but_not_the_page()
    with_no_engine_answer_the_row_reads_exactly_as_before()
    a_verdict_cannot_promote_a_conversation_nobody_answered()
    a_stale_verdict_does_not_reach_the_newer_message()
    one_real_thread_outranks_five_courtesies()
    an_autoresponder_is_still_the_engines_other_answer()
    a_thank_you_does_not_re_open_a_contact_closed_by_phone()
    a_real_request_still_re_opens_a_closed_contact()
    nothing_is_dropped()
    return 0


if __name__ == "__main__":
    sys.exit(_main())
