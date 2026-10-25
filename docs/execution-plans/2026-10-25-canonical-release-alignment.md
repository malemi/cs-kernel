---
status: active
---
# Canonical release alignment execution plan
Approved brief: docs/briefs/2026-10-25-canonical-release-alignment.md.
Owner: lead engineer; canonical changes belong to cs-kernel; clone adoption belongs to each maintained clone.
Classification: substantial development/release. New CLI/configuration and send/permission surfaces exclude the fast path.
Dependency order: M1 -> M2 -> M3 -> M4 -> M5 -> M6. Fresh plan review precedes implementation; fresh integration review closes each milestone before dependent work.

## M1 — freeze and reconcile the actual recovery candidate
Lead owns inventory decisions; installed-inventory executor owns both clone package/origin/pin inventories; canonical executor owns source reconciliation.
Capture complete original dirty/untracked bytes,modes,hashes and Git identities outside the repository. Never reset,stash or overwrite the original checkout.
Reconcile each installed cs module/resource and unexpected file against its declared release,canonical working source and the sibling's exhaustive delta inventory. Give every delta an explicit canonical mapping or justified exclusion; unknown material deltas block replacement.
Create an isolated release worktree from origin/main2821a6a,whose lineage retains published v0.53.0. Apply tracked dirty delta from518f599 and explicit untracked paths with hash guards; retain newer remote release metadata/immutable anchors.
Reconcile overlapping CHANGELOG,active-context and template inventory assertions manually. Do not restore0.52.0 metadata over remote0.53.0. Inspect separate Stripe Payment Links branch changes only where inventory identifies a required installed delta; existing branches are not automatic scope.
Installed standing-instruction reader snapshots can conflict materially with current charter authority over company files. Preserve their exact bytes and production behavior inventory; reconcile through a bounded explicit authority/behavior decision and fresh review. Do not silently restore an old source priority or drop managed production behavior. An unresolved material authority conflict blocks replacement.
Treat the recovered source as one reviewed composition spanning exact drafts,ordinary recovery/native discovery,worksets,logging/monitoring,workflow retirement and retained Stripe instructions. Keep clone-authored prose/configuration separate.
Verification: every inventoried file and deletion has status,origin,SHA-256 and decision; candidate package import closure includes needed untracked modules; original snapshot still matches its hashes; no installed-only required behavior is unexplained.
Review the recovered M1 composition before dependent code changes or runtime installation.

## M2 — restore green checks and finish the pending diagnostic decision
Canonical executor owns root-cause repairs; lead owns the existing logging-plan dependency and independent review.
Start with retained baseline failures: two company-shaped temp prefixes; actual Anthropic SDK auth headers; review.gather fixture/interface mismatches; stamped compose authority; draft-reply engine-error status; SIP wrapper request count; bootstrap scheduled-byte/hash receipts.
Distinguish stale tests from product defects using the actual final behavior. Preserve auth,permission,assignment,source-completeness and no-replay guards; never bless invented prior receipts or relax tests merely to obtain green.
Inspect the interrupted ACCOUNTING diagnostic continuation in its existing reviewed logging plan. Complete only authorized bounded diagnosis/repair and its regression/blind evidence checks when feasible. If required evidence or authority is unavailable,retain the exact unresolved issue and exclude unreviewed changes; never claim the incident repaired.
Verification: focused previously failing tests pass for demonstrated reasons; full bash tests/run.sh passes against the isolated candidate with fresh site-packages/template inventory. Supply real clone golden-pack inputs where applicable rather than counting a skip as parity.
Run new diagnostic/integrity regression paths explicitly if not yet wired into the harness. Preserve failure receipts and actual command/output hashes.
Review M2 before dependent package acceptance.


### Reopened M2 — actual draft material compatibility and publication diagnostics

Canonical executor owns only `cs/operator_inventory_material.py`, the actual
publication/fallback boundary in `cs/unanswered.py`, and focused regressions;
the lead owns retained-input replay and a fresh blind diagnostic check. The
verified failed input is `run-ojxx7tc9/workset-review.json`: six Gmail draft
fields (`bcc`, `from`, `identity_headers_valid`, `is_draft`, `mime_plain_only`,
`mime_structure`) are rejected before discovery capture. Retained tasks validate.
Add only the typed optional fields justified by the actual Gmail producer and
full retained rows, including nested MIME shape where present. Preserve the
closed schema, unknown-field/type rejection, owner/nonce/digest/source bindings,
full material projection, privacy and all assignment/action guards. Never drop
fields, ignore invalid material or replace the private inventory with a summary.

Make every pre-capture publication failure retain a finite sanitized cause,
actual stage/check and source origin under the existing trace/run identity.
The guard must cover material parsing, view production and material loading as
well as capture; a generic scheduled fallback must not erase that diagnostic.
Unknown causes stay explicit. Do not expose mail/header/body values, raw exception
text, credentials or local private payloads. Keep failure exit3, containment and
no-action behavior; logging does not grant execution authority.

Verification before any paid retry: validate both exact retained worksets; run
the real scheduled publication/CLI path with retained local input and demonstrate
complete bound discovery/view/envelope output. Exercise all six producer fields,
nested values and absent optional fields; reject a seventh unknown field, invalid
types, mismatched binding and publication failure at each guarded stage. Assert
safe finite diagnostics survive the scheduled fallback and appear through the
installed log/inbox path; a fresh blind reviewer must infer the failed check and
possible cause without the private truth. Run focused material/publication,
complete native receipt and causal regression suites plus `bash tests/run.sh`
with the genuine golden inputs. Fresh affected M2/M3 integration review is needed;
prior M1–M3 approvals remain historical scoped evidence, not approval of new code.

