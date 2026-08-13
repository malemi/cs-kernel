---
doc_baseline_commit: 60d9fc5
doc_baseline_date: 2026-07-30
---

# Active Context — cs-kernel

Volatile state for the shared kernel of the `<company>-cs` operators. The
durable reference is [`CLAUDE.md`](../CLAUDE.md) (the anti-fork charter, layout,
release rules) and [`CHANGELOG.md`](../CHANGELOG.md) (what each tag changed and
which clones must re-collaudo). This file tracks only what is *current*.

## Released and in use

**Latest release tag: `v0.5.2`. Current HEAD status: untagged.** The release
(tag `v0.5.2`, commit `7c4933c`, 2026-08-09) ships the `cs` console script
with the permission surface finished around it — deny sets enumerate six
command-text spellings (24-entry cron block, settings 65/7), placement-aware
gate — plus the customer-onboarding wall fixes (public install URLs, handled
`ConfigError` for unconfigured verbs, EOF/^C-safe `cs init`, release-tracking
wizard defaults), the reviewed-literals registry replacing the regex-law
charter grep, and the new `cs update` semantics (requirements.txt is
operator-owned; security-critical templates apply with a `*.local-bak`).
All 17 gates green at the tag. Do not move `v0.5.0`, `v0.5.1` or `v0.5.2`.

Both clones were re-pinned to `v0.5.2` on 2026-08-09 via
`hb/scripts/repin-clone-v0.5.2.sh` (backup, HTTPS pin, install, headless
`cs update`, clone-specific deny re-merge, verification). Collaudo against
the v0.5.1-frozen baselines, then baselines re-frozen at v0.5.2: `124-cs`
FULL tier all green (old-vs-new + autotest, 2026-08-09); `mrcall-cs` FULL
tier signed 2026-08-13 — 11/11 ALL GREEN on the same-day re-frozen baseline,
after the 08-09 auth outage (an HTTP-referrer restriction on the shared
engine web API key, since replaced by a dedicated server key restricted to
Identity Toolkit + Token Service in both clones' .env; cs-collaudo LOOP-LOG).
Operators remain paused on both clones.

| Clone | Declared | Locked | Installed | Collaudo |
|---|---|---|---|---|
| `mrcall-cs` | `v0.5.2` | `v0.5.2` (commit `7c4933c`) | `0.5.2` | full — green 2026-08-13 |
| `124-cs` | `v0.5.2` | `v0.5.2` (commit `7c4933c`) | `0.5.2` | full — green 2026-08-09 |

The kernel runs per-invocation from each clone's venv (no long-running kernel
process). The provider side — the engine RPC contract the signed closes need —
is the mrcall-desktop daemons, deployed at `d239e5f` on 2026-08-03. Both
operators remain PAUSED (`CS_PAUSE`); revival is a separate operator action.

## v0.5.1 corrective candidate — release truth gate (2026-08-01)

- Package metadata, changelog, active context and README guidance are checked by
  the release-consistency gate in `tests/run.sh` — repo files plus local git
  refs, no network. Latest release and current HEAD are separate facts, so a
  docs-only commit does not manufacture release drift.
- `v0.5.0` now documents the send-guard/draft-warning behavior and full
  re-collaudo tier instead of pointing at ephemeral agent reports.
- `cs tasks close` now signs the provider call as `actor="operator"` and sends
  a non-empty audit reason. This shape requires the engine RPC contract at
  `677e319` plus the follow-up close-history repair `1367e71` — both deployed
  to the five live daemons 2026-08-03, so the provider side is live. Rollout
  stays engine first (done), kernel second, paused operators last.
- Tagging procedure the release gate imposes: the release commit itself must
  already claim `Latest release tag:` + `Current HEAD status: tagged as` for
  the new vX.Y.Z, so the gate is red in the gap between that commit and the
  tag — commit, tag immediately, then verify the 15 gates AT the tag. The
  first post-tag commit flips the HEAD status back to untagged prose and pins
  the new tag's commit id in `IMMUTABLE_TAG_TARGETS`
  (`tests/test_release_consistency.py`); the anchor cannot ride the tagged
  commit because its own id does not exist yet.
