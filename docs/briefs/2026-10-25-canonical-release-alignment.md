# Canonical kernel release and reproducible clone alignment

Date: 2026-10-25. Owner: lead engineer.

## Intent

Both maintained clones must execute the same identifiable released kernel.
Installed Python or packaged resource edits outside the declared release are
unacceptable. A version string or requirements pin alone is insufficient proof.
The operator authorizes inventory, recovery of valuable installed changes into
canonical source, reviewed implementation, release publication and installation
through completion. Existing customer data, authored company configuration,
mailbox state and uncertain business effects must be preserved.

## Scope and constraints

Inventory every installed package file, distribution origin and declared pin on
both clones against the declared tag and canonical working source. Preserve exact
preimages and classify installed-only differences before replacement. Integrate
intended kernel changes through reviewed canonical source, never by copying files
into installed packages. Preserve the original dirty tree and concurrent work;
use an isolated release worktree if needed. Do not discard unknown deltas or
silently certify unfinished historical business acceptance.

The logging assignment and its existing plan remain open dependencies. Its
ACCOUNTING diagnostic continuation was reviewed but implementation was interrupted;
record actual pending state and include only reviewed, verified source in the
release. Existing tag v0.53.0 is immutable; verify its remote identity and choose
the next appropriate unused MINOR for changed CLI/configuration surfaces. Do not
reuse a release number merely to match the operator's initial assumption.

No direct site-packages overlays, public tag rewrites, credentials disclosure,
arbitrary mailbox replay or customer sends. Required FULL acceptance must use
approved protected test fixtures and retain real provider/engine evidence; a
missing safe fixture or authority is a concrete gate, not a reason to waive it.
Routine technical mail remains disabled and diagnosis stays manually invoked.

## Required result

- An exhaustive machine-readable inventory accounts for installed deltas and
  identifies which canonical changes preserve each required behavior.
- The release candidate passes the complete kernel harness; pre-existing failures
  cannot be carried through a release that requires green checks. Repairs preserve
  intended semantics and independently verify stale-test explanations.
- Package integrity has an operator-visible verification route that checks actual
  installed bytes and unexpected packaged files against immutable release content,
  beyond trusting version text or a locally rewritten RECORD alone. Drift is
  diagnosed explicitly; verification never repairs installed bytes in place.
- A reviewed immutable release is published according to release-procedure.md.
  Both clones install that tag through the supported package/update mechanism,
  regenerate consistent locks and version claims, and preserve authored settings.
- Independent final checks prove matching release identity, expected kernel and
  resource bytes, no unexplained package deltas, relevant two-clone acceptance,
  maintained technical-mail suppression and unchanged business authority.
- Durable docs explain release-only adoption, integrity checks, incident handling
  and how to improve insufficient logs. doc-end and separate final review close
  actual evidence; remaining historical limits stay explicit.

Rollback uses complete captured environments or a separately released known-good
package and its truthful pin. It never applies a hidden file patch, deletes logs,
restores stale business data or retries uncertain work.


## Required dependency: exact RFC identifier representation

The retained create_draft failure has a precise representation mismatch:
thread_id,in_reply_to and references contain HTML-escaped RFC identifiers, while
the trusted scoped root is literal RFC syntax. The existing exact-root guard
correctly refuses the unequal thread operand before storage. The tool's owner_id
comes from authenticated construction, never a model argument; an owner mismatch
is not established by this evidence. Which model/transport introduced escaping
remains unknown. Repeating the root in prompts is not a deterministic repair.

The smallest necessary compatibility dependency is an engine-owned argument
adapter before the unchanged owner/root/reply-header guards. Normalize only a
single, unambiguous HTML-escaped RFC identifier representation in thread_id,
in_reply_to and references. Preserve literal identifiers and supported opaque
provider IDs. Never infer or fill missing scope, select another root, change
identity order, or decode body,subject,recipient or unrelated fields. Foreign,
absent,malformed,ambiguous or doubly encoded identities must remain refused;
canonicalization grants no owner,assignment,source,approval or send authority.

