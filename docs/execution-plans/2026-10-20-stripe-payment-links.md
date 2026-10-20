---
status: active
---
# Explicit Stripe Payment Links

Approved brief: ../briefs/2026-10-20-stripe-payment-links.md. Brief review: /tmp/stripe-payment-links-20261020/brief-review.md (APPROVED).

## Ownership and dependencies

Lead owns shared kernel CLI, canonical skill, permission denies, integration, documentation and delivery. A bounded engine worker may own only Stripe provider/operation/RPC implementation and focused tests in an isolated Desktop worktree. Both candidates start from fetched origin/main; preserve all unrelated shared-checkout work. Runtime activation depends on current owner clearance and complete deployed root composition; it is independent of source delivery.

## M1: engine operation

Add stripe.payment_link_create(amount_minor, label, request_id), EUR only, positive integer cents, bounded nonempty label and opaque stable request identifier. Add a separate capability flag. Existing reads and six probes remain unchanged. Fixed form POST /v1/prices creates one-time EUR price using product_data[name]; POST /v1/payment_links uses that price and quantity one. No recurring, customer or send fields accepted. Safe errors identify required write permission without exposing Stripe bodies.

An encrypted private operation journal binds request id and payload hash to owner/company/account/mode/generation. Persist started time before writes, price id after its response and complete minimal result after link response. Deterministic per-stage idempotency keys resume identical requests; payload conflicts refuse. Unresolved operations older than 23 hours refuse; successful results remain reusable without HTTP. Use short filesystem locks and an async operation lock; never hold a synchronous lock over network await. Recheck account identity and authority/session/generation before writes and after responses. Network failures retain resumable pending state; identity changes prevent subsequent writes and completion claims.

Focused deterministic tests cover HTTP construction, positive/invalid amounts, unsafe inputs, binding changes, permission errors, two-stage timeout recovery, repeated calls, conflicting inputs and stale pending refusal. Review integrated M1 before dependent CLI integration.

## M2: operator distribution

Add cs stripe payment-link-create --amount-minor --label --request-id. Validate exact returned account/mode/generation, amount and currency; deny CS_OPERATOR_HEADLESS in both typed and raw CLI dispatch before opening RPC. Update existing canonical cs-stripe skill with explicit human-request flow, stable request-id retries and minimal write permissions. Add specific mutation ASK rules for all six launcher spellings to canonical Claude settings (taking precedence over broad RPC allow), and independent DENY rules to the cron wrapper. This allows explicitly requested interactive use; preserve existing rules. Textual host rules do not constitute a universal sandbox. Render and test all three supported hosts and CLI refusal. Do not replace installed clone package overrides or restamp unrelated files.

## Verification and delivery

Run focused Stripe engine and kernel tests plus relevant RPC/permission/render tests; run required free suites proportional to affected contracts. No paid model acceptance, real charge, browser install or Desktop UI rebuild. Invoke doc-end, reconcile affected durable docs, mechanical gate and fresh doc-critic; obtain separate final review. Commit only owned changes in each repository and push reviewable source delivery. A new public tag and broad runtime acceptance are outside this task; report installed activation separately.

## Activation and rollback

Before any activation, obtain primary-owner clearance for an exact complete candidate composition and verify global jobs, WS/CAS and cron guard. Cafe root currently operator-import-preview-a0068ca2d3af, PID3953282; preserve its entire manifest, interpreter and managed company DB/authority. No idle assumption from owner messages. Capture only owned deployed files and service binding. If unavailable, finish source delivery and retain activation as an explicit blocker. Roll back only owned artifacts; report external provider IDs and never silently delete/recreate them.

## Evidence

Brief/plan and engine/kernel integration reviews APPROVED. Engine Stripe fixtures pass20; combined Stripe/RPC contract fixtures pass46; CLI/distribution fixtures pass9. Full kernel free suite passes all gates after exact scheduled-policy regression expectations were updated and reviewed. Source commits: Desktop1a8938d9, kernelb360b47. Runtime staging preserves the complete current owner root plus five Stripe files; clone staging adds only the raw headless guard, canonical Stripe skill and exact permission/cron delta with matching ledger entries. Actual installed state is established only by the retained activation-result.json and authenticated readback in /tmp/stripe-payment-links-20261020, not by these fixture checks. No real Stripe objects or charges are created by acceptance. Public tag and installer release remain separate.
