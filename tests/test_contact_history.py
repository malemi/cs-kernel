#!/usr/bin/env python3
"""Contact history across every mailbox — and the mailboxes it could not read.

A company answers customers from several mailboxes; the operator's evidence is
scoped to one. `cs thread`, `cs ask` and `cs contacted` share that one bound, so
when they agree the agreement reads as three sources corroborating each other
while it is one absence reported three times. A colleague's reply, sent from his
own mailbox, is invisible to all three — and an operator concluded from them
that a prospect had waited two months unanswered, and drafted an apology for
silence that had not happened.

What these gates hold, in the order the work builds it:

  1. `gmail_drafts._imap` takes an EXPLICIT (address, password) and logs in with
     it; omitted, it is byte-for-byte today's behaviour, so no existing caller
     changes and none can be silently redirected to another mailbox.
  2. Another account's credential comes from ITS engine profile — owner-
     authenticated `settings.get`/`settings.get_secret` under that account's own
     uid and session files, the handover `cs init` already performs. Never from
     the environment: the operator's own Settings password is a different value
     and is never what opens the second mailbox. Cached per process (one round
     trip, not one per candidate contact).
  3. The credential cannot leak through `cs config`: it is in no `Settings`
     field, so it appears in neither the rendered report nor `--json`. Nor
     through an error message that happens to echo it back — reasons are
     redacted.
  4. ONE IMAP session per mailbox per process, reused across calls (two
     fan-outs over two mailboxes = two logins, not four), and a session that has
     since died is replaced rather than raised.
  5. A mailbox that cannot be read is `unreadable`, NEVER an empty result: the
     rows of the mailboxes that COULD be read are still returned, the failure
     names the mailbox, and the scope line says how many of how many were read.
  6. `unreadable` survives into every shape the CLI has. `cs contacted` grows a
     third outcome (exit 3) because its "no" is exit 1 and a failed login
     answering with it is the exact inversion this work exists to prevent;
     `cs history --json` carries the degraded-source note; a found message still
     answers YES even when the scope is incomplete, because a positive does not
     depend on what could not be read.
  7. No IMAP failure reaches `cli.main`'s connection handler, which would report
     it as "cannot reach the engine at wss://…" — a confidently wrong diagnosis
     — and none surfaces as a traceback.
  8. Only the two readers that decide nothing from "is this us" are fanned out.
     `thread_with` and `inbound_recent` derive direction from
     `settings.email_address` and would misattribute every message in somebody
     else's mailbox.
  9. The `--account` refusal no longer rests on "there is one mail credential,
     not one per account" — untrue the moment the kernel retrieves a second
     profile's password — and `history`, which reads every account already,
     refuses the flag on its own ground.

No network: `imaplib.IMAP4_SSL` and the engine RPC transport are replaced by
in-process doubles that implement the real protocol shapes (LIST special-use
flags, UID SEARCH/FETCH, the engine's `{values}` / `{key,value}` responses) and
raise the REAL exception types.
"""
from __future__ import annotations

import contextlib
import imaplib
import io
import json
import os
import tempfile
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cs import cli
from cs import config as config_mod
from cs import config_report
from cs import gmail_archive, gmail_drafts, mailboxes
from cs import rpc as rpc_mod
from cs.config import Settings

OPERATOR = "support@acme.example"
OPERATOR_PW = "operator-app-pw-1111"
FOUNDER = "founder@acme.example"
FOUNDER_PW = "founder-app-pw-2222"
UID_OPS = "uid-ops-acme"
UID_FOUNDER = "uid-founder-acme"

CONTACT = "prospect@customer.example"
STRANGER = "nobody@customer.example"

NOW = datetime.now(timezone.utc)


# --------------------------------------------------------------- the doubles


