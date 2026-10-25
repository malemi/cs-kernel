---
status: completed
---

# Semantic complete inventory: offline feasibility

## Authority and ownership

Approved brief: `../briefs/2026-10-19-semantic-complete-inventory-view.md`, SHA256
`4aee1342744551775b4af1481084f38bdf4408749a6a44a7a44c157a14e30afd`.
External fresh APPROVED review:
`/home/mal/.local/share/ordinary-assignment-recovery-resume/bounded-triage-workset-20261018/semantic-complete-inventory-brief-review.md`.

Coordinator permits this read-only plan and fresh review, then ONE external M0
worker only after APPROVED: 15-minute limit, checkpoint8, no tuning/extension loop.
Lead owns plan/handoff; worker owns external M0 files only; fresh reviewer owns
semantic verdict. Runtime code/adoption/paid work need separate coordinator
scope after measured M0 and semantic APPROVED. No automatic continuation.

Old lossless M0 remains FAILED/STOP and its artifacts immutable. Old lossless plan
is superseded in direction, to be marked honestly at scoped documentation closure;
no baseline advancement or unrelated doc rewrite in this feasibility-only scope.

## Exact M0 readable format

Versioned UTF-8 text, schema `cs.semantic_inventory.v1`, deterministic compact
JSON-lines tables with a short plain-language legend first. Each table has a
single explicit ordered column-name header; each following row is a JSON array.
No abbreviation without that header/legend. Null/false/empty/absent stay distinct:
absent cells use tagged `["absent"]`; a literal array with this shape is encoded
as `["literal",value]`. String and boolean/number types are never coerced.
All strings quoted by JSON; no hidden values or digest-only inventory rows.

Visible identity legend has columns `id,kind,value`; IDs `r1` root, `a1` actor,
`s1` space, `m1` mailbox, allocated first occurrence in original traversal.
Every reference cell is tagged `["id",id]`, every literal cell remains literal
unless ambiguity requires the literal tag. Exact original identities appear in
legend once. No message IDs in identity legend unless classified KEEP by brief.
Root component arrays preserve EVERY root and order using typed references.
No string-prefix compression, external raw lookup or Python reconstruction is
needed to understand any visible root/owner/reason/hold.

Tables in fixed order:

1. `binding`: schema, raw SHA/length, owner, nonce, ancestry PID/start, exit code,
   source/current native invocation identity when available from retained receipt.
   M0 marks missing binding unavailable and cannot fabricate it. View hash/length
   are in separate envelope to avoid circular hashing.
2. `groups`: original discovery keys/order/type/count, including empty groups and
   scalars. Scalars appear exact; row tables retain original group/index.
3. `inventory`: group,index,email,name,subject,last_inbound_date,days_waiting,
   thread_key,state,reason,_workset_revision,escalated_at,escalated_owner,
   escalated_reason,days_escalated. Missing fields use explicit absent cells.
   Columns entirely absent for a group may be omitted from that group's header;
   the schema states they are absent for every row, never default/null.
4. `assignments`: inventory group/index,version,actor_uid,space_id,thread_key,
   authoritative_thread_key,component_thread_keys,component_scope_present,
   source_owner_uid,complete,authority_complete,state,hold_auto_reply,hold_scope,
   reason,task,events,current_inbound,covered_inbound, provenance basis/owner/reason
   in exact order, and current/covered message-ID counts plus raw detail reference.
   Empty/null task/events/inbound stay exact. Nonempty unclassified shape REFUSES.
5. `observations`: parent group/index,original observation index,version,actor_uid,
   space_id,source_id,thread_key,complete,judgement,reason,source.actor_uid,
   source.mailbox_id,source.thread_key,source.observation_only; every occurrence
   exact and ordered, no inferred aggregation or dedup of observations.
6. `protected_originals`: complete original fixture fields, order and values,
   preserving message/provider/owner/body digest exactly.
7. `workset`: complete,limit and separate selected/deferred/held headers/rows;
   every ordered selected thread_key/revision/sources, deferred thread_key/reason/
   sources and held thread_key/reason/source/identity. Identity nested values KEEP
   exact typed value; classify shape before encoding, no field silently dropped.
8. `raw_details`: shared path templates, per-parent lookup rule and actual counts
   for RAW REF containers/fields. They explicitly remain UNINSPECTED by native.
   Raw path/hash envelope identifies retained input; no repeated full JSON pointer
   per opaque digest. Reference mapping must be independently enumerable.

