# Preserve executor prompt caching across long ordinary reads

## Intent and actual failure

Finish the existing executor-only MrCall/Cafe restoration without repeated cold
bootstrap billing. The immutable0.70.1 attempt is consumed and FAILED, not
resumable:23 reconciled responses cost8.0846050USD in usage-price estimates;
normal admission refused another request at soft8. Five required phases were
completed; whole workflow, Cafe and signup acceptance were not established.
The exact terminal and independent336-process/fixture/scheduling cleanup proof
live under /tmp/mrcall-ai-kit/pydantic-headless-20261028/bootstrap-cache-adoption-20261101/.

The explicit stable bootstrap cache point works on the rapid turns. Responses21
and22 have zero cache reads after request gaps1199.31s and551.84s, respectively;
each rewrites approximately375k tokens and costs1.88USD. Response23, after3.86s,
again reads357059 cached tokens. Configured TTL is5m. This supports expiration
as the investigation route; provider-internal eviction/routing state is unknown.
Do not claim the timing correlation alone proves the provider's initiating cause.
Before implementation, verify actual retained wire TTLs and stable prefix hashes
at those transitions. No inference request is needed for this diagnosis.

## Proposed result and scope

Add an explicit opt-in1h cache mode to the existing Pydantic executor, using
public pinned SDK configuration and CachePoint support. Preserve disabled and5m
behavior. Bind actual TTLs, model settings, provider wire, configured source
identity and independent acceptance evidence. All cache breakpoints must obey
the provider's longer-before-shorter ordering; prefer a uniform selected TTL.
No injected request mutation or model keepalive calls.

Account for supported1h cache writes exactly, including raw/SDK bucket agreement,
subset semantics and strict malformed/unknown usage rejection. Existing raw
cache-creation totals must never be counted twice with their1h subset. Require
complete explicit relevant pricing, conservative worst-case reservation and
canonical producer/consumer agreement. Never price1h writes as5m or infer an
undocumented fallback rate. The direct active model is claude-opus-5-5, whose
current official page lists input4/output20, cache read0.20,5m write5 and1h write8
USD per million tokens. Retain a dated source snapshot; other models/providers
need their own evidenced metadata or must refuse safely before paid submission.

Use normal prework fallback metadata and original job/attempt bounds; no new
fallback allowance, retry or bypass if1h metadata is unavailable. Determine the
smallest compatible supported contract in the plan before changing schemas.
The scope remains scheduled executor migration and its authorized kernel,
Desktop runner/transport/policy and two consumer clone paths. No IMAP/business
judgement, source authority, send permission, dedup, paging coverage, mailbox
content, prompts, SDK versions or models change. No site-packages/source override.

## Bounded authority and financial discipline

The operator explicitly authorizes finishing, dependencies and greater spending,
while forbidding token waste and supervisor communication. Adopt lead operating
ceilings of aggregate95USD, target10/hard18.25 per native job, signup2, and at most
one genuinely new sequential MrCall FULL -> Cafe FULL -> signup cohort after
reviewed free checks and admission. This is a budget adjustment, not permission
to weaken business, source, ownership, coverage or acceptance guards. No public
push, consumed-attempt retry/reset, unowned control changes or reserve release.
No paid admission occurs merely because this brief exists.

Independently verified committed basis is37.9204054 historical estimates plus
8.0846050 new native estimates plus8.012607 retained uncertainty =54.0176174USD.
A full worst-case new cohort18.25+18.25+2=38.50USD plans92.5176174USD: above85 by7.5176174,
below95 by2.4823826. Neither these estimates nor the prior reserve establish
invoice completeness. Refresh only newly consequential authorized accounting
coverage once before admission; preserve missing/external/classifier coverage.
Higher limits alone are not the correction:1h wire/pricing/accounting support
and a reviewed new immutable candidate are required before the single new run.

## Acceptance and verification limits