- This section records working-tree intent only; it must not be described as
  tagged, pushed, installed or live before those actions are separately approved.

## v0.5.2 candidate — EOF-safe `cs update` (2026-08-04)

- The two `cs update` conflict prompts resolve a closed stdin (EOFError) to
  the declared keep-local default instead of crashing mid-run; the decision
  is printed. Gate 16 (`tests/test_project_update.py`) proves the real
  `python -m cs update` subprocess path with `stdin=DEVNULL` against a
  manufactured conflict. Not tagged; `v0.5.1` remains the latest release.
  Static re-collaudo at the next re-pin.

## v0.4.0 — multi-provider LLM + template literal purge (2026-07-28..30)

The kernel can now make its own LLM calls, with the provider and model as
configuration. Built in the `feat/multi-provider-llm` worktree, adversarially
reviewed (a subagent review produced 7 confirmed findings — all fixed and
re-verified), and verified end-to-end the way a clone runs it: clean venv,
`pip install "cs-kernel[llm]"`, real billed calls through both OpenRouter and
Anthropic direct.

- **`cs/model_catalog.py`** — the catalog is FETCHED, not hardcoded:
  `GET /v1/models` (no key) gives ids, ship dates and real prices for ~357
  models; 17 curated **families** (`@glm`, `@claude-opus`, …) resolve to a
  product line's newest member at call time. Disk cache (24 h TTL, atomic
  write), stale-cache fallback, static offline snapshot last; a corrupt cache
  reads as a missing cache. A hand-written model list was measurably wrong
  within eight days (three superseded ids, one price off 37%).
