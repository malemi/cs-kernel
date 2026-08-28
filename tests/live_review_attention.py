#!/usr/bin/env python3
"""Opt-in semantic replay for the `/cs-review` attention contract.

Runs Claude with zero tools, no persisted session, structured output, and a
bounded budget. This is deliberately outside ``tests/run.sh``: it spends money
and needs a signed-in Claude CLI. The hermetic gate validates the same shared
contract on every run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = (
    ROOT / "cs" / "templates" / "partials" / "review-attention-contract.md.j2"
)
FIXTURE = ROOT / "tests" / "fixtures" / "review_attention_cases.json"
LABELS = ["act_now", "waiting_external", "informational", "stale", "uncertain"]


def schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "verdict": {"type": "string", "enum": LABELS},
                        "reason": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["id", "verdict", "reason", "evidence"],
                },
            }
        },
        "required": ["decisions"],
    }


def structured(envelope: dict) -> dict:
    if isinstance(envelope.get("structured_output"), dict):
        return envelope["structured_output"]
    if "decisions" in envelope:
        return envelope
    raw = envelope.get("result")
    if isinstance(raw, str):
        return json.loads(raw)
    raise ValueError(f"Claude returned no structured output: keys={sorted(envelope)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="opus")
    ap.add_argument("--max-budget-usd", type=float, default=0.50)
    args = ap.parse_args()

    cases = json.loads(FIXTURE.read_text())
    prompt = (
        "Classify every candidate below using the decision contract. "
        "Return one decision per id and no extra ids. The supplied "
        "current_evidence is the complete current conversation evidence for "
        "this replay.\n\nCANDIDATES:\n"
        + json.dumps(cases, indent=2)
    )
    cmd = [
        "claude", "-p", "--safe-mode", "--tools", "",
        "--no-session-persistence", "--output-format", "json",
        "--json-schema", json.dumps(schema(), separators=(",", ":")),
        "--model", args.model, "--effort", "high",
        "--max-budget-usd", str(args.max_budget_usd),
        "--system-prompt", CONTRACT.read_text(), prompt,
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        return proc.returncode or 1
    try:
        data = structured(json.loads(proc.stdout))
    except Exception as exc:  # noqa: BLE001 — report the provider envelope
        print(f"invalid Claude output: {exc}\n{proc.stdout[:2000]}", file=sys.stderr)
        return 1

    rows = data.get("decisions") or []
    got: dict[str, dict] = {}
    duplicate = set()
    for row in rows:
        rid = row.get("id")
        if rid in got:
            duplicate.add(rid)
        got[rid] = row
    expected = {row["id"]: row["expected"] for row in cases}
    failures = []
    if duplicate:
        failures.append(f"duplicate ids: {sorted(duplicate)}")
    if set(got) != set(expected):
        failures.append(
            f"id mismatch: missing={sorted(set(expected) - set(got))}, "
            f"extra={sorted(set(got) - set(expected))}"
        )
    for rid, gold in expected.items():
        actual = (got.get(rid) or {}).get("verdict")
        if actual != gold:
            failures.append(f"{rid}: expected {gold}, got {actual}")

    print(f"model: {args.model}")
    for rid in expected:
        row = got.get(rid) or {}
        print(f"  {rid:28} {row.get('verdict', 'MISSING'):18} {row.get('reason', '')}")
    if failures:
        print("LIVE REVIEW ATTENTION: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(f"LIVE REVIEW ATTENTION: PASS ({len(expected)}/{len(expected)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
