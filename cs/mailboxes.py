"""Configured mailbox scope — read, unreadable or deliberately self-owner skipped.

WHY THIS EXISTS: a company answers its customers from several mailboxes, and
the operator's evidence is scoped to one of them. `gmail_archive` reads the
operator mailbox; `cs thread` and `cs ask` read the engine's archive of that
same mailbox. Three surfaces, one bound: when they agree, the agreement reads
as corroboration while it is one absence reported three times. A colleague's
reply, sent from his own mailbox with the operator on no header, exists in none
of them — so "we have never written to this person" gets answered from evidence
that could not have seen the answer.

This module widens the evidence and, more importantly, makes its EDGE VISIBLE.

  * WHICH mailboxes. The operator's own, plus every account registered in
    `CS_ACCOUNTS` (`Settings.account_map`), plus every address declared in
    `manifest.toml [operator].read_mailboxes`. Both registries are
    configuration, edited for other reasons, so the scope is coupled to lists
    nobody maintains with dedup in mind — which is exactly why every answer
    prints read, unreadable and deliberately skipped mailboxes. A mailbox is
    never asked about its own owner; the shared rule applies to single-address
    and multi-address reads, including send gates. There is no scope flag:
    a knob that let one clone gate on one mailbox and another on five is the
    dedup-source knob the charter forbids, wearing a different name.

  * WHERE the credential comes from. Two sources, one fan-out. An account with
    an ENGINE PROFILE hands its mailbox password over itself, with
    owner-authenticated `settings.get_secret` over that profile's own socket —
    the same handover `cs init` uses (`cs/project_init.py`). A DECLARED mailbox
    has no profile and never will: the people who answer customers from their
    own mailboxes contribute nothing, ever, which is the binding constraint
    this design is built around. Its credential is an ordinary IMAP password in
    the clone's own env file (`CS_READ_MAILBOX_PASSWORDS`, beside
    `EMAIL_PASSWORD`, in no repo), parsed strictly at config load
    (`cs/config.parse_read_credentials`).

    Standard IMAP, not a vendor API: the read path is the one this kernel
    already speaks, so reaching a profile-less mailbox adds no dependency and
    no provider coupling. The trade-off is stated rather than hidden — such a
    password can also send, so read-only is a property of this code, not of the
    credential. What contains it: it never becomes a value `cs config` prints
    (it is in `SECRET_FIELDS`), it is redacted out of every error path here,
    and it never reaches a send path — `send_mail` logs in with
    `email_address`/`email_password` and nothing else.

  * WHAT a failure renders as. `unreadable`, never an empty result. A failed
    login and a genuine absence must never render the same, or the fan-out
    reproduces inside the fix the very error it exists to prevent. Every
    per-mailbox failure — no engine session, a stopped daemon, a profile with
    no stored password, a refused IMAP login — is caught HERE and reported as
    a named mailbox with a reason. None of them reaches `cli.main`'s
    connection handler, which would report an IMAP failure as "cannot reach
    the engine": a confidently wrong diagnosis.

Only functions that decide nothing from "is this us" can be fanned out.
`sent_to` and `inbound_since` qualify. `thread_with` and `inbound_recent`
derive direction from `settings.email_address` and would misattribute every
message in another mailbox, so they stay single-mailbox and say so.

Read-only throughout: SEARCH and BODY.PEEK header fetches, no writes, no flag
changes. One IMAP session per mailbox per process, reused — the per-call TLS,
LOGIN, LIST and SELECT is the whole cost of a fan-out, and a gate that pays it
once per candidate per mailbox is a gate nobody can afford.
"""
from __future__ import annotations

import imaplib
from dataclasses import dataclass, field
from typing import Callable, Iterable

from . import config as config_mod
from . import gmail_archive, gmail_drafts, rpc
from .config import Settings


# What a declared read-only mailbox is CALLED in a scope line. Profile accounts
# carry their registry name; these have none — they are declared in the
# manifest and opened with a credential from the clone's env, and that is what
# the operator needs to know to fix one.
DECLARED = "declared"

# The one sentence every incomplete answer ends on, wherever it is rendered.
# It is the whole point of the `unreadable` outcome: an absence of evidence is
# not evidence of absence, and the reader is about to act on it.
INCOMPLETE = "A message absent from this answer is not proof that none exists."