## M3 — add a minimal release-bound installed integrity check
Canonical executor owns one operator-visible read-only CLI route,extending existing CLI/package inventory surfaces; no watchdog,repair daemon or new monitoring infrastructure.
Compare the actual imported installed cs files and packaged resources,including unexpected files,against independently obtained immutable release content. Resolve the declared tag and expected commit from the truthful clone pin/lock; verify the requested immutable commit before constructing a clean package reference.
Do not trust version text,installed RECORD or a reference manifest copied from the same installed files as the comparison authority. Exclude only documented runtime caches; fail explicitly for modified,missing,extra or ambiguous package files and wrong import origin.
The command reports release identity and exact mismatches and never repairs site-packages. Normal recovery is reinstalling a reviewed immutable package through supported installation.
Verification: clean isolated release installation passes; modifying Python and a packaged template fails; an unexpected package file fails; editing RECORD to bless modified bytes still fails; wrong revision/import shadowing and unavailable reference yield explicit non-success; source and installer paths remain separate.
Document network/reference requirements and the limit that this is accidental-drift verification,not attestation against a malicious interpreter or command.
Implementation refinement: use the single `cs verify-install` route described by the retained integrity design; compare actual imported package files against independently resolved immutable Git object content, not dirty reference files or installed RECORD. The final installed-only native consumer also requires actual discovery producer root/PYTHONPATH fields beside its existing payload digest; add and test those two observed private receipt fields without changing discovery output, business guards or deadlines. This bounded diagnostic linkage is reviewed with M3 before FULL. Review M3 before final source freeze. Reconcile shipping documentation and obtain prepublication semantic/source review before freezing. Run the green suite, commit all shipping source and final release metadata for the next unused MINOR (currently0.55.0), and create its local immutable tag immediately. Capture that exact commit/tag and built artifact; no shipping code or metadata may change after acceptance without a new candidate and applicable review.

## M4 — prove FULL behavior on both exact candidate installations before publication
Lead owns safe-run coordination and spending limits; the existing protected-fixture runner owner owns live execution; independent verifier owns provider/engine readback.
Use the exact final release commit/local tag and dependency identities frozen after M3; install through clean supported package builds on both clones. Record immutable revision,artifact digest,actual interpreter/import origin and source/resource hashes. No PYTHONPATH overlay or direct installed edit may supply tested behavior.
Capture package/config/manifest/ledger/crontab preimages and active-work state first. Preserve pause,mode,permissions,budgets,company rules,technical-mail suppression and all uncertain business effects.
Run the existing protected native FULL contract with fresh fixture identifiers and its existing per-tick limits, at most USD16 aggregate and one initial run (a repaired affected retry requires a named cause and an explicit lead budget decision): independently received correct support reply; Cafe exact owner/full-ID provider draft with no send; ordinary acknowledgement/no-loop proof; expected signup policy; genuine job terminals; source/owner/session/process bindings; verified cleanup.
Kernel bash tests/run.sh is controlled harness evidence and cannot replace this native/provider gate. Historical signed R9 applies only to its original candidate. Never replay an uncertain fixture or synthesize the expected model answer.
Verification: original signed fresh FULL result validates the exact final package on BOTH clones and unchanged strict oracle; independent actual provider observations establish effects and absence of extras; schedules/enrollments/processes restore cleanly.
The current FULL policy has missing historical temporary paths and no release evidence. Reconstruct supported authentic references where possible. If producer enrollment is hard-coded to historical paths, a separately reviewed candidate-neutral enrollment correction may bind the actual immutable package without weakening any oracle, signature, owner, effect or native-job check; orient the owning repository first and retain its own source/tests/review evidence. Never use a path alias, fake receipt or mode relabeling to evade validation. Missing safe fixture,credentials,runner capability,approved bounded budget or required authority blocks publication while independent canonical work continues. Do not classify incomplete jobs or legitimate unrelated holds as completed proof without the existing structural evidence.
Review M4 before publication; any substantive candidate edit returns to affected checks and fresh candidate-bound acceptance.


### Replacement candidate and one repaired M4 attempt

Keep local `v0.54.0` at `e5f68b2` immutable and unpublished as the failed candidate.
Its already installed version must not acquire different bytes. After the named
M2 repair and applicable approvals, recheck remote tags and freeze the next unused
MINOR, currently `v0.55.0` (remote exact-tag query returned no reference during
this amendment). Build a fresh artifact and independently bind every shipped
Python/resource file to its new immutable commit. Rebuild both clone environments
through supported package installation, preserving dependency versions and all
captured rollback/control state. Refresh actual consumer artifact/manifest/native
digest bindings and genuine review references; do not relabel v54 evidence as55.
Before paid execution, BOTH actual `full_runtime_identity` paths, actor preflight,
cron inventory, retained-input publication and installed integrity must pass.

The lead explicitly permits exactly ONE fresh repaired FULL attempt for this
verified schema/publication cause, inside the original USD16 aggregate ceiling.
Spent native cost is USD1.3509014. Cap each of the next three native jobs at USD4;
the resulting maximum aggregate is USD13.3509014. Keep existing absolute deadlines,
strict provider/signature/native oracle, SEND/DRAFT modes and dependency order.
Use fresh exact originals/nonces; preserve old originals, failed evidence and any
uncertain effects. Independent verification confirms the old crontab is restored,
both enrollments absent and all recorded owned process identities gone. Do not
replay an uncertain old fixture or retry another failure automatically. Any new
paid attempt beyond this one requires a new named cause and explicit bounded lead
decision without exceeding USD16; this amendment grants none.

Only fresh successful signed two-clone evidence for55 can close M4 and permit
publication under the existing authorization. No engine migration, new business
feature, oracle relaxation, technical SMTP or automatic diagnostic agent is added.

