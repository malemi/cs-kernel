# Operator runtime, models and spending

The agent host executes the skills; the `cs` CLI executes their commands. In an
interactive workspace the host is the user's chosen coding agent. Unattended
operator ticks use Claude Code, launched by the generated
[`bin/cs_operator_cron.sh` template](../cs/templates/project/bin/cs_operator_cron.sh.j2)
as `claude -p "/cs-operator"` under the kernel's deterministic supervisor.
This is distinct from a headless engine daemon:
that daemon is an RPC service whose LLM work uses provider APIs.

| Execution path | Model/auth owner | Budget boundary | Pause boundary |
|---|---|---|---|
| Claude Code operator reasoning/tool selection | Primary: Claude login. Optional fallback: explicit manifest model and saved OpenRouter key supplied to that process | Primary account limits or fallback key limit; the engine ledger does not cover either | Wrapper checks `~/.<slug>-cs/CS_PAUSE` before launch and again before fallback; does not terminate a running process |
| Engine analysis, memory, task judgement and contextual generation | Active engine profile `LLM_PROVIDER`, model preset/role overrides and personal key or MrCall credits | Engine profile's daily reservation ledger | Preparation pause/automatic-update settings govern processing; budget zero refuses new paid engine requests |
| Kernel direct classification | Clone/provider env and `model_config.py`, independent of engine profile | Direct provider billing; no engine reservation or daily cap | Not disabled globally by `CS_LLM_ROUTE=engine`; caller-specific guards apply |

An operator tick can spend on all three paths: Claude reasons, commands request
engine generation, and a send guard requests its own classification. Read-only
RPCs do not themselves generate engine LLM spend; a draft-only policy does not
make reasoning or generation free. Charging Claude to a subscription rather than
API billing must be checked in its actual runtime authentication, not inferred
from `claude -p` or the engine's credentials. The generic supervisor's primary run supplies no
`--model` or `--max-budget-usd` flag. The fallback, when configured, supplies
both; the budget flag is a soft guard that may be exceeded by one model call.
The alternate key's provider-side limit is the final spending boundary. Never
assume the engine's selected model is Claude's.

A clone-owned executable may supply primary API authentication and its own
budget flag before invoking Claude. Inspect that executable as well as the
supervisor: the generic primary flags do not establish the clone's actual
billing route or cap.

The supervisor in [`operator_recovery.py`](../cs/operator_recovery.py) starts a
second Claude process only after a structured, immediate quota or payment
refusal proves no tool ran and no tokens were billed. It reuses the same prompt,
command allow list, command deny list and headless send marker for both attempts.
Before launching Claude, it checks that a `send` triage mode has explicit send
permissions and the headless send marker, while a `draft` mode has neither.
A mismatch stops the tick and sends the owner an urgent notice. A three-hour
process watchdog stops a hung tick and
reports the stop; it never retries that tick. The manifest must set
`knobs.cron_fallback_model` to an
explicit Claude model route and `knobs.cron_fallback_budget_usd` to a positive
per-tick amount; otherwise the operator stops and alerts its owner. The
fallback key comes from the engine's saved `OPENROUTER_API_KEY` secret. It is
passed in process environment, so tools launched by Claude may inherit it;
the key must have a provider-side spending limit. It is never written to the
Claude settings file or placed in command arguments. Existing workspace trust
and permissions are used for both attempts. A fixed, non-LLM SMTP notice with
subject `URGENT: operator LLM route` reports route changes, effective model
changes and stops to the owner mailbox from `Settings`. Repeated identical
states are deduplicated, and failed notices remain queued in the clone state
directory for a later tick. A notice for a fallback attempt includes the
masked start/end of the exact key used, the clone's owner mailbox and engine
profile UID, and the OpenRouter workspace, key creator and organization IDs
when `GET /api/v1/key` returns them. This read-only endpoint accepts the same
ordinary API key; no management key is needed. If that lookup fails, the
notice still goes out with the local key fingerprint and labels the provider
IDs unavailable.

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
mutation policy. Supervised `cs chat` and `cs draft-reply` keep their existing
contracts. The scheduled wrapper also denies raw RPC entry points that run
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
