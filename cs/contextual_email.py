"""Known campaign replies use an exact engine draft and its guarded lifecycle.

Fixed-template bulk and source-free first contact remain on their existing paths.
No prose or recipient-history inference establishes reply intent here.
"""

import asyncio

from . import rpc
from .thread_key import thread_key, normalize_key


def campaign_draft(settings, contact):
    dossier = contact.get("dossier") or {}
    draft_id = dossier.get("engine_draft_id")
    root = dossier.get("thread_id")
    target = dossier.get("target_message_id")
    if not any((draft_id, root, target, dossier.get("source_email_id"))):
        return None
    capabilities = rpc.call_sync(settings, "system.capabilities", {})
    if not isinstance(capabilities, dict) or capabilities.get("contextual_email_policy") != 1:
        raise RuntimeError("engine contextual email policy version 1 required")
    if not isinstance(draft_id, str) or not draft_id.strip():
        raise RuntimeError("contextual campaign requires an exact engine_draft_id; compose with draft-reply first")
    drafts = rpc.call_sync(settings, "drafts.list", {"status": "draft"}) or []
    matches = [draft for draft in drafts if draft.get("id") == draft_id]
    if len(matches) != 1:
        raise RuntimeError("exact contextual campaign engine draft is unavailable")
    draft = matches[0]
    refs = draft.get("references") or []
    actual = draft.get("thread_id") or thread_key(None, " ".join(refs) if isinstance(refs, list) else refs,
                                                 draft.get("in_reply_to"))
    if root and normalize_key(root) != actual:
        raise RuntimeError("campaign thread disagrees with exact engine draft")
    if target and draft.get("in_reply_to") != target:
        raise RuntimeError("campaign original message disagrees with exact engine draft")
    if contact["email"].lower() not in {str(value).lower() for value in draft.get("to_addresses") or []}:
        raise RuntimeError("campaign recipient disagrees with exact engine draft")
    context = {"draft_id": draft_id}
    for field, value in (("thread_key", root), ("target_message_id", target),
                         ("source_email_id", dossier.get("source_email_id"))):
        if value:
            context[field] = value
    return draft, context


def send_campaign_draft(settings, draft, context):
    draft_id = draft["id"]
    approved = False
    def exact(tool, inputs):
        nonlocal approved
        if tool != "send_draft" or inputs.get("draft_id") != draft_id or approved:
            return False
        approved = True
        return True
    answer = asyncio.run(rpc.chat(
        settings, f"Send only the existing reviewed draft {draft_id}. Call send_draft exactly once; do not compose or edit.",
        allow_tools={"send_draft"}, approval_predicate=exact, email_context=context,
    ))
    result = answer.get("result") or {}
    if (result.get("metadata") or {}).get("error"):
        raise RuntimeError("engine refused contextual campaign send")
    receipts = [entry for entry in answer.get("approvals") or [] if entry.get("mode") == "once"]
    if len(receipts) != 1 or receipts[0].get("tool") != "send_draft" or (receipts[0].get("input") or {}).get("draft_id") != draft_id:
        raise RuntimeError("engine did not approve the exact contextual campaign draft")
    sent = rpc.call_sync(settings, "drafts.list", {"status": "sent"}) or []
    matches = [row for row in sent if row.get("id") == draft_id and row.get("sent_message_id")]
    if len(matches) != 1:
        raise RuntimeError("exact contextual campaign delivery is unconfirmed; inspect engine before retry")
    return matches[0]["sent_message_id"]
