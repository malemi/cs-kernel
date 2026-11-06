"""Safe incident evidence retained in alerts and read-only incident views."""

from __future__ import annotations

import math
import re

from .observability import CERTAINTY, REASONS, STAGES, diagnostic_id, safe_metadata


def safe_detail(value: dict) -> dict:
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("Invalid incident evidence")
    result = {}
    for key, item in value.items():
        if key in {"stage", "reason", "effect_certainty", "expected_action"}:
            allowed = {
                "stage": STAGES,
                "reason": REASONS,
                "effect_certainty": CERTAINTY,
                "expected_action": {"draft", "send", "review", "none", "unknown"},
            }[key]
            if not isinstance(item, str) or item not in allowed:
                raise ValueError("Invalid incident enum")
        elif key == "level":
            if item not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
                raise ValueError("Invalid incident level")
        elif key in {"event_id", "trace_id", "span_id"}:
            if diagnostic_id(item) != item:
                raise ValueError("Invalid incident reference")
        elif key in {"root_id", "request_revision", "draft_id", "provider_id", "job_id", "operation_id"}:
            if item is not None and (
                not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{64}", item)
            ):
                raise ValueError("Invalid incident root")
        elif key in {"at", "first", "last", "last_progress", "expected_at", "deadline"}:
            if item is not None and (
                type(item) not in {int, float} or not math.isfinite(item) or item < 0
            ):
                raise ValueError("Invalid incident time")
        elif key in {"held", "deferred", "uncertain"}:
            if type(item) is not bool:
                raise ValueError("Invalid incident state")
        elif key in {"pending_count", "error_code", "error_line"}:
            if type(item) is not int or not -(2**53) < item < 2**53:
                raise ValueError("Invalid incident count")
        elif key == "error_class":
            if not isinstance(item, str) or item not in {
                "TimeoutError",
                "PermissionError",
                "ConnectionError",
                "OSError",
                "ValueError",
                "RuntimeError",
                "CancelledError",
                "EngineError",
                "UnknownError",
                "HTTPError",
                "URLError",
                "SSLError",
                "ConnectionRefusedError",
            }:
                raise ValueError("Invalid incident error")
        elif key in {"error_file", "method", "command"}:
            if safe_metadata({key: item}).get(key) != item or item is None:
                raise ValueError("Invalid incident source")
        elif key == "achieved_stages":
            if safe_metadata({key: item}).get(key) != item:
                raise ValueError("Invalid achieved stages")
        elif key == "causal":
            from .observability_causal import validate
            validate(item)
        elif key == "logging":
            from .observability_logging import validate_logging

            validate_logging(item)
        elif key == "gaps":
            if (
                not isinstance(item, list)
                or len(item) > 16
                or not all(
                    isinstance(reason, str)
                    and reason
                    in {
                        "retention",
                        "retention-expired",
                        "cursor-evicted",
                        "cursor-truncated",
                        "malformed-event",
                        "unreadable",
                        "logging",
                        "response-limit",
                        "clock-skew",
                        "observer-capacity",
                        "collector-lag",
                    }
                    for reason in item
                )
            ):
                raise ValueError("Invalid incident coverage")
        else:
            raise ValueError("Unexpected incident evidence")
        result[key] = item
    return result
