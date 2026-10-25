"""Interactive review preparation and conservative exact Gmail mirror persistence."""
from __future__ import annotations

import os
import contextlib
import hashlib
from uuid import UUID

from . import gmail_drafts
from .draft_identity import authored_plain
from .draft_state import _recipient_set


def interactive():
    """Existing launcher markers keep every scheduled path on its current policy."""
    return not any(os.environ.get(key) for key in (
        "CS_OPERATOR_HEADLESS", "CS_HEADLESS_SEND", "CS_OPERATOR_HEALTH_CONTEXT",
    ))


def select(settings, root, rows, *, source=None, legacy=False):
    """Do not attribute an unrelated concurrent write to this request."""
    if len(rows) != 1:
        raise ValueError("engine did not identify exactly one prepared draft")
    row = rows[0]
    from .thread_key import thread_key
    refs = row.get("references")
    if refs is not None and (not isinstance(refs, list)
            or any(not isinstance(value, str) or not value for value in refs)):
        raise ValueError("engine draft References are malformed")
    refs = " ".join(refs) if isinstance(refs, list) else refs
    actual_root = row.get("thread_id") or (thread_key(None, refs, row.get("in_reply_to")) if legacy else None)
    value = row.get("id")
    if (not isinstance(value, str) or str(UUID(value)) != value
            or row.get("owner_id") != settings.email_address
            or row.get("status") != "draft" or actual_root != root
            or (source is not None and thread_key(None, refs, row.get("in_reply_to")) != root)
            or not row.get("body") or not _recipient_set(row.get("to_addresses"))
            or row.get("attachment_paths") or row.get("bcc_addresses")):
        raise ValueError("engine draft identity/content is incomplete or unsupported for a review copy")
    binding = row.get("reply_binding")
    if ((not legacy or binding is not None) and
            (not isinstance(binding, dict) or binding.get("root") != root
             or binding.get("target") != row.get("in_reply_to"))):
        raise ValueError("engine draft has no exact source binding")
    if source is not None and (row.get("in_reply_to") != source["target"]
            or _recipient_set(row.get("to_addresses")) != (source["sender"],)
            or _recipient_set(row.get("cc_addresses"))):
        raise ValueError("engine draft recipient or reply target does not match the verified source")
    return row


def _read(settings):
    observed = {}
    rows = gmail_drafts.list_drafts(settings, observation=observed)
    if observed.get("complete") is not True:
        raise RuntimeError("Gmail review inventory is incomplete; no additional copy was appended")
    return rows


def _matches(row, draft, root, owner):
    body, note = authored_plain(draft["body"])
    return (row.get("is_draft") is True
            and row.get("mime_plain_only") is True
            and row.get("identity_headers_valid") is True
            and row.get("from") == draft.get("owner_id")
            and "bcc" in row and not _recipient_set(row.get("bcc"))
            and row.get("engine_owner_uid") == owner
            and row.get("thread_key") == root
            and row.get("in_reply_to") == draft.get("in_reply_to")
            and (row.get("references") or "").split() == (draft.get("references") or [draft["in_reply_to"]])
            and _recipient_set(row.get("to")) == _recipient_set(draft.get("to_addresses"))
            and _recipient_set(row.get("cc")) == _recipient_set(draft.get("cc_addresses"))
            and row.get("subject") == draft.get("subject")
            and row.get("body_complete") is True and not row.get("body_note")
            and note is None and row.get("body") == body)


def _mirror(settings, root, draft):
    """Reuse exact copies, preserve edits, and verify readback after an append."""
    rows = _read(settings)
    copies = [row for row in rows if row.get("engine_draft_id") == draft["id"]]
    if copies:
        if len(copies) != 1 or not _matches(copies[0], draft, root, settings.engine_owner_uid):
            raise RuntimeError("existing Gmail copy changed or conflicts; preserved for human review")
        print(f"Existing Gmail review draft reused (UID {copies[0]['uid']}).")
        return
    # A legacy or human-created draft on this thread must not become a duplicate.
    if any(row.get("thread_key") == root for row in rows):
        raise RuntimeError("another Gmail draft already covers this thread; preserved for human review")
    gmail_drafts.append_draft(
        settings, to=", ".join(draft["to_addresses"]), subject=draft.get("subject") or "",
        body=draft["body"], in_reply_to=draft["in_reply_to"], references=draft.get("references"),
        cc=", ".join(draft.get("cc_addresses") or []) or None, body_md=True,
        engine_draft_id=draft["id"], engine_owner_uid=settings.engine_owner_uid,
    )
    copies = [row for row in _read(settings) if row.get("engine_draft_id") == draft["id"]]
    if len(copies) != 1 or not _matches(copies[0], draft, root, settings.engine_owner_uid):
        raise RuntimeError("engine draft saved; Gmail append needs verification before retrying")
    print(f"Gmail review draft verified (UID {copies[0]['uid']}).")


@contextlib.contextmanager
def mirror_lock(settings, root):
    """Serialize this host's mirrors for an owner/root; persistent inode, no retry."""
    import fcntl
    directory = settings.state_dir / "review-draft-locks"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = hashlib.sha256((settings.engine_owner_uid + "\0" + root).encode()).hexdigest()
    descriptor = os.open(directory / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another review copy operation is active for this thread") from exc
        yield
    finally:
        os.close(descriptor)


from .observability_producers import observe as _diagnostic_observe


@_diagnostic_observe("verification", success="verified", effect="verified")
def mirror(settings, root, draft):
    with mirror_lock(settings, root):
        _mirror(settings, root, draft)
