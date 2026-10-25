---
status: active
brief: ../briefs/2026-10-19-scheduled-review-read-budget.md
owner: MrCall kernel engineering lead
brief_sha256: a627bdce4db2eae9cd2becb3a375aa11e69c19b814f1e2068624ae018bb13841
implementation: not-started
---
# Complete review within the existing native window

Classification: substantial kernel read-coordination change. It crosses a scheduling evidence boundary and needs reviewed milestones. This document authorizes no implementation before the plan gate and verified C32 cleanup/source unfreeze.

## Evidence and design decision

C32 ended FAILED and the lead verified post-terminal cleanup at 2026-10-19 22:02 UTC: 576 owned identities quiescent, seven runtime bindings/payloads unchanged, both full kernels and source exact, original cron restored and four locks free. The retained proof is `/home/mal/.local/share/mrcall-operational-evidence/2026-10-19/ordinary-assignment-recovery-v32/root-cleanup-live-check.json`. Source freeze has ended; implementation still requires plan approval.

Approved brief: `../briefs/2026-10-19-scheduled-review-read-budget.md`, exact hash above; independently reviewed copy retained at `/home/mal/.local/share/mrcall-workflow-evidence/2026-10-18/c32-review-tail-repair/brief-review/brief.reviewed.md`. Diagnoses are `/home/mal/.local/share/mrcall-workflow-evidence/2026-10-18/c32-review-tail-diagnosis/report.md` and `/home/mal/.local/share/mrcall-workflow-evidence/2026-10-18/c32-cafe-fixture-diagnosis/report.md`. Personally inspected current K `cs/review.py`, `cs/task_assignment.py`, `cs/rpc_reads.py`, `cs/engine_view.py`, the complete `unanswered.sweep` implementation, `cmd_review`, inventory/reservation seams, draft reconciliation/inventory seams, and existing bounded dossier supervisor. No live probe, test, model call or runtime mutation occurred during planning.

K is `/home/mal/hb/cs-kernel`. A is `/home/mal/worktrees/operator-assignment-recovery-resume-20261016`. The maintained Café clone is `/home/mal/124/124-cs`; the lead's frozen composition manifest supplies the second maintained clone/copy, never a guessed path.

`review.gather` independently projects listed assignments and then invokes `unanswered.sweep`, which projects recent inbound again. Each projection invocation has a 3600-second default and per-request canonical caches. `_unknown` already expresses incomplete/held roots. `split_inbound` preserves these in human work, while complete closure and later-inbound audits have separate paths. `cmd_review` records JSON as scheduled evidence before printing it; incomplete draft proof must therefore fail the existing observer, regardless of parseability. Classification's absent view and settlement's absent verdict are degradation, never conclusive negative observations.

Choose one union projection pass, rather than a new generic observation service. Extend only the internal sweep coordination seam to accept listed assignment roots and return its projection map to review. Discover all existing inbound/sent scope first, derive current priority, append every listed root, and project the complete ordered union once. Within that pass share exact original/canonical read outcomes across requested-root states. This removes duplicate passes and duplicate canonical requests without inventing cross-method equivalence. Standalone sweep callers keep their default behavior.

Use a private review-owned supervisor around aggregation because draft/mailbox helpers and authentication do not expose a reliable whole-operation bound. Follow the existing `operator_dossier` owned-process-group pattern; do not import its reservation markers or effect permissions. Keep this implementation in `cs/review.py` unless a separately reviewed extraction proves necessary. Extend existing machinery rather than build another generic runtime framework.

## Budget, reuse and completeness contracts

One monotonic 540-second total starts before process launch and settings transfer. Work stops at 525 seconds. Reserve 10 seconds for owned child/group cleanup and 5 seconds for final validation/rendering. All stages consume this same deadline; no fresh tail budget, timeout increase or background continuation. Normal stage timeouts are clamped to remaining work time. Kill protection is a final bound, not the mechanism for producing a successful review.

The supervisor receives atomic stage checkpoints of completed observations and coverage from its own worker. Private temporary evidence is command-local and removed after use; no credentials/tokens are checkpointed. Each checkpoint is bound to that exact worker identity, selected account/configuration and command attempt, and accepted only as a whole validated record. Retain full completed global draft inventory, raw handles, reconciliation rows and every discovered root after an interrupted later stage. Partial wire JSON is never parsed as a checkpoint. At interruption, synthesize held/unknown projections only for the requested roots whose complete projection is absent; retain successful observations unchanged. Unknown mailbox/list coverage stays visibly incomplete, without claiming knowledge of undiscovered roots. Cleanup failure invalidates successful completeness.

Global draft inventory is mandatory: run full existing listings and reconciliation, with unchanged mailbox scope, derived uncapped draft window, identity matching, raw UID coverage and `inventory_proof`. A draft phase exhausting the budget cannot yield a complete inventory. Preserve returned raw rows but set incomplete proof and row holds using existing representations. No later reservation or paid case proceeds from that result. If draft time dominates, report the exact failed stage and stop acceptance; do not shorten history or expand scope into a draft-latency project.

Prioritize currently relevant inbound/task roots ahead of older assignment-only roots. Priority must use actual current observations and existing structural rules, not a fixture constant. Within each root preserve all configured peer coverage before calling it complete. All other roots remain queued and explicitly represented if deferred. Prevent classification/settlement from consuming the entire remaining projection opportunity: make ordering and an explicit remaining-time allocation testable; retain their degradation notes and conservatively keep affected work visible when they cannot complete. Existing optional engine judgments do not turn transport unknown into complete absence.

The command context exists only inside one review worker. Read identity includes selected owner UID, actual engine endpoint/configuration identity, method and exact parameters; successful projections additionally bind validated `space_id`. Peer roster/configuration is frozen for that invocation. Cache original and canonical outcomes by exact identity; canonical reuse occurs only through `_validate_projection` and `_resolve_peer_aliases`, not from matching subject, contact or unvalidated aliases. Revalidate requesting/root/space binding when consuming an outcome. Never rewrite a requested-root envelope into an unrelated canonical-root response.

Keep errors, malformed envelopes, conflicts, missing peers and original provenance. A failed read is not a cache miss inviting unbounded retries. Preserve the existing single `SOURCE_UNAVAILABLE` recovery allowance per exact identity and retain its original hold if recovery is deferred. No retries after the deadline. Cache keys include failures' request identity even when no company can be validated; never admit these failures as validated company evidence. No process-global or disk cache, no reuse between commands, and no changes to fresh `project`, `guard`, dossier or effect-time authority.

## Milestones and ownership

### M1 — Bounded aggregation and explicit coverage

Owner: kernel executor, K `cs/review.py`, `cs/unanswered.py`, and focused review tests. Dependency: fresh plan APPROVED and lead-confirmed source unfreeze. Introduce the command deadline, private owned worker/checkpoints and stderr progress for assignment listing, inbound/sent discovery, classification, settlement and projection. Pass deadline/group through internal read seams where available. Preserve JSON fields and current CLI exit meanings; feed failure through existing incomplete inventory/observer paths rather than add a success status for killed work. Keep successful synchronous gather fixtures callable through an internal aggregation seam.

