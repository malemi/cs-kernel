from __future__ import annotations

import json
from typing import Any

from . import config, rpc

VERSION = 1
STATES = {"normal", "needs-assignment", "assigned", "conflict", "unknown", "closed", "later-inbound"}
HOLD_STATES = {"needs-assignment", "assigned", "conflict", "unknown"}


class AssignmentUnavailable(RuntimeError):
    pass


def _envelope(settings, result: Any, space_id: str | None = None) -> dict:
    if not isinstance(result, dict) or type(result.get("version")) is not int or result["version"] != VERSION:
        raise AssignmentUnavailable("assignment protocol version 1 is unavailable")
    if result.get("actor_uid") != settings.engine_owner_uid:
        raise AssignmentUnavailable("assignment engine identity does not match the selected account")
    if not isinstance(result.get("space_id"), str) or not result["space_id"]:
        raise AssignmentUnavailable("assignment company scope is unavailable")
    if space_id is not None and result["space_id"] != space_id:
        raise AssignmentUnavailable("assignment peer belongs to a different company space")
    if type(result.get("complete")) is not bool:
        raise AssignmentUnavailable("assignment completeness is missing")
    return result


def _row(row: Any, space_id: str) -> dict:
    if not isinstance(row, dict) or row.get("space_id") != space_id:
        raise AssignmentUnavailable("assignment task company scope is invalid")
    if not all(isinstance(row.get(k), str) and row[k] for k in ("id", "thread_key", "assignee_uid")):
        raise AssignmentUnavailable("assignment task identity is incomplete")
    if type(row.get("revision")) is not int or row["revision"] < 1 or row.get("state") not in {"assigned", "closed"}:
        raise AssignmentUnavailable("assignment task revision or state is invalid")
    if not isinstance(row.get("covered_inbound"), list) or not all(isinstance(v, str) for v in row["covered_inbound"]):
        raise AssignmentUnavailable("assignment task coverage is invalid")
    return row


def listing(settings) -> dict:
    result = _envelope(settings, rpc.call_sync(settings, "tasks.assignment.list", {}, timeout=60))
    if not result["complete"] or not isinstance(result.get("items"), list):
        raise AssignmentUnavailable("assignment list is incomplete")
    for row in result["items"]:
        _row(row, result["space_id"])
    return result


def _unknown(thread_key: str, reason: str) -> dict:
    return {"version": VERSION, "complete": False, "thread_key": thread_key,
            "state": "unknown", "hold_auto_reply": True, "task": None,
            "events": [], "covered_inbound": [], "reply_evidence": [], "reason": reason}


def _project_one(settings, thread_key: str, space_id: str | None = None) -> dict:
    result = _envelope(settings, rpc.call_sync(settings, "tasks.assignment.project", {"thread_key": thread_key}, timeout=60), space_id)
    if result.get("thread_key") != thread_key or result.get("state") not in STATES:
        raise AssignmentUnavailable("assignment projection does not name the requested thread")
    if type(result.get("hold_auto_reply")) is not bool:
        raise AssignmentUnavailable("assignment projection has no action boundary")
    if result["state"] in HOLD_STATES | {"closed"} and not result["hold_auto_reply"]:
        raise AssignmentUnavailable("assignment projection has contradictory action boundary")
    if not result["complete"] and not result["hold_auto_reply"]:
        raise AssignmentUnavailable("incomplete assignment projection permits an automatic reply")
    if result.get("task") is not None:
        _row(result["task"], result["space_id"])
        if result["task"]["thread_key"] != thread_key:
            raise AssignmentUnavailable("assignment task belongs to another thread")
    expected_task_state = {"assigned": "assigned", "closed": "closed", "later-inbound": "closed"}.get(result["state"])
    if expected_task_state and (result.get("task") or {}).get("state") != expected_task_state:
        raise AssignmentUnavailable("assignment projection has contradictory task state")
    if result["state"] == "normal" and result.get("task") is not None:
        raise AssignmentUnavailable("normal assignment projection carries a task")
    if not isinstance(result.get("reason"), str):
        raise AssignmentUnavailable("assignment projection reason is unavailable")
    for key in ("covered_inbound", "current_inbound", "current_message_ids", "covered_message_ids"):
        if not isinstance(result.get(key), list) or not all(isinstance(value, str) for value in result[key]):
            raise AssignmentUnavailable("assignment projection coverage metadata is incomplete")
    for key in ("events", "covered_inbound", "reply_evidence"):
        if not isinstance(result.get(key), list):
            raise AssignmentUnavailable("assignment projection metadata is incomplete")
    return result


