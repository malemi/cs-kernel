---
status: completed
---

# Attention agenda — execution plan

Brief: [`../briefs/2026-08-28-attention-agenda.md`](../briefs/2026-08-28-attention-agenda.md)

## Outcome

`/cs-review` returns a current, evidence-backed agenda rather than a union of
raw drafts, engine tasks, and unanswered-mail candidates. The model already
running the command performs one explicit attention judgement per candidate;
the kernel adds no LLM call and mutates no source state.

## Phase 1 — Preserve evidence needed for judgement

- [x] Extend `cs review --json` task rows to retain stable task identity,
  reason, suggested action, timestamps, and sources instead of only the
  truncated display fields.
- [x] Add backward-compatible `cs unanswered --json --all-buckets`, returning
  returns every bucket (`open`, `resumed`, `automatic`, `courtesy`, `handled`,
  `escalated`, and degradation notes). Keep bare `--json` as the existing open
  list consumed by autonomous triage.
- [x] Add backward-compatible `cs thread --json --full`, which
  resolves each search summary through `emails.list_by_thread`. Search results
  alone are thread summaries and are not sufficient evidence for attention
  judgement.
- [x] Keep the human renderer compact and backward-compatible; added JSON
  fields must not expand its task table.
- [x] Add hermetic assertions for all three enriched JSON shapes.

Verification:

```bash
python3 tests/test_review_bootstrap.py
```

## Phase 2 — Replace transcription with attention adjudication

- [x] Put the verdict vocabulary, positive-evidence rule, and output invariants
  in one Jinja partial shared by the rendered command and the live replay; no
  second copy of the judgement prompt may drift.
- [x] Rewrite the kernel-owned
  `cs/templates/project/.claude/commands/cs-review.md.j2` so it gathers
  `cs review --json` and
  `cs unanswered --days 45 --crm --json --all-buckets`.
- [x] Build one candidate set keyed by conversation/task/draft identity; merge
  duplicate evidence for the same item without collapsing two distinct
  conversations merely because they share an address. Provenance can contain
  `task`, `unanswered`, and/or `draft`.
- [x] Require `cs thread <email> --json --full` for every email candidate before a
  verdict. A candidate without a resolvable conversation must become
  `uncertain`, not `act_now` by default.
- [x] Require exactly one verdict per candidate: `act_now`,
  `waiting_external`, `informational`, `stale`, or `uncertain`.
- [x] Require a pre-report completeness check: decision count equals candidate
  count, candidate ids are unique, and every decision cites current evidence.
- [x] Require positive current evidence for `act_now`; source membership is
  never sufficient evidence.
- [x] Replace “ready drafts” and “open support queue” in the greeting with an
  `act_now` agenda, a separate `uncertain` block, and an audit summary for
  everything excluded.
- [x] Preserve handles, source disagreements, engine verdicts, human takeover,
  out-of-band records, campaign escalations, and system state without turning
  them into work automatically.
- [x] End the command after the report. Remove the embedded repair/send posture
  and instruct the agent to wait for a new, named operator action.

Verification:

```bash
python3 tests/test_review_bootstrap.py
python3 tests/test_stamped_surfaces.py
```

## Phase 3 — Incident replay gates

- [x] Add a company-neutral JSON fixture covering the seven incident classes:
  bank newsletter, successful commerce-platform invoice, completed export
  notification, ancient empty draft, current questionnaire, current customer
  question, and a task already settled outside email.
- [x] Extend the hermetic review test to prove the rendered command contains
  the verdict vocabulary, positive-evidence rule, per-candidate thread read,
  output partition, complete-decision check, and stop-before-repair boundary.
- [x] Add an opt-in live replay script that passes the decision contract and
  fixture to `claude -p` with `--tools ""`, structured JSON output, no session
  persistence, and a bounded budget.
- [x] Make the live runner compare every returned label with the gold label and
  fail loudly on missing, duplicate, unknown, or mismatched decisions.
- [x] Run the live replay in this session and record the exact model/result:
  Claude Opus, high effort, no tools or persisted session, **PASS 7/7**.

Verification:

```bash
python3 tests/test_review_attention.py
python3 tests/live_review_attention.py --model opus
```

## Phase 4 — Full regression and rendered-clone proof

- [x] Run formatting/diff checks and the complete 43-gate kernel suite.
- [x] Render a fresh neutral clone and verify its `/cs-review` bytes carry the
  adjudication contract and no company literal.
- [x] Run `cs update` against a disposable copy of `mario124-cs` and verify the
  generated review command changes without touching clone-authored company
  files or the real clone.
- [x] Update living documentation to coded-but-not-live-operator-verified
  status; do not claim the real mario124 morning is fixed until the operator
  runs the stamped command against the live mailbox.

Verification:

```bash
git diff --check
bash tests/run.sh
python3 /home/mal/.config/mrcall-ai-kit/doc-check.py --repo .
```

## Release boundary

This changes an operator-facing command, so it is a MINOR release. Final path
inspection showed that it does not modify a mandatory FULL trigger: no send,
campaign, Gmail dedup, authentication, permission file, or cron-wrapper path is
touched. The release tier is therefore static + live read-only on both clones;
the live engine/thread reads make static alone insufficient. This execution did
not install or upgrade a real clone or run a customer-facing send.

## Completion evidence

- `git diff --check`: clean.
- `bash tests/run.sh`: all 43 gates green.
- `python3 tests/live_review_attention.py --model opus`: PASS 7/7.
- Disposable `mario124-cs` copy: one generated file updated
  (`.claude/commands/cs-review.md`); `company/`, `manifest.toml`, and
  `docs/active-context.md` remained byte-identical to the real clone.
- The real clone and its mailbox were not modified or exercised.
