# Operational logs and collected problems

Scope: diagnostic events, bounded log access, filesystem collection and manual
investigation. The current [brief](briefs/2026-10-23-debug-logs-hybrid-monitor.md)
and [plan](execution-plans/2026-10-23-debug-logs-hybrid-monitor.md) own delivery.
The earlier observability attempt remains failed and closed.

## Read logs and find problems

Use the selected clone's installed interpreter:

```bash
.venv/bin/python -m cs logs locations --local --json
.venv/bin/python -m cs logs recent --json
.venv/bin/python -m cs logs trace --trace-id TRACE_ID --limit 100 --json
```

Locations report the actual package, owner-scoped store and monitor
`config_path`. Use that path with `cs monitor status --config CONFIG` to obtain
`problems_path` and `investigations_path`. `cs monitor events --config CONFIG
--offset 0` lists bounded incident pages; follow `next_incident_offset`.
`--incident EXACT_ID` reads one incident. Follow explicit log cursors and coverage
gaps; an empty page does not prove that no problem exists.

Each maintained clone has a private `observability/monitor-state/problems.json`
under its state directory. It includes clone/component, incident ID/revision,
first/last observation, severity, symptom, stage/reason, evidence references,
investigation path and next diagnostic step. `remaining_count` and an incident
index route disclose omitted rows. Records are retained in the monitor SQLite
store; the readable file is an atomic bounded projection, not a second ledger.
Projection fitting and final writes use the same non-indented JSON format.
The complete envelope remains subject to the 256 KiB hard limit; omitted records
remain retrievable from the ledger with truthful remaining counts. A failed
projection write preserves its prior file and the pending notice queue.

`/cs-diagnose` in Claude Code, `$cs-diagnose` in Codex, or the project skill
`cs-diagnose` in OpenCode starts the manual investigation workflow. The human may
supply an inbox/configuration and incident explicitly. The skill reads bounded
safe evidence, separates cause from hypothesis and unknowns, and retains private
findings in `investigations/INCIDENT_ID.md`. Collection never overwrites those
notes. Its packaged `record_findings.py` helper validates the private destination,
derives identity/UTC from evidence and writes mode0600 atomically. An omitted
incident is read by exact ID from the same owner-validated local store without
rewriting the inbox. Analysis does not acknowledge an incident, prove recovery or authorize a
business retry, send, permission change or service restart.

## Levels and production

`[observability].log_level` accepts DEBUG, INFO, WARNING, ERROR or CRITICAL.
The initial/default threshold is DEBUG, including all five levels.

| Level | Meaning |
|---|---|
| DEBUG | Stage start/running and safe command/method context. |
| INFO | Normal observed outcomes. |
| WARNING | Holds, deferral, pause or other nonterminal limitations. |
| ERROR | Technical failure or an uncertain/incomplete effect requiring inspection. |
| CRITICAL | Essential runtime/logging failure; an unwritable store also emits a fixed critical stderr signal. |

Severity complements stage/status/reason/effect certainty. Explicit ERROR or
CRITICAL is detectable even with a generic result status; a legitimate policy
hold remains a hold. Filtering below the threshold is not a logging failure.
New kernel events persist `level`. Older level-less records remain unchanged on
disk and acquire status-derived severity when read. That value is interpretation,
not proof the original producer emitted a native severity. The installed actor
engines already write DEBUG verbose logs; their structured events retain the
legacy compatible schema.

## Current write health and retained loss

Coverage may include a strictly validated version1 `logging` object when failure
history exists. `current_state` is `failed`, `unknown` or `recovered`;
`history_retained` remains true. `observed_failures` counts newly observed
failures, while `lost_events_unknown` preserves missing historical totals.
`first_failure_at`, safe `last_failure` metadata and an exact `recovery` event
reference retain known evidence. A legacy marker has unknown cause/time/count;
reader-local zero counters do not resolve that history.

Only a fresh successful append, including flush/fsync, ordered after retained
failure can establish recovery. Reads, pruning, process liveness and filtered
emissions cannot. The original `.logging-failed` marker and logging gap remain;
recovery never restores lost records. Newer or unordered failures invalidate
older recovery. Unsafe or malformed diagnostic state remains missing coverage.

