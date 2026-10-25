---
status: active
---

# Ordinary assignment recovery

Approved brief: [ordinary assignment recovery](../briefs/2026-10-15-ordinary-assignment-recovery.md).

## Classification and boundaries

Substantial repair: ownership interpretation, trusted recipient routing and bounded discovery behavior change. The fast path does not apply. Three dependent milestones below keep source acceptance separate from installed acceptance. No database migration, new ownership ledger, provider/model change, historical rewriting, automatic assignment approval or public release is planned.

The engine owner works in ACTOR `/tmp/operator-assignment-regression-actor-candidate`, against each deployed family's actual preimage. MAIN is not a deployment artifact. The kernel owner changes only assignment consumption/scheduling and its focused tests in `cs-kernel`. The lead owns exact host configuration, activation, ordinary verification and documentation closure. Preserve concurrent changes in every repository. Prefer one implementer for the coupled authority change; delegation is useful only for independent review or the separate kernel transport change after the contract is fixed.

## Grounded decisions

The captured two failure traces and `repair-framing.md` are under `/tmp/cafe-assignment-current-trace/`. Six relevant ACTOR modules were byte-compared with the installed `operator-context-readonly-1aa6464a3705` family: mail, store, evidence, projection, trust and draft policy all match. The installed evidence hash remains `d160ab7af25a51d819bc01083bc6672a74d82af139a6fd2562e0fb516f07cbcd`.

`task_assignment_mail.Ancestry.resolve()` rejects a requested anchor merely because it has a parent. `rows()` also assumes its stored grouping is the first References identity. Removing either check alone would leave `store.get()`, preview/commit, draft-write CAS and final effects looking up independent keys. Resolve the bounded connected RFC identity once through a shared engine authority helper instead. Use the sole existing task key within that proven component, preserving its row, events, revisions, receipts and signed payloads. If no task exists, choose the proven earliest RFC ancestor consistently. Refuse multiple existing task records rather than merge/delete history. Recompute component membership under final write validation; new connecting evidence or a newly assigned component must invalidate stale admission.

Private rows alone cannot assert a missing edge or mailbox ownership. Traverse only exact Message-ID/References/In-Reply-To relationships within authenticated mailbox scope, with existing identity, duplicate, cycle, node/edge and deadline limits. Authenticate provider copies through the same component proof. Do not match subject or infer absent ancestry. Cross-profile peers must agree on the resulting authority identity or remain held; a peer with no local component cannot contradict an existing shared task under a different anchor by returning authoritative absence.

Delivery routes are distinct from member sender aliases. Add an optional strictly validated root-owned exact mailbox-route document under the existing protected configuration boundary, keyed by company, member and configured mailbox identity; absent routes preserve existing direct-recipient behavior. Both live reply evidence and snapshot must use the same recipient check. A configured route authorizes a specific recipient address delivered to that mailbox, never outbound From identity. Validate both scoped and live inbound headers, exact provider mailbox binding and unchanged recipient identity. Arbitrary Delivered-To, caller JSON, a company-domain wildcard or provider presence alone does not establish a route.

The lead may activate an exact route using the owner's repair authorization, documented company address and bounded authenticated mailbox/header/configuration evidence. Keep that evidence and the root-owned configuration preimage. Separately, documented equivalent Ivan mailbox addresses may extend sender membership only after authenticated actual Sent/header evidence confirms the exact alias; recipient routes do not imply this extension. Unproved aliases remain held, without asking the owner to perform technical setup.

Kernel source establishes an additional independent cause: `unanswered.py` sorts keys lexically, `projections()` sorts again, each local batch consumes up to 90 seconds before peer batches, and one request TimeoutError stops the entire multiplexed reader. Four workers and a global 180-second deadline cannot promise arbitrary historical coverage. Repair useful-work priority and complete peer coverage before spending remaining time on history; do not merely raise deadlines or remove peer checks.

## M1 — One authority across connected anchors and exact delivery routes

Owner: engine implementer. Depends on approved plan. Candidate surfaces: `task_assignment_mail.py`, `task_assignment_trust.py`, `task_assignment_store.py`, `task_assignment_projection.py`, `task_assignment_evidence.py`, `task_assignment_draft_policy.py`, assignment RPC adapter and actual final-effect consumers found by direct callsite search. Extend existing helpers rather than build a second ledger or migration.

1. Add bounded component resolution and component-aware task lookup. Preserve requested thread identity separately from authoritative task key. Add explicit authenticated resolution metadata where the wire must return a task stored under another anchor; update kernel validation to accept only that exact bound shape, preserving the old shape for unchanged roots. Never rewrite task keys inside returned historical rows. Mutation preview signs the selected authoritative key, commit verifies that exact signed intent and rechecks the full component under CAS. Old grants that would create a second task through a connected alias refuse.
2. Apply the same authority to projection, evidence, source-owner closure, preview/commit, scoped draft-write CAS and the installed scheduled/final-send guard. Inventory direct `AssignedTask.thread_key` queries and projection consumers; no path may retain an exact-key-only bypass. Active human assignments can establish a hold before expensive provider work. Closed coverage still requires fresh complete creator evidence. Existing sender, mailbox, grant and read-only boundaries remain binding.
3. Add the optional protected exact delivery-route configuration and shared scoped/live recipient validator. Keep sender alias validation separate. Prepare only evidence-supported exact configuration; preserve malformed/missing/writable configuration refusal and no-route backward behavior.

