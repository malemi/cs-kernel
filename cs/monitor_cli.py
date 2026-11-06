"""Collect or inspect operational problems; acknowledgement is interactive."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cs monitor", description=__doc__)
    parser.add_argument("action", choices=("once", "run", "status", "events", "ack"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--incident")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--seconds", type=int, default=86400)
    args = parser.parse_args(argv)
    if args.action not in {"status", "events"} and any(
        os.environ.get(name) for name in ("CS_OPERATOR_HEADLESS", "CS_HEADLESS_SEND")
    ):
        print(
            "Monitoring changes and acknowledgements require an interactive operator",
            file=sys.stderr,
        )
        return 2
    from .monitor_config import load

    try:
        config = load(args.config)
        if args.action in {"status", "events"}:
            from .monitor_store import snapshot

            result = snapshot(config.state_dir, config.owner_uid, incident_id=args.incident,
                              incident_offset=args.offset)
            result["problems_path"] = str(Path(config.state_dir) / "problems.json")
            result["investigations_path"] = str(Path(config.state_dir) / "investigations")
            result["mode"] = config.mode
            if args.action == "status":
                result.pop("events", None)
        elif args.action == "ack":
            import time
            from .monitor_store import MonitorStore
            import re

            if not args.incident or not re.fullmatch(r"[a-f0-9]{64}", args.incident):
                raise ValueError("Exact incident ID required")
            result = {
                "acknowledged": MonitorStore(config.state_dir, config.owner_uid).ack(
                    args.incident, time.time(), args.seconds
                )
            }
        elif args.action == "once":
            from .monitor import scan

            result = scan(config)
        else:
            from .monitor import run

            run(config)
            return 0
        print(json.dumps(result, separators=(",", ":"), allow_nan=False))
        return 0 if result.get("status") not in {"degraded", "unavailable", "absent"} else 1
    except Exception:
        print(
            "Problem collection unavailable; inspect the selected configuration and storage",
            file=sys.stderr,
        )
        return 2


def add_subparsers(sub) -> None:
    parser = sub.add_parser("monitor", help="collect or inspect recorded operational problems")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    parser.set_defaults(func=lambda args: main(args.arguments))


if __name__ == "__main__":
    raise SystemExit(main())
