#!/usr/bin/env python3
"""A rendered `bin/` shell script must be EXECUTABLE, or cron fails silently.

`cs/project_init.py::render_templates` used to write every rendered/copied
file with a bare `write_text`/`write_bytes` and never chmod anything. A
stamped clone's `bin/cs_operator_cron.sh` therefore came out mode 0644; the
crontab line the docs tell the operator to install then failed with
"Permission denied" and NO other symptom — cron does not mail a traceback
for a non-executable script, it just silently does not run. The operator's
only signal was "the product does nothing".

Guards:
  (i)  `cs init`'s `render_templates`, run against the real template tree
       into a scratch directory, produces a `bin/cs_operator_cron.sh` whose
       mode bits are 0755 — not merely a file that exists.
  (ii) `cs update`'s write path restores the same executable bit on an
       EXISTING clone whose `bin/cs_operator_cron.sh` had regressed to 0644
       (e.g. copied by a tool that does not preserve mode bits) — an
       operator re-running `cs update` must not stay stuck non-executable.
  (iii) a file NOT under `bin/` and not a `.sh.j2` source (`.gitignore`, an
       ordinary `.md`) stays at the default non-executable mode — the fix
       must not blanket-chmod the whole tree.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from cs import project_init

# The same full variable set tests/test_template_render.py uses — the whole
# template tree renders under StrictUndefined, so every var any template
# references must be present, not just the ones bin/cs_operator_cron.sh.j2
# itself needs.
BASE = dict(
    company_name="Acme Corp", company_display_name="Acme", company_from_name="Acme Support",
    company_slug="acme", company_prog_name="acme-cs",
    email_address="support@acme.example", engine_owner_uid="UID123",
    engine_ws_url="wss://engines.example.com",
    platform_env_path="", producer_adapter="none", producer_mrcall_tracking=False,
    crm_adapter="none", crm_shopify=False, drive_scope="",
    cs_triage_mode="draft", dedup_days="30", reminder_max="2",
    system_senders="", send_guard_min_chars=40, send_guard_banned_phrases="",
    sms_enabled=False, sms_hour="18", sms_proxy_base="",
    smtp_host="smtp.example.com", smtp_port="587",
    imap_host="imap.example.com", imap_port="993",
    timezone="Europe/Rome",
    cron_comment="acme-cs", cron_schedule="0 8 * * *",
    firebase_sa_path="~/.acme-cs/firebase-sa.json",
    founder_sweep_enabled=False, founder_sweep_account="",
    excluded_campaign="", repo_docs_shape="generic",
    repo_git_remote="git@example.com:acme/acme-cs.git", repo_kernel_version="v0.6.1",
    name="Acme",
    accounts={"support": "UID123"}, accounts_default="support",
    operator_voice=project_init.DEFAULT_OPERATOR_VOICE,
)

TEMPLATE_ROOT = Path(project_init.__file__).parent / "templates" / "project"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _test_cs_init_bin_is_executable() -> None:
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td, "acme-cs")
        config = {**BASE, "dest_dir": str(dest)}
        success, _checksums = project_init.render_templates(config, TEMPLATE_ROOT, dest)
        assert success, "the full template tree must render cleanly with the full var set"

        cron = dest / "bin" / "cs_operator_cron.sh"
        assert cron.exists(), f"expected {cron} to exist after render_templates"
        mode = _mode(cron)
        assert mode & 0o111, (
            f"bin/cs_operator_cron.sh must be executable after `cs init`, got mode "
            f"{oct(mode)} — a 0644 cron wrapper fails SILENTLY in cron"
        )
        assert mode == 0o755, f"expected mode 0755, got {oct(mode)}"

        # A file outside bin/ and not a *.sh.j2 source must NOT be chmod'd —
        # the fix targets shell-script targets only, not the whole tree.
        gitignore = dest / ".gitignore"
        assert gitignore.exists(), f"expected {gitignore} to exist"
        assert not (_mode(gitignore) & 0o111), (
            f".gitignore must stay non-executable, got mode {oct(_mode(gitignore))} — "
            "the fix must not blanket-chmod every rendered file"
        )


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN")}
    env["HOME"] = str(home)
    return env


def _test_cs_update_restores_executable_bit() -> None:
    """An EXISTING clone whose `bin/cs_operator_cron.sh` regressed to 0644
    (e.g. checked out by a tool that drops the exec bit) must come back
    executable after `cs update` re-renders it — the operator should never
    have to `chmod` it by hand."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        (clone / "bin").mkdir()
        cron = clone / "bin" / "cs_operator_cron.sh"
        cron.write_text("#!/usr/bin/env bash\n# stale, pre-fix render\necho legacy\n")
        cron.chmod(0o644)
        assert not (_mode(cron) & 0o111), "fixture must start non-executable"

        # A bogus stored checksum forces cmd_update to see "template changed"
        # for this file, same technique tests/test_project_update.py uses.
        # bin/cs_operator_cron.sh is in project_update.SECURITY_CRITICAL, so
        # this also exercises the never-ask, always-apply branch.
        manifest = {
            "template_version": "1",
            "init_data": {
                "company_slug": "acme",
                "company_name": "Acme Corp",
                "company_prog_name": "acme-cs",
                "email_address": "support@acme.example",
            },
            "file_checksums": {"bin/cs_operator_cron.sh": "sha256:" + "0" * 64},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, f"`cs update` must exit 0, got {proc.returncode}:\n{out}"

        mode = _mode(cron)
        assert mode & 0o111, (
            f"cs update must restore the executable bit on bin/cs_operator_cron.sh, "
            f"got mode {oct(mode)}:\n{out}"
        )


def main() -> int:
    _test_cs_init_bin_is_executable()
    _test_cs_update_restores_executable_bit()
    print("test_render_permissions: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
