"""IMAP connection for archive observation and fixed-template delivery."""
import imaplib

from .config import Settings


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
