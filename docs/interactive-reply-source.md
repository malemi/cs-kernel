# Interactive reply source contract

## Availability and scope

This untagged kernel source adds the M1–M3 callers to main without replacing its
runner, native workflows or scheduled branches. Compatible engine services are
required independently; this document does not certify installed behavior.
The [integration plan](execution-plans/2026-11-06-interactive-reply-core-main.md)
owns source evidence and remaining acceptance. The published v9 bootstrap guard
is preserved. The [M4 collector binding](operational-diagnostics-source.md) has
its own integration scope; M5 workflow changes remain a separate follow-on.

## Prepare and resume one review draft

```bash
cs draft-reply 'Prepare the reply for review' --thread-id '<root@example.com>' --source-id ENGINE_EMAIL_ID --json
cs draft-reply --resume-draft FULL_ENGINE_DRAFT_ID --thread-id '<root@example.com>' --operation-id OPERATION_UUID --json
```

Interactive preparation corroborates the exact source against the owner's complete
mailbox evidence, supplies the source as untrusted correspondence, and permits no
send approval. It selects exactly one changed draft with matching owner, thread,
reply target and recipients. `supervised_review_draft_policy: 1` requires
`assignment_draft_policy: 1`. When the supervised capability is absent, the legacy
generic generation route remains explicitly human-review-only and its result is
checked locally; it is not server-enforced source scoping. Unknown versions refuse.

Publication requires `exact_draft_publication: 1` and an engine-owned operation
journal. Resume inspects the existing draft and reuses the named publication
operation instead of generating another reply. Saved engine text alone is not a
verified Gmail review copy. JSON reports achieved stages, operation identity,
effect certainty and next action; failed or uncertain publication returns 3.
Unknown APPEND outcomes require operation inspection, not another blind append.
Scheduled execution retains the main guarded legacy path and refuses exact resume.

## Send one exact reviewed draft

```bash
cs draft-send FULL_ENGINE_DRAFT_ID
cs draft-send FULL_ENGINE_DRAFT_ID --operator-request --operation-id OPERATION_UUID --json
```

Ordinary send retains the engine's single exact `send_draft` approval and contextual
policy. Interactive completion freezes the predispatch draft, checks the exact
engine sent row and complete bounded Gmail Sent MIME, then retires only its
unchanged exact Gmail review mirror. Missing, ambiguous, oversized or changed
material leaves cleanup incomplete. Exit 5 means delivery/verification/cleanup
needs inspection: do not retry sending. Scheduled completion retains its main path.

`--operator-request` requires `interactive_exact_send: 1`, authenticated owner and
exact inspection/snapshot binding. It checks pause, self-recipient and suppression
holds. Only a positively identified manual-member assignment can receive the
narrow send exception; peer conflicts, incomplete authority and other holds still
refuse. This does not mutate thread ownership or require the separate signed
assignment-mutation grant. Scheduled callers refuse this route.

A supplied operation ID first resolves the retained operation. Unknown delivery
must be inspected with that identity. A proven terminal `not_dispatched` outcome
is not permission to retry automatically: any later send is a new explicit
operation, with a new ID, after its cause is resolved. A confirmed send with
cleanup pending returns 5; held/unknown results return 3. No result authorizes
another delivery or broad mirror retirement.

## Retire one exact mirror

`cs draft-retire FULL_ENGINE_DRAFT_ID --gmail-uid UID --uidvalidity VALUE` previews
two effects on one exact pair. Commit must carry the unchanged preview's
`--gmail-fingerprint` and `--engine-snapshot`. Ordinary retirement first moves the
Gmail copy to Trash, then calls `drafts.discard_exact` to discard the engine row.
These effects are not atomic. An uncertain MOVE prevents the discard; a later
refused or uncertain discard can leave Gmail in Trash with the engine row still
present or its state unknown. Inspect the named stores before retrying; do not
repeat both effects blindly. Restore the Gmail copy from Trash when appropriate.

`--sent-mirror` instead selects verified-sent residual recovery, with the preview's
exact thread, operation ID and Gmail folder bindings. This route uses the engine
journal and retains the engine sent row. Both routes check exact
UID/UIDVALIDITY/fingerprint and use recoverable MOVE, never expunge. Neither route
sends or regenerates a draft.

## Boundaries still open

Local loopback/fake-provider tests cover publication uncertainty, resume,
retirement, send failures and admission. They do not prove current installed
engine pairing, native agent execution, real provider behavior or both ordinary
FULL clone obligations. No template workflow, main runner, operational package,
customer thread or account configuration is adopted by this source change.
