#!/usr/bin/env python3
"""The send gates read every mailbox — and refuse when one cannot be read.

Until now every gate that decides "have we already written to this person" and
"have they replied" read ONE mailbox: the operator's. A company answers from
several, so a colleague's reply — sent from his own address, with the operator
on no header — was invisible to the check, and the runner composed four drafts
to a prospect a co-founder had answered the next day. Widening the read is only
half the fix. The other half is what a gate does when a mailbox cannot be read,
and there is only one safe answer: refuse, and name the mailbox.

Fail-open would reproduce the incident at machine speed, once per contact,
unattended — an absence of evidence read as evidence of absence. Fail-closed
can halt outreach on one dead credential, and that is the accepted cost: a
contact not written to today is recoverable; a second cold mail to someone a
colleague answered two months ago is not.

What these gates hold:

  1. EVERY sending path refuses when a mailbox in scope cannot be read —
     `send_draft`, `queue_draft`, `send_reminder`, `send_sms` — and each
     refusal NAMES the mailbox and the fix. The refusal comes from the fan-out
     itself, never from a traceback and never from the CLI's engine-error
     handler, which would announce an IMAP failure as "cannot reach the
     engine".
  2. NOTHING is mutated on the way to that refusal: no SMTP connection, no SMS,
     no Gmail draft, no `campaign.update_contact`, no `sends` row. Every one of
     these gates runs before its first write, so a refusal is a clean no-op —
     asserted by making any mutation raise.
  3. `reconcile` refuses too, because "no Sent thread anywhere" is a claim about
     every mailbox and cannot be made from a partial read.
  4. `pending` SURFACES a contact it could not judge as its own item, and never
     as a send candidate. A contact that quietly vanishes from a worklist is
     the incident's own shape one level up: the list looks complete and is
     wrong.
  5. A POSITIVE reading from another mailbox stops the send. This is the
     incident itself, replayed: the operator mailbox holds nothing, a colleague
     wrote to the prospect, and `send_draft` refuses.
  6. ONE IMAP login per mailbox per PROCESS, across the whole gate-heavy run.
     The runner asks the gate once per drafted contact; N mailboxes × M
     contacts logins would make the fan-out unusable, and the session cache is
     what keeps it affordable.
  7. `cs dossier`'s verdict — the mandatory pre-contact check — fails closed
     with the mailbox named, instead of printing "cold contact" from a scope it
     could not read.
  8. The review's draft verdicts widen too, but they do NOT retire a row. An
     unreadable mailbox lands ON THE ROW (`evidence_incomplete`) and is printed
     inside the ready block, where the operator is about to press send — not in
     a footer below the next block, and not only as a note.
  9. The dossier's verdict is about "have we EVER", not about the dedup window.
     A colleague's reply from two months ago, with every mailbox readable, must
     not come back as `cold contact` — that is the incident's own shape
     surviving inside the check meant to prevent it.

No network: `imaplib.IMAP4_SSL` and the engine transport are replaced by
in-process doubles speaking the real protocol shapes and raising the real
exception types.
"""
from __future__ import annotations

import contextlib
import imaplib
import io
import os
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

from cs import campaign as campaign_mod
from cs import cli
from cs import config as config_mod
from cs import draft_state, gmail_drafts, mailboxes
from cs import rpc as rpc_mod
from cs import send_mail, sms
from cs.config import Settings

OPERATOR = "ops@acme.example"
OPERATOR_PW = "operator-app-pw-1111"
COLLEAGUE = "colleague@acme.example"
COLLEAGUE_PW = "colleague-app-pw-2222"
CONTACT = "prospect@customer.example"

NOW = datetime.now(timezone.utc)
PACK = "vendor-migration"

CAMPAIGN_TOML = f"""\
[pack]
kind = "fixed-template"
description = "trial pack for the send-gate fan-out"
campaign = "{PACK}"
status = "active"
dates = "2026-07-22..31"

[windows]
reminder_after_hour = 0
sms_hour = 0
reminder_max = 3
"""