The required free acceptance exercises canonical engine code through the real
argument/guard/storage seam with controlled external boundaries and no SMTP:
encoded/literal same-root equivalence, correct stored literal identities, trusted
owner construction, unchanged content/recipients, opaque-ID preservation and
foreign-owner/root,missing-root,malformed,double-encoding and changed-header
refusals. Include a nearby genuinely different identity; never substitute the
trusted root for a mismatched input or synthesize a successful business outcome.
Preserve the original failed trace and uncertain effects; do not replay it.

Actual adoption, if authorized by the existing scoped engine-delivery mandate,
is limited to the TWO actor engines used by these maintained clones. Use reviewed
canonical source and an immutable preserved source family, exact prior-source
preimages, fresh complete actor baseline/delta/deployment bindings and an updated
hosted manifest. Preserve the four peer engines,Qonto,credentials,mailboxes,
company rules,budgets,permissions,technical-mail suppression and runtime controls.
No direct site-packages edit,unsupported source overlay or unreviewed host patch
is a delivery route. Any required affected-service restart belongs explicitly
in reviewed adoption/rollback; unrelated running services remain untouched.

Fresh brief and plan reviews precede implementation and adoption. Source proof
must be concrete before the deployment-authority/risk gate. The reviewer must
identify the existing authority for the exact actor change; if that authority
cannot be established or material operational risk is unresolved, actual hosted
adoption is BLOCKED while authorized free implementation/verification proceeds.
This brief does not invent that authority or waive any release/native gate.

Successful free encoding tests do not establish live adoption,SMTP success,
Gmail behavior,57FULL or publication. Fresh installed two-clone preflight and
strict genuine FULL remain mandatory after the reviewed hosted composition is
actually loaded. The frozen57kernel requires no new kernel workaround for this
engine representation bug. Existing plans own ordered execution and closure.
Private evidence: create-draft-argument-wiring.md and
v56/create-draft-argument-proof.json under the existing release-alignment root.


## Source-evidence repair dependency

The genuine57attempt sent its protected reply successfully but failed whole-tick
health on two actual source-correspondence defects. Lower-level readonly probes
in the actual service mount namespaces establish a support Sent source with9
provider References versus0stored, and one genuine peer Sent source absent from
its owner/mailbox archive. Probe-only DNS/login failures outside those namespaces
are refuted as production causes. Preserve the original failed case.

Repair only these two provider-backed archive records through existing native
fetch/conversion/storage code after exact owner/mailbox, RFC hash, UIDVALIDITY,
UID and nondraft checks. This is acquisition of actual mail evidence, never
assignment creation, closure, manual SQL, guard relaxation or replay. Preserve
existing row identities and processing/business fields; the newly acquired Sent
record remains subject to normal downstream handling. No new sync API, broad
resynchronization, peer code deployment, source patch or model call is authorized
by this dependency. Prove the selected native storage path is model-free before
execution; otherwise stop and reassess. Retain private preimages and per-field
delta evidence, and verify actual guarded projections independently afterward.
No passing projection, new FULL or publication is presumed from source repair.


For the existing support record, an explicitly reviewed, one-off conditional
update through the native Email ORM/session is permitted when the existing
whole-row storage operation cannot preserve concurrent changes safely. Its
only assigned business column is References, sourced from the exact verified
provider message; exact owner,mailbox,rowID,RFCID and original References are
mandatory predicates and affected rowcount must be1. Native updated_at may
advance. No raw SQL, fabricated header, source patch, content/state/identity
rewrite, general repair API or recurring job is permitted. Retain private
preimage and prove every other column is unchanged; refuse concurrent References
changes. This bounded maintenance exception is not assignment/send authority
and does not waive any independent projection or FULL gate.


For the absent peer Sent record, the same bounded maintenance exception permits
a plain native Email ORM insertion built from the existing native provider
conversion and native storage-record expression, with cached local embedding.
The native owner/mailbox/RFC uniqueness constraint must refuse a concurrent
insert and roll back; never run ON CONFLICT UPDATE or overwrite an existing row.
This exception assigns only actual provider-derived fields and normal native
model defaults; it neither fabricates an assignment nor changes an existing mail.
Persist the complete selected postimage immediately after either mutation, before
validation assertions, so failed verification retains actual effects.


