---
status: completed
---

# Source-bound native business read outcomes

Approved brief: [intent and acceptance](../briefs/2026-10-19-native-business-read-outcomes.md).
Approved brief SHA256: `070d3bfbd7fffac05381e0e61d4b4f459bf5ab2aebac5f4adee7bdb7801f5d7a`.

## Classification, ownership and authority

This is substantial development: private persistent evidence and the native
failure boundary change across kernel and Actor consumers. It is not fast path.
The lead owns this paired plan, kernel implementation/tests and Actor consumer
changes. No parallel implementation is needed: the producer and all consumers
form one integrated reviewable milestone. Preserve unrelated concurrent edits.
Fresh brief approval precedes this plan; fresh plan approval precedes source edits.

Scope is finite: existing protected canonical discovery, exact assignment-status
JSON human holds with exit3, and complete contacted/history absence with exit1.
No public flag, printed output, exit status, model/upstream call, engine capability,
action authority, send route, permission, budget, cron or pause change is allowed.
Rootless/deferred reads, malformed/unknown/foreign/contradictory evidence,
incomplete required inventory and every failed mutation remain failures.

## M1 — integrated producer, native codec and consumers

1. Add a finite typed business-read receipt surface under cs/, separate from the
   existing discovery namespace. Reuse existing process identity, private-file,
   bounded capture and exact native-wrapper validation primitives from
   operator_discovery_receipt/operator_health; extract only the minimum shared
   parameterized primitive where necessary. Do not weaken the canonical discovery
   command matcher or create a generic arbitrary-command success receipt.
   Capture uses the ordinary private HEALTH_CONTEXT directory, owner, nonce and
   supervisor identity, not an acceptance-only environment dependency. Bound
   record count, byte sizes, capture time and cleanup; refuse unsafe paths, links,
   duplicate or ambiguous records. Missing/failed capture preserves the original
   CLI output/code and leaves supervisory health failed, never waived.
2. In cs/assignment_cli.py, capture only the exact requested-root JSON status
   produced by the existing authority projection after workset checks. Validate
   the complete source-owned human-hold shape, including actual actor/space/root,
   member/source evidence and existing ancestry-conflict semantics; a state label
   alone is insufficient. Reuse task_assignment validators without broadening
   action policy. No aggregate/rootless or plain-rendered status exemption.
   In cs/cli.py contacted/history, capture the already computed typed mailbox
   fanout only when complete and empty. Include configured/read/skipped scope,
   no unreadable scope, exact contact/query and the contacted day window or
   explicit unbounded history. Support existing prose and JSON rendering without
   parsing prose or changing bytes. No extra mailbox read to certify the result.
3. Every receipt binds exact argv and native command, owner, nonce, query scope,
   CLI/native/supervisor process identities and approved package/binary identity,
   typed result, exact stdout bytes/digest and actual return code. Join the record
   to the original tool-use/task/run/session and original result bytes/code using
   the existing protected ancestry/wrapper approach. Do not claim the CLI knew
   native task IDs; establish those bindings at the supervisor's unique join.
   Shell composition, prefixes, ambiguous joins and mismatched output refuse.
4. Update cs/operator_native_composition.py to represent the actual finite
   nonzero code instead of assuming every failed foreground task means3. Keep
   notification/result ordering, genuine terminal, producer and all lifecycle
   guards. Structural recognition of an eligible command is not successful
   business-read proof. Actual exception acceptance requires its independently
   joined typed receipt. Preserve the protected existing discovery path,
   including supported automatic completion. Do not expand unsupported task
   lifecycles to make a fixture pass.
5. Update cs/operator_recovery.py and cs/operator_health.py so ordinary cron and
   acceptance use the same joined business-read decisions. Replace loose textual
   status exemptions with protected finite outcomes. Record bounded business-read
   proofs separately from required phase/discovery receipts. Require proof for
   each nonzero eligible read, including reads without task metadata. Absence
   or human hold grants no action authority. Required discovery, typed review,
   task inventory, phase completeness and operation-failure checks stay strict.
6. Update Actor scripts/operator_operational_common.py to independently validate
   the finite receipt schema, code, identity and native task/result bindings;
   allow exit1 only for proven contacted/history absence and exit3 only for
   existing discovery or proven exact human hold. Preserve all other acceptance
   predicates. Update source-owner provenance/policy references only where these
   owned current files require it; retain historical candidate identities.

7. Lead owns the minimum shared triage-template clarification and two separately
   staged clone guide deltas: scheduled direct deep reads, including fact sourcing
   or post-compose checks, use only selected canonical RFC roots. Broad Sent search
   examples remain interactive; needed off-workset evidence is explicitly deferred
   without issuing a forbidden RPC. Preserve complete discovery, queue order,
   evidence requirements, custom company prose, send authority and all guards.
   Add exact staged/rendered/literal guidance checks for both actors and three
   canonical host paths. No fixture priority or broader read permission.
   For completed native task output, explicitly use built-in Read through the
   complete file with paging as needed; do not execute Python/shell summarizers
   or repeat the review. This closes the repeated V17/V21 optional report-parser
   auto-classifier refusal without changing permissions, codec or inventory.
   Extend the scheduled-surface test with one additive exact guidance ledger,
   reversing only these two reviewed paragraphs before the historical workset
   comparison; preserve the old immutable ledger and mutation negatives.

### M1 verification and review

