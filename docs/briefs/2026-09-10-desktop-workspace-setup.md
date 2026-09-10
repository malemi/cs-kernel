# Complete desktop-to-workspace setup

<!-- doc-scope:start -->
Scope: cs-kernel's implementation slice of the desktop-to-operator journey:
explicit descriptor selection, truthful installation/login outcomes, and a
repeatable readiness report. This is proposed work, not a release claim.
<!-- doc-scope:end -->

## Intent and product boundary

The user configures a remote engine through the desktop, then creates a local
company workspace and uses their separately paid Codex or Claude Code agent.
This change makes the handoff explicit and recoverable. It does not replace
the agent, introduce delegated identities, or perform a general security audit.

## Scope

1. `cs init --descriptor PATH` explicitly selects the desktop handoff. Invalid
   explicit input fails before writing; it never falls back to another account.
   Descriptor secrets stay outside template config, ledger, command arguments,
   and printed output. The CLI argument is a path, never token content.
2. Use the same selected descriptor for safe mailbox settings and credential
   handoff; do not rescan by UID and pick an unrelated endpoint. When engine
   settings cannot be read, ask for missing connection settings explicitly.
3. Separate workspace creation, dependency installation, engine login, and
   readiness outcomes. Installation failure is nonzero and resumable; a declined
   optional install is an honest created-but-not-installed result. Offer login
   only after successful installation, with a default-no confirmation and EOF
   handling; never run cron, sync, generation, or sending from initialization.
4. Add `cs setup [--json]` to report workspace prerequisites, expected engine
   identity, mailbox settings, preparation evidence, company memory, and agent
   executable availability. Use only read RPCs; authentication may refresh its
   existing local caches. Presence of an agent executable does not prove login.
5. Reuse existing canonical template surfaces. If modifying a skill, verify
   Claude Code, Codex, and OpenCode resolve the same canonical content. Keep
   company data in the manifest and avoid introducing literal exceptions.

## Contract and acceptance

- Explicit descriptor selection works with several ambient profiles and a
  workspace path containing spaces/apostrophes; malformed input fails clearly.
- Descriptor secrets (refresh token and other credentials) cannot leak into
  stamped files, setup JSON, stdout, or `template-manifest.json`; existing secret
  storage remains separate. Non-secret UID, email, and endpoint metadata are
  intentionally carried into the workspace configuration.
- A successful RPC envelope with a wrong/missing UID or signed-out result must
  not report a successful login or ready workspace.
- A configured but empty mailbox is a preparation state, not an auth error.
  Unsupported readiness fields/methods produce an upgrade/unverified action.
- Setup probes are bounded and never generate, send, sync, alter business
  records, install software, or launch the external agent.
- An isolated stamped-workspace scenario demonstrates installation/login
  failures and recovery with a fake local RPC transport, plus a final report
  consistent with the engine evidence. Public release availability is not
  inferred from installing the source worktree.
- Preserve all existing init callers without `--descriptor`, store-then-prove
  login behavior, owner-scoped account selection, and existing send boundaries.

## Delivery limits

Work in the dedicated worktree. No automatic commits, tags, pushes, live clone
upgrades, or production credentials. This changes a CLI surface and therefore
requires a MINOR release when a release is later requested. Auth-boundary changes
retain the existing FULL clone-verification requirement before publication;
offline tests here do not discharge that future release gate.

The cross-repository journey is owned by mrcall-desktop's
`docs/briefs/2026-09-10-desktop-to-operator-onboarding.md`. A reviewed execution
plan is required before implementation.