Check: fake-clock tests at draft listing, reconciliation, listing, discovery, classification, settlement and projection; each returns within total plus bounded scheduling tolerance, retains every completed checkpoint row and never claims incomplete draft proof complete. Real subprocess tests stall a child and descendant, exercise malformed/missing checkpoint, worker crash, PID identity mismatch and cleanup failure. Assert only owned processes are killed, no descendants survive accepted cleanup, stdout remains one parseable JSON object, and stderr identifies the stage. Test actual CLI observer rejects incomplete mandatory review evidence. Run new tests plus `tests/test_review_progress.py`, `test_review_inventory.py`, `test_review_evidence_gaps.py`, `test_operator_workset_cli.py` with the actual existing K interpreter using `PYTHONDONTWRITEBYTECODE=1` and `-B`. Independent M1 integration review must approve before M2 depends on it.

### M2 — One faithful projection pass and C32 readiness replay

Owner: same kernel executor, K `cs/task_assignment.py`, internal sweep/review coordination and focused tests. Dependency: M1 approval. Remove review's independent listed-root projection pass. Supply all listed roots to sweep's ordered union; return their exact projections for review provenance while preserving unlisted inbound and all audit buckets. Share original/canonical read futures/outcomes inside that pass and keep per-account/concurrency/timeout safeguards. Add optional deadline/group plumbing to `engine_view.classify` only where needed; settlement gets remaining explicit timeout. `rpc_reads.py` changes require a demonstrated deadline/cleanup defect, not speculative batching work.

Check: overlap/canonical-alias tests assert exact RPC counts and identical complete semantic output to uncached execution. Include different account, endpoint, company, peer roster, conflicting canonical metadata, closed/later inbound, unavailable peer, original/canonical source recovery, malformed envelope, transport timeout, exhausted deadline and a second command proving no reuse. Assert output root set equals union of listed and eligible inbound roots, even under capacity exhaustion, and every incomplete projection holds action. Preserve requested-root-specific evidence when canonical reads are reused.

Deterministic C32 replay uses frozen actual task/discovery/draft evidence plus explicitly labeled simulated transport responses, never forged native events. Exercise real `gather` orchestration, scheduled observation, `_inventory` and reservation against private temporary state. The resolved task `500048b9-3628-454f-a127-652ef9875b48`, root `<179244264351.1832872.14378365271212943800@operator-test.mrcall.ai>`, must become a candidate/reservation with complete required inventory and complete non-held current root authority while unrelated older unresolved roots stay held. Complement with unresolved fixture, all-unknown projections and incomplete global drafts: these cannot satisfy readiness. Replay proves code behavior, not historical successful review or provider readiness.

Run new deterministic tests and focused assignment, unanswered, courtesy/thread, RPC, review, operational-fixture, workset, dossier and effect guard suites. Execute each actual test script under `PYTHONDONTWRITEBYTECODE=1 <existing-K-python> -B`; retain command, complete output and exit. Do not substitute pytest collection success for these script suites. Independent source/milestone review checks freshness, completeness and all-unknown refusal before adoption.

### M3 — Exact adoption and one actual Café read

Owner: lead activation operator; kernel executor supplies reviewed file hashes. Dependency: M2 approved, frozen exact candidate, free checks green and C32 cleanup verified. Prepare a fresh minimal private activation packet from the already reviewed four-lock outer helper `/var/lib/mrcall-workflow-activation-packets/c32-row-holds-4ccnn00s/activate.py` (SHA256 `93b18374268af4d87ddff31e7c7bb4669c4ae6e9b53d84891075e79f8dd6b810`), its `kernel_primitives.py`, `pin_composer.py` and manifest. Prior review is `/home/mal/.local/share/mrcall-workflow-evidence/2026-10-18/c32-row-hold-activation-review/report.md`. Independently review the new exact packet and dependency reuse; prior approval alone does not approve new bytes.

Install only reviewed kernel files into both maintained kernel copies under the existing bounded four-lock protocol. Preserve both Actor prefixes, engine payloads, seven bindings, services and unrelated files. Change only exact A common/policy candidate references if required by composition checks. No engine writes, service/Actor restart, cron/model/budget/grant changes, release or commit. Verify installed hashes and imports using both clone interpreters before any provider read. Record before/after outside-allowlist inventories and lock cleanup.

Run exactly one normal-owner Café `cs review --json` in the maintained clone on the installed candidate, using its real environment and `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m cs review --json`. Outer capture may allow 550 seconds solely to retain the command's own 540-second result/cleanup; it must not extend native600 or work time. Retain full stdout/stderr, timings, exit, process cleanup and installed hashes. This authorized read may invoke normal engine classification/model work under existing billing controls.

Readiness requires genuinely completed full draft inventory, all discovered/requested roots represented, actual current relevant observations sufficient for a candidate, older unknowns visibly held, valid checkpoint provenance and successful cleanup. Parseable all-unknown JSON is a failed readiness gate. Cross-check inventory identity counts/handles and root coverage with actual read observations, without a second live probe. On failure retain evidence and stop the paid-case branch; fix only demonstrated in-scope causes through review and deterministic checks, never automatically rerun paid reads.

Rollback: under the same bounded locks restore exact pre-activation kernel bytes and candidate pins from the packet, verify both copies and outside-allowlist preservation. Never roll back mailbox/provider state or unrelated concurrent changes.

### M4 — One strict case and original assignment closure

Owner: lead operational runner, then lead documentation owner. Dependency: M3 actual readiness passes and exact composition remains unchanged. Run one new unchanged strict ordinary two-clone case through existing driver, normal cron/guards/generation and current budgets. Require independently received correct MrCall reply, usable provider-visible Café draft, acknowledgement, actual native ancestry/proof, normal jobs, preservation and exact cleanup in that same case. Preserve C32 as failed/incomplete. No manual draft/send, enrollment reuse, lifecycle-schema expansion, relaxed deadline or reconstructed native evidence.

Run the actual strict checker/finalizer and retain complete result references. An exit zero, zero work, task discovery or deterministic reservation replay cannot substitute. If the case fails, report that actual failure and remaining obligations; no unattended paid retry loop.

Reconcile affected K operator/review durable docs and living context plus A's original migration/operational plans and relevant Desktop docs. Preserve historical narrative in the existing archive. Run required mechanical completion check, explicit doc-critic (including unchanged affected contracts and living-context shape), separate final review through the user path, then completion finalize only when every required receipt exists. Bind optional verification warnings to the existing exact tasks; do not create replacement tasks or invent runtime IDs.

## What this plan does not establish

The exact killed C32 call remains unproven. This plan does not prove the present provider can complete review within540, that the fixture is currently eligible, that either installed copy already matches a future candidate, or that any operational case has passed. Source freeze and activation dependencies are lead-owned prerequisites. The prior activation helper reference is supplied evidence, not personally executed adoption. No source/runtime/provider changes or tests were performed by this read-only planner. Future verification listed above belongs to implementation and acceptance, not present evidence. Broad test-runner output was not used as a verified suite result.


