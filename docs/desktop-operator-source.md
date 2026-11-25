# Embedded Desktop operator helpers

## Source and dependency boundary

Main includes the embedded Desktop management, MCP, scoped read/import, bootstrap
and package-export helpers alongside the released native mailbox implementation.
The [main integration plan](execution-plans/2026-11-25-mailbox-main-integration.md)
owns current source verification. The November 6 plans retain historical checks.
This source integration creates no release or installed Desktop pairing.

`cs.desktop_runtime.main` exposes `desktop-init`, `desktop-status`,
`desktop-revoke`, `desktop-configure`, `desktop-export` and `desktop-mcp`.
The host supplies its entry point and MCP dependency environment; kernel metadata
does not install a standalone MCP SDK. Descriptor version 1 binds the owner,
company, workspace and generation. Managed operations retain workspace locks,
revocation and operation receipts.

The embedded MCP exposes nine tools: `operator_context`, `list_tasks`,
`list_drafts`, `search_email`, `read_email`, `list_projects`, `read_project`,
`ask_operator` and `prepare_reply`, plus `operator://guidance`.
`prepare_reply` prepares an engine draft and retains uncertain-operation refusals.
It does not implement the retired kernel Gmail review-copy workflow.

`cs.desktop_diagnostic` is a separate loopback diagnostic entry. It accepts
loopback Host headers and SDK requests without Origin, and rejects browser origins
and public Host headers. It is not a hosted reverse-proxy or browser-origin API.
Scoped reads preserve provenance, bounded continuation, instruction integrity,
incomplete coverage and binding-change refusals. Import proofs bind the compiler
and protected write semantics. These helpers register no extra normal `cs` CLI
verbs. The current CLI and canonical native workflows retain the released source.

## Effects and verification limits

Managed operations require authenticated scope and capabilities. `ask_operator`
and `prepare_reply` can incur engine model cost; the latter writes a draft.
Availability does not grant send authority. The merge adopts no clone descriptor,
credential, provider operation or running service.

Controlled source checks exercise management subprocesses, official SDK STDIO,
loopback diagnostics, owner/company rejection, uncertain operations, concurrent
operations and package export after removing original inputs. The standalone SDK
case requires its declared runtime environment; a skipped case proves nothing.
Actual results and any dependency limitations are retained by the integration
plan. These checks do not certify native model execution or installed host pairing.