## M5 — close documentation and publish the new immutable release
Lead owns reconciliation,doc-end,version claims and publication; fresh reviewers own semantic documentation and separate final review.
Reconcile durable docs,unchanged contracts,missing coverage and active-context shape; archive historical narrative verbatim. Explain release-only adoption,integrity verification and insufficient-log handling. Preserve explicit unresolved historical acceptance limits.
Run doc-end mechanical completion check and explicit doc-critic; repair STALE and retain UNVERIFIABLE. Final review must inspect actual final-user evidence and refuse missing required gates.
Recheck remote tags; v0.53.0=4f4f027 remains untouched. Select next unused MINOR,currently v0.55.0. Commit all approved shipping source before release steps; the already frozen release metadata records why/what/migration and FULL BOTH-clone tier.
The final local release tag already exists before M4. Follow release-procedure.md: run bash tests/run.sh at that exact tag, retain M4 FULL proof, then make the post-tag untagged-context and immutable-anchor commit. Complete the kernel version sweep. Prepublication review does not advance the final completion baseline; adoption evidence and a separate post-adoption final review remain required.
Publish main and new tag under the user's existing authorization. Never move an already published tag.
Verification: release-consistency check at tag and post-tag state; frozen tested package content including metadata equals the tagged artifact; remote new tag/commit and package version match; full version-sweep inventory classifies every hit.
Review publication evidence before final clone pin completion.

## M6 — finalize supported clone adoption and independent delivery
Each clone adoption executor owns its clone; lead owns joint completion and operational-pin sign-off.
Install the published immutable tag through cs update --pin and uv package installation as applicable; refresh templates through the supported update flow. Preserve authored company files/workflows and inspect security-critical local backups.
Regenerate each requirements.lock from its validated environment,then install that lock alone into a fresh uv environment. Align requirements,template-manifest,architecture and active-context live version claims; sweep every clone version occurrence.
Run cs --version,cs whoami and the new release-bound integrity route from each actual clone interpreter. Verify both installed package/source/resource inventories equal the immutable release and have no unexplained extra files or PYTHONPATH/source shadowing.
Confirm all three skill surfaces resolve intended canonical bytes,pause/business permissions remain unchanged,technical mail stays disabled,and existing logging/inbox collection still works through installed code.
Verification: fresh lock-only environments reproduce the exact Git revision; both live clones report the same release and pass actual-byte integrity; relevant FULL acceptance remains bound to identical runtime content; independent final verifier reviews real receipts.
Only after both clones pass,update the kernel operational-pin marker,reconcile post-adoption documentation, run fresh doc-end/critic plus a separate final reviewer over source, both installed user paths and all adoption receipts, then completion check/finalize advances the final baseline. Deliver the immutable tag/commit plus retained evidence and explicit remaining limits.

## Risk,rollback and limits
Rollback restores complete captured environments or installs a separately released known-good package with a truthful pin. It never hand-patches installed files,reverts mailbox/business data,deletes logs or retries uncertain work.
A public prior tag alone may lack installed operational repairs; validate rollback completeness before using it. Preserve logs,problems,findings,failed runs and source preimages.
This plan establishes ordered ownership and acceptance gates. It does not establish semantic approval of all recovered files,green current suite,installed equivalence,ACCOUNTING incident repair,FULL live success,paid-budget availability or readiness to publish.
Kernel-only acceptance clarification: Desktop installer publication is outside this assignment. Genuine strict `development_hosted` FULL may establish the exact final kernel behavior against existing reviewed hosted engines, provided its original signed oracle checks, exact kernel import/payload/native receipt binding and all two-clone provider outcomes pass. This does not claim Desktop installer equivalence and does not require engine migration. Restore authentic hosted provenance and add a narrowly reviewed truthful per-clone installed-package binding if required; preserve every strict check and acceptance scope. The existing runner injects a common source PYTHONPATH and therefore cannot certify the required installed package unchanged. Before M4 execution, a bounded separately reviewed consumer adaptation must remove source injection, bind each real clone interpreter/import root to its clean-installed identical immutable release artifact and verify native receipt provenance against those installed packages. This adaptation must retain all existing business/provider/signature/oracle/deadline checks and be tested through both actual installed paths. A source-tree FULL run alone is insufficient. The Desktop `--release` validator is not a kernel publication gate. Independent review must validate the complete original signature and kernel-bound proof rather than mislabel it as Desktop exact-candidate acceptance.

Current checked evidence: remote latest tag0.53.0,origin/main identity,300-path inventory,retained failing baseline; python3 tests/test_release_consistency.py exits0 and bash -n tests/run.sh exits0. Full fresh implementation/runtime checks remain milestone work.

## Execution evidence and pending delivery

M1 recovery is APPROVED after preserving all516 original snapshot entries and mapping all21 installed deltas; rejected instruction-authority guidance was repaired. M2 source repairs and the authentic six-build golden comparison are APPROVED; the root-owned full harness completed exit0. M3 immutable Git-object/actual-wheel verification and private native producer identity are APPROVED after malformed metadata handling was repaired; real installed CLI adversarial cases and producer checks pass. Two final fixture corrections pass in a fresh Python3.12 environment. Final pre-tag whole-harness verification is recorded by the actual root-owned command and retained log.

ACCOUNTING causal source diagnostics and a fresh eight-case blind comparison are APPROVED. Parser behavior, guards and held3 remain unchanged. No file overlays were installed in this assignment. The old logging plan's M10 overlay-adoption route is superseded by this canonical package release.

The installed-only FULL consumer is independently APPROVED for its new target mode, including actual Git-tag origins and excluded-profile source preservation. Thirteen new focused checks pass; fourteen legacy tests remain unverifiable against missing historical external records and are not called green. Fresh six-role baseline/delta/deployment bindings and the excluded source-only record are APPROVED; actual kernel artifact, policy integration, FULL outcomes, publication and final adoption remain required. No engine or bank operation is introduced.

Private evidence root: `/tmp/mrcall-ai-kit/20261025-release-alignment/`. Actual reports and immutable manifests there own approvals; progress notes do not replace them. Final baseline advancement remains after post-adoption doc-end and separate final review.

