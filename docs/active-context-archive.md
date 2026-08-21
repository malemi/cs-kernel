# Active Context — archive (cs-kernel)

Pruned session narrative from `docs/active-context.md`, relocated verbatim,
dated, newest-first. Cold storage: `/doc-start` never reads this file. It
exists to answer "when did we do X" without reconstructing it from
`git log -p docs/active-context.md`.

## 2026-08-21 — the v0.9.x arc, tag by tag (superseded by CHANGELOG.md)

Relocated from `active-context.md`, which had accumulated a release-by-release
narrative that `CHANGELOG.md` already owns properly:

`v0.9.4` clears the maintainer-facing noise from `cs update`'s output
(`--verbose` now owns the "left alone" notices). `v0.9.3` fixes `cs update
--check`, which still recommended the manual three-step upgrade v0.9.2 had
just replaced. `v0.9.2` makes `cs update` genuinely one command (the offer's
install used `python -m pip`, absent from uv-made venvs), exempts
`manifest.toml` from the overwrite flow, and stops the empty-diff conflict
prompt. `v0.9.1` added the `cs init` install offer (one y, venv+install done)
on top of `v0.9.0`'s session-surface release (`/cs-review` merge, `cs-`
prefix, `/cs-cron` `/cs-campaign` `/cs-help`, the `cs update` release offer,
human `cs whoami`, wizard slug + derived pin default, uvx quick-start).
Static tier throughout.

Shipped in `v0.8.0`/`v0.8.1` (MINOR, new CLI surface; static tier): `cs
init` writes `~/.<slug>-cs/.env` itself (getpass for the mailbox password,
`FIREBASE_WEB_API_KEY` from the Step-0 descriptor, `CS_ACCOUNTS` from the
accounts registry; never overwrites, EOF-safe, 0600) — gate 24; the README
quick-start cut to size, install snippets resolving the newest tag
dynamically (a literal `cs-kernel@vX.Y.Z` in README is now a gate failure);
the wizard's clone-pin default follows the operational pin.

Both live clones were re-stamped in place as the v0.9.0/v0.9.1 surface was
built (2026-08-19/21: renamed commands, new workflows, checksums), so their
re-pin changes no stamped file — it makes the installed CLI match the
surface they already carry.

## 2026-08-16 — v0.7.1 release: a tag must install as the version it claims

`v0.7.1` (commit `57c2caf`, 2026-08-16, pushed) fixes a package that
installed under the wrong number — `v0.6.1` and
`v0.7.0` were both tagged without bumping `pyproject.toml`, so a clone
pinned at either reports `0.6.0`, including from the `cs --version` that
`v0.7.0` adds. The release gate now checks `git show <tag>:pyproject.toml`
against every tag; writing that check surfaced the same drift at `v0.4.0`
and `v0.5.0`, all four recorded in `TAG_VERSION_EXCEPTIONS` because a
published tag is immutable and a recorded mistake beats a hidden one.

## 2026-08-16 — v0.7.0 release: the three things a newcomer reaches for

`v0.7.0` (commit `79d8ea3`, 2026-08-16) adds the three things a newcomer
reaches for and does not find: a root `cs --version` (it used to exit 2
with a usage dump), `cs login` auto-selecting the descriptor whose uid
matches the configured identity instead of offering a menu in which every
other entry is refused after the fact, and `cs update --check` / `--pin`
so a clone can learn a newer kernel tag exists without a hand-edit — with
no auto-bump, because requirements.txt is the operator's pin. Re-collaudo
declared **STATIC, both clones**: the first release under the amended
charter rule (tier decided by what the release touches, not by the semver
digit) — nothing here touches a send path, the auth boundary, a manifest
field or a permission byte. Deliberately NOT in it: the report-language
manifest field, reverted under the rule of two (both clones are Italian,
so no company needs the knob yet).

## 2026-08-16 — v0.6.1 onboarding-path patch

`v0.6.1` (commit `f75969e`, 2026-08-16) is the onboarding-path patch an
adversarial UX review forced: rendered files under `bin/` are created 0755
by both `cs init` and `cs update` (every clone ever stamped had a mode-0644
cron wrapper, so the documented crontab entry failed SILENTLY), an
unreachable engine prints one actionable line instead of a
`ConnectionRefusedError` traceback (catching `ConnectionError`, never
`OSError` — whose `FileNotFoundError` subclass would misreport a missing
file as an unreachable engine), the stamped templates stop shipping
`desktop.example.com` / "this is the mother clone" / unguarded `none`
adapter bullets / references to the non-existent `cs-template` and
`copier`, and the README documents `cs login`, the desktop app and its
daemon, troubleshooting, and the Gmail prerequisite. Three new gates
(20-22). The clones are NOT re-pinned to it yet — the operational pin
below is still `v0.6.0`.

## 2026-08-16 — both clones re-pinned to v0.6.0, FULL collaudo signed

