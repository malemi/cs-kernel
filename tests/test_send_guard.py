#!/usr/bin/env python3
"""The model-output send guard: what must never reach the wire, and what must.

The incident this exists for (2026-07-28): a campaign loop mailed a customer
the model's own meta-deliberation verbatim — a paragraph reasoning about what
the customer had written, "here is the reply:", the reply between `---` rules,
and a closing question to the OPERATOR asking whether to prepare the mail to
send to that customer's address. The loop's own guard checked length, unfilled
placeholders and AI-self-outing phrases, and passed it: nothing asked WHO the
text was addressed to.

OFFENDING below is that body's shape, reconstructed. It is Italian because the
original was, and because the guard has to work in the language a clone
actually writes in — the address in it is a neutral stand-in, since a real
customer's address has no business in the kernel repo.

The load-bearing assertion is not "the guard returns False". It is that a call
to `send_mail.send()` with the offending body opens NO SMTP connection, while
the same call with a legitimate reply reaches the socket — i.e. the guard was
the only thing standing between that text and the wire. `smtplib.SMTP` is
swapped for a sentinel that records the attempt and refuses to make it, and the
SMTP host is `.invalid` so nothing could leave even if the swap were bypassed.

No network by default. The register-judgment leg runs against stubs; the LIVE
provider leg is opt-in (`CS_SEND_GUARD_LIVE=1`, exactly two calls) so the suite
stays free and offline like every other gate here.

Section 6 covers the OTHER side of the guard: the Gmail-draft path
(`cs/gmail_drafts.py`'s `append_draft`) is deliberately UNGUARDED in the
blocking sense — a draft is the human review surface, so a bad body must
reach the reviewer, not be hidden — but it still runs the guard's
deterministic tells on model-composed bodies and surfaces any hits as
warnings. The load-bearing assertion there is the mirror image of section 2's:
the offending body must still reach the (sentinel) IMAP APPEND, unlike on the
send path where it must not reach the (sentinel) SMTP socket.

Run: python tests/test_send_guard.py
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import types
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import campaign as campaign_mod, gmail_drafts, rpc, send_guard, send_mail  # noqa: E402
from cs.send_guard import (  # noqa: E402
    TELL_BANNED,
    TELL_FENCE,
    TELL_HR,
    TELL_PLACEHOLDER,
    TELL_RECIPIENT_IN_BODY,
    TELL_REGISTER,
    TELL_TOO_SHORT,
    TELL_TRAILING_QUESTION,
    SendGuardRefusal,
)
from cs.state import State  # noqa: E402

FAIL = 0
CUSTOMER = "studio.esempio@example.com"


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAIL
    if cond:
        print(f"  ok   {label}")
    else:
        FAIL = 1
        print(f"  FAIL {label} {detail}")


# --------------------------------------------------------------- the bodies

OFFENDING = f"""Il cliente dice "Ok grazie" — e' una chiusura cortese, non una domanda. Non serve riaprire nulla: il numero e' gia' stato spostato e lui ha gia' impostato l'inoltro. Rispondo breve e resto a disposizione.

Ecco la risposta (senza saluto iniziale, senza firma, senza markdown):

---

Perfetto, allora e' tutto a posto: il numero nuovo e' attivo e l'inoltro risulta impostato correttamente. Se dovesse servirle altro sono qui.

---

Vuoi che prepari la bozza della mail completa da inviare a {CUSTOMER}?"""

LEGITIMATE = """Buongiorno, confermo che il numero nuovo e' gia' attivo: le basta impostare l'inoltro dal telefono, digitando il codice che le abbiamo mandato ieri.

Se qualcosa non dovesse funzionare al primo tentativo mi scriva pure, ci mettiamo un attimo a controllare insieme."""

LEGITIMATE_QUESTION = """Buongiorno, ho verificato: la sua linea e' gia' stata spostata e l'inoltro risulta attivo da ieri sera.

Le va bene se la richiamo giovedi' mattina per chiudere il passaggio?"""


