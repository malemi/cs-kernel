from __future__ import annotations

from . import observability
from contextlib import nullcontext

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import time
from collections import deque
from typing import Any

from . import config, rpc, rpc_reads
from .operator_health import _ancestry_conflict

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


def listing(settings, *, deadline=None) -> dict:
    timeout = 60 if deadline is None else min(60, deadline - time.monotonic())
    if timeout <= 0:
        raise AssignmentUnavailable("assignment listing capacity deferred: deadline")
    result = _envelope(settings, rpc.call_sync(settings, "tasks.assignment.list", {}, timeout=timeout))
    if not result["complete"] or not isinstance(result.get("items"), list):
        raise AssignmentUnavailable("assignment list is incomplete")
    for row in result["items"]:
        _row(row, result["space_id"])
    return result


def _unknown(thread_key: str, reason: str, *, owner_uid: str | None = None) -> dict:
    binding = ({"actor_uid": owner_uid, "source_owner_uid": owner_uid}
               if isinstance(owner_uid, str) and owner_uid.strip() else {})
    return {**binding, "version": VERSION, "complete": False, "thread_key": thread_key,
            "state": "unknown", "hold_auto_reply": True, "task": None,
            "events": [], "covered_inbound": [], "reply_evidence": [], "reason": reason}


def _observe_peer(settings, thread_key, response=None, *, failure=None):
    try:
        from .observability_causal import PAIRS, decision
        from .observability_producers import emit
        if response is not None and not (response["state"] == "unknown" or (not response["complete"] and response["state"] != "needs-assignment")):
            return
        code = failure or response.get("reason")
        allowed = PAIRS["assignment_peer_projection"] if failure else {"REPLY_SOURCE_UNAVAILABLE", "SOURCE_UNAVAILABLE", "SOURCE_OWNER_REQUIRED"}
        code = code if code in allowed else "unknown"
        observations = [("assignment_peer_projection", code)]
        if response is not None:
            for item in response["reply_evidence"]:
                if (isinstance(item, dict) and ("version" not in item or (type(item["version"]) is int and item["version"] == VERSION))
                        and all(field not in item or item[field] == response[field] for field in ("actor_uid", "space_id", "thread_key"))
                        and item.get("complete") is False
                        and item.get("judgement") == "UNKNOWN"):
                    reply = item.get("reason")
                    observations.append(("assignment_peer_reply", reply if isinstance(reply, str) and reply in PAIRS["assignment_peer_reply"] else "unknown"))
        for check, cause in observations:
            causal = decision(check, cause, layer="source", command="assignment", method="tasks.assignment.project",
                outcome="unknown" if cause == "unknown" else "failed",
                **({"scoped_sent_match_unique": False} if cause == "SENT_REPLY_NOT_SYNCED" else {}))
            emit(settings, "authority", "failed", reason="incomplete-input", root_id=thread_key,
                command="assignment", method="tasks.assignment.project", error_file="cs/task_assignment.py", causal=causal)
    except Exception:
        pass


def _project_one(settings, thread_key: str, space_id: str | None = None) -> dict:
    try:
        raw = rpc.call_sync(settings, "tasks.assignment.project", {"thread_key": thread_key}, timeout=150)
    except rpc.EngineError as error:
        _observe_peer(settings, thread_key, failure="remote_invalid_params" if error.code == -32602 else "remote_error")
        raise
    except Exception:
        _observe_peer(settings, thread_key, failure="transport_unavailable")
        raise
    try:
        result = _validate_projection(settings, thread_key, raw, space_id)
    except Exception:
        _observe_peer(settings, thread_key, failure="projection_invalid")
        raise
    _observe_peer(settings, thread_key, result)
    return result


