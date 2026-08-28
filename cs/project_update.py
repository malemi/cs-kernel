"""cs update — selectively merge template changes into an existing clone.

Reads `template-manifest.json` (created by `cs init`) in the clone root,
compares current template files against stored checksums, and selectively
overwrites or asks on conflict.

Two opt-in discovery/re-pin flags (bare `cs update` is unchanged):

  --check      read the clone's configured kernel origin — the git URL
               already pinned in requirements.txt, parsed, never hardcoded
               — for its tags, and print installed-vs-latest plus (when
               determinable) the newer tag's re-collaudo tier. Writes
               NOTHING.
  --pin TAG    rewrite the kernel pin line in requirements.txt to TAG, and
               with it the ONE derived copy of that number the templates
               render from — `template-manifest.json`'s
               `init_data.repo_kernel_version`. Prints the before/after of
               both. Deliberately does not install it — `uv pip install -r
               requirements.txt` stays a separate, deliberate step.

Neither flag auto-bumps the pin: requirements.txt is the operator's own
pin (v0.5.2 decision — "cs update never touches it"), and every kernel
upgrade owes a re-collaudo (CLAUDE.md, Versioning & release). A `--check`
that rewrote the pin itself would not be a pin anymore.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from difflib import unified_diff
from pathlib import Path

from ._version import kernel_version, kernel_version_bare
from .project_init import (
    RETIRED_COMMAND_NAMES,
    TEMPLATE_DEFAULTS,
    build_jinja_env,
    install_agent_surfaces,
    is_clone_authored,
    is_executable_target,
    load_existing_config,
)


def _retire_generated_commands(clone_root: Path) -> int:
    """Remove the closed set of command-era generated files from a clone."""
    command_dir = clone_root / ".claude" / "commands"
    removed = 0
    for name in RETIRED_COMMAND_NAMES:
        path = command_dir / name
        if path.is_symlink() or path.is_file():
            path.unlink()
            removed += 1
            print(f"  - .claude/commands/{name} (retired)")
    if command_dir.is_dir():
        try:
            command_dir.rmdir()
        except OSError:
            pass
    return removed


def _render_vars(clone_root: Path, init_data: dict) -> dict:
    """The variables today's templates render against, for THIS clone.

    Three layers, weakest first:

    1. `TEMPLATE_DEFAULTS` — the floor. A template that grows a variable an
       older clone's frozen `init_data` never carried would otherwise fail
       under `StrictUndefined` on every existing clone, and `cs update` is
       exactly where that failure lands.
    2. `init_data` — what `cs init` froze into `template-manifest.json`.
    3. The clone's own `manifest.toml`, re-derived here rather than trusted from
       the freeze. `manifest.toml` is the ONE place a clone's values change
       (charter, "Editing this clone"), and `cs init` is not re-run to change
       one: without this layer a value edited there reaches the runtime
       `Settings` but never the stamped surfaces, which then keep rendering
       whatever was true on the day the clone was created.

    Only keys the manifest actually supplies win; a missing or blank one leaves
    the frozen value standing, so a manifest that declares less than the freeze
    never blanks a rendered file.
    """
    merged = {**TEMPLATE_DEFAULTS, **init_data}
    for key, value in (load_existing_config(clone_root) or {}).items():
        if value is None or value == "":
            continue
        merged[key] = value
    merged.pop("dest_dir", None)  # runtime-only; never a template var
    return merged


def _checksum(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


def _read_manifest(clone_root: Path) -> dict | None:
    mf = clone_root / "template-manifest.json"
    if not mf.exists():
        return None
    return json.loads(mf.read_text())


def _write_manifest(clone_root: Path, data: dict) -> None:
    (clone_root / "template-manifest.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    )


def _write_clone_file(clone_file: Path, content: str, out_rel: Path, tpl_name: str) -> None:
    """Write a rendered template into the clone, then restore the mode a
    shell-script target needs. An existing clone re-running `cs update` must
    also end up with an executable `bin/cs_operator_cron.sh` — see
    `is_executable_target`'s docstring for why a 0644 wrapper is a silent
    cron failure, not a cosmetic detail.
    """
    clone_file.write_text(content)
    if is_executable_target(out_rel.parent, tpl_name):
        clone_file.chmod(0o755)


def _read_overwrite_choice(prompt: str, default: str) -> str:
    """Read a conflict-resolution answer from stdin.

    A headless run (agent, cron, `stdin </dev/null`) has no tty to answer
    from: `input()` raises EOFError instead of blocking. Apply the default
    the prompt itself declares (e.g. the capital letter in `[y/N/diff]`)
    rather than letting the traceback kill the whole `cs update` run.
    """
    try:
        return input(prompt).strip().lower()
    except EOFError:
        print("    (no tty — keeping local file)")
        return default


# The draft-only invariant lives in these rendered files. A template update to
# them must LAND — it must never be held hostage by an interactive prompt or a
# headless default that keeps the stale version. On conflict the new render is
# applied, the operator's local version is preserved next to it, and a loud
# message says what to re-apply by hand.
SECURITY_CRITICAL = {".claude/settings.json", "bin/cs_operator_cron.sh"}

# The exact shape `requirements.txt.j2` stamps (see that template):
#   cs-kernel @ git+https://example.invalid/org/cs-kernel@v0.6.1
# Group 1 is the literal PEP 508 direct-URL prefix, group 2 the origin URL
# (whatever it is — never hardcoded here, always read off this line), group
# 3 the pinned tag.
_PIN_RE = re.compile(r"^(cs-kernel\s*@\s*git\+)(\S+)@([^\s@]+)\s*$")

# This project's own tag shape (CLAUDE.md, Versioning & release): semver
# `v0.MINOR.PATCH`, MAJOR always 0.
_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

_RECOLLAUDO_RE = re.compile(r"\*\*Re-collaudo:?\*\*\s*(.+)")


def _find_pin_line(text: str) -> tuple[int, str, str, str] | None:
    """Locate the kernel pin line in `requirements.txt` content.

    Returns `(line_index, prefix, origin_url, tag)` — `prefix` is the
    literal `"cs-kernel @ git+"` text, `origin_url` the git remote the
    pin points at (parsed, never assumed), `tag` the pinned ref — or
    `None` when no line matches the shape this kernel's own
    `requirements.txt.j2` stamps."""
    for i, line in enumerate(text.splitlines()):
        m = _PIN_RE.match(line.strip())
        if m:
            prefix, origin_url, tag = m.groups()
            return i, prefix, origin_url, tag
    return None


def _tag_key(tag: str) -> tuple[int, int, int]:
    m = _TAG_RE.match(tag)
    return tuple(int(x) for x in m.groups()) if m else (-1, -1, -1)


def _parse_remote_tags(ls_remote_output: str) -> list[str]:
    """`vX.Y.Z` tag names from `git ls-remote --tags` output, deduped
    (annotated tags list twice — the ref itself and a `^{}` peeled
    entry) and sorted oldest -> newest. Anything not matching this
    project's own tag shape is ignored, not just skipped-with-a-warning —
    a stray non-release tag on the remote is not this command's business."""
    names: set[str] = set()
    for line in ls_remote_output.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        name = parts[1][len("refs/tags/"):]
        if name.endswith("^{}"):
            name = name[:-3]
        if _TAG_RE.match(name):
            names.add(name)
    return sorted(names, key=_tag_key)


