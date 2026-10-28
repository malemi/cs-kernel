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

Correlate the complete trace across parent and isolated-child PIDs. A review
checkpoint can update only before and after an entire projection; its age alone
does not establish that child reads are idle. Inspect existing per-read
start/result/failure events and bind process observations to PID, start identity
and timestamp. A socket or process snapshot is instantaneous evidence, not proof
of a continuous state between samples. Preserve any unobserved interval.

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
field dropped by one boundary is not a delivered improvement. Check the actual
reader's imported schema against the producer before rollout: a healthy reader
process can reject every new diagnostic field. Prove an exact retained event
roundtrip through each installed client's authenticated ordinary access, retaining
malformed-record counts, continuation gaps and owner/auth rejection controls. Preserve the first
decisive failure across child/fallback selection and final reporting. Distinguish
success of a child, a diagnostic write and the whole supervised task. A later
unrelated or generic wrapper success must not erase a known failure. In an
unresolved incident, keep the initiating payload and event reference together;
a later error must not replace them under the earlier first timestamp. Retain
latest observation time and references separately, and require recovery after
the latest failure with unchanged authority predicates.
For persistence size failures, compare the complete encoded wire value with its
hard limit, including envelope and formatting. A compact list estimate does not
prove an indented final file fits. Retained evidence and an incident row do not
prove the readable projection succeeded. Preserve a latched startup persistence
failure through child completion; retry through freshly loaded durable state.

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
work. A financial diagnosis must identify the actual boundary (native run,
provider key/account or engine ledger), the evidenced limit and consumption,
the rejected operation and original safe terminal/error code. Missing limits or
costs stay unknown. Native diagnostics retain a finite nonnegative terminal
`total_cost_usd` as `native_total_cost_usd` when supported composition exposes it;
missing or invalid values remain unavailable, not zero. A primary opaque launcher
may not disclose its configured run limit; ordinary terminal rejection alone
cannot establish exhaustion.
If a needed fact is unavailable, improve its bounded producer/propagation path;
retain an explicit unknown instead of inferring an authentication, engine or
budget failure. Do not raise budgets, shrink required coverage or replay work merely
to obtain a passing result without the appropriate scope and evidence.

This workflow is recurring. A passing previous trial does not certify all paths,
all future incidents or customer-service autonomy. Every newly observed problem
reopens these two questions for its own actual diagnostic path.


## Native protocol and scoped identifier failures

Artifact files and delivery markers do not establish accepted native inspection.
Compare the original stream with the pinned lifecycle validator. An unsupported
host event is a distinct protocol fault; preserve its exact type, ordering and
source, and test compatibility without filtering events or inventing a terminal.
A captured prefix may prove one complete context delivery while the whole run
remains failed. Keep constructed capacity cases separate from genuine execution.

For a failed draft action, follow its trace into engine persistence diagnostics.
The failed method, finite error code and relative guard origin can identify a
scope rejection before any storage write. Check whether identifiers retain the
exact authorized representation before blaming delivery, payment or quota.
Use bounded equality results and hashes; never publish the private body or tool
arguments. A generic wrapper failure does not erase a more precise engine event.
Representation normalization grants no owner/root authority and does not permit
replaying an uncertain attempt. Verify actual provider/store effects first.


## Provider evidence and archive correspondence

A Sent source can exist in the provider while its owner/mailbox archive is
missing or retains different ancestry headers. SENT_REPLY_NOT_SYNCED alone
does not distinguish zero from multiple scoped rows. SOURCE_UNAVAILABLE alone
does not establish authentication, transport, missing mail or header disagreement.
Check exact source identity, scoped cardinality and provider-versus-stored
References/In-Reply-To before proposing synchronization or data repair. Preserve
all business holds and verify ordinary technical health independently.

Hosted probes must use the actual service mount namespace, selected profile,
working directory, environment and OS identity. Bind the complete deployed source
inventory: a Git branch or family label is not byte identity. Reuse the runtime's
real profile loader; its selected settings can be absent from the initial process
environment. A probe outside that context can produce misleading DNS, login or
configuration failures. Report probe setup and helper/API contract failures
separately from failures of the actual service.

