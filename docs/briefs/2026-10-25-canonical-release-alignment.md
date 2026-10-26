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