def _settings(**over):
    """The fields send_mail + send_guard + campaign actually read. A real
    Settings needs a manifest and a HOME; these tests are about the guard."""
    s = types.SimpleNamespace(
        email_address="operator@example.test",
        email_from_name="Operator",
        email_password="app password",
        smtp_host="smtp.invalid",   # RFC 6761: guaranteed unresolvable
        smtp_port=587,
        imap_host="imap.invalid",   # RFC 6761: guaranteed unresolvable
        imap_port=993,
        send_guard_min_chars=40,
        send_guard_banned_phrases="",
    )
    for k, v in over.items():
        setattr(s, k, v)
    return s


# ------------------------------------------------- 1. deterministic tells
print("deterministic tells (no LLM)")

v = send_guard.evaluate(OFFENDING, CUSTOMER, settings=_settings(), use_llm=False)
check("the 2026-07-28 body is refused", v.ok is False)
check("...on the horizontal rule", TELL_HR in v.tell_names, v.tell_names)
check("...on its own recipient named in the body",
      TELL_RECIPIENT_IN_BODY in v.tell_names, v.tell_names)
check("...and the trailing question to the operator",
      TELL_TRAILING_QUESTION in v.tell_names, v.tell_names)
check("the reason names the tells", CUSTOMER in v.reason, v.reason)

for label, body, tell in [
    ("a bare horizontal rule",
     "Buongiorno, le confermo che e' tutto a posto.\n\n---\n\nA presto.", TELL_HR),
    ("a code fence",
     "Buongiorno, ecco il testo che le serve.\n\n```\nqualcosa\n```\n\nA presto.",
     TELL_FENCE),
    ("an unfilled placeholder",
     "Buongiorno {nome}, le confermo che la linea e' gia' stata spostata ieri.",
     TELL_PLACEHOLDER),
    ("a body shorter than the floor", "Ok, grazie.", TELL_TOO_SHORT),
]:
    got = send_guard.evaluate(body, CUSTOMER, settings=_settings(), use_llm=False)
    check(f"{label} refuses", got.ok is False and tell in got.tell_names, got.tell_names)

for phrase in ("come assistente ai", "as an ai", "non posso"):
    body = f"Buongiorno, {phrase} confermarle la data prima di domani mattina."
    got = send_guard.evaluate(body, CUSTOMER, settings=_settings(), use_llm=False)
    check(f"banned phrase {phrase!r} refuses",
          got.ok is False and TELL_BANNED in got.tell_names, got.tell_names)

# The address tell must not fire on the quoted thread: their own headers and
# signature legitimately carry it, and refusing there would bounce every reply
# that quotes the customer.
quoted = (
    "Buongiorno, confermo che la linea e' gia' stata spostata come da accordi.\n\n"
    f"> Il giorno 27 luglio {CUSTOMER} ha scritto:\n"
    "> Buongiorno, quando spostate il numero?\n"
)
got = send_guard.evaluate(quoted, CUSTOMER, settings=_settings(), use_llm=False)
check("the address inside a quoted thread is not a tell",
      got.ok is True, got.tell_names)

got = send_guard.evaluate(LEGITIMATE, CUSTOMER, settings=_settings(), use_llm=False)
check("a legitimate reply passes the deterministic layer", got.ok is True, got.tell_names)

got = send_guard.evaluate(LEGITIMATE_QUESTION, CUSTOMER, settings=_settings(), use_llm=False)
check("a reply that ends on a question TO THE CUSTOMER still passes",
      got.ok is True, got.tell_names)

# The knobs, and only the knobs, come from the clone.
got = send_guard.evaluate("Ok, va bene, grazie mille.", CUSTOMER,
                          settings=_settings(send_guard_min_chars=10), use_llm=False)
check("the length floor is a manifest knob", got.ok is True, got.tell_names)
got = send_guard.evaluate(
    "Buongiorno, le confermo che la pratica risulta chiusa in data odierna.",
    CUSTOMER, settings=_settings(send_guard_banned_phrases="pratica risulta chiusa"),
    use_llm=False)
check("the manifest EXTENDS the banned list",
      got.ok is False and TELL_BANNED in got.tell_names, got.tell_names)
check("...without dropping the kernel's own phrases",
      send_guard.banned_phrases(_settings(send_guard_banned_phrases="x"))[:3]
      == send_guard.BANNED_PHRASES)

