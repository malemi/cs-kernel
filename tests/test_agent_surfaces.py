"""Gate: every agent reads the SAME commands — `install_agent_surfaces`.

Found live 2026-08-21: a clone's `.opencode/commands/` was a git-tracked
COPY of the commands, frozen in July, still advertising `/munchausen` and
the other pre-`cs-` names weeks after `.claude/commands/` had been
renamed. The kernel only ever rendered `.claude/`, so nothing kept the two
in step — a second copy is a second source, and it drifts.

`.claude/` stays the one rendered set; every other surface points into it:
`.opencode/commands/*.md`, `.opencode/skills`, `AGENTS.md` (which BOTH
OpenCode and Codex read as project instructions), and — home-global, so
shared by every clone on the machine — `~/.codex/prompts/*.md`.

Guards:
1. after a stamp, OpenCode sees exactly the same command NAMES as Claude
   Code, resolving to the same bytes, as symlinks (no second copy);
2. renaming a command in `.claude/` and re-stamping removes the old name
   from `.opencode/` — the exact drift that happened;
3. `AGENTS.md` resolves to `CLAUDE.md`;
4. Codex prompts already owned by ANOTHER clone are never silently
   hijacked: with `ask=True` and a closed stdin the answer resolves to No
   and the other clone keeps them (the v0.5.2 EOF contract);
5. a filesystem that refuses symlinks still gets working copies.
"""
from __future__ import annotations

import builtins
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cs import project_init as pi  # noqa: E402

FAILED = 0


def check(label: str, cond: bool) -> None:
    global FAILED
    print(f"  {'ok  ' if cond else 'FAIL'} {label}")
    if not cond:
        FAILED += 1


def _clone(root: Path, name: str, commands=("cs-review.md", "cs-help.md")) -> Path:
    d = root / name
    (d / ".claude" / "commands").mkdir(parents=True)
    (d / ".claude" / "skills" / "cs-operator").mkdir(parents=True)
    for c in commands:
        (d / ".claude" / "commands" / c).write_text(f"# {c} of {name}\n")
    (d / ".claude" / "skills" / "cs-operator" / "SKILL.md").write_text("skill\n")
    (d / "CLAUDE.md").write_text(f"# manual of {name}\n")
    return d


@contextlib.contextmanager
def _codex_home(tmp: Path, name: str = "codex-prompts"):
    """Point CODEX_PROMPTS at a scratch dir — the real one is the
    developer's own ~/.codex, which a test must never write into. Each
    scenario gets its OWN directory: Codex's prompt dir is home-global, so
    a shared fixture would carry one scenario's ownership into the next."""
    real = pi.CODEX_PROMPTS
    pi.CODEX_PROMPTS = tmp / name
    try:
        yield pi.CODEX_PROMPTS
    finally:
        pi.CODEX_PROMPTS = real


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        clone = _clone(tmp, "acme-cs")

        print("stamping a fresh clone")
        with _codex_home(tmp) as codex:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                pi.install_agent_surfaces(clone)

            oc = clone / ".opencode" / "commands"
            claude_names = {p.name for p in (clone / ".claude/commands").glob("*.md")}
            check("OpenCode sees the same command names as Claude Code",
                  {p.name for p in oc.glob("*.md")} == claude_names)
            check("they are symlinks, not a second copy",
                  all(p.is_symlink() for p in oc.glob("*.md")))
            check("and they resolve to the same bytes",
                  (oc / "cs-review.md").read_text()
                  == (clone / ".claude/commands/cs-review.md").read_text())
            check("skills are wired too",
                  (clone / ".opencode/skills/cs-operator/SKILL.md").is_file())
            check("AGENTS.md resolves to CLAUDE.md",
                  (clone / "AGENTS.md").read_text() == (clone / "CLAUDE.md").read_text())
            check("Codex prompts point at this clone",
                  os.path.realpath(codex / "cs-review.md")
                  == os.path.realpath(clone / ".claude/commands/cs-review.md"))

            print("a renamed command must not survive in .opencode/")
            (clone / ".claude/commands/cs-review.md").unlink()
            (clone / ".claude/commands/cs-triage.md").write_text("# renamed\n")
            with contextlib.redirect_stdout(io.StringIO()):
                pi.install_agent_surfaces(clone)
            check("the old name is gone from OpenCode",
                  not (oc / "cs-review.md").exists())
            check("the new name is there",
                  (oc / "cs-triage.md").is_symlink())

        print("Codex prompts owned by another clone")
        other = _clone(tmp, "other-cs", commands=("cs-triage.md",))
        with _codex_home(tmp, "codex-shared") as codex:
            with contextlib.redirect_stdout(io.StringIO()):
                pi.install_agent_surfaces(other)          # other-cs claims them
            first = os.path.realpath(codex / "cs-triage.md")
            check("the first clone owns them",
                  first == os.path.realpath(other / ".claude/commands/cs-triage.md"))

            old_input = builtins.input
            builtins.input = lambda *a, **k: (_ for _ in ()).throw(EOFError())
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    pi.install_agent_surfaces(clone)      # acme-cs asks, gets EOF
            finally:
                builtins.input = old_input
            check("a closed stdin does NOT hijack another clone's prompts",
                  os.path.realpath(codex / "cs-triage.md") == first)
            check("and it says where they stayed", "leaving Codex" in out.getvalue())

            old_input = builtins.input
            builtins.input = lambda *a, **k: "y"
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    pi.install_agent_surfaces(clone)
            finally:
                builtins.input = old_input
            check("an explicit yes does move them",
                  os.path.realpath(codex / "cs-triage.md")
                  == os.path.realpath(clone / ".claude/commands/cs-triage.md"))

        print("a filesystem that refuses symlinks")
        nolink = _clone(tmp, "win-cs", commands=("cs-help.md",))
        real_symlink = Path.symlink_to

        def refuse(self, target, target_is_directory=False):
            raise OSError("symlinks not supported")

        Path.symlink_to = refuse
        try:
            with _codex_home(tmp, "codex-win"):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    pi.install_agent_surfaces(nolink, ask=False)
                dst = nolink / ".opencode/commands/cs-help.md"
                check("falls back to a real copy", dst.is_file() and not dst.is_symlink())
                check("with the right content",
                      dst.read_text() == (nolink / ".claude/commands/cs-help.md").read_text())
                check("and says it copied", "copied" in out.getvalue())
        finally:
            Path.symlink_to = real_symlink

    print("test_agent_surfaces: all assertions passed" if not FAILED
          else f"test_agent_surfaces: {FAILED} FAILURES")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
