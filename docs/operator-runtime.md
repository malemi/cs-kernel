# Operator runtime, models and spending

The agent host executes the skills; the `cs` CLI executes their commands. In an
interactive workspace the host is the user's chosen coding agent. Unattended
operator ticks select their host through the generated
[`bin/cs_operator_cron.sh` template](../cs/templates/project/bin/cs_operator_cron.sh.j2)
and the kernel's deterministic supervisor. The wrapper retains its legacy Claude
default until reviewed adoption explicitly exports `CS_OPERATOR_EXECUTOR=pydantic`.
That selection launches a Python executor child instead of `claude -p`; it does
not launch the configured legacy Claude executable. Interactive hosts are unchanged.
This is distinct from a headless engine daemon:
that daemon is an RPC service whose LLM work uses provider APIs.

[Operational logging](operator-observability.md) provides `cs logs`, DEBUG-first
records and a ten-minute filesystem problem collector on both maintained clones.
The human launches `cs-diagnose` to investigate. Routine technical notices are
recorded in the private problem inbox instead of being emailed to users. The old
scanner/SMTP services and off-host watchdogs are disabled; engine readers remain
available. Logging does not establish current customer-mail reliability.

| Execution path | Model/auth owner | Budget boundary | Pause boundary |
|---|---|---|---|
| Claude Code operator reasoning/tool selection | Primary: Claude login. Optional fallback: explicit manifest model and saved OpenRouter key supplied to that process | Primary account limits or fallback key limit; the engine ledger does not cover either | Wrapper checks `~/.<slug>-cs/CS_PAUSE`; the local supervisor checks before/after intake and before fallback; does not terminate a running process |
| Pydantic scheduled reasoning/tool selection | Explicit executor API provider/model/key binding; Anthropic or the existing OpenRouter Anthropic Messages route; no reuse of a Claude subscription login | Separate soft target and supervisor-admitted ceiling, conservative request reservations and retained uncertainty; neither the engine ledger nor session quota covers it | Same wrapper and supervisor pause boundaries; timeout/cancellation cleanup revalidates owned process identities |
| Engine analysis, memory, task judgement and contextual generation | Active engine profile `LLM_PROVIDER`, model preset/role overrides and personal key or MrCall credits | Engine profile's daily reservation ledger | Preparation pause/automatic-update settings govern processing; budget zero refuses new paid engine requests |
| Kernel direct classification | Clone/provider env and `model_config.py`, independent of engine profile | Direct provider billing; no engine reservation or daily cap | Not disabled globally by `CS_LLM_ROUTE=engine`; caller-specific guards apply |

An operator tick can spend on three separate billing paths: its selected host reasons, commands request
engine generation, and a send guard requests its own classification. A read-labelled
RPC is not a zero-cost guarantee: ordinary `emails.needs_reply` can invoke engine
model classification. Deterministic health assessment and problem collection consume
recorded execution evidence and issue no extra model requests. A draft-only
policy does not make reasoning or generation free. Charging Claude to a subscription rather than
API billing must be checked in its actual runtime authentication, not inferred
from `claude -p` or the engine's credentials. The legacy supervisor's primary run supplies no
`--model` or `--max-budget-usd` flag. The fallback, when configured, supplies
both; the budget flag is a soft guard that may be exceeded by one model call.
The alternate key's provider-side limit is the final spending boundary. Never
assume the engine's selected model is Claude's.

A clone-owned executable may supply primary API authentication and its own
budget flag before invoking Claude. Inspect that executable as well as the
supervisor: the generic primary flags do not establish the clone's actual
billing route or cap.

For the legacy backend, the supervisor in [`operator_recovery.py`](../cs/operator_recovery.py) starts a
second Claude process only after a structured, immediate quota or payment
refusal proves no tool ran and no tokens were billed. It reuses the same prompt,
command allow list, command deny list and headless send marker for both attempts.
Before launching Claude, it checks that a `send` triage mode has explicit send
permissions and the headless send marker, while a `draft` mode has neither.
A mismatch stops the tick and records a stopped-run problem. A three-hour
process watchdog stops a hung tick and
records the stop; it never retries that tick. The manifest must set
`knobs.cron_fallback_model` to an
explicit Claude model route and `knobs.cron_fallback_budget_usd` to a positive
per-tick amount; otherwise the operator stops and records a technical problem. The
fallback key comes from the engine's saved `OPENROUTER_API_KEY` secret. It is
passed in process environment, so tools launched by Claude may inherit it;
the key must have a provider-side spending limit. It is never written to the
Claude settings file or placed in command arguments. Existing workspace trust
and permissions are used for both attempts. A fixed, non-LLM technical notice records service changes,
effective model changes and stopped runs in the filesystem inbox. The retained
notice renderer distinguishes informational backup/model changes, recovery and
unconfirmed/stopped runs; rendered subjects are diagnostic data, not automatic
mail delivery. Existing queued notices migrate only after durable recording.

