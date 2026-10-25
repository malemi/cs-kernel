# Exact mirrored-draft lifecycle

<!-- doc-scope:start -->
Scope: the exact identity, review and explicit retirement contract for engine
drafts and their Gmail review copies. Kernel release and clone adoption
remain owned by the execution plan and release procedure.
<!-- doc-scope:end -->

New `cs draft-reply` mirrors carry the full engine draft ID in
`X-CS-Engine-Draft-ID` and the selected owner UID in `X-CS-Engine-Owner-UID`.
Review pairs unique IDs only when owner, complete To/CC sets and thread context
agree. Its JSON reports `identity_evidence` as `exact`, `legacy-inferred`,
`gmail-only` or `engine-only`, with a separate `identity_conflict` when needed.
Conflicting IDs never fall back to inference. Legacy inference is display
evidence and cannot authorize automatic retirement.

Gmail content is read through bounded `BODY.PEEK`, without changing Seen flags.
The complete MIME observation supplies both identity/context and fingerprint.
Incomplete MIME has no mutation fingerprint. Newly authored plain/HTML text is
compared exactly after normalization; conflicting alternatives and ambiguous
reply continuation cannot establish duplicate content. Quoted history and
attachments do not establish newly authored text. An unreadable or ambiguous
body remains qualified by a note.

## Explicit review preparation — local candidate

Interactive `cs draft-reply` selects its contract before composition. Engines
advertising `supervised_review_draft_policy:1` require assignment policy1 and use
source-bound supervised preparation. Unknown advertised contracts refuse. The
local MAIN engine supports that stronger contract; selected hosted services do
not yet advertise it. An engine omitting the supervised capability uses the
legacy generic-chat review route with no send approvals. That route checks source
scope locally and does not claim server-enforced source isolation. Generation
failure is never replayed through another route. Missing or conflicting original
and recipient evidence refuses on both paths. Assignment holds remain binding on
sending.

The supervised engine can reuse identical rows and refuses conflicting existing
content. An explicit interactive request may edit an existing row through the
legacy engine path. The kernel selects exactly one new or materially changed
owner/root-bound row, then requires complete Gmail inventory before mirroring.
An unchanged or ambiguous result refuses without a second generation attempt. Existing matching copies are reused; edited, conflicting, legacy or
other thread copies are preserved with an explicit incomplete result. A new append
requires exact identity, recipients, headers, Draft flag and complete authored-body readback
before the command reports a prepared review draft. Persistent nonblocking owner/root
locks serialize copies sharing the same local state directory; this is not a
cross-host IMAP transaction. Attachment/Bcc-bearing drafts
are not mirrored through this candidate path.

Scheduled launchers retain policy1 admission and their existing selection and
send permissions. A review request grants no send approval. Actual provider and
ordinary two-clone acceptance, hosted adoption and final approval remain pending
in the [shared plan](execution-plans/2026-10-21-supervised-review-draft.md).

## Retire an exact pair

Read `cs review --json` and select the exact full engine ID, `gmail_uid` and
`gmail_uidvalidity`. Preview:

```bash
cs draft-retire FULL_ENGINE_DRAFT_ID --gmail-uid 17 --uidvalidity 9
```

The preview checks both stores, including the engine's current discard
authority, and returns `gmail_fingerprint` and `engine_snapshot`. Commit requires
those exact values from the preview:

```bash
cs draft-retire FULL_ENGINE_DRAFT_ID --gmail-uid 17 --uidvalidity 9 \
  --gmail-fingerprint PREVIEW_GMAIL_FINGERPRINT \
  --engine-snapshot PREVIEW_ENGINE_SNAPSHOT --commit
```

Changed content, folder identity, owners or engine state refuse the effect.
Gmail checks the full observation again on the same connection before moving
the UID to Trash; it never expunges. The engine consumes an unchanged full-row
snapshot under its writer reservation. Both effects are preflighted, but they
are not one atomic transaction across providers. An uncertain or partial
result names the exact handles and says which store to inspect before retrying.
The command refuses headless execution and cross-account mailbox selection.

`cs draft-delete` remains the separately named Gmail-only operation. Sent-mirror
cleanup acts only on an exact unique identity with unchanged, verifiable authored
content; edited or inferred copies remain for review. No review verdict deletes
a draft.

## Record an external delivery

The corresponding local engine candidate exposes `drafts.inspect`,
`drafts.discard_exact` (including guarded `dry_run`) and
`drafts.reconcile_external`. The last operation independently reads the selected
owner's Sent mailbox; caller-provided headers or inferred pairing are not proof.
It requires one exact Sent Message-ID, mirror ID/UID, recipients, thread and
content, and records the actual Sent identity/date with conflict-safe replay.
Recording an existing delivery does not authorize a new send.

There is no automatic reconciliation caller. Both selected hosted engines
expose the exact methods; real Sent recording, conflict-safe replay and guarded
retirement pass through authenticated runtime calls. The scoped kernel candidate
passes both-clone CLI acceptance, but maintained kernel packages retain their
public pin. Scheduled settings and launchers already deny the new mutations.

Real Gmail IMAP APPEND/replacement and owner-to-self SMTP preserve the custom
identity headers. Replacement-edit and stale-fingerprint refusal pass on both
mailboxes. These observations do not establish Gmail browser/mobile/API native
edit/send preservation or any Message-ID fallback; those remain unverified and
automatic reconciliation remains disabled. Release/adoption preparation and
precise evidence belong to the [live acceptance plan](execution-plans/2026-10-13-exact-draft-live-acceptance.md).

The Gmail folder identity read is non-consuming: checking UIDVALIDITY twice
retains the same selected-folder value. Sent subject comparison tolerates RFC
header folding while preserving internal text differences.

## Interactive completion and material updates

Interactive preparation compares immutable before/after material fields and
identifies exactly one new or changed engine row even when `updated_at` does not
advance. Ambiguous changes and unchanged results refuse without replaying
composition. RFC2047 decoding preserves subject text differences. Exact mirror
reuse requires complete plain MIME, no added attachments/alternatives or Bcc,
and unchanged owner, sender, recipients, headers and body.

After one successful interactive `draft-send`, the installed completion helper
requires the exact engine Sent row and one complete provider Sent message with
matching Message-ID, recipients, thread, subject and full MIME content. Only its
single unchanged review mirror is moved to Trash using UIDVALIDITY and fingerprint
checks. A complete fresh inventory must then prove its absence. Additional MIME,
changed headers/content, missing evidence or failed cleanup preserves a qualified
`delivered-but-cleanup-incomplete` result (exit5), explicitly forbidding a resend.
Scheduled routing and existing assignment/send approval guards retain their
current behavior. Native-client manual delivery reconciliation remains separate.
The [completion plan](execution-plans/2026-10-22-interactive-send-completion.md)
records source/installed tests and live-provider coverage limits.
