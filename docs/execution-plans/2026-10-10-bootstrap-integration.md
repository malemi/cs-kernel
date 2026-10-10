---
status: completed
---

# Local bootstrap integration

Approved intent: [brief](../briefs/2026-10-10-bootstrap-integration.md).
Lead owns integration, documentation reconciliation and local promotion.
Independent reviewers own brief, plan, integrated milestone and final gates;
the delegated critic verifies documentation without repairing it.

## Ordered work

1. Save original main SHA and exact digests of its 13 dirty tracked files.
   Keep the original checkout unchanged until final approval. Run the full
   pre-integration suite in the clean integration worktree.
2. Merge bootstrap `83ebb58` into integration branch based on main `eb6dc1a`.
   Resolve only docs/README.md, docs/active-context.md and its archive.
   Preserve both routing entries and each parent's archival additions verbatim.
   Keep current state concise; archive superseded bootstrap status verbatim.
   Production source and tests must equal Git's automatic merge result except
   the explicitly approved stale teaching-byte regression described below.
   Preserve exact teaching/compiler bytes; require exact RPC module AST
   equality outside chat against its historical base, including publication
   and read-only transport. Guard chat is checked against current main.
   Add only the ast import and adapt that one regression method; preserve all
   remaining test, fixture and auditor bytes. Record the initially failed run.
3. Verify full kernel suite and bootstrap render/fixture checks. Compare canonical
   host templates and bootstrap read routes with bootstrap parent, retaining
   proof that the main-side guard is unchanged. Historical native 19-case
   acceptance stays attached to its frozen parent. Changed relevant routes
   require repair/review and necessary fresh evidence before continuing.
4. Obtain independent M1 integration approval with actual command outputs.
   Reconcile affected docs, run doc-end mechanical and doc-critic shape/semantic
   gates, then separate final review. Checker alone finalizes baseline and this
   plan's active-to-completed transition. Commit the reviewed merge locally.
5. Verify both parent ancestry and a clean committed integration tree before
   promotion. Recheck main SHA and dirty-file digests. Switch the original dirty checkout
   to `work/preserved-main-bootstrap-20261010`, requiring identical file bytes
   and status. Free main can then be checked out in the integration worktree
   and fast-forwarded to the reviewed merge with its separately verified
   post-commit documentation closure only after preserved checkout equality
   passes. The final read-only audit repeats ancestry,
   clean-main and preserved-checkout checks. If an unexpected concurrent edit
   invalidates that audit after promotion, retain both branches and evidence,
   report the discrepancy and do not rewind or overwrite any checkout.

Dependencies: both reviewed parent tips and the isolated integration worktree;
kernel virtualenv remains supplied by /home/mal/hb/cs-kernel/.venv.
Evidence is retained outside source at
`/home/mal/.local/state/codex-evidence/bootstrap-integration-20261010`.
No production repair, external write, tag, push, engine merge or clone rollout is
part of this plan. Never stash, reset, drop or overwrite the preserved edits.
If a pre-promotion gate fails, main stays at its saved tip; retain the candidate and evidence
for correction. If promotion ref checks fail, stop promotion and preserve both
checkouts without changing shared refs.

## Results

The clean main precheck exits 0 (`precheck.log`, actual session 58508).
Both parents merge without a production conflict; three documentation conflicts
retain both routing entries, current guard/sharing state and all archival bytes.
The archive proof and owned insertions are in the external evidence directory.

The first integrated suite exits 1 solely on the stale whole-rpc.py regression;
its original failed log remains `integrated-suite-failed-before-repair.log`.
The brief and plan amendment reviews approve the one-method test adaptation.
All other test, fixture, auditor and production bytes remain unchanged by the
repair. No native observation or verdict is rerun or recredited.

The corrected full suite exits 0, `RESULT: all gates green`, actual session
70691 (`integrated-suite-fixed.log`, `integrated-suite-receipt.json`). All 80
fixture regressions pass (session 61659, `fixture-fixed.log`). Twenty canonical
bootstrap/render/update checks pass (session 43045, `render-focused.log`).
The independent equivalence script passes 21 checks: exact canonical templates
and bootstrap discovery routes, current-main chat/assignment guards and the
automatic production merge tree, with only the approved unit-test exception.
`integration-equivalence.json` owns these results; original frozen-parent native
runtime and configuration qualifications remain in the bootstrap plan.

M1, integration documentation closure and separate final approval are complete.
Merge commit `fd04b47` retains both reviewed parents. Main promotion requires
post-commit documentation closure and the preservation checks in step 5.
Original main remains at its saved tip with exact13 file/status/diff digests
captured in `preserved-main-before.json` and its recoverable binary patch.
The checked promotion sequence in step 5 remains mandatory after these gates.