For an exact UID read, verify the actual native parser contract as well as the
adapter's requested limit. A whole-folder precondition can refuse a single-UID
request before its FETCH. Native counterfactual controls must preserve exact UID
selection and independent aggregate limits. Retain observed count, configured
ceiling, finite substage, exception type and relative origin before the primary
error is discarded; record cleanup separately. A later corrected read proves
only its own result, not the original missing exception.

Archive absence requires exact owner/mailbox/source cardinality before recovery.
Compare an authenticated source tuple with the existing same-UIDVALIDITY cursor
and real sync predicate before proposing a reset or wider scan. Stale cursor
progress and disabled reconstructed scheduling do not prove no other insertion
path ran or establish the historical skip cause. Keep private identifiers out of
ordinary output and retain an explicit unknown when causal facts are missing.
Readonly SQLite diagnostic engines must support the native RPC thread model;
a diagnostic connection's thread-affinity exception is not a production cause.

Retained historical SOURCE_UNAVAILABLE records can lack the original exception
or failed predicate; later source inspection cannot reconstruct missing evidence.
Current provider diagnostics retain known safe exception origins and connection,
operation, progress and deadline observations through ordinary logs and the inbox.
They do not prove that every source-correspondence rejection is fully classified.
For each incident, check its actual retained fields; improve a missing predicate
at its producer without headers, bodies or exception text. Supervisor or provider
component acceptance alone does not certify all assignment-source coverage.

Never repair an archive by blindly re-storing a fetched message: native
conversion can change content, thread identity, dates or read/processing marks.
A reviewed one-off source correction needs exact provider identity, private
preimages, narrow assigned fields, concurrency-safe writes and complete
postimages retained before verification can fail. A newly acquired Sent record
is normal source evidence; acquisition grants no assignment or sending authority.

For assignment-projection transport timeouts, distinguish dispatch, executor
enqueue, worker start, provider work and terminal cleanup. A projection timer
started inside a queued worker does not measure its earlier queue wait. Retain
a safe correlation ID and monotonic elapsed values at those existing boundaries,
with explicit absent-stage metadata and finite error classes. Carry validated
correlation explicitly across thread pools and subprocesses; ContextVars and an
environment value alone do not restore worker context. Give concurrent requests
separate child spans and join actual client/server observations. A shared
capability probe must finish before dependent diagnostic envelopes are selected,
without turning optional diagnostics into business admission.
The current retained failed case cannot distinguish queue wait from execution latency; this
is a diagnostic gap and a supported investigation route, not a proven queue
starvation cause. A later successful exact-root read does not clear the failed
whole-inventory observation.

## Clock selection, remote rejection and header identity

Compare the actual cause with elapsed and remaining time. A selected batch or
shared bound is not proof of expiry: an early connection failure can occur with
ample allowance. Follow the primary failure event before interpreting derived
account deferrals. Error-free local RPC returns also do not prove complete peer
coverage or unheld business authority.

Use structured remote error codes to distinguish an invalid-parameter rejection
from connection failure. For identity parameters, inspect the complete retained
header through the pinned parser path: tokenizing MIME encoded words before
whole-header decoding can yield a fragment. Preserve privacy with hashes and
bounded structural comparisons. Never invent brackets, omit malformed drafts or
reinterpret UNKNOWN as success to improve a health result.

When a safe exception origin is available, inspect that exact pinned source
branch before stopping at its broad exception class. An inventory-count guard
can reject after normal IMAP operations; it is not a transport or deadline cause.
If actual count, limit or selection mode was discarded, retain that limit and
improve those finite producer facts for the next failure. A recovered later read
does not erase the earlier guard failure or establish its missing arguments.

Time sizing needs complete-work measurements or explicitly qualified partial
extrapolation, non-projection allowance and a coherent native/suite envelope.
Financial quota is a different boundary. A workload can expose both insufficient
shared time and malformed input; extra time cannot repair rejected identities.

## Intermittent daemon failures

