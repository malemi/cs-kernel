"""Explicit existing-draft sending through the engine's exact operation."""

import json
import re
import sys
from uuid import uuid4

from . import rpc, state, task_assignment
from .addr_match import AddrSet
from .draft_identity import canonical_message_id
from .review_draft import interactive


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _operation(value, settings, draft_id, operation_id, selected):
    if not isinstance(value, dict) or any(
        value.get(key) != expected
        for key, expected in {
            "owner_uid": settings.engine_owner_uid,
            "draft_id": draft_id,
            "operation_id": operation_id,
            "operation_type": "send",
            "canonical_root": selected["binding"]["root"],
        }.items()
    ):
        raise ValueError("operation identity mismatch")
    bound = value.get("binding")
    if (
        not isinstance(bound, dict)
        or {key: item for key, item in bound.items() if key != "transport"}
        != selected["binding"]
        or not _digest(value.get("expected_snapshot"))
        or type(value.get("active")) is not bool
        or type(value.get("version")) is not int
        or value["version"] < 0
        or value.get("stage")
        not in {
            "reserved",
            "inventoried",
            "dispatch_possible",
            "acknowledged",
            "completed",
            "not_dispatched",
        }
        or value["active"] != (value["stage"] not in {"completed", "not_dispatched"})
    ):
        raise ValueError("operation binding mismatch")
    return value


def _outcome(answer, identity, previous):
    if (
        not isinstance(answer, dict)
        or type(answer.get("version")) is not int
        or answer["version"] != 1
        or type(answer.get("ok")) is not bool
        or any(answer.get(key) != value for key, value in identity.items())
        or answer.get("cleanup_certainty") != "not-dispatched"
        or answer.get("audit_reason") != "explicit_operator_request"
        or not isinstance(answer.get("cause"), str)
        or not answer["cause"]
    ):
        raise ValueError("invalid exact send response")
    expected = {
        "sent-with-cleanup-pending": (
            True,
            "verified",
            ["engine-saved", "sent"],
            "retire-sent-mirror",
        ),
        "delivery-unknown": (False, "unknown", ["engine-saved"], "inspect-operation"),
        "send-held": (False, "not-dispatched", ["engine-saved"], None),
    }.get(answer.get("state"))
    if (
        expected is None
        or (answer["ok"], answer.get("effect_certainty"), answer.get("achieved_stages"))
        != expected[:3]
    ):
        raise ValueError("contradictory exact send response")
    if expected[3] is not None and answer.get("next_action") != expected[3]:
        raise ValueError("invalid next action")
    if expected[3] is None and answer.get("next_action") not in {
        "inspect-draft",
        "new-explicit-operation",
    }:
        raise ValueError("invalid next action")
    if (
        previous
        and previous["stage"] in {"dispatch_possible", "acknowledged", "completed"}
        and answer["effect_certainty"] == "not-dispatched"
    ):
        raise ValueError("historical dispatch uncertainty lost")
    if answer["ok"]:
        proof = answer.get("provider_handles")
        if not isinstance(proof, dict) or proof.get("complete") is not True:
            raise ValueError("missing sent proof")
        handle = proof.get("handle")
        if (
            not isinstance(handle, dict)
            or not _digest(handle.get("raw_fingerprint"))
            or any(
                not isinstance(proof.get(key), str)
                or not proof[key]
                or handle.get(key) != proof[key]
                for key in ("folder", "uidvalidity")
            )
            or not isinstance(handle.get("uid"), str)
            or not handle["uid"].isdigit()
            or not canonical_message_id(proof.get("message_id"))
            or not _digest(proof.get("mime_digest"))
        ):
            raise ValueError("invalid sent proof")
        if previous and any(
            proof[key] != previous["binding"]["transport"][key]
            for key in ("message_id", "mime_digest")
        ):
            raise ValueError("sent transport changed")
    return answer