## M3 actual coverage repair — 2026-10-19

The first installed 8f5bf4 actual Café review completed in518.100934 seconds with
full74-engine/7-Gmail/74-reconciled draft inventory and no owned survivors, but
M3 is REVISE:81 unknown and1 needs-assignment; all82 surfaced assignments held
and incomplete. Preserve that failed readiness observation. Evidence:
`/home/mal/.local/share/mrcall-workflow-evidence/2026-10-18/c32-review-tail-repair/actual-cafe-review/`
and `../m3-installed-readiness-review/report-r2.md` relative to its parent.

A bounded read-only diagnosis demonstrates a coverage defect in the existing
scope: review records explicit task/draft roots in `_known_roots`, but passes
only company-listed assignment roots into the union. On successful aggregation
it exports only listed-root projections and removes internal known/completed
coverage. The interrupted path alone preserves those extra roots as held
unknown. The actual resolved fixture task remains listed without public
assignment authority. This does not prove whether it was projected earlier.
The exact initial transport failure remains unproven; one separately retained
read-only direct projection of the failed root later returned complete NORMAL
in1.103587 seconds, with no model generation or effect. Do not label this a
historical successful review or waive M3.

Repair only this demonstrated coverage loss before further adoption. Owner:
bounded kernel executor, `cs/review.py`, `cs/unanswered.py` only if needed, and
focused tests. Supply explicit observed task/draft roots to the same one-pass
union without removing any current inbound/company-listed root. Publish an
additive per-root observational coverage field with every requested root and
its exact complete or held projection, plus original requested order/source
categories sufficient to audit inclusion. Missing/unprojected roots are explicit
held UNKNOWN. Keep existing assignments/human_work/audit meanings and settled
filtering; do not turn old normal roots into new actionable candidates or reuse
coverage as effect-time authority. Existing priority uses actual observations;
no fixture constant, speculative reorder, timeout increase, account-block
removal, new read, cache lifetime or retry change.

Checks: actual production-worker/CLI success with task-only and draft-only roots
absent from mailbox discovery; complete normal settled root remains observable
without entering human_work; timeout/unknown roots remain held; union includes
all source categories exactly once; existing M1/M2 integration/effect suites.
Fresh independent source/integration approval is required. Reuse approved brief
framing: preserve every requested root and make deferred unknowns visible.

After free checks and exact source approval, prepare/review/apply one new minimal
kernel-only packet under the same four-lock preservation controls. On that new
reviewed installed candidate authorize exactly one bounded normal-owner Café
read, retaining the failed prior attempt separately. Its coverage and genuinely
usable current authority must satisfy unchanged M3 criteria before M4. No paid
case or automatic read retry follows failure; investigate actual evidence and
retain all unmet obligations. This amendment permits no second read of the
unchanged failed candidate and no relaxation of whole-case acceptance.


## C38 amendment — bounded scheduled canonical discovery (2026-10-20)

Classification: substantial continuation of the same scheduled-review-read-budget-kernel-20261019 task, not a new task or fast path. This appendix supersedes only the earlier standalone-discovery default and current acceptance sequence. Preserve every preceding byte, failure and obligation. Current approved brief SHA256 is fef58c7fe1a3ef747c7e6594b8f8aa5b12fa14311cfefa61f05a3625144285ff; independent approval is c38-discovery-budget-amendment/brief-review/report.md in the workflow evidence root. The lead reports actual C37 terminal cleanup PASS:816 owned identities, seven runtime bindings/full payloads, both kernels, sources, cron and four locks. Confirm that retained cleanup before implementation; this planner did not execute it.

### Decided implementation boundary

K owns cs/cli.py, cs/unanswered.py and focused tests. Keep cs/review.py, cs/task_assignment.py, cs/operator_dossier.py, native/material producers and consumers byte-identical. Reuse review._save_checkpoint/_read_checkpoint and operator_dossier._stop without API changes. Do not extract a generic supervisor. A needed change to these shared helpers requires an explicit amended-plan review before implementation.

Add a private scheduled-discovery supervisor in unanswered.py. The scheduled CLI dispatches to it before configuration loading or any discovery work; normal unscheduled cmd_unanswered retains its exact existing behavior. Preserve the current predicate: workset_enabled exactly true selects scheduled mode; malformed supplied context remains fail-closed. Missing/false context does not silently opt into scheduling. No public flag, native-schema exception or relaxation of canonical argv is introduced.

The supervisor starts one540-second monotonic lifecycle before worker launch, configuration loading and settings transfer. Reserve conservative absolute subwindows: observational worker must finish by started+510; its owned process-group cleanup gets at most10 seconds, by started+520; parent publication gets at most5 seconds, by started+525; final validation/output transfer gets at most5, by started+530. The remaining10 seconds are safety margin, not extra work. These allocations stay below the original525 work/10 cleanup/5 final limits and540 total. No stage resets a deadline. Sweep and its supported seams receive the same absolute observation deadline/group. Unsupported initial mailbox/state helpers run only inside that owned supervised worker. Check before every stage and refuse all later dispatch after expiry.

Choose DEFERRED PARENT PUBLICATION, not rollback of the persistent reservation cursor. The worker loads normal settings, enumerates and projects, checkpoints observations and buffers the complete result; it MUST NOT call reserve(), capture(), receipt capture or any persistent reservation/publication operation. A private unanswered.py worker entry and finite authenticated input follow the existing review worker pattern, binding exact parent/worker PID/start/UID, fresh attempt, arguments, selected configuration identity and owner. No generic FD framework or same-argv recursive child is needed. The parent remains the genuine canonical CLI process with unchanged sys.argv and actual native supervisor ancestry.

Only after normal terminal worker completion AND verified quiescence of its entire owned process group may the parent enter the existing canonical reserve/capture/render tail. Parent loads normal settings through config.load(), verifies its full effective identity against the worker binding and checks the absolute publication deadline BEFORE reserve. No configuration override, health context/nonce alteration or invented ancestor is allowed. Parent config loading belongs to this reserved publication window; failure/mismatch/deadline refusal publishes no reservation. Existing reserve and capture remain unchanged. Their observed source uses bounded private records, finite cursor capacities and nonblocking flock, with no RPC/model call or unbounded lock wait. Capture uses the genuine parent canonical argv/ancestry, so no new validator admission is required.

No child cleanup can fail AFTER cursor publication: it is a prerequisite already proven before the parent calls reserve. If cleanup fails or cannot be proved, the parent does not call reserve/capture and leaves the pre-existing cursor and markers byte/metadata exact. Do not attempt to repair this by deleting a new marker after mutating a prior cursor. Existing reserve's own error ordering remains unchanged: it can replace cursor before marker creation. A parent reservation error is a failed publication with no successful discovery/native/readiness credit, not authority to roll back concurrent state or retry. Preserve its exact existing same-nonce recovery/refusal semantics; do not claim transactional rollback or power-loss safety. No worker is allowed to publish an output/result that makes failed publication usable.