- **`cs/model_config.py`** — `Provider`/`Tier`/`Role` (one role:
  `CLASSIFIER`), `MODEL_<ROLE>` → `MODEL_<TIER>` → tier-family default
  (LEAD `@claude-opus`, WORKER `@claude-sonnet` — moving a role to a cheaper
  model must be EARNED by a measurement on that role's real task),
  `resolve_spec()` (dotted OpenRouter versions normalized to Anthropic's
  dashed form for the direct wire — `claude-haiku-4.5` 404s there, verified
  live 2026-07-30), `llm_env()` endpoint
  resolution over the same env chain as `Settings`, host-based (never
  substring) provider detection, `CS_LLM_PROVIDER=custom` without a base URL
  refuses to resolve (a config typo must not send a gateway credential to
  Anthropic's host).
- **`cs/llm_client.py`** — provider-correct auth header, `""` base_url
  normalization, unchosen credential nulled post-construction,
  `text_of()` raises on `stop_reason=="max_tokens"` BEFORE extracting text.
- **`cs/worker_llm.py`** — `call`/`complete`/`classify`;
  `DEFAULT_MAX_TOKENS=2048` sized for reasoning-model *thinking*, not the
  answer (at 64, two of seven A/B candidates truncated on all 61 items);
  `LLMConfigError` raised pre-send when a gateway-style id meets the
  Anthropic-direct wire.
- **`cs/rpc.py::chat(role=)`** — the routing seam. A ROLE-DECLARED call is
  served directly by the configured provider iff `CS_LLM_ROUTE=direct`
  (default: engine, unchanged). An empty `allow_tools` is deliberately NOT
  the signal: `cs draft-reply` and campaign composers also run tool-free and
  write customer-facing words, which stay on the engine (charter §4).
  `CS_LLM_ROUTE=engine` is the kill switch; direct-path errors are LOUD, no
  silent engine fallback. Engine response shape preserved verbatim.
- **`cs llm` verb group** — `show` / `models` (family, newest id, ship date,
  real price, what it is for) / `set` (validates the family before writing;
  refuses without a manifest slug) / `test` (one real round trip,
  `max_retries=0`).
- **Dependency:** `anthropic>=0.107` as the optional extra `cs-kernel[llm]`,
  imported lazily.
- **Nothing calls the new path yet.** No kernel call site passes `role=`, and
  `CS_LLM_ROUTE` defaults to the engine — v0.4.0 is behavior-neutral for a
  clone until it wires one call site (one argument) and opts in via env.

**Model choice, measured (2026-07-28, corrected 07-30):** A/B on the LIVE
classification task (`giada.py::_verdict` in the batch-2 campaign: 4-field
verdict with calendar date resolution, real prompt captured by monkeypatch,
61 real replies, engine baseline, hand-adjudicated gold, scored through the
clone's own `parse_verdict`). Recommendation **`MODEL_CLASSIFIER=@glm`**
(z-ai/glm-5.2): ties the engine's accuracy on the calls both completed
(56/58 each), zero unagreed schedule writes (the engine has one — a bare
"ok" read as "migrate now"), answered 61/61 where the engine's transport
failed 3, 3.1 s vs 33 s median, $1.17/1k calls. Per-token price does NOT
rank per-call cost (deepseek-v4-pro: 2.8× cheaper per token, 1.8× dearer
per call — it thinks in 434 tokens). Full record with per-item tables:
meta-repo `docs/briefs/2026-07-28-multi-provider-llm-ab.md` (quotes customer
mail; never enters this repo).

## Gates — all green (12/12 at v0.4.0, first time since v0.3.0; 15 steps as of the v0.5.1 candidate)

Gate 1 (zero company literals) was red at every tag since `v0.3.0`. The fix
turned out to need **no new manifest fields**: the offending paragraph already
had `{{ engine_ws_url }}` available and simply never used it. Pulling that
thread exposed the real size of the problem — the operator's first name in 20+
places across the project templates, his personal mailbox as a search example,
a real customer's name in an incident note, and a `… | reject(…) | first`
expression in four templates that **crashed `cs init` under StrictUndefined
for any single-account clone**. All purged/fixed. Two new enforcements:

- Gate 1's pattern now also matches the operator's name and mailbox (the
  pattern documented in `CLAUDE.md` must be kept in sync with it).
- **Gate 12** (`tests/test_template_render.py`) renders all project templates
  (29 today; the test rglobs, no hardcoded count) with
  `cs init`'s own jinja env (StrictUndefined) in single- AND multi-account
  shapes, and sweeps the RENDERED output for literals — the source grep
  cannot see a literal the template engine assembles.

`tests/test_llm_client.py` (91 assertions, offline, hermetic — it neither
fetches the live catalog nor touches the operator's real cache file) runs as
gate 11 and includes the routing-seam tests: no `role=` never reaches the
worker even with the opt-in set; `role=` without the opt-in never reaches it
either.

## Unresolved / watch

- ~~Both clones sit on `v0.4.5`~~ — RESOLVED 2026-08-04: `v0.5.1` released and
  both clones re-pinned with full collaudo (matrix above).
- ~~`cs update` crashes (EOFError) on a conflict prompt when stdin is not a
  tty~~ — FIXED on main 2026-08-04 (v0.5.2 candidate, gate 16): EOF resolves
  to the declared keep-local default and the decision is printed. Ships to
  clones at the next tag + re-pin (static tier).
- **First wiring candidate** is whatever replaces `giada.py` (the batch-2
  campaign loop is being superseded by a more general agent — the A/B
  measurement transfers to it). One `role=Role.CLASSIFIER` argument +
  `MODEL_CLASSIFIER=@glm` + `CS_LLM_ROUTE=direct` in the clone's env.
- **The A/B gold was adjudicated by the same party that built the harness**
  (disclosed in the brief §7.6). The safety metric and cost/latency numbers
  do not depend on it; the lenient-accuracy ranking does.

## Immediate next steps

1. ~~Tag the corrective `v0.5.1`~~ — DONE 2026-08-03 (`b2f07b2`, gates green at
   the tag, pushed). `v0.5.0` never moves.
2. ~~Re-pin both clones to `v0.5.1` with FULL collaudo~~ — DONE 2026-08-04,
   one clone at a time, `mrcall-cs` first (matrix above; probe closes verified
   live on both engines).
3. Promote the batch-2 loop's reusable parts (unchanged from last session):
   the flock'd schedule store (`schedule.py`), the deterministic migrator
   pattern (`migrator.py`), and the IMAP attachment reader
   (`ext/attachments.py` — the engine indexes filenames but stores no bytes
   and exposes no fetch RPC). The attachment reader is the clearest
   candidate, since every clone's `/find-document` wants it.