Verification to implement and run: captured parented-anchor/trimmed-reference regression from both anchors; existing assignment under either anchor; concurrent assignment appearing before draft/send/commit; two preexisting component tasks held with unchanged audit; cycles, duplicate conflicting identity, missing ancestors, mailbox crossing and graph/deadline exhaustion refused. SQLite/RPC tests must exercise preview, signed commit replay, close and actual scoped draft/final-send guards, not only graph helpers. Recipient fixtures cover exact forwarded route, live/scoped recipient mismatch, direct recipient, unconfigured alias, spoofed delivery header, malformed/writable configuration and unchanged outbound identity. Run focused `engine/tests/assignments` and directly affected final-effect tests in each changed baseline family. Save real commands/results and source hashes; no paid calls.

Exit gate: fresh source/integration reviewer approves component consistency, unchanged human priority, route authority and preserved family differences before activation or dependent kernel behavior.

## M2 — Recent useful work gets complete bounded peer coverage

Owner: kernel implementer. Depends on M1 wire contract and its source gate. Surfaces: `cs/unanswered.py`, `cs/task_assignment.py`, `cs/rpc_reads.py`, focused assignment/reader tests and any CLI consumer required by the exact resolution metadata.

Build stable candidate order from eligible inbound work, latest received date first with deterministic ties; preserve that order through projection instead of lexical re-sorting. Schedule small recent-thread windows through all configured distinct peers before moving to historical windows. Reuse bounded multiplexed transports and preserve a global concurrency cap of four and the 180-second projection wall bound, including cleanup. Allow the current thread window's peer requests to progress concurrently rather than spend the full local backlog budget first. Keep each authenticated peer connection separate. Do not turn a single per-key timeout into fictitious unavailable results for healthy queued peers/threads; on genuinely broken transport retain explicit failures and use only bounded reconnection within the original deadline. No unbounded retries or dispatch after cancellation.

Return exact per-thread incomplete results for scopes not completed: distinguish capacity/deadline deferral from observed provider evidence failure. Every unverified peer still holds that thread. Do not relabel partial work healthy or hide old scopes from health artifacts. Older work remains eligible on later ordinary runs; this change guarantees priority within measured capacity, not that an arbitrarily large queue clears in one tick.

Verification to implement and run: real multiplexed protocol fixture with slow historical keys lexically preceding fresh PROVA-like work; fresh priority survives both discovery ordering layers and completes all four peer scopes inside the unchanged bound. One timed-out unrelated key cannot cancel independently healthy peer results. Exhausted capacity, failed peer auth/company binding, malformed component metadata, differing tasks/components and active human assignment remain UNKNOWN/conflict/held. Existing reader cleanup/cancellation tests and `tests/test_task_assignment.py`, `tests/test_rpc_reads.py` run without model/provider calls. Use the same installed CLI entry point against fixture transport to prove the actual consumer result.

Exit gate: fresh milestone reviewer approves complete peer merge, actual time/concurrency measurements, metadata validation and zero guard relaxation. If measured latency still exceeds capacity, retain and report the exact remaining constraint before deployment claims.

## M3 — Preserved activation and ordinary outcome

Owner: lead. Depends on M1 and M2 approvals. Capture per-service actual interpreter/import path, full owned-file preimages, package/configuration hashes, service identity and clone permissions. Apply only reviewed deltas to each necessary installed family; do not replace an entire family with MAIN or restart unrelated tenants. Shared authority semantics must be active on every affected company peer before ordinary work resumes. Preserve Qonto and unrelated MrCall health adoption. Install exact route/alias configuration only after its evidence check. Deploy the kernel delta under the real clone lock, preserving health hooks and custom workflows.

Use zero-generation authenticated projections for the two captured failing conversations and the already existing manual PROVA-001 thread. Compare requested root, resolved authority, peer completeness and held human candidates. A legitimate human-reply candidate may correctly change from technical UNKNOWN to needs-assignment; it is not automatically released. Record whether any remaining technical hold is provider-unavailable, ambiguous ownership or capacity-limited.

Then observe one ordinary Café draft-mode tick using its actual wrapper and installed interpreter. Prefer its next useful eligible work; inspect the existing own-address draft rather than regenerate it. Read back real engine draft plus provider copy, exact inbound/recipient bindings and absence of duplicate drafts or sends. Record ordinary discovery coverage and deterministic alarm outcome. A paid classification/generation, if the ordinary tick requires it, is normal useful work and must be identified explicitly; monitoring and diagnostic projections remain symbolic. Run one fresh exact-candidate two-clone operational acceptance required by AGENTS.md: actual normal MrCall reply independently received and actual Café provider draft, with unchanged assignment/ACK/no-extra-effects checks. Reuse the existing retained harness and do not repeat successful gates or paid campaigns without new failure evidence. Historical R9 cannot certify the new source.

Rollback: restore owned source/configuration preimages and service pin only for affected tenants, retaining all task/audit/receipt data and useful drafts. Because no schema migration or history rewrite occurs, no database rollback is planned. Disable the new route before returning to an engine that cannot validate it. A rollback may restore conservative holds; it must not present them as operational success.

Close affected engine assignment/runtime docs and kernel discovery/runtime docs, including unchanged contracts that constrain final effects. Preserve historical R9 evidence unchanged. Run mechanical closure, explicit doc-critic and separate fresh final review through the installed-user path before baseline advancement. Keep MrCall health installation/notice proof in its separate record.

## What this establishes and what it does not

Successful completion establishes consistent authority for the captured RFC component, verified exact delivery routing, measured recent-work peer coverage and one actual ordinary draft-mode outcome under the retained guards. It does not establish every historical conversation is actionable, globally complete mailbox recovery, automatic human-assignment resolution, native Gmail edit/send reconciliation, installer acceptance or public-release readiness. The mandatory two-clone operational run certifies only its exact tested case, not broad MrCall customer-workload recovery. Any unverified route, conflicting task history, unavailable peer/provider or deferred capacity scope remains visible and held with its exact reason.


