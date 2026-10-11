---
status: active
---

# Bootstrap release and requested clone adoption

Approved intent: [brief](../briefs/2026-10-11-bootstrap-release.md).
Lead owns release/source equality, original-state preservation, publication and
MrCall upgrade. Independent gates review the brief, plan, release milestone,
documentation and final result. Evidence remains outside source at
`/home/mal/.local/state/codex-evidence/bootstrap-release-20261011`.

## Ordered work

1. Preserve exact dirty tracked/untracked original clone files and status,
   installed package/pin, permissions, cron wrapper, custom launcher and schedule.
   Verify candidate source matches reviewed `83ebb58` apart from the already
   reviewed clone README. Compare send/auth/campaign/permission bytes to v0.51.0.
   Copy only reviewed README surfaces from `a3a3bc6`; no new runtime feature.
2. Build isolated current-clone fixtures from both maintained manifests. Install
   the release candidate in separate environments, refresh templates preserving
   authored guidance and compare effective settings/help/permissions. Required
   read-tier acceptance covers authenticated JSON identity, capabilities, tasks,
   thread and prior-contact reads, plus connection-failure and bootstrap
   rendering/update checks on both fixtures. Additional business/campaign/Drive
   reads use bounded diagnostic calls. Wide dossier/review reads are retained
   diagnostics: compare bounded baseline latency and exact unchanged command,
   RPC and dependency behavior; do not describe timeout/termination as a pass.
   Their existing full-mailbox latency workstream is outside this runtime change.
   Never run paid ticks, generation or customer sends. Keep the old July harness
   red evidence separate; declare only the scoped current read-tier result.
3. Reconcile release documentation with actual state; retain superseded current
   narrative verbatim in the owned archive insertion. Run the full kernel suite
   on the clean, committed release candidate. Obtain M1 approval before tagging.
4. Follow the executable release procedure: version/changelog/tag-state commit,
   immediately create v0.52.0, full suite at the tag, then first post-tag commit
   with immutable target and untagged state. Sweep every version claim. Never
   move/delete an existing published tag; on failure retain evidence and stop.
5. Merge release metadata into main, preserving exact main guard/runtime bytes
   and its separate unreleased documentation. Resolve only documentation
   conflicts; main runtime must equal saved a3a3bc6. Run applicable integrated
   checks. Perform doc-end and separate final review before authorized publication.
   Push main and the exact immutable release tag only after all release gates.
6. Upgrade only mrcall-cs through cs update at the published tag. Keep local
   harness/AGENTS and operator guidance on prose conflicts. Refresh cs-help and
   onboarding only after reviewing any local differences; preserve their local
   additions. Security files must retain prior effective authority/custom denies.
   Verify company bytes, schedule, custom launcher and unrelated edits unchanged.
7. Regenerate requirements.lock from the installed tag, prove lock-only rebuild,
   authenticated identity and applicable read-tier checks. Verify all three host
   paths resolve canonical new skills. Align owned version claims without
   overwriting prior clone edits. Close clone documentation with the harness;
   commit only isolated upgrade deltas. Do not commit pre-existing dirty work.
   Keep the shared operational-pin marker at its existing value: Café 124 is not
   upgraded. Record asymmetric clone pins explicitly.

## Failure recovery

Before publication, failed tests or changed original-state digests stop dependent
steps; preserve branches and evidence. After publication, no tag rewrite. If the
clone fails adoption, use the old v0.51.0 pin and saved lock via supported
installation, restore only owned upgrade deltas, and verify original dirty files
again. Do not reset/stash user work or alter pause/scheduling/send posture.

## Results

The clean pre-release candidate `3e93509` passes `bash tests/run.sh` (exit 0;
`pre-release-suite.log`, final all-gates-green result). All runtime modules
except the explicit CLI WebSocket exception import equal v0.51.0; sending,
authentication, campaign, settings and cron bytes are unchanged. Original clone
bytes and schedules match the saved pre-work snapshots. Fixture new skills and
supporting files resolve canonical bytes on all three host paths.

Scoped read-tier checks pass on both fixtures: authenticated JSON identity,
capabilities, tasks, thread and prior-contact reads; bounded campaign and Drive
reads also pass. Installed dependencies and dossier/review ASTs match v0.51.0.
Both baseline dossiers exceed a 60-second diagnostic bound; the candidate
MrCall dossier reaches 600 seconds, while Café 124 completes in 133.5 seconds.
Wide review termination and legacy default-whoami JSON-validator failures remain
failed diagnostics, not passing acceptance. New skills have 24 canonical file
paths across three hosts. The bounded verification plan has separate approval.

Both isolated installed candidates pass the real localhost connection-failure
check and ten fresh-interpreter error-family/non-connection cases; logs are
`mrcall-cs-connection-failure.log` and `124-cs-connection-failure.log`.

Publication and MrCall adoption remain pending; at-tag checks pass. Raw fixture
results and preservation proofs are in `fixtures/` under the retained evidence.

### M2 — Immutable tag and main integration

Both full suites exit 0, including the exact release tag. `v0.52.0` resolves
to `3c0e78c533db91a17bd390657de58cf6931b5c73`; its first post-tag commit binds
that immutable target. Main integration `bf6ca918c3b07630fd3cd73101581781670f89ee` retains the exact
`cs/` tree from `a3a3bc6`; the strengthened email guard remains unreleased and
is absent from the tag. Release consistency and mechanical gates pass on main.
Tag and release version claims are classified in the retained sweeps. Publication
and actual MrCall adoption remain pending their ordered gates.
