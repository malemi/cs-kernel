#!/usr/bin/env python3
"""`cs config` — the resolved value AND where it came from.

The failure this verb exists for: two consecutive headless operator ticks read
"no CS_TRIAGE_MODE environment variable" as "so the default draft applies",
while manifest.toml declared `send` and `config.load()` returned `send`. The
gates below are the claims that failure needs to stay fixed.

  1. a value declared in the manifest reports the manifest, naming the TOML
     table and key — the file to edit;
  2. an env layer that overrides it reports THAT layer and its env KEY;
  3. process env beats every file layer;
  4. a knob NOT written in manifest.toml reports "kernel default", never the
     manifest — `settings_overrides` always emits the numeric/bool knobs, so a
     naive reading would send a reader to a `[knobs]` line that is not there;
  5. the duplicate-declaration warning fires when one setting is declared in
     two layers — INCLUDING when the two agree today, which is the case the
     platform owner banned ("MAI avere due repository di verità");
  6. two alias spellings of one setting inside the SAME file are flagged too;
  7. NO secret value is ever printed — not in the text report, not in --json,
     not under --all;
  8. the CS_PAUSE kill-switch is reported by path AND current presence;
  9. MANIFEST_KEYS does not drift from manifest.settings_overrides;
 10. --strict turns a duplicate into an exit code; the default stays 0,
     because a read verb that exits non-zero reads as "the question failed";
 11. a bare install with no manifest at all still answers.

Everything runs against a REAL `python -m cs config` subprocess with a sandbox
HOME and a trial manifest — no company value from any real clone.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cs import config_report
from cs import manifest as manifest_mod

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
adapter = "none"

[producer]
adapter = "none"

[campaigns]
excluded_campaign = "legacy-campaign"

[knobs]
cs_triage_mode = "send"
"""

SECRET_PW = "sandbox-password-do-not-print"
SECRET_KEY = "sandbox-web-api-key-do-not-print"
SECRET_TOKEN = "sandbox-shopify-token-do-not-print"


def _clean_env(home: Path) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
        and k
        not in (
            "DEDUP_DAYS",
            "DRY_RUN",
            "SLUG",
            "TIMEZONE",
            "ACCOUNTS",
            "ACCOUNTS_DEFAULT",
            "EXCLUDED_CAMPAIGN",
            "CRM_ADAPTER",
            "PRODUCER_ADAPTER",
            "TOKEN_CACHE_PATH",
            "REFRESH_TOKEN_PATH",
        )
    }
    env["HOME"] = str(home)
    return env


def _run(repo: Path, env: dict, *argv: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "cs", "config", *argv],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _report(repo: Path, env: dict, *argv: str) -> dict:
    rc, out, err = _run(repo, env, "--json", *argv)
    assert rc == 0, f"cs config --json exited {rc}:\n{err}"
    return json.loads(out)


def _by_name(rep: dict) -> dict:
    """Every setting the report carries, indexed by name."""
    out: dict[str, dict] = {}
    for sec in rep["sections"]:
        for f in sec["settings"]:
            out[f["name"]] = f
    for f in rep["secrets"]:
        out[f["name"]] = f
    for f in rep["all"] or []:
        out[f["name"]] = f
    return out


# ------------------------------------------------------- 9. anti-drift on the
#                                                             manifest key map


def _fill(model_cls):
    """A manifest sub-model with every field populated — so settings_overrides
    emits everything it is capable of emitting (it skips empty strings)."""
    import typing

    from pydantic import BaseModel

    kwargs = {}
    for name, info in model_cls.model_fields.items():
        ann = info.annotation
        args = typing.get_args(ann)
        if args and type(None) in args:  # Optional[SubModel]
            ann = next(a for a in args if a is not type(None))
        if typing.get_origin(ann) is dict:
            kwargs[name] = {"default": "x"}
        elif isinstance(ann, type) and issubclass(ann, BaseModel):
            kwargs[name] = _fill(ann)
        elif ann is bool:
            kwargs[name] = True
        elif ann is int:
            kwargs[name] = 7
        elif ann is str:
            kwargs[name] = "x"
        else:  # a shape this helper does not know: leave the model default
            continue
    return model_cls(**kwargs)


