# Attention agenda — brief

## Problem

`/cs-review` promises to answer “what needs the operator today”, but its inputs
do not answer that question:

- `cs unanswered` is a high-recall, Sent-anchored candidate set. Its own
  contract says that it does not classify intent.
- `cs review` returns persisted engine tasks and drafts plus freshness signals.
  A task or draft is evidence that somebody once considered work necessary; it
  is not proof that the work is necessary now.
- the rendered `/cs-review` command currently requires every row to appear in a
  fixed shape and emphasizes transcription over judgement.

The result degrades as state accumulates. In the 2026-08-28 mario124 review,
Qonto marketing and Shopify billing/export notifications appeared as open
support work, an empty draft from 2020 appeared as ready to send, and the
24-task ledger contained low-confidence informational items. The subsequent
Claude session recognized the errors only after the operator objected, then
edited `manifest.toml` despite the review's explicit no-write boundary.

This is a product failure. Internal provenance does not make a false agenda
acceptable to the operator.

## Decision

Make `/cs-review` an explicit attention adjudicator rather than a formatter.
The Claude session already running the command is the judgement model; the
kernel will not add a second LLM call, credential, provider route, or competing
source of semantic truth.

The review will build a union of candidates from drafts, engine tasks, and the
Sent-anchored support sweep, deduplicate them by contact/conversation where
possible, load the current thread for every candidate, and assign exactly one
attention verdict:

- `act_now` — the operator has a concrete obligation now;
- `waiting_external` — the next move belongs to somebody else;
- `informational` — notification, receipt, newsletter, completed automation,
  or other mail that requires no response or decision;
- `stale` — an old task/draft whose premise no longer matches the conversation;
- `uncertain` — current evidence is insufficient for a safe conclusion.

Only `act_now` is the operator's agenda. `uncertain` is a separate, short review
queue. The other verdicts remain auditable as counts plus concise reasons, but
must never be presented as work to perform.

An `act_now` verdict requires positive evidence in the current conversation:
a direct unanswered request/question, an unfulfilled commitment by the
operator, a decision only the operator can make, or a concrete consequence or
deadline requiring intervention. “It is inbound and nobody replied” is not
positive evidence. Neither is “the engine has an open task”.

## Evidence and authority

The adjudicator must preserve source authority without confusing it with the
final product answer:

- Gmail remains authoritative for message existence and Sent deduplication.
- The engine remains authoritative for its stored classifications, memory, and
  task ledger.
- The current conversation is authoritative for what is true now.
- The review model owns only the final presentation question: whether the
  evidence deserves the operator's attention today.

The review may disagree with a stored task for presentation purposes, but it
must state the disagreement and must not silently mutate or close the task.
Persistent corrections remain named human actions.

## Draft semantics

The existing `ready` draft verdict means only “no overtaken, superseded, or
settled signal fired”. The review must not translate that into “ready to send”.
A draft with no recipient, no subject/body, no usable conversation, or an
ancient premise is `stale` or `uncertain`, never `act_now`. A genuinely current
draft appears as work to review, not as authorization to send.

## Read-only boundary

Review and repair are separate modes. During the review, no repo edit, task
write, draft mutation, send, memory write, or configuration change is allowed.
The optional engine catch-up remains the one named exception and runs only
after explicit confirmation. Discovering a bad sender or bad task produces a
reported disagreement, not a configuration edit.

The rendered command must end after presenting the agenda. Subsequent changes
require a new explicit operator instruction naming the target and action.

An interactive Claude Code session already has the ambient permissions granted
to that workspace; a slash-command prompt cannot revoke them for the duration
of one expansion. This work therefore enforces the boundary at the command
contract and regression-gate level: the review contains no repair instruction,
names no mutating command except the confirmed catch-up, and must stop after the
report. Hard tool isolation would require launching a separate restricted
process and would change the operator's one-command workflow; it is not claimed
as part of this delivery.

## Regression contract

The incident becomes a permanent replay fixture. The minimum gold set is:

| candidate | expected verdict |
|---|---|
| Qonto newsletter about aggregated business data | `informational` |
| Shopify invoice successfully issued/charged | `informational` |
| Shopify “order export is ready” notification | `informational` |
| empty draft from 2020 with no recipient | `stale` |
| current insurance questionnaire awaiting completion | `act_now` |
| current customer reply requiring a business answer | `act_now` |
| invoice already paid and confirmed on WhatsApp | `stale` after the handled record |

Hermetic gates verify the rendered command's decision contract, required
evidence, candidate enrichment, output partition, and no-write posture. A
separate opt-in live replay runs the rendered adjudication prompt against the
gold cases with no tools and fails on any label mismatch. Prompt changes are
not trusted until both gates pass.

## Scope

In scope:

- the kernel-owned `/cs-review` template and its rendered clone surface;
- read-only candidate/thread gathering needed by that command;
- incident-derived hermetic fixtures and an opt-in live semantic replay;
- documentation of the new agenda contract.

Out of scope for this workstream:

- automatically deleting drafts or closing engine tasks;
- changing the engine's task detector or retraining its stored prompt;
- installing cron, configuring CRM, or expanding `system_senders`;
- releasing a tag or upgrading clones without a separate explicit approval.

## Rejected approaches

- **Extend `system_senders`.** Useful as an optimization, but it only hides
  known examples and cannot decide whether a novel notification matters.
- **Trust engine tasks as the agenda.** A ledger is persistent evidence and can
  be stale or noisy; the current conversation must be consulted.
- **Add another kernel LLM classifier.** It duplicates the headless model,
  introduces provider/credential drift, and makes the review pay twice for one
  judgement.
- **Let the model freely improvise.** The current failure proves that a capable
  model without an explicit responsibility and output contract can become a
  formatter. Judgement must be required, structured, replayed, and auditable.

## Acceptance

The work is accepted when:

1. the rendered command enriches every unique candidate with current thread
   evidence before classifying it;
2. only `act_now` rows appear in the main agenda, with `uncertain` separate;
3. source labels (`task`, `unanswered`, `draft`) are provenance, never verdicts;
4. the seven incident gold cases pass the hermetic contract and live semantic
   replay;
5. the review command contains no mutation path other than a separately
   confirmed catch-up, and explicitly stops before any repair;
6. the full kernel gate remains green and a freshly rendered clone carries the
   same behavior.
