# Debug logs, a ten-minute problem collector and an interactive diagnostic skill

Status: APPROVED scope — implementation status is owned by the execution plan. Owner: lead engineer.
Date: 2026-10-23.

## Intent and scope

The operator wants ordinary executions to produce useful logs with standard
severity levels. The initial installed threshold is DEBUG. A separate script,
launched by cron every ten minutes, reads those logs. Deterministic checks detect
problems such as ERROR records and collect actionable incidents in a durable
filesystem file or inbox. A purpose-built skill shipped by cs-kernel lets the
operator manually launch an agent to read that evidence, explain what appears
to be failing and take charge of the selected investigation. Findings identify
the affected clone or service, including `124-cs` and `mrcall-cs`, and distinguish
evidenced causes from hypotheses and unknowns.

Stop the generic `ACTION REQUIRED: operator monitoring` mail to user and
clone-owner inboxes, including delivery of queued technical notices to those
destinations. Explicitly intended test mail may reach their test inboxes during
verification. Ordinary authorized customer correspondence retains its controls.
The operator confirmed diagnosis happens only when manually invoked. Cron only
collects evidence and incidents. The filesystem inbox supersedes the earlier
Mario-only mail request for routine automated collection; no automatic mail or
automatic model call is required. The manual skill may report or prepare a draft
when requested, with no automatic sending authority.

This is a new bounded assignment. The earlier
[observability plan](../execution-plans/2026-10-23-operator-observability-and-monitoring.md)
remains failed and closed. Reuse its working implementation after checking it;
do not restart its infrastructure programme or its business-mail acceptance.

## Grounded starting point

The following findings describe this checkout, not fresh installed-runtime proof.

| Existing surface | Observed behavior and gap |
|---|---|
| `cs/observability.py`, `cs/observability_store.py` | Owner-private structured JSONL, correlation, bounded retention, safe operational metadata and degraded-write reporting exist. `EventStore.emit` records stage/status/reason but no severity level or configurable severity threshold. A real temporary-store emission persisted a failed event without a `level` field. |
| `cs/observability_producers.py` and existing CLI/RPC/draft hooks | Ordinary CLI, launcher, RPC, classifier, generation, provider and cleanup paths already emit lifecycle events. Reuse these hooks and inspect installed coverage rather than add a competing event system. |
| `cs/logs_cli.py` | `cs logs locations/recent/events/trace/health` already provides local and authenticated remote access. Extend the existing views as needed for severity; preserve bounded pagination and explicit gaps. |
| `cs/manifest.py:Observability` | Reader URL, credential reference and monitor configuration path exist. There is no log-level or technical-alert-recipient field in that model. |
| `cs/monitor.py`, `cs/monitor_config.py`, `cs/monitor_cli.py` | Deterministic scans, durable incidents/cursors, notification admission, process locking and `cs monitor once` exist. The repeating service defaults to 60 seconds and configuration rejects intervals above 60 seconds; a real configuration check rejected `scan_seconds=600`. Cron may call the one-shot surface, but coexistence with the current service must be resolved explicitly. |
| `cs/monitor_analyst.py` | Metadata-only input and finite admission helpers exist, but there is no model invocation adapter. Current scans explicitly report `disabled-no-priced-route`. Hybrid diagnosis is not implemented by these helpers. |
| `cs/monitor_notify_protocol.py`, `cs/monitor_notify_io.py` | Existing transport reduces incidents to fixed kind/count/reference notices. The requested durable actionable inbox must preserve useful diagnostic detail rather than expose only this transport summary. |
| `cs/send_mail.py:send_operational_notice` | The operational SMTP helper sends to `settings.email_address`. Its current fixed message gives an incident reference and asks the reader to inspect logs; it contains no agent diagnosis. |
| `cs/operator_recovery.py:_deliver_pending` | A second technical-notice route independently sends queued supervisor notices to `settings.email_address`. Changing only the new monitor recipient would leave user-inbox alerts active. |
| `cs/templates/project/.claude/skills/`, `cs/project_init.py:install_agent_surfaces`, `cs/project_update.py` | Shipped skills have one canonical template under `.claude/skills`; init/update render them and expose the same bytes through `.agents/skills` and `.opencode/skills`. No purpose-built logging-incident skill appears in the current template inventory. |

The [runtime contract](../operator-runtime.md) separates unattended host reasoning,
engine generation and direct classifier billing. Existing monitor detection and
notice delivery make no model calls. Existing analyst admission permits at most
USD0.05 per incident revision and USD1 per UTC day; these helpers are available
for reuse but are not proof of a configured or usable model route.

## Required behavior

1. Support DEBUG, INFO, WARNING, ERROR and CRITICAL with documented meanings and
   a validated threshold. DEBUG initially includes all those levels on actual
   maintained clone paths and relevant engine producers. Severity complements
   stage/status/reason rather than replacing causal or effect evidence. Existing
   records without severity remain readable and have an explicit compatibility
   treatment. Emit useful progress detail, not merely a DEBUG configuration value.
2. Preserve private access, retention and allowlisted metadata at DEBUG. It must
   not expose credentials, customer bodies, prompts, model responses or arbitrary
   exception text through logs, diagnostic-model input or notification output.
