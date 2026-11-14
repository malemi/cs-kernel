"""Owner-only diagnostic JSONL persistence, bounded rotation and paginated reads."""

from __future__ import annotations

import base64
import contextlib
import fcntl
import json
import hashlib
import os
import re
import stat
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Iterator

from .observability import (
    MAX_EVENT_BYTES,
    MAX_RESPONSE_BYTES,
    diagnostic_id,
    STAGES,
    STATUSES,
    REASONS,
    CERTAINTY,
    safe_metadata,
    LEVELS,
    event_level,
)


def _check(path: Path, *, directory: bool = False) -> os.stat_result:
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not expected(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
        or (not directory and info.st_nlink != 1)
    ):
        raise PermissionError("unsafe diagnostic path")
    return info


def _root(store: Any, create: bool = False) -> None:
    for ancestor in (store.root, *store.root.parents):
        if ancestor.is_symlink():
            raise PermissionError("symlink diagnostic parent")
    base = getattr(store, "namespace_base", None)
    if (
        base is None
        and store.root.parent.name == "observability"
        and re.fullmatch(r"owner-[a-f0-9]{64}", store.root.name)
    ):
        base = store.root.parent
    if base is not None:
        expected = "owner-" + hashlib.sha256(store.owner_uid.encode()).hexdigest()
        if store.root.parent != base or store.root.name != expected:
            raise PermissionError("diagnostic owner namespace differs")
        if create:
            base.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent = base.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid():
            raise PermissionError("unsafe diagnostic state parent")
        if create:
            base.mkdir(mode=0o700, exist_ok=True)
        _check(base, directory=True)
        if create:
            store.root.mkdir(mode=0o700, exist_ok=True)
    elif create:
        store.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _check(store.root, directory=True)


def _open(path: Path, flags: int, mode: int = 0o600) -> int:
    fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise PermissionError("unsafe diagnostic file")
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def _locked(store: Any, *, write: bool = False) -> Iterator[None]:
    _root(store, create=write)
    fd = _open(store.root / ".lock", os.O_RDWR | (os.O_CREAT if write else 0))
    started = time.monotonic()
    try:
        while True:
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() - started > 0.05:
                    raise TimeoutError("diagnostic lock unavailable")
                time.sleep(0.001)
        yield
    finally:
        os.close(fd)


def _segments(store: Any) -> list[Path]:
    files = sorted(store.root.glob("events-*.jsonl"))
    if len(files) > 1024:
        raise ValueError("diagnostic segment inventory exceeds bound")
    for path in files:
        if not re.fullmatch(r"events-[0-9]{20}\.jsonl", path.name):
            raise ValueError("unknown diagnostic segment")
        _check(path)
    return files


def _gap(store: Any, removed: int) -> None:
    path = store.root / "retention.json"
    previous = _retention_record(store)
    count = previous["evicted_segments"] if previous is not None else 0
    data = json.dumps(
        {"evicted_segments": count + removed, "last_eviction_at": time.time()}
    ).encode()
    fd = _open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


from .observability_logging import record_failure, before_append, after_append, add_coverage


def _segment_time(path: Path) -> float:
    return int(path.name[7:-6]) / 1_000_000_000


def _validate_event(event: Any, store: Any) -> bool:
    if (
        not isinstance(event, dict)
        or event.get("schema_version") != 1
        or event.get("owner_uid") != store.owner_uid
    ):
        return False
    if (
        event.get("component") not in {"kernel", "engine"}
        or event.get("stage") not in STAGES
        or event.get("status") not in STATUSES
        or event.get("reason") not in REASONS
        or event.get("effect_certainty") not in CERTAINTY
        or ('level' in event and (not isinstance(event['level'], str) or event['level'] not in LEVELS))
    ):
        return False
    base = {
        "schema_version",
        "event_id",
        "timestamp",
        "monotonic_ns",
        "sequence",
        "component",
        "owner_uid",
        "pid",
        "process_start",
        "trace_id",
        "span_id",
        "parent_span_id",
        "run_id",
        "attempt_id",
        "stage",
        "status",
        "reason",
        "effect_certainty",
        "version",
        "source_digest",
        "source_digest_scope",
        "level",
    }
    try:
        allowed = base | set(safe_metadata(event))
    except (ValueError, TypeError, KeyError):
        return False
    if "achieved_stages" in event and safe_metadata(event).get("achieved_stages") != event["achieved_stages"]:
        return False
    if set(event) - allowed:
        return False
    for name in ("event_id", "trace_id", "span_id"):
        if diagnostic_id(event.get(name)) is None:
            return False
    for name in ("parent_span_id", "run_id", "attempt_id"):
        if name in event and diagnostic_id(event[name]) is None:
            return False
    for name in ("monotonic_ns", "sequence", "pid"):
        if type(event.get(name)) is not int or event[name] < 0:
            return False
    if not isinstance(event.get("timestamp"), str) or len(event["timestamp"]) > 40:
        return False
    try:
        stamp = datetime.fromisoformat(event["timestamp"])
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            return False
    except (ValueError, TypeError):
        return False
    if event.get("process_start") is not None and (
        not isinstance(event["process_start"], str)
        or not re.fullmatch(r"[0-9]{1,32}", event["process_start"])
    ):
        return False
    for key in ("draft_id", "job_id", "root_id", "request_revision", "provider_id", "evidence_ref", "operation_id"):
        if key in event and (
            not isinstance(event[key], str) or not re.fullmatch(r"[a-f0-9]{64}", event[key])
        ):
            return False
    if not isinstance(event.get("version"), str) or not re.fullmatch(
        r"[a-zA-Z0-9.+_-]{1,80}", event["version"]
    ):
        return False
    if not isinstance(event.get("source_digest"), str) or not re.fullmatch(
        r"[a-f0-9]{64}", event["source_digest"]
    ):
        return False
    if event.get("source_digest_scope") != "observability-module":
        return False
    return True


