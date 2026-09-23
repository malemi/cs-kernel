#!/usr/bin/env python3
"""An HTML-escaped message id addresses the same conversation as a clean one.

The rows are the live support@ queue of 2026-09-22, reduced to plain dicts.
Four replies went out on 2026-09-18 carrying `In-Reply-To` / `References`
values whose angle brackets were escaped (`&lt;id@host&gt;`). A reader that
takes such a value literally files the reply under a conversation of its own:
the customer's thread is never settled, `cs unanswered` reports them open for
ever, and with `cs_triage_mode = send` an unattended tick answers them again.

Two of them showed a second face of the same fault. Their contact was reported
with a `last_inbound_date` eleven days older than their real last message,
because the escaped reply left an OLDER conversation of the same contact open
and that older conversation is what the sweep then reported.

The key normalises, so both faces close at once and no stored mail is rewritten.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cs.thread_key import normalize_key, thread_key, unescape_ids
from cs.unanswered import compute_open

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)

# Real ids off the incident, escaped exactly as they went out.
CLEAN = "<178506031954.3796104.15878029736436858473@mrcall.ai>"
ESCAPED = "&lt;178506031954.3796104.15878029736436858473@mrcall.ai&gt;"


def _dt(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


def _in(email, date, thread, subject="s", name="N"):
    return {"email": email, "name": name, "date": date, "subject": subject,
            "thread_key": thread}


def _out(to, date, thread):
    return {"to": list(to), "date": date, "thread_key": thread}


def _emails(rows):
    return [r["email"] for r in rows]


def an_escaped_id_is_the_same_key() -> None:
    """The unit: escaped in, clean key out, from every header position."""
    assert thread_key(ESCAPED) == CLEAN
    assert thread_key(None, ESCAPED) == CLEAN
    assert thread_key(None, None, ESCAPED) == CLEAN
    # References keeps its "first entry" rule with escaped ids too.
    assert thread_key(None, f"{ESCAPED} &lt;later@host&gt;") == CLEAN
    # Folding is still collapsed before the split.
    assert thread_key(None, f"\r\n {ESCAPED}\r\n <later@host>") == CLEAN
    assert normalize_key(ESCAPED) == CLEAN
    print("OK: an escaped id yields the conversation's real key")


def a_clean_id_is_untouched() -> None:
    """No escaped bracket, no substitution — including a literal `&`."""
    assert thread_key(CLEAN) == CLEAN
    literal_amp = "<a&b=c@host>"
    assert thread_key(literal_amp) == literal_amp
    # `&amp;` alone is NOT unescaped: without an escaped bracket there is no
    # evidence of the corruption, and an id that legitimately carries `&amp;`
    # must address the conversation it already addresses.
    amp_entity = "<a&amp;b@host>"
    assert thread_key(amp_entity) == amp_entity
    assert unescape_ids("") == ""
    assert thread_key(None, None, None) == ""
    print("OK: a clean id, and a literal ampersand, survive untouched")


def an_escaped_amp_inside_an_escaped_id_is_repaired() -> None:
    """One escaping pass in, one pass out — `&amp;` included, once a bracket
    proves the value went through `html.escape`."""
    assert thread_key("&lt;a&amp;b@host&gt;") == "<a&b@host>"
    # ...and only one pass. A doubly-escaped value carries no `&lt;` of its
    # own, so the guard never fires and the value is left exactly as it came:
    # nothing observed produces one, and guessing at a second pass is how an
    # ampersand a mailer really wrote gets eaten.
    assert thread_key("&amp;lt;a@host&amp;gt;") == "&amp;lt;a@host&amp;gt;"
    print("OK: one escaping pass is inverted, and only one")


def the_escaped_reply_settles_the_customers_thread() -> None:
    """The sweep: our reply, escaped on the wire, closes their conversation."""
    inbound = [_in("newlifeodontoiatrica@gmail.com", _dt(4), thread_key(CLEAN))]
    # The Sent row as Gmail holds it: the header is escaped, and the key is
    # computed from that header by the same function the sweep uses.
    sent = [_out(["newlifeodontoiatrica@gmail.com"], _dt(3.9),
                 thread_key(None, ESCAPED))]
    assert compute_open(inbound, sent, set(), set(), NOW) == [], \
        "an escaped reply must settle the conversation it answers"
    print("OK: a reply sent with escaped headers settles the thread it answers")


def the_older_conversation_stops_dating_the_contact() -> None:
    """The second face: an unsettled older thread was dating the contact.

    Their real last message is 1 day old; the escaped reply had left a thread
    from 12 days ago open, so the contact was reported with THAT date — the
    eleven-day staleness seen on the live queue.
    """
    old_key = thread_key("<old@mrcall.ai>")
    inbound = [
        _in("simona.restelli1965@gmail.com", _dt(12), old_key, "vecchio"),
        _in("simona.restelli1965@gmail.com", _dt(1), thread_key(CLEAN), "nuovo"),
    ]
    sent = [
        # Both answered; the older one's reply is the escaped row.
        _out(["simona.restelli1965@gmail.com"], _dt(11), thread_key(None, "&lt;old@mrcall.ai&gt;")),
        _out(["simona.restelli1965@gmail.com"], _dt(0.5), thread_key(None, ESCAPED)),
    ]
    assert compute_open(inbound, sent, set(), set(), NOW) == [], \
        "no conversation is open, so the contact must not be reported at all"

    # And when the newer one genuinely IS open, the row carries the NEW date,
    # not the stale one the unsettled old thread used to supply.
    still_open = compute_open(inbound, sent[:1], set(), set(), NOW)
    assert _emails(still_open) == ["simona.restelli1965@gmail.com"], still_open
    assert still_open[0]["days_waiting"] == 1, still_open[0]
    print("OK: a settled old thread no longer dates the contact")


def run() -> None:
    an_escaped_id_is_the_same_key()
    a_clean_id_is_untouched()
    an_escaped_amp_inside_an_escaped_id_is_repaired()
    the_escaped_reply_settles_the_customers_thread()
    the_older_conversation_stops_dating_the_contact()


if __name__ == "__main__":
    run()
