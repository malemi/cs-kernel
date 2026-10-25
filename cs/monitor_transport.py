"""Bounded authenticated diagnostic transport. No redirects, effects or retry loops."""

from __future__ import annotations

import json
import urllib.request
import urllib.parse

from .monitor_config import Endpoint


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(endpoint: Endpoint, payload: dict) -> dict:
    """One bounded attempt; incident persistence decides when another is allowed."""
    raw = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > 262144:
        raise ValueError("Diagnostic transport limit")
    request = urllib.request.Request(
        endpoint.url,
        data=raw,
        method="POST",
        headers={"Authorization": "Bearer " + endpoint.token(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=12 if urllib.parse.urlsplit(endpoint.url).path.endswith("/alerts") else 3) as response:
            body = response.read(8193)
        if len(body) > 8192:
            raise ValueError("Diagnostic acknowledgement limit")
        result = json.loads(body)
        if not isinstance(result, dict) or result.get("accepted") is not True:
            raise ValueError("Diagnostic delivery not acknowledged")
        return {"accepted": True}
    except Exception as exc:
        from .monitor_process import ObservationError, safe_failure

        raise ObservationError(safe_failure(exc)) from None


def post(endpoint: Endpoint, payload: dict) -> dict:
    """Apply an absolute deadline even if a peer keeps trickling bytes."""
    from .monitor_process import bounded

    return bounded("post", (endpoint, payload), seconds=12 if urllib.parse.urlsplit(endpoint.url).path.endswith("/alerts") else 3)


def _get(endpoint: Endpoint, view: str, params: dict, credential: str | None = None) -> dict:
    if view not in {"status", "events"}:
        raise ValueError("Invalid watchdog view")
    parsed = urllib.parse.urlsplit(endpoint.url)
    url = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rsplit("/", 1)[0] + "/" + view,
            urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}),
            "",
        )
    )
    token = endpoint.token() if credential is None else credential
    if not 32 <= len(token) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("Invalid diagnostic credential")
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=3) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError("Watchdog response limit")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Invalid watchdog response")
    return result


def get(endpoint: Endpoint, view: str, params: dict, *, credential: str | None = None) -> dict:
    from .monitor_process import bounded

    return bounded("get", (endpoint, view, params, credential), seconds=3)
