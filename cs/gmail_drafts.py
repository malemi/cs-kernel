"""Put outreach drafts where the operator actually works: Gmail Drafts.

Review surface: the engine composes and persists the authoritative draft
(memory + voice + threading), then cs APPENDs a second, editable copy into the
operator's Gmail Drafts. That mirror is for review only. Sending it from Gmail
bypasses the engine draft's claim/status/message-id lifecycle and leaves the
engine row stale, so an engine-owned contextual draft is sent through the
kernel's exact-id engine send path. `cs review` reconciles the two stores for
display, but reconciliation does not mutate either one.

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
from email.header import decode_header, make_header
from email.utils import formatdate

from .config import Settings
from .thread_key import thread_key
from .draft_identity import (BODY_BYTES, ID_HEADER, OWNER_HEADER, authored_message,
                             fingerprint, validate_identity)


def _imap(
    settings: Settings, credential: tuple[str, str] | None = None
) -> imaplib.IMAP4_SSL:
    """A logged-in IMAP session. Without `credential`, the operator mailbox's
    own pair from Settings — which is what every caller here wants and why the
    argument is optional.

    `credential` is `(address, password)` for ANOTHER mailbox of the same
    company, retrieved from its own engine profile (`cs/mailboxes.py`); it is
    never read from the environment and never printed. Host and port stay the
    Settings ones: they are the company's mail provider, one per clone, not a
    per-mailbox fact."""
    address, password = (
        credential
        if credential is not None
        else (settings.email_address, settings.email_password)
    )
    M = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    # tolerate the spaced app-password paste
    M.login(address, (password or "").replace(" ", "").strip())
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


from .observability_producers import observe as _diagnostic_observe


@_diagnostic_observe("provider", success="accepted", effect="accepted")
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
    engine_draft_id: str | None = None,
    engine_owner_uid: str | None = None,
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
    engine_draft_id = validate_identity(engine_draft_id)
    engine_owner_uid = validate_identity(engine_owner_uid)
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
    if engine_draft_id is not None:
        msg[ID_HEADER] = engine_draft_id
    if engine_owner_uid is not None:
        msg[OWNER_HEADER] = engine_owner_uid
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


def list_drafts(settings: Settings, *, observation: dict | None = None) -> list[dict]:
    """Headers and bounded complete authored bodies of the drafts waiting in the operator's Gmail Drafts —
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

    coverage = {"version": 1, "complete": False, "search_complete": False,
                "expected_uids": [], "observed_uids": [], "uidvalidity": None}
    if observation is not None:
        observation.clear()
        observation.update(coverage)
    M = _imap(settings)
    try:
        folder = find_drafts_folder(M)
        typ, _ = M.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            raise RuntimeError("cannot select Gmail Drafts")
        validity = _uidvalidity(M)
        coverage["uidvalidity"] = validity
        typ, data = M.uid("SEARCH", None, "ALL")
        if typ != "OK" or not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], bytes):
            return []
        uids = data[0].split()
        coverage["search_complete"] = all(u.isdigit() for u in uids)
        coverage["expected_uids"] = [u.decode() for u in uids]
        out = []
        fetches_complete = True
        for uid in uids:
            typ, md = M.uid(
                "FETCH",
                uid,
                "(BODY.PEEK[HEADER.FIELDS (TO CC SUBJECT DATE MESSAGE-ID "
                "REFERENCES IN-REPLY-TO X-CS-ENGINE-DRAFT-ID X-CS-ENGINE-OWNER-UID)])",
            )
            if typ != "OK" or not md or not md[0]:
                continue
            hdr = _email.message_from_bytes(md[0][1])
            body_observation = {}
            payload = _body_evidence(M, uid, observation=body_observation)
            fetches_complete = fetches_complete and body_observation.get("fetch_complete") is True
            observed_headers = payload.pop("_headers", None)
            flags = payload.pop("_flags", "") or ""
            payload["is_draft"] = bool(re.search(r"\\Draft(?=[\s)])", flags, re.I))
            coverage["observed_uids"].append(uid.decode())
            out.append({**payload, "uidvalidity": validity, "uid": uid.decode(),
                        **(observed_headers or _header_evidence(hdr))})
        coverage["complete"] = bool(validity and coverage["search_complete"] and fetches_complete
                                    and coverage["expected_uids"] == coverage["observed_uids"]
                                    and len(uids) == len(set(uids)))
        return out
    finally:
        if observation is not None:
            observation.update(coverage)
        try:
            M.logout()
        except Exception:
            pass


