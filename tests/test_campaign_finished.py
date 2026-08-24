#!/usr/bin/env python3
"""A finished campaign delivers NOTHING, on any path.

Why this exists (2026-08-23, a live clone): the autonomous operator was handed
26 `send_sms` items for a migration campaign that had ended on 31 July. The
pack said so in two places — `status` had simply never been flipped, and
`dates = "2026-07-22..31"` was documented in the loader as "prose: when it
ran" — and NOTHING read either one. The SMS would have told 26 real customers
their phone number changes at a moment three weeks in the past. The tick
recognised the contradiction and wrote `CS_PAUSE`; the kill switch worked, but
the work should never have been offered. The sibling pack had said
`status = "done"` since June and would have delivered identically, saved only
by being excluded BY NAME in that clone's manifest — a per-clone workaround for
a runner with no notion of a campaign being over.

The two gates, and why they are shaped this way:

`status` (active | done) is the primary gate and the one a human sets. An
unrecognised value refuses at LOAD: it decides whether a campaign may send at
all, so guessing is not available to it.

`ends_on` is the backstop for the day nobody flips `status` — which is exactly
what happened. It is a NEW typed field rather than a parser over `dates`,
deliberately: `dates` legitimately holds free prose (a live pack reads
`continuous from 2026-08`), so a parser over it must either half-work — and a
half-working gate on a send path is worse than none — or refuse a value that
was never meant to be a date and break a running campaign. Typed field, prose
field, one job each. An unreadable `ends_on` refuses at load, because "cannot
parse, so no limit" is how this whole class of bug survives.

A pack with no `ends_on` at all keeps delivering for ever: the open-ended
onboarding loop is a real shape and must not acquire an expiry by accident.
It carries an advisory instead, so "nobody said" stays distinguishable from
"deliberately never".

Hermetic: a neutral trial pack in a tmp dir, `cs.rpc.call_sync` and the Gmail
ground truth stubbed. No engine, no mailbox, no network, nothing sent.
"""
from __future__ import annotations

import os
import tempfile
import types
from datetime import date, datetime
from pathlib import Path

from cs import campaign, campaign_pack, config, gmail_archive, rpc

# Neutral names — this is the kernel, and a company literal fails the charter
# grep gate. The SHAPE is the incident's: a fixed-template migration pack with
# a first notice, a reminder and an SMS.
PACK = "vendor-migration"
ENDED_ON = date(2026, 7, 31)

CAMPAIGN_TOML = """\
[pack]
kind = "fixed-template"
description = "trial pack for the end-of-campaign gate"
campaign = "%s"
status = "%s"
dates = "2026-07-22..31"
%s
[windows]
reminder_after_hour = 0
sms_hour = 0
reminder_max = 3
"""

MAIL_FIRST = "Subject: Your number moves\n\nCiao {name}, il numero cambia.\n"
MAIL_REMINDER = "Subject: Reminder for {name}\n\nCiao {name}, promemoria.\n"
SMS_TXT = "Reminder {name}: check your mail.\n"

# Each delivery path applies to a contact in a different state, so the control
# case ("an active pack delivers") has to meet each one where it lives:
# send_first is the FIRST notice and refuses a contact already `sent`; the pack
# senders apply only to `sent`; the composed-draft paths carry their copy on
# the contact row.
PATH_STATE = {
    "send_first": "queued",
    "send_reminder": "sent",
    "send_sms": "sent",
    "send_draft": "drafted",
    "queue_draft": "drafted",
}
DRAFT_PATHS = ("send_draft", "queue_draft")


def _write_pack(base: Path, *, status: str = "active", ends_on: str | None = None,
                name: str = PACK) -> Path:
    """A complete, sendable pack — so that every refusal below is the
    end-of-campaign gate and never a missing template."""
    pdir = base / name
    pdir.mkdir(parents=True, exist_ok=True)
    ends_line = f"ends_on = {ends_on}\n" if ends_on is not None else ""
    (pdir / "campaign.toml").write_text(
        CAMPAIGN_TOML % (name, status, ends_line), encoding="utf-8"
    )
    (pdir / "mail_first.md").write_text(MAIL_FIRST, encoding="utf-8")
    (pdir / "mail_reminder.md").write_text(MAIL_REMINDER, encoding="utf-8")
    (pdir / "sms.txt").write_text(SMS_TXT, encoding="utf-8")
    return pdir