def _extract_recollaudo_tier(changelog_text: str, tag: str) -> str | None:
    """Pull the first `**Re-collaudo:** …` line out of `tag`'s own `##
    <version> — …` section of a CHANGELOG.md that follows this project's
    entry style (see neighbouring CHANGELOG entries). Best-effort: any
    format surprise just yields `None`, never a crash — this is a
    convenience for `--check`'s output, not a parser the release process
    depends on."""
    version = tag[1:] if tag.startswith("v") else tag
    heading = re.search(rf"^## {re.escape(version)}\b", changelog_text, re.MULTILINE)
    if not heading:
        return None
    section = changelog_text[heading.end():]
    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]
    tier = _RECOLLAUDO_RE.search(section)
    if not tier:
        return None
    # First line only: the CHANGELOG's own paragraph is prose for a human
    # reading the file directly, not for a one-line `--check` summary.
    return tier.group(1).split("\n")[0].strip()


def _changelog_tier(origin_url: str, tag: str) -> str | None:
    """Best-effort: the re-collaudo tier `tag`'s CHANGELOG.md entry
    declares, read WITHOUT any extra network round trip beyond the `git
    ls-remote` `--check` already made. Only succeeds when `origin_url`
    names a location git can read straight off the local filesystem (a
    `file://` remote, or a plain local path — the shape a kernel
    developer's own clone may legitimately pin to). A real customer clone
    is pinned to a remote URL (GitHub, in practice) and has no local copy
    of the kernel's tree to read the tag's CHANGELOG.md from; that is the
    common case, and this returns `None` so the caller falls back to
    printing just the tag — never a raw fetch failure."""
    if origin_url.startswith("file://"):
        local_path = origin_url[len("file://"):]
    elif os.path.isdir(origin_url):
        local_path = origin_url
    else:
        return None
    try:
        proc = subprocess.run(
            ["git", "show", f"{tag}:CHANGELOG.md"],
            cwd=local_path, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return _extract_recollaudo_tier(proc.stdout, tag)


def cmd_update_check(clone_root: Path) -> int:
    """`cs update --check`: read the clone's configured kernel origin
    (parsed from requirements.txt's own pin line — never a hardcoded URL)
    for its tags, and print installed-vs-latest. WRITES NOTHING — this is
    discovery only; re-pinning is `--pin`'s job, on request. A network
    failure prints one handled line, never a traceback."""
    req_path = clone_root / "requirements.txt"
    if not req_path.exists():
        print(
            "error: no requirements.txt found in current directory.\n"
            "Run `cs update --check` from the clone root.",
            file=sys.stderr,
        )
        return 1

    found = _find_pin_line(req_path.read_text())
    if found is None:
        print(
            "error: requirements.txt has no recognizable cs-kernel pin line "
            "(expected `cs-kernel @ git+<url>@<tag>`) — cannot check for updates.",
            file=sys.stderr,
        )
        return 1
    _, _prefix, origin_url, pinned_tag = found

    installed = kernel_version_bare()
    print(f"  installed:  {installed or '(unknown — package not installed)'}")
    print(f"  pinned:     {pinned_tag}  ({origin_url})")

    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--tags", origin_url],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"\ncould not reach {origin_url}: {type(e).__name__}: {e}")
        return 1
    if proc.returncode != 0:
        print(f"\ncould not reach {origin_url}: "
              f"{proc.stderr.strip() or 'git ls-remote failed'}")
        return 1

    tags = _parse_remote_tags(proc.stdout)
    if not tags:
        print(f"\nno release tags found at {origin_url}")
        return 1
    latest = tags[-1]
    print(f"  latest:     {latest}")

    if _tag_key(latest) <= _tag_key(pinned_tag):
        print("\nup to date.")
        return 0

    tier = _changelog_tier(origin_url, latest)
    if tier:
        print(f"\nnewer tag available: {latest} — re-collaudo: {tier}")
    else:
        print(f"\nnewer tag available: {latest}")
    print(
        "Every kernel upgrade owes a re-collaudo (CLAUDE.md, Versioning & "
        "release) — this only reports the tag, it writes nothing.\n"
        "To upgrade: run `cs update` and answer y — it re-pins, installs "
        "and re-stamps in one go.\n"
        f"To pin a DIFFERENT version (a rollback, say): `cs update --pin "
        f"<tag>` then `uv pip install -r requirements.txt`."
    )
    return 0


def _sync_manifest_kernel_version(clone_root: Path, tag: str) -> None:
    """Bring `template-manifest.json`'s `init_data.repo_kernel_version` in
    step with the pin `requirements.txt` now carries.

    That field is not decoration: `docs/ARCHITECTURE.md.j2` renders its
    "Kernel pin" row straight out of it (`cs-kernel@v{{ repo_kernel_version
    }}`). A re-pin that left it behind made the operator hand-edit a
    GENERATED file to state the version he had just pinned — and that hand
    edit is what leaves the checksum ledger describing content nobody has on
    disk (see `cmd_update`'s "template unchanged" branch). Owning the field
    here removes the hand edit entirely: the next `cs update` renders the new
    row itself, writes it, and records its checksum in the same pass.

    Bare number, no `v` — every template that reads this field writes the `v`
    itself. A stored `"v0.3.0"` (a real clone carried one for five releases)
    renders `cs-kernel@vv0.3.0`, so the prefix is stripped whatever the
    caller passes.

    Silent no-op when the cwd is not a stamped clone: `--pin` must keep
    working against a bare requirements.txt.
    """
    manifest = _read_manifest(clone_root)
    if manifest is None:
        return
    init_data = manifest.get("init_data")
    if not isinstance(init_data, dict):
        return
    bare = tag[1:] if tag.startswith("v") else tag
    old = init_data.get("repo_kernel_version")
    if old == bare:
        return
    init_data["repo_kernel_version"] = bare
    _write_manifest(clone_root, manifest)
    print(
        f"  · template-manifest.json init_data.repo_kernel_version: "
        f"{old if old is not None else '(absent)'} -> {bare}"
    )


def cmd_update_pin(clone_root: Path, tag: str, advice: bool = True) -> int:
    """`cs update --pin <tag>`: rewrite the kernel pin line in
    requirements.txt to `tag`, print the before/after line, and re-stamp the
    one derived copy of that number the templates render from
    (`template-manifest.json`'s `init_data.repo_kernel_version` — see
    `_sync_manifest_kernel_version`). Does not install it — `uv pip install
    -r requirements.txt` stays a separate, deliberate step, and no rendered
    file is written here: `cs update` is what re-renders them."""
    req_path = clone_root / "requirements.txt"
    if not req_path.exists():
        print(
            "error: no requirements.txt found in current directory.\n"
            "Run `cs update --pin` from the clone root.",
            file=sys.stderr,
        )
        return 1

    text = req_path.read_text()
    found = _find_pin_line(text)
    if found is None:
        print(
            "error: requirements.txt has no recognizable cs-kernel pin line "
            "(expected `cs-kernel @ git+<url>@<tag>`) — nothing to re-pin.",
            file=sys.stderr,
        )
        return 1
    idx, prefix, origin_url, _old_tag = found

    lines = text.splitlines(keepends=True)
    old_line = lines[idx]
    ending = "\n" if old_line.endswith("\n") else ""
    new_line = f"{prefix}{origin_url}@{tag}{ending}"
    lines[idx] = new_line
    req_path.write_text("".join(lines))

    print(f"  - {old_line.rstrip(chr(10))}")
    print(f"  + {new_line.rstrip(chr(10))}")
    _sync_manifest_kernel_version(clone_root, tag)
    if advice:
        print(
            "\nrequirements.txt updated. Installing it is a separate, deliberate "
            "step: run `uv pip install -r requirements.txt`, then re-collaudo per "
            "the new tag's CHANGELOG entry before un-pausing operators."
        )
    return 0


def _offer_release_upgrade(clone_root: Path) -> int | None:
    """Bare `cs update` opener: one quick look at the pinned origin's tags;
    when a newer release exists, OFFER the upgrade —
    ``Found new tag (vX.Y.Z). Update? [y/N]``.

    The pin stays operator-owned: the default is No, EOF/^C on the prompt
    resolves to No with the decision printed (the v0.5.2 EOF contract), and
    nothing is rewritten without an explicit "y". On yes: rewrite the pin
    line (the same path as ``--pin``), install requirements into THIS venv,
    then re-exec ``cs update`` so the template refresh runs on the NEW
    kernel — the old one stays loaded in this process and would stamp the
    previous release's templates. An unreachable origin is one printed line
    and the update continues offline: discovery must never block a template
    refresh. Returns an exit code to stop with, or None to continue.
    """
    req_path = clone_root / "requirements.txt"
    if not req_path.exists():
        return None  # nothing pinned — nothing to offer
    found = _find_pin_line(req_path.read_text())
    if found is None:
        return None
    _idx, _prefix, origin_url, pinned_tag = found
    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--tags", origin_url],
            capture_output=True, text=True, timeout=20,
        )
        tags = _parse_remote_tags(proc.stdout) if proc.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        tags = []
    if not tags:
        print(f"(release check skipped: could not read tags from {origin_url})")
        return None
    latest = tags[-1]
    if _tag_key(latest) <= _tag_key(pinned_tag):
        return None  # up to date — proceed quietly
    tier = _changelog_tier(origin_url, latest)
    tier_note = f" — re-collaudo: {tier}" if tier else ""
    try:
        answer = input(
            f"Found new tag ({latest}, pinned {pinned_tag}{tier_note}). "
            f"Update? [y/N]: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo answer — keeping the current pin "
              "(explicit re-pin: `cs update --pin`).")
        answer = "n"
    if answer not in ("y", "yes"):
        print(f"Keeping {pinned_tag}; the template refresh below uses the "
              f"installed kernel.")
        return None
    rc = cmd_update_pin(clone_root, latest, advice=False)
    if rc != 0:
        return rc
    print("Installing the new pin into this venv …")
    # `uv pip install`, not `python -m pip` — a venv created exactly per
    # this kernel's own README Step 2 (`uv venv .venv`, no `--seed`) has no
    # `pip` module inside it AT ALL, confirmed live 2026-08-21 ("No module
    # named pip"). `uv` is already a hard prerequisite (Step 1); `--python`
    # targets THIS process's interpreter, matching the working pattern
    # `cs/project_init.py`'s own install offer already uses.
    proc = subprocess.run(
        ["uv", "pip", "install", "--python", sys.executable,
         "-q", "-r", "requirements.txt"],
        cwd=clone_root,
    )
    if proc.returncode != 0:
        print(
            "pip install FAILED — the pin is rewritten but not installed. "
            "Fix the error, run `uv pip install -r requirements.txt`, then "
            "`cs update` again.",
            file=sys.stderr,
        )
        return proc.returncode
    print(f"Installed {latest}. Re-running `cs update` on the new kernel …")
    os.execv(sys.executable, [sys.executable, "-m", "cs", "update"])
    return 0  # unreachable in production; reached only when execv is stubbed


