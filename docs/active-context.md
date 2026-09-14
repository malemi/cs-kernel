---
doc_baseline_commit: d79e495803eef9ebb6cc6c0817079d172e159952
doc_baseline_date: 2026-09-14
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: current source capabilities, untagged development and unresolved work.
Durable rules live in [`AGENTS.md`](../AGENTS.md), release history in
[`CHANGELOG.md`](../CHANGELOG.md), and dated operational observations in
[`active-context-archive.md`](active-context-archive.md).
<!-- doc-scope:end -->

## State now

The unattended operator is a Claude Code process; engine API calls and kernel
direct classifiers have separate model/billing/stop controls. See [runtime boundaries](operator-runtime.md).

- **Latest release tag: `v0.45.0`. Current HEAD status: untagged.**
  The published tag and both maintained clones passed their release
  verification under the [rollout plan](execution-plans/2026-09-14-vonage-production-rollout.md).
  Both production clones have v0.45.0 installed and independent lock rebuilds.
  Original operator pause states are restored; crontab is unchanged.
- The Vonage CLI supports clone-scoped reads, provisioning previews, supervised
  domain/user creation and additive public ACL updates. Provider credentials
  resolve only from explicit clone references. Headless and paused mutations
  refuse; password handoff stays outside model prompts. See
  [Vonage](integrations/vonage.md) for the exact boundary.
- The README's integration index routes to separate Vonage, Shopify, Drive and
  Faire guides. Faire application setup is documented; authenticated API use
  and a kernel adapter remain unverified/unimplemented respectively.
- The engine owns mail classification, task judgement and company memory.
  Shared written projects use revisioned engine records, separate from entity
  memory. Legacy project folders remain recoverable in private clone Git.
- `cs init --descriptor` uses an explicit desktop handoff; `cs setup` checks
  workspace, engine identity, preparation evidence, memory and agent tools.
  Preparation counts do not prove reply quality or mailbox credential validity.
- Workspace instructions live in stamped `AGENTS.md`; `CLAUDE.md` is a one-time
  bootstrap. Claude Code, Codex and OpenCode share canonical skills.
- Cross-mailbox history spans configured profiles and read mailboxes. Incomplete
  evidence refuses applicable sends; `send_first` remains deliberately ungated.
  Sent/All Mail owns message-existence evidence; the engine owns judgement.
- General role routing remains opt-in through `CS_LLM_ROUTE`; the send guard
  can use a direct classifier. `cs memory` reports the ten-store memory map.

## Unresolved

- No customer trunk mutation or real SIP authentication/call was part of release
  validation. Telephone-number association and PBX configuration remain separate.
- The six reported disagreements between `cs unanswered` and Sent evidence remain
  undiagnosed. Repair the engine verdict or sweep window, not a parallel judgement.
- Review-latency criteria 2–4 lack fixture gates for verdict corrections and
  round-trip/message bounds; historical engine LLM latency is not remeasured.
- `cs unanswered --all-buckets` can exit 3 after unreadable mail without stderr;
  the stamped skills do not explain that outcome.
- Paid agent-tick/live draft behavior, including an `evidence_incomplete` refusal,
  remains outside the read-only FULL harness. Outbound sourcing has instruction
  tests but no demonstrated agent-behavior proof.
- Historical clone observations of send posture and ambient provider credentials
  need checks in their owning environments. Interactive skills cannot revoke
  ambient permissions. MrCall preparation backlog needs normal engine updating.
- Secondary-account onboarding remains separate from the released mint command.

## Next

1. Diagnose unanswered-mail disagreement and close evidence/latency gaps.
2. Complete secondary-account onboarding when requested; replace internal
   verification terminology exposed by `cs update` with operator-facing language.
