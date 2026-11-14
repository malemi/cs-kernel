"""Retire one explicitly named, unchanged Gmail/engine draft pair.

Each store verifies its own current snapshot. A provider move and an engine
discard are separate effects; partial or uncertain completion remains visible.
"""
from __future__ import annotations

import os
import re

from . import draft_state, gmail_drafts, rpc
from .draft_identity import validate_identity


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _exact_pair(mirror, draft, owner_uid):
    from .thread_key import normalize_key

    gmail = draft_state._gmail_row(mirror)
    engine = draft_state._engine_row(draft)
    gmail_context = normalize_key(gmail["thread_key"]) or "subject:" + gmail["subject"].strip().lower()
    engine_context = normalize_key(engine["thread_key"]) or "subject:" + engine["subject"].strip().lower()
    return (
        mirror.get("engine_draft_id") == draft.get("id")
        and mirror.get("engine_owner_uid") == owner_uid
        and gmail_context == engine_context
        and draft_state._recipient_set(mirror.get("to")) == draft_state._recipient_set(draft.get("to_addresses"))
        and draft_state._recipient_set(mirror.get("cc")) == draft_state._recipient_set(draft.get("cc_addresses"))
    )


def _bound(value, settings, draft_id):
    return (
        isinstance(value, dict)
        and value.get("ok") is True
        and value.get("draft_id") == draft_id
        and value.get("engine_owner_uid") == settings.engine_owner_uid
        and str(value.get("owner_id") or "").lower() == settings.email_address.lower()
    )


from .observability_producers import observe as _diagnostic_observe


