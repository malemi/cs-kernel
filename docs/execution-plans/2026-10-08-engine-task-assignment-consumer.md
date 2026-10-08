---
status: completed
---

# Explicit engine assignment consumers — local delivery

Intent: [approved brief](../briefs/2026-10-08-engine-task-assignment-consumer.md).
Fresh brief APPROVED evidence: persistent fanout recovery evidence,
`assignment-kernel-brief-review.json` and immutable approved brief.
Depends on approved Desktop explicit-task-assignment brief/plan and fresh M1
engine milestone review before dependent implementation. No release or live work.

## Ownership, source and integration contract

Lead owns trace, docs, completion records and gate ordering. One execute worker
owns kernel changes only: new `cs/task_assignment.py` common authority adapter,
`cs/assignment_cli.py` commands and bounded metadata projection helper if needed;
small delegations in `cs/cli.py`; per-thread integration in `cs/unanswered.py`,
`cs/review.py`, dossier and draft/handled handlers; cron deny template; affected
canonical triage/operator/customer guidance and meaningful tests/suite wiring.
Desktop M2 worker owns engine RPC/evidence and publishes frozen interface before
kernel integration. Workers are not alone and preserve foreign/instructions
changes; no concurrent editing of shared templates. All artifacts stay English.

Engine methods: `tasks.assignment.list/get/preview/commit/project/reply_evidence`.
Authoritative actor/company membership, independent signed approval, CAS, receipts,
closed audit and uncertainty remain engine-owned. Kernel reads exact protocol
version and validates response shape and expected peer UID/company space. Unknown
method/unavailable scope is UNKNOWN, not an empty successful list. No new auto-send
authority and no kernel signing/ownership persistence. Do not replace existing
private ordinary task contracts or put assignee in arbitrary sources JSON.

Projection fields agreed with Desktop M2 cover exact thread key, state,
completeness, task ID/revision/assignee, source provenance, covered inbound IDs,
closed audit and explicit unknown/conflict reasons. Reply evidence comes from
owner-authenticated configured peer engines and remains advisory until engine
independently validates a signed exact-source confirmation. Nonautomatic member
reply is a candidate needing human verification, never proof of authorship.

## K1 — Consumer APIs, CLI and lifecycle integration

After fresh engine M1 review, implement one shared adapter calling real RPC.
Expose `cs assignment` status, preview/export and grant commit operations with
bounded file parsing and strict errors. Actor derives from engine session; account
selection uses existing registry/auth, never arbitrary caller UID fields. Export
contains no secret or mail body. Engine supports explicit manual assignment
without claiming a detected reply. Host operator approval remains a separate
privileged command; no generic chat approval, tenant key or automatic signer.

Query ownership per exact thread BEFORE sender rollup/answered subtraction. Keep
human-owned, unknown/conflicting and needs-assignment work in visible separate
queues. A different open thread from the same sender remains machine work;
represent both without address-wide ownership suppression. One candidate must
survive ANSWERED subtraction until assignment is explicitly confirmed/resolved.

Use the same projection in review/dossier and draft guards. Render manual,
confirmed-by-answer and escalation provenance separately; agreement once with
both reasons, disagreement held with both identities. Unknown reads hold the
scoped work and remain visible even when another peer has a positive answer.
No new interpretation of reply kind or automatic flags in the kernel.

Handled workflow may record the existing local gesture but can settle assignment
only via exact engine ID/revision/covered IDs and signed close intent. Show
acknowledged engine close versus local-only/unconfirmed close. A failed close
remains active/unknown and held; broad handled suppression cannot hide it.
Closed covered IDs govern scope: a new inbound identity, including same/old Date,
returns operator work without restoring the former assignee. Active ownership
retains later inbound with its human. Retain all close audit.

If additional Gmail metadata is needed, extend existing batched reader with an
explicit projection, never modify scopes 1–5 row shapes or add per-message header
reads. Actual provider source verification remains in engine. Avoid broad changes
to unrelated send gates; draft guards consume scoped assignment authority before
writing a draft. Direct engine APIs retain their own approval/send policy.

Add all six cron spellings for named assignment mutations and raw commit surface;
read-only detection remains available. Server grant checks are the real write
boundary, not shell matching. Preserve existing escalation permissions.