## Required dependency: bounded ACTOR provider cleanup with R8 safety

This is substantial engine behavior work and requires fresh brief approval,
then an amendment to the existing plan and fresh plan approval before source
implementation. The kernel 57 candidate remains frozen. The actual ACTOR
observation closes its guards before disconnect; provider_deadline then cancels
its timer and restores the 120-second command timeout before logout. This is a
concrete cleanup deadline escape. It does not establish the historical cause
of the interrupted 57 attempt or explain its 15 unknown results. The independent
same-root native read completed normally in 37.584 seconds; neither observation
establishes executor occupancy or the failed request's actual cleanup stage.
Retain the failed attempt and uncertain backend/effect state without replay.

Preserve the R8 safety contract documented in Desktop's task-assignment feature:
provider/projection guards must finish their socket checks before disconnect
closes the retained socket. Blindly moving disconnect before guard exit can
reintroduce EBADF and overwrite valid evidence with UNKNOWN. The minimal proposed
repair keeps that ordering and adds an explicitly non-graceful native client
disposal path for terminal evidence cleanup, using the existing local connection
shutdown/discard primitive without IMAP LOGOUT or another provider round trip.
Ordinary graceful disconnect callers retain their behavior. Cover observation
cleanup, its partial-construction failure path and standalone snapshot cleanup;
no new business logic, transport deadline increase or background cleanup worker.
Guard expiry and genuine provider/guard failure must still propagate and fail
closed. Every owned client must be released even when an earlier cleanup fails;
locks, timers, context tokens and connection references must not leak.

Canonical provenance precedes patching. Desktop MAIN b8dcfc665a4f lacks the ACTOR
Observation surface. Git history does retain it in 0a4261f8; the existing
prepare/m10-poststripe-20261016 worktree at d52f68f0 also retains that family.
These are provenance anchors, not proof of byte equality with current hosted
ACTOR or permission to absorb their unrelated changes. The encoding-owned
release/scoped-rfc-encoding-20261025 commit 9e82549 remains a separate source
anchor. Preserve MAIN's foreign WIP and ordinary index. The engine owner must
produce a reviewed, owned canonical patch against the existing ACTOR lineage,
with exact baseline/postimage hashes and a recorded mapping to BOTH current
actor source families. If the historical lineage differs, retain an explicit
context-checked family adaptation of only the cleanup hunks; never copy the
ACTOR evidence module wholesale into MAIN or silently treat MAIN tests as ACTOR
proof. Preserve the independently reviewed RFC adapter in both compositions.

Before any paid retry, record free RED/GREEN evidence through the real native
IMAP client and actual ACTOR observation/reply/snapshot paths with controlled
external boundaries and disposable state. A fake protocol peer must stall or
trickle LOGOUT so the old cleanup demonstrably exceeds a short absolute bound;
the repaired terminal path must perform no LOGOUT and finish within that bound.
Use real socket lifecycle behavior to reject settimeout on a closed descriptor,
proving guards exit before local disposal and preventing the historical EBADF
regression. Also cover expiry before cleanup, guard-exit failure, partial setup,
multiple clients, nested deadlines and repeated cleanup. Verify retained complete
results only on successful unexpired evidence and unchanged UNKNOWN/held results
on provider failure or expiry. Assert no SMTP, draft/storage mutation, assignment
change or model call. Repeat against both exact preserved-family candidates;
source review owns the chosen numeric bound and actual commands/results.

After source approval, reuse the existing immutable preserved-family activation
and rollback procedure. Capture complete current preimages, package inventories,
modes/ownership, exact source delta and runtime binding for TWO actors only;
refresh those two aggregate manifest rows and independently verify all six
company-family rows plus excluded Qonto. The already disclosed two-actor restart
authority does not authorize peer updates or interruption of unrelated traffic;
retain the existing activity/quiescence and service-identity gate. Rollback
restores the captured owned source/activation only, never business data or effects.
Preserve auth, permissions, modes, budgets, technical-mail suppression, deduplication,
unknown/fail-closed behavior and each family's existing guards.

