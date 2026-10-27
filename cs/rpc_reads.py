"""Bounded multiplexed reads with explicit per-key unavailable outcomes."""
from __future__ import annotations

from . import observability
from contextlib import nullcontext

import asyncio
from dataclasses import dataclass
import math
import json
import os
import signal
import subprocess
import sys
import time
from typing import Any

from . import rpc

METHODS = frozenset({"tasks.assignment.project", "emails.list_by_thread"})
BATCH_SECONDS = 90
REQUEST_SECONDS = 60
ASSIGNMENT_REQUEST_SECONDS = 150
ASSIGNMENT_BATCH_SECONDS = 180
CLOSE_SECONDS = 2
CONCURRENCY = 4


@dataclass(frozen=True)
class ReadOutcome:
    value: Any = None
    error: Exception | None = None
    diagnostic: dict | None = None


CAUSES = {'remote_invalid_params', 'remote_error', 'request_timeout', 'batch_deadline', 'shared_deadline', 'worker_timeout', 'connection_failure', 'transport_unavailable', 'connection_setup_timeout', 'account_timeout_deferred', 'capacity_timeout_deferred', 'read_deferred_after_failure'}
BOUND_ORIGINS = {'request_timeout', 'batch_deadline', 'shared_deadline', 'not_attempted'}


def diagnostic(cause, started, bound, remaining=None, *, bound_origin=None, remote_error_code=None):
    value = {'cause': cause, 'bound_origin': bound_origin or cause,
        'elapsed_ms': min(10**12, max(0, round((time.monotonic() - started) * 1000))),
        'bound_ms': min(10**12, max(0, round(bound * 1000))),
        'remaining_ms': None if remaining is None else min(10**12, max(0, round(remaining * 1000)))}
    if remote_error_code is not None:
        value['remote_error_code'] = remote_error_code
    return validate_diagnostic(value)


def validate_diagnostic(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) not in ({'cause', 'bound_origin', 'elapsed_ms', 'bound_ms', 'remaining_ms'},
                {'cause', 'bound_origin', 'elapsed_ms', 'bound_ms', 'remaining_ms', 'remote_error_code'})
            or value['cause'] not in CAUSES or value['bound_origin'] not in BOUND_ORIGINS):
        raise ValueError('Invalid read diagnostic')
    for key in ('elapsed_ms', 'bound_ms', 'remaining_ms'):
        item = value[key]
        if key == 'remaining_ms' and item is None:
            continue
        if type(item) is not int or not 0 <= item <= 10**12:
            raise ValueError('Invalid read timing')
    if 'remote_error_code' in value:
        code = value['remote_error_code']
        if type(code) is not int or not -(2**53) < code < 2**53:
            raise ValueError('Invalid remote error code')
    return dict(value)


READ_COMMAND = (sys.executable, "-c", "from cs.rpc_reads import _isolated_main; _isolated_main()")


def _cacheable(token, remaining):
    try:
        return (isinstance(token, str) and len(token.split(".")) == 3
                and rpc.auth._token_exp(token) - time.time() > max(rpc.auth._SKEW_SECONDS, remaining))
    except (ValueError, TypeError, IndexError, KeyError):
        return False


async def _close(client):
    reader = client._recv_task
    handlers = list(client._handlers)
    try:
        await asyncio.wait_for(client.__aexit__(None, None, None), CLOSE_SECONDS)
    except (Exception, asyncio.CancelledError):
        ws = client._ws
        transport = getattr(ws, "transport", None)
        if transport is not None:
            transport.abort()
    finally:
        tasks = [task for task in [reader, *handlers] if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), CLOSE_SECONDS)