The five-second parent publication bound is checked before and after each finite local operation and by focused fake-clock tests; overrun/refusal yields incomplete status and no completed discovery/output credit. This is a bound on the existing normal local filesystem path, not a claim that Python can interrupt a kernel-stalled filesystem syscall. A demonstrated inability of these unchanged finite helpers to satisfy the reserved window blocks readiness and requires a fresh reviewed correction; do not raise a deadline, create a transaction framework or silently move publication into the worker. Parent output is withheld until terminal validation; diagnostics remain stderr.

The private component entry uses the SAME supervisor/worker sweep implementation and standard settings loader, with explicit no-publication mode: no workset reserve, health capture, discovery receipt, native context or effects. This exists as an internal test/readiness seam, not a new CLI behavior or permission. Its normal-owner harness verifies and supplies the exact canonical argv unanswered --days 14 --json --all-buckets, with days14/full buckets and records full bounded result plus timing/provenance. Free CLI integration proves the actual canonical branch invokes the same work lifecycle; only the future native case proves native wiring end to end.

Checkpoints reuse existing atomic private-file encoding and size limit. Each record binds version, random command attempt, supervisor and worker PID/start, selected configuration identity, owner UID, exact canonical arguments, phase, complete-enumeration booleans, all completed raw observations, every known root, completed projection map and terminal completion. Validate all fields/types and whole binding before using a record. Preserve original observation provenance and timestamps; encode/decode dates explicitly so an interrupted result cannot alter date ordering. No tokens/settings payload is checkpointed. Missing/malformed/oversized/foreign/symlink checkpoint fails closed. Private state is command-local and removed after terminal cleanup.

Checkpoint after full inbound enumeration, full Sent enumeration, eligible-root derivation, classification, settlement, complete requested-root list, projection and final rendered result. Before a phase starts, retain its current known-root set. Incomplete initial enumeration sets existing read_incomplete; it cannot establish undiscovered absence. Completed enumeration may retain completed valid projections and original rows while representing every remaining known root through existing _unknown/provenance/split_inbound held rows and assignment_incomplete. Do not add a public discovery field or change v2 material schema. Preserve all existing buckets and audit rows. Use existing compatible note/read_incomplete/assignment_incomplete fields for interruptions; native health may correctly reject incomplete reads. No readiness/action/native credit comes from a held fallback.

Only an authenticated normally completed terminal checkpoint, complete required enumeration, verified cleanup and successful required parent publication can release ordinary CLI output; component mode performs no publication. Preserve the canonical command's existing logical exit0 OR logical exit3 exactly: a normally completed full enumeration with validated rows/provenance may return3 because unrelated roots remain explicitly held while an independent root is complete. Parent propagation must preserve that exact logical exit, output and native correlation; no separate OS/protocol-success wrapper may launder a failed command into success. Exit3 alone never establishes admissibility. On worker crash, expiry, checkpoint mismatch or cleanup failure, release only explicit incomplete output/exit3, with no completion or readiness credit. Because publication is deferred until cleanup is already verified, worker/cleanup failure leaves no new reservation/capture artifact or cursor mutation to withdraw. Preserve prior and concurrent cursor state exactly. Tests must prove the no-publication-before-cleanup boundary; no validator change may make it pass.

### Renewed M1 — bounded scheduled command and complete held fallback

Owner: one bounded kernel executor, the files above. Dependency: fresh amended-plan approval and verified ended C37 freeze. Implement the scheduled wrapper, exact CLI dispatch/private worker boundary, checkpoints and parent-only deferred publication. No operator_workset.py/helper API change is authorized. Preserve unscheduled calls, existing review worker, command-local projection cache, peer coverage, fair actual-source ordering, one SOURCE_UNAVAILABLE recovery, account1/global4 limits and fresh effect guards. Do not alter mailbox scope, roots, transport permissions, engine/runtime services or the original driver.

Checks: fake-clock/real orchestration tests stall config/settings transfer, initial inbound, Sent, classification, settlement, projection and rendering. Assert one unchanged absolute deadline, no later RPC after expiry, exact complete-root coverage and unchanged completed rows. Unknown enumeration must remain read_incomplete; complete enumeration plus partial projection must retain every known root held unless its complete original projection survives. Include settled/closed/later-inbound audit, empty genuine enumeration, cross-account/config/alias separation, missing peers, malformed/conflicting responses and existing recovery limits. Compare successful scheduled output to unsupervised sweep on identical fixture observations, including all buckets and revisions. No test may relabel all-unknown output usable.

Real short-budget subprocess checks create child and grandchild plus an unrelated surviving bystander. Verify exact PID/start ownership, normal cleanup, stalled initial/tail workers, malformed checkpoint, PID mismatch, cleanup failure, no surviving owned descendants and no reserve/capture call before successful cleanup. Start with a pre-existing cursor and prove it remains exact after worker/cleanup failure. Test same-nonce re-entry against unchanged existing reserve semantics, a concurrent foreign cursor update before deferred publication (preserve it and let unchanged reserve validate under its own lock), and reserve failure between cursor replacement and marker creation (no discovery/capture/native success or readiness; retain existing recoverable cursor semantics without overwriting foreign state). No automatic re-entry/retry follows a failed publication. Exercise genuine canonical argv under a locally generated test-only supervisor fixture, keeping this explicitly simulated and outside live authority. Prove no context fabrication is used by the actual-read harness. Assert native tool-use/result correlation and captured genuine ancestry both name the actual parent canonical command; its observational worker is already quiescent and is not fabricated into capture ancestry. Rejected task_updated/background notices remain rejected. Test observation cutoff510, cleanup by520, parent publication by525 and final transfer by530 separately; neither leftover540 safety margin nor an expired terminal artifact grants more work.

Run actual existing K interpreter with PYTHONDONTWRITEBYTECODE=1/-B: new scheduled-discovery tests and existing test_review_budget.py, test_review_union.py, test_review_progress.py, test_review_inventory.py, test_review_evidence_gaps.py, test_operator_workset_cli.py; retain exact complete outputs/exits. These are future required checks, not presently executed results. Fresh M1 reviewer evaluates every changed file, cleanup/publication and complete unknown representation before dependent adoption.

### Renewed M2 — semantic integration and exact minimal CLI composition

Owner: kernel executor plus independent source reviewer. Dependency: renewed M1 approved. Run existing assignment, unanswered, courtesy/thread, operational fixture, workset/dossier/effect, native nonexecution and v2 full-material/paging/early-effect suites affected by this change. Keep source-handle and material modules byte-identical. Free CLI integration exercises absent/false/true/malformed scheduling context, exact canonical args, incomplete exit3, complete full output and authentic local test ancestry. Include an authenticated normal logical3 full-enumeration case with a complete independent root and unrelated held roots; preserve its exact exit/output/native correlation. Pair it with forced/incomplete logical3 and failed-worker cases that receive no readiness credit. Verify current independent-root authority can coexist with unrelated held roots, without converting unknown peers or incomplete enumeration into success.

