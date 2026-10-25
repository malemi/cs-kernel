# Operator reliability — analysis method and evidence sufficiency

Status: REJECTED by operator; brief-only. Owner: lead engineer. Date: 2026-10-23.

## Rejection — 2026-10-23

Operator rejected this brief. It describes log/evidence analysis abstractly but
omits the concrete prerequisite: inventory available logs, inspect their actual
contents/coverage, and establish how failed requests can be identified from
received correspondence, execution traces and observed outcomes. It assumes
concrete failed cases can be selected before establishing that capability.

The preceding adversarial review returned APPROVED but missed this framing gap.
That approval is superseded by the operator's rejection. This brief is not an
approved basis for investigation or implementation. Original text below is
retained as the rejected proposal, not a current approved method.

## Mandate / problem

- CTO reports: MrCall fails to send; Café fails to produce drafts; interactive-send-completion effort failed. Treat reported product failure as input, not disproved by component tests.
- Deliver an executable investigation METHOD before diagnosis or repair. Scope: cs-kernel + mrcall-desktop engine + actual maintained clone/runtime boundaries.
- Equal targets: (A) why owed work fails; (B) whether available evidence permits that question to be answered; (C) why previous verification failed to establish ordinary reliability.
- CTO reports insufficient diagnostic information. Treat insufficiency as an explicit concern to measure, not a completed finding about particular missing signals.
- Lead owns technical decisions, evidence gathering design and conclusions. Do not route engineering investigation/testing to CTO.

## Scope / non-goals

- IN: investigation protocol, evidence contracts, sampling, falsification, observability assessment, bounded experiment design, decision criteria.
- OUT now: operational diagnosis, implementation, instrumentation deployment, model/prompt changes, live calls, paid runs, real sends, cron/service changes, release, baseline advancement.
- This brief grants no runtime authority. Subsequent investigation/experiments require their applicable scope and controls. Existing permissions are not inferred from historical test records.
- Separate paths: MrCall interactive send; MrCall scheduled send; Café scheduled draft. Shared cause is a hypothesis. Success on one path does not certify another.
- Root docs identify routing/contracts; their current-runtime claims require evidence. No ambient archive/plan ingestion. Read historical bodies only for a selected case/comparison.

## Required method

### 1. Independent expected outcome

- Unit = exact request revision, not log entry / command / whole tick.
- Establish from original correspondence + authoritative company instructions: owed action, valid abstention conditions, expected destination/content, completion deadline.
- Do not derive eligibility solely from the classifier under investigation. Ambiguous business expectation stays unresolved; exclude from definitive success/failure denominator until resolved.
- Identify original by owner + RFC identity + provider identity + revision/body commitment; preserve mappings to root/task/draft/run/RPC identities.

### 2. Actual execution topology

- Capture actual launcher/job, process/start identity, imported package/resource hashes, effective instruction/permission/configuration versions, target engine/profile/capabilities and relevant peer services.
- Distinguish checkout / installed package / loaded process. Record overlays and unknown provenance.
- Map provider mail, operator reasoning, engine generation and direct classifiers separately; each has its own auth, budget, deadline and pause boundary.
- Freeze an observational baseline; detect concurrent changes. Do not silently alter runtime to obtain a cleaner case.

### 3. Request-level causal trace

`provider receipt -> engine acquisition -> discovery -> selection -> authority -> context delivery -> generation -> engine persistence -> provider draft/send -> independent effect verification -> terminal state`

- Branches/repeated stages explicit; absence of an event is not proof of nonexecution.
- Per transition: request/run/attempt IDs; component identity; input identity/freshness/completeness; decision + reason + source; output/effect identity; timestamps/duration; retries/cancellation; cost or cost-unknown; evidence pointer.
- Locate first divergence between independently expected transition and observed transition. Last exception is not automatically root cause.
- Distinguish attempted / accepted / persisted / provider-visible / recipient-received / verified. Timeout does not prove cancelled or unsent.
- Track deferred work across ticks: age, selection history, reconsideration trigger, recovery condition. Detect starvation and indefinite holds, not only exceptions.

### 4. Evidence sufficiency / analysability audit

