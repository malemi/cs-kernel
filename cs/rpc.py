"""JSON-RPC 2.0 client for the mrcall-desktop engine daemon.

Transport: one JSON object per WebSocket TEXT message, against
``wss://<host>/ws/<uid>`` (Caddy routes to the per-uid unix socket).
The handshake carries ``Authorization: Bearer <firebase-id-token>``;
the daemon verifies RS256 and gates ``token.sub == OWNER_ID``.

A background receive task routes responses to per-id futures and
collects server notifications (frames without ``id``), so a second
call (e.g. ``chat.approve``) can be issued while a long-running one
(``chat.send``) is still in flight — that is how the engine's
approval gate works.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

import websockets

from . import auth
from .config import Settings

if TYPE_CHECKING:  # import cycle: model_config imports config, config imports nothing
    from .model_config import Role

NotifyHandler = Callable[[str, Any], Optional[Awaitable[None]]]


class EngineError(RuntimeError):
    """JSON-RPC error response from the engine."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"engine error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class EngineClient:
    def __init__(
        self,
        settings: Settings,
        on_notification: NotifyHandler | None = None,
        id_token: str | None = None,
    ):
        self.settings = settings
        self.on_notification = on_notification
        # A caller that already holds a valid ID token passes it here instead
        # of letting `auth.get_id_token` read the clone's stored session —
        # `cs init` is the case: it has a descriptor's refresh token in hand
        # and no state dir written yet, and a wizard the operator may still
        # cancel must not leave a session file behind.
        self._id_token = id_token
        self.notifications: list[dict] = []
        self._ws = None
        self._recv_task: asyncio.Task | None = None
        self._pending: dict[Any, asyncio.Future] = {}
        self._handlers: set[asyncio.Task] = set()
        self._ids = itertools.count(1)

    @property
    def url(self) -> str:
        base = self.settings.engine_ws_url.rstrip("/")
        if not base:
            raise RuntimeError(
                "engine_ws_url not configured — set [engine].ws_url in manifest.toml"
            )
        return f"{base}/ws/{self.settings.engine_owner_uid}"

    async def __aenter__(self) -> "EngineClient":
        token = self._id_token or auth.get_id_token(self.settings)
        self._ws = await websockets.connect(
            self.url,
            additional_headers={"Authorization": f"Bearer {token}"},
            max_size=32 * 1024 * 1024,  # email bodies / search results can be large
            open_timeout=30,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        return self

    async def __aexit__(self, *exc) -> None:
        if self._recv_task:
            self._recv_task.cancel()
        for t in list(self._handlers):
            t.cancel()
        if self._ws:
            await self._ws.close()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()

    async def _recv_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    frame = json.loads(raw)
                except ValueError:
                    continue
                if frame.get("id") is not None and (
                    "result" in frame or "error" in frame
                ):
                    fut = self._pending.pop(frame["id"], None)
                    if fut and not fut.done():
                        if "error" in frame:
                            e = frame["error"] or {}
                            fut.set_exception(
                                EngineError(
                                    e.get("code", -1), e.get("message", ""), e.get("data")
                                )
                            )
                        else:
                            fut.set_result(frame.get("result"))
                else:  # notification
                    method = frame.get("method", "")
                    params = frame.get("params")
                    self.notifications.append({"method": method, "params": params})
                    if self.on_notification:
                        out = self.on_notification(method, params)
                        if asyncio.iscoroutine(out):
                            # NEVER await a handler inline. This task is the only
                            # consumer of the socket, and the approval handler
                            # answers a notification by issuing `chat.approve` —
                            # whose response only THIS loop can deliver. Awaiting
                            # here deadlocks: the approve request goes out, the
                            # engine really does run the tool, and every frame
                            # after it is buffered and never dispatched, so the
                            # caller hangs until something kills it.
                            t = asyncio.create_task(out)
                            self._handlers.add(t)
                            t.add_done_callback(self._handler_done)
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            self._fail_pending(ConnectionError("engine connection closed"))
        except Exception as exc:  # noqa: BLE001
            # The receive task must never die quietly: whatever killed it, every
            # caller waiting on a future is now waiting on a loop that will never
            # answer. Surfacing the real exception turns a silent hang into a
            # failure the caller can log and retry.
            self._fail_pending(exc)

    def _handler_done(self, task: asyncio.Task) -> None:
        """Retire a finished notification handler, loudly if it failed.

        A fire-and-forget task whose exception nobody retrieves is reported by
        asyncio only at garbage-collection time, long after the run it belongs
        to. An approval that failed to reach the engine is exactly the kind of
        thing that must not be discovered that way.
        """
        self._handlers.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            import sys

            sys.stderr.write(f"[rpc] notification handler failed: {exc!r}\n")

    def _fail_pending(self, exc: BaseException) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)

    async def call(self, method: str, params: dict | None = None, timeout: float = 60) -> Any:
        rid = next(self._ids)
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        await self._ws.send(
            json.dumps(
                {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
            )
        )
        return await asyncio.wait_for(fut, timeout=timeout)


def call_sync(
    settings: Settings,
    method: str,
    params: dict | None = None,
    timeout: float = 60,
    id_token: str | None = None,
) -> Any:
    """One-shot convenience for CLI verbs: connect, call, disconnect."""

    async def _run():
        async with EngineClient(settings, id_token=id_token) as c:
            return await c.call(method, params, timeout=timeout)

    return asyncio.run(_run())


async def chat(
    settings: Settings,
    message: str,
    *,
    allow_tools: set[str] | None = None,
    timeout: float = 600,
    echo: Callable[[str], None] = print,
    conversation_id: str | None = None,
    role: "Role | None" = None,
) -> Any:
    """Run one engine-chat turn with an explicit tool-approval policy.

    **Routing.** Passing ``role=`` declares this call to be mechanical kernel
    work — a classification, an extraction — rather than generation a customer
    will read. Such a call MAY be served directly by the configured provider
    instead of the engine, which is what makes a cheap model reachable without
    routing customer-facing prose through it. It only happens when the clone
    has opted in with ``CS_LLM_ROUTE=direct``; without a role, or without the
    opt-in, the call goes to the engine exactly as before.

    The role has to be declared by the CALLER, and an empty ``allow_tools`` is
    deliberately NOT used as the signal, because it does not carry the meaning
    one would hope: ``cs draft-reply`` and a campaign's reply-composer also run
    with an empty allow-list, and they write the words a customer reads.
    Inferring "safe to route" from tool-freedom would send exactly the traffic
    the charter keeps on the engine (policy, voice and signature live in the
    engine's ``USER_NOTES``, outside every repo) to whatever model is cheapest.

    Two semantics differ from the engine path, on purpose:

    * ``timeout`` is per ATTEMPT, not overall — the worker client retries
      transient failures (SDK default, 2 retries), so the worst case is ~3×
      the given timeout. The engine path treats it as one overall budget.
    * Errors are LOUD: a truncated answer, a configuration mismatch or an
      exhausted retry raises out of this call rather than silently falling
      back to the engine. A fallback would hide a broken provider config
      behind the very spend this path exists to avoid; the caller (or the
      operator, via ``CS_LLM_ROUTE=engine``) decides what degradation means.

    The engine pauses on destructive tools (send_email, update_memory, …)
    and emits ``chat.pending_approval``; we approve a tool only if it is in
    ``allow_tools``, otherwise we deny and the engine LLM continues without
    it. Non-destructive tools (search, compose, create_draft) auto-execute
    engine-side and never reach this gate.

    Each call gets a UNIQUE ``conversation_id`` by default. The engine's
    busy-guard is per conversation_id, defaulting to "general"; if every cs
    one-shot used "general" they would share one lane, and an interrupted
    call (or a parallel session) leaving "general" occupied would make every
    later call fail ``ChatBusyError``. A fresh id per one-shot isolates us.
    """
    import uuid

    from . import model_config

    if role is not None and model_config.route_direct():
        from . import worker_llm

        # to_thread, not a bare call: worker_llm uses the SYNCHRONOUS anthropic
        # client, and blocking this loop would stall any concurrent engine work
        # a caller has in flight.
        done = await asyncio.to_thread(worker_llm.call, message, role=role,
                                       timeout=timeout)
        echo(f"[direct] {done.model} {done.output_tokens}t "
             f"{done.latency_ms:.0f}ms"
             + (f" ${done.cost_usd:.6f}" if done.cost_usd is not None else ""))
        # The engine's response shape, kept verbatim: callers read
        # result["response"], and a router that changes the contract is a
        # router every call site has to be taught about.
        return {"result": {"response": done.text}, "approvals": [],
                "notifications": []}

    allow = allow_tools or set()
    conv = conversation_id or f"cs-{uuid.uuid4().hex[:16]}"
    client: EngineClient | None = None
    approvals: list[dict] = []

    async def on_notify(method: str, params: Any) -> None:
        if method != "chat.pending_approval":
            return
        p = params or {}
        tool = p.get("tool_name") or p.get("name") or ""
        tool_use_id = p.get("tool_use_id")
        mode = "once" if tool in allow else "deny"
        approvals.append({"tool": tool, "mode": mode, "input": p.get("input")})
        echo(f"[approval] {tool} -> {mode}")
        await client.call("chat.approve", {"tool_use_id": tool_use_id, "mode": mode})

    async with EngineClient(settings, on_notification=on_notify) as c:
        client = c
        result = await c.call(
            "chat.send", {"message": message, "conversation_id": conv}, timeout=timeout
        )
        return {"result": result, "approvals": approvals, "notifications": c.notifications}
