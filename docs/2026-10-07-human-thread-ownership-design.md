# Human ownership of a mail thread — proposed task-ledger design

Date: 2026-10-07. Status: independently reviewed design; operator selected
explicit engine task assignment on 2026-10-08. Nothing here implements ownership or grants a scheduled write.
Scope: scope 6 of the meta-repository fan-out brief dated 2026-10-06.

## Recommended mechanism and present contract

Use an engine-owned, explicitly assigned task to represent ownership of one
thread by a human. Keep mail classification and ordinary work tasks in the
engine. The kernel reads evidence and renders the resulting authority; it does
not keep a shadow ownership ledger. An address-wide handled or escalated record
cannot represent a thread assignment.

Current `TaskItem.owner_id` is the authenticated profile boundary, not the
assignee. The model has no assignee or ownership revision. `tasks.create`
accepts `sources`, and storage can match `sources.thread_id` or referenced email
IDs. Creation upserts by `(owner_id, event_type, event_id)` and refuses a closed
target unless explicitly reopened. These primitives provide thread references,
not company-wide assignment or a race-safe ownership transition.

`tasks.list_by_thread` exposes open ordinary tasks only. `tasks.get` exposes an
individual visible open/closed task including close audit. Both storage lookup
paths can turn an exception into empty/null, which cannot establish absence of
an authoritative assignment. Ordinary tasks live in profile stores; sharing a
company memory key does not share their ledger. Putting an assignee string in
`sources` would provide no enforced assignment and is not this design.

The alternative is a dedicated engine-owned thread-assignment record linked to
tasks. Choose that only if extending tasks cannot provide company membership,
unique authority and lifecycle without changing ordinary-task semantics. Both
require an engine contract. A clone-local JSON/SQLite ledger and reusing
`owner_id` as assignee are rejected alternatives.

Engine gaps are filed in Desktop
`engine/docs/features/human-thread-ownership-gaps.md`. The operator chooses the
mechanism after this design's independent review; kernel-only implementation
starts afterward under its own acceptance. No ownership implementation is part
of the current bounded-reader correction.

## Evidence and the minimal reader extension

A candidate human answer requires an actual message in the mapped colleague
mailbox's Sent folder, a usable normalized RFC conversation key matching the
customer thread, and a recipient participating in that thread. A From address
or address-wide prior exchange alone is insufficient. A team mailbox,
autoresponder or service identity is not a human solely because it can send.
Human/reply classification remains the engine's responsibility; Sent provenance
proves message existence and location, not that a person authored it.

Extend the existing batched header reader with an explicit evidence projection
for ownership, preserving the current scopes 1–5 row shapes. The same FETCH
response already contains MESSAGE-ID, REFERENCES and IN-REPLY-TO. The projection
carries normalized `thread_key`, message ID, mailbox/profile identity, selected
folder and Sent provenance, From/To/Cc and message timestamp. It must retain
provenance before merging directions; a row labelled `in` is not Sent evidence.
Reuse `_fetch_headers` and the shared mailbox/session/failure handling. Do not
create another per-message reader or infer Sent provenance from All Mail.

The self-owner skip remains fixed for address-based fan-outs. Detecting a
colleague's answer to a customer asks the colleague mailbox about that customer,
not about its own owner. An identity-only query never bypasses the skip. Use the
existing multi-address batching where appropriate; no extra body fetch is needed
for a header join. Engine classification may require already-synced message data
and must return UNKNOWN when unavailable.

`cs.thread_key.thread_key` uses the first References ID, else In-Reply-To, else
Message-ID, normalizing folding and one transport escaping. Missing/ambiguous
IDs, incomplete recipients, unreadable mailbox or uncertain human classification
produce unknown ownership. They never create an assignment or remove a thread
from the operator queue. A timestamp alone cannot join two conversations.
Live same-thread keys between Sent and recipient copies must be accepted on both
maintained clones before detection is released; deterministic fixtures cannot
establish Gmail threading equivalence for all real messages.

## Identity, authority and concurrent transitions

Resolve mailbox to an explicit verified human identity within the authenticated
company. Email display text is not identity. Aliases may map to one person only
through an engine-owned membership mapping; unmapped/shared mailboxes remain
unknown. A caller must never assign an external sender or a person in another
company. Profile authorization remains separate from human assignment.

The proposed engine transition accepts company/thread identity, assignee,
source message ID/provenance, expected assignment revision and a stable operation
ID. The engine validates membership and source authority, deduplicates replay,
and atomically records the revision plus audit event. A stale revision returns
a conflict and current authoritative state. Human reassignment or closure wins
over delayed detection; replay never silently recreates/reopens its old task.
Two different human answers are competing evidence, not permission to overwrite
the first assignee by arrival order. Surface the conflict for human resolution.

Separate the assignment's active/closed state from the customer's latest inbound
watermark. A later inbound in the same still-active assigned thread stays the
assignee's work and appears in the human queue. Inbound after assignment/task
closure returns the thread to the operator pending new authoritative assignment;
it does not revive closed ownership from an old Sent message. A different thread
from the same address is independent.

## Lifecycle and rendering

