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


### Superseded stop condition — service authority obtained

All57kernel source/at-tag/package/installed/local-lock and mechanical checks pass;
scoped doc-critic finds no STALE claim. Both clones run the clean immutable local57
artifact. The engine normalization fix and its canonical24-test replay are reviewed.
The two preserved-family candidates and source/configuration rollback artifacts are
also reviewed after foreign-unit inventory and file-mode protections were repaired.
No hosted file, drop-in or engine process has been changed.

The operator has been asked to authorize applying the prepared fix and controlled
restarts of support and Café engines, including possible interruption of LIVE voice
and chats. That indispensable authority is pending; no reply is inferred. Exact
owned temporary repair pauses are removed while preserving original schedules.
After authority: complete activity/drain handling, reviewed immutable two-actor
adoption and actual readback, replace hosted bindings with fresh reviewed evidence,
then run the existing ONE57FULL attempt under the recorded lead budget. Successful
FULL, public57publication and supported public-origin adoption/rebuilds on BOTH,
joint operational pin, final doc-end/review and baseline advancement remain owed.
Never reuse failed56or historicalR9 as new success, and never retry uncertain work.
Private resumption state is retained in v57/pending-service-authority.json.


### Authorized actor adoption and genuine57 attempt

The operator explicitly instructed completion after the disclosed restart question.
Both reviewed actor artifacts were applied through the owned rollout helper; the
support and Café services restarted with new PIDs2454319/2455705. Complete437/457
file inventories, canonical single-module deltas, modes/ownership, source-load
ordering and retained unit controls pass independent row review. Four peers and
excluded Qonto retain their exact source/runtime bindings. No new permission,
model, budget, voice configuration or key was introduced.

The newly enrolled hosted manifest has canonical digest
`8e221f0c01ea73ade5b05884b18df95c788962bd4b731481b5afd4317997abd1`.
Separate integration review binds it to the unchanged57artifact and R6consumer;
policy validation and actual actor/cron preflight pass. The fresh root-owned57FULL
is active under v57/full-installed-v57, with five-minute read-only controls in
v57/five-minute-control.jsonl. No successful terminal, business acceptance,
publication or baseline advancement is claimed while that run remains incomplete.


### Genuine57 terminal and source-evidence blocker

The immutable v57/full-installed-v57 case failed. Native run-ewmxfc45 ended
naturally with clean terminal and USD2.7948136 cost. Accepted complete automatic
context and intact2,077,919-byte capture establish the protocol repairs. The
actual support reply reached the independent Café mailbox exactly once without
response errors. The supervisor still rejects assignment_read_incomplete: two
unknown projections carry SOURCE_UNAVAILABLE and SENT_REPLY_NOT_SYNCED;24other
human holds are legitimate. Café/signup phases did not run. Independent cleanup
confirms original schedules restored and controlled jobs quiescent. This is no
FULL acceptance and no publication authority waiver.

The existing historical source row exists; retained logs discarded its actual
exception origin. Sent correspondence can mean zero or multiple synchronized
rows, not necessarily a missing row. Existing owner-wide sync is not an exact
historical backfill API. Fresh isolated DNS/authentication probe failures are
separate observations until connected to the actual historical failure. Preserve
failed case, source/authority guards and uncertain effects. No paid retry follows
without a named cause, freely demonstrated repair and a fresh finite resource
decision/review. Actual proof references: v57/failed57-independent-reply.json,
failed57-cleanup.json, assignment-gate-safe-proof.json, sent-failure-safe-proof.json
and source-exception-probe-output.json under the retained release evidence root.


### Bounded native source-evidence acquisition amendment (pending review)

Dependency facts are retained in source-validation-safe-proof.json and
sent-peer-namespace-proof.json. Existing peer sync.run silently lacks the newer
email-only scope branch; do not invoke it under a false email-only claim. Its
actual native authentication succeeds inside its real mount namespace, so no
authentication bypass or fabricated session is necessary. Ordinary incremental
sync skips known Message-IDs and cannot refresh the stale support References.

After fresh brief/plan approval and model-free storage-path proof, acquire ONLY
support SentUID4934 and peer SentUID11381 using each actual service's native
IMAPClient.fetch_messages_by_uid and EmailArchiveManager._store_messages with
bound owner/mailbox and unmodified live source modules. Before write, verify
UIDVALIDITY5, selected folder/nondraft and exact source RFC hashes from the retained
probes; ensure unique existing support row and absent peer row. Private0600
preimages retain selected records. Invoke no models, SMTP, assignment mutation,
globalcursor rewrites, source deployment or restart. Reject concurrent source/row
changes or any selected storage path that cannot meet these constraints.
Before any write, compare EVERY native converted field with the existing support
row and refuse unrelated body, labels, dates or business-field differences; only
the independently evidenced source References correction is allowed. Do not use
post-write comparisons as permission to overwrite unrelated data. Preflight local
fastembed CPU and existing cached model assets; refuse downloads and all remote
embedding/model/provider dispatch before writes. Missing cache is a stop condition.

Compare per-field postimages: preserve support row ID, created_at, owner/mailbox,
processing/business marks and authored content; changed source headers must agree
with independently fetched provider data. The absent peer Sent row is a genuine
new acquisition and may enter ordinary downstream processing. Verify its exact
scoped cardinality1 and unchanged unrelated rows/cursors. Do not restore stale
business data blindly on failure; retain failure/preimages and reassess.

Then obtain existing authenticated complete assignment projections model-free
where supported, preserving all24legitimate holds. If classification would invoke
a model, require a separate finite resource decision rather than fake a result.
Repair success alone does not pass prior57case. A fresh BOTH-clone FULL needs an
explicit finite reviewed budget decision and original fixtures; prior failed
evidence remains immutable. All publication/adoption/doc-end gates stay open.


### References-only native storage refinement

Readonly actual-provider conversion refuses the support full-message UPSERT: it
would change thread_id,date,date_timestamp,snippet,body_html as well as References.
Do not execute that conversion. For the existing support row, use the existing
Storage.store_emails_batch entry with an exact existing-row-shaped input, replacing
ONLY References with the independently verified native provider References.
Preserve native datetime/string/JSON semantics and map id to its existing gmail_id
as required by that entry. The actual native record-construction AST preflight
proves References is its only changed nonmetadata field. All omitted pin/read/
archive/delete timestamps are currentlyNULL and read_events exactly'[]'; require
these exact predicates again before writing, since this native entry would
otherwise reset them. Preserve identity,created_at,processing marks,body,labels,
thread_id,dates,attachments and all unrelated rows/cursors. Allowed derived
metadata differences are updated_at and the existingNULLembedding becoming a
localCPU-derived embedding. No remote model/download is allowed.

The absent peer Sent record may use the original native fresh-provider archive
conversion/storage path with exact scope/header checks. Retain both private
preimages and full safe field-delta evidence; fail prewrite if actual predicates
change. This refinement changes no installed code, schema, assignment guard or
business classification and does not grant replay/send authority. Require a
fresh plan review of this exact refinement and execution-script review before
application. Verify no unrelated field/source/business mutation afterward.


### Atomic native-model alternative for the existing header

The native batch lacks an expected-row predicate and opens its own session.
Prefer a narrowly scoped conditional update through the existing native Email
SQLAlchemy model/session for ONLY the support References field: match exact
owner,mailbox,rowID,RFCID and original References, assign the provider-verified
References, require rowcount1 and verify postimage. Other concurrently changed
columns remain untouched; do not serialize their old values back into the row.
This uses the native storage model, not raw SQL/data fabrication or a modified
installed module. No content,thread,date,labels,processing,identity or cursor
field may be assigned. Native updated_at maintenance is the only permitted
derived side effect; no embedding is needed for this header-only operation.

This alternative preserves the approved provider/source/UIDVALIDITY/nondraft
checks, private preimage and actual namespace/OS-owner execution. A changed
References value or nonunique target refuses the update. The peer record still
uses the independently reviewed fresh-provider archive conversion and native
store path, with local cached CPU embedding and zero remote-model/download
dispatch. Require fresh review and executable-script review before application.


### Concurrent-safe peer insertion refinement

Do not invoke the peer native archive UPSERT: it lacks transaction-held absence
checks and could overwrite a concurrently synchronized row. Use the explicit
brief exception: fresh native provider conversion, the exact native batch
record-construction expression and warmed cached local embedding produce a
native Email model; Session.add/flush/commit performs INSERT ONLY. Verify the
existing owner/mailbox/RFC uniqueness constraint. Any concurrent duplicate must
raise IntegrityError and roll back without touching the existing row. Never
implement ON CONFLICT UPDATE. Preserve exact provider/source guards and scoped
cardinality0 before insertion,1 after. No engine freeze/restart is necessary.
For BOTH actions, retain full selected postimages immediately after mutation
before any assertion, including verification failures; do not blindly restore
stale data. Execution remains gated on fresh brief/plan/script approval.


### Finite post-source-repair acceptance decision (pending review)

After independently verified two-record maintenance and BOTH native authenticated
affected-root reads with complete technical reply evidence and only legitimate
NEEDS_HUMAN_VERIFICATION holds (not unknown source failures), allow ONE fresh
genuine BOTH-clone FULL
with new original fixtures and the unchanged57artifact, R6consumer and hosted
source bindings. No paid retry follows a further failure. Source repair and the
affected-root projection path use zero model calls. Capture actual cleanup and
signed final proof; prior failed57case remains failed.

The lead's nominal cumulative reserve becomes USD22, replacing its previous20
planning reserve: known54/55cost2.6874532 plus conservative interrupted56reserve4
plus knownfailed57cost2.7948136 equals9.4822668; one3job trial reserves12 at the
unchanged4/job launcher settings, total21.4822668. This is a finite planning
reserve, not a claim that provider billing has a new hardcap. Preserve actual
models, daily limits, perjob controls and5400-second overall timeout. Reassess
any unexpected spending before another paid action; never start another FULL
on this decision. Root cause/fielddelta/nativeprojection proof and fresh resource
review are prerequisites, not assumed successful outcomes.


### Applied source maintenance receipt

The exact reviewed script45d97a11ced7acda566860af7041f2a785120fafea158857cc20231eddc04144
and coordinated driver26bed87859c20f248afcb84093e66309ecfa151600085137eea6d12978cc5c3c
applied successfully. Support selected postimage differs ONLY in References;
peer has exactly1new native provider-backed row. Complete other-table/row digests
remain unchanged; preimages/postimages are private0600. All three original cron
lines are restored exactly. No code,identity,processing,assignment,model/budget
setting or source guard changed. Independent native authenticated affected-root
projections are now under verification; no FULL/publication follows until complete.
Proof: v57/source-repair-coordinated-result.json and source-repair-script-review-r2.md.


The affected-root projection receipt now passes native authentication on BOTH
actors with zero model calls. All reply_evidence entries are complete; states
are needs-assignment/NEEDS_HUMAN_VERIFICATION, which intentionally retain
projection.complete=false until a human business decision. This is the existing
legitimate-hold contract, not a remaining technical read fault and not permission
to assign/close work for acceptance. The unchanged kernel discovery/health path
must accept the actual result through operator_health.assess before a new FULL.
Legitimate human holds retain assignment_incomplete=true and CLIexit3; neither
flag rewriting nor forcing exit0 is permitted. Independent repair
verification passes actual provider/currentDB comparisons and exact cron restore
in v57/source-repair-independent-proof.json.


The additional pre-FULL actual discovery is a single ordinary readonly
`.venv/bin/python -m cs unanswered --days 14 --json --all-buckets` invocation.
Its emails.needs_reply path can use one batch model call, so do not call it
model-free. Reserve up to0.50nominal for that ONE call inside the22reserve:
9.4822668+0.50+12=21.9822668. Preserve engine model/daily controls; this is not
a new provider hardcap. No repeated discovery or FULL on failure. Evaluate its
actual complete retained inventory with the unchanged health predicate and
preserve legitimate human holds. Capture any observed charge or explicit unknown;
unexpected spending triggers reassessment before the FULL. This adds no write,
assignment, send, source modification or acceptance exception.


### Eliminate the redundant standalone health precondition

The ONE added standalone discovery reached the diagnostic wrapper's360-second
timeout during inbound assignment projection; its ordinary inbound/sent discovery,
classification and settlement stages finished. It produced no accepted captured
discovery. The wrapper/helper and CLI are quiescent; this failed diagnostic is
preserved and never reported as health acceptance. Actual charge remains unknown
inside the reserved0.50. Do not repeat this standalone scan.

Supersede ONLY the newly added requirement for a second complete discovery before
starting FULL. The unchanged genuine FULL already executes that same actual
publication/ancestry/digest/health assessment under its normal runtime controls.
It remains mandatory for acceptance and publication. This removes duplicate
preflight work, not a shipping criterion: no FULL or health success is inferred.
The independently verified two-record correction and BOTH genuine authenticated
affected-root reads with complete technical reply evidence are the actual free
repair preconditions. Current installed/source/hosted/instruction preflight passes.

Under fresh plan review, proceed directly to the previously bounded ONE fresh
BOTH-clone FULL with original fixtures, unchanged57/R6composition, USD22nominal
reserve including the consumed0.50standalone allowance, and5400-second limit.
No further standalone discovery or paid FULL retry follows any new failure.
Preserve original failed57and standalone evidence; no flags, holds, validator,
coverage, costs or outcomes may be rewritten to obtain a pass.


### Fresh source-repaired FULL started

Fresh root-owned case f489c1c28eda7805028d16707db0e753 is active under
v57/full-installed-v57-source-repaired-r1. The unchanged driver/consumer uses
actual57installed kernels and the same reviewed hosted source/policy composition.
A separate observer records five-minute status under
v57/five-minute-control-source-repaired.jsonl. No terminal/provider success,
health acceptance, publication or baseline advancement is inferred while active.
The old failed57and standalone-timeout cases remain separately preserved.


## Bounded ACTOR cleanup continuation — pending fresh plan review