Extend existing kernel native-composition/discovery-receipt/health/recovery,
assignment and contact-history tests, plus Actor scripts/tests/test_operator_operational.py.
Use real local subprocesses and private temporary directories for capture/join;
label protocol children and constructed native events as constructed controls.
Exercise both ordinary health context with no acceptance variables and optional
acceptance export. Positive cases cover exact held status, contacted absence,
history absence in both renderings and unchanged canonical discovery.
Negative cases mutate owner, nonce, process start, argv, contact/root/window,
output bytes/code, task/run/session, proof scope, links/modes and duplicate joins.
Unknown/partial/foreign projections, unreadable mailbox, rootless status,
workset deferral, changed required phases and failed draft/send/retirement must
remain failed. Verify existing output bytes and return codes are unchanged.

Replay immutable V21 as a native-lifecycle regression, retaining original values.
Its historical stream lacks newly introduced private capture: it cannot prove
new end-to-end receipt acceptance. Report that missing historical binding and
keep unaugmented V21 fail-closed at protected proof validation. A separate
explicitly constructed, source-produced receipt/control may test the join;
never label it historical provider/native acceptance or reseal V21. Replay
V19/V20 action failures as negatives and preserve all original evidence.
Run focused checks first, then one fresh bash tests/run.sh plus the affected
Actor test command. Fix failures and rerun affected checks; repeat broad checks
only for a material integration change. Fresh M1 reviewer examines the whole
producer/consumer boundary, source ownership and actual evidence before staging.

## M2 — reviewed narrow adoption and free installed verification

Depends on M1 APPROVED. Stage only reviewed kernel modules atop the exact current
installed base on both clones, excluding unrelated source changes. Jointly bind
Actor producer package/current-source pins and policy. Apply only the two
reviewed minimum clone-guide clarifications from M1, preserving all other guide
bytes and canonical host links; do not change launchers, controls or historical
provenance. Record exact source/payload hashes,
owned preimages and every unchanged payload entry. Fresh activation review covers
helper, scope, controls, three operator/signup locks, permissions/ownership,
conditional sibling swaps and rollback before applying anything.

After authorized reviewed adoption, independently verify both normal clone
interpreters without PYTHONPATH, exact installed producer/source pins and protected
binary/driver identities. Run actual installed local subprocess capture/join and
supervisor/Actor controls for both actors, including ordinary context without
acceptance variables. Verify literal guidance/mode/send contracts remain exact;
run scoped free actor/peer/excluded/source/fixture/lock preconditions, with no
model, provider write or extra operational attempt. Preserve failure evidence.

## Closure, limits and rollback

Reconcile affected kernel/Actor durable contracts and current living-context
rows; preserve displaced history verbatim. Assess unchanged clone docs against
the actual installed contract. Run doc-end, mechanical checks, semantic doc-critic
and separate final review before completion check/finalize. Report actual broad
suite exit status and any affected reruns without promoting partial evidence.

This plan establishes only source and narrowly installed/free behavior. It does
not establish a new ordinary/provider PASS, retrospective V21 success, action
permission from held/absent evidence or a public release. The umbrella recovery
remains open. No next paid case, fixture send or customer-draft cleanup is
authorized; those require separate existing-task authority after these gates.

Before adoption, rollback is restoration of exact owned source preimages only.
After adoption, retain whole package sibling preimages and paired current pins;
restore only if owned postimages still match, under the same locks. Refuse to
undo another session's changes. Never restore or mutate mail/provider state,
public release pins, protected drafts or excluded engines as rollback.

## Execution checkpoint — 2026-10-19

M1 is approved in `native-business-read-m1-review-r2.md` under the retained R3
plan. Actual current Actor checks pass all 84 existing tests and five independent
read-outcome tests. The single complete kernel run exited 1 solely at the old
guidance comparison (gate63); its additive ledger repair, rendering, capture and
literal guide checks pass, followed by passing final-source gates63b/64/65.
This is qualified gate coverage, not a claimed fresh complete-run exit0.

M2 is installed and independently approved. The exact payload is
`e4b49f97571a51866d667c51e5811712631a3cd6e0f6689911896cbfac33e148`:
116 files, eight owned changes and108 unchanged entries over both actual7deb
bases. The initial locked preflight refused an existing ordinary cron; that
failure did not create an authorizing baseline. The complete normal stream,
including both genuine callback terminals, remains retained without a health
or operational-acceptance promotion. All old processes subsequently ended.

The fresh actual four-lock preflight passes in
`native-business-read-adoption-stage-r1/activation-8b1244112c954e48b465fe5aa5841929/`.
Reviewed conditional adoption passes in `activation-084770bfffe541d5a4a6387b14bc080d/`.
Independent verification in `native-business-read-installed-independent-verify.md`
confirms both normal installed payloads/imports and capture controls, current
Actor84+5 tests and17 exact preservation checks. The scoped free actor/peer/
excluded/source/standing-doc/fixture/lock preconditions pass without model calls
or provider writes. Temporary-only transaction/rollback controls remain distinct
from executed live rollback, which was unnecessary.

Component documentation reconciliation, semantic critic and separate final
review govern baseline advancement. Their final current evidence belongs to the
four `native-business-read-*-20261019` completion tasks. This bounded source and
configuration component does not complete umbrella ordinary/provider recovery.
V21 remains FAILED; Café/signup were not run, no signed current PASS exists and
no next paid attempt or release is authorized. Remaining operational acceptance
retains its existing umbrella owner and criteria.

Exact reports, raw failures, qualified checks, source/payload manifests,
preimages and preservation records are under
`/home/mal/.local/share/ordinary-assignment-recovery-resume/bounded-triage-workset-20261018/`.