@_diagnostic_observe("cleanup", success="result", effect="unknown")
def retire(settings, draft_id, gmail_uid, uidvalidity, *, commit=False,
           gmail_fingerprint=None, engine_snapshot=None, timeout=120):
    """Preview both effects, or consume the operator's exact preview snapshots."""
    base = {"draft_id": draft_id, "gmail_uid": gmail_uid, "uidvalidity": uidvalidity}

    def refused(reason, **details):
        return {**base, "ok": False, "reason": reason, **details}

    if os.environ.get("CS_OPERATOR_HEADLESS"):
        return refused("draft retirement requires an interactive operator")
    try:
        validate_identity(draft_id)
        validate_identity(settings.engine_owner_uid)
    except (ValueError, AttributeError):
        return refused("full draft identity and selected owner are required")
    if not draft_id or not getattr(settings, "engine_owner_uid", None) or not getattr(settings, "email_address", None):
        return refused("full draft identity and selected owner are required")
    if not all(isinstance(x, str) and re.fullmatch(r"[1-9][0-9]{0,9}", x)
               and int(x) <= 4294967295
               for x in (gmail_uid, uidvalidity)):
        return refused("name a positive Gmail UID and its UIDVALIDITY")
    if commit and not (_digest(gmail_fingerprint) and _digest(engine_snapshot)):
        return refused("commit requires the Gmail fingerprint and engine snapshot from preview")

    try:
        inspected = rpc.call_sync(settings, "drafts.inspect", {"draft_id": draft_id}, timeout=timeout)
        if not _bound(inspected, settings, draft_id):
            return refused("engine did not acknowledge this exact owner and draft")
        draft = inspected.get("draft")
        snapshot = inspected.get("expected_snapshot")
        if not isinstance(draft, dict) or draft.get("id") != draft_id or not _digest(snapshot):
            return refused("engine draft snapshot is unavailable")
        if commit and snapshot != engine_snapshot:
            return refused("engine draft changed since preview")
        mirrors = gmail_drafts.list_drafts(settings)
        selected = [r for r in mirrors if r.get("uid") == gmail_uid]
        copies = [r for r in mirrors if r.get("engine_draft_id") == draft_id]
        if len(selected) != 1 or len(copies) != 1 or selected[0] is not copies[0]:
            return refused("the exact Gmail copy is missing or ambiguous")
        mirror = selected[0]
        if not _exact_pair(mirror, draft, settings.engine_owner_uid):
            return refused("Gmail and engine identity or recipient/thread context conflicts")
        fingerprint = mirror.get("fingerprint")
        if str(mirror.get("uidvalidity")) != uidvalidity or not _digest(fingerprint):
            return refused("Gmail UIDVALIDITY or complete message fingerprint is unavailable")
        if commit and fingerprint != gmail_fingerprint:
            return refused("Gmail draft changed since preview")
        expected = {
            "expected_engine_draft_id": draft_id,
            "expected_owner_uid": settings.engine_owner_uid,
            "expected_uidvalidity": uidvalidity,
            "expected_fingerprint": fingerprint,
        }
        prepared = rpc.call_sync(settings, "drafts.discard_exact", {
            "draft_id": draft_id, "expected_snapshot": snapshot, "dry_run": True,
        }, timeout=timeout)
        if not (_bound(prepared, settings, draft_id)
                and prepared.get("would_discard") is True
                and prepared.get("discarded") is False
                and prepared.get("expected_snapshot") == snapshot):
            return refused("engine refuses retirement of this unchanged draft")
        preview = gmail_drafts.delete_draft(settings, uid=gmail_uid, commit=False, **expected)
        target = preview.get("target") or {}
        if (preview.get("ok") is not True or preview.get("dry_run") is not True
                or target.get("uid") != gmail_uid or not preview.get("would_move_to")
                or any(str(target.get(k)) != str(v) for k, v in {
                    "engine_draft_id": draft_id, "engine_owner_uid": settings.engine_owner_uid,
                    "uidvalidity": uidvalidity, "fingerprint": fingerprint,
                }.items())):
            return refused("Gmail refuses retirement of this unchanged copy")
    except Exception as exc:
        return refused(f"retirement preview unavailable ({type(exc).__name__})")

    if not commit:
        return {**base, "ok": True, "dry_run": True, "gmail_fingerprint": fingerprint,
                "engine_snapshot": snapshot, "to": mirror.get("to"),
                "subject": mirror.get("subject"), "would_move_to": preview["would_move_to"],
                "would_discard": draft_id}

    # Gmail first: it is recoverable in Trash. A refused/stale engine CAS leaves
    # the authoritative row intact and reports the precise remaining handle.
    try:
        moved = gmail_drafts.delete_draft(settings, uid=gmail_uid, commit=True, **expected)
    except Exception as exc:
        return refused(f"Gmail move outcome uncertain ({type(exc).__name__})",
                       partial=True, gmail_moved=None, engine_discarded=False,
                       check="Check the named Gmail copy and Trash before retrying; the engine copy remains.")
    if not isinstance(moved, dict):
        return refused("Gmail move outcome was not acknowledged; engine discard was not attempted",
                       partial=True, gmail_moved=None, engine_discarded=False)
    if moved.get("outcome_uncertain") is True:
        return refused("Gmail MOVE acknowledgement unavailable; engine discard was not attempted",
                       partial=True, gmail_moved=None, engine_discarded=False,
                       check="Check the named Gmail copy and Trash before retrying; the engine was not modified.")
    moved_target = moved.get("target")
    if (moved.get("ok") is not True or moved.get("moved_to") != preview["would_move_to"]
            or not isinstance(moved_target, dict) or moved_target.get("uid") != gmail_uid
            or any(str(moved_target.get(k)) != str(v) for k, v in {
                "engine_draft_id": draft_id, "engine_owner_uid": settings.engine_owner_uid,
                "uidvalidity": uidvalidity, "fingerprint": fingerprint,
            }.items())):
        return refused("Gmail move was refused or not acknowledged; engine copy retained",
                       partial=moved.get("ok") is True,
                       gmail_moved=None if moved.get("ok") else False, engine_discarded=False)
    try:
        discarded = rpc.call_sync(settings, "drafts.discard_exact", {
            "draft_id": draft_id, "expected_snapshot": snapshot, "dry_run": False,
        }, timeout=timeout)
    except Exception as exc:
        return refused(f"engine discard outcome uncertain ({type(exc).__name__})",
                       partial=True, gmail_moved=True, engine_discarded=None,
                       check="Gmail copy is in Trash; inspect the exact engine draft before retrying.")
    if not isinstance(discarded, dict):
        return refused("Gmail copy moved to Trash; engine discard outcome was not acknowledged",
                       partial=True, gmail_moved=True, engine_discarded=None,
                       engine_id_to_check=draft_id,
                       check="Inspect the exact engine row before retrying.")
    if not (_bound(discarded, settings, draft_id)
            and discarded.get("discarded") is True
            and discarded.get("consumed_snapshot") == snapshot):
        return refused("Gmail copy moved to Trash; engine discard was refused or not acknowledged",
                       partial=True, gmail_moved=True,
                       engine_discarded=False if discarded.get("ok") is False else None,
                       surviving_engine_id=draft_id,
                       check="Inspect the exact engine row. Restore the Gmail copy from Trash if needed; do not retry both effects blindly.")
    return {**base, "ok": True, "gmail_moved": True, "moved_to": moved["moved_to"],
            "engine_discarded": True}