class FakeIMAP:
    """An IMAP server double: special-use LIST, UID SEARCH by TO/FROM, header
    FETCH. It speaks the same shapes `cs/gmail_archive.py` parses and raises
    `imaplib.IMAP4.error` — the real type — when a login is refused."""

    opened: list["FakeIMAP"] = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.address = None
        self.folder = None
        self.dead = False
        self.logged_out = False
        FakeIMAP.opened.append(self)

    # -- protocol ---------------------------------------------------------
    def login(self, address, password):
        want = MAILBOXES.get(address)
        if want is None or want["password"] != password:
            raise imaplib.IMAP4.error(
                f"b'[AUTHENTICATIONFAILED] Invalid credentials for {address} "
                f"(tried {password})'"
            )
        self.address = address
        return "OK", [b"authenticated"]

    def noop(self):
        if self.dead:
            raise imaplib.IMAP4.abort("socket error: EOF")
        return "OK", [b""]

    def list(self):
        return "OK", [
            b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"',
            b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"',
        ]

    def select(self, folder, readonly=True):
        assert readonly, "the fan-out must never select a mailbox writable"
        self.folder = folder.strip('"')
        # A mailbox can fail the two fan-outs in two DIFFERENT places: they read
        # different folders, so a broken Sent folder is a SELECT failure on one
        # pass and nothing at all on the other.
        if "Sent" in self.folder and MAILBOXES[self.address].get("fail_select_sent"):
            raise imaplib.IMAP4.error(f"SELECT {self.folder} failed")
        return "OK", [b"1"]

    def _messages(self):
        box = MAILBOXES[self.address]
        return box["sent"] if "Sent" in (self.folder or "") else box["in"]

    def uid(self, command, *args):
        if command == "SEARCH":
            if "All" in (self.folder or "") and MAILBOXES[self.address].get(
                "fail_search_all"
            ):
                raise imaplib.IMAP4.error("SEARCH FROM failed")
            _none, key, value = args
            hits = [
                str(i + 1).encode()
                for i, m in enumerate(self._messages())
                if m["peer"] == value and key in ("TO", "FROM")
            ]
            return "OK", [b" ".join(hits)]
        if command == "FETCH":
            uid = args[0]
            msg = self._messages()[int(uid) - 1]
            raw = (
                f"Date: {format_datetime(msg['date'])}\r\n"
                f"From: {self.address if 'Sent' in self.folder else msg['peer']}\r\n"
                f"To: {msg['peer'] if 'Sent' in self.folder else self.address}\r\n"
                f"Subject: {msg['subject']}\r\n"
                f"Message-ID: <{uid.decode()}@acme.example>\r\n\r\n"
            ).encode()
            return "OK", [(b"1 (BODY[HEADER])", raw)]
        raise AssertionError(f"unexpected UID command {command}")

    def logout(self):
        self.logged_out = True
        return "BYE", [b""]


def _msg(peer: str, subject: str, days_ago: int) -> dict:
    return {"peer": peer, "subject": subject, "date": NOW - timedelta(days=days_ago)}


MAILBOXES: dict[str, dict] = {}


def _reset_world(founder_password: str = FOUNDER_PW) -> None:
    """One operator mailbox that never wrote to the contact, one founder mailbox
    that answered them 61 days ago — the shape of the incident."""
    MAILBOXES.clear()
    MAILBOXES.update(
        {
            OPERATOR: {"password": OPERATOR_PW, "sent": [], "in": []},
            FOUNDER: {
                "password": founder_password,
                "engine_password": founder_password,
                "sent": [_msg(CONTACT, "Re: your request", 61)],
                "in": [_msg(CONTACT, "private-label request", 62)],
            },
        }
    )
    FakeIMAP.opened.clear()
    mailboxes._CREDENTIALS.clear()
    mailboxes._SESSIONS.clear()
    RPC_CALLS.clear()


RPC_CALLS: list[tuple[str, str]] = []


