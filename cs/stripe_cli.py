"""Read-only bridge to the engine-owned Stripe connection."""
from __future__ import annotations

import argparse
import asyncio
import json

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


async def call(client, method: str, params: dict | None = None) -> dict:
    try:
        result = await client.call(method, params or {}, timeout=60)
    except rpc.EngineError as exc:
        if exc.code == -32601:
            raise StripeClientError("Update the engine to use Stripe, then connect Stripe in Desktop Settings.") from None
        raise StripeClientError("Stripe lookup unavailable. Check the connection and read permissions in Desktop Settings.") from None
    if not isinstance(result, dict):
        raise StripeClientError("The engine returned an unsupported Stripe response; update the engine.")
    return result


async def execute(args) -> int:
    async with rpc.EngineClient(config.load()) as client:
        status = await call(client, "stripe.status")
        if args.stripe_action == "status":
            print(json.dumps(status, ensure_ascii=False))
            return 0
        if status.get("status") != "connected":
            raise StripeClientError(CONNECT)
        action = args.stripe_action
        capability = args.resource if action == "detail" else action
        if capability in {"payment_intents", "charges"}:
            capability = "payments"
        capabilities = status.get("capabilities")
        if not isinstance(capabilities, list) or capability not in capabilities:
            raise StripeClientError("This Stripe resource is unavailable. Check read permissions in Desktop Settings.")
        if action == "detail":
            params = {"resource": args.resource, "id": args.id}
        else:
            params = {"limit": args.limit}
            for key in ("starting_after", "customer", "email"):
                value = getattr(args, key, None)
                if value is not None:
                    params[key] = value
        result = await call(client, "stripe." + action, params)
        account = status.get("account")
        account_id = account.get("id") if isinstance(account, dict) else None
        result_account = result.get("account_id")
        if (not account_id or result_account != account_id
                or result.get("mode") != status.get("mode")
                or result.get("generation") != status.get("generation")):
            raise StripeClientError("Stripe connection changed during lookup; retry against the current connection.")
        if not isinstance(result.get("retrieved_at_utc"), str):
            raise StripeClientError("The engine returned Stripe evidence without retrieval provenance.")
        if action == "detail":
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
        message = "Stripe lookup failed. Check engine availability, sign-in and the Stripe connection in Desktop Settings."
    print(json.dumps({"error": "stripe_unavailable", "message": message}))
    return 1


def register(sub) -> None:
    parser = sub.add_parser("stripe", help="read Stripe records through the Desktop connection")
    actions = parser.add_subparsers(dest="stripe_action", required=True)
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
