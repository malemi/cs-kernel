---
doc_baseline_commit: baa9b0d7245089c1d046fe67860165746bb19148
doc_baseline_date: 2026-10-11
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: current source capabilities, untagged development and unresolved work.
Durable rules live in the [kernel charter](kernel-charter.md), release history in
[`CHANGELOG.md`](../CHANGELOG.md), and dated operational observations in
[`active-context-archive.md`](active-context-archive.md).
<!-- doc-scope:end -->

## State now

- **Latest release tag: `v0.73.2`; Current HEAD status: tagged as `v0.73.2`.**
  It gives the inventory context hooks 60 seconds each. `v0.73.1` makes a completed run with an incomplete mailbox or assignment read
  exit 0 and raises the inventory context delivery from 48 to 64 slots. `v0.73.0` adds `CS_PRIMARY_BUDGET_USD`, the spending cap per scheduled Claude
  run, to `v0.72.0`, which carries the interactive reply runtime, its agent
  workflow and permission rules, and the discovery schema entry for
  unreadable-mailbox gaps ([changelog](../CHANGELOG.md)). Both maintained clones
  install `v0.73.1` since 2026-11-15: `cs verify-install` matches all 168
  package files on each, and each lock file installs alone. Public provenance remains unmet; no
  public push is performed.
- Reviewed D1/F/P controls are installed; the0.70.1 cache change adds only an
  explicit5m point after the full immutable bootstrap. Compared with0.70.0,
  only the approved executor module changes. No dependency, model, price,
  permission or business guard changes. Both mandatory release suites pass.
  R1/R2 integration reviews and actual normal producer validation pass.
  Previous failures, helper REVISE findings and corrected rollback remain retained.
- The private0.70.1 cohort is FAILED at admission/soft_target_reached after23
  reconciled responses costing8.0846050USD in usage-price estimates. Identity,
  config, tasks, review and discovery completed; the whole workflow did not.
  Cafe/signup never started. All336 recorded PID/start identities are absent,
  both exact fixture enrollments are absent and three owned schedules are held.
- The earlier0.70.0 soft8 failure remains consumed and retained. No attempt is
  resumed or reset. Current inspected5m wire prefixes are identical; two cold
  requests follow approximately20/9-minute tool intervals. Provider-internal
  cache eviction remains unknown. [Longer cache work](briefs/2026-11-01-executor-long-cache.md)
  adds explicit1h support with correct accounting before any further paid run.
- Qualified committed estimates, captured engine delta and retained uncertainty
  total54.0427724USD. The lead selects finite aggregate95, native target10/hard18.25,
  signup2 and at most one new38.50USD cohort under the operator's broader spending
  authorization. Worst-case planning is92.5427724, leaving2.4572276USD. These
  bounds require fresh candidate/admission review before execution. Provider
  invoices and uncaptured/external charges remain unknown; no reserve is released.
- Private E1/E3 and exact E13 engine corrections remain adopted. The repaired
  source case returns three complete human-hold observations and
  `NEEDS_HUMAN_VERIFICATION`; automatic replies stay held. This does not repair
  the historical failed FULL or prove whole-inventory/model acceptance.
- The MrCall operator and signup schedules run since 2026-11-14. An operator
  tick uses the `claude` scheduled host with a pinned model, on the API key, the
  USD 4 cap and the Claude Code build named in its clone's
  `operator-executor.env`; the signup job uses no model. The Café 124
  schedule is held until its first staff mailbox has a working IMAP credential:
  with that mailbox unreadable a tick prepares no draft. The Pydantic executor has not completed a scheduled tick: ten
  recorded runs between 2026-10-29 and 2026-11-01 ended held, out of capacity,
  out of budget or failed.
- The read-only goal
  checker has reviewed isolated positive feasibility and real-failure rejection.
  Missing PID, cost or closure controls also reject. This structural proof grants
  no operational acceptance.

Durable platform contracts remain in the [kernel charter](kernel-charter.md),
[operator runtime](operator-runtime.md), [log diagnosis](log-diagnosis-workflow.md),
[assignments](task-assignment.md) and [draft lifecycle](draft-lifecycle.md).
Historical deployment observations are retained in the archive; this diagnostic
candidate does not re-audit those deployments or grant new send authority.

## Unresolved

- `campaigns/*/flagged` is one of the sixteen list paths of the discovery
  material schema without an element shape, and `cs/review.py` fills it when a
  campaign contact's dossier is escalated: that tick's discovery publication
  fails.
- The Pydantic executor's OpenRouter route refuses a cached run with
  `wire_usage_bucket_binding_differs` when the package is installed in a fresh
  environment. No test covers that route's cache accounting. No maintained clone
  selects the Pydantic executor.
- The native stream check accepts one Claude Code build, 2.1.296
  (`cs/operator_discovery_receipt.py`, `CLAUDE_VERSION` and `CLAUDE_SHA256`).
  On any other build a tick that completes is recorded `stopped||no_result` and
  exits 1. The clones select that build with `CLAUDE_BIN`; the host's default
  `claude` is newer.