## M3 recovery amendment — observed historical Sent compatibility

The fresh V4 operational attempt remains FAILED and unsigned. Its actual MrCall
normal operator could not compose a reply because the separately owned workflow
bridge rejected ordinary chat with `history_invalid`. That bridge owner is
preparing a source correction and free regression checks; no new paid case runs
before the combined installed path passes read-only checks. The exact failed
candidate and unchanged evidence are retained under
`/home/mal/.local/share/mrcall-operational-evidence/2026-10-15/ordinary-assignment-recovery-v4`.

Bounded authenticated provider headers also reproduce twelve MrCall technical
scopes in four groups. The narrow implementation proposal is
`/tmp/cafe-assignment-current-trace/mrcall-source-diagnosis/repair-proposal.md`
(SHA-256 `0d8a5b6c87d63d10cac053e7737952445054e92c4e06be4871d78cc21c46dad1`).
Its framing retains this approved brief's constraints: preserve stored task keys,
audit, source/provider history and all human holds; no authority from subject,
thread grouping, HTML decoding or caller claims. A valid direct target already
in a proven References chain may be accepted only with exact scoped target and
unchanged graph/CAS refusal checks. Genuinely omitted legacy References may be
observed compatibly only when live References is exactly the existing direct
target and all other identities match. Verified outbound follow-ups remain
human-held and cannot confirm external replies or close work. A malformed Sent
message may expose only an exact-message human observation, never fabricated
canonical component completeness, task absence or mutation/send authority.
This observation fallback requires no directly retrieved task; existing task,
events, source owner and held disposition always take precedence.

The engine owner implements reviewed rules and focused adversarial SQLite/RPC
checks. The kernel owner handles only any required explicit held-observation
contract, preserving unknown peer failures and existing component/authority
validation. A fresh amendment review precedes edits; fresh source integration
approval precedes preserved activation. Recheck all twelve actual scopes without
models before one new exact-candidate normal operational acceptance. Any remaining
technical failure stays visible and prevents completion. Rollback, documentation
closure and separate final review remain as specified above.


## M3 support composition dependency

The amended brief permits a separately reviewed support-only finance privacy-fence
repair. Its owner supplies immutable current-prefix preimages, exact approved
source deltas, focused refusal tests, and a read-only reconstruction of both
ordinary chat and drafting using actual current company instructions, captured
native inputs and the complete receipt index. No real provider call, reservation,
receipt deletion or banking operation supplies this proof. Chronology alone,
generic prompt exemptions, length thresholds and unchecked caller assertions
cannot establish benign content. Any exact public occurrence exception requires
independent qualification and a strictly protected, UID/company/revision/hash-bound
root policy; private or overlapping financial content remains refused.

The lead integrates only those approved files into ACTOR when every existing-file
preimage matches, and into support's first immutable import prefix. An auxiliary
PYTHONPATH tail cannot override its existing client module. Other company profiles
receive only the approved assignment delta; the separate Qonto process, source,
connections and bank data remain unchanged. A fresh preserved-activation review
checks the combined package, effective module paths/hashes, exact policy preimage
and protection, unchanged controls and conditional rollback under all three real
operator locks. No new public release or source-history rewrite is included.

Retain the existing passing component and kernel checks. Before another paid
normal-path case, all twelve captured scopes must be rechecked read-only and the
actual current composition reconstruction must pass every retained receipt guard.
A known failure prevents another paid retry. Temporary maintenance locks avoid
repeating the failed cron while this repair is prepared; release them for the
atomic activation and normal acceptance, then restore normal scheduling.


## M3 reboot resumption

Restore the retained failed candidate into a persistent worktree and recover
tool source from authentic transcript records without replaying shell actions.
Use existing immutable V5 packages and exact current kernel module; capture
new actual PID, complete resource inventories, baseline preimages and protected
configuration. A fresh activation reviewer checks the recovered helper and all
owned targets before effects. Preserve exact old/source-independent Qonto.

For the harness, retain the original historical policy/bindings, reconstruct the
fixed 342/352 core/overlay inventory from those actual preserved packages, and
replace lost temporary report dependencies only with independently reviewed
current composition evidence and permanently pinned records. The normal current
route must check both original core/overlay preservation and every V4-to-V5
resource delta, including exactly two approved new support helper files. Keep
all strict run/outcome checks unchanged. Verify mutation refusal for a missing
record, wrong digest, undeclared added/removed resource, wrong peer/native
producer and changed policy, then obtain a fresh bounded harness integration
review before the single paid acceptance. Historical R9/V4 records are untouched.

Run the twelve exact roots recovered from permanent discovery against isolated
V5 under verified session and read-only actual stores. Reconstruct missing
finance policy against current source only with independent qualification and
all-receipt free replay. No blanket prompt exemption or threshold is permitted.
Finalize documentation only after actual acceptance; preserve incomplete
obligations honestly if new technical failures emerge.


## M3 provider-read correction

Depends on the fresh approved provider-read brief amendment. Engine ownership is
`task_assignment_sent_index.py`, `task_assignment_evidence.py`, their focused
assignment tests and, only if the existing client API cannot express complete
bounded header search, the narrowly required method in `email/imap_client.py`.
`task_assignment_projection.py` additionally owns the read-only observation-scope
adapter and bounded positive held-witness observation. After complete component
candidate discovery, one fully verified human/internal/own-Sent follow-up witness
may end further reply reads while leaving the projection incomplete and held.
A known unavailable discovery item anywhere in the list or an earlier unavailable
reply prevents this shortcut. Automatic-reply absence requires every candidate;
final actor, route and latest-task checks remain mandatory. No prior failure is
relabelled successful. Other V5 assignment/store/final-effect code and all kernel
source remain unchanged.