The approved brief dependency is bound by the raw review
v57/cleanup-brief-review.md (brief SHA-256
651fb5d8dc458f082fca70e2bf250c587b3da749ac427bebfbd1b44dcafe8d69).
This is substantial engine behavior work. Existing milestones and release gates
remain; this section adds their prerequisite dependency order. No implementation,
restart or paid retry starts from this unreviewed plan amendment. The earlier
USD22 decision was for one attempt and supplies no further retry allowance.
Historical R8 cleanup evidence proves its safety regression and repair, not the
cause of either interrupted 57 timeline. Current failure/effect uncertainty stays
explicit; no historical case is resealed.

### C0 — reconcile the interrupted case before any restart

Owner: lead operational executor. Capture the complete retained case
f489c1c28eda7805028d16707db0e753, native receipts and actual process/start/service
identities under a new private cleanup-continuation evidence directory. The
run-2913_1_k native trace contains draft-reply and draft-send invocations; these
are effect attempts, not proof of success or permission to resend. Establish
actual terminal receipt status and whether associated backend work remains
active; CLI disappearance or exit alone does not prove completion.

Use existing authenticated native read paths, without models or mutation, to
read the exact owner's matching engine draft records and actual provider Drafts
and Sent records by the preserved fresh fixture RFC identities. Retain exact
owner/mailbox, threading, recipient and provider UID/UIDVALIDITY bindings and
claim/deduplication state. Independently read the protected receiver for the
matching reply. Compare trace, engine state, provider postimages and receiver;
record confirmed, absent or unknown effects separately. Do not infer no delivery
from a missing terminal result or retry an uncertain send. Preserve customer
mail, fixture effects and audit; no blanket deletion, stale database restore or
reclassification. Quiesce/drain only the already authorized affected actor work
through existing controls and retain the actual completion/cancellation proof.
An unresolved active write blocks that actor's restart; source work can proceed.

Verification: independent operational review of the complete effect matrix and
backend/task quiescence evidence must agree with actual provider and receiver
readback before C2. C0 does not establish a passing FULL or historical timeout
cause. Any ambiguity remains held and is carried into subsequent acceptance.

### C1 — canonical cleanup patch and real native RED/GREEN

Owner: Desktop engine executor, limited to ACTOR evidence cleanup, the native
IMAP terminal disposal primitive and directly relevant regression tests. Resolve
canonical provenance first: commits 0a4261f8b5fd8f1c1bcafedd1b3784825962680a and
d52f68f059d4638de511f2ad3de6da21e43794dc retain Observation; the latter is the
existing prepare/m10-poststripe-20261016 worktree. MAIN b8dcfc665a4f is a distinct
family and its foreign WIP/index must remain intact. Record exact Git blobs,
current actor preimages and context differences before choosing the isolated
owned branch/index. The separately owned encoding commit is
9e82549d422c81c16c66c7dc2730b515c2f08ae3 on
release/scoped-rfc-encoding-20261025. Preserve that reviewed adapter in both
family compositions. Never import an entire ACTOR module into MAIN, commit
foreign changes or replace actual family business logic with a historical tree.

Implement only local terminal disposal, using the existing native shutdown/
discard mechanism without LOGOUT or another protocol round trip. Retain R8's
provider/projection-guard-before-socket-disposal order so final deadline checks
never touch a deliberately closed retained descriptor. Preserve ordinary
graceful-disconnect behavior. Cover Observation.close, partial setup failure and
standalone snapshot cleanup; release all owned clients after earlier failure,
reset the observation token and clear references without leaking timers/locks.
Propagate guard/provider expiry and errors with existing UNKNOWN/held behavior;
local disposal must not manufacture successful or complete evidence.

Before patching, add a focused real-native-client test using fake external IMAP
boundaries and real sockets. Use a short absolute evidence deadline (for example
0.2 seconds) and a child-process watchdog (2 seconds); a stalled/trickled LOGOUT
must make the existing code fail its completion bound. Kill/reap the owned test
child and close fixtures on RED rather than leaving blocked work. GREEN must
perform zero LOGOUT, finish inside the same bound and close the actual sockets.
Run successful observation/reply/snapshot paths plus deadline expiry, provider
failure, guard-exit failure, partial construction, multiple clients, nested
deadlines and repeated cleanup. A real closed-socket settimeout regression must
reject the old disconnect-before-guard ordering and pass the preserved R8 order.
Assert context reset, released locks/timers/references, retained valid unexpired
results, fail-closed expiry/failures and zero model, SMTP, assignment or storage
effects. Do not substitute AST-only or mocked disconnect ordering for native
client/socket behavior. Record exact commands, interpreter, RED/GREEN outputs,
timing bounds and cleanup. Repeat the focused checks on BOTH exact actor-family
postimages and the existing relevant assignment/IMAP suites. Fresh source review
must approve the owned canonical patch, numeric bound and family adaptations
before C2; a conflict blocks adoption rather than widening the patch.

### C2 — preserved two-actor artifacts and reviewed activation

Owner: existing adoption executor; depends on approved C0 effect/quiescence and
C1 source/test proof. Reuse the already reviewed immutable-family build and
activation/rollback mechanism. Apply only the reviewed cleanup hunks with
baseline/context/hash guards to each current actor family, preserving its RFC
adapter and every unrelated byte. Retain complete prior payloads/activation,
new immutable artifacts, complete baselines/deltas and ownership/mode/link
inventories. Review concrete artifact composition and rollback before activation.
No installed kernel edit, site-packages overlay, peer update or wholesale module
copy is a delivery route.

The existing disclosed restart authority covers these TWO actor engines only.
Recheck actual service/profile/start/import identities and Café activity/drain
safety immediately before each switch; do not signal a reused PID. Switch only
the reviewed actor family, restart through the existing service procedure, then
capture the new PID/start and exact loaded source imports. Independently compare
all six company-family payload/control rows and excluded Qonto against their
captured baselines; the four peers and Qonto retain their actual sources,
process identities and controls. Preserve models, budgets, modes, auth,
permissions, technical-mail suppression, deduplication and business data.
Rollback uses the retained activation/source family through the same procedure,
with new runtime/import verification, never stale business state or resend.

Produce fresh complete baseline/delta/deployment records and aggregate hosted
manifest with exactly two changed actor rows. Refresh policy/source bindings and
native receipt provenance through the existing reviewed enrollment path; do not
rewrite old failed-run packets. Independently review actual artifact loading,
peer/Qonto preservation, manifest/policy identity and free installed native reads
before any paid admission. Run BOTH installed kernel 57 integrity/identity/lock
checks and existing actor/cron preflight against that exact composition. No
passing provider outcome or FULL is inferred from activation.

### C3 — finite resource decision and existing release completion

Owner: lead, after independent C2 integration approval. Record actual known
charges plus explicit unknown reserves from all prior attempts, including the
interrupted case; retain the consumed USD22 decision as historical. Decide a
new finite nominal ceiling and ONE-attempt admission in a separately reviewed
resource entry before any model or paid FULL call. Preserve existing provider,
per-job and daily controls. No automatic retry, repeated discovery, production
budget increase or unlimited unattended run is authorized by this amendment.
If free proof or actual adoption fails, no paid trial starts.

Under that reviewed admission, execute one fresh genuine strict BOTH-clone FULL
with new protected fixtures, both actual immutable kernel 57 installations and
the freshly reviewed actor/hosted/policy bindings. Preserve all original strict
provider, receiver, ordinary native workflow, natural completion, authority,
automatic ACK, no-extra-effects, deadline and cleanup checks. Uncertain previous
effects remain deduplicated and are never resent. A failure stays failed and
ends that admission. Only actual independent PASS permits existing publication,
public Git installation/rebuild on both clones, version/pin sweeps, doc-end,
doc-critic, separate final review and completion-check/finalize gates.

This amendment establishes dependency order and accountable verification only.
It does not establish implementation, historical causation, completed effect
reconciliation, safe restart, adopted source, new spending authority, FULL,
publication or final release readiness.


### Interrupted source-repaired case and cleanup candidate receipt

Case f489c1c28eda7805028d16707db0e753 remains interrupted/incomplete, never PASS.
Its actual discovery contains1transport TimeoutError and14conservative capacity
deferrals. Lead interrupted the controlled driver after that permanent health
failure; independent scheduling/registry/process checks verify original cron
restoration, absent fixtures and no live owned jobs. A correct-identity reply was
already sent and independently received once; body acceptance is unmeasured.
Never resend it. Artifacts: source-repaired-full-discovery-failure.json,
source-repaired-full-cleanup-proof.json and source-repaired-interrupted-effects-proof.json.

An isolated native read of the timed-out root is normal/complete in37.584seconds.
This refutes a persistent source-evidence defect on that root but does not prove
the historical transport cause. Astra's source review identifies an actual
cleanup bound hole: R8 correctly exits guards before disconnect to prevent EBADF,
but the subsequent logout can wait120seconds beyond the projection deadline.
Executor queue delay and draining after client disconnect remain other hypotheses.

Owned canonical ACTOR commit c461491206242038bc0006888b32a9b72638d591, based
on existing0a4261f8, changes only the evidence cleanup module and focused tests.
MAIN source/WIP and all installed modules remain untouched. Both exact actor
candidates have matching cleanup code; native stalled-LOGOUT RED takes2.017s
and fails, while five native/socket GREEN tests pass for canonical/support/Café.
Partial-construction and actual candidate reply/projection integration are under
verification before source approval. No new actor adoption or paid FULL is
authorized by these component receipts alone. Existing22reserve admission is
consumed; C3 requires a separately reviewed finite decision after actual repair.


### C3 bounded admission after verified local-disposal repair

C1 source approval is cleanup-source-review-r2.md for canonical ACTOR
fd051dc0ada0ab89b7f314780712c4dab31d7f57. Both unchanged/candidate historical
suites pass55 tests; all three native-client suites pass6; the real stalled
LOGOUT preimage remains RED. Genuine authenticated candidate replies preserve
success, UNKNOWN and expiry outcomes. Historical timeout causation stays unknown.

Both reviewed immutable actor families are now active. The companion checks
required two narrowly reviewed controller repairs: boot-time quantization was
resolved by restarting support after stable source files; the Café guard now
strictly excludes only systemd ExecStart execution bookkeeping while retaining
command/runtime/file checks. Source maps remain exact437/457; all other families
are preserved. Fresh row approval and policy integration/activation remain
prerequisites. Original cron is temporarily held in maintenance-scheduling.json;
the normal operator was interrupted before effects (only four read commands).

The lead authorizes, subject to fresh resource review and activated exact runtime
bindings, ONE actual standalone discovery/unchanged health assessment with a
900-second wrapper deadline, followed ONLY on acceptance by ONE genuine strict
BOTH-clone FULL with fresh originals. Use the existing4/job settings and5400
overall limit; preserve all holds and all health/coverage/provider criteria.
The new wrapper must terminate its complete owned process group on timeout.
Any failed standalone or FULL grants no further retry from this admission.

Nominal cumulative acceptance reserve: earlier54/55known2.6874532, interrupted56
reserve4, first57known2.7948136, earlier standalone allowance0.50, interrupted
source-repaired57reserve4 =13.9822668. Reserve0.50for the one new discovery and12
for three unchanged4/job jobs, total26.4822668 within lead planning reserveUSD27.
This is not a provider hardcap or a change to production daily/model controls;
unknown actual interrupted/standalone charges remain explicit. Normal configured
production activity and Codex coordination have separate existing billing. No
budget escalation or paid execution follows merely from this prose: fresh
review, actual post-adoption preflight and complete technical health are required.
Restore exactly the owned cron lines before the canonical driver takes over its
own scheduling window; avoid a scheduled-tick boundary and verify final cleanup.


### Accepted actual health and admitted cleanup FULL

The sole post-cleanup actual discovery completed within its900-second wrapper
bound. Actual CLIexit3 matches authenticated capture, unchanged health.assess
accepts it, read_incomplete is absent, technical unknowns0 and legitimate human
holds26. No flags or holds were rewritten. Raw proof is
v57/cleanup-health-preflight-result.json; this is component health, not FULL.

The exact three maintenance-owned cron lines are restored and normal actor/cron
preflight passes. Resource review and concrete wrapper review are APPROVED.
Fresh root-owned case 87e3b09294474f4448acb39db30bdb31 is active under
v57/full-installed-v57-cleanup-r1 using the unchanged R6consumer and exact57
installed package/new approved actor composition. Its separate five-minute
observer records v57/five-minute-control-cleanup.jsonl. No successful terminal,
provider acceptance, signature, publication or baseline advancement is presumed.


### Interrupted cleanup FULL: strict health failure

Case87e3b09294474f4448acb39db30bdb31 is interrupted, not PASS. Its actual
ordinary discovery publishes exit3 with ten unknown/incomplete assignments:
one transport TimeoutError and nine subsequent capacity deferrals. Seventeen
other human-assignment holds remain legitimate. The exact fixture status later
succeeds; that narrow result does not clear whole-inventory discovery failure.
Evidence: v57/full-live-progress-review-r2.md and retained exact discovery
SHA256dea759cd69ba833eee053c8df73265ef4876c00e733eca99ce9a0abfa9fc5e0e.

The lead sent SIGINT only to verified owned driver2878347; it exited130. The
canonical case result remains incomplete and is never relabeled. Original cron
is restored byte-for-byte (v57/cleanup-full-scheduling-proof.json). Exact fixture,
process and effect checks are separate pending receipts. No prior or uncertain
mail may be resent. The local-disposal defect is repaired, but this failing
ordinary case proves that repair insufficient for strict shipping health;
historical timeout stage/causation remains unknown until supported by evidence.

The one-attempt admission is consumed. No additional paid acceptance, relaxed
health/coverage, public release or claimed BOTH adoption follows from it. Free
diagnosis and cleanup continue; any further candidate requires a specific actual
cause, new free proof and separately reviewed finite admission. Required FULL,
public provenance, final documentation approval and baseline advancement remain
unmet. The existing plan stays active as the accountable resumption trace.

