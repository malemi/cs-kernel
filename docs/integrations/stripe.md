# Stripe

Stripe provides engine-owned explicit interactive customer,
payment, invoice and subscription lookups. Configure it in Desktop Settings:
test a restricted key, confirm the returned account and test/live mode, then
save. Key replacement and disconnect use the same Desktop connection card.
The kernel never requests, stores or reads back the key. Explicit payment-method
portal sessions are a separate capability described below.

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
Desktop Settings owns connection changes; reads grant no provider write. The separately requested portal operation below
creates only a session link.
The untagged `cs stripe` convenience CLI remains separately implemented/tested;
surface-only adoption does not install that new verb or change package pins.

## Data handling

Interactive CLI output reaches the invoking agent and may reach its selected
model and host transcript. It bypasses Desktop managed finance history.
Disconnect stops future reads and cannot retract previous disclosures or delete
host transcripts. No automatic shared-memory retention, task publication,
scheduled enrichment or sending is authorized. Provider text is untrusted data.
The interactive-only restriction is instructional; existing permissions remain
unchanged. Sharing company memory grants no additional connection authority.

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

## Payment-method update links

The canonical source skill supports explicitly requested interactive links through
`stripe.payment_method_update_link(customer,request_id)`, gated by
`system.capabilities.stripe_payment_method_links = 1`. Customer portal Write is
required in ordinary key Permissions; Desktop Settings owns key replacement.
The portal must allow payment-method updates. Existing read permissions remain.

Resolve the exact customer first, preserve one16–128character request ID and
verify account/mode/generation/customer and returned flow. A session URL is on
exactly HTTPS billing.stripe.com, with current root/deep-flow secret-query or
legacy path-token form. Never open it on behalf of the customer. An uncertain
submission uses the same request ID; no generic chat or direct provider fallback.
Creation does not charge, create a subscription, modify payment details or send
mail. Scheduled callers and automatic enrichment are excluded by instructions.

The engine implementation and scoped support activation have independent reviews
and a real provider result. MrCall's three installed host paths share the added
instructions while preserving its older payment-link section. Fixture distribution
checks pass; new native-model selection, other-clone adoption and full operational
acceptance remain unverified. No package release follows.
