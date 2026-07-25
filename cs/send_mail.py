"""SMTP send as the company mailbox for fixed-template operational bulk mail.

Deliberately a SEND path (not the engine), for fixed-template operational
mail where there is no AI text to preserve: exact wording guaranteed.
Replies still arrive at the mailbox and the daemon ingests them as tasks,
so the agentic reply loop is unaffected. This path stays DENIED in the
headless permission set — it is the operator's deliberate bulk tool.

Sends multipart/alternative (clean anchor text in HTML, full URL only in
href), generates a Message-ID, and IMAP-APPENDs the sent MIME to the
mailbox's Sent so the outbound shows in mrcall-desktop and replies thread
to it. Never used for AI-composed outreach — that goes through the
engine's compose path.
"""
from __future__ import annotations

import html as _html
import imaplib
import re
import smtplib
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from .config import Settings
from .gmail_drafts import _imap  # reuse IMAP login

_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")  # markdown links — structured input


def find_special_folder(M: imaplib.IMAP4_SSL, attr: str, fallback: str) -> str:
    """Folder carrying the \\<attr> special-use flag (locale-proof)."""
    typ, data = M.list()
    if typ == "OK":
        token = ("\\" + attr).lower()
        for raw in data or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            if token in line.lower() and '"' in line:
                return line.rsplit('"', 2)[-2]
    return fallback


def md_to_plain(body: str) -> str:
    """`[text](url)` -> `text: url` for the text/plain part."""
    return _LINK.sub(r"\1: \2", body)


def md_to_html(body: str) -> str:
    """`[text](url)` -> <a href="url">text</a>; paragraphs on blank lines."""
    out = []
    for para in body.split("\n\n"):
        esc = _html.escape(para)
        esc = _LINK.sub(r'<a href="\2">\1</a>', esc)
        out.append("<p>" + esc.replace("\n", "<br>") + "</p>")
    return (
        '<html><body style="font-family:Arial,Helvetica,sans-serif;'
        'font-size:14px;color:#222;line-height:1.45">' + "\n".join(out) + "</body></html>"
    )


def build_mime(
    settings: Settings,
    to: str,
    subject: str,
    *,
    plain: str | None = None,
    html: str | None = None,
    body_md: str | None = None,
    cc: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> EmailMessage:
    """Build a multipart/alternative message. Pass either an explicit
    (plain, html) pair (preferred for hand-built rich HTML) or `body_md`
    (markdown convenience).

    Threading: pass `in_reply_to` (the angle-bracketed `Message-ID` of the
    message being answered) to make the mail land INSIDE that thread instead
    of starting a new one. `references` is the parent's own `References`
    header plus its `Message-ID`, space-separated; when empty it falls back to
    `in_reply_to`. Both values are used VERBATIM — they are already
    angle-bracketed `Message-ID`s, never re-quoted or re-encoded."""
    if body_md is not None:
        plain = md_to_plain(body_md)
        html = md_to_html(body_md)
    if plain is None or html is None:
        raise ValueError("provide (plain, html) or body_md")
    msg = EmailMessage()
    # From display name comes from the manifest ([company].from_name →
    # settings.email_from_name); bare address when unset.
    sender = settings.email_address
    msg["From"] = f"{settings.email_from_name} <{sender}>" if settings.email_from_name else sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] if "@" in sender else None)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to.strip()
        refs = (references or "").strip() or in_reply_to.strip()
        msg["References"] = refs
    elif references:
        msg["References"] = references.strip()
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    return msg


def send(
    settings: Settings,
    to: str,
    subject: str,
    body_md: str | None = None,
    *,
    plain: str | None = None,
    html: str | None = None,
    cc: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> str:
    """SMTP-send as the operator mailbox and append a copy to Sent. Returns Message-ID.

    Raises on SMTP failure (caller must NOT mark the contact sent). A
    failed Sent-mirror APPEND is logged but does not raise — the mail
    already went out; raising would invite a double-send on retry.

    `in_reply_to` / `references` thread the mail into an existing
    conversation — see `build_mime`. A reply to a customer must always carry
    them, or the mail opens a second thread in the customer's mailbox.
    """
    msg = build_mime(settings, to, subject, plain=plain, html=html, body_md=body_md, cc=cc,
                     in_reply_to=in_reply_to, references=references)
    pw = settings.email_password.replace(" ", "").strip()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
        s.starttls()
        s.login(settings.email_address, pw)
        s.send_message(msg)
    M = _imap(settings)
    try:
        folder = find_special_folder(M, "Sent", "[Gmail]/Sent Mail")
        typ, resp = M.append(
            f'"{folder}"', r"(\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes()
        )
        if typ != "OK":
            import sys

            sys.stderr.write(f"[send_mail] WARNING: Sent APPEND failed for {msg['Message-ID']}: {typ} {resp!r}\n")
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return msg["Message-ID"]