def _identity_header(hdr, name: str) -> str | None:
    values = hdr.get_all(name, [])
    if not values:
        return None
    if len(values) != 1:
        return "invalid:duplicate-header"
    try:
        return validate_identity(str(values[0]))
    except ValueError:
        return "invalid:malformed-header"


def decoded_subject(hdr):
    values = hdr.get_all("Subject", [])
    if len(values) != 1:
        return None
    try:
        value = str(make_header(decode_header(str(values[0]))))
        return value if not any(ord(c) < 32 and c not in "\r\n\t" for c in value) else None
    except (LookupError, UnicodeError, ValueError):
        return None


def _header_evidence(hdr) -> dict:
    from .draft_identity import canonical_message_id
    from email import policy
    from email.parser import Parser
    checked = Parser(policy=policy.default).parsestr(hdr.as_string(), headersonly=True)
    identity_headers_valid = all(
        len(checked.get_all(name, [])) <= 1
        and all(not getattr(value, "defects", ()) for value in checked.get_all(name, []))
        for name in ("From", "To", "Cc", "Bcc", "Subject", "Message-ID", "References", "In-Reply-To"))
    target = canonical_message_id(hdr.get("In-Reply-To"))
    if hdr.get_all("In-Reply-To", []) and target is None:
        identity_headers_valid = False
    def addresses(name):
        return ", ".join(str(v) for v in hdr.get_all(name, [])) or None
    return {
        "identity_headers_valid": identity_headers_valid,
        "engine_draft_id": _identity_header(hdr, ID_HEADER),
        "engine_owner_uid": _identity_header(hdr, OWNER_HEADER),
        "to": addresses("To"), "cc": addresses("Cc"),
        "subject": decoded_subject(hdr), "date": hdr.get("Date"),
        "bcc": addresses("Bcc"),
        "from": str(hdr.get("From") or ""),
        "message_id": hdr.get("Message-ID"), "references": hdr.get("References"),
        "in_reply_to": target,
        "thread_key": thread_key(hdr.get("Message-ID"), hdr.get("References"), hdr.get("In-Reply-To")),
    }


def _merge_body_evidence(target: dict, evidence: dict) -> bool:
    """Bind context and flags to the MIME observation; refuse an observed race."""
    headers = evidence.pop("_headers", None)
    flags = evidence.pop("_flags", None)
    changed = bool(headers and any(target.get(k) != headers.get(k) for k in
                                  ("engine_draft_id", "engine_owner_uid", "to", "cc", "subject", "date", "message_id")))
    target.update(evidence)
    if headers:
        target.update(headers)
    if flags is not None:
        target["flags"] = flags
    return not changed


def _uidvalidity(M) -> str | None:
    try:
        # imaplib.response() pops the SELECT response. Reading it twice on
        # the same connection would invent a changed folder before MOVE.
        responses = getattr(M, "untagged_responses", None)
        if isinstance(responses, dict):
            typ, data = "UIDVALIDITY", responses.get("UIDVALIDITY")
        else:
            typ, data = M.response("UIDVALIDITY")
        if typ and data and data[0]:
            value = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
            return value if value.isdigit() else None
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _mime_evidence(raw):
    from email import policy
    from email.parser import BytesParser
    message = BytesParser(policy=policy.default).parsebytes(raw)
    parts = list(message.walk())
    structural = [(part.get_content_type(), part.get_content_disposition(), part.get_filename()) for part in parts]
    valid = all(not part.defects and all(len(part.get_all(name, [])) <= 1
                and all(not getattr(value, "defects", ()) for value in part.get_all(name, []))
                for name in ("Content-Type", "Content-Disposition", "Content-Transfer-Encoding", "MIME-Version"))
                for part in parts)
    return {"mime_structure": structural,
            "mime_plain_only": bool(valid and len(parts) == 1 and structural == [("text/plain", None, None)])}


def _body_evidence(M, uid: bytes, *, observation: dict | None = None) -> dict:
    if observation is not None:
        observation["fetch_complete"] = False
    typ, data = M.uid("FETCH", uid, f"(FLAGS RFC822.SIZE BODY.PEEK[]<0.{BODY_BYTES}>)")
    parts = [p for p in (data or []) if isinstance(p, tuple) and isinstance(p[1], bytes)] if typ == "OK" else []
    if len(parts) != 1:
        return {"body": "", "body_complete": False, "body_note": "MIME body unavailable", "fingerprint": None}
    if observation is not None:
        observation["fetch_complete"] = True
    meta, raw = parts[0]
    match = re.search(rb"RFC822.SIZE\s+(\d+)", meta or b"", re.I)
    complete = bool(match and int(match[1]) == len(raw) and len(raw) < BODY_BYTES)
    if not complete:
        return {"body": "", "body_complete": False, "body_note": "MIME size unknown or body incomplete", "fingerprint": None}
    import email as _email
    body, note = authored_message(raw)
    return {**_mime_evidence(raw), "body": body, "body_complete": True, "body_note": note, "fingerprint": fingerprint(raw),
            "_headers": _header_evidence(_email.message_from_bytes(raw)),
            "_flags": (meta or b"").decode(errors="replace")}


