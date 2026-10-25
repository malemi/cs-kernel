# Ordinary operator discovery and health

## Intent
Restore ordinary scheduled drafting when unrelated conversations have incomplete authority, and notify the mailbox owner when technical failures prevent the operator from working. A clean model terminal is not sufficient proof of a healthy tick.

## Evidence
On 2026-10-15 all Café scheduled runs report zero drafts, clipped discovery output and missing optional acceptance capture. The 14:00 UTC run returned process exit zero despite SOURCE_UNAVAILABLE/timeouts. The 15:10:42 UTC user test is synchronized and its current peer-merged authority is complete NORMAL/unheld. Café runs every two hours, not immediately upon receipt.

## Scope and constraints
Use existing kernel discovery, supervisor and owner-notice infrastructure. The owner explicitly requires symbolic/deterministic monitoring and alerting: no LLM dependency or paid model call for health assessment, failure notification or delivery retry; credit/quota exhaustion must still alert. No-work and technical outcomes must be determined from typed execution evidence, never natural-language summaries. Make complete discovery readable in ordinary runs, without pretending capture proves inspection. Detect missing/malformed/incomplete required execution evidence and technical mailbox/authority failures independently of agent prose. Distinguish legitimate human assignments and an empty work queue from technical failures. Preserve exact-thread guards and allow independently complete work; never clear unknown authority globally. No new send grants, retries, source classification heuristics, automatic reconciliation, public release or unrelated engine changes. Keep existing protected acceptance evidence behavior intact. Local installed adoption must preserve preimages and unrelated work.

## Acceptance
- Large ordinary discovery can be inspected fully through a bounded normal path without test-only enrollment.
- A model exit-zero with missing/clipped discovery or technical discovery/authority failure produces nonzero unhealthy status and an actionable owner alert; no automatic replay.
- Empty queues and valid human holds do not falsely report technical failure.
- Notice delivery failures remain queued and visible; repeated identical failures deduplicate and genuine recovery is reported.
- Focused semantic regressions and required checks pass. Verify the installed Café path and actual SMTP owner-alert acceptance; establish mailbox delivery read-only where available.
- Continue the already authorized two-address test without sending customer mail. Report manual generation separately from ordinary scheduled acceptance.

## Assumptions
The owner explicitly requested repairing this failure and receiving an alarm. Existing mailbox-owner notice routing is the initial delivery target. General provider reliability and arbitrary customer workloads remain outside a single test's proof.
