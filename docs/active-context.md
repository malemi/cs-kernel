---
doc_baseline_commit: dd7b873579c9203b39bc04afdc2542a4d0e7b593
doc_baseline_date: 2026-09-08
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: current source capabilities, untagged development and unresolved work.
Durable rules live in [`AGENTS.md`](../AGENTS.md), release history in
[`CHANGELOG.md`](../CHANGELOG.md), and dated operational observations in
[`active-context-archive.md`](active-context-archive.md).
<!-- doc-scope:end -->

## State now

- **Latest release tag: `v0.43.0`. Current HEAD status: untagged.** These
  sentences are parsed by `tests/test_release_consistency.py`; preserve their
  wording. Release, push and operational clone upgrades require explicit
  authorization and the release procedure's verification gates.
- Workspace instructions are stamped into `AGENTS.md`; `CLAUDE.md` is a
  one-time bootstrap. Claude Code, Codex and OpenCode share canonical skills.
- The engine owns mail classification, task judgement and company memory.
  Shared company memory exists in the companion engine implementation;
  `cs setup` checks its availability through `memory.status`; both maintained
  operational clones passed this read during the authorized release verification.
- `cs memory` reports the ten-store map. Outbound sourcing instructions require
  memory first and a second source when memory is empty. Their runtime semantic
  effectiveness is still a verification gap below.
- Cross-mailbox history uses profile accounts and declared read mailboxes.
  Unreadable evidence causes applicable send gates to refuse; `send_first`
  remains deliberately ungated. The engine remains authoritative for judgement,
  while Sent/All Mail remains the dedup source.
- Provider routing is partial: the send guard can use a direct classifier;
  general role routing remains opt-in through `CS_LLM_ROUTE`.
- Both maintained clones now run the public `v0.43.0` tag. Their locks rebuild
  independently; read-only FULL comparisons found no material regression.
  Existing crontab and clone-specific deny rules were preserved, and temporary
  upgrade pauses removed. The release record identifies remaining harness drift.

**Workspace setup.**

`cs init --descriptor PATH` selects an explicit desktop handoff, reuses that
selection for mailbox settings and credentials, and distinguishes creation,
installation and optional login outcomes. Login requires the engine to confirm
the configured UID and signed-in state.

`cs setup [--json]` checks workspace files, mailbox configuration, expected engine
identity, preparation evidence, company memory and external-agent executables.
Missing old-engine evidence stays unverified. Completed preparation requires
all three agent prompts and no pending memory processing. Processing counts do
not prove reply quality; mailbox credential validity and agent login are not
probed. Auth can refresh local caches; no business mutation is initiated.

Full local gates pass, including an isolated generated workspace, installation
of changed source into its own environment and a controlled local WebSocket.
The published v0.43.0 release includes these commands and guarded `login --mint`,
refresh-cache invalidation and closed cron stdin. Both operational clones prove
engine identity and shared-memory access. 124 is ready; MrCall has fourteen
messages awaiting preparation at the release check. Evidence lives in
[the delivery plan](execution-plans/2026-09-10-desktop-workspace-setup.md).

## Unresolved

- An operator report dated 2026-09-08 found six disagreements between
  `cs unanswered` and Sent evidence. It remains undiagnosed; resolve the engine
  verdict or sweep window rather than adding a parallel kernel judgement.
- Review-latency brief criteria 2–4 still lack fixture gates for the reported
  verdict corrections and round-trip/message bounds. Historical operator runs
  also reported substantial engine LLM latency; no new timing was measured.
- `cs unanswered --all-buckets` can exit 3 after a mailbox-read failure without
  stderr, and the stamped skills do not document that outcome.
- End-to-end observation of a draft-only tick encountering `evidence_incomplete`
  remains outstanding. The historical live gate also compares variable LLM prose
  and clock-dependent state; its reproducibility defect remains open.
- Outbound sourcing is tested as rendered instructions, not demonstrated agent
  behavior. Interactive skills cannot revoke ambient session permissions.
- Historical clone notes identify a mismatch between documented send posture
  and observed cron state, plus reliance on an ambient provider credential in
  another clone. These require deliberate checks in their owning environments;
  neither condition was re-observed or changed here.
- Secondary-account migration remains separate from the released mint capability.
  Automated FULL does not establish paid agent-tick or live draft behavior;
  the external harness still needs its obsolete rate-cap and cron assumptions
  updated. MrCall preparation backlog requires the normal engine update flow.

## Next

1. Complete secondary-account onboarding when requested and repair obsolete
   external-harness assumptions; the kernel rollout and lock proofs are complete.
2. Diagnose unanswered-mail disagreement and close the evidence/latency gaps.
3. Replace internal verification terminology still exposed by `cs update` with
   operator-facing language; promote clone-specific tools only under rule two.