def project(settings, thread_key: str, *, peers: bool = True) -> dict:
    if not isinstance(thread_key, str) or not thread_key.strip():
        return _unknown(thread_key or "", "exact thread identity is required")
    try:
        result = _project_one(settings, thread_key)
    except Exception as exc:
        return _unknown(thread_key, f"assignment authority unavailable ({type(exc).__name__})")
    if not peers:
        return result
    responses = [(settings.engine_owner_uid, result)]
    unknown = []
    seen = {settings.engine_owner_uid}
    for name, uid in settings.account_map.items():
        if uid in seen:
            continue
        seen.add(uid)
        try:
            peer = config.load(engine_owner_uid=uid)
            responses.append((name, _project_one(peer, thread_key, result["space_id"])))
        except Exception:
            unknown.append(name)
    evidence = [item for _, response in responses for item in response["reply_evidence"]]
    for _, response in responses:
        if response.get("task") != result.get("task"):
            return {**result, "state": "conflict", "hold_auto_reply": True,
                    "reason": "assignment changed while reading peer scope", "reply_evidence": evidence}
    task = result.get("task") or {}
    creator = next((response for _, response in responses
                    if task.get("state") == "closed" and response["complete"]
                    and response["state"] in {"closed", "later-inbound"}
                    and response["actor_uid"] == task.get("creator_uid")), None)
    if creator is not None:
        result = creator
    for name, response in responses:
        owner_refusal = (creator is not None and response["reason"] == "SOURCE_OWNER_REQUIRED"
                         and response.get("source_owner_uid") == task.get("creator_uid"))
        if ((not response["complete"] and response["state"] != "needs-assignment") or response["state"] == "unknown") and not owner_refusal:
            unknown.append(name)
    result = {**result, "reply_evidence": evidence}
    if unknown:
        return {**result, "state": "unknown", "complete": False, "hold_auto_reply": True,
                "reason": "assignment peer scope unreadable: " + ", ".join(unknown)}
    if any(response["state"] == "needs-assignment" for _, response in responses) and result["state"] in {"normal", "later-inbound"}:
        return {**result, "state": "needs-assignment", "complete": False, "hold_auto_reply": True,
                "reason": "peer reply requires explicit human verification and assignment"}
    return result


def projections(settings, thread_keys) -> dict[str, dict]:
    return {key: project(settings, key) for key in sorted(set(thread_keys))}


def provenance(projection: dict, escalated: dict | None = None) -> dict:
    task = projection.get("task") or {}
    basis = "supervised_reply" if task.get("source_confirmation") else "explicit_manual"
    reasons = ([{"basis": basis, "assignee_uid": task["assignee_uid"]}]
               if task.get("state") == "assigned" else [])
    result = {**projection, "provenance": reasons}
    if escalated:
        result["hold_auto_reply"] = True
        owner = escalated.get("owner") or "operator (unspecified identity)"
        reasons.append({"basis": "address_escalation", "owner": owner, "reason": escalated.get("reason") or ""})
        if task.get("state") == "assigned" and owner != task["assignee_uid"]:
            result.update(state="conflict", hold_auto_reply=True,
                          reason="engine assignee and address escalation name different or unverified identities")
    return result


