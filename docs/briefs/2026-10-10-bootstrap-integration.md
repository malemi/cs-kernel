# Local bootstrap integration

Integrate reviewed bootstrap commit `83ebb58` and its legal-research dependency
onto current main `eb6dc1a`, preserving the contextual-email assignment guard.
The operator authorizes a local merge; publication, release and clone upgrades
remain separate tasks.

Scope is Git integration, the three conflicting documentation files, a current
integration work trace and verification. Repair the stale teaching regression
in tests/test_live_capabilities_fixture.py that compares all rpc.py bytes to
the historical pre-guard base: retain exact compiler/teaching-body equality and
exact AST equality for the RPC module outside chat, including publication and
read-only transport. The changed contextual-email chat policy is independently
verified against main and its existing behavioral tests. This is a test-only
integration adaptation; fixture, auditor, production and capture bytes remain
unchanged. Production code must equal Git's
automatic merge of the approved parents; any required source repair reopens
the relevant review. Preserve both parents' routing entries and archive bytes.
Reconcile the living context into current state, retaining historical prose
verbatim in the archive. Do not modify or commit the 13 pre-existing local
changes in `/home/mal/hb/cs-kernel`.

Acceptance: both parents are ancestors of the merged commit; the full kernel
suite passes on the integrated tree; bootstrap fixture/render checks and
contextual-email guards pass; relevant bootstrap read-route implementations
and canonical host instruction bytes are compared to their reviewed parent.
The previous 19 native observations remain evidence for their frozen parent,
not fresh native acceptance of the merged tree. No paid native rerun is required
unless an integration difference changes those instructions or read routes.
Documentation closure, an independent integration review and a separate final
review must pass before main advances. Before promotion, preserve the dirty
original checkout on a named branch with exact file-digest equality, without
changing its files. Stash and reset are prohibited throughout this operation.

Assumptions: the already-approved legal-research stack is intended dependency;
the main-side contextual-email guard is retained in full; no parallel process
changes the parent refs or dirty checkout during promotion. Verify refs and
file digests immediately before changing branch ownership. Rollback is to
retain the integration branch and leave main at its original tip if any gate
fails. Never reset, drop, stash or overwrite the unrelated working changes.
