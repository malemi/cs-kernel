#!/usr/bin/env python3
"""`cs escalated` — "a human is personally writing to this one", and every
surface that could write to them obeys it.

Why this gate exists: the owner was mid-conversation with two customers,
writing to them himself. Gmail Sent shows no reply from us yet, so the
Sent-anchored sweep counted both as unanswered work and the two-hourly headless
operator — which answers customers itself — kept preparing a second reply. Two
hands writing to the same customer is the failure this operator exists to
avoid, and the only states on offer were "resolved" (a lie: nothing was
resolved) and "nothing" (the collision).

Asserted here:

  1. an escalated sender leaves the OPEN list and comes back in its own bucket
     with the owner, the reason and the AGE of the takeover;
  2. a NEWER inbound does NOT release it — the asymmetry with `handled`, and
     the whole point: the customer replying to the human who took the thread
     over is that same conversation, so expiring there would re-arm the
     collision on the very event that causes it;
  3. `handled` WINS over an escalation and clears it — a thread cannot be both
     over and still being written;
  4. the verb is dry-run until `--commit`, in both directions, and a dry run
     writes nothing;
  5. it NEVER touches the engine: the task stays open, because the work is not
     done and the task is the only durable trace that somebody owes an answer;
  6. refusals (a mistyped address, `--account`, an undo with no record) are
     clean and write nothing;
  7. every surface that hides an escalated contact also PRINTS it, aged:
     `unanswered`, `review`, `dossier` (whose verdict flips to STOP);
  8. no automated outbound reaches them — the producer worklist skips them with
     a counted reason, and the campaign senders + `pending()` refuse.

Hermetic: a sandbox HOME for the SQLite ledger, stubbed IMAP + RPC. No mailbox,
no engine, no network.
"""
from __future__ import annotations

import os
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cs import _time, campaign, cli, config as cfg, filter as filt, rpc, unanswered
from cs.state import State

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
TZ = "Europe/Rome"


def _dt(days_ago: float) -> datetime:
    return NOW - timedelta(days=days_ago)


def _ago(days: int) -> datetime:
    """A moment `days` whole days before the REAL clock — the surfaces that
    render an age (sweep, review) read `now` themselves and cannot be frozen.
    The extra hour keeps the integer day count off the rounding boundary."""
    return datetime.now(timezone.utc) - timedelta(days=days, hours=1)


def _settings(db_path: str):
    return types.SimpleNamespace(
        db_path=db_path,
        timezone=TZ,
        prog_name="cs",
        email_address="support@example.test",
        self_email_set=set(),
        self_uid_set=set(),
        system_sender_set=set(),
        dedup_days=30,
        excluded_campaign_set=set(),
        cs_triage_mode="draft",
        sms_hour=18,
        reminder_max=3,
        pause_path=Path(db_path).parent / "no-such-CS_PAUSE",
    )


# --------------------------------------------------------------- pure logic