Local interruption cleanup is independently verified in
v57/cleanup-full-cleanup-proof.json and cleanup-full-cleanup-review.md: original
cron exactly restored, both fixture registries absent, all519 tracked process
identities plus driver/watcher absent. All1178 retained native events contain14
tool calls and no draft/send attempt. This does not establish absence of detached
backend work or independent provider effects; no resend is permitted.

The bounded free diagnosis identifies one exact timed-out root. Kernel owner
concurrency1 deliberately converts later reads to nine capacity deferrals. The
backend queues projection through asyncio.to_thread before its120-second
projection deadline begins. Queue delay is a supported hypothesis; retained
logs lack correlated enqueue/start/stage timings and cannot distinguish queue
wait from actual execution latency. No historical cause is asserted. See
v57/cleanup-full-timeout-diagnosis.md. A next reviewed diagnostic change should
retain safe correlation and bounded queue/start/stage elapsed metadata at that
seam; another FULL without that evidence is not justified.

### D — classify and correct the remaining timeout without a speculative retry

This is substantial continuation of the existing release task, not a fast path.
The diagnostic/transport brief amendment has fresh framing approval in
v57/timeout-brief-review.md, binding full brief SHA256
117bd98ffa6f49eaba8bfe46c24bb1a5c95f48cea202b7a4c3621d4ceb0019f0.
Fresh plan approval precedes implementation. The prior admission remains consumed.

Source facts: frozen kernel e3e8799 passes the scheduled discovery's original
absolute deadline into assignment projections. Its standalone projection cap is
3600 seconds, but scheduled observation is510 seconds and reserves10 seconds
before rendering. Each assignment request is capped at150 seconds and its batch
at180, additionally clamped by that original deadline and cleanup reservations.
The isolated child explicitly injects the assignment request cap into
REQUEST_SECONDS; the apparent60-second minimum in _read is not a missing opt-in.
Canonical ACTOR fd051dc0 starts its evidence deadline at40 seconds inside the
executor; the exact hosted families preserve their distinct120-second budget.
Do not change either value by treating these families as byte-identical.

The verified diagnostic defect is loss of timeout origin: the isolated reader
serializes request/batch TimeoutError as the same finite timeout, then read_many
reconstructs a generic exception. Parent worker expiry and exhausted remaining
projection capacity are separate possible boundaries. Queue delay before the
backend worker starts is another hypothesis, not the historical cause. One
transport timeout then deliberately blocks that account and produces remaining
capacity deferrals; those deferrals are not separate observed provider failures.

#### D0 — free failure classification and delivered causal evidence

Owner: one kernel executor, owning cs/rpc_reads.py, its exact caller seam in
cs/task_assignment.py, directly needed causal-event validation/propagation, and
focused tests. A separate bounded engine executor is warranted only if the
classified loss is beyond the RPC boundary; its ownership is the canonical
ACTOR rpc/task_assignments.py and services/task_assignment_projection.py seams
and their focused tests. MAIN's unrelated dirty tree/index remain untouched.
No worker owns arbitrary stderr capture, company code or business policy.

Before changing behavior, add free real-transport/process controls that fail the
required causal distinction on the preimage. Exercise request timeout with ample
shared budget, shared-deadline exhaustion with a longer request allowance,
isolated-worker expiry before a result, connection failure, and a successful
response followed by bounded cleanup. Use actual EngineClient/local protocol
peers and the real isolated reader; retain actual process cleanup. Add the
real projection caller to prove one observed timeout and derived later deferrals
stay distinguishable without changing UNKNOWN or hold decisions. Existing
transport tests are prerequisites, not proof that new diagnostic fields work.

Preserve only finite metadata through child IPC, validation, ordinary structured
events, CLI and private problem inbox: failure boundary, selected bound, elapsed
time, remaining shared budget, existing request/trace correlation and hashed
thread identity where supported. Explicitly retain unavailable values. Derive
the selected bound at the actual min operation, not from exception text; do not
export raw stderr, exception messages, mail/header/body content, tokens or prompts.
For backend evidence, distinguish dispatch/enqueue/worker-start/provider/cleanup
only at real observed boundaries and use monotonic durations. A missing start
record cannot be labeled queue starvation. The diagnostic path must preserve
the first decisive failure, original result and conservative account reservation.

Verification: real producer-to-CLI-to-collector/inbox regression for each distinct
failure, healthy and legitimate-held controls, privacy/sink-failure controls,
and a fresh blind analyst receiving only ordinary log/inbox access. The analyst
must detect the malfunction and identify the correct observed boundary or
supported next inspection, while leaving unsupported upstream cause unknown.
Retain exact source hashes, actual commands/results, RED/GREEN and independently
reviewed evidence before D1. Run `PYTHONPATH=tests python3 -m unittest
test_rpc_reads.Transport` and the affected assignment/causal propagation suites;
add tests for the new distinctions rather than merely rerunning old assertions.

#### D1 — repair only the demonstrated limiting mechanism

Owner: the executor for the actual deciding component, after independent D0
review. Use the retained classified failure and free real-path reproduction to
state a concrete source patch and numeric bound in this existing plan; obtain
fresh applicable brief/plan review before that behavior patch. Queue isolation,
new caching, retries, parallelism changes, larger deadlines or budget increases
are not predetermined repairs. A diagnostic improvement alone is not a claim
that operational latency has been repaired or that FULL can now pass.

If retained history cannot identify the original boundary, one separately
reviewed bounded model-free native diagnostic read may obtain current evidence
after exact source/preflight verification. Its finite root set, wall time,
resource controls, ownership and cleanup are named before execution; it cannot
stand in for complete workload acceptance or replay an uncertain effect.
Stop that admission on a failing free check rather than repeating discovery.

The lead's current isolated read-only probe targets only the exact failed root
under the selected support service's current source/environment, verified native
authentication and SQLite read-only access, bounded to155 seconds. Its pending
receipt is v57/timeout-native-root-probe.json. Safe measured function timings
describe that isolated invocation only; its fresh executor cannot establish the
daemon's historical queue wait. This receipt does not admit a second probe or
another FULL and must remain pending until the actual process terminates.

Verification: the actual preimage fails a reproduced product requirement and the
candidate passes through the same native path with unchanged authority and full
inventory requirements. Exercise the nearby genuinely slower/failed case, expiry,
cancellation, held/UNKNOWN and successful unexpired cases. Preserve the R8
guard-before-disposal ordering and the reviewed local-disposal/RFC adaptations.
No provider send, assignment mutation, changed schedule or model is needed for
these controlled tests. Independent milestone review precedes deployment.

#### D2 — exact adoption, one finite admission and existing delivery gates

Owner: existing deployment executor and lead, dependent on an approved D1
disposition. A demonstrated behavior repair requires the D1 RED/GREEN proof.
If the historical limiting mechanism remains unobserved, admit no speculative
behavior patch: a separately reviewed finite diagnostic trial may proceed only
with new actual telemetry and accepted complete current installed health. This
is not latency-repair acceptance or a waiver of any FULL/shipping criterion.
Use the existing complete two-actor baseline/delta/deployment and rollback gates;
preserve all other family bytes, controls, four peers and excluded Qonto. A
kernel change requires a new immutable candidate/version and supported clean
installation on BOTH clones; never move frozen57 or modify its installed bytes.
An engine-only change preserves57 and binds the exact two changed actor families
through fresh reviewed rows/policy/native provenance. Neither route waives FULL.

Before any paid call, reconcile actual settled native charges where available,
retain explicit unknown reserves for interrupted jobs and standalone diagnostics,
and independently review a new finite one-attempt decision. USD27 was a lead
planning reserve, not a provider hardcap or evidence that every reservation was
charged. No new spending is authorized by this proposed plan. Preserve actual
per-job/model/daily controls; admit no paid run on a failing free candidate.

Only after actual healthy complete installed discovery, exact actor/cron
preflight and unchanged guards pass may the reviewed admission start one fresh
genuine strict BOTH-clone FULL. Its owned passive monitor checks progress every
five minutes; known terminal health failure ends the attempt and triggers exact
cleanup/effect verification. Natural jobs, provider/receiver outcomes, authority,
automatic acknowledgement, no-extra-effects and complete health remain required.
An interruption never becomes PASS and uncertain prior work is never resent.

Actual independent FULL success then permits the existing publication, normal
public-tag adoption and lock-only rebuild on BOTH clones, version/pin sweeps,
doc-end/doc-critic, separate final review and completion-check/finalize gates.
Rollback restores only captured owned source/activation, never business data.
This continuation establishes dependency order and bounded ownership only. It
does not establish a historical queue cause, implemented repair, safe deployment,
new resource admission, successful FULL, publication or completed alignment.


### D0 component proof and finite58 admission proposal

Canonical kernel29edc68 repairs the reproduced diagnostic conflation and false
causal reference, not a claimed historical transport/queue defect. Fresh source
review is APPROVED after the actual connection-failure → timeout → deferral
regression. Real CLI/collector/inbox proof and the refreshed blind analyst identify
a selected request timeout and an explicitly unattempted derived consequence.
Both actor families now preserve reviewed canonical diagnostic commit543f311e;
all437/457files and seven runtime/unit/metadata guards pass. A real normal
installed CLI request to the current daemon completes the exact failed root in
4.314seconds with legitimate NEEDS_HUMAN_VERIFICATION. Ordinary CLI trace paging
retains all five new boundary commands. Historical queue causation stays unknown.

The first full free source run overlapped the last reviewed causal-reference
repair: its installed parent and source child had different package digests,
correctly rejecting six receipt joins. Stable canonical recheck passes those
cases and a fresh whole harness is all-green. No verifier was weakened. New
immutable58 at77bef42 is frozen; at-tag checks, installation, policy activation
and whole-discovery acceptance remain separate prerequisites.

Reconcile reserves before a new paid admission: older54/55known2.6874532;
interrupted56unknownreserve4; natural first57known2.7948136; firststandalone
allowance0.50; interrupted source-repaired57unknownreserve4; postcleanup
standalone allowance0.50; latest interrupted cleanup57MrCall jobunknownreserve4.
Latest Café/signup jobs never started; their previous8nominal reserved dollars
are not asserted charged. This conservative subtotal is18.4822668, not an
invoice or proof of actual interrupted charges. Retain another1for prior
uncertain nonnative diagnostic/classifier charges rather than calling them zero.

D1 disposition for this candidate: no historical limiting mechanism or latency
repair is established, so no deadline/scheduling/provider behavior patch is
admitted. The separately reproduced diagnostic loss and incorrect causal link
are repaired and reviewed. The proposed admission is ONE diagnostic trial with
new exact telemetry and complete current health, not a claim that the old
transport defect is fixed. D2 requires independent approval of this explicit
disposition; its behavior-repair branch remains conditional on actual proof.
A failed diagnostic trial still cannot ship or renew itself.

Subject to a fresh independent finite-resource/plan review, the lead proposes
ONE bounded installed58 whole-discovery/unchanged-health attempt (allowance0.50,
900-second owned-process-group wrapper), then ONLY on actual technical health
acceptance ONE strict fresh BOTH-clone FULL with the unchanged4/native-job and
5400-second overall controls (reserve12). Cumulative conservative planning
reserve31.9822668 is within32. This is a lead one-attempt planning ceiling, not
a provider hardcap or production model/daily-budget change. Codex coordination
and unrelated normal production billing remain distinct. Unknown charges stay
unknown; do not silently reuse an already consumed admission.

Actual58 byte/identity/lock checks, exact two-actor reviewed policy, source gates
and real preflight must pass first. Diagnostic repair grants no assumption of
latency recovery. Failed discovery or known decisive FULL health failure ends
this admission; no retry follows automatically. Restore exactly owned cron lines
before canonical FULL takes its own scheduling window; verify final cleanup and
all uncertain effects without resend. Full provider/authority/ACK/no-extra-effects
and normal-job criteria remain unchanged. This proposal authorizes no paid call
before its actual approval and prerequisites.

### D1 amendment — bounded read-only SELECT recovery after failed58 health

Disposition: NOT APPROVED; superseded by the diagnostic-only amendment below.
The operator requires connection/state/cause evidence before proposing a repair.
The retained proposal is historical planning narrative, not executable authority.

Status: planning only; fresh brief framing approval and fresh plan approval are
mandatory before implementation. This extends D1, not the consumed58 admission.
The failed installed58 discovery returned exit3, assignment_read_incomplete,
unknown_states1 after730.5seconds; FULL never started. No additional paid or
provider admission is granted. Kernel58 remains immutable and unchanged.

Evidence: v58/health-unknown-engine-events.json and health-unknown-summary.json
under /tmp/mrcall-ai-kit/20261025-release-alignment. Two observed dispatch waits
were approximately1.3milliseconds. The first120-second source failure was the
_early_replies deadline guard at task_assignment_projection.py:109; the next
attempt failed at imap_client.py:807 in readonly SELECT after120seconds.
Cleanup then failed at the already-expired remaining-time guard, line750.
These facts identify an unbounded-within-the-whole-budget SELECT as a concrete
reproduction target. They do not prove a stale socket, provider outage, the
first attempt's upstream cause, or that a reconnect will repair production.

Read source finding: examine_existing has no local recovery. _deadline_check
permits a command to consume all remaining absolute time (maximum120seconds).
Outside a projection scope, _ensure_connected can reconnect after failed NOOP;
inside the installed families' projection_connection scope it instead pins one
connection and rejects replacement. Canonical543f311e has the same
examine_existing and disposal functions but not that projection scope, so a
canonical-only test cannot establish safe family adoption. Do not remove this
family guard to make a retry pass.

Owner: one native IMAP executor owns canonical engine/zylch/email/imap_client.py,
focused real-protocol tests, and explicitly reviewed equivalent family changes.
MAIN's unrelated worktree/index remain untouched. First extend the existing
brief with the exact bounded read-only recovery behavior and obtain its fresh
review; then review this amendment. No implementation starts before both gates.

