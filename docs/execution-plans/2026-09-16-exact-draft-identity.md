---
status: active
updated: 2026-10-13
---

# Exact mirrored-draft identity plan

## Current execution

Approved brief: [exact draft identity](../briefs/2026-09-16-exact-draft-identity.md).
The brief's current implementation boundary limits this execution to source
and controlled local acceptance. Release, hosted activation, clone upgrades,
real sends and production cleanup are separate authorizations.

Canonical exact-ID `cs draft-send` is already released in `v0.47.0`. This work
addresses the separate identity of the Gmail review mirror and engine row.

### Ownership and dependencies

- Kernel identity worker owns `cs/gmail_drafts.py`, `cs/draft_state.py`, a new
  authored-content helper and focused identity/body tests. It writes the full
  engine draft ID and owner UID into new mirrors, reads both back, and pairs
  exact unique identities before explicitly labelled legacy inference. Exact
  IDs with missing/wrong owners, duplicate copies, or conflicting recipient/
  thread context remain visible as conflicts and never fall back to inference.
- Engine worker owns the independently verified external-delivery RPC and its
  storage/transport tests in mrcall-desktop. The operation takes an exact draft
  ID and Sent Message-ID, independently reads the owner's Sent mailbox, checks
  unique identifiers/owner/context, and uses existing draft writer reservation
  and CAS. It is not a chat tool. Caller-provided headers are not evidence.
  Live provider preservation is unverified; automatic reconciliation is not
  activated by this change. No kernel review path invokes the mutation.
- Lead owns CLI mirroring, logical retirement, review output, permission
  enumeration, test-suite wiring and documentation. Work begins only after
  fresh plan approval. Concurrent operator-notice and engine-workflow edits
  belong to other sessions and must be preserved.

### M1 — Identity and independently verified delivery

1. Controlled MIME/IMAP fixtures preserve both exact identifiers through
   APPEND, fixture edit and fixture Sent retrieval. This is explicitly not
   Gmail provider certification. No Message-ID fallback is asserted.
2. Pair on full draft ID plus selected owner; bound MIME body reads use
   BODY.PEEK and refuse incomplete/truncated payloads as authored evidence.
   Extract plain/HTML newly authored content conservatively, excluding quote
   blocks and standard reply delimiters. Exact normalized matches alone may
   yield duplicate; uncertain extraction remains visible with a note.
3. Exercise reordered same-thread alternatives, forged/missing owners,
   duplicate IDs, edited mirrors, short authored text over long quotes,
   oversized MIME, attachments and unreadable bodies.
4. Engine independently checks Sent evidence and exact owner before CAS;
   prove idempotence and conflict refusal, no subject/recipient fallback,
   no SMTP call and no route around sending/discard reservations.
5. Review M1 integration before wiring dependent CLI effects.

### M2 — Explicit logical retirement and operator surfaces

1. New `cs draft-retire` requires the exact engine draft ID, Gmail UID and
   Gmail UIDVALIDITY. Preview reads both stores and names both effects;
   `--commit` remains an interactive-only gesture. A headless marker refuses
   inside the command; settings/cron deny all six command spellings.
2. Gmail retirement checks UIDVALIDITY, full identity, selected owner and
   current message fingerprint on the same selected IMAP connection before
   UID MOVE to Trash. No expunge. Engine discard uses exact current draft
   revision/content evidence through its guarded RPC; no substring selector.
3. Preflight both effects before the first write; on partial completion name
   the surviving copy and safe next action. Do not widen a retry to a different
   UID or engine row. No cross-provider atomicity claim is made.
4. Mirror creation passes engine ID/owner; JSON review labels identity evidence.
   Automatic post-send retirement must not act on heuristic legacy pairs.
   Existing named Gmail-only delete remains available as a separate operation.
5. Focused real CLI/parser and controlled transport/store checks, complete
   kernel suite from a clean build artifact directory, affected engine tests,
   mechanical/semantic documentation review, then separate fresh final review.

