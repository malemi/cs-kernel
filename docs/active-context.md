---
doc_baseline_commit: 03b444936cdc288e795d0edef481d5a883fbcab9
doc_baseline_date: 2026-10-10
---

# Active Context — cs-kernel

<!-- doc-scope:start -->
Scope: current capabilities and publication state of this isolated Stripe release
branch. The kernel charter and release procedure own durable rules; historical
base observations are retained in active-context-archive.md.
<!-- doc-scope:end -->

## State now

- **Latest release tag: `v0.53.0`. Current HEAD status: tagged as `v0.53.0`.**
- This branch adds Stripe read CLI and canonical workflow routing to immutable
  v0.52.0. Bootstrap remains `cs-capabilities`; unreleased bootstrap renaming,
  contextual email changes and retirement work are excluded. Existing backend,
  authentication, permission and scheduled template bytes are unchanged.
- The canonical skill uses fixed authenticated `cs rpc stripe.*` methods and
  the convenience `cs stripe` CLI supplies typed filters. Desktop owns keys and
  connection changes. The [Stripe reference](integrations/stripe.md) owns
  supported reads, data handling and verification limits.
- Candidate transport has owner-authenticated identity and Stripe status proof
  on both maintained clones: support connected/live, Café disconnected.
  No conversation, provider list, model request or package replacement runs.
- Active installed repair layers and cron coordination belong to the ordinary
  operations owner. Public tag publication grants no right to overwrite them.

## Unresolved

- Public v0.53.0 publication awaits tag checks and final review; the full candidate suite passes.
- Installed package/pin/lock adoption is held until coordinated composition
  preserves the current repair layers. Operational pin remains unchanged.
- Native automatic skill selection and a stable Desktop installer are not
  established. Desktop lacks fresh signed exact-candidate operational proof.

## Next

1. Complete the [release plan](execution-plans/2026-10-18-stripe-public-release.md)
   and publish only the independently approved immutable candidate.
2. Coordinate clone adoption with the current runtime/package owner; retain
   backups, package locks and authored content before any replacement.
