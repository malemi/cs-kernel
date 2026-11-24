# Mailbox draft lifecycle

The Desktop engine owns draft reads and mutations. Gmail Drafts is the
editable resource for the mailbox candidate. Each current row has an opaque
owner-bound exact IMAP message handle and mailbox ID. Saved external edits can
replace the handle. List/read current drafts before an explicit send; a stale
handle never adopts another draft. Review reads `drafts.list` and computes
its verdicts from current correspondence, Sent and settlement evidence.
A failed list or incomplete row remains visible to discovery as a hold.

## Reply preparation

`cs draft-reply [intent] --thread-id ROOT --source-id SOURCE` invokes
`drafts.compose_reply` with mode `draft`. Interactive preparation
corroborates the inbound source and applies local SELF and suppression checks.
A person can use this path to request a review draft on a held thread.

An authorized send-mode launcher invokes `cs reply-send` with the same
source arguments and mode `send`. The generic launcher grants draft
preparation only. The engine checks assignment, the current conversation,
Sent and existing drafts before generating. Both modes preserve a draft
already present and hold a human-answered thread until another inbound arrives.
Direct send returns the verified Sent message ID without creating a draft.

Both reply verbs accept `--request-key KEY` and report the key used. Reuse the
key for the same operation. A local interactive binding stores the owner, key,
mode, thread and source ID. If the original source becomes unavailable,
recovery can address an engine operation already admitted for that request.
An uncertain send stays unconfirmed until exact Sent proof is available.
Preparation recovery reads the original native draft handle or its operation
Message-ID in Drafts; it never repeats a possible create.

## Named mailbox operations

A person can send a current draft with `cs draft-send HANDLE` or inspect
the target with `cs draft-delete HANDLE`. Add `--commit` to move the named
draft to Trash. Sending uses current recipients and body, including Gmail edits. Drafts with
attachments remain visible and trashable; unsupported attachment sending refuses
before transmission. Retry an uncertain operation with the same
operation ID (`--operation-id KEY` on `draft-send`). Missing or externally
sent drafts stay absent.

## Campaigns

Campaign authors supply `draft_request_key` with draft material in
`campaign.add_contact` and `campaign.update_contact`. The engine prepares
the mailbox resource and stores its handle in `dossier.mailbox_draft_id`.
The campaign queue reads that handle. Sending a named campaign draft requires
the guarded human path and verified Sent evidence. A retry first reads
`drafts.send_status` for the original request. Confirmation can complete after
the original message disappears, including when ordinary Sent dedup already
sees delivery. `drafts.send_status` observes only; explicit original-key send can
finish verified post-Sent cleanup without another SMTP submission. Preparing a fresh pack
for review supplies its rendered body, format and CC through the same campaign preparation operation; sending fresh fixed-template bulk mail uses
the existing SMTP sender.
