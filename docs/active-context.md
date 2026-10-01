---
doc_baseline_commit: 258c9277ffc408e5d4ba51e2018716c04830717c
doc_baseline_date: 2026-10-01
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: current source capabilities, untagged development and unresolved work.
Durable rules live in [`AGENTS.md`](../AGENTS.md), release history in
[`CHANGELOG.md`](../CHANGELOG.md), and dated operational observations in
[`active-context-archive.md`](active-context-archive.md).
<!-- doc-scope:end -->

## State now

The unattended operator runs through Claude Code; engine APIs and kernel direct
classifiers have separate models, billing and stop controls. See
[runtime boundaries](operator-runtime.md). Engine daily caps do not cover all
operator activity, and CS_PAUSE does not stop engine processing.

- **Latest release tag: `v0.49.0`. Current HEAD status: untagged.** These
  sentences are parsed by `tests/test_release_consistency.py`; preserve their
  wording. Release verification records are in the [customer-service playbook plan](execution-plans/2026-09-20-company-customer-service-playbooks.md).
  Both maintained clones report `0.49.0`; tag `v0.49.0` points to `1aea012`.
  This checkout is based on `258c927`, behind published history, and declares
  `0.46.1`. Its dirty source and local CHANGELOG are not the production tree.
  Release history after this HEAD is available through `git show origin/main:CHANGELOG.md`.
- Released `v0.49.0` adds `cs instructions`: clone company files own standing
  instructions and `instructions.store` publishes their compiled engine copy.
  This other-session change is absent from this checkout; its older charter
  still describes USER_NOTES. Live engine acceptance is not established here.
- Vonage supports clone-scoped reads, provisioning previews, supervised
  domain/user creation and additive ACL changes with explicit credential
  references. Headless/paused mutations refuse. See [integration](integrations/vonage.md).
- Integration guides separate Vonage, Shopify, Drive and Faire. Faire application
  setup is documented; authenticated use and a kernel adapter remain unverified
  and unimplemented respectively.
- The engine owns mail classification, task judgement and company memory.
  Shared written projects are revisioned engine records; legacy clone folders
  remain recoverable in private Git history.
- `cs init --descriptor` consumes the explicit Desktop handoff. `cs setup` checks
  workspace, identity, preparation evidence, memory and agent tools; preparation
  counts do not certify reply quality or mailbox credential validity.
- Stamped AGENTS.md owns workspace instructions. CLAUDE.md is a one-time
  bootstrap; Claude Code, Codex and OpenCode share canonical skills.
- `cs-triage-mail` reads an optional clone-owned
  `company/customer-service-playbook.md`; the shared skill retains send and
  tool-approval boundaries across all three agent surfaces.
- Cross-mailbox history includes configured profiles and read mailboxes.
  Incomplete evidence refuses applicable sends; send_first remains deliberately
  ungated. Sent/All Mail owns message-existence evidence; the engine owns judgement.
- Role routing is opt-in through CS_LLM_ROUTE; send guards can use a direct
  classifier. `cs memory` reports the ten-store memory map.
- Local and released source make `cs ask` negotiate engine read-only chat policy version
  1 before sending a question. The scheduled wrapper denies all six command
  spellings of update, reconsolidation, memory join/reset/restore and preparation
  resume RPCs, including `memory.restore_version`. These capabilities are
  included in the installed release; no new runtime test is claimed here.
- Local and released source include interactive `cs draft-send <full-engine-draft-id>`:
  it approves the exact engine draft and checks recorded sent status. The
  supplied cron wrapper denies the command; the CLI has no headless/pause guard.
  Guidance reserves ambient Gmail connectors for reviewing engine-owned drafts.
- Released scheduled-Claude recovery retries a proven pre-tool quota/payment
  refusal through OpenRouter and sends fixed owner notices without an LLM.
  Both clones configure a $4 fallback budget. MrCall's clone-owned launcher
  uses an Anthropic API primary and reports missing/restored primary keys;
  its latest observed tick exits 0. The local untracked supervisor predates
  the released send-mode support and must not replace the installed package.
- Local pricing and triage templates contain another session's uncommitted
  workflow changes. Their brief records an exercise; release and installed
  equivalence remain open in the
  [pricing integration plan](execution-plans/2026-09-21-pricing-skill-production-economics.md).

## Unresolved

- The [exact-draft-identity plan](execution-plans/2026-09-16-exact-draft-identity.md)
  specifies preservation proof, exact pairing and reconciliation. These are not
  implemented; a Gmail send outside the engine can still leave a stale mirrored
  draft. Current pairing uses thread/recipient inference, and Gmail-only rows
  have no authored body in review. Dated inventory counts are in the archive.
- Unanswered-mail disagreements and review-latency fixture gaps remain open.
  `cs unanswered --all-buckets` can exit 3 after unreadable mail without stderr;
  stamped skills do not explain that outcome.
- Paid agent-tick/live draft behavior remains outside read-only FULL checks.
  Instruction tests do not establish agent-behavior proof or revoke ambient
  permissions. Historical clone send posture requires checks in that clone.
- Live SIP/customer-trunk acceptance, telephone-number association, PBX setup
  and secondary-account onboarding remain separate from the release checks.

## Next

1. Reconcile this checkout with published history in a separate integration,
   preserving the pricing and other local changes.
2. Continue exact draft identity from its active plan; verify canonical send and
   reconciliation before a new release/clone rollout.
3. Diagnose unanswered-mail disagreement and close evidence/latency gaps in the
   owning engine or kernel path rather than adding parallel judgement.
4. Complete secondary-account onboarding when requested and replace internal
   verification terminology in operator-facing update output.
