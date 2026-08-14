#!/usr/bin/env python3
"""Semantic guard for `cs login` (`cs/login.py`) and the two nearby human
verbs that share its machinery: `cs init`'s descriptor-based prefill
(`project_init.descriptor_defaults()`, which reuses `login.descriptor_root`/
`scan_descriptors`/`parse_descriptor`) and `cs update`'s new argparse layer.

NO real network egress anywhere: the `account.who_am_i` proof call succeeding
(step 7 of `cmd_login`) needs a live engine and is deliberately out of scope
here — see `tests/test_auth_boundary.py` for the (also network-free)
auth-boundary guard `cs login` feeds. The proof call FAILING is in scope
(guard viii below): it dials a closed local port, which refuses the TCP
connect immediately, so nothing ever leaves the machine.

Guards:
  (i)   `parse_descriptor` accepts a valid fixture and rejects: bad JSON,
        wrong version, and each missing required field (message names the
        missing field).
  (ii)  `scan_descriptors`, rooted at a temp tree via `CS_ZYLCH_ROOT`, finds
        the real descriptors and does not choke on an invalid one sitting
        next to them (parsing — and therefore skipping — is the caller's
        job, exercised here directly).
  (iii) `cmd_login` with zero descriptors found: a real `python -m cs
        login` subprocess, stdin closed, exits 1 and names the
        mrcall-desktop app on stderr.
  (iv)  `_identity_conflict`, exercised directly against a hand-built
        `Settings` (no `config.load()`, no filesystem, no network — mirrors
        `tests/test_auth_boundary.py`'s `_settings()` helper): a uid
        mismatch refuses naming BOTH uids; an email mismatch refuses naming
        both emails but is case-insensitive; an empty configured uid
        refuses pointing at `cs init`.
  (v)   `project_init.descriptor_defaults()`, hermetic via `CS_ZYLCH_ROOT`:
        `{}` on zero valid descriptors, `{}` on two (`cs init` stays
        neutral — picking among signed-in profiles is `cs login`'s job),
        the mapped dict on exactly one — and its `engine_ws_url` is the
        BASE (no `/ws/` left in it), not the descriptor's full per-uid URL.
  (vi)  `cs update --help`: a real `python -m cs update --help` subprocess
        exits 0 and prints usage, proving Task 3's argparse layer runs
        before the manifest check (no `template-manifest.json` needed in
        the cwd).
  (vii) `descriptor_ws_base` strips the descriptor's own `/ws/<uid>` suffix
        and passes a bare base through unchanged when the suffix isn't there.
  (viii) `cmd_login`'s proof-call failure (closed local port, `get_id_token`
        stubbed): exits 1, names the failure, and — the point of this guard
        — never lets a raw traceback reach stderr.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cs import login
from cs.config import Settings

UID = "uid-test-abc123"
OTHER_UID = "uid-someone-else"


def _valid_descriptor(**overrides) -> dict:
    d = {
        "version": 1,
        "email": "ops@acme.example",
        "uid": UID,
        "engine_ws_url": "wss://engine.example/ws",
        "firebase_web_api_key": "fake-web-api-key",
        "refresh_token": "rt-abc",
        "written_at": "2026-08-14T10:00:00Z",
    }
    d.update(overrides)
    return d


def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def _test_parse_descriptor() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # -- valid fixture --
        good = _write(root / "good.json", _valid_descriptor())
        parsed = login.parse_descriptor(good)
        assert parsed["uid"] == UID and parsed["email"] == "ops@acme.example", parsed

        # -- bad JSON --
        bad_json = _write(root / "bad.json", "{not json")
        try:
            login.parse_descriptor(bad_json)
            raise AssertionError("expected ValueError on invalid JSON")
        except ValueError as e:
            assert "not valid JSON" in str(e), str(e)

        # -- wrong version --
        wrong_version = _write(root / "wrong_version.json", _valid_descriptor(version=2))
        try:
            login.parse_descriptor(wrong_version)
            raise AssertionError("expected ValueError on unsupported version")
        except ValueError as e:
            assert "version" in str(e) and "2" in str(e), (
                f"message must name the version actually found: {e}"
            )

        # -- each missing required field, one at a time: message names it --
        for field in login.REQUIRED_STRING_FIELDS:
            d = _valid_descriptor()
            del d[field]
            p = _write(root / f"missing_{field}.json", d)
            try:
                login.parse_descriptor(p)
                raise AssertionError(f"expected ValueError with {field!r} missing")
            except ValueError as e:
                assert field in str(e), (
                    f"message must name the missing field {field!r}: {e}"
                )

    print(
        "OK: parse_descriptor — valid fixture accepted; bad JSON / wrong "
        "version / each missing field rejected, naming the reason"
    )


def _test_descriptor_ws_base() -> None:
    """`descriptor_ws_base` strips the descriptor's own `/ws/<uid>` suffix
    (the shape `cs/rpc.py::EngineClient.url` re-appends onto the configured
    BASE) and passes a bare base straight through when the suffix is not
    there — proving the two are safe to compare after normalization."""
    full = login.descriptor_ws_base(
        _valid_descriptor(engine_ws_url=f"wss://engine.example/ws/{UID}")
    )
    assert full == "wss://engine.example", full

    bare = login.descriptor_ws_base(
        _valid_descriptor(engine_ws_url="wss://engine.example")
    )
    assert bare == "wss://engine.example", bare

    print(
        "OK: descriptor_ws_base — strips the descriptor's own `/ws/<uid>` "
        "suffix; a bare base URL (no suffix) passes through unchanged"
    )


def _test_scan_descriptors() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good1 = _write(
            root / "profiles" / "uid-aaa" / login.DESCRIPTOR_FILENAME,
            _valid_descriptor(uid="uid-aaa", email="a@acme.example"),
        )
        good2 = _write(
            root / "profiles" / "uid-bbb" / login.DESCRIPTOR_FILENAME,
            _valid_descriptor(uid="uid-bbb", email="b@acme.example"),
        )
        bad = _write(
            root / "profiles" / "uid-ccc" / login.DESCRIPTOR_FILENAME,
            "{not json",
        )

        found = login.scan_descriptors(root)
        assert set(found) == {good1, good2, bad}, found

        parsed_ok, skipped = [], []
        for p in found:
            try:
                parsed_ok.append(login.parse_descriptor(p))
            except ValueError as e:
                skipped.append((p, str(e)))
        assert {d["uid"] for d in parsed_ok} == {"uid-aaa", "uid-bbb"}, parsed_ok
        assert len(skipped) == 1 and skipped[0][0] == bad, skipped

        # -- descriptor_root() honours CS_ZYLCH_ROOT --
        old = os.environ.get("CS_ZYLCH_ROOT")
        os.environ["CS_ZYLCH_ROOT"] = str(root)
        try:
            assert login.descriptor_root() == root
        finally:
            if old is None:
                os.environ.pop("CS_ZYLCH_ROOT", None)
            else:
                os.environ["CS_ZYLCH_ROOT"] = old

        # -- a root with no profiles/ dir at all: zero results, not a crash --
        empty_root = Path(td, "empty-root")
        empty_root.mkdir()
        assert login.scan_descriptors(empty_root) == []

    print(
        "OK: scan_descriptors — finds real descriptors under profiles/*/, "
        "an invalid one sitting next to them is found-but-unparsable "
        "(skipped by the caller), CS_ZYLCH_ROOT honoured, missing "
        "profiles/ = zero results"
    )


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN")}
    env["HOME"] = str(home)
    return env


def _test_cmd_login_zero_descriptors() -> None:
    """Real `python -m cs login` subprocess, closed stdin, no manifest.toml
    in the cwd (so `config.load()` takes its tolerant "no manifest" path,
    never the ManifestError one — see tests/test_config.py's own "no
    manifest at all" case) and `CS_ZYLCH_ROOT` pointing at a root with no
    `profiles/` at all: `cmd_login` must exit 1 and name the mrcall-desktop
    app on stderr, without ever blocking on the closed stdin."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        zylch = Path(td, "zylch")  # deliberately never created: no profiles/

        env = _clean_env(home)
        env["CS_ZYLCH_ROOT"] = str(zylch)

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "login"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}:\n{out}"
        assert "mrcall-desktop" in out, f"message must name the mrcall-desktop app:\n{out}"
        assert "no profile descriptor found" in out, (
            f"message must say no descriptor was found:\n{out}"
        )

    print(
        "OK: cmd_login (real subprocess, closed stdin) — zero descriptors "
        "-> exit 1, message names the mrcall-desktop app"
    )


