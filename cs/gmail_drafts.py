"""Put outreach drafts where the operator actually works: Gmail Drafts.

Phase-1 review surface: the engine composes (memory + voice + threading),
cs APPENDs the result into the operator's Gmail Drafts; the operator reviews,
edits and SENDS from Gmail. The sent mail lands in Gmail Sent and the
engine's normal sync picks it up — archive, threading and dedup stay
correct with zero extra plumbing. The engine-side Draft store is NOT used
in this flow (single copy, no divergence).

The surface was append-only until 2026-08-23, when a composed draft quoted a
sentence the customer had never written and nothing in cs could take it back:
a bad draft sat in the review queue where a human could send it by mistake. A
draft is a loaded gun until somebody removes it, so `delete_draft` exists —
ONE named draft per call, dry-run by default, moved to Trash (recoverable)
and never expunged. See its docstring; it is the only write here that is not
an append.

This path is deliberately UNGUARDED in the blocking sense used by
`cs/send_mail.py`: a Gmail draft IS the human review surface, so a bad body
must reach the reviewer's eyes, not be hidden or refused. What it does get is
the middle ground — `append_draft(..., body_md=True)` runs the send guard's
DETERMINISTIC tells (`cs/send_guard.py`'s `inspect()`; no LLM, no cost) on
model-composed bodies and surfaces any hits as warnings (logged here, and
returned so the caller can put them in its own JSON/stdout shape). It never
blocks, never raises, and never alters `body`. See `append_draft` below.
"""
from __future__ import annotations

import imaplib
import re
import sys
import time
from email.message import EmailMessage
from email.utils import formatdate

from .config import Settings
from .thread_key import thread_key


def _imap(settings: Settings) -> imaplib.IMAP4_SSL:
    M = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    # tolerate the spaced app-password paste
    M.login(settings.email_address, settings.email_password.replace(" ", "").strip())
    return M


def _find_special(M: imaplib.IMAP4_SSL, flag: str) -> str | None:
    """Folder carrying a given IMAP special-use flag (locale-proof), or None
    when the server advertises no such folder — e.g. `\\drafts`, `\\trash`.

    Returning None matters: a caller that DELETES must refuse rather than fall
    back to a guessed folder name, which on a non-English mailbox would be the
    wrong folder or no folder at all."""
    typ, data = M.list()
    if typ == "OK":
        for raw in data or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            if flag in line.lower() and '"' in line:
                return line.rsplit('"', 2)[-2]
    return None


def find_drafts_folder(M: imaplib.IMAP4_SSL) -> str:
    """Folder carrying the \\Drafts special-use flag (locale-proof).

    Falls back to Gmail's own English name for the APPEND/LIST paths, where a
    wrong guess costs a failed append, not a lost message. The delete path does
    NOT use this: it resolves strictly via `_find_special` and refuses on None."""
    return _find_special(M, "\\drafts") or "[Gmail]/Drafts"


def find_trash_folder(M: imaplib.IMAP4_SSL) -> str | None:
    """Folder carrying the \\Trash special-use flag (locale-proof), or None."""
    return _find_special(M, "\\trash")


def append_draft(
    settings: Settings,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
    html: str | None = None,
    cc: str | None = None,
    body_md: bool = False,
) -> tuple[str, list[str]]:
    """Append one draft; returns ``(folder, guard_warnings)``.

    With ``html``, the draft is multipart/alternative: ``body`` is the
    text/plain fallback, ``html`` the rich part (clean anchor text, full
    URLs — UTM included — only in href).

    ``body_md=True`` marks ``body`` as MODEL-COMPOSED text — the same marker
    role `send_mail.send`'s `body_md` parameter plays on the send path (see
    `cs/send_guard.py`). It is a bool here, not the text itself, because
    `body` is always present regardless of source; the flag only says
    whether it is worth inspecting. When set, this runs the guard's
    DETERMINISTIC tells (`send_guard.inspect()` — no LLM, no cost) and, if
    any fire, logs ONE warning naming them and returns their string forms as
    `guard_warnings`. It NEVER blocks the append and NEVER alters `body` —
    the draft is the human review surface, so a bad body must reach the
    reviewer, not be hidden. Defaults to False, so human/pack-template
    callers (e.g. `send_first`'s draft branch, fixed-template copy from a
    campaign pack) are unaffected and never pay for an inspection they don't
    need."""
    guard_warnings: list[str] = []
    if body_md:
        from . import send_guard

        tells = send_guard.inspect(body, to, settings=settings)
        if tells:
            guard_warnings = [str(t) for t in tells]
            sys.stderr.write(
                f"[gmail_drafts] WARNING: draft to {to} tripped send-guard "
                f"tell(s) — review before sending: {'; '.join(guard_warnings)}\n"
            )

    msg = EmailMessage()
    msg["From"] = settings.email_address
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = " ".join(references or [in_reply_to])
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    M = _imap(settings)
    try:
        folder = find_drafts_folder(M)
        typ, resp = M.append(
            f'"{folder}"', r"(\Draft)", imaplib.Time2Internaldate(time.time()), msg.as_bytes()
        )
        if typ != "OK":
            raise RuntimeError(f"IMAP APPEND failed: {typ} {resp!r}")
        return folder, guard_warnings
    finally:
        try:
            M.logout()
        except Exception:
            pass


