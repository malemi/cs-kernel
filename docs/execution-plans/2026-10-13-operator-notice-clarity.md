---
status: completed
---

# Clear scheduled-operator notices

Approved brief: [intent and acceptance](../briefs/2026-10-13-operator-notice-clarity.md).

## Ownership and dependencies
Lead owns `cs/operator_recovery.py`, a neutral notice-rendering module if useful, `tests/test_operator_recovery.py`, notice coverage tests and affected runtime docs. Existing unrelated working-tree edits are preserved. One implementation milestone M1; no dependent implementation milestone.

## M1
1. Inventory all supervisor status/reason combinations, including queued older notices.
2. Render subject, outcome, explanation, next attempt and resolution independently of SMTP. Successful primary/backup notices are informational. Stopped runs use `ACTION REQUIRED: scheduled assistant run stopped`, without claiming a permanent service outage.
3. Give every reason a concrete user/admin remedy. Unknown failures direct administrators to the scheduled-run log and users to share the email with their administrator; advise reviewing completed actions before manually retrying. Payment/limits/configuration/credentials/permissions have distinct remedies. Separate primary timeout from unknown failure using existing watchdog evidence; describe both five-hour and weekly quota limits without inventing reset time. Preserve execution, dedup signature/queue, recipient and credential masking.
4. Verify complete plain/HTML output, legacy queue rendering and severity. Use real child-process supervisor checks to prove no immediate replay, recovery transitions, queue retry and permission refusal. Capture sample emails through a local SMTP substitute; never send mail.
5. Fresh M1 integration review before closure.

## Verification
Pre-change `.venv/bin/python tests/test_operator_recovery.py` passes. After edits run focused notice/recovery checks and `bash tests/run.sh`, retaining actual output. Source review checks all notice callers and user/admin instructions. Runtime/provider deployment is outside local acceptance.

## Documentation and closure
Update `docs/operator-runtime.md` notification contract and add local-unreleased state in `docs/active-context.md`; preserve superseded prose verbatim in archive when replacing it. Run doc-end mechanical and doc-critic (including unchanged boundaries and living-context shape), completion pre-review gate and a separate final reviewer. Intended status transition: active to completed only through finalization.

## Rollback
Revert this task's notice rendering, reason selection and documentation edits together; do not remove or rewrite the persisted notice queue. No schema migration or deployment is involved.


## Local acceptance evidence

- Brief: `/root/notice_brief_review` APPROVED; plan: `/root/notice_plan_review` APPROVED.
- M1 integration: `/root/notice_m1_review` APPROVED; affected recheck covers concrete log location and retained backup account identifiers.
- `tests/test_operator_notices.py`: 20 captured emails cover all stop reasons, unknown/legacy reasons, informational outcomes, remedies, partial-work warnings, HTML parity and persisted queue delivery.
- `tests/test_operator_recovery.py`: real child processes verify retry eligibility, permissions, transitions, watchdog, notice deduplication, failed-SMTP retry and an unreported backup model retaining masked account identity.
- Complete MIME samples and raw check/review results are retained at `/tmp/operator-notice-clarity-evidence/`. No real mail is sent; deployed clone/provider delivery is outside this acceptance.
- The first full-suite run encountered stale generated build templates. That generated directory is preserved outside the source tree; a subsequent isolated installation verifies all 50 template paths and bytes. The final full-suite result is retained in `full-tests-final.log` in the evidence directory. The intermediate clean-build run installed source before the final log-location addition, so its capture test correctly rejected that older installed renderer; the final run checks the frozen updated source.
- The shared-worktree final suite passes notice tests but fails `test_draft_state.py` while concurrent draft-identity development modifies Gmail reconciliation. That work is outside this notification task. The isolated baseline plus this task's source/test changes is checked separately; complete output is `full-tests-isolated.log`.
- Closure uses completion task `operator-notice-clarity-20261013`; final checks and reviews must pass before the intended completed transition.
