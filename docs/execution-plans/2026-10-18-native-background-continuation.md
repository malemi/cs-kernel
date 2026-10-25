---
status: active
---

# Ordered native background continuations

Depends on the freshly approved [brief](../briefs/2026-10-18-native-background-continuation.md).
The retained genuine13-event probe supplies two same-session init records differing
only in UUID, result_index0 then1, and an explicit second-result origin:
kind=task-notification, producer=session-task, runId matching the native Bash task.

## M1 — strict source protocol

Add cs/operator_native_lifecycle.py with a pure continuation(events) validator.
Single-result behavior remains in the existing supervisor. Multiple segments
require immutable init configuration except UUID, one session across all events,
unique UUID/task/run/tool identities, result_index starting0 and increasing by1,
successful typed segment terminals, and genuine native Bash task_started,
task_updated completed and task_notification completed metadata. Every resumed
segment terminal must explicitly name its matching notified task run in origin;
every init after the first needs that ordered callback. Reject duplicate/replayed,
failed, pending, foreign, unknown or unexplained transitions. No prose parsing
or task summary is an authority source. The last segment is terminal, with no
uncompleted task or unmatched callback. Bound processing by existing stream cap.
Return the final terminal only after the entire chain is valid, plus a versioned
proof with counts, exact session ID, completed task/run/tool IDs and event digest.

Lead owns supervisor/discovery integration and the Desktop Actor consumer;
a bounded execute worker owns only the new pure module and its focused test.
Both preserve concurrent changes. Supervisor keeps actual repeated session_ids
and emits proof only for a validated chain. Discovery uses that same validator,
and still rejects any discovery use that itself became a background task.
The Desktop consumer requires the explicit typed proof before accepting repeated
same-session init IDs; other source/process/canonical/full-read checks remain.

Test the actual retained raw stream separately from constructed fixtures. Add
mutations of session/init configuration, callback/task/run/tool IDs, order,
result_index, origin, pending/failed tasks, terminal failure, duplicate events
and unexplained extra results. Existing strict discovery/consumer tests and
normal single-segment behavior must remain valid. Register the focused gate,
run the full kernel suite and affected Actor tests. Preserve failed logs.
Fresh source/milestone review approves exact implementation and evidence.

## M2 — narrow installed composition

After M1 approval, capture both clone-package preimages; apply only reviewed
diagnostic, lifecycle, supervisor and discovery bytes, preserving all other
resources, modes, permissions, company guidance and engines. Independently
compare complete packages and actual imports. Update current candidate-owned
native-producer/package identities using the existing pinned provenance path;
no arbitrary rebaseline, broad tree install or waived expected identity.
Run focused installed checks and obtain fresh integration review before mail.
Lead owns activation/provenance; reviewers inspect, do not mutate runtimes.

## M3 — one actual acceptance and closure

Freeze source, docs, packages and runtime policy; confirm coordinated owners
hold conflicting writes. Execute ONE fresh ordinary case with new originals,
USD4 configuration,45-minute Café allocation and90-minute absolute deadline.
Require all unchanged provider/native/current-authority/ACK/no-extra-effect
checks and full cleanup. Preserve raw stream diagnostics. A failed result stays
FAILED and unsigned; no automatic retry or resealing. Reconcile documentation,
invoke doc-critic, obtain separate final review and checker-governed closure.
Publication and native Gmail UI remain outside this authorization.

Rollback restores only owned bytes against exact current preimages, preserving
other sessions and failed evidence. No parser rollback may relabel a past case.
Source/check delivery is bounded to45minutes; the actual case retains its normal
execution budget and cannot be rushed to meet that engineering estimate.

## Current retained outcome

M1 source and M2 actual activation reviews approved the installed composition.
The one M3 case is V18, run `0b8ac4c23a5e9fdb9173e989ab3815e5`, and remains
FAILED and unsigned. Candidate SHA71a680b7987676e5b6ec2e1edc8fb10558c3a82fe8f851451cbd5f254ca65016
is identical before/after. MrCall operator and signup pass; actual received reply,
Café provider draft/engine binding/no-send, no-duplicates and loaded-candidate
checks pass. Café reaches its unchanged45-minute limit without a terminal;
its ordinary discovery proof and normal guarded route are unproven. Exact cron,
owned process and enrollment cleanup pass. No retry was launched.

Private exact raw diagnostics and the actual Café USD4.0855942 cost-state record
are retained in the V18 `free-diagnosis` directory. The interrupted stream has
four same-session init events and zero result events, so it does not validate
the complete continuation protocol. Its ordinary discovery and review calls
auto-background after ten minutes; that discovery remains unsupported by the
strict foreground join. Three native evidence agents and99Bash calls expand
triage beyond the successfully created requested draft. The separately reviewed
[bounded workset](2026-10-18-bounded-triage-workset.md) is source-only follow-up;
it cannot waive these native obligations. Final acceptance and closure stay open.
