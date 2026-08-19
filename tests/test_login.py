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
        mismatch refuses naming BOTH uids (and `account_switched=True`
        never relaxes it — uid equality IS the identity statement for a
        secondary account); an email mismatch refuses naming both emails,
        is case-insensitive, and points at `cs --account <name> login` for
        the legitimate secondary case — UNLESS `account_name` names a
        given-but-not-switched `--account` (it already resolved to this
        clone's own default uid), in which case the message names that
        real cause instead of the now-wrong pointer; an empty configured
        uid refuses pointing at `cs init`; `account_switched=True` skips
        the email check entirely for a deliberately selected secondary
        account.
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
  (ix)  `cs --account <name> login` (real subprocess, B1.5's LOAD-BEARING
        routing pin): the deliberate secondary-account selection routes
        through `cli.main()`'s full argparse tree, skips the
        operator-mailbox email cross-check, and stores the session at that
        account's own per-uid `refresh_token-<uid>.json` — never the
        primary's. The contrast case (same descriptor, no `--account`)
        still refuses the uid mismatch and writes no session file at all.
        Both proof-call legs die at the same closed local port — the WS
        connect directly, the id-token exchange via an http_proxy/
        https_proxy env override — so nothing leaves the machine, online
        or not.
  (x)   `cmd_login`'s known-uid auto-select (Task 2 / backlog `cs-kernel:
        cs --account <name> login asks the operator to pick a descriptor
        it already knows`): with `settings.engine_owner_uid` already
        configured, the matching descriptor among several is picked with
        NO prompt at all — `_prompt_yes_no`/`_prompt_choice` are stubbed
        to raise if called, so this is a positive guard, not just an
        output assertion — and a configured uid with no matching
        descriptor fails immediately, naming the uid (and the --account
        name when given), writing nothing. Guard (ix) above's contrast
        case exercises the real subprocess routing for the same fix; this
        one isolates the selection step in-process.
"""
from __future__ import annotations

import json
import os
import stat
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
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN",
                         "TOKEN_CACHE_PATH", "REFRESH_TOKEN_PATH")}
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

    # -- same uid, email mismatch: refusal names both emails, and points at
    # `--account` for the legitimate secondary-account case --
    reason = login._identity_conflict(
        _settings(), _valid_descriptor(uid=UID, email="someone-else@acme.example")
    )
    assert reason is not None, "expected a refusal on email mismatch"
    assert "ops@acme.example" in reason and "someone-else@acme.example" in reason, reason
    assert "--account" in reason, (
        f"refusal must point at `cs --account <name> login` for a legitimate "
        f"secondary account: {reason}"
    )

    # -- same uid, email mismatch, `--account <name>` given but it did NOT
    # switch the uid (it resolved to this clone's own default): the generic
    # "run `cs --account <name> login`" pointer would be wrong advice here —
    # --account WAS already used — so the message must name the real cause
    # (a CS_ACCOUNTS/CS_ENGINE_OWNER_UID configuration error) instead --
    reason = login._identity_conflict(
        _settings(),
        _valid_descriptor(uid=UID, email="someone-else@acme.example"),
        account_switched=False,
        account_name="founder",
    )
    assert reason is not None, "expected a refusal on email mismatch"
    assert "'founder'" in reason and "default uid" in reason, reason
    assert "run `cs --account <name> login`" not in reason, (
        f"the generic pointer must not appear once account_name names the "
        f"real cause: {reason}"
    )

    # -- same uid, email mismatch, but account_switched=True: `cs --account
    # X login` is a deliberate registry selection, so the descriptor's own
    # mailbox legitimately differs from the clone's operator mailbox — no
    # conflict --
    ok = login._identity_conflict(
        _settings(),
        _valid_descriptor(uid=UID, email="someone-else@acme.example"),
        account_switched=True,
    )
    assert ok is None, (
        f"account_switched=True must skip the operator-mailbox email check: {ok}"
    )

    # -- uid mismatch + account_switched=True: STILL refuses — the flag
    # never relaxes the uid check, which IS the identity statement for a
    # secondary account --
    reason = login._identity_conflict(
        _settings(),
        _valid_descriptor(uid=OTHER_UID, email="ops@acme.example"),
        account_switched=True,
    )
    assert reason is not None, "account_switched=True must NOT relax the uid check"
    assert UID in reason and OTHER_UID in reason, reason

    # -- configured uid empty: refuse pointing at `cs init` --
    reason = login._identity_conflict(
        _settings(engine_owner_uid=""), _valid_descriptor(uid=UID)
    )
    assert reason is not None and "cs init" in reason, reason

    print(
        "OK: _identity_conflict — uid mismatch refuses naming both uids "
        "(account_switched never relaxes it); email mismatch refuses naming "
        "both emails and points at `--account` (case-insensitive match is "
        "not a conflict); a given-but-not-switched --account names the real "
        "cause instead of the generic pointer; account_switched=True skips "
        "the email check for a deliberate secondary-account login; empty "
        "configured uid refuses pointing at `cs init`"
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
                # feeds write_state_env: cs init writes the .env key the
                # descriptor already carries instead of prompting for it
                "firebase_web_api_key": "fake-web-api-key",
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


def _test_known_uid_auto_select() -> None:
    """Task 2 (backlog `cs-kernel: cs --account <name> login asks the
    operator to pick a descriptor it already knows`): when
    `settings.engine_owner_uid` is already known, `cmd_login` must
    auto-select the descriptor whose uid matches — printing which one,
    NEVER prompting — and fail immediately, naming the uid, when none
    matches.

    Both `login._prompt_yes_no` and `login._prompt_choice` are swapped for
    a stub that raises `AssertionError` if called at all: with TWO
    descriptors present (one matching, one not) a naive "one descriptor ->
    confirm, otherwise -> numbered pick" implementation would call one of
    them, so this is a positive guard against the exact bug being fixed,
    not just an assertion on the printed output. Mirrors
    `_test_cmd_login_proof_call_failure`'s in-process stubbing idiom (a
    closed local port so the proof call fails deterministically, no real
    network egress) since the point here is the SELECTION step, not the
    proof call."""
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

    def _no_prompt(*_a, **_k):
        raise AssertionError(
            "the known-uid auto-select path must never prompt the operator"
        )

    # -- match found among SEVERAL descriptors: auto-selected, no prompt,
    # the session is stored under the MATCHING descriptor's own data --
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root / "profiles" / UID / login.DESCRIPTOR_FILENAME,
            _valid_descriptor(
                uid=UID, email="ops@acme.example", engine_ws_url=closed_url,
                firebase_web_api_key="fake-web-api-key",
            ),
        )
        _write(
            root / "profiles" / OTHER_UID / login.DESCRIPTOR_FILENAME,
            _valid_descriptor(uid=OTHER_UID, email="someone-else@acme.example"),
        )
        settings = Settings(
            _env_file=(),
            engine_owner_uid=UID,
            email_address="ops@acme.example",
            engine_ws_url=closed_url,
            firebase_web_api_key="fake-web-api-key",
            refresh_token_path=str(root / "refresh_token.json"),
            token_cache_path=str(root / "id_token.json"),
        )

        old_zylch = os.environ.get("CS_ZYLCH_ROOT")
        os.environ["CS_ZYLCH_ROOT"] = str(root)
        orig_load = config_mod.load
        orig_get_id_token = auth_mod.get_id_token
        orig_yn, orig_choice = login._prompt_yes_no, login._prompt_choice
        config_mod.load = lambda: settings
        auth_mod.get_id_token = lambda *a, **k: "fake-id-token"
        login._prompt_yes_no = _no_prompt
        login._prompt_choice = _no_prompt

        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = login.cmd_login([])
        finally:
            config_mod.load = orig_load
            auth_mod.get_id_token = orig_get_id_token
            login._prompt_yes_no, login._prompt_choice = orig_yn, orig_choice
            if old_zylch is None:
                os.environ.pop("CS_ZYLCH_ROOT", None)
            else:
                os.environ["CS_ZYLCH_ROOT"] = old_zylch

        printed = out.getvalue()
        assert code == 1, (
            f"expected exit 1 (the proof call fails against a closed port), got {code}"
        )
        assert f"selected: ops@acme.example ({UID})" in printed, (
            f"the matching descriptor must be auto-selected and named:\n{printed}"
        )
        assert (root / "refresh_token.json").exists(), (
            "the auto-selected descriptor's session must still be stored"
        )
        written = json.loads((root / "refresh_token.json").read_text())
        assert written == {"uid": UID, "refresh_token": "rt-abc"}, written

    # -- configured uid with NO matching descriptor at all: immediate
    # failure naming the uid (and the --account name, when given), nothing
    # written, no prompt --
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root / "profiles" / OTHER_UID / login.DESCRIPTOR_FILENAME,
            _valid_descriptor(uid=OTHER_UID, email="someone-else@acme.example"),
        )
        settings = Settings(
            _env_file=(),
            engine_owner_uid=UID,
            email_address="ops@acme.example",
            refresh_token_path=str(root / "refresh_token.json"),
            token_cache_path=str(root / "id_token.json"),
        )

        old_zylch = os.environ.get("CS_ZYLCH_ROOT")
        os.environ["CS_ZYLCH_ROOT"] = str(root)
        orig_load = config_mod.load
        orig_yn, orig_choice = login._prompt_yes_no, login._prompt_choice
        config_mod.load = lambda: settings
        login._prompt_yes_no = _no_prompt
        login._prompt_choice = _no_prompt

        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = login.cmd_login([], account_name="founder")
        finally:
            config_mod.load = orig_load
            login._prompt_yes_no, login._prompt_choice = orig_yn, orig_choice
            if old_zylch is None:
                os.environ.pop("CS_ZYLCH_ROOT", None)
            else:
                os.environ["CS_ZYLCH_ROOT"] = old_zylch

        stderr_text = err.getvalue()
        assert code == 1, f"expected exit 1, got {code}:\n{stderr_text}"
        assert f"no descriptor for uid {UID}" in stderr_text, stderr_text
        assert "'founder'" in stderr_text, (
            f"the no-match refusal must name the --account name when given:\n{stderr_text}"
        )
        assert "mrcall-desktop" in stderr_text, (
            f"the no-match refusal must point at the mrcall-desktop app:\n{stderr_text}"
        )
        assert not (root / "refresh_token.json").exists(), (
            "a no-match refusal must never write a session file"
        )

    print(
        "OK: known-uid auto-select — a matching descriptor among several is "
        "picked with NO prompt (both prompt helpers stubbed to raise if "
        "called); a configured uid with no matching descriptor fails "
        "immediately, naming the uid (and the --account name when given), "
        "writing nothing"
    )


