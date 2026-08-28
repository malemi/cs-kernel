"""Gate: every agent resolves the same project-scoped skills.

The canonical render lives under `.claude/skills`. Codex and OpenCode receive
repository links to that tree; command-era project mirrors and home-global
Codex prompts are retired by an exact, closed name set. Unrelated user files
must survive, and filesystems without symlink support receive equivalent
copies.
"""
from __future__ import annotations

import contextlib
import io
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


def _clone(root: Path, name: str) -> Path:
    clone = root / name
    for skill in ("cs-review", "cs-help"):
        path = clone / ".claude" / "skills" / skill / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(f"---\nname: {skill}\ndescription: {name}\n---\n")
    (clone / "CLAUDE.md").write_text(f"# manual of {name}\n")
    return clone


@contextlib.contextmanager
def _legacy_prompts(tmp: Path, name: str = "codex-prompts"):
    real = pi.LEGACY_CODEX_PROMPTS
    pi.LEGACY_CODEX_PROMPTS = tmp / name
    try:
        yield pi.LEGACY_CODEX_PROMPTS
    finally:
        pi.LEGACY_CODEX_PROMPTS = real


def _seed_legacy(clone: Path, prompts: Path) -> None:
    for directory in (clone / ".opencode" / "commands", prompts):
        directory.mkdir(parents=True)
        for name in pi.RETIRED_COMMAND_NAMES:
            (directory / name).write_text("obsolete\n")
        (directory / "mine.md").write_text("keep\n")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        clone = _clone(tmp, "acme-cs")

        print("project-scoped skill wiring and exact legacy cleanup")
        with _legacy_prompts(tmp) as prompts:
            _seed_legacy(clone, prompts)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                pi.install_agent_surfaces(clone)

            canonical = clone / ".claude" / "skills"
            codex = clone / ".agents" / "skills"
            opencode = clone / ".opencode" / "skills"
            check("Codex skills are a repository symlink", codex.is_symlink())
            check("OpenCode skills are a repository symlink", opencode.is_symlink())
            check("Codex resolves canonical bytes",
                  (codex / "cs-review/SKILL.md").read_bytes()
                  == (canonical / "cs-review/SKILL.md").read_bytes())
            check("OpenCode resolves canonical bytes",
                  (opencode / "cs-help/SKILL.md").read_bytes()
                  == (canonical / "cs-help/SKILL.md").read_bytes())
            check("AGENTS.md resolves to CLAUDE.md",
                  (clone / "AGENTS.md").read_text() == (clone / "CLAUDE.md").read_text())
            check("all retired OpenCode commands are gone",
                  all(not (clone / ".opencode/commands" / n).exists()
                      for n in pi.RETIRED_COMMAND_NAMES))
            check("all retired global prompts are gone",
                  all(not (prompts / n).exists() for n in pi.RETIRED_COMMAND_NAMES))
            check("unrelated OpenCode command survives",
                  (clone / ".opencode/commands/mine.md").read_text() == "keep\n")
            check("unrelated global prompt survives",
                  (prompts / "mine.md").read_text() == "keep\n")
            check("cleanup is reported", "Retired 10 obsolete" in out.getvalue())

            with contextlib.redirect_stdout(io.StringIO()):
                pi.install_agent_surfaces(clone)
            check("a second wiring pass is idempotent",
                  (codex / "cs-review/SKILL.md").is_file())

        print("fresh clones create no command surface")
        fresh = _clone(tmp, "fresh-cs")
        with _legacy_prompts(tmp, "fresh-prompts"):
            with contextlib.redirect_stdout(io.StringIO()):
                pi.install_agent_surfaces(fresh)
        check("no .claude/commands directory", not (fresh / ".claude/commands").exists())
        check("no .opencode/commands directory", not (fresh / ".opencode/commands").exists())

        print("a filesystem that refuses symlinks")
        nolink = _clone(tmp, "win-cs")
        real_symlink = Path.symlink_to

        def refuse(self, target, target_is_directory=False):
            raise OSError("symlinks not supported")

        Path.symlink_to = refuse
        try:
            with _legacy_prompts(tmp, "win-prompts"):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    pi.install_agent_surfaces(nolink)
            codex_copy = nolink / ".agents/skills/cs-help/SKILL.md"
            opencode_copy = nolink / ".opencode/skills/cs-review/SKILL.md"
            check("Codex falls back to a real skill copy",
                  codex_copy.is_file() and not (nolink / ".agents/skills").is_symlink())
            check("fallback copy has canonical content",
                  codex_copy.read_bytes()
                  == (nolink / ".claude/skills/cs-help/SKILL.md").read_bytes())
            check("OpenCode fallback also has canonical content",
                  opencode_copy.read_bytes()
                  == (nolink / ".claude/skills/cs-review/SKILL.md").read_bytes())
            check("copy fallback is disclosed", "copied" in out.getvalue())
        finally:
            Path.symlink_to = real_symlink

    print("test_agent_surfaces: all assertions passed" if not FAILED
          else f"test_agent_surfaces: {FAILED} FAILURES")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