async def _read(settings, method, requests, request_timeout, batch_timeout, deadline, token_cache=None, deadline_origin='shared_deadline'):
    started = time.monotonic()
    batch_limit = started + batch_timeout
    limit = min(batch_limit, deadline - 2 * CLOSE_SECONDS) if deadline is not None else batch_limit
    origin = deadline_origin if deadline is not None and deadline - 2 * CLOSE_SECONDS <= batch_limit else 'batch_deadline'
    outcomes = {key: ReadOutcome(error=TimeoutError("read batch incomplete")) for key in requests}
    if not requests or time.monotonic() >= limit:
        return {key: ReadOutcome(error=row.error, diagnostic=diagnostic(origin, started, limit-started, limit-started, bound_origin=origin)) for key, row in outcomes.items()}
    client = None
    workers = []
    fatal = asyncio.Event()
    pending = iter(requests.items())

    async def worker():
        while not fatal.is_set() and time.monotonic() < limit:
            try:
                key, params = next(pending)
            except StopIteration:
                return
            remaining = limit - time.monotonic()
            allowance = min(request_timeout, REQUEST_SECONDS)
            bound = min(allowance, remaining)
            selected = 'request_timeout' if allowance <= remaining else origin
            request_started = time.monotonic()
            if bound <= 0:
                return
            try:
                diagnostic_context = observability.current_context()
                with (observability.context({**diagnostic_context, "parent_span_id": diagnostic_context.get("span_id"), "span_id": None})
                      if diagnostic_context else nullcontext()):
                    value = await asyncio.wait_for(client.call(method, params, timeout=bound), bound)
                outcomes[key] = ReadOutcome(value=value)
            except Exception as exc:
                cause = ('remote_invalid_params' if exc.code == -32602 else 'remote_error') if isinstance(exc, rpc.EngineError) else selected if isinstance(exc, TimeoutError) else 'connection_failure' if isinstance(exc, ConnectionError) else 'transport_unavailable'
                code = exc.code if isinstance(exc, rpc.EngineError) and type(exc.code) is int and -(2**53) < exc.code < 2**53 else None
                outcomes[key] = ReadOutcome(error=exc, diagnostic=diagnostic(cause, request_started, bound, limit-time.monotonic(), bound_origin=selected, remote_error_code=code))
                if isinstance(exc, (TimeoutError, ConnectionError)):
                    fatal.set()
                    return

    try:
        token = (token_cache or {}).get(settings.engine_owner_uid)
        if not _cacheable(token, limit - time.monotonic() + 2 * CLOSE_SECONDS):
            token = rpc.auth.get_id_token(settings)
            if token_cache is not None:
                token_cache[settings.engine_owner_uid] = token
        client = rpc.EngineClient(settings, id_token=token)
        await asyncio.wait_for(client.__aenter__(), max(0.001, limit - time.monotonic()))
        if time.monotonic() < limit:
            workers = [asyncio.create_task(worker()) for _ in range(min(CONCURRENCY, len(requests)))]
            finished = asyncio.gather(*workers)
            stopped = asyncio.create_task(fatal.wait())
            try:
                await asyncio.wait([finished, stopped, client._recv_task], timeout=max(0, limit - time.monotonic()), return_when=asyncio.FIRST_COMPLETED)
                await asyncio.sleep(0)
            finally:
                stopped.cancel()
                await asyncio.gather(stopped, return_exceptions=True)
                for task in workers:
                    task.cancel()
                await asyncio.gather(finished, return_exceptions=True)
    except Exception as exc:
        cause = 'connection_setup_timeout' if isinstance(exc, TimeoutError) else 'connection_failure' if isinstance(exc, ConnectionError) else 'transport_unavailable'
        outcomes = {key: ReadOutcome(error=exc, diagnostic=diagnostic(cause, started, limit-started, limit-time.monotonic(), bound_origin=origin)) for key in requests}
    finally:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        if client is not None:
            await _close(client)
    for key, row in outcomes.items():
        if row.error is not None and row.diagnostic is None:
            cause = origin if time.monotonic() >= limit else 'read_deferred_after_failure' if fatal.is_set() else 'connection_failure' if client is not None and client._recv_task.done() else 'transport_unavailable'
            outcomes[key] = ReadOutcome(error=row.error, diagnostic=diagnostic(cause, started, limit-started, limit-time.monotonic(), bound_origin=origin))
    return outcomes