The existing coverage incident keeps its ID and investigation. Active/unknown
logging failure is ERROR. Proven recovered logging loss is WARNING only when no
other unresolved nonretention gap remains; unrelated faults remain ERROR.
Stable recovery evidence prevents each heartbeat from creating a new revision.
Safe failure metadata contains an allowlisted exception class, optional integer
code and relative Python file/line, never exception text or a traceback.

## Causal supervisor decisions

A process exit, a validated native terminal, ordinary-run health and the final
supervisor outcome are separate observations. A child can exit0 while required
phase evidence, a read proof or notice persistence fails. A wrapper's successful
logging call is not proof that the supervised work succeeded.

New supervisor events include a strictly validated optional `causal` object,
version1. It identifies `layer`, `check`, finite `cause`, `outcome`, known safe
`phase`/`command`/`method`, observed `facts`, diagnostic `refs`, `missing_refs`
and local `evidence_complete`. Known command names contain no arguments.
References identify actual run, attempt, child and cause events when available;
failed emissions leave missing references explicit. Completeness describes the
local diagnostic observation, not complete business authority or delivery.

For example, phase absence records the particular required phase and
`required=true,present=false`. A different discovery-cardinality failure records
`expected=1,uses=1,results=0`. A missing read result differs from a duplicate
result or an error lacking its required proof. These facts survive ordinary
trace/event reads, collection and `problems.json` as `evidence.causal`.
The registry in `cs/observability_causal.py` owns the exact allowed shape/codes.

The first decisive failure remains authoritative, including a pending notice
write failure before a healthy child starts. A later generic wrapper observation
cannot erase it. `supervisor_completion/run_verified` is emitted only after the
actual applicable native, health and notice checks pass; it is not proof that
every customer received a reply. Legitimate hold/empty controls stay distinct
from technical faults. Upstream cause remains unknown when not evidenced.
Legacy events retain their missing historical cause; they are not rewritten.

The [log-driven diagnosis workflow](log-diagnosis-workflow.md) defines the
mandatory detect → explain → improve → blind-check loop, its evidence standards,
acceptance cases and current coverage limits.

## Native completion and financial evidence

The producer in installed65 preserves `native_terminal_reason` as a closed
value (`completed`, `budget_exhausted`, `max_turns`, `api_error`, `error` or
`unknown`) and `native_total_cost_usd` only when its selected terminal reports a
finite, nonnegative number. Missing or invalid cost remains unavailable, never
zero. Parsed supported-composition facts flow through ordinary events and collected
causal evidence. Rejected native composition can make terminal facts unavailable;
retain its rejection reference and raw stream. Repeated same-session dollar reports
do not establish a cumulative charge without known aggregation semantics.
The unreleased catalog correction remains separate from this installed producer.

A completed native child with a missing required campaigns phase remains
`required_phase_presence/required_phase_absent`, with `phase=campaigns`,
`required=true` and `present=false`. Completion and reported cost do not erase
that failure. A structured financial refusal remains a separate rejected native
terminal; assistant prose about future cost cannot establish that refusal.

Identify which financial boundary rejected work: native run, provider account/key
or engine daily ledger. Report its configured limit only when directly evidenced.
The generic primary launcher may be opaque; its limit stays unknown rather than
borrowing the fallback or engine budget. Reported usage is neither an invoice nor
proof that remaining work would fit. Follow the retained first cause and exact
run/attempt/child references; do not raise limits or replay uncertain work merely
to obtain a passing outcome. Controlled budget-terminal tests prove propagation
and interpretation, not actual vendor-side enforcement.

The successor's optional closed `causal.timing` object retains parent-side
worker PID/start availability, signal and reap observations, bounded microsecond
durations, and reserved finalization versus work allowance. Unknown identity or
status is not fabricated. Projection finalization samples disclose
`final_write_excluded=true`; they do not measure their own final emission or all
caller/observer overhead. Separate controlled caller measurements preserve the
original end-to-end intervals. A missing-stage or partial timing observation
supports a bounded investigation, not a claimed complete historical cause.

## Candidate provider-connection evidence

The local59 candidate accepts optional `provider_diagnostic` version1 metadata.
Controlled real daemon/TLS/RPC → ordinary CLI → collector/inbox checks pass on
canonical and both exact actor families. Both maintained clones and actors now
load the verified diagnostic source; actual imports, modes, full source/unit
bindings and authenticated instruction readback pass. Original intermittent
failure causation and future genuine-failure capture remain unverified. This
component evidence does not certify whole business-workload acceptance.