_UID_RE = re.compile(r"^[0-9]+$")


def _draft_row(M: imaplib.IMAP4_SSL, uid: bytes) -> dict:
    """What one candidate IS, in the terms a human recognises it by: flags plus
    recipient / subject / date / Message-ID. Headers only, never the body —
    identification, not a second review surface. BODY.PEEK, so a refusal never
    marks anything \\Seen."""
    import email as _email

    typ, md = M.uid(
        "FETCH", uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (TO CC SUBJECT DATE MESSAGE-ID X-CS-ENGINE-DRAFT-ID X-CS-ENGINE-OWNER-UID)])"
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
        "engine_draft_id": _identity_header(hdr, ID_HEADER) if hdr else None,
        "engine_owner_uid": _identity_header(hdr, OWNER_HEADER) if hdr else None,
        "flags": flags,
        "to": (", ".join(str(v) for v in hdr.get_all("To", [])) or None if hdr else None),
        "cc": (", ".join(str(v) for v in hdr.get_all("Cc", [])) or None if hdr else None),
        "subject": (decoded_subject(hdr) if hdr else None),
        "date": (hdr.get("Date") if hdr else None),
        "message_id": (hdr.get("Message-ID") if hdr else None),
    }


def delete_draft(
    settings: Settings,
    uid: str | None = None,
    message_id: str | None = None,
    *,
    commit: bool = False,
    expected_engine_draft_id: str | None = None,
    expected_owner_uid: str | None = None,
    expected_uidvalidity: str | None = None,
    expected_fingerprint: str | None = None,
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
        strict = any(v is not None for v in (expected_engine_draft_id, expected_owner_uid, expected_uidvalidity, expected_fingerprint))
        target["uidvalidity"] = _uidvalidity(M)
        if strict:
            if not _merge_body_evidence(target, _body_evidence(M, matched[0])):
                return {"ok": False, "refused": "draft headers changed during MIME read", "target": target}
            checks = {"engine_draft_id": expected_engine_draft_id, "engine_owner_uid": expected_owner_uid,
                      "uidvalidity": expected_uidvalidity, "fingerprint": expected_fingerprint}
            for key, expected in checks.items():
                if expected is not None and (target.get(key) is None or str(target[key]) != str(expected)):
                    return {"ok": False, "refused": f"draft {key} changed or unavailable", "target": target}
            if target.get("fingerprint") is None or target["uidvalidity"] is None:
                return {"ok": False, "refused": "complete MIME fingerprint and UIDVALIDITY required", "target": target}
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

        if strict:
            current = _draft_row(M, matched[0])
            if not _merge_body_evidence(current, _body_evidence(M, matched[0])):
                return {"ok": False, "refused": "draft headers changed during MIME read", "target": current}
            current["uidvalidity"] = _uidvalidity(M)
            if any(current.get(k) != target.get(k) for k in ("engine_draft_id", "engine_owner_uid", "uidvalidity", "fingerprint")) or "\\Draft" not in current["flags"]:
                return {"ok": False, "refused": "draft changed before MOVE", "target": current}
        try:
            typ, resp = M.uid("MOVE", target["uid"], f'"{trash}"')
        except imaplib.IMAP4.error:
            # Includes IMAP4.abort: MOVE may have applied before its response
            # was lost. Only a received tagged refusal establishes no effect.
            return {"ok": False, "partial": True, "outcome_uncertain": True,
                    "folder": folder, "target": target,
                    "error": "IMAP UID MOVE acknowledgement unavailable",
                    "check": "Check the named draft and Trash before retrying; no expunge is attempted."}
        if typ != "OK":
            return {"ok": False, "folder": folder, "target": target,
                    "error": f"IMAP UID MOVE to {trash!r} failed: {typ} {resp!r}"}
        return {"ok": True, "folder": folder, "target": target, "moved_to": trash}
    finally:
        try:
            M.logout()
        except Exception:
            pass
