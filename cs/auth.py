"""Headless Firebase ID token for the operator mailbox's engine.

The desktop app owns the interactive Firebase sign-in and is the usual
source of the Firebase *refresh* token: `cs login` reads the profile
descriptor the desktop app writes at sign-in and stores that token locally
(``settings.refresh_token_path``). `mint_refresh_token` below is the other
source — it signs and exchanges one locally, for a uid this clone's own
Firebase service-account key can sign for, with no descriptor and no
interactive sign-in. Either way, every call in this module turns the
stored refresh token into a fresh, short-lived ID token through Google's
Secure Token API — mirroring the engine's own headless refresh
(``mrcall-desktop/engine/zylch/auth/refresh.py``: ``exchange_refresh_token``
/ ``ensure_fresh_session``) — and caches the result on disk until ~5
minutes before expiry.

The engine daemon (zylch-server@<uid>) verifies this token on the WebSocket
handshake and gates ``token.sub == OWNER_ID`` — we never bypass that gate.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import ConfigError, Settings

# Google's Secure Token API — form-encoded body, web API key as a query
# param. Same endpoint and request shape the engine uses.
_SECURE_TOKEN_URL = "https://securetoken.googleapis.com/v1/token?key={key}"
# Identity Toolkit's custom-token exchange — used only by `mint_refresh_token`.
_SIGN_IN_WITH_CUSTOM_TOKEN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={key}"
)
_SKEW_SECONDS = 300  # refresh when less than 5 minutes of life remain

_mint_app = None  # module-global Firebase app for minting; see _ensure_mint_app


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
    if not token or data.get("uid") != (settings.engine_owner_uid or "").strip():
        return None
    if _token_exp(token) - time.time() < _SKEW_SECONDS:
        return None
    return token


def _write_cache(settings: Settings, id_token: str) -> None:
    p = _cache_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"uid": (settings.engine_owner_uid or "").strip(), "id_token": id_token}
    )
    # 0600 from creation, never a world-readable window; tmp+rename so a
    # concurrent reader never sees a half-written long-lived credential.
    tmp = p.with_name(p.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, p)


def _refresh_path(settings: Settings) -> Path:
    return Path(settings.refresh_token_path)


def _read_refresh(settings: Settings) -> dict | None:
    """Read the stored refresh-token descriptor
    (``{"uid": ..., "refresh_token": ...}``, written by `cs login`).

    Returns None if the file is missing, unparsable, or carries no token —
    the caller turns that into the "not signed in" ConfigError. The uid
    check is deliberately the CALLER's job, not this function's, so the
    resulting error can name both the stored and the configured uid.
    """
    p = _refresh_path(settings)
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("refresh_token"):
        return None
    return data


def _write_refresh(settings: Settings, refresh_token: str) -> None:
    p = _refresh_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"uid": (settings.engine_owner_uid or "").strip(), "refresh_token": refresh_token}
    )
    # 0600 from creation, never a world-readable window; tmp+rename so a
    # concurrent reader never sees a half-written long-lived credential.
    tmp = p.with_name(p.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, p)
    # A stored session's id-token cache must not survive it: `get_id_token`
    # reads the cache FIRST and never compares it against the refresh file
    # (see `_read_cache` / `get_id_token` below), so a cache left over from
    # the PREVIOUS session would let every call — including `cs login`'s own
    # `account.who_am_i` proof — succeed on the session that was just
    # replaced, not the one just written. Delete it only after the refresh
    # file's rename above has landed, so a failed write never leaves an
    # account with neither file.
    _cache_path(settings).unlink(missing_ok=True)


def _exchange(settings: Settings, refresh_token: str) -> dict:
    """POST the refresh token to Google's Secure Token API and return the
    parsed JSON response.

    Mirrors the engine's own exchange
    (``zylch/auth/refresh.py::exchange_refresh_token``): a form-encoded
    ``grant_type=refresh_token&refresh_token=…`` body against
    ``securetoken.googleapis.com``, the web API key as a query param.

    Every failure surfaces as ONE handled ``ConfigError`` line — never a
    traceback — naming what happened and, where known, what to do about it.
    """
    url = _SECURE_TOKEN_URL.format(key=settings.firebase_web_api_key)
    body = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()
        except Exception:  # noqa: BLE001
            pass
        err_code = None
        try:
            err_code = json.loads(body_text).get("error", {}).get("message")
        except (ValueError, AttributeError, TypeError):
            pass
        parts = [f"Secure Token API exchange failed: HTTP {e.code} {e.reason}"]
        if err_code:
            parts.append(
                f"({err_code}) — sign in again in the desktop app, then re-run `cs login`"
            )
        if e.code == 403:
            parts.append(
                "— this can also be an API-key restriction: the web API key "
                "must allow the Token Service / Identity Toolkit APIs for "
                "this host"
            )
        raise ConfigError(" ".join(parts)) from None
    except urllib.error.URLError:
        raise ConfigError("cannot reach securetoken.googleapis.com — network?") from None

    try:
        return json.loads(raw)
    except ValueError as e:
        raise ConfigError(f"Secure Token API returned an unparsable response: {e}") from None


def _ensure_mint_app(settings: Settings):
    """Module-global Firebase app used only by `mint_refresh_token`.

    Mirrors `cs/resolve.py::_ensure_app`'s pattern exactly, but under a
    fixed neutral name distinct from that module's ``"cs-kernel-resolve"``
    — a second `initialize_app` call under a name already registered
    raises, so the two mint/resolve call sites cannot share one.

    `firebase_admin` is imported HERE, not at module scope: `cs/rpc.py`
    imports this module, so every verb — `--help` included — would
    otherwise pay ~0.2s to import a package only minting ever uses.
    """
    import firebase_admin
    from firebase_admin import credentials
    global _mint_app
    if _mint_app is None:
        cred = credentials.Certificate(settings.firebase_sa_path)
        _mint_app = firebase_admin.initialize_app(cred, name="cs-kernel-mint")
    return _mint_app


def mint_refresh_token(settings: Settings, uid: str) -> str:
    """Mint a refresh token for `uid` with no interactive sign-in and no
    descriptor, using this clone's own Firebase service-account key.

    Two calls to Google, error handling mirroring `_exchange` above
    exactly: every failure — an unreadable or invalid key file, an HTTP
    error from the exchange, a response with no ``refreshToken`` — raises
    ONE handled `ConfigError` naming what happened, never a traceback,
    and never token material, the private key, or the web API key in the
    message.

      1. Sign a custom token LOCALLY for `uid`
         (``firebase_admin.auth.create_custom_token``) — no IAM round
         trip, just the private key at `settings.firebase_sa_path`.
      2. Exchange it at Google's Identity Toolkit
         ``accounts:signInWithCustomToken`` for a refresh token, using
         this clone's own `settings.firebase_web_api_key` — the same key
         `_exchange` reads.

    The returned refresh token authenticates as `uid` exactly as a
    descriptor-born one does: the engine daemon's ``token.sub ==
    OWNER_ID`` gate cannot tell the two apart.
    """
    try:
        from firebase_admin import auth as fa_auth  # lazy, see _ensure_mint_app

        app = _ensure_mint_app(settings)
        custom_token = fa_auth.create_custom_token(uid, app=app)
    except Exception as e:  # noqa: BLE001 — the SDK raises many types (bad/missing key file, invalid uid, …)
        raise ConfigError(
            f"could not sign a custom token for uid {uid!r}: {type(e).__name__}: {e} "
            "— check that this clone's Firebase service-account key "
            "(settings.firebase_sa_path) is present and valid"
        ) from None
    token_str = custom_token.decode() if isinstance(custom_token, bytes) else custom_token

    url = _SIGN_IN_WITH_CUSTOM_TOKEN_URL.format(key=settings.firebase_web_api_key)
    body = json.dumps({"token": token_str, "returnSecureToken": True}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode()
        except Exception:  # noqa: BLE001
            pass
        err_code = None
        try:
            err_code = json.loads(body_text).get("error", {}).get("message")
        except (ValueError, AttributeError, TypeError):
            pass
        parts = [f"accounts:signInWithCustomToken failed: HTTP {e.code} {e.reason}"]
        if err_code:
            parts.append(f"({err_code})")
        if e.code == 403:
            parts.append(
                "— this can also be an API-key restriction: the web API key "
                "must allow the Token Service / Identity Toolkit APIs for "
                "this host"
            )
        raise ConfigError(" ".join(parts)) from None
    except urllib.error.URLError:
        raise ConfigError(
            "cannot reach identitytoolkit.googleapis.com — network?"
        ) from None

    try:
        resp = json.loads(raw)
    except ValueError as e:
        raise ConfigError(
            f"accounts:signInWithCustomToken returned an unparsable response: {e}"
        ) from None

    refresh_token = resp.get("refreshToken")
    if not refresh_token:
        raise ConfigError(
            "accounts:signInWithCustomToken response carried no refreshToken"
        )
    return refresh_token


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

    stored = _read_refresh(settings)
    if stored is None:
        raise ConfigError(
            "not signed in — run `cs login` (it reads the profile descriptor "
            "the desktop app writes at sign-in)"
        )
    configured_uid = (settings.engine_owner_uid or "").strip()
    if stored.get("uid") != configured_uid:
        raise ConfigError(
            "this clone's profile does not match the stored session "
            f"(stored uid {stored.get('uid')!r} != configured uid "
            f"{configured_uid!r}) — re-run `cs login`"
        )
    refresh_token = stored["refresh_token"]

    resp = _exchange(settings, refresh_token)

    resp_uid = resp.get("user_id")
    if resp_uid != configured_uid:
        raise ConfigError(
            f"Secure Token API returned a session for uid {resp_uid!r}, "
            f"expected {configured_uid!r} — re-run `cs login`"
        )
    id_token = resp.get("id_token")
    if not id_token:
        raise ConfigError("Secure Token API response carried no id_token")

    new_refresh = resp.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        _write_refresh(settings, new_refresh)

    _write_cache(settings, id_token)
    return id_token