## Exhaustive classification and refusal

The approved brief table is the normative path classification, not a vague allow
list. Before rendering, recursively enumerate actual input fields against it.
KEEP root binding, every global group/row field, all assignment authority/hold/
root/component/provenance facts, every listed semantic observation/source fact,
protected-original fields and workset exactly. RAW REF only root output_sha256,
assignment.route_digest, current/covered message IDs, observation digest,
source.message_id/provider.{folder,uid,uidvalidity}, source route/header/content
commitments and retained full observation proof container. Container references
do not suppress its separately KEEP semantic observations. Other unknown fields,
nonempty unclassified material task/event/inbound or unexpected types REFUSE.
No new semantic classification can be added to make actual V22 pass silently.

M0 fixtures cover actual nonempty held.identity shape; if the approved generic
KEEP rule cannot represent all its facts clearly, report refusal for framing,
not new inference. All identity references resolve within view. Every omission is
an explicit approved RAW REF or group-wide absent field, never compacting by loss.

## M0 input, independence and free gates

Worker external root:
`/home/mal/.local/share/ordinary-assignment-recovery-resume/bounded-triage-workset-20261018/semantic-complete-inventory-m0/`.
Input immutable V22 `/home/mal/.mrcall-cs/operator-runs/run-mrb5_98o/discovery.json`,
SHA `eadff68465626b9d972e226b2c5f5c63831693c9f5e66c0f6e21fd8425ba13a6`,
98,755 bytes; verify retained manifest and copied native artifact agree. Do not
modify them. Existing transport trust only, no upstream MIME/header authenticity
claim or live engine query. Stdlib/Python -B only; no network/models/providers.

One worker implements one candidate producer and a genuinely independent checker:
checker separately walks raw with explicit approved path assertions and parses
visible headers/rows/legend to compare exact typed KEEP tuples, field presence,
full group/root universe, duplicate occurrence/order and workset. It does not
import producer projection/normalization/schema helpers or compare a producer
boolean/digest. RAW REF mapping is checked independently against original parent
indices/path and counts, including semantic facts exposed from that same proof.
Retain producer/checker/test source and actual commands/results/hash manifests.

Acceptance before any runtime decision:

- Actual readable view at most TWO8192-byte pages with stride8064 (max16,256 bytes),
  INCLUDING legend/binding/headers/allrows/notes; raw/view envelope counted if
  native must read it. No metadata exclusion to manufacture page gain.
- Exact independent KEEP projection, field presence/type/order, every group/root/
  occurrence/workset and RAW REF mapping pass. Unknown/refusal cases pass.
- Adversarial negatives reject row/root/group/observation deletion/duplication/
  reordering, workset selection/revision/source/hold changes, altered identity/
  state/eligibility/completeness/reason/error/provenance/observation-only, unknown
  field loss, null/absent/empty/false confusion, wrong raw/view/binding, missing/
  ambiguous identity refs, opaque reference substitution and malformed headers.
- Fresh semantic reviewer reads ENTIRE actual view, without Python/raw decoding,
  traces actual human holds plus both selected roots and all held/deferred global
  facts, finds full identities/reasons/current state/semantic observations within
  the view and correctly identifies which selected-case details remain uninspected.
  Reviewer may use independent parity report as evidence of complete scope, but
  must not outsource readability to checker. Ambiguity/material loss => REVISE.

If >2 pages or any free negative/parity failure, stop candidate immediately; no
paid semantic acceptance on a numerically nonpassing candidate, no alternative
codec tuning or cap change. Report actual bytes/pages and limits. If all free
checks pass, fresh semantic review is mandatory before coordinator decision.
Neither offline check nor human-readable view proves native actual inspection,
current selected-root deep reads, action success or provider acceptance.

## Verification and rollback boundary

M0 writes disposable external files only; no source/config/package pin/cron/lock/
enrollment/draft/engine change. Preserve failed artifacts/report and restore
nothing live because nothing live changes. Runtime protocol/page recognizer,
source-owned progress, safe artifact creation/adoption/rollback and installed
free checks require a separate reviewed authorized plan after M0. Existing raw
route and genuine native event/process binding are never waived. Current engine
guards, six phases, budgets and protected drafts unchanged.

