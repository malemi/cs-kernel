# Interactive send completion

## Intent

The operator rejected the prior four-customer test: successful interactive sends
left identical Gmail drafts, Elisa was manually sent after our report, and
Francesco's draft could not be found under his invoice request. A green isolated
record is not a successful operator workflow. Correct these actual cases and the
normal interactive send completion behavior without replaying delivery.

## Scope and constraints

Existing engine-draft updates can change subject/body without advancing updated_at.
Select one changed draft by a before/after content snapshot, not a timestamp
that the live engine does not maintain; validate source/output and preserve
conflicting provider edits. Never replay a successful edit after mirror refusal.

After one exact-ID send, independently verify the exact outgoing Gmail Sent
message and retire only its unchanged, owner/recipient/thread/body-bound review
mirror. Preserve human edits, unrelated drafts and unknown outcomes. Sending and
cleanup are separate effects: cleanup failure must report delivery as already
sent, never trigger a resend. Keep current assignment, source and approval gates.
Retain scheduled behavior unless a required shared safety check is documented.
No public release, blanket deletion, assignment mutation or ambient-app sending.

Apply the operator's clarified billing rule to unsent invoice replies. Preserve
his exact two-week/receipt instruction as provenance; do not falsely claim an
absolute legal ban where the official source describes late issuance. Process
actual answerable support queue items with dossiers, current thread checks and
exact-ID sends; held threads still receive verified review drafts.

## Acceptance

- Stefano and Omar each have one corroborated Sent reply and no unchanged mirror.
- Elisa's reported manual send is independently corroborated and not resent.
- Francesco has one current, clearly identifiable provider draft explaining the
  fiscal reason (late-issuance penalties, accounting checks where applicable),
  retaining customer-entered complete details and the firm receipt instruction
  only where an invoice was not obligatory. No unsupported fourteen-day legal
  ban, blanket business-invoice exemption, arbitrary refusal, duplicate copy or
  unverified claim about his VAT records; exact recipient and reply headers.
- Updating an existing engine draft without a changed updated_at is identified
  correctly; multiple/concurrent conflicting changes refuse without another edit.
- The normal interactive exact-send path performs verified mirror cleanup;
  changed/unknown provider evidence preserves drafts and reports a qualified
  delivered-but-cleanup-incomplete result without repeating delivery.
- Tests inspect resulting provider and engine states, including duplicate and
  missing-draft failures, policy text and all effect counts. Negative controls
  demonstrate that the test actually fails on the original bad outcome.
- At least two independent Astra reviews agree on the exact candidate before
  bounded clone adoption, then real readback proves the installed behavior.
- Remaining queue obligations and provider/UI coverage limits stay explicit;
  neither a partial inventory nor source unit tests prove queue completion.

## Assumptions

The live instruction authorizes correction of these exact residual drafts and
processing support requests, with existing reversible Trash operations. It does
not authorize deleting human edits, bypassing assignment guards, new service
configuration changes or unlimited paid acceptance loops.
