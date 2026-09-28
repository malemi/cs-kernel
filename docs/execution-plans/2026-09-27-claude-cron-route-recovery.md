---
status: active
---

# Claude Code cron route recovery

Brief: [2026-09-27-claude-cron-route-recovery.md](../briefs/2026-09-27-claude-cron-route-recovery.md).
Brief review: APPROVED after the adversarial pass replaced an unsupported
credential-isolation claim and made the paid fallback's per-tick budget
explicit. The review also confirmed that this is a cron-harness change, not an
engine-provider change.

## Implementation boundary

`cs/templates/project/bin/cs_operator_cron.sh.j2` is the single scheduled
entry point. Its lock and pause checks stay in the shell. A kernel supervisor
module owns process results, route selection, secret retrieval and notification
state. The wrapper passes its one literal `--disallowed-tools` list to that
module for both launches. No skill or model output decides to retry or send an
alert. The supervisor exposes no general operator verb and never grants a
customer-send command.

The settings path is `cs/manifest.py` `[knobs]` → `cs/config.py` `Settings` →
supervisor. `cs/project_init.py` must preserve the new values during `cs
update`, and `cs/templates/project/manifest.toml.j2` must stamp them. This is a
new manifest surface, so the release is MINOR. The existing broad recovery
plan still owns engine generation and direct classification.

## 1. Prove the retry signal and alternate route

Owner: `cs-kernel`. Capture Claude Code's machine-readable process events,
stderr and exit status in an isolated, supervised probe. Confirm the observed
weekly-limit message appears before any tool event. Define an allowlist of
specific immediate access/quota/payment refusals, anchored to the actual
process result; everything else is non-retryable. If the host cannot prove
that no tool ran, stop and alert instead of replaying the tick. Include a
result size limit so a runaway agent cannot fill the state directory; a
truncated or unparseable event stream is non-retryable.

Resolve the primary model used by this clone and test one explicitly selected
equivalent Claude model through OpenRouter. Use process-only fallback
credentials so the interactive Claude login is unchanged. An isolated Claude
configuration was rejected in the live probe because Claude Code stopped
trusting the workspace and ignored its permission allow list. Verify the
gateway's auth selection, model, skill loading and tool-call event shape. The
clone's saved OpenRouter key reported a $20 daily key limit on 2026-09-27;
verify remaining capacity at activation without treating it as a promise of
future credit. Measure a representative tick's usage before choosing the
clone's per-tick budget; absent evidence or an explicit budget means no paid
fallback. Measure whether tool subprocesses inherit the key and record the
result. Do not put the key in a command argument, persistent settings or log.
If Claude Code cannot use the route without altering interactive auth, stop
this design before implementation.

Gate: a measured pre-work refusal and a working alternate route, or a clear
non-retryable outcome. No cron installation at this stage.

## 2. Build deterministic recovery and owner notice

Owner: `cs-kernel`. Add a small supervisor used by the generated wrapper.
Add `cron_fallback_model` and `cron_fallback_budget_usd` under manifest
`[knobs]`, carry them through `Settings`, and require an explicit supported
model plus a positive budget before launch. Preserve those values in `cs
update` and show the effective, non-secret configuration in `cs config`.
Fetch only the saved OpenRouter secret through the authenticated owner RPC
inside the supervisor; never ask the agent to fetch it. An absent secret,
invalid budget, incompatible model or unavailable engine produces a failure
state; none triggers a speculative model call.

The helper launches at most one fallback process using the same command and
deny arguments as the primary. It records primary/fallback route, effective
model, reason and outcome without prompts or credentials. Send a fixed notice
through `cs/send_mail.py` with human-authored `plain`/`html` content, never
`body_md`; the `tests/run.sh` boundary forbids another SMTP implementation in
`cs/`. Use `Settings.email_address` as sender and recipient, begin the subject
with `URGENT`, and describe a route or model change or complete stop. Persist
pending transitions and the last delivered state atomically under the clone
state directory while the cron lock is held. Mark a notice delivered only
after SMTP confirms the send; log and retry pending notices later when
delivery fails. Make the return to the primary route a reportable recovery
state. Do not claim exactly-once delivery after an ambiguous SMTP failure.

Gate: focused tests at the supervisor's real process and SMTP boundaries show
one fallback, one notice per state transition, no LLM in routing or mail, and
no secret in logs or process arguments. Tests cover failed SMTP followed by a
later retry. Review this milestone before wrapper integration.

## 3. Wire the generated cron wrapper and verify safety

Owner: `cs-kernel`. Keep `CS_PAUSE`, `flock`, working directory and
`CS_OPERATOR_HEADLESS` in their current order. Pass one shared literal deny
array to the supervisor for both Claude invocations; preserve every denied
spelling and the clone-local script denies. Extend `tests/run.sh` gate 17 to
prove the list reaches both attempts; its current parser assumes the list
appears directly on one `claude` command. A successful primary tick remains
one invocation. A primary result with any tool activity never starts a new
process. Recheck `CS_PAUSE` immediately before the fallback launch while the
same lock is held.

