#!/usr/bin/env python3
"""Batched read parity, explicit failure, and real CLI recovery without network."""
from __future__ import annotations

import contextlib
import copy
import email
import imaplib
import io
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from email import policy
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import cli, config, gmail_archive as ga, mailboxes, rpc, state

OWNER = "support@acme.example"
CONTACT = "contact@customer.example"
PASSWORD = "test-operator-password"
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)


def headers(n):
    out = []
    for i in range(n):
        raw = (f"Date: {format_datetime(NOW - timedelta(hours=i))}\r\n"
               f"From: Person {i} <{CONTACT}>\r\nTo: {OWNER}\r\n"
               f"Subject: =?utf-8?q?R=C3=A9ponse_{i}?=\r\n"
               f"Message-ID: <{i}@customer.example>\r\n\r\n").encode()
        out.append(raw)
    return out


class IMAP:
    def __init__(self, sent=(), inbound=(), *, search_no=None, fetch_no=None,
                 raised=None):
        self.rows = {"Sent": list(sent), "All": list(inbound)}
        self.search_no = search_no
        self.fetch_no = fetch_no
        self.raised = raised
        self.folder = None
        self.commands = []
        self.fetches = Counter()
        self.logged_out = False

    def list(self):
        return "OK", [b'(\\Sent) "/" "Sent"', b'(\\All) "/" "All"']

    def select(self, folder, readonly=True):
        assert readonly is True
        self.folder = folder.strip('"')
        self.commands.append(("SELECT", self.folder, readonly))
        return "OK", [str(len(self.rows[self.folder])).encode()]

    def noop(self):
        return "OK", [b""]

    def uid(self, command, *args):
        self.commands.append((command, self.folder, args))
        if command == "SEARCH":
            assert args[0] is None and args[1] in ("TO", "FROM")
            assert args[2] == CONTACT
            if self.raised:
                raise self.raised
            if self.folder == self.search_no:
                return "NO", [b""]
            return "OK", [b" ".join(str(i + 1).encode()
                                     for i in range(len(self.rows[self.folder])))]
        assert command == "FETCH", command
        assert args[1].startswith("(BODY.PEEK[HEADER.FIELDS "), args
        self.fetches[self.folder] += 1
        if (self.folder, self.fetches[self.folder]) == self.fetch_no:
            return "NO", [None]
        return "OK", [(b"1 (BODY[HEADER])", self.rows[self.folder][int(uid) - 1])
                      for uid in args[0].split(b",")]

    def logout(self):
        self.logged_out = True
        return "BYE", [b""]


def settings(path=None, password=PASSWORD):
    return config.Settings(_env_file=(), email_address=OWNER,
                           email_password=password, slug="acme", prog_name="cs",
                           db_path=path or ":memory:", engine_owner_uid="fixture-owner")


def expected(raws, direction=None):
    result = []
    for raw in raws:
        h = email.message_from_bytes(raw, policy=policy.default)
        if direction:
            result.append({"date": h.get("Date"), "from": h.get("From") or "",
                           "to": h.get("To") or "", "subject": h.get("Subject"),
                           "direction": direction})
        else:
            result.append({"date": h.get("Date"), "subject": h.get("Subject"),
                           "message_id": h.get("Message-ID")})
    return result


def typed(rows):
    return [{k: (type(v).__qualname__, v) for k, v in row.items()} for row in rows]


def test_batch_and_parity():
    raws = headers(450)
    M = IMAP(sent=raws)
    assert typed(ga.sent_to_on(M, CONTACT)) == typed(expected(raws))
    assert M.fetches == {"Sent": 3}, M.fetches
    M = IMAP(inbound=raws)
    want = [{k: v for k, v in row.items() if k != "message_id"}
            for row in expected(raws)]
    assert typed(ga.inbound_since_on(M, CONTACT)) == typed(want)
    assert M.fetches == {"All": 3}, M.fetches
    for sent, inbound in [(raws, []), ([], raws), (raws, raws), ([], [])]:
        M = IMAP(sent=sent, inbound=inbound)
        with patch.object(ga, "_imap", return_value=M):
            got = ga.correspondence(settings(), CONTACT)
        assert typed(got) == typed(expected(sent, "sent") + expected(inbound, "in"))
        assert M.fetches == {k: 3 for k, v in M.rows.items() if v}, M.fetches
        assert M.logged_out
    print("PASS: 450 UIDs: exactly 3 PEEK FETCHes per folder; exact ordered row/value/type parity")