@dataclass(frozen=True)
class Mailbox:
    """One readable mailbox: who it belongs to, and how to open it.

    `password` is `repr=False` DELIBERATELY. A dataclass repr lands in
    tracebacks, log lines and `print(obj)`, and this one carries a
    send-capable credential for somebody else's mailbox."""

    account: str          # the CS_ACCOUNTS name, or the default account's name
    address: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class Unreadable:
    """One mailbox this process could NOT read, and why — in the operator's
    terms, naming the mailbox to fix."""

    account: str
    address: str          # "" when the address itself could not be learned
    reason: str

    def describe(self) -> str:
        who = f"{self.account} <{self.address}>" if self.address else self.account
        return f"{who} — {self.reason}"


@dataclass(frozen=True)
class Skipped:
    """One mailbox this process DELIBERATELY did not read, and why.

    Distinct from `Unreadable` on purpose, and the distinction is load-bearing.
    `Unreadable` is a failure: a send gate refuses on it
    (`cs/campaign.py` `_evidence_refusal`), every `ready` draft row carries it
    as `evidence_incomplete`, and the operator is told to go fix a credential.
    A skip is none of that — it is a mailbox we chose not to ask because asking
    it could not produce evidence. Recording a skip as `Unreadable` would
    refuse every campaign send to a colleague's address, forever, over nothing.

    But it is not `read` either: `scope_line()` printing "4 of 4 read" when one
    was skipped is precisely the invisible narrowing this module exists to
    prevent. So: a third outcome, named and printed."""

    account: str
    address: str
    reason: str

    def describe(self) -> str:
        who = f"{self.account} <{self.address}>" if self.address else self.account
        return f"{who} — {self.reason}"


@dataclass
class Fanout:
    """The answer plus the scope it was answered from.

    `rows` are the underlying reader's rows, each tagged with the `mailbox`
    they came from. `read` is what was actually opened; `unreadable` records failed required
    reads; `skipped` records deliberate self-owner exclusions. A caller that ignores `unreadable` is reading an absence as a
    fact, which is the failure this whole module exists to prevent."""

    rows: list[dict]
    read: list[str]
    unreadable: list[Unreadable]
    skipped: list[Skipped] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        # A deliberate skip does NOT make a scope incomplete: nothing was lost,
        # because the mailbox could not have answered the question. Only a
        # mailbox we wanted and could not open does.
        return not self.unreadable

    def scope_line(self) -> str:
        """The scope actually read, printed on EVERY answer — complete or not.

        A scope that can silently narrow is the incident; a scope that narrows
        visibly is a fact the operator can act on."""
        # Distinct mailboxes, because a mailbox can be BOTH read and partially
        # skipped — read for the other contacts, not asked about its own owner.
        # Counting it twice printed "2 of 3" over two mailboxes, which is the
        # same misleading arithmetic this line exists to prevent, inverted.
        names = {a.strip().lower() for a in self.read}
        read_count = len(names)
        names |= {(u.address or u.account).strip().lower() for u in self.unreadable}
        names |= {(k.address or k.account).strip().lower() for k in self.skipped}
        line = f"scope: {read_count} of {len(names)} mailbox(es) read"
        if self.read:
            line += " — " + ", ".join(self.read)
        if self.skipped:
            # Named, never folded into the denominator silently: "3 of 3" when
            # a fourth was skipped is the invisible narrowing itself.
            line += "; not asked about their own owner: " + "; ".join(
                k.describe() for k in self.skipped)
        if self.unreadable:
            line += "; UNREADABLE, so this answer is INCOMPLETE: " + "; ".join(
                u.describe() for u in self.unreadable
            )
        return line

    def note(self) -> str | None:
        """The degraded-source note for machine-readable shapes — None when the
        scope was complete. Same convention as the CRM note the sweep carries:
        a degraded source travels WITH the data, not only in the printed line."""
        if self.complete:
            return None
        return (
            "evidence INCOMPLETE — "
            + "; ".join(u.describe() for u in self.unreadable)
            + ". "
            + INCOMPLETE
        )

    def as_dict(self) -> dict:
        return {
            "rows": self.rows,
            "scope": {
                "read": list(self.read),
                "unreadable": [
                    {"account": u.account, "address": u.address, "reason": u.reason}
                    for u in self.unreadable
                ],
                "skipped": [
                    {"account": k.account, "address": k.address, "reason": k.reason}
                    for k in self.skipped
                ],
                "complete": self.complete,
            },
            "note": self.note(),
        }


