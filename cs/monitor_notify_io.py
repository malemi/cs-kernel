"""Bounded fixed upstream delivery and a permanent signed-message recipient."""

from __future__ import annotations

import json
import multiprocessing
import re
import threading
import time
import urllib.parse
import urllib.request

from .monitor_notify_config import NotifyConfig
from .monitor_notify_protocol import canonical, signed, verified
from .monitor_notify_store import Inbox
from .monitor_transport import NoRedirect

UPSTREAM = "https://ntfy.sh"
DISPLAY_PREFIX = (
    "Operator monitoring requires attention.\n"
    "Inspect cs logs health. Do not resend uncertain work.\nReceipt: "
)


def topic(config: NotifyConfig) -> str:
    value = config.credential(config.topic_env)
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", value):
        raise ValueError("Invalid private notification topic")
    return value


def ingest(config: NotifyConfig, inbox: Inbox, event: dict, *, now=None) -> bool:
    if not isinstance(event, dict) or event.get("event") != "message":
        return False
    raw = event.get("message")
    if not isinstance(raw, str) or len(raw.encode()) > 2048:
        return False
    try:
        value = json.loads(raw[len(DISPLAY_PREFIX) :] if raw.startswith(DISPLAY_PREFIX) else raw)
        body = verified(config, value)
        return inbox.received(
            body, event.get("id"), canonical(value), time.time() if now is None else now
        )
    except (ValueError, TypeError, KeyError):
        return False


class Subscriber(threading.Thread):
    """A real recipient: only verified, expected messages enter its durable inbox."""

    def __init__(self, config: NotifyConfig, *, base: str = UPSTREAM):
        super().__init__(daemon=True)
        self.config, self.base = config, base
        self.stop_event = threading.Event()
        self.connected = threading.Event()

    def run(self):
        inbox = Inbox(self.config.state_dir, self.config.owner_uid, self.config.monitor_id)
        while not self.stop_event.is_set():
            try:
                query = urllib.parse.urlencode({"since": inbox.last_id()})
                request = urllib.request.Request(f"{self.base}/{topic(self.config)}/json?{query}")
                with urllib.request.build_opener(NoRedirect()).open(
                    request, timeout=60
                ) as response:
                    while not self.stop_event.is_set():
                        line = response.readline(8193)
                        if not line or len(line) > 8192:
                            break
                        event = json.loads(line)
                        if isinstance(event, dict) and event.get("event") in {"open", "keepalive"}:
                            self.connected.set()
                        ingest(self.config, inbox, event)
            except Exception:
                pass  # URLs, upstream error bodies and untrusted messages never enter logs.
            finally:
                self.connected.clear()
            self.stop_event.wait(2)


def _publish(config: NotifyConfig, item: dict, base: str, deadline: float) -> dict:
    inbox = Inbox(config.state_dir, config.owner_uid, config.monitor_id)
    nonce, fresh = inbox.reserve(item["fingerprint"], config.daily_limit, time.time())
    existing = inbox.receipt(nonce)
    if existing:
        return {"accepted": True, "receipt": existing}
    if not fresh:
        return {"accepted": False}
    if config.backend == "smtp":
        # Loaded only on the operator host. No mailbox credential enters remote config.
        from .config import load
        from .send_mail import send_operational_notice

        settings = load()
        if settings.engine_owner_uid != config.owner_uid:
            raise ValueError("SMTP owner binding differs")
        raw = canonical(
            {
                "nonce": nonce,
                "kind": item["kind"],
                "count": item["count"],
                "reference": item["reference"],
            }
        )
        inbox.bind(nonce, raw)
        identity = send_operational_notice(
            settings, nonce, item["kind"], item["count"], incident_reference=item["reference"]
        )
        return {"accepted": True, "sink": "filesystem", "reference": identity}

    else:
        message = canonical(signed(config, item, nonce))
        inbox.bind(nonce, message)
        request = urllib.request.Request(
            f"{base}/{topic(config)}",
            data=DISPLAY_PREFIX.encode() + message,
            method="POST",
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Title": "Operator monitoring requires attention",
                "Priority": "high",
            },
        )
        remaining = max(0.05, min(1.5, deadline - time.monotonic()))
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=remaining) as response:
            raw = response.read(8193)
        if len(raw) > 8192:
            raise ValueError("Notification admission limit")
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get("event") != "message":
            raise ValueError("Notification not admitted")
        inbox.provider(nonce, result.get("id"))
    while time.monotonic() < deadline:
        receipt = inbox.receipt(nonce)
        if receipt:
            return {"accepted": True, "receipt": receipt}
        time.sleep(0.02)
    return {"accepted": False}


def _worker(pipe, config, item, base, deadline):
    try:
        result = _publish(config, item, base, deadline - 0.15)
    except BaseException as error:
        from .monitor_process import safe_failure
        from .observability_producers import error_metadata, error_reason

        failure = {**safe_failure(error), **error_metadata(error)}
        reason = error_reason(error)
        if reason != "unknown":
            failure["reason"] = reason
        try:
            Inbox(config.state_dir, config.owner_uid, config.monitor_id).failure(failure)
        except Exception:
            pass
        result = {"accepted": False, "failure": failure}
    try:
        pipe.send(result)
    except (OSError, EOFError):
        pass
    finally:
        pipe.close()


def publish(config: NotifyConfig, item: dict, *, base: str = UPSTREAM) -> dict:
    """Provider/socket trickling cannot extend the absolute notification deadline."""
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    deadline = time.monotonic() + (9 if config.backend == "smtp" else 2.65)
    process = context.Process(
        target=_worker, args=(send, config, item, base, deadline), daemon=True
    )
    try:
        process.start()
        send.close()
        if receive.poll(max(0, deadline - time.monotonic())):
            return receive.recv()
        return {"accepted": False}
    finally:
        receive.close()
        send.close()
        if process.pid is not None:
            process.join(0.05)
            if process.is_alive():
                process.terminate()
                process.join(0.1)
            if process.is_alive():
                process.kill()
                process.join(0.1)
            if process.is_alive():
                raise ValueError("Notification worker cleanup unconfirmed")
            process.close()