def cmd_update(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cs update")
    parser.add_argument("--version", action="version", version=kernel_version())
    checkpin = parser.add_mutually_exclusive_group()
    checkpin.add_argument(
        "--check", action="store_true",
        help="check the clone's configured kernel origin (requirements.txt) "
        "for a newer tag; print installed-vs-latest and, when known, the "
        "re-collaudo tier the newer tag's CHANGELOG entry declares. Writes "
        "NOTHING.",
    )
    checkpin.add_argument(
        "--pin", metavar="TAG",
        help="rewrite requirements.txt's kernel pin line to TAG (e.g. "
        "v0.7.0), and with it template-manifest.json's derived "
        "init_data.repo_kernel_version; print the before/after of both. "
        "Does not install it — `uv pip install -r requirements.txt` is a "
        "separate, deliberate step.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="also report the files cs update deliberately leaves alone "
        "(requirements.txt, manifest.toml) — normally silent, since a file "
        "that was not touched is not an event.",
    )

    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 1)

    clone_root = Path.cwd()
    verbose = parsed.verbose

    if parsed.check:
        return cmd_update_check(clone_root)
    if parsed.pin:
        return cmd_update_pin(clone_root, parsed.pin)

    # Verify we're in a clone
    manifest = _read_manifest(clone_root)
    if manifest is None:
        print(
            "error: no template-manifest.json found in current directory.\n"
            "Run `cs update` from the clone root (where template-manifest.json lives).",
            file=sys.stderr,
        )
        return 1

    # Bare `cs update` opens with the release offer (prompted, default No);
    # on an accepted upgrade it re-execs on the new kernel and never returns.
    rc = _offer_release_upgrade(clone_root)
    if rc is not None:
        return rc

    # Find template root
    import cs as cs_mod

    template_root = Path(cs_mod.__file__).parent / "templates" / "project"
    if not template_root.is_dir():
        print(f"error: template directory not found at {template_root}", file=sys.stderr)
        return 1

    env = build_jinja_env(template_root)

    init_data = manifest.get("init_data", {})
    render_vars = _render_vars(clone_root, init_data)
    old_checksums: dict = manifest.get("file_checksums", {})
    new_checksums: dict[str, str] = {}

    updated = 0
    skipped = 0
    added = 0
    retired = _retire_generated_commands(clone_root)
    # Paths whose stored checksum does NOT describe the file on disk, and
    # which this run had no update to offer for. The ledger is left as it is
    # (see the branch that fills this list); what may not happen is that the
    # run ends without saying so.
    drifted: list[str] = []

    # Walk template files
    for tpl_file in sorted(template_root.rglob("*")):
        if tpl_file.is_dir():
            continue

        # Compute relative path (strip template_root)
        rel: Path = tpl_file.relative_to(template_root)
        str_rel = str(rel)

        # Strip .j2 extension for the output path
        out_rel = rel.parent / rel.name[:-3] if rel.name.endswith(".j2") else rel
        str_out_rel = str(out_rel)

        # The two clone-owned files are decided BEFORE the render, not after.
        # Rendering a template whose output is discarded is not free: it is
        # evaluated against this clone's own variables, so a template that grows
        # a variable nothing answers fails here — printing "! failed to render
        # manifest.toml.j2" on every update, about a file cs update was never
        # going to write.
        if str_out_rel == "requirements.txt":
            # requirements.txt is operational state, not a template render
            # target: "upgrades are a pin bump" (CLAUDE.md, Versioning &
            # release). Letting cs update rewrite it would either silently
            # re-pin the clone or overwrite it with whatever `cs init` froze
            # long ago — stale or outright broken. It is the operator's file;
            # cs update only reports that it exists and leaves it alone.
            if verbose:
                print("  · requirements.txt is yours (the version pin) — left alone")
            continue

        if str_out_rel == "manifest.toml":
            # manifest.toml is clone-owned by charter (CLAUDE.md.j2,
            # "Editing this clone" — the ONE place values change), same
            # class as requirements.txt: written once by `cs init`, never a
            # render target again. Confirmed live 2026-08-21: offering it
            # through the normal diff/overwrite flow let an operator
            # "overwrite" their hand-authored manifest with a bare re-render
            # from frozen init_data — which also broke the file outright,
            # because bare TOML keys can't hold an `@` (an email-shaped
            # account name, the DOCUMENTED recommended shape, made the
            # rendered file fail to parse). cs update only reports that it
            # exists and leaves it alone; `cs init` is the only writer.
            if verbose:
                print("  · manifest.toml is yours (your company settings) — left alone")
            continue

        if rel.name.endswith(".j2"):
            # Render through the SAME environment `cs init` uses — loader
            # included, and the template loaded BY NAME rather than from a
            # string. An env built with no loader raises "no loader for this
            # environment specified" on the first `{% include %}`, which would
            # mean a shared partial renders at `cs init` and breaks every
            # clone's next `cs update`.
            try:
                tpl = env.get_template(str(rel).replace(os.sep, "/"))
                rendered = tpl.render(**render_vars)
            except Exception as e:
                print(f"  ! failed to render {rel}: {e}", file=sys.stderr)
                continue
        else:
            rendered = tpl_file.read_text()

        if is_clone_authored(str_out_rel):
            # A clone-authored file: create it if the clone has none, then never
            # touch it again. See CLONE_AUTHORED_PREFIXES for why this is not a
            # conflict to resolve but a file class that must not be tracked.
            clone_file = clone_root / out_rel
            if clone_file.exists():
                if verbose:
                    print(f"  · {str_out_rel} is yours (clone-authored) — left alone")
            else:
                clone_file.parent.mkdir(parents=True, exist_ok=True)
                _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
                added += 1
                print(f"  + {str_out_rel}")
            continue

        rendered_checksum = _checksum(rendered)
        # Provisional: this is the right value for every path that ends with the
        # clone holding today's render. A declined overwrite is the exception and
        # puts the OLD checksum back, because recording today's render for a file
        # the operator refused would make the next run compute
        # `rendered == stored` and report "template unchanged" — the conflict is
        # never offered again and the clone keeps a stale file in silence. A
        # decision to skip once is not a decision to stop being asked.
        new_checksums[str_out_rel] = rendered_checksum

        clone_file = clone_root / out_rel

        if str_out_rel in old_checksums:
            # Template existed before
            old_tpl_checksum = old_checksums[str_out_rel]
            if rendered_checksum == old_tpl_checksum:
                # The TEMPLATE is unchanged. That is not the same statement as
                # "the clone file is unchanged", and this branch used to make
                # the second one for free: it skipped without ever reading the
                # file, re-recording a checksum nothing had compared against
                # disk. That is how a ledger entry comes to describe content
                # that is not there — an operator hand-edits a stamped file,
                # today's render happens to equal the stored value, and
                # `cs update` walks past in silence. Releases later the
                # template finally changes, the divergence surfaces as
                # "modified locally AND template changed", a headless run
                # answers the declared N, and the file drops out of template
                # maintenance for good (`v0.21.0`: five releases). So the file
                # is read here too, and the two cases it can be in are both
                # answered rather than assumed away.
                if not clone_file.exists():
                    # The ledger claims a checksum for a file the clone does
                    # not have. Nothing of the operator's can be lost by
                    # writing the render the stored checksum already blesses —
                    # it IS that content — and every other branch of this walk
                    # restores a missing template file. Only this one did not.
                    clone_file.parent.mkdir(parents=True, exist_ok=True)
                    _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
                    added += 1
                    print(f"  + {str_out_rel} (restored — the clone no longer had it)")
                elif _checksum(clone_file.read_text()) != rendered_checksum:
                    # Locally modified, and today's template has nothing to
                    # offer it: there is no conflict to resolve, so nothing is
                    # written and the stored checksum stays the TEMPLATE's.
                    # Recording the local content instead would make the next
                    # real template change read as "clone is original" and
                    # overwrite the edit without asking. Reported at the end of
                    # the run: a ledger entry that does not describe its file is
                    # exactly the thing that must never be silent.
                    drifted.append(str_out_rel)
                continue

            # Template changed. Check if clone was modified.
            if clone_file.exists():
                clone_content = clone_file.read_text()
                clone_checksum = _checksum(clone_content)

                if clone_checksum == old_tpl_checksum:
                    # Clone is original (unmodified since init) — safe to overwrite
                    clone_file.parent.mkdir(parents=True, exist_ok=True)
                    _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
                    updated += 1
                    print(f"  ✓ {str_out_rel}")
                elif clone_checksum == rendered_checksum:
                    # The file on disk already IS today's render — the stored
                    # checksum is just stale (content brought in sync by some
                    # other means: a hand-edit that converged, a one-off
                    # re-render outside `cs update`). Nothing to ask: the
                    # "modified locally AND template changed" branch below
                    # would fire here too, but its diff is empty by
                    # construction (clone_content == rendered), which is
                    # confirmed confusing live — the operator sees a conflict
                    # prompt and a "diff" option that prints nothing. Silently
                    # re-record the correct checksum instead.
                    print(f"  ✓ {str_out_rel} (already current)")
                elif str_out_rel in SECURITY_CRITICAL:
                    # Security-critical: never ask. Apply the new render, and
                    # preserve the operator's local version next to it — the
                    # backup always holds the state from just before THIS
                    # update, so overwrite it if one already exists.
                    backup_file = clone_file.with_name(clone_file.name + ".local-bak")
                    backup_file.write_text(clone_content)
                    _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
                    updated += 1
                    print(f"  ! {str_out_rel}: SECURITY-CRITICAL template updated — new version applied.")
                    print(f"    Your locally-edited version was saved to {str_out_rel}.local-bak.")
                    print("    Re-apply any clone-specific entries on top of the new file, then delete the backup.")
                else:
                    # Clone was modified AND template changed — ask
                    print(f"\n  ? {str_out_rel}: modified locally AND template changed.")
                    response = _read_overwrite_choice("    Overwrite? [y/N/diff] ", default="n")
                    if response == "y":
                        clone_file.parent.mkdir(parents=True, exist_ok=True)
                        _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
                        updated += 1
                        print(f"    → overwritten")
                    elif response == "diff":
                        diff = list(
                            unified_diff(
                                clone_content.splitlines(True),
                                rendered.splitlines(True),
                                fromfile=f"clone/{str_out_rel}",
                                tofile=f"template/{str_out_rel}",
                            )
                        )
                        print("".join(diff))
                        response2 = _read_overwrite_choice("    Overwrite? [y/N] ", default="n")
                        if response2 == "y":
                            clone_file.parent.mkdir(parents=True, exist_ok=True)
                            _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
                            updated += 1
                            print(f"    → overwritten after diff")
                        else:
                            new_checksums[str_out_rel] = old_tpl_checksum
                            skipped += 1
                    else:
                        new_checksums[str_out_rel] = old_tpl_checksum
                        skipped += 1
            else:
                # Clone doesn't have this file yet — add it
                clone_file.parent.mkdir(parents=True, exist_ok=True)
                _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
                added += 1
                print(f"  + {str_out_rel}")
        else:
            # New template file (not in old manifest)
            clone_file.parent.mkdir(parents=True, exist_ok=True)
            _write_clone_file(clone_file, rendered, out_rel, tpl_file.name)
            added += 1
            print(f"  + {str_out_rel}")

    # Update manifest
    manifest["file_checksums"] = new_checksums
    _write_manifest(clone_root, manifest)

    print(
        f"\nDone: {updated} updated, {skipped} skipped (modified locally), "
        f"{added} added, {retired} retired."
    )

    if drifted:
        print(
            f"\n! {len(drifted)} file(s) on disk differ from the checksum "
            f"template-manifest.json records for them:"
        )
        for rel_path in drifted:
            print(f"    {rel_path}")
        print(
            "  Today's template renders exactly what the ledger already holds, so\n"
            "  there was nothing to apply and nothing was written — these carry local\n"
            "  edits. A template-owned file is edited in the KERNEL TEMPLATE, never in\n"
            "  the clone (CLAUDE.md, \"Editing this clone\"). Left as they are, the next\n"
            "  release that changes one of these templates arrives as a conflict prompt,\n"
            "  and a headless run answers it \"keep local\" — which is how a file leaves\n"
            "  template maintenance without anyone deciding that it should."
        )

    # Re-point every agent at the refreshed canonical skills tree and retire
    # the exact command-era OpenCode/Codex entries. This is not optional or a
    # separate verb: an update must not leave a second discovery surface stale.
    install_agent_surfaces(clone_root)
    return 0