class FakeIMAP:
    """An IMAP server double: special-use LIST, UID SEARCH by TO/FROM, header
    FETCH, and a login that can be refused — which is how a rotated app
    password behaves, and the whole point of these gates."""

    opened: list["FakeIMAP"] = []

    def __init__(self, host, port):
        self.address = None
        self.folder = None
        FakeIMAP.opened.append(self)

    def login(self, address, password):
        box = WORLD.get(address)
        if box is None or box["password"] != password:
            raise imaplib.IMAP4.error(
                f"b'[AUTHENTICATIONFAILED] Invalid credentials for {address}'"
            )
        self.address = address
        return "OK", [b"authenticated"]

    def noop(self):
        return "OK", [b""]

    def list(self):
        return "OK", [
            b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"',
            b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"',
        ]

    def select(self, folder, readonly=True):
        assert readonly, "a gate must never select a mailbox writable"
        self.folder = folder.strip('"')
        return "OK", [b"1"]

    def _rows(self, key, value):
        box = WORLD[self.address]
        return box["sent_to" if key == "TO" else "inbound_from"].get(value, [])

    def uid(self, command, *args):
        if command == "SEARCH":
            _none, key, value = args
            self._last = self._rows(key, value)
            return "OK", [b" ".join(str(i + 1).encode()
                                    for i in range(len(self._last)))]
        if command == "FETCH":
            i = int(args[0].decode()) - 1
            when = self._last[i]
            raw = (
                f"Date: {format_datetime(when)}\r\n"
                f"From: {self.address}\r\n"
                f"To: {CONTACT}\r\n"
                f"Subject: an earlier message\r\n"
                f"Message-ID: <{i}@acme.example>\r\n\r\n"
            ).encode()
            return "OK", [(b"1 (BODY[HEADER])", raw)]
        raise AssertionError(f"unexpected UID command {command}")

    def logout(self):
        return "BYE", [b""]


WORLD: dict[str, dict] = {}


def _world(*, colleague_password: str = COLLEAGUE_PW,
           colleague_wrote: bool = False, wrote_days_ago: int = 3) -> None:
    """The incident's shape: an operator mailbox that never wrote to the
    contact, and a colleague mailbox that may have — or may be unreadable.

    `wrote_days_ago` is the other half of the incident: the real reply was 61
    days old, which is outside every dedup window anyone would set."""
    WORLD.clear()
    WORLD.update({
        OPERATOR: {"password": OPERATOR_PW, "sent_to": {}, "inbound_from": {}},
        COLLEAGUE: {
            "password": colleague_password,
            "sent_to": ({CONTACT: [NOW - timedelta(days=wrote_days_ago)]}
                        if colleague_wrote else {}),
            "inbound_from": {},
        },
    })
    FakeIMAP.opened.clear()
    mailboxes._CREDENTIALS.clear()
    mailboxes._SESSIONS.clear()


def _settings(db_path: str) -> Settings:
    return Settings(
        _env_file=(),
        email_address=OPERATOR,
        email_password=OPERATOR_PW,
        read_mailboxes=COLLEAGUE,
        read_mailbox_passwords=f"{COLLEAGUE}:{COLLEAGUE_PW}",
        engine_owner_uid="uid-ops",
        engine_ws_url="wss://engine.example",
        imap_host="imap.acme.example",
        slug="acme",
        prog_name="acme-cs",
        db_path=db_path,
        cs_triage_mode="send",
        sms_enabled=True,
        sms_proxy_base="https://sms.invalid/send",
        timezone="Europe/Rome",
        sms_hour=0,
        reminder_max=3,
    )


MUTATIONS: list[str] = []


def _contact(state: str) -> dict:
    c = {"id": "c1", "email": CONTACT, "state": state,
         "created_at": "2026-07-22T08:00:00Z", "sent_at": "2026-07-22T09:00:00Z",
         "dossier": {"phone": "+393331234567", "name": "Anna"}}
    if state == "drafted":
        c["draft_subject"] = "Hello"
        c["draft_body"] = "A long enough hand-written note to pass the guard."
    return c


def _engine(state: str, contacts: list[dict] | None = None):
    """campaign.list / campaign.contacts answered; every WRITE recorded as a
    mutation, which the refusal cases assert never happens."""
    rows = contacts if contacts is not None else [_contact(state)]

    def fake(settings, method, params=None, timeout=None):
        if method == "campaign.list":
            return [{"id": "camp-1", "name": PACK}]
        if method == "campaign.contacts":
            return rows
        if method == "tasks.list":
            return []
        MUTATIONS.append(f"{method} {params}")
        return {"ok": True}

    rpc_mod.call_sync = fake
    campaign_mod.rpc.call_sync = fake


