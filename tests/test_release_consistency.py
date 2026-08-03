"""Release-truth gate: package metadata, the changelog, the operator docs and the
gates `tests/run.sh` actually EXECUTES must agree.

Hermetic: reads files from this repo plus one local `git tag --points-at HEAD`.
No network, no engine, no mailbox.

Each check is a drift class that has really happened:

1. the pyproject version owns a changelog SECTION with a real body and a
   re-collaudo tier — never a placeholder pointing at an ephemeral report
   (`v0.5.0` shipped as two lines saying the drafts were "in the agents'
   reports", which no reader of this repo can open);
2. the company-literal gate in `tests/run.sh` rejects every charter token IN
   THE PATTERN IT RUNS, and the case-sensitive `\\bHB\\b` leg still exists —
   asserting on the file's TEXT passes on a token left in a comment;
3. `docs/active-context.md` names the tag that actually points at HEAD as the
   tip (or states explicitly that HEAD carries no tag) — the active context
   called `v0.4.0` the tip while `v0.5.0` was cut;
4. every `cs-kernel@vX.Y.Z` install line in `README.md` is either the package
   version or the operational pin recorded in `CHANGELOG.md` — a blacklist of
   one obsolete tag rots the day a second obsolete tag appears.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SEMVER = r"\d+\.\d+\.\d+"

# Tier vocabulary CHANGELOG.md declares in its own header line:
# "which clones must re-collaudo and at which tier (… static / +live read-only / full)".
COLLAUDO_TIERS = ("static", "live read-only", "full")

# Charter §1 tokens: the company literals the gate must reject. The same list has
# to appear in CLAUDE.md's documented grep AND in the pattern tests/run.sh runs.
COMPANY_TOKENS = (
    "mrcall\\.ai",
    "cafe124",
    "124-cs",
    "centralix",
    "/home/mal",
    "mario",
    "alemi",
)
# The shared-drive literal, grepped case-SENSITIVELY as its own leg.
HB_TOKEN = "\\bHB\\b"

# A release entry states why, what, and the re-collaudo tier. The v0.5.0
# placeholder that prompted this gate was 2 non-blank lines / ~126 chars.
MIN_BODY_LINES = 5
MIN_BODY_CHARS = 300

# The tier is stated on the re-collaudo marker line or in its wrapped
# continuation; the marker plus five lines covers both the bullet shape
# ("- **Re-collaudo:** …") and the heading shape ("### Re-collaudo").
COLLAUDO_WINDOW = 6

# How far above an install line the pin guidance may sit.
POINTER_LOOKBACK = 5

# `grep [-flags] '<pattern>' cs/` — the invocation shape of the charter gate.
GREP_CALL_RE = re.compile(r"grep\s+(?P<opts>(?:-{1,2}\S+\s+)*)'(?P<pattern>[^']*)'\s+cs/")

# Who is the tip. Both shapes occur in the operator docs:
#   "**`v0.4.0` is the tip; …**"   /   "The immutable repository tip/tag is `v0.5.0`"
TIP_CLAIM_RES = (
    re.compile(
        rf"`?\*{{0,2}}v(?P<v>{SEMVER})\*{{0,2}}`?\s+(?:is|remains|stays)\s+"
        rf"(?:the\s+)?(?:current\s+|repository\s+|immutable\s+)?tip",
        re.I,
    ),
    re.compile(rf"tip(?:/tag)?\s*(?:is|:|=)\s*\*{{0,2}}`?v(?P<v>{SEMVER})", re.I),
)
NO_TAG_RES = (
    re.compile(r"no tag (?:currently )?points at HEAD", re.I),
    re.compile(r"HEAD (?:is untagged|carries no tag)", re.I),
)

PIN_RE = re.compile(rf"cs-kernel@v(?P<v>{SEMVER})")
PIN_MARKER_LABEL = "current operational pin"
POINTER_RE = re.compile(r"operational pin[^.]*CHANGELOG\.md", re.I | re.S)


# --------------------------------------------------------------------------- #
# 1. changelog completeness
# --------------------------------------------------------------------------- #
def check_changelog_entry(changelog: str, release: str) -> tuple[int, str]:
    """The section for `release` has a real body and names a re-collaudo tier."""
    lines = changelog.splitlines()
    version_re = re.compile(rf"(?<![\w.]){re.escape(release)}(?![\w.])")
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("## ") and version_re.search(ln)),
        None,
    )
    assert start is not None, (
        f"{release} (the pyproject version) has no '## …{release}…' heading in CHANGELOG.md"
    )
    end = next(
        (j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")), len(lines)
    )
    body = lines[start + 1 : end]
    filled = [ln for ln in body if ln.strip()]
    text = "\n".join(filled)
    assert len(filled) >= MIN_BODY_LINES and len(text) >= MIN_BODY_CHARS, (
        f"the CHANGELOG.md section for {release} is a placeholder: {len(filled)} "
        f"non-blank line(s), {len(text)} chars (need >= {MIN_BODY_LINES} lines and "
        f">= {MIN_BODY_CHARS} chars). A release entry states why, what, and the "
        f"re-collaudo tier — not a pointer to a report this repo does not hold.\n"
        f"--- section body ---\n{text}\n--- end of section body ---"
    )

    tier = None
    for k, line in enumerate(body):
        if "collaudo" not in line.lower():
            continue
        window = " ".join(body[k : k + COLLAUDO_WINDOW]).lower()
        tier = next((t for t in COLLAUDO_TIERS if t in window), None)
        if tier:
            break
    assert tier is not None, (
        f"the CHANGELOG.md section for {release} has no re-collaudo line naming a "
        f"tier ({' / '.join(COLLAUDO_TIERS)}). Every entry states which clones must "
        f"re-collaudo and at which tier (design brief §6.6)."
    )
    return len(filled), tier


# --------------------------------------------------------------------------- #
# 2. the charter gate that actually executes
# --------------------------------------------------------------------------- #
def grep_legs(text: str) -> list[tuple[str, str]]:
    """(short flags, pattern) for every `grep … '<pattern>' cs/` invocation in `text`."""
    legs = []
    for m in GREP_CALL_RE.finditer(text):
        flags = "".join(
            opt.lstrip("-") for opt in m.group("opts").split() if not opt.startswith("--")
        )
        legs.append((flags, m.group("pattern")))
    return legs


def _best_leg(legs: list[tuple[str, str]]) -> tuple[str, str]:
    """The leg carrying the most company tokens — the company-literal gate."""
    return max(legs, key=lambda leg: sum(t in leg[1] for t in COMPANY_TOKENS))


def check_executing_charter_gate(runner: str, charter: str) -> None:
    runner_legs = grep_legs(runner)
    assert runner_legs, (
        "could not parse a single `grep … '<pattern>' cs/` invocation out of "
        "tests/run.sh: this gate cannot verify a gate it cannot read. Fix the "
        "parser or the runner — do not let it pass silently."
    )
    flags, pattern = _best_leg(runner_legs)
    missing = [t for t in COMPANY_TOKENS if t not in pattern]
    assert not missing, (
        f"the company-literal grep tests/run.sh EXECUTES does not reject {missing}. "
        f"Executed pattern: {pattern!r}. A token that survives only in a comment or "
        f"in prose gates nothing."
    )
    assert "i" in flags, (
        f"the company-literal grep must run case-insensitively (-i), or 'cafe124' "
        f"misses 'CAFE124'; flags parsed from tests/run.sh: {flags!r}"
    )

    hb_legs = [leg for leg in runner_legs if HB_TOKEN in leg[1]]
    assert hb_legs, (
        f"tests/run.sh executes no grep over cs/ carrying {HB_TOKEN!r}: the "
        f"shared-drive literal leg is gone. Patterns found: {[p for _, p in runner_legs]}"
    )
    assert any("i" not in f for f, _ in hb_legs), (
        f"the {HB_TOKEN!r} leg must stay case-SENSITIVE, or the lowercase 'hb' path "
        f"segment false-positives; flags found: {[f for f, _ in hb_legs]}"
    )

    charter_legs = grep_legs(charter)
    assert charter_legs, (
        "CLAUDE.md documents no `grep … '<pattern>' cs/` command, so the charter and "
        "the executable gate can no longer be compared."
    )
    _, charter_pattern = _best_leg(charter_legs)
    charter_missing = [t for t in COMPANY_TOKENS if t not in charter_pattern]
    assert not charter_missing, (
        f"the grep documented in CLAUDE.md omits {charter_missing}; charter and "
        f"executing gate must reject the same tokens. Documented pattern: "
        f"{charter_pattern!r}"
    )
    assert any(HB_TOKEN in p for _, p in charter_legs), (
        f"the grep documented in CLAUDE.md omits {HB_TOKEN!r}"
    )


# --------------------------------------------------------------------------- #
# 3. the tip the repository actually has
# --------------------------------------------------------------------------- #
def tags_at_head() -> list[str]:
    """Version tags pointing at HEAD. Local git read: hermetic, but real."""
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "tag", "--points-at", "HEAD"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"`git tag --points-at HEAD` failed (rc={proc.returncode}): "
        f"{proc.stderr.strip()!r}. This gate must read the real tip; it does not skip."
    )
    return [
        t.strip()
        for t in proc.stdout.splitlines()
        if re.fullmatch(rf"v{SEMVER}", t.strip())
    ]


def check_tip(active: str) -> list[str]:
    tags = tags_at_head()
    if not tags:
        assert any(rx.search(active) for rx in NO_TAG_RES), (
            "no version tag points at HEAD and docs/active-context.md does not say "
            "so. State the discrepancy explicitly (e.g. 'no tag points at HEAD')."
        )
        return tags

    claimed = sorted({m.group("v") for rx in TIP_CLAIM_RES for m in rx.finditer(active)})
    assert claimed, (
        f"docs/active-context.md makes no claim about the repository tip while "
        f"{', '.join(tags)} points at HEAD. Name the tip explicitly."
    )
    actual = {t.lstrip("v") for t in tags}
    wrong = [c for c in claimed if c not in actual]
    assert not wrong, (
        f"docs/active-context.md calls v{', v'.join(wrong)} the tip, but the tag(s) "
        f"actually pointing at HEAD are {', '.join(tags)}."
    )
    return tags


# --------------------------------------------------------------------------- #
# 4. README install pins
# --------------------------------------------------------------------------- #
def operational_pins(changelog: str) -> list[str]:
    """Tags CHANGELOG.md records on its '<current operational pin>' marker line."""
    pins: list[str] = []
    for line in changelog.splitlines():
        if PIN_MARKER_LABEL in line.lower():
            pins.extend(m.group(1) for m in re.finditer(rf"v({SEMVER})", line))
    return pins


def check_readme_pins(readme: str, changelog: str, release: str) -> list[str]:
    lines = readme.splitlines()
    hits = [(i, m.group("v")) for i, ln in enumerate(lines) for m in PIN_RE.finditer(ln)]
    assert hits, (
        "README.md contains no 'cs-kernel@vX.Y.Z' install line, so its pin guidance "
        "cannot be checked against anything."
    )
    pins = operational_pins(changelog)
    assert pins, (
        f"CHANGELOG.md has no '{PIN_MARKER_LABEL}' line naming a vX.Y.Z tag; the "
        f"README's install pin then has no recorded fact to agree with."
    )
    allowed = {release.lstrip("v"), *pins}
    wrong = sorted({v for _, v in hits if v not in allowed})
    assert not wrong, (
        f"README.md installs cs-kernel@v{', v'.join(wrong)}; the only pins it may "
        f"name are the package version {release} and the operational pin(s) recorded "
        f"in CHANGELOG.md ({', '.join('v' + p for p in pins)})."
    )
    assert any(
        POINTER_RE.search("\n".join(lines[max(0, i - POINTER_LOOKBACK) : i]))
        for i, _ in hits
    ), (
        "no README.md install line is introduced by a pointer to the operational pin "
        "recorded in CHANGELOG.md, so a reader gets a bare tag with no way to tell "
        "whether it is still the current one."
    )
    return sorted({v for _, v in hits})


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    release = f"v{version}"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    active = (ROOT / "docs" / "active-context.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    charter = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    runner = (ROOT / "tests" / "run.sh").read_text(encoding="utf-8")

    body_lines, tier = check_changelog_entry(changelog, release)
    check_executing_charter_gate(runner, charter)
    tags = check_tip(active)
    assert release in active, (
        f"{release} (the pyproject version) is not mentioned in docs/active-context.md"
    )
    pins = check_readme_pins(readme, changelog, release)

    print(
        f"test_release_consistency: {release} — changelog section {body_lines} lines, "
        f"re-collaudo tier '{tier}'; executing charter grep carries "
        f"{len(COMPANY_TOKENS)} company tokens + {HB_TOKEN}; tip "
        f"{', '.join(tags) or 'untagged (declared in active-context)'}; README pins "
        f"{', '.join('v' + p for p in pins)}"
    )


if __name__ == "__main__":
    main()
