# Engine-owned thread assignments

## Availability

This consumer ships in `v0.51.0` and is installed in both maintained clones.
CLI, queues, draft guards and canonical workflows consume the same engine
authority. The [delivery plan](execution-plans/2026-10-08-engine-task-assignment-consumer.md)
owns local source/transport/native acceptance. Six hosted engines have compatible
source and verified root-owned trust. Café 124's four members share one space;
MrCall support and Mario share support's company space after a separately
authorized fenced join. Both members have complete authenticated assignment reads
and shared project access; private mail and ordinary/Qonto tasks remain isolated.
Real assignment writes and live peer-answer parity remain unverified.

The engine owns assignment state, membership, source verification and signed
mutation authority. The kernel keeps no assignment ledger and never signs or
self-approves an operation. See the engine's
[operational contract](../../mrcall-desktop/engine/docs/features/task-assignment.md)
for fixed root-owned trust/signing paths and rollback restrictions.

## Contextual email policy — unreleased candidate

The local [contextual-email workstream](execution-plans/2026-10-08-contextual-email-assignment-guard.md)
extends the engine boundary to reply draft updates and final sending, including
already composed drafts. It is not included in the installed `v0.51.0` clones
or the six hosted engine pins. The old `assignment_draft_policy: 1` capability
proves only its scoped draft contract and cannot certify final-send enforcement.

The engine owns durable [assignment enrollment](../../mrcall-desktop/engine/docs/features/assignment-enrollment.md).
Missing trust or an empty ledger cannot turn a managed company into an unmanaged
one. Fresh never-enabled local profiles retain contextual email without root
configuration; ambiguous assignment-capable legacy profiles require trusted
offline historical classification or privileged enrollment.

Generic send-tool approval grants an effect permission, not an assignment
exemption. Exact thread/source/draft context must survive composition, ordinary
email-backed task routing and final send. Stale draft snapshots cannot clear or
send around a newer binding. Source-free standalone messages keep ordinary
approval rules; arbitrary prose is not semantically classified as reply intent.
Kernel fixed-template bulk and first-contact delivery remain separate.

The candidate requires `system.capabilities.contextual_email_policy: 1` for
`cs chat`, `cs draft-reply` and `cs draft-send`; unavailable support refuses
before chat generation or a draft effect. `draft-reply` also retains its existing
assignment-draft policy negotiation and required exact thread flag.

```bash
cs chat --thread-id '<root@example.com>' --reply-to '<inbound@example.com>' 'Prepare this reply'
cs chat --allow send_draft --thread-id '<root@example.com>' --source-id ENGINE_EMAIL_ID 'Send the approved reply'
cs draft-reply 'Prepare this reply' --thread-id '<root@example.com>' --source-id ENGINE_EMAIL_ID
cs draft-send FULL_ENGINE_DRAFT_ID
```

`cs chat` accepts `--thread-id`, `--source-id`, `--reply-to` and `--draft-id`.
They bind the original RFC root, owner-scoped engine email, exact RFC target and
existing draft respectively. All supplied identifiers must agree with stored
source; they cannot name a different owner or strip an established reply binding.
`draft-send` binds its exact draft automatically. The engine receives these as
`chat.send.email_context` with `contextual_email_policy_version: 1`.

Ordinary email-backed task context also constrains effects across chat and worker
thread hops. Multiple original messages in one task are admissible only within
the same exact thread; an explicit original source can narrow that set. Conflicting
threads or unavailable identities remain held. A custom send launcher must pass
the selected original thread and source explicitly; the separately owned MrCall
launcher candidate is an uninstalled handoff, not a changed live schedule.

Contextual campaign sending requires an exact existing engine draft and verifies
its recorded sent state after the guarded engine lifecycle. A campaign's
`queue-draft` cannot copy a contextual reply into Gmail: review its existing
engine draft instead. A separate unlocked provider append would evade current
assignment admission. Source-free campaign queueing retains its previous
Gmail review surface.

The existing `cs draft-reply` Gmail review-copy behavior remains compatible.
It checks current assignment projection immediately before append, but the
append is outside the engine/company lock and has no atomic assignment guarantee.
Manual Gmail edits/sends and other external mailbox clients are outside engine
enforcement. The strengthened capability certifies actual engine private draft
writes and final transport, not a global lock on mailbox credentials or clients.