def _no_delivery() -> None:
    """Every path that puts something in front of a customer, wired to fail the
    test if it is reached at all."""

    def boom(*a, **k):
        raise AssertionError("a delivery path was reached on a refusing gate")

    send_mail.send = boom
    campaign_mod.send_mail = send_mail
    sms.send = boom
    gmail_drafts.append_draft = boom


@contextlib.contextmanager
def _installed(settings):
    orig = (imaplib.IMAP4_SSL, rpc_mod.call_sync, config_mod.load,
            send_mail.send, sms.send, gmail_drafts.append_draft)
    imaplib.IMAP4_SSL = FakeIMAP
    config_mod.load = lambda engine_owner_uid=None: settings
    MUTATIONS.clear()
    try:
        yield
    finally:
        (imaplib.IMAP4_SSL, rpc_mod.call_sync, config_mod.load,
         send_mail.send, sms.send, gmail_drafts.append_draft) = orig
        campaign_mod.rpc.call_sync = rpc_mod.call_sync
        mailboxes._SESSIONS.clear()
        mailboxes._CREDENTIALS.clear()


def _assert_refused(out: dict, label: str) -> None:
    assert out.get("ok") is False, f"{label}: expected a refusal, got {out}"
    blocked = out.get("blocked") or ""
    assert "evidence incomplete" in blocked, f"{label}: {out}"
    assert COLLEAGUE in blocked, (
        f"{label}: the refusal must NAME the mailbox to fix, or the operator "
        f"cannot act on it: {out}"
    )
    assert "CS_READ_MAILBOX_PASSWORDS" in blocked or "IMAP" in blocked, (
        f"{label}: the refusal must carry the reason, not only the name: {out}"
    )
    assert not MUTATIONS, f"{label}: a refusing gate wrote state: {MUTATIONS}"


# ------------------------------------------------------------------- gates


def _test_every_sender_fails_closed(db_path: str) -> None:
    """(1)(2)(3) Each gate class, with one mailbox refusing its login."""
    settings = _settings(db_path)
    cases = [
        ("send_draft", "drafted",
         lambda s: campaign_mod.send_draft(s, "c1", commit=True, now=NOW)),
        ("queue_draft", "drafted",
         lambda s: campaign_mod.queue_draft(s, "c1", commit=True, now=NOW)),
        ("send_reminder", "sent",
         lambda s: campaign_mod.send_reminder(s, "c1", commit=True, now=NOW)),
        ("send_sms", "sent",
         lambda s: campaign_mod.send_sms(s, "c1", commit=True, now=NOW)),
        ("reconcile", "drafted",
         lambda s: campaign_mod.reconcile(s, "c1", commit=True)),
    ]
    for label, state, call in cases:
        with _installed(settings):
            _world(colleague_password="rotated-yesterday")
            _engine(state)
            _no_delivery()
            _assert_refused(call(settings), label)


def _test_pending_surfaces_what_it_cannot_judge(db_path: str) -> None:
    """(4) The contact stays on the worklist, as its own item."""
    settings = _settings(db_path)
    with _installed(settings):
        _world(colleague_password="rotated-yesterday")
        _engine("drafted")
        _no_delivery()
        entry = campaign_mod.pending(settings, now=NOW)["campaigns"][0]
        actions = {(i["action"], i["email"]) for i in entry["items"]}
        assert (campaign_mod.EVIDENCE_ACTION, CONTACT) in actions, (
            f"a contact the run could not judge must appear as its own item: {entry}"
        )
        assert ("send_draft", CONTACT) not in actions, (
            f"…and never as a send candidate: {entry}"
        )
        item = [i for i in entry["items"] if i["action"] == campaign_mod.EVIDENCE_ACTION][0]
        assert COLLEAGUE in " ".join(item["unreadable"]), item
        assert campaign_mod.EVIDENCE_ACTION not in campaign_mod.DELIVERY_ACTIONS

    # the same for a contact whose REPLY could not be looked for
    with _installed(settings):
        _world(colleague_password="rotated-yesterday")
        _engine("sent")
        _no_delivery()
        entry = campaign_mod.pending(settings, now=NOW)["campaigns"][0]
        actions = [i["action"] for i in entry["items"]]
        assert campaign_mod.EVIDENCE_ACTION in actions, entry
        assert "send_reminder" not in actions and "send_sms" not in actions, (
            f"a contact whose reply could not be looked for must not be nudged: {entry}"
        )