Current immutable candidate: local tag `v0.54.0` at `e5f68b2cbf061cfcec50e9ac386439c6b3216a68`; wheel SHA256 `6ebbeb16bc42782cb5698c1f12caa2d18c20fdce365e8d1ff2c0c668b28d0154`. The root-owned at-tag harness completed exit0. Post-tag commit1669c97 records the immutable anchor and restores untagged development state; release-consistency passes there.

Both actual clone environments were replaced through UV clean builds, preserving exact non-kernel dependency versions and retaining old environments outside clone repositories. All158 Python/resource files equal immutable tag objects, with zero extras. Both actual `cs whoami` calls succeed as their respective owner. Pins and template-manifest init_data are54; final public VCS installation, public lock-only proof and publication remain pending. Prior custom permissions and company workflows are preserved during template refresh.

The first real installed-consumer policy check found two preflight defects missed by fixture coverage: Path-component versus relative-string ordering in payload digest, and UV's exact reviewed wheel URL with empty archive metadata. The bounded R4 consumer correction unifies string ordering and admits only the exact reviewed local wheel URI/optional matching hash fragment, still requiring independent wheel hash and complete actual payload equality. Fifteen focused checks and actual two-clone policy validation pass; fresh preflight review and genuine FULL remain required. These are consumer-enrollment repairs, not claims of successful business acceptance.

## Current M4 outcome and publication blocker

The genuine root-owned run `full-installed-v54-r3` failed. Both synthetic originals
were independently received and narrowly enrolled. MrCall ended naturally with
supervisor exit1 and failed health; its native model returned success but generated
no response or draft. Discovery exited3 with incomplete assignment input and no
required discovery/inventory artifacts; full read inspection could not complete.
Café and signup jobs did not start. The native cost was USD1.3509014, below its
USD4 tick cap; no paid retry is running. Model success did not override the failed
native/business gate. The exact failed packet and raw stream are retained.

The scheduling-window restoration record is true; independent cleanup verification
owns remaining process/enrollment assertions. Source/installed integrity and local
lock-only proofs still pass, but they do not satisfy M4. Publication, public VCS
installation and public-reference lock-only verification remain unmet. The lead
has no authority to call FULL passed or silently waive AGENTS' before-publication
requirement. The operator's outstanding deferral question has not been answered.

Three remaining cloned-document authority contradictions were reconciled after
the terminal run using the already reviewed canonical v54 wording: MrCall's
AGENTS and architecture now distinguish authenticated legacy/managed authority;
Café's bootstrap no longer claims unavailable published reads can use offline
local files. No package, company rule, executable, permission or mode changed.
Fresh semantic review and final review must evaluate these post-run prose changes;
no signed final-composition or successful FULL claim is made.


Current continuation decision: the verified material-schema/publication failure
reopens the affected source gate; no publication waiver is assumed. The named
repair, fresh review and unique replacement candidate precede the one bounded
retry. The three post-terminal clone authority-prose corrections require fresh
semantic and final review against unchanged effective guards. This amendment
establishes scope/order/budget only. It does not establish repaired source,
publication success, installed55 equality, blind diagnostic success or FULL pass.

Maintenance coordination: the lead owns temporary `CS_PAUSE` markers on both
clones, captured in the private evidence root's `v55-maintenance-controls.json`.
They block new ticks during supported replacement, not running or engine work.
Remove only marker files whose bytes match that receipt, restoring the original
unpaused state before FULL or any handoff/yield. The unrelated Café tick finished
naturally; no normal job was killed or replayed for package adoption.

The bounded repair is source-APPROVED after precise schema/diagnostic tests and
four real retained-input CLI controls. Optional automatic publication recovery was
removed entirely: source errors stay available for manual diagnosis. A fresh blind
read of the final logs distinguishes the two schema causes and preserves unknowns.
The root-owned whole harness R3 completed exit0/all gates green; the packaged
bootstrap clarification also passes42templates x3configs and semantic critic.
The release metadata freezes unique55 next; fresh at-tag verification, supported
both-clone installation and the single bounded native retry remain required.

Unique local tag55 is frozen at f446dee07651da6b9434a9b9868552d572c3fffd;
its wheel SHA256 is5a9ad2ef05ce9fbc7e3526548eb9579fc1102efbb05a22e978f54cd5dff0d81c.
Independent Git-blob/wheel and actual both-clone inventories match all158files.
Both55configuration/lock/local-rebuild/identity/integrity gates pass, preserving
permissions, company rules, SEND/DRAFT modes and shared skill discovery. The
root-owned at-tag full harness completed exit0/all gates green. Installed-only
actor, published-instruction and cron preflight passes; raw preflight approval
binds the exact new package and unchanged genuine hosted manifest.

No55FULL has started at this point. The operator has been asked explicitly
whether to defer that mandatory gate for immediate publication of this exact
verified candidate; no answer is inferred from elapsed time. Without an explicit
derogation, the one approved repaired native run remains required. Temporary
maintenance markers are still owned and must be restored before that run/yield.

## Bounded publication-anchor correction (review before mutation)

The frozen55snapshot accidentally requires unpublished failed tag54 in its
published-tag test inventory. Fresh public checkout would fail CI when that
private candidate correctly stays unpublished. Neither54 nor55 is remote.
Correct only this release bookkeeping: preserve initial55commit f446dee under
an immutable local non-release candidate reference; remove unpublished54/55
anchors from the new tag's test snapshot, create a test/docs-only correction
commit and retarget only the still-unpublished local55reference. Then add the
corrected55anchor in the normal post-tag untagged commit. Never publish54 or
force-move any remote tag.

