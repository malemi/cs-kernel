"""Only signed fixed operational summaries leave the diagnostic trust boundary."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re

from .monitor_notify_config import NotifyConfig
from .monitor_details import safe_detail

CAUSES = frozenset(
    ("monitor-absent", "monitor-scan-stale", "primary-alert-unconfirmed", "monitor-degraded")
)
INCIDENT_CAUSES = frozenset(
    (
        "coverage",
        "stale-observation",
        "missing-launch",
        "stalled-stage",
        "overdue-work",
        "unresolved-expectation",
        "engine-liveness-unconfirmed",
        "operation-failure",
        "alert-delivery-unconfirmed",
        "watchdog-unavailable",
    )
)


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def summary(config: NotifyConfig, payload: dict) -> dict:
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or type(payload.get("schema_version")) is not int
        or payload.get("monitor_id") != config.monitor_id
        or payload.get("owner_uid") != config.owner_uid
    ):
        raise ValueError("Notification binding refused")
    if "causes" in payload:
        if set(payload) - {
            "schema_version",
            "monitor_id",
            "owner_uid",
            "causes",
            "last_received_at",
            "action",
        }:
            raise ValueError("Invalid watchdog summary")
        causes = payload["causes"]
        if (
            not isinstance(causes, list)
            or not 1 <= len(causes) <= 4
            or any(c not in CAUSES for c in causes)
        ):
            raise ValueError("Invalid watchdog causes")
        when = payload.get("last_received_at")
        if when is not None and (
            type(when) not in (int, float) or not math.isfinite(when) or when < 0
        ):
            raise ValueError("Invalid receipt time")
        identity = {"kind": "watchdog", "causes": sorted(set(causes)), "last_received_at": when}
        count = len(causes)
    else:
        if set(payload) - {
            "schema_version",
            "monitor_id",
            "owner_uid",
            "incident_count",
            "total_open_incidents",
            "groups",
            "incidents",
            "omitted_detail_count",
            "diagnostic_action",
        }:
            raise ValueError("Invalid incident summary")
        count = payload.get("incident_count")
        if type(count) is not int or not 1 <= count <= 200:
            raise ValueError("Invalid incident count")
        incidents = payload.get("incidents")
        if not isinstance(incidents, list) or not 1 <= len(incidents) <= 64:
            raise ValueError("Invalid incident references")
        references = []
        for row in incidents:
            if not isinstance(row, dict) or set(row) != {
                "id",
                "revision",
                "component",
                "cause",
                "first",
                "last",
                "detail",
            }:
                raise ValueError("Invalid incident reference")
            if (
                not isinstance(row["id"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", row["id"])
                or type(row["revision"]) is not int
                or row["revision"] < 1
            ):
                raise ValueError("Invalid incident identity")
            if (
                row["cause"] not in INCIDENT_CAUSES
                or not isinstance(row["component"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", row["component"])
            ):
                raise ValueError("Invalid incident cause")
            safe_detail(row["detail"])
            for key in ("first", "last"):
                if (
                    type(row[key]) not in (int, float)
                    or not math.isfinite(row[key])
                    or row[key] < 0
                ):
                    raise ValueError("Invalid incident time")
            references.append([row["id"], row["revision"]])
        identity = {"kind": "incident", "references": sorted(references), "count": count}
    fingerprint = hashlib.sha256(canonical({"monitor": config.monitor_id, **identity})).hexdigest()
    return {
        "kind": identity["kind"],
        "count": count,
        "fingerprint": fingerprint,
        "reference": references[0][0] if identity["kind"] == "incident" else fingerprint,
    }


def signed(config: NotifyConfig, item: dict, nonce: str) -> dict:
    body = {
        "v": 1,
        "monitor": config.monitor_id,
        "kind": item["kind"],
        "count": item["count"],
        "nonce": nonce,
        "reference": item["reference"],
    }
    body["signature"] = hmac.new(
        config.credential(config.signing_key_env).encode(), canonical(body), hashlib.sha256
    ).hexdigest()
    return body


def verified(config: NotifyConfig, body: object) -> dict:
    if not isinstance(body, dict) or set(body) != {
        "v",
        "monitor",
        "kind",
        "count",
        "nonce",
        "reference",
        "signature",
    }:
        raise ValueError("Invalid signed notification")
    if (
        type(body["v"]) is not int
        or body["v"] != 1
        or body["monitor"] != config.monitor_id
        or body["kind"] not in {"incident", "watchdog"}
        or type(body["count"]) is not int
        or not 1 <= body["count"] <= 200
        or not isinstance(body["nonce"], str)
        or not re.fullmatch(r"[a-f0-9]{32}", body["nonce"])
        or not isinstance(body["reference"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", body["reference"])
    ):
        raise ValueError("Invalid notification summary")
    original = dict(body)
    signature = original.pop("signature")
    expected = hmac.new(
        config.credential(config.signing_key_env).encode(), canonical(original), hashlib.sha256
    ).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        raise ValueError("Notification signature refused")
    return original
