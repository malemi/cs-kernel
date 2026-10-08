#!/usr/bin/env python3
"""The legal-research skill reaches a clone whole, and its helper only counts days.

`cs-legal-research` is the first kernel skill that carries supporting files:
four reference documents, a provenance file and a date-arithmetic helper beside
its `SKILL.md`. Four properties are gated here.

**Every file of the skill is a `.j2` template.** A plain `.py` under
`cs/templates/` is byte-compiled by `pip install`, and both stamping walks then
meet a `__pycache__/*.pyc`: `render_templates` stamps it into the clone and
`cs update` dies reading it as text. The package-inventory gate (step 3) also
inventories `*.j2` only, so a plain supporting file could be missing from the
wheel with every gate green. A supporting file is therefore a `.j2` whose whole
body sits in one `{% raw %}` block, which renders it byte for byte.

**A stamped clone holds the whole skill, on every host.** `.agents/skills` and
`.opencode/skills` resolve the same bytes as `.claude/skills` for all seven
files, every one is in the checksum ledger, and every relative link the skill
prints points at a file the clone actually has.

**The helper is arithmetic and says so.** The stamped `count_days.py`, run
through each host's own path, reproduces the arithmetic cases it was written
against, labels every result as arithmetic and not a legal deadline, and
refuses — with no result on stdout — what it cannot count.

**The skill grants nothing.** Neither `.claude/settings.json` nor the cron
wrapper names the skill or its helper, and the triage branch the skill points
legal customer mail at is still there. Its interactive-only boundary is
instruction-level, so what is asserted is the text that carries it: the
description every host reads before it selects a skill.

The last leg stamps from the INSTALLED package, and only runs when this
interpreter holds an installed build of this very version — under tests/run.sh,
the environment `pip install` just made.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TPL = ROOT / "cs" / "templates" / "project"
SKILL = "cs-legal-research"
SKILL_TPL = TPL / ".claude" / "skills" / SKILL

# The stamped files, relative to the skill directory. Other gates import this
# list rather than keep their own.
LEGAL_FILES = (
    "PROVENANCE.md",
    "SKILL.md",
    "references/administrative-remedies.md",
    "references/deadlines.md",
    "references/evidence.md",
    "references/sources.md",
    "scripts/count_days.py",
)
HELPER = "scripts/count_days.py"
HOSTS = (".claude", ".agents", ".opencode")
RAW_OPEN, RAW_CLOSE = "{% raw -%}\n", "{% endraw %}\n"

ARITHMETIC_ONLY = "arithmetic_only_not_a_legal_deadline"

# (what the case proves, arguments, expected values by dotted path)
CASES = (
    ("a trigger inside an exclusion starts counting on the first day after it",
     ["--trigger", "2026-08-10", "--days", "60", "--exclude", "2026-08-01:2026-08-31"],
     {"first_counted_day": "2026-09-01", "result": "2026-10-30"}),
    ("no exclusion and no holiday is ever implied",
     ["--trigger", "2026-08-10", "--days", "120"],
     {"result": "2026-12-08", "inputs.expiry_holidays": []}),
    ("a supplied holiday moves the expiry and keeps the raw last day",
     ["--trigger", "2026-08-10", "--days", "120", "--expiry-holiday", "2026-12-08"],
     {"raw_last_counted_day": "2026-12-08", "result": "2026-12-09"}),
    ("weekends inside the period are counted; only the expiry rolls",
     ["--trigger", "2026-09-04", "--days", "3", "--roll-weekday", "5", "--roll-weekday", "6"],
     {"result": "2026-09-07"}),
    ("consecutive expiry adjustments chain, each one recorded",
     ["--trigger", "2026-09-04", "--days", "1", "--roll-weekday", "5", "--roll-weekday", "6",
      "--expiry-holiday", "2026-09-07"],
     {"result": "2026-09-08", "expiry_adjustments.#": 3}),
    ("overlapping exclusions are not double counted",
     ["--trigger", "2026-07-30", "--days", "3", "--exclude", "2026-08-01:2026-08-20",
      "--exclude", "2026-08-15:2026-08-31"],
     {"result": "2026-09-02"}),
    ("an exclusion's end date is inclusive",
     ["--trigger", "2026-08-30", "--days", "1", "--exclude", "2026-08-01:2026-08-31"],
     {"result": "2026-09-01"}),
    ("--include-trigger counts the trigger day itself",
     ["--trigger", "2026-09-01", "--days", "1", "--include-trigger"],
     {"result": "2026-09-01"}),
    ("a leap day is a day",
     ["--trigger", "2028-02-28", "--days", "2"], {"result": "2028-03-01"}),
    ("a period crosses the year boundary",
     ["--trigger", "2026-12-31", "--days", "1"], {"result": "2027-01-01"}),
)

# (what is refused, arguments, text stderr must carry or None)
REFUSALS = (
    ("a date that does not exist", ["--trigger", "2026-02-30", "--days", "1"], None),
    ("a period of zero days", ["--trigger", "2026-01-01", "--days", "0"], None),
    ("a reversed exclusion interval",
     ["--trigger", "2026-01-01", "--days", "1", "--exclude", "2026-08-31:2026-08-01"], None),
    ("rolling the expiry off every weekday",
     ["--trigger", "2026-01-01", "--days", "1"]
     + [arg for n in range(7) for arg in ("--roll-weekday", str(n))], None),
    ("a period past the last representable date",
     ["--trigger", "9999-12-31", "--days", "1"], None),
    ("an expiry adjustment that enters an excluded interval",
     ["--trigger", "2026-07-30", "--days", "1", "--expiry-holiday", "2026-07-31",
      "--exclude", "2026-08-01:2026-08-31"], "not supported"),
)

FAILED = 0


def check(label: str, cond: bool) -> None:
    global FAILED
    print(f"  {'ok  ' if cond else 'FAIL'} {label}")
    if not cond:
        FAILED += 1


_MISSING = object()


def _dig(value, dotted: str):
    """`a.b` walks dicts; a trailing `#` is the length of what it reached.
    A key the helper did not print is `_MISSING`, which equals no expectation."""
    for part in dotted.split("."):
        try:
            value = len(value) if part == "#" else value[part]
        except (KeyError, TypeError):
            return _MISSING
    return value


def _bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _text(path: Path) -> str:
    """A missing file reads as empty: the check that needs its text then fails
    by name, instead of the script dying on the first absent file."""
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _source_shape() -> None:
    print("every file of the skill is a .j2, and a supporting file is one raw block")
    compiled = sorted(p.relative_to(ROOT).as_posix()
                      for p in (ROOT / "cs" / "templates").rglob("*")
                      if p.is_file() and (p.suffix in (".py", ".pyc") or "__pycache__" in p.parts))
    check(f"no Python source or bytecode sits in the template roots: {compiled}", not compiled)

    present = sorted(p.relative_to(SKILL_TPL).as_posix()
                     for p in SKILL_TPL.rglob("*") if p.is_file())
    check(f"the skill's template files are exactly the seven .j2 sources: {present}",
          present == sorted(f"{rel}.j2" for rel in LEGAL_FILES))

    for rel in LEGAL_FILES:
        template = SKILL_TPL / f"{rel}.j2"
        if not template.is_file():
            continue  # already reported by the exact-set check above
        raw = template.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        # `cs update` decodes every template as text and writes it back with
        # LF endings, so anything else reaches an updated clone differently
        # from a freshly stamped one — or stops the update outright.
        check(f"{rel}.j2 is UTF-8 text with LF line endings",
              text is not None and b"\r" not in raw)
        if rel == "SKILL.md" or text is None:
            continue
        body = text[len(RAW_OPEN):len(text) - len(RAW_CLOSE)]
        check(f"{rel}.j2 is one raw block and nothing else",
              text.startswith(RAW_OPEN) and text.endswith(RAW_CLOSE)
              and "{% raw" not in body and "{% endraw" not in body)


def _render(dest: Path) -> dict:
    from cs import project_init as pi
    from test_project_update import _FULL_INIT_DATA

    dest.mkdir(parents=True)
    real = pi.LEGACY_CODEX_PROMPTS
    pi.LEGACY_CODEX_PROMPTS = dest.parent / "no-legacy-prompts"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ok, checksums = pi.render_templates(
                {**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}, TPL, dest)
            pi.install_agent_surfaces(dest)
    finally:
        pi.LEGACY_CODEX_PROMPTS = real
    check("the clone renders", ok)
    return checksums


def _stamped_whole(clone: Path, checksums: dict) -> None:
    print("a stamped clone holds the whole skill, on every host")
    canonical = clone / ".claude" / "skills" / SKILL
    stamped = sorted(p.relative_to(canonical).as_posix()
                     for p in canonical.rglob("*") if p.is_file())
    check(f"the clone receives exactly the seven files: {stamped}",
          stamped == sorted(LEGAL_FILES))

    for rel in LEGAL_FILES:
        template = SKILL_TPL / f"{rel}.j2"
        rendered = _bytes(canonical / rel)
        if rel != "SKILL.md" and template.is_file():
            source = template.read_text(encoding="utf-8")
            wrapped = source[len(RAW_OPEN):len(source) - len(RAW_CLOSE)]
            check(f"{rel} is stamped byte for byte from its raw block",
                  rendered == wrapped.encode("utf-8"))
        if rel == "SKILL.md":
            # The one file rendered as a template. A supporting file is a raw
            # block, where `{{` is ordinary text and the comparison above is
            # the proof.
            check("SKILL.md carries no unrendered Jinja",
                  rendered is not None and b"{%" not in rendered and b"{{" not in rendered)
        check(f"{rel} is stamped", rendered is not None)
        check(f"{rel} is in the checksum ledger",
              f".claude/skills/{SKILL}/{rel}" in checksums)
        for host in (".agents", ".opencode"):
            check(f"{host} resolves the canonical {rel}",
                  rendered is not None
                  and _bytes(clone / host / "skills" / SKILL / rel) == rendered)

    skill = _text(canonical / "SKILL.md")
    parts = skill.split("---", 2)
    front = parts[1] if len(parts) == 3 else ""
    check("frontmatter names the skill after its directory", f"name: {SKILL}\n" in front)
    check("the description confines the skill to an interactive human's question",
          "interactive session" in front and "scheduled operator" in front
          and "customer mail" in front)

    for rel in ("SKILL.md", *(r for r in LEGAL_FILES if r.startswith("references/"))):
        text = _text(canonical / rel)
        for target in re.findall(r"\]\((?!https?://)([^)#]+)\)", text):
            check(f"{rel} links to a stamped file: {target}",
                  (canonical / rel).parent.joinpath(target).is_file())
    deadlines = _text(canonical / "references/deadlines.md")
    named = f".claude/skills/{SKILL}/{HELPER}"
    check("the deadlines reference names the helper by its path inside the clone",
          named in deadlines and (clone / named).is_file())


def _helper(clone: Path) -> None:
    print("the stamped helper only counts days, through every host path")
    for host in HOSTS:
        script = clone / host / "skills" / SKILL / HELPER

        def run(args):
            return subprocess.run([sys.executable, str(script), *args],
                                  capture_output=True, text=True)

        for label, args, expected in CASES:
            proc = run(args)
            try:
                value = json.loads(proc.stdout)
            except ValueError:
                value = None
            ok = proc.returncode == 0 and value is not None
            check(f"[{host}] {label}",
                  ok and _dig(value, "status") == ARITHMETIC_ONLY
                  and all(_dig(value, path) == want for path, want in expected.items()))
        for label, args, needle in REFUSALS:
            proc = run(args)
            check(f"[{host}] refuses {label} with no result on stdout",
                  proc.returncode != 0 and not proc.stdout
                  and (needle is None or needle in proc.stderr))


def _grants_nothing(clone: Path) -> None:
    print("the skill grants nothing and points at a live triage branch")
    for rel in (".claude/settings.json", "bin/cs_operator_cron.sh"):
        text = (clone / rel).read_text(encoding="utf-8")
        check(f"{rel} names neither the skill nor its helper",
              SKILL not in text and "count_days" not in text)
    triage = (clone / ".claude/skills/cs-triage-mail/SKILL.md").read_text(encoding="utf-8")
    check("triage still escalates a legal-sensitive customer message",
          "**(b) Escalate**" in triage and "legal-" in triage)
    skill = _text(clone / ".claude/skills" / SKILL / "SKILL.md")
    check("the skill sends legal customer mail to that branch",
          "Escalate branch of `cs-triage-mail`" in skill)
    for rel in ("AGENTS.md", ".claude/skills/cs-help/SKILL.md"):
        check(f"{rel} routes to the skill",
              f"`{SKILL}`" in (clone / rel).read_text(encoding="utf-8"))


_INSTALLED_RENDER = """\
import contextlib, io, json, sys
from pathlib import Path
import cs
from cs import project_init as pi
dest = Path(sys.argv[1])
pi.LEGACY_CODEX_PROMPTS = dest.parent / "no-legacy-prompts"
with contextlib.redirect_stdout(io.StringIO()):
    ok, _ = pi.render_templates(
        {**pi.TEMPLATE_DEFAULTS, **json.load(sys.stdin)},
        Path(cs.__file__).parent / "templates" / "project", dest)
    pi.install_agent_surfaces(dest)