For the measured remaining provider latency, fetch target identity headers,
including Date and PEC markers, without downloading an ordinary target body.
PEC identities requiring envelope content retain full target reads. Sent source
bodies remain fully read for automation classification. Evidence owns a scoped
ContextVar and client factory: one serialized owner/mailbox client may be borrowed
only within the current projection and original deadline. No cross-request,
profile or owner reuse, global socket pool, RPC client serialization or proof
cache is allowed. Every observation and final reobservation performs fresh reads.
Projection exits release evidence guards before disconnecting clients and resetting
the scope, including exception paths; standalone callers retain explicit closure.
Focused tests cover target Date/PEC identity, owner/profile mismatch, fresh reads,
borrowed versus owned closure, exceptions and serialized race/guard ordering.
No source is deployed from MAIN.

Implement complete component-specific Sent search as described in the brief.
Use exact sanitized RFC identifiers and bound total query, UID, graph and fetched
header sizes. Require stable UIDVALIDITY/UIDNEXT/count before and after the entire
fixed point. Reject partial/missing/duplicate provider responses, ambiguous IDs,
missing required ancestry and unsupported searches. Component results may be cached
only with exact scope and fresh folder identity; never masquerade as global absence.
For absent local References, independently validate the direct target's live
identity/recipients/ancestry, require the exact inherited chain and retain final
source reobservation and automation classification.

Run the proposal's protocol/SQLite negatives, existing directly affected evidence,
projection and mutation/final-effect checks without models. A fresh source
integration review precedes staging. Build a new immutable family from each
actual V4 baseline with only exact approved current deltas, retaining the support
finance correction/policy and every unrelated resource. Freeze actual changed
paths in the harness; no generic allowance for new modules. Fresh staged imports
and all twelve real read-only roots must pass, with legitimate human holds
preserved, before atomic activation or the single paid operational case.
Reuse unchanged kernel/full-suite, finance replay and helper results; recheck
only newly affected bindings, source and outcomes. Preserve every failed V5
receipt and its reviewed inactive package without relabelling them successful.


## M2 full-batch scheduling amendment (2026-10-16)

Status: pending fresh plan review; no production edits.

The free installed-package baseline completed in 172.461 seconds: 24 healthy reads followed by two timeouts. The first timeout began with only 15.425 seconds of the overall budget remaining. All 26 children were reaped. This establishes cumulative batch-budget exhaustion for the retained root union; original unlogged ordering remains unverifiable.

Problem: the current projection reader serializes entire requested-thread windows. With two configured actors, at most two of the global four request positions are used. Every window waits for its slower actor before any next requested root starts. Actual free baseline timing is captured separately, without changing the worker.

Keep the engine as the only assignment authority. Preserve all strict projection validation, company/actor binding, component alias validation, original and canonical holds, observation-only authority, creator exception, and per-key result keys. Preserve the 40-second engine operation, 60-second caller, 180-second global deadline and fixed global four-request cap. No new retries or caching of assignment evidence.

Use one bounded FIFO scheduler for both requested and canonical scopes. Each configured actor has at most two dispatched requests, and all actors together at most four. The first useful root must still dispatch to every configured actor before any historical root consumes the spare slots. Beyond that first root, requested scopes follow caller order while a slow actor cannot prevent another actor using an available position. Canonical fallback jobs consume the same positions; no synchronous fallback may bypass the global cap. A root can merge only after all its required original and canonical outcomes are known or explicitly unavailable.

An actual client transport timeout retains its physical slot reservation and blocks new requests to that actor for the run, as today. Other already-dispatched scopes may finish and retain their evidence. Do not assume socket close cancels engine provider work. Distinguish an undispatched scope whose global deadline expired from a dispatched transport timeout in the existing fail-closed reason; neither authorizes an action. Empty capacity remains UNKNOWN, never absent/normal. Token reuse remains ephemeral and per account; two workers cannot introduce unsafe credential persistence.

Verification must use a real local WebSocket server with delayed request work surviving socket close. Measure global maximum four, per-actor maximum two, FIFO account fairness, all peers for the first root, exact single versus bulk merge parity, canonical lookup sharing capacity, original conflict and observation holds, and no replacement after timeout. Include enough consecutive healthy delayed roots that the current serial windows exhaust a scaled 180-second deadline while the bounded pipeline completes; a fresh-one-root fixture is inadequate. Reuse the unchanged isolation auth/DNS/cleanup tests and focused assignment tests. Only after review may the installed-package candidate run one complete no-model assignment-only batch against the captured union, retaining the same qualification about original unlogged order. No paid ordinary case is needed to select the scheduling fix.


## M3 projection protocol overhead amendment (2026-10-16)

Keep generic IMAP behavior unchanged. Add a default-off per-client projection-connection context. Only while the existing original-deadline provider guard and request-owned serialized projection context are active, return an already connected client from _ensure_connected after the existing deadline/connection check without sending NOOP. Cold connection/authentication, actual command status failures, all EXAMINE observations and UIDVALIDITY/UIDNEXT/count comparisons remain unchanged. No reconnect retry, shared socket/proof cache or folder-freshness reduction is added.

