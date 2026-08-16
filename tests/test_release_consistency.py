"""Release-truth gate: package metadata, the changelog, the operator docs and the
gates `tests/run.sh` actually EXECUTES must agree.

Hermetic: reads files from this repo plus local git refs. No network, no engine,
no mailbox.

Each check is a drift class that has really happened:

1. the pyproject version owns a changelog SECTION with a real body and a
   re-collaudo tier — never a placeholder pointing at an ephemeral report
   (`v0.5.0` shipped as two lines saying the drafts were "in the agents'
   reports", which no reader of this repo can open);
2. the company-literal gate in `tests/run.sh` rejects every charter token IN
   THE PATTERN IT RUNS, and the case-sensitive `\\bHB\\b` leg still exists —
   asserting on the file's TEXT passes on a token left in a comment;
3. `docs/active-context.md` names BOTH the latest semver release tag and whether
   current HEAD is tagged — a docs-only commit after a release must not turn the
   release truth red, while calling `v0.4.0` latest after `v0.5.0` still fails;
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

# Explicit release-state markers. "Latest release" and "HEAD" are different
# facts: after a docs-only commit v0.5.0 can remain the latest immutable release
# while HEAD is (truthfully) untagged.
LATEST_RELEASE_RE = re.compile(
    rf"latest release tag:\s*`(?P<tag>v{SEMVER})`", re.I
)
HEAD_UNTAGGED_RE = re.compile(r"current HEAD status:\s*untagged\b", re.I)
HEAD_TAGGED_RE = re.compile(
    rf"current HEAD status:\s*tagged as\s*`(?P<tag>v{SEMVER})`", re.I
)

# This tag was already published before this candidate existed. Moving it is
# forbidden by the release plan; pin its object so a force-move cannot be
# described away in prose.
IMMUTABLE_TAG_TARGETS = {
    "v0.5.0": "038d7e59dd4ec0959cb190e060271041575f2dc9",
    "v0.5.1": "b2f07b29623a2cf4fa4d46c370fac02617833716",
}

# A published tag must install as the version it claims: `git show
# <tag>:pyproject.toml` has to declare the tag's own number, or a clone
# pinned at vX.Y.Z reports something else from `cs --version` and from
# `pip show`, and the collaudo's "Installed" column lies.
#
# The exceptions below are IMMUTABLE MISTAKES, recorded rather than hidden —
# the tags cannot be moved, so the registry is the only honest place to keep
# them. Nothing may be added here without an operator decision; a NEW
# mismatch is a release bug to fix before tagging, not an entry to append.
TAG_VERSION_EXCEPTIONS = {
    # Historical, found by this gate the day it was written — the drift is
    # older than the incident that prompted it, which is the point of
    # writing gates instead of remembering rules.
    "v0.4.0": "0.3.7",
    "v0.5.0": "0.4.5",
    # 2026-08-16: v0.6.1 and v0.7.0 were both cut without bumping
    # pyproject.toml, so each installs and reports 0.6.0 — including from
    # the `cs --version` that v0.7.0 exists to add. Fixed forward by
    # v0.7.1, which is also where this gate lands.
    "v0.6.1": "0.6.0",
    "v0.7.0": "0.6.0",
}

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
# 3. release refs and current HEAD are separate facts
# --------------------------------------------------------------------------- #
def _git(*args: str) -> list[str]:
    """Run one read-only git query and return its non-blank output lines."""
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"`git {' '.join(args)}` failed (rc={proc.returncode}): "
        f"{proc.stderr.strip()!r}. This gate reads real refs; it does not skip."
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _version_key(tag: str) -> tuple[int, int, int]:
    return tuple(  # type: ignore[return-value]
        int(part) for part in tag.removeprefix("v").split(".")
    )


def version_tags() -> list[str]:
    """All local semver tags, newest version first."""
    tags = [tag for tag in _git("tag", "--list") if re.fullmatch(rf"v{SEMVER}", tag)]
    return sorted(tags, key=_version_key, reverse=True)


def version_tags_at_head() -> list[str]:
    """Semver tags pointing exactly at current HEAD."""
    return [
        tag
        for tag in _git("tag", "--points-at", "HEAD")
        if re.fullmatch(rf"v{SEMVER}", tag)
    ]


def check_tag_versions(tags: list[str]) -> list[str]:
    """Every release tag must ship a pyproject declaring that same version.

    Returns the tags checked clean. A mismatch that is not in
    TAG_VERSION_EXCEPTIONS fails: it means a tag was cut without bumping
    `pyproject.toml`, so the package installs under the previous number
    while claiming to be the new one.
    """
    checked = []
    for tag in tags:
        raw = "\n".join(_git("show", f"{tag}:pyproject.toml"))
        declared = tomllib.loads(raw)["project"]["version"]
        expected = tag[1:]
        if declared == expected:
            checked.append(tag)
            continue
        known = TAG_VERSION_EXCEPTIONS.get(tag)
        assert known == declared, (
            f"{tag} ships pyproject version {declared!r}, expected {expected!r} — "
            f"a clone pinned at {tag} would install and report {declared}. "
            "Bump pyproject.toml in the release commit BEFORE tagging; only an "
            "already-published tag may be recorded in TAG_VERSION_EXCEPTIONS, "
            "and only by operator decision."
        )
    return checked


def tag_commit(tag: str) -> str:
    lines = _git("rev-parse", f"{tag}^{{commit}}")
    assert len(lines) == 1, f"expected one commit for {tag}, got {lines}"
    return lines[0]


def check_immutable_tag_targets(actual: dict[str, str]) -> list[str]:
    """Published anchors never move, even if prose and HEAD move together."""
    for tag, expected in IMMUTABLE_TAG_TARGETS.items():
        assert tag in actual, f"immutable release tag {tag} is missing"
        assert actual[tag] == expected, (
            f"immutable release tag {tag} moved: expected {expected}, got {actual[tag]}"
        )
    return sorted(actual)


def check_release_state(
    active: str, tags: list[str], head_tags: list[str]
) -> tuple[str, list[str]]:
    """Active context agrees with latest release and current HEAD separately."""
    assert tags, "repository has no semver release tags"
    latest = tags[0]
    claims = {m.group("tag") for m in LATEST_RELEASE_RE.finditer(active)}
    assert claims == {latest}, (
        f"docs/active-context.md must contain exactly "
        f"'Latest release tag: `{latest}`'; "
        f"found {sorted(claims) or 'no explicit claim'}"
    )

    says_untagged = bool(HEAD_UNTAGGED_RE.search(active))
    claimed_head_tags = {m.group("tag") for m in HEAD_TAGGED_RE.finditer(active)}
    assert not (says_untagged and claimed_head_tags), (
        "docs/active-context.md claims HEAD is both tagged and untagged"
    )
    if head_tags:
        assert claimed_head_tags == set(head_tags), (
            f"HEAD carries {head_tags}, but active context claims "
            f"{sorted(claimed_head_tags) or 'no HEAD tag'}"
        )
    else:
        assert says_untagged, (
            "current HEAD has no semver tag; active context must contain the explicit "
            "marker `Current HEAD status: untagged`"
        )
        assert not claimed_head_tags
    return latest, head_tags


def _expect_assertion(fn, needle: str) -> None:
    try:
        fn()
    except AssertionError as exc:
        assert needle in str(exc), f"negative proof failed for the wrong reason: {exc}"
    else:
        raise AssertionError(f"negative proof did not fail: expected {needle!r}")


def prove_release_state_negatives(
    active: str, tags: list[str], head_tags: list[str], actual_targets: dict[str, str]
) -> int:
    """Prove the gate rejects its own two highest-risk drift classes."""
    assert len(tags) >= 2, "negative proof needs an older release tag"
    stale = LATEST_RELEASE_RE.sub(
        f"Latest release tag: `{tags[1]}`", active, count=1
    )
    _expect_assertion(
        lambda: check_release_state(stale, tags, head_tags),
        "must contain exactly",
    )

    moved = dict(actual_targets)
    moved["v0.5.0"] = "0" * 40
    _expect_assertion(
        lambda: check_immutable_tag_targets(moved),
        "immutable release tag v0.5.0 moved",
    )
    return 2


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
    tags = version_tags()
    head_tags = version_tags_at_head()
    latest, head_tags = check_release_state(active, tags, head_tags)
    tag_versions = check_tag_versions(tags)
    actual_targets = {tag: tag_commit(tag) for tag in IMMUTABLE_TAG_TARGETS}
    immutable = check_immutable_tag_targets(actual_targets)
    negative_proofs = prove_release_state_negatives(
        active, tags, head_tags, actual_targets
    )
    assert release in active, (
        f"{release} (the pyproject version) is not mentioned in docs/active-context.md"
    )
    pins = check_readme_pins(readme, changelog, release)

    print(
        f"test_release_consistency: {release} — changelog section {body_lines} lines, "
        f"re-collaudo tier '{tier}'; executing charter grep carries "
        f"{len(COMPANY_TOKENS)} company tokens + {HB_TOKEN}; latest release "
        f"{latest}; HEAD {', '.join(head_tags) if head_tags else 'untagged'}; immutable "
        f"{', '.join(immutable)}; {negative_proofs} negative release proofs; README pins "
        f"{', '.join('v' + p for p in pins)}; tag/pyproject match "
        f"{len(tag_versions)}/{len(tags)} ({len(TAG_VERSION_EXCEPTIONS)} recorded exceptions)"
    )


if __name__ == "__main__":
    main()