def _settings():
    """A settings stand-in carrying only what the campaign paths read. SMS is
    ON and CS_PAUSE points at a path that does not exist, so nothing else can
    account for a refusal."""
    ns = types.SimpleNamespace(
        excluded_campaign="", dedup_days=30, timezone="Europe/Rome",
        sms_hour=0, reminder_max=3, cs_triage_mode="send",
        sms_enabled=True, sms_proxy_base="https://sms.invalid/send",
        email_address="", db_path=":memory:",
        pause_path=Path("/nonexistent/CS_PAUSE"),
    )
    ns.excluded_campaign_set = config.Settings.excluded_campaign_set.fget(ns)
    return ns


def _stub_engine(*, state: str = "sent", replied: bool = False) -> None:
    """One campaign, one contact with an Italian mobile (so the SMS branch is
    reachable) and no reminder/SMS stamp (so the day guards are open)."""

    def fake_call_sync(settings, method, params, timeout=None):
        if method == "campaign.list":
            return [{"id": "camp-1", "name": PACK}]
        if method == "campaign.contacts":
            c = {"id": "contact-1", "email": "person@example.test",
                 "state": state, "created_at": "2026-07-22T08:00:00Z",
                 "sent_at": "2026-07-22T09:00:00Z",
                 "dossier": {"phone": "+393331234567", "name": "Anna"}}
            if state == "drafted":
                c["draft_subject"] = "Ciao"
                c["draft_body"] = "Un messaggio abbastanza lungo da superare il guard."
            return [c]
        raise AssertionError(f"unexpected RPC: {method} {params}")

    rpc.call_sync = fake_call_sync
    # Gmail is the reply/dedup ground truth and is not what this file is about:
    # unless a case asks for a reply, nobody has replied and nothing is in
    # Sent, so the ONLY variable left is whether the campaign is over.
    inbound = [{"date": "2026-08-22T10:00:00Z"}] if replied else []
    gmail_archive.inbound_since = lambda settings, email, after=None: list(inbound)
    gmail_archive.sent_to = lambda settings, email, days: []


def _at(day: str) -> datetime:
    """Noon UTC on `day` — inside every window this file's pack declares."""
    return datetime.fromisoformat(f"{day}T12:00:00+00:00")


DURING = _at("2026-07-25")     # inside the campaign
AFTER = _at("2026-08-23")      # the day of the incident


def _call(label: str, settings, now: datetime) -> dict:
    """Invoke one delivery path the way a headless tick or a hand-typed contact
    id reaches it — by contact id, never through `pending()`."""
    _stub_engine(state=PATH_STATE[label])
    fn = getattr(campaign, label)
    return fn(settings, "contact-1", commit=False, now=now)


def _run_all(settings, now: datetime) -> dict:
    return {label: _call(label, settings, now) for label in PATH_STATE}


# --------------------------------------------------------------- loader gates


def test_status_vocabulary() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td, "campaigns")
        for good in campaign_pack.STATUSES:
            pack = campaign_pack.load_pack(_write_pack(base, status=good))
            assert pack.status == good, pack.status

        # An unknown word REFUSES at load. Silently treating it as active is
        # the failure this gate exists for; treating it as done would silently
        # stop a running campaign, which is no better.
        for bad in ("finished", "Active", "paused", "closed", "true", ""):
            _write_pack(base, status=bad)
            try:
                campaign_pack.load_pack(base / PACK)
            except campaign_pack.PackError as e:
                assert "status" in str(e) and repr(bad) in str(e), e
            else:
                raise AssertionError(f"status={bad!r} must raise PackError")

        # A pack with NO status key at all is a pack nobody has finished —
        # every pack written before this gate existed keeps working.
        pdir = base / PACK
        (pdir / "campaign.toml").write_text(
            '[pack]\nkind = "fixed-template"\ncampaign = "%s"\n' % PACK,
            encoding="utf-8",
        )
        assert campaign_pack.load_pack(pdir).status == "active"
    print("OK: status is active|done, an unknown value refuses at load")


