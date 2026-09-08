#!/usr/bin/env python3
"""An engine failure inside a successful JSON-RPC envelope is reported, never
silently swallowed as an answer.

`chat.send` can return `result.metadata.error` on an otherwise-successful
JSON-RPC frame: the TRANSPORT succeeded, the ENGINE TURN did not. Every `cs`
verb that reads a `rpc.chat` result used to unwrap only `response` and end
with a hardcoded `return 0` — an outage became fluent assistant prose ("I
encountered an error processing your message: ...") printed to STDOUT with a
SUCCESS exit code, indistinguishable from a real answer both by stream and by
status. That is how a context-overflow outage on the `production@cafe124.it`
engine profile ran for months: the operator's own log recorded the failure in
prose, tick after tick, while every exit code said 0 — nobody escalated it
because the one place a monitor could have caught it told the opposite story.

Fixture: the real captured SHAPE from
`docs/briefs/2026-09-07-engine-error-exit-code.md` — the same keys, at the
same nesting, as an actual `INTERNAL_ERROR` reported inside an otherwise
successful `chat.send` result. The specific error text is genericised here
(this repo is a template stamped into every clone, and ships no real
upstream-provider or hostname literal), but the shape — `response` carrying
fluent prose, `metadata.error` / `metadata.error_detail` carrying the real
verdict — is not invented.

Four properties, and the third is the one this whole fix exists to hold:

  1. A `chat.send` result carrying `metadata.error` makes `cmd_ask`,
     `cmd_chat` and `cmd_draft_reply` all exit NON-ZERO, with `error` /
     `error_detail` on STDERR and nothing on stdout.
  2. A successful turn's STDOUT and exit code are byte-identical to before
     the fix — a real answer is not reshaped by any of this.
  3. Failure is read from `metadata.error` alone. A `response` string
     carrying the SAME "I encountered an error" prose, with no
     `metadata.error` key, is a SUCCESS — proving detection cannot have been
     re-derived from the text of the answer, the second-implementation
     pattern the operator charter bans ("the engine is authoritative for
     what it owns").
  4. `cmd_draft_reply` stops at the failure and never reaches its
     post-compose `drafts.list` diff — a failed turn composed no draft, so
     there is nothing to mirror and nothing to (misleadingly) report as
     "composed no new draft" over a real engine outage.

A test that only asserted "the exit code is non-zero" would still pass a fix
that re-derived failure from the response text — hence property 3, checked
directly against the helper, not inferred from the two verbs that use it.
"""
from __future__ import annotations

import io
import sys
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import cli, config as cfg, rpc  # noqa: E402

# The real captured SHAPE from the brief, with the error text genericised —
# this repo is a template stamped into every clone and carries no real
# upstream-provider name or hostname. The keys and nesting are unchanged:
# `response` is fluent prose an operator could mistake for an answer;
# `metadata.error` / `metadata.error_detail` carry the real verdict.
FAILED_RESULT = {
    "response": "I encountered an error processing your message: upstream "
                "transport error (502): gateway_error: {...}",
    "tool_calls": [],
    "metadata": {
        "execution_time_ms": 912.89,
        "error": "INTERNAL_ERROR",
        "error_detail": "upstream transport error (502): gateway_error: "
                        "{...}",
    },
    "session_id": None,
}


def _failed_envelope() -> dict:
    return {"result": dict(FAILED_RESULT), "approvals": [], "notifications": []}


def _ok_envelope(text: str) -> dict:
    return {
        "result": {
            "response": text, "tool_calls": [],
            "metadata": {"execution_time_ms": 42.0}, "session_id": "s1",
        },
        "approvals": [], "notifications": [],
    }


def _stub_chat(envelope: dict):
    async def fake_chat(settings, message, *, allow_tools=None, timeout=600,
                        echo=print, conversation_id=None):
        return envelope
    return fake_chat


def _install_common_stubs():
    cfg.load = lambda: types.SimpleNamespace()


