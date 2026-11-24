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

The local forward release candidate is `0.75.1` on
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

The reviewed HB November 24 amendment requires IMAP/SMTP with the existing app
password; Gmail OAuth consent is not a dependency. The engine source milestone
is APPROVED at `/tmp/mrcall-ai-kit/mailbox-imap-engine-milestone-review/report.md`.
Kernel handles remain opaque and public RPC shapes remain compatible; current
engine RPC inventory checks pass against this exact kernel source. The HB plan requires native
Desktop/MCP/Gmail checks, two ordinary draft-mode ticks selecting the same original,
one direct-send tick, the separate exact 17-target Trash order and one hosted
engine release across seven units. These checks are pending; no live result or
documentation baseline advancement is asserted here. Compatible rollback preserves
engine receipts and never restores discarded internal drafts or repeats a possible
send. Earlier workstreams retain their separate acceptance and spending limits.


The unpublished v0.75.0 tag remains fixed at 6022ec6. Current v0.75.1 repairs
bounded campaign request keys and explicit same-key retirement after Sent proof.
The unchanged independent actual kernel/RPC/SQLite/IMAP reproductions pass2;
actual caller/CLI tests pass22. Its fresh M2 source compatibility review is
APPROVED at `/tmp/mrcall-ai-kit/mailbox-imap-docs-kernel-review-20261124/m2-repaired-review.md`.
The earlier full-suite evidence above applies to its recorded original bytes;
the repaired release requires its own complete at-tag run and BOTH normal-clone
FULL acceptance. Default Desktop token persistence is a separate prerequisite
under the approved HB November24 refresh-only authentication brief and plan.