This exception permits reuse of exact-package FULL across that source-provenance
correction only if independent review proves the complete cs Git tree, pyproject,
README/license/other wheel inputs and the actual built wheel remain byte-identical.
The actual installed environments, manifests/policies enrolled in running FULL and
hosted engines must remain untouched until that run terminates. Preserve every
initial manifest/report/signed or failed result; record both source commits and
new-tag equivalence separately. This changes no package version, behavior, budget,
authority, oracle or required FULL outcome and authorizes no extra paid attempt.

Before publication, separately review actual new-tag equivalence and a fresh
checkout containing only public release refs plus corrected55. Run the complete
source suite at the corrected local tag while native FULL continues against the
identical immutable wheel. Final public-origin adoption must verify actual bytes
against the corrected public Git commit. Missing equality or evidence blocks
publication and invalidates this exception; do not silently relabel old proof.

## Current result and remaining authority

Corrected local55 is8ce4039dbef31218f5fd2a2d3d2b82c9e1b08d6e. Independent
review confirms identical158files/shipping inputs/exact5a9wheel; a fresh public-ref
checkout without failed54passes release consistency. The complete corrected-tag
suite completed exit0/all gates green. Original f446 enrollment and evidence stay
unchanged under the preserved local candidate ref. No public ref has been pushed.

The single repaired native55attempt FAILED after MrCall's natural terminal:
all4inventory artifacts exist and installed view.load verifies their content and
source commitments, but the agent inspected only page1of36. The ordinary ERROR
reports discovery_inspection_incomplete in discovery despite process_exit0. Native
costUSD1.3365518 remained below USD4; the model anticipated future overspend,
not an actual hard quota refusal. Affordability of complete inspection is unproved.
No generation/send or other business-mutation commands appear. Café/signup did
not run, so the required joint FULL is not established. Total native test cost
isUSD2.6874532. The approved repaired attempt is consumed; no new paid retry or
business/budget/coverage-policy change is undertaken in this release task.

Independent checks prove exact crontab restoration, absent protected enrollments
and no remaining owned PID/start identities. Maintenance pauses were restored to
their original absent state before the run; there are no outstanding owned control
changes. Both current locks now resolve corrected8ce, actual offline integrity and
fresh local lock-only rebuilds match158files on each clone; public Git adoption
and public-reference rebuilding remain pending. Current docs retain the failed54
and55evidence instead of rewriting it as successful acceptance.

The indispensable publication gate remains: AGENTS requires FULL on both clones
before tag shipping, or the operator must explicitly authorize an exception. The
current55waiver question is unanswered. Required delivery still includes that
outcome/authority, publication of main plus55only, public VCS adoption/rebuilds,
operational-pin signoff, final doc-end/independent review and baseline advancement.
No completion, final approval, successful FULL or public provenance is claimed.


## Reopened M2/M4 — complete inspection delivery, unique56, no waiver

This continuation supersedes the preceding unanswered-waiver and no-further-retry
statements. The operator rejected deferral and requires the genuine FULL gate.
Keep failed54 and failed55 local, immutable and unpublished. Installed55 must not
acquire different package bytes. The next behavior-changing candidate is unique56,
subject to a fresh remote-tag check. Preserve all failed receipts and original
source workspace bytes; only the isolated release worktree receives source work.

### Named cause and smallest decided repair

Actual retained run `run-dxbrr4n1` has a290,253-byte semantic view and6,585-byte
envelope, totaling296,694 Unicode characters. Its complete view needs36 literal
pages. Actual `operator_context_delivery.parts` rejects it:16slots x7,000characters
cannot hold the current snapshot. The model then inspected only the first literal
page and abandoned inspection based on a forecast, although its actual cost was
USD1.3365518 below the enforced USD4cap. This establishes delivery overflow and
premature abandonment; it does not establish that full inspection costs overUSD4.
The six-field schema repair worked: all four artifacts exist and verify.

Canonical executor owns `cs/operator_context_delivery.py`, the corresponding
operator/triage skill templates, and focused delivery/coverage regressions.
Extend the existing bounded delivery capacity from16to48slots without changing
7,000-character chunks, per-native-part limits, bindings, owner/session/ancestry,
source hashes, native-result authenticity, exact EOF coverage or effects ordering.
Do not add a delivery mechanism or weaken the auditor. Align triage with the
operator's existing complete-current automatic-context route. Explicitly require
continuing complete current inspection rather than declaring budget exhaustion
from a forecast; actual launcher budget/quota/deadline failures remain terminal
and incomplete. Production and per-job monetary limits stay unchanged.

The offline process-only48slot experiment produces43parts, maximum7,853UTF-16
units per part below the10,000 limit, with exact envelope+view reconstruction.
Source and artifact bytes were untouched. This is shape proof, not genuine native
hook delivery or FULL success. The executor must verify the actual installed
hook path emits and the native transcript retains all43parts before effects;
configured hooks alone establish no inspection. If native capacity rejects this,
stop the paid route and retain the exact actual limit, without inventing coverage.

Do not strip material to meet a target size. Typed definitions account for only
24,240bytes; tasks47,161,assignment coverage43,987,RAWREF index33,723,human work
30,635,drafts20,797,and engine drafts17,524dominate instead. Bodies already are
explicit UNINSPECTED RAWREF. No additional field has been justified for exclusion.
The smallest repair preserves the entire290,253-byte view byte-for-byte rather
than redesigning its semantic representation. Fresh selected-root assignment,
body,dossier,history,dedup reads and all engine guards remain mandatory.

### Free acceptance before a paid attempt

1. Fresh plan reviewer approves this cause, bounded change and unchanged authority.
2. Regression with the exact retained view/envelope proves old capacity refusal,
   new43part exact reconstruction, all original rows/roots/holds/reasons and source
   commitments unchanged. Check largest UTF-16 part bound, non-ASCII boundaries,
   capacity overflow fallback, altered/missing/duplicate/foreign/late part rejection,
   and effects before complete delivery. Exact bytes, not a passing model answer,
   are the oracle. No private values appear in reports or checked-in fixtures.
