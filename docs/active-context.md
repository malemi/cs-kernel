---
doc_baseline_commit: 176c547
doc_baseline_date: 2026-08-21
---

# Active Context — cs-kernel

Volatile state for the shared kernel of the `<company>-cs` operators. The
durable reference is [`CLAUDE.md`](../CLAUDE.md) (the anti-fork charter, layout,
release rules) and [`CHANGELOG.md`](../CHANGELOG.md) (what each tag changed and
which clones must re-collaudo). Pruned history lives in
[`active-context-archive.md`](active-context-archive.md). This file tracks only
what is *current*.

## State now

- **Latest release tag: `v0.13.0`. Current HEAD status: untagged.**
  The `v0.9.x` train (2026-08-21) rebuilt the operator-facing surface. What each
  tag did is in `CHANGELOG.md`, not here — static tier through `v0.11.1`;
  `v0.12.0` (2026-08-23) removed the `RATE_CAP` send quota from the code;
  `v0.13.0` (2026-08-24) adds `cs config`, `cs draft-delete` and `cs handled`,
  puts `handled` in the cron wrapper's deny set, lets
  `[campaigns].excluded_campaign` hold more than one campaign, and finishes the
  `RATE_CAP` removal in the templates. Both are FULL re-collaudo. `v0.8.0`
  remains the recorded tag→0.7.1 exception (object pinned immutable).
- The repo is **public** at `github.com/malemi/cs-kernel` — the single origin.
  The old private `hahnbanach/cs-kernel` is archived; the clone guide points
  at the public one.
- **The surface a clone now gets:** five `cs-`-prefixed commands —
  `/cs-review` (the ONE sit-down bootstrap: what the operator prepared, plus
  the day's outreach candidates where a producer is wired), `/cs-account`,
  `/cs-cron`, `/cs-campaign`, `/cs-help` — over the operator skills
  (`cs-operator`, `cs-triage-mail`, `cs-campaign-tick`, `cs-customer`,
  `cs-find-document`). `/munchausen` no longer exists. Since v0.10.0 every
  agent surface (`.opencode/`, `AGENTS.md`, `~/.codex/prompts`) is a symlink
  into `.claude/` — stamped by init AND update, no second copy to drift.
- **Upgrading a clone is one command**: bare `cs update` offers any newer
  tag and on "y" re-pins → installs → re-execs → re-stamps. `--pin` is the
  rollback hatch, `--check` writes nothing, and `requirements.txt` +
  `manifest.toml` are clone-owned (never touched).
- Clone matrix (verified 2026-08-21 from inside each clone —
  `requirements.txt` + `cs --version`; measuring `python -m cs` from another
  cwd reads the local package, not the clone's):

  | Clone | Pinned / installed | Provider → classifier | Operator |
  |---|---|---|---|
  | `mrcall-cs` | `v0.9.6` | OpenRouter → `z-ai/glm-5.3` | un-paused; cron deliberately not installed (interactive-only — operator decision 2026-08-19; `cs cron install` turns it on) |
  | `124-cs` | `v0.9.6` | Anthropic direct → `claude-sonnet-5` | un-paused, ticking (cron installed) |

  Both pin `v0.9.6`; `v0.12.0` is now available. **Re-pinning the clones is
  the operator's own move, not this session's** — stated twice on 2026-08-21,
  after a `cs update` overwrite cost him a hand-authored `manifest.toml`.
  Propose, never run it for him.

- The kernel runs per-invocation from each clone's venv (no long-running
  kernel process). The provider side is the mrcall-desktop daemons, running an EDITABLE
  install of `/home/mrcalld/mrcall-desktop` — so "deployed" is whatever
  that checkout's HEAD is, `3f8e4f1` (2026-08-18, v0.1.44) as of this
  writing, not a frozen artifact.
- Releases follow [`release-procedure.md`](release-procedure.md) — ordered
  steps, the inventory of every file carrying a version claim, and the
  mandatory multi-version sweep. Read it; do not reconstruct it.
- The multi-provider LLM path is **partly live**. The `role=`/`CS_LLM_ROUTE`
  routing seam is unwired (no call site passes `role=`; the default is the
  engine), but the send guard's register judgment IS a direct provider call:
  `cs/send_guard.py:338` → `judge_register` (`:324`) → `evaluate` (`:375`), which
  `cs/send_mail.py:162` runs on the **model-composed** send path (`body_md`)
  — a fixed-template `plain`/`html` send never reaches it. Gated by
  `llm_available()` — anthropic SDK plus a
  resolved provider credential — NOT by `CS_LLM_ROUTE`, and degrades loudly
  to deterministic checks without one. **Measured per clone 2026-08-21,
  after the v0.9.6 re-pin** (`llm_available()`, run inside each): BOTH
  clones → **True**, so both register judgments are live and spending.
  Do not infer this state from the packaging — reading the dependency list
  and concluding "no key configured" is how this file carried the wrong
  answer for a day. Run the check.
- That measurement is now the DEFAULT (v0.9.6): `ROLE_FAMILIES` resolves
  CLASSIFIER to `@glm` on OpenRouter (Anthropic direct keeps
  `@claude-sonnet` — `@glm` is not served there). `MODEL_CLASSIFIER` still
  overrides. A/B record in meta-repo
  `docs/briefs/2026-07-28-multi-provider-llm-ab.md` — quotes customer mail,
  never enters this repo).

