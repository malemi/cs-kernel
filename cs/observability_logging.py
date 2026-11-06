"""Private bounded logging-failure history and append-backed recovery evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

ERROR_CLASSES = frozenset(
    (
        "TimeoutError",
        "PermissionError",
        "ConnectionError",
        "OSError",
        "ValueError",
        "RuntimeError",
        "CancelledError",
        "EngineError",
        "UnknownError",
    )
)
FIELDS = {
    "schema_version",
    "current_state",
    "history_retained",
    "observed_failures",
    "lost_events_unknown",
    "first_failure_at",
    "last_failure",
    "recovery",
}
FAILURE_FIELDS = {
    "timestamp",
    "pid",
    "process_start",
    "error_class",
    "error_code",
    "error_file",
    "error_line",
}
RECOVERY_FIELDS = {"event_id", "timestamp", "pid", "process_start"}
STATE_FILE = ".logging-health.json"
MARKER = ".logging-failed"
_PENDING_GUARD = threading.Lock()


def _pending(store):
    with _PENDING_GUARD:
        return getattr(store, "_logging_failure", None)


def _clear_pending(store, failure):
    with _PENDING_GUARD:
        if getattr(store, "_logging_failure", None) is failure:
            store._logging_failure = None


def _write_marker(store):
    from .observability_store import _open, _root, _check

    _root(store)
    target = store.root / MARKER
    try:
        _check(target)
    except FileNotFoundError:
        pass
    data = json.dumps(
        {"reason": "logging", "coverage_lost": True, "failure_id": uuid.uuid4().hex},
        separators=(",", ":"),
    ).encode()
    temp = store.root / (".logging-marker-" + uuid.uuid4().hex + ".tmp")
    try:
        fd = _open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temp, target)
            info = os.fstat(stream.fileno())
            return [
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
                hashlib.sha256(data).hexdigest(),
            ]
    finally:
        temp.unlink(missing_ok=True)


def _integer(value, low=0):
    return type(value) is int and low <= value < 2**53


def _stamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid logging timestamp")
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError("invalid logging timezone")
        return stamp
    except (TypeError, OverflowError):
        raise ValueError("invalid logging timestamp") from None


def _process(value):
    if not _integer(value.get("pid")):
        raise ValueError("invalid logging process")
    start = value.get("process_start")
    if start is not None and (
        not isinstance(start, str) or not re.fullmatch(r"[0-9]{1,32}", start)
    ):
        raise ValueError("invalid logging process start")


def validate_logging(value):
    """Validate the common private wire shape without accepting diagnostic text."""
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("invalid logging health fields")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["history_retained"] is not True
    ):
        raise ValueError("invalid logging health version")
    if value["current_state"] not in ("failed", "recovered", "unknown"):
        raise ValueError("invalid logging health state")
    if not _integer(value["observed_failures"]) or type(value["lost_events_unknown"]) is not bool:
        raise ValueError("invalid logging loss count")
    first = value["first_failure_at"]
    if first is not None:
        _stamp(first)
    failure = value["last_failure"]
    if failure is not None:
        if not isinstance(failure, dict) or set(failure) != FAILURE_FIELDS:
            raise ValueError("invalid logging failure")
        _process(failure)
        last = _stamp(failure["timestamp"])
        if first is None or _stamp(first) > last or value["observed_failures"] < 1:
            raise ValueError("invalid logging failure history")
        if (
            not isinstance(failure["error_class"], str)
            or failure["error_class"] not in ERROR_CLASSES
        ):
            raise ValueError("invalid logging error class")
        code, line, file = failure["error_code"], failure["error_line"], failure["error_file"]
        if code is not None and not _integer(code, -(2**53) + 1):
            raise ValueError("invalid logging error code")
        if line is not None and not _integer(line, 1):
            raise ValueError("invalid logging error line")
        if file is not None and (
            not isinstance(file, str)
            or len(file) > 180
            or not re.fullmatch(r"[a-zA-Z0-9_/.-]+\.py", file)
            or file.startswith("/")
            or ".." in file.split("/")
        ):
            raise ValueError("invalid logging error file")
    elif first is not None or value["observed_failures"] != 0:
        raise ValueError("missing logging failure history")
    recovery = value["recovery"]
    if value["current_state"] == "failed" and failure is None:
        raise ValueError("missing current logging failure")
    if value["current_state"] == "recovered":
        if not isinstance(recovery, dict) or set(recovery) != RECOVERY_FIELDS:
            raise ValueError("missing logging recovery proof")
        _process(recovery)
        if not isinstance(recovery["event_id"], str) or not re.fullmatch(
            r"[a-f0-9]{32}", recovery["event_id"]
        ):
            raise ValueError("invalid logging recovery event")
        if failure is not None and _stamp(recovery["timestamp"]) <= _stamp(failure["timestamp"]):
            raise ValueError("unordered logging recovery")
        _stamp(recovery["timestamp"])
    elif recovery is not None:
        raise ValueError("unexpected logging recovery")
    return copy.deepcopy(value)


def _unknown():
    return dict(
        schema_version=1,
        current_state="unknown",
        history_retained=True,
        observed_failures=0,
        lost_events_unknown=True,
        first_failure_at=None,
        last_failure=None,
        recovery=None,
    )


def _fingerprint(store):
    from .observability_store import _open

    try:
        fd = _open(store.root / MARKER, os.O_RDONLY)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        raw = stream.read(4097)
        final = os.fstat(stream.fileno())
    if len(raw) > 4096 or (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
        final.st_ino,
        final.st_size,
        final.st_mtime_ns,
        final.st_ctime_ns,
    ):
        raise ValueError("unstable logging marker")
    return [
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        hashlib.sha256(raw).hexdigest(),
    ]


def _read(store):
    from .observability_store import _open

    marker = _fingerprint(store)
    try:
        fd = _open(store.root / STATE_FILE, os.O_RDONLY)
    except FileNotFoundError:
        return (_unknown() if marker is not None else None), marker
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ValueError("oversized logging state")
    state = json.loads(raw)
    if (
        not isinstance(state, dict)
        or set(state) != {"owner_uid", "logging", "marker"}
        or state["owner_uid"] != store.owner_uid
    ):
        raise ValueError("foreign logging state")
    logging = validate_logging(state["logging"])
    prior = state["marker"]
    if (
        not isinstance(prior, list)
        or len(prior) not in (4, 5)
        or any(type(v) is not int or v < 0 for v in prior[:4])
        or (
            len(prior) == 5
            and (not isinstance(prior[4], str) or not re.fullmatch(r"[a-f0-9]{64}", prior[4]))
        )
    ):
        raise ValueError("invalid logging marker reference")
    if marker is None or marker != prior:
        logging.update(current_state="unknown", recovery=None, lost_events_unknown=True)
    return logging, marker


def _save(store, logging, marker):
    from .observability_store import _open, _check

    validate_logging(logging)
    target = store.root / STATE_FILE
    try:
        _check(target)
    except FileNotFoundError:
        pass
    data = json.dumps(
        {"owner_uid": store.owner_uid, "logging": logging, "marker": marker}, separators=(",", ":")
    ).encode()
    if len(data) > 4096:
        raise ValueError("oversized logging state")
    temp = store.root / (".logging-" + uuid.uuid4().hex + ".tmp")
    try:
        fd = _open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def _failure(exc):
    from .observability import process_start

    name = type(exc).__name__ if exc is not None else "UnknownError"
    code = getattr(exc, "errno", None)
    file, line = None, None
    tb = getattr(exc, "__traceback__", None)
    base = Path(__file__).parent
    remaining = 64
    while tb is not None and remaining:
        remaining -= 1
        try:
            relative = Path(tb.tb_frame.f_code.co_filename).relative_to(base)
            candidate = relative.as_posix()
            if (
                len(candidate) <= 180
                and re.fullmatch(r"[a-zA-Z0-9_/.-]+\.py", candidate)
                and ".." not in candidate.split("/")
            ):
                file, line = candidate, tb.tb_lineno
        except ValueError:
            pass
        tb = tb.tb_next
    return dict(
        timestamp=datetime.now(timezone.utc).isoformat(),
        pid=os.getpid(),
        process_start=process_start(),
        error_class=name if name in ERROR_CLASSES else "UnknownError",
        error_code=code if _integer(code, -(2**53) + 1) else None,
        error_file=file,
        error_line=line,
    )


def _record_locked(store, failure):
    logging, marker = _read(store)
    if logging is None:
        logging = _unknown()
        logging["lost_events_unknown"] = False
    marker = _write_marker(store)
    previous = logging["last_failure"]
    latest = (
        previous
        if previous and _stamp(previous["timestamp"]) > _stamp(failure["timestamp"])
        else failure
    )
    first = logging["first_failure_at"]
    logging.update(
        current_state="failed",
        recovery=None,
        last_failure=latest,
        first_failure_at=min(first, failure["timestamp"]) if first else failure["timestamp"],
        observed_failures=min(logging["observed_failures"] + 1, 2**53 - 1),
    )
    _save(store, logging, marker)
    _clear_pending(store, failure)
    return logging, marker


def record_failure(store, exc=None):
    """Record a known failed emission; an unsafe store retains only safe local evidence."""
    from .observability_store import _locked

    failure = _failure(exc)
    with _PENDING_GUARD:
        store._logging_failure = failure
    try:
        with _locked(store, write=True):
            _record_locked(store, failure)
    except Exception:
        try:
            _write_marker(store)
        except Exception:
            pass
        raise


def before_append(store):
    """Capture retained history under the existing append lock."""
    fallback = _pending(store)
    if fallback is not None:
        return _record_locked(store, fallback)
    return _read(store)


def after_append(store, event, before):
    """Publish the first fresh append after a failure, retaining the original marker."""
    pending = _pending(store)
    if pending is not None:
        _record_locked(store, pending)
        return
    logging, marker = before
    if logging is None or logging["current_state"] == "recovered":
        return
    if marker is None or marker != _fingerprint(store):
        return
    if (
        logging["current_state"] == "unknown"
        and _stamp(event["timestamp"]).timestamp() * 1_000_000_000 <= marker[2]
    ):
        return
    failure = logging["last_failure"]
    if failure is not None and _stamp(event["timestamp"]) <= _stamp(failure["timestamp"]):
        return
    logging.update(current_state="recovered", recovery={key: event[key] for key in RECOVERY_FIELDS})
    _save(store, logging, marker)
    pending = _pending(store)
    if pending is not None:
        _record_locked(store, pending)


def add_coverage(store, coverage):
    """Attach retained history without changing it or inferring health from local counters."""
    try:
        logging, _ = _read(store)
    except Exception:
        logging = _unknown()
        if not any(g.get("reason") == "unreadable" for g in coverage["gaps"]):
            coverage["gaps"].append({"reason": "unreadable"})
    fallback = _pending(store)
    if fallback is not None:
        logging = logging or _unknown()
        logging.update(
            current_state="failed",
            recovery=None,
            last_failure=fallback,
            first_failure_at=logging["first_failure_at"] or fallback["timestamp"],
            observed_failures=max(1, logging["observed_failures"]),
        )
    if logging is not None:
        coverage["logging"] = logging
        if not any(g.get("reason") == "logging" for g in coverage["gaps"]):
            coverage["gaps"].append({"reason": "logging", "count": 1})
        if coverage["status"] in ("observed", "absent"):
            coverage["status"] = "degraded"
