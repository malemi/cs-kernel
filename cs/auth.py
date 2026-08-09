"""Headless Firebase ID token for the operator mailbox's engine.

Mints a custom token for ``CS_ENGINE_OWNER_UID`` signing LOCALLY with the
service-account private key (no IAM signBlob API, no extra role needed),
exchanges it via identitytoolkit ``signInWithCustomToken``, and caches the
resulting ID token on disk until ~5 minutes before expiry.

The engine daemon (zylch-server@<uid>) verifies this token on the WebSocket
handshake and gates ``token.sub == OWNER_ID`` — we never bypass that gate.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
from pathlib import Path

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials

from .config import ConfigError, Settings

_EXCHANGE_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={key}"
)
_SKEW_SECONDS = 300  # refresh when less than 5 minutes of life remain

_app = None


def _ensure_app(settings: Settings):
    global _app
    if _app is None:
        cred = credentials.Certificate(settings.firebase_sa_path)
        # Fixed neutral app name: the string is internal to firebase_admin's
        # in-process registry and never leaves the host (kernel constant).
        _app = firebase_admin.initialize_app(cred, name="cs-kernel-mint")
    return _app


def _token_exp(id_token: str) -> int:
    """Read `exp` from the JWT payload (introspection only, no verify —
    the engine does the real RS256 verification)."""
    payload = id_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return int(json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0))


def _cache_path(settings: Settings) -> Path:
    return Path(settings.token_cache_path)


def _read_cache(settings: Settings) -> str | None:
    p = _cache_path(settings)
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    token = data.get("id_token")
    if not token or data.get("uid") != settings.engine_owner_uid:
        return None
    if _token_exp(token) - time.time() < _SKEW_SECONDS:
        return None
    return token


def _write_cache(settings: Settings, id_token: str) -> None:
    p = _cache_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"uid": settings.engine_owner_uid, "id_token": id_token}))
    os.chmod(p, 0o600)


def get_id_token(settings: Settings, force: bool = False) -> str:
    """Return a valid Firebase ID token for the engine owner uid."""
    if not settings.engine_owner_uid:
        raise ConfigError(
            "CS_ENGINE_OWNER_UID not set — export it in the profile env; it is "
            "the engine owner's uid (cs/scripts/find_profile_uid.py can look it up)"
        )
    if not settings.firebase_web_api_key:
        raise ConfigError(
            "FIREBASE_WEB_API_KEY not set — export it in the profile env; it is "
            "the Web API key of the engine's Firebase project"
        )

    if not force:
        cached = _read_cache(settings)
        if cached:
            return cached

    app = _ensure_app(settings)
    custom = fb_auth.create_custom_token(settings.engine_owner_uid, app=app)
    req = urllib.request.Request(
        _EXCHANGE_URL.format(key=settings.firebase_web_api_key),
        data=json.dumps({"token": custom.decode(), "returnSecureToken": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    id_token = resp["idToken"]
    _write_cache(settings, id_token)
    return id_token
