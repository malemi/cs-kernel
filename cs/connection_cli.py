"""Provider CLI dispatch; connections are clone-scoped, never engine-account-scoped."""
from __future__ import annotations

import json
import sys

from . import config
from .vonage import Client, ProviderError


def register(sub):
    root = sub.add_parser("connection", help="configured external provider connections")
    providers = root.add_subparsers(dest="provider", required=True)
    vonage = providers.add_parser("vonage", help="Vonage account and Programmable SIP")
    actions = vonage.add_subparsers(dest="connection_action", required=True)
    for action, desc in (("status", "verify the configured account and voice applications"),
                         ("domains", "list account SIP domains"),
                         ("show", "inspect one SIP domain"),
                         ("users", "list digest users without secrets")):
        parser = actions.add_parser(action, help=desc)
        if action in ("show", "users"):
            parser.add_argument("domain")
        parser.set_defaults(func=run)
    parser = actions.add_parser("provision", help="preview a new application SIP domain; --commit applies interactively")
    parser.add_argument("domain")
    parser.add_argument("--application", required=True)
    parser.add_argument("--ip", action="append", required=True, help="confirmed public IPv4 or CIDR; repeat for multiple")
    parser.add_argument("--username", required=True)
    parser.add_argument("--secret-file", required=True, help="new private file inside this clone's state directory")
    parser.add_argument("--commit", action="store_true")
    parser.set_defaults(func=run)
    parser = actions.add_parser("allow-ip", help="preview additive ACL change; --commit applies interactively")
    parser.add_argument("domain")
    parser.add_argument("--ip", action="append", required=True)
    parser.add_argument("--commit", action="store_true")
    parser.set_defaults(func=run)


def run(args):
    try:
        settings = config.load()
        binding = settings.connections.vonage
        client = Client(*config.connection_credentials(settings))
        action = args.connection_action
        if action == "status":
            domains = client.domains()
            out = {"provider": "vonage", "authenticated": True,
                   "region": binding.region, "domains": len(domains),
                   "applications": [client.application(a) for a in binding.application_ids]}
        elif action == "domains":
            out = {"domains": client.domains()}
        elif action == "show":
            out = client.domain(args.domain)
            if out is None:
                raise ProviderError("SIP domain does not exist on the configured account")
        elif action == "users":
            out = {"users": client.users(args.domain)}
        elif action in ("provision", "allow-ip"):
            from . import sip_provision
            if action == "provision":
                out = sip_provision.provision(client, settings, name=args.domain,
                    app_id=args.application, ips=args.ip, username=args.username,
                    secret_file=args.secret_file, commit=args.commit)
            else:
                out = sip_provision.allow_ip(client, settings, name=args.domain,
                    ips=args.ip, commit=args.commit)
        else:
            raise ProviderError("unknown provider operation")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    except config.ConfigError as e:
        print(f"connection: {e}", file=sys.stderr)
        return 1
