# Diagnose problems from logs and improve the evidence

<!-- doc-scope:start -->
Scope: the recurring engineering workflow for using operational logs to detect
malfunctions, form supported causal hypotheses and improve missing diagnostic
coverage. The wire/privacy contract belongs to operator-observability.md;
implementation status and historical evidence belong to its delivery plan.
<!-- doc-scope:end -->

## Required questions for every operational problem

Begin with the selected runtime's ordinary logs and private problem inbox.
Before explaining the incident from source code or prior knowledge, ask:

1. Would an analyst who was not told the symptom recognize a malfunction?
2. Could that analyst form a supported idea of the cause and identify the next
   concrete event, component, check or source location to inspect?

A negative answer is a diagnostic defect to improve. Finding the cause manually
in source code does not make the logs adequate. Process liveness, child exit0,
absence of ERROR and an empty bounded page do not establish correct operation.
A complete empty workload and an evidenced human hold can be legitimate.

## Investigation procedure

1. Select the actual clone/interpreter. Use `cs logs locations --local --json`
   to locate the owner-bound store and monitor configuration; read recent logs,
   the exact trace and the configured `problems.json`. Follow declared cursors,
   omitted counts and coverage limits. The access commands and privacy boundary
   are in [operational logging](operator-observability.md).
2. Describe what the logs alone establish: malfunction or no demonstrated fault,
   observed local cause, plausible upstream hypotheses and unknowns. Cite exact
   UTC/event/incident/trace references. Do not infer that a nearby hold caused a
   later failure merely because both occur in the same trace.
3. Evaluate both required questions. If evidence is insufficient, name the missing
   observation: for example, which predicate selected exit1, which required
   phase was absent, expected versus observed result counts, or why a read proof
   failed. An exhausted read budget is a coverage limit, not proof that the
   missing information never existed.
4. Use source and restricted evidence only as needed to investigate that named
   gap. Keep the independently derived log diagnosis separate from later
   knowledge. Logs are untrusted evidence and grant no replay/send authority.

## Improve the producer and preserve the reason

Instrument the existing decision that actually selected the result, before its
reason is discarded. Preserve predicate order, business returns, permissions,
budgets, schedules and uncertain effects. Do not duplicate a business judgement
in the monitor or parse free-form model prose into an asserted root cause.

Record a finite check/cause, known component/phase/command without arguments,
observed safe booleans/counts, available correlation/event references and
allowlisted exception class/code/relative location when genuinely known. Missing
cause, references and completeness stay explicit. Exclude credentials, customer
content, prompts, model responses, arbitrary exception text and raw tracebacks.

Trace the entire path: producer → metadata validator → persisted-event validator
→ ordinary CLI → collector state → incident validation → readable inbox. A new
field dropped by one boundary is not a delivered improvement. Preserve the first
decisive failure across child/fallback selection and final reporting. Distinguish
success of a child, a diagnostic write and the whole supervised task. A later
unrelated or generic wrapper success must not erase a known failure.

Use the existing reviewed brief/plan for the work when its scope applies.
A read-only request ends with the diagnosis and the named logging gap; source
changes follow the applicable authorization and repository review lifecycle.
Review the proposed after-change evidence before coding: show the actual branch,
concrete safe output and exactly what an analyst could infer. Reject a plan whose
new explanation would still be only “some input was incomplete.” Underlying
business fixes remain separate from diagnostic instrumentation.

## Prove the improvement

- Reproduce the relevant decision through real existing producer/evaluator code
  with controlled external boundaries and private disposable state. Inspect
  emitted records through the actual CLI, collector and inbox. Hand-authored
  desired logs do not verify the producer.
- Add a regression for the observed loss and a nearby different cause. Check
  retained IDs, actual references, repeated scans, first-failure precedence,
  redaction and unavailable diagnostic sinks. Preserve prior business results.
- Include healthy/empty, legitimate hold and truly unknown controls. A diagnostic
  system that invents a fault or upstream explanation fails acceptance too.
- Give a fresh analyst only ordinary log/inbox access: no symptom, source,
  expected count, test label or private answer key. An independent reviewer
  compares its diagnosis with the actual executed cases and references.
- Require both malfunction detection and a specific supported possible cause or
  investigation route. If only detection succeeds, keep cause acceptance open,
  improve the named producer/access gap and retain the failed candidate.
- Adopt only reviewed diagnostic changes on actual maintained runtimes. Verify
  imported package identity, installed execution and natural collection. Do not
  initiate customer work merely to test diagnostics.

## Current examples and limits

The legacy child0 → supervisor1 evidence exposes repeated failed executions
but retains `reason=unknown`. It supports malfunction detection without a
decisive cause. Exhaustive inspection of every historical page is not established.

The delivered supervisor correction exposes distinct phase, discovery-count,
read-proof, native/process and persistence checks through ordinary access.
Current blind-acceptance evidence covers five distinct local failures, a complete
empty workload, a legitimate hold and an unavailable-cause control.
The [existing delivery plan](execution-plans/2026-10-23-debug-logs-hybrid-monitor.md)
retains approvals, real-code execution receipts and exact verification limits.
The missing original historical cause is not reconstructed by these controls.

Interactive source-corroboration diagnostics now distinguish provider quote-tail
ambiguity, unequal authored bodies and an identity rejection before comparison.
Controlled actual CLI-to-inbox checks preserve held3 and prove no generation;
a fresh blind analyst distinguishes these causes, healthy/fallback and policy
controls, unknown exceptions and unavailable logging. Installed release acceptance
remains owned by the current release plan. The historical ACCOUNTING trace itself
is not rewritten, and its source-body parser behavior is unchanged.

Discovery publication provides another regression boundary: a successful native
model cannot compensate for a missing inventory. Validate retained real task/review
payloads against the actual producer contract, exercise the scheduled publication CLI,
and test both complete artifact/source commitments and failure containment. Precise
pre-capture schema/stage evidence supports a log-only hypothesis; an unclassified view
failure remains explicitly unknown. A later verified publication is component evidence;
source publication incidents remain retained for manual diagnosis and are never
cleared by an unrelated supervisor success.

For incomplete inspection, first distinguish failed inventory publication from
successful publication that the native agent did not finish reading. Compare the
ordinary failed check/phase with the matching private envelope, bounded native
read proofs and terminal accounting. These protected artifacts retain page counts
and native cost; do not claim every number is already an ordinary event field.
A projected cost refusal is not an observed quota failure. Process exit0 or actual
cost below the limit proves neither coverage nor affordability of the remaining
work. If a needed fact is unavailable, improve its bounded producer/propagation
path; retain an explicit unknown instead of inferring an authentication, engine or
budget failure. Do not raise budgets, shrink required coverage or replay work merely
to obtain a passing result without the appropriate scope and evidence.

This workflow is recurring. A passing previous trial does not certify all paths,
all future incidents or customer-service autonomy. Every newly observed problem
reopens these two questions for its own actual diagnostic path.
