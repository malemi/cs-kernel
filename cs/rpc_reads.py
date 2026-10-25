"""Bounded multiplexed reads with explicit per-key unavailable outcomes."""
from __future__ import annotations

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


async def _read(settings, method, requests, request_timeout, batch_timeout, deadline, token_cache=None):
    limit = min(time.monotonic() + batch_timeout, deadline - 2 * CLOSE_SECONDS) if deadline is not None else time.monotonic() + batch_timeout
    outcomes = {key: ReadOutcome(error=TimeoutError("read batch incomplete")) for key in requests}
    if not requests or time.monotonic() >= limit:
        return outcomes
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
            bound = min(request_timeout, REQUEST_SECONDS, limit - time.monotonic())
            if bound <= 0:
                return
            try:
                value = await asyncio.wait_for(client.call(method, params, timeout=bound), bound)
                outcomes[key] = ReadOutcome(value=value)
            except Exception as exc:
                outcomes[key] = ReadOutcome(error=exc)
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
        outcomes = {key: ReadOutcome(error=exc) for key in requests}
    finally:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        if client is not None:
            await _close(client)
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
    limit = min(time.monotonic() + batch_timeout, deadline) if deadline is not None else time.monotonic() + batch_timeout
    outcomes = {key: ReadOutcome(error=TimeoutError("read capacity deferred: deadline")) for key in requests}
    if not requests or time.monotonic() >= limit - 2 * CLOSE_SECONDS:
        return outcomes
    process = None
    try:
        token = (token_cache or {}).get(settings.engine_owner_uid)
        payload = json.dumps({"settings": settings.model_dump(mode="json"), "method": method,
            "requests": requests, "request_timeout": request_timeout, "batch_timeout": batch_timeout,
            "deadline": limit - 2 * CLOSE_SECONDS, "token": token if _cacheable(token, limit - time.monotonic()) else None,
            "close_seconds": CLOSE_SECONDS, "request_seconds": request_timeout}).encode()
        process = subprocess.Popen(READ_COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=owned_process_group is None)
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
            if not isinstance(row, dict) or set(row) != {"value", "error"} or row["error"] not in {None, "timeout", "connection", "unavailable"}:
                raise ValueError("read worker outcome is invalid")
            error = {"timeout": TimeoutError, "connection": ConnectionError, "unavailable": RuntimeError}.get(row["error"])
            decoded[key] = ReadOutcome(value=row["value"], error=error("bounded read unavailable") if error else None)
        if token_cache is not None and _cacheable(result["token"], limit - time.monotonic()):
            token_cache[settings.engine_owner_uid] = result["token"]
        return {key: decoded[key] for key in requests}
    except subprocess.TimeoutExpired:
        return outcomes
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
    outcomes = asyncio.run(_read(selected, payload["method"], payload["requests"], payload["request_timeout"],
        payload["batch_timeout"], payload["deadline"], cache))
    rows = {key: {"value": outcome.value, "error": "timeout" if isinstance(outcome.error, TimeoutError)
        else "connection" if isinstance(outcome.error, ConnectionError) else "unavailable" if outcome.error is not None else None}
        for key, outcome in outcomes.items()}
    print(json.dumps({"outcomes": rows, "token": cache.get(selected.engine_owner_uid)}))