def test_ends_on_parsing() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td, "campaigns")

        # A TOML date literal — the intended shape, validated by the parser.
        pack = campaign_pack.load_pack(_write_pack(base, ends_on="2026-07-31"))
        assert (pack.ends_on, pack.ends_on_declared) == (ENDED_ON, True), pack
        # The same date as a string, for anyone who quotes it out of habit.
        pack = campaign_pack.load_pack(_write_pack(base, ends_on='"2026-07-31"'))
        assert (pack.ends_on, pack.ends_on_declared) == (ENDED_ON, True), pack
        # Deliberately open-ended: DECLARED, and no date.
        pack = campaign_pack.load_pack(_write_pack(base, ends_on='"never"'))
        assert (pack.ends_on, pack.ends_on_declared) == (None, True), pack
        # Absent: also no date, but NOT declared — the difference the advisory
        # is built on.
        pack = campaign_pack.load_pack(_write_pack(base, ends_on=None))
        assert (pack.ends_on, pack.ends_on_declared) == (None, False), pack

        # Unreadable values refuse LOUDLY. "cannot parse, so no limit" is
        # exactly how a finished campaign keeps delivering.
        for bad in ('"2026-07-32"', '"31 July 2026"', '"continuous from 2026-08"',
                    '""', '"soon"', "31", "true"):
            _write_pack(base, ends_on=bad)
            try:
                campaign_pack.load_pack(base / PACK)
            except campaign_pack.PackError as e:
                assert "ends_on" in str(e), e
            else:
                raise AssertionError(f"ends_on = {bad} must raise PackError")
    print('OK: ends_on takes a date or "never"; anything else refuses at load')


def test_dates_is_prose_and_gates_nothing() -> None:
    """The deliberate non-feature: `dates` is not parsed, in either direction.

    A live pack carries `dates = "continuous from 2026-08"`. Any parser strict
    enough to be trusted on a send path would refuse that value and break a
    running campaign; any parser lax enough to accept it would be guessing.
    """
    with tempfile.TemporaryDirectory() as td:
        base = Path(td, "campaigns")
        pdir = _write_pack(base, status="active", ends_on=None)
        # `dates` names a range that ended a month ago; with no ends_on the
        # pack still delivers, and says nothing about the prose.
        pack = campaign_pack.load_pack(pdir)
        assert pack.dates == "2026-07-22..31"
        assert pack.delivery_refusal(AFTER.date()) is None

        # Free prose loads fine — it is never a parse target.
        (pdir / "campaign.toml").write_text(
            '[pack]\nkind = "fixed-template"\ncampaign = "%s"\n'
            'dates = "continuous from 2026-08"\n' % PACK,
            encoding="utf-8",
        )
        assert campaign_pack.load_pack(pdir).dates == "continuous from 2026-08"
    print("OK: dates stays prose — never parsed, never a gate")


