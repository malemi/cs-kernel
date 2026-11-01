---
status: active
brief: ../briefs/2026-11-01-executor-long-cache.md
owner: kernel integration lead
created: 2026-11-01
dependencies: approved brief; fresh plan review before implementation
task_id: pydantic-headless-executor-20261028
---
# Executor long cache

## Classification, evidence and boundaries

Substantial development: selected TTL, billing and independent acceptance change across two repositories and two installed clones. No fast path. This is a bounded continuation of parent M5, not a new restoration strategy. A fresh reviewer must approve this plan before source implementation. Each milestone needs integration review before dependent work. Existing valid core, cache, route, lifecycle, permission, source and release evidence remains reusable for unchanged predicates.

K is `/home/mal/worktrees/cs-kernel-pydantic-headless-20261028`; D is `/home/mal/worktrees/mrcall-desktop-pydantic-executor-20261028`; Q is `/tmp/mrcall-ai-kit/pydantic-headless-20261028/executor-long-cache-20261101`. The framing approval is Q/brief-review.md and its immutable input Q/approved-brief.md, SHA-256 `fc583b0fc32f54dbb2f26dbd65017731cfebadd5dc58dbd1595589f3e0d1d889`. The repository brief adds the lead's dated accounting checkpoint. That addition is APPROVED in Q/brief-finance-checkpoint-review.md; Q/approved-brief-current.md and the repository brief have SHA-256 `b9866d90e074e7354810a791958092902857b398b3b0822bfc6875f3886347e8`. Preserve both historical immutable approvals. The current reserve-sizing brief is separately APPROVED in Q/brief-budget-r1-review.md; its immutable Q/approved-brief-budget-r1.md SHA-256 is `e97477d4e137489f7001e7fd753463260308886ffd8462df4bf83be572a47979`. This proposed plan is Q/plan-budget-r1-candidate.md and requires a fresh plan review before activation. Canonical K/D/clone documents and financial configuration remain unchanged while the exact tagged-state suite runs.

The prerequisite actual-wire check is complete in Q/actual-ttl-prefix-verification.md and actual-ttl-prefix-proof.json. Requests 1 and 20–23 have identical complete bootstrap-prefix SHA-256 `e1209bc301a7ab94909f2bc784a72b5ab33701685a4ccbd20dbc2c2637160126`, explicit 5m markers, the same recorded model and endpoint. Gaps 1199.31s and 551.84s precede zero reads; 3.86s precedes 357059 reads. Expiry is consistent with these facts; provider eviction, internal routing and cache-key implementation remain unknown. Do not repeat inference to investigate them.

Keep executor F fail-fast and P bounded history, all delivered-page/EOF/source checks, IMAP behavior, business judgments, human holds, prompts, model identities, SDK versions, send grants, dedup and source authority unchanged. No engine work, new model, keepalive inference, dependency upgrade, source overlay, supervisor message or public push. The failed 0.70.1 attempt stays consumed. Its cleanup and exact historical receipts remain intact.

## Decided compatible contract

Use the existing independent primary/fallback mode settings. `cs/operator_recovery.py` already selects `CS_EXECUTOR_CACHE_MODE` separately from `CS_EXECUTOR_FALLBACK_CACHE_MODE`; metadata renewal freezes the latter before intake. Enable opt-in 1h on the reviewed primary. Keep normal fallback resolution on disabled/5m and retain `pydantic-fallback-resolution-v1`. An explicitly requested fallback 1h must fail before intake, primary submission or business work through normal metadata preflight. Never silently downgrade a requested fallback mode. A primary 1h plus fallback 5m is valid because these are distinct attempts, each with its own uniform wire markers and reviewed prices. Full metadata-driven fallback 1h support is excluded from this correction.

