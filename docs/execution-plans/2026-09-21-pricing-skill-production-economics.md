---
status: superseded
---

# Pricing workflow integration

Brief: [pricing skill and economic reasoning](../briefs/2026-09-21-pricing-skill-production-economics.md).

## Current disposition

Kernel integration is abandoned. `cs-pricing` remains a locally maintained
skill in the Cafe 124 clone: production costs, product constraints and
commercial rules are company-specific, and another company's pricing workflow
requires its own design. This follows the kernel charter's rule of two.

The local skill exists at `.claude/skills/cs-pricing/SKILL.md`; the clone's
`.agents/skills` and `.opencode/skills` links resolve the same bytes. Clone
commits `1a5009d` and `6b33f4e` record its installation and subsequent updates.
The clone's completed `2026-10-07-price-list-good-for-124-acceptable-to-customers`
plan records the published pricing-project and price-list results. The operator
confirms ongoing use; this status correction is not a fresh quotation exercise.

The preserved kernel branch below is historical recovery material, not a
delivery queue. No pricing template is distributed by current kernel `cs init`
or `cs update`, and this plan creates no obligation to integrate or release one.
The original integration proposal below is retained as historical context;
its open steps no longer describe pending work.

## Historical integration snapshot

This plan records the inspectable state at 2026-10-01. The existing brief
records a prior exercise; this consolidation does not reconstruct its review
history or treat that record as a new live acceptance test.

### Preserved implementation

Branch `work/pricing-triage-20261001`, commit `d16e3e5`, preserves the
`cs-pricing` template, triage routing, help/charter indexes and rendering checks
from the original checkout. Its five source files match the reconciliation
snapshot byte for byte. The branch retains the older source base and mixed
send-mode guidance; integration with published standing instructions,
acceptance and release remain open.

### Abandoned delivery steps

1. Preserve these changes when integrating published kernel history, including
   the new company-file standing-instruction ownership.
2. Review the resulting pricing and triage instructions against the brief:
   cost scope, capacity, supplier thresholds, missing facts and approval of
   external prices. Keep company values outside kernel source.
3. Render all fixture configurations and evaluate a representative proposal
   against the brief's criteria. Record evidence and unresolved inputs;
   do not send a customer message as part of this evaluation.
4. Obtain final integration review, then follow the kernel release procedure
   if publication is requested. Verify installed templates before claiming
   delivery complete.

Rollback of an unsuccessful integration restores the reviewed pre-integration
template snapshot while preserving the original local changes separately.