def test_dates():
    cutoff = NOW - timedelta(days=7)
    dates = [format_datetime(cutoff - timedelta(seconds=1)), format_datetime(cutoff),
             format_datetime(cutoff + timedelta(seconds=1)),
             (cutoff + timedelta(seconds=2)).strftime("%a, %d %b %Y %H:%M:%S"),
             "invalid", None]
    raws = [(f"Date: {d}\r\n" if d else "").encode() +
            f"Subject: row {i}\r\nMessage-ID: <{i}@customer.example>\r\n\r\n".encode()
            for i, d in enumerate(dates)]
    with patch.object(ga, "datetime", FrozenDateTime):
        assert [r["subject"] for r in ga.sent_to_on(IMAP(sent=raws), CONTACT, 7)] == [
            "row 1", "row 2", "row 3"]
        assert len(ga.sent_to_on(IMAP(sent=raws), CONTACT)) == 6
        assert len(ga.sent_to_on(IMAP(sent=raws), CONTACT, 0)) == 6
    assert [r["subject"] for r in ga.inbound_since_on(IMAP(inbound=raws), CONTACT, cutoff)] == [
        "row 2", "row 3"]
    assert len(ga.inbound_since_on(IMAP(inbound=raws), CONTACT)) == 6
    print("PASS: frozen Date cutoff inclusive for sent, exclusive for inbound; naive/malformed/missing preserved")


def expect_raises(kind, call):
    try:
        call()
    except Exception as exc:
        assert type(exc) is kind, (kind, type(exc), exc)
        return exc
    raise AssertionError(f"did not raise {kind.__name__}")


def test_failures_and_logout():
    for reader in ["sent", "in", "correspondence-sent", "correspondence-in"]:
        folder = "Sent" if reader.endswith("sent") else "All"
        for failure in ["search", "fetch"]:
            M = IMAP(sent=headers(450), inbound=headers(450),
                     search_no=folder if failure == "search" else None,
                     fetch_no=(folder, 2) if failure == "fetch" else None)
            kind = ga.SearchFailed if failure == "search" else ga.ChunkFetchFailed
            with patch.object(ga, "_imap", return_value=M):
                call = ((lambda: ga.sent_to(settings(), CONTACT)) if reader == "sent" else
                        (lambda: ga.inbound_since(settings(), CONTACT)) if reader == "in" else
                        (lambda: ga.correspondence(settings(), CONTACT)))
                exc = expect_raises(kind, call)
            assert "not read" in str(exc)
            assert M.logged_out
            if failure == "fetch":
                assert M.fetches[folder] == 2
    for reader in [ga.sent_to, ga.inbound_since, ga.correspondence]:
        sentinel = imaplib.IMAP4.error("sentinel server refusal")
        M = IMAP(raised=sentinel)
        with patch.object(ga, "_imap", return_value=M):
            exc = expect_raises(imaplib.IMAP4.error, lambda: reader(settings(), CONTACT))
        assert exc is sentinel and M.logged_out
    print("PASS: SEARCH NO and second-chunk NO raise typed failures; wrappers propagate unchanged and log out")


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_fanout_and_cli_failure():
    for failure in ["search", "fetch"]:
        def session(*args):
            return IMAP(sent=headers(450), inbound=[],
                        search_no="Sent" if failure == "search" else None,
                        fetch_no=("Sent", 2) if failure == "fetch" else None)
        with patch.object(config, "load", return_value=settings()), patch.object(
                mailboxes, "session", side_effect=session):
            fan = mailboxes.sent_to_across(settings(), CONTACT)
            assert not fan.rows and not fan.complete
            assert fan.unreadable[0].address == OWNER
            assert ("SearchFailed" if failure == "search" else "ChunkFetchFailed") in fan.unreadable[0].reason
            for verb in ["history", "contacted"]:
                code, out, err = run_cli([verb, CONTACT])
                assert code == 3 and "UNKNOWN" in out and OWNER in out, (code, out, err)
                assert "Traceback" not in out + err and "cannot reach the engine" not in out + err
    print("PASS: actual fan-out yields named Unreadable; actual history/contacted handlers exit 3, no false absence")


