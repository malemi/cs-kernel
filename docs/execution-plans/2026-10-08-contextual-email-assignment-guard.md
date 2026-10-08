---
status: completed
---

# Contextual email assignment guard — local implementation

Approved intent: [brief](../briefs/2026-10-08-contextual-email-assignment-guard.md).
Both repositories' identical approved brief has SHA256
`dbb86ca0f32efe6c2044c6c67f9ae2ae69a79ff8107ea36323ef7f674197be0a`.
Fresh brief APPROVED report/result: persistent fanout recovery evidence,
`generic-chat-assignment/brief-review.txt` and its result JSON.
Implementation waits for fresh plan APPROVED. No release/live operations.

## Dependencies, ownership and baseline

Existing approved Desktop explicit-task-assignment and kernel
engine-task-assignment-consumer brief/plans establish the assignment authority,
CAS, signed mutations, source projection and scoped draft policy. Preserve their
completed historical records. This work intentionally extends enforcement to
unscoped contextual writes and final transport, with explicit enrollment
compatibility rather than requiring root trust for every Desktop account.

One execute worker owns the decided changes in the isolated Desktop and kernel
release worktrees only. Lead owns work trace, gate records, durable documentation
reconciliation and any separately assigned custom MrCall launcher patch. Workers
are not alone: preserve foreign changes and new upstream work; do not edit the
original dirty repositories, clone/runtime state or live host configuration.

M1 owns Desktop engine core:
- `engine/zylch/storage/assigned_task_models.py`, `storage/database.py`,
  `memory/store.py`, `services/project_store.py` only for the additive enrollment
  model, correct company binding and pre-install migration integration.
- New bounded `services/task_assignment_enrollment.py`, source/effect guard
  module(s) and `scripts/server/assignment_enroll.py` or similarly named
  standalone maintenance entry point; reuse existing trust/identity/evidence.
- `services/task_assignment_draft_policy.py`, `task_assignment_store.py`,
  `task_assignment_join.py`; narrow `memory/join.py`, `join_import.py` and
  `join_recover.py` hooks required to retain enrollment and provenance.
- `storage/storage.py` actual draft create/update and immutable reply binding;
  `email/imap_client.py` final IMAP-compatible SMTP send/send_message boundary;
  `tools/gmail_tools.py`, `services/command_handlers.py`, `solve_tools.py` and
  `agents/task_orchestrator_agent.py` narrow effect-context/transport hooks.
- Focused assignment/migration/join and write/transport regression fixtures.

M2 owns caller integration, only after fresh M1 integration APPROVED:
- Desktop `rpc/methods.py`, `services/chat_service.py`, relevant
  `services/task_executor.py` and task-context routing to preserve exact binding.
- Kernel `cs/rpc.py`, `cs/cli.py`, contextual campaign draft/send callers only
  where an existing source/thread is already known; no first-contact bulk change.
- Engine RPC inventory/capability fixtures and kernel CLI/transport tests.
- Required shared templates/help for exact caller contract. Clone-specific
  launcher work is an explicit separate ownership handoff; never copy company
  behavior into shared kernel or modify the dirty clone implicitly.

Baseline before source edits: candidate engine, using original engine venv
executable with candidate working directory, passed 57 tests/187 warnings in
33.09s, exit 0: assignment draft-policy, send-draft double-send, send-draft
approval and create-draft idempotency. Raw `generic-chat-assignment/baseline.log`;
`baseline-imports.txt` verifies executable and candidate zylch import path.
The old passing draft-policy case explicitly permits the unscoped assigned-thread
write; preserve that baseline fact and change its expected behavior deliberately.

All subsequent test invocations set candidate cwd/PYTHONPATH explicitly and record
resolved package paths. Kernel checks likewise import candidate `cs`, not the
installed released clone package. Preserve original failed outputs as well as
successful corrected checks; no external providers or paid model calls in tests.

## M1 — Durable applicability and authoritative email effects

### Enrollment and migration

Install one schema/versioned company enrollment record keyed to immutable
ProjectSpace: `never-enabled`, `managed`, `legacy-unknown`, plus classification
provenance/audit. Managed is irreversible through application/maintenance APIs.

Under the existing memory migration file lock, capture and durably record the
pre-install classification BEFORE generic create_all adds assignment tables.
Fresh new ProjectSpace plus never-enabled marker must be atomic; a provably
pre-assignment complete schema may be classified never-enabled. Previously
present complete assignment schema with no marker/trust/history is ambiguous,
not never-enabled. Partial schema or failed inspection refuses contextual effects.
Valid root trust or any retained task/event/receipt makes managed. Preserve the
pre-install evidence across interrupted migration and restart; never let newly
created tables change a previously recorded classification. Validate marker
space/schema on every admission; missing/unreadable state is unavailable.

