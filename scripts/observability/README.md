# Filesystem log collection

The maintained clones use ten-minute cron collection, private `problems.json`
files and the manually invoked `cs-diagnose` skill. The current contract is
[operational logging](../../docs/operator-observability.md), with delivery and
rollback evidence in the [current plan](../../docs/execution-plans/2026-10-23-debug-logs-hybrid-monitor.md).
The earlier monitoring plan remains failed.

## Bind the selected runtime

Use the actual clone interpreter/package, selected owner UID, state directory and
engine-reader route. Configuration and credential environment files are private,
mode0600, in a private directory. Do not print credentials during inspection.
`[observability].monitor_config_path` binds the configuration for `cs logs`;
the maintained installations use `<state>/observability/deployment/monitor.json`.
The generic discovery fallback remains `<state>/observability/monitor-config.json`.

The collection JSON uses the existing `MonitorConfig` with:

```json
{
  "mode": "filesystem",
  "scan_seconds": 600,
  "clone_label": "selected-clone"
}
```

These fields supplement the required monitor ID, owner UID, state directory,
expected start and components; this fragment is not a complete configuration.
Reuse the existing verified owner-bound component routes and expected business
schedules. Set `alert` and `watchdog` to null for the selected filesystem
installation. A kernel component's local root uses
`cs.observability.owner_root(clone_state, owner_uid)`; never borrow another
owner's namespace. Source configuration validity does not prove deployed access.

## Cron wrapper

`scripts/observability/collect_logs.sh` takes exactly four arguments:

```bash
bash collect_logs.sh CLONE_ROOT PRIVATE_CONFIG PRIVATE_ENV LAST_RUN_LOG
```

It sets a private umask, replaces the latest-run log, enters the selected clone,
exports the trusted credential environment and runs the installed
`.venv/bin/python -m cs.monitor_cli once --config PRIVATE_CONFIG`. A 150-second
outer timeout bounds execution. It performs no model call or mail operation.
Use only trusted private environment files: the wrapper sources shell syntax.

The installed private copy lives beside each runtime's configuration. Tagged
`*/10 * * * *` entries invoke it with explicit paths. `MAILTO=""` applies to the
collector block, so cron cannot turn a collector failure into a user-inbox
email. Preserve all original business cron lines and their ordering.
The latest-run log plus monitor scan/cursor records expose outcomes; an exit1
can mean correctly collected open problems, not a failed inbox write.

The collector reads at most twenty pages per component, reserves processing time
inside its120-second scan deadline, rotates component order and commits each
completed page. Incomplete pages replay safely. Durable lag/gap findings expose
unfinished catch-up. Existing locking refuses overlapping scans. No five-minute
notification or whole-host outage guarantee applies to this ten-minute mode.

## Read and investigate

```bash
.venv/bin/python -m cs logs locations --local --json
.venv/bin/python -m cs monitor status --config PRIVATE_CONFIG
.venv/bin/python -m cs monitor events --config PRIVATE_CONFIG --offset 0
```

Follow `next_incident_offset`; `--incident EXACT_ID` reads a selected incident.
`problems_path` and `investigations_path` locate the readable file and separate
manual findings. General problem details are safe metadata; restricted notice
sidecars are not input to an agent merely because their path is present.
Invoke `/cs-diagnose` in Claude Code, `$cs-diagnose` in Codex, or the project
`cs-diagnose` skill in OpenCode. Explicit inbox paths also work without a live
engine. Collection never launches this agent.

## Read causal decisions and improve missing evidence

The ordinary trace and inbox preserve optional versioned `causal` metadata from
the actual supervisor check. Inspect the selected layer/check/cause, safe known
command/phase, observed counts and actual child/cause event references. Child
exit0 and a generic wrapper terminal do not certify the supervised run. Unknown
references and upstream causes stay unknown.

Use the [log-driven diagnosis workflow](../../docs/log-diagnosis-workflow.md)
for every incident. If logs cannot reveal the malfunction or support a specific
cause/investigation route, instrument the existing decision and verify the whole
producer → CLI → collector → inbox path with real controlled execution and blind
healthy/hold/unknown cases. Do not bypass business guards or replay uncertain work.

## Interpret logging coverage

Retained `.logging-failed` markers record history, not a permanent claim that
all later writes fail. Inspect `coverage.logging.current_state` and its recovery
event using ordinary log reads. Only a later real append proves recovery; a
reader restart or zero local counters does not. The collector retains the same
coverage incident and investigation, using WARNING for proven historical-only
loss and ERROR for active, unknown or additional coverage failures.

When adopting the diagnostic correction, preserve each installed engine source
family. Copy its existing package and replace only the reviewed diagnostic
modules; guard exact preimages, check active work and verify the refreshed
writer/reader PID, binding and real event. Install compatible clone readers
first. Keep original markers, logs and findings through adoption or rollback.

## Installed transition and rollback

Both clone kernels use the reviewed severity/inbox code, DEBUG default and
filesystem configuration. Former evidence-monitor and owner-notice systemd
services are disabled. Two retained TEST watchdog deployments have zero
replicas; their data persists, but current off-host notification/mirror coverage
is not claimed. Independent authenticated engine readers remain active.
Existing engine DEBUG verbose logging and legacy structured formats are retained.

The supervisor queue and former operational-notice helper record private
filesystem evidence. Queue removal follows successful durable recording;
failure retains the item without sending to the user's mailbox. Ordinary
customer/test-mail functions retain their existing policy. Processes that
already imported older code retain it until they finish.

Before installation, capture actual package bytes/modes, selected config,
manifest/checksum ledger, unit enablement and crontab. Guard those preimages
against concurrent changes. Add only the new skill files/ledger entries and
preserve authored workflows and existing three-host links. Validate both installed
namespaces, actual log production, a safe ERROR, inbox durability, no-mail routes
and a natural scheduled run. Native skill behavior needs separate evidence.

Rollback removes only the tagged collector block and restores selected package,
configuration and service preimages while preserving logs, problems and findings.
Do not automatically re-enable user-inbox technical mail. Record any absent
monitoring coverage. The retained transport/watchdog deployment examples support
the legacy optional mode; they are not the selected installation procedure and
authorize no activation, customer send, model call or release.
