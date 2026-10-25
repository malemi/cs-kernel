# Interactive draft source corroboration and diagnostic loss

## Intent

Allow an explicitly requested review draft to proceed when complete provider
mail and the engine archive identify the same latest inbound, despite ordinary
reply-history formatting. Preserve refusal for genuinely ambiguous or conflicting
sources. Make each refusal diagnosable through ordinary operational logs.

This brief authorizes no implementation, customer replay, send, installation or
release. The requested deliverable is this brief; subsequent development requires
the repository's brief and plan review gates.

## Observed failure

An interactive `cs draft-reply` stopped before composition on 2026-10-24.
Trace `0952cb83a7f8487fbe9eb3f203c3b2e6` ran from 12:40:56.874790 to
12:41:01.307059 UTC and returned exit3, `held/incomplete-input`.
The trace contains capability and exact-thread reads, without a generation call.
No draft creation, Gmail append or send was attempted. This is a kernel source
corroboration failure, not evidence of an engine/Gmail persistence failure.

The complete provider body was available (9,267 characters); the normalized
engine authored body contained 251 characters. Source inspection identified:

1. `cs/draft_identity.py::authored_plain` encounters a reply delimiter followed
   by nonempty, unquoted text. It returns an empty body with an ambiguity note.
2. `cs/interactive_draft.py::_body` collapses that result to an empty string,
   losing the distinction between missing content and ambiguous extraction.
3. `_same_source_body` cannot corroborate the bodies. Its narrow fallback only
   covers `-----Messaggio originale-----` with four validated quoted headers;
   that fallback does not resolve this incident.
4. `source` raises `ValueError: Gmail and engine source do not identify the same
   latest inbound`. Several independent identity predicates share this message.
5. `prepare` catches the exception, prints its detail only to stderr and returns3.
   `observability_producers.observe` persists the generic held result, without
   retaining the decisive check or extraction reason.

These observations establish why the current path refuses. They do not prove
that all text after the delimiter is disposable history or a signature, nor that
accepting the original message without additional evidence would be correct.
The original investigation checked source/installed module equality; implementation
must re-establish actual package identity and reproduce the selected decision.

## Scope and constraints

- Repair source corroboration in the shared kernel, using explicit evidence and
  a documented treatment of complete provider content versus archived content.
  Do not substitute fuzzy/prefix equality or matching headers alone for source
  identity. Do not silently discard possible inline or bottom replies.
- Preserve the strict authored-content semantics used for draft identity,
  mirror reuse, retirement and Sent verification. A change needed for inbound
  source corroboration must not weaken these other consumers.
- Keep complete relevant provider MIME representations available to the engine
  within existing bounds; quoted or unquoted content remains untrusted mail.
- Preserve exact owner/root, latest-inbound, recipient, suppression, completeness,
  assignment and capability checks. Uncertain/conflicting source evidence must
  still stop before generation. No fallback composition after a failed attempt.
- Instrument the actual decisive predicate before its reason is discarded.
  Retain finite safe cause/check identifiers, phase, correlation references and
  extraction/completeness observations; distinguish parser ambiguity, true body
  conflict and other identity failures. Never persist customer text, credentials,
  arbitrary exception strings or raw tracebacks.
- Use the existing logging pipeline and its validators/ordinary access/collector;
  avoid a parallel incident logger. Preserve unrelated source and runtime work.

## Acceptance criteria

1. A privacy-safe reproduction derived from the observed formatting reaches the
   same current parser/comparison branch before the fix. The proposed matching
   rule explains what evidence permits continuation and what remains ambiguous.
2. After repair, an independently corroborated formatting case reaches exactly
   one engine review-preparation attempt, preserves material provider content,
   and supports verified engine-row selection and Gmail review-copy readback.
   This must not be reported as proven by a parser unit test alone.
3. Negative controls cover inline/bottom replies, conflicting authored content,
   different latest messages, incomplete/truncated provider reads, conflicting MIME
   alternatives, wrong owner/root and ambiguous recency. They retain the required
   refusal and produce no generation or persistence effect when source checks fail.
4. Exact draft identity, mirror reuse, retirement and Sent-content regressions
   retain their conservative guarantees; the existing Italian-header fallback
   and ordinary equivalent-source cases remain covered.
5. Actual producer-path regressions demonstrate that the decisive safe reason
   survives validation, persisted events, ordinary CLI and collector/inbox where
   applicable. A nearby different failure, legitimate hold, healthy case and
   unknown-cause control remain distinguishable; diagnostic sink failures do not
   alter business outcomes. A fresh blind reader can identify the blocked phase
   and a supported investigation route without source code or the answer key.
6. Delivery evidence identifies the exact source and installed candidates. Any
   authorized adoption/release follows the applicable two-clone gates; local
   regressions do not establish provider, ordinary-path or release acceptance.

## Evidence and ownership

The trace above is the incident locator; retain raw correspondence only in its
existing restricted stores. Use redacted/synthetic fixtures in the kernel.
The implementation owns `cs/interactive_draft.py` and relevant shared parsing
and observability paths, with regression coverage for every affected consumer.
Coordinate diagnostic instrumentation with the existing
[operational logging plan](../execution-plans/2026-10-23-debug-logs-hybrid-monitor.md),
which already records this separate gap. The parser/comparison repair remains
distinct from the delivered supervisor diagnostics.

Relevant contracts: [kernel charter](../kernel-charter.md),
[exact draft lifecycle](../draft-lifecycle.md), and
[log-driven diagnosis](../log-diagnosis-workflow.md).

## Open design decisions

Choose the evidence needed to reconcile complete provider content with a shorter
archive representation, including whether existing identity/MIME evidence is
sufficient or an upstream contract needs improvement. Do not pre-approve a
general rule that ignores everything following a reply delimiter. If the
incident remains genuinely ambiguous under the reviewed rule, retain the hold
with a precise explanation and identify the additional evidence required.