def _pure() -> None:
    inbound = [
        # the owner is writing to this one himself
        {"email": "Mine@example.test", "name": "Mine", "date": _dt(6),
         "subject": "non risolto"},
        # …and they wrote AGAIN afterwards: still his, that is the same
        # conversation continuing
        {"email": "wroteback@example.test", "name": "Wrote", "date": _dt(1),
         "subject": "ti risponde?"},
        {"email": "wroteback@example.test", "name": "Wrote", "date": _dt(9),
         "subject": "problema"},
        {"email": "cold@example.test", "name": "Cold", "date": _dt(4),
         "subject": "hello?"},
    ]
    taken = {
        "mine@example.test": {"owner": "", "reason": "sto scrivendo io",
                              "escalated_at": _dt(3)},
        "WroteBack@example.test": {"owner": "Andrea", "reason": "",
                                   "escalated_at": _dt(3)},
    }

    rows = unanswered.compute_open(inbound, [], set(), set(), NOW, None, taken)
    emails = [r["email"] for r in rows]
    assert emails == ["cold@example.test"], \
        f"an escalated sender must leave the open list: {emails}"

    mine = unanswered.compute_escalated(inbound, [], set(), set(), NOW, None, taken)
    by_email = {r["email"]: r for r in mine}
    assert set(by_email) == {"mine@example.test", "wroteback@example.test"}, by_email
    assert by_email["wroteback@example.test"]["escalated_owner"] == "Andrea", by_email
    assert by_email["mine@example.test"]["escalated_reason"] == "sto scrivendo io"
    assert by_email["mine@example.test"]["days_escalated"] == 3, \
        "the row must carry the age of the TAKEOVER, not only the customer's wait"
    assert by_email["mine@example.test"]["days_waiting"] == 6, by_email
    assert by_email["wroteback@example.test"]["days_waiting"] == 1, \
        "a newer inbound must NOT release the contact (the handled asymmetry)"

    # absent map == no map at all: the argument is optional and must not move a
    # single verdict on its own
    assert unanswered.compute_open(inbound, [], set(), set(), NOW) == \
        unanswered.compute_open(inbound, [], set(), set(), NOW, None, {}), \
        "an empty escalated map must be identical to no map at all"
    assert len(unanswered.compute_open(inbound, [], set(), set(), NOW)) == 3

    # handled BEATS escalated: closing a thread you had taken over settles it
    handled = {"mine@example.test": _dt(3)}
    held = unanswered.compute_handled(inbound, [], set(), set(), NOW, handled, taken)
    assert [r["email"] for r in held] == ["mine@example.test"], held
    assert "mine@example.test" not in [
        r["email"]
        for r in unanswered.compute_escalated(inbound, [], set(), set(), NOW, handled, taken)
    ], "a handled record must win over a stale takeover, not double-report it"

    # a reply of ours after their last inbound still closes them, record or not
    sent = [{"to": ["mine@example.test"], "date": _dt(0.5)}]
    assert unanswered.compute_escalated(inbound, sent, set(), set(), NOW, None, taken) == [
        r for r in mine if r["email"] != "mine@example.test"
    ]
    print("OK: compute_open/compute_escalated — own bucket, no expiry, handled wins")


# ------------------------------------------------------------------- state


def _ledger(db_path: str) -> None:
    st = State(db_path)
    assert st.escalated_to_human() == {}
    assert st.escalated_set() == set()

    st.mark_escalated("Mine@example.test", owner="", reason="sto scrivendo io",
                      escalated_at=_dt(3))
    recs = st.escalated_to_human()
    assert set(recs) == {"mine@example.test"}, recs
    assert recs["mine@example.test"]["escalated_at"] == _dt(3), recs
    assert recs["mine@example.test"]["reason"] == "sto scrivendo io"
    assert recs["mine@example.test"]["owner"] == ""
    assert st.escalated_set() == {"mine@example.test"}

    # idempotent: twice is not an error, and the newer moment wins
    st.mark_escalated("mine@example.test", owner="Andrea", escalated_at=_dt(1))
    recs = st.escalated_to_human()
    assert len(recs) == 1, recs
    assert recs["mine@example.test"]["escalated_at"] == _dt(1), recs
    assert recs["mine@example.test"]["owner"] == "Andrea", recs

    # NOT a suppression list: we very much want to keep talking to them
    assert st.do_not_contact_set() == set(), st.do_not_contact_set()

    # resolving it clears it — enforced in the store, so no caller can leave a
    # "with you" label ageing on a thread that is over
    st.mark_handled("mine@example.test", reason="risolto al telefono")
    assert st.escalated_to_human() == {}, \
        "mark_handled must clear the takeover record"
    assert set(st.handled_out_of_band()) == {"mine@example.test"}

    st.mark_escalated("mine@example.test")
    assert st.unmark_escalated("mine@example.test") is True
    assert st.escalated_to_human() == {}
    assert st.unmark_escalated("mine@example.test") is False, \
        "releasing a contact that was never taken must report False"
    print("OK: state ledger — owner+reason+age, idempotent, cleared by handled")


# --------------------------------------------------------------------- CLI