The local candidate reports symptom, evidenced cause, affected provider/account,
repair and post-repair behavior. It distinguishes account payment refusal from a
proved exhausted OpenRouter key cap, API billing from Claude subscription usage,
authentication from request permissions, and per-run budgets from engine budgets.
Repair links point to the relevant provider billing, usage or key page. Known
account emails, organization/workspace/creator IDs and masked key identifiers
identify the credential involved; the recipient mailbox and engine profile UID
are explicitly not evidence of the provider payer. Unknown causes and identities
remain explicit, with captured safe codes and concrete read-only diagnostic
commands using the scheduled executable and workspace. There is no assumed
administrator or invented contact address.

Legacy primary identity comes from the configured Claude-compatible executable's
read-only `auth status --json`, with a five-second deadline and 16 KiB retained
response limit. Custom launchers must honor that command contract. Failed probes
never prevent the scheduled run. API authentication never borrows a saved OAuth
email. Inherited key fingerprints and endpoint overrides are used only for native
executables; opaque wrappers may replace those values, so unreported identity
stays unknown. A firstParty API report from an opaque wrapper is also insufficient
to establish the provider: Claude-compatible gateways can report that same value.
Rejected backup credentials point specifically to the engine profile's saved key
in Desktop Settings. The backup identity uses the exact saved OpenRouter key and its
[read-only key metadata](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key).
This lookup has a five-second request timeout and 16 KiB response limit; failed
lookups retain the masked key. Limits are re-read after a failed backup attempt.
Diagnostic classification does not authorize replay: the independent pre-work
proof remains required before a backup run can start.

Ordinary account repairs require no daemon restart or manual replay; the next
enabled, unpaused scheduled tick tries the main service again. A completed backup
is informational. If both routes fail, repairing the main service alone can
restore the next run. Uncertain or interrupted work requires checking recent
sent messages and drafts before manually repeating it. Unknown failures receive
a concrete diagnostic step rather than a claimed definitive repair.

Queued notices retain the failed attempt's diagnostic/account/configuration
context, including the engine profile that stores the backup credential, excluding full keys and arbitrary agent/tool error text. Legacy queued
reasons remain renderable with their missing historical evidence disclosed.
Cause/provider/account changes notify again; timestamps and session IDs do not
break deduplication. Failed filesystem recording retains the pending queue. These
records concern the scheduled run, including its email-intake prerequisite.
The [delivery plan](execution-plans/2026-10-13-operator-actionable-diagnostics.md)
records its diagnostic contract; current filesystem adoption is covered by the
[logging plan](execution-plans/2026-10-23-debug-logs-hybrid-monitor.md).

## Pydantic executor authority and evidence

The migration replaces the scheduled host, not the CLI, engine, workflow or
business oracle. The supervisor's `--executor pydantic` option retains the existing
mode/send-marker check, pause, intake and bounded child boundary. Select the host
in the scheduled launch environment or explicit supervisor arguments; merely
putting the selector in a dotenv file read later by Python does not select it
in the shell wrapper. Adoption state and outstanding acceptance are recorded in
[active context](active-context.md), not inferred from source tests.

Executor configuration is separate from classifier and engine settings. It binds
`CS_EXECUTOR_PROVIDER`, `CS_EXECUTOR_MODEL`, `CS_EXECUTOR_API_KEY_ENV`, the exact
endpoint and reviewed `CS_EXECUTOR_PRICING_JSON`, together with the separate soft
target and `CS_EXECUTOR_ADMITTED_CEILING_USD`. The model cannot edit those inputs.
An alias requires a finite reviewed set of actual response models. OpenRouter
uses the existing `https://openrouter.ai/api/v1/messages` route and an explicit
isolated token; it is not silently promoted to primary. Claude subscription
login is not API authority. Never print or put credentials in process arguments.

The real child invokes canonical CLI commands through finite `run_cs` arguments,
loads the rendered workflow source and reads bounded current-run artifacts.
There is no shell, arbitrary Python, raw unrestricted RPC or model-callable file
mutation tool. The shared rendered host mapping preserves native interactive
spelling while mapping scheduled typed tools to the same operations. Bare
`campaign mark CONTACT` previews the current contact without committing a
classification update.

The `pydantic-executor-v1` journal is distinct from native Claude events. Parent
process/config/source binding, actual CLI start/end/output joins and complete
SDK-to-provider call maps establish provenance. Pages must reach the real
provider request and a matching response before effects. Both the kernel and
the independent Desktop consumer reject missing identities, foreign results,
partial delivery and unresolved lifecycle events. Transport proof still does
not establish model compliance, a mailbox effect or full operational acceptance.

Request admission reserves a conservative maximum before transport. Usage-price
estimates distinguish new input, cache reads, cache writes and output using
explicit reviewed rates; normalized input totals already include cached tokens.
Set `CS_EXECUTOR_CACHE_MODE=5m` explicitly with all four billing rates; the
fallback uses its separately reviewed `CS_EXECUTOR_FALLBACK_CACHE_MODE`.
Invalid or unsupported usage retains the reservation. An uncached configuration
without billing-rate detail is labelled a conservative usage upper estimate,
not a provider invoice. Do not count retained reservations as actual spend or
reset them on fallback.

