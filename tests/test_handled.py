#!/usr/bin/env python3
"""`cs handled` — "I resolved this outside email", and every surface obeys it.

Why this gate exists (2026-08): a customer wrote on 17 July, the owner
TELEPHONED him and resolved it. Gmail Sent is the dedup ground truth and knows
nothing about a phone call, so `compute_open` re-discovered that thread on every
tick and told the owner to write to him — daily, for over a month. The only
filter the sweep had was `ignore`: permanent and undated, i.e. exactly wrong for
a customer we want to keep talking to.

Asserted here:

  1. an inbound BEFORE the handled moment is not open work;
  2. a NEWER inbound re-opens the contact with no second command;
  3. the held-back senders are still reported (with date + reason) — an
     invisible filter is indistinguishable from a bug;
  4. the record is idempotent, and re-recording moves the moment;
  5. `--undo` removes it and the mail becomes open again;
  6. recording CLOSES the contact's open engine tasks with actor="human" —
     reading `id` from tasks.list, which is NOT the `task_id` tasks.complete
     wants (that mismatch has already cost one bug);
  7. a mistyped address, an unparseable `--at`, and an `--at` in the FUTURE (a
     permanent ignore wearing a date) are clean refusals that write nothing —
     never a traceback, and never a silently retired customer;
  8. `sweep()` really feeds the db record into the open-logic (the wiring, not
     just the pure function), and `--account` cannot redirect the record;
  9. `cs review` — where the operator looks when he sits down — shows the
     record, on his own calendar day, with the reason and how to undo it.

Hermetic: a sandbox HOME for the SQLite ledger, stubbed IMAP + RPC. No mailbox,
no engine, no network.
"""
from __future__ import annotations

import os
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cs import _time, cli, config as cfg, rpc, unanswered
from cs.state import State

NOW = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
TZ = "Europe/Rome"


