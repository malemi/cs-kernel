#!/usr/bin/env python3
"""`cs project new` — the per-project memory scaffold, against a REAL subprocess
in a sandbox clone (trial manifest, no value from any real clone):

  - stamps index + status + timeline + meetings/, every file front-matter'd
    and abstract-first (the shape the docs/ harness relies on)
  - every template variable renders; an unrendered `{{ … }}` reaching a clone
    is a silent template bug that only shows up in someone's dossier
  - the date comes from the manifest timezone, not UTC
  - `meetings/` survives a commit (a .gitkeep, or the append-only half of the
    scaffold vanishes from git)
  - REFUSES an existing folder without touching it — a project's memory is
    append-only, and clobbering it destroys the only copy of a judgment
  - refuses a non-slug name, and refuses to run outside a clone root
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = "Europe/Madrid"

MANIFEST = f"""\
[company]
name = "Acme"
display_name = "Acme Group"
from_name = "Acme Ops"
slug = "acme"
prog_name = "acme-cs"

[operator]
email_address = "ops@acme.example"

[engine]
owner_uid = "uid-ops-acme"
ws_url = "wss://engine.example"

[engine.accounts]
default = "ops"
ops = "uid-ops-acme"

[crm]
adapter = "none"

[producer]
adapter = "none"

[knobs]
timezone = "{TZ}"

[repo]
kernel_version = "v0.1.0"
"""


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN")}
    env["HOME"] = str(home)
    return env


def _run(repo: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "cs", *args], cwd=repo, env=env,
                          capture_output=True, text=True)


def _digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        repo = Path(td, "repo"); repo.mkdir()
        (repo / "manifest.toml").write_text(MANIFEST)
        env = _clean_env(home)

        # ---- 1. the happy path -------------------------------------------
        proc = _run(repo, env, "project", "new", "acme-corp",
                    "--title", "Acme Corp S.p.A.")
        assert proc.returncode == 0, f"project new failed:\n{proc.stderr}"

        dest = repo / "docs" / "projects" / "acme-corp"
        expected = ["README.md", "status.md", "timeline.md", "meetings/.gitkeep"]
        for rel in expected:
            assert (dest / rel).exists(), f"missing from the scaffold: {rel}"

        # ---- 2. abstract-first, front-matter'd ---------------------------
        for rel in ("README.md", "status.md", "timeline.md"):
            text = (dest / rel).read_text()
            assert text.startswith("---\n"), f"{rel}: no front matter"
            assert "\n---\n" in text, f"{rel}: front matter not closed"
            assert "## Abstract" in text, f"{rel}: no abstract — the harness reads it first"
            assert "project: acme-corp" in text, f"{rel}: project slug not stamped"

        # ---- 3. every variable rendered ----------------------------------
        # StrictUndefined catches a MISSING var at render time; a var that is
        # defined but never referenced, or a typo'd `{{` in prose, survives to
        # the clone. Assert no Jinja syntax reaches the stamped files.
        for path in sorted(dest.rglob("*")):
            if not path.is_file():
                continue
            body = path.read_text(errors="replace")
            for token in ("{{", "{%"):
                assert token not in body, f"{path.name}: unrendered template syntax {token}"

        readme = (dest / "README.md").read_text()
        assert "Acme Corp S.p.A." in readme, "--title not honoured"
        # A title ending in a period must not produce "S.p.A.." — the template
        # never puts {{ project_title }} at the end of a sentence.
        assert "S.p.A.." not in readme, "title concatenated into a double period"
        # The mailbox that owns relationships: founder sweep is off in this
        # manifest, so it must fall back to the operator address.
        assert "ops@acme.example" in readme, "owner account not resolved"

        # ---- 4. the date is market-local, not UTC ------------------------
        today_local = datetime.now(timezone.utc).astimezone(ZoneInfo(TZ)).strftime("%Y-%m-%d")
        assert f"created: {today_local}" in readme, (
            f"date not taken from the manifest timezone ({TZ}): "
            f"expected {today_local}"
        )

        # ---- 4b. with the founder sweep on, THAT mailbox owns the project --
        # The branch that matters on a real clone: business relationships live
        # on the founder inbox, not on the autonomous operator's default. Wrong
        # mailbox here sends the next session looking in an empty archive.
        repo2 = Path(td, "repo2"); repo2.mkdir()
        (repo2 / "manifest.toml").write_text(
            MANIFEST + '\n[engine.founder_sweep]\nenabled = true\n'
            'account = "founder@acme.example"\n'
        )
        proc = _run(repo2, env, "project", "new", "acme-corp")
        assert proc.returncode == 0, f"founder-sweep clone failed:\n{proc.stderr}"
        readme2 = (repo2 / "docs/projects/acme-corp/README.md").read_text()
        assert "founder@acme.example" in readme2, \
            "founder-sweep account must own the project when the sweep is on"

        # ---- 5. an existing folder is refused, and left alone ------------
        before = _digest(dest)
        (dest / "meetings" / "2026-01-31-kickoff.md").write_text("hand-written note\n")
        before[str(Path("meetings") / "2026-01-31-kickoff.md")] = hashlib.sha256(
            b"hand-written note\n"
        ).hexdigest()

        proc = _run(repo, env, "project", "new", "acme-corp")
        assert proc.returncode != 0, "an existing project folder must be refused"
        assert "already exists" in (proc.stderr + proc.stdout)
        assert _digest(dest) == before, "refusal still modified the project folder"

        # ---- 6. a name that is not a slug is refused --------------------
        for bad in ("Acme Corp", "ops@acme.example", "acme_corp", "-acme", "ACME"):
            proc = _run(repo, env, "project", "new", bad)
            assert proc.returncode != 0, f"non-slug name accepted: {bad!r}"

        # ---- 7. outside a clone root: refused, nothing created ----------
        loose = Path(td, "loose"); loose.mkdir()
        proc = _run(loose, env, "project", "new", "acme-corp")
        assert proc.returncode != 0, "must refuse to stamp outside a clone root"
        assert "manifest.toml" in (proc.stderr + proc.stdout)
        assert not (loose / "docs").exists(), "created docs/ outside a clone"

    print("test_project_memory: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