def _fake_rpc(settings, method, params=None, timeout=60, id_token=None):
    """The engine's own two answers, per PROFILE. The uid on the Settings is
    what decides whose mailbox is described — that is the owner-authentication
    this path rests on, so it is asserted rather than ignored."""
    uid = settings.engine_owner_uid
    RPC_CALLS.append((uid, method))
    assert uid, "an engine call with no owner uid cannot be owner-authenticated"
    assert settings.refresh_token_path.endswith(f"refresh_token-{uid}.json"), (
        "the per-account Settings must derive THAT uid's own session files, or "
        f"the call authenticates as somebody else: {settings.refresh_token_path}"
    )
    known = {UID_FOUNDER: FOUNDER, UID_OPS: OPERATOR}
    address = known.get(uid)
    if address is None:
        raise ConnectionRefusedError("no daemon for that profile")
    if method == "settings.get":
        return {"values": {"EMAIL_ADDRESS": address, "EMAIL_PASSWORD": "<set>"}}
    if method == "settings.get_secret":
        assert params == {"key": "EMAIL_PASSWORD"}, "one key per call, always"
        box = MAILBOXES[address]
        # What the PROFILE holds, which is not always what the server still
        # accepts — a rotated app password is the ordinary way a mailbox goes
        # unreadable, and it must not be simulated as an empty mailbox.
        return {"key": "EMAIL_PASSWORD", "value": box.get("engine_password", box["password"])}
    raise AssertionError(f"unexpected engine method {method}")


def _settings(**over) -> Settings:
    base = dict(
        _env_file=(),
        email_address=OPERATOR,
        email_password=OPERATOR_PW,
        engine_owner_uid=UID_OPS,
        accounts=f"ops:{UID_OPS},founder:{UID_FOUNDER}",
        accounts_default="ops",
        engine_ws_url="wss://engine.example.com",
        imap_host="imap.example.com",
        prog_name="acme-cs",
        slug="acme",
    )
    base.update(over)
    return Settings(**base)


@contextlib.contextmanager
def _world(settings: Settings, founder_password: str = FOUNDER_PW):
    """The doubles installed at the two real seams: the IMAP socket and the
    engine transport. Everything between them is the kernel's own code."""
    _reset_world(founder_password)
    orig_ssl = imaplib.IMAP4_SSL
    orig_rpc = rpc_mod.call_sync
    orig_mailboxes_rpc = mailboxes.rpc.call_sync
    orig_load = config_mod.load
    imaplib.IMAP4_SSL = FakeIMAP
    rpc_mod.call_sync = _fake_rpc
    mailboxes.rpc.call_sync = _fake_rpc

    def _load(engine_owner_uid=None):
        return settings if not engine_owner_uid else _settings(
            engine_owner_uid=engine_owner_uid
        )

    config_mod.load = _load
    mailboxes.config_mod.load = _load
    try:
        yield
    finally:
        imaplib.IMAP4_SSL = orig_ssl
        rpc_mod.call_sync = orig_rpc
        mailboxes.rpc.call_sync = orig_mailboxes_rpc
        config_mod.load = orig_load
        mailboxes.config_mod.load = orig_load
        mailboxes._SESSIONS.clear()
        mailboxes._CREDENTIALS.clear()


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


# ------------------------------------------------------------------- gates


def _test_imap_credential_argument() -> None:
    """(1) The default is today's behaviour; an explicit pair is honoured."""
    settings = _settings()
    with _world(settings):
        M = gmail_drafts._imap(settings)
        assert M.address == OPERATOR, "no credential must mean the operator's own"
        M2 = gmail_drafts._imap(settings, (FOUNDER, FOUNDER_PW))
        assert M2.address == FOUNDER, "an explicit credential must be the one used"
        # the spaced app-password paste is still tolerated on both paths
        M3 = gmail_drafts._imap(settings, (FOUNDER, "foun der-app-pw-2222"))
        assert M3.address == FOUNDER, "spaced app password must still log in"
        refused = False
        try:
            gmail_drafts._imap(settings, (FOUNDER, "wrong-password"))
        except imaplib.IMAP4.error:
            refused = True
        assert refused, "a wrong password must raise, never open a session"


