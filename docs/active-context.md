---
doc_baseline_commit: 06c6c4d
doc_baseline_date: 2026-08-28
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: the volatile state of this kernel — the tag in force, what each clone
actually runs, and what is still open. Durable rules live in
[`CLAUDE.md`](../CLAUDE.md) (charter, layout, release rules), per-tag detail in
[`CHANGELOG.md`](../CHANGELOG.md), pruned narrative in
[`active-context-archive.md`](active-context-archive.md). This file tracks only
what is *current*.
<!-- doc-scope:end -->

## State now

- **Latest release tag: `v0.32.1`. Current HEAD status: tagged as `v0.32.1`.**
  Those two sentences are a machine-readable claim the release gate parses
  verbatim (`tests/test_release_consistency.py`), so rephrasing them turns the
  suite red — keep the wording and change only the value. `git describe` is
  the live answer for how far past a tag HEAD is, so no commit count is
  written down here (one would be stale the moment this file is committed).
  Twelve tags on 2026-08-25/27, `v0.20.0` → `v0.31.0`, each with a CHANGELOG
  entry naming its re-collaudo tier. **Both clones last verified on
  `v0.28.0`** (2026-08-27); `mrcall-cs`'s `requirements.txt` pins `v0.30.0`
  as of 2026-08-28 — a re-pin in progress whose install state this tree
  cannot see. `v0.31.0` is pinned nowhere, and re-pinning is the operator's
  own move.
- **`cs unanswered` is a conversation sweep that asks the engine what a message
  IS.** The unit is the thread; the engine's `emails.needs_reply` decides
  whether a settled thread's last message owes an answer. The kernel re-derives
  neither judgement — charter invariant 4.
- **The engine side of that is DEPLOYED and live**:
  `/home/mrcalld/mrcall-desktop` is at `810d7a4`, `zylch-server@` units
  restarted 2026-08-26, `cs rpc emails.needs_reply` answers instead of
  `-32601`. That install is EDITABLE, so "deployed" is the checkout's HEAD
  **plus** a restart — a pull alone leaves the old modules in memory.
