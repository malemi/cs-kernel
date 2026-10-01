---
status: active
---

# LLM recovery and owner alerts across the operator

## Intent

Keep the company operator working when a configured LLM provider refuses work
for quota or credits. Cover the three independent paths: Claude Code cron
reasoning, engine generation and judgement, and kernel direct classification.
Tell the clone's owner when any path automatically changes provider, changes
model, or cannot do its job. Recovery and notifications must use no LLM.

## Scope and constraints

- The cron wrapper owns Claude Code execution. The engine owns generation,
  judgement and its daily spending ledger. The kernel owns direct classifier
  calls. Each path needs a recovery decision at its own dispatch boundary.
- The engine's saved daily limit remains a spending boundary. A provider
  switch makes a new admission under that same limit. Exhaustion is reported
  to the owner, never silently interpreted as an empty work queue.
- Use the already configured OpenRouter credential from the authenticated owner
  profile for cron recovery. Engine and classifier fallbacks may use only
  credentials already saved for the clone/profile. Never print, persist, or
  pass credentials in command arguments.
- Retry only a provider refusal that proves no work was billed or performed.
  A cron tick that may have run tools must not be restarted. An ambiguous
  provider timeout or 5xx must not be repeated automatically.
- Preserve model capability and quality when changing billing transport.
  Any automatic model change needs an explicit supported fallback and an
  owner alert; an unsupported model stops with an alert.
- Preserve the existing cron permission denies on every attempt and the
  CS_PAUSE and lock gates.
- Send a fixed SMTP message to `Settings.email_address`, with `URGENT` in the
  subject. Engine notifications use the owner's own configured mailbox.
  Suppress duplicates across repeated failures, and report recovery.
- No company value or credential belongs in `cs/` source.

## Acceptance

The cron can use a configured alternate endpoint after an immediate quota
refusal, under the same tool restrictions. Engine and direct classifier calls
attempt another configured provider only after a provable pre-inference
refusal, with bounded attempts and normal spending admission. A successful
provider/model change and a complete failure each produce an `URGENT` owner
message without LLM involvement. Repeated ticks or calls do not flood the
mailbox. Tests cover the real dispatch boundaries and both maintained clone
renders; no customer send is part of verification.
