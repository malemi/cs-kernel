# Close the historical Desktop/kernel hardening workstream

## Intent

Finish the bounded, still-applicable engineering checks from the August 1
Desktop/kernel assessment and close its obsolete umbrella plan with an honest
item-by-item disposition. The operator requests completing everything feasible
and explicitly withdraws installer smoke tests, application verification in the
daemon updater, and splitting oversized modules. None of those is a delivery
requirement of this workstream.

## Scope and decisions

- Repair the current kernel release-consistency check after the charter moved
  from the root index to `docs/kernel-charter.md`, retaining its positive and
  negative semantic checks.
- Repair Desktop's missing `llm.models` parameter declaration without weakening
  the registry-wide check. Investigate the two dedup minimal-payload failures:
  preserve bounded-preparation admission and distinguish legitimate policy
  refusal from internal error. Keep the contract tests offline, including IMAP.
- Complete feasible task ownership/reconciliation and transport contract checks
  on synthetic profiles. Check real kernel-to-engine journeys with the installed
  kernel; add missing regression checks where justified by the old plan.
- Assess the remaining preload/type-shape inventory requirement against the
  current app. Complete bounded mechanical coverage when possible; explicitly
  retain any unproved type/return coverage rather than claiming name agreement
  proves full schema equivalence.
- Recheck existing memory eligibility, company isolation, task policy/cursor and
  billing/identity tests. No live data cleanup or backfill is authorized or needed
  for administrative closure.
- Reconcile each old phase as verified, superseded by later delivery, withdrawn
  by the operator, or transferred to an existing named workstream. The permanent
  task-first operator redesign already has its own blocked kernel plan and must
  stay explicit there; do not implement a new unattended operator as a side
  effect of closing this reliability assessment.

## Constraints

Preserve concurrent harness changes and all unrelated working copies. No releases,
commits, pushes, live sends, deployments, clone upgrades, paid inference, live
credential reads or live data mutations. Preserve RPC compatibility except the
intended rejection of unknown `llm.models` parameters. Do not mark unverified
runtime or historical acceptance as newly verified. Retain old narrative as
historical evidence while making its terminal disposition unambiguous.

## Acceptance

1. Kernel release-consistency and task verb checks pass against current source,
   with meaningful negative proofs retained.
2. Desktop boundary tests have zero open methods and no unexplained internal
   failures on advertised minimal payloads. Network-backed dependencies are
   isolated in synthetic tests, without weakening production admission.
3. Focused task, proxy, memory, billing and real kernel/WebSocket checks pass;
   ownership/refusal and transport claims are supported by real outputs.
4. Old plan no longer presents withdrawn work or already-superseded deliveries
   as pending. Any genuinely uncompleted requirement has a clear named owner
   and is not mislabeled built.
5. Documentation closure and independent final review report actual verification
   and limitations. Release remains outside scope.

## Assumptions

This is closure of an old reliability workstream, not authorization to build the
separate blocked permanent-operator product. If evidence shows a remaining change
requires redesign or a public contract change beyond the narrow RPC declaration,
keep it in its owning workstream with the precise dependency and report it.
