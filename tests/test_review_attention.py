#!/usr/bin/env python3
"""Attention-agenda evidence shapes and rendered decision contract.

Hermetic: no engine, mailbox, provider, or Claude process.
"""
from __future__ import annotations

import io
import json
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cs import cli, review, unanswered  # noqa: E402
from cs.project_init import build_jinja_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "cs" / "templates" / "project"
FIXTURE = ROOT / "tests" / "fixtures" / "review_attention_cases.json"
fails = 0


def check(cond, msg: str) -> None:
    global fails
    if not cond:
        print(f"  FAIL: {msg}")
        fails += 1


def capture(fn) -> object:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn()
    check(rc == 0, f"command exits zero, got {rc}")
    return json.loads(buf.getvalue())


def test_task_evidence() -> None:
    raw = {
        "id": "task-123",
        "contact_email": "person@example.test",
        "title": "Answer current question",
        "summary": "fallback",
        "urgency": "high",
        "reason": "A direct question is unanswered.",
        "suggested_action": "Reply with the confirmed production date.",
        "created_at": "2026-08-27T10:00:00Z",
        "analyzed_at": "2026-08-28T08:00:00Z",
        "sources": {"thread_id": "thread-1", "emails": ["mail-1"]},
    }
    row = review._task_row(raw)
    for key in ("id", "email", "title", "urgency", "reason",
                "suggested_action", "created_at", "analyzed_at", "sources"):
        check(key in row, f"review JSON task evidence keeps {key}")
    check(row["email"] == raw["contact_email"], "task identity is normalized")


def test_unanswered_all_buckets() -> None:
    base = {
        "open": [{"email": "open@example.test", "thread_key": "open-1"}],
        "handled": [{"email": "done@example.test"}],
        "escalated": [{"email": "mine@example.test"}],
        "resumed": [{"email": "again@example.test", "thread_key": "again-1"}],
        "automatic": [{"email": "robot@example.test"}],
        "courtesy": [{"email": "thanks@example.test"}],
        "note": "engine note",
    }
    orig_load, orig_sweep, orig_crm = (
        cli.config.load, unanswered.sweep, unanswered.crm_annotate)
    cli.config.load = lambda: types.SimpleNamespace()
    unanswered.sweep = lambda _settings, days: json.loads(json.dumps(base))

    def annotate(_settings, rows):
        rows[0]["crm_known"] = True
        rows[0]["crm"] = "ACTIVE"
        return "crm note"

    unanswered.crm_annotate = annotate
    try:
        detailed = capture(lambda: cli.cmd_unanswered(types.SimpleNamespace(
            days=45, json=True, crm=True, all_buckets=True)))
        legacy = capture(lambda: cli.cmd_unanswered(types.SimpleNamespace(
            days=45, json=True, crm=False, all_buckets=False)))
    finally:
        cli.config.load, unanswered.sweep, unanswered.crm_annotate = (
            orig_load, orig_sweep, orig_crm)

    for key in ("open", "handled", "escalated", "resumed", "automatic",
                "courtesy", "note", "crm_note"):
        check(key in detailed, f"detailed unanswered JSON keeps {key}")
    check(detailed["open"][0]["crm"] == "ACTIVE",
          "CRM evidence stays on detailed open rows")
    check(legacy == base["open"], "bare --json remains the legacy open list")