def append(store: Any, event: dict) -> None:
    data = (json.dumps(event, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    if len(data) > MAX_EVENT_BYTES:
        raise ValueError("event exceeds byte limit")
    with _locked(store, write=True):
        logging_before = before_append(store)
        files = _segments(store)
        total = sum(path.stat().st_size for path in files)
        removed = 0
        now = time.time()
        while files and (
            total + len(data) > store.max_bytes
            or now - _segment_time(files[0]) > store.retention_seconds
        ):
            path = files.pop(0)
            total -= path.stat().st_size
            path.unlink()
            removed += 1
        if removed:
            _gap(store, removed)
        if files and files[-1].stat().st_size + len(data) <= store.segment_bytes:
            target = files[-1]
        else:
            target = store.root / f"events-{time.time_ns():020d}.jsonl"
        fd = _open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        with os.fdopen(fd, "wb") as stream:
            if stream.write(data) != len(data):
                raise OSError("partial diagnostic append")
            stream.flush()
            if logging_before[0] is not None and logging_before[0]["current_state"] != "recovered":
                os.fsync(stream.fileno())
        after_append(store, event, logging_before)


def _cursor(name: str, offset: int) -> str:
    return base64.urlsafe_b64encode(
        json.dumps([name, offset], separators=(",", ":")).encode()
    ).decode()


def _parse_cursor(value: str) -> tuple[str, int]:
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("invalid diagnostic cursor")
    try:
        name, offset = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
    except Exception:
        raise ValueError("invalid diagnostic cursor") from None
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"events-[0-9]{20}\.jsonl", name)
        or type(offset) is not int
        or offset < 0
    ):
        raise ValueError("invalid diagnostic cursor")
    return name, offset


def _coverage_gap(result: dict, reason: str) -> None:
    gaps = result["coverage"]["gaps"]
    for gap in gaps:
        if gap["reason"] == reason:
            gap["count"] += 1
            return
    gaps.append({"reason": reason, "count": 1})


