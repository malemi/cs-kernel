#!/usr/bin/env python3
"""The `unanswered` ignore list matches PATTERNS as well as literal addresses.

Why this gate exists: seven of one sweep's rows were the SAME bounce, from seven
different senders. An undeliverable customer address made the provider's mail
daemon answer from a rotating host — `mail-daemon@<host-NN>.<domain>`, a new
name every few days — so an exact-match ignore list was stale on the next
bounce and the operator was handed a robot to answer. `fnmatch` makes the rule
expressible (`mail-daemon@*`) and keeps it deterministic: no LLM decides who is
a person.

The gate guards THREE things, and the last one is the one that could hurt
somebody:

- a pattern drops every rotation of the same robot, in every bucket;
- a list with no wildcard behaves EXACTLY as it did before patterns existed —
  same set, no prefix effects, no accidental widening — and no pattern here can
  reach an address a human writes from;
- a wildcard SUPPRESSION blocks outreach and not merely the queue. Teaching
  operators to type wildcards while `cs/filter.py` still matched exactly would
  have made `cs suppress '*@<domain>'` fail OPEN: a quieter sweep, the same mail
  going out, and an operator who can see the protection working. Both lists read
  a typed entry through `cs/addr_match.py` for that reason.
"""
from __future__ import annotations

import os
import tempfile
import types
from datetime import datetime, timedelta, timezone

from cs import filter as filt
from cs.addr_match import AddrSet
from cs.state import State
from cs.unanswered import compute_escalated, compute_handled, compute_open

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def _dt(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


def _inbound(email: str, days_ago: float, subject: str = "x") -> dict:
    return {"email": email, "name": "", "date": _dt(days_ago), "subject": subject}


def _open(inbound, ignore, **kw) -> set[str]:
    return {
        r["email"]
        for r in compute_open(
            inbound, kw.pop("sent", []), self_addrs=kw.pop("self_addrs", set()),
            ignore=ignore, now=NOW, **kw
        )
    }


def _rotating_daemon_is_one_rule() -> None:
    """The measured case: one bounce, seven senders, one line of config."""
    inbound = [
        _inbound("mail-daemon@host-07.bounce.example", 34, "Recapito fallito"),
        _inbound("mail-daemon@host-03.bounce.example", 33, "Recapito fallito"),
        _inbound("mail-daemon@host-13.bounce.example", 29, "Recapito fallito"),
        _inbound("mailer-daemon@relay.other.example", 20, "Undelivered Mail"),
        _inbound("postmaster@mail.third.example", 15, "Delivery Status"),
        _inbound("customer@example.com", 10, "il mio assistente non risponde"),
    ]
    rows = _open(inbound, {"mail-daemon@*", "mailer-daemon@*", "postmaster@*"})
    assert rows == {"customer@example.com"}, rows

    # And the exact-match list can NOT express it: naming one host leaves the
    # other six. This is the regression the patterns exist to prevent.
    rows = _open(inbound, {"mail-daemon@host-07.bounce.example"})
    assert len(rows) == 5, rows


def _domain_patterns_do_not_leak() -> None:
    """`*@<host>` drops that host and nothing that merely resembles it."""
    inbound = [
        _inbound("notification@notify.example", 3),
        _inbound("alerts@notify.example", 2),
        # A DIFFERENT host that shares the prefix — a separate entry, or it stays.
        _inbound("notification@notify-test.example", 2),
        # A human whose domain merely ends the same way.
        _inbound("person@example.com", 1),
        # A human whose LOCAL PART is the robot's — never the same sender.
        _inbound("notification@customer.example", 1),
    ]
    rows = _open(inbound, {"*@notify.example"})
    assert rows == {
        "notification@notify-test.example",
        "person@example.com",
        "notification@customer.example",
    }, rows

    rows = _open(inbound, {"*@notify.example", "*@notify-test.example"})
    assert rows == {"person@example.com", "notification@customer.example"}, rows


def _patterns_cannot_reach_a_human() -> None:
    """A daemon rule must not fire on an address a person writes from."""
    humans = [
        _inbound("daemon.mail@example.com", 5),        # local part merely similar
        _inbound("postmaster.general@example.com", 4),  # not `postmaster@`
        _inbound("info@maildaemon-repairs.example", 3),  # brand contains the word
        _inbound("mail-daemon-support@example.com", 2),  # `-support` before the @
    ]
    rows = _open(humans, {"mail-daemon@*", "mailer-daemon@*", "postmaster@*"})
    assert rows == {r["email"] for r in humans}, rows


def _literals_behave_exactly_as_before() -> None:
    """The compatibility guarantee: no wildcard, no change."""
    inbound = [
        _inbound("noreply@sys.example", 6),
        # Same address plus a suffix: a literal must not act as a prefix rule.
        _inbound("noreply@sys.example.org", 5),
        _inbound("noreply2@sys.example", 4),
        _inbound("xnoreply@sys.example", 3),
        _inbound("customer@example.com", 2),
    ]
    ignore = {"noreply@sys.example", "transactional@sys.example"}
    got = _open(inbound, ignore)
    # Recomputed with the pre-pattern rule (`e in ignore`), not asserted by eye.
    expected = {
        m["email"] for m in inbound if m["email"] not in {a.lower() for a in ignore}
    }
    assert got == expected, (got, expected)

    # Case and surrounding whitespace normalise on both sides, as they always did.
    rows = _open(
        [_inbound("NoReply@SYS.example", 1)], {"  noreply@sys.example  ", "", "   "}
    )
    assert rows == set(), rows


def _wildcard_in_a_real_address_still_matches_itself() -> None:
    """`*` and `?` are legal in a local part. Such an entry becomes a pattern,
    and the pattern still drops its own sender — `*` spans the empty string and
    `?` spans the character it sits on — so nothing an operator already wrote
    can stop working."""
    for addr in ("odd*name@example.com", "odd?name@example.com"):
        rows = _open([_inbound(addr, 1)], {addr})
        assert rows == set(), (addr, rows)


def _ignored_before_every_bucket() -> None:
    """An ignored sender is not work in ANY view — a pattern hit must not
    reappear as `handled` or `escalated`, where the operator would read it as
    something a human is on."""
    inbound = [
        _inbound("mail-daemon@host-99.bounce.example", 4),
        _inbound("customer@example.com", 3),
    ]
    ignore = {"mail-daemon@*"}
    handled = {
        "mail-daemon@host-99.bounce.example": _dt(1),
        "customer@example.com": _dt(1),
    }
    escalated = {
        "mail-daemon@host-99.bounce.example": {
            "escalated_at": _dt(2), "owner": "someone", "reason": "r"
        }
    }
    held = compute_handled(
        inbound, [], set(), ignore, NOW, handled=handled, escalated=escalated
    )
    assert [r["email"] for r in held] == ["customer@example.com"], held
    mine = compute_escalated(inbound, [], set(), ignore, NOW, escalated=escalated)
    assert mine == [], mine


def _sent_anchoring_is_untouched() -> None:
    """Patterns filter WHO is considered; they must not change the open rule."""
    inbound = [_inbound("a@example.com", 5), _inbound("b@example.com", 5)]
    sent = [{"to": ["a@example.com"], "date": _dt(4)}]
    rows = _open(inbound, {"mail-daemon@*"}, sent=sent)
    assert rows == {"b@example.com"}, rows


def _wildcard_suppression_blocks_outreach() -> None:
    """One entry, both surfaces — the sweep AND the send gate.

    `cs suppress` means "never write to them". If the queue honours a wildcard
    and the producer worklist does not, the operator gets silence that looks
    like protection while the mail still goes out; that is strictly worse than
    a noisy queue, so it is asserted on the SEND side first.
    """
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "cs.db")
        st = State(db)
        st.suppress("*@blocked.example", reason="the whole domain asked us to stop")
        st.suppress("one@literal.example", reason="a single address, as before")

        settings = types.SimpleNamespace(
            self_email_set=set(), self_uid_set=set(), dedup_days=30
        )
        payload = {
            "leads": [],
            "cancellations": [],
            "signups": [
                # Case differs from the suppression entry on purpose.
                {"business_id": "b1", "email_address": "Owner@Blocked.example"},
                {"business_id": "b2", "email_address": "one@literal.example"},
                {"business_id": "b3", "email_address": "someone@allowed.example"},
            ],
        }
        wl = filt.build_worklist(payload, settings, st)
        assert [b["business_id"] for b in wl["to_contact"]["signup"]] == ["b3"], wl
        for key in ("b1", "b2"):
            assert {"category": "signup", "key": key, "reason": "suppressed"} \
                in wl["skipped"], (key, wl["skipped"])

        # The same two entries, read by the sweep: one list, one meaning.
        rows = _open(
            [
                _inbound("owner@blocked.example", 3),
                _inbound("one@literal.example", 2),
                _inbound("someone@allowed.example", 1),
            ],
            st.do_not_contact_set(),
        )
        assert rows == {"someone@allowed.example"}, rows


