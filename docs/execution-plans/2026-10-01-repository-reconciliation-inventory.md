---
status: active
---

# Reconciliation inventory

Scope: the eighteen dirty paths recorded before reconciliation. Snapshot
`46a79fe869dc7c8aca790d1b8895b233a00b0665` preserves all original bytes;
`backup/reconcile-20261001T134452Z` and its independently verified bundle
retain that snapshot. The initial source base is `7484e9f`; the fetched
published base is `d16e12b`. None of the old recovery copies is new code.

| Original path | Evidence | Destination |
|---|---|---|
| `cs/config.py` | Exact Git blob match to `d16e12b` | Integrated main keeps published file |
| `cs/config_report.py` | Exact Git blob match to `d16e12b` | Integrated main keeps published file |
| `cs/manifest.py` | Exact Git blob match to `74ea403` | Integrated main keeps newer published recovery/send-mode/instruction implementation; original retained in snapshot |
| `cs/project_init.py` | Exact Git blob match to `d16e12b` | Integrated main keeps published file |
| `cs/templates/project/.claude/skills/cs-help/SKILL.md.j2` | Unpublished pricing/triage workflow or associated rendering checks | Exact file committed on `work/pricing-triage-20261001`; acceptance remains open |
| `cs/templates/project/.claude/skills/cs-triage-mail/SKILL.md.j2` | Unpublished pricing/triage workflow or associated rendering checks | Exact file committed on `work/pricing-triage-20261001`; acceptance remains open |
| `cs/templates/project/AGENTS.md.j2` | Committed guard corrections plus uncommitted pricing index, predating standing instructions | Guard corrections on main; exact original file on `work/pricing-triage-20261001`; keep published standing-instruction ownership on main |
| `cs/templates/project/bin/cs_operator_cron.sh.j2` | Exact Git blob match to `74ea403` | Integrated main keeps newer published recovery/send-mode/instruction implementation; original retained in snapshot |
| `cs/templates/project/manifest.toml.j2` | Exact Git blob match to `d16e12b` | Integrated main keeps published file |
| `docs/operator-runtime.md` | Local billing/restore clarifications plus older recovery prose | Merge clarifications into published runtime documentation, preserving send-mode and instructions.store descriptions |
| `tests/run.sh` | Exact Git blob match to `74ea403` | Integrated main keeps newer published recovery/send-mode/instruction implementation; original retained in snapshot |
| `tests/test_render_permissions.py` | Exact Git blob match to `d16e12b` | Integrated main keeps published file |
| `tests/test_sip_surfaces.py` | Exact Git blob match to `d16e12b` | Integrated main keeps published file |
| `tests/test_stamped_surfaces.py` | Exact Git blob match to `d16e12b` | Integrated main keeps published file |
| `tests/test_template_render.py` | Unpublished pricing/triage workflow or associated rendering checks | Exact file committed on `work/pricing-triage-20261001`; acceptance remains open |
| `cs/operator_recovery.py` | Exact Git blob match to `74ea403` | Integrated main keeps newer published recovery/send-mode/instruction implementation; original retained in snapshot |
| `cs/templates/project/.claude/skills/cs-pricing/SKILL.md.j2` | Unpublished pricing/triage workflow or associated rendering checks | Exact file committed on `work/pricing-triage-20261001`; acceptance remains open |
| `tests/test_operator_recovery.py` | Exact Git blob match to `74ea403` | Integrated main keeps newer published recovery/send-mode/instruction implementation; original retained in snapshot |

## Local commits

- `43d17fd`: retain as a merge ancestor. Integrate guard corrections, archive,
  Shopify API documentation, pricing trace and recovery delivery updates;
  retain later published acceptance records when reconciling overlapping docs.
- `7484e9f`: retain as a merge ancestor; replace its baseline with the reviewed
  integration commit after verification, keeping the recorded history.

## Incomplete work

The five exact pricing/triage files are preserved together on their original
source base. That branch is an unfinished work product, not a release candidate.
It contains older standing-instruction guidance and mixed pricing/send-mode
changes that require integration with the published company-file ownership.
The snapshot also preserves every superseded recovery file.

## Final evidence

Pending milestone reviews and integrated verification. No clean-checkout or
publication success is asserted by this inventory until those checks finish.
