#!/usr/bin/env python3
"""The kernel negotiates and sends an engine-enforced read-only ask policy."""

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


if __name__ == "__main__":
    test_read_only_chat_negotiates_before_sending_policy()
    test_old_engine_is_refused_before_chat_send()
    test_cmd_ask_requests_read_only_policy()
    test_supervised_chat_does_not_claim_read_only()
    print("OK: cs ask negotiates and sends the engine read-only policy; supervised chat does not")
