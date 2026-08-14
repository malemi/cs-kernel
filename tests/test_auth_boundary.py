#!/usr/bin/env python3
"""Semantic guard for the refresh-token auth boundary (`cs/auth.py`).

NO network, NO mock servers: every case here is reachable without an HTTP
call, so a stubbed transport would be theatre. Each `Settings` is built
directly (explicit kwargs beat every env/dotenv layer — see
`settings_customise_sources` in `cs/config.py`) with its state paths pointed
at a fresh temp dir per case, so nothing here can touch the real
`~/.<slug>-cs` state on the machine running the suite.

Guards:
  (i)   no refresh file at all -> ConfigError naming `cs login`
  (ii)  a refresh file for a DIFFERENT uid -> ConfigError (identity mismatch
        must be caught before any network call is attempted)
  (iii) `_write_refresh` writes uid-tagged JSON at mode 0600
  (iv)  a still-valid cached id_token is returned straight from the cache,
        proven by pointing `refresh_token_path` at a directory that does not
        exist: if `get_id_token` ever fell through to the refresh/exchange
        path it would blow up on that path, not silently reach the network
  (v)   per-uid session files coexist with no cross-talk: two accounts'
        token-cache/refresh-token paths derive to distinct, uid-suffixed
        basenames under the SAME state dir; both refresh files can be
        written and read back simultaneously (mode 0600, each its own uid +
        token); both id-token caches likewise coexist and each account's
        `get_id_token` call returns exactly its own cached token
"""
from __future__ import annotations

import base64
import json
import os
import stat
import tempfile
import time
from pathlib import Path

from cs import auth
from cs.config import ConfigError, Settings

UID = "uid-test-abc123"
OTHER_UID = "uid-someone-else"


def _settings(root: Path, **overrides) -> Settings:
    fields = {
        "engine_owner_uid": UID,
        "firebase_web_api_key": "fake-web-api-key",
        "token_cache_path": str(root / "id_token.json"),
        "refresh_token_path": str(root / "refresh_token.json"),
    }
    fields.update(overrides)
    # _env_file=() disables the dotenv layer entirely: this test must not
    # depend on (or be broken by) whatever happens to sit at the invoking
    # process's CWD.
    return Settings(_env_file=(), **fields)


def _fake_jwt(exp: int) -> str:
    """A JWT shape `_token_exp` can read: base64url payload only, no real
    header/signature and no crypto — introspection-only, exactly what
    `_token_exp` does (the engine performs the real RS256 verification)."""
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=")
    return f"unused-header.{payload.decode()}.unused-signature"


