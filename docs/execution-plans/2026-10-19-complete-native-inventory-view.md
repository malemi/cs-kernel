---
status: superseded
---

# Complete native inventory view: gated feasibility plan

## Authority, dependencies and ownership

Scope: reviewed brief `../briefs/2026-10-19-complete-native-inventory-view.md`,
SHA256 `31327435abff87e31e0fc113f0f6225832b43701a0adebdcd5c66512197cf22c`.
Fresh brief APPROVED and metadata-only binding are retained externally at
`/home/mal/.local/share/ordinary-assignment-recovery-resume/bounded-triage-workset-20261018/complete-native-inventory-brief-review.md`.
V22 remains FAILED; no provider acceptance is superseded.

Current authorization is PLAN and fresh plan review only. After plan APPROVED,
coordinator permits one bounded M0 worker (15 minutes, no extensions/loops
without new facts). M0 owns external prototype/fixtures/report only. Lead owns
this plan and handoff; fresh reviewer owns semantic M0 verdict. No runtime M1
code, installation or paid continuation is authorized by this plan approval.

## Exact candidate schema

Separate private UTF-8 JSON view, schema `cs.complete_inventory.v1`:
`binding`, `schemas`, `objects`, `arrays`, `root` in fixed order. `binding`
contains raw file SHA256/length, owner UID, nonce, exact ancestry PID/start ticks,
source identity and native invocation identity from the authoritative receipt.
A separate envelope records view payload SHA256/length to avoid self-hashing.
Hash canonical bytes using UTF-8 JSON with ensure_ascii=False, compact separators,
no NaN, trailing newline, preserving input object key order. Duplicate JSON keys
and non-JSON values refuse rather than normalize. No company literal in code.

Tagged values are exclusively `["s",literal_string]`, `["n",number]`,
`["b",boolean]`, `["z"]`, `["o",object_id]`, `["a",array_id]`.
Schema definitions are ordered exact object-key arrays. Object definitions are
`[object_id,schema_id,[tagged_value,...]]`; array definitions are
`[array_id,[tagged_value,...]]`. IDs use first traversal occurrence, depth-first;
exact repeated objects/arrays may reuse one definition only when their complete
ordered typed value trees match. Object equality includes key order. Strings
remain inline initially for readability. No digest replaces an object definition.
Each ID and schema has a human-readable legend in the view; meaningful original
field names and all literal values remain visible. Raw wrapper is root, so all
binding and discovery fields can be reconstructed, not just discovery rows.

The raw artifact/public stdout/raw receipt remain byte-identical; nothing is
rewritten in M0. Independent decoder uses its own traversal and comparisons,
without importing producer parity logic. Reconstructed value must equal an
independently parsed ordered typed raw tree including every occurrence, key,
array order, scalar and distinction between absent/null/empty/false. Record
per-group counts and exact ordered workset membership independently. Unknown
fields are encoded by the same generic tree rule, never filtered.

Resource refusal bounds: 16MiB raw and view each, depth64, 200,000 distinct
object/array definitions, 200,000 schemas, 2,000,000 total tagged cells and
references. Strings are bounded by the byte ceiling, not truncated. Reject
invalid UTF-8, nonfinite numbers, duplicate keys/IDs, unknown tags, schema arity
mismatch, invalid type/boolean-as-number, missing/forward-unresolvable references,
cycles and overflow. M0 may discover tighter compatible bounds; changing schema
or semantic rules requires amended review before runtime work.

## M0: one external, offline feasibility experiment

Input is immutable actual V22 raw discovery, SHA independently recorded from
retained native artifact manifest and checked against private original. Copy to
external workset; never edit historical evidence or source trees. Use stdlib only,
no network, engine, provider, model or installed-package writes. Python runs -B.
Prototype producer, independently written decoder/parity checker, tests and view
live beneath external `complete-native-inventory-m0/`.

One worker, 15-minute limit. Deliver actual raw/view bytes, 8192-byte pages with
128-byte overlap (stride8064), ratios, full group/row/workset parity, literal
field visibility and failures. Material gain means at least25% fewer native
pages on V22, with no semantic omission. Do not tune endlessly to hit threshold.
If the exact candidate fails, report failure and stop; no alternative codec loop.
This numeric gate is not permission to cap or truncate future inventories.

Fresh semantic reviewer then reads the entire actual view and raw selected
samples/independent full-parity result. It must establish usable context, e.g.
trace an actual human hold, its actor/root/source/provider facts, current selected
roots and revisions, deferred/held reasons and ordering using only the view and
its legend; full nested proof must be accessible without Python/raw lookup.
No native/model run is needed. APPROVED requires meaningful readability plus
actual reduction plus independent full parity. Opaque reference chasing, missing
meaning, poor gain or negative failure => STOP/REVISE framing, not runtime M1.

