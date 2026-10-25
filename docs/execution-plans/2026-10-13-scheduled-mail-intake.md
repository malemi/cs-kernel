---
status: active
---

# Scheduled mail intake

Approved brief: [scheduled mail intake](../briefs/2026-10-13-scheduled-mail-intake.md), SHA256 0f132043b4b684a27a6b6c8b697f776d745394b84cb8127a0fdab0071514c629. Fresh framing verdict APPROVED; report /tmp/mrcall-ai-kit/exact-draft-live/mail-intake/brief-review.md.

## Dependencies and ownership

Kernel owns cs/operator_recovery.py and tests/test_operator_recovery.py. Add notice wording only if existing generic stopped wording cannot describe intake accurately; tests/test_operator_notices.py then belongs to this scope too. Preserve concurrent source changes. Engine owner separately implements/reviews sync.run explicit scope=email, strict echoed scope and typed result, actual-work serialization surviving client abandonment, preserving default sync and MCP overlay. No kernel activation before approved actual engine contract.

## M1 implementation

After current permission validation, return paused before any intake. Perform exactly one authenticated sync.run with {scope:email,days_back:14}; use Settings owner. Require mapping, exact scope email, boolean success=true and errors=[]; any other outcome stops before primary identity or either model. Pause again after intake before primary identity/launch. Existing fallback shares the completed prerequisite.

Bound client waiting at 180 seconds for connection plus request, with existing synchronous authentication HTTP timeout separately acknowledged; bound close to 2 seconds and abort transport if needed, cancel/reap reader and handlers. Avoid existing rpc.call timeout text falsely asserting server cancellation by using an outer deadline shorter than its internal timeout. No timeout retries. Explicitly document client abandonment and engine retained serialization rather than claiming whole-server cancellation. Error output and durable queued notice use fixed safe causes/class names, never arbitrary provider errors or mail bodies/secrets.

## Verification and integration

Pre-change real recovery subprocess checks pass. Extend them to prove intake precedes identity/model, executes once across fallback, zero intake with invalid permissions/pause, pause during intake prevents model, and all legacy/malformed/error/timeout outcomes refuse model. Test actual async client seam and cleanup including pending reader; preserve existing recovery assertions by explicit deterministic intake fixture. Run focused checks then bash tests/run.sh once. Repair only demonstrated in-scope failures.

Fresh M1 source review checks source, real check outputs and honest deadline semantics before dependent activation. Freeze a new immutable kernel candidate; preserve old r1 package and failed live records. Parent integrates exact engine family hashes and kernel selection, then reviews combined coherence before normal-cron acceptance. Do not mutate participating sources during live execution.

## M2 live and closure

Parent is sole live owner. Independently deliver fresh originals with paid automatic updates disabled. Ordinary cron must synchronize bodies before natural native generation. Require real MrCall reply, Cafe draft/no-send, signup policy, acknowledgement/no-loop, natural terminals and independent owned cleanup under existing exact authority protocol. No manual sync/storage injection, fake model output or loosened oracle. Failed earlier runs remain failed.

Lead reconciles operator-runtime and living context, adds route, invokes doc-end/doc-critic and separate final review. Baseline advancement requires actual mandatory results; publication remains separately authorized. Tested frozen-source evidence remains distinct from post-closure current release readiness.

## Rollback

Stop and clean only owned live processes before changing selection. Revert this intake seam or select the prior immutable kernel if needed; preserve concurrent kernel, engine/MCP and customer data. Retain failure evidence and pending live obligations.

## Current hosted development acceptance

Genuine r9 (`ecc64a8400e35d6f699a9c193ba5e399`) passes the unchanged strict
seven-check matrix on the actual installed kernel `9857f1bb…` and repaired
six engine runtimes. MrCall sends the correct 212 reply; Café creates exact
engine draft `71589012-ba68-4e7d-8e31-f45df722c349` with result311 and one
provider mirror without sending. Both operators terminate naturally with exit0.
Signup's documented policy passes with legacy exit1, not three zero exits.
The new Sent source is complete AUTOMATIC, root authority complete NORMAL/unheld,
and the actually received reply is classified automatic with no additional
received/sent/provider-draft/engine-draft effects. No manual intake or substituted
model output supplies native generation. Cleanup restores exact cron759ab3,
removes owned enrollments/markers/processes and preserves six runtimes plus Qonto.

The original signed result and complete pre/post1053-object tested source are
retained before documentation edits at `/home/mal/.local/share/mrcall-operational-evidence/2026-10-14/after-repair-full-checkpoint-guard-r9`. Retention manifest SHA-256:
`0701b581b092c6c0360d159dc36cedd3bbe949e33e6ec5c9b229b11ce08b8482`.
This is `development_hosted` acceptance; public installer/release and native
Gmail browser/mobile/API edit/send preservation remain unverified. Automatic
reconciliation remains off. Earlier failed runs stay failed and unsigned.
Operational acceptance remains separate from checker-governed documentation
completion and public release.
Independent operational APPROVED: `/tmp/mrcall-ai-kit/r9-acceptance-verification/report.md`,
SHA-256 `7de3884807f781e8a0aa5391113c6652ba059f378d6fe764a3aee124492435bc`.
Actual native inspection covers both complete physical receipts through EOF.
