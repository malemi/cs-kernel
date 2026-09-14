"""Supervised SIP changes with preview and explicit, private secret handoff.

Remote changes are not transactional. Preserve recovery credentials before the
first write, never retry an ambiguous mutation and never delete on failure.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from .vonage import DOMAIN_FIELDS, ProviderError, domain_name, user_key


def public_ips(values: list[str]) -> list[str]:
    if not values:
        raise ProviderError("public PBX IP addresses are required; request them from the technician")
    out = []
    for value in values:
        try:
            network = ipaddress.ip_network(value, strict=True)
        except ValueError:
            raise ProviderError("PBX ACL entries must be canonical public IPv4 addresses or CIDRs") from None
        if network.version != 4 or not network.is_global or network.is_multicast or network.is_reserved:
            raise ProviderError("PBX ACL entries must be public IPv4 addresses or CIDRs; no private or all-address ranges")
        # A broad range may contain private/special addresses even if its
        # endpoints are public. Check every special network from the standard
        # library's classifier, not just the two endpoints.
        special = ipaddress.IPv4Address._constants._private_networks
        if any(network.overlaps(block) for block in special) or network.overlaps(ipaddress.ip_network('100.64.0.0/10')):
            raise ProviderError("PBX ACL range includes non-public addresses")
        canonical = str(network)
        if canonical not in out:
            out.append(canonical)
    return out


def require_commit_context(settings):
    if os.environ.get("CS_OPERATOR_HEADLESS") or os.environ.get("CS_HEADLESS_SEND") or not sys.stdin.isatty():
        raise ProviderError("Vonage changes require an interactive operator terminal; headless commits are refused")
    if settings.pause_path.exists():
        raise ProviderError("operator is paused; provider changes refused")


def require_application(settings, app_id):
    if app_id not in settings.connections.vonage.application_ids:
        raise ProviderError("application is not in this clone's Vonage application_ids allowlist")


def complete_domain(data):
    if data is None or any(k not in data for k in DOMAIN_FIELDS):
        raise ProviderError("Vonage domain state is incomplete; changes refused")
    if data["domain_type"] != "app" or not data["application_id"]:
        raise ProviderError("this workflow changes application domains only")
    if not isinstance(data["digest_auth"], bool) or not isinstance(data["acl"], list):
        raise ProviderError("Vonage domain authentication state is incomplete")
    if data["tls"] not in ("always", "never", "optional") or data["srtp"] not in ("always", "never", "optional"):
        raise ProviderError("Vonage media security settings are invalid")
    return data


def secret_destination(settings, raw: str) -> Path:
    path = Path(raw).expanduser().absolute()
    root = settings.state_dir.expanduser().resolve()
    if path.parent.resolve() != root or path.parent.is_symlink() or path.name in (".", ".."):
        raise ProviderError("choose a new secret file directly inside this clone's private state directory")
    try:
        st = path.parent.stat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ProviderError("secret directory must be owned by this user with mode 0700")
        if path.exists() or path.is_symlink():
            raise ProviderError("secret destination already exists; choose a new file and inspect prior recovery state")
    except OSError:
        raise ProviderError("private state directory is not accessible; create it with mode 0700 first") from None
    return path


def provision(client, settings, *, name, app_id, ips, username, secret_file, commit=False):
    name, username = domain_name(name), user_key(username)
    require_application(settings, app_id)
    acl = public_ips(ips)
    destination = secret_destination(settings, secret_file)
    if commit:
        require_commit_context(settings)
    client.application(app_id)
    if client.domain(name) is not None:
        raise ProviderError("domain already exists; inspect it and its users instead of creating or rotating credentials")
    payload = {"name": name, "application_id": app_id, "domain_type": "app",
               "digest_auth": True, "acl": acl, "tls": "optional", "srtp": "optional"}
    plan = {"action": "provision", "domain": payload, "username": username,
            "region": settings.connections.vonage.region, "secret_file": str(destination),
            "readiness": "number association and a real PBX call test are still required"}
    if not commit:
        return {"preview": True, **plan}
    # A second preflight immediately before side effects reduces the preview
    # race. Provider conflict responses still cause a stop, never an overwrite.
    if client.domain(name) is not None:
        raise ProviderError("domain appeared during preflight; changes refused")
    require_commit_context(settings)
    secret = secrets.token_urlsafe(32)
    record = {"domain": name, "application_id": app_id, "username": username,
              "secret": secret, "region": settings.connections.vonage.region}
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
    except OSError:
        raise ProviderError("cannot save recovery credentials securely; no provider mutation attempted") from None
    stage = "credentials saved; domain creation not verified"
    try:
        require_commit_context(settings)
        client.create_domain(payload)
        observed = complete_domain(client.domain(name))
        if observed != payload:
            raise ProviderError("created domain readback differs from the requested configuration")
        stage = "domain verified; digest user creation not verified"
        require_commit_context(settings)
        client.create_user(name, username, secret)
        if {"key": username, "domain": name} not in client.users(name):
            raise ProviderError("created digest user was not found on readback")
        if complete_domain(client.domain(name)) != payload:
            raise ProviderError("domain configuration changed during user creation")
    except ProviderError as e:
        raise ProviderError(f"partial or uncertain provisioning: {stage}; {e}. Recovery file: {destination}. Inspect before any retry") from None
    return {"preview": False, "verified": True,
            "verification": "domain configuration and digest user existence; SIP authentication and calls not tested",
            **plan}


def allow_ip(client, settings, *, name, ips, commit=False):
    name = domain_name(name)
    additions = public_ips(ips)
    if commit:
        require_commit_context(settings)
    before = complete_domain(client.domain(name))
    require_application(settings, before["application_id"])
    # Do not pretend adding a narrow entry restricts an already open ACL.
    public_ips(before["acl"])
    client.application(before["application_id"])
    desired = dict(before)
    current_networks = {ipaddress.ip_network(x, strict=True) for x in before["acl"]}
    desired["acl"] = before["acl"] + [x for x in additions if ipaddress.ip_network(x) not in current_networks]
    plan = {"action": "allow-ip", "before": before, "after": desired,
            "concurrency": "PSIP exposes no documented conditional update; avoid concurrent dashboard or API edits"}
    if not commit:
        return {"preview": True, **plan}
    if complete_domain(client.domain(name)) != before:
        raise ProviderError("domain changed during preflight; review a fresh preview")
    if desired == before:
        return {"preview": False, "verified": True, "changed": False, **plan}
    try:
        require_commit_context(settings)
        client.update_domain(name, desired)
        if complete_domain(client.domain(name)) != desired:
            raise ProviderError("ACL readback does not match the requested configuration")
    except ProviderError as e:
        raise ProviderError(f"ACL change outcome uncertain: {e}; inspect the domain before retrying") from None
    return {"preview": False, "verified": True, "changed": True, **plan}