- Independently verified actual failure/cold-prefix evidence and honest unknowns.
- Real pinned SDK transport controls for both routes prove disabled/5m parity,
  selected1h breakpoints, consistent raw/SDK subset accounting and rejection of
  malformed prices/usage/TTL mismatches. A bounded delayed-turn cache model may
  demonstrate intended expiry economics, but is never provider savings proof.
- Semantic finance controls prove conservative reservations, cumulative ceilings,
  no double count and unchanged refusal/uncertainty/fallback ownership behavior.
- Fresh brief, plan and integration reviews; normal release/version/dependency
  identity procedure and full required suites once per actual changed candidate.
- New immutable normal installs on both clones, full166-or-current source
  inventories and complete lock/nonkernel provenance; no dependency churn unless
  demonstrated necessary. Private adoption only; preserve authored context.
- One new genuine bounded cohort, stop first failure, reconcile actual costs,
  provider effects and exact owned processes/fixtures/schedules. Initial ERRORs
  can recover; complete actual native/CLI and receipt predicates govern acceptance.
- Kernel/Desktop/clone documentation closure, explicit doc-critic, parentM5 and
  separate final review, then supported pinned-checker acceptance if its protected
  interface is available. Preserve exact4MiB inspect limitation and all failures;
  no synthetic closure, checker changes or repeated unchanged acceptance.

## Primary references

- https://platform.claude.com/docs/en/models/opus-5-5/overview
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://openrouter.ai/docs/guides/best-practices/prompt-caching

## Exclusions and rollback

Do not change model/provider identities to mask the expense, renew cache with
extra paid inference, drop required context or classify legitimate human holds
as repairable business failures. Roll back uncertain installation through normal
immutable package management before business work; after possible effects,
preserve uncertainty and clean only exact owned identities/nonces. On a failed
new cohort retain its result and diagnose a material change before any further
paid admission. Existing private tags and consumed attempts remain untouched.

## Dated finance checkpoint after framing approval

The one-per-clone normal engine accounting refresh at2026-11-01T20:58:34Z
adds0.025155USD endpoint spend (support3calls, Cafe0) to the pre-refresh basis
above. Current qualified committed54.0427724 plus38.50 plans92.5427724, leaving
2.4572276 below the lead-selected95 ceiling. Exact per-task attribution of the
endpoint delta remains unknown; it is included conservatively. Active reserves
are0 at both captured endpoints; stale holds remain unchanged and are not
released or counted twice. No invoice completeness or zero external charges is
inferred. Q/accounting-refresh/snapshot.md retains the finance-only verifier's
proposal wording; Q/authorization-admission-r1.json separately records the operator's actual
broad authorization and the lead's finite selected bounds. This checkpoint
changes no approved scope or business guard and grants no paid admission.
Here Q is the executor-long-cache-20261101 evidence root named by the plan.

## Admission-reserve sizing correction

The free verification admission-sizing-verification.md establishes that hard16
can refuse a1h request below the proposed soft12. For both retained primary
configurations, context1,000,000 and output8,192 give maximum reserve8.098304USD
at conservative input8/output20 per million. No output or coverage is reduced.
The revised target10/hard18.25 funds that maximum while spend is below10, with
0.151696USD additional headroom; the normal soft stop still applies at10 and
unknown primary reservations remain fully retained on fallback. Actual Admission
probes and exact arithmetic are in admission-sizing-alternative.md/json.

These limits supersede the earlier unadmitted12/16/34 proposal. The aggregate95
ceiling and one-new-cohort allowance remain unchanged. Maximum38.50 plus current
qualified54.0427724 gives92.5427724 and margin2.4572276. This is not a promise of
full-job cost/completion or invoice completeness. Preserve the earlier approvals,
authority record, source reviews and failed runs. No financial configuration or
paid admission is changed before fresh brief/plan review and the explicit R7
acceptance-scope prerequisite. This amendment is prepared outside K while the
exact tagged-state suite runs; apply approved canonical docs only afterward.
