#!/usr/bin/env python3
"""`cs --version` (Task 1, backlog `cs-kernel: no top-level cs --version`).

Before this fix, `cs --version` exited 2 with an argparse usage dump
demanding a subcommand — the version was only reachable as `cs init
--version` / `cs update --version`, neither discoverable from a bare
`cs --version`, which is the first thing a newcomer or an operator
verifying a re-pin actually types.

Guards, all real `python -m cs …` subprocesses (no manifest anywhere —
`--version` must work on a bare install, before any clone exists to `cd`
into, exactly like `--help` already does):

  (i)   `python -m cs --version` (no manifest, empty cwd) exits 0 and
        prints "cs-kernel X.Y.Z" on stdout, no "usage:" line, no
        traceback.
  (ii)  the string is byte-identical to what `cs init --version` and
        `cs update --version` print — the point of the fix routing all
        three through one shared `cs/_version.py` helper instead of a
        third copy of the same importlib.metadata try/except.
  (iii) `cs --version` still works from INSIDE a directory with no
        manifest.toml at all (the common "have I got the pin right"
        check, run before any clone is `cd`-ed into) — a regression here
        would be the exact case the backlog item was filed against.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN")}
    env["HOME"] = str(home)
    return env


def _run(argv: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cs", *argv],
        cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=60,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        empty = Path(td, "empty"); empty.mkdir()  # no manifest.toml anywhere
        env = _clean_env(home)

        proc = _run(["--version"], empty, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, (
            f"`cs --version` must exit 0, got {proc.returncode}:\n{out}"
        )
        assert "cs-kernel" in proc.stdout, (
            f"expected 'cs-kernel X.Y.Z' on stdout:\n{out}"
        )
        assert "usage:" not in out.lower(), (
            f"`cs --version` must not fall through to an argparse usage "
            f"dump (the pre-fix bug — a bare subcommand-less invocation "
            f"used to require one):\n{out}"
        )
        assert "Traceback" not in out, f"must not traceback:\n{out}"

        # -- same string as the two subcommand stubs (Task 1: reuse the
        # code path, don't duplicate it) --
        init_proc = _run(["init", "--version"], empty, env)
        update_proc = _run(["update", "--version"], empty, env)
        assert init_proc.returncode == 0 and update_proc.returncode == 0, (
            f"init/update --version must still exit 0:\n"
            f"init: {init_proc.stdout + init_proc.stderr}\n"
            f"update: {update_proc.stdout + update_proc.stderr}"
        )
        assert proc.stdout == init_proc.stdout == update_proc.stdout, (
            "`cs --version`, `cs init --version` and `cs update --version` "
            f"must print the byte-identical string:\n"
            f"  root:   {proc.stdout!r}\n"
            f"  init:   {init_proc.stdout!r}\n"
            f"  update: {update_proc.stdout!r}"
        )

    print("test_version: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