Produce a restricted installed CLI by applying ONLY reviewed scheduled-discovery hunks to the current P8 installed CLI preimage. Never copy the whole K CLI: it contains unrelated Stripe changes. Verify all other installed CLI functions/bytes and every unchanged kernel file against that preimage. A normal import/help run under each clone interpreter and actual candidate fixture orchestration must pass. Source review includes the exact restricted render, not merely the whole source file.

Use the existing immutable task configuration and existing M1/M2 gate IDs/artifact paths. Renew their evidence against current artifacts and the fresh comprehensive report; do not invent an extra configured milestone, reset the task or edit configuration to admit new paths. The report must attribute new unanswered/CLI changes explicitly even where configured artifact paths are unchanged. Snapshot changed paths through the existing checker. Preserve earlier approved review behavior as unchanged evidence, not as proof of the new scheduled entry.

### Renewed M3 — guarded adoption and one actual scheduled-sweep component read

Owner: lead activation operator; independent packet and installed reviewers. Dependency: renewed M2/source approval and all free checks green. Use current P8 live121-file/full f727-prefixed payload as beforeimage, confirming its COMPLETE digest from retained actual installed proof; a prefix is not an activation pin. Freeze exact full121 candidate maps, metadata, canonical Path-based payload digest, restricted CLI render and exact A common/policy candidate-pin deltas. Reuse current reviewed bounded four-lock activation transaction. Fresh packet review and fault/rollback checks must cover every changed publication and absent-file case if any. No engine write/restart, cron/grant/model/budget change or unrelated adoption.

Apply only the reviewed finite allowlist. Verify both complete kernel maps, metadata, canonical payload digest, source/config/cron/service preservation, own interpreters and exact Actor pins; obtain fresh independent installed approval before a live read. Rollback restores only exact owned preimages under the same locks; refuse foreign changes and preserve provider/mailbox state. Existing material and source-handle code stays exact outside the explicitly reviewed budget deltas.

Root personally reviews the actual readiness harness before its single execution. Run as normal Café owner in /home/mal/124/124-cs with its own installed .venv interpreter, cwd and standard config.load() environment, without environment/configuration overrides selecting another tenant. Invoke the SAME installed scheduled supervisor component entry with days14/full buckets, using its normal provider settings. Do not manufacture CS_OPERATOR_HEALTH_CONTEXT, nonce, reservation, supervisor identity, discovery receipt or native events. Capture full output/stderr, actual exit, start/end/phase times, installed hashes and exact owned process cleanup. Outer watchdog permits at most550 seconds solely for observing the internal540 result, never extra work or a native-limit extension. Classification may incur ordinary existing billing; this is not a free test.

Readiness requires authenticated normal worker completion, complete actual inbound/Sent enumeration, all known roots represented with original provenance, usable complete current independent-root authority, explicit held unrelated roots, compatible complete result, no late dispatch and successful owned cleanup within540. Preserve existing logical exit0/3 semantics: normal cooperative completion with full enumeration, a genuinely complete independent root and unrelated held roots may satisfy readiness under unchanged rules even when the canonical logical exit is3. A forced/incomplete checkpoint cannot; neither a bare3 nor transport completion is evidence of readiness. Parseable all-unknown, missing enumeration, forced fallback, cleanup failure or deadline overrun FAILS readiness. A direct component read does not establish CLI/native capture, reservation, native v2 inspection, draft or whole-case success. Reuse unchanged earlier actual review evidence; no extra paid review. On failure preserve the exact evidence and stop this paid branch; no blind repeat on the unchanged candidate.

### M4 — unchanged strict case38 and all original closures

Owner: lead. Dependency: actual M3 readiness PASS, exact candidate unchanged and fresh root case authority/freeze. Run ONE unchanged original strict two-clone case under existing native600, Café2700 and original driver limits/budgets. Require actual native canonical CLI completion, full v2 inspection before effects, independently received correct MrCall reply, usable provider-visible Café draft, correct acknowledgement, normal jobs and exact terminal cleanup/preservation in THAT same case. Preserve C37 FAILED; no partial-case aggregation, task_updated admission, manual effect, fixture priority or retry/timeout waiver.

After actual case PASS and cleanup, reconcile all affected durable/living docs and preserve archives verbatim. Complete all25 existing task closures, including remaining case milestones, mechanical checks, explicit doc-critic/active-context shape, fresh separate final reviews and immediate check/finalize baseline advancement. No new task/reset, commit, push or release is authorized.

### Present limits

This read-only plan establishes a source-supported design and verification sequence only. It does not establish actual remote latency, a successful implementation or restriction render, installed adoption, feasible provider timing/current eligibility, an actual read or a strict successful case. The deferred parent-publication and finite local publication-window boundaries need explicit plan approval and real tests before use. A failure there is implementation work or a revised plan, never authority to weaken capture/cleanup. The lead owns actual C37 cleanup confirmation and complete P8 digest retrieval. No source/runtime edit, RPC, model call or paid probe occurred in this planning task.


## C38 parent publication failure containment — 2026-10-20

This appendix refines the approved deferred-parent-publication design without changing helper APIs, cursor semantics, budgets or native criteria. The entire preceding plan remains an exact byte prefix. Source inspection confirms main() calls config.load() before cmd_unanswered; therefore the narrow scheduled canonical dispatch MUST occur in main before that initial load. It recognizes only the canonical scheduled command/context predicate and delegates to the reviewed lifecycle; ordinary parser, unscheduled verbs, init/update/login and other CLI bytes remain unchanged. Add a stalled initial-main-config test proving no unbounded configuration work precedes scheduling. Internal observational worker dispatch does not recursively select this branch.

Parent publication may fail or overrun after capture has exclusively created discovery.json, inventory-view.jsonl, inventory-view-envelope.json or inventory-view-progress.json. A capture exception is not proof that nothing was written. Before publication, under the existing authorized operator/run ownership controls, record the exact canonical private run directory identity and each of these FOUR literal paths' preimage status. Never glob a directory or delete by filename/nonce alone. Existing files, symlinks, foreign directory identity or an ambiguous preimage must fail publication before calling capture; preserve them exactly. Include any additional legacy receipt target only if the actual canonical invocation already requires it and its exact path is source-derived and reviewed; no general recursive cleanup.

Keep a finite parent-owned publication record in memory: attempt, owner UID, original genuine context nonce/supervisor, directory device/inode, each path's pre-absence and observed post-creation device/inode, uid, mode, link count, byte count and SHA256. Validate actual complete content against the expected discovery record/current nonce, original output hash and exact source identity. Bind view/envelope/progress to that same discovery via existing pure producers/validators and exact expected byte hashes. Record postimages immediately after the call returns OR raises, before further publication/output. Partial or invalid bytes, absent creation provenance, unexpected inode replacement or inability to bind a file to this attempt are UNPROVEN OWNERSHIP, not permission to delete it. No helper API change or process-global os.open monkeypatch is authorized to manufacture ownership receipts.