- **Two ledger verbs, opposite meanings, both human-only**: `cs handled`
  (resolved out of band) and `cs escalated` (`v0.20.0` — a named human took the
  contact over: still open, still owed an answer, not the operator's to answer).
  Neither expires; every surface that stops offering the contact still prints
  it, aged, and the cron wrapper denies both in all six command-text spellings.
  **A `CS_SYSTEM_SENDERS` entry may also be an fnmatch pattern** (`v0.23.0`,
  pattern only when it carries `*`, `?` or `[`), and the same matcher
  (`cs/addr_match.py`) now reads `do_not_contact` — without that half, a
  wildcard suppression would have quietened the queue while outreach still
  went out.
- **`/cs-review` is the ONE command an operator types when he sits down**
  (`v0.24.0`): settings from `cs config`, the support queue with customers
  grouped by the CRM port, the pin from `cs --version` and the changes from
  `git log`, a digest of `docs/owner-actions.md`, per-draft handles and the
  out-of-band records. Its tone rule is a gate: the kill-switch is the
  operator's standing decision and appears exactly once, as neutral state, with
  no alarm and no suggestion to lift it.
- **Every draft carries a verdict, and it is computed, not narrated**
  (`v0.31.0`, `cs/draft_state.py`): `overtaken` / `superseded` from Gmail,
  `settled` from the engine, `ready` when nothing fired. The two copies of a
  mirrored draft are one row with both handles. Nothing retires a draft
  automatically — the cron denies `cs draft-delete` AND `cs rpc drafts.discard`
  in all six spellings, and the engine's discard deletes the row outright.
  `/cs-review` says whether the unattended operator is running
  (`cs cron status --json`: absent / paused / stale / ticking) and offers
  `cs catchup` — the engine's own `sync.run` + `update.run` — only when the
  mailbox holds mail the engine has not ingested.
- **The stamped surfaces speak the voice the clone declares** (`v0.31.0`):
  `[surface] operator_voice` in its own `manifest.toml`, kernel default
  `"American English, professional and direct"`. `cs update` merges the
  manifest over the frozen `init_data`, so editing that line reaches the stamp
  without re-running `cs init`. The three agent-facing surfaces share one
  role-framing preamble from `cs/templates/partials/`, a third template root
  with its own package-data glob.
- **`v0.31.0` is tagged locally and pushed nowhere**, and its retire path
  assumes an engine the VPS does not run yet: `drafts.discard` and the
  single-flight pipeline guard exist at mrcall-desktop `9c72683`, while the
  deployed engine is at `810d7a4`. Until that engine ships, retiring a
  mirrored draft removes only the Gmail copy. Rollout — push, engine deploy
  first, re-pin both clones, FULL collaudo, plus `mrcall-cs`'s
  `[surface] operator_voice = "Italian, founders' register"` manifest line —
  is sequenced in the meta-repo plan
  (`hb docs/execution-plans/2026-08-27-cs-review-fresh-state.md`) and waits on
  the operator's go.
- The repo is **public** at `github.com/malemi/cs-kernel` — the single origin;
  the old private `hahnbanach/cs-kernel` is archived. What a clone gets and how
  it upgrades is `README.md`; the five `cs-` commands and the five operator
  skills are one rendered `.claude/` set, with every other agent surface
  (`.opencode/`, `AGENTS.md`, `~/.codex/prompts`) symlinked into it since
  `v0.10.0` — no second copy to drift.
- Clone matrix (verified 2026-08-27 from inside each clone — `requirements.txt`
  + `.venv/bin/python -m cs --version`; measuring from another cwd reads the
  local package, not the clone's):

  | Clone | Pinned / installed | Provider → classifier | Operator |
  |---|---|---|---|
  | `mrcall-cs` | pins `v0.30.0` (2026-08-28, install unverified) | OpenRouter → `z-ai/glm-5.3` | **PAUSED** since 2026-08-24 13:21 (`~/.mrcall-cs/CS_PAUSE`). The engine defect that caused it is fixed and deployed; the pause is now the owner's standing decision, not a blocker. Three crons live when un-paused — hourly signup loop and 2-hourly operator, both **sending**, plus the dormant July batch-2 lines |
  | `124-cs` | `v0.28.0` | Anthropic direct → `claude-sonnet-5` | Running, not paused. Cron installed, 2-hourly, draft-only |

  `v0.28.0`'s static + live read-only collaudo was run on both — `cs whoami`
  signs in on each profile and `cs config` reports **no setting declared in
  more than one place** on either; each `requirements.lock` resolves the tag
  to `76f6656`. **Re-pinning a clone is the operator's own move unless he
  asks for it.**
- **The poisoned-ledger class is closed at `v0.29.0`, at both its levels** —
  no `cs update` run can leave a stored checksum silently contradicting its
  file, and the hand edit that produced the divergence is gone (`cs update
  --pin` owns `template-manifest.json`'s `init_data.repo_kernel_version`).
  Both clones are still on `v0.28.0`, where neither half exists yet; the
  `v0.29.0` CHANGELOG entry carries the one-time migration step (re-run
  `cs update --pin` on the NEW kernel, then bare `cs update`).
- **`docs/active-context.md` is clone-authored** (`v0.30.0`), alongside
  `company/`: a seed the kernel writes only when the clone has none, then never
  writes, never prompts about and never checksums. Measured on a copy of a real
  clone before the tag, the drift report then names exactly one file —
  `bin/cs_operator_cron.sh`, whose clone-owned deny line has been lost at three
  re-pins — and nothing else.
- The multi-provider LLM path is **partly live**. The `role=`/`CS_LLM_ROUTE`
  routing seam is unwired; the send guard's register judgment IS a direct
  provider call, reached only on the model-composed send path, gated by
  `llm_available()` — NOT by `CS_LLM_ROUTE` — and it degrades loudly without a
  credential. **Measured per clone 2026-08-21: BOTH → `True`**, so both
  register judgments spend; never infer this from the packaging.

## Unresolved

- **`124-cs` bills an undeclared account.** Its `.env` carries no provider key
  (verified 2026-08-26: neither `~/.124-cs/.env` nor `~/124/.env.local` declares
  one), yet `llm_available()` is True — `ANTHROPIC_API_KEY` reaches it from the
  PROCESS environment, so its guard runs on Anthropic direct at Sonnet prices on
  a credential nobody declared for that clone, and behaves differently under
  cron, which usually lacks that variable. Fix by giving 124 its own
  `OPENROUTER_API_KEY` (it would then inherit `@glm`) or an explicit
  `CS_LLM_PROVIDER`/`MODEL_CLASSIFIER`. Operator's call; nothing was touched.
- **A `/cs-operator` tick takes ~4 minutes, and it is all engine LLM.** Measured
  2026-08-21: a `cs` RPC round trip is 0.5s, one `cs ask` is **29s**, and
  `draft-reply` runs once per candidate — the tick scales with the candidate
  count and no template bounds it. Charter §4 keeps customer-facing prose on the
  engine, so only read-only queries could move, which is a decision, not a
  cleanup. Since `v0.26.0` every tick also pays for one batched classification
  call, because `cs unanswered --json` runs the same sweep.
- The `cs init` install offer and the secrets writer are gate-proven (gates
  24/25, function level) but the full **interactive `cs init` walk** on a fresh
  machine has never been run end to end. The clean-Mac customer walk (meta-repo
  Phase B handoff, open item 4) is the verification vehicle.
- **First wiring candidate** for the LLM routing seam is whatever replaces
  `giada.py` (the batch-2 campaign loop is being superseded by a more general
  agent — the A/B measurement transfers to it). One `role=Role.CLASSIFIER`
  argument + `MODEL_CLASSIFIER=@glm` + `CS_LLM_ROUTE=direct` in the clone's env.
  Caveat on that measurement: **the A/B gold was adjudicated by the same party
  that built the harness** (brief §7.6) — safety, cost and latency do not depend
  on it, the lenient-accuracy ranking does.
- The collaudo `live` gate is RED-by-default by construction (it diffs LLM prose
  and clock-dependent state such as `campaign_pending` vs `sms_hour`); the fix
  is filed in the meta-repo `docs/harness-backlog.md`.

## Next

1. Finish charter rule 6's vocabulary clean-up: `cs update --check` and the
   upgrade prompt still print `re-collaudo: <tier>` and "Every kernel upgrade
   owes a re-collaudo (CLAUDE.md, Versioning & release)"
   (`cs/project_update.py:291, :295`, more at `:385, :428` — verify the
   numbers before acting, they move with every edit). The operator has already objected to exactly this
   vocabulary once. Replace with what a tier MEANS for them ("re-test before
   trusting it unattended") or drop it from their surface.
2. Promote the batch-2 loop's reusable parts: the flock'd schedule store
   (`schedule.py`), the deterministic migrator pattern (`migrator.py`), and the
   IMAP attachment reader (`ext/attachments.py` — the engine indexes filenames
   but stores no bytes and exposes no fetch RPC). The attachment reader is the
   clearest candidate, since every clone's `/cs-find-document` wants it.
