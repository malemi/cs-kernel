# Canonical contextual send

## Problem

`cs draft-reply` deliberately creates one logical reply in two stores: the
engine draft row and a Gmail Drafts mirror. An interactive assistant that also
has the Gmail app can send the mirror with Gmail's `send_draft` action. The
message then exists in Gmail Sent, but the engine row stays `status=draft` with
no `sent_at` or `sent_message_id` because the engine send lifecycle never ran.

This happened on 2026-09-15 for the Café 124 James Fryer reply. Gmail records a
native Gmail send at 17:56:21 UTC with Message-ID
`<CAJ1mzbGNjyvm+m8FyFTiCLO0bnxgwk-w77VvMzLA9Bppiw0SeA@mail.gmail.com>` and no
`X-Mailer`; the engine has no sent record and still holds draft
`452ddb83-69c9-479c-98ab-b6f690eab2a7`. The operator states that an interactive
assistant sent it, not a human using Gmail. The available assistant toolset
contains the Gmail-native `send_draft` action. Together these facts identify
the bypass as a Gmail-native send outside the engine. The exact connector call
is absent from the retained local session logs, so the evidence establishes the
path and failure boundary, not the individual tool invocation record.

## Intent

Give interactive operators one explicit contextual-send command that names an
engine draft and verifies the engine lifecycle completed. Make the stamped
operator charter unambiguous that Gmail/Superhuman/app connector send actions
must never send an engine-owned contextual draft.

## Scope

- Add `cs draft-send <engine-draft-id>` as the canonical interactive send verb.
- Require an exact engine draft ID, confirm the draft exists before sending,
  invoke only the engine's approval-gated `send_draft`, and verify afterward
  that the named row left the engine's `draft` state.
- Refuse when the engine did not request/receive exactly one `send_draft`
  approval for the named ID, or when the named draft remains sendable.
- Add the new verb to the headless cron deny surface in all command spellings.
- Stamp explicit guidance that contextual drafts are never sent through Gmail,
  Superhuman, or another ambient connector.

## Out of scope

- Removing the Gmail plugin globally; it remains useful for read-only mailbox
  work and its permissions are user-global, not repository-scoped.
- Changing Gmail's human Drafts workflow.
- Guessing that a stale engine draft was sent based only on recipient/subject.
  Reconciliation of externally sent mirrors belongs in the engine and needs a
  separate exact-identity design.
- Deploying or tagging a release in this change.

## Acceptance criteria

1. The command refuses a missing, ambiguous, or non-draft engine ID without
   contacting anyone.
2. The command's engine turn can approve only `send_draft` and names the exact
   full draft ID in its instruction.
3. Success requires an approval event for `send_draft` whose input carries the
   same draft ID and a post-send engine read showing the named row is no longer
   `draft`.
4. A model reply claiming success without the matching tool event fails.
5. Headless execution cannot reach the new verb.
6. Stamped docs explicitly prohibit ambient mail connector sends for
   engine-owned contextual drafts.
7. Focused regression tests cover success, mismatched approval, no approval,
   engine error, and postcondition failure.

## Material assumptions

- The deployed engine already requires `draft_id`, rejects missing/ambiguous
  handles, claims a draft atomically, and marks it sent after transport. Those
  invariants are covered in `mrcall-desktop` by the send-draft ID, approval,
  and double-send tests.
- `drafts.list` accepts a status filter; querying `status=sent` can establish
  the positive postcondition without relying on the engine mail archive.
