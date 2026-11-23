"""Exact source selection and mailbox reply operations through the engine."""
from __future__ import annotations

import json
import os
import sys
import hashlib
import contextvars
import functools
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from uuid import UUID, uuid4

from . import gmail_archive, rpc, state
from .engine_view import _parse
from .authored_mail import authored_plain
from .addr_match import AddrSet
from .thread_key import normalize_key, thread_key
from . import observability_causal as causal
from .observability_producers import emit, error_metadata, observe

_SOURCE = contextvars.ContextVar("draft_source_diagnostic", default=None)


def _preparation_scope(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        token = _SOURCE.set({})
        try:
            with causal.scope():
                return function(*args, **kwargs)
        finally:
            _SOURCE.reset(token)
    return wrapped


def _source_decision(check, cause, **facts):
    return causal.decision(check, cause, layer="source", method="draft.prepare",
                           phase="review", command="draft-reply", **facts)


def _source_observe(function):
    @functools.wraps(function)
    def wrapped(settings, root, source_id, timeout):
        try:
            return function(settings, root, source_id, timeout)
        except Exception as exc:
            try:
                value = causal.selected()
                if value is None:
                    facts = {"generation_started": False}
                    diagnostic = _SOURCE.get()
                    if diagnostic is not None:
                        facts["body_comparison_performed"] = bool(diagnostic.get("comparison_performed"))
                    value = _source_decision("causal_evidence", "unknown", outcome="unknown", **facts)
                emit(settings, "generation", "failed", level="ERROR", reason="incomplete-input",
                     effect_certainty="none", root_id=root, method="draft.prepare",
                     causal=value, **error_metadata(exc))
            except Exception:
                pass
            raise
    return wrapped


def _body(value):
    text = str(value or "")
    body, note = authored_plain(text)
    known = {
        "ambiguous unquoted text after reply delimiter; authored text not compared": 1,
        "ambiguous reply delimiter; authored text not compared": 2,
        "ambiguous forwarded/reply header; authored text not compared": 2,
    }
    try:
        diagnostic = _SOURCE.get()
        if diagnostic is not None and diagnostic.get("parses") is not None:
            diagnostic["parses"].append((len(text), len(body), bool(note),
                known.get(note, 3 if note else 0)))
        elif diagnostic is not None and note:
            code = known.get(note)
            _source_decision("draft_source_body" if code else "causal_evidence",
                "engine_authored_unquoted_tail" if code == 1 else "source_authored_ambiguous" if code else "unknown",
                outcome="failed" if code else "unknown", engine_body_chars=len(text),
                engine_authored_chars=len(body), engine_parse_ambiguous=True,
                body_comparison_performed=False, generation_started=False)
    except Exception:
        pass
    return "" if note else " ".join(body.split())


def _compare_source_body(engine, provider, owner, sender):
    """Allow one known archive quote cut only with the full provider original.

    This establishes the archive's authored prefix, never provider completeness.
    The caller separately requires a complete read and supplies its entire body
    to the engine, including any material after the quoted-message headers.
    """
    left, right = _body(engine), _body(provider)
    if left and left == right:
        return True
    marker = "-----Messaggio originale-----"
    if engine.count(marker) != 1 or provider.count(marker) != 1:
        return False
    original, ending = engine.split(marker)
    current, tail = provider.split(marker)
    if ending.strip() or not _body(original) or _body(original) != _body(current):
        return False
    lines = tail.strip().splitlines()
    if len(lines) < 4 or any(not lines[i].startswith(prefix) for i, prefix in enumerate(("Da:", "Inviato:", "A:", "Oggetto:"))):
        return False
    def quoted_address_matches(value, expected):
        value, expected = value.strip(), expected.lower()
        display, bracket, _ = value.partition("<")
        if bracket and "@" in display and not display.lstrip().startswith('"'):
            return value.lower() == f"{expected} <{expected}>"
        return parseaddr(value)[1].lower() == expected
    return (quoted_address_matches(lines[0][3:], owner)
            and quoted_address_matches(lines[2][2:], sender))


def _same_source_body(engine, provider, owner, sender):
    diagnostic = _SOURCE.get()
    if diagnostic is None:
        return _compare_source_body(engine, provider, owner, sender)
    diagnostic["comparison_performed"] = True
    diagnostic["parses"] = []
    try:
        result = _compare_source_body(engine, provider, owner, sender)
        if not result:
            try:
                left, right = diagnostic["parses"][:2]
                cause = ("unknown" if 3 in (left[3], right[3]) else
                         "provider_authored_unquoted_tail" if right[3] == 1 else
                         "engine_authored_unquoted_tail" if left[3] == 1 else
                         "source_authored_ambiguous" if left[2] or right[2] else "source_body_different")
                _source_decision("causal_evidence" if cause == "unknown" else "draft_source_body", cause,
                    outcome="unknown" if cause == "unknown" else "failed", body_comparison_performed=True,
                    generation_started=False, engine_body_chars=left[0], provider_body_chars=right[0],
                    engine_authored_chars=left[1], provider_authored_chars=right[1],
                    engine_parse_ambiguous=left[2], provider_parse_ambiguous=right[2])
            except Exception:
                pass
        return result
    finally:
        diagnostic.pop("parses", None)


@_source_observe
def source(settings, root, source_id, timeout):
    if not isinstance(root, str) or not root or normalize_key(root) != root:
        raise ValueError("exact RFC thread is required")
    result = rpc.call_sync(settings, "emails.list_by_thread", {"thread_id": root}, timeout=timeout)
    rows = result.get("emails") if isinstance(result, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("exact-thread source unavailable")
    ids, inbound = set(), []
    for row in rows:
        value = row.get("id") if isinstance(row, dict) else None
        if (not isinstance(value, str) or str(UUID(value)) != value or value in ids
                or row.get("mailbox_address") != settings.email_address
                or (row.get("thread_id") is not None and row["thread_id"] != root)):
            raise ValueError("source identity is foreign, missing or ambiguous")
        ids.add(value)
        sender = parseaddr(row.get("from_email") or "")[1].lower()
        if not sender or type(row.get("is_user_sent")) is not bool:
            raise ValueError("source message direction or sender is unknown")
        if sender == settings.email_address.lower() or row["is_user_sent"]:
            continue
        when = _parse(row.get("date"))
        if when is None:
            raise ValueError("inbound source recency is unknown")
        inbound.append((row, sender, when))
    if source_id and source_id not in ids:
        raise ValueError("requested source ID is not in this own-mailbox thread")
    if not inbound:
        raise ValueError("source has no complete inbound metadata")
    selected = max(inbound, key=lambda item: item[2])
    if sum(item[2] == selected[2] for item in inbound) != 1:
        raise ValueError("latest engine inbound source is ambiguous")
    if source_id and selected[0]["id"] != source_id:
        raise ValueError("requested source is not the latest inbound")
    row, sender, when = selected
    if not _body(row.get("body_plain")):
        raise ValueError("latest inbound source body is incomplete")
    if sender in settings.self_email_set or sender == settings.email_address.lower():
        raise ValueError("source sender is a configured self identity")
    local = state.State(settings.db_path)
    try:
        suppressed = AddrSet(local.do_not_contact_set())
    finally:
        local.conn.close()
    if sender in suppressed:
        raise ValueError("source sender is suppressed")
    observed = {}
    window_start = min(when, datetime.now(timezone.utc)) - timedelta(days=1)
    messages = gmail_archive.thread_with(settings, sender, limit=100, observation=observed,
                                         body_limit=65536, thread_root=root, thread_since=window_start)
    if observed.get("inventory_complete") is not True:
        raise ValueError("Gmail source observation is incomplete")
    matching = [m for m in messages if m.get("outbound") is False
                and thread_key(m.get("message_id"), m.get("references"), m.get("in_reply_to")) == root]
    if (not matching or any(not m.get("date") or not m.get("from_addr")
                            or not str(m.get("provider_uid") or "").isdigit() for m in matching)
            or len({m["provider_uid"] for m in matching}) != len(matching)):
        raise ValueError("Gmail cannot corroborate exact source thread")
    latest = max(matching, key=lambda m: int(m["provider_uid"]))
    target = latest.get("message_id")
    if (latest.get("body_complete") is not True
            or latest.get("from_addr") != sender
            or latest.get("date") is None or latest["date"] < window_start
            or not target or sum(m["date"] == latest["date"] for m in matching) != 1
            or int(latest["date"].timestamp()) != int(when.timestamp())
            or latest.get("subject") != row.get("subject")
            or not _same_source_body(row["body_plain"], latest.get("body") or "", settings.email_address, sender)
            or (row.get("original_message_id") and normalize_key(row["original_message_id"]) != target)):
        if causal.selected() is None:
            _source_decision("draft_source_identity", "source_identity_uncorroborated",
                             body_comparison_performed=bool((_SOURCE.get() or {}).get("comparison_performed")), generation_started=False)
        raise ValueError("Gmail and engine source do not identify the same latest inbound")
    alternatives = []
    for alternative in latest.get("body_alternatives") or []:
        if alternative["body"] != latest["body"] and alternative not in alternatives:
            alternatives.append(alternative)
    if len(latest["body"]) + sum(len(value["body"]) for value in alternatives) > 65536:
        raise ValueError("complete source MIME representations exceed the total 65536 character prompt bound")
    return {"id": row["id"], "sender": sender, "target": target,
            "references": latest.get("references") or "", "body": row["body_plain"],
            "provider_body": latest["body"],
            "provider_alternatives": alternatives,
            "provider_evidence": {"window_since": observed.get("window_since"),
                                  "header_count": observed.get("header_count"),
                                  "exact_root_count": observed.get("exact_root_count"),
                                  "provider_uid": latest["provider_uid"],
                                  "inventory_complete": observed["inventory_complete"]}}


def scheduled():
    return any(os.environ.get(key) for key in (
        "CS_OPERATOR_HEADLESS", "CS_HEADLESS_SEND", "CS_OPERATOR_HEALTH_CONTEXT"))


def _require(settings, capability, timeout):
    caps = rpc.call_sync(settings, "system.capabilities", {}, timeout=timeout)
    if not isinstance(caps, dict) or type(caps.get(capability)) is not int or caps[capability] != 1:
        raise ValueError(f"engine capability {capability} version 1 required")


def _key(args, mode, identity):
    if getattr(args, "operation_id", None):
        return args.operation_id
    context = json.loads(os.environ.get("CS_OPERATOR_HEALTH_CONTEXT") or "{}")
    if mode in ("send-draft", "trash") or context.get("nonce"):
        material = json.dumps([mode, context.get("nonce"), identity], separators=(",", ":"))
        return "cs:" + hashlib.sha256(material.encode()).hexdigest()
    return str(uuid4())


def _bound_source(settings, key, mode, root, source_id=None):
    db = state.State(settings.db_path)
    try:
        if source_id:
            with db.conn:
                db.conn.execute(
                    "INSERT OR IGNORE INTO mailbox_reply_sources VALUES (?, ?, ?, ?, ?)",
                    (settings.email_address, key, mode, root, source_id))
        row = db.conn.execute(
            "SELECT mode, thread_key, source_id FROM mailbox_reply_sources WHERE owner=? AND request_key=?",
            (settings.email_address, key)).fetchone()
        if row and (tuple(row)[:2] != (mode, root) or source_id and source_id != row["source_id"]):
            raise ValueError("request key already bound to another reply")
        return row["source_id"] if row else None
    finally:
        db.conn.close()


def _report(settings, command, value, root=None):
    from .observability_operations import record
    if not (causal.selected() and value.get("effect_certainty") == "not-dispatched" and not value.get("ok")):
        record(settings, value, command=command, root=root)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0 if value.get("ok") is True else 5 if value.get("effect_certainty") in ("unknown", "unconfirmed") else 3


def named_action(settings, args, action):
    command = "draft-send" if action == "send" else "draft-delete"
    key = _key(args, "send-draft" if action == "send" else "trash", args.draft_id)
    params = {"draft_id": args.draft_id}
    attempted = False
    try:
        if scheduled():
            raise ValueError("named mailbox actions require a person's instruction")
        _require(settings, "mailbox_drafts", args.timeout)
        if action != "get":
            params["request_key"] = key
        attempted = action != "get"
        result = rpc.call_sync(settings, "drafts." + action, params, timeout=args.timeout)
        if not isinstance(result, dict) or type(result.get("ok")) is not bool:
            raise ValueError("mailbox operation returned an invalid receipt")
        if result["ok"] and action != "get" and (
                result.get("request_key") != key or result.get("draft_id") != args.draft_id
                or result.get("effect_certainty") != "verified"
                or result.get("state") != {"send": "sent", "trash": "trashed"}[action]
                or action == "send" and not result.get("message_id")):
            raise ValueError("mailbox operation returned an incomplete receipt")
    except Exception as exc:
        result = {"ok": False, "cause": str(exc), "draft_id": args.draft_id,
                  "request_key": key, "effect_certainty": "unknown" if attempted else "not-dispatched"}
    return _report(settings, command, result)


@_preparation_scope
@observe("generation", success="result", effect="unknown")
def prepare(settings, args):
    from . import task_assignment
    mode = getattr(args, "reply_mode", "draft")
    command = "reply-send" if mode == "send" else "draft-reply"
    root = args.thread_id
    key = _key(args, mode, root)
    attempted = False
    try:
        headless = scheduled()
        if mode == "send" and (not headless or settings.cs_triage_mode.lower() != "send"
                or os.environ.get("CS_HEADLESS_SEND") != "1" or settings.pause_path.exists()):
            raise ValueError("scheduled send authority required")
        if headless and settings.cs_triage_mode.lower() != mode:
            raise ValueError("scheduled launcher mode disagrees with reply operation")
        if not root or normalize_key(root) != root:
            raise ValueError("exact RFC thread is required")
        source_id = getattr(args, "source_id", None)
        recovery = False
        bound = None
        if not headless:
            bound = _bound_source(settings, key, mode, root)
            if bound and source_id and source_id != bound:
                raise ValueError("request key already bound to another source")
        try:
            if headless:
                task_assignment.guard(settings, root)
            if not headless or not source_id:
                source_id = source(settings, root, source_id or bound, args.timeout)["id"]
        except Exception:
            if not bound and not (source_id and getattr(args, "operation_id", None)):
                raise
            source_id = source_id or bound
            recovery = True
        _require(settings, "mailbox_reply", args.timeout)
        if str(UUID(source_id)) != source_id:
            raise ValueError("exact source email ID required")
        params = {"thread_key": root, "source_email_id": source_id, "request_key": key, "mode": mode}
        if recovery:
            params["recover_only"] = True
        elif not headless:
            _bound_source(settings, key, mode, root, source_id)
        if args.message:
            params["request_text"] = args.message
        if headless:
            params.update(operator_origin="scheduled_operator", operator_origin_version=1)
        print(f"Reply request key {key}", file=sys.stderr)
        attempted = not recovery
        result = rpc.call_sync(settings, "drafts.compose_reply", params, timeout=args.timeout)
        if not isinstance(result, dict) or type(result.get("ok")) is not bool or result.get("request_key") != key:
            raise ValueError("reply operation returned an invalid receipt")
        if result["ok"]:
            if result.get("state") in ("draft_exists", "answered") and headless:
                pass
            elif result.get("state") == "needs_review":
                pass
            elif mode == "send":
                if result.get("state") != "sent" or result.get("effect_certainty") != "verified" or not result.get("message_id"):
                    raise ValueError("direct send lacks a confirmed Sent receipt")
            elif result.get("state") != "completed" or not result.get("draft_id") or result.get("current_draft", {}).get("exists") is not True:
                raise ValueError("prepared mailbox draft is no longer available")
        result = {k: result[k] for k in ("ok", "state", "cause", "operation_id", "request_key",
                  "draft_id", "message_id", "effect_certainty", "current_draft", "review") if k in result}
        result.update(thread_key=root, source_email_id=source_id, mode=mode)
    except Exception as exc:
        result = {"ok": False, "cause": str(exc), "request_key": key,
                  "effect_certainty": "unknown" if attempted else "not-dispatched"}
    if result.get("ok") and result.get("state") == "completed":
        prepared = _source_decision("draft_preparation", "review_prepared", outcome="accepted", generation_started=True)
        emit(settings, "generation", "result", reason="none", effect_certainty="verified",
             root_id=root, method="draft.prepare", causal=prepared)
    return _report(settings, command, result, root)
