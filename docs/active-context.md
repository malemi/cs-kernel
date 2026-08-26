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

- **Latest release tag: `v0.24.0`. Current HEAD status: tagged as `v0.24.0`.**
  `v0.24.0` makes `/cs-review` the ONE command an operator types when he sits
  down: `cs config` (the switch and the triage mode, read rather than inferred
  from a log tail), `cs unanswered --days 45 --crm` (the support queue, with
  customers as their own group via the CRM port), `cs --version` + `git log`
  (the pin actually installed, and what changed), a digest of
  `docs/owner-actions.md`, per-draft uids and the out-of-band records — paid
  for by a campaign block that had become 31 identical `[engaged]` rows. Its
  tone rule is a gate, not a preference: the kill-switch is the operator's
  standing decision and appears exactly once, as neutral state, with no alarm
  and no suggestion to lift it (gate 36). FULL tier — the operator's primary
  surface. `cs config` also gained the `system_senders` section.
  `v0.23.0` lets a `CS_SYSTEM_SENDERS` entry be an fnmatch pattern, because a
  bounce daemon's sending host rotates per message and an exact list is stale on
  the next bounce; the same matcher (`cs/addr_match.py`) now reads the
  `do_not_contact` table, which had kept comparing exactly and would have made a
  wildcard suppression quieten the queue while outreach still went out. FULL
  tier — the failure class is "a rule hides a real customer's mail".
  `v0.21.0` changes no code: it drops the clone index template to 162 rendered
  lines, moves its mechanism prose to `docs/ARCHITECTURE.md` § How it works,
  and deletes three passages that recounted history rather than describing the
  system. `v0.22.0` fixes `cs update`: declining an overwrite no longer
  advances the stored checksum, so a declined conflict is offered again
  instead of vanishing. Both are static tier.
  The `v0.9.x` train (2026-08-21) rebuilt the operator-facing surface. What each
  tag did is in `CHANGELOG.md`, not here — static tier through `v0.11.1`;
  `v0.12.0` (2026-08-23) removed the `RATE_CAP` send quota from the code;
  `v0.13.0` (2026-08-24) adds `cs config`, `cs draft-delete` and `cs handled`,
  puts `handled` in the cron wrapper's deny set, lets
  `[campaigns].excluded_campaign` hold more than one campaign, and finishes the
  `RATE_CAP` removal in the templates; `v0.14.0` (2026-08-24) makes a FINISHED
  campaign deliver nothing on any of the five send paths, enforcing
  `[pack].status` and the new typed `[pack].ends_on`. Those three are FULL
  re-collaudo. `v0.15.0` (2026-08-24) touches no `cs/` code: it cuts the
  stamped clone index from 290 to 187 lines so a clone's own doc gate passes
  again, and adds `docs/sessions/` to this repo's `.gitignore` and to the
  clone template's — **static tier, and the suites were waived by the
  operator, not run**. `v0.16.0` (2026-08-24) takes one company's operational
  facts out of the project templates — the `company/` prose slots are now
  instructions rather than the mother clone's own internals — extends the grep
  gate to the bare brand and adds a shape contract on those slots, and makes
  `company/**` create-if-missing so `cs update` never prompts about authored
  prose again; **static tier, suites waived by the operator, not run**.
  `v0.17.0` (2026-08-24) finishes that job on the last file that needed it:
  `docs/ARCHITECTURE.md` is generated all the way down, and the section it used
  to declare "NOT stamped" moves to the new `company/clone-notes.md` slot —
  **static tier, suites waived by the operator, not run**. `v0.18.0`
  (2026-08-24) makes `manifest.toml` the list of knobs that exist: six stamped
  fields nothing read are gone (`[knobs].dry_run`, `[knobs].autonomous`,
  `[repo].kernel_version`, `[skills]`, `[extensions]`,
  `[campaigns].posture_note`), and the three the code reads on every tick —
  `system_senders` and both send-guard knobs — are stamped for the first time.
  `founder_sweep_enabled` and `platform_env_path` were proposed for the same
  cut and KEPT, because what `cs config` reports for them is true.
  **Static tier, suites waived by the operator, not run.** `v0.19.0`
  (2026-08-24) makes the SMS send endpoint a kernel default, so
  `[sms].enabled` is the whole switch and `cs init` can no longer emit an SMS
  configuration that cannot send — **FULL tier by what it touches (`sms.py`,
  `campaign.py`, and send capability itself); the suites were waived by the
  operator and NOT run, so this tag shipped without the collaudo its own tier
  calls for.** `v0.20.0` (2026-08-25) adds `cs escalated`: the sibling of
  `handled` that says NOT resolved — still open, still owed an answer, but a
  named human has personally taken the contact over, so the machine stops
  offering them as work and no campaign path delivers to them. Every surface
  that hides them also prints them, aged; the cron denies the verb in all six
  command-text spellings, taking the wrapper's deny set from 34 to 40 entries.
  **FULL tier by what it touches (the campaign delivery paths and the
  permission surface).** `v0.8.0` remains the recorded tag→0.7.1 exception
  (object pinned immutable).
