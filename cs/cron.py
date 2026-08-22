"""cs cron — manage the user crontab entry for the operator tick.

Reads [cron].schedule and [cron].comment from manifest.toml (the raw file —
[cron] is template-only, not in the runtime Settings model), builds a crontab
line pointing at bin/cs_operator_cron.sh (absolute path), and installs/removes
it idempotently using a tag comment.

The crontab line looks like:
    <schedule>  /abs/path/bin/cs_operator_cron.sh >> ~/.<slug>-cs/cs_operator.log 2>&1  # cs-cron:<slug>

The tag `# cs-cron:<slug>` lets us find/replace/remove it safely.
"""

import subprocess
import tomllib
from pathlib import Path


def _read_raw_cron(manifest_path: Path) -> tuple[str, str]:
    """Read [cron] table from raw manifest.toml."""
    with open(manifest_path, "rb") as fh:
        data = tomllib.load(fh)
    cron_table = data.get("cron", {})
    schedule = cron_table.get("schedule", "").strip()
    comment = cron_table.get("comment", "").strip()
    if not schedule:
        raise ValueError(f"[cron].schedule is missing or empty in {manifest_path}")
    return schedule, comment


def _clone_root() -> Path:
    """Find the clone root (directory containing manifest.toml)."""
    from . import manifest as manifest_mod
    path = manifest_mod.find_manifest_path()
    if path is None:
        raise RuntimeError("manifest.toml not found")
    return path.parent


def _crontab_line(clone_root: Path, slug: str, schedule: str, comment: str) -> str:
    """Build the crontab line."""
    script_path = (clone_root / "bin" / "cs_operator_cron.sh").resolve()
    log_path = f"~/.{slug}-cs/cs_operator.log"
    tag = f"# cs-cron:{slug}"
    return f"{schedule}  {script_path} >> {log_path} 2>&1  {tag}"


def _read_crontab() -> list[str]:
    """Read the current crontab entries."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result.stdout.splitlines()
        return []
    except Exception:
        return []


def _write_crontab(lines: list[str]) -> None:
    """Write lines to crontab."""
    p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    p.communicate(input="\n".join(lines) + "\n")
    if p.returncode != 0:
        raise RuntimeError("Failed to write crontab")


def cmd_cron_install(args) -> int:
    """Install or update the crontab entry."""
    from . import config
    clone_root = _clone_root()
    slug = config.load().slug
    schedule, comment = _read_raw_cron(clone_root / "manifest.toml")
    line = _crontab_line(clone_root, slug, schedule, comment)
    
    existing = _read_crontab()
    # Remove any existing line with our tag
    filtered = [l for l in existing if f"# cs-cron:{slug}" not in l]
    filtered.append(line)
    
    _write_crontab(filtered)
    
    print(f"Installed cron entry:\n  {line}")
    print(f"Log: ~/.{slug}-cs/cs_operator.log")
    print(f"Pause: touch ~/.{slug}-cs/CS_PAUSE")
    return 0


def cmd_cron_uninstall(args) -> int:
    """Remove the crontab entry."""
    from . import config
    slug = config.load().slug
    existing = _read_crontab()
    filtered = [l for l in existing if f"# cs-cron:{slug}" not in l]
    
    if len(existing) != len(filtered):
        _write_crontab(filtered)
        print(f"Removed cron entry for {slug}-cs")
    else:
        print(f"No cron entry found for {slug}-cs")
    return 0


def cmd_cron_status(args) -> int:
    """Show if the cron entry is installed, the manifest intent, and whether
    the CS_PAUSE kill-switch is active. Both signals matter and are
    independent: an installed crontab entry sends nothing while CS_PAUSE is
    present, and CS_PAUSE alone says nothing about whether cron is even
    installed."""
    from . import config
    settings = config.load()
    slug = settings.slug
    schedule, comment = _read_raw_cron(_clone_root() / "manifest.toml")

    existing = _read_crontab()
    installed = [l for l in existing if f"# cs-cron:{slug}" in l]

    if installed:
        print("Crontab: installed")
        for line in installed:
            print(f"  {line}")
    else:
        print("Crontab: not installed. Run: cs cron install")

    paused = settings.pause_path.exists()
    if paused:
        print(f"Pause: active ({settings.pause_path} exists — operator will not send). Run: rm {settings.pause_path} to resume")
    else:
        print(f"Pause: not active ({settings.pause_path} absent)")

    print(f"Manifest schedule: {schedule} ({comment})")
    return 0