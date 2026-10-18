# Publish the Stripe operator release

The operator authorizes public Stripe publication. Publish a minor cs-kernel release from immutable v0.52.0 with only the already reviewed Stripe read CLI, canonical skill, generic existing-workflow routing and their tests/docs. Preserve the released bootstrap name; exclude unreleased email/authentication/send changes and bootstrap renaming. Use an isolated worktree and keep shared dirty trees intact.

Acceptance: full deterministic kernel suite green before and at the tag; package contains canonical skill/partial; both maintained clone identities and Stripe status verified using the candidate without model calls; read-only release classification independently reviewed; immutable tag and public source verified. Installed adoption must preserve hosted repair overrides and authored files; coordinate with their owner before replacing packages or restamping managed security files.

Desktop stable publication additionally requires fresh signed exact-candidate operational acceptance. Current free preflight refuses absent operational-evidence/latest.json and the tracked policy is development_hosted. Do not weaken that gate, promote the test artifact as stable, or spend on acceptance/builds while these prerequisite conditions fail. Retain a concrete release-blocker record and coordinate its owning workstream. No engine restart, cron/send change or new paid model trial belongs to this release preparation.

Rollback: unpublished candidate can be discarded; published immutable tags never move. Clone adoption retains exact package/file backups and preserves operational overrides. Desktop remains on its existing stable release until its exact-candidate gate passes.