def test_dossier_continues_honestly():
    with tempfile.TemporaryDirectory() as td:
        s = settings(str(Path(td) / "cs.db"), password="test operator password")
        st = state.State(s.db_path)
        st.mark_handled(CONTACT, reason="resolved by telephone", handled_at=NOW)
        st.conn.close()
        cases = [("search-sent", IMAP(sent=headers(450), search_no="Sent")),
                 ("search-in", IMAP(sent=headers(1), search_no="All")),
                 ("fetch-sent", IMAP(sent=headers(450), fetch_no=("Sent", 2))),
                 ("fetch-in", IMAP(sent=headers(1), inbound=headers(450), fetch_no=("All", 2))),
                 ("password", IMAP(raised=imaplib.IMAP4.error(
                     "refused test operator password / testoperatorpassword")))]
        for label, prototype in cases:
            for evidence in ["empty", "older", "recent"]:
                M = copy.deepcopy(prototype)
                raw = headers(1) if evidence == "recent" else headers(1500)[-1:] if evidence == "older" else []
                def session(*args):
                    return IMAP(sent=raw)
                calls = []
                def engine(s, method, params, timeout=60):
                    calls.append(method)
                    assert method == "tasks.list"
                    return [{"contact_email": CONTACT, "urgency": "normal", "title": "Follow up with customer"}]
                with patch.object(config, "load", return_value=s), patch.object(
                        ga, "_imap", return_value=M), patch.object(mailboxes, "session", side_effect=session), patch.object(
                        rpc, "call_sync", side_effect=engine), patch.object(
                        cli, "_print_crm_section", side_effect=lambda *a: print("CRM fixture section read")):
                    code, out, err = run_cli(["dossier", CONTACT])
                assert code == 0, (label, code, out, err)
                assert f"Gmail correspondence: UNKNOWN for {OWNER}" in out
                assert "Gmail correspondence (0)" not in out
                assert "UNKNOWN whether they have written since" in out
                assert "their last message predates" not in out and "they have written SINCE" not in out
                assert calls == ["tasks.list"] and "CRM fixture section read" in out
                assert "Follow up with customer" in out and "taken over by a human" in out
                assert "contacted in last" in out and "scope:" in out
                verdict = next(line for line in out.splitlines() if line.startswith("verdict:"))
                if evidence == "empty":
                    assert "STOP" in verdict and "UNKNOWN" in verdict and "cold contact" not in verdict
                else:
                    assert "STOP" in verdict or "REPLY IN THREAD" in verdict, verdict
                assert out.splitlines()[-1].startswith("evidence INCOMPLETE")
                assert OWNER in out.splitlines()[-1]
                assert "Traceback" not in out + err and "cannot reach the engine" not in out + err
                assert "test operator password" not in out + err and "testoperatorpassword" not in out + err
                assert M.logged_out
                print(f"PASS: dossier {label}/{evidence}: exit 0, UNKNOWN, sections continue, independent Sent evidence retained, final INCOMPLETE")


def main():
    test_batch_and_parity()
    test_dates()
    test_failures_and_logout()
    test_fanout_and_cli_failure()
    test_dossier_continues_honestly()
    print("test_bounded_header_readers: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
