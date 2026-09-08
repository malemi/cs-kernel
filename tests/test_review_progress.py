#!/usr/bin/env python3
"""`cs review`'s progress trail (M4) — stderr only, and the two named timeouts.

`cs review` used to emit zero bytes for fourteen minutes with no way to tell a
slow run from a hang; an instrumented run later passed 25 minutes still going.
M4 makes the slowness VISIBLE — it does not fix it (that is M2/M3) — by
announcing each `gather()` stage on stderr as it starts and timing it when it
finishes, and by naming an explicit timeout for the two calls that previously
ran under whatever default happened to sit on the callee:
`campaign.contacts` (looped once per campaign) and `engine_view.settled`
(the engine may make a model call to answer it).

Two properties, and the first is the one every other line of this milestone
would be pointless without:

  1. `cs review --json` stdout is parsed (the cron's bootstrap step 4c) and
     must stay exactly what it always printed — every progress line has to
     land on stderr, never stdout, whatever else changes.
  2. `campaign.contacts` and `engine_view.settled` each carry a NAMED,
     explicit timeout, appear on the progress trail, and — the direction that
     matters — a timeout degrades to a line that NAMES the bound rather than
     to a hang or to the blank string a bare `asyncio.TimeoutError` prints.

Hermetic: no engine, mailbox, or network. Every seam `gather()` reads through
(`gmail_drafts.list_drafts`, `rpc.call_sync`, `draft_state.reconcile`,
`campaign.list_campaigns`, `engine_view.settled`) is replaced with an in-memory
fixture, following the same monkeypatch pattern as
`tests/test_draft_state.py`'s `_review_surface`.
"""
from __future__ import annotations

import io
import json
import tempfile
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import cli, review  # noqa: E402


def _settings():
    """A settings object real enough for `gather()`'s non-mocked reads
    (`State`, `_last_log_lines`) to succeed cleanly against an empty temp
    ledger — a real empty DB, not a missing path, so `escalated` and
    `handled_out_of_band` come back `[]` with no error key to work around."""
    s = types.SimpleNamespace()
    s.excluded_campaign_set = set()
    s.db_path = Path(tempfile.mkdtemp()) / "cs.db"
    s.timezone = "Europe/Rome"
    s.log_path = Path(tempfile.mkdtemp()) / "cs_operator.log"
    return s


def _assert_in_order(text: str, markers: list[str]) -> None:
    """Every marker is present, and in the given order — proves the stages
    are announced start-then-elapsed, nested correctly (`engine_view.settled`
    inside `draft reconcile`, `campaign.contacts <name>` inside the
    per-campaign loop), not just present anywhere in the stream."""
    cursor = 0
    for m in markers:
        idx = text.find(m, cursor)
        assert idx != -1, (
            f"missing or out-of-order progress marker {m!r} (searched from "
            f"offset {cursor}) in:\n{text}")
        cursor = idx + len(m)