def _test_credential_comes_from_the_engine() -> None:
    """(2) Another mailbox's password is the ENGINE's, not the environment's,
    and it is fetched once per process."""
    settings = _settings()
    with _world(settings):
        mb = mailboxes.credential(settings, "founder", UID_FOUNDER)
        assert (mb.address, mb.password) == (FOUNDER, FOUNDER_PW)
        assert mb.password != settings.email_password, (
            "the second mailbox must NOT be opened with the operator's own "
            "credential — that would answer about the wrong mailbox"
        )
        assert [m for _u, m in RPC_CALLS] == ["settings.get", "settings.get_secret"]
        before = len(RPC_CALLS)
        for _ in range(5):
            mailboxes.credential(settings, "founder", UID_FOUNDER)
        assert len(RPC_CALLS) == before, (
            "the credential must be cached per process: a send gate asks once "
            f"per candidate contact, and {len(RPC_CALLS) - before} extra engine "
            "round trips per contact is not a cost a tick can carry"
        )
        # every call went out under the FOUNDER's uid, never the operator's
        assert {u for u, _m in RPC_CALLS} == {UID_FOUNDER}

    # An account whose profile has no password is unreadable, not empty.
    with _world(settings, founder_password=""):
        MAILBOXES[FOUNDER]["password"] = ""
        raised = ""
        try:
            mailboxes.credential(settings, "founder", UID_FOUNDER)
        except mailboxes.MailboxUnreadable as e:
            raised = str(e)
        assert "EMAIL_PASSWORD" in raised and FOUNDER in raised, (
            f"a profile with no stored password must name itself: {raised!r}"
        )


def _test_credential_cannot_leak_through_cs_config() -> None:
    """(3) No Settings field carries it, so `cs config` cannot print it — and
    an error message that echoes it back is redacted."""
    settings = _settings()
    with _world(settings):
        mailboxes.credential(settings, "founder", UID_FOUNDER)
        for name in type(settings).model_fields:
            assert getattr(settings, name, None) != FOUNDER_PW, (
                f"another mailbox's password reached Settings.{name} — from "
                "there `cs config` prints it unless someone remembers to add "
                "the field to SECRET_FIELDS"
            )
        rep = config_report.build(settings)
        rendered = config_report.render(rep) + json.dumps(rep, default=str)
        assert FOUNDER_PW not in rendered, "cs config printed another mailbox's password"
        assert OPERATOR_PW not in rendered, "cs config printed the operator's password"
        assert "email_password" in config_report.SECRET_FIELDS

    # The IMAP double echoes the attempted password in its refusal, exactly as
    # a chatty server could. The reason line must not carry it.
    with _world(settings):
        MAILBOXES[FOUNDER]["password"] = "rotated-yesterday"  # the profile still hands the old one
        fan = mailboxes.sent_to_across(settings, CONTACT)
        reasons = " ".join(u.reason for u in fan.unreadable)
        assert reasons, "a refused login must produce a reason"
        assert FOUNDER_PW not in reasons, f"the reason leaked the password: {reasons}"
        assert "<redacted>" in reasons, (
            f"a secret echoed back by the server must be redacted: {reasons}"
        )


def _test_one_session_per_mailbox_per_process() -> None:
    """(4) Reuse, not reconnect — and a dead session is replaced."""
    settings = _settings()
    with _world(settings):
        mailboxes.sent_to_across(settings, CONTACT)
        mailboxes.inbound_since_across(settings, CONTACT)
        assert len(FakeIMAP.opened) == 2, (
            "two fan-outs over two mailboxes opened "
            f"{len(FakeIMAP.opened)} sessions — the per-call TLS+LOGIN+LIST+"
            "SELECT is the entire cost of reading N mailboxes, so sessions are "
            "held per mailbox for the process"
        )
        assert {m.address for m in FakeIMAP.opened} == {OPERATOR, FOUNDER}

        # a session that died between calls: replaced, and the answer still comes
        for m in FakeIMAP.opened:
            m.dead = True
        fan = mailboxes.sent_to_across(settings, CONTACT)
        assert len(FakeIMAP.opened) == 4, "a dead session must be reopened"
        assert fan.complete, "a reopened session must not report the mailbox unreadable"
        assert len(fan.rows) == 1

        mailboxes.close_sessions()
        assert not mailboxes._SESSIONS, "close_sessions must leave nothing open"


