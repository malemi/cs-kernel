---
status: completed
---

# Desktop workspace setup delivery

<!-- doc-scope:start -->
Scope: kernel ownership and evidence for the coordinated two-worktree setup
delivery; the cross-repository plan lives in the desktop repository.
<!-- doc-scope:end -->

## Intent and review

[Brief](../briefs/2026-09-10-desktop-workspace-setup.md): approved by an
independent reviewer on 2026-09-10. Cross-repository implementation plan:
mrcall-desktop `docs/execution-plans/2026-09-10-desktop-to-operator-onboarding.md`.
Plan review passed on 2026-09-10; implementation is authorized.

## M1 — Kernel implementation

Worktree `/home/mal/worktrees/cs-kernel-operator-setup`, branch
`feat/operator-setup-ux`, baseline `7d8d3f0`. Baseline full gates pass.

1. Add explicit descriptor selection to init; maintain separate secret-bearing
   selection context, use it for mailbox-setting/credential handoff, and avoid
   duplicate selection by scanning. Preserve unflagged init.
2. Truthful install stages and exit codes; argument-list subprocesses; optional
   confirmed post-install login. Validate identity in login's proof response.
3. `cs setup [--json]`: bounded, read-only business checks and actionable state.
   Engine `setup.state` adds nullable `emails_analyzed_count`,
   `emails_pending_analysis`, and `last_email_analyzed_at`; older engines are
   unverified. These indicate memory processing, not reply quality or task
   completion. Auth may refresh existing token caches.
4. Tests: explicit selection with multiple profiles, no leaked credentials,
   safe paths, failed installation/login and recovery, wrong UID, missing old
   readiness evidence, empty mailbox, installed agent vs unverified login.

Fresh integration review across both worktrees is required before M2.

## M2 — Verification and documentation

Run full `bash tests/run.sh`, installed-package/stamped-clone readiness scenario
with a local controlled transport and isolated state, and canonical agent-surface
checks. Update the user guide and living context, preserving current tag/version
claims. Mechanical and semantic documentation checks and a fresh final-user-path
review precede completion.

No releases, pushes, operational clone upgrades, or live engine/mail calls.
Source installation is development evidence, not public-release availability.
Rollback is discarding the isolated development branch.

## Progress

- Brief and plan approved (independent reviews, 2026-09-10).
- M1 implementation and independent integration review: approved.
- M2 full suite: all gates green including gate 53; optional external golden
  fixtures absent. Log: `/tmp/cs-kernel-operator-setup-final.log`.
- Installed-source journey: isolated stamped workspace, space/apostrophe paths,
  selected descriptor, matching identity, wrong-UID refusal and recovery,
  readiness evidence and canonical agent surfaces. Controlled local WebSocket
  transport; no operational profiles or live service calls.
- Fresh final cross-repository user-path review: approved.
- Documentation semantic review approved; release consistency and mechanical
  documentation checks pass. Public-install and live authentication remain
  unverified.

## Production rollout — v0.43.0

The CTO authorized production release and installation on 2026-09-10, after
Desktop v0.1.47 was released. Scope includes the earlier reviewed minted-session
work already in the branch: mint guards, cached-token retirement and cron stdin
closure, plus descriptor setup and strict login proof. MINOR / FULL on both
maintained clones. Adding company accounts or migrating secondary credentials is
separate consumer work and is not implied by installing this kernel.

Release review finds no code blocker. Before publication:

1. Preserve clone pin/template/security files, installed freezes and unrelated
   edits. Capture a private current0.42.0 baseline with the FULL external harness
   on both clones; historical baselines remain untouched. Inspect gate results
   rather than trusting capture's exit code. Existing defects must be identified.
2. Run the kernel suite before versioning. Make the release commit, immediately
   tag0.43.0 locally, rerun the suite at the tag, and make the mandatory first
   post-tag immutable-target/untagged documentation commit.
3. Pause future clone ticks only during the upgrade window, preserving prior
   pause state; wait for running tick locks. Install the local candidate tag in
   both clones, use the supported pin/template refresh, and inspect every changed
   security file against its saved pre-upgrade contents. Preserve clone-owned
   deny rules and authored documents. No outbound messages or account migration.
4. Run FULL checks with the candidate installed against both current baselines;
   classify expected CLI additions and pre-existing harness drift explicitly.
   Independently prove live identity/setup reads and known safety assertions.
   Any unexplained functional regression blocks publication and triggers repair
   or restoration of the previous installed pin.
5. Follow the release-procedure version sweep. Publish main+tag after review;
   normalize both installations to the published tag, regenerate requirements.lock
   and prove each lock alone in a throwaway environment. Align every live pin
   claim. Commit only upgrade-owned clone files, then update the operational-pin
   marker after both installations and verifications succeed.
6. Restore only pause flags introduced by this rollout, retaining existing
   operator pauses. Update Desktop's installation guide for the released kernel.

Evidence directory: `/tmp/cs-kernel-release-043-collaudo` (private business output);
rollback files: `/tmp/cs-kernel-043-upgrade-backup` (private). The automated FULL
harness does not send messages; manual paid ticks and live draft creation are
outside that automated tier and will not be claimed as tested.

Rollout state: pre-upgrade verification active.

### CI prerequisite correction

The published tag's CI run `34496419413` reached gate 53 and failed because
the GitHub runner had no `uv` executable. Its log contains no other failed gate;
the same installed-workspace journey passed locally where `uv` was present.
The workflow now installs `uv` after selecting Python and before the semantic
suite. This is a CI environment correction only: release-tag contents and
runtime code stay unchanged. The corrected workflow must pass on the next push.
