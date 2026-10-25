# Deterministic source handles for exact-thread draft composition

## Intent and observed problem

Finish the authorized engine-workflow ordinary path without asking the operator to find or re-enter an already authenticated message. Original C35 is FAILED. Its exact owner-scoped emails.list_by_thread read returns the original email UUID and body. Ordinary draft-reply receives only the RFC root; the scoped engine embeds that root and intent without ordinary ChatService email context. The model then guesses unsupported textual thread_id search syntax, finds nothing and creates no draft. This is an observed context-routing omission, not a missing synced message or permission question.

## Chosen scope and ownership

Kernel owns the normal exact-thread cmd_draft_reply path in cs/cli.py and focused tests. After the existing scheduled workset and assignment admission, resolve source handles through exactly one normal authenticated emails.list_by_thread read for the unchanged requested thread. Validate the existing response schema, finite row/identifier bounds and canonical internal UUIDs, reject duplicates/empty/malformed/oversized responses and read errors before generation. Supply all returned validated handles as a deterministic bounded list in the compose instruction, with explicit existing read_email guidance. Do not copy message bodies, infer a latest message or answer, select a different actor, guess an alias, retry/search, or use local/provider caches. Keep exact thread and original caller intent.

Returned handles are source context only. This RPC matches authenticated owner/active mailbox and exact stored thread_id; it does not prove canonical RFC-component completeness/current-inbound authority. Aliases with no exact stored rows stay held. Engine admission, scoped read/write transaction checks, owner/root/route guards and separate exact-ID send remain authoritative. No caller handle or prompt can bypass them. Preserve capability negotiation and the stronger explicit --source-id contract; do not drop/transform supplied contextual bindings. Preserve general chat and source-free behavior outside ordinary exact-thread draft-reply. No new RPC/API/model permission, source-body logging, raw answer injection or engine restart is included.

Source changes may coexist with the separately reviewed Actor lifecycle-envelope counterpart. Actual installed CLI must retain its own baseline: current source CLI has unrelated Stripe imports absent from installed packages. Render only the approved cmd_draft_reply/helper delta onto the actual installed CLI, preserving every other byte/function and the earlier approved cmd_rpc search-exclusion delta. Independently review the rendering and full installed payload. Do not install the whole source CLI or alter user Stripe work.

## Acceptance

1. Meaningful free regressions invoke actual cmd_draft_reply with a neutral exact RFC root absent from searchable subject/body fields, capture the authenticated read and compose instruction, and prove valid UUID handles are supplied before generation without bodies/answers. No model/provider request is needed.
2. Empty, duplicate, malformed, foreign-shaped, oversized or failing reads produce zero chat/mirror/send calls. Existing scheduled workset/assignment holds and explicit contextual capability refusals still happen before generation; original root/intent and all fresh prewrite/premirror guards survive.
3. Integration uses the existing guarded engine route and actual read_email tool with local fixtures to establish source-handle consumption while wrong-owner/thread/held/concurrent-assignment writes still refuse. No fabricated model answer substitutes for later operational acceptance.
4. Relevant caller/CLI/assignment/draft suites and actual rendered CLI help/import checks pass. Fresh source/rendered/installed approvals precede any paid repeat.
5. One combined fresh unchanged strict ordinary same-case acceptance proves actual MrCall reply received independently, usable Cafe provider-visible draft, signup, ACK/no-extra-effects and full terminal cleanup. Original5400/4200/2700-second bounds and USD4 soft native limit remain, with separate engine/classifier billing and no aggregate guarantee. Never retry a known free failure.
6. Reconcile affected durable/living docs and complete critic/final/checker closure. Preserve original C35 FAILED evidence. No commit, push, release or installer publication.

## Constraints and evidence

No engine source, credentials, provider data, permissions, cron, billing/pause settings or unrelated package baseline changes. Runtime activation uses the existing independently reviewed outer transaction after new candidate free validation; all seven service bindings, clone aliases/ledgers and unrelated resources remain preserved. Exact source/journal diagnosis: /home/mal/.local/share/mrcall-workflow-evidence/2026-10-18/c35-composer-diagnosis/report.md. Existing historical tasks remain intact; this is a new bounded kernel task.