def read_many(settings, method: str, requests: dict, *, request_timeout: float = REQUEST_SECONDS,
              batch_timeout: float = BATCH_SECONDS, deadline: float | None = None,
              token_cache: dict | None = None, owned_process_group: int | None = None) -> dict:
    """Read each key once; failures never imply absence or authorize action."""
    if owned_process_group is not None and (type(owned_process_group) is not int
            or owned_process_group != os.getpid() or os.getpgrp() != owned_process_group):
        raise ValueError('read worker group is not owned')
    if method not in METHODS:
        raise ValueError("method is not an allowed batch read")
    if any(not math.isfinite(value) or value <= 0 for value in (request_timeout, batch_timeout)):
        raise ValueError("read timeouts must be finite and positive")
    if deadline is not None and not math.isfinite(deadline):
        raise ValueError("read deadline must be finite")
    request_cap = ASSIGNMENT_REQUEST_SECONDS if method == "tasks.assignment.project" else REQUEST_SECONDS
    batch_cap = ASSIGNMENT_BATCH_SECONDS if method == "tasks.assignment.project" else BATCH_SECONDS
    request_timeout = min(request_timeout, request_cap)
    batch_timeout = min(batch_timeout, batch_cap)
    started = time.monotonic()
    batch_limit = started + batch_timeout
    limit = min(batch_limit, deadline) if deadline is not None else batch_limit
    origin = 'shared_deadline' if deadline is not None and deadline <= batch_limit else 'batch_deadline'
    outcomes = {key: ReadOutcome(error=TimeoutError("read capacity deferred: deadline"), diagnostic=diagnostic(origin, started, limit-started, limit-started, bound_origin=origin)) for key in requests}
    if not requests or time.monotonic() >= limit - 2 * CLOSE_SECONDS:
        return outcomes
    process = None
    try:
        token = (token_cache or {}).get(settings.engine_owner_uid)
        payload = json.dumps({"settings": settings.model_dump(mode="json"), "method": method,
            "requests": requests, "request_timeout": request_timeout, "batch_timeout": batch_timeout,
            "deadline": limit - 2 * CLOSE_SECONDS, "token": token if _cacheable(token, limit - time.monotonic()) else None,
            "close_seconds": CLOSE_SECONDS, "request_seconds": request_timeout, "deadline_origin": origin}).encode()
        process = subprocess.Popen(READ_COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=owned_process_group is None,
            env=dict(os.environ, CS_DIAGNOSTIC_CONTEXT=json.dumps(observability.current_context())))
        output, _ = process.communicate(payload, timeout=max(0.001, limit - 2 * CLOSE_SECONDS - time.monotonic()))
        if process.returncode != 0:
            raise RuntimeError("read worker unavailable")
        result = json.loads(output)
        if not isinstance(result, dict) or set(result) != {"outcomes", "token"}:
            raise ValueError("read worker output is invalid")
        rows = result["outcomes"]
        if not isinstance(rows, dict) or set(rows) != set(requests):
            raise ValueError("read worker coverage is incomplete")
        decoded = {}
        for key, row in rows.items():
            if not isinstance(row, dict) or set(row) not in ({"value", "error"}, {"value", "error", "diagnostic"}) or row["error"] not in {None, "timeout", "connection", "unavailable"}:
                raise ValueError("read worker outcome is invalid")
            error = {"timeout": TimeoutError, "connection": ConnectionError, "unavailable": RuntimeError}.get(row["error"])
            decoded[key] = ReadOutcome(value=row["value"], error=error("bounded read unavailable") if error else None, diagnostic=validate_diagnostic(row.get("diagnostic")))
        if token_cache is not None and _cacheable(result["token"], limit - time.monotonic()):
            token_cache[settings.engine_owner_uid] = result["token"]
        return {key: decoded[key] for key in requests}
    except subprocess.TimeoutExpired:
        return {key: ReadOutcome(error=row.error, diagnostic=diagnostic('worker_timeout', started, limit-started-2*CLOSE_SECONDS, limit-time.monotonic(), bound_origin=origin)) for key, row in outcomes.items()}
    except Exception as exc:
        return {key: ReadOutcome(error=exc) for key in requests}
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    if owned_process_group is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
                try:
                    process.communicate(timeout=CLOSE_SECONDS)
                except subprocess.TimeoutExpired:
                    if process.stdin is not None:
                        process.stdin.close()
                    if process.stdout is not None:
                        process.stdout.close()
            else:
                process.wait()


def _isolated_main():
    from .config import Settings
    payload = json.load(sys.stdin)
    if payload["method"] not in METHODS:
        raise ValueError("method is not an allowed batch read")
    global CLOSE_SECONDS, REQUEST_SECONDS
    CLOSE_SECONDS = payload["close_seconds"]
    REQUEST_SECONDS = payload["request_seconds"]
    selected = Settings(_env_file=(), **payload["settings"])
    cache = {selected.engine_owner_uid: payload["token"]} if payload["token"] else {}
    from .observability_producers import inherited_context
    metadata = inherited_context()
    diagnostic_context = {key: value for key in ("trace_id", "span_id", "parent_span_id", "run_id", "attempt_id")
                          if (value := observability.diagnostic_id(metadata.get(key))) is not None}
    with (observability.context({**diagnostic_context, "parent_span_id": diagnostic_context.get("span_id"), "span_id": None})
          if diagnostic_context else nullcontext()):
        outcomes = asyncio.run(_read(selected, payload["method"], payload["requests"], payload["request_timeout"],
            payload["batch_timeout"], payload["deadline"], cache, payload.get("deadline_origin", "shared_deadline")))
    rows = {key: {"value": outcome.value, "error": "timeout" if isinstance(outcome.error, TimeoutError)
        else "connection" if isinstance(outcome.error, ConnectionError) else "unavailable" if outcome.error is not None else None, "diagnostic": outcome.diagnostic}
        for key, outcome in outcomes.items()}
    print(json.dumps({"outcomes": rows, "token": cache.get(selected.engine_owner_uid)}))
