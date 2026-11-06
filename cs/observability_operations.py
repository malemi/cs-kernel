"""Finite exact-operation observations carried by the existing diagnostic registry."""

from . import observability_causal as causal

CAUSES = {
    "explicit_operator_request": "explicit_operator_request",
    "sent_mirror_retired": "mirror_retired",
    "sent_mirror_reconciled": "mirror_retired",
    "publication_outcome_unresolved": "uncertain_provider_outcome",
    "append_readback_unresolved": "uncertain_provider_outcome",
    "operation_held": "operation_held",
    "thread_copy_conflict": "thread_conflict",
    "residual_copy_conflict": "thread_conflict",
    "publication-unsupported": "saved_unpublished",
    "generation-returned-error-after-save": "saved_unpublished",
    "stale_snapshot": "changed_snapshot",
    "draft_changed": "changed_snapshot",
    "exact_send_binding_changed": "changed_snapshot",
    "operation_binding_changed": "changed_snapshot",
    "exact_send_unconfirmed": "uncertain_provider_outcome",
    "retirement_unconfirmed": "uncertain_provider_outcome",
    "exact_send_operation_held": "operation_held",
    "thread_operation_held": "operation_held",
    "exact_send_not_dispatched": "operation_not_dispatched",
    "exact_sent_verified": "sent_verified_cleanup_pending",
    "automatic_manual_hold": "automatic_manual_hold",
    "assignment_hold": "assignment_hold",
    "paused": "local_send_hold",
    "self_recipient": "local_send_hold",
    "suppressed_recipient": "local_send_hold",
    "interactive_exact_send_unsupported": "unsupported_operation",
    "sent_mirror_recovery_unsupported": "unsupported_operation",
}


def summary():
    state = causal._STATE.get()
    return state.get("operation_summary") if state else None


def record(settings, value, *, command, root=None):
    try:
        if not isinstance(value, dict):
            return
        from .observability_producers import emit

        stages = value.get("achieved_stages") or []
        certainty = value.get("effect_certainty", "unknown")
        cause = CAUSES.get(value.get("cause"), "unknown")
        if value.get("state") == "review-visible" and value.get("ok") is True:
            cause = "review_verified"
        if value.get("cause") == "publication-or-generation-incomplete" and certainty == "not-dispatched" and "engine-saved" in stages:
            cause = "saved_unpublished"
        if value.get("cause") == "sent_mirror_recovery_unavailable" and certainty == "unknown":
            cause = "uncertain_provider_outcome"
        if cause in {"automatic_manual_hold", "assignment_hold", "local_send_hold", "operation_held"}:
            status, reason, outcome = "held", "policy-hold", "held"
        elif value.get("ok") is True:
            status, reason, outcome = "verified", "none", "accepted"
            if cause == "sent_verified_cleanup_pending":
                status = "delivered-cleanup-incomplete"
        else:
            status, reason, outcome = "failed", "incomplete-input", "failed"
        if certainty == "unknown" and status != "verified":
            status, reason = "unknown-effect", "unknown"
        certainty = "none" if certainty == "not-dispatched" else certainty
        if certainty not in {"none", "unknown", "accepted", "verified"}:
            certainty = "unknown"
        if cause == "unknown":
            check, outcome = "causal_evidence", "unknown"
        else:
            check = "exact_draft_operation"
        if cause == "explicit_operator_request":
            status = "accepted"
        previous = summary()
        if previous and causal.selected() and causal.selected()["outcome"] != "accepted":
            return
        decision = causal.decision(check, cause, layer="exact_draft", command=command, outcome=outcome, replace=bool(causal.selected() and causal.selected()["outcome"] == "accepted"),
            engine_saved="engine-saved" in stages, review_visible="review-visible" in stages,
            sent_verified="sent" in stages, operator_requested=value.get("audit_reason") == "explicit_operator_request")
        metadata = {"command": command, "draft_id": value.get("draft_id"), "root_id": value.get("root") or root,
                    "operation_id": value.get("operation_id"), "request_revision": value.get("expected_snapshot"),
                    "achieved_stages": stages, "causal": decision}
        stage = "cleanup" if command == "draft-retire" else "authority" if reason == "policy-hold" else "verification"
        event = emit(settings, stage, status, reason=reason, effect_certainty=certainty, **metadata)
        causal.cause(event)
        state = causal._STATE.get()
        if state is not None:
            state["operation_summary"] = {"status": status, "reason": reason, "effect_certainty": certainty, "metadata": metadata}
    except Exception:
        pass


def assignment_hold(settings, value, root, *, operator=False):
    evidence = value.get("reply_evidence") or []
    positive = (value.get("state") == "needs-assignment" and value.get("reason") == "NEEDS_HUMAN_VERIFICATION"
        and value.get("task") is None and value.get("authority_complete") is not False
        and bool(evidence) and all(isinstance(item, dict) and item.get("complete") is True for item in evidence)
        and any(item.get("judgement") in {"NONAUTOMATIC_MEMBER_REPLY_CANDIDATE", "MEMBER_ACTIVITY_REQUIRES_HUMAN_VERIFICATION"} for item in evidence))
    cause = "automatic_manual_hold" if positive and not operator else "assignment_hold"
    record(settings, {"cause": cause, "ok": False, "effect_certainty": "not-dispatched"}, command="draft-send", root=root)
    return cause
