# Shopify

## What we can do

The existing CRM adapter looks up customers by email through Shopify Admin
GraphQL and adds commercial context to a support dossier. It returns customer
identity, order count, amount spent, tags, account state and the last order's
name. Use it to identify existing customers and ground replies in their
commercial relationship. This is a customer summary, not a complete order ledger.

From a configured clone:

```bash
.venv/bin/python -m cs business customer@example.com
.venv/bin/python -m cs dossier customer@example.com
```

`business` returns the CRM result; `dossier` combines CRM information with
conversation and prior-contact evidence. Drafting remains an engine workflow
with the normal dossier and sending checks.

## Configuration and credentials

Set `[crm].adapter = "shopify"` in the clone manifest. The optional
`[crm.shopify].env_prefix` selects the credential prefix; `api_version` selects
the Admin API version used by the adapter. Configure `<PREFIX>_STORE_DOMAIN`
and either `<PREFIX>_CLIENT_ID` plus `<PREFIX>_SECRET`, or a static
`<PREFIX>_ADMIN_TOKEN` in private env layers. A static token takes precedence.
The configured app needs customer/order read access on the selected store.

The client-credentials path exchanges app credentials for an access token and
caches it in `shopify_token.json` under the clone's state directory. Keep tokens
out of documentation and prompts. The existing loader supports bare `SHOPIFY_*`
fallback; it does not use Vonage's strict credential-reference model or a
`[connections.shopify]` binding.

## Limits and failure handling

- The query requests at most ten customer matches and does not paginate a store.
- There are no kernel operations here for creating or changing orders, refunds,
  fulfillment, inventory, products or customer records.
- Missing credentials produce a stub with `ok=false`. API, scope or
  authentication errors produce a failed result with a note. Neither means
  the customer does not exist; inspect `ok` and `note` before using the rows.
- CRM is auxiliary context. It does not override the dossier's contact/sending
  verdict, which relies on mailbox evidence.

## Verification and implementation

The adapter is registered in [the CRM port](../../cs/crm/__init__.py) and
called by `business` and `dossier` in [the CLI](../../cs/cli.py).
[The adapter](../../cs/crm/shopify.py) owns its query and result fields.
Existing clone records document a successful live customer lookup. The
2026-09-13 documentation review verified runtime wiring and source behavior,
not a new live Shopify request. A newly configured clone must verify its own
account with a known customer before relying on results.
