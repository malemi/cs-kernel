---
doc_baseline_commit: 32bbda7a2918c57db9b91ab283aec4cf702c6eea
doc_baseline_date: 2026-09-01
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: the volatile state of this kernel — the tag in force, what each clone
actually runs, and what is still open. Durable rules live in
[`CLAUDE.md`](../CLAUDE.md), per-tag detail in [`CHANGELOG.md`](../CHANGELOG.md),
and pruned narrative in [`active-context-archive.md`](active-context-archive.md).
<!-- doc-scope:end -->

## State now

- **Latest release tag: `v0.36.0`. Current HEAD status: untagged.** These
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
- **The `cs-review` skill adjudicates attention.** It builds a
  conversation/task/draft ledger, reads full current threads, requires one of
  five explicit verdicts per candidate, and puts only positive-evidence
  `act_now` rows in the main agenda. Its work trace is
  [`execution-plans/2026-08-28-attention-agenda.md`](execution-plans/2026-08-28-attention-agenda.md).
- **`v0.36.0` carries two changes: agent-skills-only, and memory-first for
  outbound facts.** Its re-test tier is static + live read-only on both clones —
  above static because `cs update` deletes command-era files on the clone, which
  has to be observed rather than asserted.
- **Two sourcing rules bind every outbound message.** Memory is the first source
  for any fact that will appear in one — not only entity facts — and an empty
  search obliges a second source rather than a derivation. They are stated once
  in `cs/templates/partials/outbound-fact-sourcing.md.j2` and included by
  `CLAUDE.md.j2` § 9, `cs-triage-mail` § 2b and `cs-campaign-tick`. `cs-review`
  is not a host: it composes nothing and inherits them by reading `CLAUDE.md`.
  The read path is `cs ask`; `cs chat` is denied to the cron. The rules ship
  abstract, because a concrete value correct in one country is inherited as
  false everywhere else.
- **`cs init` discovers engine identity and mailbox credentials.** It selects a
  matching mrcall-desktop descriptor, reads the mailbox password through
  owner-authenticated `settings.get_secret`, and falls back to a prompt only
  when the engine cannot provide it.
- **No clone runs `v0.36.0`.** `mrcall-cs` declares and installs `v0.32.1`
  (`requirements.txt` pin and the venv's dist-info agree). `mario124-cs` is
  recorded at `v0.35.0`; that clone is not present on this machine, so its state
  is a claim from its own last upgrade, not a reading. The CHANGELOG
  operational-pin marker says `v0.28.0`, because its owner step is the re-pin
  sign-off that runs only after both clones move.
- **The provider-routing seam is partial.** The send guard can call a direct
  classifier through `cs/worker_llm.py`; general `role=` routing remains opt-in
  through `CS_LLM_ROUTE`. Kernel-owned LLM work must stay fixed-output and
  company-neutral.

## Unresolved

- **`v0.36.0` is published but applied nowhere.** Both clones are behind it. The
  tag's static + live read-only re-test has not been run on either, and the
  attention agenda released in `v0.35.0` still has no live-operator run against
  a real mailbox.
- **The outbound sourcing rules are proven as rendered text, not as behaviour.**
  Gates hold that they appear once per surface and that no fourth surface can
  paste them in unnoticed. Whether a session actually reaches memory before
  composing needs a live engine and has not been exercised.
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

1. Upgrade each clone to `v0.36.0` when its operator chooses, then run the tag's
   static + live read-only re-test: ten skills and no `.claude/commands`, the
   agent surfaces resolving to the canonical tree, no unrelated file retired,
   and the sourcing rules once per rendered surface.
2. `mrcall-cs` is four minor releases behind at `v0.32.1`, so its upgrade
   crosses `v0.33.0`, `v0.34.0` and `v0.35.0` as well. Read each of those
   entries' re-test tiers and run the strictest one they demand, not only
   `v0.36.0`'s.
3. Update the CHANGELOG operational-pin marker once both clones are on the same
   tag — it is the sign-off, not a running commentary.
4. Replace internal `re-collaudo` wording still exposed by `cs update` with
   plain operator language.
5. Promote reusable attachment-reading and scheduling pieces only when a second
   clone needs them, per the rule of two.
