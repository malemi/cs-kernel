#!/usr/bin/env python3
"""Gate: the charter lands in AGENTS.md; CLAUDE.md is a one-time bootstrap.

A clone's project instructions are AGENTS.md — the file Codex and OpenCode read
natively, and the one Claude Code reaches through CLAUDE.md's `@AGENTS.md`
import. The kernel stamps AGENTS.md on every update and writes CLAUDE.md
exactly once, when a clone has none: it is clone-authored, never re-stamped
and never in the checksum ledger, so whoever manages the file afterwards — a
documentation harness, an operator — owns it without a drift report.

Clones stamped before v0.42.0 carry the charter in CLAUDE.md and an
`AGENTS.md -> CLAUDE.md` symlink. Three things make the migration safe, and
this file holds all three:

  - a symlink at a render target is replaced at write time, never written
    through: `write_text` follows a symlink, so rendering AGENTS.md through the
    link would put the charter back into CLAUDE.md and leave the shape exactly
    as it was — invisibly, on every later run;
  - the CLAUDE.md bootstrap (`@AGENTS.md`) lands only once AGENTS.md is a
    regular file beside it. Both walks are sorted, so AGENTS.md is visited
    first; when ITS render fails the clone is left exactly as it was, ledger
    entry included, and the run says so;
  - a clone-authored file that is byte-identical to the checksum the ledger
    holds for it was never authored by anyone. It is still the kernel's own
    default, and the new default replaces it, once. A file that differs by a
    single byte is the operator's and is left alone, on every run.

Real `python -m cs update` subprocesses against scratch clones, as in
test_project_update.py, whose scaffolding this file borrows.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from cs import project_init as pi  # noqa: E402
from cs.project_init import TEMPLATE_DEFAULTS  # noqa: E402
from test_project_update import (  # noqa: E402
    _FULL_INIT_DATA, _checksum, _clean_env, _run_update,
)

TPL = ROOT / "cs" / "templates" / "project"
STUB = (TPL / "CLAUDE.md").read_text()
# render_templates() takes the config as `cs init` hands it over — defaults
# already folded in; `cs update` folds them in itself (_render_vars).
INIT = {**TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}

# Any text will do for "the charter an older kernel stamped": the rule under
# test compares the file on disk with the LEDGER, never with today's render.
OLD_CHARTER = "# CLAUDE.md\n\nThe charter as an older kernel rendered it.\n"


def _charter_render() -> str:
    """Today's AGENTS.md render, produced independently of the code under
    test, through the same environment both stamping paths use."""
    env = pi.build_jinja_env(TPL)
    return env.get_template("AGENTS.md.j2").render(**INIT)


def _legacy_clone(clone: Path, claude_md: str, ledgered: str | None) -> None:
    """The pre-v0.42.0 shape: the charter (or whatever the operator left) in
    CLAUDE.md, `AGENTS.md -> CLAUDE.md`, and a ledger that may or may not
    describe CLAUDE.md. A minimal skills tree, so install_agent_surfaces()
    runs its wiring rather than returning early."""
    clone.mkdir(parents=True, exist_ok=True)
    (clone / "CLAUDE.md").write_text(claude_md)
    (clone / "AGENTS.md").symlink_to("CLAUDE.md")
    skill = clone / ".claude" / "skills" / "cs-review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: cs-review\n---\n")
    checksums = {"CLAUDE.md": _checksum(ledgered)} if ledgered is not None else {}
    (clone / "template-manifest.json").write_text(json.dumps({
        "template_version": "1",
        "init_data": dict(_FULL_INIT_DATA),
        "file_checksums": checksums,
    }, indent=2))


def _ledger(clone: Path) -> dict:
    return json.loads((clone / "template-manifest.json").read_text())["file_checksums"]


def _assert_v8_shape(clone: Path, label: str) -> None:
    agents = clone / "AGENTS.md"
    assert agents.is_file() and not agents.is_symlink(), f"[{label}] AGENTS.md must be a regular file"
    assert agents.read_text() == _charter_render(), f"[{label}] AGENTS.md must hold today's charter render"
    assert agents.read_text().endswith("\n"), f"[{label}] the rendered charter must keep its trailing newline"
    assert "CLAUDE.md" not in _ledger(clone), f"[{label}] CLAUDE.md must not be in the ledger: {_ledger(clone)}"
    assert "AGENTS.md" in _ledger(clone), f"[{label}] AGENTS.md must be in the ledger"


# ----------------------------------------------------------------- cs init

def _fresh_render_stamps_the_shape() -> None:
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "acme-cs"
        with contextlib.redirect_stdout(io.StringIO()):
            ok, checksums = pi.render_templates(dict(INIT), TPL, dest)
        assert ok, "render_templates must succeed"
        agents = dest / "AGENTS.md"
        assert agents.is_file() and not agents.is_symlink(), "a fresh clone gets a real AGENTS.md"
        assert agents.read_text() == _charter_render()
        assert agents.read_text().endswith("\n"), "the rendered charter keeps its trailing newline"
        assert (dest / "CLAUDE.md").read_text() == STUB, "a fresh clone gets the bootstrap CLAUDE.md"
        assert STUB.splitlines()[0] == "@AGENTS.md", (
            "the bootstrap's first line is the import Claude Code follows — the charter "
            "reaches a session with no documentation harness installed")
        assert "CLAUDE.md" not in checksums, f"CLAUDE.md is clone-authored and never ledgered: {sorted(checksums)}"
        assert "AGENTS.md" in checksums


def _init_restamp_over_the_legacy_shape() -> None:
    """The documented in-place restamp (`cs init` with dest_dir "." on an
    existing clone) — the path where a live symlink could take the charter into
    CLAUDE.md and the CLAUDE.md render then overwrite it. The walk is sorted so
    AGENTS.md lands before the bootstrap that imports it. With a ledger present
    the kernel default is superseded; without one there is no proof the file
    is the kernel's, so it is kept; and a charter that does not render leaves
    the legacy shape untouched."""
    with tempfile.TemporaryDirectory() as td:
        clone = Path(td) / "acme-cs"
        _legacy_clone(clone, OLD_CHARTER, ledgered=OLD_CHARTER)
        with contextlib.redirect_stdout(io.StringIO()):
            ok, checksums = pi.render_templates(dict(INIT), TPL, clone)
        assert ok
        agents = clone / "AGENTS.md"
        assert agents.is_file() and not agents.is_symlink(), "restamp must retire the symlink"
        assert agents.read_text() == _charter_render(), "restamp must not lose the charter"
        assert (clone / "CLAUDE.md").read_text() == STUB, "a ledgered, untouched CLAUDE.md is superseded by the stub"
        assert "CLAUDE.md" not in checksums

    with tempfile.TemporaryDirectory() as td:
        clone = Path(td) / "acme-cs"
        _legacy_clone(clone, OLD_CHARTER, ledgered=None)
        with contextlib.redirect_stdout(io.StringIO()):
            ok, _ = pi.render_templates(dict(INIT), TPL, clone)
        assert ok
        assert (clone / "AGENTS.md").read_text() == _charter_render()
        assert (clone / "CLAUDE.md").read_text() == OLD_CHARTER, "with no ledger entry the file is the operator's"

    broken = {k: v for k, v in INIT.items() if k != "email_address"}
    with tempfile.TemporaryDirectory() as td:
        clone = Path(td) / "acme-cs"
        _legacy_clone(clone, OLD_CHARTER, ledgered=OLD_CHARTER)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            ok, checksums = pi.render_templates(dict(broken), TPL, clone)
        assert not ok, "a charter that does not render is a failed stamp"
        assert (clone / "AGENTS.md").is_symlink(), "a failed render replaces nothing"
        assert (clone / "CLAUDE.md").read_text() == OLD_CHARTER, "the old charter stays where it was"
        assert "bootstrap" in out.getvalue(), out.getvalue()


# --------------------------------------------------------------- cs update

def _update_migrates_a_pristine_legacy_clone() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone")
        _legacy_clone(clone, OLD_CHARTER, ledgered=OLD_CHARTER)
        env = _clean_env(home)

        proc = _run_update([], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        assert "Overwrite?" not in out, f"a pristine clone must never prompt:\n{out}"
        _assert_v8_shape(clone, "first run")
        assert (clone / "CLAUDE.md").read_text() == STUB, f"CLAUDE.md must become the bootstrap:\n{out}"
        assert "+ AGENTS.md" in out, out
        assert "CLAUDE.md" in out, f"the supersession must be reported:\n{out}"

        proc = _run_update([], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        _assert_v8_shape(clone, "second run")
        assert (clone / "CLAUDE.md").read_text() == STUB
        assert "CLAUDE.md" not in out, f"a superseded default is never mentioned again:\n{out}"


def _update_leaves_an_authored_claude_md_alone() -> None:
    """Two shapes of 'not the kernel's file': a harness template already
    installed, and the old charter with one line added. Both differ from the
    ledger's checksum, so neither may be touched — on this run or the next."""
    harness = "# Documentation Harness\n\n@AGENTS.md\n\nThe harness contract.\n"
    edited = OLD_CHARTER + "\nOne line the operator added.\n"
    for label, content in (("harness template", harness), ("hand edit", edited)):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td, "home"); home.mkdir()
            clone = Path(td, "clone")
            _legacy_clone(clone, content, ledgered=OLD_CHARTER)
            env = _clean_env(home)
            for run in ("first", "second"):
                proc = _run_update([], clone, env)
                out = proc.stdout + proc.stderr
                assert proc.returncode == 0, f"[{label}/{run}] {out}"
                assert "Overwrite?" not in out, f"[{label}/{run}] {out}"
                _assert_v8_shape(clone, f"{label}/{run}")
                assert (clone / "CLAUDE.md").read_text() == content, (
                    f"[{label}/{run}] an authored CLAUDE.md must be left byte-identical")