Evidence observation marks direct projection scope; the provider factory explicitly disables protocol reuse in its standalone fallback. Only marked scopes enter the new client context. Malformed-own-Sent borrows through that factory and uses the existing exact header target helper, including Date, PEC detection and full PEC fallback. Preserve final raw ancestry, sender/recipient/date, identity, routes and row-digest checks and the incomplete observation-only human hold. Ordinary Sent reply evidence retains full body automation classification.

Focused negatives: unchanged generic/standalone NOOP behavior; projection skips NOOP but preserves fresh folder-state mutation refusal; actual command failure remains held without reconnect; context resets on exception/profile mismatch; malformed ordinary source body is unused; PEC full fallback failure held; malformed signed confirmation remains refused. The prior forty-second failure remains unverified at command level; this proposal does not claim permanent provider recovery or complete batch capacity.


Measured grounding: the free kernel-candidate batch returned 41 of 52 original
account reads in 172.135 seconds and failed; two engine SOURCE_UNAVAILABLE
responses and four outer timeouts remain retained. No adoption or paid case
followed. A transparent two-root concurrent V8 probe measured 4.042 seconds for
the malformed scope and 14.159 seconds for DB9, with negligible index-lock wait.
DB9 spent 4.225 seconds on 19 NOOPs and 2.959 seconds on 12 EXAMINEs; its full
source fetch took 0.832 seconds. The earlier 40-second operation remains unknown.
The approved brief's bounded provider-read and request-owned client scope governs
this amendment. Ownership is evidence.py and imap_client.py plus directly affected
tests; projection, final-effect/store guards and kernel source remain frozen.

Fresh plan approval precedes these source edits, followed by focused tests and a
fresh source integration review. Run the existing representative actual read-only
roots and paired concurrent timing against isolated staged source, preserving
verified auth and both query-only stores. Stage each of the six V8 baselines with
only the approved two-file delta, transplanting only the changed IMAP methods in
the heterogeneous peer baseline; preserve every unrelated byte and the finance
policy, excluded Stripe runtime, configs and useful drafts. Fresh activation
review covers exact staged imports, preimages, real locks and conditional rollback.

A reviewed reversible engine adoption under maintenance locks may precede the
full captured-union probe because that probe must exercise the native active RPC
path. It does not authorize normal model work. Run the complete 26-root no-model
kernel-candidate batch against the adopted engine source before kernel adoption
or any paid case. If it fails, retain actual outcomes, keep the normal jobs held
and diagnose or conditionally roll back; never normalize partial coverage as PASS.
Do not raise the global four/per-actor two or 40/60/180-second bounds, retry reads,
cache authority, omit required roots or weaken health/acceptance. Only complete
free coverage permits the separately reviewed two-clone kernel adoption, exact
harness binding refresh and one fresh normal paid acceptance case.


## M2 measured-capacity implementation amendment (2026-10-16)

Depends on the fresh approved measured-capacity brief amendment. This supersedes
only the earlier 180-second global projection bound: set it to 360 seconds
including cleanup. Keep engine40/caller60/read-batch90, physical global4/actor2,
timeout reservations, authentication, validation and all final effect guards.
Ownership: cs/task_assignment.py and directly affected tests only; rpc_reads.py
and all six active V9 engine packages remain unchanged. No retry or proof cache.

Order each actor's pending canonical work by its originating requested root so
an early useful root's required canonical observation precedes later history.
Keep original root order and all canonical jobs inside the same controller/caps.
Do not reuse evidence across requests or omit any original/canonical scope.

Run focused assignment/reader tests plus real-WebSocket scaled global-bound,
unchanged caller/cap/timeout-reservation, and early-canonical priority regressions.
Freeze exact changed source and obtain a fresh M2 source integration verdict.
Then run ONE new native no-model replay of the same26root union against actual
V9, actual clone auth, and the frozen candidate. Require all52original and every
canonical observation valid, no technical failures, actual elapsed<=360 and all
children reaped. Preserve prior failures and the original-order qualification.
Only actual PASS permits rebasing the pending two-clone adoption packet to the
new source and actualV9 preservation, then fresh activation review/check/adoption,
exact harness binding review and one fresh normal operational case. Otherwise
retain failure and continue diagnosis without paid work. No engine restart or
public release is authorized by this kernel amendment.


## M2 contention-safe actor admission amendment (2026-10-16)

The 360-second union27 replay dispatched all54original and two canonical scopes
but retained four typed Mario SOURCE_UNAVAILABLE responses and one outer timeout.
After all remote handlers drained, the exact five failures were read sequentially
under unchanged40-second operations: all complete NORMAL in12.787,7.171,8.911,
14.376 and6.652 seconds (49.900 total), with negligible index-lock wait. The actual
concurrent peer trace measured shared-index lock wait. These measurements justify
preventing overlapping projection RPCs to the same authenticated actor instead
of another engine change. They do not certify future whole-batch success.

Keep the approved physical ceilings: at most four global and at most two per
actor reservations, including timed-out work. Admit only ONE active projection
RPC per actor; other actors continue independently in caller order. Every original
and canonical scope uses this same controller. Keep the360global,40engine,
60caller and90read-batch bounds, early canonical priority, timeout reservations,
all validators/holds and all final action guards. No retry or authority cache.
Ownership remains task_assignment.py and directly affected tests only; active
V9 engine source and rpc_reads.py remain untouched. This conservative admission
is within the brief's maximum ceilings and removes no authority requirement.