Smallest deciding RED: exercise the actual native projection/IMAP adapter against
a local socket protocol server. Authenticate normally, let the first EXAMINE
stall, and let a fresh authenticated connection return valid EXISTS,
UIDVALIDITY and UIDNEXT plus the required evidence. On the preimage, demonstrate
that the stalled command exhausts the short test's unchanged absolute deadline
and yields conservative UNKNOWN. Use actual socket waits, not a fake select()
that merely raises an exception. Retain commands, monotonic timings, connection
identities and process/socket cleanup. This is free and model/provider independent.

Candidate repair, only if that RED confirms the mechanism: cap each readonly
SELECT attempt at min(15seconds, remaining original evidence deadline), with
short proportional test bounds. Permit at most ONE fresh authenticated retry
per projection, solely for a timeout/disconnect during readonly SELECT, and only
with time remaining. Existing connect limits, absolute deadline, concurrency and
resource budgets stay unchanged. Fully dispose and detach the old connection
before reconnecting. Reapply the attempt cap after connection establishment;
restore ordinary command timeout only within the original remaining deadline.
Do not retry authentication denial, missing folders, malformed responses,
identity/source-guard failures, SMTP, writes, or any mutating command.

The installed pinned-connection scope needs explicit reviewed handling: retry
before any evidence acceptance, or invalidate and recompute the complete evidence
snapshot once under the same absolute deadline. Never silently rebind a scope
with accepted observations. Revalidate UIDVALIDITY/UIDNEXT and all existing
source/ownership guards against the fresh connection; changed identities or
incomplete inventories stay held/UNKNOWN. If this requires broadening beyond
one bounded recovery and complete recomputation, stop this implementation branch
and return the measured RED and exact scope conflict for a revised D1 decision.

Required GREEN through the same actual native/local-protocol path: first stalled
connection is closed, exactly one fresh connection succeeds, the final result
contains independently validated complete evidence, and no command is a write.
Nearby controls: both attempts stall; provider genuinely exceeds the unchanged
absolute budget; already-expired deadline; cancellation during the first attempt
and during reconnect; malformed/changed UIDVALIDITY or UIDNEXT; and non-retryable
auth/folder failure. Each must preserve held/UNKNOWN and bounded cleanup where
appropriate, never spin or accept mixed-connection evidence. Assert total elapsed
bound, no third connection, unchanged guard-before-disposal/R8 ordering and no
leaked sockets/threads. Existing offline transport suites remain prerequisites.

Independent milestone review must inspect exact canonical and BOTH family
contexts, particularly projection_connection/_ensure_connected differences.
Only approved RED/GREEN and complete family maps permit the existing immutable
source deployment, captured rollback and exact policy/activation gates. A new
finite health/FULL admission requires its own actual resource disposition and
review; neither this plan nor diagnostic success renews the failed58 allowance.
This amendment establishes a testable source hypothesis and bounded repair
contract. It does not establish upstream root cause, implemented recovery,
production health, FULL success, public release or completed alignment.

### D1 replacement — diagnose the actual daemon connection before any repair

Status: cause UNKNOWN; current diagnostics INSUFFICIENT. This is diagnostic-only
continuation of the existing plan. The prior SELECT retry proposal is NOT
APPROVED and cannot authorize implementation, a retry admission or latency-fix
claim. Root owns the existing brief amendment; fresh framing review then fresh
plan review must approve this replacement before coding. No behavioral retry,
deadline, budget, concurrency, authority, SMTP or business-policy changes.

Actual evidence distinguishes projection elapsed time from operation elapsed
time: the second retained failure is located in SELECT after120seconds of
projection time, but SELECT entry time and connection state were not retained.
Fresh per-observation mailbox clients do not establish a global reused-pool
cause. Read the complete private select-connection-diagnosis.md under
/tmp/mrcall-ai-kit/20261025-release-alignment/v58 for the observed source facts
and their limits. Fresh-process success cannot explain a daemon-only failure.
No further real-provider retries merely to obtain a passing result are admitted;
ordinary future failures should retain diagnostic evidence automatically.

#### D1a — reviewed diagnostic contract and actual daemon capture

Owner: one engine executor owns canonical ACTOR native IMAP/projection diagnostic
seams and their focused local-protocol tests, with explicit equivalent adaptations
for BOTH actual actor families. Preserve MAIN's unrelated worktree/index and
family-specific projection_connection pinning, deadlines, disposal and guard
ordering. Do not overwrite a family module from canonical source: canonical
543f311e lacks the installed families' pinned projection-connection scope.

Capture INSIDE the actual daemon RPC execution, rather than only a standalone
process: opaque per-process connection identity plus generation; socket open/
closed and timeout state; IMAP state and TLS state; pinned/current/deadline
connection equality; outstanding tag and command COUNTS without values; exact
operation entry, exit, duration and remaining absolute deadline; ordered command
VERBS without arguments; timer armed/fired/cancelled and socket abort/disposal
cause from finite enums. Preserve first failure separately from cleanup failure.
Events must retain actual trace/root correlation and safe actor/family provenance.
No credential, address, mailbox name, mail header/body, raw response, prompt or
raw exception message may enter events, private files or test receipts. A
connection identifier cannot be a pointer revealing process address; generate an
opaque token scoped to the runtime. No extra network operation is diagnostic.

Contract decision from actual engine/kernel safe_metadata inspection:58 currently
supports elapsed_ms, count/pending_count/deadline_seconds, complete/available,
command/method, hashed evidence_ref and safe error origin. These can faithfully
carry operation events, duration, actual counts and hashed correlation only.
It does NOT support the required typed connection generation/state, pin-match,
subsecond remaining deadline or timer/disposal cause. Do not smuggle those into
command identifiers, unrelated count/error fields or causal facts with different
meaning, and do not silently drop them while claiming the full contract passed.

Prefer an existing field only where its documented meaning fits. The full
ordinary CLI/collector contract therefore needs an explicitly reviewed typed
bounded diagnostic schema shared by engine emission and kernel validation, or
a reviewed narrower requirement. This plan chooses the schema route for full
acceptance, contingent on fresh brief/plan approval; kernel58 installed bytes and
tag remain unchanged. If kernel code is needed, produce a NEW immutable kernel
candidate under the existing version/release procedure and validate BOTH clones.
An engine-only58-compatible subset can be separately verified but cannot close
the full connection-state diagnostic acceptance or underlying defect.

#### D1b — real controlled daemon failure and propagation proof

Owner: the same bounded diagnostic executor; independent reviewer owns the
milestone verdict. Run a real native daemon RPC against a staged local IMAP/TLS
protocol peer using the exact family contexts, native handler/auth and isolated
read-only fixture data. No real provider, model, SMTP or writes are needed.
Exercise a connection that authenticates then stalls a specific EXAMINE, a
partial-protocol-progress case, and expiry/disposal while a command is pending;
include an unexpired success and legitimate-held control. Preserve the existing
absolute deadline semantics; test fixtures may use shorter injected existing
bounds without changing production values. Do not patch results or bypass the
family pin, source guards or first-failure preservation to manufacture evidence.

The preimage must demonstrably lose the deciding operation/state. Candidate
GREEN must show which connection/generation, exact operation and entry-time
remaining budget, protocol state/progress and timer/disposal sequence actually
precede failure. Retain real EventStore records, ordinary CLI paging, collector
and private inbox evidence through the normal schema validation path. Current58
must retain the honest compatible subset; the new schema candidate must retain
all approved typed fields through that same path. Test bounded payloads,
malformed/unexpected fields and secret-bearing sentinel rejection. A blind
analyst receiving only those ordinary records must identify the malfunction and
the supported causal boundary or precise next inspection, without being told
the injected failure or inventing an upstream cause. All observed timers,
threads, socket cleanup and unchanged conservative held/UNKNOWN decisions need
real receipts. Passing unit doubles alone does not satisfy native daemon proof.

#### D1c — separate diagnostic closure from underlying-defect closure

Independent review may close the diagnostic component only after D1a/D1b evidence
and privacy/schema/family checks pass. Exact source deployment and rollback use
the existing reviewed family maps, policy/activation and release gates; no new
provider acceptance trial follows automatically. Documentation must explicitly
state the unresolved underlying cause and retained next inspection route.

Underlying-defect closure requires an ACTUAL daemon failure with sufficient
connection/state evidence, a supported cause, and a targeted repair verified
through the SAME native daemon path, with nearby failed/held controls preserved.
That repair requires a subsequent reviewed D1 decision, not this diagnostic-only
amendment. Neither a fresh-process pass, absence of ERROR, recovered retry,
healthy process nor finished logging component proves the malfunction fixed or
the whole release/alignment assignment complete. Existing FULL/publication/BOTH
clone adoption/doc-end/final-review obligations remain separately outstanding.

### D1 execution contract — brief-approved diagnostic continuation

Framing gate: APPROVED, daemon-diagnostic-brief-review.md, brief SHA256
6cd5cee79f045b136155637f9d6f8954e4aa3b3d2c22f4bf90503430a7681627.
This concrete refinement now requires a fresh PLAN review before coding. It
supersedes no held/cause-UNKNOWN constraint above and admits no live-provider run.

#### P0 — canonical provenance prerequisite, before typed changes

Owner: engine executor, isolated canonical ACTOR branch/index descended from
543f311e. The exact nine existing source paths are engine/zylch/observability.py,
observability_context.py, observability_logging.py, observability_producers.py,
observability_profile.py, observability_reader.py, observability_recent.py,
observability_retention.py and observability_store.py. They are absent from
543f311e Git history, although present untracked in MAIN and installed in BOTH
actual actor families. Independent read-only provenance inspection finds all
nine MAIN bytes equal BOTH immutable hosted copies. Preserve their exact
preimage hashes and source origin; do not pretend543f311e already tracks them.
The observability.py anchor SHA256 is
fcfbc53025e6407f89798e802a3493276751f4239f80c9bf49d9717fec549684.

Recover ONLY these nine existing modules into the isolated owned canonical
index, unchanged as a separately reviewed provenance baseline. Inventory their
imports and the already-live RPC/read binding seams; required dependencies must
resolve from tracked ACTOR code or explicitly reviewed exact-family baseline.
An absent dependency is a named prerequisite, never an implicit MAIN/WIP import.
Capture complete installed family maps before any delta; preserve their
projection pinning,120-second family deadlines and source/disposal guards.
Do not touch MAIN's foreign worktree/index, create runtime-only patches, copy
whole family IMAP modules to canonical, or invent a source-history attestation.
Verification: exact nine-path hashes equal each hosted preimage; clean isolated
import/test process resolves every dependency without MAIN PYTHONPATH; independent
review accepts this provenance cohort before diagnostic implementation.

#### P1 — exact small optional wire object

Owners: kernel executor owns cs/observability.py and cs/observability_store.py
validation, normal engine-log import/read, monitor_details/evaluate propagation
and private-inbox failure detail; engine executor owns the matching nine-module
source surface, IMAP producer seams, observation/terminal propagation and native
RPC harness. Use existing modules and tests; no replacement logging framework.
Follow the actual existing monitor_details/evaluate definitions to their direct
modules only. Preserve legacy causal-envelope validation unchanged.

Add optional top-level metadata `provider_diagnostic`, a CLOSED object with
exact keys below. All keys are required inside an object; unavailable observations
are JSON null where explicitly allowed, never guessed. Serialized object maximum
4096 UTF-8 bytes. No additional keys, coercion, bool-as-number, NaN or Infinity.
`version`: integer exactly1.
`connection_id`: random runtime-scoped lowercase32-hex token or null; never id(),
fd, address, mailbox, credential or hash derived from a secret.
`generation`: integer1..2147483647 or null, incremented on connection creation.
`sequence`: integer1..2147483647, allocated atomically per observation across threads.
`operation_id`: integer1..2147483647 or null; entry/exit share the same number.
`operation`: enum observation/connect/tls/login/examine/search/fetch/guard/timer/
abort/dispose/unknown. `phase`: enum enter/exit/failed/armed/fired/cancelled/joined.
`command`: enum CAPABILITY/LOGIN/EXAMINE/SELECT/UID_SEARCH/UID_FETCH/NOOP/OTHER or null;
this is a native command VERB, never its arguments or a provider response.
`socket_state`: enum absent/open/closed/unknown.
`imap_state`: enum DISCONNECTED/NONAUTH/AUTH/SELECTED/LOGOUT/UNKNOWN.
`tls_state`: enum absent/negotiating/established/closed/unknown.
`pin_match`: bool or null, observing current versus projection pinned connection.
`deadline_match`: bool or null. At ordinary operation events compare current
connection identity/generation with the active deadline connection; at timer
armed/fired/abort/dispose events compare the actual current target with the
identity/generation captured when that timer was armed. Null means either
identity is unavailable, never presumed equality. The event's connection_id and
generation retain the originally armed target on timer events, while this flag
records whether the actual current target still matches it.
`inbound_progress_count`: integer0..2147483647 or null, counting successful
nonempty returns from the native IMAP socket/read path for THIS operation.
Reset to zero at command entry; null means that operation's native read path
cannot be observed safely. Increment only after an existing native read returns,
without retaining, parsing or logging payload, issuing extra reads, peeking or
changing read boundaries. No per-read event is emitted.
`last_inbound_progress_offset_ms`: finite number0..3600000 or null, monotonic
offset from observation start of the latest counted nonempty native read for
this operation; null before any progress or if unavailable. Snapshot both
progress fields at meaningful command/state transitions and first fault only;
entry records zero/null, terminal records the accumulated count/latest offset.
Counter overflow clamps and sets overflow=true; it cannot become a complete
causal proof. A return observed in a nested reader must be counted at exactly
ONE chosen native ingress seam, not counted again by outer parsing wrappers.
`pending_tags`: integer0..65535 or null; count only, never tag values.
`pending_commands`: integer0..65535 or null; count only.
`offset_ms`: finite number0..3600000, monotonic elapsed from observation start.
`duration_ms`: finite number0..3600000 or null; null at entry, measured at terminal.
`remaining_ms`: finite number0..3600000 or null, clamped at zero after expiry;
this measures the ORIGINAL absolute deadline, never an extended local bound.
`socket_timeout_ms`: finite number0..3600000 or null.
`cause`: enum none/deadline/cancelled/socket_error/protocol_error/cleanup/normal/
unknown. These describe the observed transition, not an inferred provider cause.
`overflow`: bool, true if diagnostic sequence/state exceeded capture bounds.

