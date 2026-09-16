# Exact identity and lifecycle for mirrored drafts

## Problem

An engine-composed contextual reply currently exists in two writable stores:
the authoritative engine draft row and an editable Gmail Drafts mirror. The
copies have no shared durable identifier. `cs review` therefore pairs them by
thread plus recipient (or subject plus recipient for a new compose), while an
interactive mail connector can send or edit the Gmail copy without updating
the engine row.

This creates three separate failure modes:

1. one logical draft appears twice or is paired with the wrong alternative;
2. a Gmail-side send leaves the engine row `status=draft` and apparently
   sendable;
3. retiring a stale logical draft requires two unrelated handles and can leave
   the other copy behind.

The canonical `cs draft-send <full-engine-draft-id>` change prevents the normal
interactive operator path from causing mode 2. It cannot identify legacy
copies, reconcile a send performed by an ambient Gmail connector, or retire
both stores atomically.

## Production observation — 2026-09-16

A read-only Café 124 review found 5 rows in Gmail Drafts and 61 engine rows,
which the current heuristic paired into 63 logical drafts. Three Gmail rows
paired with engine rows; two were Gmail-only.

| Gmail UID | Recipient | Current evidence | Meaning |
|---|---|---|---|
| 975 | Edoardo Plateo | `superseded` | First of two alternative replies to the same old thread; a later mail was sent. |
| 977 | Edoardo Plateo | `superseded` | Second alternative reply to the same old thread; a later mail was sent. |
| 1018 | Dean Sahar | `overtaken` | The customer wrote again after this reply was composed. |
| 1049 | Edoardo Plateo | `ready`, Gmail-only | A new follow-up whose MIME body quotes the already-sent reply. Full-body similarity to Sent is 0.849, but the newly authored text is distinct. |
| 1051 | Custom124 | `ready`, Gmail-only | No engine handle exists, so current review cannot pair or retire an engine copy. |

The UID 1049 result is a critical negative example. Comparing whole Gmail
bodies approximately would call quoted history a duplicate. Exact duplicate
classification must compare the newly authored portion, or use a durable copy
identifier, rather than a similarity threshold over the entire MIME body.

The same audit found 1 exact delivered-body duplicate, 29 overtaken rows, 18
superseded rows and 15 ready rows across the 63 logical drafts. These counts
describe the mailbox at the audit time; they are evidence for the lifecycle
problem, not durable mailbox state.

## Required system shape

### Stable copy identity

When `cs draft-reply` mirrors an engine draft into Gmail, the message must carry
an opaque, exact identifier derived from the full engine draft ID. The first
candidate is an `X-CS-Engine-Draft-ID` header. Before relying on it, a live
fixture must prove that Gmail preserves it through Drafts editing and into Sent.
If Gmail removes it, use an explicitly generated Message-ID recorded on the
engine row and preserved by both transports.

`gmail_drafts.list_drafts` must return that identifier. Pairing uses it first;
the current thread/recipient heuristic remains only for legacy rows and must
label the evidence as inferred.

### Authored-body comparison

Gmail-only drafts need a bounded, read-only body fetch so review can inspect the
newly authored part. The parser must separate authored content from quoted
history using MIME structure and known reply delimiters. It must never use a
whole-body fuzzy threshold: UID 1049 proves that quoted Sent content dominates
such a score and creates a false duplicate.

An exact match of normalized authored content may yield `duplicate`. An
approximate match may be displayed as evidence for human review but must not
retire, suppress or relabel a draft automatically.

### External-send reconciliation

When Gmail Sent contains the stable copy identifier, the engine reconciler can
mark that exact draft sent with Gmail's Message-ID and sent timestamp. Recipient,
subject, date or body similarity are insufficient to mutate engine state.
Reconciliation must be idempotent and must refuse conflicting identifiers.

### One logical retire operation

Add an interactive, dry-run-first operation that accepts the logical row's
exact handles and previews both effects:

- move the named Gmail UID to Trash, recoverably;
- call `drafts.discard` for the exact engine ID.

Commit proceeds only when the expected Gmail and engine identities still match.
Partial completion must be reported with the surviving handle and a safe retry
instruction. Headless execution continues to deny both halves.

## Safety boundary

- Gmail Sent remains the authority that a message exists.
- The engine remains the authority for draft lifecycle and message meaning.
- No subject/recipient/body heuristic may write `status=sent`.
- No review verdict deletes or discards a draft.
- Existing mailbox cleanup requires a live human instruction naming the rows;
  this investigation performed read-only inspection only.

## Acceptance criteria

1. A newly mirrored Gmail draft exposes the exact engine ID on the next read.
2. Two alternatives in one thread never pair to the same engine draft.
3. A Gmail-side send with the preserved ID reconciles only that engine row.
4. Quoted Sent history never produces an automatic duplicate verdict.
5. The retire preview names both handles and commit cannot widen either selector.
6. A partial retire or uncertain send is loud and never invites a blind retry.
7. Legacy drafts remain visible with explicitly inferred identity.