@_diagnostic_observe("cleanup", success="result", effect="unknown")
def retire_sent_mirror(settings, draft_id, gmail_uid, uidvalidity, *, thread_id,
                       commit=False, gmail_fingerprint=None, engine_snapshot=None,
                       gmail_folder=None, operation_id=None, timeout=120):
    """Recover only an exact residual sent copy through the engine journal."""
    from uuid import uuid4
    from .draft_identity import canonical_message_id

    operation_id = operation_id or (None if commit else str(uuid4()))
    base = {"version": 1, "draft_id": draft_id, "operation_id": operation_id,
            "engine_discarded": False, "ok": False}
    from .review_draft import interactive
    if not interactive():
        return {**base, "cause": "interactive_retirement_required"}
    root = canonical_message_id(thread_id)
    if not root or not operation_id:
        return {**base, "cause": "exact_root_and_operation_required"}
    if commit and not (gmail_folder and _digest(gmail_fingerprint) and _digest(engine_snapshot)):
        return {**base, "cause": "commit_requires_preview"}
    attempted = False
    try:
        capabilities = rpc.call_sync(settings, "system.capabilities", {}, timeout=timeout)
        if not isinstance(capabilities, dict) or type(capabilities.get("sent_mirror_recovery")) is not int or capabilities["sent_mirror_recovery"] != 1:
            return {**base, "cause": "sent_mirror_recovery_unsupported"}
        inspected = rpc.call_sync(settings, "drafts.inspect", {"draft_id": draft_id}, timeout=timeout)
        if not _bound(inspected, settings, draft_id) or not _digest(inspected.get("expected_snapshot")):
            return {**base, "cause": "exact_draft_unavailable"}
        expected = engine_snapshot if commit else inspected["expected_snapshot"]
        target = {"uid": gmail_uid, "uidvalidity": uidvalidity}
        if commit:
            target.update(folder=gmail_folder, raw_fingerprint=gmail_fingerprint)
        attempted = commit
        answer = rpc.call_sync(settings, "drafts.retire_sent_mirror", {
            "draft_id": draft_id, "expected_snapshot": expected, "thread_id": root,
            "operation_id": operation_id, "target": target, "commit": commit,
        }, timeout=timeout)
        if not isinstance(answer, dict) or any(answer.get(key) != value for key, value in {
            "draft_id": draft_id, "operation_id": operation_id, "owner_uid": settings.engine_owner_uid,
            "owner_id": settings.email_address, "root": root, "expected_snapshot": expected,
        }.items()):
            raise ValueError("retirement response binding mismatch")
        return answer
    except Exception:
        return {**base, "cause": "sent_mirror_recovery_unavailable",
                "effect_certainty": "unknown" if attempted else "not-dispatched",
                "next_action": "inspect-operation" if attempted else "retire-sent-mirror"}