## Checkpoints

- Brief: APPROVED, hash bound above.
- Plan review: APPROVED; external `semantic-complete-inventory-plan-review.md`,
  reviewed SHA256 `6b049895080f59dfc7a68b630bcd499497fc5dd2e57ac9f988b4dbb2b5bc9158`.
- M0: FAILED/STOP, one candidate only. Actual native-needed42,700 bytes/six
  pages exceeds16,256/two-page gate. Immutable input/copy/manifest match98,755
  bytes and pinned hash. Producer exit0; size gate exit2. No tuning.
  External evidence: `semantic-complete-inventory-m0/report.md`,
  `size-gate.log`, `input-check.json`, `output-manifest.json` under the workset
  declared above. Independent checker/adversarial source retained but unrun
  after numeric failure; no parity/type/classification/readability PASS claimed.
- Semantic review: not run because mandatory free size gate failed.
  No extension, alternate codec or runtime authorization follows.
- Runtime/adoption/paid acceptance: not authorized.


## Prospective frozen-candidate gate amendment

Root authorized same framing+plan reviewer amendment ONLY, followed conditionally
by bounded existing-candidate independent checks and fresh semantic review.
Original two-page FAILED M0 report/hash is retained verbatim. No retroactive PASS.
No new codec/tuning/field omission/runtime/adoption/paid work.

Freeze exact existing `view.jsonl` SHA256
`6e99df6b7214d1e385ae74b23f36bcd4e5889ed25e0234049174cb1814cdf975`,
producer, input/binding and envelope via external manifest before any work.
A missing/mismatching manifest or candidate mutation refuses continuation.
Prospective threshold max48,512 native-needed bytes/six pages AND at least50%
fewer pages than13 raw (actual42,700/six=53.85% fewer pages). Count all envelope/
binding/legend/headers/notes. Preserve historical report; new checks go in a new
amendment report, explicitly prospective.

After BOTH same framing and plan amendments APPROVED, one bounded worker may
finish independent checker/adversarial tests on this frozen candidate: hard
10 minutes, checkpoint5, no extension/loop without new authority. Worker writes
only new check/test/report files or repairs checker/tests; frozen candidate input/
producer/view/envelope unchanged. Independent checker cannot import producer
helpers or projection/schema normalization. It separately recomputes exact typed
approved KEEP tuples/field absence, all inventory roots/groups/counts/occurrences/
order/workset, every semantic observation and RAW REF mapping from original raw.
Unknown/unclassified or ambiguous/missing facts refuse; don't silently accept
because the output fits. Record failures honestly; candidate fix is unauthorized.

If all checks pass, fresh semantic reviewer (not implementer) reads ENTIRE actual
view, traces human holds and both selected roots including identities across all
six pages without raw/Python decoding, assesses global report sufficiency and
explicitly recognizes selected-case RAW detail as uninspected. It also challenges
six-page practicality under existingUSD4 and separately designed remaining-offset
hints: no claim of budget guarantee, current hint implementation or actual native
compliance. Failure => REVISE/STOP; root decides next scope from real results.

Documentation closure later marks the prior lossless direction superseded without
altering its FAILED artifacts, reconciles historical two-page failure and new
prospective gate separately. No baseline/publication step in this bounded M0.

Prospective brief amendment APPROVED binding:
`0ffd4f3dbbbbe3732f4b78f0972f92274996d8b53cbf9635be644c09bf5cc802`,
external same framing review. Original brief hash above is historical gate evidence.


Prospective amendment result: FAILED/STOP, not adoption. Size passes42,700/six
pages and53.85% fewer pages. Independent current parity PASS (14 groups,
18 assignments,49 observations,80 held);44 adversarial controls reject. However
six invalid scalar-type controls are rejected only by consumer, accepted by frozen
producer: required pre-render type refusal is missing. No producer fix authorized.
Expanded suite was terminated without claiming a result. All nine frozen files
remain unchanged before/after. Entire-view semantic review not run on failed free
candidate. External evidence: `semantic-complete-inventory-m0/` prospective check
report/log/negative report/output manifest. Historical two-page failure untouched.