def merge_directions(sent: Fanout, inbound: Fanout) -> Fanout:
    """Two fan-outs over the same scope, as ONE answer with a `direction` on
    every row (`sent` = we wrote it, `in` = they did).

    The scopes are unioned rather than assumed equal: a mailbox can be readable
    for one call and dead by the next, and the answer must carry the WORST case
    it saw, never the better of the two.

    ONE record per MAILBOX, keyed `(account, address)` and never by the whole
    record. The two fan-outs read different folders, so one dead mailbox fails
    them in two different places — `SELECT [Gmail]/Sent Mail` on one pass, the
    All Mail SEARCH on the other — and record-equality dedup let that mailbox
    be counted twice: `scope: 1 of 3 mailbox(es) read` out of two mailboxes. A
    scope line that overstates its own denominator is the class of wrong
    evidence this module exists to stop.

    Distinct reasons are KEPT, joined, rather than one being chosen: they are
    two different diagnoses of the same mailbox and the operator needs both to
    know what to fix. An identical reason (the ordinary case — a refused login
    fails both passes the same way) collapses to one."""
    rows = [{**r, "direction": "sent"} for r in sent.rows]
    rows += [{**r, "direction": "in"} for r in inbound.rows]
    read = []
    seen = set()
    for address in sent.read + inbound.read:
        key = address.strip().lower()
        if key not in seen:
            read.append(address)
            seen.add(key)
    merged: dict[tuple[str, str], Unreadable] = {}
    for u in list(sent.unreadable) + list(inbound.unreadable):
        key = (u.account, u.address.strip().lower())
        prev = merged.get(key)
        if prev is None:
            merged[key] = u
        elif u.reason not in prev.reason:
            merged[key] = Unreadable(
                prev.account, prev.address, f"{prev.reason} / {u.reason}"
            )
    bad = list(merged.values())
    # A mailbox that failed either call is not a mailbox that was read.
    failed = {u.address.strip().lower() for u in bad if u.address}
    read = [a for a in read if a.strip().lower() not in failed]
    skipped: dict[tuple[str, str], Skipped] = {}
    for item in sent.skipped + inbound.skipped:
        key = (item.account, item.address.strip().lower())
        previous = skipped.get(key)
        if previous is None:
            skipped[key] = item
        elif item.reason != previous.reason and item.reason not in previous.reason:
            skipped[key] = Skipped(previous.account, previous.address,
                                   f"{previous.reason} / {item.reason}")
    return Fanout(rows=rows, read=read, unreadable=bad, skipped=list(skipped.values()))


class MailboxUnreadable(RuntimeError):
    """A mailbox could not be opened. The message is operator-facing and is
    what lands in `Unreadable.reason`."""


# --------------------------------------------------------------- credentials

# uid -> Mailbox, for THIS process. A send gate asks per candidate contact, and
# one engine round trip per candidate per mailbox is not a cost any tick can
# carry. Never persisted: the credential lives as long as the process and no
# longer.
_CREDENTIALS: dict[str, Mailbox] = {}


def _redact(text: str, secrets: Iterable[str]) -> str:
    """Blank out anything secret an exception message may have echoed back.

    Defence in depth: no library here is known to put the password in its
    error, and a reason string ends up on stdout, in cron logs and in an
    agent's context, so "known to" is not the standard to hold it to."""
    out = str(text)
    for s in secrets:
        s = (s or "").strip()
        if len(s) >= 6 and s in out:
            out = out.replace(s, "<redacted>")
    return out


def _reason(exc: BaseException, *secrets: str) -> str:
    """One operator-readable line for a failure, secret-free.

    `imaplib` names its exception class `error`, so the bare type name reads as
    "error: <server text>" and says nothing about WHICH component refused —
    which is the one thing the reader needs, since the same run also talks to
    the engine."""
    name = "IMAP" if isinstance(exc, imaplib.IMAP4.error) else type(exc).__name__
    return _redact(f"{name}: {exc}", secrets)