Root-owned standalone enrollment verifies exact store/space, obtains the company
writer lock and durably latches managed BEFORE publishing trust. Failed trust
installation leaves managed/blocked. Existing valid-trust deployments migrate
managed before serving. Assignment APIs require managed enrollment; tenant calls
cannot activate authority. Unexpected valid trust may conservatively latch
managed under the same writer lock. Never-enabled compatibility requires complete
readable enrollment, not missing trust or empty tables. Revocation never clears
marker/history. Retain safe permission/path checks; no live files are installed.

Document the offline one-time legacy classification procedure: explicit trusted
historical attestation, local data-owner authority for genuinely local store or
independent privileged operator for hosted store, exact company/store lock,
complete empty assignment schema, completely inspected absent trust, retained
audit. A definitive ENOENT after safe complete parent/path inspection is absence
for this offline procedure; malformed/unreadable files, unsafe paths, permission
failures and other IO errors refuse classification. Missing trust alone still
never establishes never-enabled: explicit trusted historical attestation is
required. Valid trust instead classifies managed; all six currently hosted engines
have valid public trust and migrate managed automatically. It can classify legacy-unknown only; no managed downgrade/history erasure,
no RPC/chat approval or hosted tenant command. Fixtures prove hosted tenant cannot
invoke any new maintenance surface. If implemented as a CLI, authority checks
must derive hosted/local binding from trusted configuration and filesystem
ownership, never a caller's local/hosted boolean. A documented direct trusted
maintenance procedure is acceptable without inventing a signing protocol.

### Reply binding and write guard

Factor reusable resolution/admission from existing scoped policy. Derive exact
RFC root/target from owner-scoped original stored message and validated reply
headers; all provided source/task/thread identifiers must agree. Reject malformed,
foreign-owner, missing or ambiguous source. A known contextual source cannot be
made standalone by stripping tool headers. Draft update retains established
source binding and refuses a change that alters/erases it; approval card edits
cannot widen authority. Existing reply-bearing drafts receive fresh resolution
at send, including drafts predating the assignment or this migration.

A genuinely source-free standalone message has neither RFC reply headers nor
known bound task/source context; preserve its current approval behavior. Do not
classify prose as human intent or suppress unrelated threads by recipient.
Managed replies require complete projection and accepted exact current inbound
identity. Assigned/pending/conflict/unknown/closed coverage holds the effect;
later-inbound admits only actual uncovered target identity. Never-enabled replies
skip root-trust/provider-assignment checks but still validate known source binding
and serialize final compatibility admission with activation.

Prepare provider evidence outside the company writer lock. Inside the lock,
recheck enrollment, actor/profile/company binding, current membership for managed
companies, join fence and assignment row/CAS, then execute the private draft
write or bounded irreversible provider handoff. Keep the company lock through
provider acceptance; no model, search or evidence scan inside it. Lock acquisition
is consistently company then private storage for these effects. Avoid reentering
separate company write transactions in nested send wrappers: one scoped effect
context owns final lock, admission and binding; nested transport validates/reuses
that exact active admission without opening an unrelated bypass or wrong-thread
scope. Existing SMTP deadlines and truthful uncertain-delivery semantics remain.

### Actual effect inventory and joins

Guard actual `Storage.create_draft` and `update_draft`, then `IMAPClient.send` /
`send_message` final SMTP path. `SendDraftTool.execute` and `/email send` must
carry resolved persisted draft binding through claim, edits and final handoff;
retain the single-send claim lifecycle. Solve `_send_email` and legacy task
orchestrator send entry points carry known source/task context and must not strip
it. Gmail/Outlook imports referenced by legacy branches are absent: guard their
entry point before dispatch, preserve existing unavailability, and make no claim
of live OAuth provider acceptance. No new provider implementation.

Keep current assignment-history/schema join refusals. History-free joins retain
the stricter source/destination enrollment (`managed` > `legacy-unknown` >
`never-enabled`) bound to destination actual immutable space in the existing
write transactions, and retain classification provenance in join audit. Refuse
before cutover when preservation fails. Joined memory capabilities do not grant
membership; destination trust remains independent. Exercise history-free
managed-to-managed and never-enabled joins, unknown propagation and rollback;
no lossless assignment-history migration is introduced.

### M1 verification and review

Meaningful real SQLite fixtures, deterministic mail/provider doubles, no network:
- Old unscoped assigned-thread create regression now refuses with no row change;
  create/update/send for assigned, pending, closed, unknown and revoked authority.
