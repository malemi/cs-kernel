"""Independent evidence-only monitor. It never runs mailbox or model operations."""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from .monitor_config import Component, MonitorConfig
from .monitor_evaluate import evaluate, initial_state, observe
from .monitor_process import bounded
from .monitor_store import MonitorStore
from .monitor_transport import post
from .observability import EventStore


def _read_component(component: Component, owner: str, cursor: str | None) -> dict:
    """One observational page, in an expendable deadline-bound subprocess."""
    if component.reader:
        from .logs_cli import reader_read

        binding = SimpleNamespace(
            reader_url=component.reader.url, reader_token_env=component.reader.token_env
        )
        settings = SimpleNamespace(
            observability=binding, engine_owner_uid=owner, _connection_env_files=()
        )
        return reader_read(settings, "events", {"cursor": cursor, "limit": 200})
    store = EventStore(component.local_root, owner, component.kind)
    maintenance = store.prune()
    if component.legacy_state_dir:
        from .observability_retention import prune_for_state

        legacy = prune_for_state(Path(component.legacy_state_dir), owner_uid=owner)
        maintenance["complete"] = maintenance.get("complete", False) and legacy.get(
            "complete", False
        )
    page = store.events(cursor=cursor, limit=200)
    if not maintenance.get("complete", False):
        page["coverage"]["status"] = "degraded"
        page["coverage"]["gaps"].append({"reason": "unreadable"})
    if component.kind == "kernel" and component.legacy_state_dir:
        # Existing owner notices remain owned by their original sender. Only the
        # queue length is observed; provider/account details never leave the file.
        from .observability_store import _check, _open
        import os

        path = Path(component.legacy_state_dir) / "operator-route-notices.json"
        if path.exists() or path.is_symlink():
            try:
                _check(path)
                fd = _open(path, os.O_RDONLY)
                with os.fdopen(fd, "rb") as stream:
                    raw = stream.read(65537)
                data = json.loads(raw) if len(raw) <= 65536 else None
                if not isinstance(data, dict) or not isinstance(data.get("pending"), list):
                    raise ValueError("Unreadable legacy notice state")
                page["notice_pending_count"] = len(data["pending"])
            except Exception:
                page["coverage"]["status"] = "degraded"
                page["coverage"]["gaps"].append({"reason": "unreadable"})
    return page


def _impact(detail: dict) -> str:
    # Timestamps and event IDs changing on every occurrence are not new impact.
    keys = {
        key: value
        for key, value in detail.items()
        if key
        not in {
            "at",
            "last",
            "first",
            "last_progress",
            "event_id",
            "expected_at",
            "trace_id",
            "span_id",
        }
    }
    return hashlib.sha256(json.dumps(keys, sort_keys=True).encode()).hexdigest()


def _sync(
    store: MonitorStore, component: str, findings: list[dict], now: float, *, allow_recovery: bool
) -> None:
    with store.connect() as db:
        current = {
            row[0]
            for row in db.execute(
                "SELECT id FROM incidents WHERE component=? AND active=1", (component,)
            )
        }
        wanted = set()
        for finding in findings:
            identity = finding["id"]
            wanted.add(identity)
            detail = json.dumps(finding["detail"], allow_nan=False, separators=(",", ":"))
            previous = db.execute(
                "SELECT detail,revision,active FROM incidents WHERE id=?", (identity,)
            ).fetchone()
            if previous is None:
                db.execute(
                    "INSERT INTO incidents(id,component,cause,first,last,active,revision,detail) "
                    "VALUES (?,?,?,?,?,1,1,?)",
                    (identity, component, finding["cause"], now, now, detail),
                )
            else:
                changed = (
                    _impact(json.loads(previous[0])) != _impact(finding["detail"])
                    or not previous[2]
                )
                db.execute(
                    "UPDATE incidents SET last=?,active=1,revision=?,detail=?,"
                    "acknowledged=CASE WHEN ? THEN 0 ELSE acknowledged END,"
                    "sends=CASE WHEN ? THEN 0 ELSE sends END,"
                    "last_sent=CASE WHEN ? THEN 0 ELSE last_sent END WHERE id=?",
                    (now, previous[1] + int(changed), detail, changed, changed, changed, identity),
                )
        if allow_recovery:
            for identity in current - wanted:
                db.execute("UPDATE incidents SET active=0,last=? WHERE id=?", (now, identity))


