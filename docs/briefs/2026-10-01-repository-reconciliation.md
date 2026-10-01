# Reconcile the shared checkout with published history

## Problem and outcome

The checkout contains two local documentation commits, fifteen published
commits missing locally, and eighteen dirty paths. Earlier recovery source
overlaps published releases; pricing and triage work is also present. A clean
status alone would not prove that the correct implementation survived.

Account for every original path and local commit. Integrate reviewed changes
on current published history, retain incomplete work in named committed
branches, and leave the primary checkout clean with recoverable evidence.
Publication is limited to the already-authorized integration; no new release
tag, installed-clone upgrade or customer-mail action is needed.

## Constraints

- Preserve the exact initial tracked and untracked contents before mutation.
  The independent bundle and Git backup ref are recorded outside the worktree.
- Treat current remote implementation as the base. Compare older local recovery
  snapshots to their historical published versions; do not overwrite newer
  permission or standing-instruction behavior with an older implementation.
- Do not claim other-session pricing work complete merely because it renders.
  If acceptance is incomplete, commit it on a dedicated branch with its plan.
- Review every conflict resolution and classification independently. Preserve
  source permissions and any unrelated concurrent changes.
- Before changing the primary checkout, compare its contents to the initial
  inventory plus this workstream's known additions. Re-inventory any drift.

## Acceptance

Every original dirty file and both local commits have a recorded destination:
integrated, identical to published history, superseded by an identified newer
implementation with differences reviewed, or committed on a named work branch.
The integrated tree passes relevant source/template tests and documentation
checks. A separate final review checks the integrated tree and inventory.
The primary branch contains published history and approved integration, has
no merge conflicts or dirty paths, and reports local/remote publication state
explicitly. The original snapshot remains recoverable independently.
