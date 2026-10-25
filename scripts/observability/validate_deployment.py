"""Validate private candidate inputs offline; this does not verify host independence."""

from __future__ import annotations

import argparse
import json

from cs.monitor_config import load


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monitor", required=True)
    parser.add_argument("--watchdog", required=True)
    args = parser.parse_args()
    try:
        monitor, watchdog = load(args.monitor), load(args.watchdog, watchdog=True)
        if (
            monitor.owner_uid != watchdog.owner_uid
            or monitor.monitor_id != watchdog.monitor_id
            or "REPLACE" in monitor.owner_uid
            or not monitor.watchdog
            or not monitor.alert
            or monitor.expected_start_utc <= 0
            or watchdog.expected_start_utc <= 0
            or monitor.watchdog.token_env != watchdog.token_env
        ):
            raise ValueError("Unbound deployment inputs")
        for binding in (
            monitor.alert,
            monitor.watchdog,
            watchdog.alert,
            *[c.reader for c in monitor.components if c.reader],
        ):
            if ".example." in binding.url:
                raise ValueError("Example endpoint")
        if any(
            c.kind == "kernel" and not c.legacy_state_dir or c.kind == "engine" and not c.reader
            for c in monitor.components
        ):
            raise ValueError("Legacy retention and independent engine reader bindings required")
        print(
            json.dumps(
                {
                    "configuration": "valid",
                    "runtime_access": "unverified",
                    "host_independence": "unverified",
                    "actual_alert_receipt": "unverified",
                    "ordinary_mail_outcomes": "unverified",
                }
            )
        )
        return 0
    except Exception:
        print("Deployment inputs incomplete or inaccessible; no services changed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
