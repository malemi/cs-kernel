# Consume explicit engine task assignments

Date: 2026-10-08. Local implementation intent; no release or live clone change.

## Intent and authorization

Complete the kernel part of scope 6 of the meta-repository fan-out brief after
operator selection of explicit engine tasks. The reviewed
[ownership design](../2026-10-07-human-thread-ownership-design.md) supplies lifecycle;
Desktop's approved [brief](../../../mrcall-desktop/docs/briefs/2026-10-08-explicit-task-assignment.md)
and [plan](../../../mrcall-desktop/docs/execution-plans/2026-10-08-explicit-task-assignment.md)
own the authoritative assignment contract. Engine M1 must pass fresh integration
review before dependent kernel implementation begins.

## Scope

Consume typed engine assignments and owner-authenticated peer reply evidence.
Add explicit preview/export/commit CLI operations without a local ownership ledger.
The privileged host operator signs exact operations; the kernel never signs,
self-approves, modifies membership or grants a scheduled writer. Deny new mutation
surfaces and raw assignment commit in all six cron spellings. No changes to
ordinary escalation authority or public/private task visibility.

Reuse the existing batched mailbox reader for actual Sent/thread metadata if
needed; keep scopes 1–5 row bytes intact. Source verification, automation and
human confirmation belong to engine. Never turn an address exchange, timestamp,
From header or false automatic flag into verified human authorship. Peer evidence
is advisory until the owning engine validates the exact source for a signed
human-confirmed operation. Partial sources remain UNKNOWN even with a candidate.

One common adapter projects engine authority into unanswered, review, dossier,
triage and draft guards. Preserve thread identity through address rollups: one
assigned conversation cannot hide a different unanswered conversation with the
same sender. Keep active human work, needs-assignment, conflicts and unknown work
visible; held work cannot generate/send an automatic reply. Distinguish manual
assignment, supervised answer confirmation and address-level escalation; agreement
renders provenance once, disagreement holds action and names both authorities.

Handled records stay local statements about out-of-band resolution. Closing an
assignment requires exact engine ID/revision/covered inbound identities and a
signed operation. Only acknowledged closure settles ownership; conflicts and
unavailable source leave held visible work even if a local handled record exists.
Later inbound with a new identity returns operator work, including the same or
older Date header, without restoring prior assignee. Active ownership retains
later inbound with its current human. Retain closed assignment audit in dossier.

## Acceptance

- Actual CLI and WebSocket/SQLite fixture journeys exercise manual assignment,
  reassign, confirmed reply, close/handled acknowledgement and failure, restart,
  later inbound and unrelated same-address threads.
- Every lifecycle state appears in human work/review/dossier and the corresponding
  machine output. Unknown, candidate, active ownership and conflict hold drafts;
  closed audit does not suppress a new inbound identity.
- Raw/scheduled callers cannot forge grants, actor, source or membership. Cron
  denial enumeration passes; authority remains enforced by engine independently.
- Existing sender/gate and scopes 1–5 fixtures remain equivalent. Full kernel
  suite, installed package, template/permission gates pass with actual logs.
- Any changed canonical skills are actually discovered and executed by Claude,
  Codex and OpenCode using the same rendered bytes, with final decisions retained.
- Documentation, fresh milestone review, doc-critic and final-user review pass;
  original reader/native evidence and historical limitations remain intact.

## Constraints and rollback

Company-neutral Settings/manifest data only; no parallel classification or
ownership database. Preserve private task/Qonto boundaries, company-authored
files and all concurrent edits. Feature compatibility with older engines must be
explicit: unavailable assignment authority is not an empty successful read and
must not claim no owner. Do not silently widen sending permission.

Rollback removes only owned consumer changes and retains engine assignment/audit
history; no data deletion or clone repin. Production trust configuration, live
Sent/recipient parity, mailbox latency and both-clone FULL acceptance remain
separate release obligations. This brief authorizes local completion only.
