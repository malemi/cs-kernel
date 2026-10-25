---
status: active
---

# Private native stream diagnostics

Approved framing: [brief](../briefs/2026-10-18-private-native-stream.md), fresh
review retained under the private native-stream-retention-20261018 evidence root.

1. Implement a private diagnostic sink in cs/operator_recovery.py. Open the new
   run directory by no-follow directory FD; verify owner and0700 mode. Create
   stream and manifest exclusively with0600 mode. Retain only stdout lines
   already admitted by MAX_CAPTURE_BYTES, preserving their order and bytes
   except existing fallback-key redaction. Enforce the same cap on stored bytes.
   Retention failures produce a symbolic notice and an incomplete manifest when
   writable; they do not alter Attempt, existing output or acceptance decisions.
   Manifest records digest, byte counts, overflow/malformed state, child identity,
   process exit and complete/incomplete diagnostic status; it grants no authority.
2. Add a focused real-subprocess test using constructed stream events: a normal
   terminal; ordered init/result/background/init/result for the same session;
   malformed data; overflow; key redaction and restrictive umask/file privacy;
   directory/file safety and recording failure. Duplicate-init/terminal cases
   remain rejected by the actual discovery join and clean-terminal validator.
   Register the focused test in tests/run.sh and run existing recovery, discovery
   and health tests plus the full kernel suite. Preserve baseline and failure logs.
3. Fresh milestone review checks the exact diff and real free test results.
   Update diagnostic documentation and route this trace in docs/README.md.
   Apply documentation closure and a separate final review for this bounded
   source-only diagnostic delivery. Native operational acceptance remains open:
   no hosted installation, paid retry or historical resealing is authorized here.

Ownership: lead owns the two source/test files, test-runner line and scoped docs;
reviewers inspect only and have three-minute bounded tasks. Other sessions are
active; do not revert their changes. Dependencies: approved brief, then fresh
plan approval before implementation, then milestone and final gates. Rollback
only this narrow diagnostic delta against matching preimages. Existing two-MB
capture, watchdog, launch argv, models, budgets, permissions, exact one-init and
one-terminal checks remain unchanged. Actual missing lifecycle cannot be invented
from fixtures; any later protocol amendment needs its own reviewed evidence.

## Retained installed observation

The separately approved continuation composition installed this diagnostic source
in both clones. V18 retained1,210,068 admitted native stream bytes for the
interrupted Café attempt; its private exact copy and SHA256 are in
`ordinary-assignment-recovery-v18/free-diagnosis/causal-summary.json`. Forced
supervisor termination left no final stream manifest for that attempt. The
admitted stream is useful causal evidence, not a completed diagnostic lifecycle
or native acceptance. Source checks and milestone reviews pass; final semantic
closure remains pending with the open ordinary acceptance obligations.