def list_drafts(settings: Settings) -> list[dict]:
    """Header summaries of the drafts waiting in the operator's Gmail Drafts —
    the review queue the operator sends from. Read-only.

    Each row carries its `uid`: that is the handle `delete_draft` takes, and
    without it the operator has no way to NAME the draft they want gone. UID
    commands (not sequence numbers) for exactly that reason — a sequence number
    shifts the moment any other message leaves the folder, so it can never be
    quoted back as an identifier.

    Each row also carries the CONVERSATION it belongs to: `references`,
    `in_reply_to` and the `thread_key` derived from them (`cs/thread_key.py`,
    the same string the engine stores as `thread_id`). `append_draft` already
    writes both headers, so this costs two more header fields in a FETCH that
    was happening anyway — and without the key a draft cannot be reconciled
    against the thread it answers (`cs/draft_state.py`) nor paired with the
    engine's own copy of itself."""
    import email as _email

    M = _imap(settings)
    try:
        folder = find_drafts_folder(M)
        M.select(f'"{folder}"', readonly=True)
        typ, data = M.uid("SEARCH", None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        out = []
        for uid in data[0].split():
            typ, md = M.uid(
                "FETCH",
                uid,
                "(BODY.PEEK[HEADER.FIELDS (TO SUBJECT DATE MESSAGE-ID "
                "REFERENCES IN-REPLY-TO)])",
            )
            if typ != "OK" or not md or not md[0]:
                continue
            hdr = _email.message_from_bytes(md[0][1])
            out.append({"uid": uid.decode(), "to": hdr.get("To"),
                        "subject": hdr.get("Subject"), "date": hdr.get("Date"),
                        "message_id": hdr.get("Message-ID"),
                        "references": hdr.get("References"),
                        "in_reply_to": hdr.get("In-Reply-To"),
                        "thread_key": thread_key(hdr.get("Message-ID"),
                                                 hdr.get("References"),
                                                 hdr.get("In-Reply-To"))})
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


_UID_RE = re.compile(r"^[0-9]+$")


def _draft_row(M: imaplib.IMAP4_SSL, uid: bytes) -> dict:
    """What one candidate IS, in the terms a human recognises it by: flags plus
    recipient / subject / date / Message-ID. Headers only, never the body —
    identification, not a second review surface. BODY.PEEK, so a refusal never
    marks anything \\Seen."""
    import email as _email

    typ, md = M.uid(
        "FETCH", uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (TO SUBJECT DATE MESSAGE-ID)])"
    )
    flags, hdr = "", None
    for part in (md or []) if typ == "OK" else []:
        if isinstance(part, tuple):
            if part[0]:
                flags += part[0].decode(errors="replace")
            if part[1]:
                hdr = _email.message_from_bytes(part[1])
        elif isinstance(part, bytes):
            flags += part.decode(errors="replace")
    return {
        "uid": uid.decode(),
        "flags": flags,
        "to": (hdr.get("To") if hdr else None),
        "subject": (hdr.get("Subject") if hdr else None),
        "date": (hdr.get("Date") if hdr else None),
        "message_id": (hdr.get("Message-ID") if hdr else None),
    }


