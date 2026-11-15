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
already composed drafts. The stronger engine feature is excluded from public
`v0.52.0` and hosted engine pins. The old `assignment_draft_policy: 1` capability
proves only its scoped draft contract and cannot certify stronger final-send enforcement.
The [compatible caller repair](execution-plans/2026-10-13-released-email-caller-compatibility.md)
restores the released ordinary chat, exact-thread draft and exact-ID send contract
without activating persistent enrollment or advertising contextual policy v1.

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

Explicit contextual bindings require `system.capabilities.contextual_email_policy: 1`
and unavailable support refuses before generation. This applies to the new chat
context flags, scheduled `draft-reply --source-id`, and direct RPC
contextual/required-policy requests. Interactive review preparation has its
separate locally validated contract below. A failed bound request is never
retried as an unbound operation.

Ordinary generic chat retains its released approval contract. Scheduled
`draft-reply` with only its exact thread requires `assignment_draft_policy: 1`
and sends the original assignment scope/version. Ordinary `draft-send FULL_ID` requires current assignment
admission, approves exactly one matching send and verifies the exact Sent row;
it does not assert stronger contextual-policy enforcement on older engines.

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
Explicit bindings are carried as `chat.send.email_context` with
`contextual_email_policy_version: 1`. Ordinary exact-ID sending retains its separate
released full-ID approval and Sent verification contract.

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

The scheduled `cs draft-reply` Gmail review-copy behavior remains compatible.
It checks current assignment projection immediately before append, but the
append is outside the engine/company lock and has no atomic assignment guarantee.
Manual Gmail edits/sends and other external mailbox clients are outside engine
enforcement. The strengthened capability certifies actual engine private draft
writes and final transport, not a global lock on mailbox credentials or clients.

## Interactive review preparation

An explicit interactive `draft-reply` request prepares a review draft even when
assignment or takeover evidence holds sending. The command selects its route
before composition: engines advertising the supervised-review contract retain
that path; supported legacy engines use their existing generic interactive chat
for draft composition, with all send approvals denied. The legacy route provides
source/recipient/header validation before a Gmail review copy, not a claim of
newer engine-enforced source scope. Missing or ambiguous originals and invalid
returned drafts refuse. Failed generation is never replayed through another route.

Source corroboration inventories recent All Mail headers across participants,
starting one day before the earlier of the selected source Date and current UTC
time. The window permits at most 1,000 headers with exact batched UID coverage;
normalized RFC-root filtering precedes at most 100 full message reads. Gmail's
References search is not completeness evidence. Provider UID arrival order,
known direction/date and matching source content establish the selected original.
Incomplete search, fetch, header or draft-label evidence refuses.

The selected plain body must match the engine source. Complete additional raw
plain/HTML representations reach the engine as untrusted source material;
presentation differences alone do not discard material or prevent preparation.
Incomplete decoding, clipping or more than 65,536 retained source characters
refuses before generation. An unrelated message's body defect cannot invalidate
complete source inventory. One narrow quoted-envelope form accepts a repeated
known address as its unquoted display name; it does not relax actual From-header
validation or omit the provider's quoted tail.

Interactive preparation publishes the Gmail review copy only through the
engine's exact publication operation (`exact_draft_publication: 1`). Without
that capability the draft stays engine-saved, the outcome says so, and no local
copy is appended. `cs draft-reply --resume-draft FULL_ID --thread-id ROOT`
publishes an existing saved draft without generating another one.

A prepared review draft does not clear an assignment or authorize sending.
Ordinary `draft-send FULL_ID` keeps its exact-ID and current-assignment admission
checks. `draft-send FULL_ID --operator-request` is the interactive operator's
explicit request to send one existing draft through the engine's exact send
operation (`interactive_exact_send: 1`). It admits only a positively identified
manual-member-activity hold on the exact root and current target; other holds,
pause, SELF recipients and suppression still refuse, and scheduled sessions
refuse the flag.
Scheduled callers retain scoped assignment negotiation and workset restrictions.
This local candidate's actual source and hosted checks are recorded in the
[continuity plan](execution-plans/2026-10-22-interactive-draft-continuity.md).

## Scheduled reply origin — local candidate