def _manifest_key_map_in_step() -> None:
    full = _fill(manifest_mod.Manifest)
    emitted = set(manifest_mod.settings_overrides(full))
    mapped = set(config_report.MANIFEST_KEYS)
    assert emitted == mapped, (
        "config_report.MANIFEST_KEYS has drifted from manifest.settings_overrides:\n"
        f"  emitted but unmapped: {sorted(emitted - mapped)}\n"
        f"  mapped but never emitted: {sorted(mapped - emitted)}"
    )
    # Every mapped TOML path must actually exist in a full manifest, or the
    # report would look for a key the schema cannot hold.
    dumped = full.model_dump()
    for field_name, path in config_report.MANIFEST_KEYS.items():
        node = dumped
        for part in path:
            assert isinstance(node, dict) and part in node, (
                f"MANIFEST_KEYS[{field_name!r}] = {path} does not resolve in the "
                "manifest schema"
            )
            node = node[part]


# ---------------------------------------------------------------------- main


def main() -> int:
    _manifest_key_map_in_step()

    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home")
        home.mkdir()
        repo = Path(td, "repo")
        repo.mkdir()
        state = home / ".acme-cs"
        state.mkdir()
        (repo / "manifest.toml").write_text(MANIFEST)
        (state / ".env").write_text(
            f"EMAIL_PASSWORD={SECRET_PW}\n"
            f"FIREBASE_WEB_API_KEY={SECRET_KEY}\n"
            f"SHOPIFY_ADMIN_TOKEN={SECRET_TOKEN}\n"
            "CS_ACCOUNTS=ops:uid-ops-acme\n"
        )
        env = _clean_env(home)

        # -- 1. manifest provenance, named down to the TOML table+key --------
        rep = _report(repo, env)
        f = _by_name(rep)
        assert f["cs_triage_mode"]["value"] == "send", f["cs_triage_mode"]
        assert f["cs_triage_mode"]["layer"] == "manifest", f["cs_triage_mode"]
        assert f["cs_triage_mode"]["origin"] == "manifest.toml [knobs].cs_triage_mode", (
            "provenance must name the file AND the key to edit: "
            f"{f['cs_triage_mode']['origin']}"
        )
        assert f["engine_owner_uid"]["origin"] == "manifest.toml [engine].owner_uid"
        assert f["accounts_default"]["origin"] == "manifest.toml [engine.accounts].default"
        assert f["excluded_campaign"]["value"] == "legacy-campaign"
        assert f["crm_adapter"]["origin"] == "manifest.toml [crm].adapter"
        assert rep["duplicates"] == [], rep["duplicates"]
        # The manifest declares `sa_path = "~/…"` and Settings resolves it to
        # the absolute form. That is the SAME declaration, and reporting it as
        # an unexplained value would put a spurious `?` on a correct config —
        # a cross-check that cries wolf gets ignored the day it is right.
        assert rep["notes"] == [], rep["notes"]
        assert rep["mismatched"] == [], rep["mismatched"]

        # the text report says the same thing (this is what an agent reads)
        rc, out, _ = _run(repo, env)
        assert rc == 0, rc
        assert "cs_triage_mode" in out and "send" in out
        assert "manifest.toml [knobs].cs_triage_mode" in out, out

        # -- 4. a knob NOT written in the manifest is a kernel default -------
        # dedup_days is absent from [knobs] above, yet settings_overrides emits
        # it unconditionally. Reporting "manifest.toml" here would send the
        # reader to a line that does not exist.
        assert f["dedup_days"]["value"] == 30, f["dedup_days"]
        assert f["dedup_days"]["origin"] == "kernel default", f["dedup_days"]
        assert f["dedup_days"]["declarations"] == [], f["dedup_days"]

        # -- 7. no secret value, anywhere ------------------------------------
        for secret in (SECRET_PW, SECRET_KEY, SECRET_TOKEN):
            assert secret not in out, "text report leaked a secret value"
        rc_all, out_all, _ = _run(repo, env, "--all")
        assert rc_all == 0
        _, json_all, _ = _run(repo, env, "--json", "--all")
        for secret in (SECRET_PW, SECRET_KEY, SECRET_TOKEN):
            assert secret not in out_all, "--all leaked a secret value"
            assert secret not in json_all, "--json --all leaked a secret value"
        assert f["email_password"]["value"] == "set", f["email_password"]
        assert f["email_password"]["secret"] is True
        assert "EMAIL_PASSWORD" in f["email_password"]["origin"], (
            "presence is not enough — the report must name the env KEY: "
            f"{f['email_password']['origin']}"
        )
        # the declaration records must not carry the value either
        for d in f["email_password"]["declarations"]:
            assert "value" not in d, d

        # -- 8. the kill-switch, by path and by presence ---------------------
        assert rep["pause"]["path"].endswith("/CS_PAUSE"), rep["pause"]
        assert rep["pause"]["present"] is False
        (state / "CS_PAUSE").write_text("")
        paused = _report(repo, env)
        assert paused["pause"]["present"] is True
        rc_p, out_p, _ = _run(repo, env)
        assert "PAUSED" in out_p, out_p
        (state / "CS_PAUSE").unlink()

        # -- 2. + 5. an env layer overrides it, and BOTH are reported --------
        (repo / ".env").write_text("CS_TRIAGE_MODE=draft\n")
        rep2 = _report(repo, env)
        f2 = _by_name(rep2)
        assert f2["cs_triage_mode"]["value"] == "draft", f2["cs_triage_mode"]
        assert f2["cs_triage_mode"]["layer"] == "repo"
        assert f2["cs_triage_mode"]["origin"] == ".env (CS_TRIAGE_MODE)", (
            f2["cs_triage_mode"]["origin"]
        )
        dups = {d["name"] for d in rep2["duplicates"]}
        assert dups == {"cs_triage_mode"}, rep2["duplicates"]
        decls = rep2["duplicates"][0]["declarations"]
        assert [d["layer"] for d in decls] == ["manifest", "repo"], decls
        assert [d["value"] for d in decls] == ["send", "draft"], decls
        rc2, out2, _ = _run(repo, env)
        assert rc2 == 0, "a read verb answers the question; --strict is the hook"
        assert "DUPLICATE DECLARATIONS" in out2, out2

        # -- 10. --strict turns it into an exit code -------------------------
        rc_strict, _, _ = _run(repo, env, "--strict")
        assert rc_strict == 1, rc_strict

        # -- 5b. the warning fires even when the two declarations AGREE ------
        (repo / ".env").write_text("CS_TRIAGE_MODE=send\n")
        rep3 = _report(repo, env)
        assert {d["name"] for d in rep3["duplicates"]} == {"cs_triage_mode"}, (
            "a duplicate that agrees TODAY is still two repositories of truth"
        )
        assert _by_name(rep3)["cs_triage_mode"]["value"] == "send"
        (repo / ".env").unlink()

        # -- 3. process env beats every file layer ---------------------------
        env_p = dict(env)
        env_p["CS_TRIAGE_MODE"] = "draft"
        rep4 = _report(repo, env_p)
        f4 = _by_name(rep4)
        assert f4["cs_triage_mode"]["value"] == "draft"
        assert f4["cs_triage_mode"]["layer"] == "process", f4["cs_triage_mode"]
        assert f4["cs_triage_mode"]["origin"] == "process env (CS_TRIAGE_MODE)"
        assert {d["name"] for d in rep4["duplicates"]} == {"cs_triage_mode"}

        # -- 6. two alias spellings inside ONE file ---------------------------
        # CS_ENGINE_OWNER_UID and ENGINE_OWNER_UID both feed engine_owner_uid;
        # the first wins silently, which is the same disease one layer down.
        (repo / ".env").write_text(
            "CS_ENGINE_OWNER_UID=uid-from-alias\nENGINE_OWNER_UID=uid-shadowed\n"
        )
        rep5 = _report(repo, env)
        f5 = _by_name(rep5)
        assert f5["engine_owner_uid"]["value"] == "uid-from-alias", f5["engine_owner_uid"]
        assert f5["engine_owner_uid"]["origin"] == ".env (CS_ENGINE_OWNER_UID)"
        dup5 = {d["name"] for d in rep5["duplicates"]}
        assert "engine_owner_uid" in dup5, rep5["duplicates"]
        shadow = [
            d["shadowed"]
            for d in next(
                x for x in rep5["duplicates"] if x["name"] == "engine_owner_uid"
            )["declarations"]
            if d["shadowed"]
        ]
        assert shadow == [["ENGINE_OWNER_UID"]], shadow
        rc5, out5, _ = _run(repo, env)
        assert "ENGINE_OWNER_UID" in out5 and "same layer" in out5, out5
        (repo / ".env").unlink()

        # -- 11. no manifest at all: the verb still answers -------------------
        bare = Path(td, "bare")
        bare.mkdir()
        rep6 = _report(bare, env)
        f6 = _by_name(rep6)
        assert rep6["manifest"] is None
        assert f6["cs_triage_mode"]["value"] == "draft"
        assert f6["cs_triage_mode"]["origin"] == "kernel default"

        # -- 12. the THREE-file chain: a platform env layer, and the prefixed
        # Shopify source that sits above the process environment ------------
        # The scan mirrors pydantic-settings by hand, so both of the shapes it
        # could mislabel get exercised: the optional lowest layer, and the
        # custom source whose prefix comes from the MANIFEST (not from the
        # resolved shopify_env_prefix field — an env-set prefix does not
        # change which keys that source reads).
        plat = Path(td, "platform.env")
        plat.write_text(
            "export SHOPIFY_ACME_STORE_DOMAIN=prefixed.example\n"
            "SHOPIFY_STORE_DOMAIN=bare-fallback.example\n"
            "CS_TRIAGE_MODE=send\n"
        )
        repo2 = Path(td, "repo2")
        repo2.mkdir()
        (repo2 / "manifest.toml").write_text(
            MANIFEST.replace(
                '[crm]\nadapter = "none"',
                '[crm]\nadapter = "shopify"\n\n[crm.shopify]\nenv_prefix = "SHOPIFY_ACME"',
            )
            + f'\n[env]\nplatform_env_path = "{plat}"\n'
        )
        rep7 = _report(repo2, env, "--all")
        f7 = _by_name(rep7)
        assert [lay["id"] for lay in rep7["layers"]] == ["platform", "home", "repo"], (
            rep7["layers"]
        )
        assert f7["shopify_store_domain"]["value"] == "prefixed.example", (
            "the prefixed key must win over the bare SHOPIFY_* fallback: "
            f"{f7['shopify_store_domain']}"
        )
        assert f7["shopify_store_domain"]["layer"] == "shopify-prefix", (
            f7["shopify_store_domain"]
        )
        assert "SHOPIFY_ACME_STORE_DOMAIN" in f7["shopify_store_domain"]["origin"]
        # the platform file is a real layer, named by its own path
        assert f7["cs_triage_mode"]["value"] == "send"
        assert f7["cs_triage_mode"]["layer"] == "platform", f7["cs_triage_mode"]
        assert str(plat) in f7["cs_triage_mode"]["origin"], f7["cs_triage_mode"]
        # ...and the manifest declares it too, so it is a duplicate
        assert "cs_triage_mode" in {d["name"] for d in rep7["duplicates"]}
        # nothing anywhere failed the resolved-value cross-check
        assert rep7["notes"] == [], rep7["notes"]

        # -- 12b. the prefix the prefixed source uses is the MANIFEST's -------
        # An env-set SHOPIFY_ENV_PREFIX changes the settings FIELD but not
        # which keys `_ShopifyPrefixSource` reads (config.load seeds it from
        # the manifest overrides). Reading the field here would have the report
        # name a key that never fed the value.
        env_x = dict(env)
        env_x["SHOPIFY_ENV_PREFIX"] = "SHOPIFY_OTHER"
        env_x["SHOPIFY_OTHER_STORE_DOMAIN"] = "other-prefix.example"
        rep8 = _by_name(_report(repo2, env_x, "--all"))
        assert rep8["shopify_env_prefix"]["value"] == "SHOPIFY_OTHER"
        assert rep8["shopify_store_domain"]["value"] == "prefixed.example", (
            "the store domain still comes from the MANIFEST prefix: "
            f"{rep8['shopify_store_domain']}"
        )
        assert "SHOPIFY_ACME_STORE_DOMAIN" in rep8["shopify_store_domain"]["origin"], (
            "provenance must name the key that actually fed the value: "
            f"{rep8['shopify_store_domain']['origin']}"
        )

        # -- 13. a provenance it cannot verify is reported as UNVERIFIED ------
        # The scan mirrors pydantic-settings by hand; a mirror can drift. When
        # the winning declaration does not explain the value the settings
        # object actually holds, the report must say so rather than narrate a
        # source it has not established. Simulated by holding a value no layer
        # declares: the manifest still says `send`, the settings object says
        # otherwise, and the scan has no honest way to attribute it.
        probe = (
            "import json, sys;"
            "from cs import config, config_report;"
            "s = config.load();"
            "s.cs_triage_mode = 'value-no-layer-declares';"
            "r = config_report.build(s);"
            "f = {x['name']: x for sec in r['sections'] for x in sec['settings']};"
            "print(json.dumps({'notes': r['notes'], 'mismatched': r['mismatched'],"
            " 'value': f['cs_triage_mode']['value'],"
            " 'line': [l for l in config_report.render(r).splitlines()"
            "          if l.strip().startswith('cs_triage_mode')]}))"
        )
        proc = subprocess.run(
            [sys.executable, "-c", probe], cwd=repo, env=env,
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        probed = json.loads(proc.stdout)
        assert probed["mismatched"] == ["cs_triage_mode"], probed
        assert "UNVERIFIED" in probed["notes"][0], probed
        # the VALUE stays the real resolved one — only the provenance is doubted
        assert probed["value"] == "value-no-layer-declares", probed
        assert probed["line"] and probed["line"][0].strip().endswith(
            "? manifest.toml [knobs].cs_triage_mode"
        ), probed["line"]

    print("test_config_report: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