def _validate_projection(settings, thread_key: str, raw, space_id: str | None = None) -> dict:
    result = _envelope(settings, raw, space_id)
    if result.get("thread_key") != thread_key or result.get("state") not in STATES:
        raise AssignmentUnavailable("assignment projection does not name the requested thread")
    if type(result.get("hold_auto_reply")) is not bool:
        raise AssignmentUnavailable("assignment projection has no action boundary")
    if result["state"] in HOLD_STATES | {"closed"} and not result["hold_auto_reply"]:
        raise AssignmentUnavailable("assignment projection has contradictory action boundary")
    if not result["complete"] and not result["hold_auto_reply"]:
        raise AssignmentUnavailable("incomplete assignment projection permits an automatic reply")
    extension = {"authoritative_thread_key", "component_thread_keys", "component_scope_present"}
    if extension.intersection(result):
        authority = result.get("authoritative_thread_key")
        component = result.get("component_thread_keys")
        if (not extension.issubset(result) or not isinstance(authority, str) or not authority
                or type(result.get("component_scope_present")) is not bool
                or not isinstance(component, list) or not component
                or not all(isinstance(value, str) and re.fullmatch(r"<[^<>\s@]+@[^<>\s@]+>", value)
                           for value in component)
                or component != sorted(set(component)) or thread_key not in component or authority not in component
                or (not result["component_scope_present"] and (component != [thread_key] or authority != thread_key))):
            raise AssignmentUnavailable("assignment component metadata is invalid")
    else:
        authority = thread_key
    if result.get("task") is not None:
        _row(result["task"], result["space_id"])
        if result["task"]["thread_key"] != authority:
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
    if result["reason"] == "RFC_ANCESTRY_CONFLICT" and not _ancestry_conflict(result, thread_key):
        raise AssignmentUnavailable("ancestry conflict has contradictory partial authority")
    _validate_observation_hold(result, thread_key)
    return result




def _validate_observation_hold(result, thread_key):
    if not {"authority_complete", "hold_scope"}.intersection(result):
        return
    if (result.get("authority_complete") is not False or result.get("hold_scope") != "exact_observed_message"
            or result["complete"] is not False or result["state"] != "needs-assignment"
            or result["hold_auto_reply"] is not True or result.get("task") is not None
            or result.get("component_scope_present") is not False
            or result.get("source_owner_uid") != result["actor_uid"]
            or any(result[key] for key in ("covered_inbound", "current_inbound", "current_message_ids", "covered_message_ids"))):
        raise AssignmentUnavailable("observation-only assignment hold has contradictory authority")
    observations = [item for item in result["reply_evidence"] if isinstance(item, dict)
                    and item.get("judgement") == "MALFORMED_OWN_SENT_REQUIRES_HUMAN_VERIFICATION"]
    if len(observations) != 1:
        raise AssignmentUnavailable("observation-only assignment evidence is unavailable")
    item = observations[0]
    source = item.get("source")
    if (type(item.get("version")) is not int or item["version"] != VERSION or item.get("complete") is not True
            or any(item.get(key) != result[key] for key in ("actor_uid", "space_id"))
            or item.get("thread_key") != thread_key or not isinstance(item.get("source_id"), str) or not item["source_id"]
            or not isinstance(source, dict) or source.get("actor_uid") != result["actor_uid"]
            or source.get("message_id") != thread_key or source.get("thread_key") != thread_key
            or source.get("observation_only") is not True
            or not isinstance(source.get("mailbox_id"), str) or not source["mailbox_id"]):
        raise AssignmentUnavailable("observation-only assignment evidence binding is invalid")
    provider = source.get("provider")
    if (not isinstance(provider, dict) or not isinstance(provider.get("folder"), str) or not provider["folder"]
            or any(type(provider.get(key)) is not int or provider[key] < 1 for key in ("uidvalidity", "uid"))
            or any(not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None
                   for value in (item.get("digest"), source.get("route_digest"), source.get("raw_header_digest")))):
        raise AssignmentUnavailable("observation-only assignment source metadata is invalid")


def project(settings, thread_key: str, *, peers: bool = True) -> dict:
    if not isinstance(thread_key, str) or not thread_key.strip():
        return _unknown(thread_key or "", "exact thread identity is required", owner_uid=settings.engine_owner_uid)
    try:
        result = _project_one(settings, thread_key)
    except Exception as exc:
        return _unknown(thread_key, f"assignment authority unavailable ({type(exc).__name__})", owner_uid=settings.engine_owner_uid)
    if not peers:
        return result
    responses = [(settings.engine_owner_uid, result)]
    peer_settings = {settings.engine_owner_uid: settings}
    unknown = []
    seen = {settings.engine_owner_uid}
    for name, uid in settings.account_map.items():
        if uid in seen:
            continue
        seen.add(uid)
        try:
            peer = config.load(engine_owner_uid=uid)
            peer_settings[uid] = peer
            responses.append((name, _project_one(peer, thread_key, result["space_id"])))
        except Exception:
            unknown.append(name)
    responses, unknown = _resolve_peer_aliases(thread_key, responses, unknown,
        lambda uid, key: _project_one(settings if uid == settings.engine_owner_uid else config.load(engine_owner_uid=uid), key, result["space_id"]),
        observe=lambda response, code: _observe_peer(peer_settings[response["actor_uid"]], thread_key, failure=code))
    return _merge_peers(result, responses, unknown)