Verification: real isolated CLI→authenticated fixture WebSocket→SQLite journeys
with operator grants for assign/reassign/close, peer candidate, incomplete source,
conflicting escalation, stale revision, replay, failed acknowledgement and restart.
Prove two threads from same sender separate, same-second/old-Date inbound reopening,
closed audit and ordinary/Qonto privacy. Preserve reader/gate baseline fixtures.
Fresh K1 review before changing downstream workflow prose or calling integration
accepted; include actual source versions and complete logs.

## K2 — Workflow surfaces and complete local acceptance

After fresh K1 review, reconcile canonical triage/operator/customer instructions
with the actual common projection/CLI. Hold candidate/unknown/assigned/conflict
before drop/draft; keep named human work visible. Render identical canonical bytes
on all hosts. Preserve standing-instructions edits and company-authored content.

Run actual native Claude/Codex/OpenCode discovery/execution of every changed skill
with explicit assigned/candidate/unknown/handled-failure/later-inbound decisions;
retain full reads, final decisions and unchanged product-state proof for read-only
cases. Fixture writes for signed lifecycle are explicitly scoped and audited.
No acceptance from timeout or partial read. Existing recovered 15-case M3 pass
remains historical evidence for the earlier frozen bytes, not this new workflow.

Run all focused lifecycle/permission/source-contract tests, `bash tests/run.sh`
including fresh installed-package gate, render/byte identity and cron enumeration.
Fresh K2 integration review covers all changed source and templates before closure.

## Documentation, final review and completion

Lead reconciles README/CHANGELOG, new operational feature guide, engine contract
links, original fanout design/child plan and living context with verbatim archives.
Original root umbrella remains active for separate live/FULL release acceptance.
This local consumer plan can complete verified local scope independently.

Run doc-end: explicit development completion record, real immutable approved
brief/plan/K1/K2 artifacts and reviews, held startup, impact/reconciliation,
mechanical/keyword/oversized ledger, focused actual CLI/transport check, fresh
doc-critic including context shape, pre-review readiness and separate fresh final
review. Finalize baseline/status only after actual completion check passes.
Retain erased historical receipt and production acceptance limits explicitly.

## Rollback

Reverse owned consumer hunks only; retain engine assignment/event/receipt tables
and closed audit. Do not infer no owner against an older/unavailable engine.
Disabling trust denies writes but retains assignments. No live clone repin,
credentials, membership changes, deployments, repository commits or pushes.
Real Sent/recipient key parity, mailbox latency and FULL both-clone acceptance
remain separately authorized release obligations.

## Local verification record — 2026-10-08

K1 is fresh independently APPROVED at the persistent recovery directory's
`assignment-k1-review/final-review.txt`. The retained 17-file source union,
approved brief/plan and actual log hashes bind that verdict. Fifteen focused
commands exit 0, including 20 consumer tests and both production permission
renders. The reviewer independently repeats 13 real CLI/authenticated-WebSocket/
SQLite lifecycle commands. Initial REVISE findings and interrupted full-suite
attempts remain retained and are not counted as successful acceptance.

K2 canonical triage/operator/customer instructions now consume all buckets and
exact thread authority before drop/draft, retaining human work and closed audit.
Render checks pass for 36 templates across three configurations; init/update and
canonical host byte identity pass. The final full suite exits 0 with all gates
green and no changes across 173 source entries (`assignment-kernel-k2/full-final-result.json`).
Nine native cases pass against that final freeze across Claude, Codex and
OpenCode, with complete canonical reads and explicit held UNKNOWN, assignment,
failed acknowledgement, closed audit, later-inbound and unrelated-thread decisions.
Six harmless read/help/parser corrections retain their original raw false results;
an aborted duplicate is excluded. The first two native cases retain computed
equality checks without full persisted before maps. Fixture body/search failures
remain disclosed; no live retrieval success is inferred.

Fresh K2 integration is APPROVED (`assignment-k2-review/final-review.txt`); Desktop
M2 integration is also APPROVED (`assignment-m2-review/final-review.txt`). Immutable
reviewed artifacts and source/log comparisons are retained. Documentation and
separate final-user closure use the completion record; only checker finalization
transitions this local plan to completed. Production enablement remains separate.