def _check_raises() -> None:
    try:
        send_guard.check(_settings(), CUSTOMER, OFFENDING, use_llm=False)
    except SendGuardRefusal as e:
        check("check() raises SendGuardRefusal carrying the tells",
              TELL_HR in e.tell_names and bool(e.reason), e.tell_names)
        return
    check("check() raises SendGuardRefusal carrying the tells", False, "no raise")


_check_raises()


# ------------------------------------------------------- 2. the wire itself
print("send_mail.send — was the socket ever opened?")


class _SmtpReached(RuntimeError):
    """Raised by the sentinel: proof the guard let the body through."""


class _Sentinel:
    opened: list = []

    def __init__(self, host, port, *a, **kw):
        _Sentinel.opened.append((host, port))
        raise _SmtpReached(f"SMTP connection attempted to {host}:{port}")


_real_smtplib = send_mail.smtplib
send_mail.smtplib = types.SimpleNamespace(SMTP=_Sentinel)
# This section calls send() for real, which means the guard's LLM leg would go
# out to whatever provider the machine happens to have configured — a suite
# that spends money and needs the network depending on the operator's env. Pin
# it to the degraded mode instead: it is also the harder case to get right,
# since a good mail must still reach the wire with the register leg switched
# off. The judgment itself is exercised in section 3.
_real_available = send_guard.llm_available
send_guard.llm_available = lambda: (False, "offline test")
try:
    _Sentinel.opened.clear()
    try:
        send_mail.send(_settings(), CUSTOMER, "Re: spostamento", body_md=OFFENDING)
        check("the offending body is refused by send()", False, "send() returned")
    except SendGuardRefusal as e:
        check("the offending body is refused by send()", True)
        check("...and NO SMTP connection was opened", _Sentinel.opened == [],
              _Sentinel.opened)
        check("...naming why", TELL_RECIPIENT_IN_BODY in e.tell_names, e.tell_names)
    except _SmtpReached:
        check("the offending body is refused by send()", False, "reached SMTP")

    _Sentinel.opened.clear()
    try:
        send_mail.send(_settings(), CUSTOMER, "Re: spostamento", body_md=LEGITIMATE)
        check("a legitimate reply reaches the SMTP layer", False, "no socket attempt")
    except SendGuardRefusal as e:
        check("a legitimate reply reaches the SMTP layer", False, f"guard refused: {e}")
    except _SmtpReached:
        check("a legitimate reply reaches the SMTP layer",
              _Sentinel.opened == [("smtp.invalid", 587)], _Sentinel.opened)

    # The fixed-template path is a HUMAN's copy from a campaign pack — rules,
    # dial codes and all. Guarding it would bounce legitimate packs, so this
    # asserts the guard is scoped to body_md and nothing else.
    _Sentinel.opened.clear()
    try:
        send_mail.send(_settings(), CUSTOMER, "Avviso",
                       plain=f"---\n{{nome}}\n---\nda inviare a {CUSTOMER}",
                       html="<p>x</p>")
        check("a plain/html fixed-template send is NOT guarded", False, "no attempt")
    except SendGuardRefusal:
        check("a plain/html fixed-template send is NOT guarded", False, "guard fired")
    except _SmtpReached:
        check("a plain/html fixed-template send is NOT guarded", True)
finally:
    send_mail.smtplib = _real_smtplib
    send_guard.llm_available = _real_available


# ------------------------------------------- 3. the register judgment (stubs)
print("register judgment (stubbed provider)")

_calls: list = []


def _stub_classify(label=None, exc=None):
    def _f(prompt, labels, **kw):
        _calls.append(prompt)
        if exc is not None:
            raise exc
        return label
    return _f


def _with_stub(body, *, label=None, exc=None, available=(True, "")):
    from cs import worker_llm

    warnings: list = []
    send_guard.llm_available = lambda: available
    real = worker_llm.classify
    worker_llm.classify = _stub_classify(label, exc)
    try:
        return send_guard.evaluate(body, CUSTOMER, settings=_settings(),
                                   warn=warnings.append), warnings
    finally:
        worker_llm.classify = real
        send_guard.llm_available = _real_available


