---
status: active
---

# Stripe public release

Approved [brief](../briefs/2026-10-18-stripe-public-release.md); brief review: /tmp/stripe-stable-20261018/brief-review.md.

## M1 — Isolated release candidate (lead)

Start branch release/stripe-v0.53.0 from immutable public v0.52.0 in /tmp/stripe-stable-20261018/kernel. Run baseline suite before edits. Apply only reviewed Stripe source from 518f599: new stripe_cli registration and module, canonical skill/partial, help/charter additions and focused test/run hook. Apply its narrow bootstrap additions to the existing cs-capabilities template, keeping its name; update the distribution test's bootstrap path accordingly. Preserve all other backend, permission, scheduled and company template bytes against v0.52.0; verify exact changed-path inventory. Carry standalone integration documentation and link it from existing guides. Run full deterministic suite with zero model calls. Independently review M1 before release metadata/tagging.

## M2 — Read-only installed checks and publication (lead)

Use a disposable candidate installation and each clone's existing owner-authenticated configuration for whoami and Stripe status; no provider list or model call is needed. Keep returned secrets and business records out of logs. Verify wheel template resources and three-host rendered link/copy equality. Declare MINOR, both maintained clones +live read-only, explaining unchanged send/auth/permission boundaries. Bump package/changelog/tagged-state claims together; commit and create immutable v0.53.0 immediately. Run the full suite at that tag. Commit post-tag immutable target binding and restore untagged HEAD status. Sweep all version claims in kernel and both clones; classify live/historical/structural, never edit historical narrative.

Obtain final release approval before public branch/tag push. Publish only the isolated branch/tag, preserving main's unreleased sources; integrate metadata to main only with exact conflict review. Verify remote tag target and package installation from that immutable tag.

## M3 — Clone adoption (lead, runtime owner dependency)

Inspect both clones and coordinate active override ownership. Adoption is separate from public-tag publication: never replace an installed repair override, security files or cron while another owner holds them. Where safe, normal cs update --pin v0.53.0 and uv install/restamp must preserve authored files, current permission/cron bytes and operational repair layers, regenerate requirements.lock and prove lock-only installation in a throwaway venv; verify version, identity, Stripe status and all three skill surfaces, update all live inventory claims and commit/push only owned changes. Update kernel operational-pin marker only after both actual adoptions pass. Otherwise retain explicit pending adoption and the existing operational pin; do not certify or force it.

## Desktop stable prerequisite

Free validator refuses missing operational-evidence/latest.json and tracked policy is development_hosted. The ordinary-operations owner confirms there is no exact_candidate publishable proof; the last strict V14 attempt failed. Retain this blocker, do not run paid acceptance or installer builds and do not promote prerelease .3 as stable. That workstream must first produce exact-candidate operational proof.

## Closure and rollback

Lead reconciles current scoped state and preferences, preserves prior narrative, runs mechanical checks, doc-critic/shape and a separate final review; record exact publication/deferral evidence. Never advance a broader development baseline or claim original operational acceptance. Candidate rollback is removal of unpublished artifacts; published immutable tags never move. Adoption rollback restores captured package/pin/lock and owned rendered files without touching other owners' changes.
