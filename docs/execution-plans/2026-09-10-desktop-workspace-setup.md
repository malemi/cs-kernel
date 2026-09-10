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