One distinct existing fallback may follow a strictly evidenced immediate
prework billing refusal, with no model-executed tools or business work. The
current new backend supports the structured HTTP402 billing case; HTTP429 does
not establish the old native weekly/five-hour refusal category and remains held.
Retain the primary's full unknown reservation and known cost, subtract them from
the original admitted job ceiling, and admit the fallback only within that
remainder and any narrower approved fallback cap. Its manifest soft target does
not enlarge that ceiling. The parent preserves both proofs and the independent
consumer checks the admission chain. Unknown effects, timeout, missing evidence,
same-route retry and a second fallback remain forbidden. A successful fallback
does not erase the primary's uncertainty. The reviewed rationale is in the
[execution plan](execution-plans/2026-10-28-pydantic-headless-executor.md).

## Shared workflow time bounds

Workflow time is separate from model spending. The installed kernel gives
review 2700 seconds of work, 10 seconds cleanup and a 2715-second total envelope.
Scheduled discovery observes for 2710 seconds, reserves its last 10 seconds for
completion, and separately bounds cleanup/publication/finalization at 10/5/5
seconds, for 2730 seconds total. Both worker admission ceilings follow those
actual payload deadlines. Standalone projection remains capped at 3600 seconds;
a caller's inherited earlier deadline still wins.

The reviewed E9 launcher correction binds both `BASH_DEFAULT_TIMEOUT_MS` and
`BASH_MAX_TIMEOUT_MS` to 2730000 in the ordinary `/cs-operator` child's copied
environment. The canonical parent operator instruction requests that same Bash tool
timeout for discovery/review. Installed66 triage and campaign instructions
request the same2730000ms. Custom prompts and the parent environment retain
their existing behavior. This aligns host command lifetime with bounded kernel
work; it grants no new kernel, suite, financial or authority allowance. Actual
rendered instructions are verified on both clones; genuine native conformance
remains a separate gate in the current release plan. A structured killed/stopped task remains a failure,
with its upstream cause unknown unless independently evidenced.

The reviewed Desktop acceptance consumer bounds the native MrCall/Café/signup
jobs at 6600/1800/600 seconds and its suite at 10200 seconds. Resume age and
terminal elapsed validation use that same finite suite envelope; native terminal
validation also rejects overrun or nonfinite timestamps. The original
consumer/policy preimages stay preserved during owned maintenance. Activation
requires exact installed composition, independent review and installed preflight.
Protected fixture authority still expires at 5400 seconds; a longer test window
never extends that authority or waives expiry refusal.

The sizing uses partial measured per-account read work with explicit headroom,
not a guaranteed completion time. One active read per account, four globally,
150-second assignment requests, 180-second batches, the 120-second backend bound,
three-hour ordinary watchdog and financial controls remain unchanged. A timeout
or invalid input stays incomplete and held; the larger envelope grants no replay,
assignment or send permission. The existing release plan owns adoption and
unchanged strict BOTH-clone acceptance.

## Deterministic ordinary-run health

The local [ordinary-health repair](execution-plans/2026-10-15-ordinary-operator-health.md)
adds a private per-attempt discovery artifact to the canonical `/cs-operator`
run. Its nonce, owner and actual process ancestry bind the bounded complete CLI
result to that attempt. Ordinary output supplies its path; protected runs can
read the existing current health context instead. Capture grants no authority.
Clipped native discovery requires complete genuine current automatic context or
contiguous matching bounded `dd` reads through EOF of the validated semantic view
AND envelope before recognized drafting. Scheduled v2 recurring material cannot
be replaced by raw discovery alone. Native identity, configuration, tasks, discovery,
campaign and review results are required, plus enabled founder reads.

Health assessment, filesystem recording and pending-recording retry are deterministic
code; none requires an LLM or paid model credit. They consume existing execution
results and do not launch extra discovery or classification. Technical unknown
scope, unreadable mailboxes, missing phases or incomplete inspection return an
unhealthy nonzero tick even when Claude exits zero. Legitimate human holds and
empty queues remain healthy. A failed attempted draft or contextual send also
requires a deterministic operation-failure notice, without inferring a cause
from agent prose. Independently eligible work can continue; no post-work failure
authorizes replay. Earlier technical incompleteness still
warns even if one exact conversation later recovers.

Engine email action failures are collected in bounded request-local metadata,
including the scoped assignment-draft route. Failed create_draft/update_draft/
send_draft results set metadata.error and activate the existing CLI/supervisor
failure path. Delivery certainty remains unknown and no blind replay is
permitted. Safe engine chat diagnostics, where deployed, contain a fixed known
exception label and validated relative engine file/line locations; they exclude
exception messages, source lines, locals, arguments and chained error payloads.
The RPC response remains generic. Current installations and full ordinary
acceptance belong to the assignment recovery plan and living context.

Pending notices are recorded before intake/authentication/model launch when the
supervisor runs. Recording failure keeps the queue and visible failure state,
with no fallback to the selected user's mailbox. An intentionally paused outer
wrapper does not invoke the supervisor. The separate ten-minute collector reads
ordinary observations; it does not start business work or classify mail. Both
maintained clones have the filesystem notice route installed. Already-running
processes retain their imported older code until they finish; changing installed
files does not hot-patch them. Historical SMTP receipts establish only their
previous candidate's notification route.