Emit only operation/state transitions, not bytes, message counts per payload,
raw protocol responses, headers/body, exception text or repeated polling events.
At most2048 diagnostic records per observation, reserving8 terminal/failure
records. Overflow emits one marked incomplete terminal snapshot and prevents
claiming diagnostic completeness. Snapshot readings must be nonblocking attribute
observations: no NOOP, extra provider call, TLS handshake, recv or socket probe.
Any unsupported state is unknown/null. Do not parse provider text to fill enums.
Retain one immutable FIRST-FAULT object in the existing terminal failed event;
cleanup events retain their separate objects and cannot replace the first fault.
The normal private inbox carries that snapshot plus existing trace references,
not the whole diagnostic sequence. Correctly update monitor_details/evaluate so
the typed object survives actual producer-to-inbox transformation.

Timer callbacks receive the observation's explicit safe trace context and
connection/generation identity captured when armed. ContextVar inheritance cannot
be assumed for threading.Timer. Atomic sequence allocation must not block native
I/O, and telemetry failure must not change RPC outcomes or cleanup ordering.
Record armed/fired/abort/dispose against their ACTUAL observed target identities;
never label a later pointer as the originally armed target without comparison.

Compatibility: object absent preserves old event semantics; new readers accept
legacy records. A malformed object is rejected by validation and diagnostic
completeness fails; never silently replace it with a sanitized successful record.
Kernel58 has no such typed field and may reject/drop it, so cannot certify this
wire shape. Freeze58 untouched; new immutable59 candidate carries the reviewed
wire extension and BOTH clone installation under existing release gates. Keep
emission/deployment ordered so58 is not left reading an incompatible engine stream.
No opaque-state facts are hidden in unrelated existing fields or command names.

Verification: run exact native schema round trips, legacy-absent controls,
all enum/null/boundary cases, unexpected key/type/oversize/sentinel rejection,
first-fault-versus-cleanup and timer-thread correlation/concurrency controls.
A schema unit pass is insufficient without P2 ordinary-surface receipts.

#### P2 — concrete staged daemon/native-protocol acceptance

Owner: engine executor owns a new focused
engine/tests/assignments/test_daemon_provider_diagnostics.py plus a small staged
socket peer next to the existing email protocol fixtures. Extend the established
engine/tests/assignments/test_transport_evidence.py WebSocket setup: real
server_ws._process_request and _handle_connection, native method dispatch to
rpc.task_assignments.project, asyncio.to_thread, actual project/observation and
IMAPClient. Use the existing assignment fixture's temporary SQLite profile and
signed/fixture identity admission; reject a foreign bearer as a negative control.
Fixture identity verification is explicitly offline, not proof of production
Firebase. Do not replace projection, provider_client, IMAP select, EventStore or
RPC response with predetermined fake outcomes.

Replace only the external provider endpoint with a loopback IMAP/TLS socket
server using a test CA trusted only by the fixture client; use real TLS, LOGIN
and imaplib command framing. Seed source/assignment/mailbox fixtures before the
read-only request; restrict runtime DB reads and assert no business-data writes.
A bounded fixture deadline may shorten production120seconds for test execution,
without altering production constants or retrying commands. Local endpoint-only
network policy and failing model/SMTP sentinels prove zero provider/model/send use.

RED preimage: actual authenticated daemon RPC reaches a peer-selected EXAMINE
that never completes; ordinary retained events cannot identify its connection,
entry-time remaining budget, protocol state and timer-abort order. GREEN same
peer scenario: new typed records plus frozen first-fault terminal object retain
all these facts while the native result remains conservative held/UNKNOWN.
Additional staged cases: successful EXAMINE then later stalled command; partial
untagged progress without tagged completion; cancellation/expiry while pending;
unexpired success and legitimate hold. The analyst must distinguish time spent
before EXAMINE from time spent inside it, and initiating failure from cleanup.
The no-response stall must retain inbound_progress_count=0 after command entry;
the partial untagged case must retain a positive count/latest progress offset
before the same tagged-command expiry. These snapshots establish that bytes
arrived, not that their content was valid or that the provider caused failure.
A native read that never returns is not counted as progress. Retain the local
peer's controlled scenario separately from the blind analyst's ordinary evidence.
No retry/recovery success substitutes for a failure receipt.

Persist through real engine EventStore; fetch via actual logs RPC and normal
new-candidate `cs logs trace` paging, then run the real collector and private
inbox transformation. Retain producer/native RPC/CLI/collector/inbox receipts
bound to exact source hashes. Reader58 compatibility means legacy records still
work; it does not mean new fields magically survive58. Blind review sees only
ordinary records, identifies the controlled malfunction and supported boundary,
and leaves unsupported production cause UNKNOWN. Also verify private files,
stdout/stderr and EventStore contain none of the fixture secret/header/body
sentinels; normal TLS/IMAP debug remains disabled. Assert native timers, threads,
sockets and process groups terminate, source guards and family pinning remain
unchanged, and no third-party endpoint or business mutation occurred.

Milestone review P0 precedes P1; P1 schema/native controls review precedes P2
integration/deployment. Root supplies exact isolated source roots and evidence
paths to each executor; workers do not restart repository-wide orientation.
A failed local proof is repaired locally before any adoption or paid acceptance.
Controlled GREEN closes only diagnostic delivery. Production-defect closure
still requires real daemon failure evidence, supported cause and a subsequently
reviewed targeted fix verified on the same path. FULL, publication, BOTH-clone
adoption and documentation/final review remain owned by the existing lead task.

### D1 verified diagnostic adoption — remaining acceptance stays open

The immutable59 candidate is ec7d84f8414e0df441bf9eef9a0c57c2f628626b;
source and at-tag67-gate harnesses pass. BOTH normal clones match all159files,
authenticated identities and lock-only rebuilds, preserving nonkernel dependencies,
authored instructions and SEND/DRAFT modes. Public Git provenance is pending.
Canonical engine diagnostics are90bb447be5cabab5a81a21d5ea6e3ef1293753fe;
P0/P1/P2 and the exact rollout packet have independent approval. Twelve native
controlled daemon/TLS/RPC/ordinaryCLI/collector/inbox cases pass. Blind analysis
recognizes three distinct deadline failures and a legitimate hold; it leaves
upstream production causation unknown. The40-versus3fixture metadata discrepancy
and malformed-method wrapper regression were corrected with retained RED/GREEN
and exact new-source receipts, not by discarding failed evidence.

Actual supportPID170010 and CaféPID178296 load the reviewed immutable families;
complete source/mode/unit/fleet checks and fresh actual-row/integration approvals
pass. Exactly one deployment restart per actor and zero rollback were used.
Kernel59 and final active runtime policy78b216e88a880ff51b226333ffdd14eddfea2d2d416408c73ba7b3fd062c6c89
pass authenticated instruction readback. Original cron93b2e2898f521e1c2ae6277522b0efad80121401d89d0ce640706e3ace66cdf4
is restored; only owned pauses were removed. Four peers and Qonto are unchanged.
The terminal receipt is v59/rollout-terminal-receipt.json under the existing
release-alignment evidence root. Rollback controls are tested; live rollback was
not exercised. No manual job compensates for a maintenance-skipped schedule.

Original intermittent IMAP cause remains UNKNOWN. This closes diagnostic delivery,
not the underlying defect, strict BOTH FULL, public release/adoption, documentation
completion or baseline advancement. No paid health/FULL admission was renewed.
Next evidence comes from passive existing schedules/logs, not a new provider retry.


### Delivery reconciliation — reported costs, public provenance and diagnostic limit

The retained native terminal receipts report USD1.3509014 for
`run-ojxx7tc9`, USD1.3365518 for `run-dxbrr4n1`, and USD2.7948136 for
`run-ewmxfc45`: USD5.4822668 total. These are native cost reports, not
settled provider invoices. Three interrupted ticks retain USD12 of unknown
reservations; two earlier standalone allowances retain USD1, and uncertain
other diagnostics retain USD1. The failed58 health adds its USD0.50 allowance.
The conditional USD12 FULL reserve never became an executed FULL. Together
these explain the historical USD31.9822668 planning reservation; they do not
establish that this amount was spent. The numeric ceilings16/20/22/27/32 and
failure-stop admissions are lead decisions in this plan, not quoted operator
spending limits. Operator instructions authorize finishing, publication and both
clone updates; they do not authorize unlimited spending or automatic retries.
The existing admission is consumed; this reconciliation grants no new attempt.

Read-only remote verification at2026-10-26 13:49 UTC confirms public main
`2821a6a3fcd7280f645970e35bd81eb6a79e8189` and published53 at
`4f4f027fac51d676b369548021a387d136be4917`; public54–59 tags are absent.
Local59 remains immutable at `ec7d84f8414e0df441bf9eef9a0c57c2f628626b`.
Both local installations and local lock-only proofs do not establish public Git
provenance. Strict BOTH-clone FULL remains the publication prerequisite.

The additional bounded log lookup is concluded. Event
`4bc07dcfbeff44edbdb11d5463e32785` explicitly records an unattempted deferral;
its cause event `c93b15356453455fa4b42dadd6fa62b6` records a shared deadline
at8191ms against8187ms. The parent owner `x59G6SnymAN2lkFny0JDGJgdFz33`
runs unchanged peer PID2615148, outside the authorized two-actor rollout.
All three retained engine JSONL files for that owner were scanned:15144events,
9688251bytes, no exact parent trace match. A temporally overlapping engine RPC
has another trace and remains unbound. No dispatch, IMAP phase, connection,
progress or cleanup cause is inferred from that coincidence. Provider cause
remains UNKNOWN; no peer rollout or added diagnostic loop is authorized here.
Evidence: external `v59/charge-reconciliation.json`,
`operator-release-resource-quotes.json`, `passive-exact-owner-retained.json`,
`passive-temporal-candidate.json` and `passive-correlation-handoff.json`.


### One reviewed original-root read — current availability, historical cause unknown

The single model-free native read is complete. Fresh review approved the exact
bounded launcher after its missing immediate preflight and client wall bound
were repaired. The supported kernel59 client called only
`tasks.assignment.project` for the original failed58 root hash
`d4fb6a8a61fd7a3dd0bcab25dc3a827a2a4b480cd53056cb05468a328c1e9dba`
on actual support daemon170010/90bb. Retained original daemon events establish
that root/owner binding. Immediate source/PID/policy checks passed; no unfinished
support assignment RPC was observed and the earlier natural job was terminal.
This does not assert global chat idleness. No peer request, model generation,
assignment commit, send, configuration change or restart was requested.

The client finished in48.86seconds, exit0, without its155-second timeout. Actual
server trace `83948f1e8e044e50ac49eac5558716bf` binds the same root, owner and PID.
Its enqueue-to-worker delay is3.05ms; projection and RPC terminals are held at
14:01:01UTC. The1069provider records show one connection,41EXAMINE,6SEARCH and
16FETCH entry/exit pairs, successful LOGIN/TLS and normal disposal with about
72.46seconds remaining. No provider fault record is present in this call.

The result is `needs-assignment`, `NEEDS_HUMAN_VERIFICATION`,
`hold_auto_reply=true`, `complete=false`. The ordinary health validator accepts
this kind of human-work hold when the surrounding inventory, flags and provenance
are consistent. A single root response does not prove those whole-health
conditions. The probe summary did not retain the specific reply-evidence
judgement, so its exact business justification is not independently established.
No further call is made to fill that gap. This current successful observation
neither explains nor repairs the historical timeout and does not admit FULL.
The different peer deadline incident remains a separate root/owner chain.

Evidence: external `v59/one-original-support-read-packet.json`,
`one-original-support-read-review.md`, `one-original-support-read-preflight.json`,
`one-original-support-read-execution.json`, `one-original-support-read-result.json`,
`one-original-support-read-events-progress.json` and
`one-original-support-read-analysis.json`. The reviewer retained the initial
REVISE separately. AI-KIT coordination is disengaged by operator instruction;
no additional observation loop or pending paid proposal is approved by that stop.


### E0 — instrument the failed59 ordinary admission before selecting a repair

Approved framing: `full59-repair-brief-review.md`, brief SHA
`49c055b1473836bff8ad0d3503c1c0606589faaf06033d43b9f5212ccc13baac`.
Operator requires corrections through actual strict BOTH-clone FULL success.
Do not change the outcome of failed run555fb4ca9d69820a070a3890ffac312d.

Kernel executor owns only canonical `cs/operational_fixture.py`, finite causal
entries in `cs/observability_causal.py`, directly needed validator propagation
and focused fixture/causal tests. Record real aggregate inbound/enrollment/exact
match/provider-confirmed counts. At existing branches retain absent/invalid/
expired enrollment and the first failed binding predicate, never operand values.
Provider observations name actual connect/login/select/UIDVALIDITY/fetch/MIME
phase, monotonic elapsed time and actual finite error metadata. Keep the first
failure separate from logout failure. The configured15-second socket timeout
is not an operation deadline. Reuse typed cause contracts and existing allowed
facts; invalid causal output must not silently become a successful test.

Desktop executor owns only the existing runner's checkpoint observation and its
focused tests. Retain safe read_incomplete presence/type and producer event/trace
references without logging its arbitrary text. Keep fixture identities, source
matching, independent provider checks, native-job dependency order, signing,
cleanup and every strict oracle unchanged. A failed checkpoint remains failed.
Preserve MAIN's foreign changes/index; do not commit unrelated work.

Fresh plan review precedes implementation. Both workers have10-minute first
milestones and lead progress checks at most five minutes apart. Required free
controls distinguish absent source(0candidates/0confirmed), duplicate source
(2matches/rejected), provider failure(1candidate/0confirmed) and exact success
(1/1). Exercise absent/invalid/expired registry, each binding predicate, timeout,
provider rejection, cleanup failure and diagnostic-sink failure without changing
return semantics, source guards or provider call counts. Use a real local IMAP
protocol peer/client to stall a selected operation; retain phase and exception.
Privacy checks reject sensitive operands and unexpected fields. Exercise actual
EventStore, ordinary logs CLI and collector/inbox propagation of non-null causal
evidence. Existing whole harness must remain green. Independent integration
review checks actual evidence before adoption or another paid run.