This dependency establishes scope and acceptance requirements only. It does not
establish implemented cleanup, exact historical causation, live adoption, FULL
or release readiness. A reviewed finite retry budget and fresh free integration
proof precede any new paid attempt. Strict genuine FULL on BOTH actual kernel 57
installations, publication/adoption and existing documentation/final-review gates
remain required; no installed-kernel patch or FULL waiver is permitted.


## Required continuation: observable bounded assignment reads

The post-cleanup strict FULL87e3b092 remains interrupted after one transport
TimeoutError and nine conservative capacity deferrals. Local disposal alone
does not resolve the release blocker. The historical timeout's exact stage is
unknown. Executor queue wait, request time, shared remaining observation time
and actual provider execution are distinct candidate mechanisms; no source
repair may assume one merely because it is plausible.

Extend the existing assignment read decision and diagnostic path sufficiently
to distinguish these mechanisms without message content, raw identifiers,
credentials, exception messages or arbitrary tracebacks. Use safe correlation,
finite stage/check/cause codes, monotonic elapsed/remaining timings and actual
exception class where known. Propagate decisive facts through existing bounded
worker outcomes, validators, ordinary log CLI, filesystem collector and inbox;
log-only diagnosis must distinguish the observed failure from neighboring causes
and legitimate holds. Preserve historical missing facts as unknown.

Permit only a narrow deadline/scheduling/provider-boundary correction supported
by an actual deterministic free RED/GREEN reproduction or fresh restricted
read-only evidence. Preserve exact authority, provider/source checks, whole
inventory coverage, finite existing deadlines/concurrency, models, budgets,
permissions and no-extra-effects requirements. Do not turn timeouts into success,
relax discovery health, add blind retries or merely increase timeouts. Any
proposed behavior repair must name its reproduced failure and revised invariant
in the existing plan before implementation. Diagnostics alone grant no retry.

Use owned canonical source branches and exact context-checked family adaptations;
never patch installed kernels or live service source. Keep immutable57/e3e8799
unchanged. If kernel code changes, create a fresh immutable forward candidate
version and rerun its source/installed gates; do not retag57 or claim changed
bytes are the same release. Preserve foreign WIP/index and all nonowned runtime
families. Existing two-actor deployment authority and guards remain unchanged.

Review this framing, then amend/review the same plan before coding. Bound each
worker and monitor every five minutes. Require real-path failure controls and
privacy/propagation checks before adopting a repair. Reconcile actual known
charges and unknown reserves before proposing a fresh finite admission; the
consumed admission is not silently extended and no paid acceptance starts on
failing free checks. Full strict BOTH-clone acceptance, public publication and
normal Git installation/lock verification, doc-end and separate final review
remain required.

## Required continuation: diagnose the failing daemon connection

The failed58 health attempt remains failed. Its daemon records locate an
exception at readonly SELECT after roughly120seconds of projection time; they
retain neither SELECT entry time nor the failed connection's protocol/socket
state. They do not establish a120second SELECT duration or an upstream cause.
A fresh isolated-process connection subsequently authenticated and completed41
readonly selections; that success establishes intermittency, not a repair.
Current result: cause UNKNOWN; diagnostic evidence INSUFFICIENT.

The next dependency is diagnostic-only. Retain opaque runtime-scoped connection
identity/generation, socket/IMAP/TLS state, pinned/current/deadline identity
comparisons, bounded pending-command counts, operation entry/exit timing and
remaining absolute budget, and timer/abort/disposal ordering. Capture within the
actual daemon execution and preserve the initiating failure separately from
cleanup failure. No extra network command, retry, timeout/deadline change,
concurrency change, business-policy change or new paid acceptance is authorized
by this continuation. The prior proposed SELECT retry is superseded and unapproved.