### Rollback and deferred acceptance

Revert only this task's named files or changes, preserving unrelated edits.
Additive mirror headers are harmless to old readers; older engines refuse new
RPCs. No deployment or persistent production mutation occurs in this run.
Engine schema changes, if needed, use the existing idempotent migration runner.
Live Gmail edit/send preservation, both-clone FULL acceptance, release/adoption
and operator-named backlog cleanup remain explicit M6 obligations. They are
not claimed completed by controlled fixture acceptance.

## Original milestone outline

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
no draft was moved, discarded or reclassified. Canonical-send code is released;
the new mirror-identity implementation and its acceptance are recorded in the
current execution above and subsequent Results.

## Results — local candidate, 2026-10-13

M1 and M2 source integration have APPROVED independent reviews. The kernel
implements exact mirror headers, conservative authored-body evidence and
snapshot-bound retirement; the engine supplies inspect, guarded discard and
independently verified explicit Sent recording. No schema migration is needed.

Verification evidence is retained under
`/tmp/mrcall-ai-kit/exact-draft-identity/`. The complete kernel suite on the
frozen integrated source exits 0 with `RESULT: all gates green`
(`/tmp/exact-kernel-frozen-suite.log`); task-scoped source hashes match the
reviewed working tree. The affected engine suite reports 76 passed
(`/tmp/exact-engine-m2-affected.log`). RPC contract generation and negative
proofs pass (`/tmp/exact-rpc-contract-inventory-final.log`). Focused real
CLI/parser, controlled IMAP and SQLite checks cover changed snapshots,
conflicting identity, edited content and lost MOVE acknowledgements.

Local acceptance uses controlled provider/storage fixtures. Live Gmail
edit/send preservation, hosted activation, both-clone FULL acceptance,
release/adoption and operator-named production cleanup remain pending.
Automatic external reconciliation remains disabled. This plan stays active
for those explicitly deferred obligations; local implementation does not
claim full provider or rollout completion.

## Results — real provider and installed engine acceptance, 2026-10-13

The separately authorized [live acceptance plan](2026-10-13-exact-draft-live-acceptance.md)
owns this extension beyond the historical local-only scope. Both maintained
mailboxes preserve exact custom identity through real IMAP APPEND/replacement
and owner-to-self SMTP. Exact edits, duplicate identity, wrong owner, changed
folder identity and stale fingerprints refuse unsafe retirement. Recoverable
Trash cleanup removes only marked test drafts.

The live Gmail run found a consuming UIDVALIDITY read and an RFC-folded Subject
comparison defect; both have regressions and reviewed fixes. The engine's
released-baseline transaction adapter preserves private writer/CAS and old
send-claim exclusion without introducing unreleased contextual policies.
Main adapter tests report 27 passed; actual released-baseline tests report
25 passed, with two modern-assignment-only cases explicitly deselected.

Both hosted engines load the isolated exact extension. Authenticated CLI
acceptance against the kernel candidate and real hosted Sent reconciliation
pass on both profiles. Replay is idempotent, conflicting replay refuses and
already-sent discard refuses. All 111 support and 61 production pre-existing
draft rows match their retained original hashes after this fixture acceptance;
created engine fixtures are removed. Original Gmail draft UIDs remain present.
Existing interpreters, configuration, service users, sandbox/egress and production
voice binding remain unchanged. Scheduled permissions are forward-protected
with the canonical eighteen new denies; dynamic launcher argument checks pass.

Evidence: `/tmp/mrcall-ai-kit/exact-draft-live/`, including provider/edit journals,
Sent MIME journals, installed CLI/Sent journals, activation records, original-row
verification logs and M3/M4 independent review reports. Native Gmail browser/
mobile/API edit/send preservation remains unverified; automatic reconciliation
is disabled. Public kernel publication/adoption and exact operator-named
customer cleanup remain pending. This plan stays active.