Adversarial offline tests: deletion/duplication/reordering of rows, group swap,
wrong counts, changed selected/deferred/held membership/order/revision/sources,
changed hold/eligibility/completeness/reason/owner/root/provider facts, unknown
field loss, absent/null/empty/false confusion, duplicate keys/IDs, bad tags,
references/cycles/arity/limits, and raw/view/binding substitution. Include actual
V22 and small explicit fixtures that exercise each branch, not producer-shaped
assertions alone. Preserve historic raw V22 negative unchanged.

## Prospective M1 design boundary (not authorized to implement)

After M0 APPROVED, seek coordinator's bounded runtime source scope and fresh
review of exact candidate/impacts before edits. Likely kernel responsibility:
new neutral private view codec, secure artifact creation alongside discovery,
inspection recognizer and canonical shared guide. Independent Actor responsibility:
separate parity/native coverage validator and strict negative fixtures. No engine
guard or scheduler change. Both clones eventually receive the same reviewed
payload; no adoption occurs at M0.

Exact paging candidate: retain native Bash six-token `dd if=EXACT_VIEW_PATH bs=1
skip=N count=M status=none`, 0<M<=8192, initial offset0 and overlapping stride8064
through EOF. No grep, Read, TaskOutput, summaries or bytes from another artifact
count. Original full canonical/raw inspection remains strict compatibility route.
Independent validators first check raw provenance, decode/parity and binding,
then exact current view bytes and genuine native tool/result/process bindings,
contiguous coverage and no effects before inspection. Existing strict negatives,
all six phases and selected-root deep evidence remain mandatory.

Deterministic progress candidate: existing supervisor native-event loop updates a
private progress sidecar only after matching successful view-page results. It
contains pinned view hash/length, observed byte ranges, remaining byte ranges and
next exact dd command; initial sidecar is the full page plan with zero coverage.
Native may read this sidecar using the same already permitted dd surface after a
completed page; no polling, retries, extra CLI verb or permission widening. Such
reads are hints only, never inspection evidence. Supervisor never injects a
synthetic native event, user message or fabricated result. Terminal acceptance
recomputes coverage independently from genuine captured events; progress is not
trusted. Actual allowed-tool compatibility and progress availability/race handling
must be verified free before source approval; if unavailable, revise the mechanism
rather than widen permissions or pretend live feedback exists. Secure atomic
writes, private ownership/mode, nofollow bounded reads and current-context binding
are mandatory. Byte decoding/clipping and asynchronous task results retain current
fail-closed behavior; no inferred completed page or fixed output-limit waiver.

This mechanism gives source-owned measurable remaining offsets without altering
public discovery stdout, model budget or action authority. It cannot force a
model to comply; actual ordinary acceptance remains separately required.

## Verification, rollback and delivery

M0 touches only disposable external files; rollback is remove that new workset,
retaining its report and reviewed immutable input reference. No locks/processes/
cron/enrollment/pins/controls or installed source change, no live preflight needed.

Any future M1/M2 needs separate bounded implementation, milestone review, source
and independent Actor checks, installed preservation/free verification, doc-end,
separate final review and explicit paid-case authorization. Free failures block
paid acceptance. No automatic retry, higher budget, fixture priority, relaxed
coverage or operational success claim follows from this plan.

## Checkpoints

- Brief fresh review: APPROVED; metadata-only hash rebound above.
- Plan fresh review: APPROVED; external `complete-native-inventory-plan-review.md`,
  reviewed SHA256 `d28739bd2ad1cfbf86c73d478caee47f4a35c30acd975583e3d1f68cfd3ba1d8`.
- M0 execution: FAILED / STOP at free reduction gate. Actual V22 raw98,755
  bytes/13 pages becomes84,433 bytes/11 pages (15.38% fewer pages, below25%;
  passing would require at most9). Independent ordered typed parity passes;
  75 adversarial controls reject. External evidence:
  `/home/mal/.local/share/ordinary-assignment-recovery-resume/bounded-triage-workset-20261018/complete-native-inventory-m0/tests/report.json`
  and sibling `output-manifest.json`. No alternate candidate or runtime edit.
- M0 semantic review: not run because the mandatory free reduction gate failed.
  Readability/runtime/native inspection remain unverified; no adoption permitted.
  Reframing needs coordinator direction; no automatic extension or paid retry.
- Runtime source/installation/provider acceptance: not authorized here.

Direction superseded by [semantic global inventory](2026-10-19-semantic-complete-inventory-view.md). The lossless M0 FAILED reduction result and all historical evidence remain unchanged; no runtime adoption of that candidate occurred.
