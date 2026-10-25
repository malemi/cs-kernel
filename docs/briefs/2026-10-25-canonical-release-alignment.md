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