- **A clone that declined a `cs update` conflict before `v0.22.0` still has a
  poisoned ledger, and the fix does not clean it up.** `mrcall-cs` is one:
  `CLAUDE.md` and `docs/ARCHITECTURE.md` were declined once under `v0.21.0`, so
  both carry that render as their stored checksum and `cs update` now reports
  nothing to do about them. Removing the two entries from
  `template-manifest.json`'s `file_checksums` is what makes the conflict visible
  again.
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
- Clone matrix (verified 2026-08-25 from inside each clone —
  `requirements.txt` + `cs --version`; measuring `python -m cs` from another
  cwd reads the local package, not the clone's):

  | Clone | Pinned / installed | Provider → classifier | Operator |
  |---|---|---|---|
  | `mrcall-cs` | `v0.23.0` | OpenRouter → `z-ai/glm-5.3` | **PAUSED** since 2026-08-24 13:03 by its own tick: `cs chat --allow send_draft` ignored the draft id it was asked for, twice, and sent a different draft. The pause is still set and was NOT cleared by the re-pin. Three crons installed and live when un-paused — hourly signup loop and 2-hourly operator, both **sending**, plus the dormant July batch-2 lines |
  | `124-cs` | `v0.23.0` | Anthropic direct → `claude-sonnet-5` | Running, not paused. Cron installed, 2-hourly, draft-only |

  Both pin `v0.23.0` as of 2026-08-25, installed and verified from inside each
  clone (`cs --version` reports `0.23.0`), with `v0.23.0`'s FULL collaudo run
  on both — not waived. The re-pin also repaired two stale claims per clone:
  `template-manifest.json` and the ARCHITECTURE row were still on `0.20.0`,
  and both locks still resolved `v0.19.0`'s commit. `mrcall-cs` needed its `template-manifest.json` repaired first — two
  entries removed — because it had hit the declined-overwrite bug the same day,
  under `v0.21.0`. `124-cs` took both documents cleanly: its copies were
  unmodified since init, so no conflict was raised. **Re-pinning a
  clone is the operator's own move unless he asks for it** — stated twice on
  2026-08-21, after a `cs update` overwrite cost him a hand-authored
  `manifest.toml`. This round was asked for, with a per-file decision given in
  advance for every prompt. That care is now partly structural: `company/**`
  joins `manifest.toml` and `requirements.txt` as a file class `cs update`
  cannot overwrite at all.

  **`docs/ARCHITECTURE.md` was the same hazard, and `v0.17.0` closes it.** It
  was template-owned with a last section hand-authored by contract ("This
  section is NOT stamped"), so an overwrite that was right for the stamped table
  destroyed the notes underneath it — 59 lines on `124-cs`, restored by hand
  from git. That section no longer exists in the template: the file is generated
  all the way down and safe to overwrite unconditionally, and the notes live in
  `company/clone-notes.md`, which the kernel creates once and never touches.
  No file in a clone is half-generated any more.

- **Both clones' `requirements.lock` is current again**, regenerated on
  2026-08-24 from each clone's own collaudo'd venv. Until then each resolved
  `b2f07b2` (`v0.5.1`) from `hahnbanach/cs-kernel`, the ARCHIVED private repo,
  so a venv rebuilt from the lock got a kernel eight releases old or failed
  outright — the harness-backlog's 2026-07-25 entry. Nothing yet ENFORCES the
  regeneration: it stays a hand step in the upgrade procedure, and the file
  rots again the first time a pin bump ships without it.

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

- **`cs update` asks about a template conflict ONCE and then forgets it for
  ever.** `cs/project_update.py:528` records the newly rendered checksum into
  `file_checksums` before any branch runs, so declining the overwrite (or
  hitting the no-tty default, which keeps the local file) still stores "the
  clone is in sync with this render". On the next run the `rendered_checksum
  == old_tpl_checksum` short-circuit at `:535` skips the file entirely and the
  operator is never asked again — the clone keeps a stale template-owned file
  with no way for `cs update` to notice. It bit both clones at the `v0.14.0`
  re-pin: each kept a `campaigns/README.md` that was one release behind AND
  still carried an untranslated Italian sentence. Recovering it needed the
  stored checksum to be forced back to the clone file's own hash so the
  "unmodified, safe to overwrite" branch would fire. The fix is to record the
  rendered checksum only when the render is actually WRITTEN, and to keep the
  previous value when the operator declines.
- **`124-cs` bills an undeclared account.** Its `.env` carries no provider
  key, yet `llm_available()` is True: `ANTHROPIC_API_KEY` reaches it from
  the PROCESS environment (inherited shell), so its guard runs on Anthropic
  direct at Sonnet prices, on a credential nobody declared for that clone —
  and behaves differently under cron, which usually lacks that variable.
  Fix by giving 124 its own `OPENROUTER_API_KEY` (it would then inherit
  `@glm` like mrcall-cs) or an explicit `CS_LLM_PROVIDER`/`MODEL_CLASSIFIER`.
  Operator's call; neither its `.env` nor the environment was touched.
- **`cs config` reports duplicate declarations on BOTH clones and nobody has
  acted on them**: 11 on `mrcall-cs`, 9 on `124-cs` — the same value written
  into `~/.<slug>-cs/.env` and `manifest.toml`. They agree today and the env
  layer wins in every case, so nothing is broken; the point is that two
  repositories of truth for one value eventually disagree, and on `124-cs` one
  of the duplicates is `cs_triage_mode` itself. Deleting the losing
  declaration is an operator decision (which of the two he wants to keep), so
  the 2026-08-24 re-pin reported them and changed neither.
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