Add one optional explicit `cache_write_1h_usd_per_million` price to primary Pricing. Existing disabled/5m configurations retain their four-rate or upper-only semantics; absence of the new field must remain compatible in canonical comparisons and fallback projection/digests. Do not make the four legacy metadata prices require a fifth rate or accidentally serialize an unsupported extra field into strict ResolvedPricing. Require complete relevant exact rates and a sufficient upper rate for selected 1h before launch; unknown models/providers need independently evidenced prices or refuse. The active direct Anthropic Opus 5.5 snapshot dated 2026-11-01 gives normal/read/5m-write/1h-write/output USD per million 4/0.20/5/8/20. Its input upper rate is at least 8, with any larger existing conservative bound retained; output upper is at least 20. Preserve the dated official-source evidence and identity binding.

Reuse `cache_write_tokens` as the inclusive creation total and `cache_write_1h_tokens` as its subset. For input total I, read R, creation W and one-hour H: require 0 <= H <= W and R+W <= I; normal N=I-R-W; five-minute writes W-H. Exact estimate is `(N*normal + R*read + (W-H)*write5m + H*write1h + output*output_rate)/1000000`. Never add H to input or to W. Require SDK and raw totals, nested/top-level split representations when present, and the SDK H subset to agree. A positive write total in 1h mode needs unambiguous supported split evidence; never infer a missing split from configured TTL. Unknown/malformed splits or charges preserve the reservation and stop subsequent requests. Disabled/5m preserve their existing refusal of unsupported 1h usage.

Use public pinned SDK settings and CachePoint with the selected TTL for automatic, instructions, tools and immutable bootstrap breakpoints. Select one TTL throughout each request; this enforces longer-before-shorter ordering without mixed-marker policy. Keep disabled marker-free and existing implicit 5m semantics. A 1h marker must explicitly say 1h; absent TTL means 5m and cannot pass a 1h binding. No request-body mutation. Inspection of the existing 2.63.0 environment confirms all relevant settings and CachePoint accept 1h; actual serialization remains an M1 check.

## Milestones

### M1 — kernel TTL, exact accounting and free SDK proof

Owner: kernel executor implementer. Own K/cs/operator_executor_config.py, cs/operator_executor.py, cs/operator_executor_evidence.py, tests/test_operator_executor_cache.py and targeted route/alias runtime tests. Change cs/operator_recovery.py only if an actual preflight gap appears. Existing ModelResponse already carries the H subset, so no new response record or codec discriminator is planned. Protocol changes require a demonstrated need and review. Do not edit Desktop, business tools or clone state. Keep shared canonical serialization and fallback projection changes together under this owner.

Extend config validation, exact estimate, raw/SDK usage binding, supported model settings, auto-cache profile and initial CachePoint. Producer evidence must reconstruct the same selected mode, prices and arithmetic. Preserve uncertainty, original job ceilings and deadline behavior. Add focused controls to the current cache and route suites rather than parallel machinery.

Verification: use the pinned project test interpreter to run `tests/test_operator_executor_cache.py`, `tests/test_operator_executor_routes.py` and `tests/test_operator_executor_alias_runtime.py`, retaining exact interpreter identity, commands and complete output. Socket-denied real SDK controls must cover both Anthropic Messages routes with disabled/5m parity and explicit 1h serialization, every marker including bootstrap after more than 20 history blocks, unchanged prompt/page bytes and bounded marker count. Free OpenRouter 1h serialization is compatibility evidence, not authority to admit a fallback 1h request.

Require a red/green 1h write/read example with Decimal arithmetic; total/subset disagreement, H>W, negative/bool/unknown buckets, absent positive-write split, conflicting split representations, missing/partial/nonpositive/over-upper 1h prices, unknown TTL, mixed markers and wrong source/model/policy must reject. Prove nonzero uncertainty blocks the next request, conservative input/output reservation bounds actual 1h writes, cumulative soft/hard ceilings retain their semantics, and unsupported fallback1h refuses before intake or any inference submission. Existing primary1h -> distinct prework fallback5m free path must retain primary uncertainty, original remainder and deadline. A deterministic delayed-turn cache fixture may compare the observed gaps under 5m/1h; label it simulated economics, never measured provider savings. Fresh M1 review precedes M2 integration.

### M2 — independent Desktop codec and installed free integration