The [scheduled provenance repair](execution-plans/2026-10-13-scheduled-reply-provenance.md)
negotiates `operator_reply_provenance: 1` independently of contextual policy.
It carries authenticated caller automation intent only for the existing scheduled
send marker plus actual send-tool authorization. Intent is not permission or
proof of human ownership. The opted-in engine route must check existing complete
assignment authority and exact owner, original root and reply target immediately
before SMTP. Assigned, pending, conflicting or UNKNOWN inputs remain held.
This origin-specific final gate is new; generic released approval alone does not
supply it. It does not activate the separate enrollment/contextual-policy rollout.

Normal projections use `current_message_ids` for exact current inbound identity;
`current_inbound` carries a closed task's digested snapshot and can be empty in a
complete normal projection. The kernel preserves both fields without inventing
identity or treating an incomplete reply observation as absence. Actual automatic
reply headers distinguish a new automated delivery from a potential human answer;
caller prose and local Sent storage alone cannot establish that fact. Source
checks pass, both reviewed ACTOR engines are active and both ordinary clone
packages contain the approved caller. Historical signed R9 certifies only its retained hosted candidate. The reviewed
scheduling repair is installed; current ordinary acceptance belongs to the
[recovery plan](execution-plans/2026-10-15-ordinary-assignment-recovery.md). Historical failed cases retain their failed status.

## Current authority after incomplete discovery

The source-approved ordinary workflow treats discovery authority as a snapshot.
A held UNKNOWN row remains visible until the existing once-only exact-thread
status read returns new current peer-merged authority. Only the same authenticated
actor/source owner/company/root with the exact original RFC identity in
`current_message_ids`, typed complete normal state and no hold can supersede that
older incomplete observation. Preserve both observations in the report.

Candidate, active, conflicting and closed-coverage holds are not transient UNKNOWN
recovery; current incomplete/UNKNOWN or wrong identity still refuses. Address
human takeover, unreadable mailbox, suppression, applicable dossier STOP and dedup
retain their independent force. Actual source bodies and current effect-time
assignment guards remain required. This adds no RPC retry, permission or assignment
mutation. Complete consecutive discovery inspection must reach EOF before
eligibility decisions; software checks do not prove native model inspection.

The [M4 plan](execution-plans/2026-10-13-scheduled-reply-provenance.md) owns the
source approval, shared canonical insertion, new package adoption and fresh FULL.
Historical R6 remains FAILED; signed historical R9 acceptance belongs to its
retained candidate, as recorded below.

## Incomplete exact-message human observations

The reviewed legacy-Sent consumer recognizes only the paired engine extension
`authority_complete: false` and `hold_scope: exact_observed_message` on the exact
held observation. This is incomplete component authority, not task absence.
Malformed or contradictory flags refuse. Component canonicalization and a closed
creator read cannot promote it to complete NORMAL or closed coverage; existing
tasks and independently failed peers keep their own held disposition. The source
is implemented and installed on both maintained clones. Healthy current ordinary
acceptance remains unmet in the recovery plan.

## Incomplete structural ancestry conflicts

The exact typed `RFC_ANCESTRY_CONFLICT` observation is incomplete, human-held
conflict work, not complete task absence. It requires `state=conflict`,
`complete=false`, `hold_auto_reply=true`, no task or reply/coverage evidence,
a singleton requested component and matching actor/source owner; component scope
is explicitly unavailable. The consumer and deterministic health classifier
share the same strict shape predicate. Malformed shapes and other failures
remain technical UNKNOWN. The discovery CLI may still exit 3 for held work;
recognizing this human hold never authorizes automatic drafting, assignment or
closure. Explicit interactive review preparation follows its separate contract.

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

`cs draft-reply` requires exact `--thread-id` before composition. Scheduled
composition negotiates engine assignment scope before a draft write; a
post-compose check alone cannot establish that engine boundary. An older engine
without the required policy cannot compose the scheduled scoped workflow.
Interactive review preparation instead selects the contract documented above
before generation. Existing send authorization remains separate from assignment
status.

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

The [ordinary assignment recovery](execution-plans/2026-10-15-ordinary-assignment-recovery.md)
implementation prioritizes useful inbound work using the existing engine
classification, then newest receipt first. Each authenticated actor admits one
active projection RPC; other actors advance independently. At most four reads
run globally, including reserved timed-out work. Required canonical observations
retain their originating root's priority before later historical roots.