- The same check accepts a permission denial only in one shape: a Bash command
  that is not a `cs` command, refused by the auto-mode classifier with the
  reason `[Auto-Mode Bypass]` after a `permission_check_status` cycle
  (`cs/operator_native_composition.py`). A completed tick with any other
  classifier denial is recorded `stopped||no_result` and exits 1.
- The run hook delivers the inventory view in at most 64 context slots
  (`cs/operator_context_delivery.py`). Café 124's view needed 52 to 53 on
  2026-11-15 (about 405,000 bytes); with 48 slots three ticks stopped before
  reading it and prepared nothing: the agent did not page it literally. Each
  slot is a hook process that verifies the whole view; 64 of them on that view
  take about 11 seconds on the scheduled host and have 60 (`HOOK_TIMEOUT`).
  With `v0.73.1`, which left them 10, the client cancelled part of the hooks
  and the tick was recorded `stopped||no_result`.
- A tick that completes while discovery reports an incomplete mailbox or
  assignment read is recorded `stopped||<cause>`. It exits 0 when that read is
  its only defect and 1 when a further health check fails
  (`cs/operator_recovery.py`, `_health_exit`; `cs/operator_health.py`,
  `read_gap_only`). In both cases the owner notice names only the incomplete
  read; the further failed check is in the tick log. Every MrCall tick carries
  `assignment_read_incomplete`, for one thread of its unreadable second account.
- No test drives the fallback route with an incomplete-read verdict.
- The kernel appends `--max-budget-usd` whenever `CS_PRIMARY_BUDGET_USD` is set
  (`cs/operator_recovery.py`, `_run`), so a launcher that also passes the flag
  passes it twice. No clone launcher passes the flag.
- No test covers the refusal of an unusable `CS_PRIMARY_BUDGET_USD` in
  `_run_tick`; the tests of the variable call `_run`.
- The kernel records no command line of a scheduled run. The cap of the
  re-collaudo ticks was read from the process arguments while they ran; Café
  124's two ticks on `v0.73.0` were started by hand with the cron line's
  command.
- Commits `12d7264` and `18da6e7`, the `v0.72.0` release commits and the whole
  of `v0.73.0` and `v0.73.1` have no independent review.
  The scheduled-surface hash ledger of this release is `PENDING_FRESH_REVIEW`.
- The pinned external R7 checker accepts only disabled/5m and hardcodes60USD.
  It cannot accept the reviewed1h/95USD correction through a new artifact index.
  Free private release/adoption may proceed; the new paid cohort is held until
  a supported reviewed acceptance path resolves this contract and interface.
  No checker/service/index mutation or legacy goal completion is performed.
- Protected goal-client inspect exceeds its4MiB response bound; the service has
  no compact inspect request. A stale generation prevents reporting with the old
  token. Final protected acceptance remains unverified; client/service guards
  are unchanged. Both clone harness checks separately retain the pre-existing
  legacy-or-foreign CLAUDE entry violation. The retirement proposal is withdrawn
  pending native-entry compatibility: Cafe has an ancestor CLAUDE file. Both
  bootstrap imports remain intact. No baseline advancement is claimed.
- The existing completion record accepts current lead startup attestation. Its
  remaining obligations include refreshed documentation/focused evidence, M5 and
  final review. Historical workflow-hash refusals remain retained; no reset or
  migration is performed. Baseline advancement and runtime acceptance stay open.
- Genuine strict BOTH-clone FULL and signup remain required. Publication and
  public Git installation proof await separate explicit authority. Failed runs
  and uncertain charges/effects remain retained; a component read certifies no FULL.
- Recurring peer ingestion history and mutable scheduling remain unknown.
  E13 repairs one exact source counterpart; it grants no automatic business
  authority or recurring scheduling change.
- Historical SELECT, empty-fixture and discarded helper exceptions remain
  UNKNOWN. Later success and controlled reproductions cannot recover missing
  production observations. Time ceilings and economic quotas are separate.
- [Assignment recovery](execution-plans/2026-10-15-ordinary-assignment-recovery.md)
  retains failed V27 and separate permission/ordinary acceptance. Earlier V14,
  scoped Café draft and R9 proofs certify only their respective cases.
- OpenCode diagnosis selection and conditional-instruction reading have qualified
  native coverage. Native Gmail edits, wide dossier latency and live unanswered
  parity retain their owners; incomplete authority continues to hold named roots.
- The [contextual-email guard](execution-plans/2026-10-08-contextual-email-assignment-guard.md)
  remains undeployed; newer explicit bindings require stronger policy, while
  compatible released workflows retain current guards and separate launch limits.
- Engine/classifier failover, SIP/customer trunks, PBX, secondary-account onboarding
  and factory update/help debt remain separate work.

## Next

1. Restore the held Café 124 schedule once a scheduled tick completes its work
   on this tag.
2. Publication needs FULL on both clones. Its runtime policy binds an earlier
   system and nothing regenerates it. The changelog lists the two gates that
   fail at the tag.
3. Require actual M5, documentation critic and separate final review. Baseline
   and protected goal acceptance remain open until their prerequisites pass.