Keep installed59 immutable throughout source work. After free approval, freeze
one new unused immutable MINOR candidate, build its artifact, run its at-tag
checks and adopt through supported package/update/lock flows on BOTH clones.
Refresh only exact installed package identities and reviewed runner provenance
in the existing policy/manifest; no engine restart or peer rollout is needed.
Capture preimages and prove actual-byte equality, fresh lock rebuilding and
preserved company rules, dependencies, modes, pauses and technical-mail controls.

### E1 — observe the exact failure boundary, repair only demonstrated behavior

Use new producer evidence through the actual installed path to classify a failed
protected-source discovery. A bounded model-free read of the existing verified
original may supply current evidence without sending or executing it again.
It cannot retrospectively prove a historical cause. Missing-source/binding and
provider failures must remain separate; a successful read is not a repair claim.
Before a behavior patch, state the demonstrated mechanism, concrete correction
and same-path RED/GREEN acceptance in this plan and obtain fresh affected review.
No blind timeout increase, repeated whole-run retry, forced fixture, validator
weakening or business-policy change is admitted.

### E2 — finish genuine BOTH-clone FULL after verified correction

Execute the unchanged strict suite with fresh protected originals and the exact
installed composition. Existing three-job USD4 nominal settings and5400-second
suite bound remain; these are soft guards, not provider billing hardcaps. The
operator's renewed instruction authorizes necessary bounded acceptance and
correction; it does not authorize unlimited retries. Retain actual charges and
unknown reserves per attempt. A newly classified failure returns to E1 with its
new evidence. Success requires original independent provider/receiver outcomes,
SEND/DRAFT, ACK/no-loop/no-extra-effects, all natural job terminals and cleanup.
Retain publication/public Git adoption and doc-end/final-review obligations under
the original assignment; do not claim them complete from a test result alone.


### E0/E1 delivered; genuine E2 FULL60 is active

E0 source/component integration is APPROVED. The real local IMAP failure,
cardinality/binding/registry controls and EventStore→CLI→collector/inbox checks
pass. The whole kernel harness passes before freeze and at immutable60,
including six genuine external golden-pack builds. Desktop's seven focused
checkpoint tests and actual EventStore-reference proof pass; its pre-existing
two failures/eight errors remain unchanged and are not claimed green.

Kernel60 tag `9c69b9936f96531e430f36c6535eb5a909592291` is frozen;
post-tag3364f58 pins it. Both actual normal clones match159files, identities and
fresh local lock-only rebuilds. Company rules, nonkernel dependencies and modes
are preserved. R7 consumer canonical commit is
`0f3296dd63e0da47f722e446dd60333efba4aec5`; its three actual paths match that
commit while Desktop's foreign worktree and ordinary index remain preserved.
Exact runtime-policy integration is independently APPROVED and activated at
SHA `343845e99474f513fc975ea6ab492a50cc1135f6271421ce2abbac3ef3f0c4a5`.
The90bb actors, four peers and excluded Qonto are unchanged; no restart occurs.

The approved E1 read uses the same retained original, unchanged nonce/expiry and
provider receipt under actual job/acceptance locks. It sends nothing and invokes
no classifier/model/business action. Trace
`d8f263a52b4c4fca9497bec7acf88c55` records one inbound/enrollment/match/candidate/
confirmation in2.581seconds and all provider phases in the same trace. The prior
historical failure remains unexplained. A diagnostic launcher API mismatch failed
before provider work; its exact failed artifacts are preserved and its one-line
context-API correction was independently re-reviewed before the actual read.

The first copied lock-proof helper accidentally wrote two old59 auxiliary files
before uv refused the already-existing environment. It changed no normal clone
or proof environment. The old auxiliary install log and derived lock cannot be
claimed original retained bytes; the incident is explicit in external
`v60/failed-lock-helper-route/incident.json`. Fresh60 proofs use new directories
and refuse existing ones; both pass. Other old receipts and failed runs remain.

The adoption scheduling transaction restored the exact original cron and removed
only its pauses. Fresh strict E2 run `139d12dc3bc9f964fbc705f327ce6c5b` starts at
15:55:47UTC under the existing R7 strict runner. Both new original receipts and
ordinary checkpoints pass; the genuine MrCall native job is active. Café/signup
and all final provider/signature/cleanup checks remain pending. The runner owns
its temporary schedule window and must restore it. External `v60/RESUME.md` owns
live handles; no publication, completed FULL or baseline advancement is claimed.


### E3 — make cumulative time-budget failure explicit in ordinary logs

Approved framing: external `v60/time-budget-brief-review.md` and exact approved
brief snapshot. User requires unmistakable causes; FULL60 remains FAILED.

Kernel executor owns `cs/task_assignment.py`, the finite causal registry and
strictly needed fact validators, plus focused RPC/scheduler/propagation tests.
Instrument the actual existing scheduler without changing deadlines, admission,
provider calls, reservations, root ordering, result content or authority. Emit
bounded batch/lane summaries: effective time available at entry, actual elapsed/
remaining time, expected/dispatched/returned/timed-out/deferred counts, actual
per-account/global concurrency and cumulative serial work. Distinguish sums of
request durations from wall time. Reference the first actual deciding timeout;
use its measured bound origin, never infer provider failure or financial quota.
Do not label effective remaining allowance as original configured budget when
the original is unknown. Keep absence/normal holds non-ERROR and diagnostics
best-effort. Preserve existing per-request events and deferral cause references.

Fresh plan review precedes code. First worker milestone is8minutes; progress
check within5minutes. Real transport controls must distinguish cumulative shared
expiry from an individual request timeout with ample shared time. Assert exact
counts, unchanged calls/results/reservations, healthy/zero-work/held behavior,
first-cause links, privacy and actual CLI/collector/inbox propagation. A fresh
log-only analyst must identify time-budget exhaustion without code or hints.
Independent integration review and green complete source/at-tag gates precede
one new immutable candidate and supported BOTH-clone adoption. No actor/peer
rollout or financial-control change is part of E3.

### E4 — measure before correcting the workflow time allowance

After separate execution-safety review, one assignment-only measurement may use
actual installed `task_assignment.projections` over the exact captured84-root
requested_order, after all guarded native work is quiescent. Hold the actual
operator/signup and acceptance locks; prevent new guarded ticks through an owned
reversible scheduling transaction. Preserve per-account1/global4, request150 and
backend120 limits. Its800-second diagnostic ceiling changes no production
setting. Do not call review.gather/sweep/classify/generate/send or mutate business
data. Retain only safe per-root state/hash and exact producer time/expiry data;
no addresses, bodies, arbitrary reasons or exception strings. Bound process and
cleanup; remove only owned controls. A successful read is a measurement, not a
historical-repair claim. Use actual complete work and native1800-second envelope
to frame the smallest time-budget correction with fresh affected review. Do not
ship an arbitrary larger timeout, change concurrency or repeat FULL blindly.


### E2 terminal evidence and E3/E4 current execution

FULL60 terminated FAILED at16:27:17UTC. Native MrCall exited0 after1767.265s,
but its genuine supervisor rejected final assignment health: exit3 and24UNKNOWN
roots. Café/signup never started. Exact cron restoration was independently
checked; whole acceptance and publication remain open. Both checkpoint originals
passed; this failure is distinct from historical59 unknown discovery.

Astra's1376-event analysis establishes cumulative caller shared-deadline expiry,
not a proven120s provider operation timeout or monetary quota. Review completed
36projections totaling385.386s on support; final caller allowances shrank to
16.483s and4.765s. A matched support trace finished after its caller timed out,
with individual provider operations below0.879s. These facts explain that
caller's expiry; they do not establish every older failure's cause.

E3 implementation has7focused,34existingRPC and8causal tests passing, with real
transport and CLI→collector→inbox proof. Fresh blind analysis and integration
review are running; the complete source harness is active. No E3 code is installed
in normal clones. E4 execution remains unapproved pending retention of validated
per-outcome bound diagnostics; no live measurement has run. Normal MrCall cron
started a separate job at16:50UTC and remains active, so E4 must not overlap.


### E4 terminal measurement: partial coverage, mixed causes

The single approved model-free measurement completed at17:27:56UTC after
792.206s under the800s shared allowance. Actual admission acquired all four
guards and found no matching jobs. The child was reaped, no live process-group
members remained, and the lead independently reacquired all four guard locks.
The first launch had failed before any provider call because its process scanner
read an unrelated non-dumpable systemd cwd; its evidence is preserved. A narrow
scanner fix passed offline/current-process checks and fresh execution review
before the only live measurement.

Observer evidence retains87matched starts/finishes,174records, no overflow/write
failures and47unique locally observed roots. All84requested roots have outcome
hashes, but37were never locally invoked. Outcomes:13normal,2conflict,
23needs-assignment,46unknown. The unknown partition is6successful-RPC-only,
2error-only,1both and37never invoked. This is usable partial measurement, not
complete coverage or FULL. The admission receipt's initial status remains
`failed` although terminal execution says `measurement_completed`; use terminal
evidence and explicit lock/scan facts rather than that misleading initial label.

Two deciding errors select the shared deadline. A separate469ms local read
failed remotely with113272ms left; a matching-time daemon validation event and
independent input validation show an invalid RFC root. The producer currently
labels this `transport_unavailable`, which is too broad. Larger shared time
cannot repair invalid input or explain six unknown outcomes after successful
RPCs. Therefore no production deadline increase or paid FULL retry follows yet.

The long110.198s support read spent104.798s in normal EXAMINE/FETCH/SEARCH and
finished before120s backend/150s request limits. Its held terminal excludes
unknown/SOURCE_UNAVAILABLE under the pinned producer mapping; exact hold subtype
is absent. A preceding same-root failure at imap_client.py:875 is conclusively
the header-inventory message-count guard; actual caller/limit/count were not
retained. Subsequent measurement state for that root is needs-assignment. This
source-count failure is not an asserted transport or time-budget failure.

Astra is diagnosing the malformed root and six successful-RPC unknowns from
existing evidence; a source explorer maps the remote-rejection diagnostic gap.
Before any next code, amend this same plan with concrete diagnosed mechanisms,
finite diagnostic fields/corrections, tests and fresh review. Preserve all
strict authority/source/whole-inventory oracles and financial controls. No peer
rollout, unbounded scan, invalid-root omission or forced PASS is authorized.


### E5 — integrated MIME identity, remote-rejection provenance and measured shared time

Status: proposed; fresh plan APPROVED is required before implementation. This
amends the existing release plan, following E4; it does not reopen historical
receipts as successful acceptance. Classification: substantial behavior and
cross-repository acceptance work; the fast path does not apply.
Approved framing is the complete combined repair brief SHA-256
`8d3dd07d8bbe4d33acc4ad18a2b7aec57ff660c1c8719aa9c80c227906bffae8`
and the retained time-correction, remote-rejection and header-repair brief reviews
in `v60/assignment-profile`. Diagnosis/source maps there are scoped planning
evidence, not independently rerun source or runtime confirmations in this amendment.

Dependency order: E5a and E5b are independently reviewable; E5c may proceed only
after fresh plan approval and its numeric/source checks. E5d integrates all three
before dependent freeze, adoption or paid acceptance. Lead owns coordination and
evidence; bounded executors own only their listed surfaces and preserve foreign
WIP/index. Each execution assignment has an eight-minute first deliverable and a
progress check within five minutes; a stall returns to the lead without blind retry.

#### E5a — recover complete header identity without changing authority

Kernel identity owner extends `cs/thread_key.py` and only directly necessary
`gmail_drafts`/`draft_state` discovery seams and focused identity tests. Decode the
bounded whole References/In-Reply-To MIME header before whitespace tokenization;
use strict charset/byte decoding and structurally complete RFC identities rather
than replacement characters or guessed brackets. Preserve normal identifiers,
HTML-escaped supported representations and ordered multi-ID References. Invalid,
partial, ambiguous, malformed encoded-word and unknown-charset material remains
explicit uncertainty under existing fail-closed behavior; retain its draft in
whole-inventory coverage. Do not substitute a trusted root, opportunistically
merge identities, change owner/source/peer guards or decode unrelated content.

Verification: retain RED with the actual captured two-encoded-word header shape
(full header 121 characters, full decoded ID 80 characters, erroneous first raw
token 66 characters); GREEN must demonstrate discovery through the real Gmail
row/thread-key path yields the same complete identity as the retained full
header, without a provider call or invented identifier. Focused regressions cover
normal and HTML identities, ordered distinct multi-ID References, both header
sources, malformed/partial/ambiguous encoding, unknown charset and nearby distinct
identity. Assert inventory retention and unchanged foreign/missing-root refusal.
Use private fixtures safely; do not publish raw customer headers in receipts.
Fresh integration review of these checks closes E5a. Offline identity recovery
alone does not establish the current engine binding or an accepted assignment.

#### E5b — retain typed remote response provenance across bounded reads

Kernel RPC diagnostics owner extends `cs/rpc_reads.py`, the exact-key diagnostic
validators/causal registry and `cs/task_assignment.py` event propagation, with
focused real WebSocket tests. The wire client already retains `EngineError.code`;
classify that structured exception before generic IO fallback. Distinguish
`-32602` invalid parameters, other remote errors and connection/IO failure. Carry
only an optional bounded integer `remote_error_code` in the typed read diagnostic;
update constructor, exact-key validation, worker JSON, parent validation, causal
allowlists and event forwarding together. Never parse message text or invent the
remote Python exception type. Exact diagnostic schema retains required keys `cause`, `bound_origin`,
`elapsed_ms`, `bound_ms`, `remaining_ms`, with only optional `remote_error_code`.
Its type is strictly int (not bool), `-(2**53) < code < 2**53`, matching the
existing producer's safe range; absent code stays absent. Timing validation stays
0..10**12 integer milliseconds, with only remaining_ms permitting null. Add
causes `remote_invalid_params` for -32602 and `remote_error` for other
EngineError responses; preserve existing bound_origin choices. Event propagation
uses existing error_class=EngineError/error_code fields from this typed diagnostic,
while the returned parent exception remains RuntimeError. No other schema keys
or error payload fields are admitted.

