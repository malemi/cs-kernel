# Operator observability and independent monitoring

Status: PROPOSED — brief only. Owner: lead engineer. Date: 2026-10-23.

## Problem and intended result

The operator reports that MrCall does not send mail and Café does not produce
drafts. Engineering cannot promptly locate the ordinary execution logs, establish
which work was owed, or explain where it stopped. The operator discovers the
failure instead of receiving a timely, useful notification. This is a product
failure in observability, regardless of whether more files exist somewhere.
**Logs that an engineer cannot promptly locate and use are operationally absent.**

Build usable logging and independent monitoring across `cs-kernel` and
`mrcall-desktop`, with the maintained clone runtimes included in acceptance.
For a missing draft or send, engineering must be able to find the relevant
ordinary execution, see the last evidenced stage and its reason, distinguish an
unknown effect from a failed effect, and identify the next diagnostic action.
An independent monitoring agent must detect failures and stalled work before
the operator has to discover them manually.

This is a delivery brief for those capabilities. It replaces the framing of the
rejected [analysis-method brief](2026-10-23-operator-reliability-analysis-method.md).
It does not diagnose the current mail failures or promise that adding logs fixes
them. The resulting system must make future failures detectable and explainable.

## Evidence available at brief creation

The initial local inventory found these materials on 23 October 2026:

| Material | Observed location and coverage |
|---|---|
| MrCall Claude transcripts | `/home/mal/.claude/projects/-home-mal-hb-mrcall-cs/`: 390 JSONL files, about 239 MB; latest modification 09:07 UTC. |
| Café Claude transcripts | `/home/mal/.claude/projects/-home-mal-124-124-cs/`: 238 JSONL files, about 213 MB; latest modification 08:20 UTC. |
| Earlier verification outputs | `/home/mal/.local/state/codex-evidence/` and `/home/mal/.local/state/claude-evidence/`: test logs, stdout, stderr and receipts. |
| Ad hoc investigation material | `/tmp/cafe124-*-20261023.json`, `/tmp/cafe124-mail-review-20261023/` and `/tmp/mrcall-invoice-answer-test-20261022/`. Snapshots and test directories are not ordinary execution logs. |

The bounded local search did not locate ordinary cron or engine service logs.
That establishes a failure of operational access. It does not establish the
physical nonexistence of every log on every host. The transcript counts establish
retained volume, not complete tool coverage, causal diagnosis or successful mail.

[Operator runtime](../operator-runtime.md) documents per-invocation deterministic
health checks, SMTP notices and pending-notice queues, private native streams,
discovery artifacts and some safe engine action diagnostics. It explicitly says
this is not an independent host/cron heartbeat. Those existing mechanisms are
the starting point: inspect and extend them rather than create another parallel
notification system. Their documented existence does not satisfy discoverability,
current deployed coverage, independent supervision or request-level explanation.

## Scope and ownership

The lead engineer owns delivery and acceptance across the boundary. No gap may
be handed back as “the other repository logs it.”

- **Kernel:** CLI entry and exit, clone launcher and supervisor, native host/tool
  execution, permission refusals, direct classifiers, RPC client errors and
  ambiguous responses, effect verification and pending alert delivery.
- **Desktop/engine:** service startup, shutdown and restart; authenticated RPC
  receipt and completion; ingestion and background jobs; selection, authority,
  generation, persistence and provider operations; exceptions and cancellations.
- **Installed runtimes:** both maintained clones, their actual launchers and
  interpreters, relevant engine profiles/services and log access permissions.
  Source changes alone cannot close this work.
- **Independent monitoring:** expected launches, service and logging health,
  request progress, backlog age, alert delivery and the monitoring agent itself.

Prioritize the complete draft/send journey, while using one shared event and
access contract for other kernel commands, engine RPCs and background jobs.
Do not build a second mail classifier, task ledger or source of send authority.
Company identity, destinations and deployment configuration remain in Settings
and the manifest. The same capability must work for both maintained companies.

## Required behavior

### 1. Find the logs without a filesystem hunt

Provide one documented read-only entry point from the ordinary operator surface.
It must report each installed component, its current log location or authenticated
access route, coverage interval, most recent event, retention status and access
failure. It must work when a component is stopped and when the local checkout
differs from the installed package. A remote location without a working access
route is missing coverage, not a completed inventory.

