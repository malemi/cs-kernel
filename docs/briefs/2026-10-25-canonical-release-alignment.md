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
