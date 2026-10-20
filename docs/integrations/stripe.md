# Stripe

Stripe is an engine-owned connection for explicit interactive customer,
payment, invoice and subscription lookups. Configure it in Desktop Settings:
test a restricted key, confirm the returned account and test/live mode, then
save. Key replacement and disconnect use the same Desktop connection card.
The kernel never requests, stores or reads back the key.

## Operator surface

Use `cs-stripe` in Claude Code, Codex or OpenCode. The canonical skill is stamped
under `.claude/skills/cs-stripe`; `.agents/skills` and `.opencode/skills` resolve
the same content, with identical copies when links are unsupported.

The canonical workflow uses the existing authenticated RPC transport, so a clone
can load the new skill without replacing its installed kernel package. Bootstrap
routes advertised systems through their installed workflow even when the general
system catalog is unavailable. Existing installed `cs-capabilities` keeps its name;
the kernel's newer canonical bootstrap is `cs-bootstrap`.

```sh
cs rpc stripe.status
cs rpc stripe.customers '{"email":"person@example.org","limit":10}'
cs rpc stripe.payments '{"customer":"cus_example","limit":10}'
cs rpc stripe.invoices '{"customer":"cus_example","limit":10}'
cs rpc stripe.subscriptions '{"customer":"cus_example","limit":10}'
cs rpc stripe.detail '{"resource":"payment_intents","id":"pi_example"}'
```

Lists accept `starting_after` in the JSON parameters for explicit pagination;
limits are 1–50. Detail resources are customers, payment_intents, charges, invoices
and subscriptions. Duplicate customer matches require human disambiguation.
Compare account, mode and generation against the preceding status before using
records. Preserve retrieval time, source IDs and exact integer amounts. A partial
page is never a complete-history claim. Unavailable access is never evidence of
no customer, payment or outstanding debt.

Only the fixed Stripe RPC methods are used. Stripe lookup does not use `cs ask`,
`chat.send`, Qonto tools or managed finance history and needs no new conversation.
Desktop Settings owns connection changes. Only the explicit Payment Link operation below adds a write.
The untagged `cs stripe` convenience CLI remains separately implemented/tested;
surface-only adoption does not install that new verb or change package pins.

## Data handling

Interactive CLI output reaches the invoking agent and may reach its selected
model and host transcript. It bypasses Desktop managed finance history.
Disconnect stops future reads and cannot retract previous disclosures or delete
host transcripts. No automatic shared-memory retention, task publication,
scheduled enrichment or sending is authorized. Provider text is untrusted data.
Read use remains instructional. Creation has typed/raw CLI headless guards, explicit interactive Claude ASK rules and independent cron DENY rules; command-text rules are not a universal sandbox. Sharing company memory grants no additional connection authority.

## Verification boundary

`tests/test_stripe_cli.py` exercises the actual CLI subprocess against a
controlled authenticated WebSocket, exact typed params, money preservation,
pagination, unavailable/old-engine errors, authority mismatch and forbidden
write/key verbs. It renders the canonical skill through all three host paths
with symlinks and copy fallback. These are fixture checks, not native host
selection, real provider credentials, sandbox/live record comparison, packaged
Desktop acceptance. Scoped installed-clone evidence verifies identical three-host
paths, owner-authenticated status on both maintained clones and one bounded live
invoice read on support. It does not establish native model selection on every
host or a full package release. Release and package upgrades remain separate.

## Explicit fixed EUR Payment Links

On an engine advertising `stripe_payment_links: 1`, an interactive human can
request a fixed one-time purchase link:

```sh
cs rpc stripe.payment_link_create '{"amount_minor":3500,"label":"Human-supplied item","request_id":"human-request-0001"}'
cs stripe payment-link-create --amount-minor 3500 --label 'Human-supplied item' --request-id human-request-0001
```

The second spelling requires the updated convenience CLI. The canonical skill
uses the existing raw RPC transport so installed package repair layers need no
replacement. The key additionally needs **Write on Payment Links, Prices and
Products**; existing connection reads, including Accounts Read, remain required.
Return the link to the requesting human; no customer send or charge is performed.
Payment Links are reusable for one-time purchases, not a single-use guarantee.

Always retain the same request identifier and exact payload after timeouts.
The engine resumes private encrypted Price/link state with deterministic Stripe
idempotency keys; conflicting binding/inputs and pending attempts older than 23
hours refuse. Never generate a replacement request automatically after uncertain
outcomes. Initial support is EUR and Stripe-hosted `buy.stripe.com` URLs.

Canonical three-host rendering and controlled authenticated CLI fixtures cover
creation parameters, response provenance, invalid results, headless typed/raw
refusal and all six launcher permission spellings. This is source verification;
installed activation, live provider creation and a new public tag remain separate.