def _test_account_login_routing() -> None:
    """The LOAD-BEARING routing pin for B1.5: `cs --account <name> login`
    must actually route through `cli.main()`'s full argparse tree (NOT the
    early `argv[0] == "login"` dispatch, which `--account` bypasses since it
    occupies argv[0] instead), carry `account_switched=True` into
    `_identity_conflict`, and store the session at the SECONDARY account's
    own per-uid path — never the primary's, and never answering "different
    profile" for a deliberately selected secondary. Real subprocess (this
    proves the actual `--account` plumbing end to end, not just the pure
    `_identity_conflict` function `_test_identity_conflict` exercises
    above); the proof call's WS URL is a closed local port, same trick as
    `_test_cmd_login_proof_call_failure`, and — unlike that in-process
    guard — this one cannot stub `auth.get_id_token`, so `http_proxy`/
    `https_proxy` are forced onto the SAME closed port: urllib builds its
    ProxyHandler from the environment, so the id-token exchange's HTTPS
    CONNECT to securetoken.googleapis.com dies there too, deterministically,
    online or offline. Both proof-call legs therefore fail locally."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    closed_port = s.getsockname()[1]
    s.close()
    closed_url = f"ws://127.0.0.1:{closed_port}"

    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        state = home / ".acme-cs"; state.mkdir()
        (state / ".env").write_text(
            "CS_ACCOUNTS=founder:uid-founder-xyz\n"
            "FIREBASE_WEB_API_KEY=fake-web-api-key\n"
        )
        # Minimal manifest (adapted from tests/test_config.py's MANIFEST
        # fixture idiom): just enough for a primary identity and a WS URL
        # that dials nowhere.
        (clone / "manifest.toml").write_text(
            "[company]\n"
            'slug = "acme"\n'
            "\n"
            "[operator]\n"
            'email_address = "ops@acme.example"\n'
            "\n"
            "[engine]\n"
            'owner_uid = "uid-primary"\n'
            f'ws_url = "{closed_url}"\n'
        )
        descriptor_path = _write(
            clone / "founder-descriptor.json",
            _valid_descriptor(
                uid="uid-founder-xyz",
                email="founder@acme.example",
                engine_ws_url=closed_url,
                refresh_token="rt-founder",
            ),
        )

        env = _clean_env(home)
        # An inherited no_proxy/NO_PROXY (e.g. "*" or a googleapis.com entry)
        # would bypass the proxy override below via proxy_bypass_environment,
        # letting the exchange reach the real network silently — drop it.
        env.pop("no_proxy", None)
        env.pop("NO_PROXY", None)
        # Force the id-token exchange's HTTPS CONNECT through the SAME
        # closed local port as the WS proof call above: urllib builds its
        # ProxyHandler from http_proxy/https_proxy, so the connect to
        # securetoken.googleapis.com dies here too, deterministically,
        # online or offline — no real network egress either way. Applies to
        # BOTH subprocess runs below, which share this env dict.
        env["http_proxy"] = env["https_proxy"] = f"http://127.0.0.1:{closed_port}"
        founder_refresh = state / "refresh_token-uid-founder-xyz.json"
        primary_refresh = state / "refresh_token-uid-primary.json"

        # -- contrast case FIRST: bare `cs login` (no --account) refuses the
        # uid mismatch and writes NOTHING — the founder descriptor's uid
        # does not match this clone's configured primary uid, and no
        # --account was given to relax the check. Since B1.6 (the
        # known-uid auto-select fix) this is caught BEFORE
        # `_identity_conflict` even runs: the configured uid resolves the
        # choice deterministically, so a descriptor for a different uid is
        # never offered as a pick in the first place, and the refusal names
        # only the configured uid (the message this clone actually knows),
        # not the descriptor's — see `_test_known_uid_auto_select` below
        # for the direct guard on that branch. --
        proc = subprocess.run(
            [sys.executable, "-m", "cs", "login", "--descriptor", str(descriptor_path)],
            cwd=clone, env=env, input="y\n",
            capture_output=True, text=True, timeout=60,
        )
        out = proc.stdout + proc.stderr
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}:\n{out}"
        assert "no descriptor for uid uid-primary" in out, (
            f"expected the known-uid no-match refusal without --account:\n{out}"
        )
        assert "mrcall-desktop" in out, (
            f"the no-match refusal must point at the mrcall-desktop app:\n{out}"
        )
        assert "different profile" not in out, (
            f"the known-uid auto-select path must never reach the "
            f"post-pick _identity_conflict refusal:\n{out}"
        )
        assert not founder_refresh.exists() and not primary_refresh.exists(), (
            "the refused bare login must not write any session file"
        )

        # -- `cs --account founder login`: the deliberate secondary-account
        # selection must route through cli.main()'s full argparse tree,
        # carry account_switched=True, skip the operator-mailbox email
        # cross-check, and store the session at the FOUNDER's own per-uid
        # path only. `--account founder` resolves CS_ENGINE_OWNER_UID to
        # the founder's own uid before config.load() runs, so this is also
        # the known-uid AUTO-SELECT path (Task 2/B1.6): the single
        # descriptor's uid matches, so it is picked with no prompt at all —
        # `input="y\n"` is passed but never consumed, proving nothing reads
        # it. --
        proc = subprocess.run(
            [sys.executable, "-m", "cs", "--account", "founder", "login",
             "--descriptor", str(descriptor_path)],
            cwd=clone, env=env, input="y\n",
            capture_output=True, text=True, timeout=60,
        )
        out = proc.stdout + proc.stderr
        assert proc.returncode == 1, (
            f"expected exit 1 (the proof call fails against a closed port), "
            f"got {proc.returncode}:\n{out}"
        )
        assert "selected: founder@acme.example (uid-founder-xyz)" in out, (
            f"the known uid must be auto-selected, printed, and not prompted for:\n{out}"
        )
        assert "Proceed?" not in out and "Multiple profiles" not in out, (
            f"the known-uid auto-select path must never show a picker prompt:\n{out}"
        )
        assert "stored the session" in out, (
            f"the session must be stored even though the proof call fails:\n{out}"
        )
        assert "different profile" not in out, (
            f"--account must skip the operator-mailbox email cross-check:\n{out}"
        )
        assert "Traceback" not in out, f"must not traceback:\n{out}"

        assert founder_refresh.exists(), "founder's per-uid session file was not written"
        mode = stat.S_IMODE(founder_refresh.stat().st_mode)
        assert mode == 0o600, f"founder session file mode is {oct(mode)}, expected 0o600"
        written = json.loads(founder_refresh.read_text())
        assert written == {"uid": "uid-founder-xyz", "refresh_token": "rt-founder"}, written

        assert not primary_refresh.exists(), (
            "the --account run must not cross-write the primary's session file"
        )

    print(
        "OK: cs --account <name> login (real subprocess) — routes through "
        "the full argparse tree, skips the operator-mailbox email "
        "cross-check, and stores the session at the secondary account's "
        "OWN per-uid path (no cross-write onto the primary's); the "
        "contrast case (no --account) still refuses the uid mismatch and "
        "writes no session file at all"
    )


def main() -> int:
    _test_parse_descriptor()
    _test_descriptor_ws_base()
    _test_scan_descriptors()
    _test_cmd_login_zero_descriptors()
    _test_cmd_login_proof_call_failure()
    _test_known_uid_auto_select()
    _test_identity_conflict()
    _test_account_login_routing()
    _test_descriptor_defaults()
    _test_cmd_update_help()
    print("test_login: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
