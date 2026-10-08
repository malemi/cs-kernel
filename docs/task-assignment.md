# Engine-owned thread assignments

## Availability

This consumer is local source work under
[the delivery plan](execution-plans/2026-10-08-engine-task-assignment-consumer.md).
CLI, queues, draft guards and canonical workflows consume the same engine
authority. The delivery plan owns source, transport and three-host acceptance. Existing released
clones and production engines have not been upgraded by this task.

The engine owns assignment state, membership, source verification and signed
mutation authority. The kernel keeps no assignment ledger and never signs or
self-approves an operation. See the engine's
[operational contract](../../mrcall-desktop/engine/docs/features/task-assignment.md)
for fixed root-owned trust/signing paths and rollback restrictions.

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
Offline fixtures do not establish live mailbox parity or latency, installed
Desktop behavior or FULL acceptance on both maintained clones. Release,
production trust setup and clone upgrades require separate authorization.