58 does not support this object; legacy records without it retain their semantics.
Compatible readers must precede engine emission during any future adoption.

The closed object retains a random runtime-scoped connection token/generation,
ordered operation identity and phase, finite IMAP/socket/TLS states, pin and
deadline-target comparisons, pending counts, operation timing and remaining
absolute budget. Nonempty existing reads contribute only a bounded progress
count and latest-progress time. No command arguments or protocol bytes are kept.
Unknown observations remain null or explicit unknown enums. The strict validator
in `cs/observability_provider.py` owns all accepted fields, enums and bounds;
unexpected keys, unsafe values and malformed objects fail validation.

The failed event's snapshot and trace route survive collection; cleanup evidence
remains separate. Capture overflow prevents a completeness claim. Timing refers
to observed operations: projection elapsed time alone cannot establish how long
SELECT took. These fields support investigation, not an asserted upstream cause.
Controlled protocol failure proves diagnostic retention; the production defect
stays unresolved until actual daemon failure evidence supports a cause and a
correction is verified on that path.

## Assignment read boundaries

The58 candidate retains finite `assignment_read` causes for request timeout,
batch/shared deadline, isolated-worker expiry, connection/setup failure and
capacity deferral. The actual selected bound, elapsed and available remaining
milliseconds survive worker IPC and `evidence.causal.facts`. Selection flags
identify the limiting clock; unavailable timing remains explicit.

A derived account deferral references the timeout that reserved its account.
Earlier connection failures cannot replace that cause. Undispatched work records
`attempted=false` with no selected request/batch/shared clock; it is not another
observed timed-out request. These diagnostics preserve existing UNKNOWN/held
results and grant no retry or delivery authority.

The separately reviewed actor dependency emits enqueue, worker-start, projection
and terminal observations under one propagated trace. Queue wait and execution
have separate monotonic elapsed observations; missing stages and historical
causes stay unknown. Safe `elapsed_ms`/`deadline_seconds` survive incident
projection. Actual installation and FULL belong to the canonical release plan.

## Cumulative assignment time summaries

The kernel emits one `assignment_time_budget` decision per account
after the existing scheduler returns. `effective_entry_ms` is the time available
at scheduler entry, not an asserted original configured allowance. `elapsed_ms`
is total wall time; `serial_read_ms` sums local read invocation durations for
that account. `remaining_ms`, actual global/account concurrency and the first
actual timeout's bound and cause-event reference make cumulative expiry visible.

`expected_roots`, `scheduler_dispatched`, `returned_values`, `read_timeouts` and
`scheduler_deferred` distinguish scheduled work from results and unattempted work.
Dispatch means a local `read_many` invocation; it does not prove backend or
provider dispatch. Returned values are error-free transport outcomes, not proof
of business correctness. Individual request, batch and shared-deadline causes
remain distinct. Zero entry capacity can defer work without any request timing
out; ordinary successful reads and legitimate holds remain DEBUG.

When shared time expires, inspect caller allocation, per-account cumulative work
and the referenced read before changing a limit. This is evidence about a time
budget, not a financial quota. The summary alone cannot establish whether slow
service, work volume or an unsuitable allowance caused that exhaustion. Missing
backend evidence and older causes stay unknown. These diagnostics preserve
business results and authority. The separate reviewed shared-time correction
changes workflow allowances, not individual request/provider or financial limits.
Installation and genuine BOTH FULL remain separate acceptance obligations.

A selected request/batch/shared bound identifies the smallest permitted clock;
it does not prove that clock expired. An early connection failure retains its
primary cause-event link and a generic `read_failed` summary rather than a false
batch expiry. Synthetic unattempted deferrals cannot become the primary failure.
The summary's successful read count does not establish complete peer authority.

Remote-response diagnostics preserve structured `EngineError` metadata
through isolated workers: `remote_invalid_params` records code `-32602`, while
`remote_error` retains other bounded integer codes. The client-side exception
class is not a claimed remote Python type. Parent exception compatibility,
request ordering and fatal/deferred behavior remain unchanged. No error message,
data payload or raw identifier is propagated. Ordinary CLI, collection and inbox
retain the code and causal distinction; connection/IO and deadline failures
remain separate. A remote rejection with ample remaining time is not evidence
that the time or financial budget was exhausted.

