"""Owner-private problem projection and retained technical-notice evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

from .monitor_store import MonitorStore
from .observability_store import _check


def _atomic(path: Path, value: dict) -> None:
    _check(path.parent, directory=True)
    if path.exists() or path.is_symlink():
        _check(path)
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    if len(raw) > 262144:
        raise ValueError("Problem file size limit")
    fd, name = tempfile.mkstemp(prefix=".problem-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def publish(store: MonitorStore, *, clone_label: str = "", now: float | None = None) -> dict:
    """Project bounded safe incidents; manually written investigations stay separate."""
    label = clone_label or "selected-runtime"
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label):
        raise ValueError("Invalid diagnostic clone label")
    investigations = store.root / "investigations"
    investigations.mkdir(mode=0o700, exist_ok=True)
    _check(investigations, directory=True)
    rows = store.incidents(active_only=True)
    problems = []
    for row in rows:
        detail = row["detail"]
        findings = investigations / (row["id"] + ".md")
        retained = findings.exists() or findings.is_symlink()
        if retained:
            _check(findings)
        item = {
            "id": row["id"], "clone": label, "component": row["component"],
            "first_observed": row["first"], "last_observed": row["last"],
            "severity": detail.get("level", "ERROR"), "symptom": row["cause"],
            "stage": detail.get("stage", "monitor"), "reason": detail.get("reason", "unknown"),
            "revision": row["revision"], "evidence": detail,
            "investigation_status": "findings-retained" if retained else "open",
            "investigation_path": str(findings),
            "next_step": "Read matching cs logs trace and retained evidence; preserve uncertain effects",
        }
        if row["component"] == "operator-notices":
            retained_notice = store.root / "notice-evidence" / (row["id"] + ".json")
            item["restricted_evidence_path"] = str(retained_notice)
            item["restricted_evidence_available"] = retained_notice.is_file() and not retained_notice.is_symlink()
        if len(json.dumps(problems + [item]).encode()) > 220000:
            continue
        else:
            problems.append(item)
    total = store.counts()["active"]
    result = {
        "schema_version": 1, "owner_uid": store.owner_uid, "clone": label,
        "generated_at": time.time() if now is None else now,
        "problem_count": total, "problems": problems,
        "remaining_count": total - len(problems),
        "retrieval": "cs monitor events --config <private-config> --offset 0; follow next_incident_offset",
        "incident_index_offset": 0,
        "investigations_path": str(investigations),
    }
    _atomic(store.root / "problems.json", result)
    return {"path": str(store.root / "problems.json"), "problem_count": total}


def location(settings) -> tuple[Path, str, str]:
    """Resolve the selected deployment without borrowing another owner's inbox."""
    from .monitor_config import load
    from .observability import owner_root

    owner = str(settings.engine_owner_uid or "").strip()
    if not owner:
        raise ValueError("Selected owner required for technical evidence")
    binding = getattr(settings, "observability", None)
    configured = getattr(binding, "monitor_config_path", "")
    deployment = Path(settings.state_dir) / "observability" / "deployment" / "monitor.json"
    legacy = Path(settings.state_dir) / "observability" / "monitor-config.json"
    target = Path(configured) if configured else deployment if deployment.exists() or deployment.is_symlink() else legacy
    label = (str(getattr(settings, "slug", "")) + "-cs").lstrip("-") or "selected-runtime"
    if any(parent.is_symlink() for parent in (target, *target.parents)):
        raise PermissionError("Unsafe technical evidence configuration")
    if target.exists():
        deployment = load(target)
        if deployment.owner_uid != owner:
            raise ValueError("Technical evidence owner mismatch")
        return Path(deployment.state_dir), owner, deployment.clone_label or label
    if configured:
        raise ValueError("Configured technical evidence unavailable")
    return owner_root(settings.state_dir, owner) / "monitor", owner, label


def record_notice(settings, notice: dict) -> str:
    """Retain a queued technical notice before its original queue may be removed."""
    root, owner, label = location(settings)
    raw = json.dumps(notice, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > 65536:
        raise ValueError("Technical evidence limit")
    identity = hashlib.sha256(raw).hexdigest()
    if any(parent.is_symlink() for parent in (root, *root.parents)):
        raise PermissionError("Unsafe technical evidence root")
    missing = []
    current = root
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
    store = MonitorStore(root, owner)
    evidence = root / "notice-evidence"
    evidence.mkdir(mode=0o700, exist_ok=True)
    _check(evidence, directory=True)
    entries = list(evidence.iterdir())
    if len(entries) > 4096:
        raise ValueError("Technical evidence capacity exhausted")
    size = 0
    retained_count = 0
    for entry in entries:
        _check(entry)
        if not re.fullmatch(r"[a-f0-9]{64}\.json", entry.name):
            raise ValueError("Unexpected technical evidence file")
        if entry.stat().st_mtime < time.time() - 30 * 86400:
            entry.unlink()
            continue
        retained_count += 1
        size += entry.stat().st_size
    target = evidence / (identity + ".json")
    if (retained_count >= 4096 or size + len(raw) > 64 * 1024**2) and not target.exists():
        raise ValueError("Technical evidence capacity exhausted")
    _atomic(target, notice)
    from .observability import REASONS
    reason = notice.get("reason")
    reason = reason if isinstance(reason, str) and reason in REASONS else "unknown"
    status = notice.get("status")
    level = "INFO" if status == "primary" else "WARNING" if status == "fallback" else "ERROR"
    active = int(status != "primary")
    detail = {"stage": "alert", "reason": reason, "level": level}
    causal = notice.get('causal')
    if causal is not None:
        from .observability_causal import validate
        detail['causal'] = validate(causal)
    now = time.time()
    with store.connect() as db:
        db.execute(
            "INSERT INTO incidents(id,component,cause,first,last,active,revision,detail) "
            "VALUES (?, 'operator-notices', 'operation-failure', ?, ?, ?, 1, ?) "
            "ON CONFLICT(id) DO UPDATE SET last=excluded.last,active=excluded.active",
            (identity, now, now, active, json.dumps(detail)),
        )
    publish(store, clone_label=label, now=now)
    return identity
