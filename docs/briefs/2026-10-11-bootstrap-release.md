# Bootstrap release and operator upgrade

## Intent

Publish the reviewed interactive bootstrap and upgrade the requested MrCall
operator clone. The user authorizes commits, release publication and that clone
upgrade. Existing dirty operator work and company guidance must survive.

## Scope and constraints

Release from reviewed bootstrap parent `83ebb58`, with the reviewed README
corrections from `a3a3bc6`. Preserve the integrated contextual-email candidate
on main as unreleased development. MrCall's authenticated engine currently
advertises assignment draft policy but no contextual email policy; shipping
main's new guard would refuse existing chat and send workflows. This release
therefore carries no guard changes or engine deployment.

The release source must equal the frozen reviewed bootstrap parent, except the
reviewed clone README and release/version documentation. Its only runtime
change against v0.51.0 is the explicit WebSocketException import. Sending,
authentication, campaign code, permission settings and cron bytes retain the
released contracts. New bootstrap and legal-research skills remain canonical
across all three hosts. No new native/model calls are needed.

Choose v0.52.0 (MINOR for new operator workflows), with read-tier checks on both
clone fixtures: the connection-error path can affect live reads. Below FULL is
safe only after exact equality of all send/auth/permission surfaces is proved.
Follow docs/release-procedure.md, including at-tag tests, immutable tag binding,
version sweep, documentation closure and explicit-path commits.

## Acceptance

- Pre-release and at-tag kernel suites pass; canonical instructions retain their
  frozen-parent acceptance qualifications.
- Isolated clone fixtures verify current settings, CLI and read-only engine
  behavior, without changing production state, schedules or sending authority.
- Main keeps the contextual-email candidate; published tag excludes it. Release
  metadata is integrated without undoing main's guard or unrelated local work.
- MrCall installs the immutable tag through the supported upgrade path. Pin,
  ledger, architecture and lock agree; a lock-only rebuild and authenticated
  identity pass. Company files and pre-existing dirty edits are preserved.
- Refresh bootstrap/help onboarding while preserving the clone's local harness
  and operator guidance. Both new skills resolve through all three host paths.
- Café 124 is checked for release compatibility but is not upgraded; do not claim
  a shared operational pin after only one clone moves.

## Rollback and limits

Preserve original clone bytes and a recoverable package/lock reference before
upgrade. If validation fails, keep the original installed tag or restore that
pin through the supported upgrade path. Never rewrite a published tag, reset
unrelated work, alter schedules or enable sending. The engine may lack the new
catalog; procedure loading works locally and catalog discovery reports unknown.