def _cli(db_path: str) -> None:
    settings = _settings(db_path)
    cfg.load = lambda: settings
    calls: list[tuple] = []

    def fake_call_sync(_settings, method, params=None, timeout=None):
        calls.append((method, params))
        return []

    rpc.call_sync = fake_call_sync

    def _args(**kw):
        base = dict(email=None, why=None, who=None, undo=False, commit=False)
        base.update(kw)
        return types.SimpleNamespace(**base)

    # --- refusals first: nothing must be written by a bad call ---
    assert cli.cmd_escalated(_args(email="Camorali", commit=True)) == 2, \
        "a non-address must refuse"
    assert cli.cmd_escalated(_args(email="a@b", commit=True)) == 2, \
        "a domain with no dot must refuse"
    assert cli.cmd_escalated(
        _args(email="x@example.test", commit=True, account_switched=True)
    ) == 2, "--account must not redirect the record"
    assert cli.cmd_escalated(
        _args(email="nobody@example.test", undo=True, commit=True)
    ) == 1, "releasing a contact with no record must refuse cleanly (exit 1)"
    assert State(db_path).escalated_to_human() == {}, "a refusal must write nothing"

    # --- dry run is the default, in BOTH directions ---
    assert cli.cmd_escalated(_args(email="mine@example.test", why="sto scrivendo io")) == 0
    assert State(db_path).escalated_to_human() == {}, \
        "without --commit nothing may be written"

    # --- the real thing ---
    assert cli.cmd_escalated(
        _args(email="Mine@example.test", why="sto scrivendo io", commit=True)
    ) == 0
    recs = State(db_path).escalated_to_human()
    assert set(recs) == {"mine@example.test"}, recs
    assert recs["mine@example.test"]["reason"] == "sto scrivendo io", recs
    assert recs["mine@example.test"]["owner"] == "", recs
    assert calls == [], \
        "escalated must NOT touch the engine: the task stays open, the work is not done"

    # --who names somebody else
    assert cli.cmd_escalated(
        _args(email="other@example.test", who="Andrea", commit=True)
    ) == 0
    assert State(db_path).escalated_to_human()["other@example.test"]["owner"] == "Andrea"

    # --- bare `cs escalated` lists what is on record ---
    assert cli.cmd_escalated(_args()) == 0
    assert calls == [], "listing must not touch the engine"

    # --- undo: dry-run first, then commit ---
    assert cli.cmd_escalated(_args(email="mine@example.test", undo=True)) == 0
    assert "mine@example.test" in State(db_path).escalated_to_human(), \
        "an undo without --commit must not release the contact"
    assert cli.cmd_escalated(_args(email="mine@example.test", undo=True, commit=True)) == 0
    assert "mine@example.test" not in State(db_path).escalated_to_human()
    assert calls == [], "undo must not touch the engine either"

    # --- `cs handled` on a taken-over contact clears it, and says so ---
    def tasks_call_sync(_settings, method, params=None, timeout=None):
        calls.append((method, params))
        return [] if method == "tasks.list" else {"ok": True}

    rpc.call_sync = tasks_call_sync
    State(db_path).mark_escalated("other@example.test", owner="Andrea")
    hargs = types.SimpleNamespace(
        email="other@example.test", why="risolto al telefono", at=None, undo=False
    )
    assert cli.cmd_handled(hargs) == 0
    assert State(db_path).escalated_to_human() == {}, \
        "handled must clear the takeover — the thread is over"
    print("OK: cs escalated — refusals, dry-run default, no engine write, undo, handled clears")


# ------------------------------------------------------------- sweep wiring