From a request identifier or a clone/profile and time window, that surface must
return a bounded incident view with references to the underlying records. It
must also answer “what failed recently?” without requiring a known request ID.
Locations and access instructions must survive a restart, update and rotation.
Ordinary logging must be enabled without acceptance-test flags, a special prompt,
manual receipt setup or searching Claude's private session directories.

### 2. Explain a request from arrival to observed outcome

Record the ordinary path as it actually executes:

`mail acquisition -> discovery -> selection/deferral -> authority -> context -> generation -> engine persistence -> provider draft/send -> effect verification -> outcome`

Interactive requests need the equivalent path from the human's requested action.
Branches, retries, callbacks and background work remain visible. Each stage needs
a start and a result or an explicit unfinished status. A later stage must not
erase an earlier failure. The trace must distinguish these situations:

- No scheduled launch; launch refused; intentionally paused or disabled.
- Work not acquired, excluded, deferred, held, selected or never reached.
- Generation not attempted, failed, produced no draft or persisted a draft.
- Provider action refused, accepted, independently verified or still unknown.
- Delivery verified but cleanup incomplete; process stopped before its result.

Join request revision, owner/profile, conversation/RFC identity, run, attempt,
native tool, RPC, background job, engine draft and provider identifiers wherever
those entities exist. IDs must propagate across the kernel/engine boundary;
missing linkage must be explicit. Record UTC timestamps, local event order and
durations, process/start identity, installed version and relevant configuration
or workflow revision. Missing or skewed clocks must not imply invented ordering.

Record typed reasons at the decision point: authentication, quota, permission,
timeout, cancellation, incomplete input, policy hold, provider rejection,
persistence failure and unknown cause. Include safe exception type, component,
relative source location and upstream error/request code when available.
Preserve the original diagnostic record, subject to redaction; a generic outer
error or agent paraphrase must not replace it. Raw sensitive detail belongs in
restricted evidence, with a usable reference in the ordinary incident view.

Agent explanations are observations. They do not prove why a tool failed, that a
message was sent or that eligible work did not exist. Unknown effects remain
unknown until independently checked. Logging and monitoring grant no resend,
retry, cleanup, permission bypass or business-policy authority.

### 3. Detect omitted work as well as exceptions

The monitor needs expected schedules and explicit pause/disable state independent
of run logs, plus observed intake/discovery freshness and authoritative pending
work summaries. Otherwise it cannot distinguish no work from no observation.
Track request age, repeated deferral/hold, last progress and the condition required
to resume. A legitimate hold is visible without being labelled a technical error.

Compare observed completions with the recorded expected action for known work.
Use engine-owned judgements and authoritative instructions; do not introduce a
second classifier to manufacture eligibility. If the expected action cannot be
established, show that limitation and its age. An empty queue, zero exit code or
healthy process must never conceal stale discovery or unresolved expected work.
Acceptance must independently establish what selected cases were actually owed;
the system under test cannot certify its own business correctness by narration.

### 4. Monitor continuously and independently

Deploy a monitoring agent that regularly consumes the ordinary logs, correlates
incidents and reports actionable evidence. It must run outside the monitored
operator tick and remain useful when Claude, the cron wrapper or an engine fails.
Deterministic checks own missing launches, stale progress, missing terminal
records, logging failures, backlog thresholds and alert delivery. Diagnosis may
use a bounded analyst agent, but model availability must not gate detection or
notification. Model-produced hypotheses must link evidence and disclose unknowns.

The monitor needs its own execution record, heartbeat and last successful scan.
An independent watchdog must detect its absence. At least one escalation path
must remain usable when the monitored mail/SMTP path or its host fails; select
and verify the actual channel before deployment. Queuing another notice through
the broken path does not prove notification. Monitor outages and failed alert
delivery must be visible through this independent path without infinite layers
of model agents or unbounded retry loops.

An incident reports affected service/profile, first/last occurrence, impacted
work and age, last observed stage, evidenced cause or unknown, evidence reference,
delivery status and next diagnostic action. Deduplicate repeated symptoms while
escalating materially changed causes, wider impact and continued overdue work.
Acknowledgement suppresses repeated paging for a bounded period, not the incident
or its evidence. Recovery requires fresh evidence; a restart or quiet log is not
recovery. Keep existing owner notices where useful and join them to the incident.

### 5. Retain useful evidence within explicit limits

Define retention and byte limits for structured records, restricted raw evidence
and incident summaries. Rotation must preserve incident references and expose
evicted intervals. Record dropped events, truncation, collector lag, access
failure and disk exhaustion. A logger that cannot write must degrade monitoring
health and reach the independent alert path; silence cannot look healthy.