def test_stdout_stays_json_clean_while_stderr_carries_every_stage():
    gmail_fixture = [{"gmail_uid": "101", "to": "a@example.test",
                      "subject": "Hello"}]
    engine_fixture = [{"id": "eng-1"}]
    task_fixture = [{"id": "task-1", "contact_email": "b@example.test",
                     "title": "Question", "urgency": "high"}]
    campaign_fixture = [{"id": "camp-1", "name": "spring-launch",
                         "contacts_by_state": {"pending": 2}}]
    contacts_fixture = [{"email": "c@example.test", "state": "pending",
                         "dossier": {}}]
    reconcile_rows = [{"verdict": "ready", "to": "a@example.test",
                       "gmail_uid": "101", "engine_id": None,
                       "evidence_incomplete": []}]

    calls = []

    def _list_drafts(_s):
        return gmail_fixture

    def _call_sync(_s, method, params=None, timeout=None, **kw):
        calls.append((method, params, timeout))
        if method == "drafts.list":
            return engine_fixture
        if method == "tasks.list":
            return task_fixture
        if method == "campaign.contacts":
            return contacts_fixture
        raise AssertionError(f"unexpected rpc method in this test: {method}")

    def _settled_stub(_s, thread_ids, timeout=None):
        assert timeout == review.ENGINE_SETTLED_TIMEOUT_SECONDS, timeout
        return {}, None

    def _reconcile(_s, gd, ed, **kw):
        settled_fn = kw.get("settled")
        assert settled_fn is not None and settled_fn is not review.engine_view.settled, (
            "gather() must inject its own progress+timeout wrapper as the "
            "settled seam, not leave reconcile() to default to the bare "
            "engine_view.settled")
        # Actually exercise it, so the "engine_view.settled" stage really
        # appears on the trail below rather than being asserted by name alone.
        views, note = settled_fn(_s, ["thread-9"])
        assert (views, note) == ({}, None), (views, note)
        return list(reconcile_rows), []

    orig = (review.gmail_drafts.list_drafts, review.rpc.call_sync,
            review.draft_state.reconcile, review.campaign.list_campaigns,
            review.engine_view.settled)
    review.gmail_drafts.list_drafts = _list_drafts
    review.rpc.call_sync = _call_sync
    review.draft_state.reconcile = _reconcile
    review.campaign.list_campaigns = lambda _s: campaign_fixture
    review.engine_view.settled = _settled_stub

    settings = _settings()
    orig_load = cli.config.load
    cli.config.load = lambda: settings

    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.cmd_review(types.SimpleNamespace(json=True))
    finally:
        cli.config.load = orig_load
        (review.gmail_drafts.list_drafts, review.rpc.call_sync,
         review.draft_state.reconcile, review.campaign.list_campaigns,
         review.engine_view.settled) = orig

    assert rc == 0, f"cs review --json still exits 0, got {rc}"

    stdout_text = out.getvalue()
    assert "[review]" not in stdout_text, (
        f"progress leaked onto stdout — the parsed contract is broken:\n"
        f"{stdout_text}")

    parsed = json.loads(stdout_text)  # raises if progress corrupted the JSON
    assert parsed["gmail_drafts"] == gmail_fixture, parsed["gmail_drafts"]
    assert parsed["engine_drafts"] == engine_fixture, parsed["engine_drafts"]
    assert parsed["drafts"] == reconcile_rows, parsed["drafts"]
    assert parsed["drafts_notes"] == [], parsed["drafts_notes"]
    assert parsed["tasks"] == [review._task_row(t) for t in task_fixture], \
        parsed["tasks"]
    assert "tasks_error" not in parsed, parsed
    assert parsed["escalated"] == [] and "escalated_error" not in parsed, parsed
    assert (parsed["handled_out_of_band"] == []
            and "handled_out_of_band_error" not in parsed), parsed
    assert len(parsed["campaigns"]) == 1, parsed["campaigns"]
    assert parsed["campaigns"][0]["campaign"] == "spring-launch", parsed["campaigns"]
    assert "campaigns_error" not in parsed, parsed
    assert parsed["last_tick"] == [], parsed["last_tick"]
    print("OK: cs review --json stdout is exactly the parsed digest — no "
          "progress marker reached it")

    campaign_calls = [c for c in calls if c[0] == "campaign.contacts"]
    assert len(campaign_calls) == 1, campaign_calls
    assert campaign_calls[0][2] == review.CAMPAIGN_CONTACTS_TIMEOUT_SECONDS, (
        f"campaign.contacts must carry the named explicit timeout, got "
        f"{campaign_calls[0]}")

    stderr_text = err.getvalue()
    _assert_in_order(stderr_text, [
        "[review] Gmail draft listing: starting",
        "[review] Gmail draft listing: done (",
        "[review] engine drafts.list: starting",
        "[review] engine drafts.list: done (",
        "[review] draft reconcile: starting",
        "[review] engine_view.settled: starting",
        "[review] engine_view.settled: done (",
        "[review] draft reconcile: done (",
        "[review] tasks.list: starting",
        "[review] tasks.list: done (",
        "[review] per-campaign loop: starting",
        "[review] campaign.contacts spring-launch: starting",
        "[review] campaign.contacts spring-launch: done (",
        "[review] per-campaign loop: done (",
    ])
    print("OK: all six gather() stages — plus the two nested calls — "
          "announce themselves and report elapsed time, in order, on stderr")


def test_campaign_contacts_carries_named_timeout_and_reports_it():
    calls = []

    def _ok(_s, method, params=None, timeout=None, **kw):
        calls.append((method, params, timeout))
        return ["contact-row"]

    orig = review.rpc.call_sync
    review.rpc.call_sync = _ok
    try:
        got = review._campaign_contacts(
            object(), {"id": "camp-1", "name": "spring-launch"})
    finally:
        review.rpc.call_sync = orig
    assert got == ["contact-row"], got
    assert calls == [("campaign.contacts", {"campaign_id": "camp-1"},
                      review.CAMPAIGN_CONTACTS_TIMEOUT_SECONDS)], calls
    print("OK: _campaign_contacts passes the named explicit timeout")

    def _timeout(_s, method, params=None, timeout=None, **kw):
        raise TimeoutError()  # what asyncio.wait_for actually raises: no message

    review.rpc.call_sync = _timeout
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            try:
                review._campaign_contacts(
                    object(), {"id": "camp-2", "name": "autumn-followup"})
            except TimeoutError as e:
                msg = str(e)
            else:
                raise AssertionError(
                    "a timeout must still raise so gather()'s existing "
                    "except-and-note catches it — swallowing it here would "
                    "be a silent narrowing")
    finally:
        review.rpc.call_sync = orig
    assert "exceeded" in msg and str(review.CAMPAIGN_CONTACTS_TIMEOUT_SECONDS) in msg, (
        f"a bare asyncio.TimeoutError stringifies to '' — the wrapper must "
        f"name the bound instead of leaving a blank degradation line, got "
        f"{msg!r}")
    assert "FAILED" in buf.getvalue(), (
        f"the stage line must mark the failure, not read like a normal "
        f"'done':\n{buf.getvalue()}")
    print("OK: a campaign.contacts timeout degrades to a line naming the "
          "bound, never a hang or a blank exception")


