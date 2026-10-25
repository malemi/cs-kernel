# Actionable operator failure emails

## Intent and correction
The previous notice rewrite is locally complete but fails the user's acceptance: forwarding to an unspecified administrator is not a repair. Every notice must present symptom, evidenced cause, affected provider/account, repair and post-repair behavior.

## Scope
Scheduled operator notices only. Preserve execution permissions and the existing strict pre-work fallback gate. Add diagnostic classification independent of retry eligibility, bounded read-only account metadata, explicit provider/account/key identity and concrete provider/configuration actions. Capture diagnostic context in pending notices so later delivery refers to the failed attempt. Replace administrator referrals across every existing notice.

## Acceptance
- Primary credit/payment, authentication, quota/rate limit, provider outage, run-budget, turn-limit, watchdog and malformed/missing-result failures no longer collapse indiscriminately into unknown_failure when evidence distinguishes them.
- Never infer the payer from the operator mailbox or engine profile. Report a verified account email/org ID or masked credential identifier; identify unavailable metadata honestly and give an exact diagnostic command instead of inventing an account.
- Credit refusal differs from an observed exhausted OpenRouter key budget. Provider repair links are official and provider-specific; no advice to recharge the wrong provider or to raise unrelated engine budgets.
- For each stoppage, the mail says what failed, evidence, who/where, what exact action addresses it, and whether a later scheduled run is sufficient. Manual replay is not needed for ordinary account repairs; partial work is explicit.
- Configuration errors name the exact file/setting and current invalid/missing values; authentication repair points to the configured credential source. No fictional administrator or support address.
- Unknown causes include usable process/session diagnostics and a concrete local diagnostic action, explicitly acknowledging that a definitive repair is not yet known.
- Subjects retain proportional severity. Completed fallback notices explain how to restore the primary account without implying current work is blocked.
- Credentials, arbitrary tool/customer text and raw auth responses never enter persisted diagnostics or emails. Legacy queue entries still render, dedup remains bounded, and no paid/auth-mutating probe runs.
- Real child-process tests cover failure-to-email delivery with SMTP substituted, metadata failure, primary/backup identity, and unchanged no-replay eligibility. Final generated examples must be assessed for whether the recipient can actually act.

## Boundaries
Local implementation and verification only; no real email, payment, account mutation, release or clone deployment. The current environment includes concurrent draft-identity development; preserve it and test this change in an isolated baseline plus owned files. Existing message language remains English. Provider identity that cannot be verified is not a diagnosis.