def _wiring(db_path: str) -> None:
    """The pure logic can be perfect and the tick still write to the customer:
    what matters is that `sweep()` reads the ledger and hands it to the
    open-logic."""
    from cs import gmail_archive

    settings = _settings(db_path)
    inbound = [
        {"email": "mine@example.test", "name": "M", "date": _dt(6), "subject": "aiuto"},
        {"email": "cold@example.test", "name": "C", "date": _dt(4), "subject": "ciao"},
    ]
    gmail_archive.inbound_recent = lambda s, days: inbound
    gmail_archive.sent_recent = lambda s, days: []

    State(db_path).mark_escalated("mine@example.test", reason="ci penso io",
                                  escalated_at=_ago(2))

    d = unanswered.sweep(settings, days=14)
    assert [r["email"] for r in d["open"]] == ["cold@example.test"], d["open"]
    assert [r["email"] for r in d["escalated"]] == ["mine@example.test"], d["escalated"]
    assert d["escalated"][0]["escalated_reason"] == "ci penso io", d["escalated"][0]
    assert d["escalated"][0]["days_escalated"] == 2, d["escalated"][0]
    assert d["handled"] == [], d["handled"]
    assert unanswered.open_threads(settings, days=14) == d["open"]

    # the human-readable verb must SAY it, with the age — a contact that just
    # stops appearing is the silent drop this ledger exists to end
    settings_out = _settings(db_path)
    cfg.load = lambda: settings_out
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.cmd_unanswered(types.SimpleNamespace(days=14, json=False))
    text = buf.getvalue()
    assert "cold@example.test" in text
    assert "mine@example.test" in text, \
        "an escalated contact must be printed, not filtered out of existence"
    assert "with you" in text and "ci penso io" in text, text
    assert "not the operator's to answer" in text, \
        "the section must say WHY they are not in the list above"
    assert "--undo" in text, "the output must say how to hand one back"

    # …but the machine feed must NOT carry them: that list is what the headless
    # tick works, and working one is exactly the collision
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.cmd_unanswered(types.SimpleNamespace(days=14, json=True))
    assert "mine@example.test" not in buf.getvalue(), \
        "--json is the tick's work list: an escalated contact must not be in it"
    print("OK: sweep() feeds the ledger; the human sees the row, the tick does not")


def _review(db_path: str) -> None:
    """`cs review` is where the operator asks what there is to do: the answer
    has to include "you are on these", with an age, or an escalation rots."""
    from cs import campaign as campaign_mod, gmail_drafts, review

    settings = _settings(db_path)
    settings.log_path = Path(db_path).parent / "no-such.log"
    State(db_path).mark_escalated("mine@example.test", reason="sto scrivendo io",
                                  escalated_at=_ago(12))
    State(db_path).mark_escalated("other@example.test", owner="Andrea",
                                  escalated_at=_ago(1))
    gmail_drafts.list_drafts = lambda s: []
    campaign_mod.list_campaigns = lambda s: []
    rpc.call_sync = lambda *a, **k: []

    d = review.gather(settings)
    assert [r["email"] for r in d["escalated"]] == [
        "mine@example.test", "other@example.test"
    ], "oldest first — the top row is the one most likely to have been forgotten"
    assert d["escalated"][0]["days"] == 12, d["escalated"][0]
    assert d["escalated"][0]["escalated_on"] == _time.local_date(_ago(12), TZ)
    assert d["escalated"][1]["owner"] == "Andrea", d["escalated"][1]

    text = review.render(d)
    assert "mine@example.test" in text and "sto scrivendo io" in text, text
    assert "Andrea" in text, text
    assert "for 12d" in text, "the digest must carry the age of the takeover"
    assert "with you" in text, "the operator's own rows read as his"
    assert "--undo" in text, "the digest must say how to put one back in play"
    print("OK: cs review answers 'what is there to do' with 'these are yours'")


def _dossier(db_path: str) -> None:
    """The dossier is the mandatory step before ANY contact, so it is the
    chokepoint where an agent that never heard of this verb still learns to
    keep its hands off."""
    import contextlib
    import io

    from cs import crm, gmail_archive

    settings = _settings(db_path)
    cfg.load = lambda: settings
    State(db_path).mark_escalated("mine@example.test", owner="Andrea",
                                  reason="ci parlo io")
    gmail_archive.correspondence = lambda s, e: [
        {"direction": "in", "date": "Mon, 18 Aug 2026 09:00:00 +0200",
         "subject": "non risolto"}
    ]
    gmail_archive.sent_to = lambda s, e, days=30: []
    rpc.call_sync = lambda *a, **k: []
    crm.lookup = lambda s, e: types.SimpleNamespace(
        source="none", rows=[], render_hints=[], note=None,
        as_dict=lambda: {},
    )

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.cmd_dossier(types.SimpleNamespace(email="mine@example.test", dedup_days=30))
    text = buf.getvalue()
    assert "with Andrea" in text, text
    assert "do NOT draft" in text, text
    assert "verdict: STOP" in text, \
        f"the verdict is what an agent reads — it must refuse: {text}"
    assert "ci parlo io" in text, text
    print("OK: cs dossier — the mandatory pre-contact step refuses outright")


# ------------------------------------------------------- no automated mail