## Unresolved

- **`124-cs` bills an undeclared account.** Its `.env` carries no provider
  key, yet `llm_available()` is True: `ANTHROPIC_API_KEY` reaches it from
  the PROCESS environment (inherited shell), so its guard runs on Anthropic
  direct at Sonnet prices, on a credential nobody declared for that clone —
  and behaves differently under cron, which usually lacks that variable.
  Fix by giving 124 its own `OPENROUTER_API_KEY` (it would then inherit
  `@glm` like mrcall-cs) or an explicit `CS_LLM_PROVIDER`/`MODEL_CLASSIFIER`.
  Operator's call; neither its `.env` nor the environment was touched.
- The `CHANGELOG.md` "Current operational pin" marker trails the clones
  (it records `v0.9.4` for mrcall-cs and `v0.9.1` for 124-cs; both are
  actually at `v0.9.6`); it converges at the next
  re-pin the operator runs.
- **A `/cs-operator` tick takes ~4 minutes, and it is all engine LLM.**
  Measured 2026-08-21: a full `cs` RPC round trip is 0.5s (0.38 of it Python
  import), while one `cs ask` is **29s**. `cs-triage-mail` MENTIONS `cs ask`
  five times and `draft-reply` six, but only ~3 are real call sites (two
  mentions argue against using `ask`) and `draft-reply` runs once per
  candidate — so the template bounds nothing; the tick's length scales with
  the candidate count. The A/B-measured direct path is ~10x faster
  but charter §4 keeps customer-facing prose on the engine — only read-only
  state queries (`cs ask`) are candidates to move, and that is a decision,
  not a cleanup.
- The `cs init` install offer and the secrets writer are gate-proven (gates
  24/25, function level) but the full **interactive `cs init` walk** on a
  fresh machine has never been run end to end. The clean-Mac customer walk
  (meta-repo Phase B handoff, open item 4) is the verification vehicle.
- **First wiring candidate** for the LLM path is whatever replaces `giada.py`
  (the batch-2 campaign loop is being superseded by a more general agent —
  the A/B measurement transfers to it). One `role=Role.CLASSIFIER` argument +
  `MODEL_CLASSIFIER=@glm` + `CS_LLM_ROUTE=direct` in the clone's env.
- **The A/B gold was adjudicated by the same party that built the harness**
  (disclosed in the brief §7.6). The safety metric and cost/latency numbers
  do not depend on it; the lenient-accuracy ranking does.
- The collaudo `live` gate is RED-by-default by construction (it diffs LLM
  prose and clock-dependent state such as `campaign_pending` vs `sms_hour`);
  the fix is filed in the meta-repo `docs/harness-backlog.md`.

## Next

1. `cs update --pin <tag>` must also refresh `template-manifest.json`'s
   `init_data.repo_kernel_version` (bare number, no `v`). Found 2026-08-19:
   mrcall-cs's init_data still said `"v0.3.0"` five releases later, so the
   ARCHITECTURE re-stamp would have rendered `cs-kernel@vv0.3.0` — stamped
   data rots when the pin verb doesn't own it. Now that the upgrade offer
   re-pins on the operator's behalf, the verb owning that field matters more,
   not less.
2. Finish charter rule 6's vocabulary clean-up: `cs update --check` and the
   upgrade prompt still print `re-collaudo: <tier>` and "Every kernel
   upgrade owes a re-collaudo (CLAUDE.md, Versioning & release)"
   (`cs/project_update.py:256, 260, 308, 351`; README 421/424/456 — verify
   the numbers before acting, they move with every edit). The
   operator has already objected to exactly this vocabulary once. Replace
   with what a tier MEANS for them ("re-test before trusting it unattended")
   or drop it from their surface.
3. Promote the batch-2 loop's reusable parts: the flock'd schedule store
   (`schedule.py`), the deterministic migrator pattern (`migrator.py`), and
   the IMAP attachment reader (`ext/attachments.py` — the engine indexes
   filenames but stores no bytes and exposes no fetch RPC). The attachment
   reader is the clearest candidate, since every clone's `/cs-find-document`
   wants it.
