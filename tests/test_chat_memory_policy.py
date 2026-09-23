#!/usr/bin/env python3
"""The kernel's memory posture: read-only asks, and no standing memory grants.

Two separate guarantees, both about what a headless clone may cause to happen to
company memory.

``cs ask`` negotiates a server-enforced read-only policy, so a read cannot become
a write by the engine choosing to route it through a mutating tool.

``cs chat --allow`` may grant tools, and it answers every
``chat.pending_approval`` for a granted name — that is what ``--allow`` means,
and it is all it means: it never asks for a session grant, and nothing on this
side writes memory on its own.
"""

from __future__ import annotations

import asyncio
import inspect
import types
from unittest.mock import patch

from cs import cli, rpc


class FakeClient:
    instances = []
    capability = {"chat_read_only_policy": 1}

    def __init__(self, settings, **kwargs):
        self.calls = []
        self.notifications = []
        self.__class__.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def call(self, method, params=None, timeout=60):
        self.calls.append((method, params or {}, timeout))
        if method == "system.capabilities":
            return self.capability
        return {"response": "read result"}


def test_read_only_chat_negotiates_before_sending_policy():
    FakeClient.instances.clear()
    with patch.object(rpc, "EngineClient", FakeClient):
        out = asyncio.run(rpc.chat(types.SimpleNamespace(), "search memory", read_only=True))
    calls = FakeClient.instances[-1].calls
    assert [call[0] for call in calls] == ["system.capabilities", "chat.send"], calls
    payload = calls[1][1]
    assert payload["mutation_policy"] == "read_only"
    assert payload["policy_version"] == 1
    assert out["result"]["response"] == "read result"


def test_old_engine_is_refused_before_chat_send():
    FakeClient.instances.clear()
    FakeClient.capability = {}
    try:
        with patch.object(rpc, "EngineClient", FakeClient):
            asyncio.run(rpc.chat(types.SimpleNamespace(), "search memory", read_only=True))
    except RuntimeError as exc:
        assert "read-only chat policy version 1" in str(exc)
    else:
        raise AssertionError("an engine without the read-only capability was accepted")
    assert [call[0] for call in FakeClient.instances[-1].calls] == ["system.capabilities"]
    FakeClient.capability = {"chat_read_only_policy": 1}


def test_cmd_ask_requests_read_only_policy():
    seen = {}

    async def fake_chat(settings, message, **kwargs):
        seen.update(kwargs)
        return {"result": {"response": "ok"}, "approvals": [], "notifications": []}

    args = types.SimpleNamespace(question="find it", timeout=12)
    with patch.object(cli.config, "load", return_value=types.SimpleNamespace()), patch.object(
        cli.rpc, "chat", fake_chat
    ):
        assert cli.cmd_ask(args) == 0
    assert seen["read_only"] is True
    assert seen["allow_tools"] == set()


def test_supervised_chat_does_not_claim_read_only():
    source = inspect.getsource(cli.cmd_chat)
    assert "read_only=True" not in source


# ─── --allow answers by name, once, and asks for nothing more ─────────


class NotifyingClient(FakeClient):
    """An engine that raises approval notifications while ``chat.send`` runs."""

    notify_with: list = []

    async def call(self, method, params=None, timeout=60):
        self.calls.append((method, params or {}, timeout))
        if method == "system.capabilities":
            return self.capability
        if method == "chat.send":
            for notification in self.notify_with:
                await self._on_notification("chat.pending_approval", notification)
            return {"response": "done"}
        return {"ok": True}

    def __init__(self, settings, **kwargs):
        super().__init__(settings, **kwargs)
        self._on_notification = kwargs.get("on_notification")


def approvals_for(notifications, allow):
    NotifyingClient.instances.clear()
    NotifyingClient.notify_with = notifications
    with patch.object(rpc, "EngineClient", NotifyingClient):
        out = asyncio.run(
            rpc.chat(types.SimpleNamespace(), "correggi la memoria", allow_tools=allow)
        )
    return out, NotifyingClient.instances[-1]


def test_an_allowed_tool_is_still_approved_once():
    """The guard below is about one name, not about disabling ``--allow``."""
    out, client = approvals_for(
        [{"name": "update_memory", "tool_use_id": "tu-1", "input": {"blob_id": "b1"}}],
        {"update_memory"},
    )
    assert out["approvals"] == [
        {"tool": "update_memory", "mode": "once", "input": {"blob_id": "b1"}}
    ]
    approve = [c for c in client.calls if c[0] == "chat.approve"]
    assert approve[0][1] == {"tool_use_id": "tu-1", "mode": "once"}


def test_the_kernel_never_asks_for_a_session_grant():
    """The kernel answers each notification on its own; a standing yes would
    outlive the turn it was given in."""
    source = inspect.getsource(rpc.chat)
    assert '"session"' not in source
    assert "'session'" not in source


if __name__ == "__main__":
    test_read_only_chat_negotiates_before_sending_policy()
    test_old_engine_is_refused_before_chat_send()
    test_cmd_ask_requests_read_only_policy()
    test_supervised_chat_does_not_claim_read_only()
    test_an_allowed_tool_is_still_approved_once()
    test_the_kernel_never_asks_for_a_session_grant()
    print("OK: cs ask negotiates the read-only policy; --allow grants by name, once")
