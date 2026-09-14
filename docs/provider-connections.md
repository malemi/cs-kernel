# Provider connections

Each integration has its own capability and configuration reference:

- [Vonage SIP](integrations/vonage.md): development connection and supervised
  provisioning, with explicit credential references per clone.
- [Shopify](integrations/shopify.md): existing customer-lookup CRM adapter.
- [Google Drive](integrations/google-drive.md): existing read-only document access.
- [Faire](integrations/faire.md): existing clone-level credential setup;
  authenticated API access unverified and no reusable kernel adapter.

The `[connections.vonage]` configuration belongs to the new connection surface.
Shopify and Drive retain their own configuration paths. Each reference states
the supported operations, limits and verification evidence; appearing in this
list does not imply a common API or the same readiness level.