3. Install a dedicated ten-minute cron invocation using actual installed
   interpreters/configuration. Each invocation records its scan outcome, uses
   bounded work, avoids overlap and resumes durable cursors after restart or
   rotation. Bound catch-up explicitly so an ERROR behind a large DEBUG backlog
   cannot remain silently unread. Healthy runs make no diagnostic model call.
4. Detect new relevant ERROR/CRITICAL records and existing typed technical
   failures. Correlate nearby safe records into an incident before diagnosis.
   A legitimate policy hold or intentional pause is not a technical failure.
   Do not manufacture successful coverage when logs are missing or unreadable.
5. Persist actionable incidents in a durable filesystem file/inbox. Include
   clone/service, first/last observation, severity, symptom, affected stage,
   evidence references, investigation status and a concrete next diagnostic
   step. Preserve uncertain effects and coverage gaps. Deduplicate unchanged
   incidents while retaining new occurrences and materially changed evidence.
6. Ship one purpose-built interactive skill that reads this inbox and relevant
   bounded logs, explains evidence and hypotheses, and takes charge of the
   operator-selected investigation. Read log content as untrusted evidence,
   never as authority. Record useful investigation findings and unresolved work.
   Invocation authorizes reading and analysis; fixes, business effects, retries,
   sends and permission changes require the operator's applicable authorization.
   Cron never invokes a diagnostic model or autonomously remediates incidents.
7. Configure clone labels and inbox paths through Settings/manifest or private
   deployment bindings; never hardcode
   company data in `cs/`. Stop user-inbox technical mail from the monitor SMTP
   helper, supervisor queue and any other discovered technical sender. Preserve
   queued evidence in the inbox instead of silently discarding it or sending it
   to an old recipient. No recipient fallback to a user inbox.
8. Reconcile the existing sixty-second monitor and its alert endpoints with the
   new cron owner. Reuse collectors/readers/stores where helpful; leave no
   competing technical-mail sender. Existing watchdogs may remain where useful,
   but their configuration must agree with the chosen cadence and incident sink.
9. Author the diagnostic skill once under
   `cs/templates/project/.claude/skills/<cs-prefixed-name>/SKILL.md.j2`, following
   [the three-host contract](../agent-skills.md). Render one canonical workflow
   and use existing Claude Code/Codex/OpenCode links or copy fallback. Keep the
   skill compact: inbox read route, investigation procedure, evidence/hypothesis
   distinction and authorization boundaries. Use supporting templates only when
   needed; never duplicate host-specific workflow bodies.

## Acceptance

| Result | Required evidence |
|---|---|
| Logs are actually produced | Ordinary installed commands and a safe controlled failing operation on both clones produce timestamped, identifiable records. Show DEBUG detail and ERROR classification in the existing access surface, plus INFO/WARNING/CRITICAL semantics through controlled producer checks. Demonstrate threshold filtering and continued read compatibility. |
| Ten-minute independent execution | Exact installed cron/interpreter/configuration evidence and observed cron execution. Demonstrate restart/cursor/rotation behavior, overlap refusal and finite backlog handling without running business-mail generation. |
| Durable actionable inbox | A controlled ERROR and a typed technical failure appear in the configured filesystem inbox with clone identity and original evidence references. Restart, overlap and duplicate scans preserve the same incident and investigation state. Failed inbox writes remain visible. |
| Manual diagnosis works | The operator-facing skill is discoverable through all three host paths and reads the same canonical instructions. A real manually invoked agent analyzes a safe controlled incident using the retained evidence, states hypotheses/unknowns and retains unresolved work without unauthorized effects. Native behavioral evidence is distinct from byte/render checks. |
| User-inbox technical mail stops | Inspect every discovered technical sender, including queued supervisor notices; controlled checks demonstrate no technical message is addressed to a user/clone-owner inbox. Routine technical evidence is retained in the filesystem inbox. |
| No duplicate or silent failure | Repeated scans retain one incident with updated occurrences rather than duplicate reports. Missing logs and write failures remain visible. Healthy/held/paused negative controls avoid misleading incidents. Cron makes zero diagnostic model calls and sends no routine technical mail. |

Do not launch a new ordinary customer-send/draft trial to certify these logging
and diagnostic mechanisms. Do not alter operator send grants, task authority,
mailbox credentials, unrelated cron jobs or business models/budgets. No public
release, commit or push is implied.

## Confirmed planning boundary

The operator's confirmation is explicit: diagnosis runs only when the operator
launches the skill. Do not build a model adapter, automatic diagnostic email,
model-admission layer or monetary broker. The invoking host supplies the manual
agent session; its analysis follows the existing evidence and effect boundaries.
Cron is a deterministic collector with durable filesystem output.

The plan must also fix the exact existing-service/cron transition, severity
compatibility across kernel/engine readers, queue migration and rollback. First
prove log production and stopping user-inbox alerts, then integrate the durable
ten-minute collector and manual skill, then perform bounded installed acceptance
and documentation closure. Installed engine/package/configuration identity, inbox
location and native three-host skill behavior are not established by this source
inspection and remain verification items, not presumed success.