- Before causal verdict, build matrix: question -> necessary observation -> current producer/store -> correlation keys -> retention/access -> observed coverage -> gap -> inference prohibited by gap.
- For each boundary ask: can we distinguish not invoked / invoked but denied / running / failed / completed with lost response / effect completed but verification failed?
- Assess: missing events; swallowed exceptions; generic errors; missing reason provenance; truncated model/tool context; unjoined IDs; unordered clocks; stale snapshots; overwritten logs; missing package identity; inaccessible/expired evidence; unrecorded retries and costs.
- Verify diagnostic claims against actual retained bytes/records in subsequent investigation. File existence or logging code alone proves neither emission nor useful coverage.
- Separate model-visible context from retained payload; neither proves model understanding. Agent explanations are observations, not causal proof.
- Deliver per-boundary rating: SUFFICIENT / PARTIAL / ABSENT / UNVERIFIED, with the exact questions answerable and unanswerable.
- Missing evidence yields UNDETERMINED, never invented cause. Identify smallest additional observation that would distinguish remaining hypotheses.
- If existing evidence is insufficient: propose a bounded instrumentation specification as a separate future change, with question, fields, emission point, correlation, retention, privacy, overhead and verification criteria. No instrumentation implementation authorized here.
- Diagnostics must not expose credentials or indiscriminately duplicate customer content. Retain private originals when necessary; reference commitments/IDs in shared reports. Hashes establish identity, not semantic correctness.
- Assess observer effects: diagnostic reads may cost money, mutate flags/state, consume streams or change timing. Classify before using them.

### 5. Competing hypotheses / minimum experiments

- Hypothesis record: observation explained; causal mechanism; predicted discriminating observation; falsifier; alternative explanations; least-cost experiment; authority/risk; time/cost bound; stop condition.
- Evidence order: retained runtime/provider records -> offline deterministic replay -> bounded read-only observation -> separately scoped live experiment if indispensable.
- Change one explanatory variable where feasible; document confounders where not. Preserve failed evidence unchanged.
- No identical paid retry without new evidence; no budget/deadline expansion to manufacture success; no fixes during initial failure capture.
- Mechanism confirmed by convergent trace/reproduction or controlled discrimination; correlation alone remains qualified. A future repair is not prerequisite for reporting an evidence-supported diagnosis.

### 6. Verification-system audit

- Compare tested path/environment/data/permissions/candidate with ordinary path. Review the failed completion plan and only relevant retained runs during investigation.
- Independently distinguish PRODUCT_OUTCOME, CHECKER_OUTCOME, EVIDENCE_QUALITY. Checker is fallible; false pass and false fail both possible.
- Component tests, reviewer approval, exit zero, empty work queue and historical signed PASS do not establish current owed-work completion.
- Check synthetic fixture representativeness, special enrollment/handling, manual preparation, skipped stages, failed-case exclusions and candidate drift.
- Historical success is a comparator only with known code/config/data/path differences. Do not transfer its certification to current runtime.

## Sampling / measures / boundedness

- Initial localization sample: at least one concrete reported failure per affected path; matched success if available. If no retained case exists, record the gap; do not fabricate or silently trigger a new case.
- Expand by distinct failure mechanism/path, not by accumulating similar logs. Include eligible actions and legitimate abstentions; inspect a bounded consecutive time window to avoid cherry-picking.
- Reliability requires independently adjudicated denominator: eligible request revisions, correct completions within agreed time, false holds, omissions, unsafe/duplicate effects, human interventions, latency and cost distribution.
- Separate unavailable evidence from product failure counts; publish exclusions and uncertainty. Small localization sample cannot establish a reliability rate.
- Before execution: fix case/window limits, wall-clock and paid budget, authorized observations, checkpoints and stop rules in the investigation plan. No unattended open-ended loops.
- Stop a branch when mechanism is supported, necessary evidence is unavailable, authority is missing or limit reached. Continue useful independent branches within the same bounds.

## Deliverables / acceptance

1. Actual topology for three paths, version/authority boundaries and explicit unknowns.
2. Case ledger + joined transition traces; first divergence, observed effects and independent expected outcome for every selected case.
3. Evidence-sufficiency matrix covering every transition; concrete gaps and smallest proposed observations; explicit list of conclusions impossible today.
4. Hypothesis ledger with supporting/refuting evidence, remaining alternatives and bounded experiment specifications.
5. Verification-gap assessment: what previous proofs established, what they did not, why ordinary failure could escape detection (or why this remains unknown).
6. Recoverability assessment: demonstrated localized defects vs evidence-supported structural constraints vs unresolved questions; assess required latency/cost/human intervention. Do not claim impossibility or feasibility without support.

Method accepted only if another engineer can identify what to inspect, how to correlate it, what falsifies each explanation, when to stop, and what evidence would justify a later repair/reliability claim.
No completion claim from narrative alone. This brief's completion is the reviewed method, not recovery of either operator.

## Routing references

- Kernel: `docs/kernel-charter.md`, `docs/operator-runtime.md`, `docs/draft-lifecycle.md`, `docs/task-assignment.md`.
- Desktop: `../mrcall-desktop/AGENTS.md`, `docs/cross-cutting-contracts.md`, `docs/operator-operational-testing.md` (latter two relative to Desktop).
- Selected failed work: `docs/execution-plans/2026-10-22-interactive-send-completion.md`.
- Known startup constraint: that plan uses unsupported status `failed`; mechanical gate blocks source work. Preserve failure semantics; any metadata correction is separate from this brief-only artifact and must not imply success.