def credential(settings: Settings, account: str, uid: str) -> Mailbox:
    """That account's own mailbox address and password, from ITS engine profile.

    Authenticated as the profile owner: `config.load(engine_owner_uid=uid)`
    derives that uid's own session files, so the socket handshake presents that
    profile's token and the daemon's `token.sub == OWNER_ID` gate passes on its
    own terms. This is the handover `cs init` performs for the operator mailbox,
    aimed at a second account — no new mechanism, no second registry, and no
    place for a human to retype a secret.

    Two calls, both charter-listed shapes: `settings.get` -> `{values}` for the
    non-secret `EMAIL_ADDRESS`, and `settings.get_secret` -> `{key, value}` for
    the one secret. `settings.get` masks every secret deliberately, which is
    why the password needs its own named call.

    Cached per process. Raises `MailboxUnreadable` — never returns a Mailbox
    with a missing half, because a mailbox opened with an empty password reads
    as an empty mailbox."""
    cached = _CREDENTIALS.get(uid)
    if cached is not None:
        return cached

    acct = config_mod.load(engine_owner_uid=uid)
    try:
        got = rpc.call_sync(acct, "settings.get", {}, timeout=30)
    except Exception as e:  # noqa: BLE001 — one mailbox degrades, never the run
        raise MailboxUnreadable(
            f"cannot read the engine profile for account {account!r} "
            f"({_reason(e)}) — is that profile signed in (`cs login`) and its "
            f"daemon running?"
        ) from None
    values = (got or {}).get("values") or {}
    address = str(values.get("EMAIL_ADDRESS") or "").strip()
    if not address:
        raise MailboxUnreadable(
            f"the engine profile for account {account!r} declares no "
            f"EMAIL_ADDRESS — it cannot say which mailbox it is"
        )
    try:
        secret = rpc.call_sync(
            acct, "settings.get_secret", {"key": "EMAIL_PASSWORD"}, timeout=30
        )
    except Exception as e:  # noqa: BLE001
        raise MailboxUnreadable(
            f"the engine profile for {address} refused its mailbox credential "
            f"({_reason(e)})"
        ) from None
    password = str((secret or {}).get("value") or "")
    if not password.strip():
        raise MailboxUnreadable(
            f"the engine profile for {address} stores no EMAIL_PASSWORD — set "
            f"it in that profile, or its mailbox stays unreadable"
        )
    mb = Mailbox(account=account, address=address, password=password)
    _CREDENTIALS[uid] = mb
    return mb


# ------------------------------------------------------------------ sessions

# address -> live IMAP session, for THIS process.
_SESSIONS: dict[str, imaplib.IMAP4_SSL] = {}


def session(settings: Settings, mailbox: Mailbox) -> imaplib.IMAP4_SSL:
    """The open IMAP session for `mailbox`, opening one only if needed.

    Reuse is the point. Every reader in `gmail_archive` opens its own TLS +
    LOGIN + LIST + SELECT and logs out again; the campaign runner pays that
    once per drafted contact, and multiplying it by N mailboxes is what would
    make a fan-out unusable. A cached session that has since died (idle
    timeout, network drop) is detected by NOOP and replaced, so reuse never
    turns into a stale-connection failure."""
    live = _SESSIONS.get(mailbox.address)
    if live is not None:
        try:
            typ, _ = live.noop()
            if typ == "OK":
                return live
        except (imaplib.IMAP4.error, OSError):
            pass
        _drop(mailbox.address)
    M = gmail_drafts._imap(settings, (mailbox.address, mailbox.password))
    _SESSIONS[mailbox.address] = M
    return M


def _drop(address: str) -> None:
    M = _SESSIONS.pop(address, None)
    if M is None:
        return
    try:
        M.logout()
    except Exception:  # noqa: BLE001 — closing a broken socket is best-effort
        pass


def close_sessions() -> None:
    """Log out of every open mailbox. A verb that has finished answering calls
    this; a long-running process does not have to."""
    for address in list(_SESSIONS):
        _drop(address)


# ------------------------------------------------------------------- fan-out


def _default_account_name(settings: Settings) -> str:
    """What to CALL the operator's own mailbox in a scope line: its registry
    name when it has one, otherwise a neutral label. Never a literal."""
    uid = (settings.engine_owner_uid or "").strip()
    for name, u in settings.account_map.items():
        if u == uid:
            return name
    return (settings.accounts_default or "").strip() or "operator"


def operator_mailbox(settings: Settings) -> Mailbox:
    """This clone's own operator mailbox, from Settings — no engine round trip.

    Its credential is the one the clone already holds for drafting and
    fixed-template bulk; the engine handover above is for the OTHER accounts."""
    address = (settings.email_address or "").strip()
    account = _default_account_name(settings)
    if not address:
        raise MailboxUnreadable(
            "this clone declares no operator mailbox (email_address) — "
            "run `cs init` or set it in manifest.toml [operator]"
        )
    if not (settings.email_password or "").strip():
        raise MailboxUnreadable(
            f"no mailbox password for {address} — `cs init` reads it from the "
            f"engine (settings.get_secret), or set EMAIL_PASSWORD in this "
            f"clone's env"
        )
    return Mailbox(account=account, address=address, password=settings.email_password)


