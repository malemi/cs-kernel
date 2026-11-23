---
status: active
created: 2026-11-23
brief: ../briefs/2026-11-23-mailbox-drafts.md
---

# Kernel mailbox draft delivery

The governing approved execution plan is
`/home/mal/hb/docs/execution-plans/2026-11-23-drafts-live-in-the-mailbox.md`.
Its ownership, review order, spending controls, rollout and installed acceptance
apply to this leaf. The delivery lead owns integration and release.

The source candidate is `0.75.0` on
`/home/mal/worktrees/cs-kernel-mailbox-implementation`. Both installed clones
remain on `v0.74.1`; recurring schedules are paused. The generic candidate launcher remains
draft-only. The prepared support-launcher patch grants scheduled `reply-send`
and denies named-draft sends; it is not installed yet. Five prepared adoption patches preserve
both clones' local permission deltas.

The immutable v0.74.1 baseline full suite passes. Candidate executor checks and
independent actual kernel/engine-dispatch integration pass. The complete candidate
suite exits zero with `RESULT: all gates green` in
`/tmp/mrcall-ai-kit/kernel-mailbox-implementation/full-observed.log`. Its durable
process receipt is `full-observed-exit.json` beside that log, completed at
2026-11-23 19:38:52 UTC. All 164 product files remain unchanged through the run;
the product manifest SHA-256 is
`35c94954d61c8c5f713869b68142212330069892c2691d4445e000e235037250`.
The M2 source integration review is APPROVED and retained at
`/tmp/mrcall-ai-kit/mailbox-kernel-integration-review/report.md`.

Before release, retain the completed full suite and independent integration
verdict, reconcile documents and review their semantics. Before public publication, run FULL on both normal clones using the exact
frozen local release commit and clean built artifact. Retain that candidate
installation state. Publish only the reviewed immutable tag after those checks;
then adopt/verify the public tag through the normal pin/install/render route
and complete actual-byte and public-reference provenance checks. No normal clone receives a source override.

The Gmail account consent dependency remains open. The HB plan requires native
Desktop/MCP/Gmail checks, two ordinary draft-mode ticks selecting the same original,
one direct-send tick, the separate exact 17-target Trash order and one hosted
engine release across seven units. These checks are pending; no live result or
documentation baseline advancement is asserted here. Compatible rollback preserves
engine receipts and never restores discarded internal drafts or repeats a possible
send. Earlier workstreams retain their separate acceptance and spending limits.
