---
status: completed
---

# Reconcile the shared repository

Brief: [scope and acceptance](../briefs/2026-10-01-repository-reconciliation.md).
Brief gate: APPROVED by a fresh reviewer on 2026-10-01.

## M1 — inventory and preservation

The lead owns the integration; reviewers are read-only. The original index,
all 226 nonignored files, HEAD and dirty status are saved externally. Backup
ref `backup/reconcile-20261001T134452Z` and its verified standalone bundle
retain snapshot `46a79fe`. Recheck the saved manifest before primary-worktree
mutation. The eighteen original dirty paths resolve initially to seven exact
remote matches, five exact matches to published ancestor `74ea403`, and six
unique files. Review unique diffs and all superseding changes before accepting
their disposition. Record all paths and the two local commits in a durable
inventory. Gate: reviewer approves the full classification with evidence.

## M2 — integrate on published history

Create an isolated integration worktree from current `origin/main`. Merge the
local branch so both local commits remain ancestors. Resolve documentation
conflicts by retaining published acceptance records and adding verified session
facts; update the living context to describe the integrated tree.
Keep current remote recovery, manifest, cron permissions and tests, rather than
reintroducing the five proven older snapshots. Integrate the reviewed charter
corrections and runtime clarifications. Preserve the five unique pricing/triage
files on a dedicated work branch; merge the sixth unique file, runtime
documentation, into main. Work-branch source must be compared to the
original snapshot and its acceptance remains explicitly incomplete. The branch
must retain the original pricing/triage text, including mixed send guidance,
without publishing unreviewed workflow changes as production-ready.
Gate: integration review covers conflicts and exact preservation evidence.

## M3 — verification and primary checkout

Run the full kernel suite on the integrated tree, focused rendering for the
preserved work branch, documentation mechanics, and a separate final review.
Classify any failure against the published base; repair integration-caused
failures and do not label failing gates green. Commit coherent integration and
documentation updates. Only after all original files have proven destinations,
compare original-worktree content hashes and HEAD/index to the saved snapshot
plus known brief/plan additions. Any unexpected change triggers a fresh diff
and preservation before continuing.

Remove only the exact inventoried working copies now retained in Git, then
fast-forward the primary branch to the reviewed merge. Preserve ignored files
and other worktrees. Recheck status, ancestry, inventory and tests as needed.
Publish main only by an ordinary fast-forward push after verifying the remote
has not changed; retain incomplete work on the named local branch and bundle.
Record the exact main, remote and work-branch commits in the final report.

## Rollback

The original branch commits, snapshot ref and independent bundle survive every
step. Before the main fast-forward, discard only the isolated candidate if its
review fails. After the fast-forward, restore the original snapshot in a new
recovery worktree if necessary; do not force-push or erase concurrent history.

## Completion evidence — 2026-10-01

- Fresh brief, plan, inventory, integration and final reviews returned APPROVED.
- Integrated merge `2be7a44` retains local commits `43d17fd` and `7484e9f`
  and published base `d16e12b` as ancestors. The primary checkout was
  fast-forwarded to that merge and the ordinary push to origin/main succeeded.
- `bash tests/run.sh` exited 0 with `RESULT: all gates green` on the integrated
  tree. Documentation mechanics passed; the living context shape passed and
  semantic review found zero STALE reconciliation claims. Historical live
  probes and customer reply quality were not independently reproduced.
- Immediately before cleanup, all 226 original file hashes, original HEAD
  and index matched the saved snapshot; only the three known trace additions
  existed, and those originals were also backed up. Exact-path cleanup and
  fast-forward left the primary checkout clean.
- Five unfinished pricing/triage files remain byte-identical to the initial
  snapshot on `work/pricing-triage-20261001` at `d16e3e5`; its focused render
  check passed (34 templates, three configurations). Its acceptance stays open.
- Standalone `snapshot.bundle` and `reconciled.bundle` are retained under
  `/home/mal/.local/state/cs-kernel-reconcile/20261001T134452Z/`.
  The initial bundle was independently restored and all 226 hashes verified.
- Keyword coverage was 66/68. Missing literals `compiled` and `send-enabled`
  are vocabulary variants of documented instruction compilation and send mode.
  No new release tag or clone upgrade was part of this reconciliation.
