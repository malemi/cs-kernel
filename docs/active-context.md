---
doc_baseline_commit: 1f74122f9510c6a45aceca5342de1a6838df472c
doc_baseline_date: 2026-09-03
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: the volatile state of this kernel — the tag in force, what each clone
actually runs, and what is still open. Durable rules live in
[`AGENTS.md`](../AGENTS.md), per-tag detail in [`CHANGELOG.md`](../CHANGELOG.md),
and pruned narrative in [`active-context-archive.md`](active-context-archive.md).
<!-- doc-scope:end -->

## State now

- **Latest release tag: `v0.39.0`. Current HEAD status: untagged.** These
  sentences are parsed by `tests/test_release_consistency.py`; keep the wording
  and change only the values. Every published tag has a CHANGELOG entry with
  its re-test tier. Releasing, pushing, or upgrading a clone still requires the
  operator's explicit approval.
- **The deployed mrcall-desktop engine is `459df0f`.** All five `zylch-server@`
  units were restarted on it (2026-09-02 08:03) and serve `settings.get_secret`.
  Engine deployment means checkout HEAD plus restarted processes, never a pull
  alone.
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
- **Two sourcing rules bind every outbound message.** Memory is the first source
  for any fact that will appear in one — not only entity facts — and an empty
  search obliges a second source rather than a derivation. They are stated once
  in `cs/templates/partials/outbound-fact-sourcing.md.j2` and included by
  `CLAUDE.md.j2` § 9, `cs-triage-mail` § 2b and `cs-campaign-tick`. `cs-review`
  is not a host: it composes nothing and inherits them by reading `CLAUDE.md`.
  The read path is `cs ask`; `cs chat` is denied to the cron. The rules ship
  abstract, because a concrete value correct in one country is inherited as
  false everywhere else.
- **Contact history is cross-mailbox everywhere — the human verbs and every
  send gate.** The fan-out reads profile accounts (credential from the engine
  handover) plus manifest-declared mailboxes (app passwords in
  `CS_READ_MAILBOX_PASSWORDS`, plain IMAP, strictly parsed). A mailbox that
  cannot be read is `unreadable`, never absent; a send gate meeting one
  refuses, names it, and mutates nothing; a `ready` draft row carries its
  incomplete evidence inline; the dossier verdict keys off "ever". Proven live
  on `124-cs` including fail-closed under a real authentication refusal.
  `send_first` stays deliberately ungated.
  [Work trace](execution-plans/2026-09-01-contact-history-across-mailboxes.md).
- **Both clones declare, install and run `v0.39.0`** (2026-09-02, verified on
  the installed package, locks proven by solo-install). The CHANGELOG
  operational-pin marker carries the sign-off. `mario124-cs`
  (`/home/mal/124/mario124-cs`) is pinned at `v0.35.0`; its tree has no commits
  and no remote, so that clone's own history starts whenever its operator makes
  it start.

- **The provider-routing seam is partial.** The send guard can call a direct
  classifier through `cs/worker_llm.py`; general `role=` routing remains opt-in
  through `CS_LLM_ROUTE`. Kernel-owned LLM work must stay fixed-output and
  company-neutral.

## Unresolved

- **One collaudo leg remains unobserved on both clones**: a draft-only campaign
  tick meeting an `evidence_incomplete` refusal end-to-end. Ticks run and pass,
  but with healthy credentials no refusal occurs, so the leg discharges only at
  a real credential failure or a deliberately injected one. Recorded in each
  clone's own active-context.
- **`mrcall-cs/docs/owner-actions.md` records a stopped-sends posture that is
  not current** — its two send crons were live before and after the upgrade
  window. That file records the operator's own posture decision, so it is his
  to reconcile, not the kernel's.
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

1. Observe the outstanding collaudo leg: a draft-only campaign tick meeting an
   `evidence_incomplete` refusal — at a real credential failure or an injected
   one, whichever comes first.
2. Replace internal `re-collaudo` wording still exposed by `cs update` with
   plain operator language.
3. Promote reusable attachment-reading and scheduling pieces only when a second
   clone needs them, per the rule of two.
