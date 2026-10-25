# Proposed brief: canonical roots for email-backed task serialization

PRIVATE PROPOSAL ONLY. No implementation, database write, RPC/provider/model call, deployment or paid case is authorized. C31 remains FAILED; preserve its partial MrCall/signup successes and qualified cleanup, including the first failed source check and retained/removed pycache evidence.

## Scope decision

This is an engine/public task-output contract change, not a nullable codec or EOF repair. It needs a fresh scoped brief and plan review. Root may attach the reviewed amendment to the existing ordinary-assignment recovery engine task if its approved intent supports this boundary, explicitly declaring the added ownership; do not reset records or silently enlarge the context/EOF tasks. This proposal creates no task IDs. The independent nullable-source proposal remains a separate required dependency.

## Evidence and limits

C31 tasks.list retained internal email/blob UUIDs but no RFC root; the protected original retained its RFC identity but no bridge to those UUIDs. cmd_tasks preserves the RPC response and _root correctly refuses the missing data. Text/contact/subject/nonce matching cannot repair it.

Actual deployed-file comparison is retained in `c31-task-root-deployed-source-comparison.private.json`. For both Café and MrCall, the entire task_creation.py and public_task serializer file match A and Main; relevant tasks_list/get_task_items/get_email_by_supabase_id function/decorator slices also match both. Some whole RPC/storage files differ due other code. Assignment authority/store and mail-component files match A; Main differs. Relevant deployed source mtimes precede the same verified running process starts. This establishes the current serialization seam and current writer omission, not which historical writer created this exact task. Excluded profile lacks assignment service files; absence is preserved, not treated as equality.

## Minimal result

At the ordinary email-task serialization boundary, expose additive top-level thread_key only when the authenticated owner's complete internal-email sources resolve to exactly one canonical RFC conversation root. Perform read-time enrichment so existing legacy rows and future rows benefit without database backfill, migration or creator persistence. No task_creation change is needed for the minimal repair.

Resolve sources.emails and email event_id as internal Email primary keys, under the existing authenticated profile/owner key. Never equate mailbox address with UID, accept a caller-supplied owner, use a blob/contact/text match, or assume Message-ID/thread_id is already the canonical root. Reuse the deployed-matched bounded RFC component/assignment canonicalization with its conflict and actor/space checks; do not copy unrelated Main changes. Confirm that chosen resolution path is DB-only/read-only. Blob-only/calendar/non-email rows remain unchanged and held when no exact email mapping exists.

All relevant source IDs must resolve completely in the correct scope and converge to one component/root. Missing rows, malformed IDs, unavailable/conflicting ancestry, multiple components, cross-owner/profile sources, or conflicting preexisting root fields leave the task without an admitted new root. Preserve original source arrays and task facts. A resolved root is inventory identity, never assignment permission or authority to compose/send.

Keep tasks.list ordering, filters, limits, task creation, public_task/Qonto visibility, kernel _root, workset two-root fairness and all holds/action guards. No fixture/reference/nonce priority or special case. Free regressions must establish generic candidate membership and normal fairness, not promise future fixture selection.

## Acceptance

Free owner-scoped storage/service integration tests demonstrate legacy and fresh email tasks resolving correctly, canonical aliases converging, and every missing/conflicting/cross-owner case staying held. Kernel tests consume the enriched RPC-shaped row unchanged and use existing _root/_inventory, without parser widening or authority grants. Verify exact deployed source identities and narrow rollout preimages before any install; no production DB mutation or unreviewed engine restart follows. Resolve nullable projection too. Only after both repairs have free evidence and independent installed approval may root separately authorize one original business case. No retrospective C31 draft or inspection PASS.

## Fail-closed handling of existing roots

For email-backed tasks, an existing parseable top-level thread_key/thread_id or sources.thread_id must not survive a failed/conflicting canonical-source resolution as usable inventory identity. Preserve persistent rows and their source arrays. If canonical resolution completes and every existing root agrees, preserve those roots and add the canonical thread_key. If resolution fails or conflicts and any existing root would otherwise be accepted, fail tasks.list with a bounded symbolic error rather than returning that unsafe row or an empty successful list. Unresolved email tasks without an existing admitted root remain unchanged and held. Non-email tasks retain their existing behavior. Tests must exercise each existing-root field, agreeing roots, conflicting roots, unavailable/cross-owner sources with a preexisting root, and zero accepted inventory/effects from every failed case. This explicitly leaves kernel parsing and all persistent data unchanged.

## Explicit actor-family implementation scope

Implement only in A, the deployed-matched actor recovery family used by both operational clones. Main has a different canonical API and remains source-identical; do not port A canonical services, promise Main compatibility or create a Main implementation task for this repair. Both actors may receive the narrowly reviewed A delta, while four peers and excluded Qonto preserve their existing bytes/processes. This scope qualifies the implementation rather than reducing any original workflow, operational, documentation or final closure obligation.