Both clones were re-pinned to `v0.6.0` on 2026-08-16 and signed in live with
the new auth: `cs login` for the primary mailbox plus
`cs --account <name> login` for each configured secondary, each account
holding its own session file (mode 0600, per uid). FULL collaudo signed the
same day on both — the RED gates were the three declared deltas (help tree,
per-uid session paths, stamped auth-chain paragraph) plus live diffs that
were root-caused as non-regressions: engine-authored prose over identical
items, and `campaign_pending` losing its `send_sms` entries purely because
that branch is gated on `local_hour >= sms_hour` (18:00 Rome) and baseline
and candidate straddled it. Baselines re-frozen on both (cs-collaudo
`20e8785`); that live gate is RED-by-default by construction and the fix is
filed in `hb/docs/harness-backlog.md`. Operators remain paused on both
clones.

## 2026-08-16 — pin matrix at v0.6.0, operators paused (superseded by the v0.7.1 re-pin)

| Clone | Declared | Locked | Installed | Collaudo |
|---|---|---|---|---|
| `mrcall-cs` | `v0.6.0` | `v0.6.0` (commit `0d75ea6`) | `0.6.0` | full — signed 2026-08-16 |
| `124-cs` | `v0.6.0` | `v0.6.0` (commit `0d75ea6`) | `0.6.0` | full — signed 2026-08-16 |

The kernel runs per-invocation from each clone's venv (no long-running kernel
process). The provider side — the engine RPC contract the signed closes need —
is the mrcall-desktop daemons, deployed at `d239e5f` on 2026-08-03. Both
operators remain PAUSED (`CS_PAUSE`); revival is a separate operator action.

## 2026-08-15 — v0.6.0 auth release (Firebase refresh-token exchange)

The auth release (tag `v0.6.0`, commit `0d75ea6`, 2026-08-15) moves auth to a Firebase
refresh-token exchange via the Secure Token API: the vendor-only
service-account file leaves the mint path entirely, `cs login` reads the
profile descriptor the mrcall-desktop app writes at sign-in, and sessions
are stored PER ACCOUNT UID (`refresh_token-<uid>.json` / `id_token-<uid>.json`)
so `cs --account <name>` keeps working across logins. `cs --help` finally
lists `init`/`update`/`login`. FULL collaudo signed on BOTH clones
2026-08-16: permission bytes byte-identical, the three declared deltas being
the help tree, the per-uid session paths and the stamped auth-chain
paragraph (cs-collaudo `20e8785`). Do not move any released tag.

## 2026-08-09 — v0.5.2 release (`cs` console script + onboarding-wall fixes)

The previous release (tag `v0.5.2`, commit `7c4933c`, 2026-08-09) ships the `cs` console script
with the permission surface finished around it — deny sets enumerate six
command-text spellings (24-entry cron block, settings 65/7), placement-aware
gate — plus the customer-onboarding wall fixes (public install URLs, handled
`ConfigError` for unconfigured verbs, EOF/^C-safe `cs init`, release-tracking
wizard defaults), the reviewed-literals registry replacing the regex-law
charter grep, and the new `cs update` semantics (requirements.txt is
operator-owned; security-critical templates apply with a `*.local-bak`).
All 17 gates green at that tag (19 at v0.6.0).

## 2026-08-04 — v0.5.2 candidate — EOF-safe `cs update`

- The two `cs update` conflict prompts resolve a closed stdin (EOFError) to
  the declared keep-local default instead of crashing mid-run; the decision
  is printed. Gate 16 (`tests/test_project_update.py`) proves the real
  `python -m cs update` subprocess path with `stdin=DEVNULL` against a
  manufactured conflict. Not tagged; `v0.5.1` remains the latest release.
  Static re-collaudo at the next re-pin.

## 2026-08-04 — resolved watch items and completed steps

- ~~Both clones sit on `v0.4.5`~~ — RESOLVED 2026-08-04: `v0.5.1` released and
  both clones re-pinned with full collaudo (matrix above).
- ~~`cs update` crashes (EOFError) on a conflict prompt when stdin is not a
  tty~~ — FIXED on main 2026-08-04 (v0.5.2 candidate, gate 16): EOF resolves
  to the declared keep-local default and the decision is printed. Ships to
  clones at the next tag + re-pin (static tier).
- ~~Tag the corrective `v0.5.1`~~ — DONE 2026-08-03 (`b2f07b2`, gates green at
  the tag, pushed). `v0.5.0` never moves.
- ~~Re-pin both clones to `v0.5.1` with FULL collaudo~~ — DONE 2026-08-04,
  one clone at a time, `mrcall-cs` first (matrix above; probe closes verified
  live on both engines).

## 2026-08-01 — v0.5.1 corrective candidate — release truth gate

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

## 2026-07-30 — Gates all green (12/12 at v0.4.0, first time since v0.3.0)

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

## 2026-07-28..30 — v0.4.0 — multi-provider LLM + template literal purge

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
