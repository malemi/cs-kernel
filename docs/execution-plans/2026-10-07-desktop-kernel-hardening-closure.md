---
status: completed
created: 2026-10-07
owner: engineering
source: docs/briefs/2026-10-07-desktop-kernel-hardening-closure.md
---

# Desktop/kernel hardening closure

## Approved scope

Follow the closure brief. Installer smoke tests, updater application verification
and module splitting are withdrawn. No release, production changes, clone upgrade,
live inference or live data cleanup. Preserve unrelated concurrent edits.

## Milestones and ownership

### M1 — Repair current executable gates

Owner: engineering, Desktop engine and kernel release-consistency test.

- Repair the charter location resolution without weakening negative proofs.
- Declare `llm.models` parameters. Diagnose minimal dedup errors and preserve
  bounded-preparation policy errors across dispatch.
- Make contract probes hermetic, including sync/IMAP.
- Run kernel release gate and focused Desktop contract regression checks.
- Independent milestone integration review before reconciliation depends on M1.

### M2 — Complete feasible contract evidence

Owner: engineering, Desktop tests/tooling and root evidence records.
Depends on M1.

- Add meaningful cross-owner mutation and stale-view reconciliation checks.
- Exercise one synthetic task lifecycle through actual stdio and WebSocket paths.
- Inventory app/kernel RPC call sites. Compare statically extractable preload
  payload keys with accepted engine params and run app typecheck. Record the
  limits of dynamic return/type-shape inference rather than imply a shared schema.
- Run focused task, memory, cursor, billing/proxy checks and installed-kernel
  WebSocket journeys; run the full kernel suite. Store real outputs outside source.
- Independent milestone review before final documentation closure.

### M3 — Reconcile and close historical work

Owner: lead, root and affected child docs.
Depends on M1 and M2.

- Give every old phase a terminal disposition with evidence or a named existing
  owner. Supersede the historical umbrella with this closure; retain historical
  prose. Separate blocked eternal-operator plan remains blocked.
- Update durable contract docs only for actual changes. Reconcile living context
  and preserve removed historical narrative verbatim in its archive.
- Run doc-end, mechanical verification, independent doc-critic and living shape
  checks, then separate final review. Advance eligible baselines only using the
  completion API. Report any pre-existing completion-record limitation honestly.

## Verification and rollback

Synthetic fixtures and no real credentials/sends. Tests must assert behavior,
not only registry names. Evidence distinguishes source/local execution from live
clones, fleet and packaged artifacts. Retain raw reports and approved artifacts
outside the reviewed tree. Revert only this task's source/test/docs hunks for
rollback; no schema/data migrations or tags are involved.

## Acceptance and remaining obligations

Closure brief acceptance applies. Missing full shared return/type schemas and
live legacy-memory cleanup, if unproved, remain explicit owned obligations;
withdrawn tests cannot be silently reinstated. Record exact commands/results
in the final evidence section after execution, without rewriting approved scope.

## M1 integration evidence

Source changes are limited to kernel `tests/test_release_consistency.py` and
`tests/run.sh`, Desktop `engine/zylch/rpc/usage_queries.py`, `dispatch.py`, and
`engine/tests/rpc/test_contract_boundaries.py`. The charter resolver follows the
index's explicit durable-charter link, retains inline compatibility and refuses
missing/ambiguous/escaping links. Executable company-token and clone authority
checks remain. The release gate passes with 21 negative proofs; extracted step
38 and `bash -n tests/run.sh` pass. A stale ignored `build/lib` cs-pricing template
was retained outside source and removed before the fresh install gate.

Desktop contract tests: 26 passed; privacy/preparation tests: 33 passed.
The missing model-catalog signature is declared. Actual paused/busy preparation
refusals retain code -32020 with a fixed privacy-safe message; unknown task
exceptions remain private. Contract probes block network socket/DNS fallback,
and sync uses an offline fixture. Raw results:
`/tmp/mrcall-ai-kit/hardening-closure/m1/`. Full kernel suite remains running.

## M2 integration evidence

The full kernel `bash tests/run.sh` exits 0, all gates green. Desktop focused
verification passes 234 tests (314 warnings), including installed-kernel
WebSocket journeys, task/dedup/urgency, IMAP cursor, memory eligibility/isolation
and billing/proxy gates. Identity/admission checks pass 19 tests (13 warnings).
Raw outputs: `/tmp/hardening-m2-focused.log`, `/tmp/hardening-identity-tests.log`,
and `/tmp/mrcall-ai-kit/hardening-closure/m1/kernel-full.log`.

Two transport tests pass against real subprocess stdio and the production
WebSocket connection handler on synthetic stores and fixture claims. They prove
foreign-owner refusal, unrelated-row preservation and stale-create refusal after
human close, without paid inference or external services.

Desktop's reproducible `npm run test:rpc-contracts` inventory/check compares
112 engine methods, 82 preload calls, 110 renderer methods and 55 kernel candidate
call sites. Payload keys/required names and argument/declared-return assignability
pass. Four negative proofs reject unknown/missing preload keys, an incompatible
renderer argument and an incompatible declared return. Thirteen duplicate type
declaration gaps are aligned through type-only imports of existing Qonto/mailbox
interfaces and WhatsApp transcription; node tsconfig includes those two existing
declaration sources. App typecheck passes. Runtime imports/behavior are unchanged.

The machine-readable Desktop `docs/rpc-contract-inventory.json` records exact
limits: ten unresolved kernel calls; candidate extraction does not resolve every
Python alias/dataflow; `any`/`unknown` and declared return shapes are not runtime
validation. There is no new shared runtime response schema. The narrow
`.github/workflows/rpc-contracts.yml` is source-wired for relevant PR/push checks;
remote CI execution is not certified by local runs. Browser fixtures, installers,
fleet and live data were not rerun. Raw M2 artifacts:
`/tmp/mrcall-ai-kit/hardening-closure/m2/`.

## Closure state and remaining owners

M1 and M2 are APPROVED by separate fresh reviewers. The workflow-equivalent
Desktop gate passes 39 tests (42 warnings). Documentation closure reconciles the
historical umbrella to superseded and the assessment brief to closed. Installer
smoke tests, updater application verification and module extraction are withdrawn.
The engine living snapshot is condensed from 341 to 112 lines; its original body
is preserved verbatim in `engine/docs/active-context-archive.md`.

Remaining product work is not silently certified by this closure: mnemonic
AC 5/rollout and any proposed live legacy-memory cleanup belong to the mnemonic
harness; the permanent task-first operator stays in its existing blocked kernel
plan; mirrored draft identity stays in its existing active kernel plan. Full
runtime response/value schemas and unresolved dynamic call analysis are explicit
Desktop/kernel harness-backlog items. Source CI is wired, remote execution open.
No release, fleet change, clone upgrade, paid inference or live-data mutation.

The meta-repository completion API refuses initialization on pre-existing
untracked nested checkout `mrcall-agent-free-billing/` (directory/submodule file
binding unsupported). Its baseline is not advanced. Root completion metadata
remains blocked on that kit limitation, not on an uncompleted source fix; child
completion records can finalize after critic/final review. Evidence lives in
`/tmp/hardening-closure-20261007/` and
`/tmp/mrcall-ai-kit/hardening-closure/`. No checker bypass or checkout removal.