Assignment projection has a 120-second engine deadline and 150-second caller
limit. Bulk projection explicitly selects 150-second requests and 180-second
isolated batches, with a standalone shared ceiling of 3600 seconds including
authentication and cleanup. An inherited caller deadline can be shorter; these
limits do not grant a fresh projection budget inside review or discovery. Supervised reads permit these higher finite caps only for opted-in
`tasks.assignment.project`; defaults and other allowed methods remain 60/90
seconds. Blocked authentication or DNS cannot outlive the supervised boundary.
A timed-out lane retains its physical reservation for the rest of the run;
undispatched or unavailable scopes remain explicitly incomplete and held.
Only batch discovery permits one fresh read per authenticated actor and exact
thread key after a completed, fully validated SOURCE_UNAVAILABLE response.
Original and canonical observations share that retry budget and the original
global deadline. Transport failures, invalid responses and other holds do not
retry. Final guards and mutations retain their separate authority. No
cross-request authority cache or arbitrary queue-coverage guarantee is added.
The recovery plan owns exact source, installed adoption and ordinary acceptance.

The installed shared-time correction gives review 2700 seconds of
work and scheduled discovery a 2700-second sweep inside 2710 seconds observation.
These finite allowances use partial workload extrapolation and headroom, not a
coverage guarantee; actual installed state belongs to the living context.
Required peer observations and timed-out reservations remain mandatory.

Thread-key handling decodes complete bounded MIME-encoded identity
headers before References tokenization. A valid multi-word encoding must produce
complete RFC identities; ordinary/HTML-supported identities and multi-ID order
remain intact. Malformed/partial/unknown-charset encodings cannot borrow an
unrelated Message-ID. Missing-root drafts remain visible and explicitly held by
the workset consumer. Lossless header recovery does not establish engine binding
or override owner, source, assignment or exact-send guards.

Optional engine component metadata binds the requested anchor to its authoritative
thread key and authenticated local component. Stored task keys remain unchanged.
An empty peer mailbox does not establish an alternative component; canonical
fallback retains original conflicts and all applicable holds. Multiple existing
tasks, malformed metadata or unavailable required peers remain held. Old engines
without the extension retain exact-root validation. Source and installed identity
checks pass. The reviewed scheduling repair is installed; fresh ordinary
acceptance remains a separate requirement in the recovery plan. Earlier
R9 acceptance below certifies its retained candidate only.

Protocol version 1 and configured peer identity/company are checked explicitly.
Unavailable methods, malformed responses and unreadable source are unknown;
no fallback turns them into successful absence. The delivery plan retains
canonical workflow and scheduled-wrapper verification.
Offline fixtures alone do not establish live mailbox parity or latency.
Separately authorized release acceptance must verify scoped current FULL on both
clones, real provider reads, root key permissions, exact hosted bindings and
reproducible clone locks. The canonical release plan records its current result;
retained R9 acceptance below certifies only that frozen hosted candidate.
General customer workloads, real assignment mutations, installed Desktop GUI
behavior and public installer acceptance require their separate evidence.

## Historical hosted development acceptance

Genuine r9 (`ecc64a8400e35d6f699a9c193ba5e399`) passes the unchanged strict
seven-check matrix on the actual installed kernel `9857f1bb…` and repaired
six engine runtimes. MrCall sends the correct 212 reply; Café creates exact
engine draft `71589012-ba68-4e7d-8e31-f45df722c349` with result311 and one
provider mirror without sending. Both operators terminate naturally with exit0.
Signup's documented policy passes with legacy exit1, not three zero exits.
The new Sent source is complete AUTOMATIC, root authority complete NORMAL/unheld,
and the actually received reply is classified automatic with no additional
received/sent/provider-draft/engine-draft effects. No manual intake or substituted
model output supplies native generation. Cleanup restores exact cron759ab3,
removes owned enrollments/markers/processes and preserves six runtimes plus Qonto.

The original signed result and complete pre/post1053-object tested source are
retained before documentation edits at `/home/mal/.local/share/mrcall-operational-evidence/2026-10-14/after-repair-full-checkpoint-guard-r9`. Retention manifest SHA-256:
`0701b581b092c6c0360d159dc36cedd3bbe949e33e6ec5c9b229b11ce08b8482`.
This is `development_hosted` acceptance; public installer/release and native
Gmail browser/mobile/API edit/send preservation remain unverified. Automatic
reconciliation remains off. Earlier failed runs stay failed and unsigned.
Operational acceptance remains separate from checker-governed documentation
completion and public release.
Independent operational APPROVED: `/tmp/mrcall-ai-kit/r9-acceptance-verification/report.md`,
SHA-256 `7de3884807f781e8a0aa5391113c6652ba059f378d6fe764a3aee124492435bc`.
Actual native inspection covers both complete physical receipts through EOF.
