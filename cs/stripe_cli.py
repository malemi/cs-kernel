"""Bridge to the engine-owned Stripe connection and explicit Payment Links."""
from __future__ import annotations

import argparse
import asyncio
import json
import os

from . import config, rpc

RESOURCES = ("customers", "payment_intents", "charges", "invoices", "subscriptions")
CONNECT = "Connect Stripe in Desktop Settings, then retry this lookup."


class StripeClientError(RuntimeError):
    pass


def bounded_limit(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("limit must be an integer from 1 to 50") from None
    if not 1 <= number <= 50:
        raise argparse.ArgumentTypeError("limit must be from 1 to 50")
    return number


def interactive_creation() -> None:
    if os.environ.get("CS_OPERATOR_HEADLESS"):
        raise StripeClientError("Payment Link creation requires an interactive human request.")


async def call(client, method: str, params: dict | None = None) -> dict:
    try:
        result = await client.call(method, params or {}, timeout=60)
    except rpc.EngineError as exc:
        if exc.code == -32601:
            raise StripeClientError("Update the engine to use Stripe, then connect Stripe in Desktop Settings.") from None
        if method == "stripe.payment_link_create":
            outcome = exc.message.split(":", 1)[0]
            messages = {
                "price_write_permission": "Enable Write for Prices and Products on the restricted Stripe key; retry the same request_id.",
                "payment_link_write_permission": "Enable Write for Payment Links on the restricted Stripe key; retry the same request_id.",
                "request_conflict": "Request identifier conflicts with prior inputs or connection. Do not create a replacement automatically.",
                "operation_stale": "Pending creation is outside the safe retry window. Inspect Stripe before any new request.",
            }
            raise StripeClientError(messages.get(outcome, "Creation outcome unavailable. Retry only with the same request_id and identical inputs; check the engine and connection first.")) from None
        raise StripeClientError("Stripe lookup unavailable. Check the connection and read permissions in Desktop Settings.") from None
    if not isinstance(result, dict):
        raise StripeClientError("The engine returned an unsupported Stripe response; update the engine.")
    return result


async def execute(args) -> int:
    creating = args.stripe_action == "payment-link-create"
    if creating:
        interactive_creation()
        import re
        if (not 1 <= args.amount_minor <= 99_999_999 or not 1 <= len(args.label) <= 200
                or args.label != args.label.strip() or any(ord(c) < 32 or ord(c) == 127 for c in args.label)
                or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", args.request_id)):
            raise StripeClientError("Use positive integer EUR cents, a nonempty item label and a stable 16–128 character request identifier.")
    async with rpc.EngineClient(config.load()) as client:
        status = await call(client, "stripe.status")
        if args.stripe_action == "status":
            print(json.dumps(status, ensure_ascii=False))
            return 0
        if status.get("status") != "connected":
            raise StripeClientError(CONNECT)
        action = args.stripe_action
        capability = args.resource if action == "detail" else action
        if creating:
            capability = None
        if capability in {"payment_intents", "charges"}:
            capability = "payments"
        capabilities = status.get("capabilities")
        if not creating and (not isinstance(capabilities, list) or capability not in capabilities):
            raise StripeClientError("This Stripe resource is unavailable. Check read permissions in Desktop Settings.")
        if creating:
            params = {"amount_minor": args.amount_minor, "label": args.label, "request_id": args.request_id}
        elif action == "detail":
            params = {"resource": args.resource, "id": args.id}
        else:
            params = {"limit": args.limit}
            for key in ("starting_after", "customer", "email"):
                value = getattr(args, key, None)
                if value is not None:
                    params[key] = value
        result = await call(client, "stripe.payment_link_create" if creating else "stripe." + action, params)
        account = status.get("account")
        account_id = account.get("id") if isinstance(account, dict) else None
        result_account = result.get("account_id")
        if (not account_id or result_account != account_id
                or result.get("mode") != status.get("mode")
                or result.get("generation") != status.get("generation")):
            raise StripeClientError("Stripe connection changed during lookup; retry against the current connection.")
        if not isinstance(result.get("retrieved_at_utc"), str):
            raise StripeClientError("The engine returned Stripe evidence without retrieval provenance.")
        if creating:
            from urllib.parse import urlsplit
            try:
                url = urlsplit(result.get("url", ""))
                valid = (type(result.get("amount_minor")) is int and result["amount_minor"] == args.amount_minor
                    and result.get("currency") == "eur" and result.get("request_id") == args.request_id
                    and isinstance(result.get("id"), str) and result["id"].startswith("plink_")
                    and isinstance(result.get("price_id"), str) and result["price_id"].startswith("price_")
                    and url.scheme == "https" and url.hostname == "buy.stripe.com"
                    and not url.username and not url.password and url.port in (None, 443)
                    and bool(url.path.strip("/")) and not url.query and not url.fragment)
            except ValueError:
                valid = False
        elif action == "detail":
            valid = isinstance(result.get("data"), dict)
        else:
            valid = (isinstance(result.get("data"), list)
                     and type(result.get("has_more")) is bool
                     and (not result["has_more"] or isinstance(result.get("next_cursor"), str)))
        if not valid:
            raise StripeClientError("The engine returned incomplete Stripe evidence; retry or update the engine.")
        print(json.dumps(result, ensure_ascii=False))
        return 0


def command(args) -> int:
    try:
        return asyncio.run(execute(args))
    except StripeClientError as exc:
        message = str(exc)
    except (Exception, KeyboardInterrupt):
        message = ("Creation outcome unavailable. Retry only the same request_id and identical inputs; check engine availability and Desktop Settings." if args.stripe_action == "payment-link-create" else "Stripe lookup failed. Check engine availability, sign-in and the Stripe connection in Desktop Settings.")
    print(json.dumps({"error": "stripe_unavailable", "message": message}))
    return 1


def register(sub) -> None:
    parser = sub.add_parser("stripe", help="use Stripe records and explicit Payment Links through Desktop")
    actions = parser.add_subparsers(dest="stripe_action", required=True)
    create = actions.add_parser("payment-link-create", help="create one fixed EUR Payment Link on explicit human request")
    create.set_defaults(func=command)
    create.add_argument("--amount-minor", required=True, type=int, help="exact EUR cents (35 EUR = 3500)")
    create.add_argument("--label", required=True)
    create.add_argument("--request-id", required=True, help="stable opaque identifier; reuse on retries")
    for name in ("status", "customers", "payments", "invoices", "subscriptions", "detail"):
        child = actions.add_parser(name)
        child.set_defaults(func=command)
        if name == "detail":
            child.add_argument("resource", choices=RESOURCES)
            child.add_argument("id")
        elif name != "status":
            child.add_argument("--limit", type=bounded_limit, default=10)
            child.add_argument("--starting-after")
            if name == "customers":
                child.add_argument("--email")
            else:
                child.add_argument("--customer")
