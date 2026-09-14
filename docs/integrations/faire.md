# Faire

## Current status

Faire has an existing clone-level setup: the platform's operator-access
document describes direct REST access for wholesale work, and private env
files contain an application ID and application secret. This was checked on
2026-09-13 without printing credential values.

No Faire adapter or `cs connection faire` command exists in this kernel.
No Faire access-token variable was found in the inspected clone/platform env
files or current process, and no Faire-named state file was found in that
clone's state directory. These checks do not prove a token cannot exist
elsewhere. No authenticated API read has been verified in this work.

## What we can do reliably now

- Locate the documented application setup and check which credential types are
  present without exposing their values.
- Identify the authorization prerequisite and prepare a bounded read-only
  verification against the correct company account.
- Handle Faire-related email through the existing mailbox/dossier workflow.
  That gives access to synced mail, not complete order data or retailer
  conversations inside the Faire portal.

We cannot yet promise order lookup, catalog/inventory access, retailer-message
reading or any Faire mutation through this integration. Those operations need
authenticated verification and an implemented operator surface first.

## Authorization prerequisite

The [official Faire API documentation](https://developers.faire.com/docs)
distinguishes application credentials from authorization to a brand's data.
The OAuth path uses application credentials together with an OAuth access token;
an application ID and secret alone do not establish usable account access.
Faire also documents a brand-portal path for obtaining an API key for a custom
integration in [How do I get an API key?](https://www.faire.com/support/articles/37632363832091).

Use the clone's own account and private credential store. Do not borrow another
company's token, infer a token from an application secret, or log secret values.
Check the current provider contract before choosing the authentication path.

## What must be verified next

1. Locate or obtain the intended brand's authorized token through the supported
   provider flow; confirm the account and granted access.
2. Make one bounded read-only request against a documented endpoint. Check its
   status and expected structure without exposing credentials or dumping
   customer data into logs.
3. Verify returned records against a known record in that brand's portal.
   Record the date, account scope and operation actually proven.
4. Define the reusable kernel surface and tests for the required operations.
   Any write operation needs its own authorization, preview and verification.

Until those checks pass, report **application setup present; authenticated
access unverified**. Do not report either a working integration or a complete
absence of prior Faire setup.
