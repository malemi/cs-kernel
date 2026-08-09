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

2026-08-09: widened past the EOF regression to the two other operator
decisions `cmd_update` makes about WHICH files may hit that conflict branch
at all — also end-to-end, same closed-stdin subprocess technique:

  - `requirements.txt` is the operator's pin, never cs update's: it must be
    skipped outright (no write, no prompt, no manifest entry) even when its
    stored checksum differs from today's render.
  - SECURITY_CRITICAL templates (`.claude/settings.json`,
    `bin/cs_operator_cron.sh`) must never reach the interactive prompt at
    all: on conflict the new render is applied unconditionally, the
    operator's prior local content is preserved as `<file>.local-bak`, and a
    message says so.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import jinja2

from cs import project_update

# The smallest real template in cs/templates/project: `.gitignore.j2`
# interpolates exactly one variable (company_slug), so a minimal init_data
# renders it with no other moving parts. Not in project_update.SECURITY_CRITICAL
# — it stays the neutral file that exercises the interactive prompt.
CONFLICT_REL = ".gitignore"
BOGUS_CHECKSUM = "sha256:" + "0" * 64

# One of the two project_update.SECURITY_CRITICAL paths. Renders from four
# variables (company_slug, company_name, company_prog_name, email_address) —
# enough to exercise a real conflict without needing every template's full
# variable set: cmd_update renders the WHOLE template tree on every run, and
# templates outside a given test's concern simply fail to render individually
# under a minimal init_data — the same tolerance the scenario above already
# relies on.
SECURITY_CRITICAL_REL = "bin/cs_operator_cron.sh"


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


def _render_current_template(rel: str, init_data: dict) -> str:
    """Render `<template_root>/<rel>.j2` with the SAME jinja settings
    cmd_update uses, independently of cs/project_update.py, so a test can
    know what "the new render" is without trusting the code under test to
    report its own output correctly."""
    import cs as cs_mod

    tpl_path = Path(cs_mod.__file__).parent / "templates" / "project" / f"{rel}.j2"
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True,
    )
    return env.from_string(tpl_path.read_text()).render(**init_data)


def _e2e_security_critical_conflict_applies_with_backup() -> None:
    """A SECURITY_CRITICAL file (project_update.SECURITY_CRITICAL) must never
    be gated behind the interactive prompt: on a "modified locally AND
    template changed" conflict the new render is applied unconditionally, the
    operator's prior local content is preserved next to it as
    `<file>.local-bak`, and a loud message names both facts. Manufactured the
    same way as the neutral-file scenario above: the stored checksum matches
    neither the local edit nor what the template renders today."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        (clone / "bin").mkdir()
        local_content = (
            "#!/usr/bin/env bash\n"
            "# locally edited cron — must be BACKED UP, not silently discarded\n"
            "echo legacy\n"
        )
        (clone / SECURITY_CRITICAL_REL).write_text(local_content)

        init_data = {
            "company_slug": "acme",
            "company_name": "Acme Corp",
            "company_prog_name": "acme-cs",
            "email_address": "support@acme.example",
        }
        manifest = {
            "template_version": "1",
            "init_data": init_data,
            "file_checksums": {SECURITY_CRITICAL_REL: BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, (
            f"`cs update` must exit 0 on a SECURITY_CRITICAL conflict, got {proc.returncode}:\n{out}"
        )
        assert "Overwrite?" not in out and "modified locally AND template changed" not in out, (
            f"a SECURITY_CRITICAL conflict must never show the interactive prompt:\n{out}"
        )

        expected_new = _render_current_template(SECURITY_CRITICAL_REL, init_data)
        actual_new = (clone / SECURITY_CRITICAL_REL).read_text()
        assert actual_new == expected_new, (
            "the SECURITY_CRITICAL file must hold the NEW template render after update:\n"
            f"--- expected ---\n{expected_new}\n--- actual ---\n{actual_new}"
        )

        backup_path = clone / f"{SECURITY_CRITICAL_REL}.local-bak"
        assert backup_path.exists(), f".local-bak backup was not created:\n{out}"
        assert backup_path.read_text() == local_content, (
            "the .local-bak backup must hold the EXACT prior local content, unchanged"
        )

        assert (
            f"{SECURITY_CRITICAL_REL}: SECURITY-CRITICAL template updated — new version applied."
            in out
        ), f"the SECURITY-CRITICAL message must name the file and state it was applied:\n{out}"
        assert (
            f"Your locally-edited version was saved to {SECURITY_CRITICAL_REL}.local-bak." in out
        ), f"the message must name the backup path:\n{out}"
        assert (
            "Re-apply any clone-specific entries on top of the new file, then delete the backup."
            in out
        ), f"the message must tell the operator what to do next:\n{out}"


def _e2e_requirements_txt_never_touched() -> None:
    """requirements.txt is the operator's pin, not a render target: cmd_update
    must never write it, never prompt on it, and never record it in the
    updated manifest's file_checksums — even though its stored checksum here
    differs from today's template render, which for any OTHER file would be
    exactly the "template changed" trigger."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        pinned_content = "cs-kernel==0.4.7\nrequests>=2.31\n"
        (clone / "requirements.txt").write_text(pinned_content)

        manifest = {
            "template_version": "1",
            "init_data": {
                "company_slug": "acme",
                "company_name": "Acme Corp",
                "company_prog_name": "acme-cs",
                "repo_kernel_version": "0.5.2",
            },
            "file_checksums": {"requirements.txt": BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, (
            f"`cs update` must exit 0 past a requirements.txt entry, got {proc.returncode}:\n{out}"
        )
        assert (clone / "requirements.txt").read_text() == pinned_content, (
            "requirements.txt must be byte-identical to what it held before the update:\n" + out
        )
        assert "requirements.txt is the operator's pin — cs update never touches it" in out, (
            f"the never-touches-it message must be printed:\n{out}"
        )

        updated_manifest = json.loads((clone / "template-manifest.json").read_text())
        assert "requirements.txt" not in updated_manifest["file_checksums"], (
            "requirements.txt must be absent from the updated manifest's file_checksums:\n"
            f"{updated_manifest['file_checksums']}"
        )


def main() -> int:
    _characterize_eof_default()
    _e2e_conflict_keeps_local_with_closed_stdin()
    _e2e_security_critical_conflict_applies_with_backup()
    _e2e_requirements_txt_never_touched()
    print("test_project_update: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