Test the rendered wrappers for both maintained clone manifests with fake
Claude processes: immediate quota, alternate success, alternate refusal, tool
event before failure, truncated event stream, timeout/unknown error, primary
recovery, pause before fallback and overlapping lock. Verify fixed owner-mail
messages through a local fake SMTP server. Run `bash tests/run.sh` and inspect
the wordlist gate. Review the
integrated milestone before live verification.

## 4. Supervised live acceptance and delivery

Run one draft-only alternate-route check with the configured per-tick budget.
Confirm the model and tool permissions from events, inspect the provider's
recorded use, and send one owner-only test notice. Compare the result with the
preflight findings; stop rollout on auth conflict, unknown model, leaked
credential in output, unexpected permission, or unbounded spend. The Claude
`--max-budget-usd` limit is soft: a live minimal call exceeded a $0.05 setting,
so the provider-side key cap remains required. Do not send
customer mail during verification.

Perform a separate final review through the generated clone path. Reconcile
the brief and plan with results. Follow [release-procedure.md](../release-procedure.md)
for the MINOR version, CHANGELOG entry, both-clone FULL collaudo before tagging
and the clone upgrades. Do not push without the operator's explicit approval.
Rollback is the prior pinned kernel tag and prior generated wrapper; the
saved provider choice and customer records remain untouched.

## Plan review

APPROVED after a separate adversarial pass. The plan has a narrow owner, an
ordered proof-before-retry gate, explicit stop conditions, a single permission
list for both attempts, the repository's SMTP boundary, focused verification,
and the required release checks. The review repaired two gaps: a truncated
event stream is not proof of no work, and the pause file must be rechecked
before the second launch. This pass was performed in-session without an
independent reviewer; implementation still receives milestone integration
reviews and a separate final review.

## Implementation and acceptance record (2026-09-27)

- Implemented `cs/operator_recovery.py`, the shared wrapper deny array, the
  manifest/Settings fields, fixed owner notices and durable notice retries.
  A three-hour watchdog stops a hung process without replaying its work.
- `bash tests/run.sh` passed every gate. Gate 17 checked both rendered deny
  lists; gate 59 exercised quota, payment, post-tool failure, timeout, route
  recovery, model change, SMTP failure and retry with real child processes.
  `git diff --check` passed.
- A live clone-workspace OpenRouter probe used the configured Claude model,
  executed one `Bash(pwd)` tool and completed. Its effective model was
  `anthropic/claude-sonnet-5`, reported cost $0.1494388. A second safe probe
  confirmed that a Claude tool subprocess can read `ANTHROPIC_AUTH_TOKEN` from
  its environment; it printed only whether the value was present. Its
  reported cost was $0.0902528. No workspace-trust warning appeared.
- One fixed test notice to the clone owner's own mailbox was accepted by its
  SMTP server. This proves the current mailbox send path; it does not prove
  delivery to the inbox or a cron-triggered notice.
- The clone still has no fallback model or budget configured, and this kernel
  revision is neither released nor installed there. Full two-clone collaudo,
  tag, clone upgrades and production cron acceptance remain release work.

## Supervised clone probe (2026-09-28)

The clone still runs kernel 0.46.0 and its installed cron has no supervisor.
With its actual 70 deny rules, the uninstalled supervisor source was invoked
under the cron lock and `CS_OPERATOR_HEADLESS=1`, with an environment-only
OpenRouter model and $1 per-tick budget. Claude Code immediately refused with
its weekly limit. OpenRouter ran and charged about $0.24, then returned HTTP
402: the next request exceeded available credits given in-flight requests.
The supervisor stopped with exit 1 and sent the `URGENT` owner notice. IMAP
confirmed that message in the owner's Inbox at 09:56 UTC. The initial message
was too generic; the subsequent code change classifies HTTP 402 explicitly in
future notices, and its focused process/SMTP test passes. This probe does not
activate the fallback in the installed cron. Release and clone upgrade remain
open.

## Owner account identification before release (2026-09-28)

The owner requested an actionable key/workspace identifier in every fallback
notice. The ordinary saved key successfully queried OpenRouter's read-only
`GET /api/v1/key` endpoint. It returned a workspace ID and key creator user ID;
the clone's engine profile UID and mailbox come from `Settings`. The supervisor
now mails those distinct identifiers and a short, locally derived start/end
fingerprint of the key actually passed to Claude. It never sends the full key
in a notice or uses a management key. A failed metadata lookup leaves provider
IDs explicitly unavailable and does not suppress the alert. Focused tests
cover the mail fields and the fingerprint. Release remains open.

## v0.47.0 release candidate review (2026-09-28)