## Existing task date alignment

Free actual Storage.get_task_items -> public_task -> unchanged kernel inventory proves root-only enrichment leaves fresh tasks at date0: the task serializer exposes last_signal_at, while the reader ignores it. In addition to A-only engine resolution, authorize a narrow company-neutral kernel reader change: for tasks only, consume the existing last_signal_at as a fallback after currently recognized dates, falling back to created_at only when that signal is absent. Include these existing fields in stable task revision input. Do not manufacture updated_at/last_inbound_date, change engine timestamp production, use analyzed_at separately, or alter the two-slot fresh/old scheduling algorithm. Preserve original last_signal_at semantics (latest source event, existing analyzed_at/created_at fallback) rather than claim it is always a verified inbound timestamp. Generic fresh-task/backlog fairness must be proved with actual serialized neutral rows and unchanged source dates, including older-thread new-signal revisions, missing/invalid values and all authority holds. This adds one paired kernel task for date consumption, not Main engine implementation; no existing records reset.

## Finite preservation successor and concrete activation

The reviewed new module is an actual resource addition in each actor family. Current operational preservation intentionally rejects every addition, so pins alone cannot truthfully adopt it. Explicitly authorize the minimal A harness compatibility source: operator_operational_common.reboot_preservation gains a separately reviewed finite successor for ONLY the two named actor UIDs and a new exact baseline generation. Actual old current actor packages are the new before inventories; retain all earlier immutable generations and four peer original cases unchanged. Admit only the exact tasks_list-only methods.py postimage and one task_source_roots.py file with exact content/size/type/owner/group/mode. Every other resource or metadata change refuses. No wildcard, rewritten preimage, generic addition permission, effect/authority guard or deadline waiver. Neutral tests cover both actors, old peer cases and hostile extra/missing/changed resources/generations/metadata.

Prepare unreachable complete actor releases and one newly reviewed outer four-lock transaction before live execution. It combines only the two kernel module replacements per clone, exact actor source selection/restart, reviewed consumer adoption and necessary frozen provenance/constants/policy. Preserve all other118 kernel files, source-only Stripe omissions, Support dependency path, configs/policies/modes/budgets, four peer processes/packages, excluded Qonto and protected draft. One20-second forward/30-second absolute deadline covers attributable apply/conditional rollback; no nested flock transactions. Unknown/busy actor work means zero mutation, not termination. Concrete activation review and root authority precede any live source switch/restart. Read-only preparation may inspect scoped systemd/proc/idle state; no model/provider/workflow call or production DB mutation. After actual installation and independent identity proof, one bounded normal-auth tasks.list per actor may be separately authorized to catch real-data/latency defects before any paid case. All original strict operational, documentation and final obligations remain.

## Row-local unresolved task compatibility amendment

The actual authenticated MrCall task read exposes legitimate historical source
shapes that the UUID resolver cannot prove, including RFC values and one malformed
legacy source value. A historical aggregate task may also span distinct email
components. These are row-local observational gaps, not grounds to conceal the
whole task list behind an RPC failure. No historical identifiers are rewritten,
no captured fixture identity becomes a bridge, and no new provider lookup is added.

This amendment supersedes the earlier rule that a failed row resolution with an
existing valid root must fail the whole RPC. Every email-backed returned row gains
`source_root_state` with exactly `resolved` or `unresolved`. Only a complete,
owner-bound single-component resolution agreeing with every existing valid root
may emit resolved and its canonical thread_key. Missing/invalid/unsupported source
IDs, incomplete sources, conflicting roots or multiple components emit unresolved
while preserving all original source arrays and root fields. Unknown source IDs
are not guessed or treated as RFC lookup authority.

The paired kernel must hold every row with explicit unresolved, malformed or
unknown source_root_state before considering any pre-existing root for scheduling.
The typed marker enters task revision identity and the held reason is explicit.
Missing marker retains the existing older-engine compatibility path. Resolved rows
still require normal exact roots and all later authority/effect guards. Complete
inventory remains visible; per-row unresolved state never supplies action authority.
Global identity/membership/project binding failures, database/query/deadline failures
and final binding changes continue to fail the whole RPC through its existing
sanitized error, without partial/empty success. No persistent task data changes.

Acceptance adds isolated valid-old-root/invalid-source and multi-component holds,
marker tamper/unknown controls, unchanged source arrays, continued global failure,
normal source-correlated new rows, then one bounded normal-owner task read per actor
on the repaired candidate before a new paid ordinary case. The failed earlier
MrCall read and all prior failed cases remain immutable; full same-case ordinary
acceptance and all documentation/final closure remain owed.