def _test_fanout_tags_rows_and_names_what_it_could_not_read() -> None:
    """(5) Rows carry their mailbox; a bad credential is `unreadable`, never an
    empty result; and only the self-free readers are fanned out."""
    settings = _settings()
    with _world(settings):
        fan = mailboxes.sent_to_across(settings, CONTACT)
        assert [r["mailbox"] for r in fan.rows] == [FOUNDER], (
            "the answer must say WHICH mailbox wrote — the operator's did not"
        )
        assert fan.complete and set(fan.read) == {OPERATOR, FOUNDER}
        assert fan.note() is None, "a complete scope must carry no degraded note"

        inb = mailboxes.inbound_since_across(settings, CONTACT)
        assert [r["mailbox"] for r in inb.rows] == [FOUNDER], (
            "inbound must fan out too, or the reply gate stays single-mailbox"
        )

    with _world(settings):
        MAILBOXES[FOUNDER]["password"] = "rotated-yesterday"
        fan = mailboxes.sent_to_across(settings, CONTACT)
        assert fan.read == [OPERATOR], f"the readable mailbox must still be read: {fan.read}"
        assert not fan.complete and len(fan.unreadable) == 1
        u = fan.unreadable[0]
        assert u.account == "founder" and u.address == FOUNDER, (
            "the failure must NAME the mailbox to fix, or the operator cannot act"
        )
        assert "1 of 2 mailbox(es) read" in fan.scope_line()
        assert FOUNDER in fan.scope_line() and "UNREADABLE" in fan.scope_line()
        assert "not proof that none exists" in (fan.note() or ""), fan.note()

    # An account whose engine cannot be reached at all: unreadable, and the
    # failure is per mailbox — the operator's own answer still comes back.
    with _world(settings):
        s = _settings(accounts=f"ops:{UID_OPS},ghost:uid-no-such-profile")
        fan = mailboxes.sent_to_across(s, CONTACT)
        assert fan.read == [OPERATOR] and len(fan.unreadable) == 1
        assert fan.unreadable[0].account == "ghost"

    # (8) exactly two readers are fanned out, and they are the two that decide
    # nothing from "is this us".
    fanned = {n for n in dir(mailboxes) if n.endswith("_across")}
    assert fanned == {"sent_to_across", "inbound_since_across"}, (
        f"unexpected fan-out surface {fanned}: `thread_with` and "
        "`inbound_recent` derive direction from settings.email_address and "
        "would misattribute every message in another mailbox"
    )
    for reader in ("thread_with", "inbound_recent"):
        src = gmail_archive.__dict__[reader].__doc__ or ""
        assert "SINGLE-MAILBOX" in src, (
            f"{reader} stays single-mailbox and must SAY so in its docstring"
        )


def _test_contacted_has_a_third_outcome() -> None:
    """(6)(7) `contacted` cannot render an unreadable mailbox as 'never'."""
    settings = _settings()
    with _world(settings):
        code, out, err = _run(["contacted", CONTACT])
        assert code == 1, f"a real, read absence stays exit 1: {code} {out}"
        assert out.startswith("no — "), out
        assert "scope:" in out and "1 of 1 mailbox(es) read" in out, (
            f"every answer must print the scope it read: {out}"
        )
        assert "ONE mailbox" in out and "history" in out, (
            "the line must say it is one mailbox and where the wider question "
            f"lives, instead of ending on an unqualified verdict: {out}"
        )
        assert "ground truth" not in out, (
            f"'ground truth' at the end of a one-mailbox line reads as a verdict "
            f"on the company, and was read as one: {out}"
        )

    with _world(settings):
        MAILBOXES[OPERATOR]["password"] = "rotated-yesterday"
        code, out, err = _run(["contacted", CONTACT])
        assert code == 3, (
            f"a mailbox that could not be read must NOT exit 1 ('no'): rc={code}\n{out}{err}"
        )
        assert "UNKNOWN" in out and "not a 'no'" in out, out
        assert OPERATOR in out, "the unreadable mailbox must be named"
        assert "Traceback" not in out + err, (
            f"a refused IMAP login used to surface as a traceback: {err}"
        )
        assert "cannot reach the engine" not in out + err, (
            "an IMAP failure reported as an engine failure is a confidently "
            f"wrong diagnosis: {out}{err}"
        )

    # a connection-level IMAP failure: same three-way outcome, still not
    # reported as an unreachable engine.
    settings2 = _settings()
    with _world(settings2):
        def _refuse(host, port):
            raise ConnectionRefusedError(f"[Errno 111] connect to {host}:{port}")

        imaplib.IMAP4_SSL = _refuse
        code, out, err = _run(["contacted", CONTACT])
        assert code == 3, f"rc={code}: {out}{err}"
        assert "cannot reach the engine" not in out + err, out + err
        assert "Traceback" not in out + err