def _settings(**overrides) -> Settings:
    fields = {"engine_owner_uid": UID, "email_address": "ops@acme.example"}
    fields.update(overrides)
    # _env_file=() disables the dotenv layer entirely — same reasoning as
    # tests/test_auth_boundary.py's _settings(): this must not depend on (or
    # be broken by) whatever happens to sit at the invoking process's CWD.
    return Settings(_env_file=(), **fields)


def _test_identity_conflict() -> None:
    # -- uid mismatch: refusal names BOTH uids --
    reason = login._identity_conflict(
        _settings(), _valid_descriptor(uid=OTHER_UID, email="ops@acme.example")
    )
    assert reason is not None, "expected a refusal on uid mismatch"
    assert UID in reason and OTHER_UID in reason, (
        f"refusal must name BOTH the configured and descriptor uid: {reason}"
    )

    # -- matching uid + matching email (case-insensitive): no conflict --
    ok = login._identity_conflict(
        _settings(), _valid_descriptor(uid=UID, email="OPS@ACME.EXAMPLE")
    )
    assert ok is None, f"case-insensitive email match must not be a conflict: {ok}"

    # -- same uid, email mismatch: refusal names both emails --
    reason = login._identity_conflict(
        _settings(), _valid_descriptor(uid=UID, email="someone-else@acme.example")
    )
    assert reason is not None, "expected a refusal on email mismatch"
    assert "ops@acme.example" in reason and "someone-else@acme.example" in reason, reason

    # -- configured uid empty: refuse pointing at `cs init` --
    reason = login._identity_conflict(
        _settings(engine_owner_uid=""), _valid_descriptor(uid=UID)
    )
    assert reason is not None and "cs init" in reason, reason

    print(
        "OK: _identity_conflict — uid mismatch refuses naming both uids; "
        "email mismatch refuses naming both emails (case-insensitive match "
        "is not a conflict); empty configured uid refuses pointing at `cs init`"
    )


