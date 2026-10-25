# Private native stream diagnostics

The failed V17 ordinary run has a complete discovery capture, but its supervisor
receipt records two init events with the same session ID. The strict join rejects
that cardinality before reading the capture. Its native result stream was not
retained, so the exact terminal/background sequence cannot be established.

Add bounded private diagnostic retention to the existing native supervisor. Store
the ordered stream lines already admitted by its existing two-million-byte cap,
using the same fallback-key redaction as the parser. Retain a private manifest
with byte counts, digest, child identity, process exit, overflow, malformed-input
and retention status. A diagnostic recording failure must neither hide a product
failure nor change native execution, acceptance, model, budget or permissions.

Scope is cs/operator_recovery.py, focused local subprocess tests, the test runner
and durable diagnostic documentation. No hosted installation, new paid execution,
release or weakening of the one-init/one-terminal contract is included. Original
V17 stays FAILED. Raw stdout before key redaction is intentionally not persisted.

Acceptance: real local synthetic subprocesses retain ordered same-session
background/init/result events without accepting them as a clean terminal; the
single-terminal case keeps existing behavior; overflow remains rejected and the
file stays within the existing cap; malformed input is recorded and rejected;
fallback key bytes are absent; files/directories are private; recording errors
are visible in diagnostic status without changing the native Attempt result.
No actual Claude lifecycle is inferred from software fixtures.