| State | Operator worklist and triage | Review and dossier |
|---|---|---|
| No assignment or answer candidate; complete evidence | Normal engine judgement | Normal open work |
| Verified human-answer candidate; assignment approval pending | Hold automatic replies for this thread; retain visible work in the needs-assignment queue | Show answering human, source message and “assignment unconfirmed”; require the human assignment action |
| Active verified assignment by answer | Remove only this thread from automatic reply work; show it in the human-owned queue | Name assignee, thread and source answer |
| Live human escalation only | Preserve current escalation semantics | Show named takeover as an assertion, not detected evidence |
| Assignment and escalation agree | Render once, with both reasons | Show both provenance records |
| Assignment and escalation disagree | Hold automatic action; surface conflict | Show both names and request resolution |
| Ownership evidence unreadable/unknown | Keep visible; refuse actions that require clear ownership | UNKNOWN with named failed source, never “unassigned” |
| Assignment closed, including acknowledged handled supersession; no later inbound | Engine's closed/resolved judgement applies | Retain close actor/reason/revision and source evidence |
| Later inbound after close | Return to operator queue pending engine judgement | Explain reopened work, retain prior closed ownership |
| Human reassignment | Follow latest committed engine revision | Show new owner and audit; stale detector cannot undo it |

A verified answer candidate is a read-derived, provisional state, not a stored
assignment and not proof that the assignee accepted work. The engine's confirmed
human-reply judgement may satisfy ANSWERED for the relevant message watermark,
but the thread stays visible in a needs-assignment queue until the human approves
assignment or explicitly resolves the candidate. No automatic reply is prepared
or sent while this candidate needs resolution. Review and dossier distinguish
“answered by X; assignment unconfirmed” from active ownership. Missing membership,
classification or source evidence is UNKNOWN rather than a verified candidate.
Later inbound remains visible in that queue and must never be silently dismissed
by the earlier answer. These are proposed scope-6 rules, not behavior added by
the bounded-reader correction.

An ownership task's human closure ends the assignment. A business thread closure
also closes its assignment through the engine's audited transition; closing an
unrelated ordinary task does not. A dated `handled` record alone never
changes engine assignment. In the proposed interactive workflow, the named human
gesture also requests a revision-checked engine closure of the specifically
covered assignment(s), citing the handled record ID and cutoff. Only an
acknowledged engine transition ends ownership: the resulting assignment state is
closed-by-handled, removed from active human work and retained with its assignee,
source and closure audit. It does not claim a human reply. If the transition
fails/conflicts, ownership remains active or UNKNOWN as reported by the engine;
review/dossier show “handled recorded; assignment closure unconfirmed” and hold
automatic replies while the human resolves it. The local record is never proof
of an engine close.

Inbound newer than the handled cutoff and assignment-close watermark reopens
operator work, not the old assignment. Review/dossier show prior handled closure
and new inbound; unanswered/triage apply engine judgement to the new work. Only
a fresh later answer or explicit new assignment can transfer it again. A broad
handled record cannot suppress a newer human-owned thread; the engine transition
must name covered thread IDs and refuse stale revision/watermark coverage.

`cs unanswered` distinguishes our automatic work, human-owned work and unknown
ownership. `cs review` lists assigned work separately rather than dropping it
from every queue. Triage's ANSWERED rule requires actual engine reply judgement;
assignment is its own stop condition and is never fabricated from address-wide
history. Dossier groups by thread and shows his-by-answer, his-by-escalation or
both; address-level escalation remains labelled as such. Unknown evidence cannot
render a definitive takeover or absence. The exact machine-readable result
contract must expose completeness and provenance alongside those states.

## Read/write posture

| Surface | Detect/read evidence | Write ownership | Existing human gestures |
|---|---|---|---|
| Interactive operator | Allowed within company/profile read authority | Only a human-approved proposed transition through the new engine contract | Named handled/escalated gestures retain current authority |
| Scheduled draft-only tick | Read and report candidate/unknown states | Denied in this proposal, including generic/raw RPC aliases | handled/escalated remain denied |
| Engine scheduled analysis | Read under engine source authority | No new authority implied; requires separately approved engine policy | Cannot impersonate a human gesture |
| Desktop human action | Read own authorized company/thread state | Future explicit assignment/reassignment/close UI with revision check | Actual human action recorded as human |

The current cron wrapper denies handled/escalated in six spellings but does not
enumerate `tasks.create` as denied. That absence grants no ownership authority.
The future assignment API needs server-side policy enforcement and a named
headless-denied kernel surface/raw RPC enumeration. Literal shell deny lists
alone are not a sandbox. Until that policy exists, a draft-only tick may only
report candidates; it must not create an ordinary task pretending to be an
assignment. An open ordinary escalation task remains permissible under its
existing workflow and must stay visible without asserting human takeover.

## Acceptance before implementation and release

1. Fresh independent design review, then recorded operator mechanism choice.
2. Engine brief/plan and reviews for company membership, assignment persistence,
   atomic revision/idempotence, complete read/error contract and source authority.
3. Kernel reader projection tests prove actual Sent provenance and thread joins,
   missing IDs/recipients/read failure remain UNKNOWN, and scopes 1–5 rows stay
   byte-equivalent. Classification authority stays in the engine.
4. Real engine transport tests prove foreign-company refusal, concurrent human
   changes, replay, conflicting answers, close/later-inbound/handled/reassignment
   transitions, closed audit retrieval and unreadable-query distinction.
5. Actual operator CLI/triage results verify every lifecycle row, with no hidden
   human-owned queue, fabricated escalation or new scheduled mutation authority.
6. Authorized FULL acceptance on both maintained clones proves real Sent and
   recipient thread identities and correct mapped human ownership, without sends.

This design has no migration or runtime effect. Its later engine implementation
must specify additive schema migration and rollback preserving assignment/audit
history; reverting the kernel must never erase engine-owned ownership.


## Selected mechanism — 2026-10-08

The operator selected explicit engine task assignment after independent review.
The Desktop [implementation brief](../../mrcall-desktop/docs/briefs/2026-10-08-explicit-task-assignment.md)
owns implementation intent and authority; its reviewed plan governs source work.
Earlier decision prerequisites remain historical design requirements. This design
is not an as-built contract or proof that assignment is implemented.