def _deliver(config: MonitorConfig, store: MonitorStore, now: float, sender=post) -> bool:
    """One bounded actionable batch; durable admission prevents revision retry loops."""
    if config.mode == "filesystem":
        from .operational_inbox import publish

        try:
            publish(store, clone_label=config.clone_label, now=now)
        except Exception as exc:
            from .monitor_process import safe_failure

            store.set("inbox_write_failure", safe_failure(exc))
            return False
        store.set("inbox_write_failure", None)
        with store.connect() as db:
            db.execute("UPDATE incidents SET accepted_revision=revision WHERE active=1")
        return True
    pending = store.incidents(active_only=True, due_at=now)
    if not pending:
        return store.counts()["unconfirmed"] == 0
    if config.alert is None:
        return False
    admitted = []
    day = int(now // 86400)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        for incident in pending:
            row = db.execute(
                "SELECT attempts FROM alerts WHERE day=? AND incident=?", (day, incident["id"])
            ).fetchone()
            attempts = row[0] if row else 0
            if attempts >= 3:
                continue
            db.execute(
                "INSERT OR REPLACE INTO alerts VALUES (?,?,?)", (day, incident["id"], attempts + 1)
            )
            db.execute(
                "UPDATE incidents SET sends=sends+1,last_sent=? WHERE id=?", (now, incident["id"])
            )
            admitted.append(incident)
    if not admitted:
        return store.counts()["unconfirmed"] == 0
    groups = {}
    for incident in admitted:
        key = incident["component"] + ":" + incident["cause"]
        groups[key] = groups.get(key, 0) + 1
    payload = {
        "schema_version": 1,
        "monitor_id": config.monitor_id,
        "owner_uid": config.owner_uid,
        "incident_count": len(admitted),
        "total_open_incidents": store.counts()["active"],
        "groups": groups,
        "incidents": [
            {
                key: incident[key]
                for key in ("id", "revision", "component", "cause", "first", "last", "detail")
            }
            for incident in admitted[:64]
        ],
        "omitted_detail_count": max(0, len(admitted) - 64),
        "diagnostic_action": "Inspect cs logs trace and current provider evidence; do not resend uncertain work",
    }
    try:
        if sender(config.alert, payload).get("accepted") is not True:
            raise ValueError("Alert unacknowledged")
        with store.connect() as db:
            for incident in admitted:
                db.execute(
                    "UPDATE incidents SET accepted_revision=? WHERE id=?",
                    (incident["revision"], incident["id"]),
                )
    except Exception as exc:
        from .monitor_process import safe_failure

        store.set("alert_transport_failure", safe_failure(exc))
        return False
    return store.counts()["unconfirmed"] == 0


def _scan(config: MonitorConfig, *, now: float | None = None, reader=None, sender=post) -> dict:
    """Observe a finite page per component, preserving cursors and source event IDs."""
    now = time.time() if now is None else now
    store = MonitorStore(config.state_dir, config.owner_uid)
    store.prune(now)
    cursors = {component.id: store.get("cursor:" + component.id) for component in config.components}
    rows = {}

    started = time.monotonic()
    deadline = started + 120
    read_deadline = started + 30
    components = config.components
    if config.mode == "filesystem":
        first = store.get("component_start", 0) % len(components)
        components = components[first:] + components[:first]
        store.set("component_start", (first + 1) % len(components))

    def read(component):
        cursor = cursors[component.id]
        collected = []
        checkpoints = []
        gaps = []
        page_count = 0
        last = {}
        limit = 20 if config.mode == "filesystem" else 1
        while page_count < limit and time.monotonic() < read_deadline:
            try:
                if reader:
                    page = reader(component, config.owner_uid, cursor)
                else:
                    page = bounded("read", (component, config.owner_uid, cursor),
                                   seconds=min(3, max(0.05, read_deadline - time.monotonic())))
                if not isinstance(page, dict) or not isinstance(page.get("events"), list):
                    raise ValueError("Invalid observation page")
                last = page
                page_count += 1
                collected.extend(page["events"])
                health = page.get("coverage", {})
                gaps.extend(health.get("gaps", []))
                next_cursor = page.get("next_cursor")
                checkpoints.append((len(collected), next_cursor))
                if not health.get("continuation_required"):
                    break
                if not next_cursor or next_cursor == cursor:
                    raise ValueError("Observation cursor made no progress")
                cursor = next_cursor
            except Exception as exc:
                from .monitor_process import safe_failure

                last = {
                    "events": [], "next_cursor": cursor,
                    "coverage": {
                        "available": False, "status": "unavailable",
                        "gaps": [{"reason": "unreadable"}],
                    },
                    "observer_failure": safe_failure(exc),
                }
                gaps.extend(last["coverage"]["gaps"])
                break
        if not last:
            last = {"events": [], "next_cursor": cursor,
                    "coverage": {"available": False, "status": "unavailable",
                                 "continuation_required": True,
                                 "gaps": [{"reason": "collector-lag"}]}}
        last["events"] = collected
        last["checkpoints"] = checkpoints
        last["coverage"]["gaps"] = list({json.dumps(g, sort_keys=True): g for g in gaps}.values())
        last["pages_read"] = page_count
        return last

    with ThreadPoolExecutor(max_workers=min(8, len(config.components))) as pool:
        pages = list(pool.map(read, components))
    for component, page in zip(components, pages):
        from .observability_store import _validate_event

        state = store.get("state:" + component.id, initial_state())
        health = page.get("coverage", {})
        paused = bool(
            component.schedule
            and component.schedule.pause_marker
            and Path(component.schedule.pause_marker).is_file()
        )
        valid = True
        checkpoints = dict(page["checkpoints"])
        if checkpoints.get(0):
            store.set("cursor:" + component.id, checkpoints[0])
        for index, event in enumerate(page.get("events", []), start=1):
            if time.monotonic() >= deadline:
                health = {**health, "continuation_required": True}
                break
            if (
                not _validate_event(event, SimpleNamespace(owner_uid=config.owner_uid))
                or event["component"] != component.kind
            ):
                valid = False
            elif store.remember(component.id, event, now):
                observe(state, event, now)
            if checkpoints.get(index):
                store.set("state:" + component.id, state)
                store.set("cursor:" + component.id, checkpoints[index])
        if not valid:
            health = {
                "available": False,
                "status": "degraded",
                "gaps": [{"reason": "malformed-event"}],
            }
        if page.get("next_cursor") and health.get("continuation_required"):
            state["gaps"] = sorted(set(state["gaps"] + ["collector-lag"]))
        elif "collector-lag" in state["gaps"]:
            state["gaps"].remove("collector-lag")
        findings = evaluate(component, state, health, now, paused=paused)
        if page.get("observer_failure"):
            for finding in findings:
                if finding["cause"] == "coverage":
                    finding["detail"].update(page["observer_failure"])
        if type(page.get("notice_pending_count")) is int and page["notice_pending_count"] > 0:
            identity = hashlib.sha256((component.id + ":legacy-notices").encode()).hexdigest()
            findings.append(
                {
                    "id": identity,
                    "component": component.id,
                    "cause": "alert-delivery-unconfirmed",
                    "detail": {
                        "stage": "alert",
                        "reason": "unknown",
                        "pending_count": page["notice_pending_count"],
                    },
                }
            )
        complete = (
            valid and health.get("available", False) and not health.get("continuation_required")
        )
        _sync(
            store,
            component.id,
            findings,
            now,
            allow_recovery=complete
            and not paused
            and not (component.schedule and component.schedule.disabled),
        )
        store.set("state:" + component.id, state)
        rows[component.id] = {
            "coverage": health,
            "paused": paused,
            "disabled": bool(component.schedule and component.schedule.disabled),
            "open_incidents": len(findings),
            "pages_read": page.get("pages_read", 1),
        }
    # Enforce copy limits on this scan's new records before exposing/mirroring them.
    store.prune(now)
    delivered = _deliver(config, store, now, sender)
    incidents = store.counts()["active"]
    result = {
        "schema_version": 1,
        "monitor_id": config.monitor_id,
        "owner_uid": config.owner_uid,
        "scan_at": now,
        "sequence": store.next_sequence(),
        "components": rows,
        "status": "degraded" if incidents or not delivered or (config.mode == "transport" and config.alert is None) else "observed",
        "alert_delivery_ok": delivered,
        "open_incidents": incidents,
        "observer_eviction_at": store.get("observer_eviction"),
        "analyst": "manual-only" if config.mode == "filesystem" else "disabled-no-priced-route",
        "mode": config.mode,
        "problems_path": str(Path(config.state_dir) / "problems.json"),
        "investigations_path": str(Path(config.state_dir) / "investigations"),
        "alert_configured": config.alert is not None,
        "inbox_write_failure": store.get("inbox_write_failure"),
    }
    store.set("last_scan", result)
    if config.watchdog and config.mode != "filesystem":
        heartbeat = {
            key: result[key]
            for key in (
                "schema_version",
                "monitor_id",
                "owner_uid",
                "sequence",
                "scan_at",
                "status",
                "alert_delivery_ok",
                "open_incidents",
            )
        }
        heartbeat["events"] = []
        mirror_cursor = store.get("mirror_seq", 0)
        mirror = store.mirror_page(mirror_cursor)
        last_copied = mirror_cursor
        # Drain originals in durable order instead of repeatedly copying a tail.
        for sequence, event in mirror["rows"]:
            candidate = heartbeat["events"] + [event]
            if len(json.dumps({**heartbeat, "events": candidate}).encode()) > 240000:
                break
            heartbeat["events"] = candidate
            last_copied = sequence
        heartbeat["copy_truncated"] = mirror["pending"] > len(heartbeat["events"])
        heartbeat["copy_gap"] = mirror["gap"] or store.get("mirror_gap", False)
        if heartbeat["copy_gap"]:
            store.set("mirror_gap", True)
            heartbeat["status"] = result["status"] = "degraded"
        try:
            if sender(config.watchdog, heartbeat).get("accepted") is not True:
                raise ValueError("Watchdog unacknowledged")
            store.set("watchdog_delivery", {"accepted": True, "at": now})
            store.set("mirror_seq", last_copied)
            store.set(
                "mirroring",
                {
                    "pending": mirror["pending"] - len(heartbeat["events"]),
                    "gap": heartbeat["copy_gap"],
                    "at": now,
                },
            )
            _sync(store, "observer", [], now, allow_recovery=True)
            result["open_incidents"] = store.counts()["active"]
            if (
                not result["open_incidents"]
                and delivered
                and config.alert is not None
                and not heartbeat["copy_gap"]
            ):
                result["status"] = "observed"
        except Exception as exc:
            from .monitor_process import safe_failure

            result["status"] = "degraded"
            result["watchdog_delivery"] = "unconfirmed"
            store.set("watchdog_delivery", {"accepted": False, "at": now})
            store.set("last_scan", result)
            identity = hashlib.sha256(b"observer:watchdog-unavailable").hexdigest()
            _sync(
                store,
                "observer",
                [
                    {
                        "id": identity,
                        "component": "observer",
                        "cause": "watchdog-unavailable",
                        "detail": {"stage": "monitor", **safe_failure(exc)},
                    }
                ],
                now,
                allow_recovery=False,
            )
            result["alert_delivery_ok"] = _deliver(config, store, now, sender)
            result["open_incidents"] = store.counts()["active"]
            store.set("last_scan", result)
    elif config.mode != "filesystem":
        result["status"] = "degraded"
        result["watchdog_delivery"] = "not-configured"
        store.set("last_scan", result)
    store.set("last_scan", result)
    return result


def run(config: MonitorConfig, *, stop=None) -> None:
    """A separate service loop; storage failure stops heartbeats for watchdog detection."""
    while stop is None or not stop.is_set():
        started = time.monotonic()
        scan(config)
        remaining = max(0, config.scan_seconds - (time.monotonic() - started))
        if stop is not None:
            stop.wait(remaining)
        else:
            time.sleep(remaining)


def scan(config: MonitorConfig, *, now: float | None = None, reader=None, sender=post) -> dict:
    """Only one scanner may reserve notifications for a selected observer store."""
    import fcntl
    import os
    from .observability_store import _open

    store = MonitorStore(config.state_dir, config.owner_uid)
    fd = _open(store.root / ".monitor.lock", os.O_RDWR | os.O_CREAT)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "degraded", "reason": "monitor-already-running"}
        return _scan(config, now=now, reader=reader, sender=sender)
    finally:
        os.close(fd)