# A body with NO deterministic tell at all: only the register judgment can
# refuse it. That is the whole point of the second layer.
CLEAN_META = ("Il cliente ringrazia e chiude la conversazione, quindi non serve "
              "riaprire nulla. Preparo una risposta breve e cortese e poi la "
              "sottopongo prima di mandarla.")

_calls.clear()
v, warns = _with_stub(CLEAN_META, label="meta_deliberation")
check("a clean-looking deliberation is refused on register alone",
      v.ok is False and TELL_REGISTER in v.tell_names, v.tell_names)
check("...carrying the label", v.register == "meta_deliberation", v.register)
check("...with no warning (nothing degraded)", warns == [], warns)

v, _ = _with_stub(CLEAN_META, label="mixed")
check("'mixed' refuses too — a real reply with meta stapled on is the incident",
      v.ok is False and v.register == "mixed", v.register)

v, _ = _with_stub(LEGITIMATE, label="customer_reply")
check("'customer_reply' passes", v.ok is True and v.register == "customer_reply")

# A provider outage must degrade the guard, not stop the mail — and must say so.
v, warns = _with_stub(LEGITIMATE, exc=RuntimeError("gateway 503"))
check("a failing provider does not crash the send", v.ok is True)
check("...it degrades", "503" in v.degraded, v.degraded)
check("...announcing it exactly once", len(warns) == 1, warns)
check("...in a line that names the degraded mode",
      warns and "register judgment SKIPPED" in warns[0], warns)

v, warns = _with_stub(LEGITIMATE, available=(False, "no provider credential resolved"))
check("no credential configured degrades the same way",
      v.ok is True and "credential" in v.degraded, v.degraded)
check("...and still warns", len(warns) == 1, warns)

# Already refused deterministically → never pay for a classification.
_calls.clear()
v, _ = _with_stub(OFFENDING, label="customer_reply")
check("a deterministic refusal short-circuits the LLM call",
      v.ok is False and _calls == [], len(_calls))


# ------------------------------------- 4. the caller: state must stay untouched
print("campaign.send_draft surfaces the refusal and writes nothing")

with tempfile.TemporaryDirectory() as td:
    db = str(Path(td) / "cs.db")
    contact = {"id": "c1", "email": CUSTOMER, "state": "drafted",
               "draft_subject": "Re: spostamento", "draft_body": OFFENDING,
               "dossier": {}, "_campaign_name": "trial", "_campaign_id": "camp1"}
    rpc_calls: list = []
    st = _settings(db_path=db, rate_cap=25, dedup_days=30, cs_triage_mode="send",
                   pause_path=Path(td) / "CS_PAUSE")

    _r_get, _r_sent, _r_call = (campaign_mod._get_contact,
                                campaign_mod._sent_threads_to, rpc.call_sync)
    campaign_mod._get_contact = lambda s, cid: dict(contact) if cid == "c1" else None
    # (threads, unreadable): the gate reads every mailbox in scope, and
    # nothing here is unreadable — what this file varies is the BODY.
    campaign_mod._sent_threads_to = lambda s, e, d: ([], [])
    rpc.call_sync = lambda s, m, p, **kw: rpc_calls.append((m, p)) or {}
    send_mail.smtplib = types.SimpleNamespace(SMTP=_Sentinel)
    _Sentinel.opened.clear()
    try:
        out = campaign_mod.send_draft(st, "c1", commit=True)
    finally:
        (campaign_mod._get_contact, campaign_mod._sent_threads_to,
         rpc.call_sync) = _r_get, _r_sent, _r_call
        send_mail.smtplib = _real_smtplib

    check("send_draft reports ok=False", out.get("ok") is False, out)
    check("...naming the guard", out.get("refused") == "send_guard", out)
    check("...listing the tells", TELL_HR in (out.get("tells") or []), out)
    check("...and never opening a socket", _Sentinel.opened == [], _Sentinel.opened)
    check("the contact was NOT marked sent",
          not any(m == "campaign.update_contact" and "state" in p for m, p in rpc_calls),
          rpc_calls)
    check("no `sends` row was written",
          State(db).conn.execute("SELECT COUNT(*) FROM sends").fetchone()[0] == 0)