def _test_a_colleagues_message_stops_the_send(db_path: str) -> None:
    """(5) The incident, replayed: the operator mailbox is empty and the send
    is refused anyway, because somebody else here already wrote."""
    settings = _settings(db_path)
    with _installed(settings):
        _world(colleague_wrote=True)
        _engine("drafted")
        _no_delivery()
        out = campaign_mod.send_draft(settings, "c1", commit=True, now=NOW)
        assert out["ok"] is False and out.get("next") == "reconcile", out
        assert "already in Sent" in out["error"], out
        assert not MUTATIONS, MUTATIONS

        entry = campaign_mod.pending(settings, now=NOW)["campaigns"][0]
        assert [i["action"] for i in entry["items"]] == ["reconcile"], entry


def _test_one_login_per_mailbox_per_process(db_path: str) -> None:
    """(6) The cost discipline the runner cannot live without."""
    settings = _settings(db_path)
    contacts = [dict(_contact("drafted"), id=f"c{i}", email=f"p{i}@customer.example")
                for i in range(4)]
    with _installed(settings):
        _world()
        _engine("drafted", contacts=contacts)
        _no_delivery()
        entry = campaign_mod.pending(settings, now=NOW)["campaigns"][0]
        assert len(entry["items"]) == 4, entry
        assert len(FakeIMAP.opened) == 2, (
            f"{len(FakeIMAP.opened)} logins for 2 mailboxes over 4 contacts — the "
            "gate runs once per contact, so a session per call would multiply "
            "TLS+LOGIN+LIST+SELECT by every contact in the run"
        )
        # and the gate calls that follow reuse the same sessions
        campaign_mod.send_draft(settings, "c0", commit=False, now=NOW)
        campaign_mod.queue_draft(settings, "c1", commit=False, now=NOW)
        assert len(FakeIMAP.opened) == 2, (
            f"a send gate reopened a session: {len(FakeIMAP.opened)}"
        )


def _test_dossier_verdict_fails_closed(db_path: str) -> None:
    """(7) The mandatory pre-contact check does not call a contact cold on a
    scope it could not read."""
    settings = _settings(db_path)
    with _installed(settings):
        _world(colleague_password="rotated-yesterday")
        _engine("drafted")
        from cs import crm
        import types as _types

        crm.lookup = lambda s, e: _types.SimpleNamespace(
            source="none", rows=[], render_hints=[], note=None, as_dict=lambda: {})
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["dossier", CONTACT])
        text = out.getvalue()
        assert code == 0, f"rc={code}\n{text}{err.getvalue()}"
        assert "Traceback" not in text + err.getvalue(), err.getvalue()
        assert "cannot reach the engine" not in text + err.getvalue(), (
            "an IMAP failure reported as an engine failure is a confidently "
            f"wrong diagnosis: {text}"
        )
        verdict = [ln for ln in text.splitlines() if ln.startswith("verdict:")][0]
        assert "STOP" in verdict and "evidence incomplete" in verdict, verdict
        assert COLLEAGUE in verdict, verdict
        assert "cold contact" not in verdict, (
            f"'cold contact' from a partial scan is the sentence that produced "
            f"an apology for silence that had not happened: {verdict}"
        )