def render(projection: dict) -> str:
    task = projection.get("task") or {}
    identity = f" task={task['id']} revision={task['revision']} assignee={task['assignee_uid']}" if task else ""
    origins = projection.get("provenance") or []
    provenance_text = "; ".join(
        f"{item['basis']}={item.get('assignee_uid') or item.get('owner') or '?'}"
        + (f" ({item['reason']})" if item.get("reason") else "") for item in origins
    )
    return (f"{projection.get('thread_key') or '?'}: {projection['state']}{identity} "
            f"— {projection.get('reason') or ''}; automatic reply "
            f"{'HELD' if projection['hold_auto_reply'] else 'not held by assignment'}"
            + (f"; provenance: {provenance_text}" if provenance_text else ""))


def guard(settings, thread_key: str) -> dict:
    result = project(settings, thread_key)
    if result["hold_auto_reply"]:
        raise AssignmentUnavailable(render(result))
    return result


def commit(settings, intent: dict, grant: dict) -> dict:
    if intent.get("actor_uid") != settings.engine_owner_uid or type(intent.get("version")) is not int or intent.get("version") != VERSION:
        raise AssignmentUnavailable("assignment intent does not match the selected engine identity")
    result = rpc.call_sync(settings, "tasks.assignment.commit", {"intent": intent, "grant": grant}, timeout=60)
    if not isinstance(result, dict) or type(result.get("version")) is not int or result.get("version") != VERSION or result.get("acknowledged") is not True:
        raise AssignmentUnavailable("engine did not acknowledge assignment mutation")
    expected = {"operation_id": intent.get("operation_id"), "task_id": intent.get("task_id"),
                "space_id": intent.get("space_id"), "revision": intent.get("expected_revision", -1) + 1,
                "state": "closed" if intent.get("operation") == "close" else "assigned"}
    if intent.get("operation") == "close":
        expected["handled_ref"] = intent.get("handled_ref")
    else:
        expected["assignee_uid"] = intent.get("assignee_uid")
    import hashlib
    payload_digest = hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    if any(result.get(k) != v for k, v in expected.items()) or result.get("payload_digest") != payload_digest:
        raise AssignmentUnavailable("assignment acknowledgement does not match exact intent")
    if intent.get("operation") == "close" and result.get("covered_inbound") != intent.get("covered_inbound"):
        raise AssignmentUnavailable("assignment close acknowledgement does not match exact inbound coverage")
    return result


def split_inbound(inbound: list[dict], assignment: dict[str, dict], escalated: dict,
                  self_addrs: set[str], ignore, now) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    from .addr_match import AddrSet
    normal, human, audit, reopened = [], [], [], []
    groups = {}
    for message in inbound:
        email = (message.get("email") or "").strip().lower()
        if not email or email in self_addrs or email in AddrSet(ignore) or message.get("date") is None:
            normal.append(message)
            continue
        key = (message.get("thread_key") or "").strip()
        groups.setdefault((email, key), []).append(message)
    for (email, key), messages in groups.items():
        projection = provenance(assignment.get(key, _unknown(key, "exact thread authority unavailable")), escalated.get(email))
        latest = max(messages, key=lambda row: row["date"])
        row = {"email": email, "name": latest.get("name") or "", "subject": latest.get("subject") or "",
               "last_inbound_date": latest["date"], "days_waiting": (now - latest["date"]).days,
               "thread_key": key, "state": projection["state"], "assignment": projection}
        if escalated.get(email) and projection["state"] == "normal":
            normal.extend(messages)
        elif escalated.get(email):
            human.append(row)
        elif projection["state"] == "closed" and projection["complete"]:

            covered = projection.get("covered_message_ids")
            fresh = [m for m in messages if not m.get("message_id") or not isinstance(covered, list)
                     or m["message_id"] not in covered]
            if fresh:
                new = max(fresh, key=lambda item: item["date"])
                reopened.append({**row, "subject": new.get("subject") or "", "last_inbound_date": new["date"],
                                 "days_waiting": (now - new["date"]).days, "state": "open",
                                 "assignment": {**projection, "state": "later-inbound", "reason": "inbound identity is not covered by acknowledged closure"}})
            else:
                audit.append(row)
        elif projection["hold_auto_reply"]:
            human.append(row)
        elif projection["state"] == "later-inbound":
            reopened.append({**row, "state": "open"})
        else:
            normal.extend(messages)
    return normal, human, audit, reopened