Use an explicitly reviewed, bounded typed optional diagnostic contract across
engine producer/storage, kernel validation, ordinary CLI, collector and inbox.
Do not encode connection state in unrelated command/count/error fields. Preserve
compatibility and missing facts as unknown. Exclude credentials, mailbox/folder
names, raw identifiers, addresses, headers, bodies, responses and exception text.
Keep58 immutable; any kernel source change needs a new immutable candidate.
Canonical provenance and exact two-family adaptations precede source adoption.

Verify a controlled failure through a real staged native daemon RPC and local
protocol peer, preserving authentication, connection pinning and source guards.
Exercise stalled command, partial progress and expiry/disposal ordering, with
success and legitimate-held controls. Demonstrate that preimage evidence loses
the deciding facts and candidate evidence survives the actual EventStore,
ordinary paged CLI and collector/inbox. A blind analyst must detect the failure
and identify its supported boundary without learning the injected answer.
Controlled failure proves the diagnostic component; it does not retrospectively
explain the production failure. No passing provider retry closes that defect.

Underlying-defect closure requires retained evidence from the actual failing
daemon path, a cause supported by those observations, and a targeted correction
verified on that same path. Until then state cause unknown and retain the next
inspection route. Logging completion, an isolated successful probe and process
liveness cannot substitute for defect closure, strict FULL on BOTH clones,
public release/adoption or existing documentation/final-review obligations.


## Required continuation: failed59 ordinary protected-source discovery

The operator explicitly requires the full test on both clones, Astra diagnosis
on failure, and necessary corrections until the test passes. Strict run
555fb4ca9d69820a070a3890ffac312d failed before native jobs: the exact protected
original is independently received/admitted for both owners, but the later
ordinary discovery contains no MrCall original while Café retains its exact
binding. Native jobs are absent. The failure is not a native reply/draft result.
Astra cannot distinguish a missing inbound candidate, enrollment/binding rejection
or provider reconfirmation failure from retained logs. A15-second IMAP timeout
is plausible from timing, not a supported historical cause.

First close this demonstrated observational gap at the real admission producer:
safe counts at inbound/enrollment/exact-match/provider-confirmed boundaries,
finite failed binding predicate, actual provider operation and exception class,
and ordinary read-incomplete provenance in the test checkpoint. Exclude all mail
content, addresses, folder names, credentials, raw identifiers and exception text.
Preserve candidate selection, independent provider confirmation, owner/nonce/time/
MIME/body/UIDVALIDITY/UID identity, fail-closed rejection and strict signed oracle.
Do not treat an empty result as proof of absent mail or technical health.

Before behavior changes, reproduce distinct missing-source, mismatched binding
and provider failure paths with real controlled protocol/process boundaries,
and prove their actual producer diagnostics stay distinct. A bounded observation
of an existing protected original may use its retained verified provider receipt
without sending it again, changing authority or executing business actions.
New observation success alone does not explain the earlier failure. Repair only
a demonstrated mechanism; no blind timeout increase, retry loop, guard weakening,
false PASS, fixture bypass, forced answer or source overlay in normal clones.

Use this existing brief and execution plan for fresh framing/plan review before
source changes. Keep installed59 immutable; kernel changes require the next
immutable candidate, supported adoption on both clones and exact policy/provenance
refresh. A runner-only diagnostic correction must preserve all acceptance checks
and receives source-bound review before use. Retain failed runs and uncertain
effects; only fresh genuine strict FULL on both actual clones proves acceptance.


## Required continuation: explicit cumulative time-budget causes

The operator requires log generation to make the cause evident. FULL60 failed
ordinary health after native process exit0:24UNKNOWN assignment rows remain.
Actual review and unanswered timeout events select their shared phase deadline.
A matched support daemon request enters its worker after3.359ms and completes
normally after20.748s while its caller allowed only16.483s. Support's36 completed
review projections total385.386s. This establishes cumulative caller time-budget
exhaustion, not a financial quota, a120s SELECT stall or a peer implementation
fault. The earlier empty-fixture cause remains unknown and separate.

