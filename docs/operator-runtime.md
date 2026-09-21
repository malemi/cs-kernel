# Operator runtime, models and spending

The agent host executes the skills; the `cs` CLI executes their commands. In an
interactive workspace the host is the user's chosen coding agent. Unattended
operator ticks use Claude Code, launched by the generated
[`bin/cs_operator_cron.sh` template](../cs/templates/project/bin/cs_operator_cron.sh.j2)
as `claude -p "/cs-operator"`. This is distinct from a headless engine daemon:
that daemon is an RPC service whose LLM work uses provider APIs.

| Execution path | Model/auth owner | Budget boundary | Pause boundary |
|---|---|---|---|
| Claude Code operator reasoning/tool selection | Claude process flags, settings, environment and login; template selects neither model nor billing mode | Claude's own account/authentication and limits; not the engine ledger | Wrapper checks `~/.<slug>-cs/CS_PAUSE` before launch; does not terminate a running process |
| Engine analysis, memory, task judgement and contextual generation | Active engine profile `LLM_PROVIDER`, model preset/role overrides and personal key or MrCall credits | Engine profile's daily reservation ledger | Preparation pause/automatic-update settings govern processing; budget zero refuses new paid engine requests |
| Kernel direct classification | Clone/provider env and `model_config.py`, independent of engine profile | Direct provider billing; no engine reservation or daily cap | Not disabled globally by `CS_LLM_ROUTE=engine`; caller-specific guards apply |

An operator tick can spend on all three paths: Claude reasons, commands request
engine generation, and a send guard requests its own classification. Read-only
RPCs do not themselves generate engine LLM spend; a draft-only policy does not
make reasoning or generation free. Charging Claude to a subscription rather than
API billing must be checked in its actual runtime authentication, not inferred
from `claude -p` or the engine's credentials. The wrapper supplies no `--model`
or `--max-budget-usd` flag. Never assume the engine's selected model is Claude's.

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
update, reconsolidation, memory join/reset or preparation resume in every
supported command spelling.

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