def _test_history_verb() -> None:
    """(6) The verb: per mailbox, both directions, unreadable named, and a
    positive answer that survives an incomplete scope."""
    settings = _settings()
    with _world(settings):
        code, out, err = _run(["history", CONTACT])
        assert code == 0, f"a found history is exit 0: {code}\n{out}{err}"
        assert "YES" in out and FOUNDER in out, out
        assert "1 message(s) sent to them, 1 received" in out, out
        assert "scope: 2 of 2 mailbox(es) read" in out, out
        assert OPERATOR in out, "the mailbox that found nothing is still in scope"

    with _world(settings):
        code, out, err = _run(["history", STRANGER])
        assert code == 1, f"a complete scope with no history is a real 'never': {code}"
        assert "no —" in out and "scope: 2 of 2" in out, out

    with _world(settings):
        MAILBOXES[FOUNDER]["password"] = "rotated-yesterday"
        code, out, err = _run(["history", STRANGER])
        assert code == 3, f"nothing found + an unreadable mailbox is not 'never': {code}"
        assert "UNKNOWN" in out and "not a 'no'" in out, out
        assert "1 of 2 mailbox(es) read" in out, out

        # --json carries the same three facts a machine reader needs
        code, out, err = _run(["history", STRANGER, "--json"])
        payload = json.loads(out)
        assert code == 3
        assert payload["found"] is False
        assert payload["scope"]["complete"] is False
        assert payload["scope"]["read"] == [OPERATOR]
        assert payload["scope"]["unreadable"][0]["account"] == "founder"
        assert payload["note"] and "INCOMPLETE" in payload["note"]
        assert FOUNDER_PW not in out, "the JSON shape leaked a mailbox password"

    with _world(settings):
        # A POSITIVE answer does not depend on the scope being complete: the
        # operator mailbox alone proves the contact was written to.
        MAILBOXES[OPERATOR]["sent"] = [_msg(CONTACT, "our own reply", 3)]
        MAILBOXES[FOUNDER]["password"] = "rotated-yesterday"
        code, out, err = _run(["history", CONTACT, "--json"])
        payload = json.loads(out)
        assert code == 0, "a message that WAS found still answers YES"
        assert payload["found"] is True and payload["scope"]["complete"] is False
        assert payload["note"], "the degraded source must travel with the data"


def _test_one_mailbox_is_counted_once() -> None:
    """(5) The scope DENOMINATOR is mailboxes, not failures.

    The two fan-outs read different folders, so one dead mailbox fails them in
    two different places — a SELECT on the Sent pass, a SEARCH on the All Mail
    pass. Deduping whole records let that mailbox be counted twice and printed
    twice: `scope: 1 of 3 mailbox(es) read` out of two mailboxes. A scope line
    that overstates its own denominator is the same class of wrong evidence as
    the absence this work exists to stop, so it is held by its own gate."""
    settings = _settings()
    with _world(settings):
        MAILBOXES[FOUNDER]["fail_select_sent"] = True
        MAILBOXES[FOUNDER]["fail_search_all"] = True

        one_way = mailboxes.sent_to_across(settings, CONTACT)
        other_way = mailboxes.inbound_since_across(settings, CONTACT)
        assert one_way.unreadable[0].reason != other_way.unreadable[0].reason, (
            "this gate is only meaningful while the two passes fail DIFFERENTLY"
        )

        fan = mailboxes.merge_directions(one_way, other_way)
        assert len(fan.unreadable) == 1, (
            f"one mailbox, one record — got {len(fan.unreadable)}: "
            f"{[u.describe() for u in fan.unreadable]}"
        )
        assert fan.read == [OPERATOR]
        assert "1 of 2 mailbox(es) read" in fan.scope_line(), fan.scope_line()
        assert fan.scope_line().count(FOUNDER) == 1, (
            f"the mailbox is named once, not once per failure: {fan.scope_line()}"
        )
        reason = fan.unreadable[0].reason
        assert "SELECT" in reason and "SEARCH" in reason, (
            f"two different diagnoses of one mailbox are both kept — the "
            f"operator needs both to know what to fix: {reason}"
        )

    with _world(settings):
        # The ordinary case — a refused login fails both passes the SAME way —
        # collapses to one reason, never a doubled one.
        MAILBOXES[FOUNDER]["password"] = "rotated-yesterday"
        fan = mailboxes.merge_directions(
            mailboxes.sent_to_across(settings, CONTACT),
            mailboxes.inbound_since_across(settings, CONTACT),
        )
        assert len(fan.unreadable) == 1
        assert " / " not in fan.unreadable[0].reason, (
            f"an identical reason must not be repeated: {fan.unreadable[0].reason}"
        )

    with _world(settings):
        # …and through the CLI, where the operator actually reads it.
        MAILBOXES[FOUNDER]["fail_select_sent"] = True
        MAILBOXES[FOUNDER]["fail_search_all"] = True
        code, out, err = _run(["history", CONTACT])
        assert code == 3, f"rc={code}: {out}{err}"
        assert "1 of 2 mailbox(es) read" in out, out
        scope = [ln for ln in out.splitlines() if ln.startswith("scope:")][0]
        assert scope.count(FOUNDER) == 1, scope
        code, out, err = _run(["history", CONTACT, "--json"])
        payload = json.loads(out)
        assert len(payload["scope"]["unreadable"]) == 1, payload["scope"]
        assert len(payload["scope"]["read"]) == 1


