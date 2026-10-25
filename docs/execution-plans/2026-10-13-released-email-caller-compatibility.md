---
status: completed
---

# Released email caller compatibility

Approved brief: [released email caller compatibility](../briefs/2026-10-13-released-email-caller-compatibility.md), SHA256 0fbce445e99ccf311eefab82f612e310653fb5e0ba93d2f5409576809b10c881; fresh APPROVED framing /tmp/mrcall-ai-kit/exact-draft-live/released-caller-compatibility/brief-review-r2.md.

## Ownership and dependencies

Kernel owns cs/cli.py, cs/rpc.py, the cs-operator template and its two canonical clone skill files, tests/test_capabilities_skill.py, and narrowly affected tests/test_contextual_email.py, test_task_assignment.py, test_draft_reply.py, test_draft_send.py and test_engine_error_exit_code.py as necessary. Preserve all unrelated AST definitions/source bytes. No engine changes. Parent owns consumer binding, cache-writer correction, sole live execution and cleanup. Prior r3 is FAILED with natural native exit0 but missing tasks phase, three capability holds and no reply; cleanup independently restored original schedules with no owned processes. No historical credit or reseal.

## M1 decided implementation

Compare four touched callers with public v0.52.0 and exact 672d702 delta. In cmd_chat, remove unconditional require_contextual_email_policy=True; supplied new context flags still produce full email_context and negotiate v1. In rpc.chat, separate legacy assignment negotiation from contextual negotiation: one capability request if either needed; require assignment_draft_policy=1 for assignment_thread_key, require contextual_email_policy=1 only for email_context or explicit require flag. Preserve full context/version when requested; no catch-and-retry or dropped fields.

For ordinary draft-reply with only its released thread flag, send assignment_thread_key and assignment_policy_version=1, without a newly invented contextual binding. If new --source-id is explicitly provided, retain full contextual binding and stronger negotiation; unsupported engines refuse before draft generation. For ordinary exact-ID draft-send, restore released unconditional current task_assignment.guard and rpc.chat exact approval predicate without auto-added new email_context. Preserve full-ID lookup, one matching approval and exact Sent verification. Explicit direct RPC contextual draft binding remains strict. No new command flags or per-company switches. Campaign stronger negotiation stays unchanged.

## M2 ordinary tasks workflow

Kernel worker owns cs/templates/project/.claude/skills/cs-operator/SKILL.md.j2 and the corresponding .claude/skills/cs-operator/SKILL.md in both maintained clones. Add one explicit step after effective configuration and before triage: execute `.venv/bin/python -m cs tasks --json` in its own native Bash call, read its actual complete result and preserve failure/held meanings. The triage skill already requires that primary tasks read; make bootstrap ordering unconditional so the native six-phase contract is actionable. No injected receipt, runner pre-read or oracle waiver.

Apply only that exact shared insertion to both canonical files, preserving company bytes and modes; verify six Claude/Codex/OpenCode aliases resolve those two files. Extend the known guidance delta admission in test_capabilities_skill.py narrowly to this exact step and prove unknown edits and identity/authority changes still refuse. A fresh M2 source review covers both template and rendered hunks before clone insertion or package adoption. Actual next native run must emit the tasks tool use/result; software guidance checks cannot earn that phase.

## Verification and fresh deployment

Meaningful transport tests exercise ordinary legacy generic chat on assignment-only/no-contextual engine; legacy scoped draft-reply accepted ONLY with exact thread and assignment policy; no assignment capability refuses; new supplied chat context/draft source/direct RPC explicit requirement all refuse unsupported engines before chat. On a v1-capable test endpoint all explicit context/version fields remain intact. Exact-ID CLI sends retain original guard/approval/Sent proof; wrong/duplicate approvals and missing thread/held assignment refuse. Compare actual legacy frames to released contract, not merely successful mocked return.

Run focused affected checks, then bash tests/run.sh. Fresh M1 source review requires actual results and bounded diff preserving previously approved intake/notices/readbounds/discovery/exactprovider behavior. Freeze a new immutable complete package and prove only reviewed cli/rpc and cs-operator template deltas versus d3a96. Prepare exact local adoption using the approved atomic exchange script under existing four idle locks, new exact prior/candidate inventories, conditional rollback, ordinary no-PYTHONPATH imports and full outside preservation. A fresh deployment-input review must approve changed manifests before effects; independent actual readback before dependent live work. Parent then pins the exact new source and obtains fresh combined integration review. No engine capability alias, persistent enrollment activation or guard bypass.

## Actual acceptance and documentation

The original genuine floor remains: fresh provider originals, deterministic ordinary intake, natural MrCall exact-thread reply, Cafe draft/no-send, signup policy, all canonical phases including tasks, acknowledgement/no-loop, natural terminals and independent cleanup. Native workflow must actually issue required tasks read; never manufacture its phase or waive it. Keep source/docs frozen throughout the run and use bytecode-disabled observers.

Reconcile task-assignment/operator-runtime and living contexts to distinguish released compatible calls from explicit unsupported contextual-v1 operations; add route, retain historical narrative verbatim and local/public provenance. Invoke doc-end/doc-critic and separate final review before baseline advancement. All required outcomes remain pending until actually observed; release requires separate authorization.

## Rollback

Clean owned live work first. Restore only unchanged owned package postimages using captured preimages and existing locks; preserve earlier rollback directories and concurrent work. Retain all failed runs and source/readback evidence. Never reactivate the separate unreleased engine migration as an implicit fallback.