Add a real-WebSocket backend with a shared per-actor critical section and an
operation deadline including lock wait: two overlapping calls must reproduce
source unavailability, while one active call completes the same workload under
the scaled360bound. Preserve asymmetric actor progress, canonical priority,
physical reservations after timeout, first-root peer coverage and global4 with
four distinct actors. Update synthetic tests that assumed same-actor parallel
backend capacity; do not claim that abandoned assumption still models this engine.
Run focused tests, freeze and obtain a fresh M2 source review. Then run ONE fresh
native no-model replay of the exact union27/all54original+requiredcanonical scopes
with no other provider work. Actual valid coverage and cleanup<=360 precede
kernel adoption, harness binding and any paid acceptance. Earlier failures remain
immutable. No additional engine activation or public release is authorized.


## M2 bounded transient-read recovery (2026-10-16)

Approved brief: final Bounded transient-read recovery amendment; exact approved
brief and review retained in batch-read-recovery/transient-recovery-brief-review/.
Previous full batches remain FAILED; isolated/native success is diagnostic only.

Ownership: existing M2 worker owns cs/task_assignment.py and directly affected
tests only. No engine source, rpc_reads.py, standalone project/final guards,
mutations, model calls, installed files or policy changes in implementation.

Change only project_many's global bound to600seconds including original cleanup.
Keep operation40/caller60/read-batch90/global4/active-per-actor1. Inside the same
scheduler, validate each completed response with existing _validate_projection
before deciding recovery. Eligible only: no transport/error, exact authenticated
actor/thread and structural validation, state unknown, complete false,
hold_auto_reply true, reason SOURCE_UNAVAILABLE. A retry is fresh RPC, with no
merged authority or retained provider proof.

Track a once-only recovery budget by authenticated actor and exact requested
thread key for the whole batch, shared across original/canonical jobs. Do not
reset the budget when root aliases repeat that exact key. Release the completed
attempt's active reservation before enqueueing one fresh attempt in the same
actor queue at its originating root priority. Pending recovery delays recording
that observation and resolving dependent canonical/peer state. All reservations,
original global deadline, cleanup cutoff and transport-timeout actor blocking
remain enforced by the existing controller. At cutoff retain the last typed
held result or explicit capacity failure; never drop the scope or manufacture
success. Other hold/error reasons and invalid envelopes never retry.

Add real-WebSocket checks for SOURCE_UNAVAILABLE then independent success; two
SOURCE_UNAVAILABLE responses end held with exactly two calls; canonical recovery
uses same controller and once-only budget; invalid identity/structure, human
holds, conflicts, other UNKNOWN and transport timeout do not retry. Check
asymmetric progress/global4/actor1, scaled600deadline including cleanup and
unchanged per-call bounds. Preserve existing56focused tests; add focused semantic
cases instead of broad redundant suites. Freeze source/test logs and fresh M2
source review before dependent work.

Then ONE full native no-model union27 replay: exact54original scopes plus every
required canonical scope, retries accounted separately; all terminal observations
valid with no technical UNKNOWN or omissions and no owned live child, elapsed
within600includingcleanup. Preserve initial failures and retry diagnostics.
Only actual PASS permits pending two-clone packet rebase to this exact source,
fresh activation gate/check/adoption, strict harness binding/review and one fresh
ordinary operational case. On failure stop paid work and retain actual failure.
Rollback: pre-adoption source can restore c83d from frozen-v4 verbatim; installed
clone packages remain unchanged until separately reviewed atomic adoption.
No engine restart or public release is authorized by this amendment.


## M1 early exact positive human hold (2026-10-16)

Depends on the approved final Exact positive human-hold admission brief amendment.
Ownership: ACTOR engine/zylch/services/task_assignment_projection.py and direct
projection tests only. Existing evidence.reply, provider freshness, local ancestry
and all final route/actor/task/component rechecks remain mandatory and unchanged.
No kernel, store, IMAP, Sent-index, finance or Stripe source edits.

For complete stored component/no task only, reuse the already loaded scoped rows
to select bounded exact local candidate IDs: nonempty sender contained in the
authenticated actor's own aliases, valid source ID, different Message-ID from
requested root, unique row identity, component membership verified by the existing
evidence.reply. Never use another member's private data, local automation flag
or body as proof. A candidate is not authority. Skip this optimization if safe
candidate selection cannot be expressed from current scoped rows or exceeds the
existing20-candidate limit; retain the old discovery path.

Use evidence.reply with the SAME original40-second projection deadline and
request-scoped client. Only a complete verified NONAUTOMATIC_MEMBER_REPLY_CANDIDATE,
INTERNAL_MEMBER_CORRESPONDENCE or OWN_SENT_EXTERNAL_FOLLOWUP can produce the early
state needs-assignment/complete false/hold true/reason NEEDS_HUMAN_VERIFICATION.
Run the existing final checks before returning, including complete/component
equality and latest task. Do not add fields that claim absence or handled scope.
If any observed candidate reply is unavailable/incomplete/contradictory, retain
that UNKNOWN and prohibit a later positive witness from waiving it. Without an
eligible complete positive witness, run the unchanged full Sent fixed point and
all-candidate automation/absence logic; early AUTOMATIC alone never provesNORMAL.
No cross-request proof cache or widened deadline.

Focused tests: valid known local candidate bypasses discovery only after FULL
reply verifier and final rechecks; unchanged malformed-component/assigned/closed
paths; invalid/unverified/foreign/empty sender candidates cannot grant a hold;
earlier UNKNOWN blocks a later positive; automatic-only still performs complete
discovery; actor/route/latest-task/component change stays conflict/UNKNOWN;
original deadline, client release and missing-source failures remain held.
Run existing affected projection/evidence/index tests, freeze exact source and
obtain a fresh source integration review. No broad redundant suite.

