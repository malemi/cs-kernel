#!/usr/bin/env python3
"""Three ways the draft review could state an absence it never established.

Found in review of the 2026-09-07 latency work, each proven to fail without
its fix:

  1. `sent_body_match` with no prior Sent mail to the address issued a FETCH
     with an EMPTY sequence-set. The server answers BAD, imaplib raises, and
     every never-contacted address printed "could not compare ... Sent bodies"
     on `cs review` — a degradation note over the most ordinary case there is.
  2. A message whose searched address appears only in `Bcc` was flagged
     `bcc_only` by the reader and then COUNTED by the bulk bucketing, so a
     draft could read `superseded` on evidence the reader itself had marked as
     unknown. The flag existed; nothing read it.
  3. When the whole cross-mailbox read failed, the run got a note but no
     mailbox entered `unreadable`, so every `ready` row carried
     `evidence_incomplete == []` — the one key whose absence a machine reader
     is promised to mean "complete".
"""
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import draft_state, gmail_archive, mailboxes  # noqa: E402

OPERATOR = "ops@acme.example"
CUSTOMER = "buyer@customer.example"
NOW = datetime.now(timezone.utc)


def _settings():
    from cs.config import Settings
    s = Settings(_env_file=None)
    s.email_address = OPERATOR
    s.email_password = "pw"
    return s


class _EmptySent:
    """A Sent folder with nothing to the address: SEARCH answers empty and a
    FETCH would be the defect itself."""

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

    def select(self, folder, readonly=True):
        return "OK", [b"0"]

    def uid(self, command, *args):
        if command == "SEARCH":
            return "OK", [b""]
        raise AssertionError(
            f"{command} {args!r} was issued after an empty SEARCH — an empty "
            "sequence-set is refused by the server and raised as a note on "
            "every never-contacted address")


class _BccOnly:
    """One message that names the customer only in Bcc."""

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

    def select(self, folder, readonly=True):
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "SEARCH":
            return "OK", [b"7"]
        if command == "FETCH":
            raw = (
                f"Date: {format_datetime(NOW - timedelta(days=1))}\r\n"
                f"From: {OPERATOR}\r\n"
                f"To: somebody@else.example\r\n"
                f"Bcc: {CUSTOMER}\r\n"
                f"Subject: s\r\n"
                f"Message-ID: <7@acme.example>\r\n\r\n"
            ).encode()
            return "OK", [(b"7 (BODY[HEADER])", raw)]
        raise AssertionError(command)


def test_no_prior_sent_mail_is_no_fetch():
    s = _settings()
    mailboxes.session = lambda settings, mb: _EmptySent()
    hit, note = gmail_archive.sent_body_match(s, "new@prospect.example",
                                              "Thank you for your request.")
    assert hit is None and note is None, (hit, note)
    print("OK: an address nothing was ever sent to is no match and no note — "
          "no FETCH is issued")


def test_bcc_only_match_is_reported_never_counted():
    # The reader flags it ...
    rows = gmail_archive.headers_for_addresses_on(
        _BccOnly(), [CUSTOMER], "TO", "\\sent", "[Gmail]/Sent Mail")
    assert len(rows) == 1 and rows[0].get("bcc_only") is True, rows
    print("OK: the reader flags a Bcc-only match as such")

    # ... and the bucketing reports it instead of counting it.
    flagged = mailboxes.Fanout(
        rows=[{**rows[0], "mailbox": OPERATOR}], read=[OPERATOR], unreadable=[])
    empty = mailboxes.Fanout(rows=[], read=[OPERATOR], unreadable=[])
    mailboxes.headers_since_across = (
        lambda settings, addrs, key, since=None: flagged if key == "TO" else empty)
    unreadable, skipped, notes = {}, {}, []
    sent, inbound = draft_state._bulk_across(unreadable, skipped, notes)(
        _settings(), [CUSTOMER], None)
    assert CUSTOMER not in sent, (
        f"a Bcc-only row was counted as a message sent to {CUSTOMER}: it mints "
        f"`superseded` on evidence the reader marked unknown: {sent}")
    assert inbound == {}, inbound
    assert len(notes) == 1 and "Bcc" in notes[0] and CUSTOMER in notes[0], notes
    assert not unreadable and not skipped
    print(f"OK: a Bcc-only match is a note, not a count — {notes[0]}")


def test_failed_bulk_read_marks_every_ready_row_incomplete():
    def _read(unreadable, skipped, notes):
        def read(settings, addrs, since):
            raise OSError("network down")
        return read
    draft_state._bulk_across = _read

    composed = NOW - timedelta(days=1)
    drafts = [{"uid": "9", "to": CUSTOMER, "subject": "re: your request",
               "date": format_datetime(composed), "body": "short",
               "thread_key": "", "message_id": "<m@acme.example>"}]
    rows, notes = draft_state.reconcile(
        _settings(), drafts, [],
        settled=lambda settings, keys: ({}, None),
        delivered=lambda settings, addr, body: (None, None),
        now=NOW)
    assert len(rows) == 1 and rows[0]["verdict"] == "ready", rows
    gaps = rows[0]["evidence_incomplete"]
    assert gaps and any("network down" in g for g in gaps), (
        "the whole cross-mailbox read failed and the `ready` row still says "
        f"its evidence is complete: evidence_incomplete={gaps!r}")
    assert any("INCOMPLETE scope" in n for n in notes), notes
    print("OK: a failed cross-mailbox read marks the `ready` row's evidence "
          "incomplete on the row itself")


def main():
    test_no_prior_sent_mail_is_no_fetch()
    test_bcc_only_match_is_reported_never_counted()
    test_failed_bulk_read_marks_every_ready_row_incomplete()
    print("test_review_evidence_gaps: all assertions passed")


if __name__ == "__main__":
    main()
