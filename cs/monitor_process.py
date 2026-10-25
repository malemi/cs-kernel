"""Absolute observer I/O deadlines; timeout never retries a business operation."""

from __future__ import annotations

import json
import multiprocessing


class ObservationError(ValueError):
    """Safe typed transport failure without URLs, headers or exception messages."""

    def __init__(self, failure: dict):
        known = {
            "TimeoutError",
            "HTTPError",
            "URLError",
            "ConnectionError",
            "ConnectionRefusedError",
            "SSLError",
            "ValueError",
            "OSError",
            "UnknownError",
        }
        reason = failure.get("reason")
        name = failure.get("error_class")
        self.failure = {
            "reason": (
                reason
                if isinstance(reason, str) and reason in {"auth", "quota", "timeout", "unknown"}
                else "unknown"
            ),
            "error_class": name if isinstance(name, str) and name in known else "UnknownError",
        }
        code = failure.get("error_code")
        if type(code) is int and 100 <= code <= 599:
            self.failure["error_code"] = code
        super().__init__("Observer operation unavailable")


def safe_failure(exc: BaseException) -> dict:
    if isinstance(exc, ObservationError):
        return dict(exc.failure)
    code = getattr(exc, "code", None)
    name = type(exc).__name__
    known = {
        "TimeoutError",
        "HTTPError",
        "URLError",
        "ConnectionError",
        "ConnectionRefusedError",
        "SSLError",
        "ValueError",
        "OSError",
    }
    result = {
        "reason": (
            "auth"
            if code in (401, 403)
            else (
                "quota"
                if code == 429
                else "timeout" if isinstance(exc, TimeoutError) else "unknown"
            )
        ),
        "error_class": name if name in known else "UnknownError",
    }
    if type(code) is int and 100 <= code <= 599:
        result["error_code"] = code
    return result


def _run(pipe, operation: str, args: tuple) -> None:
    try:
        if operation == "post":
            from .monitor_transport import _post

            result = _post(*args)
        elif operation == "read":
            from .monitor import _read_component

            result = _read_component(*args)
        elif operation == "get":
            from .monitor_transport import _get

            result = _get(*args)
        else:
            raise ValueError("Unknown observation")
        raw = json.dumps({"ok": True, "result": result}, allow_nan=False).encode()
        if len(raw) > 262144:
            raise ValueError("Observer response limit")
        pipe.send_bytes(raw)
    except BaseException as exc:
        try:
            pipe.send_bytes(json.dumps({"ok": False, "failure": safe_failure(exc)}).encode())
        except OSError:
            pass
    finally:
        pipe.close()


def bounded(operation: str, args: tuple, *, seconds: float = 3) -> dict:
    """Return a bounded metadata value or a fixed error with bounded cleanup."""
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_run, args=(send, operation, args), daemon=True)
    try:
        process.start()
        send.close()
        if not receive.poll(seconds):
            raise ObservationError({"reason": "timeout", "error_class": "TimeoutError"})
        raw = receive.recv_bytes(262144)
        result = json.loads(raw)
        if not result.get("ok") or not isinstance(result.get("result"), dict):
            raise ObservationError(
                result.get("failure", {"reason": "unknown", "error_class": "UnknownError"})
            )
        return result["result"]
    except (EOFError, OSError):
        raise ValueError("Observer operation unavailable") from None
    finally:
        receive.close()
        send.close()
        if process.pid is not None:
            process.join(0.1)
            if process.is_alive():
                process.terminate()
                process.join(0.2)
            if process.is_alive():
                process.kill()
                process.join(0.2)
            if process.is_alive():
                # Uninterruptible OS I/O cannot be claimed quiescent.
                raise ValueError("Observer cleanup unconfirmed")
            process.close()