- Fresh/pre-assignment never-enabled replies create/update/send without `/etc`;
  empty-managed missing trust refuses; history/no trust managed; ambiguous/partial
  legacy held; migration interruption/restart and space mismatch cannot downgrade.
- Existing persisted drafts, approval edits, conflicting roots, owner isolation,
  old-target versus later-inbound, unrelated same-sender and standalone compose.
- Two real database connections/threads coordinate assignment-vs-insert and
  assignment-vs-provider-handoff. Assignment first means zero transport calls;
  transport first holds competing assignment until acceptance. Equivalent real
  enrollment race covers never-enabled compatibility. Failed enrollment stays
  blocked. Failed/uncertain provider calls preserve nonduplicating claim behavior.
- Actual tool, slash, solve and IMAP adapter routes hit guard; unavailable OAuth
  branches are guarded/unavailable, not presented as successful provider tests.
- History-free join classification/provenance retention and injected failure
  rollback; retained assignment history continues to refuse before mutation.

Run the focused tests above plus complete engine assignment suite, relevant
memory join/migration regressions, existing approval/read-only/idempotency/double-
send suites, ordinary task and Qonto privacy/transport regressions. Freeze owned
source/import paths and raw command/exit evidence. Fresh M1 integration reviewer
must APPROVE actual changes/tests before M2 caller implementation.

## M2 — Explicit caller binding and complete integration

Expose a strengthened contextual-email policy capability without claiming old
assignment_draft_policy=1 covers final sends. Keep old scoped draft behavior
compatible at least as strict; negotiate the new capability for changed kernel
contextual workflows and reject unavailable/older support before model dispatch
or write. Version and field names follow reviewed M1 implementation; refresh
IPC inventory from actual signature rather than hand-inventing transport claims.

Carry source/thread from caller-known original messages, exact draft rows and
ordinary task source context through chat, direct send and task solving. Generic
chat with no known source remains usable for read-only/standalone work; known
context cannot be discarded on command/semantic routing, deferred executor or
thread hop. Caller-supplied identity/human/approval flags never relax the central
write/transport guard. `cs chat --allow send_draft` still grants only tool effect
permission; send is separately held by the current authoritative thread state.

Audit kernel contextual campaign compose/send and exact-draft send: bind existing
thread/source explicitly; leave fixed-template first-contact/bulk outside engine
contextual reply scope. Identify the custom MrCall `ext/cs_operator_send_cron.sh`
invocation/skill contract to update through a separately owned clone patch if
necessary. Record that obligation and test the equivalent real kernel transport
payload offline; do not say the live custom launcher is changed when it is not.

Verify deterministic actual generic `chat.send` dispatcher → ChatService → real
create/update/send tools, through mocked agent reasoning and fake final SMTP.
Exercise omitted old optional scope, allow approvals, stale previously composed
draft and task-context metadata stripping. Add kernel CLI→fake authenticated
engine transport fixtures for strengthened negotiation and exact binding; old
engines fail closed before writes. Record raw payloads and state unchanged on
refusal. No customer sends or paid ticks.

Run engine focused integrated suites, kernel relevant CLI/consumer/send/draft/
permission/template tests, then kernel `bash tests/run.sh` including installed-
package checks with explicitly candidate package paths. If shared canonical
skills change, execute real required three-host native fixtures with full reads
and retained product-state proof; if none change, do not invent native execution.
Fresh M2 integration reviewer checks both repositories and any separately owned
caller patch before documentation/final closure.

## Documentation, final check and rollback

Lead reconciles task-assignment availability/enrollment/provisioning/revocation,
legacy migration, source binding and hold contract; task-management contextual
routes; IPC capability/parameter inventory; kernel task-assignment and CLI help;
root routing only where affected. Update living snapshots with verbatim archives.
State source-free semantic limit, absent OAuth, current local-only verification
and unchanged live released versions. Do not edit old approved plans or claim
new host activation/clone upgrade.

Use doc-end for each affected repository: held startup, impact/reconciliation,
actual mechanical/keyword checks, explicit fresh doc-critic including unchanged
contracts and active-context shape, focused real-user dispatch check, then a
separate fresh final review over exact final source/docs/evidence. Finalize
completion/baseline and plan status only when actual checker requirements pass.