Amended brief approval: `/tmp/mrcall-ai-kit/exact-draft-live/authority-recovery/brief-review/report.md`, SHA256 `c31540e3eb44691cc925631bf840b37e8e46d060f8fde4f122c992d54a13bc2b`; amended brief SHA256 `bf0a4f80d00095bc43f241236e4e60879e0f555c410781ea37069a8883e586c1`.


## M4 — recover current authority after transient UNKNOWN

R6 is a retained actual failure: natural MrCall exit0/all six phases, no reply or draft and incomplete native receipt inspection; Café/signup did not run. Sole owner independently confirmed cleanup, exact original 759-byte crontab, no owned processes/markers/registries and equal 1053-entry before/after source inventory; the durable failed candidate is preserved. No engine/source change is justified for the original peer transport cause, which is unknown.

Worker ownership is exactly `cs/templates/project/.claude/skills/cs-operator/SKILL.md.j2`, `cs/templates/project/.claude/skills/cs-triage-mail/SKILL.md.j2` and the existing `tests/test_capabilities_skill.py` guidance-delta checks. Lead owns both amended traces and affected contracts/current state. After fresh M4 source approval, the same worker applies only the two approved shared hunks to each clone's canonical `.claude/skills/<skill>/SKILL.md`; all twelve Claude/Codex/OpenCode aliases must resolve their canonical unchanged company-specific files. Preserve company voice, mode/send grants, budgets, every deny, unrelated guidance and existing file modes. No edits outside these owned source/test/canonical files.

Clarify snapshot time in both workflows. Preserve every discovery hold, then execute the ordinary exact-thread assignment status once for a candidate. Only a later genuinely complete peer-merged projection of that exact actor/source owner/company/root, with exact original RFC identity in `current_message_ids`, `state=normal` and `hold_auto_reply=false`, may replace that earlier incomplete UNKNOWN observation for current eligibility. Preserve the earlier failure in the report. Do not rerun discovery or add retries. Current unknown/incomplete/malformed/wrong-identity status, assignment candidates/active assignments/conflicts/closed-covered work and independent address/mailbox/suppression/dedup/dossier holds refuse. Read the actual original body and continue the existing mode-authorized engine path, with ordinary draft/send guards rereading current authority. This applies to ordinary work as well as protected originals; no fixture exception or stale receipt grants eligibility.

Move the complete inspection obligation before protected-original eligibility. Use the existing capture path and exact bound receipt, explicit byte length and consecutive 8192-byte chunks with 8064-byte stride through EOF. Keep a contiguous inspected range; never jump from the first rows to tail summaries or assume unread middle rows are harmless. Missing/clipped portions mean incomplete discovery and no claim of complete inspection. Inspect all structured discovery/held sections; the quoted duplicate output is not a second interpretation. No custom interpreter, pipe, injected report or source/permission change.

Extend existing rendered-guidance/admission checks narrowly for these two exact shared changes, including positive restoration of the ordinary UNKNOWN→new complete normal rule and explicit negative preserved-human/current-UNKNOWN/wrong-original constraints. Existing unknown-edit/identity/authority changes must still refuse; prove exact canonical/alias bytes and company rules unchanged. Run focused affected checks and `bash tests/run.sh` once; retain actual failures and repair only demonstrated in-scope problems. Fresh M4 source reviewer compares the complete bounded diff and immutable before/after ownership.

Freeze a new complete kernel candidate (116 files, only the two approved template files differ from adopted 7efb), prepare exact package/canonical evidence and use the already approved atomic exchange script with fresh two-clone preimages, four idle locks, unique rollback directory and fresh input approval. Independent actual ordinary imports/full inventories/outside preservation precede parent combined review of the new kernel binding and unchanged engine families/strict observer. Parent owns literal binding/provenance changes and sole new FULL; no historical R6 promotion or manual test steering. Final acceptance still requires all three native jobs, original body, actual reply/draft-no-send/signup/ACK/no-loop, complete discovery inspection, source stability, natural terminals and independent cleanup. Lead closes documentation/critic/separate final review; public publication remains separately authorized.

## Current hosted development acceptance

Genuine r9 (`ecc64a8400e35d6f699a9c193ba5e399`) passes the unchanged strict
seven-check matrix on the actual installed kernel `9857f1bb…` and repaired
six engine runtimes. MrCall sends the correct 212 reply; Café creates exact
engine draft `71589012-ba68-4e7d-8e31-f45df722c349` with result311 and one
provider mirror without sending. Both operators terminate naturally with exit0.
Signup's documented policy passes with legacy exit1, not three zero exits.
The new Sent source is complete AUTOMATIC, root authority complete NORMAL/unheld,
and the actually received reply is classified automatic with no additional
received/sent/provider-draft/engine-draft effects. No manual intake or substituted
model output supplies native generation. Cleanup restores exact cron759ab3,
removes owned enrollments/markers/processes and preserves six runtimes plus Qonto.

The original signed result and complete pre/post1053-object tested source are
retained before documentation edits at `/home/mal/.local/share/mrcall-operational-evidence/2026-10-14/after-repair-full-checkpoint-guard-r9`. Retention manifest SHA-256:
`0701b581b092c6c0360d159dc36cedd3bbe949e33e6ec5c9b229b11ce08b8482`.
This is `development_hosted` acceptance; public installer/release and native
Gmail browser/mobile/API edit/send preservation remain unverified. Automatic
reconciliation remains off. Earlier failed runs stay failed and unsigned.
Operational acceptance remains separate from checker-governed documentation
completion and public release.
Independent operational APPROVED: `/tmp/mrcall-ai-kit/r9-acceptance-verification/report.md`,
SHA-256 `7de3884807f781e8a0aa5391113c6652ba059f378d6fe764a3aee124492435bc`.
Actual native inspection covers both complete physical receipts through EOF.