def readable(settings: Settings) -> tuple[list[Mailbox], list[Unreadable]]:
    """Configured credentials, split into available and unavailable identities.

    This resolves credentials without opening IMAP. Deduped by address: an
    account registered twice, or serving the operator identity, appears once.
    The caller then applies the fixed self-owner skip before any IMAP open."""
    boxes: list[Mailbox] = []
    bad: list[Unreadable] = []
    seen: set[str] = set()

    try:
        mb = operator_mailbox(settings)
        boxes.append(mb)
        seen.add(mb.address.lower())
    except MailboxUnreadable as e:
        bad.append(
            Unreadable(
                _default_account_name(settings),
                (settings.email_address or "").strip(),
                str(e),
            )
        )

    own_uid = (settings.engine_owner_uid or "").strip()
    for name, uid in sorted(settings.account_map.items()):
        if not uid or uid == own_uid:
            continue
        try:
            mb = credential(settings, name, uid)
        except MailboxUnreadable as e:
            bad.append(Unreadable(name, "", str(e)))
            continue
        except Exception as e:  # noqa: BLE001 — never let one account end the run
            bad.append(Unreadable(name, "", _reason(e)))
            continue
        if mb.address.lower() in seen:
            continue
        seen.add(mb.address.lower())
        boxes.append(mb)

    # The DECLARED mailboxes: this company's other mailboxes, named in the
    # manifest, opened with a credential from the clone's own env. They hold no
    # engine profile and their owners are asked for nothing — which is the
    # whole point, because the mailbox that answered the customer in the
    # incident this module exists for is one of them, and always will be.
    creds = settings.read_mailbox_credentials
    for address in settings.read_mailbox_list:
        if address in seen:
            continue
        seen.add(address)
        password = creds.get(address, "")
        if not password:
            # Declared and unopenable is UNREADABLE, never absent — and the
            # message carries the fix, because the operator reading it is the
            # one person who can apply it.
            bad.append(
                Unreadable(
                    DECLARED,
                    address,
                    f"no credential configured for {address} — add "
                    f"'{address}:<app password>' to CS_READ_MAILBOX_PASSWORDS in "
                    f"{settings.state_dir}/.env",
                )
            )
            continue
        boxes.append(Mailbox(account=DECLARED, address=address, password=password))
    return boxes, bad


def _ask_addresses(mailbox: Mailbox, addresses: Iterable[str]) -> tuple[list[str], Skipped | None]:
    """Remove known owner pairs and retain their named deliberate omission."""
    wanted = [a.strip().lower() for a in addresses if a and a.strip()]
    owner = mailbox.address.strip().lower()
    ask = [a for a in wanted if not owner or a != owner]
    if len(ask) == len(wanted):
        return ask, None
    reason = (f"not asked about its own owner {mailbox.address}" if ask else
              "every address asked about is this mailbox's own owner — its "
              "own outbox cannot say whether they wrote to us")
    return ask, Skipped(mailbox.account, mailbox.address, reason)


def _fan(
    settings: Settings,
    boxes: list[Mailbox],
    bad: list[Unreadable],
    addr: str,
    run: Callable[[imaplib.IMAP4_SSL], list[dict]],
) -> Fanout:
    """Read each eligible mailbox, tagging rows, self-owner skips and failures.

    The `except` is deliberately broad and deliberately HERE: an IMAP LOGIN
    refusal raises `imaplib.IMAP4.error`, which `cli.main` does not catch (a
    traceback), and a connection-level IMAP failure IS caught there and
    reported as "cannot reach the engine". Both are wrong answers about the
    wrong component. A per-mailbox failure is a per-mailbox fact."""
    rows: list[dict] = []
    read: list[str] = []
    failed = list(bad)
    skipped: list[Skipped] = []
    for mb in boxes:
        _ask, omission = _ask_addresses(mb, [addr])
        if omission is not None:
            skipped.append(omission)
            continue
        try:
            M = session(settings, mb)
            got = run(M)
        except Exception as e:  # noqa: BLE001 — one mailbox degrades, not the run
            _drop(mb.address)
            failed.append(Unreadable(mb.account, mb.address, _reason(e, mb.password)))
            continue
        for row in got:
            rows.append({**row, "mailbox": mb.address})
        read.append(mb.address)
    return Fanout(rows=rows, read=read, unreadable=failed, skipped=skipped)