def test_effective_status_and_the_advisory() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td, "campaigns")

        active = campaign_pack.load_pack(_write_pack(base, ends_on='"never"'))
        assert active.effective_status(AFTER.date()) == "active"
        assert active.delivery_refusal(AFTER.date()) is None
        assert active.undeclared_end_note() is None, '"never" IS a declaration'

        dated = campaign_pack.load_pack(_write_pack(base, ends_on="2026-07-31"))
        assert dated.effective_status(DURING.date()) == "active"
        # The last day is still IN the campaign — a campaign ending on the 31st
        # runs on the 31st.
        assert dated.effective_status(ENDED_ON) == "active"
        assert dated.delivery_refusal(ENDED_ON) is None
        assert dated.effective_status(date(2026, 8, 1)) == "ended"
        assert dated.effective_status(AFTER.date()) == "ended"

        done = campaign_pack.load_pack(_write_pack(base, status="done"))
        assert done.effective_status(DURING.date()) == "done"
        assert done.undeclared_end_note() is None, "a finished pack is not nagged"

        undeclared = campaign_pack.load_pack(_write_pack(base, ends_on=None))
        note = undeclared.undeclared_end_note()
        assert note and "ends_on" in note and PACK in note, note
        assert undeclared.delivery_refusal(AFTER.date()) is None, (
            "an undeclared end must NOT become an expiry — the open-ended "
            "onboarding loop delivers indefinitely by design"
        )

        # The refusal names the reason AND the date, both cases.
        ended_reason = dated.delivery_refusal(AFTER.date())
        assert "2026-07-31" in ended_reason and "2026-08-23" in ended_reason, ended_reason
        done_reason = done.delivery_refusal(AFTER.date())
        assert "done" in done_reason and "2026-08-23" in done_reason, done_reason

        # `cs campaign packs` reads the EFFECTIVE status: a listing that still
        # says "active" for a pack every send path refuses is a trap.
        assert dated.summary(AFTER.date())["effective_status"] == "ended"
        assert dated.summary(AFTER.date())["delivers"] is False
        assert active.summary(AFTER.date())["ends_on"] == campaign_pack.ENDS_ON_NEVER
        assert undeclared.summary(AFTER.date())["ends_on"] is None
    print("OK: effective status, the last-day boundary, and a dated refusal")


# ------------------------------------------------------- every delivery path


def test_active_pack_delivers() -> None:
    """The control. Without it, every refusal below could be a broken fixture."""
    settings = _settings()
    for label, res in _run_all(settings, DURING).items():
        assert res.get("ok") is True, (label, res)
        assert res.get("dry_run") is True, (label, res)
        assert "finished" not in res, (label, res)

    _stub_engine()
    entry = campaign.pending(settings, now=DURING)["campaigns"][0]
    assert {i["action"] for i in entry["items"]} == {"send_sms"}, entry
    assert "delivery_blocked" not in entry and "held" not in entry, entry
    print("OK: an active pack delivers on all five paths; the worklist offers work")


def test_done_pack_refuses_everywhere() -> None:
    settings = _settings()
    for label, res in _run_all(settings, DURING).items():
        assert res.get("ok") is False, (label, res)
        assert res.get("finished") is True, (label, res)
        assert "is finished" in res["error"], (label, res)
        assert "2026-07-25" in res["error"], (label, res)
    print("OK: status=done refuses on all five delivery paths, with the date")


def test_expired_pack_refuses_while_still_active() -> None:
    """THE case that actually bit: `status` still says active, and the date is
    three weeks past."""
    settings = _settings()
    for label, res in _run_all(settings, AFTER).items():
        assert res.get("ok") is False, (label, res)
        assert res.get("finished") is True, (label, res)
        assert "2026-07-31" in res["error"], (label, res)
        assert "2026-08-23" in res["error"], (label, res)
    # ... and the same pack was still delivering before it ended, so the gate
    # is the date and not the fixture.
    for label, res in _run_all(settings, DURING).items():
        assert res.get("ok") is True, (label, res)
    print("OK: an expired pack refuses even while status says active")


def test_open_ended_pack_delivers_indefinitely() -> None:
    settings = _settings()
    for label, res in _run_all(settings, _at("2031-01-02")).items():
        assert res.get("ok") is True, (label, res)
        assert "finished" not in res, (label, res)
    print("OK: a pack with no end date delivers indefinitely")


def test_pending_holds_deliveries_and_says_so() -> None:
    """The worklist must REFUSE VISIBLY: a contact that silently vanishes is
    the failure mode this gate exists to stop."""
    settings = _settings()
    _stub_engine()
    entry = campaign.pending(settings, now=AFTER)["campaigns"][0]
    assert entry["items"] == [], entry
    assert entry["held"] == {"send_sms": 1}, entry
    assert "2026-07-31" in entry["delivery_blocked"], entry
    assert "2026-08-23" in entry["delivery_blocked"], entry

    # A reply is NOT a delivery: a human who wrote to us is owed an answer
    # whether or not the campaign that prompted the mail is over.
    _stub_engine(replied=True)
    entry = campaign.pending(settings, now=AFTER)["campaigns"][0]
    assert [i["action"] for i in entry["items"]] == ["handle_reply"], entry
    assert "held" not in entry, entry
    assert entry["delivery_blocked"], entry
    print("OK: pending() holds the sends, names the reason, keeps the replies")


