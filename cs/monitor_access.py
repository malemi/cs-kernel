"""Discover the independent monitor from cs logs without mutating observer state."""

from __future__ import annotations

from pathlib import Path


def read(settings, view="locations", *, trace_id=None, limit=100) -> dict:
    from .monitor_config import load
    from .monitor_store import snapshot

    path = Path(
        getattr(getattr(settings, "observability", None), "monitor_config_path", "")
        or settings.state_dir / "observability" / "monitor-config.json"
    )
    if not path.is_file():
        return {
            "status": "not-configured",
            "config_path": str(path),
            "independent_monitoring": False,
        }
    try:
        config = load(path)
        if config.owner_uid != settings.engine_owner_uid:
            raise ValueError("Monitoring owner mismatch")
        result = snapshot(config.state_dir, config.owner_uid, limit=limit, trace_id=trace_id)
        if view not in {"events", "recent", "trace"}:
            result.pop("events", None)
        result["config_path"] = str(path)
        result["watchdog_configured"] = config.watchdog is not None
        result["independent_host_verified"] = False
        if config.watchdog:
            result["watchdog_route"] = config.watchdog.url
            try:
                from .monitor_transport import get
                from .observability import diagnostic_id
                from .observability_store import _validate_event
                from types import SimpleNamespace

                if view in {"events", "recent", "trace"}:
                    from .config import observability_credential

                    normalized = diagnostic_id(trace_id) if trace_id else None
                    remote = get(
                        config.watchdog, "events", {"limit": limit, "trace_id": normalized},
                        credential=observability_credential(
                            settings, credential_env=config.watchdog.token_env
                        ),
                    )
                    if (
                        set(remote)
                        - {
                            "schema_version",
                            "owner_uid",
                            "events",
                            "coverage",
                            "copy_truncated",
                            "copy_gap",
                        }
                        or remote.get("schema_version") != 1
                        or remote.get("owner_uid") != config.owner_uid
                        or remote.get("coverage") != "partial-off-host-copy"
                        or type(remote.get("copy_truncated")) is not bool
                        or type(remote.get("copy_gap")) is not bool
                        or not isinstance(remote.get("events"), list)
                        or len(remote["events"]) > min(200, limit)
                        or not all(
                            _validate_event(e, SimpleNamespace(owner_uid=config.owner_uid))
                            for e in remote["events"]
                        )
                    ):
                        raise ValueError("Invalid off-host copy")
                    result["off_host"] = remote
            except Exception:
                result["off_host"] = {"status": "unavailable", "coverage": "unverified"}
        return result
    except Exception:
        return {
            "status": "unavailable",
            "config_path": str(path),
            "independent_monitoring": "unverified",
        }