Verification: real controlled WebSocket RED/GREEN sends structured `-32602`, a
different remote code, connection failure, request timeout and successful/held
controls. Assert exact calls/results, ordering, unchanged parent RuntimeError
compatibility, fatal flags, scheduling and fail-closed UNKNOWN semantics. Strict
schema tests reject extra keys, bool/noninteger and out-of-range codes; no message,
error.data, identifier or exception text survives. Prove metadata survives actual
worker isolation, EventStore, ordinary paged CLI, collector and inbox. A fresh
blind log analyst must distinguish invalid-parameter remote rejection from IO
failure and shared expiry using only retained logs. Fresh integration review
closes E5b; diagnostics do not themselves repair rejected identities.

#### E5c — finite coordinated time allowance with explicit partial extrapolation

Kernel time owner owns review/discovery/worker ceilings in `cs/review.py` and
`cs/unanswered.py`; Desktop acceptance owner owns native-job limits, runtime-policy
and matching validators in `scripts/operator_operational_test.py`,
`scripts/operator_operational_common.py` and a staged runtime-policy PROPOSAL
in a private artifact outside `operational-evidence/runtime-policy.json`.
The Desktop time owner must leave the active runtime policy untouched. These are
coordinated changes, not an isolated longer test timeout. Only ROOT/lead may
activate a new policy, after the exact R8 consumer plus installed new-kernel
composition has passed independent composition review and installed preflight in
E5d. Preserve the current valid active composition until that gate.

Sizing proposal: the slower E4 lane completed 38 successful reads in 782.103s
(20.5817s/read); support completed 46 in 704.939s. For 84 roots, slower-lane mean
EXTRAPOLATION is `782.103 / 38 * 84 = 1728.859s`. E4 is PARTIAL: unattempted work,
future tails, fallback and actual current engine binding are unmeasured; neither
this mean nor the 800s experiment guarantees complete work. Reserve about 300s
for non-projection work plus 25% of 1728.859s (432.215s) as conservative headroom:
2461.074s; propose a finite 2700s work ceiling, leaving about 239s additional
margin. This explicit reserve is a proposal to evaluate, not a measured bound.

Proposed aligned controls: review work 2700s, cleanup 10s, total 2715s; scheduled
observation 2710s, sweep 2700s, cleanup 10s, publication 5s, final 5s, total 2730s.
Update both worker sweep/completion validation ceilings coherently with their
actual payload deadlines, including review's inherited deadline. Keep strict
positive ordered work/cleanup/total validation and bounded reaping/disposal.
MrCall native becomes 6600s; Café stays 1800s and signup stays 600s for the known
case. The existing FULL60 nonphase remainder was approximately 687s; the corrected
review-plus-discovery maximum is `2715 + 2730 = 5445s`, yielding approximately
6132s, below 6600s. This is envelope arithmetic, not a FULL runtime prediction.
Suite limit becomes 10200s: native maxima `6600 + 1800 + 600 = 9000s` plus 1200s
for stages/cleanup. Policy, resume-age checks, elapsed validators and suite cleanup
clamping must use one coherent limit; retain finite explicit cleanup reserves.
Normal guarded-job outer limit remains three hours. Retain per-account/global
concurrency 1/4, request 150s, batch 180s, backend/provider 120s, standalone
projection 3600s and all close/reservation/guard semantics. Financial controls
remain USD4 soft per job, nominal three jobs times USD4; last FULL60 actual
USD2.789 is historical spend, not a free new admission or a guaranteed future cost.

Before coding, owners check the actual source defaults and all direct ceiling
validators against this map. Evaluate whether a smaller coherent allowance is
justified by the same complete envelope; any material different sizing returns
to fresh affected plan review rather than arbitrary raising. Verification is a
deterministic real-worker/transport RED/GREEN cumulative shared-expiry case with
healthy reads and complete expected inventory under the finite corrected budget.
Use proportionate short test allowances without replacing the actual production
constant/envelope assertions. Individual request/batch timeout, exhausted shared
budget, peer-incomplete UNKNOWN, legitimate held, guard expiry and cleanup/reaping
controls must still fail or hold exactly as appropriate. Validate native/suite
policy consistency, resume age and terminal evidence rejection at each bound.
No model/provider call or paid FULL is part of these free checks. Fresh integration
review closes E5c; no backend deployment/restart is required or authorized here.

#### E5d — integrated forward candidate, exact consumer and finite BOTH FULL

Lead integrates E5a/b/c plus already reviewed E3; review the combined real-user
paths before freeze. Run the complete source harness `bash tests/run.sh`, then
all 67 current at-tag gates with all six genuine golden-pack inputs; a skipped
or fabricated golden gate is not parity. Preserve exact commands, outputs, source
hashes and independent integration verdicts. Only green free gates admit the new
immutable forward candidate 61; retain prior tags/installed bytes unchanged until
supported adoption. Never retag, overlay site-packages or alter peer merge/source
checks to make whole-inventory health pass.

Adoption owner uniformly installs the exact immutable forward tag on BOTH normal
clones through supported Git/package/update paths, verifies all 159 inventoried
package files and resources and absence of unexpected overlays, refreshes locks
and version claims, and binds exact source/runtime identity. Desktop owner makes
the R8 consumer adjustment as an isolated owned commit and stages exact policy
hashes/composition; preserve foreign WIP and all independent strict signed oracles.
Activation order is mandatory: green source/at-tag gates, supported immutable
BOTH-clone adoption, exact installed manifests and R8-consumer/policy hash binding,
independent composition review plus installed preflight, then ROOT/lead activation
of that exact reviewed policy. The time worker cannot activate it. Until ROOT
activates the reviewed composition, keep the current valid active policy intact.
Retain its complete preimage; rollback restores the matching prior consumer,
installed package/pin/lock and policy composition together before acceptance can
resume, never an incompatible policy in isolation. Require reviewed finite
spend/time admission before one genuine strict BOTH FULL. Preserve protected original
binding, independent provider confirmation, exact authority/source/whole-inventory
oracles and uncertain prior effects; no backend/peer rollout or replay.

Run the exact approved runner/policy against both actual clones, including native
MrCall/Café/signup and terminal cleanup/evidence checks. A new failure goes to
Astra with retained complete logs for evidence-based diagnosis; no blind retry,
second paid attempt or budget extension is implied. On failure, retain failed
outcomes and stop dependent publication. Rollback uses captured package/pin/lock
preimages or a separately immutable known-good release through supported install;
restore only owned scheduling controls, never business data, effects or logs.

This amendment establishes a concrete proposed dependency/verification sequence.
It does not establish implementation, exact current engine binding, a guaranteed
complete-work runtime, adoption, passing BOTH FULL, publication or retrospective
causes of earlier failures. Release publication, public installation/lock proof,
doc-end reconciliation/doc-critic and separate final review before baseline
advancement remain open obligations of this existing plan.


### E6 — public tag provenance without publishing failed candidates

Status: proposed; fresh affected plan review precedes metadata code. This is
necessary release closure under the existing approved canonical/publication
intent, not a product or authority change. Read-only origin evidence establishes
public tags through53only. The release checker incorrectly labels57–60 as
mandatory published anchors, so a fresh public clone of61would fail resolving
those absent local-only candidate refs. Failed candidates must not be published
merely to satisfy that mistaken requirement.

Lead owns tests/test_release_consistency.py and ordinary harness wiring only.
Keep every actually published immutable anchor mandatory. Preserve the exact
four57–60 candidate name/hash pairs in an explicitly local frozen-candidate
registry: absence is permitted only for those exact unshipped refs; a present
ref must match its retained hash. Do not move/delete tags, skip generic missing
releases, infer publication from local presence, or add network to the hermetic
checker. Record the next61release through the normal release/post-tag process.

Controls must prove all published anchors remain required and retargeting fails;
a public-only tag map with absent57–60 passes candidate checks; any locally
present candidate mismatch fails. Prove actual Git ref resolution does not
unconditionally dereference absent optional candidates. Retain original frozen
hashes and the independent remote-ref evidence in public-tag-closure-map.md.
Wire E5identity/RPC/review/discovery regressions into their existing full harness
steps without removing any check. Fresh affected integration review and complete
source/at-tag gates precede freeze/adoption. This does not authorize a failed tag
publication, change installed kernels, or relax any FULL/provider/authority oracle.


### E7 — paragraph-only authority template closure and forward0.61.1

Status: proposed; fresh plan approval precedes template code. Approved framing
is v61/template-framing-review.md and immutable template-brief-approved.md, SHA
febeea2405f420bc410ec0dd3ace3f7439ea089071e7c633dd14c41f1e1fe4a4.

Executor owns only cs/templates/project/docs/ARCHITECTURE.md.j2, one dedicated
render regression and its tests/run.sh invocation. Replace only the unconditional
derived-rules paragraph with the identical existing managed/legacy paragraph
shared by both actual clones. Preserve every other template byte. In particular
add no assignment section; preserve MrCall's separate local assignment prose.
No runtime Python, company values, permissions or standing-rule writes change.
First deliverable in four minutes, progress within three.

Retain RED for the unconditional authority claim and GREEN from actual Jinja
rendering for two neutral clone shapes. Privately compare the rendered authority
paragraph with both protected clone paragraphs without model/provider calls.
Prove git diff against immutable61 changes no cs Python and exactly this one
packaged template. Fresh affected integration review precedes dependent freeze.

Lead reuses all unchanged E5/E6 and R8/source reviews. Run complete source and
at-tag harnesses with six genuine golden builds for one forward patch0.61.1;
never alter frozen61 or its installed files. Build own-path v61p1 wheel/manifest
and preserve all prior evidence. Keep159package files; only the reviewed template
resource and version metadata may differ from61. The inherited unshipped runtime
composition still requires genuine FULL on BOTH clones regardless of patch digit.

Adapt supported adoption's template guard to permit exactly this reviewed
ARCHITECTURE resource delta, rejecting every other template change. Preserve
clone-authored/managed instructions and custom prose. Derive only the Kernel pin
row from the real renderer, leaving unrelated as-built content intact; update
owned active pin claims and retain their old passages verbatim. Verify both
normal imports, Git objects, identities/modes, unchanged nonkernel dependencies
and fresh local lock-only rebuilding. Source overlays remain forbidden.

Carry the EXISTING v61 scheduling transaction rather than restore/re-hold:
original3cron entries, two exact owned pauses/markers and four guards remain
bound to their original live state and immutable snapshots. Private v61p1 helper
version/manifest refs change to0.61.1; R8 canonicalf7f2471 and10200policy semantics
remain unchanged. Keep original v61 ownership/marker/control paths explicit;
never invent a new hold or mark the old one restored. Fresh affected helper
review and exact installed composition review/preflight precede activation.
No backend/peer restart, budget change or rule publication is admitted.

After verified candidate adoption, activate exact reviewed R8 consumers/policy
through the reviewed guarded rollback transaction. Restore only the original
owned scheduling hold immediately before the finite strict BOTH FULL so its
runner can own the acceptance window. One reviewed attempt uses unchanged
USD4soft controls and independent original/send/draft/health/provider oracles.
Any failure returns to Astra with retained evidence; no blind extra retry.
Doc-end/critic, separate final review, public provenance/lock verification and
publication remain open. Publish no failed61tag to satisfy provenance checks.

### Exact proposed-policy preflight repair and current acceptance

Both normal clones now match immutable0.61.1/32d9867 across159 package files;
complete source/at-tag gates and both fresh local Git lock rebuilds pass. These
component results do not certify strict operational acceptance or publication.

The first proposed-policy activation failed its independent installed preflight:
`full_runtime_identity` reread active5400 while checking proposed10200. The
transaction restored the complete normal R7 consumer/policy preimage. Its failed
output remains in `v61p1/policy/activation-61p1`; no native paid job was launched.
The bounded correction validates and propagates an explicit proposed policy through
the existing identity, credential and subprocess-environment helpers, retaining
active-policy defaults. It is canonical consumer successor ca175b9, separately
reviewed with six time, one real subprocess plumbing and seven transaction tests.
New exact composition and activation reviews bind the changed consumer/helper
and fresh policy references; old reports and proposals remain unchanged.

The reviewed second transaction passed actual installed preflight and policy-last
activation. Original V61 scheduling ownership was restored exactly before the
strict runner acquired its own acceptance window. Current genuine run
`4faf6e38a887988b2b7b1f8ce0f39669` is incomplete: both original provider receipts
and ordinary discovery checkpoints pass; the actual MrCall native job is running.
Its output is `v61p1/full-installed-v61p1-20261026`. No diagnostic continuation,
old-case resume, source overlay, oracle relaxation or financial increase is used.

Remaining order is unchanged: finish the strict BOTH-clone FULL; diagnose any
new failure from its actual evidence with Astra before a reviewed correction or
new finite attempt; only genuine success admits the already authorized successful
tag publication and public Git/lock proof on both clones. Preserve historical
unknown causes and restore owned controls. Reconcile current docs using doc-end,
explicit doc-critic and separate final review; advance no baseline or completed
plan status until the actual required results and current evidence pass.

### E8 — consistent serialized bounds for private notice persistence

Status: proposed amendment to docs/execution-plans/2026-10-25-canonical-release-alignment.md;
fresh affected plan approval precedes implementation. This is substantial
behavior repair, not fast path: persistent projection bytes and queue completion
change. Existing approved canonical-release/logging scope covers the observed
persistence defect; this adds no business authority or delivery capability.

