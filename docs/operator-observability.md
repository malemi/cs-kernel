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
