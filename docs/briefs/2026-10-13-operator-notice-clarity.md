# Clear scheduled-operator notices

## Intent
Make every operational email from the scheduled-operator supervisor understandable to a normal user: what happened, whether work stopped, what happens next and how to resolve a blockage.

## Scope
All fixed owner notices in `cs/operator_recovery.py`: primary recovery/model change, successful backup use, and every stop reason. Audit the notice inventory; preserve SMTP destination, permission checks, no-replay rule, queued delivery and deduplication. Retain useful technical identifiers below the user-facing explanation. English remains the existing notification language; localization and deployment are outside this change.

## Constraints
Never expose credentials or agent output. Do not invent a diagnosis, assert that no work happened on an uncertain failure, promise future completion, or tell users to bypass safeguards. No live sends, paid operator runs, release, clone upgrade or deployment.

## Acceptance
- Informational recovery/model-change notices and successful backup runs are not labelled URGENT.
- Every stop has an explicit stopped-run subject and an actionable remedy, distinguishing user actions from administrator actions.
- Backup success explicitly says this run completed; uncertain stops explain possible partial work and why immediate retry is avoided.
- Evidence-supported timeouts and limit windows have accurate descriptions; unknown failures remain qualified.
- Both plain text and HTML carry the same explanation; pending legacy notices remain renderable and dedup/retry semantics remain intact.
- Real child-process regression checks preserve no-replay, permissions, queue retry and recovery transitions. All notice reasons have checked severity and remedies.

## Assumptions
“All messages” means this scheduled-operator alert family, not campaign/customer emails. A stopped tick is an action-required notification, not proof that the entire engine or service is down. Use descriptive subjects rather than the blanket URGENT prefix.
