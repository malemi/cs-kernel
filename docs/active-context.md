---
doc_baseline_commit: 6eb44d2
doc_baseline_date: 2026-08-26
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

- **Latest release tag: `v0.27.0`. Current HEAD status: untagged.** Those two
  sentences are a machine-readable claim the release gate parses verbatim
  (`tests/test_release_consistency.py`), so rephrasing them turns the suite red —
  keep the wording and change only the value. `git describe` is the live answer
  for how far past a tag HEAD is, so no commit count is written down here (one
  would be stale the moment this file is committed). Eight tags on 2026-08-25/27,
  `v0.20.0` → `v0.27.0`, each with a CHANGELOG entry naming its re-collaudo
  tier; the tag-by-tag narrative this section used to carry is in the archive.
- **`cs unanswered` is a conversation sweep that asks the engine what a message
  IS.** The unit is the thread, joined on `References`/`In-Reply-To`/
  `Message-ID` already being FETCHed (`v0.25.0`); the engine's
  `emails.needs_reply` decides whether a settled thread's last message owes an
  answer, so a closing courtesy prints in its own section instead of as work
  (`v0.26.0`). The kernel re-derives neither judgement — charter invariant 4,
  *the engine is authoritative for what it owns; when it is wrong, fix the
  engine*, was written from this.
- **The engine side of that is DEPLOYED and live**, which the docs claimed for a
  day it was not. `/home/mrcalld/mrcall-desktop` is at `810d7a4`, all five
  `zylch-server@` units restarted 2026-08-26 15:18–15:19 UTC, and
  `cs rpc emails.needs_reply '{"thread_ids": []}'` answers
  `{"threads": {}, "asked": 0, "note": null}` instead of `-32601 Method not
  found`. That install is EDITABLE, so "deployed" is the checkout's HEAD **plus**
  a restart — a pull alone leaves the old modules in memory.
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
  `git log`, a digest of `docs/owner-actions.md`, per-draft uids and the
  out-of-band records. Its tone rule is a gate: the kill-switch is the
  operator's standing decision and appears exactly once, as neutral state, with
  no alarm and no suggestion to lift it.
- The repo is **public** at `github.com/malemi/cs-kernel` — the single origin;
  the old private `hahnbanach/cs-kernel` is archived. What a clone gets and how
  it upgrades is `README.md`; the five `cs-` commands and the five operator
  skills are one rendered `.claude/` set, with every other agent surface
  (`.opencode/`, `AGENTS.md`, `~/.codex/prompts`) symlinked into it since
  `v0.10.0` — no second copy to drift.
- Clone matrix (verified 2026-08-26 from inside each clone — `requirements.txt`
  + `.venv/bin/python -m cs --version`; measuring from another cwd reads the
  local package, not the clone's):

  | Clone | Pinned / installed | Provider → classifier | Operator |
  |---|---|---|---|
  | `mrcall-cs` | `v0.26.0` | OpenRouter → `z-ai/glm-5.3` | **PAUSED** since 2026-08-24 13:21 (`~/.mrcall-cs/CS_PAUSE`). The engine defect that caused it is fixed and deployed; the pause is now the owner's standing decision, not a blocker. Three crons live when un-paused — hourly signup loop and 2-hourly operator, both **sending**, plus the dormant July batch-2 lines |
  | `124-cs` | `v0.26.0` | Anthropic direct → `claude-sonnet-5` | Running, not paused. Cron installed, 2-hourly, draft-only |

  `v0.26.0`'s FULL collaudo was RUN on both, not waived, and `cs config` now
  reports **no setting declared in more than one place** on either. Each
  `requirements.lock` resolves the tag to `46f2648` and was installed ALONE into
  a fresh `uv venv` rather than assumed to. **Re-pinning a clone is the
  operator's own move unless he asks for it** — stated twice on 2026-08-21,
  after a `cs update` overwrite cost him a hand-authored `manifest.toml`.
- **`mrcall-cs` still carries the pre-`v0.22.0` poisoned ledger on
  `docs/ARCHITECTURE.md`**: declined once under `v0.21.0`, so it reports as
  locally modified for ever and its "Kernel pin" row is hand-edited at every
  re-pin (currently `cs-kernel@v0.26.0`, correct). Removing that entry from
  `template-manifest.json`'s `file_checksums` makes the conflict visible again.
  `init_data.repo_kernel_version` in the same file is likewise hand-bumped
  (currently `0.26.0`) — see `Next` 1.
- The multi-provider LLM path is **partly live**. The `role=`/`CS_LLM_ROUTE`
  routing seam is unwired (no call site passes `role=`; the default is the
  engine), but the send guard's register judgment IS a direct provider call:
  `cs/send_mail.py:162` → `send_guard.check` → `evaluate` → `judge_register`,
  reached only on the **model-composed** send path (`body_md is not None`),
  never on a fixed-template one. It is gated by `llm_available()`, NOT by
  `CS_LLM_ROUTE`,
  and degrades loudly without a credential. **Measured per clone 2026-08-21:
  BOTH → `True`**, so both register judgments spend — do not infer this from the
  packaging, which is how this file carried the wrong answer for a day.
  `ROLE_FAMILIES` (`v0.9.6`) resolves CLASSIFIER to `@glm` on OpenRouter;
  Anthropic direct keeps `@claude-sonnet`, not served there.

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

1. `cs update --pin <tag>` must also refresh `template-manifest.json`'s
   `init_data.repo_kernel_version` (bare number, no `v`). Found 2026-08-19:
   mrcall-cs's init_data still said `"v0.3.0"` five releases later, so the
   ARCHITECTURE re-stamp would have rendered `cs-kernel@vv0.3.0` — stamped data
   rots when the pin verb doesn't own it. Now that the upgrade offer re-pins on
   the operator's behalf, the verb owning that field matters more, not less.
2. Finish charter rule 6's vocabulary clean-up: `cs update --check` and the
   upgrade prompt still print `re-collaudo: <tier>` and "Every kernel upgrade
   owes a re-collaudo (CLAUDE.md, Versioning & release)"
   (`cs/project_update.py:257, 261, 309` — verify the numbers before acting,
   they move with every edit). The operator has already objected to exactly this
   vocabulary once. Replace with what a tier MEANS for them ("re-test before
   trusting it unattended") or drop it from their surface.
3. Promote the batch-2 loop's reusable parts: the flock'd schedule store
   (`schedule.py`), the deterministic migrator pattern (`migrator.py`), and the
   IMAP attachment reader (`ext/attachments.py` — the engine indexes filenames
   but stores no bytes and exposes no fetch RPC). The attachment reader is the
   clearest candidate, since every clone's `/cs-find-document` wants it.