def _resolve_peer_aliases(requested, responses, unknown, read, observe=None):
    primary = responses[0][1]
    canonical = primary.get("authoritative_thread_key", requested)
    primary_component = set(primary.get("component_thread_keys", []))

    def partial_scope(response):
        component = set(response.get("component_thread_keys", []))
        return (primary.get("component_scope_present") is True
                and response.get("component_scope_present") is True
                and {requested, response.get("authoritative_thread_key")} <= component
                and canonical in primary_component and canonical not in component
                and component < primary_component)

    authorities = {response["authoritative_thread_key"] for _, response in responses
                   if response.get("component_scope_present") is True}
    if len(authorities) > 1:
        if any(response.get("component_scope_present") is True
               and response["authoritative_thread_key"] != canonical and not partial_scope(response)
               for _, response in responses):
            unknown.append("contradictory component authority")
            if observe:
                for _, response in responses:
                    observe(response, "alias_authority_conflict")
            return responses, unknown
    else:
        canonical = next(iter(authorities), requested)
    if canonical != requested and any(_ancestry_conflict(response, requested) for _, response in responses):
        unknown.append("unresolved ancestry conflict cannot establish canonical authority")
        if observe:
            for _, response in responses:
                observe(response, "alias_authority_conflict")
        return responses, unknown
    if canonical == requested:
        return responses, unknown
    resolved = []
    for name, original in responses:
        if original.get("component_scope_present") is True and not partial_scope(original):
            resolved.append((name, original))
            continue
        fallback = None
        try:
            fallback = read(original["actor_uid"], canonical)
            if fallback.get("authoritative_thread_key", canonical) != canonical:
                raise AssignmentUnavailable("contradictory canonical authority")
            if original.get("task") is not None and original["task"] != fallback.get("task"):
                raise AssignmentUnavailable("contradictory original task")
            resolved.append((name, ({**fallback, "thread_key": requested, "reply_evidence": original["reply_evidence"]}
                                   if original["state"] == "normal" and not original["hold_auto_reply"]
                                   else {**original, "task": fallback.get("task")})))
            resolved.append((name, fallback))
        except Exception as exc:
            if observe and not (isinstance(exc, AssignmentUnavailable) and str(exc) == "assignment canonical scope pending"):
                observe(original, "alias_scope_unavailable")
            resolved.append((name, original))
            if fallback is not None:
                resolved.append((name, fallback))
            unknown.append(name + " canonical scope unreadable")
    return resolved, unknown


