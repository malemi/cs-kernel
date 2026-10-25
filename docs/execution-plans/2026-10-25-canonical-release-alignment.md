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