A successful retry or fresh-process probe does not explain a failed daemon
operation. Retain the failed daemon's connection identity/state and ordered
operations, including command entry time, remaining absolute deadline and
expiry/disposal ordering. Projection duration is not command duration unless
both command boundaries were observed. Distinguish economic quota, shared work
allowance, cumulative provider deadline and the last command's own duration.
A final command entered with only a few seconds remaining does not establish
that this command occupied the whole preceding two-minute projection. Retain
entry elapsed/remaining time, ordered operation totals and queue wait; earlier
protocol work can consume the deadline without proving its initiating cause. Record the initiating failure separately
from cleanup failures; a timer closing a socket at expiry does not explain why
prior work exhausted the budget.

If those observations are absent, report cause unknown and diagnostics
insufficient. Instrument the actual daemon path so its next failure retains the
missing evidence. Prove diagnostic retention with a controlled native failure,
but keep that proof separate from production causation. Close the underlying
defect only with failure evidence, a supported cause and a correction verified
on the same path. Repeating provider attempts until one passes leaves this
obligation open.


## Native task interruption and financial limits

A native child can exit0 after a required Bash task was killed or stopped.
Retain the first structured lifecycle rejection as `native_task_completion`
with `native_task_killed` or `native_task_stopped`; preserve strict failure.
The interruption identifies a local failure, not the upstream reason. Route
the investigation to the retained native stream and the child-local host Bash
foreground/background lifetime settings. Do not interpret model summaries as
validated timeout causes or label a time allowance as financial exhaustion.

The E9 controlled producer-to-CLI/inbox check lets a blind analyst recognize
interruption despite child exit0 and retain an unknown upstream cause. Healthy
and unknown snapshots without task completion remain outcome-unknown; they do
not certify whole-task health. Genuine native timeout behavior and BOTH-clone
acceptance remain separate requirements in the canonical release plan.


## Caller deadlines, finalization and child reaping

Keep the original end-to-end timer when investigating a bound failure. A timer
around thread dispatch or a complete CLI includes work before and after the
inner projection's deadline. Record parent entry, worker launch/wait, cleanup,
final diagnostics and return separately. Retain microsecond durations for a
sub-millisecond violation; missing stages and observer cost remain unattributed.
A completion reserve must come from the existing total allowance, apply to both
admission and reads, and preserve earlier inherited deadlines. Never relax an
assertion, move a timer or remove logging to manufacture a pass. A later passing
candidate does not identify a historical failure's missing cause.

For owned children, retain PID and available process-start identity, signal
attempt/result, exit-status availability and confirmed or unconfirmed reap.
Killing and reaping are separate observations. Pipe closure and a ResourceWarning
do not independently prove either a live child or completed cleanup. Use one
absolute cleanup allowance across communication, poll and wait; an unconfirmed
OS outcome stays visible. Once a PID disappears, its former identity and parent
cannot be reconstructed from a warning alone.

## Pydantic scheduled executor

Use the declared executor codec first. The new Python executor has no Claude
hook stream; do not interpret its journal as native events or count cancelled
native hooks as success. Retain the parent launch/configuration and source
bindings, request/submission/response chain, actual CLI captures and terminal.
Compare complete ID/name/argument maps across SDK history and provider requests
before interpreting tool results; a self-consistent hash chain is not provenance.

An HTTP status and finite error kind identify the observed provider refusal.
They do not imply zero charge or completed work. Preserve request identity,
known usage-price estimate and full uncertain reservation. For the one supported
prework fallback, inspect both original receipts and the parent admission
arithmetic against the original ceiling. A missing primary or reset allowance
is a failure even when the fallback tool or process exits successfully.

Distinguish transport, workflow disposition, health, provider effects and final
acceptance. In particular, a successful bare campaign mark is not proof that a
reply was handled; an already-classified reply may legitimately need no mutation
when its current contact preview and full-body evidence support that outcome.
Reuse the original private artifacts and precise rejected predicate. Do not
dump inventories, rerun paid work or invent an upstream cause to fill a gap.

For Python fallback renewal, distinguish the anonymous metadata read from a model
request. A renewal hold can precede intake and every executor launch. Inspect its
finite cause, current job reference, metadata byte/hash evidence and configured
price/capacity limits before attributing model cost or reasoning. A socket's idle
timeout does not bound a trickling response: use the total owned-worker deadline
and verified reap. Preserve failed and oversized reads as failures; never treat
truncated data or a stale policy as successful renewal. Compare the absolute job
deadline and independently observed launch window when checking attempt limits.
