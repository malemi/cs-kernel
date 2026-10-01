---
status: active
---

# Pricing workflow integration

Brief: [pricing skill and economic reasoning](../briefs/2026-09-21-pricing-skill-production-economics.md).

This plan records the inspectable state at 2026-10-01. The existing brief
records a prior exercise; this consolidation does not reconstruct its review
history or treat that record as a new live acceptance test.

## Current implementation

Branch `work/pricing-triage-20261001`, commit `d16e3e5`, preserves the
`cs-pricing` template, triage routing, help/charter indexes and rendering checks
from the original checkout. Its five source files match the reconciliation
snapshot byte for byte. The branch retains the older source base and mixed
send-mode guidance; integration with published standing instructions,
acceptance and release remain open.

## Remaining delivery

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