Owner: Desktop consumer implementer. Own D/scripts/operator_executor_transport.py and scripts/tests/test_operator_executor_transport.py. Touch scripts/operator_operational_common.py, scripts/operator_operational_test.py and operational-evidence/runtime-policy.json only for demonstrated route/policy binding needs; keep financial policy updates lead-owned and sequential. Never edit the live Desktop checkout. Kernel owner supplies reviewed M1 private receipts and actual configuration; Desktop reconstructs costs independently without importing kernel validators.

Extend independent pricing normalization, route validation, uniform TTL validation, usage_cost/response_cost and reviewed launch comparison. Keep legacy four-rate fallback metadata projection and strict schema shape unchanged. Prove actual selected-mode/model-settings/wire agreement, including rejecting SDK-settings/wire divergence; a wire-only success cannot establish the SDK contract. Retain all existing identity, call/result, page, phase, business, ownership and terminal checks.

Verification: M1 exports through `CS_EXECUTOR_TEST_EVIDENCE_ROOT`; run `python3 scripts/tests/test_operator_executor_transport.py` in D with `M4_CACHE_CONTROLS` bound to those exact cache exports and `M4_ALIAS_PACKET`/`M4_REAL_PACKET` bound to the actual matching current supervisor/fallback packets. Relevant integration cases must execute, not silently skip for absent environment. Replay M1 real SDK receipts through both producer and independent consumer. Mutate each H/total/normal/cost/price/mode/marker/source field separately: both must reject the invalid case, and both must agree exactly on valid mixed-bucket arithmetic without double count. Replay legacy disabled/5m and metadata fallback fixtures unchanged. Run the existing operational common/runtime-policy negative controls only where touched, retaining actual command names from that harness. Install the candidate normally into a disposable Python 3.11 environment with existing dependency versions and run the actual recovery -> metadata preflight -> executor -> SDK/CLI free path; capture source, interpreter, provider endpoint and policy identities. No live keys or paid inference. Fresh M2 integration review must approve primary1h/fallback5m and unsupported-fallback1h behavior before release.

### M3 — immutable MINOR candidate and normal adoption on both clones

Owner: integration lead for K release metadata, source manifests, CHANGELOG and docs; Desktop owner for reviewed consumer-family delivery; clone owners for their exact env, pins, locks, authored-context preservation and installed verification. The default next version is 0.71.0 if unused; verify the actual tag namespace before choosing. Never reuse or alter 0.70.1. Commit/tag only under the existing task's release authorization; this plan grants none independently. Public push remains unauthorized.

Follow K/docs/release-procedure.md in order. Declare BOTH-clone FULL because execution/accounting and acceptance boundaries are touched. Run one complete `bash tests/run.sh` at the finished pre-release candidate, then the separately mandatory one complete tagged-state run after the immutable release tag. These are distinct required source/tag gates, not permission for duplicate empty reruns. Reuse all earlier unchanged proofs; no additional broad run unless changed bytes or an actual failure makes it discriminating. Before either expensive suite, focused controls must pass. Record full logs rather than capped summaries. A failure stops release; diagnose from retained actual output, make/review a material repair, then run only justified replacement checks.

Normal private package-manager adoption must verify both actual clone interpreters from outside K, exact immutable tag/commit, `cs --version`, `cs verify-install --json` with documented offline reference flags where appropriate, complete 166-or-current package file inventories and no extra/missing/symlink/shadowed payload. Regenerate and independently install locks alone in disposable environments; compare complete package maps and nonkernel dependency provenance. No dependency churn without demonstrated need. Preserve company-authored context, take exact rollback snapshots, and perform the mandatory kernel/clone version sweeps. Rebind the reviewed consumer-family/source policy and four primary/fallback route policies to actual installed bytes; primary1h and fallback disabled/5m remain distinct. Free installed finance, TTL and recurring fallback controls must pass before paid admission. Fresh installed-candidate review approves the exact identities and admission inputs before M4.

### M4 — one genuinely new sequential FULL cohort

Paid admission remains HELD. Neither this financial correction nor its brief approval resolves the frozen R7 consumer/aggregate60 incompatibility or the separate4MiB protected-inspect limitation. M4 requires an explicit operator acceptance-scope decision and fresh acceptance-contract review, as recorded in the protected-acceptance prerequisite below. Continued free M3 work remains approved.