def test_helper_keys_on_metadata_error_never_on_response_prose():
    """`_chat_engine_error` is the ONLY place success-vs-failure is decided,
    and the captured payload's own text must not be what triggers it."""
    err = io.StringIO()
    with redirect_stderr(err):
        rc = cli._chat_engine_error(FAILED_RESULT)
    assert rc == cli._ENGINE_ERROR_RC, rc
    assert "INTERNAL_ERROR" in err.getvalue(), err.getvalue()
    assert "502" in err.getvalue(), err.getvalue()

    # Same "I encountered an error" prose, but no metadata.error key: a
    # genuine success (e.g. a reply that merely discusses an error) must NOT
    # be flagged, or detection has been re-derived from the text.
    prose_only = {
        "response": FAILED_RESULT["response"],
        "tool_calls": [], "metadata": {"execution_time_ms": 42.0},
        "session_id": "s1",
    }
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        rc2 = cli._chat_engine_error(prose_only)
    assert rc2 is None, (
        f"a response containing the SAME error prose, with no metadata.error, "
        f"was flagged as a failure (rc={rc2}) — detection has been "
        f"re-derived from response TEXT, the pattern CLAUDE.md § 0b bans")

    # The `CS_LLM_ROUTE=direct` path in `rpc.chat` returns `{"response": ...}`
    # with NO `metadata` key at all. That is success too — not a KeyError,
    # not a false failure.
    no_metadata_at_all = {"response": "a normal direct-routed answer"}
    assert cli._chat_engine_error(no_metadata_at_all) is None
    assert cli._chat_engine_error({}) is None
    assert cli._chat_engine_error(None) is None
    print("OK: failure is read from metadata.error alone, never from the "
          "text of response, and a missing metadata key is success")


def test_engine_error_rc_is_distinct_from_mailbox_incomplete_rc():
    """Two different failures, two different codes — a caller must not have
    to guess which one happened from the exit status alone."""
    assert cli._ENGINE_ERROR_RC != cli._INCOMPLETE_RC, (
        f"_ENGINE_ERROR_RC ({cli._ENGINE_ERROR_RC}) collides with "
        f"_INCOMPLETE_RC ({cli._INCOMPLETE_RC}) — a mailbox-read failure and "
        f"an engine-turn failure would be indistinguishable by exit code")
    assert cli._ENGINE_ERROR_RC != 0
    print(f"OK: _ENGINE_ERROR_RC={cli._ENGINE_ERROR_RC} is distinct from "
          f"_INCOMPLETE_RC={cli._INCOMPLETE_RC} and from success (0)")


def test_cmd_ask_fails_loudly_on_the_captured_payload():
    _install_common_stubs()
    rpc.chat = _stub_chat(_failed_envelope())
    args = types.SimpleNamespace(question="what do we know about X?", timeout=30)

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.cmd_ask(args)

    assert rc != 0, "cmd_ask returned 0 on a captured engine-failure payload"
    assert rc == cli._ENGINE_ERROR_RC, rc
    assert out.getvalue() == "", (
        f"the engine error reached STDOUT, where a real answer belongs: "
        f"{out.getvalue()!r}")
    assert "INTERNAL_ERROR" in err.getvalue(), err.getvalue()
    assert "upstream transport error (502)" in err.getvalue(), err.getvalue()
    print(f"OK: cmd_ask exits {rc} and prints the failure to stderr only, "
          "stdout empty")


def test_cmd_ask_success_is_byte_identical_to_before_the_fix():
    _install_common_stubs()
    rpc.chat = _stub_chat(_ok_envelope("the answer, grounded in memory"))
    args = types.SimpleNamespace(question="what do we know about X?", timeout=30)

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.cmd_ask(args)

    assert rc == 0, rc
    assert out.getvalue() == "the answer, grounded in memory\n", out.getvalue()
    assert err.getvalue() == "", err.getvalue()
    print("OK: a successful cmd_ask turn is byte-identical on stdout, rc 0")