def _worklist(db_path: str) -> None:
    """The producer worklist is the other place a mail starts. A template
    landing on a customer the owner is personally writing to is the same
    collision, arriving in a worse register."""
    settings = _settings(db_path)
    st = State(db_path)
    st.mark_escalated("mine@example.test", reason="ci penso io")

    payload = {
        "signups": [
            {"business_id": "b1", "email_address": "Mine@example.test"},
            {"business_id": "b2", "email_address": "cold@example.test"},
        ],
        "cancellations": [],
        "leads": [],
    }
    wl = filt.build_worklist(payload, settings, st)
    assert [b["business_id"] for b in wl["to_contact"]["signup"]] == ["b2"], wl
    assert {"category": "signup", "key": "b1", "reason": "escalated"} in wl["skipped"], \
        "the skip must be COUNTED and named, never a silent disappearance"
    print("OK: cs plan — outreach skips a taken-over contact, with a counted reason")


def _campaign(db_path: str) -> None:
    from cs import gmail_archive

    settings = _settings(db_path)
    State(db_path).mark_escalated("mine@example.test", owner="Andrea")

    contacts = [
        {"id": "c1", "email": "mine@example.test", "state": "drafted",
         "draft_subject": "s", "draft_body": "b", "dossier": {}},
        {"id": "c2", "email": "cold@example.test", "state": "drafted",
         "draft_subject": "s", "draft_body": "b", "dossier": {}},
    ]

    def fake_call_sync(_settings, method, params=None, timeout=None):
        if method == "campaign.list":
            return [{"id": "k1", "name": "trial", "contacts_by_state": {}}]
        if method == "campaign.contacts":
            return contacts
        return {"ok": True}

    rpc.call_sync = fake_call_sync
    # restored explicitly: an earlier case stubbed it away, and `pending` /
    # `_get_contact` both route through it
    campaign.list_campaigns = lambda s: fake_call_sync(s, "campaign.list")
    gmail_archive.sent_to = lambda s, e, days=30: []
    gmail_archive.inbound_since = lambda s, e, after=None: []

    out = campaign.pending(settings, now=NOW)
    entry = out["campaigns"][0]
    actions = {(i["action"], i["email"]) for i in entry["items"]}
    assert ("send_draft", "cold@example.test") in actions, entry
    assert ("send_draft", "mine@example.test") not in actions, \
        "no delivery may be proposed for a taken-over contact"
    assert entry["escalated_hold"] == {"send_draft": 1}, \
        "what was withheld must be counted on the entry, never dropped in silence"

    # an observation stays, tagged with who owns the conversation
    contacts[0]["state"] = "sent"
    gmail_archive.inbound_since = lambda s, e, after=None: [{"date": NOW}]
    entry = campaign.pending(settings, now=NOW)["campaigns"][0]
    replies = [i for i in entry["items"] if i["action"] == "handle_reply"]
    assert [i["email"] for i in replies] == ["mine@example.test"], entry
    assert replies[0]["escalated_to"] == "Andrea", \
        "the reply is real and must still be seen — flagged, not answered"

    # and the senders refuse on their own, for a caller holding a contact_id
    contacts[0]["state"] = "drafted"
    for fn in (campaign.send_draft, campaign.queue_draft):
        res = fn(settings, "c1", commit=True)
        assert res["ok"] is False and "escalated" in res.get("blocked", ""), \
            f"{fn.__name__} must refuse a taken-over contact: {res}"
        res = fn(settings, "c2", commit=False)
        assert res.get("dry_run") is True, f"{fn.__name__} must still work normally: {res}"
    print("OK: campaigns — no delivery, replies flagged, senders refuse independently")


def run() -> None:
    _pure()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HOME"] = tmp  # nothing may touch the real state dir
        _ledger(str(Path(tmp) / "ledger.db"))
        _cli(str(Path(tmp) / "cli.db"))
        _wiring(str(Path(tmp) / "wiring.db"))
        _review(str(Path(tmp) / "review.db"))
        _dossier(str(Path(tmp) / "dossier.db"))
        _worklist(str(Path(tmp) / "worklist.db"))
        _campaign(str(Path(tmp) / "campaign.db"))


if __name__ == "__main__":
    run()