Evidence: v61p1/notice-persistence-diagnosis.md retains event
c96c4899e472475ab7a471888835b562. Source selects a problems list with default
compact JSON <=220000 bytes, but _atomic writes indented JSON with a 262144-byte
hard cap. Read-only reconstruction admits 219919 compact bytes yet needs 267339
indented list bytes before the envelope. Evidence and incident are retained first;
projection failure leaves the queue pending. Native work continues, so this alert
alone does not establish the running FULL outcome or exact historical byte count.

M1 — kernel owner repairs cs/operational_inbox.py and extends existing
tests/test_operational_inbox.py; no Desktop, clone, provider or control writes.
Prefer removing indent=2 from the existing shared _atomic serialization, keeping
sort_keys=True, allow_nan=False, encoding, newline and the 262144-byte guard.
This aligns list selection and final JSON format without a parallel writer or
raising limits. Prove complete envelope headroom with actual bounded field shapes;
if that proof fails, revise selection to account for the exact final envelope
before approval rather than weakening the hard cap. Preserve selection order,
skips, remaining_count, retrieval pagination, JSON values and notice identity.
Keep fsync/replace, 0600 private files, directory/symlink checks, retention and
65536-byte canonical notice admission unchanged. No email or automatic analyst.

M1 verification: disposable real MonitorStore with safe synthetic incidents must
reproduce the old compact-fit/pretty-overflow failure through actual publish and
record_notice, retain original RED output, then succeed with parse-equivalent
GREEN output <=262144 bytes. Exercise _deliver_pending against the same backlog:
failed persistence retains queue/evidence/one incident; a freshly reloaded retry
clears queue only after all writes succeed; repeated identical notice keeps one
identity/incident, with no duplicate evidence. Do not clear _delivery_failed in
the failed in-memory state to manufacture retry. Verify 220000-list boundary,
skipped oversized item and truthful remaining_count; complete-envelope sizes;
exact 262144-byte write versus262145 refusal leaving prior file intact;
65536/65537 canonical notice admission; nested/non-ASCII values and NaN refusal.
Assert private modes, symlink refusal, retained findings/evidence, no sensitive
notice payload in projection, no SMTP/model/provider calls and unchanged ordinary
healthy/held/failed results. Run existing inbox, operator-health and recovery
regressions using the lead's actual tested interpreter; retain commands/results.
Fresh affected integration review closes M1 before dependent adoption work.

M2 — lead owns adoption decision after the current immutable 0.61.1 FULL terminates.
Preserve run 4faf6e38a887988b2b7b1f8ce0f39669, all installed bytes and controls while
it runs. Free source work grants no mutation or acceptance retry. If actual
adoption is needed, use a fresh immutable forward version through the existing
release procedure: complete source/at-tag gates with genuine golden inputs,
reviewed package manifest, supported BOTH-clone install, exact installed identity,
lock/provenance checks and independent composition/preflight review. Never overlay
installed files, retag 0.61.1 or publish a failed candidate. Capture owned adoption
preimages; rollback restores their matching package/pin/lock/composition, never
business data, retained evidence or uncertain effects. Reuse no old FULL verdict
for changed candidate bytes: exact-current strict BOTH-clone acceptance remains
required. Any new paid attempt needs explicit fresh finite spend/time review,
reconciled actual charges/reserves and green free gates; no automatic retry.

This amendment establishes source cause, narrow proposed repair and dependencies.
It does not establish implementation, final envelope proof, passing regression,
current FULL outcome, adoption, publication or release completion. Existing
doc-end/doc-critic, final review and public provenance obligations remain open.
Coverage: complete inbox module/tests and diagnosis; producer 744–840, brief 401–514,
plan 2201–2386 plus lead-approved scope handoff. Lead explicitly approved bounded
partial historical-plan use; unrelated historical body was not re-investigated.

#### E8 current delivery evidence — 2026-10-26 20:36 UTC

Source commit3f704ba and immutable0.61.2/1189037 include the reviewed complete
serialized-envelope correction. The first compact-only repair was REVISE after
an independent real50000-character fallback-owner case; its superseded receipts
remain retained. Corrected6focused/19inbox tests, health/recovery, full source and
at-tag suites pass; each whole suite includes six genuine golden builds.
Both normal clones match all159 files and fresh local Git lock rebuilding.
Installed private-copy backlog checks pass with zero outward calls: MrCall two
pending notices, max219811 bytes; Cafe one pending, max220167 bytes. Original
queues and stores remain untouched by those probes. Synthetic accidental test
state was proven newly created by birth times/exact inventory, hash-copied to
private quarantine and removed only from its owned paths; other state is retained.

Astra composition/one-finite-attempt admission and separate exact transaction
reviews pass. Actual installed preflight and policy-last activation pass for
policy149007d4; original owned hold restored exactly into runner acceptance.
Fresh strict run c47fa38e71330b7ac26056b7b4f82fb1 started20:35:36UTC at
`v61p2/full-installed-v61p2-20261026`. It is incomplete, unsigned and running;
publication, public provenance, final reviews and baseline remain open. Prior
interrupted native charge remains unknown without a terminal record; configured
financial limits are unchanged and no zero-cost or business no-effects claim is made.

### E9 — align native Bash lifetime with the approved bounded work
Status: approved amendment; M1 integration APPROVED. Source and exact-tag harnesses pass with six genuine golden builds each. BOTH adoption, native acceptance and publication remain pending. Historical body, approved brief and E5–E8 remain intact.
Classification: substantial runtime/prompt behavior repair; no fast path. Lead owns integration/adoption; one kernel executor owns only the launcher, exact operator template, focused existing tests and finite diagnostic propagation.

Evidence and exact sources
- Actual failed FULL c47fa38e71330b7ac26056b7b4f82fb1 is FAILED, not acceptance: v61p2/full61p2-failure-cause.md. Review requested600000ms, automatically backgrounded, then killed after its background lifetime; no TaskStop was found. Native process exit0 does not establish complete work.
- cs/operator_recovery.py:363–435 launches text-prompt `claude -p` with output-format stream-json; that OUTPUT option is not input-format stream-json. Its copied environment presently sets neither Bash timeout variable.
- cs/templates/project/.claude/skills/cs-operator/SKILL.md.j2:30–39 explicitly requires600000ms for discovery/review, while forbidding explicit backgrounding and preserving literal canonical commands/results.
- cs/operator_native_composition.py:240–278 correctly rejects killed task completion; retain that rejection and source/SDK-literal proof.
- Primary current vendor source: https://code.claude.com/docs/en/tools-reference#time-limit-for-background-commands and #raise-the-time-limit-for-background-commands. Text-prompt -p has600000ms background defaults; a moved foreground command gets its separate background lifetime from the move. BASH_DEFAULT_TIMEOUT_MS above600000 raises that text-prompt default; MAX alone does not raise it.
- Same primary page #timeout-and-output-limits: foreground default120000ms; effective foreground maximum is max(BASH_DEFAULT_TIMEOUT_MS,BASH_MAX_TIMEOUT_MS). #foreground-commands-that-move-to-the-background documents timeout-driven backgrounding and its stop notice.
- Installed executable /home/mal/.local/share/claude/versions/2.1.296 SHA256 f1f6e96e0d8342b9dbf41d7e88255397a6a52ce3d8736ad6a4c6b59c9b62fefa was read, never invoked. Its complete timeout helper module at byte213555515 contains tre(default120000), SRe(max600000/default), xcs(background max1800000/default), and kce(max7200000/effective max). Runtime text-prompt specialization is established by official documentation plus the actual retained600s stop, not by asserting xcs alone explains it.

Decision and rejected alternatives
Use the existing native launcher and literal Bash interface. Bind a finite child-local shell allowance2730000ms to the existing largest complete CLI phase2730s; set BOTH BASH_DEFAULT_TIMEOUT_MS and BASH_MAX_TIMEOUT_MS deterministically for ordinary /cs-operator launches only. Update the operator template discovery/review tool timeout to2730000ms. This changes neither kernel phase budgets nor host/suite deadlines.
The default variable is essential even if a model still requests600000ms: it prevents the moved task's old600000ms lifetime from preempting legitimate bounded work. Matching MAX advertises/permits the complete foreground interval. Exact phase-at-boundary completion remains subject to ordinary elapsed/cleanup failure, never guaranteed success.
Do not introduce async APIs, nohup, explicit background jobs, shell timeout wrappers, disable-background switches, broader permissions or a changed input protocol. MAX-only is insufficient. Increasing kernel/suite deadlines alone leaves the cause unchanged. Accepting killed/stopped as success is forbidden.

M1 — launcher/template correction and model-free causal proof
Owner: kernel executor; first deliverable within8minutes, lead progress check by5minutes. Extend existing launcher/test surfaces rather than parallel machinery.
Before code, retain RED from the existing real local-child subprocess fixture in tests/test_operator_recovery.py: make its harmless child report only the two inherited Bash settings and assert the required2730000 values on the actual _run launch. Current source must fail this assertion. No actual Claude/model execution.
Retain separate RED rendering the actual Jinja operator skill and asserting discovery/review request2730000 while preserving exact command spelling, separate calls, no run_in_background, and existing no-wrap/no-pipe rules. Current600000 text must fail.
GREEN: same actual subprocess and render paths pass after repair. Exercise ambient unset, smaller, invalid and larger values: ordinary launches get the exact finite contract; unrelated/custom prompts retain existing environment behavior. Assert parent environment unchanged and both direct/wrapper identity cases, denies, budget args and pin/receipt binding preserved.
Use retained representative lifecycle events to prove completed foreground/automatic work passes, killed/stopped mandatory review still fails despite process_exit0, and incomplete discovery/foreign-owner/source/SDK-literal cases stay refused. Label constructed-event evidence honestly; it is not a genuine native tool run.
Add a finite diagnostic cause for an actual structured killed/stopped native task at the rejecting producer seam. A time-limit cause requires validated structured producer evidence; otherwise retain upstream reason unknown and route to the host Bash lifetime. Never infer timeout from arbitrary task/summary text. Preserve failure semantics and actual event/cause links through real local capture→health→ordinary CLI→collector/inbox; a blind log check must recognize the interruption. Retain malformed/unknown and healthy controls; emit no customer payload or raw command.
Run the focused launcher, composition, template and affected diagnostic tests using the lead's actual interpreter; then required source harness with genuine golden inputs. No model/provider calls. Fresh integration APPROVED precedes M2.
A2730s end-to-end Bash runtime cannot be proved by a short subprocess fixture. Native timeout conformance remains explicitly unverified until the exact candidate's finite genuine FULL; documentation/static binary evidence and causal local launch proof justify admission, not retrospective acceptance.

M2 — immutable forward candidate, BOTH adoption and exact composition
Lead uses next unused immutable version under docs/release-procedure.md; never reuse/overlay0.61.2. This changes observable operator instructions, so apply the repository MINOR rule and mandatory FULL on BOTH clones. Preserve failed61/61.1/61.2 tags and evidence without publishing them as successes.
Require source/at-tag gates with six genuine golden builds; review exact package resource deltas; supported BOTH-clone installs, all159 package-file/resource inventory checks, exact import/Git identities, fresh local Git locks and source/manifest provenance. Permit only reviewed template changes in supported adoption guards; preserve managed/clone-authored prose. The actual rendered cs-operator timeout instruction must update on BOTH canonical skill trees and all three host paths before FULL; a blanket protected-file restoration must not silently retain600000. Allow only the reviewed timeout-line delta, preserve every unrelated local skill line, and retain truthful checksum/parity differences.
Carry current v61p2/bash-time-fix-adoption control transaction and its exact3cron/two-pause markers; do not reuse historical V61 restoration claims. Cleanup PASS is v61p2/full-failure-cleanup.json. Capture package/pin/lock/consumer/policy preimages and exact ownership before mutation.
Preserve existing review2700work/2715total, discovery2730, MrCall6600, Cafe1800, signup600, suite10200 and fixture-authority5400. The shell lifetime correction does not extend fixture authority: expiry must still hold/fail truthfully. Preserve per-account/global1/4, request150, batch180, provider120, guard/reaping/cleanup rules and native-job dependency order.
Independent exact installed composition/preflight review binds forward package, rendered prompt, launch contract, existing R8 consumers and10200 policy before activation. Rollback restores the matching package/pin/lock/consumer/policy composition and only owned controls; never business rows/effects/evidence. No backend deployment/restart is implied.

M3 — fresh finite admission, genuine BOTH FULL, closure
Lead reconciles final prior native reported costUSD1.8543868 and uncertain other charges; current engine budget20/remaining19.58 and19.32 is not exhaustion proof. Preserve USD4 soft/job and existing finite ceiling/reserves; no model, engine-budget or spending increase.
After green free checks, fresh composition review and explicit finite admission, permit at most ONE new strict fresh BOTH-clone FULL with authenticated original fixtures and original financial/source/signature/provider/whole-inventory/health/send/draft/terminal oracles. Do not extend fixture authority or replay uncertain effects.
Restore only the current owned maintenance hold immediately before the runner takes its own acceptance window. Retain complete raw native stream, exact Bash inputs, foreground/background transitions, truthful terminals, cost and cleanup receipts. A killed/stopped review, expired authority or any incomplete dependency fails; retain evidence and stop dependent publication without another retry.
Genuine current-candidate FULL success alone admits remaining already-authorized publication work; doc-end/doc-critic, public tag/lock proof, separate final review and baseline advancement retain their existing gates.

Does not establish: implementation/GREEN, a real Claude timeout experiment, guaranteed2730s completion, provider no-effects, current fixture admissibility, sufficient future funds, BOTH acceptance, publication or release completion. No source/config/provider/model writes occurred in planning. Scoped source excerpts were authorized by the lead; unrelated historical plan body was not re-investigated.

E9 M1 verification references: `/tmp/mrcall-ai-kit/20261025-release-alignment/v62/bash-time-integration-review.md`, `source-harness-r2-result.json`, `at-tag-harness-result.json` and `blind-bash-logs-report.md`. Immutable local candidate `v0.62.0` is `d1fa8c8218cb852093d6c551dd552cab20309afc`; all159 package files match its wheel. These component results do not certify installed adoption, native conformance or FULL.