sys.exit(0 if ok else 1)
"""


def _installed_build(tmp: Path, source_clone: Path) -> None:
    """Stamp from the package this interpreter has INSTALLED, never the source.

    `-I` keeps the working directory, the script directory and PYTHONPATH off
    the import path, so the child can only reach a real installation. Under
    tests/run.sh that is the build `pip install` just made, which is where a
    compiled helper would sit. Any other interpreter holds some other clone's
    kernel, or none, and the leg is skipped with a note rather than run
    against the wrong code.
    """
    print("a pip-installed build stamps the same seven files, and no bytecode")
    probe = subprocess.run(
        [sys.executable, "-I", "-c",
         "import importlib.metadata as m, cs, pathlib;"
         "print(m.version('cs-kernel'));"
         "print(pathlib.Path(cs.__file__).resolve().parent)"],
        cwd=tmp, capture_output=True, text=True)
    found = probe.stdout.split("\n")[:2] if probe.returncode == 0 else []
    this_version = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    package = Path(found[1]) if len(found) == 2 else None
    if package is None or found[0] != this_version or package == (ROOT / "cs").resolve():
        held = "no cs-kernel" if package is None else (
            "this source tree itself" if package == (ROOT / "cs").resolve()
            else f"cs-kernel {found[0]}")
        print(f"  note: this interpreter holds {held}, not an installed "
              f"{this_version} — skipped here; tests/run.sh runs this leg from "
              f"its fresh environment, which is what gates packaging")
        return

    packaged = sorted(p.relative_to(package).as_posix()
                      for p in (package / "templates").rglob("*")
                      if p.suffix == ".pyc" or "__pycache__" in p.parts)
    check(f"the installed template roots hold no bytecode: {packaged}", not packaged)

    from test_project_update import _FULL_INIT_DATA
    clone = tmp / "installed-cs"
    proc = subprocess.run([sys.executable, "-I", "-c", _INSTALLED_RENDER, str(clone)],
                          cwd=tmp, input=json.dumps(_FULL_INIT_DATA),
                          capture_output=True, text=True)
    check(f"the installed package renders a clone {proc.stderr.strip()[-300:]}",
          proc.returncode == 0)
    stamped_bytecode = sorted(p.relative_to(clone).as_posix() for p in clone.rglob("*")
                              if p.suffix == ".pyc" or "__pycache__" in p.parts)
    check(f"no bytecode is stamped into the clone: {stamped_bytecode}",
          not stamped_bytecode)
    skill = clone / ".claude" / "skills" / SKILL
    stamped = sorted(p.relative_to(skill).as_posix() for p in skill.rglob("*") if p.is_file())
    check(f"the installed build stamps exactly the seven files: {stamped}",
          stamped == sorted(LEGAL_FILES))
    for rel in LEGAL_FILES:
        want = _bytes(source_clone / ".claude" / "skills" / SKILL / rel)
        check(f"the installed build stamps the same {rel} as the source tree",
              want is not None and _bytes(skill / rel) == want)
        for host in (".agents", ".opencode"):
            check(f"{host} resolves the installed build's {rel}",
                  want is not None and _bytes(clone / host / "skills" / SKILL / rel) == want)


def main() -> int:
    _source_shape()
    with tempfile.TemporaryDirectory() as td:
        clone = Path(td) / "acme-cs"
        checksums = _render(clone)
        _stamped_whole(clone, checksums)
        _helper(clone)
        _grants_nothing(clone)
        _installed_build(Path(td), clone)
    print("test_legal_research_skill: all assertions passed" if not FAILED
          else f"test_legal_research_skill: {FAILED} FAILURES")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