Café breadth: same frozen producer refuses actual historical raw lacking workset;
this is a pre-workset negative, not current incompatibility proof. A bounded current
builder control cannot proceed from that retained input: tasks/review observations
absent and29 open rows lack required workset revisions. No empty observations,
revisions or selection fabricated. Existing builder needs these upstream inputs;
STOP_INPUT_GAP. External `semantic-complete-inventory-cafe-replay/` retains exact
historical input, replay refusal and `current-shape-control-gap.json`. No fresh
Café scope/authority, projected parity/readability or provider acceptance claimed.


Root authorized one external M0 correctness repair, hard8 minutes: NEW producer
source only, preserving historical frozen producer/input/view/envelope/failed
reports. Enforce reviewed scalar type families before rendering across all
classified fields, not only six failing names; exact absence/null and bool/int
boundaries. No schema/field/codec/size tuning. Valid V22 view/envelope must remain
byte-identical at pinned hashes above. Rerun independent parity,44 negatives,
six producer refusals and focused family boundaries only; other material change
stops scope. New producer/preimage hashes retained. Only after all free checks
pass, fresh entire-view semantic review bounded5 minutes. No runtime/adoption/
paid authority. Existing Café retained-input gap remains separate.


R2 bounded correctness repair: free checks PASS. New external producer-r2 SHA256
`92862de09e2b4943a10649e9b990fa5656521e59f6b91e2883c5e967db92c657`;
historical producer/preimage and nine frozen files unchanged.35 focused cases
including six original refusals and independent full parity pass;44 adversarial
controls reject. Valid view/envelope reproduce pinned hashes exactly. Evidence:
`semantic-complete-inventory-m0/r2-check-report.json`, focused/base logs and
r2-output-manifest. No historical FAILED report changed or relabelled.

Fresh entire-view semantic review APPROVED:
`semantic-complete-inventory-entire-view-review.md` in external workset. Reviewer
read all42,598 bytes via six contiguous ranges plus102-byte envelope, without raw
or Python decoding, traced all hold categories/semantic observations and both
selected roots through visible identity legend. Six pages/42,700 native-needed
bytes meet amended gate, not original two-page gate. Actual current Café compact
path, runtime/native compliance, fresh selected detail, provider results andUSD4
feasibility remain UNVERIFIED. Root decision is required before any runtime scope;
this completed offline milestone does not complete ordinary recovery.

## Authorized source and installed component: M1/M2 reviewed extension

Root authorizes substantial SOURCE+INSTALLED COMPONENT through documentation
closure, explicitly NO paid case/release. This extension requires fresh plan
APPROVED before source edits. Lead ownership: plan/reviews/integration/adoption/
docs. One bounded execute worker owns source implementation in kernel and
independent Actor consumer/test changes,20 minutes/checkpoint8; no independent
worker cascade. Preserve unrelated changes and existing evidence. Material scope
or new risk stops/escalates; routine failures are repaired/rechecked affected only.

### M1 exact integration

Kernel: new neutral `cs/operator_inventory_view.py` ports approved readable tables,
scalar families and unknown/nonempty refusal from external producer-r2, adapting
binding from OFFLINE prototype to actual current raw/context/source, not copying
historical unavailable-invocation labels into runtime evidence. Capture writes
separate private `inventory-view.jsonl`, `inventory-view-envelope.json` and
`inventory-view-progress.json` alongside unchanged `discovery.json`. Existing
public CLI discovery output/raw receipt remains byte-identical; original full
canonical/raw inspection route stays available. Projection unknown/refusal leaves
raw route mandatory; do not turn a technical error into compact success.

Envelope schema/version pins view/raw exact SHA256/length, owner/nonce, supervisor
PID/start, original ancestry and kernel source identity. Actual child/native tool/
wrapper/current command bindings are verified against current genuine raw/native
receipts and stream, not invented by projection. Independent consumer recomputes
projection from raw using independent explicit path/type classification and table/
identity parsing; it never imports producer projection helpers or trusts a parity
boolean. Preserve full inventory universe/group/order/occurrence/workset parity.
Existing engine transport checks remain; no new MIME/header authenticity claim.

Capture security: existing validated absolute private directory; bounded reads
with O_NOFOLLOW/nonblocking, ownership/mode/nlink checks; CREATE_EXCL 0600 view and
envelope, no overwrite/symlink/hardlink adoption. Max raw/view4MiB compatible with
existing health bounds, depth64 and total cells bounded. Never truncate to page
limit. Atomic private progress updates under same context, reject unsafe existing
targets; no private artifact may escape run directory. Initial page plan uses
8192 counts/8064 stride through actual EOF; capacity is not a silent row cap.

