# Vonage connection production rollout

## Intent and authority

The operator authorized finishing and putting the reviewed integration work
into production on 2026-09-14. This includes the commits, public kernel release,
pushes and maintained-clone upgrades needed for delivery. It does not authorize
customer trunk changes, customer messages or unrelated Faire implementation.

## Scope

Integrate the reviewed Vonage connection, SIP skill and integration guides with
the current published kernel history (v0.44.0 and subsequent documentation),
retaining workspace setup and engine-backed project records. Release a new
minor version and adopt it in the two maintained clones: the support operator
and the coffee-company operator. Preserve unrelated local clone changes.

The current main checkout predates origin/main. The reviewed changes are
uncommitted here; both maintained clones currently run v0.44.0. Integration must
preserve that newer behavior rather than downgrade either clone. Faire remains
documented as application setup with authenticated access unverified.

## Acceptance and verification

- Review the integrated diff, run the full kernel regression before release
  and again at the immutable new tag, and follow the release inventory/sweep.
- Apply the FULL verification tier on both clones using read-only operations,
  local fixtures and draft-only supervised paths. Never trigger live sends or
  customer provider mutations as a release test.
- Upgrade both installed packages, stamp all three agent skill surfaces, keep
  clone-owned configuration, and verify manifest/pin/lock/as-built alignment.
- Verify engine identity on both clones; verify Vonage status and preview on
  the configured support clone and disabled-provider refusal on the other.
- Verify all headless mutation denials and private credential handling; ensure
  the newly installed operator can discover its SIP workflow and company guide.
- Rebuild each regenerated dependency lock in an isolated venv and verify the
  resolved kernel version. Document final published and installed state.

## Risks and recovery

Capture initial refs, tracked and untracked changes, package pins, generated
files and private runtime backups before mutation. Hold affected scheduled
operators during installation and restore their exact prior pause state after
checks. Do not erase existing pauses or unrelated changes. An unsuccessful
clone upgrade rolls back to its recorded prior pin and templates while held.
Published tags never move; release errors are repaired forward. Commit explicit
paths only and never publish transcripts, secrets or unrelated customer records.