def delete_draft(
    settings: Settings,
    uid: str | None = None,
    message_id: str | None = None,
    *,
    commit: bool = False,
) -> dict:
    """Remove ONE named draft from Gmail Drafts by MOVING it to Trash.

    Why it exists: the review queue is where a wrong draft waits to be sent by
    a human who trusts it. Composing a replacement does not retract the bad
    one, and until this verb the bad one could not be removed at all.

    THE KEY IS THE IMAP UID. It is the only identifier every draft actually
    has: what `append_draft` uploads carries NO Message-ID header (an
    `EmailMessage` gets one only if someone sets it, and nothing here does —
    verified against the stdlib), so unless the server mints one on APPEND, a
    Message-ID lookup finds nothing for exactly the drafts cs itself wrote —
    the ones this verb was built for.
    `message_id` is therefore a CROSS-CHECK on the uid (both given:
    the uid must be among the header's hits) and only a selector of last resort
    when it is given alone. UIDs ascend and are never reused within a
    UIDVALIDITY (RFC 3501), so a stale uid resolves to nothing rather than to
    somebody else's draft: whatever happened to the draft in between — edited
    into a new message, sent, deleted — the failure is "no draft matches", not
    the wrong deletion.

    TRASH, NOT EXPUNGE — deliberately. `\\Deleted` + EXPUNGE destroys the
    message: on Gmail what an expunge does next is a per-account setting
    ("auto-expunge", and what the last-label removal does), so the same call
    means different things on two mailboxes, and on the destructive reading
    there is nothing left to recover. A message moved to Trash is retrievable
    for 30 days by the operator, in Gmail, with no tooling. This function never
    sets \\Deleted and never expunges; if the server offers no \\Trash folder
    or no MOVE, it refuses instead of falling back to the unrecoverable path.

    Dry-run by DEFAULT (`commit=False`), like the campaign verbs: it reports
    what it would delete and the folder it would move it to, and the IMAP
    session is selected READ-ONLY, so the connection is structurally incapable
    of writing. One draft per call; there is no bulk form, no wildcard and no
    "every draft for this address" — a lookup matching zero or more than one
    draft REFUSES and reports what it matched, so the caller names one.

    Returns the kernel's usual result dict: `{"ok": bool, ...}` with
    `dry_run`/`target`/`would_move_to` on a dry run, `moved_to` on a commit,
    `refused` + `matched` on a refusal. Never raises for a normal refusal."""
    uid = str(uid).strip() if uid is not None else ""
    message_id = (message_id or "").strip()
    if not uid and not message_id:
        return {"ok": False, "error": "name the draft: uid (see `review --json`, "
                                      "or `list_drafts`) and/or message_id — "
                                      "this verb never picks one for you"}
    if uid and not _UID_RE.match(uid):
        return {"ok": False, "error": f"not an IMAP UID: {uid!r} (digits only)"}
    if message_id:
        # The value goes into an IMAP SEARCH as a quoted string; a quote,
        # backslash or CRLF in it would end the string / the command. Refuse
        # rather than escape: a Message-ID containing any of them is malformed.
        if any(c in message_id for c in '"\\\r\n'):
            return {"ok": False, "error": "message_id contains a character that "
                                          "cannot appear in an IMAP SEARCH string"}
        if not message_id.startswith("<"):
            message_id = f"<{message_id}>"

    M = _imap(settings)
    try:
        # Strict resolution: no folder carries \Drafts → refuse. The APPEND
        # path may guess "[Gmail]/Drafts"; a delete may not.
        folder = _find_special(M, "\\drafts")
        if not folder:
            return {"ok": False, "refused": "no folder carries the \\Drafts "
                    "special-use flag — refusing to delete inside a guessed folder"}
        typ, _ = M.select(f'"{folder}"', readonly=not commit)
        if typ != "OK":
            return {"ok": False, "refused": f"cannot select the drafts folder {folder!r}"}

        if message_id:
            typ, d = M.uid("SEARCH", None, "HEADER", "Message-ID", f'"{message_id}"')
            matched = d[0].split() if (typ == "OK" and d and d[0]) else []
            if uid:
                # Both given: the header search NARROWS, never widens.
                matched = [u for u in matched if u.decode() == uid]
        else:
            typ, d = M.uid("SEARCH", None, "UID", uid)
            matched = d[0].split() if (typ == "OK" and d and d[0]) else []

        # Report what was matched, capped — a refusal is for a human to read.
        rows = [_draft_row(M, u) for u in matched[:10]]
        if len(matched) != 1:
            return {
                "ok": False,
                "refused": ("no draft matches" if not matched
                            else "more than one draft matches — name one by uid"),
                "folder": folder,
                "selector": {"uid": uid or None, "message_id": message_id or None},
                "match_count": len(matched),
                "matched": rows,
            }

        target = rows[0]
        # Second guard on "am I really in Drafts": a message in this folder that
        # is not flagged \Draft is not a draft, whatever the folder is called.
        if "\\Draft" not in target["flags"]:
            return {"ok": False, "refused": "the matched message is not flagged "
                    "\\Draft — refusing to delete a non-draft",
                    "folder": folder, "target": target}

        trash = find_trash_folder(M)
        if not trash:
            return {"ok": False, "refused": "no folder carries the \\Trash "
                    "special-use flag — refusing, because the only alternative "
                    "is an unrecoverable expunge",
                    "folder": folder, "target": target}

        if not commit:
            return {"ok": True, "dry_run": True, "folder": folder,
                    "target": target, "would_move_to": trash}

        try:
            typ, resp = M.uid("MOVE", target["uid"], f'"{trash}"')
        except imaplib.IMAP4.error as e:
            return {"ok": False, "folder": folder, "target": target,
                    "error": f"the server refused UID MOVE ({e}); NOT falling back "
                             f"to \\Deleted+EXPUNGE, which cannot be undone"}
        if typ != "OK":
            return {"ok": False, "folder": folder, "target": target,
                    "error": f"IMAP UID MOVE to {trash!r} failed: {typ} {resp!r}"}
        return {"ok": True, "folder": folder, "target": target, "moved_to": trash}
    finally:
        try:
            M.logout()
        except Exception:
            pass