def _test_descriptor_defaults() -> None:
    """`project_init.descriptor_defaults()`: `{}` on zero descriptors, `{}`
    on two (`cs init` stays neutral — picking among signed-in profiles is
    `cs login`'s job), and the mapped dict on exactly one. Hermetic via
    CS_ZYLCH_ROOT, same pattern as `descriptor_root()`'s own guard inside
    `_test_scan_descriptors` above."""
    from cs import project_init

    old = os.environ.get("CS_ZYLCH_ROOT")
    try:
        # -- zero: a root with no profiles/ dir at all --
        with tempfile.TemporaryDirectory() as td:
            os.environ["CS_ZYLCH_ROOT"] = str(Path(td, "empty-root"))
            assert project_init.descriptor_defaults() == {}

        # -- two valid descriptors: also {} --
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(
                root / "profiles" / "uid-aaa" / login.DESCRIPTOR_FILENAME,
                _valid_descriptor(uid="uid-aaa", email="a@acme.example"),
            )
            _write(
                root / "profiles" / "uid-bbb" / login.DESCRIPTOR_FILENAME,
                _valid_descriptor(uid="uid-bbb", email="b@acme.example"),
            )
            os.environ["CS_ZYLCH_ROOT"] = str(root)
            assert project_init.descriptor_defaults() == {}

        # -- exactly one: the mapped dict (engine_ws_url normalized to the
        # BASE — the descriptor itself carries the FULL per-uid URL, exactly
        # the shape `cs login` receives from a real desktop-app sign-in) --
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(
                root / "profiles" / UID / login.DESCRIPTOR_FILENAME,
                _valid_descriptor(engine_ws_url=f"wss://engine.example/ws/{UID}"),
            )
            os.environ["CS_ZYLCH_ROOT"] = str(root)
            defaults = project_init.descriptor_defaults()
            assert defaults == {
                "email_address": "ops@acme.example",
                "engine_ws_url": "wss://engine.example",
                "engine_owner_uid": UID,
                "default_uid": UID,
                "descriptor_email": "ops@acme.example",
            }, defaults
            assert "/ws/" not in defaults["engine_ws_url"], defaults["engine_ws_url"]
    finally:
        if old is None:
            os.environ.pop("CS_ZYLCH_ROOT", None)
        else:
            os.environ["CS_ZYLCH_ROOT"] = old

    print(
        "OK: descriptor_defaults — {} on zero descriptors, {} on two "
        "(cs init stays neutral), the mapped dict on exactly one"
    )