Inspection: exact native Bash six-token dd over the pinned current view with
bs=1, nonnegative skip,0<count<=8192,status=none. Genuine successful matching
native result bytes must cover contiguously through EOF before any effect in
captured sequence. No grep/Read/different-file/stale-result/string-attestation
substitute. Raw full-route rules unchanged. If compact files exist but tampered,
reject that route; no alternate artifact is accepted on hash alone. Supervisor
health and independent Actor both bind raw/view/context/native coverage.

Progress: existing supervisor event loop, after a genuine native page result,
updates sidecar pinned to view hash/length with actual covered/uncovered ranges
and next exact dd command. Initial sidecar is zero-covered plan. Native can read
progress with already permitted bounded dd after a completed page, never poll or
launch new model calls. Progress is advisory only: no synthetic native event/user
message/tool result, no inferred completed page, no coverage from sidecar reads.
Terminal acceptance independently recomputes from original captured events.
If existing allowlist cannot permit exact paths without widening permissions,
STOP that mechanism for revised review; do not silently add permissions.

Ordering/truth: current health is post-terminal, so this component AUDITS observed
complete view before effects; it does not add runtime action prevention or claim
that a model cannot act early. Existing engine action guards remain actual gates.
Export ordinary inspection status separately and make independent acceptance
require it; a clean native terminal alone is never ordinary success. Required
six phases, selected-root fresh deep reads and RAW-detail UNINSPECTED labels stay.
No engine, scheduler, budget, model, auth, permission or provider mutation.

Actor worktree `/home/mal/worktrees/operator-assignment-recovery-resume-20261016`:
independent projection/binding/native view coverage in operational consumer,
separate focused tests with genuinely constructed company-neutral controls for
BOTH actor shapes. Maintain current full raw/strict lifecycle/business-read
negatives; source pair substitution cannot discharge acceptance. Avoid full
historical constant dumps. Current actual Café compact/native path remains
UNVERIFIED: pre-workset retained-negative and missing upstream input are not a
fresh capability verdict. Constructed controls must be labelled as such.

M1 checks focused first: projection/type/refusal/security; positive full raw and
full current-view paths; missing/clipped/grep/stale/wrong actor/process/start/nonce/
source/identity/native tool/result; early effect; table/root/order/hold/error/
observation/workset mutation; symlink/hardlink/oversize/atomic-progress and no fake
native progress. Actual V22 deterministic replay +bothactor constructed controls.
Then ONE kernel broad `bash tests/run.sh` and affected Actor suite; retain raw
pre-existing failures and repair in-scope failures/recheck affected only. No paid
runtime/provider acceptance inferred. Lead pre-edit health smoke is run and its
actual result retained. Fresh M1 integration reviewer before dependent adoption.

### M2 reviewed narrow actual adoption

After M1 APPROVED: lead stages exact candidate outside repos, preserving unrelated
local Stripe lines and clone-authored standing files, records source/package and
before/after hashes and exact installed diff. Do not reconstruct candidate from
public tag or touch authored company content. Stamping only canonical shared
operator/triage guide paragraphs for view paging, progress and selected-root RAW
limits, across existing three-host links; no duplicate workflow/permission change.

Reuse prior reviewed narrow activation helper/rollback pattern as a NEW exact
candidate stage: verify actual current bases, all four actual locks (both operator,
signup, acceptance), exact cron/control/source preimages and no owned live run.
If a normal run holds lock, wait bounded status rather than kill or shorten it.
Fresh activation review must cover exact stage/diff, immutable passing free
preflight, lock lifetime, conditional swap and rollback preserving foreign edits.
No activation on mismatching bases or failed free checks. Capture original pins,
package paths, control/cron and protected-draft identity without modifying them.

Apply under actual locks; rollback only own exact new candidate on failure, never
foreign edit. Independent installed verifier uses normal clone interpreters and
actual imports/capture/projection checks on both clones, source/package hash,
private artifact and preserved controls/standing docs/permissions/pins/cron plus
all required locks released. Free preflight no model/provider writes. No operation
on protected Café draft. No paid retry follows automatically.

### Closure and final gate

