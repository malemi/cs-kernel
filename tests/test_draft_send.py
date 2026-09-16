#!/usr/bin/env python3
"""The interactive contextual-send verb names, gates and verifies one draft."""
from __future__ import annotations

import contextlib
import asyncio
import io
import types

from cs import cli, config as cfg, rpc


DRAFT_ID = "452ddb83-69c9-479c-98ab-b6f690eab2a7"
DRAFT = {
    "id": DRAFT_ID,
    "status": "draft",
    "to_addresses": ["james@example.test"],
    "subject": "Re: Specialty coffee",
}


def run_case(*, approval_input=None, approvals=True, final_status="sent",
             engine_error=None):
    calls = []

    def fake_call_sync(settings, method, params, timeout=None):
        assert method == "drafts.list", method
        status = params.get("status") or "draft"
        calls.append(status)
        if len(calls) == 1:
            assert status == "draft"
            return [DRAFT]
        return [dict(DRAFT, status=status)] if status == final_status else []

    async def fake_chat(settings, message, *, allow_tools=None, timeout=600,
                        echo=print, conversation_id=None, role=None,
                        approval_predicate=None):
        assert allow_tools == {"send_draft"}
        assert DRAFT_ID in message
        supplied = approval_input if approval_input is not None else {"draft_id": DRAFT_ID}
        mode = "once" if approval_predicate("send_draft", supplied) else "deny"
        rows = ([{"tool": "send_draft", "mode": mode, "input": supplied}]
                if approvals else [])
        metadata = ({"error": engine_error, "error_detail": "boom"}
                    if engine_error else {})
        return {"result": {"response": "done", "metadata": metadata},
                "approvals": rows, "notifications": []}

    cfg.load = lambda: types.SimpleNamespace()
    rpc.call_sync = fake_call_sync
    rpc.chat = fake_chat
    args = types.SimpleNamespace(draft_id=DRAFT_ID, timeout=30)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = cli.cmd_draft_send(args)
    return rc, err.getvalue(), calls


def main():
    real_chat = rpc.chat
    rc, err, calls = run_case()
    assert rc == 0, (rc, err)
    assert calls == ["draft", "sent"], calls

    rc, err, _ = run_case(approval_input={"draft_id": "wrong-id"})
    assert rc == 1 and "nothing was approved" in err, (rc, err)

    rc, err, _ = run_case(approvals=False)
    assert rc == 1 and "nothing was approved" in err, (rc, err)

    rc, err, _ = run_case(engine_error="INTERNAL_ERROR")
    assert rc == 4 and "engine error" in err, (rc, err)

    rc, err, calls = run_case(final_status="sending")
    assert rc == 5 and "Delivery is uncertain" in err, (rc, err)
    assert calls == ["draft", "sent", "draft", "sending", "failed"], calls

    # Exact ids only: a prefix never reaches chat.
    cfg.load = lambda: types.SimpleNamespace()
    rpc.call_sync = lambda *a, **k: [DRAFT]
    args = types.SimpleNamespace(draft_id=DRAFT_ID[:8], timeout=30)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = cli.cmd_draft_send(args)
    assert rc == 1 and "nothing was sent" in err.getvalue(), (rc, err.getvalue())

    # Exercise the real rpc.chat callback too: the predicate must control the
    # mode sent back to the engine, not merely be passed around by the CLI.
    real_client = rpc.EngineClient
    rpc.chat = real_chat
    approved = []

    class FakeClient:
        def __init__(self, settings, on_notification=None):
            self.on_notification = on_notification
            self.notifications = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def call(self, method, params=None, timeout=60):
            if method == "chat.send":
                for supplied in (
                    {"draft_id": "wrong-id"},
                    {"draft_id": DRAFT_ID},
                    {"draft_id": DRAFT_ID},
                ):
                    await self.on_notification(
                        "chat.pending_approval",
                        {"tool_name": "send_draft", "tool_use_id": supplied["draft_id"],
                         "input": supplied},
                    )
                return {"response": "done"}
            assert method == "chat.approve"
            approved.append(params)
            return {"ok": True}

    rpc.EngineClient = FakeClient
    exact_seen = False

    def approve_one_exact(tool, data):
        nonlocal exact_seen
        exact = tool == "send_draft" and data.get("draft_id") == DRAFT_ID
        if not exact or exact_seen:
            return False
        exact_seen = True
        return True

    try:
        out = asyncio.run(rpc.chat(
            types.SimpleNamespace(), "send exact", allow_tools={"send_draft"},
            approval_predicate=approve_one_exact,
        ))
    finally:
        rpc.EngineClient = real_client
    assert [a["mode"] for a in approved] == ["deny", "once", "deny"], approved
    assert [a["mode"] for a in out["approvals"]] == ["deny", "once", "deny"], out
    print("OK: draft-send approves and verifies one exact engine draft")


if __name__ == "__main__":
    main()