def _addrset_is_idempotent_and_splits() -> None:
    """`_partition` re-wraps whatever it is handed, so wrapping twice must not
    lose the patterns — and a blank entry must never become a rule."""
    a = AddrSet({"Mail-Daemon@*", " literal@example.com ", "", "  "})
    assert a.patterns == frozenset({"mail-daemon@*"}), a.patterns
    assert a.literals == frozenset({"literal@example.com"}), a.literals
    assert len(a) == 2, len(a)
    b = AddrSet(a)
    assert (b.literals, b.patterns) == (a.literals, a.patterns)
    assert "mail-daemon@host-01.example" in b and "someone@example.com" not in b
    # A non-string probe is not a member and must not raise.
    assert None not in a and 7 not in a


def run() -> None:
    _rotating_daemon_is_one_rule()
    _domain_patterns_do_not_leak()
    _patterns_cannot_reach_a_human()
    _literals_behave_exactly_as_before()
    _wildcard_in_a_real_address_still_matches_itself()
    _ignored_before_every_bucket()
    _sent_anchoring_is_untouched()
    _wildcard_suppression_blocks_outreach()
    _addrset_is_idempotent_and_splits()
    print(
        "OK: ignore + suppression — rotating daemons caught by pattern, literals "
        "unchanged, no pattern reaches a human, every bucket filtered, and a "
        "wildcard suppression blocks OUTREACH and not just the queue"
    )


if __name__ == "__main__":
    run()