## Read and prepare an operation

```bash
cs assignment status '<root-message@example.com>' --json
cs assignment preview assign '<root-message@example.com>' --revision 0 --assignee-uid HUMAN_UID
cs assignment export assign '<root-message@example.com>' --revision 0 --assignee-uid HUMAN_UID --output intent.json
```

Use the exact RFC thread key from correspondence. Revision 0 means no assignment;
existing rows require their current revision. `reassign` and `close` use the same
preview/export verbs with the applicable task/revision. `--source-id` selects an
own-engine message for supervised answer confirmation; the engine independently
checks the real source. Without it, assignment is explicitly manual and does not
claim a detected human answer. `--reason` supplies the operation reason.

An export creates a new file with mode 0600 and refuses to overwrite it. Intent
files contain operation metadata, not credentials or mail bodies. They expire
within five minutes. An independent privileged host operator reviews the exact
intent and emits its matching signed grant through the engine approval command.
Submit those unchanged files:

```bash
cs assignment commit --intent intent.json --grant grant.json
```

A receipt must acknowledge the exact operation, task, company, next revision and
payload digest. Closure must also acknowledge the identical inbound coverage.
Malformed, stale or unavailable responses exit 3 and are not success. Status
reads likewise exit 3 for incomplete authority. Use the existing account selection
for the intended authenticated engine; the kernel does not silently switch actor.

Close must run against the original creator/source owner's engine. A different
member's empty private mailbox is not complete closure evidence. Shared assignment
visibility does not grant access to that member's private messages.

## Work queues and draft boundary

Unanswered checks each exact thread before answered subtraction or sender rollup.
It keeps human assignments, candidates awaiting verification, conflicts and
unknown authority visible in human work. Another unanswered thread from the same
sender remains separate operator work when no address-level takeover applies;
existing address-level escalation authority still holds the contact. Review and dossier consume the same typed
projection and retain closed audit.

| State | Action |
|---|---|
| `normal` | No assignment hold established by complete engine evidence. |
| `needs-assignment` | Human verification/assignment pending; automatic reply held. |
| `assigned` | Work belongs to the named UID; automatic reply held. |
| `conflict` | Authorities disagree; visible and held. |
| `unknown` | Scope or identity cannot establish an answer; visible and held. |
| `closed` | Exact acknowledged inbound coverage is settled; audit retained. |
| `later-inbound` | New inbound identity returns operator work without reviving the former assignee. |

A nonautomatic Sent message is a candidate, not proof of human authorship. Peer
engines must match configured UID and company space. An unreadable required peer
keeps the overall result unknown even when another peer found a candidate.
Manual assignment, supervised source confirmation and local address escalation
retain separate provenance. Different or unverifiable escalation/assignee
identities hold action rather than choosing an authority silently.

`cs draft-reply` requires exact `--thread-id` before composition. The negotiated
engine assignment draft policy must also enforce that scope before a draft write;
a post-compose check alone cannot establish this boundary. An older engine without
the required policy cannot safely compose this scoped workflow. Existing send
authorization remains separate from assignment status.

## Handled resolution

`cs handled` may record a human's local out-of-band resolution. This alone does
not close a company assignment. For exact approved engine closure, provide both
`--assignment-intent` and `--assignment-grant`; the intent must close the named
thread/task/revision and name the same email as its `handled_ref`.

A failed acknowledgement leaves work visible and held even when the local record
was saved. A new inbound identity outside acknowledged coverage reopens operator
work, including the same or an older Date header. Active assignments retain new
inbound with their human. No address-wide handled cutoff overrides these identities.

## Compatibility and remaining acceptance

Protocol version 1 and configured peer identity/company are checked explicitly.
Unavailable methods, malformed responses and unreadable source are unknown;
no fallback turns them into successful absence. The delivery plan retains
canonical workflow and scheduled-wrapper verification.
Offline fixtures alone do not establish live mailbox parity or latency.
Separately authorized release checks verify scoped current FULL on both clones,
real provider reads, root key permissions, six hosted activations and reproducible
clone locks. Customer sends, paid ticks, real assignment mutations and installed
Desktop GUI behavior remain unverified.
