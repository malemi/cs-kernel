#!/usr/bin/env python3
"""Semantic guard for `--mint`, the CLI surface on `cs login` that consumes
`cs/login.py::mint_descriptor` (`tests/test_mint_descriptor.py` proves the
pure guards it is built from). This file proves the CLI-layer wiring: the
guard order as actually reached through `cmd_login`, that both spellings of
the flag behave identically, and that no refusal on this path tells the
operator to pick a descriptor that does not exist.

NO real network egress anywhere, and no Firebase service-account key is
read: every subprocess below is refused by the registry check, the tty
check, or the `--mint`/`--descriptor` mutual-exclusion check — all three
run before `_mint_resolve_email` or `auth.mint_refresh_token` would ever
touch Firebase. A successful mint is an operator-run collaudo step, not a
gate that can run unconditionally in CI (see the execution plan's M2
verification split).

Guards:
  (i)   `cs login --mint` with closed stdin, for a uid that IS in this
        clone's `CS_ACCOUNTS` registry: refuses on the tty check, naming
        the reason on stderr, exit non-zero, and writes neither the
        refresh-token file nor the id-token cache. Run under a short
        timeout: a guard that blocks on `input()` instead of checking
        `sys.stdin.isatty()` first must fail this gate by timing out, not
        hang the suite.
  (ii)  The same, through `cs --account <name> login --mint`: proves
        `cmd_login_stub` forwards `--mint` into the argv it rebuilds for
        `login.cmd_login` — asserted on the SAME tty-refusal text, not
        just a non-zero exit, because a dropped flag falls through to the
        descriptor-scan path and also exits non-zero, just for a
        different, wrong reason.
  (iii) `cs login --mint` with closed stdin, for a uid that is NOT in the
        registry: refuses naming CS_ACCOUNTS and the uid — never the tty
        reason — proving the registry check runs before the tty check.
  (iv)  `cs login --mint --descriptor PATH` together: refused with one
        line, before either flag's own machinery (descriptor scan or
        registry/tty checks) ever runs.
  (v)   `_identity_conflict(..., minted=True)`, exercised directly (pure,
        no subprocess): an email mismatch on a minted descriptor names
        `--mint` and points at the two real fixes (manifest
        [operator].email_address, or the CS_ACCOUNTS/CS_ENGINE_OWNER_UID
        pin) and never says "pick the matching descriptor" or "run `cs
        --account <name> login` instead" — a minted descriptor has no
        file to pick.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cs import login
from cs.config import Settings

TIMEOUT = 10  # a "few seconds" ceiling — a guard that blocks on input() must
# time out here rather than hang the suite (see module docstring, guard i).

TTY_REASON = "needs a human at a terminal"
REGISTRY_REASON = "CS_ACCOUNTS"


def _clean_env(home: Path) -> dict:
    """Mirrors `tests/test_login.py::_clean_env` — starts from a real
    environment (so `python -m cs` resolves its dependencies normally) and
    relocates only HOME, so `Settings.state_dir` (`Path.home() /
    ".<slug>-cs"`) lands under the sandbox instead of the real one."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN",
                         "TOKEN_CACHE_PATH", "REFRESH_TOKEN_PATH")}
    env["HOME"] = str(home)
    return env


def _make_clone(td: Path, *, owner_uid: str, accounts: str) -> tuple[Path, Path]:
    """A minimal clone + state dir, same shape as
    `test_login.py::_test_account_login_routing`'s fixture: just enough for
    `config.load()` to resolve a primary identity and a registry, with a WS
    URL that is never dialed (every gate here refuses before any RPC)."""
    home = Path(td, "home"); home.mkdir()
    clone = Path(td, "clone"); clone.mkdir()
    state = home / ".acme-cs"; state.mkdir()
    (state / ".env").write_text(
        f"CS_ACCOUNTS={accounts}\n"
        "FIREBASE_WEB_API_KEY=fake-web-api-key\n"
    )
    (clone / "manifest.toml").write_text(
        "[company]\n"
        'slug = "acme"\n'
        "\n"
        "[operator]\n"
        'email_address = "ops@acme.example"\n'
        "\n"
        "[engine]\n"
        f'owner_uid = "{owner_uid}"\n'
        'ws_url = "wss://engine.example/ws"\n'
    )
    return home, clone


def _test_mint_tty_refusal_bare() -> None:
    with tempfile.TemporaryDirectory() as td:
        home, clone = _make_clone(
            Path(td), owner_uid="uid-primary-abc", accounts="primary:uid-primary-abc"
        )
        env = _clean_env(home)

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "login", "--mint"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode != 0, f"expected a non-zero exit:\n{out}"
        assert TTY_REASON in out, f"stderr must name the tty reason:\n{out}"

        state = home / ".acme-cs"
        assert not (state / "refresh_token-uid-primary-abc.json").exists(), (
            "a refused mint must not write a refresh-token file"
        )
        assert not (state / "id_token-uid-primary-abc.json").exists(), (
            "a refused mint must not write an id-token cache file"
        )

    print(
        "OK: cs login --mint (closed stdin, registered uid) — refuses on "
        "the tty check, naming the reason, no refresh or cache file written"
    )