def _test_cmd_update_help() -> None:
    """Real `python -m cs update --help` subprocess: Task 3 gives
    `cmd_update` the same minimal argparse treatment as `cmd_init`, so
    `--help` must exit 0 and print usage WITHOUT falling through into a
    real update walk — proved by running it in a clone-less directory
    (no `template-manifest.json`), which the old code would have refused
    with exit 1 instead of printing help."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()

        env = _clean_env(home)

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update", "--help"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}:\n{out}"
        assert "usage:" in out, f"expected a usage screen:\n{out}"
        assert "cs update" in out, f"expected prog name 'cs update' in usage:\n{out}"

    print("OK: cs update --help (real subprocess) — exits 0, prints usage")


def _test_cmd_login_proof_call_failure() -> None:
    """The proof call (`account.who_am_i`) failing must never traceback: the
    session IS stored, only the live check could not run. Points
    `engine_ws_url` at a closed local port — nothing listening, so the
    WebSocket connect is refused immediately, no real network egress — and
    stubs `auth.get_id_token` so the failure exercised is the connect
    itself, not a missing credential (already covered by
    tests/test_auth_boundary.py). In-process, direct call to `cmd_login`
    with `config.load`/`auth.get_id_token`/`login._prompt_yes_no` swapped
    for the duration of the call — mirrors this file's other in-process
    guards (`_test_identity_conflict`), just with a real (local, closed)
    transport underneath instead of none at all."""
    import contextlib
    import io
    import socket

    from cs import auth as auth_mod
    from cs import config as config_mod

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    closed_port = s.getsockname()[1]
    s.close()
    closed_url = f"ws://127.0.0.1:{closed_port}"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        descriptor_path = _write(
            root / "cs-descriptor.json",
            _valid_descriptor(
                uid=UID,
                email="ops@acme.example",
                engine_ws_url=closed_url,
                firebase_web_api_key="fake-web-api-key",
            ),
        )
        settings = Settings(
            _env_file=(),
            engine_owner_uid=UID,
            email_address="",
            engine_ws_url=closed_url,
            firebase_web_api_key="fake-web-api-key",
            refresh_token_path=str(root / "refresh_token.json"),
            token_cache_path=str(root / "id_token.json"),
        )

        orig_load = config_mod.load
        orig_get_id_token = auth_mod.get_id_token
        orig_prompt = login._prompt_yes_no
        config_mod.load = lambda: settings
        auth_mod.get_id_token = lambda *a, **k: "fake-id-token"
        login._prompt_yes_no = lambda *a, **k: True

        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = login.cmd_login(["--descriptor", str(descriptor_path)])
        finally:
            config_mod.load = orig_load
            auth_mod.get_id_token = orig_get_id_token
            login._prompt_yes_no = orig_prompt

    stderr_text = err.getvalue()
    assert code == 1, f"expected exit 1, got {code}:\n{stderr_text}"
    assert "Traceback" not in stderr_text, (
        f"proof-call failure must not traceback:\n{stderr_text}"
    )
    assert "stored the session" in stderr_text, (
        f"message must say the session was stored despite the proof failure:\n{stderr_text}"
    )

    print(
        "OK: cmd_login proof-call failure (closed local port, in-process) — "
        "exit 1, message names the failure, no traceback"
    )


def main() -> int:
    _test_parse_descriptor()
    _test_descriptor_ws_base()
    _test_scan_descriptors()
    _test_cmd_login_zero_descriptors()
    _test_cmd_login_proof_call_failure()
    _test_identity_conflict()
    _test_descriptor_defaults()
    _test_cmd_update_help()
    print("test_login: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
