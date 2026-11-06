# Embedded Desktop operator helpers

## Source and dependency boundary

The kernel contains the Desktop-managed operator client modules, selected from
reviewed donor commit `6445d1eb0e31a873c4c01f095dd7bac2298eef45` and adapted to
current main's permission templates. This is a paired engine/host source component,
not a standalone kernel MCP installation or a new release. Desktop owns the
`operator-mcp` optional dependency group and its adapter to current engine main.
Kernel metadata does not promise standalone SDK installation.

`cs.desktop_runtime.main` exposes the embedded management entry: initialization,
status, revoke, configuration/export and MCP. The host supplies its entry point
and dependency environment. The helper uses descriptor/owner/company/workspace
bindings and preserves main's v9 bootstrap and canonical skill distribution.
`cs.desktop_diagnostic` is a separate local diagnostic entry, not an engine. It
binds loopback, accepts loopback Host headers and no-Origin SDK requests, and
rejects browser origins and public Host headers. Hosted reverse-proxy/browser-origin
use is unsupported by this slice. The donor public-host literals are removed
through a separately reviewed local-only correction; the literal gate is unchanged.
The source also includes bootstrap, scoped read/import and standing-instruction
helpers. Their presence does not register new bootstrap or standing-instructions
verbs in the main `cs` CLI; embedded callers own those uses.

## Permissions and operational effects

The existing settings deny list and scheduled wrapper re-deny
`operator.rules.decide` and `operator.rules.import_confirm` through all six CLI
spellings. These are owner mutation routes exposed by the paired engine; generic
raw-RPC permission must not admit them. All previous grants and denies remain.
Native skill bodies and main's runner are preserved.

Managed read/prepare operations require their actual scoped authentication and
capabilities. `ask_operator` can incur engine model cost; `prepare_reply` writes a
draft and can incur cost. Source availability or a local test is not permission
to call either against real accounts. This slice grants no send authority and
adopts no installed clone, descriptor, credential or running service.

## Reproducible source checks and limits

Local controlled fixtures cover management CLI, official SDK STDIO discovery,
loopback HTTP diagnostics, owner/company rejection, uncertainty and concurrent
operations. The selected five test files run 32 tests: 31 pass and one standalone
SDK discovery check remains skipped. The donor's legacy managed-aware native
workflow test is explicitly excluded because its required workflow bodies are not
selected here. The existing canonical three-host bootstrap test passes; that is
distribution evidence, not native model execution.

The two permission changes are exact scheduled-template successors. Gate63 keeps
its original `03b4449` base and all 58 main check predicates; strict whole-source
and rendered before/after hashes allow only those additions to be reversed for
the predecessor comparison. Actual postimage deny tests remain independent.
Four successor tests include 64 negative mutation controls. The historical shared
69-predicate comparator belongs to another candidate and is not imported.

Wheel checks verify ten helper modules, both permission resources and audited
imports without source fallback, using explicit existing third-party paths.
They do not prove a freshly resolved dependency environment or a compatible
current-main Desktop pair. The [integration plan](execution-plans/2026-11-06-desktop-operator-main.md)
retains the original failed run, source reviews and outstanding gates.