Add a bounded causal batch summary at the real assignment scheduler: effective
time available at entry, elapsed and remaining time, requested/dispatched/
returned/timed-out/deferred counts, actual per-account/global admission limits,
serial lane elapsed work and a reference to the first deciding timeout event.
Use precise time units and distinguish a shared observation deadline from request
or batch expiry. Do not call effective remaining time a configured original
budget when that original value is unavailable. Do not infer provider health,
queue stall or upstream cause from a completed RPC or elapsed time alone.

Keep authority, result ordering/content, provider calls, deadlines, concurrency,
reservations and business outcomes unchanged. Normal zero-work/legitimate holds
must not become ERROR. New diagnostic failures never alter work. Preserve the
first actual timeout and distinguish unattempted deferrals from attempted calls.
Verify real transport cumulative-deadline and individual-timeout controls, exact
counts/links, privacy, CLI/collector/inbox propagation and a fresh log-only analyst.
Use the existing brief/plan gates and a forward immutable package before adoption.

A separately reviewed single model-free measurement may project the exact
captured root set with an800-second diagnostic ceiling after guarded-job
quiescence. It uses only assignment projections, not review.gather/sweep which
can classify through a model. Capture complete per-owner work/time/expiry data
without changing production settings. This ceiling is not a proposed production
allowance or a repair claim. Any production time-budget or scheduling correction
requires measured arithmetic against the full job envelope and fresh affected
review; no financial budget increase or blind timeout retry is inferred.


## Required continuation: measured shared-time correction

Intent remains successful genuine strict FULL on both normal clones, with clear
causes and unchanged authority. E3 diagnostics passed independent integration,
blind log-only analysis and the complete kernel harness; source is committed as
71a6fb2 but remains uninstalled. E4 is an independently approved single model-free
assignment measurement under actual job/acceptance locks. Its results must remain
measurement evidence, not a historical or whole-FULL success claim.

If E4 establishes sustained successful read work exceeding existing shared phase
time, permit a coordinated finite time-allowance correction based on retained
per-owner work counts/durations and explicitly conservative headroom. A partial
measurement cannot be presented as measured complete-work duration; state its
lower bounds, extrapolation and uncertainty. Inspect any actual request/provider
errors before treating larger shared allowance as its remedy. The plan must give
concrete arithmetic and align review, discovery, worker validation, cleanup and
strict native/suite limits. A longer test timeout alone does not fix a shorter
production phase; a longer production phase alone must not exceed the native
acceptance envelope. Preserve bounded cleanup and exact terminal evidence.

Keep actual per-account/global concurrency, request/batch/provider limits, root
selection/order, held/UNKNOWN semantics, source guards and every independent
strict acceptance oracle unchanged. Financial limits remain separate and are
not increased. Do not add caching, batching, backend/peer rollout or business
features under this continuation. No installed overlays or retagging.

Fresh framing and concrete-plan review precede code. Tests must reproduce
cumulative shared exhaustion with healthy reads and show full expected coverage
under the corrected finite allowance, while individual request/batch failure,
cleanup and unchanged result/authority controls remain effective. Run required
source and at-tag gates, adopt one forward immutable candidate uniformly on both
clones, bind the exact runner/policy composition, then run the genuine BOTH FULL.
A failure returns to evidence-based Astra diagnosis, not unlimited retries.
Existing publication, public installation/lock verification, documentation and
separate final-review obligations remain open.


## Required continuation: remote rejection must not look like transport failure

The approved model-free measurement found mixed causes. Besides shared expiry,
a fast remote validation rejection had113272ms remaining yet the kernel logged
`transport_unavailable`. The captured root independently fails the pinned exact
RFC validator, and a matching-time backend event records that validation branch.
Six final UNKNOWN roots also have successful RPC observations; their authority
causes remain under read-only diagnosis. No numeric time change or paid FULL
retry is justified as a sole remedy.