An isolated worktree at `/home/mal/hb/cs-kernel-v0.47.0-candidate` starts from current
main and carries only the scheduled-Claude recovery change. The unrelated
pricing skill and its triage edits remain in the original working tree. The
candidate's `bash tests/run.sh` passes all gates; `git diff --check` passes.
Rendering the candidate wrapper with each maintained clone's actual manifest
produces 106 deny entries for `124-cs` and 120 for `mrcall-cs`, including its
one local script. Candidate `cs whoami` and `cs cron status --json` pass on
both live profiles. `124-cs` candidate `cs campaign pending` passes.

Read-only `cs review --json` did not finish within the initial 120-second
bound on either clone. The installed baselines also did not finish within 65
seconds at the same draft-reconciliation stage. With a 300-second bound, the
candidate review completed on both clones and produced valid JSON (69 draft
rows for `124-cs`, 49 for `mrcall-cs`). `mrcall-cs` candidate `cs campaign
pending` did not finish within the initial 35-second bound; its installed
baseline also timed out at 35 seconds. A longer candidate run completed
successfully within 180 seconds. These
short-bound timeouts are recorded rather than presented as success.
MrCall's installed cron uses its clone-owned send-mode wrapper, so this
kernel wrapper change does not alter its live cron route. Neither clone has
been upgraded or given fallback manifest values. No release commit, tag or
push has been made.

The proposed release number is `v0.47.0` (MINOR: new manifest fields and
changed scheduled behavior). The release note must name the fallback, key and
workspace identification through the ordinary OpenRouter key, the existing
unreleased main-branch changes since `v0.46.1`, migration of the two manifest
knobs, and FULL re-collaudo on both clones because the cron permission surface
changes. The operational-pin marker is updated only after both clone upgrades.
The candidate is ready for review, but the release metadata, commit, tag,
second kernel suite at tag, clone re-pins and push remain ordered steps.

### Proposed CHANGELOG entry

`v0.47.0` is MINOR. The scheduled Claude Code wrapper now delegates to a
deterministic supervisor. A structured quota/payment refusal before tool use
permits one OpenRouter attempt with the same draft-only command denies. Any
ambiguous or post-tool failure stops without replay. Fixed `URGENT` owner mail
reports route/model changes and stops, including the partial key fingerprint,
OpenRouter workspace and creator IDs from the ordinary current-key endpoint,
the clone owner and engine profile. No management key or LLM is used for
routing or notice delivery. Two new manifest knobs, `cron_fallback_model` and
`cron_fallback_budget_usd`, must be set explicitly; defaults keep paid fallback
off. The budget flag is soft and the provider key's spending cap is the final
boundary. Existing unreleased main changes since `v0.46.1` also enter this
tag: negotiated read-only `cs ask`, exact-ID `cs draft-send`, Shopify token and
absent-fact handling, and the headless memory-mutation deny policy. The
re-collaudo tier is FULL on both maintained clones because the cron permission
and send-related surfaces change. MrCall's separate send-mode cron remains
clone-owned and needs its own explicit adaptation before it can use this
fallback. The clone upgrades must preserve local changes and pass the version
sweep before the operational pin marker advances.

## Funded-route retest (2026-09-28)

The owner funded OpenRouter and requested another live test before release.
The isolated candidate supervisor ran one draft-only tick under the clone's
cron lock with the candidate wrapper's 208 rendered deny arguments and a $2
Claude budget. The primary Claude process returned its weekly-limit refusal
before tool use. OpenRouter then executed the operator and the supervisor
returned exit 0. The supervisor sent one `URGENT: operator LLM route` notice;
IMAP confirmed it in the owner mailbox's Inbox at 11:09 UTC. Its body reported
the actual `anthropic/claude-sonnet-5` model, the workspace and creator IDs,
and the fingerprint of the key used by that process. The key's recorded daily
usage increased by at least $0.36 during monitoring. The $2 Claude budget is
soft, so this is not a measured final charge.

During the tick, the engine's saved OpenRouter key changed from the one used
by the running process (`sk-or-v1-957a…8178`, workspace
`d93ddc17-4c7c-47ef-8e4d-426cf5197bff`) to another key
(`sk-or-v1-9fb5…7e70`, workspace
`d8a99c82-8e44-5f57-8aa2-92076269247b`). The running process and its
notice consistently identified the first key. A future tick will fetch the
currently saved second key. The OpenRouter current-key `limit_remaining`
field measures the key's own spending cap, not the account's prepaid balance.
The installed cron still runs the old wrapper; no release or clone upgrade has
been made.

The currently saved second key also passed a separate one-response Claude Code
probe with tools disabled: the result was `OK`, terminal reason `completed`,
and reported cost $0.118128. This proves that key can authenticate through
the Claude/OpenRouter route; the complete scheduled tick was exercised with
the first key only.
