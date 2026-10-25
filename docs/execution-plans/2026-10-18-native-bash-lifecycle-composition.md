---
status: completed
---

# Native Bash lifecycle composition

Approved [brief](../briefs/2026-10-18-native-bash-lifecycle-composition.md).
Both repositories retain identical framing; source-only work precedes adoption.

## M1 — bounded pure composition validator

After plan approval, one execute worker owns only new cs/operator_native_composition.py
and tests/test_operator_native_composition.py in the kernel, with a ten-minute
handoff and no subagents, source beyond ownership, model/provider calls or loops.
Lead monitors and stops stalled/repetitive work. Other sessions' edits remain.
Lead owns existing recovery/receipt hooks, their tests, tests/run.sh and Actor
scripts/operator_operational_common.py plus its scoped operational tests.
The original operator_native_lifecycle.py remains byte-identical.

API: composition(events, producer) returns None or {terminal, proof}. It consumes
only captured events and the already bound known producer; no filesystem/RPC or
customer authority. Require producer version/hash, actual child identity shape,
unique original UUIDs/session, exact init configuration, typed clean indexed
results and all original init/result order. Reject Agent/Task and every non-Bash
SDK task kind, unknown lifecycle event, failed/interrupted other task, unclosed
work, missing/intermediate/final result or unsupported late-held ordering.

Maintain task/run/tool tables over actual metadata. Foreground examples have
start false, completed notification, then a matching successful non-interrupted
raw tool result; there is no terminal update in the retained observed form.
Automatic tasks retain start false and require the real background true patch;
explicit background tasks retain their actual true. Bind actual advertisements,
terminal update/notification and original tool result. Canonical discovery may
have machine-held3 only under the existing subsequent physical join; other
asynchronous failures refuse. Completion while the segment is active does not
invent a callback. Completion between results requires its actual task/run
notification origin for the next init. Pending advertisements/callbacks must
clear; result count equals init count, with first origin null and every later
origin exactly its actual callback. No repeated init while active is admitted.

A control projection retains literal non-task original event dictionaries;
remove only separately validated SDK task/membership metadata. Never change
native flags or remove/reorder any init/result. Proof version2 records original
and projected canonical event hashes, exact removed indices/classifications,
all bound task records and actual callback identities/counters. Use the old
validator where applicable; the new finite-state check preserves its strict
control invariants when its input schema cannot express real auto transitions.
This is an explicit new proof, not a relabelled old approval.

Tests cover foreground metadata plus original genuine-probe-shaped callbacks,
canonical auto completion within a segment and actual callback ordering, zero
and held3, unknown/Agent/workflow, bad producer/identity/UUID, every incomplete
or reordered task state, missing/bad/intermediate/final results and altered
projection. Label constructed positives. Replay the actual retained V18 as a
negative; reuse the genuine old probe separately without modifying its bytes.

## M2 — ordinary wiring, canonical transport and Actor consumption

Lead pins the known executable before ordinary scheduled launches as well as
protected acceptance. Preserve custom signup behavior and existing legacy
foreground/version1 support. For the new ordinary metadata path, Attempt/result
and receipt generation use the same validated terminal/proof; an asynchronous
launch false cannot mask a later task failure. Unknown producer/new path refuses.

Canonical transport still independently proves exact physical capture/output,
owner/nonce/ancestry/source and full native inspection. Consume its actual auto
task record from composition; do not force a multiple-init stream through the
single-init helper by manufacturing terminal frames. Preserve initial native
false/null and add actual typed completion metadata. Existing foreground paths
and strict human-held3 conditions remain unchanged.

Actor validates version2 source/producer/child/session, original/projected hashes,
strict init/result counts and callback/task/removal metadata. Automatic completion
may use multiple init IDs only when this exact proof is valid and its canonical
tool/task/run binds to it. Keep old foreground and version1 tests unchanged.
Real local subprocess/pin/capture checks plus explicitly synthetic control
composition test both sides; missing original final terminal always refuses.

Fresh M1 integration review precedes dependent wiring. Fresh M2 review covers
kernel/Actor complete owned deltas and actual offline composition evidence.
Unchanged large policy inventory bodies remain outside semantic review with
exact byte-preservation checks. Focused checks first, then one final full kernel
suite; no repeated broad suite after unchanged green evidence. Reconcile docs,
explicit doc-critic and separate final review in both roots before source closure.
No installed/provider/native positive is inferred. Preserve failed receipts.

## Rollback and subsequent operational boundary

Remove only matching owned additions/hooks; preserve original validator, other
sessions, installed engines/packages, protected drafts, cron and all failed runs.
No timeout, budget, permission, producer-version or model change is included.
Activation and one prospective actual ordinary case follow only independently
reviewed complete free preconditions and the existing bounded authorization;
never add another native probe, invent a lifecycle or reseal V18.

## Reviewed narrow compatibility amendment

Reopen M1 for literal non-control telemetry compatibility before M2 review.
Preserve these events in the projection and both hashes, never as control or
authority: thinking_tokens with exact typed nonnegative counters; Bash
tool_progress heartbeat with the actual pending parent tool and typed elapsed
time; permission_check_status checking/done pairs for actual known tools, no
agent_id, closed before a tool result/final; rate_limit_event with explicit
allowed status and known producer fields. Validate original session/UUID and
active-segment position. All unknown types, task_progress from excluded Agent
work, malformed/foreign/nonallowed telemetry and incomplete permission pairs
refuse. Test all observed retained telemetry types, preserving original zero
results as a mandatory refusal. Fresh M1 re-review precedes dependent M2 review.

For the actual exec-based primary budget wrapper, explicit
CS_OPERATOR_NATIVE_BINARY selects the emitter for prelaunch pinning separately
from the launcher. Preserve cmd[0] and all launcher arguments when supplied;
actual child binding must still prove that pinned executable/file identity.
Without the explicit override, preserve direct native resolution. Never parse
a wrapper to guess its target or drop auth/budget behavior. Real local exec
wrapper tests, mismatch negatives and read-only actual cron/driver preflight
are required before activation; no paid attempt or install occurs here.

## Source delivery evidence and retained obligations

M1 and M2 have independent APPROVED reviews after targeted selector/interruption
repairs. The original lifecycle source remains byte-identical. Retained component
checks include eleven pure composition tests, real local ELF prelaunch/live-child
and budget exec-wrapper matching/mismatch tests, full physical exit0/held3 capture
with synthetic active/callback controls, and strict Actor codec corruption tests.
The exact staged clone change adds one emitter export in its API-primary branch;
preimage and candidate shell runs preserve authentication, cap, send grants and
arguments on both branches. The actual live clone file is unchanged.

Evidence root: /home/mal/.local/share/ordinary-assignment-recovery-resume/bounded-triage-workset-20261018.
Exact source: bash-composition-source-candidate-r3.json; M1 review
bash-composition-m1-review-r3.md; M2 review bash-composition-m2-review-r3.md.
The final full suite must pass bash-full-suite-r1.log before source closure.
The original V18 zero-result stream remains a negative, never a resealed PASS.

This plan's completion is source-only and qualified. Joint reviewed adoption
(including staged clone emitter export), actual known-native/ordinary/provider
acceptance, final operational documentation and the umbrella recovery closure
remain pending. No installation, model call or release is part of this component
closure. The actual subsequent case retains its existing authorization and limits.
