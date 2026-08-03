#!/usr/bin/env python3
"""Semantic guard: `cs tasks create` / `cs tasks close` write the engine task
ledger with the right params.

`cs tasks` (bare) is the open-task LIST. The two write subactions were added so
the triage sweep can reconcile against the engine ledger: create-on-miss (an
inbound the engine's own detection never turned into a task) and close (mark a
contact handled — possibly answered from a personal mailbox the Sent-anchored
sweep can't see). Both are thin transport over the engine RPCs
`tasks.create` / `tasks.complete`; this test pins the method name + params so a
refactor can't silently drop `sources`, the `event_id` idempotency key, the
close note, or the external operator's audit identity/reason.

We stub `cs.rpc.call_sync` to capture (method, params) and drive the two
cmd_* functions with a fake args Namespace — no engine, no IMAP.
"""
from __future__ import annotations

import types

from cs import cli, config as cfg, rpc


def run() -> None:
    captured: list[tuple] = []

    def fake_call_sync(settings, method, params, timeout=None):
        captured.append((method, params))
        # tasks.create -> {ok, task_id, created}; tasks.complete -> {ok}
        if method == "tasks.create":
            return {"ok": True, "task_id": "t-123", "created": True}
        return {"ok": True}

    cfg.load = lambda: types.SimpleNamespace()   # settings unused by the stub
    rpc.call_sync = fake_call_sync

    # --- create: with a thread-id, sources must carry emails + thread_id ---
    create_args = types.SimpleNamespace(
        email="cliente@example.com",
        title="Richiesta pre-vendita senza risposta",
        event_id="<msg-abc@example.com>",
        event_type="email",
        name="Mario Rossi",
        phone=None,
        urgency="high",
        reason="inbound 8 giorni fa, nessuna risposta",
        suggested_action=None,
        thread_id="thread-42",
        json=False,
    )
    rc = cli.cmd_tasks_create(create_args)
    assert rc == 0, f"cmd_tasks_create returned {rc}"

    assert captured, "cmd_tasks_create did not call the engine"
    method, params = captured[-1]
    assert method == "tasks.create", method
    assert params["contact_email"] == "cliente@example.com", params
    assert params["title"] == "Richiesta pre-vendita senza risposta", params
    assert params["event_id"] == "<msg-abc@example.com>", params
    assert params["sources"] == {
        "emails": ["<msg-abc@example.com>"],
        "thread_id": "thread-42",
    }, params
    assert params["urgency"] == "high", params
    assert params["contact_name"] == "Mario Rossi", params
    assert params["action_required"] is True, params
    # phone/suggested_action were None -> not forwarded
    assert "contact_phone" not in params, params
    assert "suggested_action" not in params, params

    # --- create without a thread-id: sources = emails only ---
    create_args2 = types.SimpleNamespace(
        email="due@example.com", title="Catch", event_id="ev-2",
        event_type="email", name=None, phone=None, urgency="medium",
        reason=None, suggested_action=None, thread_id=None, json=False,
    )
    assert cli.cmd_tasks_create(create_args2) == 0
    _, params2 = captured[-1]
    assert params2["sources"] == {"emails": ["ev-2"]}, params2

    # --- close: forwards task_id + display note + audit identity/reason ---
    close_args = types.SimpleNamespace(
        task_id="t-123", note="risposto da mario.alemi@ personale", json=False
    )
    rc = cli.cmd_tasks_close(close_args)
    assert rc == 0, f"cmd_tasks_close returned {rc}"
    method, params = captured[-1]
    assert method == "tasks.complete", method
    assert params == {
        "task_id": "t-123",
        "actor": "operator",
        "why": "risposto da mario.alemi@ personale",
        "note": "risposto da mario.alemi@ personale",
    }, params

    # --- close without a note: still carries a non-empty audit reason ---
    close_args2 = types.SimpleNamespace(task_id="t-9", note=None, json=False)
    assert cli.cmd_tasks_close(close_args2) == 0
    _, params_c2 = captured[-1]
    assert params_c2 == {
        "task_id": "t-9",
        "actor": "operator",
        "why": "closed by the cs operator via `cs tasks close`",
    }, params_c2

    print("OK: tasks create/close call tasks.create/tasks.complete with the right params")


if __name__ == "__main__":
    run()