Then minimal paired read-only native-compatible evidence must show exact actual
MUV and measured Mario human roots retain valid holds without full discovery;
all-automatic/normal roots still use complete search. Compose a new immutable
one-file projection overlay on each ACTUAL post-Stripe family, proving every
other byte/resource/config/control/voice/MCP/Qonto and excludedHxi preserved.
Fresh activation review/check may adopt these six engine-only overlays under
held clonecron locks, as the earlier approved native-RPC verification sequence
requires actual loaded source. No kernel adoption or paid case yet.

ONE full native no-model union27 replay must then cover all54original and all
requiredcanonical terminal observations under unchanged600/40/60/90/global4/actor1,
with existing once-only typed-read recovery, no technicalUNKNOWN/omission and
allchildren reaped. Only PASS permits two-kernel adoption, exact fresh strict
harness composition review and the one ordinary case. Preserve all prior failures.
Rollback only our exact written overlay/dropins; never remove Stripe or another
owner's changes. No public release.


## M3 exact post-Stripe preservation compatibility

The operator independently authorized Stripe before the final email case. Its
reviewed transition changes only rpc/dispatch.py,rpc/methods.py and adds seven
Stripe source files plus the stripe directory. Actual inventories additionally
show four ordinary families lost only group-write bits on common resources
(0664 to0644,0775 to0755); no common uid/gid/type changes. Removed paths are only
compiled caches. The exact external metadata comparison is retained, not waived
or described as unchanged. No further external source writes are planned.

Lead ownership: scripts/operator_operational_common.py current-only preservation
compatibility, direct operational tests, current runtime-policy and outside-only
patcher. Use the ACTUAL immutable post-Stripe prefix and captured whole inventory
as the current V10 baseline. Narrow reboot_preservation to exactly ONE changed
path services/task_assignment_projection.py, ZERO added/removed resources and
identical mode/uid/gid/type on EVERY existing resource including the owned file.
REBOOT_ADDED_RESOURCES is empty for each current family. Existing reboot_provenance
still compares the REAL baseline filesystem to before-inventory and REAL current
filesystem to after-inventory, with exact package/source digests. No synthetic
before-state, cumulative metadata normalization or generic pin exception.

Retain original actual V4 and V9 snapshots, old validated five/nine-path proof,
actual Stripe source-map/delta/activation/review and exact metadata-transition
records as the complete ordered provenance chain. Verify the old V4-to-V9 stage
using the exact retained earlier preservation function; never rewrite its inputs
or claim the post-Stripe baseline is historical V4. Final provenance and policy
reference both that historical chain and the current one-file transition.

Preserve all seven historical binding/provenance constants, fixed342/352 checks,
excluded-Hxi validator, and seven strict acceptance/support/discovery/job/response/
assignment/load validators AST-identical. No acceptance/finalizer change. Outside
patcher allows ONLY the exact reviewed current-preservation function plus current
constants. Tests reject any extra/missing/changed-unowned path, any metadata
change, nonempty additions, wrong owned source or altered historical/strict guard.
Fresh source/harness integration review binds actual six-engine/two-kernel runtime
and policy receipt BEFORE ACTOR write or paid acceptance. Dependencies remain
M1 actual reviewed adoption, complete native proof and two-kernel adoption. Pure
outside preparation remains refusing/PENDING until all actual receipts exist.


## M1 staged verification fixture correction

The earlier M1 phrase "measured Mario human roots" was an unsupported fixture
assumption: retained isolated Mario observations were NORMAL; actual human holds
were observed on support. Do not invent a Mario human hold or relabel the first
Mario NORMAL probe. Replace only that paired-probe condition with the same exact
real current MUV root on both actors: support must retain its verified incomplete
human hold and Mario must preserve its independently complete NORMAL outcome.
Instrument only function names/counts/timing in the isolated signed-session,
read-only staged probes: support must show full evidence.reply and exact UID FLAGS
checks with no complete Sent discovery; Mario NORMAL must show complete discovery.
No new production source change, alias fixture or authority waiver. Original
receipts remain verbatim. The full native union27/all54original+requiredcanonical
proof under unchanged bounds remains mandatory before kernel adoption or paid
acceptance, so actual peer holds/conflicts/absence are still tested together.


## Final bounded latency correction and delivery — 2026-10-17

Depends on the approved Provider latency headroom brief amendment. Reuse all
previous correct source/guard tests and staged tooling; do not restart diagnosis.
One execution worker owns ACTOR projection.py, cs/task_assignment.py, cs/rpc_reads.py
and directly affected tests. Set only projection's read deadline120; assignment
status caller150; batch projection requests explicit150/180, global3600including
cleanup. Parent supervised reader supports those finite caps ONLY for the allowed
tasks.assignment.project method when caller opts in. Default60/90 and other-method
60/90 caps remain. Propagate the selected bounded request cap to isolated child;
outer watchdog/auth/DNS/cleanup stay under the selected finite batch/whole bounds.
Preserve global4/actor1, canonical order, once-only completedtyped recovery,
transport reservations, all source/body/FLAGS/identity/route/task guards.

Run focused affected tests once, adding scaled real-WebSocket checks that a valid
assignment read beyond the former60 limit can complete within150; default and
other methods still stop at60/90;120engine bound and finite whole3600cleanup
remain enforced. Freeze3productionfiles+checks and fresh source gate. No paid
requests or changes to budgets/CS_PAUSE/auth/generation/sending permission.

