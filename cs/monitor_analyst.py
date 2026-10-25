"""Optional evidence-only analyst admission. No priced adapter is enabled by default."""

from __future__ import annotations

import json
import math
import time

from .monitor_store import MonitorStore


def reserve(
    store: MonitorStore,
    incident_id: str,
    revision: int,
    maximum_usd: float,
    *,
    now: float | None = None,
) -> bool:
    """Reserve a verified adapter's maximum cost before invocation, including uncertainty."""
    import re

    now = time.time() if now is None else now
    if (
        not re.fullmatch(r"[a-f0-9]{64}", incident_id)
        or type(revision) is not int
        or revision < 1
        or type(maximum_usd) not in (int, float)
        or not math.isfinite(maximum_usd)
        or not 0 < maximum_usd <= 0.05
    ):
        raise ValueError("Analyst admission refused")
    day = int(now // 86400)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        spent = db.execute(
            "SELECT COALESCE(SUM(usd),0) FROM reservations WHERE day=?", (day,)
        ).fetchone()[0]
        if spent + maximum_usd > 1 + 1e-9:
            return False
        return bool(
            db.execute(
                "INSERT OR IGNORE INTO reservations VALUES (?,?,?,?)",
                (day, incident_id, revision, maximum_usd),
            ).rowcount
        )


def input_for(incident: dict, event_ids: list[str]) -> dict:
    """No customer bodies or arbitrary narratives may enter optional model input."""
    import re

    cause = incident.get("cause")
    if (
        not isinstance(incident.get("id"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", incident["id"])
        or type(incident.get("revision")) is not int
        or incident["revision"] < 1
    ):
        raise ValueError("Invalid analyst identity")
    if cause not in {
        "coverage",
        "stale-observation",
        "missing-launch",
        "stalled-stage",
        "overdue-work",
        "unresolved-expectation",
        "engine-liveness-unconfirmed",
        "operation-failure",
        "watchdog-unavailable",
    }:
        raise ValueError("Unknown analyst incident")
    ids = event_ids[:30]
    if not all(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value) for value in ids):
        raise ValueError("Invalid analyst references")
    payload = {
        "incident_id": incident["id"],
        "revision": incident["revision"],
        "cause": cause,
        "event_ids": ids,
        "instruction": "Explain evidenced failure or state unknown. Cite event IDs. Never propose automatic resend or grant authority.",
    }
    if len(json.dumps(payload).encode()) > 8192:
        raise ValueError("Analyst input limit")
    return payload
