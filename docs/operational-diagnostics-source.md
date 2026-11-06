# Operational diagnostics source contract

## Availability

This M4 source candidate connects the existing event producers to ordinary log
queries, a bounded collector and an owner-bound filesystem inbox. The
[integration plan](execution-plans/2026-11-06-interactive-reply-m4-main.md)
records current verification. Source approval is not installed monitoring,
independent-host acceptance, or a guarantee that a mailbox is healthy.

## Query diagnostic evidence

```sh
cs logs locations --local --json
cs logs health --local --json
cs logs events --local --limit 100 --json
cs logs trace --local --trace-id TRACE_ID --json
```

The CLI observer records safe command/outcome metadata around ordinary commands.
Log and monitor queries bypass that observer to avoid generating their own query
noise. Producers retain operation/draft/root/snapshot correlations, achieved
stages and effect certainty; ordinary logs exclude bodies, recipients, credentials
and arbitrary exception messages. A successful command invocation does not prove
mailbox-wide health. A saved engine draft is a real achieved stage even when
publication was never dispatched.

`--local` omits the ordinary remote reader/engine query. The monitor view is read
from its configured state; optional off-host monitor copies remain separately
qualified and may be unavailable. Main Settings has no independent reader binding:
absence returns unsupported rather than raising an attribute error. No new
credential helper or main configuration field is introduced. Nonlocal log reads
retain the existing engine-capability fallback and report unavailable coverage
when the contract cannot be established.

Event/trace pages are bounded. `--request-id` hashes the supplied exact handle and
searches only the returned pages; follow cursors or an identified trace for further
evidence. Absence in one bounded page is not proof that no related event exists.

## Collect into a private filesystem inbox

```sh
cs monitor once --config /path/to/private-monitor-config.json
cs monitor status --config /path/to/private-monitor-config.json
cs monitor events --config /path/to/private-monitor-config.json
```

The explicit private JSON configuration binds schema version 1, a 32-hex-character
monitor ID, owner UID, absolute monitor state directory, expected start time and
one or more uniquely identified component routes. Select `mode: "filesystem"`
for local publication. A local component names its absolute diagnostic root;
legacy state, when selected, must bind that same owner's kernel root. Configuration
loading rejects invalid, inaccessible or oversized input without echoing it.
The ordinary logs view discovers the monitor config at
`state_dir/observability/monitor-config.json` and checks its owner.

The collector reads bounded event pages in a spawned process. Timeout/cleanup
failures produce typed safe evidence; they never retry a business operation.
Successful collection updates owner-bound incident state and publishes
`problems.json` in the monitor state directory. It creates the `investigations/`
directory and references per-incident Markdown paths for separately authored
findings; collection does not write those investigation files.
First decisive failures remain associated with their actual operation and source
across wrappers and scans. Matching verified delivery can resolve delivery
uncertainty while cleanup remains open. Incomplete or unrelated evidence cannot
clear it. Missing source coverage and failed inbox projection remain visible.

`monitor once` returns 1 for degraded, unavailable or absent status, 2 for a
configuration/collection exception, and 0 for other acknowledged results.
`status`/`events` inspect retained state. `ack` requires an exact incident ID;
it acknowledges that incident for the requested interval, not its underlying
business resolution. Mutating monitor actions refuse the existing headless markers.
`run` is the continuous collector entry. The watchdog server action is not part
of this selected source group. Existing configured HTTP transport code is retained
as a reviewed dependency; local verification does not exercise real endpoints.

## Limits

Local controls must prove the actual producer → store → logs CLI → spawned
collector → filesystem inbox chain, including repeated scans, uncertain effects,
matching recovery, redaction and sink failures. Controlled fixtures do not certify
live engine/provider behavior, current Desktop pairing, native workflows or both
ordinary FULL clone obligations. No monitor is installed or started persistently
by this source integration, and no M6 recipient or spending authority is inferred.