def test_full_thread_messages() -> None:
    summaries = [
        {"thread_id": "thread-1", "subject": "One"},
        {"thread_id": "thread-2", "subject": "Two"},
    ]
    orig_load, orig_threads, orig_rpc = cli.config.load, cli._threads_for, cli.rpc.call_sync
    cli.config.load = lambda: types.SimpleNamespace()
    cli._threads_for = lambda _settings, _email, _limit: list(summaries)

    def call(_settings, method, params, **_kwargs):
        check(method == "emails.list_by_thread", "full thread uses the full-message RPC")
        return {"emails": [{"id": f"mail-{params['thread_id']}",
                            "thread_id": params["thread_id"], "body_plain": "Full body"}]}

    cli.rpc.call_sync = call
    try:
        full = capture(lambda: cli.cmd_thread(types.SimpleNamespace(
            email="person@example.test", limit=50, json=True, full=True)))
        legacy = capture(lambda: cli.cmd_thread(types.SimpleNamespace(
            email="person@example.test", limit=50, json=True, full=False)))
    finally:
        cli.config.load, cli._threads_for, cli.rpc.call_sync = orig_load, orig_threads, orig_rpc

    check(all(t.get("emails") and t["emails"][0]["body_plain"] == "Full body"
              for t in full), "--full carries chronological full messages")
    check(legacy == summaries, "bare thread --json remains the summary list")


def test_detailed_flags_require_json_before_reads() -> None:
    orig_load = cli.config.load

    def unexpected_load():
        raise AssertionError("invalid detailed flag must fail before config/network reads")

    cli.config.load = unexpected_load
    try:
        thread_rc = cli.cmd_thread(types.SimpleNamespace(
            email="person@example.test", limit=50, json=False, full=True))
        unanswered_rc = cli.cmd_unanswered(types.SimpleNamespace(
            days=45, json=False, crm=False, all_buckets=True))
    finally:
        cli.config.load = orig_load
    check(thread_rc == 2, "thread --full requires --json without doing I/O")
    check(unanswered_rc == 2,
          "unanswered --all-buckets requires --json without doing I/O")


def test_rendered_contract() -> None:
    partial = TPL.parent / "partials" / "review-attention-contract.md.j2"
    check(partial.exists(), "one shared attention contract partial exists")
    if not partial.exists():
        return
    contract = partial.read_text()
    for label in ("act_now", "waiting_external", "informational", "stale", "uncertain"):
        check(label in contract, f"attention contract carries {label}")
    for phrase in ("positive evidence", "direct unanswered", "candidate count",
                   "current conversation", "source is evidence"):
        check(phrase.lower() in contract.lower(), f"attention contract requires {phrase}")

    env = build_jinja_env(TPL)
    # Rendering needs a full init context; the existing bootstrap test exercises
    # both variants. Use its neutral fixture rather than grow a second one.
    from test_review_bootstrap import BASE
    rendered = env.get_template(".claude/commands/cs-review.md.j2").render(**BASE)
    for command in ("cs review --json",
                    "cs unanswered --days 45 --crm --json --all-buckets",
                    "cs thread <email> --json --full"):
        check(command in rendered, f"rendered review gathers `{command}`")
    check(rendered.count("review-attention-contract:start") == 1,
          "the rendered command includes exactly one shared decision contract")
    check("End the review after the report" in rendered,
          "the review stops before repair")
    tail = rendered.split("End the review after the report", 1)[-1]
    for mutating in ("cs handled", "cs escalated", "draft-delete", "send_draft"):
        check(mutating not in tail, f"post-report surface contains no {mutating}")


def test_incident_fixture() -> None:
    rows = json.loads(FIXTURE.read_text())
    labels = {"act_now", "waiting_external", "informational", "stale", "uncertain"}
    check(len(rows) == 7, "the incident fixture has all seven gold cases")
    check(len({r["id"] for r in rows}) == len(rows), "fixture ids are unique")
    check(all(r.get("expected") in labels for r in rows), "every gold label is valid")
    check({r["expected"] for r in rows} >= {"act_now", "informational", "stale"},
          "the fixture tests action, noise, and stale state")


test_task_evidence()
test_unanswered_all_buckets()
test_full_thread_messages()
test_detailed_flags_require_json_before_reads()
test_rendered_contract()
test_incident_fixture()

if fails:
    print(f"test_review_attention: {fails} assertion(s) FAILED")
    raise SystemExit(1)
print("test_review_attention: all assertions passed")
