---
doc_baseline_commit: 46d5f80d2d9e9097142356dd99923f97032095fe
doc_baseline_date: 2026-10-08
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: current source capabilities, untagged development and unresolved work.
Durable rules live in the [kernel charter](kernel-charter.md), release history in
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
  Both maintained clones install the public `v0.49.0` tag at `1aea012` and
  report `0.49.0`. Their pinned lockfiles rebuild the same package.
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
- `cs ask` negotiates engine read-only chat policy version
  1 before sending a question. The scheduled wrapper denies all six command
  spellings of each raw mutating memory/update/preparation RPC surface. Focused
  policy tests, the deny-enumeration gate and `cs memory` pass.
- `cs instructions` compiles
  `company/customer-service-playbook.md`, `company/mailbox-identity.md` and
  `company/mailboxes/<email>.md` into the engine's reserved
  `operator-instructions` documents and, with `--commit`, stores them only
  through `instructions.store`. `cs project new/save/import` refuse the
  reserved slug; the cron wrapper denies the verb and the raw RPC in all six
  spellings; `cs setup` and `cs memory` report the company files as the
  standing-instructions store. The engine side is a separate `mrcall-desktop`
  change. Publication is verified against the real loopback fixture;
  production publication and Firebase authentication remain unverified.
- `cs-instructions` provides a canonical interactive standing-rule workflow
  across Claude, Codex and OpenCode. All 33 native fixture cases pass with
  independently checked publication, Git and refusal evidence. Final review,
  release and live clone adoption remain pending under the
  [plan](execution-plans/2026-10-07-cs-instructions-skill.md).
- Interactive `cs draft-send <full-engine-draft-id>`:
  it approves the exact engine draft and checks recorded sent status. The
  supplied cron wrapper denies the command; the CLI has no headless/pause guard.
  Guidance reserves ambient Gmail connectors for reviewing engine-owned drafts.
- Scheduled Claude retries only after a proven pre-tool quota/payment refusal.
  The optional OpenRouter model and per-tick budget are manifest knobs. Fixed
  owner mail reports route/model changes and stops. Café 124 runs the generated
  draft-only wrapper; MrCall runs its clone-owned send launcher through the
  same supervisor. The supervisor checks each launcher's permissions against
  its resolved triage mode before starting Claude. Both clones configure $4
  fallback budgets. MrCall uses its clone-owned Anthropic API primary and
  fixed missing/restored-key notices. Reply quality requires separate acceptance.

- Pricing and triage integration and acceptance remain open under the
  [pricing plan](execution-plans/2026-09-21-pricing-skill-production-economics.md),
  with candidate work on `work/pricing-triage-20261001` at `d16e3e5`.

## Unresolved

- Engine and direct-classifier failover remain separate from scheduled Claude
  recovery; the [broader plan](execution-plans/2026-09-27-operator-llm-recovery.md)
  is still active.

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
