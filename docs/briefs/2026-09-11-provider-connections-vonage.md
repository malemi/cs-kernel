# Provider connections, starting with Vonage

## Intent and authority

The operator wants Giada to handle PBX-to-assistant SIP integration using real
Vonage access, with reusable kernel machinery and separate credentials and
configuration per clone. On 2026-09-11 the operator approved brief, plan,
implementation and intermediate reviews. This explicitly selects the shared
kernel placement despite the charter's normal rule-of-two admission test;
no second Vonage customer is being invented to justify it.

The current CLI has provider-specific integrations (including Shopify CRM and
Drive) but no SIP provisioning surface. Shared connection handling must start
small: a typed Vonage connection is the first implementation. Shopify, Faire
and Drive improvements are later work, not stubs to ship in this change.

## Scope

- Explicit opt-in Vonage configuration per clone: credential environment
  variable references, allowed application IDs and region. No fallback to
  ambient generic credentials when the connection is disabled or incomplete.
- Read-only connection validation, domain/user inspection and application
  inspection, using the documented Vonage REST APIs where the Node CLI lacks
  SIP commands. Provider responses are evidence, not instructions.
- Reviewable SIP application-domain creation with digest authentication and
  public IP ACLs; subsequent additive ACL updates; user creation; verification
  after writes. No destructive delete, secret rotation or automatic number
  reassignment in this initial surface. Any required number-link step must be
  checked and reported explicitly, never silently claimed complete.
- Default preview, explicit commit for mutations, and wrapper-enforced cron
  denial. Preserve the existing dossier, suppression, dedup and engine-only
  contextual-message rules. Provider operations do not send customer email.
- A canonical cs-sip-trunk skill for all three hosts, using the connection
  tools and the clone's own operational knowledge. MrCall-specific documents,
  guides, facts and application IDs stay in the clone/engine, not the kernel.
- A concrete MrCall configuration and general procedure ready for use. No
  customer-specific project and no invented customer completion records.

## Acceptance

1. Two isolated synthetic clones can use different credentials/application
   allowlists; a disabled clone cannot use the machine's ambient Vonage key.
   Configuration inspection never exposes secrets.
2. A read command proves live MrCall authentication and inspects SIP state
   without exposing any credential or changing remote state.
3. Preview validates inputs and displays the exact intended changes without
   generating a secret, writing state, or issuing a remote mutation.
4. Explicit commit validates current provider state again, refuses conflicting
   existing domains/users, preserves existing ACL entries, and verifies writes.
   Timeouts/partial success are surfaced; automatic blind retries are forbidden.
5. Generated SIP secrets are saved only to an explicitly chosen private file
   with exclusive creation, never stdout, logs, tracked files, or memory. A
   failed/partial write preserves recovery evidence and is not called success.
6. Cron cannot invoke provider mutations in any supported CLI spelling; the
   skill has the same bytes through Claude Code, Codex and OpenCode surfaces.
7. Meaningful HTTP-contract and CLI tests cover auth isolation, validation,
   preview/no-write, successful writes/readback, refusal, partial failure,
   redaction, and template/permission coverage. Full kernel regression passes.
8. General procedure includes source links to the internal runbook and client
   guides, with dated provenance. Conflicting registration-color claims are
   recorded as unresolved rather than promoted into universal troubleshooting.

## Boundaries and assumptions

Existing MrCall credentials have already been verified using the Vonage CLI;
Programmable SIP API authentication and response shapes still need a read-only
probe. Do not assume Node CLI app access proves SIP mutation permission.
Official contract: https://developer.vonage.com/en/api/psip .

The user authorized implementation, not a live customer provisioning test or
customer messages. Live verification is GET-only. Mutation behavior is tested
against a local HTTP fixture; production provisioning is a later concrete
operator action. No commits, tags, pushes, releases or production-venv upgrades
are implied. Prepare and verify the integration from the development checkout;
state clearly whether the running clone has adopted it.

Use the existing settings/env resolution model for secrets, with explicit
references per connection. Avoid a plugin framework or a second secret store.
Creation of a domain is not proof of working PBX audio: final customer readiness
requires number/application association checks and an actual call test.