On capture exception, incomplete required capture, publication deadline overrun or failed terminal validation, withhold canonical successful output and ordinary artifact locator. Within the existing finalization allowance attempt withdrawal ONLY of the four exact newly created files whose ownership is proven. Revalidate the original directory identity, no symlink traversal, current device/inode/owner/mode/link count/size/hash and nonce/content bindings against the recorded postimage immediately before unlink; remove in reverse dependency order (progress, envelope, view, discovery). Preserve any prior file and any concurrent foreign replacement/update. Never overwrite, restore, remove or decrement cursor.json, its existing runs/root order, workset-reserved.json or other pre-existing/foreign state. Reservation/cursor mutations keep unchanged existing helper semantics; no rollback or transaction framework is introduced.

Successful withdrawal means all proven owned publication artifacts are absent and all prior/foreign objects retain their recorded bytes/metadata. A changed, ambiguous, partially written or otherwise unprovable object is left untouched and reported as failed containment; do not assert cleanup success. With no atomic compare-and-unlink primitive in the unchanged helpers, ownership controls must exclude concurrent writers during the withdrawal operation. If that exclusion cannot be proven, do not unlink: retain the ambiguous evidence, mark containment unverified and stop the case/readiness branch. No successful discovery, v2 inspection, readiness, effect or finalization credit may be claimed from this attempt until genuine containment is proven. Root must retain the failed receipt and unresolved artifact references; no retry, adoption, authority fabrication or validator relaxation follows that failure.

Tests must cover capture raising immediately after discovery creation, failure after each subsequent v2 artifact, publication overrun after all artifacts exist, invalid/partial creation, and deadline exhausted before withdrawal. Start with pre-existing files and assert byte/metadata preservation and no capture call. Inject a foreign inode replacement and same-inode foreign content update after postimage recording; neither may be deleted, and containment must fail closed. Include an unproven concurrent-writer exclusion case: no unlink/credit. Verify exact owned withdrawal when ownership is proven; cursor and pre-existing reservation marker remain unchanged by withdrawal in every case. Genuine logical exit3 full-enumeration/independent-root semantics remain unchanged; publication failure is distinct and never receives that positive credit.

These are implementation and source-review obligations, not present runtime verification. If existing capture hides an error or cannot supply enough ownership evidence through normal returned/observed files, the correct result is failed containment/no readiness. Any additional capture API or ownership-primitive change requires a fresh specifically reviewed plan amendment before implementation.


## C38 concrete publication exclusion and required legacy transport

The normal strict driver invoke_job sets CS_OPERATOR_ACCEPTANCE_RECEIPT and its nonce (Actor scripts/operator_operational_test.py463). Preserve that required existing transport; refusing it cannot satisfy the original case. Existing operator_recovery creates a fresh private run directory and authentic supervisor context. For publication/withdrawal the canonical parent opens that exact private directory with O_DIRECTORY/O_NOFOLLOW, validates its device/inode/owner/mode and holds a nonblocking exclusive flock on that existing directory descriptor throughout reserve/capture/validation/any withdrawal. No new lock file or generic lock framework. All new canonical scheduled publication attempts obey this lock; a second cooperating attempt refuses before mutation. Worker descendants are already quiescent. Native progress follows terminal output, not concurrent publication. This excludes cooperating application writers, not an arbitrary uncooperative process with the same Unix UID. Preserve prior/foreign changes by exact inode/content checks; do not invent protection against a hostile same-UID writer or claim atomic compare-unlink. Tests prove actual independent-process contention/refusal and foreign replacement/content preservation.

The required legacy capture helper remains byte-identical and keeps its existing finite CAPTURE_SECONDS5 and own fork/cancel/reap/partial-cleanup. No fresh global allowance: invoke it only inside the existing parent publication window and check the original absolute publication deadline before and after it; any overrun fails publication and must withdraw proven new success artifacts inside the existing finalization/total boundary. A finite helper can cross its local reserved window; that is a failed attempt, never completed credit or authority to extend540. The existing explicit local-filesystem stall limitation remains.

In addition to the four health/view literal paths, source-derived legacy directory_path() may contain exactly this canonical CLI parent's PID-start.json successful record. Record its preabsence and exact directory identity before capture (creating only the helper's normal private directory if necessary through its existing helper). Validate the final record with its existing actual argv, parent PID/start, native/supervisor ancestry, original nonce/owner, exact output bytes/hash/code and current package digest. Track and withdraw ONLY this proven-new exact final success path on parent publication failure under the same publication lock and directory/inode/content checks. No glob, arbitrary receipt file, foreign/pre-existing success deletion or cursor/marker rollback. Existing helper-owned partial/failure diagnostics retain their unchanged cleanup/failed-evidence semantics; they grant no success. Missing/malformed final legacy success means required capture failure even when capture() silently returns. Refuse pre-existing successful target before mutation.

Tests must include actual legacy-enabled canonical integration, failure/timeout after its final record publication, its child cleanup/reap, exact owned final withdrawal plus four health/view files, pre-existing/foreign legacy final preservation, missing/failed legacy record refusal, genuine logical3 native correlation and real directory-lock contention. No fake native context in the actual-read harness. Source review must inspect the exact ownership assumptions and unchanged helper behavior; the subsequent strict actual case alone proves genuine native transport.


## C38 guarded activation journal-order correction — 2026-10-20

This appendix authorizes no implementation until independently approved. Preserve the complete preceding plan as an exact byte prefix. The two P10 attempts remain refused with zero publications: attempt-c_8tqu6v encountered a held lock; attempt-ma9zmp54 observed an unproven automatic-update idle window. Neither refusal is installed or readiness success. Preserve P10 and all earlier packets unchanged.

### Demonstrated defect and narrow decision

The current packet's idle_window orders automatic-update events only by realtime timestamp and requires every label at the latest timestamp to be completed. Actual retained journal records for the same Café process contain progress followed by tick OK with the identical realtime AND monotonic timestamp. Trusted journal sequence numbers95725669/70 are progress;95725671/72 are completed, within sequence source6930a88682fc4007ac75d7022ed46801 and boot0ba50655f5a84837b91434d696ade281. Consequently the existing predicate refuses this genuine ordered terminal completion. Evidence is c38-header-codec-packet/root-idle-collision-journal-whitelisted.json under the workflow evidence root. This historical observation is not present live idle admission.

Correct ONLY the new private successor packet's idle.py journal parsing/idle-window ordering and directly focused private tests. Keep the prior packet immutable. Do not change activation transaction, ProductionOps, Journal, lock paths, namespace/process/DB/voice/client checks, services, automatic-update settings, daemon activity, command deadlines or allowance for unknown work. Kernel source and installed payload are unaffected by this helper correction. The reviewed codec candidate still requires its own complete four-publication packet proof and actual installed review.

Use journalctl's trusted __SEQNUM with __SEQNUM_ID and _BOOT_ID to determine event order, rather than stdout order or a message's apparent percentage. Retain the existing journal query's selected service/PID, two-hour scope,64-record bound and absolute read deadline. Validate each returned row's _PID against that selected process and _BOOT_ID against the current OS boot ID, read from /proc/sys/kernel/random/boot_id and normalized only by removing its standard hyphens. Where the trusted _SYSTEMD_UNIT is returned, require it to equal the already selected service; a mismatch refuses. The query remains explicitly filtered by _SYSTEMD_UNIT and _PID. No new provider/engine operation or broader journal query is needed.

