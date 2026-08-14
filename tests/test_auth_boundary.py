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
"""
from __future__ import annotations

import base64
import json
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

    print(
        "OK: auth boundary — missing/mismatched refresh file -> handled ConfigError; "
        "_write_refresh mode 0600; cache hit never touches the refresh/network path"
    )


if __name__ == "__main__":
    run()