def headers_since_across(settings: Settings, addrs: Iterable[str], key: str,
                         since=None) -> Fanout:
    """Messages involving `addrs`, across the configured scope with self-owner skip —
    ONE search + chunked FETCH per mailbox, and a mailbox is never asked about
    its OWN owner.

    The single-address readers and this multi-address reader share the same
    self-owner skip. The operator decision of 2026-10-06 permits it in send
    gates: a colleague's outbox to third parties is not reply evidence.
    Unreadable evidence still refuses; a real answer remains visible from
    another in-scope mailbox. This bulk reader serves reconcile; the gates
    continue to call their single-address readers.

    **The self-exclusion.** A mailbox is not asked about its own owner. Asking
    a colleague's own mailbox "has this colleague written" matches their entire
    sent history — measured once at 21,637 messages against 49 for all other
    contacts in that folder combined — and every one of those then reads as
    "they wrote again", so a draft addressed to a colleague is marked
    `overtaken` because they mailed *somebody*. The question is whether they
    wrote TO US, and a person's own outbox cannot answer it. Nothing is lost: a
    message they genuinely sent us is in the RECIPIENT's mailbox too, and every
    in-scope recipient is already in the fan.

    The skip is reported as `Fanout.skipped` — never `unreadable`, which would
    make the send gates refuse that colleague forever, and never silence, which
    would print "3 of 3 read" over a scope that narrowed."""
    boxes, bad = readable(settings)
    addrs = [a.strip().lower() for a in addrs if a and a.strip()]
    flag, default = ("\\sent", "[Gmail]/Sent Mail") if key == "TO" else (
        "\\all", "[Gmail]/All Mail")

    rows: list[dict] = []
    read: list[str] = []
    failed = list(bad)
    skipped: list[Skipped] = []
    for mb in boxes:
        ask, omission = _ask_addresses(mb, addrs)
        if omission is not None:
            skipped.append(omission)
        if not ask:
            continue
        try:
            M = session(settings, mb)
            got = gmail_archive.headers_for_addresses_on(
                M, ask, key, flag, default, since=since)
        except Exception as e:  # noqa: BLE001 — one mailbox degrades, not the run
            _drop(mb.address)
            failed.append(Unreadable(mb.account, mb.address, _reason(e, mb.password)))
            continue
        for row in got:
            rows.append({**row, "mailbox": mb.address})
        read.append(mb.address)

    return Fanout(rows=rows, read=read, unreadable=failed, skipped=skipped)


def sent_to_across(settings: Settings, addr: str, days: int | None = None) -> Fanout:
    """"Has anyone here ever written to this address?" — configured Gmail Sent
    scope, fixed self-owner skip, unbounded by default.

    The window costs nothing to drop: `sent_to` fetches every matching UID's
    header and filters by Date afterwards, so `days=None` costs what `days=30`
    costs. And "have we ever" has no natural horizon — the case this exists for
    was 61 days old, which a 60-day gate misses by one."""
    boxes, bad = readable(settings)
    return _fan(settings, boxes, bad, addr, lambda M: gmail_archive.sent_to_on(M, addr, days))


def inbound_since_across(settings: Settings, addr: str, after=None) -> Fanout:
    """"Has this address written to anyone here?" — configured All Mail scope,
    fixed self-owner skip. Safe to fan out for the same reason `sent_to`: no decision
    from "is this us"."""
    boxes, bad = readable(settings)
    return _fan(
        settings, boxes, bad, addr, lambda M: gmail_archive.inbound_since_on(M, addr, after)
    )


def sent_to_here(settings: Settings, addr: str, days: int | None = None) -> Fanout:
    """`sent_to` over the OPERATOR mailbox, with the fixed self-owner skip.

    Not a narrowing knob — the caller is the dedup verb, whose question really
    is about that one mailbox and whose window really is the re-contact policy.
    What it buys is the third outcome: a mailbox that cannot be opened comes
    back as `unreadable` here too, instead of raising past the CLI as a
    traceback or rendering as "never contacted"."""
    try:
        boxes, bad = [operator_mailbox(settings)], []
    except MailboxUnreadable as e:
        boxes, bad = [], [
            Unreadable(
                _default_account_name(settings),
                (settings.email_address or "").strip(),
                str(e),
            )
        ]
    return _fan(settings, boxes, bad, addr, lambda M: gmail_archive.sent_to_on(M, addr, days))