def _merge_peers(result: dict, responses: list, unknown: list) -> dict:
    partial = next((response for _, response in responses
                    if _ancestry_conflict(response, result["thread_key"])), None)
    if partial is not None:
        if unknown or any(response.get("task") is not None or response["state"] == "unknown"
                or (not response["complete"] and not _ancestry_conflict(response, result["thread_key"]))
                or response.get("authoritative_thread_key", result["thread_key"]) != result["thread_key"]
                for _, response in responses):
            return {**partial, "state": "unknown", "reason": "assignment peer scope unreadable with unresolved ancestry conflict"}
        return dict(partial)
    evidence = [item for _, response in responses for item in response["reply_evidence"]]
    result = {**responses[0][1], "thread_key": result["thread_key"]}
    observation_only = any(response.get("authority_complete") is False for _, response in responses)
    if observation_only:
        result.update(authority_complete=False, hold_scope="exact_observed_message", complete=False, hold_auto_reply=True)
    for _, response in responses:
        if response.get("task") != result.get("task"):
            return {**result, "state": "conflict", "hold_auto_reply": True,
                    "reason": "assignment changed while reading peer scope", "reply_evidence": evidence}
    task = result.get("task") or {}
    if observation_only and task:
        unknown.append("observed message does not establish component assignment authority")
    creator = next((response for _, response in responses
                    if not observation_only and task.get("state") == "closed" and response["complete"]
                    and response["state"] in {"closed", "later-inbound"}
                    and response["actor_uid"] == task.get("creator_uid")), None)
    if creator is not None:
        result = {**creator, "thread_key": result["thread_key"]}
    unwaived_hold = False
    for name, response in responses:
        owner_refusal = (creator is not None and response["reason"] == "SOURCE_OWNER_REQUIRED"
                         and response.get("source_owner_uid") == task.get("creator_uid"))
        unwaived_hold |= response["hold_auto_reply"] and not owner_refusal
        if ((not response["complete"] and response["state"] != "needs-assignment") or response["state"] == "unknown") and not owner_refusal:
            unknown.append(name)
    result = {**result, "reply_evidence": evidence}
    if unknown:
        return {**result, "state": "unknown", "complete": False, "hold_auto_reply": True,
                "reason": "assignment peer scope unreadable: " + ", ".join(unknown)}
    if any(response["state"] == "conflict" for _, response in responses):
        return {**result, "state": "conflict", "hold_auto_reply": True,
                "reason": "assignment peer reports conflicting authority"}
    if any(response["state"] == "needs-assignment" for _, response in responses) and result["state"] in {"normal", "later-inbound"}:
        return {**result, "state": "needs-assignment", "complete": False, "hold_auto_reply": True,
                "reason": "peer reply requires explicit human verification and assignment"}
    if unwaived_hold and not result["hold_auto_reply"]:
        return {**result, "state": "unknown", "complete": False, "hold_auto_reply": True,
                "reason": "assignment peer retains an action hold"}
    return result


PROJECTION_SECONDS = 3600
PER_ACCOUNT_CONCURRENCY = 1