Owner: lead admission/accounting and Desktop acceptance runner; clone owners manage only exact owned fixtures, processes and scheduling windows. Depend on M3 review. Reuse the existing genuine FULL/signup machinery and its business oracle. Do not reset the consumed 0.70.1 attempt, manufacture completion or resend historical effects.

The revised authority candidate Q/authorization-admission-r1.proposed.json retains actual operator quotations and proposes aggregate95, native target10/hard18.25, signup2 and maximum one38.50 cohort. Activation requires fresh approval of this amended plan; preserve Q/authorization.json and all earlier unadmitted12/16/34 receipts unchanged. After approval, the lead records the activated authority separately as Q/authorization-admission-r1.json through the normal admission process. The existing finance-only refresh grants no authority itself. Its current qualified basis54.0427724 includes the conservatively attributed0.025155 endpoint delta; plus38.50 plans92.5427724 and leaves2.4572276. Preserve8.012607 historical uncertainty, all stale holds and unknown external/classifier/invoice coverage. No second endpoint refresh is needed merely to repeat this evidence. Any newly consequential independently observed charge must still reduce headroom. Apply reviewed bounds through normal policy/env surfaces, never a bypass; assert just-over-limit refusal and original per-job/fallback remainder controls in free checks first.

Before admission verify actual keys by supported nonsecret presence/authority checks, unchanged selected models/routes, dated complete prices, upper8-or-greater input for1h, source/lock/package identities, consumer family, exact business scopes and original ownership. Funds must cover the whole remaining cohort, native reservation overshoot, signup and retained uncertainty; otherwise hold. Freeze existing scheduling windows and pending effects, without altering unowned controls. Execute one fresh MrCall FULL -> Cafe FULL -> signup cohort sequentially, stop at first genuine job failure. Initial ERROR lines may recover; actual complete native/CLI, provider/Sent/receipt and signup predicates decide acceptance. Never spend on later stages after an earlier failed gate.

Retain all actual SDK/wire TTLs and bootstrap identities, raw/SDK usage buckets, exact independently recomputed costs and uncertainties. Compare reads at actual gaps honestly; no minimum real delay or extra inference is required. Real provider cache savings remain conditional on observed usage, not guaranteed by the flag. Independently reconcile possible effects and verify all exact owned PID/start identities, nonces, fixtures and scheduling controls are cleaned or held as required. No release of uncertainty from exit0 or absent ERROR. Fresh cohort integration review must approve evidence and cleanup before closure; failure remains failure and consumes this cohort allowance.

### M5 — documentation and parent restoration closure

Owner: lead across K, D and both clones. Reconcile operator runtime/cache/pricing/fallback documentation, affected Desktop policy/acceptance docs, clone live pins/context and relevant release claims. Existing correct unchanged documents are in the semantic review scope. Archive historical narrative verbatim; active context states present knowledge, real results and pending holds. Link this bounded correction into parent M5 without rewriting earlier failed receipts or asserting whole restoration from transport proof.

Invoke applicable doc-end and explicit doc-critic in each affected documentation harness, including living-context shape. Run each installed `doc-check.py --completion check` through its supported repository/task binding, and the optional verification-warnings check for the exact existing task when installed. Missing binding/helper remains explicit. Obtain a separate final reviewer through the actual installed user path after genuine BOTH FULL/signup and cost/cleanup proof; no integration reviewer substitutes for it. Only then use supported completion finalization/baseline advancement. Invoke the pinned protected checker only if its supported interface is available. Preserve the exact4MiB inspect limitation and original failures; never alter checker internals, synthesize acceptance or repeat unchanged paid acceptance to obtain a verdict.

## Rollback and limits

Before effects, remove the opt-in selection or restore the prior immutable package/configuration through the normal procedure under the owned pause window, then verify imported bytes and rollback identities. Disabled/5m compatibility provides rollback behavior, not proof the failed older attempt is acceptable. Do not modify installed package files. After possible effects, stop/reap only exact owned process groups, preserve private journals and uncertainty, reconcile exact provider/Sent/draft identities and clean only owned fixtures/nonces. Software rollback cannot undo delivery. Keep required holds until ordinary acceptance authorizes resumption.