Before classifying any record validate all required trusted fields. __SEQNUM must be a nonempty ASCII decimal string of at most20 digits, positive and at most2**64-1. __SEQNUM_ID and _BOOT_ID must be32 lowercase hexadecimal characters. __REALTIME_TIMESTAMP retains the existing nonempty decimal-string length1..20 contract, parsed as integer microseconds. MESSAGE remains a string. Missing fields, JSON duplicate keys, multi-value/list fields, malformed identifiers/numbers or type coercion refuse the entire idle observation; do not drop bad rows. All rows must share exactly one __SEQNUM_ID and the selected current boot/PID. Different sequence sources/boots cannot be compared, even if realtime values appear ordered. No fallback to realtime, journal output order, cursor text or a hardcoded known source ID is allowed.

Within that validated single source, deduplicate only records with identical sequence number AND identical required trusted metadata, timestamp and exact message. A repeated sequence with different message/timestamp/identity is conflicting and refuses. Sequence gaps are normal journal filtering and do not imply missing work by themselves. Sort by integer sequence number. Realtime timestamps must be nondecreasing in that order; a reversal is ambiguous and refuses rather than extending the idle interval. Keep exact existing message classification: tick OK is completed, the existing running marker is running and every other automatic-update message is unverified. The highest-sequence record alone determines the latest event; it MUST be completed. Later running or unverified progress refuses, including when its realtime equals the previous completion. An empty record set refuses.

Age remains the unchanged realtime rule on that exact terminal event:0 <= observed_time - terminal_realtime < interval -60 seconds. Equality at the upper boundary, stale and future completion refuse. Ordering precision does not create a new interval, grace period or static admission. Every actual apply still obtains all four existing nonblocking locks and rereads complete live idle/process/namespace/DB/client/voice state within the unchanged20-second forward/30-second absolute lifecycle. A free replay of a historical completed event never supplies the actual apply's idle observation.

### Required free tests and review sequence

Retain the exact whitelisted actual collision rows and hashes. Demonstrate the old predicate refuses those rows. A corrected pure-helper replay must accept their terminal sequence only at an explicitly constructed observation instant inside the existing age window; at actual stale time it must refuse. Do not call the replay live acceptance. Assert highest sequence95725672 determines completion despite identical realtime/monotonic timestamps and reversed journal output. Do not hardcode these values in production logic.

Run focused cases for chronological/reversed/permuted order; identical duplicated rows; normal sequence gaps; progress then completion at equal timestamps; completion then running/progress at equal timestamps; completion followed by unrecognized message; empty rows; stale/future/upper-bound age; malformed/missing/list/bool/negative/zero/overflow/non-ASCII sequence; malformed/missing/mixed source ID; malformed/missing/foreign boot; wrong PID and returned wrong unit; conflicting duplicate sequence/message/timestamp; duplicate JSON keys; realtime reversal; and missing required MESSAGE/timestamp. Every ambiguous or latest-noncompleted case refuses, with no target publication.

Adapt the retained19-case complete idle.check private six-profile fixture harness to include authentic-shaped journal metadata and keep every existing busy/unknown/deadline control. It must still refuse preparation, inflight, background, workflow, voice, connected-client, missing schema, unknown automatic-update state, expired deadline and unknown journal evidence. Add an actual-production-check seam replay using the retained whitelisted rows and constructed private profiles/commands; no real daemon/provider/settings mutation. Retain exact commands, complete outputs and exit codes. Reuse unchanged14 transaction controls, four publication fault/rollback matrix, full payload/pin digests, normal-mal validator and preservation checks on the newly frozen successor packet; no automatic installation or provider retry follows a failed free check.

Fresh independent source/helper review must approve these actual changes and conservative ordering rules before successor packet review. Preserve all other helper bytes; explicitly qualify idle.py as the sole changed helper and assert transaction/non-main activation logic remains unchanged. Freeze fresh preimages, source/proof snapshots and exact helper hashes. Fresh packet approval, root authority, unchanged four-lock actual apply and independent installed review remain required before the already approved one new-candidate component read. The failed original read remains failed; no native case or all25 closure credit is established by this correction.


## C38 canonical contact-rollup readiness clarification — 2026-10-20

Preserve all preceding approved plan bytes. This clarification repairs an overly broad internal component harness predicate; it does not change kernel behavior, the original strict driver, native interpretation or operational acceptance. Canonical unanswered output reports the strongest bucket and oldest relevant conversation per address. Successful scheduled output must preserve that existing contract, rather than expand one public row per observed root.

The corrected-candidate actual read completed normally in492.458711 seconds with complete inbound/Sent enumeration,118 original roots and their complete projection map, five usable visible roots,92 visible held roots and no live/zombie/unproven owned descendants. The original harness remains FAILED with child exit3 and the sole error known_root_not_visible. An independent free AST-only replay proves all21 public omissions are complete normal unheld roots for one address, newer than its visible open representative and without exact-thread Sent. They are canonical contact rollup, not SELF/fixture exclusion or lost observations. Preserve the original result, judgement, output, times, hashes and exit without rewriting any of them.

Readiness requires complete exact original-root-to-projection coverage and original source provenance in the retained actual observation; every unknown or held root must remain visible, and usable complete independent normal work must be visible. A normal root may be absent from public buckets ONLY when a retained per-root deterministic proof establishes unchanged canonical contact rollup for that exact root and representative. Require same exact normalized sender, a visible normal complete unheld open representative, original inbound/provider identities and dates, absence of a matching real Sent answer, and the canonical strongest-bucket/oldest-thread pure replay. No blanket normal-root omission, sender/domain shortcut, fixture exception, inferred settlement or generated authority is allowed. Unexplained omissions, incomplete enumeration, missing/altered provenance, any invisible held/unknown root, unusable independent work, nonnormal worker or incomplete cleanup still fail. Other legitimate settlement cases need their own retained original proof and fresh review; this correction admits no settlement-only omission.

Use a new private, read-only supplemental evaluator over these exact retained actual files and exact unchanged installed source; no cs/config/provider import, native context, reservation, publication or effect. Its positive output must identify itself as a supplemental semantic assessment, bind original result/judgement/outer/source/full121 hashes, preserve the original child exit3/error, and prove that this was solely the harness classification failure. Verify normal=true, cleanup_complete=true, actual worker code0/3, complete enumeration/coverage/usable work/held visibility and original540/cleanup bounds separately. Verify original outer timed_out=false, remaining=[], unproven_orphans=[]; never fabricate child exit0 or infer readiness from bare3. Inject missing roots, omitted held/unknown roots, changed source/provenance, altered dates/representative/Sent and other original errors to prove refusal. Retain full exact per-root mappings and pure replay evidence; include independent diagnosis hashes.

