---
doc_baseline_commit: 5736e568c50238f811e3adb57ccbebc4f7ccb130
doc_baseline_date: 2026-09-16
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

- **Latest release tag: `v0.46.0`. Current HEAD status: untagged.**
  Release verification records are in the [customer-service playbook plan](execution-plans/2026-09-20-company-customer-service-playbooks.md).
  Current clone installations must be checked in their own environments.
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
- Untagged source includes interactive `cs draft-send <full-engine-draft-id>`:
  it approves the exact engine draft and checks recorded sent status. The
  supplied cron wrapper denies the command; the CLI has no headless/pause guard.
  Guidance reserves ambient Gmail connectors for reviewing engine-owned drafts.
  The command is absent from the released tag; clone installation is unverified.

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

1. Continue exact draft identity from its active plan; verify canonical send and
   reconciliation before a new release/clone rollout. No send is part of doc-end.
2. Diagnose unanswered-mail disagreement and close evidence/latency gaps in the
   owning engine or kernel path rather than adding parallel judgement.
3. Complete secondary-account onboarding when requested and replace internal
   verification terminology in operator-facing update output.
