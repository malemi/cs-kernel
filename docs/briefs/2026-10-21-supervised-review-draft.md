# Human verification gates sending, not draft preparation

Date: 2026-10-21
Status: APPROVED — framing review, brief only

Independent framing review approved on 2026-10-21. This approves the problem,
scope and acceptance criteria; it does not certify implementation or authorize
deployment.

## Problem and operator decision

The operator requested a reply draft and corrected it to answer every customer
question. The system refused because the thread was marked
NEEDS_HUMAN_VERIFICATION / needs-assignment. The operator clarified that human
verification must apply to sending, then explicitly requested this brief in
cs-kernel so the refusal does not recur.

The existing interactive cs draft-reply command requires assignment admission
before composing an unsent draft and again before publishing its Gmail review
copy. This conflates preparation of an internal review artifact with delivery
to a customer.

## Required outcome

A normal explicit draft request prepares and saves a complete, unsent reply for
human review in the existing thread. Human verification and assignment holds
remain visible and effective for sending; they do not themselves prohibit draft
preparation. The operator must not have to repeat permission, clear an assignment,
invent a grant, select a special workaround or discover another tool each time.

This repairs an existing shared command, not a new company-specific abstraction.
Only this operator supplied the correction; do not invent a second company's
requirement. The explicit assignment is a kernel brief. Keep the repair neutral
and verify maintained clone fixtures; unrelated new capabilities require their
own justification.

## Scope and boundaries

- Separate prepare, persist/publish-for-review and send admission in CLI,
  transport and engine policy. A draft is not verification of human authorship,
  acknowledgement of assignment, closure, or delivery.
- Bind authenticated account, company, actual source, thread, To/CC and reply
  headers. Missing or contradictory source/recipient evidence remains a real
  failure; prompted identifiers alone are not identity verification.
- Keep dossier and prior-contact context. An unreadable colleague mailbox remains
  incomplete evidence, never “no contact”. Distinguish that uncertainty from
  inability to address an internal draft whose own source is verified; do not
  clear the access error or claim complete history to prepare the review artifact.
- Preserve classification, suppression, queue selection, existing human work and
  draft deduplication. Do not overwrite human edits, delete other drafts, close
  tasks or generate unsolicited replies merely because a hold exists.
- Explicit interactive draft requests need no new per-message approval ceremony.
  Scheduled selection and authorization remain unchanged. No wider cron or
  autonomous-send permissions are authorized by this brief.
- Sending remains a separate action requiring actual human approval and applicable
  fresh authority/source checks. No draft mode, flag or caller prose may grant
  send permission or carry it into another request or thread.
- Report actual persistence: a local text file is not a mailbox draft; a
  provider-only review draft is not an engine row.

## Evidence and existing alternatives

Lead-read kernel sources: cs/cli.py cmd_draft_reply calls task_assignment.guard
before generation and again before Gmail append. cs/rpc.py negotiates the
assignment draft policy separately from the newer contextual email protocol.

The engine owner reports equivalent pre-routing and storage-write gates in
services/task_assignment_draft_policy.py. They report that the actual hosted
generic manual chat route lacks typed source binding and comprehensive draft-only
effect restriction. Dropping assignment scope and relying on prompting is
therefore not a proven repair. Verify these reports against the retained runtime
before implementation; newer MAIN behavior is not evidence of deployed behavior.

The existing cs.gmail_drafts.append_draft function performs only IMAP APPEND
with the Draft flag. Independent review approved copying the already reviewed
text through that existing path for the immediate request, with provider-verified
source/headers, deduplication and complete readback, without engine identity
headers. This individual delivery is now verified: one provider-only review
draft, no send. Neither engine nor kernel source was changed. This workaround
does not resolve the normal-command bug.

The engine owner also reports that actual hosted manual sending is not universally
assignment-gated. Map real send entry points before claiming the repaired
prepare/send distinction is enforced. Close any concrete gap introduced for
affected drafts; do not import an entire uninstalled policy subsystem or claim
Gmail browser/manual sending is engine-enforced.

## Acceptance

1. Reproduce an ordinary explicit draft request on a verified own-source thread
   held for NEEDS_HUMAN_VERIFICATION. The normal command succeeds without human
   assignment confirmation and produces exactly one complete review draft.
2. Verify persisted content answers every requested question; To/CC, actual
   source, RFC root, reply headers and Draft state match. Verify the actual
   engine/provider persistence promised by the command, not a local file.
3. Repeated requests reuse or explicitly update the intended draft without
   duplicate creation or silent overwrite of human changes.
4. Preparation sends nothing. Test actual send entry points for affected drafts:
   missing approval, wrong identity/thread, stale binding or applicable unresolved
   sending holds cannot reach transport. A draft request cannot approve sending
   or other mutations through tool dispatch.
5. Preserve scheduled scope, held-work visibility, suppression and unrelated
   send behavior. Technical failures stay explicit; no incomplete result is
   rewritten as complete or waived globally.
6. Reconcile canonical workflows and error messages: distinguish “draft prepared,
   sending awaits verification” from actual source/provider failures. Remove
   instructions that refuse an unsent draft solely for pending human verification.
7. Focused regression tests and bounded real provider verification establish
   the new behavior. Preserve unrelated source work, runtime budgets and maintenance
   ownership. Record tested source, limits and rollback before adoption.

## Deliverable and exclusions

Deliver this reviewed brief only. A subsequent implementation plan must select
the smallest supported contract from verified runtime evidence and identify
kernel/engine ownership, sending enforcement and safe adoption checks. Do not
mandate a new capability, schema, durable marker or special flag before establishing
the actual gap and simpler supported alternatives.

No implementation, policy publication, baseline advancement, release, push,
runtime activation or paid acceptance loop follows from this brief. Genuine
source, authentication and provider failures may still prevent completion; the
requirement eliminates this incorrect verification refusal, not real outages.
