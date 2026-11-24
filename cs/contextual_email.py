"""Known campaign replies use an exact engine draft and its guarded lifecycle.

Fixed-template bulk and source-free first contact remain on their existing paths.
No prose or recipient-history inference establishes reply intent here.
"""

from hashlib import sha256

from .interactive_draft import scheduled

from . import rpc
from .thread_key import thread_key, normalize_key


class CampaignDraftRetirementPending(RuntimeError):
    """A bound send is in Sent, but its original draft still needs removal."""

    def __init__(self, message_id):
        super().__init__("campaign message is in Sent; its draft still needs removal")
        self.message_id = message_id


def _campaign_send_key(draft_id):
    key = "campaign-send:" + draft_id
    # Preserve existing valid receipt keys; a full IMAP handle can exceed the
    # central receipt's bound once the historical prefix is prepended.
    return key if len(key) <= 256 else "campaign-send:sha256:" + sha256(draft_id.encode("utf-8")).hexdigest()


def campaign_draft(settings, contact):
    dossier = contact.get("dossier") or {}
    draft_id = dossier.get("mailbox_draft_id")
    root = dossier.get("thread_id")
    target = dossier.get("target_message_id")
    if not draft_id:
        raise RuntimeError("contact has no native mailbox draft handle")
    capabilities = rpc.call_sync(settings, "system.capabilities", {})
    if not isinstance(capabilities, dict) or capabilities.get("mailbox_drafts") != 1:
        raise RuntimeError("engine mailbox drafts version 1 required")
    result = rpc.call_sync(settings, "drafts.get", {"draft_id": draft_id})
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("named campaign mailbox draft unavailable")
    draft = result["draft"]
    if (draft.get("id") != draft_id or draft.get("owner_id") != settings.email_address
            or draft.get("status") != "draft"):
        raise RuntimeError("campaign mailbox draft identity differs")
    refs = draft.get("references") or []
    actual = draft.get("thread_id") or thread_key(None, " ".join(refs) if isinstance(refs, list) else refs,
                                                 draft.get("in_reply_to"))
    if root and normalize_key(root) != actual:
        raise RuntimeError("campaign thread disagrees with exact engine draft")
    if target and draft.get("in_reply_to") != target:
        raise RuntimeError("campaign original message disagrees with exact engine draft")
    if contact["email"].lower() not in {str(value).lower() for value in draft.get("to_addresses") or []}:
        raise RuntimeError("campaign recipient disagrees with exact engine draft")
    return draft


def campaign_delivery(settings, draft_id, *, status_only=False):
    if scheduled():
        raise RuntimeError("scheduled operators leave existing mailbox drafts for review")
    key = _campaign_send_key(draft_id)
    method = "drafts.send_status" if status_only else "drafts.send"
    result = rpc.call_sync(settings, method, {"draft_id": draft_id, "request_key": key})
    if not isinstance(result, dict):
        raise RuntimeError("campaign mailbox receipt unavailable")
    bound = result.get("draft_id") == draft_id and result.get("request_key") == key
    if (status_only and bound and result.get("ok") is False and result.get("cause") == "named_send_operation_not_found"
            and result.get("effect_certainty") == "not-dispatched"):
        return None
    if (not bound or result.get("state") != "sent"
            or result.get("effect_certainty") != "verified" or not result.get("message_id")):
        raise RuntimeError("campaign mailbox delivery is unconfirmed")
    if (status_only and result.get("ok") is False and result.get("cause") == "draft_retirement_unconfirmed"
            and isinstance(result.get("draft_cleanup"), dict)
            and result["draft_cleanup"].get("state") == "pending"):
        raise CampaignDraftRetirementPending(result["message_id"])
    if result.get("ok") is not True:
        raise RuntimeError("campaign mailbox delivery is unconfirmed")
    return result["message_id"]
