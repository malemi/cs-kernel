"""Put outreach drafts where the operator actually works: Gmail Drafts.

Phase-1 review surface: the engine composes (memory + voice + threading),
cs APPENDs the result into the operator's Gmail Drafts; the operator reviews,
edits and SENDS from Gmail. The sent mail lands in Gmail Sent and the
engine's normal sync picks it up — archive, threading and dedup stay
correct with zero extra plumbing. The engine-side Draft store is NOT used
in this flow (single copy, no divergence).

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
import sys
import time
from email.message import EmailMessage
from email.utils import formatdate

from .config import Settings


def _imap(settings: Settings) -> imaplib.IMAP4_SSL:
    M = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    # tolerate the spaced app-password paste
    M.login(settings.email_address, settings.email_password.replace(" ", "").strip())
    return M


def find_drafts_folder(M: imaplib.IMAP4_SSL) -> str:
    """Folder carrying the \\Drafts special-use flag (locale-proof)."""
    typ, data = M.list()
    if typ == "OK":
        for raw in data or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            if "\\drafts" in line.lower() and '"' in line:
                return line.rsplit('"', 2)[-2]
    return "[Gmail]/Drafts"


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
    the review queue the operator sends from. Read-only."""
    import email as _email

    M = _imap(settings)
    try:
        folder = find_drafts_folder(M)
        M.select(f'"{folder}"', readonly=True)
        typ, data = M.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        out = []
        for num in data[0].split():
            typ, md = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (TO SUBJECT DATE)])")
            if typ != "OK" or not md or not md[0]:
                continue
            hdr = _email.message_from_bytes(md[0][1])
            out.append({"to": hdr.get("To"), "subject": hdr.get("Subject"), "date": hdr.get("Date")})
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass
