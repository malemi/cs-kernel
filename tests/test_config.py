#!/usr/bin/env python3
"""Config semantics — the gates that matter, against a REAL subprocess with a
sandbox HOME and a trial manifest (no company value from any real clone):

  - derived paths: state_dir/db/token-cache/SA all under ~/.<slug>-cs
  - layer precedence: process env > repo .env > home .env > platform env
    > manifest > kernel default
  - shopify <PREFIX>_ keys beat the bare SHOPIFY_* fallback
  - unknown adapter in the manifest = LOUD startup error
  - session paths (token cache, refresh token) derive PER ACCOUNT UID —
    id_token-<uid>.json / refresh_token-<uid>.json, empty uid keeps the
    legacy un-suffixed name, an explicit override always wins over derivation
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cs.config import Settings

DUMP = r"""
import json
from cs import config
s = config.load()
print(json.dumps({
    "state_dir": str(s.state_dir),
    "db_path": s.db_path,
    "token_cache_path": s.token_cache_path,
    "refresh_token_path": s.refresh_token_path,
    "firebase_sa_path": s.firebase_sa_path,
    "pause_path": str(s.pause_path),
    "log_path": str(s.log_path),
    "prog_name": s.prog_name,
    "slug": s.slug,
    "email_address": s.email_address,
    "email_from_name": s.email_from_name,
    "email_password": s.email_password,
    "engine_owner_uid": s.engine_owner_uid,
    "engine_ws_url": s.engine_ws_url,
    "crm_adapter": s.crm_adapter,
    "shopify_env_prefix": s.shopify_env_prefix,
    "shopify_store_domain": s.shopify_store_domain,
    "producer_adapter": s.producer_adapter,
    "excluded_campaign": s.excluded_campaign,
    "dedup_days": s.dedup_days,
    "rate_cap": s.rate_cap,
    "timezone": s.timezone,
    "sms_hour": s.sms_hour,
    "reminder_max": s.reminder_max,
    "sms_enabled": s.sms_enabled,
    "sms_proxy_base": s.sms_proxy_base,
    "drive_scope": s.drive_scope,
}))
"""

MANIFEST = """\
[company]
name = "Acme"
display_name = "Acme"
from_name = "Acme Ops"
slug = "acme"
prog_name = "acme-cs"

[operator]
email_address = "ops@acme.example"

[engine]
owner_uid = "uid-ops-acme"
ws_url = "wss://engine.example"
sa_path = "~/.acme-cs/firebase-sa.json"

[engine.accounts]
default = "ops"
ops = "uid-ops-acme"

[crm]
adapter = "shopify"

[crm.shopify]
api_version = "2025-10"
env_prefix = "SHOPIFY_ACME"

[producer]
adapter = "none"

[campaigns]
excluded_campaign = "legacy-campaign"

[knobs]
dedup_days = 21
rate_cap = 25
timezone = "Europe/Madrid"
sms_hour = 19
reminder_max = 2

[sms]
enabled = true
proxy_base = "https://sms.example/api/send"

[drive]
scope = "ACMEDRV"

[env]
platform_env_path = "{platform_env}"

[skills]
triage_domain_examples = "company/triage-domain-examples.md"

