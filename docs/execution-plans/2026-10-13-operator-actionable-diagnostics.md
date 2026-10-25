---
status: completed
---

# Actionable operator failure emails

Approved [brief](../briefs/2026-10-13-operator-actionable-diagnostics.md).

## Ownership and dependencies
Lead owns operator diagnostics/recovery/notices, their focused tests, the supervisor test gate and affected runtime documentation. Other draft-identity edits are concurrent and excluded. One cohesive milestone M1 covers diagnosis-to-email integration; its approved artifact is `cs/operator_diagnostics.py`.

## M1 implementation
1. Add a neutral bounded diagnostic module. Classify explicit structured API error codes, native terminal subtypes, watchdog/parse failures and missing results; do not change `_prework_refusal` or make a classification authorize replay. Unknown errors preserve safe codes/session identifiers, never arbitrary tool content.
2. Resolve primary account metadata through the configured Claude-compatible executable's read-only `auth status --json`, with bounded time/output and whitelisted fields. Detect provider from actual available routing/auth metadata; never assign an unrelated OAuth identity to an API-key run. Use a masked key identifier when available. Unavailable metadata remains explicit with the exact executable/config diagnostic action. Custom launchers must honor the CLI auth-status contract; failed probes do not block the operator.
3. Extend existing OpenRouter key metadata with finite numeric key-limit evidence and validated account identifiers. Keep backup engine-profile ownership distinct from provider payer identity. Read provider key state after failures to distinguish a proved key cap from an unqualified HTTP 402; no provider mutations or paid probes.
4. Persist the failed attempt's safe diagnostic/account/config context in queued notices. Preserve legacy rendering and queue retry. Dedup excludes timestamps/session IDs so repeated identical outages do not flood; cause/provider/account changes remain observable.
5. Rewrite every notice in symptom/cause/account/repair/after-repair order. Use verified official provider links, exact config fields/paths and read-only diagnostic commands. Successful fallback includes primary repair and backup completion. Ordinary account repairs need no manual run or daemon restart: the next enabled, unpaused tick retries. Do not advise changing unrelated engine budgets or invent an administrator.
6. Verify at the supervisor boundary using real child processes and captured SMTP: primary and backup credit/auth/limits/budget, identity-source isolation, malformed/missing responses, metadata failure, legacy queue, dedup and unchanged no-replay decisions. Review complete MIME examples for actionability, not just keyword presence.

## Verification and rollback
Prior recovery child-process suite passes before edits. Run focused diagnosis, notice and recovery checks, then a full suite on an isolated frozen baseline plus the task-owned files (including the earlier notice candidate). Never mix another session's evolving source into acceptance. Roll back these task-owned diagnostic/rendering changes together; retain queued notices and tolerate absent new fields.

## Closure
Fresh M1 review; update runtime contract and local candidate state, retaining historical text verbatim if superseded. Invoke doc-end/doc-critic including unchanged safety boundaries and living-context shape, then independent final-user review of concrete sample messages. Completion task records actual artifacts/checks; active-to-completed transition only after final approval. No release, clone adoption, real email or account action.

## Verification evidence

The fresh brief and plan reviews approved the scope. M1 review approved the
integrated implementation after correcting provider attribution for opaque API
launchers, the exact backup credential repair location, and queued engine-profile
identity. Retained reviews and approved artifacts are under
`/tmp/operator-actionable-evidence/`; the completion record binds their hashes.

All three focused scripts pass: `tests/test_operator_diagnostics.py`,
`tests/test_operator_recovery.py`, and `tests/test_operator_notices.py` (32 SMTP
captures). Real child processes verify pre-work-only replay, known and unknown
causes, distinct payer identities, refreshed key caps, bounded auth probes, and
delayed delivery preserving the original provider and engine profile. Five
complete plain/HTML samples in that evidence directory exercise concrete repairs.
No live provider mutation, real email, release or clone adoption is performed.
