#!/usr/bin/env python3
"""A contact who is also one of our mailboxes is never asked about themselves.

The incident: a draft was addressed to a colleague whose mailbox is in the
fan-out scope. `inbound_since_on` then asked THAT colleague's own All Mail for
everything FROM them — their entire sent history, 21,637 messages on the clone
where this was found, against 49 for all other contacts in the same folder
combined. Two consequences, and the second is the worse one:

  * it issued one FETCH round trip per message, which is where a `cs review`
    that never returned in 25 minutes spent all of it;
  * every one of those messages satisfied "wrote again after this draft was
    composed", so the draft read `overtaken` because that colleague had mailed
    SOMEBODY. The question `overtaken` asks is whether they wrote TO US, and a
    person's own outbox cannot answer it.

So the read is skipped. What this file gates is that the skip is real, that it
is VISIBLE, and that it is not mistaken for a failure:

  1. the (contact, own-mailbox) read does not happen — asserted on the double,
     because a verdict-only assertion would pass an implementation that still
     paid the 21,637 round trips and then discarded them;
  2. the skip is reported as `skipped`, never `unreadable`. `unreadable` makes
     every campaign send gate refuse that colleague forever, over nothing;
  3. `scope_line()` names it, rather than printing "N of N read" over a scope
     that quietly narrowed;
  4. other mailboxes still answer about that same contact — the exclusion is
     one pair, not one address.
"""
import imaplib
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import mailboxes  # noqa: E402

OPERATOR = "ops@acme.example"
COLLEAGUE = "colleague@acme.example"
CUSTOMER = "buyer@customer.example"
NOW = datetime.now(timezone.utc)

#: Every SEARCH the doubles were asked, as (mailbox, key, addresses).
ASKED: list[tuple] = []


class _IMAP:
    def __init__(self, host, port):
        self.address = None
        self.folder = None

    def login(self, address, password):
        self.address = address
        return "OK", [b"ok"]

    def noop(self):
        return "OK", [b""]

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"',
                      b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"']

    def select(self, folder, readonly=True):
        self.folder = folder.strip('"')
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "SEARCH":
            rest = list(args[1:])
            if len(rest) >= 2 and rest[-2] == "SINCE":
                rest = rest[:-2]
            key = next((t for t in rest if t in ("TO", "FROM")), "?")
            addrs = [rest[i + 1] for i in range(len(rest) - 1)
                     if rest[i] in ("TO", "FROM")]
            ASKED.append((self.address, key, tuple(sorted(addrs))))
            # The colleague's own All Mail holds their whole sent history. If
            # anything ever asks for it, this is what it would drag back.
            if key == "FROM" and self.address == COLLEAGUE \
                    and COLLEAGUE in addrs:
                self._n = 21637
            else:
                self._n = 1
            return "OK", [b" ".join(str(i + 1).encode() for i in range(self._n))]
        if command == "FETCH":
            spec = args[0].decode()
            parts = []
            for token in spec.split(","):
                raw = (
                    f"Date: {format_datetime(NOW - timedelta(days=1))}\r\n"
                    f"From: {CUSTOMER}\r\n"
                    f"To: {self.address}\r\n"
                    f"Subject: s\r\n"
                    f"Message-ID: <{token}@acme.example>\r\n\r\n"
                ).encode()
                parts.append((b"1 (BODY[HEADER])", raw))
            return "OK", parts
        raise AssertionError(command)

    def logout(self):
        return "BYE", [b""]


def _settings():
    from cs.config import Settings
    s = Settings(_env_file=None)
    s.email_address = OPERATOR
    return s


def _boxes():
    return ([mailboxes.Mailbox("operator", OPERATOR, "pw"),
             mailboxes.Mailbox("declared", COLLEAGUE, "pw")], [])


def main():
    imaplib.IMAP4_SSL = _IMAP
    mailboxes.readable = lambda settings: _boxes()
    mailboxes.close_sessions()
    ASKED.clear()

    s = _settings()
    fan = mailboxes.headers_since_across(
        s, [CUSTOMER, COLLEAGUE], "FROM", since=NOW - timedelta(days=30))

    # (1) the colleague's own mailbox was never asked about the colleague.
    for who, key, addrs in ASKED:
        if who == COLLEAGUE and key == "FROM":
            assert COLLEAGUE not in addrs, (
                f"{COLLEAGUE}'s own mailbox was asked FROM {COLLEAGUE} — that "
                f"matches their entire sent history and marks the draft "
                f"`overtaken` because they mailed somebody. Asked: {addrs}")
    print("OK: a mailbox is never asked about its own owner")

    # (2) reported as a skip, never as a failure.
    assert not fan.unreadable, (
        "the skip was recorded as UNREADABLE — that makes every campaign send "
        f"gate refuse this colleague forever: {[u.describe() for u in fan.unreadable]}")
    assert fan.complete, "a deliberate skip must not mark the scope incomplete"
    assert any(COLLEAGUE in k.describe() for k in fan.skipped), (
        f"the skip is invisible: skipped={[k.describe() for k in fan.skipped]}")
    print("OK: reported as `skipped`, not `unreadable`, and the scope stays complete")

    # (3) visible in the printed scope.
    line = fan.scope_line()
    assert "own owner" in line and COLLEAGUE in line, line
    # The denominator counts DISTINCT mailboxes: this one is both read (for the
    # other contact) and skipped (for itself), and counting it twice would
    # print "2 of 3" over two mailboxes.
    assert "of 2 mailbox(es)" in line, (
        "the scope denominator double-counts a mailbox that was both read and "
        f"partially skipped: {line}")
    print(f"OK: scope_line names it — {line}")

    # (4) the other mailbox still answers about that same contact.
    asked_ops = [a for who, k, a in ASKED if who == OPERATOR and k == "FROM"]
    assert asked_ops and COLLEAGUE in asked_ops[0], (
        "the exclusion must be one (contact, mailbox) PAIR, not the address "
        f"everywhere: operator was asked {asked_ops}")
    print("OK: other mailboxes are still asked about that same contact")

    # (5) the Sent side too: a mailbox is not asked TO its own owner — its
    # Sent folder holds mail to self, which says nothing about mail to us.
    ASKED.clear()
    fan_to = mailboxes.headers_since_across(
        s, [CUSTOMER, COLLEAGUE], "TO", since=NOW - timedelta(days=30))
    for who, key, addrs in ASKED:
        if who == COLLEAGUE:
            assert COLLEAGUE not in addrs, (
                f"{COLLEAGUE}'s own Sent folder was asked TO {COLLEAGUE}: {addrs}")
    assert any(COLLEAGUE in k.describe() for k in fan_to.skipped), (
        f"the Sent-side skip is invisible: {[k.describe() for k in fan_to.skipped]}")
    print("OK: the Sent side (TO) applies the same exclusion and reports the skip")

    mailboxes.close_sessions()
    print("test_own_mailbox_exclusion: all assertions passed")


if __name__ == "__main__":
    main()
