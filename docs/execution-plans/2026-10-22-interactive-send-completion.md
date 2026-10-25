---
status: failed
---
# Interactive send completion

## Operational outcome: FAILED

The operator rejected the result on 2026-10-23: the requested visible email
generation was not delivered. The assistant stopped after response-text tests
and did not complete the operational mailbox work. The development assignment
failed. Component tests and scoped review approvals do not change this outcome.
The evidence below is retained as partial evidence, not successful acceptance.

Approved brief: [send completion](../briefs/2026-10-22-interactive-send-completion.md),
SHA-256 `bafde5db83c668ffa67b4bb6a7c9a152031936015df27b7c1208cf708942bce0`.
The fresh Astra brief gate approves the updated, content-selection scope.

## Ownership and dependencies

Lead owns live case correction, billing publication, support-queue processing,
documentation, exact installed adoption and closure. A bounded execute worker
owns cs/interactive_draft.py, cs/cli.py, a focused send-completion helper if
needed, and their meaningful tests. The worker may also own narrow RFC 2047 subject decoding in cs/gmail_drafts.py
and its regression. Other dirty source is not worker-owned.
No dependent adoption precedes M1 review and two concordant Astra approvals.

## M1 implementation and verification

Capture immutable before/after draft content. Identify exactly one new or
materially changed row, including edits whose updated_at never advances. Retain
all own-source/output checks and refuse ambiguous changes. Do not replay a
successful edit when provider mirroring refuses a changed existing copy.

For interactive exact-ID sends, require independent exact Gmail Sent proof before
retiring only that draft's unchanged mirror. Bind engine owner, exact Sent
Message-ID, From/To/Cc/Bcc, root/target, subject and complete authored body; refuse
ambiguous, clipped or malformed proof. Reuse conservative strict retirement,
UIDVALIDITY and fingerprint checks, preserve human edits/unrelated copies.
Separate delivered from cleanup-complete outcomes. A failed verification or
cleanup returns an explicit delivered-but-incomplete result and never repeats
send_draft. Retain scheduled routing and guards unchanged.

Decode RFC 2047 subjects narrowly for comparison, retaining genuine text
differences and refusing malformed/ambiguous identity. Exercise an encoded
em-dash subject through append/readback: exactly one provider draft and no
repeated edit/append; a genuinely different subject remains preserved/refused.

Run free focused controls through actual command paths: successful unchanged
mirror retirement, absent/ambiguous/wrong-provider evidence, edited mirror,
cleanup failure, one send approval only, timestamp-stale content update,
multiple changes and no-change refusal. Existing known full-suite failures are
retained; do not repair unrelated tests. Review M1 before adoption.

## M2 bounded adoption and actual outcomes

Build installed preimages/postimages from only owned deltas; preserve package
inventory and unrelated local overrides. Two independent Astra reviewers inspect
the same exact candidate and adoption transaction before application. Verify
normal installed imports, unchanged files and focused tests afterward. No pin,
release, schedule, authority or budget changes.

Actual cases: independently read back Stefano/Omar Sent with no unchanged
mirrors; verify Elisa's manual send without replay; verify Francesco's updated
same engine row and one provider draft, fiscally grounded billing text (no unsupported business-invoice exemption), recognizable subject
and exact headers. Retain raw before/after evidence separately and test negative
controls against original failures. Native Gmail UI visibility is unverified if
the read connector remains unauthenticated; IMAP flags alone do not prove it.

Continue ordinary customer queue work independently, using complete dossiers,
current source evidence and exact-ID sends where admitted, review drafts when
held. Explicitly distinguish incomplete discovery from an empty queue and keep
unresolved technical/configuration work visible without inventing completion.

## Closure and rollback

Lead reconciles affected runtime/assignment/workflow docs, current snapshots and
prior misleading acceptance claims, preserving replaced history verbatim. Run
doc-end and explicit doc-critic; require the read-only completion check with
--phase pre-review to pass before the separate fresh final review. After actual
final approval, run full completion check and checker finalization. Do not mark
this failed plan completed on the basis of partial checks. No release.
Rollback only captured owned installed postimages when their current hashes
still match; recover individual moved drafts from Trash if needed. Never resend
confirmed delivery or rewrite historical failed acceptance as passing.

## Partial evidence and unmet acceptance

M1's repaired exact source patch is
`0336b5b97faa3e3ee23a5c453ff56011f1a0e0c856f0c7dc631491ffb5a907b2`.
Both independent Astra gates approve the repaired runtime patch
`e2507a74eac7ccaa5ddbeea6b5360ffc071c4c4d6246ee786fd63cc768a84d1d`
and installed manifest
`beae95748cf0ae269c61e5def3a62a43785b188d116ad883b886791f00b7be46`.
The initial attachment/Bcc defects and REVISE verdicts remain retained. The
reviewed five-file adoption succeeded; all124 package files match the receipt.
Source and actual installed focused suites pass69 tests, six negative controls
fail the original bad paths, and retained actual Stefano/Omar MIME is accepted.

The named cases have three provider Sent messages with no residual copies and
one current Zuccaro fiscal review draft (UID2380, same engine ID). Elisa's manual
send is corroborated; her engine row remains draft. No confirmed send was replayed.
Billing revision10 is published/read back and narrowly committed in the clone.
The operator's later fiscal correction has separate brief/plan approval artifacts;
the operative wording excludes unsupported legal impossibility and business-invoice
exemptions. Actual customer VAT records remain unknown.

Ordinary discovery and several broad dossiers stalled; current-root bounded reads
retain their actual incomplete assignment results. Current provider correspondence
shows many apparent tasks already have later replies. Older technical commitments
remain unverified and no task is closed from reading. The global queue is not
certified complete; new signup/campaign tasks and excluded SIP/financial work keep
their existing owners. Catch-up synced one email but update timed out after180s;
no blind repeat or invented successful sync/update is permitted.

A fresh live send through the repaired completion branch, native-client evidence,
Elisa external-send reconciliation, whole-queue parity and unattended acceptance
remain unmet. This plan is failed; no completion transition is requested for
those unmet operational obligations. Final source/documentation review must keep
these limits explicit rather than treating69 offline tests as complete acceptance.