def _dt(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


def _settings(db_path: str):
    return types.SimpleNamespace(
        db_path=db_path,
        timezone=TZ,
        prog_name="cs",
        email_address="support@example.test",
        self_email_set=set(),
        system_sender_set=set(),
    )


# --------------------------------------------------------------- pure logic


def _pure() -> None:
    inbound = [
        # phoned back on 20 Jul; their last mail is older -> NOT open
        {"email": "Phoned@example.test", "name": "Phoned", "date": _dt(36),
         "subject": "problema centralino"},
        # same record, but they wrote AGAIN afterwards -> OPEN again
        {"email": "wroteback@example.test", "name": "Wrote", "date": _dt(2),
         "subject": "ancora io"},
        {"email": "wroteback@example.test", "name": "Wrote", "date": _dt(36),
         "subject": "problema centralino"},
        # no record at all -> OPEN
        {"email": "cold@example.test", "name": "Cold", "date": _dt(9),
         "subject": "hello?"},
    ]
    handled = {
        "phoned@example.test": _dt(33),        # the call, 3 days after they wrote
        "WroteBack@example.test": _dt(33),     # mixed case must still match
    }

    rows = unanswered.compute_open(inbound, [], set(), set(), NOW, handled)
    emails = [r["email"] for r in rows]
    assert "phoned@example.test" not in emails, \
        f"inbound BEFORE the handled moment must not be open: {emails}"
    assert "wroteback@example.test" in emails, \
        f"a NEWER inbound must re-open the contact: {emails}"
    assert "cold@example.test" in emails, emails

    held = unanswered.compute_handled(inbound, [], set(), set(), NOW, handled)
    assert [r["email"] for r in held] == ["phoned@example.test"], held
    assert held[0]["handled_at"] == _dt(33), held[0]
    assert held[0]["subject"] == "problema centralino", held[0]

    # no record at all -> byte-for-byte the pre-change behaviour (the arg is
    # optional, and an absent map must not change a single verdict)
    assert unanswered.compute_open(inbound, [], set(), set(), NOW) == \
        unanswered.compute_open(inbound, [], set(), set(), NOW, {}), \
        "an empty handled map must be identical to no map at all"
    assert {r["email"] for r in unanswered.compute_open(inbound, [], set(), set(), NOW)} == {
        "phoned@example.test", "wroteback@example.test", "cold@example.test"
    }

    # a naive record must not blow up against tz-aware message dates
    naive = {"phoned@example.test": _dt(33).replace(tzinfo=None)}
    assert "phoned@example.test" not in [
        r["email"] for r in unanswered.compute_open(inbound, [], set(), set(), NOW, naive)
    ], "a naive handled timestamp must be read as UTC, not crash or be ignored"

    # a send AFTER their last inbound still closes them, record or not
    sent = [{"to": ["cold@example.test"], "date": _dt(1)}]
    assert "cold@example.test" not in [
        r["email"] for r in unanswered.compute_open(inbound, sent, set(), set(), NOW, handled)
    ]
    print("OK: compute_open/compute_handled — dated suppression, re-open on a newer inbound")


# ------------------------------------------------------------------- state


def _ledger(db_path: str) -> None:
    st = State(db_path)
    assert st.handled_out_of_band() == {}

    st.mark_handled("Phoned@example.test", reason="chiamato, risolto", handled_at=_dt(33))
    recs = st.handled_out_of_band()
    assert set(recs) == {"phoned@example.test"}, recs
    assert recs["phoned@example.test"]["handled_at"] == _dt(33), recs
    assert recs["phoned@example.test"]["reason"] == "chiamato, risolto"
    assert st.handled_at_map() == {"phoned@example.test": _dt(33)}

    # idempotent: twice is not an error, and the newer moment wins
    st.mark_handled("phoned@example.test", reason="richiamato", handled_at=_dt(30))
    recs = st.handled_out_of_band()
    assert len(recs) == 1, recs
    assert recs["phoned@example.test"]["handled_at"] == _dt(30), recs
    assert recs["phoned@example.test"]["reason"] == "richiamato", recs

    # do_not_contact is a DIFFERENT list: handling somebody must never
    # suppress them (they are a customer we want to keep talking to)
    assert st.do_not_contact_set() == set(), st.do_not_contact_set()

    assert st.unmark_handled("phoned@example.test") is True
    assert st.handled_out_of_band() == {}
    assert st.unmark_handled("phoned@example.test") is False, \
        "undoing a record that is not there must report False, not claim an undo"
    print("OK: state ledger — dated, idempotent, reversible, not do_not_contact")


# --------------------------------------------------------------------- CLI


def _cli(db_path: str) -> None:
    settings = _settings(db_path)
    cfg.load = lambda: settings
    calls: list[tuple] = []

    def fake_call_sync(_settings, method, params=None, timeout=None):
        calls.append((method, params))
        if method == "tasks.list":
            # NOTE the key: tasks.list returns `id`, tasks.complete wants `task_id`.
            return [
                {"id": "t-1", "contact_email": "Phoned@example.test", "title": "richiamare"},
                {"id": "t-2", "contact_email": "phoned@example.test", "title": "altro"},
                {"id": "t-3", "contact_email": "someone.else@example.test", "title": "no"},
                {"contact_email": "phoned@example.test", "title": "id-less row"},
            ]
        return {"ok": True}

    rpc.call_sync = fake_call_sync

    def _args(**kw):
        base = dict(email=None, why=None, at=None, undo=False)
        base.update(kw)
        return types.SimpleNamespace(**base)

    # --- refusals first: nothing must be written by a bad call ---
    assert cli.cmd_handled(_args(email="Maurizio")) == 2, "a non-address must refuse"
    assert cli.cmd_handled(_args(email="a@b")) == 2, "a domain with no dot must refuse"
    assert State(db_path).handled_out_of_band() == {}, "a refusal must write nothing"
    assert cli.cmd_handled(_args(email="nobody@example.test", undo=True)) == 1, \
        "undo with no record must refuse cleanly (exit 1), not traceback"
    assert cli.cmd_handled(
        _args(email="x@example.test", at="last tuesday")
    ) == 2, "an unparseable --at must refuse"
    assert cli.cmd_handled(
        _args(email="x@example.test", account_switched=True)
    ) == 2, "--account must not redirect the record"
    assert cli.cmd_handled(
        _args(email="x@example.test", at="2099-01-01")
    ) == 2, "a future moment is a permanent ignore in disguise — it must refuse"
    assert State(db_path).handled_out_of_band() == {}, "a refusal must write nothing"
    assert calls == [], f"a refusal must not touch the engine: {calls}"

    # …but TODAY is legitimate, and a date-only value is the END of its day —
    # so the future guard must not reject the commonest back-dating there is.
    assert cli.cmd_handled(
        _args(email="x@example.test", at=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ) == 0, "--at <today> must be accepted"
    State(db_path).unmark_handled("x@example.test")
    calls.clear()

    # --- the real thing ---
    rc = cli.cmd_handled(
        _args(email="Phoned@example.test", why="chiamato, risolto", at="2026-07-20")
    )
    assert rc == 0, rc
    recs = State(db_path).handled_out_of_band()
    assert set(recs) == {"phoned@example.test"}, recs
    # 'YYYY-MM-DD' means the END of that market-local day: a call at 15:00 must
    # cover the mail that arrived at 10:00 the same morning.
    assert recs["phoned@example.test"]["handled_at"] == _time.parse_moment("2026-07-20", TZ)
    assert recs["phoned@example.test"]["handled_at"] > datetime(
        2026, 7, 20, 18, 0, tzinfo=timezone.utc
    ), recs

    assert calls[0][0] == "tasks.list", calls
    assert calls[0][1].get("include_completed") is False, calls[0]
    closes = [c for c in calls if c[0] == "tasks.complete"]
    assert len(closes) == 2, f"both of this contact's open tasks must close: {closes}"
    assert {c[1]["task_id"] for c in closes} == {"t-1", "t-2"}, closes
    assert all(c[1]["actor"] == "human" for c in closes), closes
    assert all("chiamato, risolto" in c[1]["why"] for c in closes), closes
    assert all("t-3" != c[1]["task_id"] for c in closes), \
        "another contact's task must never be closed"

    # --- idempotent: a second run is a no-op-shaped update, never an error ---
    calls.clear()
    assert cli.cmd_handled(_args(email="phoned@example.test", why="richiamato")) == 0
    recs2 = State(db_path).handled_out_of_band()
    assert len(recs2) == 1, recs2
    assert recs2["phoned@example.test"]["reason"] == "richiamato", recs2
    assert [c for c in calls if c[0] == "tasks.complete"], \
        "re-running must retry the ledger close (the engine may have been down)"

    # --- bare `cs handled` lists what is on record ---
    calls.clear()
    assert cli.cmd_handled(_args()) == 0
    assert calls == [], "listing must not touch the engine"

    # --- undo ---
    assert cli.cmd_handled(_args(email="phoned@example.test", undo=True)) == 0
    assert State(db_path).handled_out_of_band() == {}
    assert calls == [], "undo must not touch the engine (it cannot un-close a task)"
    print("OK: cs handled — refusals, record, actor=human task close, idempotence, undo")


# ------------------------------------------------------------- sweep wiring


def _wiring(db_path: str) -> None:
    """The pure logic can be perfect and the verb still nag: what matters is
    that `sweep()` reads the ledger and hands it to the open-logic."""
    from cs import gmail_archive

    settings = _settings(db_path)
    inbound = [
        {"email": "phoned@example.test", "name": "P", "date": _dt(36), "subject": "aiuto"},
        {"email": "cold@example.test", "name": "C", "date": _dt(4), "subject": "ciao"},
    ]
    gmail_archive.inbound_recent = lambda s, days: inbound
    gmail_archive.sent_recent = lambda s, days: []

    st = State(db_path)
    st.mark_handled("phoned@example.test", reason="chiamato", handled_at=_dt(33))

    d = unanswered.sweep(settings, days=14)
    assert [r["email"] for r in d["open"]] == ["cold@example.test"], d["open"]
    assert [r["email"] for r in d["handled"]] == ["phoned@example.test"], d["handled"]
    assert d["handled"][0]["handled_reason"] == "chiamato", d["handled"][0]
    assert unanswered.open_threads(settings, days=14) == d["open"]

    # suppression still applies on top, and it is still a different list
    st.suppress("cold@example.test", "asked to be left alone")
    d2 = unanswered.sweep(settings, days=14)
    assert d2["open"] == [], d2["open"]
    assert [r["email"] for r in d2["handled"]] == ["phoned@example.test"], d2["handled"]
    print("OK: sweep() feeds the ledger into the open-logic (and still honours suppression)")


def _review(db_path: str) -> None:
    """`cs review` is where the operator looks when he sits down: the record has
    to be THERE, with its date and reason, or the filter is invisible."""
    from cs import campaign, gmail_drafts, review

    settings = _settings(db_path)
    settings.log_path = Path(db_path).parent / "no-such.log"
    State(db_path).mark_handled(
        "phoned@example.test", reason="chiamato, risolto", handled_at=_dt(33)
    )
    gmail_drafts.list_drafts = lambda s: []
    campaign.list_campaigns = lambda s: []
    rpc.call_sync = lambda *a, **k: []

    d = review.gather(settings)
    assert d["handled_out_of_band"] == [
        {
            "email": "phoned@example.test",
            "handled_at": _dt(33),
            "handled_on": _time.local_date(_dt(33), TZ),
            "reason": "chiamato, risolto",
        }
    ], d["handled_out_of_band"]
    text = review.render(d)
    assert "phoned@example.test" in text and "chiamato, risolto" in text, text
    assert _time.local_date(_dt(33), TZ) in text, \
        "the date must be the operator's own calendar day, not the UTC one"
    assert "--undo" in text, "the digest must say how to put one back"
    print("OK: cs review shows what stopped being raised, and how to undo it")


def _moments() -> None:
    assert _time.parse_moment("2026-07-20", TZ) == datetime(
        2026, 7, 20, 21, 59, 59, tzinfo=timezone.utc
    ), _time.parse_moment("2026-07-20", TZ)  # 23:59:59 CEST = 21:59:59Z
    assert _time.parse_moment("2026-07-20T09:30", TZ) == datetime(
        2026, 7, 20, 7, 30, tzinfo=timezone.utc
    ), "a naive time is the operator's own clock, not UTC"
    assert _time.parse_moment("2026-07-20T09:30+00:00", TZ) == datetime(
        2026, 7, 20, 9, 30, tzinfo=timezone.utc
    ), "an explicit offset is taken as given"
    for bad in ("", "   ", "last tuesday", "20/07/2026"):
        try:
            _time.parse_moment(bad, TZ)
        except ValueError:
            pass
        else:
            raise AssertionError(f"parse_moment accepted {bad!r}")
    print("OK: parse_moment — date-only = end of the market day, naive = market-local")


def run() -> None:
    _pure()
    _moments()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HOME"] = tmp  # nothing may touch the real state dir
        _ledger(str(Path(tmp) / "ledger.db"))
        _cli(str(Path(tmp) / "cli.db"))
        _wiring(str(Path(tmp) / "wiring.db"))
        _review(str(Path(tmp) / "review.db"))


if __name__ == "__main__":
    run()
