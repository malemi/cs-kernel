---
status: active
---

# Recover a scheduled Claude Code tick after an immediate access refusal

## Why

The maintained clone's scheduled wrapper runs `claude -p "/cs-operator"` once.
On 2026-09-27 its log showed `You've hit your weekly limit` before any operator
work, followed by exit 1 on repeated ticks. The engine's selected provider is
independent of Claude Code, so its configured alternatives do not rescue this
process. The owner receives no automatic notice.

## Intended outcome

Keep the current Claude Code harness, skill, and draft-only permissions. When
the primary Claude process demonstrably refuses access before executing a tool,
run at most one fallback Claude process through a configured alternate billing
route. Notify the clone owner with a fixed `URGENT` email when the effective
provider or model changes, or when the tick cannot run. Route selection,
classification of failures, SMTP and deduplication use no LLM.

## Scope and constraints

- This work covers the scheduled Claude Code wrapper and its supporting kernel
  code. Engine generation and kernel direct-classifier recovery remain separate
  work in the broader operator LLM recovery brief.
- Preserve `CS_PAUSE`, the non-overlap lock, headless mode, and the exact
  command deny set on primary and fallback attempts. A fallback must not change
  customer-send authority.
- Recognize only explicit access/quota/payment refusals proven to occur before
  tool execution. An ambiguous failure, timeout, or any sign of tool activity
  ends the tick without replay. Do not infer success from exit code alone.
- Use an already saved alternate credential from the authenticated owner
  profile. Resolve the owner address, mailbox credential and state path through
  `Settings`; no company literal or credential goes into kernel source, logs,
  command arguments, prompts, or alert content. Determine whether Claude's
  child tool processes inherit the credential. If they do, document that
  access and rely on the bounded provider key rather than claiming isolation
  the launcher does not provide.
- The observed alternate is OpenRouter. Its current key reports a $20 daily
  limit, shared with any other use of that key. The engine daily budget does
  not govern Claude Code. Require an explicitly configured per-tick budget
  guard on the paid fallback; absent or invalid configuration refuses fallback
  and alerts. The provider's key limit remains the final daily spend boundary.
  Do not claim a saved key proves available credits or model compatibility.
- Prefer the same supported Claude model on the alternate route. If the model
  changes, record the effective model in the owner notice. Do not silently
  substitute an untested model or a weaker capability.
- Send fixed plain-text SMTP from the clone mailbox to its owner address,
  independently of the agent. Deduplicate repeated identical failures, but
  report a recovery or a different effective route. If SMTP fails, preserve a
  visible local failure record and exit status.
- The fallback must work without changing the interactive Claude login or
  leaving the alternate credential in a persistent Claude settings file.

## Acceptance

1. A simulated immediate weekly-limit refusal leads to exactly one alternate
   Claude invocation, with the same skill and command denies. A successful
   switch emits one `URGENT` owner alert using no LLM.
2. A refusal after any tool execution, an ambiguous transport error, or a
   non-quota program failure never replays the tick. When no safe route exists,
   the owner receives an `URGENT` failure alert.
3. Repeated failed ticks do not flood the mailbox. A later return to the
   primary route or a new failure state is reported clearly.
4. Tests inspect the rendered wrappers for both maintained clones and exercise
   the real wrapper/helper boundary with fake processes and SMTP. No customer
   email or paid model call is part of automated verification.
5. A supervised, draft-only live check establishes actual Claude Code gateway
   compatibility, effective model, tool restrictions, child-process credential
   exposure, budget behaviour and owner alert delivery before any cron
   installation.