def execute(settings, args):
    supplied = getattr(args, "operation_id", None)
    operation_id = supplied or str(uuid4())
    base = {
        "version": 1,
        "draft_id": args.draft_id,
        "operation_id": operation_id,
        "ok": False,
        "state": "send-held",
        "effect_certainty": "not-dispatched",
        "achieved_stages": [],
        "next_action": "inspect-draft",
    }
    uncertain = bool(supplied)

    def report(answer):
        from .observability_operations import record
        record(settings, answer, command="draft-send")
        if getattr(args, "json", False):
            print(json.dumps(answer, sort_keys=True))
        else:
            print(
                f"Draft {args.draft_id}: {answer.get('cause')}; operation {operation_id}; "
                f"next {answer.get('next_action')}",
                file=sys.stdout if answer.get("ok") else sys.stderr,
            )
        return 5 if answer.get("state") == "sent-with-cleanup-pending" else 3

    def held(cause):
        return report(
            {
                **base,
                "cause": cause,
                "state": "delivery-unknown" if uncertain else "send-held",
                "effect_certainty": "unknown" if uncertain else "not-dispatched",
                "next_action": "inspect-operation" if uncertain else "inspect-draft",
            }
        )

    try:
        if not interactive():
            return held("operator_request_not_interactive")
        caps = rpc.call_sync(settings, "system.capabilities", {}, timeout=args.timeout)
        if (
            not isinstance(caps, dict)
            or type(caps.get("interactive_exact_send")) is not int
            or caps["interactive_exact_send"] != 1
        ):
            return held("interactive_exact_send_unsupported")
        previous = None
        if supplied:
            status = rpc.call_sync(
                settings,
                "drafts.operation_status",
                {"operation_id": operation_id},
                timeout=args.timeout,
            )
            if (
                not isinstance(status, dict)
                or type(status.get("ok")) is not bool
                or "operation" not in status
            ):
                raise ValueError("invalid operation lookup")
            previous = status["operation"]
            if status["ok"] != (previous is not None):
                raise ValueError("invalid operation lookup")
            if previous is None:
                uncertain = False
        selected = rpc.call_sync(
            settings,
            "drafts.operator_send_inspect",
            {"draft_id": args.draft_id},
            timeout=args.timeout,
        )
        if (
            not isinstance(selected, dict)
            or selected.get("ok") is not True
            or selected.get("draft_id") != args.draft_id
            or selected.get("owner_id") != settings.email_address
            or selected.get("owner_uid") != settings.engine_owner_uid
        ):
            return held("exact_send_inspection_unavailable")
        draft, bound = selected["draft"], selected["binding"]
        expected = selected["expected_snapshot"]
        base["achieved_stages"] = ["engine-saved"]
        if previous is not None:
            previous = _operation(
                previous, settings, args.draft_id, operation_id, selected
            )
            expected = previous["expected_snapshot"]
            uncertain = previous["stage"] != "not_dispatched"
        else:
            if settings.pause_path.exists():
                return held("paused")
            recipients = set(bound["recipients"] + bound["cc"])
            if recipients & (
                settings.self_email_set | {settings.email_address.lower()}
            ):
                return held("self_recipient")
            local = state.State(settings.db_path)
            try:
                suppressed = AddrSet(local.do_not_contact_set())
            finally:
                local.conn.close()
            if any(address in suppressed for address in recipients):
                return held("suppressed_recipient")
            if draft["status"] != "sent":
                task_assignment.operator_guard(settings, bound["root"], bound["target"])
            if settings.pause_path.exists():
                return held("paused")
        uncertain = True
        if not _digest(expected):
            raise ValueError("invalid snapshot")
        identity = {
            "draft_id": args.draft_id,
            "operation_id": operation_id,
            "owner_id": settings.email_address,
            "owner_uid": settings.engine_owner_uid,
            "expected_snapshot": expected,
            "root": bound["root"],
        }
        answer = rpc.call_sync(
            settings,
            "drafts.send_operator",
            {
                "draft_id": args.draft_id,
                "expected_snapshot": expected,
                "operation_id": operation_id,
                "binding": bound,
                "version": 1,
                "reason": "explicit_operator_request",
            },
            timeout=args.timeout,
        )
        return report(_outcome(answer, identity, previous))
    except Exception as error:
        return held(getattr(error, "diagnostic_cause", "exact_send_unavailable"))