3. Run the real retained-input publication CLI, then the installed read-only hook
   path with authentic current session/process binding. Inspect complete outputs
   and genuine native evidence. Existing regression/native receipt/causal suites
   and full `bash tests/run.sh` remain required. A fresh blind reader must identify
   incomplete inspection and its delivery/capacity investigation route from logs;
   preserve unknown affordability instead of claiming a quota failure.
4. Fresh affected integration review approves source, rendered BOTH-clone skills,
   measured delivery shape and unchanged complete-inspection audit. Add no company
   literals or business functionality. Update present-system durable docs through
   doc-end; historical failures remain historical evidence.

### Freeze56 and one bounded genuine final attempt

Review and freeze unique56 after checking remote refs. Reconcile all active
version claims, at-tag metadata and public-tag test anchors: failed54/55 are not
public release dependencies and must not be pushed. Preserve original55 tag and
runtime-tested reference. Build56from its immutable Git revision, independently
prove all shipping inputs/wheel bytes, and use supported clean installation on
BOTH clones with exact non-kernel dependencies, effective permissions, company
rules,SEND/DRAFT modes and rollback/control preimages preserved. Run actual
identity, installed integrity, local lock-only, actor and cron preflight on BOTH.
No direct site-packages edit, source overlay or same-version replacement.

The lead owns the explicit budget decision for exactly ONE further genuine FULL
attempt after these free gates and fresh review. Named cause: automatic delivery
capacity overflow followed by speculative budget abandonment. Native aggregate
spent isUSD2.6874532. Keep each of at most three existing native jobs cappedUSD4;
one complete attempt costs at mostUSD12, bounding aggregateUSD14.6874532 below
originalUSD16. Do not raise production budgets, loop unattended or retry another
failure automatically. Use fresh fixture identities and preserve uncertain effects.
Restore only owned controls and independently verify cleanup before yielding.

Only genuine strict FULL success for BOTH exact56installations closes M4. Then
execute existing M5/M6 authorization: source-at-tag suite, release metadata sweep,
post-tag immutable anchor, semantic documentation and separate final reviews,
publish main plus56only, adopt the public immutable Git tag on BOTH clones,
public lock-only rebuilds and actual-byte integrity, operational-pin signoff,
post-adoption doc-end/critic/final review and completion baseline advancement.

This amendment establishes a measured capacity repair and bounded delivery order.
It does not establish native delivery affordability, source approval, genuine43part
native inspection, FULL success, public provenance or completion. Evidence:
`/tmp/mrcall-ai-kit/20261025-release-alignment/inspection-size-analysis.json` and
`inspection-plan-report.md` under that same private evidence root.


### Current56 execution receipt

The bounded capacity implementation and fresh source review pass. The exact
retained production snapshot reconstructs43parts; actual installed hook commands
pass all48slots and negative controls on BOTH normal56interpreters. The finite
49/48 capacity refusal reaches ordinary CLI, collection and problem inbox without
payload disclosure. The source review's constructed blind case identifies the
capacity cause and preserves unknown affordability.

The first full source suite retained one SQLite contention error in an unchanged
subscriber test; exact focused replays pass twice and the entire rerun passes.
The exact competing transaction remains unknown. No test or inbox code was
changed to bypass it. Both complete source and at-tag56 suites end all67gates green.
Unique local56 is frozen at `5d372ea`; failed54/55 remain unpublished and immutable.
The reviewed wheel/manifest and BOTH actual158-file installations match Git blobs.
Nonkernel dependencies, settings/company/Stripe content and SEND/DRAFT authority
are preserved; only neutral inventory guidance changes in the rendered skills.
Both local-reference lock-only rebuilds and actor/cron preflight pass.

The operator explicitly authorized stopping the still-running Café tick after
MrCall's update. Its six exact PID/start identities are quiescent; prior uncertain
effects are not replayed. Owned upgrade pauses are restored before the one new
FULL attempt. The root-owned driver and five-minute read-only progress control
are active under `v56/full-installed-v56` and `v56/five-minute-control.jsonl`.
FULL, publication, public-reference adoption/rebuilds, operational signoff and
final doc-end/review/baseline remain pending. No successful business acceptance
or public provenance is inferred from these component receipts.


## Reopened M2/M4 — observed hook progress, unique57, strict acceptance

This continuation supersedes the consumed56attempt and the preceding running56
status. Local56 stays immutable and unpublished; its failed native stream is not
successful FULL evidence. The lead stopped only the exact controlled paid job
once independent free checks established that its retained events cannot pass.
The lead independently verifies process, schedule and enrollment cleanup because
the interrupted runner's result does not attest every finally-block action.
Preserve all uncertain provider/engine effects; do not replay the old originals.

### Named cause and narrowly observed compatibility

The unfiltered1541-event retained prefix contains23system/hook_progress events,
first at index800. Normal installed56hook_indices and delivered reject it before
composition normalization or paging fallback. There is no existing progress
normalizer in the kernel or current consumer. More model work cannot remove that
existing rejection. The full source and exact56tag suites remain valid component
evidence, but missed this real native-host shape.

Actual complete evidence shows exactly ONE progress event on each of23hooks.
Each is strictly between its matching start and successful final response, with
identical session/hook identity/name/event. Its exact keys are the existing base
hook keys plus stdout,stderr,output. Progress output equals stdout and equals the
complete final stdout; stderr is empty and equals final stderr. The observed
stdout lengths are8423through9184characters. Every progress-bearing hook has its
final response; the retained prefix ends with no pending hook. The prefix has no
whole-run success claim. Private content remains outside repository artifacts.

