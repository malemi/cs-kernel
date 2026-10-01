---
status: active
---

# LLM recovery and owner alerts across the operator

## Current scope status

Scheduled Claude recovery is delivered under the separate
[cron recovery plan](2026-09-27-claude-cron-route-recovery.md), including
owner notices independent of an LLM. This does not complete this broader
plan: engine provider recovery and direct-classifier recovery require their
own implementation and acceptance evidence. No completion is inferred from
the successful scheduled-operator fallback.

## Milestone 1 — engine admission and provider recovery

Owner: engine (`mrcall-desktop/engine`). Close holds for proven direct/OpenRouter
no-work refusals, then try supported equivalent models through other saved
provider credentials. Keep the daily cap and proxy receipt requirement. Expose
the effective route and refusal reason; send a fixed owner notice on change or
complete failure. Test 402, alternate success/failure, ambiguous failures,
receipts and cap enforcement at the real dispatch boundary. Review this
milestone before dependent operator work.

## Milestone 2 — scheduled Claude Code recovery

Owner: `cs-kernel`. Wrap the existing stamped invocation without changing the
deny set, lock or pause behavior. Fetch one saved credential through the
owner-authenticated engine RPC and retry only a short pre-work quota refusal.
Apply a supported model fallback when an unavailable model is proven. Send
deduplicated fixed SMTP alerts on route changes or stop. Test fake-process
execution and rendered permission surfaces; review before the next milestone.

## Milestone 3 — direct classifier recovery and end-to-end review

Owner: `cs-kernel`. Apply the same bounded no-work fallback principle to
`worker_llm`: prefer an equivalent Claude model on another configured endpoint
before a measured classifier alternative, and rebuild the client with the
correct auth header for that endpoint. Keep send-guard refusal behavior and
independent billing. Persist alert deduplication in the clone state directory;
notify the owner when classification changes route or cannot run. Verify the
actual caller path, then review the three paths together using both maintained
clone manifests. No customer email is sent during verification.

## Delivery

Reconcile docs and plan state. Follow `docs/release-procedure.md` for version,
changelog, both-clone FULL collaudo and clone upgrade; do not push without the
operator's explicit approval. Stop and report if existing credentials cannot
support a tested alternate route. The daily engine cap is not raised by this
plan. Rollback is to remove the untagged changes or repin the previous tag,
leaving customer data and saved provider settings untouched.
