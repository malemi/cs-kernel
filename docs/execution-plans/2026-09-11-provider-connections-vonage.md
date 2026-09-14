---
status: completed
---
# Provider connections — Vonage implementation

Brief: [scope and acceptance](../briefs/2026-09-11-provider-connections-vonage.md).
Brief review: APPROVED, independent reviewer, 2026-09-11.

## M1 — explicit connection and read surface

Owner: implementation agent for settings/manifest changes; lead for HTTP client
and CLI. Add a strict optional `[connections.vonage]` model, with enabled flag,
credential env-name references, region and allowed application IDs. Resolve the
referenced secrets from the existing env chain, never a generic fallback.
Expose `cs connection vonage status|domains|show|users` with bounded timeouts,
fixed official endpoints, no redirects, safe error text and allowlisted output.
Reject `--account` switching for provider operations.

Verification: two synthetic clone identities/configurations; disabled and
missing credentials; actual GET-only provider probe; no secrets in output.
Integration review must approve before M2 depends on this surface.

## M2 — preview and commit provisioning

Owner: lead. Add `cs connection vonage provision` for an application domain and
digest user, and `allow-ip` for additive ACL changes. Use domain names returned
by PSIP rather than deriving them from customer names or assistant numbers.
Creation validates new domain, allowed app ID, region and public CIDR/IP input.
Required ACL prevents an unconfirmed empty allowlist from opening traffic.
No DNS guessing: hostname input must be resolved/confirmed by the technician to
public IPs before commit. A call while waiting for IP is reported as pending.

Provision preview reads current state and prints only intended safe fields.
Commit requires explicit flags and re-reads provider state, writes a generated
secret to an exclusive mode-0600 file in the clone's private state directory,
then creates domain/user and reads both back. Existing conflicting domains or
users are refused; existing identical state is a no-op only when fully proven.
No mutation is blindly retried. Partial success retains private recovery data
and reports the last verified step. Never auto-delete to roll back.

The first release checks app-domain association and states that phone-number
association and real call testing remain separate readiness checks. No number
reassignment is added speculatively without a verified contract.

Verification: local HTTP fixtures exercise preview vs write, conflict, stale
state, ACL preservation, failures after each write, safe output and readback.
An independent milestone reviewer checks correctness before M3.

## M3 — skill, cron boundary and company procedure

Owner: lead; fresh reviewer for workflow exercise. Canonical template
`cs-sip-trunk` runs read/preview/commit through the new CLI and reads the
company's SIP procedure. Mutation subcommands are denied in all six cron
spellings; a wrapper headless marker also refuses commits in code. No broad
provider mutation allow-list is added. Verify the new skill's identical bytes
through all three host links, including copy fallback.

Prepare the clone-owned MrCall manifest configuration and procedure including
the three Drive source links, the known public-IP handoff, company application,
the boundary between provider provisioning and the customer's PBX work, and
registration-color uncertainty. Store general retrieval knowledge in engine
memory only after the proposed exact content has been reviewed; the user's
approval of execution authorizes the described general procedure, not unrelated
entity-memory updates. No customer-specific project or additional takeover/close record.

Use development checkout invocation and an isolated rendered clone to verify
the workflow. Do not silently replace the production venv or stamp production
template-owned files with an unreleased kernel. The final handoff includes the
release/adoption step still required by repository policy.

## M4 — full validation and final review

Owner: lead and fresh final reviewer. Run kernel regression including both
clone fixtures, documentation mechanical gate and semantic documentation review.
Exercise final-user read and preview paths against real Vonage with the exact
clone configuration. Exercise risky paths against a local HTTP fixture only.
Review the credential handoff and recovery limitations explicitly.

Reconcile docs, baseline and plan. No commit/tag/push or production upgrade.
Release tier is FULL because settings auth and cron permissions are touched.
Rollback for local changes is the reviewable diff; no live provider mutation
will have happened during this implementation.

## Progress and evidence