Rollback owned source hunks only; retain enrollment/assignment tables and audit,
private draft history and sent/uncertain outcomes. Managed enrollment never
becomes never-enabled. An older build reintroduces the known unscoped reply gap
and cannot safely activate authority or join managed stores; document that risk.
No tag, push, installer, paid model, live provider/customer send, real assignment,
trust installation, live store join or clone/runtime mutation belongs to this
local-development workstream. New release/production activation requires separate
authorization after verified local completion.

## Local delivery evidence and gate disposition

Evidence root: `/home/mal/.local/state/codex-evidence/fanout-recovery-20261008/generic-chat-assignment/`.
The approved brief and plan copies, original rejected reports and actual command
outputs remain there; they are not reconstructed from the final prose.

- Brief and plan framing: APPROVED before implementation. The current plan
  retains that scope; these notes record results rather than change acceptance.
- M1 core: APPROVED after independent repair review. Stale standalone snapshots
  cannot clear a new binding or send a newly bound draft. Real private writer
  reservations and current-row/claim checks cover both cases. IMAP, sync and
  mailbox-probe fresh-process imports pass after the circular import repair.
  Exact final M1 source manifest: `m1-source-freeze-attempt3.json` (28 paths);
  worker result: `m1-result-attempt3.json`. Independent 23-case import/race
  output: `m1-review-attempt3-focused.log`; actual verdict retained in
  `m1-repair-review-approved.txt` and `m1-repair-review-result-approved.json`.
  The earlier REVISE reports and bypass demonstrations remain separate evidence.
- M2 caller integration: APPROVED after the contextual campaign queue repair.
  `m2-review-approved.txt` / `.json` retain the complete independent verdict;
  `m2-source-freeze-attempt2.json` binds 35 Desktop and 10 kernel paths plus
  the concrete launcher artifact. Independent authenticated CLI: 10 tests;
  independent real-SQLite held-assignment queue: 1 test, zero provider APPENDs
  and zero dossier updates. The initial real bypass and REVISE remain retained.
- Final combined engine verification: 443 passed / 859 warnings in 402.64s,
  `m2-engine-integration-final.log`. All 35 Desktop hashes remain identical
  after the kernel-only repair. Kernel `bash tests/run.sh` on the repaired
  installed candidate: exit 0, all 61 gates green,
  `m2-kernel-full-attempt2.log`. Actual RPC inventory/negative proof passes.
  A broader 771-test run began before final narrow refinements and remains
  auxiliary evidence, not proof of the final frozen source.
- Worker commands/results: `m2-worker-result-attempt2.json` and
  `m2-worker-check-commands-attempt2.json`. A lead filename collision overwrote
  the first worker result envelope with the reviewer envelope; raw command logs,
  checks, imports, approved artifacts and source freeze were unaffected. The
  restored `m2-worker-result-attempt1.json` explicitly discloses reconstruction
  from actual logs; no unchanged-original-bytes or new-run claim is made.
  Reviewer records now use distinct producer-specific names.
- Documentation/final closure is tracked by each repository's persisted
  completion record `contextual-email-assignment-guard-20261008`. Its current
  receipts, independent critic/final verdicts and checker finalization govern
  closure; passing implementation tests alone do not establish completion.

The separately owned MrCall launcher candidate is an artifact under
`clone-caller-candidate/mrcall-cs/ext/cs_operator_send_cron.sh`, with
`clone-caller.patch` and `clone-caller-result.json`. Only its contextual-reply
briefing changes; source binding is mandatory even where the clone-local skill
example omits it. The original launcher, credential code, permissions, denial
sets, markers, budgets and schedule remain unchanged. The artifact is not
installed or executed. Shared canonical skills remain unchanged, so this
workstream claims no new three-host native skill execution.

Published Desktop `v0.1.56`, kernel `v0.51.0`, installed clone pins and hosted
runtime pins retain their released behavior. There is no release, live migration,
trust installation, assignment mutation, customer send, paid tick or company join
in this workstream. Source-free prose is not semantically classified as reply
intent. Legacy absent OAuth modules remain unavailable. Production activation,
clone adoption and the caller-patch installation require separate authorization.

### Retained external review-copy boundary

The serialized effect inventory covers actual engine private draft writes and
final enabled SMTP handoff. The existing kernel `cs draft-reply` Gmail review
append retains its compatibility contract: it checks current projection, then
appends outside engine/company locks. It is not an atomic assignment-guarded
external provider write. Manual Gmail edits/sends and other clients are also
outside engine enforcement. The new contextual campaign queue append is refused;
its old-draft-after-assignment repro is retained as an M2 REVISE case. Durable
engine/kernel/IPC contracts state this boundary without certifying a global lock
on mailbox credentials. This note does not waive required engine admission,
source propagation, final-send, enrollment or race acceptance.