def projections(settings, thread_keys, *, deadline=None, owned_process_group=None) -> dict[str, dict]:
    keys = list(dict.fromkeys(sorted(thread_keys) if isinstance(thread_keys, (set, frozenset)) else thread_keys))
    now = time.monotonic()
    if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
        raise ValueError('assignment deadline must be finite')
    if owned_process_group is not None and (type(owned_process_group) is not int
            or owned_process_group != os.getpid() or os.getpgrp() != owned_process_group):
        raise ValueError('assignment worker group is not owned')
    deadline = min(now + PROJECTION_SECONDS, deadline) if deadline is not None else now + PROJECTION_SECONDS
    results = {key: _unknown(key or "", "assignment capacity deferred: projection deadline", owner_uid=settings.engine_owner_uid) for key in keys}
    accounts = [(settings.engine_owner_uid, settings)]
    unavailable = []
    seen = {settings.engine_owner_uid}
    for name, uid in settings.account_map.items():
        if uid in seen:
            continue
        seen.add(uid)
        try:
            accounts.append((name, config.load(engine_owner_uid=uid)))
        except Exception:
            unavailable.append(name)
    first_timeout_event = {}
    budget_stats = {selected.engine_owner_uid: dict(dispatched=0, returned=0, timed_out=0,
                    deferred=0, serial_read_ms=0, failed=0, first=None, event=None,
                    shared_deferred=False, failure_event=None) for _, selected in accounts}

    def budget_summary():
        for _, selected in accounts:
            try:
                from .observability_causal import decision, validate
                from .observability_producers import emit
                stats = budget_stats[selected.engine_owner_uid]
                first = stats['first'] or {}
                origin = first.get('bound_origin')
                actual = first.get('cause')
                expired = origin if actual == 'worker_timeout' else actual
                cause = ('shared_deadline_exhausted' if expired == 'shared_deadline' else
                         'request_timeout' if expired == 'request_timeout' else
                         'batch_deadline' if expired == 'batch_deadline' else
                         'read_failed' if actual in rpc_reads.CAUSES and actual not in {'connection_setup_timeout'} else
                         'timeout_origin_unknown' if stats['timed_out'] else
                         'deadline_capacity_deferred' if stats['shared_deferred'] else
                         'capacity_deferred' if stats['deferred'] else
                         'read_failed' if stats['failed'] else 'complete' if keys else 'no_work')
                failed = stats['timed_out'] > 0 or stats['failed'] > 0 or stats['deferred'] > 0
                value = decision('assignment_time_budget', cause, layer='source', command='assignment',
                    method='tasks.assignment.budget', outcome='failed' if failed else 'accepted',
                    effective_entry_ms=max(0, round((deadline-now)*1000)),
                    elapsed_ms=max(0, round((time.monotonic()-now)*1000)),
                    remaining_ms=max(0, round((deadline-time.monotonic())*1000)), expected_roots=len(keys),
                    scheduler_dispatched=stats['dispatched'], returned_values=stats['returned'],
                    read_timeouts=stats['timed_out'], scheduler_deferred=stats['deferred'], serial_read_ms=stats['serial_read_ms'],
                    global_concurrency=rpc_reads.CONCURRENCY, account_concurrency=PER_ACCOUNT_CONCURRENCY,
                    shared_deadline_selected=origin == 'shared_deadline',
                    batch_deadline_selected=origin == 'batch_deadline', request_timeout_selected=origin == 'request_timeout',
                    bound_ms=first.get('bound_ms', 0))
                reference = stats['event'] or stats['failure_event'] or (first_timeout_event.get('event_id') if cause == 'capacity_deferred' else None)
                refs = {**value['refs'], 'cause_event_id': reference}
                value = validate({**value, 'refs': refs, 'missing_refs': [key for key in refs if refs[key] is None]})
                emit(selected, 'authority', 'failed' if failed else 'result',
                     reason='timeout' if stats['timed_out'] or stats['shared_deferred'] else 'unknown' if failed else 'none',
                     level='ERROR' if failed else 'DEBUG', method='tasks.assignment.budget', command='assignment', causal=value)
            except Exception:
                pass

    if not keys:
        budget_summary()
        return results
    selected_accounts = {selected.engine_owner_uid: (name, selected) for name, selected in accounts}
    queues = {uid: deque() for uid in selected_accounts}
    active = {uid: 0 for uid in selected_accounts}
    states = [{"original": {}, "canonical": {}} for _ in keys]
    completed = set()
    blocked = set()
    reserved = 0
    tokens = {}
    cursor = 0
    rest_started = False
    recovered = set()
    recovery_holds = {}
    observations = {}
    timeout_events = {}
    peer_observations = set()
    configurations = {uid: json.dumps(selected.model_dump(mode="json") if hasattr(selected, "model_dump") else vars(selected), sort_keys=True, default=str)
                      for uid, (_, selected) in selected_accounts.items()}

    def request_identity(uid, key):
        return (uid, configurations[uid], "tasks.assignment.project", key)

    diagnostic = observability.current_context()

    def read(uid, key):
        with (observability.context({**diagnostic, "parent_span_id": diagnostic.get("span_id"), "span_id": None})
              if diagnostic else nullcontext()):
            return read_scoped(uid, key)

    def read_scoped(uid, key):
        started = time.monotonic()
        try:
            return rpc_reads.read_many(selected_accounts[uid][1], "tasks.assignment.project",
                {key: {"thread_key": key}}, request_timeout=150, batch_timeout=180,
                deadline=deadline, token_cache=tokens,
                **({"owned_process_group": owned_process_group} if owned_process_group is not None else {}))[key]
        except Exception as exc:
            return rpc_reads.ReadOutcome(error=exc)
        finally:
            budget_stats[uid]["serial_read_ms"] += max(0, round((time.monotonic()-started)*1000))

    def finish(index):
        if index in completed or len(states[index]["original"]) != len(accounts):
            return
        key = keys[index]
        responses, unknown = [], list(unavailable)
        primary_error = None
        for uid, (name, selected) in selected_accounts.items():
            outcome = states[index]["original"][uid]
            try:
                if outcome.error is not None:
                    raise outcome.error
                responses.append((name, _validate_projection(selected, key, outcome.value)))
            except Exception as exc:
                unknown.append(name + (" " + str(exc) if isinstance(exc, AssignmentUnavailable) and "capacity deferred" in str(exc) else ""))
                if uid == settings.engine_owner_uid:
                    primary_error = exc
        primary = next((response for _, response in responses
                        if response["actor_uid"] == settings.engine_owner_uid), None)
        if primary is None:
            reason = (f"assignment authority unavailable ({type(primary_error).__name__})"
                      if primary_error is not None else "assignment authority unavailable")
            results[key] = {**_unknown(key, reason + ("; " + ", ".join(unknown)
                if isinstance(primary_error, AssignmentUnavailable) and "capacity deferred" in str(primary_error) else ""), owner_uid=settings.engine_owner_uid),
                "reply_evidence": [item for _, response in responses for item in response["reply_evidence"]]}
            completed.add(index)
            return
        scoped = []
        for name, response in responses:
            if response["space_id"] != primary["space_id"]:
                unknown.append(name)
            else:
                scoped.append((name, response))

        def canonical_read(uid, canonical):
            identity = (uid, canonical)
            cache = states[index]["canonical"]
            if identity not in cache:
                cache[identity] = None
                queue = queues[uid]
                position = next((position for position, job in enumerate(queue) if job[0] > index), len(queue))
                queue.insert(position, (index, canonical, True))
            outcome = cache[identity]
            if outcome is None:
                raise AssignmentUnavailable("assignment canonical scope pending")
            if outcome.error is not None:
                raise outcome.error
            return _validate_projection(selected_accounts[uid][1], canonical, outcome.value, primary["space_id"])

        scoped, unknown = _resolve_peer_aliases(key, scoped, unknown, canonical_read,
            observe=lambda response, code: _observe_peer(selected_accounts[response["actor_uid"]][1], key, failure=code))
        if any(outcome is None for outcome in states[index]["canonical"].values()):
            return
        results[key] = _merge_peers(primary, scoped, unknown)
        completed.add(index)

    def record(uid, job, outcome):
        index, key, canonical = job
        identity = (uid, key)
        observation = (uid, key, id(outcome))
        if observation not in peer_observations:
            peer_observations.add(observation)
            if outcome.error is None:
                try:
                    observed = _validate_projection(selected_accounts[uid][1], key, outcome.value)
                except Exception:
                    _observe_peer(selected_accounts[uid][1], key, failure="projection_invalid")
                else:
                    _observe_peer(selected_accounts[uid][1], key, observed)
            elif outcome.diagnostic is None:
                _observe_peer(selected_accounts[uid][1], key, failure="transport_unavailable")
        if outcome.error is None and identity not in recovered:
            try:
                value = _validate_projection(selected_accounts[uid][1], key, outcome.value)
            except Exception:
                value = None
            if (value is not None and value["state"] == "unknown" and value["complete"] is False
                    and value["hold_auto_reply"] is True and value["reason"] == "SOURCE_UNAVAILABLE"):
                recovered.add(identity)
                recovery_holds[(uid, job)] = outcome
                queue = queues[uid]
                position = next((position for position, queued in enumerate(queue) if queued[0] > index), len(queue))
                queue.insert(position, job)
                return
        if (isinstance(outcome.error, AssignmentUnavailable) and "capacity deferred" in str(outcome.error)
                and (uid, job) in recovery_holds):
            outcome = recovery_holds[(uid, job)]
        if outcome.error is not None and outcome.diagnostic is not None:
            try:
                from .observability_causal import decision, validate
                from .observability_producers import emit, error_metadata
                info = rpc_reads.validate_diagnostic(outcome.diagnostic)
                deferred = info['cause'] in {'account_timeout_deferred', 'capacity_timeout_deferred'}
                causal = decision('assignment_read', info['cause'], layer='source', command='assignment', method='tasks.assignment.project',
                    elapsed_ms=info['elapsed_ms'], bound_ms=info['bound_ms'], remaining_ms=info['remaining_ms'] or 0,
                    remaining_available=info['remaining_ms'] is not None, **({'attempted': False} if deferred else {}), shared_deadline_selected=info['bound_origin']=='shared_deadline', batch_deadline_selected=info['bound_origin']=='batch_deadline', request_timeout_selected=info['bound_origin']=='request_timeout')
                if causal:
                    refs = {**causal['refs'], 'cause_event_id': timeout_events.get(uid) if deferred else None}
                    causal = validate({**causal, 'refs': refs, 'missing_refs': [name for name, value in refs.items() if value is None]})
                metadata = error_metadata(outcome.error)
                if info['cause'] in {'remote_invalid_params', 'remote_error'}:
                    metadata = {'error_class': 'EngineError', **({'error_code': info['remote_error_code']} if 'remote_error_code' in info else {})}
                event = emit(selected_accounts[uid][1], 'authority', 'failed', reason='timeout' if isinstance(outcome.error, (TimeoutError, AssignmentUnavailable)) else 'unknown',
                    root_id=key, command='assignment', method='tasks.assignment.project', elapsed_ms=info['elapsed_ms'],
                    **metadata, **({'causal': causal} if causal else {}))
                if event and not isinstance(outcome.error, AssignmentUnavailable) and budget_stats[uid]['failure_event'] is None:
                    budget_stats[uid]['failure_event'] = event['event_id']
                if event and isinstance(outcome.error, TimeoutError) and uid in blocked:
                    timeout_events.setdefault(uid, event['event_id'])
                    first_timeout_event.setdefault('event_id', event['event_id'])
                    if budget_stats[uid]['event'] is None:
                        budget_stats[uid]['event'] = event['event_id']
            except Exception:
                pass
        observations[request_identity(uid, key)] = outcome
        if canonical:
            states[index]["canonical"][(uid, key)] = outcome
        else:
            states[index]["original"][uid] = outcome
        finish(index)

    def enqueue(index):
        key = keys[index]
        if not isinstance(key, str) or not key.strip():
            results[key] = _unknown(key or "", "exact thread identity is required", owner_uid=settings.engine_owner_uid)
            completed.add(index)
        else:
            for queue in queues.values():
                queue.append((index, key, False))

    enqueue(0)
    with ThreadPoolExecutor(max_workers=rpc_reads.CONCURRENCY) as pool:
        futures = {}
        while len(completed) < len(keys) or futures:
            if 0 in completed and not rest_started:
                rest_started = True
                for index in range(1, len(keys)):
                    enqueue(index)
            for uid, queue in queues.items():
                while queue:
                    cached = observations.get(request_identity(uid, queue[0][1]))
                    if cached is not None:
                        record(uid, queue.popleft(), cached)
                        continue
                    if uid in blocked:
                        reason = "assignment capacity deferred after transport timeout"
                    elif reserved == rpc_reads.CONCURRENCY:
                        reason = "assignment capacity deferred after unresolved transport timeout"
                    elif time.monotonic() >= deadline - 2 * rpc_reads.CLOSE_SECONDS:
                        reason = "assignment capacity deferred: projection deadline"
                    else:
                        break
                    cause = 'account_timeout_deferred' if uid in blocked else 'capacity_timeout_deferred' if reserved == rpc_reads.CONCURRENCY else 'shared_deadline'
                    budget_stats[uid]['deferred'] += 1
                    budget_stats[uid]['shared_deferred'] |= cause == 'shared_deadline'
                    record(uid, queue.popleft(), rpc_reads.ReadOutcome(error=AssignmentUnavailable(reason),
                        diagnostic=rpc_reads.diagnostic(cause, now, 0, deadline-time.monotonic(), bound_origin='not_attempted' if cause in {'account_timeout_deferred', 'capacity_timeout_deferred'} else 'shared_deadline')))
            while len(futures) + reserved < rpc_reads.CONCURRENCY:
                chosen = None
                uids = list(queues)
                for offset in range(len(uids)):
                    position = (cursor + offset) % len(uids)
                    uid = uids[position]
                    if queues[uid] and uid not in blocked and active[uid] < PER_ACCOUNT_CONCURRENCY:
                        chosen = uid
                        cursor = (position + 1) % len(uids)
                        break
                if chosen is None or time.monotonic() >= deadline - 2 * rpc_reads.CLOSE_SECONDS:
                    break
                job = queues[chosen].popleft()
                identity = request_identity(chosen, job[1])
                if identity in observations:
                    record(chosen, job, observations[identity])
                    continue
                active[chosen] += 1
                budget_stats[chosen]['dispatched'] += 1
                futures[pool.submit(read, chosen, job[1])] = (chosen, job)
            if futures:
                finished, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in finished:
                    uid, job = futures.pop(future)
                    active[uid] -= 1
                    outcome = future.result()
                    stats = budget_stats[uid]
                    stats['returned'] += outcome.error is None
                    stats['failed'] += outcome.error is not None
                    if isinstance(outcome.error, TimeoutError):
                        stats['timed_out'] += 1
                        if stats['first'] is None:
                            stats['first'] = outcome.diagnostic or {}
                    if isinstance(outcome.error, TimeoutError):
                        blocked.add(uid)
                        reserved += 1
                    record(uid, job, outcome)

    budget_summary()
    return results


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
                  self_addrs: set[str], ignore, now, *, owner_uid: str | None = None) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
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
        projection = provenance(assignment.get(key, _unknown(key, "exact thread authority unavailable", owner_uid=owner_uid)), escalated.get(email))
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