Use private access controls, owner/profile isolation and redaction before export
or model consumption. Do not log credentials, tokens, arbitrary environments or
unrestricted customer bodies. Retain only the restricted source material needed
to explain a case; retain safe identities and references in general summaries.
Test redaction against real field shapes and exceptions, not only clean samples.

Initial design targets are 30 days and 512 MiB of structured records per
runtime, 7 days and 128 MiB of restricted verbose evidence, with 30-day incident
summaries referencing any earlier eviction. The earlier time/size limit applies.
These are proposed acceptance budgets, not current guarantees. The subsequent
plan must validate capacity and choose explicit incident-preservation limits.
No unlimited “keep everything” store or unattended paid analysis is acceptable.

## Acceptance targets and required evidence

The following are proposed delivery targets. The implementation plan must resolve
feasibility and record any changed target before implementation, rather than
silently weakening it after a failed test.

| Requirement | Evidence required to pass |
|---|---|
| Discoverability | An engineer starting with repository instructions locates current ordinary kernel, launcher and engine logs within 2 minutes, then reconstructs one selected request within 10 minutes, without prior knowledge of temporary paths. Repeat after restart and rotation. |
| Independent detection | Check at least every minute; detect a missed launch within 5 minutes of its expected start and stale stage within 5 minutes of its declared deadline. Intentional pause is identified separately. |
| Timely notification | Deliver a new actionable incident within 5 minutes of detection; demonstrate receipt or explicitly report failed delivery through the independent channel. |
| Monitoring failure | Stop the monitor and separately break the primary alert route; the independent watchdog reports each within 5 minutes of its expected heartbeat/delivery deadline. |
| Omitted work | A known pending request that is repeatedly skipped or returns no action remains visible and alerts within one configured work deadline. Each request class must have a finite deadline; ambiguous eligibility is reported separately. |
| Causal diagnosis | Distinguish the tested failure stage and evidenced reason from downstream symptoms, including unknown effect when the response is lost after provider acceptance. No blind resend is attempted. |
| Cost and overhead | Deterministic detection uses no model calls. Measure added command latency and retained bytes. Any analyst model receives a finite per-incident deadline and daily cap fixed in the plan; cap exhaustion cannot stop alerts. |

Exercise cron never starting, launcher failure, host/process death, engine
restart, hung RPC/background job, auth/quota refusal, native permission denial,
provider rejection, persistence failure, completed effect with lost response,
logging disk full/unwritable store, rotation/truncation, stale discovery, zero
completed work despite known pending work, monitoring offline and alert outage.
Include legitimate no-work, human hold and intentional pause as negative controls.
For every case require discoverable records, correct incident classification,
bounded detection/delivery and a trace that supports the conclusion. Fault
injection must use controlled environments and must not generate customer sends.

Use deterministic tests for these mechanisms, then demonstrate ordinary deployed
coverage on both maintained clones and affected engine runtimes. Separately cover
MrCall interactive send, MrCall scheduled send and Café scheduled draft; success
on one does not certify another. Record the actual installed and running versions,
log access and monitor configuration. Use retained ordinary outcomes where they
provide complete evidence; unavailable cases remain acceptance gaps. New live or
paid cases require separate authorization and a fixed budget. Test receipts,
component passes and reviewer approval do not substitute for ordinary coverage.

## Constraints, delivery boundary and assumptions

Preserve identity, assignment, send/draft permissions, provider deduplication and
unknown-effect protections. Observability must not turn a diagnostic read into
classification/generation, change business decisions or replay unfinished work.
Reuse existing health checks, streams and notice queues where they meet the
contract; replace only mechanisms shown incapable of doing so.

The next separately authorized plan must map actual log producers and installed
hosts, identify their owners, select the independent watchdog/notification
failure domains, fix resource and work deadlines, and sequence deployment and
verification. Access to all required runtimes and an independent alert channel
are deployment dependencies, not assumptions of completed coverage. Missing
access or coverage must remain an explicit blocking acceptance item.

This assignment delivers only this brief and its review. It authorizes no
execution plan, implementation, instrumentation deployment, service/cron change,
release, customer send or further paid mailbox retry. Completion of the future
work requires demonstrated discovery, diagnosis and independent detection on
ordinary installed paths; writing more documentation is not that result.