Rebase prepared six-engine ONEprojection overlays/helper onto ACTUAL current
families, preserving support authenticated-finance-content, all Stripe/Qonto/
voice/MCP/privatecontrols/secondaryprefixes and excludedHxi. Use exact current
baseline rather than historical cumulative metadata; retain prior full chain.
Fresh activation gate plus locked check/adoption under the existing3cronlocks,
then one actual no-model native currentcorpus+retainedfailedroots replay using
new supervised reader candidate. Account every original/canonical terminal scope,
attempt, timeout and child; technicalUNKNOWN/omissions prohibit paid work.

Actual wholePASS permits kernel packet to adopt TWOownedmodules task_assignment.py
and rpc_reads.py in both distinct clone package preimages, with atomic rollback
and exact unaffected metadata/resources, no restarts. Fresh activation gate/check
then exact current harness source/policy composition review; preservehistorical
constants/sevenstrictvalidators/finalizer and original failure records.
The existing90-minute case bound remains. Before that ONE paid case, inspect its
per-job watchdogs for consistency with legitimate read latency; no unbounded job
or weakened seven-check acceptance. Use normal configured jobs/auth/budgets.
Capture and independently verify actual MrCall received reply, Café usable draft
and signup outcome; no expired fixture or old signed result reused.

Finish required doc-end semantic/mechanical closure, separate final review and
checker-managed baseline. Explicitly release all3maintenance locks only after
verified safe normal restoration; report actual results and remaining separate
GmailUI/publicrelease boundaries. No commits/tags/push/publication.


## V11 installed delivery evidence — 2026-10-17

Source manifest411ac8 and M1/M2 reviews bind the finite120/150/180/3600 correction.
Six engines use exact projectionf7ed7c3b over their actual finance/Stripe baselines.
Two guarded partial activation failures remain immutable; final continuation
preserves two owned processes and restarts the remaining four. Exact
STATE_DIRECTORY activation derives from the unchanged original systemd unit
properties; every other stable environment hash remains fixed. Independent
actual activation verification approves receipt4b7f0354.

Both installed clone packages adopt only task_assignment.py78034ebc and
rpc_reads.py96a1e013, with complete distinct inventories/metadata verified and
zero restarts. Actual adoption receipt3cff67b4 is independently approved.
The captured27-root native replay completes54original and2canonical observations
with56physical attempts, zero unknown/error/missing outcomes, actor maximum1
and all56children reaped within403.981seconds. One valid NORMAL read takes88.793s.
The original distinct-identity proofc7e916 is retained; obligation-multiplicity
proof586b3616 counts all56observations from the same unchanged raw record.

M3 manifest312121b7 and fresh source review approve the current six-engine/two-kernel
bindings, exact one-file preservation, finite watchdog alignment and unchanged
strict validators. Four live source/policy/test files equal the approved bytes;
14focused checks pass against the live files. The broader77-test attempt retains
13historical MAIN-fixture dependency errors, one outside-context Git error and
one superseded pending-state assertion; affected current checks pass separately.
Exact private evidence copies retain original hashes and permissions while
allowing the ordinary runner to verify every current provenance reference.

Fresh ordinary case: /home/mal/.local/share/mrcall-operational-evidence/2026-10-17/ordinary-assignment-recovery-v11.
The1064-entry candidate is retained before launch with digest9d1390a1. The case
is running; no final ordinary outcome, signature or completion is claimed here.
No public release, commit, push, model/budget or send-permission change occurs.

## Ordinary V11 outcome — 2026-10-17

The real case failed and remains unsigned. MrCall completed its normal six-phase job; create_draft persisted a bare RFC root while exact in_reply_to and References retained their brackets. Two ordinary sends refused before SMTP with "Exact RFC thread root Message-ID required". Independent receipt timed out; Café and signup were not launched. Original schedules SHA256759ab3f8180ced2a6b9ee5f47988f07b96d2810ff209e8092d53c7af8675889f were restored and all owned native process identities were quiescent. The full 1064-entry candidate is identical before/after (9d1390a13f3e8df1fde704f437231bdd2693a672dd3d9c00709d18fe7d393ccd); candidate-after-failed.json was retained without copying historical signatures.

A separate bounded engine storage compatibility brief and plan were independently APPROVED at /home/mal/.local/share/ordinary-assignment-recovery-resume/thread-root-compatibility/. They preserve every authority check, existing opaque provider IDs and failure records, and require normal legacy-draft compatibility plus one new strict case after source/installed-composition approval. No additional paid case has started.

### Symbolic email action boundary

V11 exposed an independent alarm gap: failed send_draft tool results became
optimistic chat prose, outer CLI exit0 and a clean supervisor terminal result.
The exact V11 record remains FAILED and unsigned. The request-local repair now
has source APPROVED for assistant/core.py, services/chat_service.py and the
indispensable scoped services/task_assignment_draft_policy.py route. The first
source review correctly returned REVISE after reproducing the scoped bypass;
revision2 passed37 focused and15 exact-candidate tests, including independent
scoped ERROR/SUCCESS/exception checks. No model/provider was called by these
checks. The existing CLI and supervisor failure/no-fallback consumers were
exercised deterministically; unknown delivery certainty does not permit replay.

Frozen source and evidence live under
`/home/mal/.local/share/ordinary-assignment-recovery-resume/symbolic-email-action-failure/`:
`source-variants-v2/manifest.json` SHA256
`54899861ad93b9dc147f3db24ff82f3ee14e8ece288ae3edee62dc05df7ece40`,
`source-review-v2/report.md` SHA256
`576756287ed79ae8c0f708ecde2668359cf9829df53f8dfafe1c32af5ad013f9`.
The orchestration agent-thread limit prevented a new independent plan/activation
reviewer; distinct lead review passes record that limitation explicitly. This
is not a claim of fresh independent kit review. Actual installation and strict
ordinary acceptance still require their own retained results.