## Discovery publication diagnostics

Scheduled discovery validates complete retained task/review material before publishing
its private inventory. The Gmail draft schema includes the provider's optional Bcc,
From, identity flags and typed MIME triples; unknown keys or wrong types still refuse.
These observations grant no assignment, source-inspection or send authority.

The `discovery_publication` source check identifies material unknown-field/type
errors and complexity refusal. Source-binding and otherwise unclassified failures
retain an explicit unknown cause with their publication stage. Its finite
`operator.discovery.*` method identifies parse, view, material, capture or verification.
Safe boolean facts distinguish review and Gmail-draft material; raw exceptions, field
values and message bodies never enter the diagnostic event. Failed publication keeps
exit3 and removes owned partial artifacts. A complete verified publication emits
`publication_prepared` as component evidence for all four artifacts. Source publication
incidents remain retained for operator diagnosis; this signal and supervisor/model
success do not automatically clear them. No automatic incident-closure feature is added.

## Protected-original admission evidence

The60 candidate records the actual protected-fixture admission decisions through
ordinary causal events. Production without an enrolled fixture records registry
absence as a DEBUG observation; absence alone is not an operational failure.
An enrolled original that cannot be found or confirmed remains unadmitted.

Read the counters in order: inbound rows, valid enrollment rows, exact matching
proofs, selected candidates and provider-confirmed originals. Zero candidates
with unrelated inbound mail is source absence; it is not proof that the first
unrelated sender mismatched the fixture. Multiple exact matches remain rejected.
For a same-identity candidate, the first failing owner/source binding predicate
is retained without its operand values. Registry invalidity and expiry remain
separate from absent source and provider failure.

Provider events identify connect, login, selection, UIDVALIDITY, fetch, MIME
validation and logout through finite `fixture.*` methods. Elapsed milliseconds
and known finite exception classes survive ordinary CLI and filesystem inbox
collection. Logout failure does not replace the initiating observation. The
configured15-second socket timeout is not a whole-operation deadline; elapsed
time alone cannot establish a timeout or an upstream provider cause.

The separately reviewed operational-test observer retains only read-incomplete
presence/type plus bounded actual event/trace references. It retains no arbitrary
read-incomplete text. Empty discovery still fails the strict fixture checkpoint;
new diagnostic evidence grants no admission, reply, draft or sending authority.
Controlled protocol/propagation checks prove these distinctions, not the cause
of a historical event whose deciding evidence was not retained.

## Interactive source-corroboration diagnostics

Draft preparation preserves a separate failed local check alongside the original
held command/exit3. The source layer uses `draft.prepare`, finite
`draft_source_body` causes for provider/engine unquoted-tail ambiguity, other
known authored ambiguity or unequal bodies, and `draft_source_identity` when
an earlier identity predicate blocks comparison. Known counts and ambiguity,
comparison-performed and generation-started facts describe actual executed checks.
The first failed predicate wins; fallback acceptance creates no false failure.

The separate ERROR check reaches the ordinary trace and collected inbox even
though legitimate held commands are excluded from technical-failure admission.
Safe exception class and relative source/line survive; bodies, parser-note text,
headers and arbitrary exception strings do not. Unknown evidence stays unknown,
including later MIME rejection after a successful body comparison. Only actual
final `draft_preparation/review_prepared` for the same root and method clears a
source incident; generic wrapper/supervisor success cannot clear it.

These diagnostics preserve parsing, source guards, exit codes and generation
behavior. They do not repair ambiguous mail or authorize a retry. Historical
records without the decision remain historically incomplete.

## Ten-minute collection and technical notices

The installed cron runs a dedicated wrapper under `*/10 * * * *` on both clones.
It invokes `cs.monitor_cli once` with a private configuration containing
`mode: filesystem`, `scan_seconds: 600` and the clone label. Configuration,
interpreter, credential environment and last-run log are explicit. Cron mail is
disabled for these entries; the wrapper records bounded latest-run output and
has a 150-second outer timeout. The deployment procedure is in
[scripts/observability](../scripts/observability/README.md).

