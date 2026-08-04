#!/usr/bin/env python3
"""`cs update` must not crash when stdin has no tty (agent, cron,
`stdin </dev/null`) and it hits a template conflict.

Reproduced live 2026-08-04 during a re-pin: the conflict prompt
`input("    Overwrite? [y/N/diff] ")` raised EOFError and the whole `cs
update` run died with a traceback instead of applying the default the
prompt itself declares — the capital N in `[y/N/diff]` means "keep the
local file".

Two levels, because a passing unit check does not prove the CLI actually
takes this path:

  - characterization: `_read_overwrite_choice` — the helper `cmd_update`
    calls at both conflict prompts — fed a stdin that raises EOFError, must
    return the declared default instead of propagating the exception.
  - end-to-end: a REAL `python -m cs update` subprocess, stdin closed, run
    against a scratch stamped clone with a manufactured conflict (a rendered
    file edited locally, and its stored template-manifest checksum forced to
    a value matching neither the local edit nor the current template
    render). This is the exact "modified locally AND template changed"
    branch that used to crash on EOF.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cs import project_update

# The smallest real template in cs/templates/project: `.gitignore.j2`
# interpolates exactly one variable (company_slug), so a minimal init_data
# renders it with no other moving parts.
CONFLICT_REL = ".gitignore"
BOGUS_CHECKSUM = "sha256:" + "0" * 64


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN")}
    env["HOME"] = str(home)
    return env


def _input_with_closed_stdin(prompt: str) -> str:
    """Call project_update._read_overwrite_choice with sys.stdin swapped for
    an already-exhausted stream, the same condition `input()` hits against
    `/dev/null` or a closed pipe — and capture what it prints."""
    real_stdin, real_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO("")  # readline() -> "" -> input() raises EOFError
    captured = io.StringIO()
    sys.stdout = captured
    try:
        return project_update._read_overwrite_choice(prompt, default="n"), captured.getvalue()
    finally:
        sys.stdin, sys.stdout = real_stdin, real_stdout


def _characterize_eof_default() -> None:
    # First conflict prompt: "modified locally AND template changed."
    result, printed = _input_with_closed_stdin("    Overwrite? [y/N/diff] ")
    assert result == "n", f"EOF must resolve to the declared default 'n', got {result!r}"
    assert "no tty" in printed and "keeping local file" in printed, (
        f"the keep-local decision must be printed to stdout, got: {printed!r}"
    )

    # Second prompt in the same flow (after the user asks for `diff`) declares
    # the same default and must degrade the same way — this is the "any OTHER
    # input() call in the same flow" the fix also had to cover.
    result2, printed2 = _input_with_closed_stdin("    Overwrite? [y/N] ")
    assert result2 == "n", f"the second prompt's EOF must also default to 'n', got {result2!r}"
    assert "no tty" in printed2 and "keeping local file" in printed2, (
        f"the second prompt must also print the keep-local decision, got: {printed2!r}"
    )


def _e2e_conflict_keeps_local_with_closed_stdin() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        local_content = "# locally edited — must survive the update\ndist/\n"
        (clone / CONFLICT_REL).write_text(local_content)

        # Manufacture the conflict: the stored checksum matches neither the
        # local edit (so "clone was modified") nor what .gitignore.j2 renders
        # to today (so "template changed") — i.e. cmd_update's ask branch.
        manifest = {
            "template_version": "1",
            "init_data": {"company_slug": "acme"},
            "file_checksums": {CONFLICT_REL: BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, (
            f"`cs update` must exit 0 on a closed stdin, got {proc.returncode}:\n{out}"
        )
        assert (clone / CONFLICT_REL).read_text() == local_content, (
            "the locally-modified file must be UNCHANGED when stdin has no tty:\n" + out
        )
        assert "modified locally AND template changed" in out, (
            f"the manufactured conflict must actually be hit by the real code path:\n{out}"
        )
        assert "no tty" in out and "keeping local file" in out, (
            f"the run's output must name the keep-local decision:\n{out}"
        )


def main() -> int:
    _characterize_eof_default()
    _e2e_conflict_keeps_local_with_closed_stdin()
    print("test_project_update: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
