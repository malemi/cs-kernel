#!/usr/bin/env python3
"""The two verbs `/cs-review` needs to say whether anything is actually running.

`cs cron status` knew whether the crontab entry existed and printed prose no
program could read, so the review inferred the state of the unattended operator
from a six-line log tail — and got it wrong, twice: it read a quiet log as a
fault and it read a timestamp as "the work happened then" when the run had
skipped. `cs catchup` is the one write `/cs-review` may offer, and it must be
offered only when it is warranted, because it spends real LLM budget.

Asserted here (no crontab, no engine, no mailbox — every read is injected):

  A. `cron_state` distinguishes the three states whose remedies differ —
     `absent`, `paused`, `stale` — from `ticking`, and carries the last run's
     timestamp AND what that run did, which is the fact a bare timestamp lies
     about.
  B. Pause outranks stale, and an ABSENT entry outranks both: the greeting must
     name the thing that has to be fixed first, and no state ever suggests
     lifting the switch.
  C. The staleness threshold comes from the SCHEDULE, not from a number in the
     kernel: the same log is fresh under a daily entry and stale under a
     2-hourly one.
  D. `cs catchup` drives the engine's own surfaces in order — `sync.run` then
     `update.run` — and reports the task DIFF rather than narrating that it ran.
     A failing `sync.run` does not cancel `update.run`, and the verb exits
     non-zero rather than reporting a pass that did not happen.
  E. `cs catchup --check` writes NOTHING: it runs neither pass, and it answers
     `stale` only when the newest message in the mailbox is one the engine
     cannot show. Every unanswerable case answers "not stale" — the only thing
     `stale` triggers is an offer to spend money.
"""
from __future__ import annotations

import io
import sys
import types
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cs import cli, cron, review  # noqa: E402

fails = 0


def check(cond, msg: str) -> None:
    global fails
    if not cond:
        print(f"  FAIL: {msg}")
        fails += 1


def _settings(tmp: Path, *, paused: bool, log: str | None):
    log_path = tmp / "cs_operator.log"
    if log is not None:
        log_path.write_text(log)
    pause = tmp / "CS_PAUSE"
    if paused:
        pause.write_text("")
    return types.SimpleNamespace(slug="acme", pause_path=pause, log_path=log_path)


def _state(tmp: Path, *, installed=True, paused=False, log=None,
           schedule="0 6-18/2 * * 2-5"):
    orig_cron, orig_raw = cron._read_crontab, cron._read_raw_cron
    cron._read_crontab = lambda: (
        ["0 6-18/2 * * 2-5  /x/bin/cs_operator_cron.sh  # cs-cron:acme"]
        if installed else ["@daily /something/else"])
    cron._read_raw_cron = lambda p: (schedule, "cs-operator")
    try:
        return cron.cron_state(_settings(tmp, paused=paused, log=log),
                               clone_root=tmp)
    finally:
        cron._read_crontab, cron._read_raw_cron = orig_cron, orig_raw


def _ts(hours_ago: float) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ A + B

def _states() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        fresh = f"{_ts(1)} acme-cs: tick start (root=/x)\n{_ts(1)} acme-cs: tick end (exit 0)\n"

        st = _state(tmp, installed=False, log=fresh)
        check(st["state"] == "absent" and st["installed"] is False,
              f"no crontab entry is `absent`, got {st['state']}")

        st = _state(tmp, log=fresh)
        check(st["state"] == "ticking" and st["stale"] is False,
              f"an entry with a fresh log is ticking, got {st}")
        check(st["last_tick_at"] and st["last_tick_action"] == "ran",
              f"the last run is dated AND says what it did, got {st}")

        skipped = f"{_ts(1)} acme-cs: paused (CS_PAUSE present) — skip\n"
        st = _state(tmp, log=skipped)
        check(st["last_tick_action"] == "skipped",
              f"a run that skipped must not read as work done, got {st}")

        old = f"{_ts(72)} acme-cs: tick end (exit 0)\n"
        st = _state(tmp, log=old)
        check(st["state"] == "stale" and st["stale"] is True,
              f"an entry whose log went quiet is stale, got {st}")

    with TemporaryDirectory() as td:
        tmp = Path(td)
        old = f"{_ts(72)} acme-cs: tick end (exit 0)\n"
        st = _state(tmp, paused=True, log=old)
        check(st["state"] == "paused",
              f"the switch outranks staleness — it explains the silence, got {st}")
        check(st["paused"] is True and st["stale"] is False,
              f"and a paused clone is never reported as failing, got {st}")

    with TemporaryDirectory() as td:
        tmp = Path(td)
        st = _state(tmp, installed=False, paused=True, log=None)
        check(st["state"] == "absent",
              f"nothing installed is the first thing to fix, got {st['state']}")


# ---------------------------------------------------------------------- C

def _threshold_from_schedule() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        log = f"{_ts(10)} acme-cs: tick end (exit 0)\n"
        two_hourly = _state(tmp, log=log, schedule="0 6-18/2 * * 2-5")
        daily = _state(tmp, log=log, schedule="0 7 * * *")
        check(two_hourly["stale"] is True and daily["stale"] is False,
              f"the threshold is the SCHEDULE's, not a kernel constant: "
              f"{two_hourly['state']} vs {daily['state']}")
        check(two_hourly["interval_hours"] == 2 and daily["interval_hours"] == 24,
              f"and the interval is reported, got {two_hourly['interval_hours']} "
              f"/ {daily['interval_hours']}")


# ---------------------------------------------------------------------- D

