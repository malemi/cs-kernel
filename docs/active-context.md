---
doc_baseline_commit: c1acee13b96c4a596c4523c5785116b69e9019c0
doc_baseline_date: 2026-08-28
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: the volatile state of this kernel — the tag in force, what each clone
actually runs, and what is still open. Durable rules live in
[`CLAUDE.md`](../CLAUDE.md), per-tag detail in [`CHANGELOG.md`](../CHANGELOG.md),
and pruned narrative in [`active-context-archive.md`](active-context-archive.md).
<!-- doc-scope:end -->

## State now

- **Latest release tag: `v0.35.0`. Current HEAD status: untagged.** These
  sentences are parsed by `tests/test_release_consistency.py`; keep the wording
  and change only the values. Every published tag has a CHANGELOG entry with
  its re-test tier. Releasing, pushing, or upgrading a clone still requires the
  operator's explicit approval.
- **The deployed mrcall-desktop engine is `1194434`.** All five
  `zylch-server@` units run that editable checkout after a restart and serve
  `settings.get_secret`. Engine deployment therefore means checkout HEAD plus
  restarted processes, never a pull alone.
- **The open-work sources are intentionally different facts.** `cs unanswered`
  is a conversation-level, Gmail-Sent-anchored candidate sweep; the engine owns
  reply/automatic classification and its task ledger; `cs review` reconciles
  drafts, tasks, human takeovers, out-of-band closures, campaigns, and the last
  scheduled run. Gmail answers whether a message exists; the engine answers
  what kind of message it is.
- **Draft freshness is recomputed at review time.** `overtaken` and
  `superseded` are Gmail signals, `settled` is the engine's verdict, and
  `ready` currently means only that none of those signals fired. Draft deletion
  remains a named human action; the cron denies both draft-retirement paths.
- **Two human-only ledger verbs remain distinct.** `cs handled` records work
  resolved outside email; `cs escalated` records a still-open contact taken over
  by a named human. Both remain visible and both are denied to the unattended
  operator.
- **The source-tree `cs-review` skill now adjudicates attention.** It builds a
  conversation/task/draft ledger, reads full current threads, requires one of
  five explicit verdicts per candidate, and puts only positive-evidence
  `act_now` rows in the main agenda. The seven-case incident replay passed 7/7
  with Claude Opus and the 43-gate suite is green. The completed work trace is
  [`execution-plans/2026-08-28-attention-agenda.md`](execution-plans/2026-08-28-attention-agenda.md).
- **All operator workflows are now project-scoped skills in the source tree.**
  `.claude/skills` is canonical; `.agents/skills` and `.opencode/skills` resolve
  those same bytes. Fresh renders have ten skills and no command directory;
  `cs update` retires the exact five command-era Claude/OpenCode paths and
  home-global Codex prompts while preserving unrelated files. The 43-gate suite
  and all ten independent skill validations are green. This work is untagged;
  its completed trace is
  [`execution-plans/2026-08-28-agent-skills-only.md`](execution-plans/2026-08-28-agent-skills-only.md).
- **`cs init` discovers engine identity and mailbox credentials.** It selects a
  matching mrcall-desktop descriptor, reads the mailbox password through
  owner-authenticated `settings.get_secret`, and falls back to a prompt only
  when the engine cannot provide it.
- **Clone pins and installed packages are aligned only for `mario124-cs`.** On
  2026-08-28, it declares and runs `v0.35.0`. `mrcall-cs` still declares
  `v0.32.1` while its venv reports `0.35.0`; it must not be described as
  pinned-and-running one version until declaration and environment agree and
  are re-tested.
- **The provider-routing seam is partial.** The send guard can call a direct
  classifier through `cs/worker_llm.py`; general `role=` routing remains opt-in
  through `CS_LLM_ROUTE`. Kernel-owned LLM work must stay fixed-output and
  company-neutral.

## Unresolved

- **The attention agenda is released but not yet live-operator verified after
  upgrade.** `mario124-cs` now declares and runs `v0.35.0`; the generated review
  skill still needs a read-only run against its live mailbox.
- **The skills-only migration is implemented but unreleased.** Its disposable
  `mario124-cs` proof passed without touching the real clone; publishing the
  MINOR release and upgrading the clone remain separate explicit actions.
- **Interactive review has an ambient-permission boundary.** A rendered skill
  can contain no mutation path and can stop before repair, but it cannot revoke
  tools already granted to the surrounding Claude Code session. Hard isolation
  would require a separate restricted process and a different operator flow.
- **`mario124-cs` can consume an undeclared provider credential.** Its own env
  carries no provider key, but an ambient `ANTHROPIC_API_KEY` can make
  `llm_available()` true interactively and absent under cron.
- **A `/cs-operator` run is dominated by engine LLM latency.** A measured run
  takes about four minutes; `cs ask` and per-candidate `draft-reply` calls scale
  with candidate count.
- The full interactive `cs init` walk on a fresh machine has not been verified
  end to end; function-level gates cover descriptor selection, secret retrieval,
  environment writing, and the install offer.
- The collaudo `live` gate remains red-by-default because it diffs LLM prose and
  clock-dependent state. The meta-repo harness backlog owns that defect.

## Next

1. Publish the skills-only MINOR release when authorized; the operator will
   perform the real clone upgrade separately.
2. Upgrade each clone when its operator chooses, run the release's static +
   live read-only re-test, then verify the real mario124 review against its
   live mailbox.
3. Reconcile each clone's declared pin with its installed package, then run the
   required re-test only after the operator explicitly requests the upgrade.
4. Replace internal `re-collaudo` wording still exposed by `cs update` with
   plain operator language.
5. Promote reusable attachment-reading and scheduling pieces only when a second
   clone needs them, per the rule of two.