Preserve typed remote error provenance in kernel diagnostics so standard remote
rejection/invalid-parameter responses remain distinct from connection/IO failure.
Use actual structured response metadata or proved finite input predicates, never
parse raw exception text or invent server codes. Keep calls, result/error
compatibility, scheduling, authority and fail-closed handling unchanged. Do not
drop malformed roots from coverage, reinterpret UNKNOWN as success, normalize
identities without a lossless proved rule, or relax the strict whole-inventory
oracle. A fresh concrete plan must state the source mechanism and real transport
RED/GREEN controls before code. Future backend producer changes or rollout need
their own affected framing/plan and existing actor/peer authority checks.


## Required continuation: recover whole MIME header identity before tokenization

Read-only E4 diagnosis establishes a kernel identity bug: three retained Gmail
drafts have a complete References/In-Reply-To header encoded as two MIME words.
The kernel takes the first raw References token, producing an invalid66-character
fragment. Decoding the complete121-character header losslessly yields one valid
80-character RFC Message-ID. The backend correctly rejects the fragment. This is
not an authorization to fabricate identity syntax or relax backend validation.

Repair the canonical thread-key path by bounded whole-header MIME decoding before
References tokenization. Accept decoding only when complete structurally valid
identities are established. Preserve normal/HTML-escaped identifiers and ordered
multi-ID References. Invalid, partial, ambiguous and unknown-charset material
must remain explicit uncertainty under existing fail-closed safeguards; never
omit its draft from inventory or merge distinct identities opportunistically.
Retain proof that discovery of the captured MIME shape reaches the same complete
RFC identity as the full retained header, without a provider call or made-up ID.
Current engine binding is not established by that offline proof; genuine strict
FULL and independent source/authority guards remain required.

Combine this diagnosed identity repair, precise remote-rejection diagnostics and
a reviewed finite shared-time correction in one forward immutable kernel
candidate. Time sizing must explicitly label partial-work extrapolation, reserve
non-projection work and align worker/cleanup/native/suite bounds. Financial caps,
concurrency and request/batch/provider limits remain unchanged. All six apparent
successful-RPC unknowns have missing required peer observations after timeout;
no evidence permits weakening peer merge or whole-inventory coverage. The
recovered inventory-count episode requires no backend rollout for this root.

The existing plan must receive concrete ownership, arithmetic, real regression
checks, ordered integration/release gates and rollback before code. Fresh review
of framing and that concrete plan precedes implementation. No backend/peer
restart, broad refactor, caching, business-feature change or extra acceptance
attempt is implied beyond a finite, source-bound, reviewed strict BOTH FULL.


## Required closure: truthful standing-authority architecture template

The current architecture template unconditionally calls company files
authoritative and engine standing rules derived. Existing code and the identical
protected paragraph on both clones distinguish managed Desktop authority from
legacy file authoring. This stale template claim is part of the already approved
canonical standing-authority recovery, not a new business capability.

Replace only that paragraph with the common existing managed/legacy contract.
Preserve unrelated custom prose, including MrCall's existing assignment section;
add no assignment prose, company configuration, rule publication or runtime
behavior. Prove neutral rendering for both clone shapes and exact agreement
with the shared protected authority paragraph. Keep actual package bytes immutable:
61is already frozen/installed, so use a forward patch candidate0.61.1 instead of
retagging or editing it. Its runtime Python behavior remains byte-identical to61;
FULL on both is still required for the unshipped inherited composition. Retain
the existing owned scheduling hold while refreshing exact candidate/provenance
inputs. No backend/peer restart or financial/concurrency/authority change follows.


## Required continuation: repair the actual FULL62 source-read failures

The operator explicitly requires genuine strict FULL on BOTH maintained clones
and necessary corrections after Astra diagnosis. Diagnostic retention alone is
not the requested result. FULL62 remains interrupted/unsuccessful with independent
cleanup PASS; immutable62 and failed evidence remain unchanged.

Investigate and correct the demonstrated ownership-source read failures through
canonical engine source. Cumulative internal120s expiry after many completed
IMAP operations is established; initiating latency and necessity of each remote
roundtrip require evidence. The Sent source-correspondence rejection requires
its exact origin and preceding guards to distinguish absent from ambiguous
archive evidence. Do not infer financial exhaustion or solve either failure by
weakening UNKNOWN, assignment completeness, source freshness or strict health.