The collector uses the existing scan lock, owner-bound SQLite and durable
cursors. Reads get up to 30 seconds within a 120-second scan budget, at most 20
pages per component. Component order rotates; every completed page commits its
progress, while an incomplete page can replay safely. Backlog, cursor gaps,
unreadable sources and failed inbox writes remain explicit problems.
Expected schedules/pause states and existing authoritative observations support
missing-launch, stalled-stage and unresolved-work findings without reclassifying
mail. With ten-minute polling, no five-minute detection promise is made.

Filesystem mode performs no diagnostic model call, SMTP notification, watchdog
heartbeat or notification transport. The prior sixty-second scanner and owner
SMTP services are disabled on both clones. The two off-host watchdog deployments
are scaled to zero; their retained data does not establish current host-outage
coverage. Authenticated engine readers remain active.

Supervisor technical notices and the former operational-notice SMTP helper now
record filesystem evidence. A queued notice is removed only after durable
recording succeeds; failure retains the queue, with no user-mail fallback.
Restricted original notice data stays in owner-private `notice-evidence/` with
safe references in the problem file. No routine technical mail is sent to users.
Ordinary authorized business/test-mail paths retain their existing controls.
A process already running older imported code retains that version until it
finishes; installation alone does not hot-patch it. No pre-cutover supervisor
remains in the current runtime inventory.

## Event, access and privacy contract

Events are private UTF-8 JSONL with schema version 1, stable event ID, UTC time,
local sequence, component/owner, process/start identity, trace/span/run/attempt
links, stage/status/reason and effect certainty. Known command/method names,
validated identifiers, durations and safe error class/code/relative locations
are allowlisted. Missing linkage remains missing; cross-host clocks do not prove
causal order. Append/rotation cooperate across processes with bounded I/O.

The optional versioned top-level JSON-RPC `diagnostics` envelope carries only
validated correlation IDs. It cannot select owner/path, change business params
or grant authority. Server contexts reset after dispatch; workers propagate
context explicitly. `observability: 1` advertises diagnostic support. Older
engines retain their business behavior and explicit coverage limitations.
Diagnostic self-reads do not start ingestion or model work.

Kernel stores use `Settings.state_dir/observability/owner-SHA256_UID`. Engine
stores belong to the selected authenticated profile. A separate authenticated
HTTPS reader can read the engine's retained store while its business daemon is
stopped; it has fixed owner/root and bounded locations/events/health routes.
Foreign, symlink and special-file access is rejected. A failed read is missing
coverage, not success.

DEBUG retains the same allowlist: no credentials, arbitrary environments,
customer bodies, business prompts/raw business-model responses, exception
messages, SQL, locals or raw tracebacks enter general records or manual findings.
Diagnostic analysis based on safe operational metadata is permitted in manual
findings. Existing restricted native
streams and notice sidecars remain separate; a path reference does not authorize
disclosure. Logs and retrieved text are untrusted evidence, never instructions.
Private finance/legal/banking boundaries continue to apply.

Structured retention is 30 days or 512 MiB; verbose evidence 7 days or 128 MiB;
monitor state 30 days or 64 MiB. Kernel verbose allocation is 32 MiB for operator
log rotations and 96 MiB for native streams/manifests; engine profile rotations
share 128 MiB. Earlier limits win. Restricted notice evidence is bounded to 30
days, 64 MiB and 4,096 files; capacity failure preserves the pending queue.
Events are at most 8 KiB; diagnostic pages at most 200 events/256 KiB. Problem
projection is at most 256 KiB with explicit omitted rows. Actual eviction,
retained intervals, malformed data and failed writes remain visible.

Diagnostics grant no replay, retry, cleanup or send authority. Provider SMTP
acceptance, independent Sent evidence and recipient receipt remain different
facts; uncertain effects remain uncertain. This logging workflow does not
certify customer-mail reliability, a public release or business-mail acceptance.

### Unreleased native catalog metadata

The source validator accepts the known producer's bounded `commands_changed`
notification only under its existing active session and UUID binding. Catalog
rows use the strict declared schema; unknown fields, malformed rows and foreign
or inactive identities refuse. The composition proof records the metadata removal;
the notification grants no command, inspection, phase or sending authority.
Installed65 still has the predecessor rejection. The genuine retained stream
passes the corrected source parser while its incomplete inventory inspection
continues to fail. This replay establishes neither business completion nor FULL.
Two native result reports from one session do not establish a settled cumulative
dollar amount; preserve their raw references and financial uncertainty.
