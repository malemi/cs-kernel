---
status: completed
---
# Vonage production rollout

Brief: [authorized delivery](../briefs/2026-09-14-vonage-production-rollout.md).
Brief review: APPROVED, 2026-09-14.
Plan review: APPROVED after requiring independent review of repaired FULL harness.

## M1 — integrate and review

Capture refs and both clone working-tree inventories in a private recovery
directory. Commit only the reviewed kernel change paths, merge current
origin/main without rewriting published history, and reconcile conflicts by
preserving both v0.44 setup/project behavior and new provider behavior. Update
release-ready documentation and run the full kernel gates. Independent reviewer
checks the integrated diff before versioning.

## M2 — candidate verification and release

Audit a fresh private copy of the prior external FULL harness against v0.44
before baseline capture. Replace obsolete RATE_CAP assertions with current
pause/dedup/headless safety proofs and independently review those harness
changes. Preserve the old harness and its baselines. Capture fresh immutable
v0.44 baselines for both clones with the repaired harness. Compare candidate
results with baseline, classifying only evidenced expected/volatile differences;
no ignored unexplained failures. Exercise local mutation/error fixtures and
actual generated wrapper denial without customer sends. Independent review of
candidate evidence gates publishing.

Follow release-procedure in order: commit integrated source, full test pass,
release commit with new MINOR version and FULL tier, immediate tag, full tests
at tag, post-tag immutable-object pin and untagged HEAD marker. Sweep version
claims. Publish main and new tag using the operator's explicit authorization.

## M3 — maintained clone upgrades

Before each installation, preserve private env/config, venv, pin/lock, stamped
files, crontab and unrelated dirty files. Record each pause's original presence
and bytes. Hold the relevant operator with its existing pause mechanism and
confirm no affected task is running before changing files. Relevant schedules:
support signup outreach and custom send operator, and coffee clone draft
operator. Check their processes and acquire their operator/runner locks where
applicable; wait for an active run rather than interrupt customer work.

Upgrade to the published tag through `cs update` (explicit pin path if needed),
inspect every conflict and preserve authored files. Verify package version,
pin, template ledger, three identical agent surfaces and headless mutation
denials, including the custom send operator's marker refusal. Run FULL clone
comparisons, engine identity and actual installed Vonage status+preview on the
configured support clone; disabled binding must refuse on the other clone.
Generate locks from the installed environments and independently install each
lock alone. Verify source package resolution in those throwaway environments.

Restore the original pause state only after that clone passes. On failure,
keep it held while restoring its backed-up package/template state, then prove
the prior version before restoring scheduling. Do not change the crontab.

## M4 — delivery and documentation

Commit explicit rollout paths in each clone, excluding transcripts and unrelated
changes, and push authorized deployment commits. Update kernel operational-pin
marker only after both pass. Resolve current-versus-historical version claims,
reconcile integration guides to installed reality, run doc-end and independent
final review, then report published tag, installed clones and tested limits.

## Evidence

- Initial checkout: 7d8d3f0; origin/main: 91372e8; both installed clones: 0.44.0.
- No affected scheduled process was running at initial inspection; recheck
  immediately before installations. Current crontab is preserved unchanged.

- M1 APPROVED: integrated with origin/main `91372e8`, preserving v0.44 project
  memory and setup behavior. Public feature commit `a1f74f7` excludes sampled
  customer identifiers from the brief and plan.
- All kernel gates passed before versioning and again at immutable v0.45.0
  (`a3e7aff4d80a1537fbe91c70e3085d4aa94c13fc`). Post-tag registry and HEAD
  markers pass the release-consistency check.
- A stale local build directory exposed retired templates in an isolated
  candidate wheel. Clean Git exports corrected the candidate; a new installed
  package gate compares all 39 template paths and bytes, including unwanted extras.
  Both exact-tag candidate environments pass. Production was not affected.
- Original FULL baseline and candidate evidence remain immutable. Independent
  review confirmed exact additive provider denies and skill discovery, retained
  custom denies and identical normalized live outputs. Supplemental harness
  review addresses normal-negative contacted status, an obsolete degraded
  fixture and staging-path normalization; no failure is silently accepted.

- M2 APPROVED: independently reviewed supplemental baseline/candidate checks pass
  for every affected surface. Original and supplemental baselines retain their
  hashes. Published main and v0.45.0 atomically; the tag target is unchanged.
- Both maintained clone upgrades install the public Git tag and stamp five
  updated files plus the new skill, with zero skipped/conflicted files. Installed
  identities, provider status/preview or disabled refusal, 39-template inventory
  and three agent surfaces pass. Both regenerated locks install alone into new
  environments and resolve the exact release object. Final FULL review is APPROVED.

- M3 APPROVED: actual installed FULL reads, settings, dedup, safety and scheduling
  checks pass. Permission/skill changes exactly match the approved candidate;
  the separate production supplement verifies the corrected degraded fixture.
  Both original and supplemental baselines retain their hashes. No customer
  trunk, draft, send or call was created by release verification.
- Both prior pause states are restored and all acquired locks released. Crontab
  bytes match the pre-upgrade copy. Pre-existing unrelated clone changes remain
  outside the deployment commits. Installed user-path and documentation reviews
  are APPROVED; live SIP writes/calls and paid agent execution remain unverified.

- M4 APPROVED: deployment commits are published (`mrcall-cs` `f3e8004`,
  `124-cs` `b8d11f3`). The kernel operational marker names v0.45.0 on both clones.
  All three documentation gates are clean; final independent semantic review
  has zero STALE findings. Historical provenance and untested live SIP/paid-agent
  behavior remain explicitly qualified. Clone baselines remain unchanged to
  avoid claiming review of unrelated earlier work; kernel doc-end advances its
  reviewed baseline separately.
