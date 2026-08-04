"""cs update — selectively merge template changes into an existing clone.

Reads `template-manifest.json` (created by `cs init`) in the clone root,
compares current template files against stored checksums, and selectively
overwrites or asks on conflict.
"""
from __future__ import annotations

import hashlib
import json
import sys
from difflib import unified_diff
from pathlib import Path


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


def cmd_update(args: list[str]) -> int:
    clone_root = Path.cwd()

    # Verify we're in a clone
    manifest = _read_manifest(clone_root)
    if manifest is None:
        print(
            "error: no template-manifest.json found in current directory.\n"
            "Run `cs update` from the clone root (where template-manifest.json lives).",
            file=sys.stderr,
        )
        return 1

    # Find template root
    import cs as cs_mod

    template_root = Path(cs_mod.__file__).parent / "templates" / "project"
    if not template_root.is_dir():
        print(f"error: template directory not found at {template_root}", file=sys.stderr)
        return 1

    import jinja2

    init_data = manifest.get("init_data", {})
    old_checksums: dict = manifest.get("file_checksums", {})
    new_checksums: dict[str, str] = {}

    updated = 0
    skipped = 0
    added = 0

    # Walk template files
    for tpl_file in sorted(template_root.rglob("*")):
        if tpl_file.is_dir():
            continue

        # Compute relative path (strip template_root)
        rel: Path = tpl_file.relative_to(template_root)
        str_rel = str(rel)

        # Strip .j2 extension for the output path
        if rel.name.endswith(".j2"):
            out_name = rel.name[:-3]
            out_rel = rel.parent / out_name
            # Render template
            template_str = tpl_file.read_text()
            try:
                env = jinja2.Environment(
                    undefined=jinja2.StrictUndefined,
                    trim_blocks=True,
                    lstrip_blocks=True,
                )
                tpl = env.from_string(template_str)
                # dest_dir is runtime-only; never a template var
                render_vars = {k: v for k, v in init_data.items() if k != "dest_dir"}
                rendered = tpl.render(**render_vars)
            except Exception as e:
                print(f"  ! failed to render {rel}: {e}", file=sys.stderr)
                continue
        else:
            out_rel = rel
            rendered = tpl_file.read_text()

        str_out_rel = str(out_rel)
        rendered_checksum = _checksum(rendered)
        new_checksums[str_out_rel] = rendered_checksum

        clone_file = clone_root / out_rel

        if str_out_rel in old_checksums:
            # Template existed before
            old_tpl_checksum = old_checksums[str_out_rel]
            if rendered_checksum == old_tpl_checksum:
                # Template unchanged — skip
                continue

            # Template changed. Check if clone was modified.
            if clone_file.exists():
                clone_content = clone_file.read_text()
                clone_checksum = _checksum(clone_content)

                if clone_checksum == old_tpl_checksum:
                    # Clone is original (unmodified since init) — safe to overwrite
                    clone_file.parent.mkdir(parents=True, exist_ok=True)
                    clone_file.write_text(rendered)
                    updated += 1
                    print(f"  ✓ {str_out_rel}")
                else:
                    # Clone was modified AND template changed — ask
                    print(f"\n  ? {str_out_rel}: modified locally AND template changed.")
                    response = _read_overwrite_choice("    Overwrite? [y/N/diff] ", default="n")
                    if response == "y":
                        clone_file.parent.mkdir(parents=True, exist_ok=True)
                        clone_file.write_text(rendered)
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
                            clone_file.write_text(rendered)
                            updated += 1
                            print(f"    → overwritten after diff")
                        else:
                            skipped += 1
                    else:
                        skipped += 1
            else:
                # Clone doesn't have this file yet — add it
                clone_file.parent.mkdir(parents=True, exist_ok=True)
                clone_file.write_text(rendered)
                added += 1
                print(f"  + {str_out_rel}")
        else:
            # New template file (not in old manifest)
            clone_file.parent.mkdir(parents=True, exist_ok=True)
            clone_file.write_text(rendered)
            added += 1
            print(f"  + {str_out_rel}")

    # Update manifest
    manifest["file_checksums"] = new_checksums
    _write_manifest(clone_root, manifest)

    print(f"\nDone: {updated} updated, {skipped} skipped (modified locally), {added} added.")
    return 0