- Integration guides, 2026-09-13: README links each of Vonage, Shopify, Drive
  and Faire to its own Markdown reference under `docs/integrations/`. Guides
  state supported requests, credential/configuration ownership, failure modes
  and dated verification evidence. Faire's application setup is included with
  authenticated access explicitly unverified. The former connection reference
  routes to the guides; its Vonage content now belongs to the Vonage guide.
- Faire inventory correction, 2026-09-13: the platform operator documentation
  for the coffee-company clone already describes direct REST access, and its
  private env files contain application credentials. No Faire access-token
  variable or reusable kernel implementation was found in the inspected paths.
  Authenticated access remains unverified. The README distinguishes this
  existing setup from a working reusable connection; "future idea only" was
  an unsupported generalization from a kernel-only search.
- Documentation follow-up, 2026-09-13: root README includes the requested
  `Integrazioni` section with implemented/development/future capabilities and
  links to the connection reference. README access, remote-engine and cron-send
  guidance is reconciled with runtime behavior. This follow-up changes prose
  only; mechanical documentation and release-consistency checks pass.
- M1–M4 implementation and verification complete. Final `bash tests/run.sh`:
  `RESULT: all gates green` (2026-09-11), including a fresh package install,
  33 templates across three configurations and all 41 provider tests.
  Evidence: `/tmp/cs-vonage-final-clean-tests.log` on the implementation host.
- At implementation completion on 2026-09-11, release/adoption remained
  separate and awaited integration plus authorization. Publication and installed
  verification now belong to the authorized
  [rollout plan](2026-09-14-vonage-production-rollout.md).
- Final implementation review APPROVED. Independent provider tests: 41 passed.
- Real exact-clone CLI `status` authenticated and verified its allowed voice
  application. A new-domain preview used synthetic public IP 8.8.8.8 solely
  to exercise validation; no provider writes or credential file were created.
- General procedure saved in the engine and retrieved through `cs ask` with
  all three source URLs. Company notes retain the memory identifier. No
  customer project was created; no live SIP changes or customer sends occurred.
- Documentation critic has zero STALE findings after release-state and ambient
  variable-name corrections; active context is a current snapshot. Historical
  live checks and Drive contents were not independently reverified by that
  reviewer; the lead's source reads remain the evidence for those documents.
- The clone's documentation gate retains six pre-existing dead project links;
  its baseline is not advanced. Kernel mechanical gate is clean, with eight
  oversized-document and two open-session advisories recorded separately.
- M2 APPROVED after fixing pause checks immediately before each mutation;
  22 local HTTP and CLI tests pass, including partial recovery and pause races.
- M3 APPROVED: rendered six-spelling denies, actual wrapper headless marker,
  three-host identical skill bytes and copy fallback verified. The general
  company-memory excerpt includes the private credential handoff rule.
- Brief APPROVED by a fresh reviewer.
- Pre-existing kernel tree clean; doc gate clean; 8 non-documentation commits
  since baseline. Existing minted-account-session plan is active awaiting its
  release step; this work must preserve those unreleased changes.
- Official PSIP GET `/v1/psip/` returned HTTP 200, array of 12 domains.
- Plan review: APPROVED, independent reviewer, 2026-09-11.
- M1 APPROVED after review correction: only a provider 404 means absence;
  empty/null successful GETs are incomplete evidence. Fifteen focused tests
  pass; real CLI status authenticates and verifies the configured voice app.
- Baseline regression has one pre-existing release-metadata failure: this
  checkout says latest tag v0.42.0, but local refs include v0.43.0 and v0.44.0
  on later commits. The operational clone already runs v0.44.0. No downgrade
  or overwrite of the production environment is part of this implementation.
- Two sampled live domains use assigned names, not telephone numbers.
  Both have digest users; their observed ACL is 0.0.0.0/0. An additive entry
  cannot restrict that ACL, so the new additive operation must refuse it and
  report the need for a separately reviewed replacement.
- PSIP's published PUT contract has no conditional revision/ETag parameter.
  Read-before-write/readback detects observed drift, not a concurrent writer in
  the final GET-to-PUT window. ACL previews state this limitation; the skill
  must avoid concurrent dashboard/API edits. User readback proves existence,
  not the secret's SIP authentication behavior; an actual call remains needed.
