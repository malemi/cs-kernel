"""cs cron — manage the user crontab entry for the operator tick.

Reads [cron].schedule and [cron].comment from manifest.toml (the raw file —
[cron] is template-only, not in the runtime Settings model), builds a crontab
line pointing at bin/cs_operator_cron.sh (absolute path), and installs/removes
it idempotently using a tag comment.

The crontab line looks like:
    <schedule>  /abs/path/bin/cs_operator_cron.sh >> ~/.<slug>-cs/cs_operator.log 2>&1  # cs-cron:<slug>

The tag `# cs-cron:<slug>` lets us find/replace/remove it safely.
"""

import re
import subprocess
import tomllib
from datetime import datetime, timezone
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


#: Fallback interval when the schedule's hour field declares no step. A daily
#: entry is the widest thing a `<company>-cs` crontab reasonably says, so a
#: schedule this cannot read is judged against a day rather than called stale.
DEFAULT_INTERVAL_HOURS = 24

#: How many missed runs before the tick is reported as not ticking. One skipped
#: run is a machine that was asleep; two is a failure to report.
STALE_FACTOR = 2

#: Timestamp shape the wrapper writes at the head of every log line
#: (`date -u +%FT%TZ` in `bin/cs_operator_cron.sh`).
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z")


def _interval_hours(schedule: str) -> int:
    """Hours between two scheduled runs, read off the crontab HOUR field.

    Handles the two shapes a `<company>-cs` schedule takes — `*/N` and a range
    with a step, `6-18/2` — and falls back to a day for anything else. This is
    deliberately not a cron parser: the only question asked of it is "roughly
    how long before the next run", and a wrong answer in the safe direction
    (too long) reports a stale tick late rather than crying wolf.
    """
    fields = (schedule or "").split()
    if len(fields) < 2:
        return DEFAULT_INTERVAL_HOURS
    hour = fields[1]
    if "/" in hour:
        try:
            step = int(hour.rsplit("/", 1)[1])
        except ValueError:
            return DEFAULT_INTERVAL_HOURS
        return step if step > 0 else DEFAULT_INTERVAL_HOURS
    if hour == "*":
        return 1
    return DEFAULT_INTERVAL_HOURS


def _last_tick(log_path) -> tuple[str | None, str | None]:
    """`(ISO timestamp, what that run did)` of the newest line in the tick log.

    The second value is the fact the greeting has already been misread without:
    a bare timestamp reads as "the run did its work then", which is false when
    the run skipped. `ran` / `skipped`, or None when the log says neither.
    """
    try:
        lines = log_path.read_text(errors="replace").splitlines()
    except OSError:
        return None, None
    for line in reversed(lines):
        m = _TS.match(line.strip())
        if not m:
            continue
        action = "skipped" if "skip" in line.lower() else "ran"
        return f"{m.group(1)}Z", action
    return None, None


def cron_state(settings, clone_root=None) -> dict:
    """The three facts about the unattended operator, as data.

    `installed` (is there a crontab entry at all), `paused` (the kill-switch
    file) and `last_tick_at` are INDEPENDENT, and their remedies differ, which
    is why they are three fields and not one status word:

    - **absent** — nothing will run until `/cs-cron` installs it;
    - **paused** — the operator's standing decision. Neutral state, never a
      fault, and nothing in this kernel offers to lift it;
    - **stale** — installed, not paused, and the newest log line is older than
      the schedule implies. A failure to report.

    `state` is the strongest of those that holds, so a caller that wants one
    word has one; the booleans stay so a caller that needs the combination is
    not forced to re-derive it.
    """
    slug = settings.slug
    schedule, comment = "", ""
    try:
        root = Path(clone_root) if clone_root else _clone_root()
        schedule, comment = _read_raw_cron(root / "manifest.toml")
    except (OSError, ValueError, RuntimeError):
        pass

    lines = [line for line in _read_crontab() if f"# cs-cron:{slug}" in line]
    installed = bool(lines)
    paused = settings.pause_path.exists()
    last_tick_at, last_tick_action = _last_tick(settings.log_path)
    interval = _interval_hours(schedule)

    stale = False
    if installed and not paused:
        if last_tick_at is None:
            stale = True
        else:
            try:
                when = datetime.fromisoformat(last_tick_at.replace("Z", "+00:00"))
                age_h = (datetime.now(timezone.utc) - when).total_seconds() / 3600
                stale = age_h > STALE_FACTOR * interval
            except ValueError:
                stale = False

    state = ("absent" if not installed
             else "paused" if paused
             else "stale" if stale
             else "ticking")
    return {
        "installed": installed,
        "crontab_lines": lines,
        "paused": paused,
        "pause_path": str(settings.pause_path),
        "schedule": schedule,
        "comment": comment,
        "interval_hours": interval,
        "last_tick_at": last_tick_at,
        "last_tick_action": last_tick_action,
        "stale": stale,
        "state": state,
    }


def cmd_cron_status(args) -> int:
    """Show if the cron entry is installed, the manifest intent, whether the
    CS_PAUSE kill-switch is active, and when the last run actually happened.

    Those signals are independent: an installed crontab entry sends nothing
    while CS_PAUSE is present, CS_PAUSE alone says nothing about whether cron
    is even installed, and an entry that exists while the log has gone quiet is
    a third state again. `--json` is the machine-readable shape `/cs-review`
    reads, so the greeting states the same facts this verb prints instead of
    inferring them from a log tail."""
    import json

    from . import config
    settings = config.load()
    st = cron_state(settings)

    if getattr(args, "json", False):
        print(json.dumps(st, ensure_ascii=False, indent=2, default=str))
        return 0

    if st["installed"]:
        print("Crontab: installed")
        for line in st["crontab_lines"]:
            print(f"  {line}")
    else:
        print("Crontab: not installed. Run: cs cron install")

    if st["paused"]:
        print(f"Pause: active ({st['pause_path']} exists — operator will not "
              f"send). Run: rm {st['pause_path']} to resume")
    else:
        print(f"Pause: not active ({st['pause_path']} absent)")

    if st["last_tick_at"]:
        print(f"Last run: {st['last_tick_at']} — {st['last_tick_action']}")
    else:
        print("Last run: no entry in the tick log yet")
    if st["stale"]:
        print(f"State: installed but not ticking — nothing newer than "
              f"{st['interval_hours']}h x {STALE_FACTOR} in the log")

    print(f"Manifest schedule: {st['schedule']} ({st['comment']})")
    return 0