This plan establishes a bounded implementation/delivery contract and the already retained TTL/pricing/accounting prerequisites. It does not establish implemented 1h support, provider cache retention/savings, full invoices, usable current credentials, new installed package identity, future FULL/signup results, resolved engine/IMAP behavior or restoration closure. SDK annotations are verified; actual 1h serialization and cross-codec semantics are milestone obligations. No paid call, release, clone adoption or implementation is performed by planning.

## Dated reserve-sizing amendment (2026-11-01)

The retained admission-sizing-alternative.md/json establishes both primary actors retain context1,000,000 and max output8,192. At conservative input8/output20 per million, maximum capacity-allowed input991,808 reserves8.098304USD. Earlier hard16 can therefore refuse below its soft12 proposal. Revised soft10 plus maximum reserve is18.098304, leaving0.151696 below hard18.25. Actual installed Admission probes admit at spend9.999999 and soft-stop at10 for both actors; reuse those receipts without repeating tests. Other eligibility gates and unknown-cost reservations still constrain admission and fallback. No output, context, model, coverage, SDK, fallback allowance or business guard changes.

One revised maximum cohort is18.25+18.25+2=38.50. Qualified54.0427724 plus38.50 is92.5427724, leaving2.4572276 under the unchanged aggregate95 ceiling. This supersedes only the earlier unadmitted12/16/34 proposal and is neither a full-job completion forecast nor invoice-complete available balance. Prior authority, reviews and failed attempts remain retained. M4 stays HELD pending fresh plan approval and the explicit acceptance-scope prerequisite.

At this amendment, the lead reports immutable v0.71.0 at c24ec85775ac352f91ea303ee7ac753c336dd404, source pre-suite PASS and the exact tagged-state suite still running. This amendment performs no new suite, tag, adoption, configuration activation or paid work. Canonical application waits for the tagged-state suite to end and fresh amended-plan approval. The implementation and protected-prerequisite notes below are preserved verbatim.

## Reviewed implementation checkpoint

M1 source is APPROVED after the retained REVISE. The prework fallback's missing
SDK-settings binding is repaired before its admission return; actual negative
controls now reject changed/omitted automatic, instruction and tool settings.
Kernel cache11, routes13, alias12 and core28 controls pass; only affected cache/
alias checks repeat after that repair. The first REVISE, red failures and invalid
initial red-summary qualification remain retained in Q.

M2 is APPROVED in Q/m2-integration-review.md. The independent consumer passes32
controls with5 unrelated optional skips, including the enabled current M4
cache/alias/real cases. A normally installed Python3.11 development candidate
0.71.0.dev2026110102 passes14 producer controls plus independent consumer replay.
All166 cs files match reviewed source, without extras;56 installed nonkernel
versions are retained. This development fixture is not an operational release.
Raw duration split replay is test-harness evidence; production journals retain
normalized W/H and the consumer independently checks costs/settings/wire/source.

## Newly established protected-acceptance prerequisite

Source-only verification in Q/pinned-r7-compatibility.md establishes that the
pinned R7 checker imports a frozen consumer accepting only disabled/5m, no1h
price field and H=0. Its check.py also hardcodes aggregate60USD. Native per-job
bounds are policy-derived and versions are artifact-derived. The mutable index
cannot substitute a newer consumer. The broader operator authorization and
lead-selected95USD ceiling do not themselves mutate this frozen contract.

Q/plan-r7-prerequisite-review.md APPROVED continued authorized FREE M3 work,
with existing schedules held. M4 PAID ADMISSION IS HELD until a supported,
separately reviewed acceptance path covers genuine1h, authorized95 budgeting
and the protected interface. Separating business acceptance from the legacy
goal requires explicit operator direction and fresh acceptance-contract review.
The separate4MiB protected-inspect limitation also remains. No checker, service,
index or unowned process is changed; no legacy completion is asserted. Source
release/install approval cannot waive this prerequisite or authorize a paid run.