def _update_supersedes_against_an_older_ledger() -> None:
    """A clone several releases behind (its CLAUDE.md matches ITS OWN older
    ledger entry, not today's render) is still a pristine kernel default: the
    rule compares disk to ledger, never disk to render."""
    older = "# CLAUDE.md\n\nA render from several minor releases ago.\n"
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone")
        _legacy_clone(clone, older, ledgered=older)
        env = _clean_env(home)
        proc = _run_update([], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        _assert_v8_shape(clone, "older ledger")
        assert (clone / "CLAUDE.md").read_text() == STUB, out


def _update_with_a_failing_charter_render_changes_nothing() -> None:
    """The case that matters most on the update path — a template variable the
    clone's frozen init_data cannot answer, exactly what `cs update` exists to
    survive. The run must leave the legacy shape untouched, keep CLAUDE.md's
    ledger entry so the move can still finish later, and say so; the next run,
    with the data repaired, completes the migration."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone")
        _legacy_clone(clone, OLD_CHARTER, ledgered=OLD_CHARTER)
        manifest = json.loads((clone / "template-manifest.json").read_text())
        manifest["init_data"].pop("email_address")
        (clone / "template-manifest.json").write_text(json.dumps(manifest, indent=2))
        env = _clean_env(home)

        proc = _run_update([], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        assert "failed to render AGENTS.md.j2" in out, out
        assert (clone / "AGENTS.md").is_symlink(), f"a failed render must replace nothing:\n{out}"
        assert (clone / "CLAUDE.md").read_text() == OLD_CHARTER, f"the old charter must stay:\n{out}"
        assert _ledger(clone).get("CLAUDE.md") == _checksum(OLD_CHARTER), (
            f"the ledger entry must survive, or the move can never finish:\n{_ledger(clone)}")
        assert "CLAUDE.md: kept as it is" in out, out

        manifest = json.loads((clone / "template-manifest.json").read_text())
        manifest["init_data"] = dict(_FULL_INIT_DATA)
        (clone / "template-manifest.json").write_text(json.dumps(manifest, indent=2))
        proc = _run_update([], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, out
        _assert_v8_shape(clone, "after repair")
        assert (clone / "CLAUDE.md").read_text() == STUB, out


# ------------------------------------------------------- the helpers

def _helpers() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "CLAUDE.md").write_text("x\n")
        (root / "AGENTS.md").symlink_to("CLAUDE.md")
        assert pi.unlink_if_symlink(root / "AGENTS.md") is True
        assert not (root / "AGENTS.md").exists() and not (root / "AGENTS.md").is_symlink()
        assert (root / "CLAUDE.md").read_text() == "x\n", "the link's target is untouched"
        assert pi.unlink_if_symlink(root / "AGENTS.md") is False, "nothing to unlink the second time"
        (root / "AGENTS.md").write_text("# real\n")
        assert pi.unlink_if_symlink(root / "AGENTS.md") is False, "a regular file is never touched"
        assert (root / "AGENTS.md").read_text() == "# real\n"

        assert pi.bootstrap_may_land(root, "CLAUDE.md") is True, "AGENTS.md is a regular file"
        assert pi.bootstrap_may_land(root, "README.md") is True, "only the bootstrap is gated"
        (root / "AGENTS.md").unlink()
        assert pi.bootstrap_may_land(root, "CLAUDE.md") is False, "no AGENTS.md, no bootstrap"
        (root / "AGENTS.md").symlink_to("CLAUDE.md")
        assert pi.bootstrap_may_land(root, "CLAUDE.md") is False, "a link is not the charter"

    with tempfile.TemporaryDirectory() as td:
        clone = Path(td) / "acme-cs"
        skill = clone / ".claude" / "skills" / "cs-review" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: cs-review\n---\n")
        (clone / "CLAUDE.md").write_text(STUB)
        (clone / "AGENTS.md").write_text("# the charter\n")
        with contextlib.redirect_stdout(io.StringIO()):
            pi.install_agent_surfaces(clone)
            pi.install_agent_surfaces(clone)
        agents = clone / "AGENTS.md"
        assert agents.is_file() and not agents.is_symlink() and agents.read_text() == "# the charter\n", (
            "install_agent_surfaces must never replace a real AGENTS.md")
        assert (clone / ".agents" / "skills").is_symlink(), "skill links are unchanged"
        agents.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            pi.install_agent_surfaces(clone)
        assert not agents.exists() and not agents.is_symlink(), "and never creates one"


def main() -> int:
    _fresh_render_stamps_the_shape()
    _init_restamp_over_the_legacy_shape()
    _update_migrates_a_pristine_legacy_clone()
    _update_leaves_an_authored_claude_md_alone()
    _update_supersedes_against_an_older_ledger()
    _update_with_a_failing_charter_render_changes_nothing()
    _helpers()
    print("test_charter_shape: all assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
