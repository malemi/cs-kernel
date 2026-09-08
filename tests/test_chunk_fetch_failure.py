#!/usr/bin/env python3
"""A failed batched header FETCH is reported, never silently dropped.

`_fetch_headers` fetches up to 200 UIDs per round trip. It used to answer a
non-OK FETCH with `continue`, which discarded that whole chunk and returned a
SHORT LIST indistinguishable from a complete one. Every caller asks a question
where a short list reads as "nothing found" — has this contact written to us,
who is still waiting — so a transient error became an absence nobody
established. That is the failure `cs/mailboxes.py` exists to prevent.

Three properties, and the third is the one that makes the other two worth
having:

  1. `_fetch_headers` RAISES `ChunkFetchFailed` on a non-OK FETCH instead of
     returning a short list.
  2. `cs review`'s freshness probe still degrades to a note and still returns
     a usable answer — it already wrapped the call, and that must keep working.
  3. `cs unanswered` degrades WITHOUT reusing the engine-failure channel, and
     the printed cause matches what actually happened.

Property 3 is the point. `sweep()`'s existing `note` means the ENGINE could not
screen, so every message reads as owed — the list is too WIDE, and the renderer
promises exactly that. A failed mailbox read is the opposite: messages never
entered the sweep, so the list is too SHORT. Folding the second into the first
prints a reassuring, conservative-sounding sentence over a silently narrow
queue, on the one verb whose entire output is who is still waiting. A test that
only asserted "it did not raise" would pass that bug, so these assert the
printed text.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import gmail_archive  # noqa: E402


class _FailingFetch:
    """Answers SEARCH normally and FETCH non-OK — a transient server error."""

    def __init__(self, n=5):
        self.n = n

    def list(self):
        return "OK", [b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"',
                      b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

    def select(self, folder, readonly=True):
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "SEARCH":
            return "OK", [b" ".join(str(i + 1).encode() for i in range(self.n))]
        if command == "FETCH":
            return "NO", [None]
        raise AssertionError(command)

    def logout(self):
        return "BYE", [b""]


def test_fetch_headers_raises_instead_of_returning_short():
    M = _FailingFetch(n=5)
    ids = [str(i + 1).encode() for i in range(5)]
    try:
        got = gmail_archive._fetch_headers(M, ids)
    except gmail_archive.ChunkFetchFailed as e:
        assert "were not read" in str(e), str(e)
        print("OK: a non-OK batched FETCH raises ChunkFetchFailed naming the "
              "messages that were not read")
        return
    raise AssertionError(
        f"_fetch_headers returned {len(got)} row(s) instead of raising — a "
        "short list is indistinguishable from 'nothing found', which is the "
        "whole defect"
    )


def test_sweep_routes_the_failure_to_read_incomplete_not_note():
    """Drive the REAL sweep() and assert WHICH channel the failure lands in.

    The renderer test below feeds a hand-built dict, so on its own it would
    still pass if `sweep()` routed the failure into `note` — the exact
    conflation this whole milestone exists to prevent. This test closes that:
    it makes `inbound_recent` raise for real and asserts `note` stays None
    while `read_incomplete` fills, so swapping the two keys in
    `cs/unanswered.py` turns this gate red."""
    from cs import gmail_archive as ga
    from cs import unanswered as un

    real_inbound, real_sent = ga.inbound_recent, ga.sent_recent

    def boom(*a, **k):
        raise ga.ChunkFetchFailed("a batched header FETCH over 200 message(s) "
                                  "returned 'NO' — those messages were not read")

    ga.inbound_recent, ga.sent_recent = boom, boom
    try:
        d = un.sweep(_settings(), days=7)
    finally:
        ga.inbound_recent, ga.sent_recent = real_inbound, real_sent

    assert d["read_incomplete"], (
        "sweep() swallowed the failure — `read_incomplete` is empty:\n" + repr(d))
    assert d["note"] is None, (
        "sweep() routed a MAILBOX-read failure into `note`, the ENGINE channel. "
        "`note` makes the renderer promise a too-WIDE list ('every message reads "
        "as needing a reply') over a list that is too SHORT. Got note=%r"
        % (d["note"],))
    for bucket in ("open", "handled", "escalated", "resumed", "automatic",
                   "courtesy"):
        assert d[bucket] == [], f"{bucket} is not empty: {d[bucket]!r}"
    print("OK: a failed mailbox read fills `read_incomplete`, leaves the engine "
          "channel `note` untouched, and yields no confidently-classified rows")


def _settings():
    """Minimal settings for sweep(); the IMAP readers are stubbed out before
    they are reached, and the ledger is opened read-only against a temp db."""
    import tempfile

    from cs import config

    s = config.Settings(_env_file=None)
    s.db_path = Path(tempfile.mkdtemp()) / "cs.db"
    return s


def test_unanswered_degrades_without_borrowing_the_engine_channel():
    """The renderer must not describe a too-short list with the too-wide
    sentence."""
    from cs import cli

    # The two channels, rendered from a sweep result directly — no IMAP, no
    # engine: this asserts the RENDERING contract, which is where the wrong
    # explanation would be printed.
    incomplete = {
        "open": [], "handled": [], "escalated": [], "resumed": [],
        "automatic": [], "courtesy": [], "note": None,
        "read_incomplete": "a batched header FETCH over 200 message(s) "
                           "returned 'NO' — those messages were not read",
    }
    buf = io.StringIO()
    with redirect_stdout(buf):
        _render_via_cmd(cli, incomplete)
    out = buf.getvalue()

    assert "MAILBOX READ INCOMPLETE" in out, out
    assert "UNKNOWN, not as nobody waiting" in out, out
    assert "every message reads as needing a reply" not in out, (
        "the engine-unavailable sentence was printed for a mailbox-read "
        "failure — it promises a conservatively WIDE list while showing a "
        "silently NARROW one:\n" + out
    )
    print("OK: a failed mailbox read prints its own cause and refuses to "
          "present the open list as complete")

    # And the engine channel still renders its own, unchanged.
    engine_down = dict(incomplete, note="engine asleep", read_incomplete=None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        _render_via_cmd(cli, engine_down)
    out = buf.getvalue()
    assert "every message reads as needing a reply" in out, out
    assert "MAILBOX READ INCOMPLETE" not in out, out
    print("OK: the engine-unavailable channel is unchanged and the two never "
          "print each other's explanation")


def test_json_path_signals_incompleteness_to_an_unattended_caller():
    """The `--json` path is the CRON's path, and it was the one still broken.

    `cs unanswered --days 14 --json` is what `cs-triage-mail` runs on an
    unattended tick. It prints only the `open` rows — a bare JSON list, whose
    shape is a contract — so the `read_incomplete` key never reached it: a
    failed read produced `[]` with rc 0, which reads as "nobody is waiting"
    with no human present to doubt it.

    stdout keeps the contract. The signal goes to stderr and the exit code."""
    import contextlib
    import types

    from cs import cli
    from cs import unanswered as unanswered_mod

    d = {
        "open": [], "handled": [], "escalated": [], "resumed": [],
        "automatic": [], "courtesy": [], "note": None,
        "read_incomplete": "a batched header FETCH over 200 message(s) "
                           "returned 'NO' — those messages were not read",
    }
    real = unanswered_mod.sweep
    unanswered_mod.sweep = lambda *a, **k: d
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.cmd_unanswered(types.SimpleNamespace(
                days=14, json=True, crm=False, account=None,
                all_buckets=False))
    finally:
        unanswered_mod.sweep = real

    assert rc != 0, (
        "cs unanswered --json returned 0 after a failed mailbox read. An "
        "unattended caller cannot distinguish that from an empty queue — the "
        "same defect as `cs ask` exiting 0 while printing an engine error.")
    assert "MAILBOX READ INCOMPLETE" in err.getvalue(), err.getvalue()
    assert "never as nobody waiting" in err.getvalue(), err.getvalue()
    # stdout is still exactly the parseable contract, nothing prepended.
    import json as _json
    assert _json.loads(out.getvalue()) == [], out.getvalue()
    print("OK: the --json path keeps its stdout contract and signals the "
          f"incomplete read on stderr with rc={rc}")


def _render_via_cmd(cli, d):
    """Drive the real renderer with a canned sweep result."""
    import types

    from cs import unanswered as unanswered_mod

    real = unanswered_mod.sweep
    unanswered_mod.sweep = lambda *a, **k: d
    try:
        cli.cmd_unanswered(
            types.SimpleNamespace(days=7, json=False, crm=False, account=None))
    finally:
        unanswered_mod.sweep = real


if __name__ == "__main__":
    test_fetch_headers_raises_instead_of_returning_short()
    test_sweep_routes_the_failure_to_read_incomplete_not_note()
    test_json_path_signals_incompleteness_to_an_unattended_caller()
    test_unanswered_degrades_without_borrowing_the_engine_channel()
    print("test_chunk_fetch_failure: all assertions passed")
