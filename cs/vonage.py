"""Vonage Programmable SIP transport. No messaging, retries or credential logging.

The public contract is https://developer.vonage.com/en/api/psip . The Node CLI
does not expose this SIP surface; both use the same account key/secret.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

import requests

from .config import ConfigError


class ProviderError(ConfigError):
    """Safe operator-facing error; never contains a provider response body."""


def domain_name(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{3,30}[a-z0-9]", value):
        raise ProviderError("domain must be a 5–32 character lowercase SIP domain name, not a URL")
    return value


def user_key(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]{1,64}", value):
        raise ProviderError("user key must contain 1–64 lowercase letters, digits or dashes")
    return value


DOMAIN_FIELDS = ("name", "application_id", "domain_type", "digest_auth", "acl", "tls", "srtp")


def public_domain(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("name"), str):
        raise ProviderError("Vonage returned an invalid domain response")
    domain_name(data["name"])
    # Explicit allowlist excludes credentials and unknown provider fields.
    out = {k: data[k] for k in DOMAIN_FIELDS if k in data}
    for k in ("application_id", "domain_type", "tls", "srtp"):
        if k in out and out[k] is not None and not isinstance(out[k], str):
            raise ProviderError("Vonage returned an invalid domain field")
    if "acl" in out and (not isinstance(out["acl"], list) or
                         any(not isinstance(x, str) for x in out["acl"])):
        raise ProviderError("Vonage returned an invalid ACL")
    if "digest_auth" in out and not isinstance(out["digest_auth"], bool):
        raise ProviderError("Vonage returned invalid authentication settings")
    return out


class Client:
    def __init__(self, api_key: str, api_secret: str):
        self._auth = (api_key, api_secret)
        self._session = requests.Session()
        # Do not inherit netrc credentials or an ambient proxy for another clone.
        self._session.trust_env = False

    def request(self, method: str, path: str, payload=None, *, missing=False):
        try:
            response = self._session.request(
                method, "https://api.nexmo.com" + path, auth=self._auth,
                json=payload, timeout=(5, 20), allow_redirects=False,
            )
        except requests.RequestException:
            raise ProviderError(
                "Vonage request failed; inspect current state before retrying a write"
            ) from None
        with response:
            if missing and response.status_code == 404:
                return None
            if not 200 <= response.status_code < 300:
                raise ProviderError(f"Vonage HTTP {response.status_code}; response body withheld")
            if not response.content:
                if method == "GET":
                    raise ProviderError("Vonage returned an empty read response; evidence incomplete")
                return None
            try:
                data = response.json()
            except (ValueError, json.JSONDecodeError):
                raise ProviderError("Vonage returned invalid JSON; inspect state before retrying a write") from None
            if data is None and method == "GET":
                raise ProviderError("Vonage returned a null read response; evidence incomplete")
            return data

    def domains(self) -> list[dict]:
        data = self.request("GET", "/v1/psip/")
        if not isinstance(data, list):
            raise ProviderError("Vonage domain listing was incomplete or malformed")
        return [public_domain(row) for row in data]

    def domain(self, name: str) -> dict | None:
        data = self.request("GET", "/v1/psip/" + quote(domain_name(name)), missing=True)
        if data is None:
            return None
        out = public_domain(data)
        if out["name"] != name:
            raise ProviderError("Vonage returned a different domain; stopped")
        return out

    def users(self, name: str) -> list[dict]:
        data = self.request("GET", "/v1/psip/" + quote(domain_name(name)) + "/users")
        if not isinstance(data, list):
            raise ProviderError("Vonage user listing was incomplete or malformed")
        out = []
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get("key"), str):
                raise ProviderError("Vonage returned an invalid user")
            user_key(row["key"])
            if row.get("domain") != name:
                raise ProviderError("Vonage returned a user for a different domain")
            out.append({"key": row["key"], "domain": name})
        return out

    def application(self, app_id: str) -> dict:
        data = self.request("GET", "/v2/applications/" + quote(app_id, safe=""))
        if not isinstance(data, dict) or data.get("id") != app_id:
            raise ProviderError("Vonage returned an invalid application")
        if not isinstance(data.get("capabilities"), dict) or "voice" not in data["capabilities"]:
            raise ProviderError("selected Vonage application has no voice capability")
        return {"id": app_id, "name": data.get("name"), "capabilities": list(data["capabilities"])}

    def create_domain(self, payload: dict):
        self.request("POST", "/v1/psip/", payload)

    def create_user(self, name: str, key: str, secret: str):
        self.request("POST", "/v1/psip/" + quote(domain_name(name)) + "/users",
                     {"key": user_key(key), "secret": secret})

    def update_domain(self, name: str, payload: dict):
        self.request("PUT", "/v1/psip/" + quote(domain_name(name)), payload)