def _test_account_refusal_message() -> None:
    """(9) The refusal that rested on a sentence step 2 makes false."""
    settings = _settings()
    with _world(settings):
        code, out, err = _run(["--account", "founder", "contacted", CONTACT])
        assert code == 2, f"the refusal must stand: {code}"
        assert "one mail credential" not in err, (
            "the kernel now retrieves a second profile's credential, so the "
            f"refusal may no longer rest on that ground: {err}"
        )
        assert "engine profile" in err, err
        assert "history" in err, (
            f"the refusal must point at the verb that CAN answer wider: {err}"
        )

    with _world(settings):
        code, out, err = _run(["--account", "founder", "history", CONTACT])
        assert code == 2, f"--account cannot select a scope history already reads: {code}"
        assert "every account" in err.lower() and "engine profile" in err, err


def _test_load_targets_another_profiles_session() -> None:
    """(2, the load half, without doubles) `config.load(engine_owner_uid=…)`
    really does derive THAT uid's own session files — which is what makes the
    engine call authenticate as that profile's owner rather than the
    operator's."""
    with tempfile.TemporaryDirectory() as td:
        home, cwd = Path(td, "home"), Path(td, "cwd")
        home.mkdir(), cwd.mkdir()
        env_keep = {k: os.environ.get(k) for k in ("HOME", "CS_ENGINE_OWNER_UID")}
        old_cwd = os.getcwd()
        try:
            os.environ["HOME"] = str(home)
            os.environ["CS_ENGINE_OWNER_UID"] = UID_OPS
            os.chdir(cwd)
            default = config_mod.load()
            other = config_mod.load(engine_owner_uid=UID_FOUNDER)
            assert default.engine_owner_uid == UID_OPS
            assert other.engine_owner_uid == UID_FOUNDER, (
                "the explicit uid must beat the process environment, or a "
                "fan-out authenticates every account as the operator"
            )
            assert other.refresh_token_path.endswith(f"refresh_token-{UID_FOUNDER}.json")
            assert default.refresh_token_path.endswith(f"refresh_token-{UID_OPS}.json")
            assert other.slug == default.slug, (
                "a change of engine identity is never a change of company"
            )
        finally:
            os.chdir(old_cwd)
            for k, v in env_keep.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def main() -> int:
    _test_imap_credential_argument()
    _test_credential_comes_from_the_engine()
    _test_credential_cannot_leak_through_cs_config()
    _test_one_session_per_mailbox_per_process()
    _test_fanout_tags_rows_and_names_what_it_could_not_read()
    _test_contacted_has_a_third_outcome()
    _test_history_verb()
    _test_one_mailbox_is_counted_once()
    _test_account_refusal_message()
    _test_load_targets_another_profiles_session()
    print("test_contact_history: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
