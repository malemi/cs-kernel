---
status: active
---

# Exact mirrored-draft identity plan

## Milestone 1 — preservation proof

- Create a disposable Gmail draft carrying `X-CS-Engine-Draft-ID` in a test
  mailbox or controlled fixture.
- Verify the header after APPEND, after Gmail-side edit, and in Sent after send.
- Record the result; choose an explicit Message-ID mapping if Gmail strips the
  custom header.

No production customer draft is used for this proof.

## Milestone 2 — exact pairing

- Pass the full engine draft ID into `gmail_drafts.append_draft` and write the
  proven identifier.
- Read it back in `list_drafts` and pair exact identities before legacy
  thread/recipient inference.
- Report whether every row is `exact`, `legacy-inferred`, `gmail-only`, or
  `engine-only`.
- Add adversarial fixtures with two alternative drafts in the same thread.

## Milestone 3 — Gmail-only authored content

- Fetch a bounded MIME body for Gmail-only drafts without changing flags.
- Separate newly authored content from quoted history.
- Compare exact normalized authored content against Sent; keep fuzzy similarity
  informational only.
- Add the UID 1049 shape as a synthetic regression fixture: a short new follow-up
  above a long quoted Sent message must not be classified as duplicate.

## Milestone 4 — exact external reconciliation

- Add an engine operation that records an externally delivered draft as sent
  only when the stable identifier and owner match exactly.
- Persist Gmail's Sent Message-ID and sent timestamp.
- Prove idempotence, conflicting-ID refusal and no recipient/subject fallback.

## Milestone 5 — logical retirement

- Add a dry-run-first interactive verb that previews the exact Gmail UID and
  engine draft ID.
- On commit, move Gmail to Trash and discard the engine row; report partial
  completion without hiding the surviving copy.
- Deny the complete surface in the headless wrapper and enumerate every command
  spelling in the permission gate.

## Milestone 6 — rollout and cleanup

- Run focused fixtures, the complete kernel suite, documentation checks and
  both-clone FULL re-collaudo.
- Release and update maintained clone pins.
- Present the existing stale Gmail and engine rows as a reviewable cleanup list.
  Delete/discard only the rows explicitly named by the operator.

## Current evidence and limits

The production mailbox audit is recorded in the paired brief. It was read-only;
no draft was moved, discarded or reclassified. The current canonical-send code
is implemented and tested in the kernel working tree but remains unreleased.