def test_pending_reports_an_undeclared_end() -> None:
    settings = _settings()
    _stub_engine()
    entry = campaign.pending(settings, now=AFTER)["campaigns"][0]
    assert "delivery_blocked" not in entry, entry
    assert {i["action"] for i in entry["items"]} == {"send_sms"}, entry
    assert "ends_on" in entry["pack_note"], entry
    print("OK: an active pack with no declared end delivers, and is reported")


def test_broken_pack_is_not_evidence_of_a_running_campaign() -> None:
    """A pack that cannot be LOADED must not be read as "no pack, therefore no
    end date" — the broken part may well be the status line itself."""
    settings = _settings()
    for label, res in _run_all(settings, DURING).items():
        assert res.get("ok") is False, (label, res)
        assert "pack error" in res["error"], (label, res)
    print("OK: an unloadable pack refuses every delivery path")


def test_no_pack_at_all_is_unchanged() -> None:
    """A campaign with no pack declares nothing about its own lifetime. The
    fixed-template senders still refuse it (no copy); the composed-draft paths,
    whose copy is on the contact row, still work — this gate must not
    accidentally require a pack where none was ever needed."""
    settings = _settings()
    results = _run_all(settings, DURING)
    for label in ("send_first", "send_reminder", "send_sms"):
        res = results[label]
        assert res.get("skipped") is True, (label, res)
        assert "NO CAMPAIGN PACK" in res["error"], (label, res)
    for label in DRAFT_PATHS:
        assert results[label].get("ok") is True, (label, results[label])
    print("OK: a campaign with no pack behaves exactly as before")


# --------------------------------------------------------------------- driver


def _in_pack_dir(fn, **pack_kwargs) -> None:
    """Run `fn` with $CS_CAMPAIGNS_DIR pointing at a freshly written pack —
    which is how the real senders find it (`campaign_pack.packs_dir`).
    `shape="none"` writes no pack at all; `shape="broken"` writes one that
    cannot be loaded."""
    shape = pack_kwargs.pop("shape", "pack")
    with tempfile.TemporaryDirectory() as td:
        base = Path(td, "campaigns")
        base.mkdir(parents=True)
        if shape == "broken":
            pdir = base / PACK
            pdir.mkdir()
            (pdir / "campaign.toml").write_text(
                '[pack]\nkind = "fixed-template"\ncampaign = "%s"\n'
                'status = "nonsense"\n' % PACK, encoding="utf-8")
        elif shape == "pack":
            _write_pack(base, **pack_kwargs)
        old = os.environ.get("CS_CAMPAIGNS_DIR")
        os.environ["CS_CAMPAIGNS_DIR"] = str(base)
        try:
            fn()
        finally:
            if old is None:
                os.environ.pop("CS_CAMPAIGNS_DIR", None)
            else:
                os.environ["CS_CAMPAIGNS_DIR"] = old


def main() -> int:
    test_status_vocabulary()
    test_ends_on_parsing()
    test_dates_is_prose_and_gates_nothing()
    test_effective_status_and_the_advisory()

    _in_pack_dir(test_active_pack_delivers, ends_on='"never"')
    _in_pack_dir(test_done_pack_refuses_everywhere, status="done", ends_on='"never"')
    _in_pack_dir(test_expired_pack_refuses_while_still_active, ends_on="2026-07-31")
    _in_pack_dir(test_open_ended_pack_delivers_indefinitely, ends_on='"never"')
    _in_pack_dir(test_pending_holds_deliveries_and_says_so, ends_on="2026-07-31")
    _in_pack_dir(test_pending_reports_an_undeclared_end, ends_on=None)
    _in_pack_dir(test_broken_pack_is_not_evidence_of_a_running_campaign, shape="broken")
    _in_pack_dir(test_no_pack_at_all_is_unchanged, shape="none")

    print("test_campaign_finished: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