def _test_review_notes_but_never_retires(db_path: str) -> None:
    """(8) The review widens its evidence, keeps every draft visible, and says
    ON THE ROW that this one is `ready` on evidence nobody could complete.

    A footer under two blocks is read after the decision, if at all. The
    operator acts row by row, so the qualification travels with the row: a
    draft can only read `ready` because nothing overtook it, and "nothing" is
    exactly what an unopened mailbox cannot establish."""
    from cs import review as review_mod

    settings = _settings(db_path)
    composed = NOW - timedelta(days=1)
    drafts = [{"uid": "9", "to": CONTACT, "subject": "re: your request",
               "date": format_datetime(composed), "body": "short",
               "thread_key": "", "message_id": "<m@acme.example>"}]
    with _installed(settings):
        _world(colleague_password="rotated-yesterday")
        _engine("drafted")
        rows, notes = draft_state.reconcile(settings, drafts, [], now=NOW)
        assert len(rows) == 1, rows
        assert rows[0]["verdict"] == "ready", (
            "the review is where a human looks: a mailbox that could not be read "
            f"must never retire a draft from it — {rows}"
        )
        gaps = rows[0]["evidence_incomplete"]
        assert gaps and COLLEAGUE in " ".join(gaps), (
            f"the row itself must carry the mailbox that could not be read: {rows[0]}"
        )
        joined = " ".join(notes)
        assert "INCOMPLETE" in joined and COLLEAGUE in joined, notes

        # …and it is PRINTED inside the ready block, above the next heading.
        text = review_mod.render({"drafts": rows, "drafts_notes": notes,
                                  "gmail_drafts": drafts, "engine_drafts": [],
                                  "tasks": []})
        head = text.split("Drafts to re-decide")[0]
        assert COLLEAGUE in head, (
            f"the incomplete evidence must appear in the READY block, on the row "
            f"the operator is about to send:\n{text}"
        )
        assert "INCOMPLETE evidence" in head, head

    with _installed(settings):
        # A complete scope leaves the field empty — a machine reader can trust
        # its absence, and no row grows a warning nobody earned.
        _world()
        _engine("drafted")
        rows, notes = draft_state.reconcile(settings, drafts, [], now=NOW)
        assert rows[0]["evidence_incomplete"] == [], rows[0]
        assert not [n for n in notes if "INCOMPLETE" in n], notes


def _test_dossier_verdict_is_about_ever_not_about_the_window(db_path: str) -> None:
    """(9) The incident's shape with NOTHING broken: a colleague answered 61
    days ago, every mailbox opens, and the mandatory pre-contact check must not
    call the contact cold.

    The dedup window answers "may we write again today". The verdict answers
    "is this person a stranger to us", and that question has no horizon — a
    60-day window misses the real case by one day."""
    settings = _settings(db_path)
    with _installed(settings):
        _world(colleague_wrote=True, wrote_days_ago=61)
        _engine("drafted")
        from cs import crm
        import types as _types

        crm.lookup = lambda s, e: _types.SimpleNamespace(
            source="none", rows=[], render_hints=[], note=None, as_dict=lambda: {})
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["dossier", CONTACT])
        text = out.getvalue()
        assert code == 0, f"rc={code}\n{text}{err.getvalue()}"
        verdict = [ln for ln in text.splitlines() if ln.startswith("verdict:")][0]
        assert not verdict.startswith("verdict: cold contact"), (
            "a contact a colleague answered two months ago is not cold, and "
            f"opening with an apology for silence is what that verdict caused: {verdict}"
        )
        assert "REPLY IN THREAD" in verdict, verdict
        assert COLLEAGUE in verdict, (
            f"the verdict must name WHERE the history is, or the reader cannot "
            f"go and read it: {verdict}"
        )
        assert "no" in text.split("-- contacted in last")[1][:80], (
            "the dedup-window answer is still 'no' — it is a different question "
            f"and it keeps its own meaning:\n{text}"
        )
        assert "older message" in text, (
            f"the history outside the window must be visible, not only implied "
            f"by the verdict:\n{text}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        packs = Path(td, "campaigns", PACK)
        packs.mkdir(parents=True)
        (packs / "campaign.toml").write_text(CAMPAIGN_TOML, encoding="utf-8")
        (packs / "mail_first.md").write_text("Subject: x\n\nCiao {name}.\n")
        (packs / "mail_reminder.md").write_text("Subject: y\n\nCiao {name}.\n")
        (packs / "sms.txt").write_text("Reminder {name}.\n")
        os.environ["CS_CAMPAIGNS_DIR"] = str(Path(td, "campaigns"))
        db = str(Path(td, "cs.db"))

        _test_every_sender_fails_closed(db)
        _test_pending_surfaces_what_it_cannot_judge(db)
        _test_a_colleagues_message_stops_the_send(db)
        _test_one_login_per_mailbox_per_process(db)
        _test_dossier_verdict_fails_closed(db)
        _test_dossier_verdict_is_about_ever_not_about_the_window(db)
        _test_review_notes_but_never_retires(db)
    print("test_send_gates_fanout: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