def test_cmd_chat_fails_loudly_through_the_same_shared_helper():
    _install_common_stubs()
    rpc.chat = _stub_chat(_failed_envelope())
    args = types.SimpleNamespace(message="hello", allow=None, timeout=30)

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.cmd_chat(args)

    assert rc == cli._ENGINE_ERROR_RC, rc
    assert out.getvalue() == "", out.getvalue()
    assert "INTERNAL_ERROR" in err.getvalue(), err.getvalue()
    print("OK: cmd_chat fails loudly through the same shared helper as cmd_ask")


def test_cmd_draft_reply_fails_loudly_and_skips_the_pointless_mirror_step():
    """A failed turn composed no draft — `cmd_draft_reply` must return at the
    failure, before its post-compose `drafts.list` diff, or it goes on to
    print a SECOND, misleading explanation ("composed no new draft") over the
    real one, and burns a round trip proving something already known."""
    _install_common_stubs()
    rpc.chat = _stub_chat(_failed_envelope())

    list_calls = {"n": 0}

    def fake_call_sync(settings, method, params, timeout=None):
        list_calls["n"] += 1
        assert method == "drafts.list", method
        return []
    rpc.call_sync = fake_call_sync

    args = types.SimpleNamespace(message="reply to the customer", timeout=30)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.cmd_draft_reply(args)

    assert rc == cli._ENGINE_ERROR_RC, rc
    assert out.getvalue() == "", out.getvalue()
    assert "INTERNAL_ERROR" in err.getvalue(), err.getvalue()
    assert "composed no new draft" not in err.getvalue(), (
        "cmd_draft_reply printed the 'nothing to mirror' explanation over a "
        "real engine failure — two disagreeing explanations for one turn:\n"
        + err.getvalue())
    assert list_calls["n"] == 1, (
        f"cmd_draft_reply called drafts.list {list_calls['n']} time(s) after "
        f"a failed turn — expected exactly 1 (the BEFORE snapshot, taken "
        f"ahead of the chat call); the AFTER diff must not run for a turn "
        f"that composed nothing")
    print("OK: cmd_draft_reply fails loudly and never reaches the "
          "drafts.list diff after an engine failure")


def test_cmd_draft_reply_success_is_unchanged():
    """The success path is untouched by the fix: a real compose still mirrors
    into Gmail Drafts exactly as before."""
    from cs import gmail_drafts

    _install_common_stubs()
    fresh = {
        "id": "new-1", "to_addresses": ["customer@example.com"],
        "cc_addresses": [], "subject": "Re: Question",
        "body": "Body of the draft the engine composed.",
        "in_reply_to": "<abc@example.com>", "references": ["<abc@example.com>"],
        "created_at": "2026-07-16T18:00:00",
    }
    calls = {"n": 0}

    def fake_call_sync(settings, method, params, timeout=None):
        assert method == "drafts.list", method
        calls["n"] += 1
        return [] if calls["n"] == 1 else [fresh]
    rpc.call_sync = fake_call_sync
    rpc.chat = _stub_chat(_ok_envelope("composed"))

    appended: dict = {}

    def fake_append(settings, to, subject, body, in_reply_to=None,
                    references=None, html=None, cc=None, body_md=False):
        appended.update(to=to, subject=subject)
        return "[Gmail]/Drafts", []
    gmail_drafts.append_draft = fake_append

    args = types.SimpleNamespace(message="compose a reply", timeout=30)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.cmd_draft_reply(args)

    assert rc == 0, rc
    assert "composed" in out.getvalue(), out.getvalue()
    assert appended.get("to") == "customer@example.com", appended
    print("OK: cmd_draft_reply's success path (mirror into Gmail Drafts) is "
          "unchanged")


if __name__ == "__main__":
    test_helper_keys_on_metadata_error_never_on_response_prose()
    test_engine_error_rc_is_distinct_from_mailbox_incomplete_rc()
    test_cmd_ask_fails_loudly_on_the_captured_payload()
    test_cmd_ask_success_is_byte_identical_to_before_the_fix()
    test_cmd_chat_fails_loudly_through_the_same_shared_helper()
    test_cmd_draft_reply_fails_loudly_and_skips_the_pointless_mirror_step()
    test_cmd_draft_reply_success_is_unchanged()
    print("test_engine_error_exit_code: all assertions passed")