The separately reviewed
[assignment recovery](execution-plans/2026-10-15-ordinary-assignment-recovery.md)
is installed on both clones and all six company engines. The retained captured
native corpus has complete original/canonical observation coverage without
terminal technical errors; its exact proof and the fresh ordinary acceptance result are
separate records in that plan. Assignment-specific read bounds are documented in
[task assignments](task-assignment.md). Public pins and automatic reconciliation
are unchanged.
Exact source, preimages and receipts belong to the respective delivery plans.

## Bounded ordinary triage — installed producer

The local [workset candidate](execution-plans/2026-10-18-bounded-triage-workset.md)
records the actual recurring task and draft-review inventories before discovery,
without extra upstream reads. Full discovery and every held bucket stay visible.
A private owner/run-bound cursor reserves at most two exact conversation revisions
across inbound, task-only requests and draft re-decisions. One slot serves fresh
newest work and the remaining reservation order rotates older work. Reservations
never mean handled, answered or closed, and provide no cached action authority.
New inbound/provider identities change an ordinary conversation revision.

Scheduled CLI guards refuse unselected deep reads and contextual composition
before their upstream calls. Selected roots still pass all current assignment,
dossier, history, dedup and engine guards. Only address takeover blocks an entire
contact; a held sibling root does not. Deferred roots and draft verdicts remain
explicit pending work. Native evidence-agent tools are denied for the ordinary
operator; separate custom prompts do not acquire these scheduling restrictions.
Incomplete workset evidence is a technical health failure using existing symbolic
notices. No model is needed for scheduling, checking or alerting.

The workset, foreground/inventory and typed read-outcome repairs are installed
in both clones. Bounded selection
does not bound full discovery/review latency or prove a successful native terminal.
V18's real Café draft and received MrCall reply passed their provider checks, but
the Café tick reached 45 minutes without completing. The source composition below supports evidenced automatic-task metadata; actual
ordinary native acceptance remains unverified. No paid retry, larger
budget or deadline, release, or signed PASS follows from this source change.

## Scheduled email intake — installed source

The installed [mail-intake source](execution-plans/2026-10-13-scheduled-mail-intake.md)
performs one authenticated `sync.run` with `scope=email` and `days_back=14`
after permission validation and before probing or launching either assistant
model. It requires the engine to echo `scope=email`, return a boolean successful
result and an empty errors array; busy or warning results also stop the tick.
An older engine that ignores the scope cannot satisfy this prerequisite.
The fallback shares the completed intake. A pause before intake prevents it;
a pause during intake prevents model launch afterward.

This prerequisite synchronizes the selected owner's configured email mailboxes
without WhatsApp, memory extraction, task classification or paid generation.
Paid automatic-processing settings, model budgets and send permissions retain
their independent controls. Success does not prove complete folder/message
coverage: missing exact original bodies remain unknown and cannot authorize
reply generation.

Authentication uses the existing synchronous HTTP request timeout separately
from the 180-second asynchronous connection/request wait. Socket close and
reader cleanup each have a two-second limit, with transport abort on failed
close. These client limits do not cancel actual server ingestion. The separately
reviewed engine contract retains its synchronization lock until actual work
finishes. Failed or malformed intake stops before either model and records a
credential-free operational problem; the next eligible scheduled tick tries again.
Both normal clone interpreters use clean immutable local release packages;
`cs verify-install` and the current release plan own their actual-byte verification.
Historical hosted-override and R9 evidence certifies only its frozen candidate,
not current ordinary queues or public Git installation provenance.

## Scheduled reply origin — installed source

The source-reviewed [provenance caller](execution-plans/2026-10-13-scheduled-reply-provenance.md)
opts in only in the engine branch when the existing launcher supplies
`CS_HEADLESS_SEND=1` and the caller allows `send_draft`. Read-only and direct
classification paths retain their behavior. One capability query includes
`operator_reply_provenance`; only integer version 1 permits `operator_origin`
`scheduled_operator` with `operator_origin_version=1`. Unsupported or malformed
support refuses before the chat request; requested intent is never dropped.

This is authenticated caller-asserted automation intent under the trusted-host
boundary. It grants no send permission, proves no cryptographic launcher origin,
and provides no assignment exemption. Existing approval predicates remain
independent. The corresponding engine contract requires exact owner/root/target
and complete unheld current authority immediately before opted-in SMTP, scoped
context isolation, truthful outgoing automation headers and complete References
persistence. Manual/default requests and historical rows retain their meaning.
The two hosted ACTOR engines and four assignment peers now use the independently
verified R8 deadline-cleanup repair; Qonto is excluded. The same previously failing
Sent source now verifies as complete AUTOMATIC with NORMAL/unheld root authority.
This read-only recovery proves the repair, not complete operational acceptance.
Both ACTOR engines advertise integer capability 1. R9 verified both ordinary
clone interpreters on the approved 116-file workflow/provenance base `9857f1bb…`.
Both maintained clones run clean immutable local release packages; the living
context records their exact version and pending FULL/public provenance. Earlier scoped hosted acceptance
is retained below. Activation and adoption evidence live
under `/tmp/operator-operational-evidence/full-completion-plan/postterminal-authority-observer/activation/`
and `/tmp/mrcall-ai-kit/exact-draft-live/scheduled-reply-provenance/`.

