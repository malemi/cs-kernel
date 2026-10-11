# Name the interactive bootstrap cs-bootstrap

## Intent
The operator requests the clearer public name `cs-bootstrap` instead of
`cs-capabilities`, and explicitly authorizes a kernel commit while excluding
any update of mrcall-cs. The skill loads procedures, workflow context and
optionally discovers engine capabilities; bootstrap describes the whole job.
The operator also requests a host-neutral name for company/claude-extra.md;
its replacement is company/other-systems.md.
The operator also requires a plain skill invocation to load local procedures
with a short confirmation. Optimization belongs in the skill, not a longer
operator prompt: engine discovery must require a systems/capabilities request.

## Scope and constraints
Rename the canonical skill and company systems guide, three-host invocation references, current operator
documentation and executable checks. Preserve the workflow authority boundaries and add an explicit plain-invocation
default: local company procedures and mailbox identity only, no engine/config
probes, no eager unrelated workflows, and a brief confirmation with actual gaps. Keep historical records and native captures under their original
identity; distinguish legacy observations from current-name distribution checks.
No permission, RPC, engine, send, authentication or business-data changes.
No release, push or maintained-clone update is part of this task.
Retire the exact old discovery path during restamping when the new canonical
skill is present. Preserve any old directory contents outside skill discovery
rather than discard local edits. Repeated restamping must be safe. Move the old company guide to the new path
before stamping only when the new path is absent; preserve both when both
already exist and report the conflict. Never overwrite authored company content.

## Acceptance
- Plain invocation is explicitly routed to local procedure loading and a short
  confirmation; system discovery remains available only for relevant requests.
  Deterministic contract checks verify these instructions; new native agent
  timing/compliance acceptance is outside this task.
- Fresh render and actual update expose cs-bootstrap through Claude, Codex and
  OpenCode, with byte-identical bodies and correct host invocation text.
- Update of an old rendered clone preserves the old skill contents outside
  discovery and leaves one canonical bootstrap entry; repeated update is safe.
- Company guide migration preserves authored bytes and repeated restamping;
  collisions preserve both files and report the unresolved duplicate.
- Current help, charter and README route to cs-bootstrap and other-systems.md; historical records
  remain unchanged and native acceptance is not claimed for the new name.
- Relevant kernel checks pass and the scoped change is committed. Production
  mrcall-cs remains unchanged.

## Assumptions
Renaming an operator workflow is a public interface change, so this is substantial
work rather than a fast-path typo. A later separately authorized release will
need a MINOR version; the current v0.52.0 tag stays immutable.
