# One main line for the mailbox kernel

## Intent

Integrate the completed mailbox release into public `main`, preserving the
independent Desktop APIs already committed there. The operator explicitly asks
for all completed work on main and a merge. This supersedes the earlier
publication-only boundary that preserved independent main without integration.

Other mailbox repositories already publish their completed work on main. This
change closes the remaining kernel split; it introduces no new live deployment.

## Starting points and existing implementation

Public main is `25099365ee1f504ba18d75889659d02a172f9a56`; the completed mailbox
release branch is `9d971276a41eedf0d87bbcadbfbf3a0297573e86`. Their common history
predates the released kernel's later improvements. Both histories must remain
reachable from the resulting main commit.

Use the current release implementation for native draft delegation, scheduled
selection, configuration, monitoring, observability and package dependencies.
Preserve main's independent `desktop_runtime`, `desktop_managed`, `desktop_mcp`,
`desktop_packages`, `desktop_diagnostic`, `operator_read`, `operator_import`,
`bootstrap` and `codex_bootstrap` modules and their supported contracts.

The embedded MCP retains its nine tools and guidance resource. Management keeps
workspace/owner binding, revocation, locking and receipts. Read APIs keep bounded
provenance, instruction integrity and explicit incomplete coverage. Import proofs
retain their compiler binding and protected write semantics.

Superseded unpublished mirror helpers are not a second draft implementation.
Do not restore kernel-owned IMAP draft writers or replace the current native
engine operations with the retired paired-copy workflow. Keep stronger released
monitoring and safe exception provenance when resolving shared files.

## Constraints

- Work in an isolated integration worktree; preserve every other checkout and
  its uncommitted work. Use normal Git ancestry and a nonforcing main push.
- Keep published tags `v0.76.1` and Desktop `v0.1.57` immutable. Do not repin or
  reinstall either clone, change hosted engines or issue a new release tag.
- Both clones remain on their verified immutable kernel. The engine's embedded
  package remains pinned. Main integration alone grants no runtime rollout.
- Preserve cron, pause files, permissions, models, budgets and uncertain sends.
  Tests use synthetic services; no live mailbox mutation or paid generation.
- Documentation states that main contains the union while installed releases
  retain their existing versions and evidence qualifications.

## Acceptance

1. Main contains both exact starting histories, with no force push or moved tag.
2. Released native mailbox behavior, package source and stronger monitoring
   contracts survive except for explicit compatibility fixes proven necessary.
3. The nine independent main modules and their relevant registrations remain
   usable; meaningful management, STDIO MCP, transport, package export, bootstrap
   and provenance checks pass through their actual supported entry points.
4. The release test suite passes on the combined source. Any baseline failure
   is identified separately and is not disguised by skipping or weakening tests.
5. Current documentation, a semantic critic and a separate integration review
   approve the actual union. The final remote main is read back, with existing
   installed tags, processes and operator pauses preserved.
