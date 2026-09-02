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

- **Latest release tag: `v0.37.0`. Current HEAD status: untagged.** These
  sentences are parsed by `tests/test_release_consistency.py`; keep the wording
  and change only the values. Every published tag has a CHANGELOG entry with
  its re-test tier. Releasing, pushing, or upgrading a clone still requires the
  operator's explicit approval.
- **The deployed mrcall-desktop engine is `1194434`.** All five `zylch-server@`
  units run that editable checkout and serve `settings.get_secret`. Engine
  deployment means checkout HEAD plus restarted processes, never a pull alone.
- **The open-work sources are intentionally different facts.** `cs unanswered`
  is a conversation-level, Gmail-Sent-anchored candidate sweep; the engine owns
  reply/automatic classification and its task ledger; `cs review` reconciles
  drafts, tasks, human takeovers, out-of-band closures, campaigns, and the last
  scheduled run. Gmail answers whether a message exists; the engine answers
  what kind of message it is.
- **Draft freshness is recomputed at review time.** `overtaken` and `superseded`
  are Gmail signals, `settled` is the engine's verdict, `ready` means only that
  none fired. Draft deletion is a named human action; the cron denies both
  draft-retirement paths.
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
- **Contact history is answerable across mailboxes; no send gate uses it yet.**
  `cs history` fans out over every `CS_ACCOUNTS` account, taking each mailbox's
  credential from the engine handover rather than any env key, reports a mailbox
  it cannot read as `unreadable` rather than absent, and prints the scope it
  actually read. It reaches only profile mailboxes so far; the `124-cs`
  mailboxes that caused the incident have none and their owners contribute
  nothing by binding constraint, so phase 1b reaches them over plain IMAP with
  app passwords the operator already holds — the standard protocol over a
  vendor API, the operator's decision. The four gating call sites follow as
  the FULL-tier release.
  [Work trace](execution-plans/2026-09-01-contact-history-across-mailboxes.md).
- **No clone runs `v0.36.0` or `v0.37.0`.** `mrcall-cs` declares and installs `v0.32.1`
  (`requirements.txt` pin and the venv's dist-info agree). `mario124-cs` is
  recorded at `v0.35.0`; that clone is not present on this machine, so its state
  is a claim from its own last upgrade, not a reading. The CHANGELOG
  operational-pin marker says `v0.28.0`, because its owner step is the re-pin
  sign-off that runs only after both clones move.
- **HEAD carries untagged work past `v0.37.0`, and it is not on the remote.**
  `cs draft-reply` now warns and names every draft it is not mirroring instead
  of dropping all but the newest, and `cs review` has a `duplicate` verdict,
  ranked above `overtaken`, for a draft whose text is already in Sent. Bodies
  below a minimum length or at the normalisation cap are not compared.
- **The provider-routing seam is partial.** The send guard can call a direct
  classifier through `cs/worker_llm.py`; general `role=` routing remains opt-in
  through `CS_LLM_ROUTE`. Kernel-owned LLM work must stay fixed-output and
  company-neutral.

## Unresolved

- **`v0.36.0` and `v0.37.0` are published and applied nowhere.** `v0.37.0`'s
  tier is FULL on both clones and the suite was not run before the tag: the
  operator authorised publication without it, so the collaudo is owed at each
  upgrade and the CHANGELOG entry records that. Nothing in `v0.37.0` has met a
  live mailbox — the fan-out, the `unreadable` outcome and the scope line are
  proven against protocol doubles only. The `v0.35.0` attention agenda still has
  no live-operator run either.
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
- **A `/cs-operator` run is dominated by engine LLM latency** — about four
  minutes measured; `cs ask` and per-candidate `draft-reply` scale with count.
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
3. Build phase 1b: `read_mailboxes` manifest field, the strict env credential
   map, wiring declared mailboxes into the fan-out, and the `124-cs` acceptance
   run — `cs history` finding the co-founder's 2026-07-03 reply.
4. Update the CHANGELOG operational-pin marker once both clones are on the same
   tag — it is the sign-off, not a running commentary.
5. Replace internal `re-collaudo` wording still exposed by `cs update` with
   plain operator language.
6. Promote reusable attachment-reading and scheduling pieces only when a second
   clone needs them, per the rule of two.
