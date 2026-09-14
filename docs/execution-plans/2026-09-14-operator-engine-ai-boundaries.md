---
status: completed
---
# Operator and engine AI boundaries — plan

Brief: [intent](../briefs/2026-09-14-operator-engine-ai-boundaries.md).

- [x] Confirm wrapper, RPC and direct classifier boundaries; review brief.
- [x] Review plan before documentation edits.
- [x] Back up local Desktop docs and fast-forward the stale checkout, retaining local content.
- [x] Put execution/model/billing/pause boundaries in all three entry indexes and owning guides; correct adjacent contradictory claims.
- [x] Record dated cron/pause observations separately from durable architecture; no runtime changes or paid calls.
- [x] Verify links/mechanical gates and independently review source-backed claims; commit only this task's files.

The scope is repository-owned documentation. Do not edit managed CLAUDE.md,
runtime code, generated clone templates, model configuration or cron schedules.
Preserve unrelated hb work and earlier local documents. No kernel tag/installer
or clone update is needed. The shared engine cap is not a global account cap:
Claude CLI usage and direct kernel API calls are outside it. Operator pause
prevents subsequent guarded ticks; it does not terminate an already running
process or stop an independent engine daemon. Checks read source/settings
metadata only, never credentials or paid CLI test commands.

Desktop checkout advanced from `9ea3dae` to released `d781787`. Earlier local
README/brief files are preserved in `/tmp/mrcall-desktop-docs-preserved-20260914`;
README links already exist upstream, one brief is byte-identical and the other
is the earlier pre-implementation version. No unique local content was lost.

Independent source review approved the three execution paths and entry routing;
adjacent stale Desktop architecture and pause claims were corrected. Mechanical
gates pass in all three repositories. Unrelated hb edits, credentials, cron,
runtime settings and generated templates remain outside this change.