[repo]
kernel_version = "v0.1.0"
"""


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN",
                         "TOKEN_CACHE_PATH", "REFRESH_TOKEN_PATH")}
    env["HOME"] = str(home)
    return env


def _dump(repo: Path, env: dict) -> dict:
    proc = subprocess.run([sys.executable, "-c", DUMP], cwd=repo, env=env,
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"config dump failed:\n{proc.stderr}"
    return json.loads(proc.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        repo = Path(td, "repo"); repo.mkdir()
        state = home / ".acme-cs"; state.mkdir()
        platform_env = Path(td, "platform.env")
        # platform layer: lowest env layer; `export K=V` lines must parse
        platform_env.write_text(
            "export RATE_CAP=7\n"
            "export SHOPIFY_ACME_STORE_DOMAIN=acme-prefixed.example\n"
            "SHOPIFY_STORE_DOMAIN=bare-fallback.example\n"
        )
        # home layer: beats platform
        (state / ".env").write_text("RATE_CAP=9\nEMAIL_PASSWORD=sandbox-pw\n")
        (repo / "manifest.toml").write_text(
            MANIFEST.format(platform_env=str(platform_env))
        )

        env = _clean_env(home)
        d = _dump(repo, env)

        # -- derived paths, all under the sandbox HOME's ~/.<slug>-cs --
        assert d["state_dir"] == str(state), d["state_dir"]
        assert d["db_path"] == str(state / "cs.db"), d["db_path"]
        assert d["token_cache_path"] == str(state / "id_token-uid-ops-acme.json")
        assert d["refresh_token_path"] == str(state / "refresh_token-uid-ops-acme.json")
        assert d["firebase_sa_path"] == str(state / "firebase-sa.json"), \
            f"manifest ~ not expanded into sandbox HOME: {d['firebase_sa_path']}"
        assert d["pause_path"] == str(state / "CS_PAUSE")
        assert d["log_path"] == str(state / "cs_operator.log")

        # -- manifest identity --
        assert d["prog_name"] == "acme-cs"
        assert d["slug"] == "acme"
        assert d["email_address"] == "ops@acme.example"
        assert d["email_from_name"] == "Acme Ops"
        assert d["engine_owner_uid"] == "uid-ops-acme"
        assert d["engine_ws_url"] == "wss://engine.example"
        assert d["crm_adapter"] == "shopify"
        assert d["producer_adapter"] == "none"
        assert d["excluded_campaign"] == "legacy-campaign"
        assert d["drive_scope"] == "ACMEDRV"

        # -- knobs: manifest beats kernel defaults --
        assert d["dedup_days"] == 21
        assert d["timezone"] == "Europe/Madrid"
        assert d["sms_hour"] == 19
        assert d["reminder_max"] == 2
        assert d["sms_enabled"] is True
        assert d["sms_proxy_base"] == "https://sms.example/api/send"

        # -- env layering: home .env (9) beats platform (7) beats manifest (25) --
        assert d["rate_cap"] == 9, f"rate_cap layering broken: {d['rate_cap']}"
        assert d["email_password"] == "sandbox-pw"

        # -- process env beats everything --
        env2 = dict(env); env2["RATE_CAP"] = "11"
        assert _dump(repo, env2)["rate_cap"] == 11

        # -- prefixed shopify key beats the bare fallback --
        assert d["shopify_env_prefix"] == "SHOPIFY_ACME"
        assert d["shopify_store_domain"] == "acme-prefixed.example", \
            f"prefix resolution broken: {d['shopify_store_domain']}"

        # -- --account style override: CS_ENGINE_OWNER_UID env wins --
        env3 = dict(env); env3["CS_ENGINE_OWNER_UID"] = "uid-other"
        assert _dump(repo, env3)["engine_owner_uid"] == "uid-other"

        # -- no manifest at all: tolerant load (--help must work) --
        empty = Path(td, "empty"); empty.mkdir()
        d0 = _dump(empty, env)
        assert d0["prog_name"] == "cs" and d0["email_address"] == ""
        assert d0["state_dir"] == str(home / ".cs")

        # -- unknown adapter: LOUD startup error --
        bad = Path(td, "bad"); bad.mkdir()
        (bad / "manifest.toml").write_text('[crm]\nadapter = "hubspot"\n')
        proc = subprocess.run([sys.executable, "-c", DUMP], cwd=bad, env=env,
                              capture_output=True, text=True)
        assert proc.returncode != 0, "unknown adapter must fail loud"
        assert "unknown CRM adapter 'hubspot'" in (proc.stderr + proc.stdout)

        # -- mrcall-tracking without paths: LOUD --
        bad2 = Path(td, "bad2"); bad2.mkdir()
        (bad2 / "manifest.toml").write_text('[producer]\nadapter = "mrcall-tracking"\n')
        proc = subprocess.run([sys.executable, "-c", DUMP], cwd=bad2, env=env,
                              capture_output=True, text=True)
        assert proc.returncode != 0
        assert "script_path" in (proc.stderr + proc.stdout)

    # -- per-uid session-file derivation (in-process; state_dir only shapes
    # the PREFIX via Path.home(), so these assert on the BASENAME only — no
    # sandbox HOME needed). `_env_file=()` only disables the DOTENV layer —
    # env_settings stays live — so an ambient CS_ENGINE_OWNER_UID /
    # ENGINE_OWNER_UID / TOKEN_CACHE_PATH / REFRESH_TOKEN_PATH in the
    # invoking process's own environment would otherwise leak into these
    # Settings and make the pins non-hermetic. Save/pop/restore, same idiom
    # as tests/test_login.py's CS_ZYLCH_ROOT guard. --
    _leak_keys = ("CS_ENGINE_OWNER_UID", "ENGINE_OWNER_UID",
                  "TOKEN_CACHE_PATH", "REFRESH_TOKEN_PATH")
    _saved_env = {k: os.environ.get(k) for k in _leak_keys}
    for k in _leak_keys:
        os.environ.pop(k, None)
    try:
        no_uid = Settings(_env_file=(), slug="acme")
        assert Path(no_uid.token_cache_path).name == "id_token.json", no_uid.token_cache_path
        assert Path(no_uid.refresh_token_path).name == "refresh_token.json", \
            no_uid.refresh_token_path

        with_uid = Settings(_env_file=(), slug="acme", engine_owner_uid="u1")
        assert Path(with_uid.token_cache_path).name == "id_token-u1.json", \
            with_uid.token_cache_path
        assert Path(with_uid.refresh_token_path).name == "refresh_token-u1.json", \
            with_uid.refresh_token_path

        explicit = Settings(
            _env_file=(), slug="acme", engine_owner_uid="u1",
            token_cache_path="/x/cache.json",
        )
        assert explicit.token_cache_path == "/x/cache.json", explicit.token_cache_path
    finally:
        for k, v in _saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print("test_config: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
