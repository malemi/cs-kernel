---
status: completed
---

# Canonical contextual send plan

## Milestone 1 — command contract

- Add the `draft-send` parser and implementation.
- Resolve only an exact full ID from `drafts.list`; print recipient and subject
  before the send turn.
- Call engine chat with only `send_draft` approved and an exact-ID instruction.
- Validate the approval event and the `status=sent` postcondition.

Verification: focused command tests with RPC/chat fakes; CLI help assertion.

## Milestone 2 — permission and operator boundary

- Add all six `draft-send` spellings to the cron wrapper deny list and its
  mechanical enumeration gate.
- Update stamped `AGENTS.md`, `README.md`, architecture, and relevant send
  workflow prose so ambient Gmail/Superhuman/app sends are explicitly outside
  the contextual-send boundary.

Verification: stamped-surface and permission tests; rendered clone comparison.

## Milestone 3 — integrated review

- Run the focused send tests, permission surface tests, and the kernel suite.
- Review the final diff separately for wrong-recipient, double-send, false
  success, and headless-reachability regressions.
- Reconcile active context and mark this plan complete only after all checks
  pass.

## Risk and rollback

The command is additive and no release or deployment occurs here. Its main risk
is false success after a model turn; matching the approval input and sent-row
postcondition makes that failure loud. Rollback is removal of the new verb and
stamped guidance before a tag.

## Verification result

- Focused tests cover the exact-ID success path, wrong-ID and missing approvals,
  repeated exact-ID requests, engine errors and uncertain delivery state.
- The implementation session recorded a passing full kernel suite, including
  rendered surfaces and the cron deny enumeration; doc-end did not rerun it.
- The documentation mechanical gate and semantic source review are clean.