def run() -> None:
    # -- (i) no refresh file at all -----------------------------------
    with tempfile.TemporaryDirectory() as td:
        settings = _settings(Path(td))
        try:
            auth.get_id_token(settings)
            raise AssertionError("expected ConfigError with no refresh file present")
        except ConfigError as e:
            assert "cs login" in str(e), f"message must point at `cs login`: {e}"

    # -- (ii) refresh file present but for a DIFFERENT uid -------------
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        settings = _settings(root)
        (root / "refresh_token.json").write_text(
            json.dumps({"uid": OTHER_UID, "refresh_token": "rt-belongs-to-other-uid"})
        )
        try:
            auth.get_id_token(settings)
            raise AssertionError("expected ConfigError on uid mismatch")
        except ConfigError as e:
            msg = str(e)
            assert UID in msg and OTHER_UID in msg, (
                f"message must name BOTH uids (stored + configured): {msg}"
            )

    # -- (iii) _write_refresh: uid-tagged JSON, mode 0600 ---------------
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        settings = _settings(root)
        auth._write_refresh(settings, "rt-freshly-written")
        p = Path(settings.refresh_token_path)
        assert p.exists(), "refresh file was not created"
        tmp = p.with_name(p.name + ".tmp")
        assert not tmp.exists(), f"atomic write left a stray {tmp} behind"
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600, f"refresh file mode is {oct(mode)}, expected 0o600"
        written = json.loads(p.read_text())
        assert written == {"uid": UID, "refresh_token": "rt-freshly-written"}, written

    # -- (iv) valid cached id_token returned WITHOUT touching the network -
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        far_future = int(time.time()) + 365 * 24 * 3600
        token = _fake_jwt(far_future)
        cache_path = root / "id_token.json"
        cache_path.write_text(json.dumps({"uid": UID, "id_token": token}))
        # Point refresh_token_path at a NONEXISTENT directory: if the cache
        # read were skipped or missed, the code would have to reach the
        # refresh file (or the network) next and this would either raise a
        # missing-file ConfigError or attempt a real HTTP call — neither of
        # which happens here, proving the cache hit short-circuits both.
        settings = _settings(
            root,
            token_cache_path=str(cache_path),
            refresh_token_path=str(root / "does-not-exist" / "refresh_token.json"),
        )
        result = auth.get_id_token(settings)
        assert result == token, "cached id_token must be returned verbatim"

    # -- (v) per-uid session files coexist, no cross-talk ----------------
    with tempfile.TemporaryDirectory() as td:
        old_home = os.environ.get("HOME")
        # TOKEN_CACHE_PATH / REFRESH_TOKEN_PATH would leak in via env_settings
        # too: engine_owner_uid/firebase_web_api_key below are explicit init
        # kwargs (which always beat env), but token_cache_path/
        # refresh_token_path are NOT explicitly set here, so an ambient value
        # for either would silently override the very derivation this guard
        # is proving. uid keys are irrelevant here — engine_owner_uid IS
        # explicit, so no ambient CS_ENGINE_OWNER_UID/ENGINE_OWNER_UID can
        # override it.
        old_token_cache = os.environ.get("TOKEN_CACHE_PATH")
        old_refresh_token = os.environ.get("REFRESH_TOKEN_PATH")
        os.environ["HOME"] = td
        os.environ.pop("TOKEN_CACHE_PATH", None)
        os.environ.pop("REFRESH_TOKEN_PATH", None)
        try:
            state = Path(td) / ".acme-cs"
            state.mkdir()
            settings_a = Settings(
                _env_file=(), slug="acme", engine_owner_uid=UID,
                firebase_web_api_key="fake-web-api-key",
            )
            settings_b = Settings(
                _env_file=(), slug="acme", engine_owner_uid=OTHER_UID,
                firebase_web_api_key="fake-web-api-key",
            )

            # -- derived paths: distinct suffixed basenames, same state dir --
            token_a, refresh_a = Path(settings_a.token_cache_path), Path(settings_a.refresh_token_path)
            token_b, refresh_b = Path(settings_b.token_cache_path), Path(settings_b.refresh_token_path)
            for p in (token_a, refresh_a, token_b, refresh_b):
                assert p.parent == state, f"not under the sandbox state dir: {p}"
            assert token_a.name == f"id_token-{UID}.json", token_a
            assert refresh_a.name == f"refresh_token-{UID}.json", refresh_a
            assert token_b.name == f"id_token-{OTHER_UID}.json", token_b
            assert refresh_b.name == f"refresh_token-{OTHER_UID}.json", refresh_b
            assert len({token_a.name, refresh_a.name, token_b.name, refresh_b.name}) == 4, \
                "the four basenames must be pairwise distinct"

            # -- both refresh files coexist, mode 0600, each its own uid+token --
            auth._write_refresh(settings_a, "rt-a")
            auth._write_refresh(settings_b, "rt-b")
            assert refresh_a.exists() and refresh_b.exists(), \
                "both per-uid refresh files must exist simultaneously"
            assert stat.S_IMODE(refresh_a.stat().st_mode) == 0o600
            assert stat.S_IMODE(refresh_b.stat().st_mode) == 0o600
            assert json.loads(refresh_a.read_text()) == {"uid": UID, "refresh_token": "rt-a"}
            assert json.loads(refresh_b.read_text()) == {"uid": OTHER_UID, "refresh_token": "rt-b"}

            # -- both id-token caches coexist; each account's cache hit
            # serves ITS OWN token (the uid tag inside the cache JSON plus
            # the per-uid filename both isolate — a cross-read would return
            # the wrong token or fall through toward the refresh/network
            # path, which guard (iv) above already proves cannot happen
            # silently) --
            far_future = int(time.time()) + 365 * 24 * 3600
            # The two cached tokens must be DIFFERENT strings, or the
            # no-cross-talk assertions below are vacuous (they would still
            # pass even if get_id_token read the wrong account's cache).
            token_val_a = _fake_jwt(far_future)
            token_val_b = _fake_jwt(far_future + 60)
            auth._write_cache(settings_a, token_val_a)
            auth._write_cache(settings_b, token_val_b)
            assert auth.get_id_token(settings_a) == token_val_a
            assert auth.get_id_token(settings_b) == token_val_b
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_token_cache is None:
                os.environ.pop("TOKEN_CACHE_PATH", None)
            else:
                os.environ["TOKEN_CACHE_PATH"] = old_token_cache
            if old_refresh_token is None:
                os.environ.pop("REFRESH_TOKEN_PATH", None)
            else:
                os.environ["REFRESH_TOKEN_PATH"] = old_refresh_token

    print(
        "OK: auth boundary — missing/mismatched refresh file -> handled ConfigError; "
        "_write_refresh mode 0600; cache hit never touches the refresh/network path; "
        "per-uid session files coexist with no cross-talk"
    )


if __name__ == "__main__":
    run()