Obtain fresh plan approval before supplemental implementation and fresh M3 independent review of the actual retained read plus corrected criterion before readiness credit. A new actual provider read is unnecessary for this demonstrated harness-only correction and is not authorized by it. Required closure/prelaunch guards may accept only this explicitly qualified supplemental assessment, its exact original artifacts and fresh M3 approval, preserving original exit3; they must not silently replace the original outer result or permit another failed-test class. No strict-case/native validator is changed. After actual readiness approval, the one unchanged strict case38 and all25 original closures remain mandatory; prior partial cases never aggregate into acceptance.


## C39 selected-owner binding for local technical holds — 2026-10-21

Brief amendment APPROVED: c39-unknown-repair/brief-review.md under the existing
2026-10-18 workflow evidence root. Current brief SHA256: f529e8fce51ffae613372a4546f53f76b64d38b8fc909c45c12821d577c0f704.
This continuation preserves preceding plan bytes, C38 FAILED/cleanup PASS118,
all25 closures and the existing completion task/milestone identities. Exact first
C38 parent exception remains UNVERIFIABLE; no historical success is reconstructed.

### Decided source change and ownership

One executor owns cs/task_assignment.py, cs/unanswered.py, cs/review.py, the
single cs/cli.py local fallback and focused tests. No operator_workset consumer,
RPC implementation, service, permission, budget, timing or native validator edits.
Add an explicit selected-owner keyword to local _unknown production and carry
it through known selected-settings paths. Both actor_uid and source_owner_uid
must equal that selected owner; root stays exactly the requested root. Retain
version1, complete=false, state=unknown, hold_auto_reply=true and empty task,
events, coverage/reply evidence. Do not invent space_id or usable authority.

project/projections and their deadline/primary-failure/invalid-root cases use
settings.engine_owner_uid. sweep's omitted-projection fallback and split_inbound
use the same selected owner. Review fallbacks receive its settings owner; parent
interruption uses its already authenticated review binding/settings owner.
Scheduled discovery interrupted fallback may use only its validated checkpoint
configuration.owner_uid. When no authenticated configuration exists, keep the
result incomplete and unbound; never load extra configuration/RPC merely to fill
an identity, nor infer identity from arbitrary rows. The CLI local no-thread
fallback uses its existing selected settings. Keep optional internal fallback
parameters compatible where an unbound failure must remain representable.

Already received projection dictionaries are preserved, even when malformed;
only locally created fallback records are bound. Consumer foreign/missing-owner
rejection stays byte-identical. An omitted/unknown hold never enters candidate
selection. Exact-root, peer/company, coverage and current effect guards remain
unchanged. Preserve all account/global timeout reservations: local child reaping
does not prove remote cancellation. No new retry/diagnostic retention framework.

### Free proof and source gate

Use existing interpreter and script tests with -B/PYTHONDONTWRITEBYTECODE. Baseline
bash tests/run.sh is running before edits; retain its full log and terminal exit,
report pre-existing failures without repair outside scope. First reproduce the
retained C38 held-row contradiction with free pure replay; retain red evidence.
Add semantic tests for actual local producer -> split_inbound -> inventory and
canonical publication with explicit private scratch/mock reserve/capture only.
Include one independent valid candidate alongside technical holds; assert hold
visibility/no candidacy and strict rejection of missing/foreign received actor
or source owner. Cover primary failure, exhausted deadline, omitted projection,
review and scheduled interrupted fallback and absent authenticated owner.

Run new tests plus task_assignment, rpc_reads (including unchanged surviving
remote timeout controls), unanswered, review_budget/union/progress/inventory/
evidence_gaps, operator_workset/CLI and scheduled discovery/publication suites.
Retain exact commands/results; fresh M1/M2 source integration review must approve
all changed bytes and actual restricted installed CLI delta. No dependent runtime
work before approval. Preserve unrelated dirty source and Stripe composition.

### Adoption and remaining acceptance

After source approval, freeze current complete installed preimages of both clone
packages and Actor pins. Reuse the reviewed finite four-lock activation with fresh
packet review, complete fault/rollback proof and current idle/ownership checks.
Install only the reviewed source deltas, compose against current actual payloads,
preserve engines/services/cron/settings/grants and unrelated files. Obtain fresh
independent installed verification before the already authorized ONE normal-owner
new-candidate readiness invocation. Full enumeration, complete independent usable
root, explicit held coverage and owned cleanup remain mandatory; all-UNKNOWN
fails. Reuse unchanged earlier actual review evidence. Only readiness PASS admits
ONE unchanged strict two-clone case with all original reply/draft/ACK/native/jobs/
cleanup criteria in that same case. Failure stops the paid branch, no blind retry.
Then reconcile original affected docs and all25 critic/final/checker obligations.
No commit, push, installer or release. Rollback only exact owned source/pin
preimages through the same guarded packet; never roll back mailbox/provider state.


### C39 exact current-composition provenance prerequisite

Free preflight now demonstrates a separate prerequisite: old acceptance pins
refer to C31 actors/346df kernels, while reviewed Stripe/B2 and the installed
context correction are current. Seven live clone references differ. Preserve
those approved changes; never restore old engines or loosen runtime matching.
The unchanged strict driver still refuses until exact provenance is composed.

Extend only A scripts/operator_operational_common.py's finite current-recovery
resource transition and literal actor/source/provenance pins, plus its focused
offline tests/private immutable composition evidence. Do not edit the driver,
seven acceptance criteria, protected-policy/peer/excluded rules, native schema,
authority, deadlines or budgets. Keep historical transition branches unchanged.
Fresh plan approval is required before this implementation. A is the existing
operator-assignment-recovery-resume-20261016 worktree, not a new workstream.

Build one finite two-actor transition from their original preserved C31 package
(and exact full inventories/digests) to their current installed packages. Bind
entire canonical before/after inventories and exact changed/added resource
sets to literal hashes independently checked against retained Stripe/B2/context
source and installed approvals. Retain complete baseline proof references and
all metadata; reject any missing, extra or changed unrelated resource. Keep
peer/excluded actors and their source proof byte-identical. New staged manifest
and inventory files are private immutable evidence, never edits to old receipts.
Update selected actor roots/pythonpaths/full payload/Python digests to those
exact reviewed current targets; preserve role, UID, mailbox and send/draft mode.

Relocate only old live-file provenance references whose retained immutable
preimages are proven against historical hashes. Add exact separately reviewed
current settings/AGENTS/cron/CLI and source-review references; do not silently
refresh a stale hash as proof. Composer may update the finite actor-binding and
recovery-root/added-resource literals in addition to existing kernel/provenance
literals, with AST/field checks proving all runtime validation functions and
nonallowed policy fields unchanged except the new exact resource-transition
branch. Fresh source and complete packet reviews cover these exact changes.

Tests reject wrong actor/root/owner/mode, a changed byte or metadata in either
entire inventory, missing/extra/foreign resource, wrong transition hashes and
changed peer/excluded/protected rules. Real free normal-owner read_runtime_policy
and both clone imports must pass on the staged exact composition before any
paid read. Retain the previous stale-policy refusal. Guarded adoption remains
only reviewed kernel files plus exact A common/policy pins; no engine restart,
service/cron/settings/grant or customer-data change. Existing worker, readiness,
strict case and all25 closure requirements remain unchanged.
