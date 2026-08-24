"""Generic SMS send via the company's SMS proxy.

The proxy endpoint comes from the manifest (``[sms].proxy_base``, the full
send-URL); it authenticates with the SAME engine ID token as the RPC
(header ``auth``) and bills the business in ``SMS_BUSINESS_ID`` (env —
the endpoint refuses to guess; the id is validated server-side).

Locks live here as defence-in-depth even though the campaign handler
already gates: ``[sms].enabled``, the ``CS_PAUSE`` file.
Gmail-dedup ("did they reply") is the CALLER's job — this module only
knows a phone number.

Raises :class:`SmsError` with the reason on ANY failure — never a silent
False (a swallowed SMS failure looks like a sent nudge).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class SmsError(RuntimeError):
    """SMS refused or failed; the message carries the actionable reason."""


def send(settings, phone: str, message: str) -> None:
    if not settings.sms_enabled:
        raise SmsError('[sms].enabled is false in manifest.toml — SMS capability is off')
    if not settings.sms_proxy_base:
        # Not reachable by leaving the field alone: the endpoint is a kernel
        # default since v0.19.0. Getting here means something DECLARED it
        # empty, so say that instead of telling the operator to set a key the
        # wizard never asks about.
        raise SmsError(
            "the SMS endpoint is declared empty — something set [sms].proxy_base "
            "or SMS_PROXY_BASE to a blank value, which switches the proxy off. "
            "Run `cs config` to see which layer declared it."
        )
    if not phone:
        raise SmsError("no phone number")
    if settings.pause_path.exists():
        raise SmsError("CS_PAUSE active — global kill-switch")

    from . import auth

    payload: dict = {"phone_number": phone, "message": message}
    if settings.sms_business_id:
        payload["business_id"] = settings.sms_business_id
    req = urllib.request.Request(
        settings.sms_proxy_base,
        data=json.dumps(payload).encode(),
        headers={"auth": auth.get_id_token(settings), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            if resp.status != 200:
                raise SmsError(f"SMS proxy HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:200]
        except Exception:  # noqa: BLE001
            pass
        raise SmsError(f"SMS proxy HTTP {e.code} {e.reason} {detail}".strip()) from None
    except urllib.error.URLError as e:
        raise SmsError(f"SMS proxy unreachable: {e.reason}") from None