Lead reconciles affected kernel/Actor/clone durable and active docs, including
unchanged relevant contracts, new missing coverage and preserved historical
narrative. Mark obsolete lossless direction superseded without changing failed
reports. Explicit doc-end/doc-critic over affected docs+active shape; fresh separate
final reviewer through final-user path. Repair stale evidence, preserve unverified
Café/runtime/provider boundaries. Completion check/finalize in all applicable
repos only after real final APPROVED; qualified component completion is not whole
ordinary recovery. Baseline, public release/push and paid acceptance are distinct.


Prospective runtime measurement qualification: mandatory native envelope EOF plus
six view pages requires SEVEN separate dd calls, not six. Current observed
43,313 total native-needed bytes is about56% fewer than98,755 raw bytes; seven
versus13 calls is46.15% fewer calls. The earlier six-page/53.85% figure describes
aggregate byte capacity or view pages, never actual combined tool calls. Root
accepts this measured material reduction as the practical component criterion,
under unchangedUSD4 budget without a completion/compliance guarantee. Both artifact
EOF checks stay strong; no metric-driven transport complexity, field/schema loss,
cap/permission change or old M0 report rewrite. Prior failed gates remain historical.
This qualification requires plan review approval before M1 acceptance.

## Component delivery evidence

The source and installed component is delivered under the reviewed runtime scope;
this does not close the umbrella ordinary recovery. Final documentation approval
and checker finalization are the remaining component closure gates. Intended plan
transition is active to completed through checker finalization only.

- M1 source integration: APPROVED in `semantic-inventory-m1-review-r3.md`.
  Exact13-file source freeze is `semantic-inventory-m1-source-freeze-r3.json`.
  Account-prefix and background early-effect counterexamples are repaired and
  independently checked on both compact and full-raw paths.
- Actual V22 offline replay: unchanged raw hash,14groups,18assignments,
  49observations and80held roots; complete independent projection passes.
- The single broad kernel run exited2: an old Settings fixture, exact guide
  ledger and lead edit of a streaming shell script caused failures. The fixture
  and additive ledger are repaired; affected read-outcome/guidance gates pass.
  Current shell syntax and all gate65 tests pass. This is qualified affected-gate
  coverage, never a whole broad exit0 claim.
- Actual M2 four-lock preflight `activation-614b7d00ab3740b788266e5cf7e0bf6f`
  passes; fresh `semantic-inventory-activation-review.md` is APPROVED. Actual
  apply `activation-0adf4fa46e694e7f855a93dfcabf6c0b` exits0 installed_verified.
  Earlier held-lock preflight refused without mutation; no normal run was killed.
- Both exact117-file installed packages have digest
  `0f455dce156fd8ef00aaba02e8df60d56b314465f2be4d79a37d61250b01df9a`.
  Only five owned files differ from the previous116-file typed-read payload;
  unrelated local Stripe source is excluded and the other112 files preserved.
  Actor source/policy pins and four canonical guide paragraphs match candidates.
- Independent installed verification is APPROVED, all41 checks passing in
  `semantic-inventory-installed-independent-verify.md` and its machinechecks.
  Both normal clone interpreters load actual packages/Settings, pass private
  capture/dd/progress controls, independent Actor8 and incomplete-export refusal.
  Constructed controls launch no native model, engine or provider actions.
  Actual before/outside control inventories match; all four locks are free.
- Actual Actor84 initially fails one historical producer-identity fixture because
  actual current packages now require ordinary-inspection artifacts it lacks.
  The fixture explicitly asserts that real refusal, then isolates identity-only
  assertions with the inspection dependency mocked; genuine receipt acceptance
  and tamper controls remain independently covered by Actor8 on BOTH installs.
  This reversible test-only repair changes no runtime enforcement. Its focused
  real check and final review include the supplemental test file.
- Actual Actor84 repaired recheck passes all84 tests (93.401seconds); original
  failing log remains retained. Actual business-read5 and semantic-inventory8
  suites pass, and the free
  preflight passes with zero model calls, unchanged driver/cron, no enrollments
  and all four idle locks. Existing failed logs remain immutable evidence.

All named evidence is retained under the external bounded-triage-workset-20261018
workset. Current Café compact/native use, new native completion, selected-root
fresh reads, provider state, protected-draft behavior and USD4 feasibility remain
UNVERIFIED. V22 stays FAILED; no fresh signed ordinary PASS or public release.