This is substantial compatibility work at an evidence/security boundary. The
canonical executor owns cs/operator_native_hooks.py and directly affected hook,
composition and inventory-inspection regressions. Extend the EXISTING lifecycle
validator, not a parallel transport or an event-filtering workaround. Admit only
that single observed full-output progress duplicate per pending known hook.
Require exact keys/types, unchanged bounds, matching identity/binding/order,
nonempty output, output/stdout equality and exact successful final stdout/stderr
equality. Reject generic chunk/prefix variants, repeated or empty progress,
unknown shape, foreign sessions/hooks, progress before start/after final, missing
final, changed final, wrong exit/outcome and duplicate identity. A progress event
alone grants ZERO inspection, tool-result or lifecycle completion credit. Only
existing complete genuine final responses may prove the exact paired inventory.
Preserve every original event and original/projected hashes and removal indices.
Current complete material, source/session/process bindings, first-effect ordering,
selected-root reads, engine guards, budgets and business permissions stay intact.

### Bounded private retention capacity in the same repair

The actual retained prefix is1,915,431bytes before a successful terminal. The
existing shared MAX_CAPTURE_BYTES=2,000,000 limits both aggregate stdout admission
and the private diagnostic stream. Measured649realempty hook pairs cost at least
563bytes each. Four further48-hook boundaries alone cost at least108,096bytes;
a constructed continuation therefore exceeds2M at2,023,527bytes even before its
native control/result/terminal records. This establishes a finite capacity risk,
not a claim the interrupted actual run necessarily would have overflowed.

The same executor owns only the shared constant in cs/operator_recovery.py and
its direct capture/aggregate-overflow regressions: set the private bounded limit
to4,000,000bytes. Preserve the existing single cap owner, exact raw event retention,
redaction, private file/directory checks, overflow/failure flags and fail-closed
ordinary/FULL proof. This changes neither model input/tool output limits nor
business behavior or permissions. Add a labelled constructed complete native
workflow based on the actual prefix and four further safe boundaries: old2M must
refuse complete retention,4M must retain every byte. Test4M+1 overflow refusal,
failed writes, no partial coverage and agreement of aggregate and stream limits.
Never synthesize a terminal into real failed evidence. The Desktop consumer has
no discovered independent2Mconstant; verify its unchanged native/source checks.
These free checks and fresh review precede any paid execution.

### Ordered free gates, ownership and release identity

1. Fresh plan reviewer approves this exact observed shape and bounded authority.
   Before coding, preserve and hash the complete original capture; retain all
   failed56receipts. Reproduce56refusal from actual installed imports.
2. The canonical executor proves the new hook validator against the unchanged
   complete1541-event prefix, then verifies actual paired context reconstruction
   before effects. Never change original source identities or synthesize a native
   terminal. The interrupted prefix MUST remain unaccepted as whole-run FULL.
   Add nearby negative controls for each condition above and altered/missing/
   duplicate context parts and early effects. Old genuine fixtures remain valid.
   Fresh integration review precedes dependent installation or paid execution.
   Confirm the independent Desktop consumer remains byte-identical and all strict
   checks unchanged; any necessary consumer edit requires its own scoped review.
3. Run the existing focused hook/composition/inspection/causal checks and whole
   kernel suite. Reconcile affected docs through doc-end and preserve historical
   failure. Check remote refs again: the scoped exact57query returned no ref;
   freeze the next unused MINOR, currently57, with truthful new metadata. Never
   change installed56bytes, retarget published refs or make failed54/55/56public
   test dependencies. Run the complete suite at the new immutable tag and prove
   a checkout with published refs plus57only passes release consistency.
4. The lead/adoption executor installs the exact frozen57artifact on BOTH clones
   through supported package management, preserving dependencies, company rules,
   modes, permissions, technical-mail suppression and controls. Verify full Git/
   wheel/installed equality, all48actual hook commands, new progress controls,
   local lock-only rebuilds, identities and actual actor/cron preflight. Keep the
   original dirty source checkout untouched. Fresh candidate-bound package and
   rendered-surface review is mandatory before another paid attempt.

### Explicit lead resource decision and remaining mandatory delivery

The lead owns the plan's acceptance spending decision. This amendment replaces
its earlier lead-chosen USD16nominal ceiling with USD20for exactly ONE further
named-cause repaired attempt after every free gate and independent cleanup pass.
Prior reported native spend isUSD2.6874532. Interrupted56cost is unknown, never
zero; conservatively reserve its existing USD4tick allowance. At most three new
existing jobs retain USD4each: nominal aggregate admission isUSD18.6874532.
The native flag is a soft guard, so this arithmetic is not a guaranteed provider
bill. Preserve actual known costs, disclose unknowns and stop when the lead's
spending threshold is reached. No production budget/configuration increase,
engine migration, new business functionality, unattended loop, automatic retry,
or more paid56execution is authorized by this amendment. A new failure requires
another named cause, fresh free proof and explicit finite lead resource decision.

Only genuine strict BOTH-clone FULL for the exact57installations closes M4.
Then retain M5/M6: publish main plus57only under existing operator authority,
verify public Git tag/commit and both supported public-origin installations,
public lock-only rebuilds, full version sweep, joint operational-pin signoff,
doc-end/critic, separate final review and checker-governed baseline advancement.
This plan establishes scope, order and bounded lead admission; it establishes
neither a source repair, genuine native compatibility, affordability, successful
FULL, cleanup, publication nor final delivery. Evidence: private
hook-progress-shape.json and v56/hook-progress-refutation.md/.json under the
existing release-alignment evidence root.


## Required engine dependency — scoped RFC representation compatibility

The fresh brief approval in engine-encoding-brief-review.md governs this bounded
continuation. The canonical57kernel shipping code and its existing free evidence
remain frozen; this dependency adds no kernel workaround or new business feature.
The retained failed56journal proves escaped thread/reply/reference operands differ
from the trusted literal root before the correct unchanged guard. Model owner_id
is not an input. Keep failed originals, private journals and uncertain effects.