def _retention_record(store: Any) -> dict | None:
    path = store.root / "retention.json"
    if not path.exists():
        return None
    fd = _open(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ValueError("invalid retention record")
    record = json.loads(raw)
    count, stamp = record.get("evicted_segments"), record.get("last_eviction_at")
    if type(count) is not int or not 0 <= count < 2**53:
        raise ValueError("invalid retention record")
    if type(stamp) not in (int, float) or not 0 <= stamp <= 10**12:
        raise ValueError("invalid retention record")
    return {"reason": "retention", "evicted_segments": count, "last_eviction_at": stamp}


def health(store: Any) -> dict:
    result = {
        "schema_version": 1,
        "owner_uid": store.owner_uid,
        "component": store.component,
        "status": "unavailable",
        "available": False,
        "failed_writes": store.failed_writes,
        "dropped_events": store.dropped_events,
        "gaps": [],
        "oldest_at": None,
        "newest_at": None,
    }
    try:
        with _locked(store):
            add_coverage(store, result)
            inventory = _segments(store)
            files = [
                p for p in inventory if time.time() - _segment_time(p) < store.retention_seconds
            ]
            expired = len(inventory) - len(files)
            if expired:
                result["gaps"].append({"reason": "retention-expired", "count": expired})
            result["available"] = bool(files)
            result["status"] = (
                "degraded"
                if store.failed_writes
                else ("observed" if files else "absent")
            )
            result["bytes"] = sum(p.stat().st_size for p in inventory)
            result["oldest_at"] = _segment_time(files[0]) if files else None
            result["newest_at"] = files[-1].stat().st_mtime if files else None
            record = _retention_record(store)
            if record is not None:
                result["gaps"].append(record)
    except FileNotFoundError:
        result["status"] = "absent"
    except Exception:
        result["gaps"].append({"reason": "unreadable"})
    if "logging" not in result and getattr(store, "_logging_failure", None) is not None:
        add_coverage(store, result)
    if result["gaps"] and result["status"] in {"observed", "absent"}:
        result["status"] = "degraded"
    return result


def read_events(store: Any, *, cursor: str | None, trace_id: str | None, limit: int) -> dict:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    trace = diagnostic_id(trace_id) if trace_id is not None else None
    if trace_id is not None and trace is None:
        raise ValueError("trace_id must be a UUID")
    start = _parse_cursor(cursor) if cursor else None
    result: dict = {
        "schema_version": 1,
        "owner_uid": store.owner_uid,
        "component": store.component,
        "events": [],
        "next_cursor": None,
        "coverage": {"available": False, "status": "absent", "gaps": []},
    }
    scanned = 0
    try:
        with _locked(store):
            add_coverage(store, result["coverage"])
            inventory = _segments(store)
            files = [
                p for p in inventory if time.time() - _segment_time(p) < store.retention_seconds
            ]
            expired = len(inventory) - len(files)
            if expired:
                result["coverage"]["gaps"].append({"reason": "retention-expired", "count": expired})
            if start and start[0] not in [p.name for p in files]:
                _coverage_gap(result, "cursor-evicted")
                start = None
            result["coverage"].update(
                {"available": bool(files), "status": "observed" if files else "absent"}
            )
            record = _retention_record(store)
            if record is not None:
                result["coverage"]["gaps"].append(record)
            stopped = False
            for path in files:
                if start and path.name < start[0]:
                    continue
                fd = _open(path, os.O_RDONLY)
                with os.fdopen(fd, "rb") as stream:
                    if start and path.name == start[0]:
                        if start[1] > path.stat().st_size:
                            _coverage_gap(result, "cursor-truncated")
                        else:
                            stream.seek(start[1])
                    while True:
                        offset = stream.tell()
                        raw = stream.readline(MAX_EVENT_BYTES + 1)
                        if not raw:
                            break
                        scanned += len(raw)
                        if scanned > MAX_RESPONSE_BYTES or len(result["events"]) >= limit:
                            result["next_cursor"] = _cursor(path.name, offset)
                            stopped = True
                            break
                        if len(raw) > MAX_EVENT_BYTES or not raw.endswith(b"\n"):
                            _coverage_gap(result, "malformed-event")
                            result["next_cursor"] = _cursor(path.name, stream.tell())
                            stopped = True
                            break
                        try:
                            event = json.loads(raw)
                            if not _validate_event(event, store):
                                raise ValueError("foreign event")
                            event.setdefault('level', event_level(event))
                        except Exception:
                            _coverage_gap(result, "malformed-event")
                            continue
                        if trace is None or event.get("trace_id") == trace:
                            if (
                                len(json.dumps(result).encode()) + len(raw) + 2048
                                > MAX_RESPONSE_BYTES
                            ):
                                result["next_cursor"] = _cursor(path.name, offset)
                                stopped = True
                                break
                            result["events"].append(event)
                    if stopped:
                        break
    except FileNotFoundError:
        pass
    except Exception:
        result["coverage"].update({"status": "unavailable", "available": False})
        _coverage_gap(result, "unreadable")
    if "logging" not in result["coverage"] and getattr(store, "_logging_failure", None) is not None:
        add_coverage(store, result["coverage"])
    if result["coverage"]["gaps"] and result["coverage"]["status"] in {"observed", "absent"}:
        result["coverage"]["status"] = "degraded"
    result["coverage"]["scanned_bytes"] = scanned
    result["coverage"]["continuation_required"] = result["next_cursor"] is not None
    if len(json.dumps(result).encode()) > MAX_RESPONSE_BYTES:
        return {
            "schema_version": 1,
            "owner_uid": store.owner_uid,
            "component": store.component,
            "events": [],
            "next_cursor": cursor,
            "coverage": {
                "available": False,
                "status": "unavailable",
                "gaps": [{"reason": "response-limit", "count": 1}],
            },
        }
    return result


def prune(store: Any) -> dict:
    """Service maintenance removes expired/oversized segments without fake work events."""
    removed = 0
    try:
        with _locked(store, write=True):
            files = _segments(store)
            total = sum(p.stat().st_size for p in files)
            for path in files:
                if (
                    total > store.max_bytes
                    or time.time() - _segment_time(path) >= store.retention_seconds
                ):
                    size = path.stat().st_size
                    path.unlink()
                    total -= size
                    removed += 1
            if removed:
                _gap(store, removed)
        return {"complete": True, "removed": removed}
    except Exception:
        return {"complete": False, "removed": removed}