## Current authority in ordinary triage

The reviewed workflow correction distinguishes a discovery-time UNKNOWN snapshot
from the later ordinary exact-thread status read. Only a new fully typed complete
normal/unheld peer-merged result for the same actor/owner/company/root and original
RFC message can recover that transient read. Human assignments and every current
unknown or independent business hold still refuse. Generation keeps actual source
body, existing mode/tool authority and current effect-time guards. Discovery must
be inspected consecutively through EOF; retained complete bytes alone are not
proof the model inspected them. The source checks and M4 source review pass;
both ordinary clone packages and canonical workflows are independently
verified adopted for historical R9. Its retained complete acceptance is recorded
below. Current exact-candidate ordinary-run health and FULL remain owned by the
canonical release plan; component evidence alone does not certify them.

## Optional complete discovery evidence

The local [native-stream diagnostic candidate](execution-plans/2026-10-18-private-native-stream.md)
retains ordered stdout lines admitted by the supervisor's bounded four-million-byte
cap as `native-stream.jsonl` in its private per-attempt run directory. The saved
bytes preserve whitespace and malformed data; the existing fallback-key redaction
also applies before storage. `native-stream.json` records the retained-byte digest,
counts, child identity, process exit, overflow and recording status. Files are0600
inside the0700 directory. Retention is incomplete on overflow or recording failure;
an unavailable manifest is not proof. These private files may contain mailbox
content and tool arguments and must not be published. No additional model call,
retry or permission is introduced. Recording failures leave execution and strict
acceptance decisions unchanged. Both maintained clones carry this local source
candidate; fresh ordinary acceptance remains pending.

The [ordered continuation candidate](execution-plans/2026-10-18-native-background-continuation.md)
recognizes repeated native init/result segments only through the evidenced
same-session background-task protocol. Init configuration stays identical apart
from UUID, result indices are sequential, and native task/run/tool completion IDs
must explain each resumed terminal's explicit task-notification origin. All tasks
and callbacks must finish; foreign sessions, duplicates, pending or failed tasks,
unexplained results and failed terminals remain rejected. Original init IDs and
raw event evidence are retained. The supervisor emits an explicit version1 proof,
which the candidate Desktop consumer requires for repeated init IDs. Discovery's
canonical foreground invocation, complete capture/source/process join and native
inspection remain mandatory. This legacy version1 path does not admit background
discovery; the separate version2 source composition below owns that boundary. One genuine isolated native stream supplies protocol
evidence; constructed negatives and source checks establish no ordinary mailbox
acceptance. Both maintained clones carry this source candidate, with approved
composition review; fresh ordinary acceptance remains pending.

The installed [discovery transport](execution-plans/2026-10-13-operator-discovery-proof.md)
captures the complete output of the canonical
`.venv/bin/python -m cs unanswered --days 14 --json --all-buckets` during
explicit operational acceptance. `CS_OPERATOR_ACCEPTANCE_RECEIPT` and its
existing nonce enable the private receipt path. With capture disabled, the CLI
performs no optional receipt I/O. Capture preserves ordinary stdout, stderr,
semantic exit and business decisions; exit 3 remains incomplete/held work.

The [helper](../cs/operator_discovery_receipt.py) uses an isolated capture worker
under a five-second parent deadline, retaining the actual CLI parent's process
identity. Overdue owned workers are killed; ordinary interruptible workers are
reaped. Uninterruptible operating-system I/O is not claimed instantly quiescent;
an unaccepted partial may remain when bounded cleanup cannot complete.
Private directories and committed regular files require owner-only permissions.
Nonblocking receipt opens reject FIFOs and other nonregular files.

The supervisor joins one complete receipt to one genuine canonical native
use/result/session through exact owner, nonce, CLI/native/supervisor process and
start identities, argv, pinned platform-wrapper grammar and package digest.
Missing, ambiguous or mismatched evidence earns no phase. Full capture does not
prove model inspection; canonical guidance requires complete bounded reads.
Local source checks pass. Historical genuine joins and hosted R9 acceptance,
including complete native receipt inspection, certify their retained source
hashes. Current recovery requires its separate exact-candidate ordinary case.

## Direct kernel calls

[`rpc.chat`](../cs/rpc.py) normally calls engine `chat.send`. Its optional
`CS_LLM_ROUTE` branch applies only when an explicit role is supplied; this is
not a global routing policy for every classifier.
[`send_guard`](../cs/send_guard.py) invokes
[`worker_llm.classify`](../cs/worker_llm.py) directly without that switch.
The worker uses a separate provider client, currently with two default SDK
retries; it does not reserve spend in the engine ledger.

