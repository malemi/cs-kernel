#!/usr/bin/env python3
"""Regression guard: `cs draft-reply` MUST mirror the engine-composed draft into
the operator's Gmail Drafts.

The engine's compose auto-runs create_draft (non-destructive → not gated by the
empty allow_tools), storing the draft in the ENGINE draft store — which is NOT
the operator's Gmail Drafts, the surface where review and sending actually
happen. If cmd_draft_reply does not APPEND the composed draft into Gmail Drafts,
the draft is invisible in Gmail and the operator (rightly) concludes "nothing was
drafted". That regression has recurred repeatedly; this test fails the moment the
append is removed.

We stub the engine RPC (chat + drafts.list) and the IMAP append, then assert
cmd_draft_reply appends the FRESHLY composed draft (the one that appeared after
the compose call) with its real to/subject/body/threading fields.
"""
from __future__ import annotations

import asyncio
import types

from cs import cli, config as cfg, rpc, gmail_drafts

OLD = {
    "id": "old-0", "to_addresses": ["stale@example.com"], "subject": "vecchia",
    "body": "vecchio corpo", "created_at": "2026-01-01T00:00:00",
}
FRESH = {
    "id": "new-1", "to_addresses": ["cliente@example.com"],
    "cc_addresses": [], "subject": "Re: Domanda",
    "body": "Corpo della bozza composta dall'engine.",
    "in_reply_to": "<abc@example.com>", "references": ["<abc@example.com>"],
    "created_at": "2026-07-16T18:00:00",
}


def run() -> None:
    calls = {"list": 0}
    appended: dict = {}

    def fake_call_sync(settings, method, params, timeout=None):
        assert method == "drafts.list", method
        calls["list"] += 1
        # 1st call = BEFORE compose (only the stale draft); 2nd = AFTER (stale + fresh)
        return [OLD] if calls["list"] == 1 else [OLD, FRESH]

    async def fake_chat(settings, message, *, allow_tools=None, timeout=600,
                        echo=print, conversation_id=None):
        # draft-reply must be structurally send-incapable: empty allow set.
        assert allow_tools == set(), f"draft-reply must pass allow_tools=set(), got {allow_tools!r}"
        return {"result": {"response": "composed"}, "approvals": [], "notifications": []}

    def fake_append(settings, to, subject, body, in_reply_to=None,
                    references=None, html=None, cc=None, body_md=False):
        appended.update(to=to, subject=subject, body=body,
                        in_reply_to=in_reply_to, references=references, body_md=body_md)
        return "[Gmail]/Drafts", []

    cfg.load = lambda: types.SimpleNamespace()          # settings unused by stubs
    rpc.call_sync = fake_call_sync
    rpc.chat = fake_chat
    gmail_drafts.append_draft = fake_append

    args = types.SimpleNamespace(message="componi una risposta", timeout=30)
    rc = cli.cmd_draft_reply(args)

    assert rc == 0, f"cmd_draft_reply returned {rc}"
    assert appended, "cmd_draft_reply did NOT append to Gmail Drafts — the regression is back"
    assert appended["to"] == "cliente@example.com", appended        # the FRESH draft, not OLD
    assert appended["subject"] == "Re: Domanda", appended
    assert appended["body"] == "Corpo della bozza composta dall'engine.", appended
    assert appended["in_reply_to"] == "<abc@example.com>", appended
    assert appended["references"] == ["<abc@example.com>"], appended
    # The engine's composed body is always model output — draft-reply must mark
    # it body_md=True so send_guard's deterministic tells run (warn, never
    # block) on the Gmail-draft path. See cs/gmail_drafts.py + cs/send_guard.py.
    assert appended["body_md"] is True, appended
    print("OK: draft-reply mirrors the freshly composed engine draft into Gmail Drafts")


if __name__ == "__main__":
    run()
