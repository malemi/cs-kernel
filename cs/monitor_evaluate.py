"""Deterministic observation of missing execution, failed effects and overdue work."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .monitor_config import Component, Schedule


def timestamp(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


def _field(text: str, value: int, low: int, high: int) -> bool:
    matched = False
    for item in text.split(","):
        base, _, step_text = item.partition("/")
        step = int(step_text) if step_text else 1
        if not 1 <= step <= high - low + 1:
            raise ValueError("Invalid schedule step")
        if base == "*":
            first, last = low, high
        elif "-" in base:
            first, last = map(int, base.split("-", 1))
        else:
            first = last = int(base)
        if not low <= first <= last <= high:
            raise ValueError("Invalid schedule range")
        matched |= first <= value <= last and (value - first) % step == 0
    return matched


def last_due(schedule: Schedule, now: float) -> float | None:
    """Find an independently configured due launch; never infer it from activity."""
    if schedule.disabled or now < schedule.anchor_utc:
        return None
    if not schedule.cron:
        return (
            schedule.anchor_utc
            + int((now - schedule.anchor_utc) // schedule.every_seconds) * schedule.every_seconds
        )
    minute, hour, day, month, weekday = schedule.cron.split()
    zone = ZoneInfo(schedule.timezone)
    end = int(now // 60) * 60
    start = max(schedule.anchor_utc, end - 31 * 86400)
    for candidate in range(end, int(start) - 1, -60):
        local = datetime.fromtimestamp(candidate, timezone.utc).astimezone(zone)
        dom, dow = _field(day, local.day, 1, 31), _field(weekday, local.isoweekday() % 7, 0, 7)
        if local.isoweekday() == 7:
            dow |= _field(weekday, 7, 0, 7)
        days = (dom or dow) if day != "*" and weekday != "*" else dom and dow
        if (
            _field(minute, local.minute, 0, 59)
            and _field(hour, local.hour, 0, 23)
            and _field(month, local.month, 1, 12)
            and days
        ):
            return float(candidate)
    return None


def next_due(schedule: Schedule, after: float) -> float:
    """The next eligible configured tick, including overnight/weekend gaps."""
    if not schedule.cron:
        if after < schedule.anchor_utc:
            return float(schedule.anchor_utc)
        return float(
            schedule.anchor_utc
            + (int((after - schedule.anchor_utc) // schedule.every_seconds) + 1)
            * schedule.every_seconds
        )
    minute, hour, day, month, weekday = schedule.cron.split()
    zone = ZoneInfo(schedule.timezone)
    start = max(int(after // 60) * 60 + 60, schedule.anchor_utc)
    for candidate in range(start, start + 31 * 86400, 60):
        local = datetime.fromtimestamp(candidate, timezone.utc).astimezone(zone)
        dom = _field(day, local.day, 1, 31)
        dow = _field(weekday, local.isoweekday() % 7, 0, 7) or (
            local.isoweekday() == 7 and _field(weekday, 7, 0, 7)
        )
        days = (dom or dow) if day != "*" and weekday != "*" else dom and dow
        if (
            days
            and _field(minute, local.minute, 0, 59)
            and _field(hour, local.hour, 0, 23)
            and _field(month, local.month, 1, 12)
        ):
            return float(candidate)
    raise ValueError("No eligible tick inside the bounded schedule horizon")


def initial_state() -> dict:
    return {
        "last_event": None,
        "last_launch": None,
        "spans": {},
        "work": {},
        "failures": {},
        "gaps": [],
        "service": None,
    }


def operation_identity(event: dict, *, uncertain: bool = False) -> str:
    for key in ("operation_id", "provider_id", "draft_id", "job_id"):
        if event.get(key):
            return key + ":" + event[key]
    if event.get("root_id") and event.get("request_revision") and not uncertain:
        return "root:" + event["root_id"] + ":" + event["request_revision"]
    if uncertain:
        return "attempt:" + event["trace_id"] + ":" + event["span_id"]
    if event["stage"] == "cli":
        command = event.get("command")
        if command and command != "unknown":
            return "command:" + command
        return "attempt:" + event["trace_id"] + ":" + event["span_id"]
    return "root:" + event["root_id"] if event.get("root_id") else "service"



def same_cause_scope(previous: dict, event: dict) -> bool:
    if previous.get("operation_id") or event.get("operation_id"):
        return all(previous.get(key) and previous[key] == event.get(key) for key in ("operation_id", "draft_id", "root_id", "request_revision"))
    old_refs = previous.get("causal", {}).get("refs", {})
    new_refs = event.get("causal", {}).get("refs", {})
    for key in ("attempt_id", "run_id"):
        if old_refs.get(key) or new_refs.get(key):
            if not old_refs.get(key) or old_refs[key] != new_refs.get(key):
                return False
    return bool(previous.get("trace_id") and previous["trace_id"] == event.get("trace_id"))


def verified_exact_delivery(event: dict) -> bool:
    cause = event.get("causal", {})
    return (event.get("command") == "draft-send"
        and event.get("effect_certainty") in {"verified", "recipient-received"}
        and event.get("status") == "delivered-cleanup-incomplete"
        and cause.get("layer") == "exact_draft"
        and cause.get("check") == "exact_draft_operation"
        and cause.get("cause") == "sent_verified_cleanup_pending"
        and cause.get("outcome") == "accepted"
        and cause.get("evidence_complete") is True
        and cause.get("facts", {}).get("sent_verified") is True
        and event.get("achieved_stages") == ["engine-saved", "sent"])

def matching_evidence(previous: dict, event: dict, *, verified: bool) -> bool:
    if previous.get("causal", {}).get("layer") == "exact_draft":
        new = event.get("causal", {})
        if not verified or new.get("layer") != "exact_draft" or new.get("outcome") != "accepted":
            return False
        if previous.get("operation_id") and not same_cause_scope(previous, event):
            return False
    elif previous.get("causal"):
        old, new = previous['causal'], event.get('causal')
        if not new or new['check'] != 'supervisor_completion' or new['cause'] != 'run_verified' or new['outcome'] != 'accepted':
            return False
        if event.get('method') != 'operator.tick' or any(not new['refs'][key] or new['refs'][key] != event.get(key) for key in ('run_id', 'attempt_id')):
            return False
    if previous["stage"] == "cli" and event["stage"] == "cli":
        command = previous.get("command")
        if command and command != "unknown":
            if event.get("command") != command:
                return False
        elif (previous["trace_id"], previous["span_id"]) != (event["trace_id"], event["span_id"]):
            return False
    if (
        previous.get("request_revision")
        and event.get("request_revision")
        and previous["request_revision"] != event["request_revision"]
    ):
        return False
    if previous.get("uncertain") and not verified:
        return False
    for key in ("operation_id", "provider_id", "draft_id", "job_id"):
        if previous.get(key):
            return previous[key] == event.get(key)
    if previous.get("uncertain"):
        return previous["trace_id"] == event["trace_id"] and previous["span_id"] == event["span_id"]
    if previous.get("root_id"):
        return previous["root_id"] == event.get("root_id") and previous.get(
            "request_revision"
        ) == event.get("request_revision")
    return True  # A non-effect service symptom; not proof of a business completion.


def observe(state: dict, event: dict, now: float) -> None:
    """Consume one validated original event; only evidenced recovery clears faults."""
    when = timestamp(event["timestamp"])
    if when > now + 60:
        state["gaps"] = ["clock-skew"]
        return
    state["last_event"] = max(state.get("last_event") or when, when)
    stage, status = event["stage"], event["status"]
    span_key = stage + ":" + event["span_id"]
    method = event.get("method")
    long_lived = method in {"engine.ws", "engine.stdio", "engine.connection"}
    if method == "engine.heartbeat" and status == "running":
        state["service"] = {"at": when, "running": True, "event_id": event["event_id"]}
    elif method in {"engine.ws", "engine.stdio"}:
        state["service"] = {"at": when, "running": status == "start", "event_id": event["event_id"]}
    if stage == "launch" and status == "start":
        state["last_launch"] = max(state.get("last_launch") or when, when)
    if status == "start" and not long_lived:
        state["spans"][span_key] = {
            "at": when,
            "stage": stage,
            "event_id": event["event_id"],
            "trace_id": event["trace_id"],
            "deadline": event.get("deadline_seconds"),
        }
    elif status in {
        "result",
        "completed",
        "failed",
        "cancelled",
        "accepted",
        "verified",
        "unknown-effect",
        "delivered-cleanup-incomplete",
        "held",
        "deferred",
        "not-attempted",
        "paused",
        "disabled",
        "lock-skipped",
        "unknown",
    }:
        state["spans"].pop(span_key, None)
    root, revision = event.get("root_id"), event.get("request_revision")
    work_key = root + ":" + revision if root and revision else None
    if stage == "selection" and work_key:
        prior = state["work"].get(work_key, {"first": when})
        prior.update(
            {
                "last": when,
                "event_id": event["event_id"],
                "root_id": root,
                "request_revision": revision,
                "expected_action": event.get("expected_action", "unknown"),
                "trace_id": event["trace_id"],
                "deferred": status == "deferred",
                "held": status == "held" and event["reason"] == "policy-hold",
            }
        )
        state["work"][work_key] = prior
    if root and event["reason"] == "policy-hold":
        for work in state["work"].values():
            if work["root_id"] == root:
                work["held"] = True
    verified = event["effect_certainty"] in {"verified", "recipient-received"}
    if stage in {"provider", "verification"} and verified and work_key:
        state["work"].pop(work_key, None)
    from .observability import event_level

    level = event_level(event)
    severity_failure = level in {"ERROR", "CRITICAL"} and status not in {
        "held", "deferred", "paused", "disabled", "lock-skipped", "not-attempted"
    } and event["reason"] != "policy-hold"
    failed = severity_failure or status in {
        "failed",
        "unknown",
        "unknown-effect",
        "delivered-cleanup-incomplete",
        "cancelled",
    }
    uncertain = status == "unknown-effect" or (
        (stage in {"provider", "persistence", "verification", "cleanup"}
         or event.get("causal", {}).get("layer") == "exact_draft"
         or (stage == "cli" and event.get("command") in {"draft-send", "draft-reply", "draft-retire", "chat", "campaign"}))
        and failed and event["effect_certainty"] == "unknown"
    )
    failure_key = ":".join(
        (
            stage,
            event.get("method", "") + (":" + (event.get("command") or "unknown") if stage == "cli" else ""),
            operation_identity(event, uncertain=uncertain),
            "uncertain" if uncertain else "failure",
        )
    )
    if verified_exact_delivery(event):
        for key, previous in list(state["failures"].items()):
            if (previous.get("uncertain") and previous.get("command") == "draft-send"
                and when > previous["at"] and same_cause_scope(previous, event)
                and matching_evidence(previous, event, verified=True)):
                state["failures"].pop(key)
    if failed:
        previous = state["failures"].get(failure_key)
        retain = (previous is not None and same_cause_scope(previous, event)
            and previous.get("causal", {}).get("cause") not in (None, "unknown"))
        prior = {"first": previous["first"] if retain else when}
        prior.update(
            {
                "at": when,
                "stage": stage,
                "reason": event["reason"],
                "level": level,
                "event_id": event["event_id"],
                "root_id": root,
                "request_revision": revision,
                "effect_certainty": event["effect_certainty"],
                "trace_id": event["trace_id"],
                "span_id": event["span_id"],
                "uncertain": uncertain,
                **{
                    key: event[key] for key in ("operation_id", "provider_id", "draft_id", "job_id") if key in event
                },
                **{
                    key: event[key]
                    for key in ("error_class", "error_code", "error_file", "error_line", "method", "command", "causal", "achieved_stages")
                    if key in event
                },
            }
        )
        if retain:
            prior = {**previous, "at": when}
        state["failures"][failure_key] = prior
    elif status in {"result", "completed", "verified", "accepted"} and event["reason"] == "none":
        for key, prior in list(state["failures"].items()):
            same_stage = stage == prior["stage"] and event.get("method", "") == prior.get(
                "method", ""
            )
            bound_effect = prior.get("uncertain") or any(
                prior.get(identity) for identity in ("provider_id", "draft_id", "job_id", "root_id")
            )
            if (
                when > prior["at"]
                and (same_stage or (verified and bound_effect) or (prior.get('causal') and event.get('causal', {}).get('check') == 'supervisor_completion'))
                and matching_evidence(prior, event, verified=verified)
            ):
                state["failures"].pop(key, None)
    for collection in ("spans", "work", "failures"):
        if len(state[collection]) > 512:
            state["gaps"] = ["observer-capacity"]
            # Keep old work, whose age must not be hidden by newer arrivals.
            state[collection] = dict(list(state[collection].items())[:512])


def evaluate(
    component: Component, state: dict, health: dict, now: float, *, paused: bool = False
) -> list[dict]:
    """Return evidence-bearing findings. Pause suppresses new launch expectations only."""
    findings = []

    def add(cause: str, key: str, detail: dict):
        identity = hashlib.sha256((component.id + ":" + cause + ":" + key).encode()).hexdigest()
        findings.append(
            {"id": identity, "component": component.id, "cause": cause, "detail": detail}
        )

    gaps = health.get("gaps", [])
    bad_gaps = [
        g["reason"] for g in gaps if g.get("reason") not in {"retention", "retention-expired"}
    ]
    logging = None
    if "logging" in health:
        from .observability_logging import validate_logging

        try:
            logging = validate_logging(health["logging"])
        except ValueError:
            bad_gaps.append("malformed-event")
        if "logging" not in bad_gaps:
            bad_gaps.append("logging")
    intentionally_idle = paused or bool(component.schedule and component.schedule.disabled)
    absent = not health.get("available") or health.get("status") == "absent"
    if (
        (absent and not intentionally_idle)
        or health.get("status") in {"unavailable", "unsupported"}
        or bad_gaps
        or state["gaps"]
    ):
        historical_only = (
            logging is not None
            and logging["current_state"] == "recovered"
            and health.get("available") is True
            and health.get("status") in {"observed", "degraded"}
            and not (set(bad_gaps) - {"logging"})
            and not state["gaps"]
        )
        detail = {
            "stage": "monitor",
            "reason": "incomplete-input",
            "gaps": sorted(set(bad_gaps + state["gaps"]))[:16],
            "level": "WARNING" if historical_only else "ERROR",
        }
        if logging is not None:
            detail["logging"] = logging
        add("coverage", "coverage", detail)
    last = state.get("last_event")
    if (
        not intentionally_idle
        and (state["work"] or state["spans"])
        and last is not None
        and now - last > component.freshness_seconds
    ):
        add(
            "stale-observation",
            "freshness",
            {"stage": "monitor", "reason": "incomplete-input", "last_progress": last},
        )
    schedule = component.schedule
    if schedule and not schedule.disabled and not paused:
        due = last_due(schedule, now - schedule.grace_seconds)
        if due is not None and (state.get("last_launch") is None or state["last_launch"] < due):
            add(
                "missing-launch",
                "schedule",
                {"stage": "launch", "reason": "unknown", "expected_at": due},
            )
    if component.kind == "engine" and not intentionally_idle:
        service = state.get("service")
        if not service or not service["running"] or now > service["at"] + 300:
            add(
                "engine-liveness-unconfirmed",
                "service",
                {
                    "stage": "launch",
                    "reason": "incomplete-input",
                    "last_progress": service["at"] if service else None,
                },
            )
    for key, span in state["spans"].items():
        deadline = span.get("deadline") or component.stage_deadline_seconds
        # Leave a full 60-second scan phase plus bounded read/processing time
        # inside the five-minute detection limit.
        if now > span["at"] + deadline + 230:
            add("stalled-stage", key, {**span, "reason": "timeout"})
    for key, work in state["work"].items():
        deadline = work["first"] + component.work_deadline_seconds
        if schedule and work.get("deferred"):
            deadline = next_due(schedule, work["first"]) + component.work_deadline_seconds
        if not intentionally_idle and not work["held"] and now > deadline:
            unknown = work.get("expected_action") == "unknown"
            add(
                "unresolved-expectation" if unknown else "overdue-work",
                key,
                {
                    **work,
                    "stage": "selection",
                    "reason": "incomplete-input" if unknown else "unknown",
                },
            )
    for key, failure in state["failures"].items():
        add("operation-failure", key, failure)
    return findings