# ---------------------------------------------------- 5. LIVE provider (opt-in)
if os.environ.get("CS_SEND_GUARD_LIVE", "").strip() == "1":
    print("register judgment (LIVE provider — 2 calls)")
    label, why = send_guard.judge_register(OFFENDING, CUSTOMER)
    check("the real model calls the offending body out",
          label is not None and label != "customer_reply", f"{label} {why}")
    label, why = send_guard.judge_register(LEGITIMATE, CUSTOMER)
    check("the real model passes a legitimate reply",
          label == "customer_reply", f"{label} {why}")
else:
    print("register judgment (LIVE provider): SKIP — set CS_SEND_GUARD_LIVE=1")


# ------------------------------------------ 6. the draft path (warn, never block)
print("gmail_drafts.append_draft — warn on model-composed tells, never block")


class _ImapAppendSentinel:
    """Mimics imaplib.IMAP4_SSL just enough for append_draft. Unlike the
    send-path _Sentinel above (which RAISES to prove a send never reached
    the wire), this one ALWAYS SUCCEEDS and records the APPEND — the draft
    path must never be blocked by the guard, so the assertion here is the
    mirror image: the append happens regardless of what inspect() finds."""

    appended: list = []   # (folder, message_bytes)
    hosts: list = []       # (host, port)

    def __init__(self, host, port, *a, **kw):
        _ImapAppendSentinel.hosts.append((host, port))

    def login(self, user, pw):
        return "OK", [b"done"]

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Drafts) "/" "[Gmail]/Drafts"']

    def append(self, folder, flags, date, message):
        _ImapAppendSentinel.appended.append((folder, message))
        return "OK", [b"1"]

    def logout(self):
        return "OK", [b"done"]


_real_gmail_imaplib = gmail_drafts.imaplib
gmail_drafts.imaplib = types.SimpleNamespace(
    IMAP4_SSL=_ImapAppendSentinel, Time2Internaldate=_real_gmail_imaplib.Time2Internaldate,
)
# The register judgment must NEVER run from the draft path — inspect() is
# deterministic by design. Any call here means the integration reached for
# evaluate()/check() instead, which would also spend money on every draft.
_register_calls: list = []
_real_judge_register = send_guard.judge_register
send_guard.judge_register = (
    lambda *a, **kw: (_register_calls.append(a) or (None, "must not run")))

DRAFT_SETTINGS = _settings(imap_host="imap.invalid", imap_port=993)

try:
    # -- offending body: appended anyway, warnings present in the return AND logged
    _ImapAppendSentinel.appended.clear()
    buf = io.StringIO()
    with redirect_stderr(buf):
        folder, warns = gmail_drafts.append_draft(
            DRAFT_SETTINGS, CUSTOMER, "Re: spostamento", OFFENDING, body_md=True)
    logged = buf.getvalue()
    check("the offending draft is appended anyway",
          len(_ImapAppendSentinel.appended) == 1, _ImapAppendSentinel.appended)
    check("...to the Drafts folder found via IMAP", folder == "[Gmail]/Drafts", folder)
    check("...only the .invalid IMAP host was ever dialed",
          _ImapAppendSentinel.hosts == [("imap.invalid", 993)], _ImapAppendSentinel.hosts)
    check("...guard_warnings names the tells",
          any(w.startswith(TELL_HR) for w in warns)
          and any(w.startswith(TELL_RECIPIENT_IN_BODY) for w in warns), warns)
    check("...exactly one WARNING line is logged", logged.count("WARNING") == 1, logged)
    check("...naming the tells and the recipient in the logged line",
          TELL_HR in logged and CUSTOMER in logged, logged)

    # -- clean body: appended, no warnings, nothing logged
    _ImapAppendSentinel.appended.clear()
    _ImapAppendSentinel.hosts.clear()
    buf = io.StringIO()
    with redirect_stderr(buf):
        folder, warns = gmail_drafts.append_draft(
            DRAFT_SETTINGS, CUSTOMER, "Re: spostamento", LEGITIMATE, body_md=True)
    check("a clean draft is appended with no warnings",
          len(_ImapAppendSentinel.appended) == 1 and warns == [], warns)
    check("...and nothing is logged", buf.getvalue() == "", buf.getvalue())

    # -- fixed-template/human body: body_md left at its default (False) — the
    # guard must not even be consulted, however tell-shaped the text looks.
    _inspect_calls: list = []
    _real_inspect = send_guard.inspect
    send_guard.inspect = (
        lambda *a, _rec=_inspect_calls, **kw: (_rec.append((a, kw)) or _real_inspect(*a, **kw)))
    try:
        _ImapAppendSentinel.appended.clear()
        folder, warns = gmail_drafts.append_draft(
            DRAFT_SETTINGS, CUSTOMER, "Avviso", OFFENDING)  # body_md defaults False
        check("a human/pack-template draft is appended",
              len(_ImapAppendSentinel.appended) == 1, _ImapAppendSentinel.appended)
        check("...with inspect() never called", _inspect_calls == [], _inspect_calls)
        check("...and no warnings surfaced", warns == [], warns)
    finally:
        send_guard.inspect = _real_inspect

    check("the register judgment never ran from the draft path",
          _register_calls == [], _register_calls)