Permit narrowly proved read-work consolidation when equivalent source identity,
header/flag and before/after mailbox-state checks remain enforced. A private
controlled regression must reproduce actual operation amplification and show
correct results under the unchanged provider deadline, including mailbox mutation,
foreign scope, missing/changed/deleted sources and genuine provider failure.
No cross-observation stale authority cache or replacement business judgement.
Any changed deadline needs independent causal justification and concrete bounded
composition review; no blanket increase or repeated paid experiment is admitted.

Source/archive acquisition is not an assignment decision. If the missing Sent
match is caused by a canonical ingestion/correspondence defect, repair that
source path with private preimages and exact scoped identity verification. Do
not insert fabricated archive rows, alter customer content, restore stale data,
change synchronization marks arbitrarily or replay uncertain customer effects.
An actual data mutation needs an exact separately reviewed transaction first.

Amend this existing execution plan with concrete source ownership, negative
cases and source/actor deployment review before coding or runtime mutation.
Use an isolated canonical Desktop worktree, preserving unrelated normal-tree
WIP and distinct installed business families. Supported immutable actor deployment
and affected-service restart are authorized only for the exact reviewed repair
and rollback; identify each affected owner explicitly. Preserve unrelated peers,
Qonto, credentials, schedules, billing, permissions and technical-mail suppression.
Normal clone kernels advance together through one forward immutable release;
never patch installed files or move tags.

After free source/integration checks and exact installed composition approval,
allow at most one fresh strict BOTH FULL under the existing finite financial
ceiling, reconciled charges/reserves and fixture authority. A failure returns
to bounded Astra causal diagnosis; success requires the original independent
reply, provider draft, acknowledgement/no-loop, signup, terminal and cleanup
oracles. Public provenance, authorized publication, doc-end, separate final
review and baseline closure remain required. No smaller component proof closes
the whole objective.


## Required E16 dependency: exact independently reviewed peer families

The existing native acceptance consumer requires every trusted peer to have one
shared full-package digest. Actual reviewed E11 source deliberately changes only
Mario's Sent diagnostic module while the other three peer families remain at
their independently approved source. Requiring those distinct reviewed packages
to be identical is a false composition constraint. Correct only the consumer's
expected-identity representation through canonical isolated source, with an
optional exact per-peer expected-payload mapping covering the entire trusted UID
cohort. Each actual peer must match its own independently reviewed FULL inventory;
a current snapshot is never approval. Missing, extra, malformed, partial or wrong
UID/digest mappings must fail closed, including signed-result validation. Keep
legacy scalar behavior when the mapping is absent; malformed presence cannot
fall back. This expresses individually exact approved families and grants no
new source, permission, action or functional-oracle authority.

Preserve the native installed-package real-root/no-symlink guard. Use supported
normal real-.venv installation with complete-environment rollback, independently
verified actual package origin and all159 Git-bound kernel entries. Change no
engine/customer source, keys, actors, excluded stripe/Qonto identity, routes,
permissions, signatures, models, budgets, absolute deadlines or strict reply,
draft, acknowledgement/no-loop, signup, native-terminal and cleanup requirements.
The minimum native schema selector must also reach its existing runner and
result checks; no scalar fallback may bypass per-UID enforcement.

Fresh brief approval precedes plan approval and code. Baseline tests, genuine
positive/negative native validation controls and fresh source review precede a
canonical consumer commit. Deploy only its exact reviewed four-file bundle with
preimage/mode guards and owned rollback under already-held controls, preserving
foreign Desktop WIP. Then prepare and separately review a policy-only atomic
activation using actual adopted identities and approved E11 source manifests.
No review.gather, sweep, discovery/native job or potential model call belongs to
free preflight. Genuine fixture authority, source/tag GREEN, BOTH immutable63
adoptions, complete free preflight and the separate E15 final root admission
remain mandatory before paid acceptance. This dependency establishes neither
activation, successful strict BOTH FULL nor public delivery.
