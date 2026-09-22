"""Shopify CRM adapter — customer lookup by email (Admin GraphQL API).

Looks up a customer and returns an order-history summary, so a support
reply can be grounded in "is this a customer, what did they order".

Auth — the CURRENT Shopify model (legacy in-admin ``shpat_`` custom-app
tokens were deprecated 2026-01-01): a **Dev Dashboard app** installed on
the store + the **client credentials grant** — client_id/client_secret
exchanged for a 24h access token (cached under ``settings.state_dir``)
against the **GraphQL** Admin API. A static token (``<PREFIX>_ADMIN_TOKEN``)
is honoured too and wins if set.

Env keys (values in the clone's env layers, prefix from the manifest
``[crm.shopify].env_prefix``, bare ``SHOPIFY_*`` as fallback):
``<PREFIX>_STORE_DOMAIN`` (the *.myshopify.com domain), ``<PREFIX>_CLIENT_ID``,
``<PREFIX>_SECRET`` (app installed on the store, scopes read_customers/
read_orders), optional ``<PREFIX>_ADMIN_TOKEN``.

Incomplete config → stub result with an actionable note; the dossier
degrades, never breaks (port contract).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import CrmCtx, CrmResult, CrmRow

RENDER_HINTS = ["orders", "spent", "tags"]

_SKEW = 300  # refresh 5 min before the 24h token expires

_CUSTOMER_QUERY = """
query($q: String!) {
  customers(first: 10, query: $q) {
    edges { node {
      id email firstName lastName numberOfOrders state tags createdAt
      amountSpent { amount currencyCode }
      lastOrder { name }
    } }
  }
}
"""


def _token_cache_path(settings) -> Path:
    # Derived from the ONE state dir — never a hardcoded per-company path.
    return settings.state_dir / "shopify_token.json"


def _env_prefix(settings) -> str:
    p = (settings.shopify_env_prefix or "").strip().upper().rstrip("_")
    return p or "SHOPIFY"


def _read_cached_token(settings) -> str | None:
    try:
        d = json.loads(_token_cache_path(settings).read_text())
    except (OSError, ValueError):
        return None
    if d.get("domain") != settings.shopify_store_domain:
        return None
    if d.get("expires_at", 0) - time.time() < _SKEW:
        return None
    return d.get("access_token")


def _write_cached_token(settings, access_token: str, expires_in: int) -> None:
    p = _token_cache_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "domain": settings.shopify_store_domain,
        "access_token": access_token,
        "expires_at": time.time() + int(expires_in),
    }))
    os.chmod(p, 0o600)


def _client_credentials_token(settings) -> str:
    """client_id/secret -> 24h Admin API token (client credentials grant),
    cached on disk. Raises on failure (lookup turns it into a note)."""
    cached = _read_cached_token(settings)
    if cached:
        return cached
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": settings.shopify_client_id,
        "client_secret": settings.shopify_secret,
    }).encode()
    req = urllib.request.Request(
        f"https://{settings.shopify_store_domain}/admin/oauth/access_token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    token = resp["access_token"]
    _write_cached_token(settings, token, resp.get("expires_in", 86399))
    return token


def access_token(settings) -> str:
    """Supported way to obtain a Shopify Admin token.

    A static token wins if explicitly set; otherwise the client-credentials
    grant. This is the name a consumer outside this module imports: the Desktop
    engine needs a token to drive `fetch_customers`, and reaching into a
    private name for it leaves the kernel free to rename that name without
    warning anyone.
    """
    return settings.shopify_admin_token or _client_credentials_token(settings)


# Kept so existing pinned callers keep working. New code uses `access_token`.
_access_token = access_token


def _graphql(settings, token: str, query: str, variables: dict) -> dict:
    url = (f"https://{settings.shopify_store_domain}"
           f"/admin/api/{settings.shopify_api_version}/graphql.json")
    req = urllib.request.Request(
        url,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _row(node: dict, email: str) -> CrmRow:
    spent = node.get("amountSpent") or {}
    last = node.get("lastOrder") or {}
    name = " ".join(filter(None, [node.get("firstName"), node.get("lastName")]))
    amount = spent.get("amount")
    currency = spent.get("currencyCode") or ""
    return CrmRow(
        id=str(node.get("id") or ""),
        label=name or str(node.get("email") or email),
        email=str(node.get("email") or email),
        facts={
            "orders": str(node.get("numberOfOrders") or "0"),
            "spent": f"{amount} {currency}".strip() if amount is not None else "",
            "state": str(node.get("state") or ""),
            "tags": ", ".join(node.get("tags") or []) if isinstance(node.get("tags"), list)
                    else str(node.get("tags") or ""),
            "last_order": str(last.get("name") or ""),
        },
    )


def lookup(ctx: CrmCtx, email: str) -> CrmResult:
    """Never raises: missing config, auth/API errors and GraphQL errors all
    become a note so the caller (dossier) keeps working."""
    settings = ctx.settings
    prefix = _env_prefix(settings)
    have_token = bool(settings.shopify_admin_token)
    have_cc = bool(settings.shopify_client_id and settings.shopify_secret)
    if not settings.shopify_store_domain or not (have_token or have_cc):
        return CrmResult(
            source="stub", ok=False,
            note=(
                f"Shopify CRM not configured — set {prefix}_STORE_DOMAIN "
                f"(the *.myshopify.com domain) + {prefix}_CLIENT_ID + {prefix}_SECRET "
                "(Dev Dashboard app installed on the store, scopes "
                f"read_customers/read_orders) in the clone's env layers; "
                f"a static {prefix}_ADMIN_TOKEN wins if set"
            ),
            rows=[], render_hints=list(RENDER_HINTS),
        )
    try:
        token = _access_token(settings)
        data = _graphql(settings, token, _CUSTOMER_QUERY, {"q": f"email:{email}"})
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:200]
        except Exception:  # noqa: BLE001
            pass
        hint = (" (app installed? scope read_customers? client_id/secret correct?)"
                if e.code in (401, 403, 400) else "")
        return CrmResult(source="shopify", ok=False,
                         note=f"Shopify Admin API HTTP {e.code} {e.reason}{hint} {detail}".strip(),
                         rows=[], render_hints=list(RENDER_HINTS))
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        return CrmResult(source="shopify", ok=False,
                         note=f"Shopify Admin API error: {type(e).__name__}: {e}",
                         rows=[], render_hints=list(RENDER_HINTS))
    if data.get("errors"):
        return CrmResult(source="shopify", ok=False,
                         note=f"GraphQL errors: {data['errors']}",
                         rows=[], render_hints=list(RENDER_HINTS))
    edges = (((data.get("data") or {}).get("customers") or {}).get("edges")) or []
    rows = [_row(e["node"], email) for e in edges]
    return CrmResult(source="shopify", ok=True, note=None,
                     rows=rows, render_hints=list(RENDER_HINTS))
