"""`cs project` — stamp a project's written memory from the kernel templates.

WHY THIS IS CODE AND NOT A CONVENTION IN A README. Every clone keeps a folder
per company under `docs/projects/`, and that folder is the operator's memory of
the relationship: what is agreed, what we owe, what happened, who these people
are. A convention documented in prose drifts the moment somebody is in a hurry —
the observed failure is a live prospect whose folder held a dossier and nothing
else, so three weeks of meetings and a changed project scope existed only in one
person's head. A generator makes the shape the default: `cs project new <name>`
and the structure is already right, in every clone, identically.

WHAT THE SHAPE IS, and why each part exists:

  README.md    what this project is + the index of its own files
  status.md    the ONLY file describing the present — agreed scope, what we owe,
               deadlines, live risks. One home for state, so two files can never
               disagree about it.
  timeline.md  what happened, when, and how we know. Append-only: a timeline's
               value is that it shows what we believed at the time.
  meetings/    one file per meeting, append-only, corrections dated at the
               bottom. A meeting note that gets edited in place quietly rewrites
               history and hides that we misread the room.

Each stamped file opens with front matter and an `## Abstract`, mirroring the
`docs/` harness: a reader decides in ten seconds whether to read on. The bodies
are HTML comments describing what to write rather than prose pretending to be
content — an empty section is honest, invented content is not.

The templates live in `cs/templates/project_memory/`, deliberately NOT under
`cs/templates/project/`: they are stamped per project by this verb, not once per
clone by `cs init`. Company variance comes from Settings (manifest → env) as
everywhere else in the kernel — this module contains no company literal.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import jinja2

from . import _time, config

# Relative to the clone root, which is also where every permission string runs
# from (`find_manifest_path()` reads ./manifest.toml, no upward walk).
PROJECTS_DIR = Path("docs") / "projects"

# A folder slug: lowercase, digits, hyphens. NOT a person's first name and not a
# mail address — those produce folders nobody can guess the name of later.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def _template_root() -> Path:
    return Path(__file__).parent / "templates" / "project_memory"


def title_from_slug(slug: str) -> str:
    """`acme-corp` -> `Acme Corp`. A starting point for the human title, which
    the operator overrides with --title when the real name has punctuation or
    a legal form (`Acme Corp S.p.A.`)."""
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def render_scaffold(dest: Path, render_vars: dict) -> list[Path]:
    """Render every template into `dest`. Returns the files written, in order.

    Kept separate from the command so a test can exercise the rendering without
    driving argparse or a manifest.
    """
    root = _template_root()
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(root)),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )
    written: list[Path] = []
    for tpl in sorted(root.rglob("*")):
        if tpl.is_dir():
            continue
        rel = tpl.relative_to(root)
        out = dest / rel
        if out.suffix == ".j2":
            out = out.with_suffix("")
        out.parent.mkdir(parents=True, exist_ok=True)
        if tpl.suffix == ".j2":
            out.write_text(
                env.get_template(str(rel)).render(**render_vars), encoding="utf-8"
            )
        else:
            out.write_bytes(tpl.read_bytes())
        written.append(out)

    # `meetings/` must survive a commit even while empty, or the scaffold's
    # append-only half silently disappears from git and the next session does
    # not know where meeting notes go.
    meetings = dest / "meetings"
    meetings.mkdir(parents=True, exist_ok=True)
    keep = meetings / ".gitkeep"
    keep.write_text("", encoding="utf-8")
    written.append(keep)
    return written


def cmd_project_new(args) -> int:
    name = args.name.strip()
    if not _SLUG_RE.match(name):
        print(
            f"error: '{name}' is not a folder slug.\n"
            "Use lowercase letters, digits and hyphens (e.g. acme-corp) — not a "
            "first name, not a mail address: the folder has to be guessable "
            "months from now.",
            file=sys.stderr,
        )
        return 2

    # Refuse to stamp outside a clone. Without this the verb happily creates
    # docs/projects/<name>/ in whatever directory it was run from.
    if not Path("manifest.toml").exists():
        print(
            "error: no manifest.toml in the current directory.\n"
            "Run `cs project new` from the clone root — that is where the "
            "manifest and env chain resolve from.",
            file=sys.stderr,
        )
        return 2

    dest = PROJECTS_DIR / name
    if dest.exists():
        print(
            f"error: {dest} already exists — refusing to overwrite it.\n"
            "A project's memory is append-only by design. To add a meeting:\n"
            f"  cp {PROJECTS_DIR / '_meeting-template.md'} {dest / 'meetings'}/"
            "$(date +%Y-%m-%d)-<slug>.md",
            file=sys.stderr,
        )
        return 1

    settings = config.load()
    render_vars = {
        "project_name": name,
        "project_title": (args.title or "").strip() or title_from_slug(name),
        "today": _time.local_date(_time.now_utc(), settings.timezone),
        "company_display_name": settings.company_display_name or settings.company_name,
        "email_address": settings.email_address,
        "accounts_default": settings.accounts_default,
        # The mailbox that actually owns business relationships. On most clones
        # that is the founder inbox, not the autonomous operator's default.
        "owner_account": settings.founder_sweep_account or settings.email_address,
    }

    written = render_scaffold(dest, render_vars)
    for path in written:
        print(f"  + {path}")
    print(
        f"\n{dest} is ready. Fill the abstract in README.md and the state in "
        f"status.md — the placeholders are HTML comments saying what belongs "
        f"where.\nA meeting note starts from "
        f"{PROJECTS_DIR / '_meeting-template.md'}; add a line for it in "
        f"timeline.md so it can be found from the chronology.\n"
        f"Conventions: {PROJECTS_DIR / 'README.md'}"
    )
    return 0
