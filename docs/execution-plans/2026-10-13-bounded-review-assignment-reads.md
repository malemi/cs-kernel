---
status: active
---
# Bounded review assignment reads

Authority: approved brief `2026-10-13-bounded-review-assignment-reads.md`,
SHA-256 `a3b055ff43d07f5f90e965bfde7aaa72697477ad92285e9da4b9e1a019010b3f`.
The raw fresh brief review and immutable version are retained under
`/tmp/mrcall-ai-kit/exact-draft-live/review-read-bounds/brief-review/`.

## Ownership and dependencies

Kernel source: `cs/rpc_reads.py` (new), `cs/task_assignment.py`,
`cs/engine_view.py`, `cs/review.py`; focused new `tests/test_rpc_reads.py` and
existing assignment/review/classification tests where meaningful.
The lead integrates only these owned deltas; preserve concurrent source edits.
No server, settings, credentials, permission, model or company-file changes.

## M1 — bounded multiplexed reads

After fresh plan approval, implement one allow-listed read helper around the
existing EngineClient. One selected-account connection, maximum four concurrent
requests, deterministic keyed outcomes and a 90-second batch budget; each actual
request retains a maximum 60-second timeout or the smaller remaining budget.
Use ordinary authentication once per connection, preserving its existing
30-second refresh bound. Never claim that synchronous authentication or socket
close is instantaneous. Explicitly bound close/cancellation cleanup and account
for it in measured elapsed time. Reject mutation methods before connection.

Each requested key gets exactly one outcome. On any connection timeout retain
already completed reads and mark every outstanding or unstarted key unreadable.
Cancel/await reader tasks and close the client; no orphan background worker may
supply late authority. No persistent connection beyond the batch or retries.

Split only the existing projection validation and peer-merging into common
helpers. Single-root `project` retains its public behavior. Bulk `projections`
reads primary roots and configured distinct peers through the bounded helper,
then applies exactly the same validation/merge in deterministic original order.
A failed primary remains UNKNOWN without inventing peer authority. Preserve
source-owner exception, current-message coverage, revision and company checks.
Use one shared 180-second overall bulk-projection deadline across peer batches;
no new peer batch or request begins after expiry. Unread roots remain held.

Use the same helper for classification without changing parsed ThreadView data
or conservative engine-unavailable semantics. Review obtains projections for its
listed roots through the bulk path, retaining its original list order/provenance.
Do not remove the full unanswered sweep or reuse its result as current authority.

## Verification and source gate

Capture relevant pre-edit checks once. Test a real local WebSocket server using
the existing EngineClient: one connection, out-of-order replies, maximum four
active reads, stalled sibling closes, completed retention, all missing keys,
cancellation and no orphan reads. Verify mutations fail before any connection.
Use controlled complete primary/peer responses to compare exact old/new semantic
results and ordering for normal/assigned/closed/later-inbound/conflict/unknown,
wrong owner/space/revision and unreadable peer. Test expiry before remaining peers
cannot permit action. Run focused tests and the full kernel suite once.

Freeze the coherent owned delta and raw results. Fresh source review precedes
main integration; compare actual integrated function changes and preserve all
other bytes. No dependent live test or producer selection before approval.

## Integration, real measurements and final acceptance

Combine only approved latency and M1 discovery-transport source. The Desktop
owner selects exact reviewed payloads and validates actual helper-produced
transport fixtures. Verify all three template/host surfaces through the existing
M2 workflow gate. Measure read-only actual review on both configured clones,
retaining complete JSON/degradation and actual stage durations; no compose/send.
Fresh combined integration review precedes SMTP. The other lead is sole live
owner: MrCall first, independently received reply, then Café plus signup; preserve
real acknowledgement/no-loop and strict phase/terminal/source criteria.

## Rollback and closure

Keep exact preimages and modes. Restore only owned delta after independent-drift
checks; never overwrite a dirty tree, customer records or frozen evidence.
Record real failures. Existing failed diagnostic stays unsigned and cannot be
promoted. Reconcile docs, critic and separate final review before completion;
publication remains separately authorized. This work promises bounded read
stages and measured improvement, not a universal whole-review 90-second bound.

## Source milestone evidence

M1 source review is APPROVED for the immutable r2 packet in
`/tmp/mrcall-ai-kit/exact-draft-live/review-read-bounds/source-M1/`.
`review/report-r2-approved.md` checks all seven frozen/current owned hashes,
14 focused tests, 42 comparisons against the original projection semantics,
and `full-suite-r2.log`: exit 0, `RESULT: all gates green`.
The earlier full-suite failure is retained. Its handled/escalated fixtures were
adapted at the existing RPC test seam without changing their business assertions.
No live measurement, deployment or three-job acceptance follows from this gate.


## Combined source gates before genuine final acceptance

The read-only ordinary review measurements complete with exit0 on both clones:
MrCall183.468seconds and Café277.883seconds. Their real JSON retains UNKNOWN
assignment authority and customer draft notes; this is not global business-green.
Measurements use the immutable approved readbounds-only snapshot with package
`b3f6d4b1053f6ddfc000a7a4405bf1db0ad46f3da921dc2178be5eddf50b35d3`,
not a claimed native run of the later combined candidate. Actual records:
`/tmp/operator-operational-evidence/full-completion-plan/`
`mrcall-full-review-measure.json` and `cafe-full-review-measure.json`.
Combined M2 source integration is APPROVED and the current ROOT full suite
passes; final actual-source operational acceptance remains required.

Evidence root: `/tmp/mrcall-ai-kit/exact-draft-live/protected-fixture/discovery-transport-m1/`.

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