def test_settled_seam_carries_named_timeout_and_reports_it():
    calls = []

    def _ok(_s, thread_ids, timeout=None):
        calls.append((thread_ids, timeout))
        return {}, None

    orig = review.engine_view.settled
    review.engine_view.settled = _ok
    try:
        views, note = review._settled_with_timeout(object(), ["k1", "k2"])
    finally:
        review.engine_view.settled = orig
    assert (views, note) == ({}, None)
    assert calls == [(["k1", "k2"], review.ENGINE_SETTLED_TIMEOUT_SECONDS)], calls
    print("OK: _settled_with_timeout passes the named explicit timeout")

    def _timeout(_s, thread_ids, timeout=None):
        raise TimeoutError()

    review.engine_view.settled = _timeout
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            try:
                review._settled_with_timeout(object(), ["k1"])
            except TimeoutError as e:
                msg = str(e)
            else:
                raise AssertionError("a timeout must still raise, not hang")
    finally:
        review.engine_view.settled = orig
    assert "exceeded" in msg and str(review.ENGINE_SETTLED_TIMEOUT_SECONDS) in msg, msg
    assert "FAILED" in buf.getvalue(), buf.getvalue()
    print("OK: an engine_view.settled timeout degrades to a line naming the "
          "bound, never a hang or a blank exception")


def test_full_gather_survives_a_campaign_timeout_without_raising():
    """Integration: the wrapper is not just correct in isolation, `gather()`
    as a whole absorbs the failure exactly as it did before this milestone —
    a note, never a traceback — and a stage that already succeeded is not
    undone by a later one timing out."""
    settings = _settings()

    def _list_drafts(_s):
        return []

    def _call_sync(_s, method, params=None, timeout=None, **kw):
        if method == "drafts.list":
            return []
        if method == "tasks.list":
            return [{"id": "t1", "contact_email": "x@example.test",
                     "title": "still here", "urgency": "low"}]
        if method == "campaign.contacts":
            raise TimeoutError()
        raise AssertionError(f"unexpected rpc method: {method}")

    def _reconcile(_s, gd, ed, **kw):
        return [], []

    orig = (review.gmail_drafts.list_drafts, review.rpc.call_sync,
            review.draft_state.reconcile, review.campaign.list_campaigns)
    review.gmail_drafts.list_drafts = _list_drafts
    review.rpc.call_sync = _call_sync
    review.draft_state.reconcile = _reconcile
    review.campaign.list_campaigns = lambda _s: [
        {"id": "c1", "name": "stuck-campaign"}]

    err = io.StringIO()
    try:
        with redirect_stderr(err):
            d = review.gather(settings)
    finally:
        (review.gmail_drafts.list_drafts, review.rpc.call_sync,
         review.draft_state.reconcile, review.campaign.list_campaigns) = orig

    assert d["tasks"], (
        "tasks.list ran before the campaign loop and must still be intact "
        f"after it times out: {d}")
    assert d["campaigns"] == [], "the timed-out campaign contributes no row"
    assert d.get("campaigns_error"), "the timeout must be reported, not swallowed"
    assert "exceeded" in d["campaigns_error"] and \
        str(review.CAMPAIGN_CONTACTS_TIMEOUT_SECONDS) in d["campaigns_error"], (
        d["campaigns_error"])
    assert "FAILED" in err.getvalue(), err.getvalue()
    print("OK: gather() as a whole degrades a campaign.contacts timeout into "
          f"a clear campaigns_error ({d['campaigns_error']!r}) without "
          "raising, and an earlier stage's result is untouched")


if __name__ == "__main__":
    test_stdout_stays_json_clean_while_stderr_carries_every_stage()
    test_campaign_contacts_carries_named_timeout_and_reports_it()
    test_settled_seam_carries_named_timeout_and_reports_it()
    test_full_gather_survives_a_campaign_timeout_without_raising()
    print("test_review_progress: all assertions passed")
