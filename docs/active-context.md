---
doc_baseline_commit: eae4d260ee09a04aaa90c4558bccaf77e6d53c61
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

Candidate [thread assignments](task-assignment.md) pass local CLI/transport,
full-suite and nine native workflow cases across Claude, Codex and OpenCode.
Version `v0.51.0` is prepared for authorized release. Both clone candidates pass
current scoped FULL acceptance and real bounded provider reads; the legacy July
harness remains red on the installed `v0.50.0` baseline. Production trust,
activation and original-clone upgrades remain pending. Local hardening is closed
with limits in the [closure record](execution-plans/2026-10-07-desktop-kernel-hardening-closure.md).

The unattended operator runs through Claude Code; engine APIs and kernel direct
classifiers have separate models, billing and stop controls. See
[runtime boundaries](operator-runtime.md). Engine daily caps do not cover all
operator activity, and CS_PAUSE does not stop engine processing.

- **Latest release tag: `v0.51.0`. Current HEAD status: tagged as `v0.51.0`.** These
  sentences are parsed by `tests/test_release_consistency.py`; preserve their
  wording. Release verification records are in the [customer-service playbook plan](execution-plans/2026-09-20-company-customer-service-playbooks.md).
  Both maintained clones install public `v0.50.0` at `29ab764` and report
  `0.50.0`. Their lockfiles independently rebuild that exact tag; static
  verification and authenticated identity reads pass on both.
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
- Candidate `v0.51.0` adds bounded cross-mailbox reads with a fixed self-owner
  skip and named read/unreadable/skipped scope. Incomplete evidence refuses
  applicable sends; `send-first` retains its existing ungated contact-state path.
  [Fan-out acceptance](execution-plans/2026-10-06-fanout-bounded-reads.md) records
  real provider history, RFC-key parity and bounded FETCH latency on both clone
  candidates. Publication and original-clone installation remain pending.
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
  independently checked publication, Git and refusal evidence. Implementation
  and final review are approved; both maintained clones install the workflow
  through the [completed plan](execution-plans/2026-10-07-cs-instructions-skill.md).
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
- Live unanswered-mail parity and review-latency acceptance remain open.
  `cs unanswered --all-buckets` reports incomplete assignment authority and
  exits 3; canonical triage guidance retains held threads.
- Clone-local help routing and MrCall triage prose contain reviewed corrections
  beyond the tagged templates. Preserve these documentation adaptations on the
  next stamp; the factory help/triage descriptions still need alignment.

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