### E1 — canonical argument adapter and free guarded-storage proof

The engine executor owns only engine/zylch/tools/gmail_tools.py and the smallest
real argument/guard/storage regressions. Capture the current dirty file, modes,
complete diff and hashes outside source before any edit; never overwrite unrelated
work. Apply one deterministic pass for unambiguous HTML-escaped RFC identifiers
in thread_id,in_reply_to,references before the EXISTING owner/root/header checks.
Literal RFC and supported opaque provider IDs, order,body,subject,recipients and
other arguments stay byte-identical. Reject CR/LF,malformed,ambiguous or double
encoding; never invent missing headers/scope or replace a foreign root with the
trusted one. Authenticated construction still owns owner_id; every guard and the
actual storage route remains binding.

Run real canonical adapter-to-guard-to-storage tests with disposable state and
controlled external boundaries, no SMTP or model calls. Assert exact stored
literal identities for escaped/literal same-root inputs and preserve opaque IDs
and unrelated content. Exercise missing root/reply headers,foreign owner/root,
changed References/In-Reply-To,malformed/double encoding and CR/LF; rejected cases
must create no draft or SMTP effect. Fresh source integration review is required.
If canonical commits are needed, stage ONLY the reviewed owned hunks using an
isolated temporary Git index seeded from HEAD and an exact reviewed unified patch;
prove its tree excludes prior dirty hunks and preserve the ordinary index/WIP.
Never commit the entire pre-dirty file merely because this repair touches it.

### E2 — exact two-actor authority, rollout and rollback gate

The lead owns operational authority/risk and coordination. The pre-existing
Desktop brief includes scoped engine delivery; its exact applicability to this
repair, TWO affected service changes and any required restart must be established
by a fresh rollout reviewer AFTER E1 provides a concrete reviewable free patch.
Café's actor can serve LIVE voice or other active work: require current activity
and drain/quiescence proof plus exact restart authority. Scoped source repair is
not blanket authority to interrupt that traffic. If authority or safe inactivity
cannot be established, bring only that indispensable decision to the CTO after
the tested,reviewed patch and concrete rollback are ready; do not restart first.
Support actor PID2737112 and Café actor PID2614933 are identity baselines, not
permission to signal a reused PID. Recheck owner/profile,process start,actual
loaded imports and current source before acting. If authority is unestablished
or material risk unresolved, mark hosted deployment BLOCKED; continue feasible
free source verification and preparation, without inventing operator approval.

The adoption executor captures complete current actor source-family and activation
preimages, guarded service/interpreter/environment descriptors and rollback.
Build separate immutable preserved source families for these TWO actors only.
Apply only reviewed owned adapter hunks to each exact actual actor baseline with
context/hash guards; preserve every other deployed source byte and prior repair.
A conflict blocks that actor instead of replacing its module with unrelated
canonical WIP. Do not edit site-packages or installed clone code. Reuse the
reviewed immutable-family activation mechanism, not a new unsupported overlay.
Preserve the four peer engines,Qonto,keys,profile/data/schema,company rules,
budgets,permissions,technical-mail suppression and current runtime controls.
Coordinate in-flight affected work and record uncertainty; never replay it.

Fresh complete baseline/delta/source-binding and proposed deployment manifests
must review the exact new actor composition and rollback before activation.
Use dedicated new raw reports/artifacts, never overwrite old hosted proofs or
failed-run policy packets. Refresh the aggregate hosted manifest for TWO changed
actor rows and unchanged peer/excluded rows. Any affected restart is bounded to
its reviewed service identity; rollback restores captured activation and source
family, never stale mailbox/business data. Verify unrelated fleet identities and
controls are unchanged after actual adoption.

### E3 — installed proof, candidate-bound FULL and existing delivery

Before paid execution, exercise both actual actor engine adapter/guard/storage
paths in disposable state without SMTP and verify normal loaded normalization
read-only through the actual imports. Bind complete new payloads,source-load
ordering and process identities; compare current guard/content behavior and
preserved control/fleet state. Fresh hosted/package integration review, both57
clone integrity/identity/local-lock checks and actual actor/cron preflight are
required. Kernel work and independent free checks may proceed in parallel.

The existing ONE57FULL admission and nominal lead USD20ceiling stay unchanged;
this dependency authorizes no extra paid retry,production budget change or mail.
Only a fresh genuine strict FULL on BOTH exact57installations against this
actually loaded reviewed engine composition supplies business acceptance. Then
finish existing publication,public Git adoption/rebuilds,version sweeps,signoff,
doc-end/critic and separate final review/baseline gates. This amendment proves
scope/order only: source repair,authority/risk clearance,actual hosted adoption,
SMTP/provider outcomes,FULL and completion remain unestablished until verified.


###57 package preflight receipt and engine dependency gate

Unique57 is frozen at `e3e879974d6eab078395e51c2bf741e852821aa3`.
Source and at-tag suites each end all67gates green. Independent metadata/package
review passes all158Git/wheel/actual installed files on BOTH clones. Actual
48hook, progress and4MBcapture controls, identities and local lock-only rebuilds
pass; all protected configuration and nonkernel dependencies remain unchanged.
Published-ref-only consistency needs57only; failed54/55/56 remain unpublished.

Canonical engine adapter commit `9e82549d422c81c16c66c7dc2730b515c2f08ae3`
contains only the owned normalization/test hunks; normal HEAD/index and foreign
work remain intact. Actual Tool→guardedStorage and canonical-archive replay each
pass24tests, including literal identifiers and invalid-scope zero-write controls.
Source review is APPROVED. Exact actor-family postimages, rollout authority and
Café LIVE voice/activity safety are still separate E2gates. No engine deployment,
new paid FULL, public package provenance or final closure follows from these
source/package receipts. Existing owned repair pauses remain until coordinated
adoption/preflight or explicit scope resolution.