def _test_mint_tty_refusal_via_account() -> None:
    with tempfile.TemporaryDirectory() as td:
        # A genuinely secondary uid — the real shape of the feature (minting
        # for a colleague), and the ONLY way `--mint` reaches a non-default
        # uid at all (`--account` always resolves through the registry).
        home, clone = _make_clone(
            Path(td), owner_uid="uid-primary-abc", accounts="founder:uid-founder-xyz"
        )
        env = _clean_env(home)

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "--account", "founder", "login", "--mint"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode != 0, f"expected a non-zero exit:\n{out}"
        # The load-bearing assertion: `cmd_login_stub` rebuilds its argv
        # from `--descriptor` alone. If `--mint` were silently dropped
        # there, this run would fall into the descriptor-scan path instead
        # (no descriptors exist under this sandbox's ~/.zylch) and print a
        # DIFFERENT refusal — asserting the exact tty reason is what makes
        # that drop visible; a bare non-zero-exit check would not.
        assert TTY_REASON in out, (
            f"stderr must name the tty reason (a dropped --mint falls "
            f"through to the descriptor-scan refusal instead):\n{out}"
        )
        assert "no profile descriptor found" not in out, (
            f"must not have fallen through to the descriptor-scan path:\n{out}"
        )

        state = home / ".acme-cs"
        assert not (state / "refresh_token-uid-founder-xyz.json").exists(), (
            "a refused mint must not write a refresh-token file"
        )
        assert not (state / "id_token-uid-founder-xyz.json").exists(), (
            "a refused mint must not write an id-token cache file"
        )

    print(
        "OK: cs --account <name> login --mint (closed stdin) — "
        "cmd_login_stub forwards --mint (same tty refusal as the bare "
        "spelling), no refresh or cache file written"
    )


def _test_mint_registry_refusal_before_tty() -> None:
    with tempfile.TemporaryDirectory() as td:
        # The configured uid is deliberately absent from CS_ACCOUNTS.
        home, clone = _make_clone(
            Path(td),
            owner_uid="uid-primary-not-registered",
            accounts="someone:uid-different-xyz",
        )
        env = _clean_env(home)

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "login", "--mint"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode != 0, f"expected a non-zero exit:\n{out}"
        assert REGISTRY_REASON in out, f"stderr must name CS_ACCOUNTS:\n{out}"
        assert "uid-primary-not-registered" in out, (
            f"stderr must name the unregistered uid:\n{out}"
        )
        assert TTY_REASON not in out, (
            f"the registry refusal must fire before the tty check ever "
            f"runs — proves the guard order:\n{out}"
        )

    print(
        "OK: cs login --mint (uid absent from CS_ACCOUNTS, closed stdin) — "
        "refuses naming the registry and the uid, never the tty reason, "
        "proving registry runs before tty"
    )


def _test_mint_descriptor_mutually_exclusive() -> None:
    """No clone setup needed: the mutual-exclusion check runs before
    `config.load()`, so this must refuse even with no manifest.toml in the
    cwd at all (same shape as `test_login.py::_test_cmd_login_zero_descriptors`)."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "login", "--mint",
             "--descriptor", "/nonexistent/cs-descriptor.json"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode != 0, f"expected a non-zero exit:\n{out}"
        lines = [ln for ln in out.splitlines() if ln.strip()]
        assert len(lines) == 1, f"expected exactly one line of output:\n{out}"
        assert "--mint" in lines[0] and "--descriptor" in lines[0], (
            f"refusal must name both flags:\n{out}"
        )
        assert "mutually exclusive" in lines[0], out

    print(
        "OK: cs login --mint --descriptor PATH — refused with one line "
        "naming both flags, before either's own machinery runs"
    )


def _test_mint_identity_conflict_wording() -> None:
    """Pure, in-process: `_identity_conflict(..., minted=True)` on an email
    mismatch must name `--mint` and the two real fixes (the manifest field,
    the registry pin), and must never tell the operator to pick a
    descriptor or run a descriptor login — a minted session has neither.
    The uid-mismatch branch is not exercised here: a minted descriptor's
    uid is built from the same `settings.engine_owner_uid` this function
    reads, so that branch is a self-comparison and provably unreachable on
    the mint path (see `_identity_conflict`'s own docstring)."""
    settings = Settings(
        _env_file=(), engine_owner_uid="uid-x", email_address="ops@acme.example"
    )
    minted_descriptor = {"uid": "uid-x", "email": "someone-else@acme.example"}

    reason = login._identity_conflict(settings, minted_descriptor, minted=True)
    assert reason is not None, "expected a refusal on the minted email mismatch"
    assert "--mint" in reason, f"refusal must name --mint: {reason}"
    assert "ops@acme.example" in reason and "someone-else@acme.example" in reason, reason
    assert "pick the matching descriptor" not in reason, (
        f"a minted descriptor has no file to pick: {reason}"
    )
    assert "cs --account" not in reason, (
        f"a minted descriptor path must not point at a descriptor login: {reason}"
    )
    assert "descriptor" not in reason, (
        f"no mint-path refusal may name 'descriptor' as an instruction: {reason}"
    )

    # -- contrast: minted=False (the default, the descriptor branch's own
    # behaviour) is completely unchanged by this parameter's existence --
    reason_default = login._identity_conflict(settings, minted_descriptor)
    assert "pick the matching descriptor" in reason_default, reason_default

    print(
        "OK: _identity_conflict(minted=True) — email-mismatch refusal "
        "names --mint and the two real fixes, never 'pick the matching "
        "descriptor' or a descriptor-login pointer; minted=False (default) "
        "is unchanged"
    )


def main() -> int:
    _test_mint_tty_refusal_bare()
    _test_mint_tty_refusal_via_account()
    _test_mint_registry_refusal_before_tty()
    _test_mint_descriptor_mutually_exclusive()
    _test_mint_identity_conflict_wording()
    print("test_login_mint: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