[`model_config.py`](../cs/model_config.py) layers platform env, clone state env,
repo `.env`, then process environment (highest precedence). `CS_LLM_PROVIDER`,
`CS_LLM_BASE_URL`, `CS_LLM_API_KEY` and provider keys choose its endpoint/auth;
`MODEL_CLASSIFIER`, then `MODEL_WORKER`, then role/provider defaults choose the
classifier model. These are distinct from engine `LLM_PROVIDER` settings.
Changing a key through Desktop Settings does not populate the clone's env.
A classifier's historical evaluation does not certify memory or merge quality.

## Read-only engine questions

`cs ask` first requires `system.capabilities.chat_read_only_policy == 1`, then
sends `mutation_policy=read_only` and `policy_version=1` with `chat.send`. It
refuses an older engine rather than treating an empty approval allowlist as a
mutation policy. Published supervised `cs chat` and `cs draft-reply` retain
their released contracts. The local unreleased [contextual-email candidate](task-assignment.md#contextual-email-policy--unreleased-candidate)
retains stronger capability negotiation for explicit context-bound operations.
The [compatible local caller](execution-plans/2026-10-13-released-email-caller-compatibility.md)
restores the released ordinary chat, scoped-draft and exact-ID send contract on
hosted engines; supplied newer bindings never fall back to unbound calls.
The scheduled wrapper also denies raw RPC entry points that run
update, reconsolidation, memory join/reset/restore, preparation resume or
`instructions.store` in every supported command spelling; the wrapper denies
the `cs instructions` verb itself the same way — compiling and storing the
operator's standing instructions stays an interactive gesture.

## Inspect before recommending or pausing

- Read the clone wrapper and its installed cron entry: company extensions may
  replace the generic draft-only wrapper and its send permissions.
- Check that clone's pause marker and running processes separately. A scheduled
  entry plus absent pause marker proves eligibility, not a successful recent tick.
- Inspect the actual Claude model/auth configuration without printing credentials.
- Inspect engine `usage.today`, saved model policy and preparation status through
  authenticated RPC; report which profile was checked.
- `cs llm` shows the separate kernel provider/model resolution. `cs llm test`
  makes a real provider call and is not a free configuration check.

Pausing the wrapper does not stop the independent engine daemon. Pausing engine
preparation does not disable the cron, Claude reasoning or direct classifiers.
No single existing control is a global spending or process kill switch.

## Retained hosted development acceptance

Genuine r9 (`ecc64a8400e35d6f699a9c193ba5e399`) passes the unchanged strict
seven-check matrix on the actual installed kernel `9857f1bb…` and repaired
six engine runtimes. MrCall sends the correct 212 reply; Café creates exact
engine draft `71589012-ba68-4e7d-8e31-f45df722c349` with result311 and one
provider mirror without sending. Both operators terminate naturally with exit0.
Signup's documented policy passes with legacy exit1, not three zero exits.
The new Sent source is complete AUTOMATIC, root authority complete NORMAL/unheld,
and the actually received reply is classified automatic with no additional
received/sent/provider-draft/engine-draft effects. No manual intake or substituted
model output supplies native generation. Cleanup restores exact cron759ab3,
removes owned enrollments/markers/processes and preserves six runtimes plus Qonto.

The original signed result and complete pre/post1053-object tested source are
retained before documentation edits at `/home/mal/.local/share/mrcall-operational-evidence/2026-10-14/after-repair-full-checkpoint-guard-r9`. Retention manifest SHA-256:
`0701b581b092c6c0360d159dc36cedd3bbe949e33e6ec5c9b229b11ce08b8482`.
This is `development_hosted` acceptance; public installer/release and native
Gmail browser/mobile/API edit/send preservation remain unverified. Automatic
reconciliation remains off. Earlier failed runs stay failed and unsigned.
Operational acceptance remains separate from checker-governed documentation
completion and public release.
Independent operational APPROVED: `/tmp/mrcall-ai-kit/r9-acceptance-verification/report.md`,
SHA-256 `7de3884807f781e8a0aa5391113c6652ba059f378d6fe764a3aee124492435bc`.
Actual native inspection covers both complete physical receipts through EOF.


## Native Bash composition — installed producer and local repair

The [composition candidate](execution-plans/2026-10-18-native-bash-lifecycle-composition.md)
binds ordinary scheduled task metadata to the known prelaunch-pinned executable
and actual child. Direct launches resolve the executable before launch. An
explicit CS_OPERATOR_NATIVE_BINARY separately identifies the emitter behind an
exec launcher; the launcher, its arguments and its authentication/budget behavior
remain intact. The MrCall clone's one-line primary-branch emitter export remains
active with the clean immutable kernel package. Its existing budget wrapper is preserved;
public-tag provenance and current whole-workflow acceptance remain pending.

Version2 preserves every original init and result in order, strict indexed
successful terminals and actual callback origins. Complete foreground, explicit
background and evidenced automatic false-to-true tasks are separately bound.
Only validated task/membership metadata leaves the literal control projection;
original/projected hashes and exact removed indices remain in the proof. Known
thinking counters, pending Bash heartbeats, closed tool permission pairs and the
observed allowed-rate envelope remain literal. Other billing telemetry shapes
remain unsupported. Unknown events, Agent/Task/workflow work, interrupted tasks,
other asynchronous failures and absent original terminals refuse. The original
version1 continuation validator remains byte-identical; legacy foreground and
custom signup behavior remain supported.

Canonical automatic discovery still requires the complete private physical
capture, exact native payload plus numeric exit trailer and owner/nonce/process/
source joins. Its actual task record supports one or multiple complete segments.
Native launch false/null is preserved; typed completion carries exit0 or legitimate
held-only3. Full inspection precedes contextual draft-reply and chat. The Actor
consumer checks explicit version2 producer/child/session, hashes, counts, task,
removal and actual callback bindings before accepting multiple init IDs.

Producer/configuration readback establishes component adoption. Complete ordinary
acceptance additionally requires inventory inspection, actual provider outcomes
and signed candidate-specific evidence in the current release plan. Failed
historical cases remain retained there.

## Complete semantic global inventory

The [reviewed component](execution-plans/2026-10-19-semantic-complete-inventory-view.md)
creates separate private inventory-view.jsonl, inventory-view-envelope.json and
inventory-view-progress.json beside unchanged discovery.json. The readable view
keeps every global root/group/ordered occurrence, ownership/hold/error/reason,
material fact, workset selection and ordered observation semantic judgement.
Opaque commitments and selected message/provider navigation stay RAW REF, not
native-inspected case detail. Unknown fields/material shapes refuse compact use.
Scheduled v2 requires the paired material view and envelope, including tasks and
review rows; raw discovery alone cannot replace that recurring material.

Envelope/raw/view hashes, owner/nonce/ancestry/supervisor/source bind the exact
projection. Actor independently recomputes its typed field/universe parity and
matches native stream commitments/process/session to complete genuine automatic
context or exact successful bounded dd results for BOTH envelope and view through
EOF before recognized effects. Current
engine guards and fresh selected-root deep reads remain required. The assessment
is after terminal, not an additional runtime action-prevention gate; separate
ordinary inspection status prevents clean native terminal from implying success.

Private bounded nofollow/owner/mode/nlink checks reject substituted artifacts.
The source emits an exact initial page plan and updates remaining offsets from
actual matched page results. Progress reads are OPTIONAL recovery hints, never
mandatory after every page, never coverage or polling. Independent literal dd
calls may be issued together; no shell loop/script/summarizer or synthetic native
messages are introduced. No extra model requests or permission/budget/engine/
scheduler change. The historical pre-framing replay uses six view pages plus one envelope
(43,313 bytes); about56% fewer bytes and46.15% fewer calls than13
raw reads, withoutUSD4 or compliance guarantees. The historical117-file semantic payload retains its offline evidence; current
installed package identity belongs to `cs verify-install` and the release plan.
Current compact/native and ordinary/provider acceptance remain separate gates.

## Source-bound business read outcomes

The installed [read-outcome contract](execution-plans/2026-10-19-native-business-read-outcomes.md)
preserves three finite observational exits: exact `assignment status ROOT --json`
typed human/ancestry-conflict hold3, complete single-mailbox `contacted` absence1 and complete configured
scope `history` absence1 (prose or JSON). Typed private capture uses already
computed results, without extra upstream or model requests. A uniquely joined
receipt binds the ordinary health nonce, owner, source digest, process/start
ancestry, shell/argv, root or contact/query/window and exact native result/code.
The acceptance envelope's separate nonce remains unchanged. Actor independently
checks the exported typed and native bindings. Human/configured-peer evidence
grants no action authority; required discovery/review phases remain mandatory.

Unreadable, unknown, partial, duplicate or foreign evidence is not an observation.
Other canonical read errors, raw RPC errors, off-workset deferral and failed
effects remain unhealthy. Public CLI output, codes, flags and effect-time guards
are unchanged. Scheduled factual sources use selected RFC roots; off-workset
corroboration is deferred without its RPC. Complete task output is inspected
through built-in Read with paging, without Python/shell summarizers or another
review. Installed/free controls certify this component, not a new ordinary or
provider acceptance, permission to retry, or public release.

## Scheduled root-bound exact sending

The installed [compatibility route](execution-plans/2026-10-19-bound-send-workset-compatibility.md)
uses `draft-reply --thread-id ROOT` followed by the full successful engine draft
ID in `draft-send`. Scheduled send requires existing send mode and its launcher
marker. The actual looked-up row must match its selected root, known owner and
same-run snapshot of recipients, body, headers and attachments. A complete typed
review may bind an existing ready draft; incomplete or changed evidence refuses.
Current assignment and exact-ID approval checks remain mandatory. Only confirmed
sending permits exact mirror retirement; retirement failure warns without resend.
MrCall's six exact-send grants replace six generic-chat grants; Café has no send
grant. Health recognizes exact-send failures using the existing symbolic notice
path. Full discovery and ordinary generation retain their existing costs/limits.

## Installed foreground and inventory repair

The [repair](execution-plans/2026-10-18-native-foreground-held-composition.md)
recognizes canonical foreground discovery3 only with agreeing original native
notification/error envelopes and complete physical capture. Each held task needs
its own tool/session-bound joined phase. Missing transport prevents a clean
protected receipt; later health assessment preserves that failure. Actor checks
foreground3 only for the exact complete discovery transport and still rejects
technical review failures. Known telemetry, original terminals and literal
false/null values stay unchanged. Killed tasks remain invalid.

Observer failures expose allowlisted reason/key codes on stderr and in a private
workset failure record. Native refusal receipts expose a bounded reason and event
index/type. Diagnostics grant no authority and include no customer payload.

Draft identity inventory now has source-owned SEARCH/FETCH coverage and exact
Gmail UIDVALIDITY/UID and engine-ID reconciliation. Complete typed proof may
coexist with visible policy/BCC notes; failed reads, reconciliation, dropped or
foreign identities still refuse. Per-row body, identity, date, root, verdict and
mailbox gaps remain held before discovery/task/review selection. Missing-root
holds retain every To/CC recipient, including list/display representations.
Without typed proof, legacy nonempty notes still refuse. Scheduling, checking
and alerts are symbolic; full review reconciliation can separately use a model.

Source regressions combine real local capture with labelled constructed controls.
Unchanged genuine V18 MrCall lifecycle passes replay; two other complete streams
contain killed tasks and refuse. V19 technical review3 and Café's zero-result
stream remain negative. One audited raw snapshot read39/74 engine and3/7 Gmail
drafts with complete UID/identity coverage; all projected verdicts were explicitly
unobserved/held. It proves input shape, not reply/draft authority or acceptance.
Source adoption is verified separately from ordinary acceptance; no additional
paid case or release follows.

## Native inventory context delivery and retained EOF framing

The canonical producer offers48 bounded slots at both PostToolUse and
UserPromptSubmit. Both normal clone interpreters must pass `cs verify-install`
against the declared immutable release before adoption is considered verified.
Hook settings alone do not prove native delivery or ordinary acceptance.

Installed66 prefers8000-character parts of the exact paired envelope and
view. If any complete part exceeds the existing UTF-16 bound, the whole
payload uses the original7000-character partition. Native acceptance requires
separate proof of complete current inspection; installed byte checks alone do
not establish it.
Every complete visible value must remain below10000 UTF-16 units. Input is
bounded at4MiB. Reserved markers, stale or foreign files, wrong owner/nonce/
session/source/process, duplicate parts and missing parts grant no compact proof.
An initial boundary without published artifacts is not a technical error; a later
boundary can deliver current artifacts but cannot repair an earlier effect.

A valid snapshot requiring more slots records finite `discovery_context_capacity`
/ `context_slots_exhausted` evidence with required and available counts and the
safe producer origin. The private diagnostic contains no mailbox content or
exception text. Capacity refusal grants no inspection credit; valid complete
literal paging remains supported. Diagnostic recording does not authorize replay.

Kernel assessment and the independent Actor consumer require complete genuine
paired payloads before effects. Indexed reconstruction preserves exact bytes and
actual event order. Complete current automatic context is an alternative to the
literal page plan; generic hook execution, partial context and progress are not
coverage. Every retained task/review row, hold, root and semantic judgement remains
mandatory. RAW REF details require fresh selected-root authority, thread, dossier,
history and dedup reads before effects. Existing engine action guards remain
mandatory; inspection assessment is post-terminal.

Deduplication is per exact snapshot/session/part. Failed delivery after writing its
marker can leave missing proof; no replay is authorized. Runtime budgets, quota
and deadlines remain unchanged. A forecast of future cost does not prove budget
exhaustion or justify abandoning unread material; actual limits leave incomplete
inspection visibly failed. Source checks establish protocol behavior only.
Genuine native retention, affordability and strict BOTH-clone FULL remain required
for the candidate's release acceptance. The release plan owns current results.

Scheduled dossiers retain complete correspondence/Sent and fresh exact selected-root
assignment authority inside a600-second lifecycle including20-second cleanup.
Task-list rows provide auxiliary context, never complete absence. Malformed or
explicit failures refuse; ready clears only a read-failure marker. Fresh engine
draft/send guards remain mandatory. In-progress/failed attempts hold their roots.
Actor runner timing and native permission acceptance remain separate obligations.


The hook validator admits one observed full-output `hook_progress` duplicate per
pending known hook. Its exact identity/session/name/event and field set must
match; output is nonempty, equals stdout and must exactly equal the later
successful final stdout, with matching empty stderr. Missing, repeated, foreign,
changed, out-of-order or otherwise unsupported progress refuses. Progress alone
grants no context, tool-result or terminal coverage. The complete original
stream and its projection hashes/removal indices remain retained. Only genuine
successful final responses can establish paired inventory inspection.

Private native stdout/stderr capture is bounded at4,000,000bytes. The unchanged
1,915,431-byte genuine prefix plus a finite constructed continuation exceeds the
old2MBbound; free tests verify exact4MBretention and refusal above it. Constructed
continuations prove capacity only. The source repair's exact native-prefix replay
does not supply a missing terminal or certify a new installed package's FULL.