finally:
    gmail_drafts.imaplib = _real_gmail_imaplib
    send_guard.judge_register = _real_judge_register


# --------------------------------------- 6b. campaign.queue_draft wiring end-to-end
print("campaign.queue_draft — guard_warnings reach the verb's own JSON shape")

with tempfile.TemporaryDirectory() as td2:
    contact2 = {"id": "c2", "email": CUSTOMER, "state": "drafted",
                "draft_subject": "Re: spostamento", "draft_body": OFFENDING,
                "dossier": {}, "_campaign_name": "trial", "_campaign_id": "camp1"}
    rpc_calls2: list = []
    st2 = _settings(db_path=str(Path(td2) / "cs.db"), dedup_days=30, timezone="Europe/Rome",
                    pause_path=Path(td2) / "CS_PAUSE", imap_host="imap.invalid", imap_port=993)

    _r_get2, _r_sent2, _r_call2 = (campaign_mod._get_contact,
                                   campaign_mod._sent_threads_to, rpc.call_sync)
    campaign_mod._get_contact = lambda s, cid: dict(contact2) if cid == "c2" else None
    # (threads, unreadable): the gate reads every mailbox in scope, and
    # nothing here is unreadable — what this file varies is the BODY.
    campaign_mod._sent_threads_to = lambda s, e, d: ([], [])
    rpc.call_sync = lambda s, m, p, **kw: rpc_calls2.append((m, p)) or {}
    gmail_drafts.imaplib = types.SimpleNamespace(
        IMAP4_SSL=_ImapAppendSentinel, Time2Internaldate=_real_gmail_imaplib.Time2Internaldate)
    _ImapAppendSentinel.appended.clear()
    try:
        out2 = campaign_mod.queue_draft(st2, "c2", commit=True)
    finally:
        (campaign_mod._get_contact, campaign_mod._sent_threads_to,
         rpc.call_sync) = _r_get2, _r_sent2, _r_call2
        gmail_drafts.imaplib = _real_gmail_imaplib

    check("queue_draft never blocks on a guard hit", out2.get("ok") is True, out2)
    check("...queued_to is the plain folder string (tuple correctly unpacked)",
          out2.get("queued_to") == "[Gmail]/Drafts", out2)
    check("...guard_warnings reaches the verb's own JSON shape",
          bool(out2.get("guard_warnings"))
          and any(w.startswith(TELL_HR) for w in out2["guard_warnings"]), out2)
    check("...the draft was actually appended", len(_ImapAppendSentinel.appended) == 1)
    check("...the contact is still marked gmail_draft_pushed",
          any(m == "campaign.update_contact" and p.get("dossier", {}).get("gmail_draft_pushed")
              for m, p in rpc_calls2), rpc_calls2)


print()
print("RESULT:", "FAIL" if FAIL else "all send-guard gates green")
sys.exit(FAIL)