def _catchup() -> None:
    calls = []

    def _call_sync(_s, method, params=None, **kw):
        calls.append(method)
        if method == "sync.run":
            return {"success": True, "summary": "3 new emails"}
        if method == "update.run":
            return {"success": True, "summary": "…",
                    "updated_tasks": {"created": ["t1", "t2"], "closed": ["t3"],
                                      "updated": []}}
        raise AssertionError(f"unexpected method {method}")

    orig_load, orig_rpc = cli.config.load, cli.rpc.call_sync
    cli.config.load = lambda: types.SimpleNamespace(prog_name="cs")
    cli.rpc.call_sync = _call_sync
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.cmd_catchup(types.SimpleNamespace(
                check=False, json=False, timeout=1800))
    finally:
        cli.config.load, cli.rpc.call_sync = orig_load, orig_rpc

    out = buf.getvalue()
    check(calls == ["sync.run", "update.run"],
          f"the engine's own two passes, in order, and nothing else: {calls}")
    check(rc == 0, f"a clean pass exits 0, got {rc}")
    check("2 task(s) created" in out and "1 closed" in out,
          f"the DIFF is what gets reported, not that it ran:\n{out}")
    check("t1" in out and "t3" in out, f"and the ids are nameable:\n{out}")

    # A failing first pass must not swallow the second, and must not read as
    # success: an operator told "done" runs the review on stale state.
    def _half(_s, method, params=None, **kw):
        if method == "sync.run":
            raise RuntimeError("IMAP refused")
        return {"success": True, "updated_tasks": {"created": [], "closed": [],
                                                   "updated": []}}

    orig_load, orig_rpc = cli.config.load, cli.rpc.call_sync
    cli.config.load = lambda: types.SimpleNamespace(prog_name="cs")
    cli.rpc.call_sync = _half
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.cmd_catchup(types.SimpleNamespace(
                check=False, json=False, timeout=1800))
    finally:
        cli.config.load, cli.rpc.call_sync = orig_load, orig_rpc
    check(rc == 1, f"a half-run pass exits non-zero, got {rc}")
    check("IMAP refused" in buf.getvalue(),
          f"and says which half failed:\n{buf.getvalue()}")

    # The engine runs this same pipeline on its own schedule and refuses to run
    # two at once: the second caller gets `busy` with an empty diff. That is the
    # guard working, not a failure — reporting it as one would send an operator
    # chasing an engine that is doing exactly what it should.
    def _busy(_s, method, params=None, **kw):
        if method == "sync.run":
            return {"success": True, "summary": "0 new emails"}
        return {"busy": True, "success": False,
                "updated_tasks": {"created": [], "closed": [], "updated": []}}

    orig_load, orig_rpc = cli.config.load, cli.rpc.call_sync
    cli.config.load = lambda: types.SimpleNamespace(prog_name="cs")
    cli.rpc.call_sync = _busy
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.cmd_catchup(types.SimpleNamespace(
                check=False, json=False, timeout=1800))
    finally:
        cli.config.load, cli.rpc.call_sync = orig_load, orig_rpc
    check(rc == 0, f"`busy` is a clean outcome, got exit {rc}")
    check("already running" in buf.getvalue(),
          f"and it is stated in the operator's terms:\n{buf.getvalue()}")
    check("0 task(s) created" not in buf.getvalue(),
          f"a busy pass reports no diff of its own:\n{buf.getvalue()}")


# ---------------------------------------------------------------------- E

def _freshness() -> None:
    newest = datetime.now(timezone.utc) - timedelta(hours=2)
    inbox = [{"email": "c@example.test", "name": "", "date": newest,
              "subject": "Still waiting", "message_id": "<m1>",
              "thread_key": "<t1>"}]

    def probe(recent, engine_reply, *, raise_engine=False):
        calls = []

        def _search(_s, days):
            calls.append("imap")
            return recent

        def _rpc(_s, method, params=None, **kw):
            calls.append(method)
            if raise_engine:
                raise RuntimeError("engine asleep")
            return engine_reply

        orig_rpc = review.rpc.call_sync
        import cs.gmail_archive as ga
        orig_recent = ga.inbound_recent
        review.rpc.call_sync = _rpc
        ga.inbound_recent = _search
        try:
            return review.engine_freshness(None), calls
        finally:
            review.rpc.call_sync = orig_rpc
            ga.inbound_recent = orig_recent

    # The engine holds it (whole-second join, the engine's naive-UTC shape).
    known = {"emails": [{"date": newest.replace(tzinfo=None).isoformat()}]}
    st, calls = probe(inbox, known)
    check(st["stale"] is False, f"a message the engine holds is not stale: {st}")
    check("sync.run" not in calls and "update.run" not in calls,
          f"--check runs NO pass: {calls}")

    st, _ = probe(inbox, {"emails": [{"date": (newest - timedelta(days=2))
                                      .replace(tzinfo=None).isoformat()}]})
    check(st["stale"] is True,
          f"the newest message missing from the engine IS stale: {st}")
    check(st["newest_inbound_at"], "and the row it is about is named")

    st, _ = probe([], {"emails": []})
    check(st["stale"] is False and "no inbound" in st["reason"],
          f"nothing to ingest is never an offer: {st}")

    st, _ = probe(inbox, None, raise_engine=True)
    check(st["stale"] is False and "engine asleep" in (st["note"] or ""),
          f"an engine that will not answer is a note, not an offer: {st}")

    unthreadable = [dict(inbox[0], thread_key="")]
    st, _ = probe(unthreadable, {"emails": []})
    check(st["stale"] is False,
          f"a message with no thread key cannot be asked about: {st}")


_states()
_threshold_from_schedule()
_catchup()
_freshness()

if fails:
    print(f"test_catchup_cron: {fails} assertion(s) FAILED")
    sys.exit(1)
print("test_catchup_cron: all assertions passed")
