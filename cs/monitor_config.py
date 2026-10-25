"""Strict deployment inventory for evidence-only monitoring; no business settings."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class Endpoint(Strict):
    url: str
    token_env: str

    @field_validator("url")
    @classmethod
    def https(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or len(value) > 2048
        ):
            raise ValueError("HTTPS endpoint without embedded credentials required")
        return value.rstrip("/")

    @field_validator("token_env")
    @classmethod
    def reference(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,95}", value):
            raise ValueError("environment credential reference required")
        return value

    def token(self) -> str:
        value = os.environ.get(self.token_env, "")
        if not 32 <= len(value) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("monitor credential unavailable")
        return value


class Schedule(Strict):
    """Explicit expected cadence; cron expressions can additionally restrict windows."""

    every_seconds: int = Field(ge=60, le=31 * 86400)
    anchor_utc: int = Field(ge=0)
    grace_seconds: int = Field(default=230, ge=0, le=300)
    disabled: bool = False
    pause_marker: str = ""
    cron: str = ""
    timezone: str = "UTC"

    @field_validator("cron")
    @classmethod
    def expression(cls, value: str) -> str:
        if value and (
            len(value) > 128
            or len(value.split()) != 5
            or re.fullmatch(r"[0-9*/ ,\-]+", value) is None
        ):
            raise ValueError("five-field numeric cron expression required")
        return value

    @model_validator(mode="after")
    def valid_fields(self):
        from zoneinfo import ZoneInfo

        ZoneInfo(self.timezone)
        if self.pause_marker and not Path(self.pause_marker).is_absolute():
            raise ValueError("absolute pause marker required")
        if self.cron:
            from .monitor_evaluate import _field

            for text, low, high in zip(self.cron.split(), (0, 0, 1, 1, 0), (59, 23, 31, 12, 7)):
                _field(text, low, low, high)
        return self


class Component(Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    kind: str = Field(pattern=r"^(kernel|engine)$")
    local_root: str = ""
    legacy_state_dir: str = ""
    reader: Endpoint | None = None
    schedule: Schedule | None = None
    stage_deadline_seconds: int = Field(default=1800, ge=1, le=10800)
    work_deadline_seconds: int = Field(default=1800, ge=1, le=31 * 86400)
    freshness_seconds: int = Field(default=3600, ge=60, le=31 * 86400)

    @model_validator(mode="after")
    def route(self):
        if bool(self.local_root) == bool(self.reader):
            raise ValueError("exactly one local root or authenticated reader required")
        if self.local_root and not Path(self.local_root).is_absolute():
            raise ValueError("absolute diagnostic root required")
        if self.reader and self.kind != "engine":
            raise ValueError("reader currently supports engine diagnostics only")
        if self.legacy_state_dir and (
            self.kind != "kernel" or not Path(self.legacy_state_dir).is_absolute()
        ):
            raise ValueError("legacy state must bind the selected kernel diagnostic root")
        return self


class MonitorConfig(Strict):
    schema_version: int = Field(default=1, ge=1, le=1)
    monitor_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner_uid: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    state_dir: str
    components: list[Component] = Field(min_length=1, max_length=32)
    alert: Endpoint | None = None
    watchdog: Endpoint | None = None
    mode: str = Field(default="transport", pattern=r"^(transport|filesystem)$")
    clone_label: str = Field(default="", pattern=r"^[A-Za-z0-9_.-]{0,80}$")
    scan_seconds: int = Field(default=60, ge=1, le=600)
    expected_start_utc: int = Field(ge=0)

    @model_validator(mode="after")
    def unique(self):
        if self.mode == "transport" and self.scan_seconds > 60:
            raise ValueError("transport monitoring requires at most sixty-second scans")
        if not Path(self.state_dir).is_absolute():
            raise ValueError("absolute monitor state directory required")
        if len({c.id for c in self.components}) != len(self.components):
            raise ValueError("duplicate component identity")
        if any(c.id == "observer" for c in self.components):
            raise ValueError("observer is a reserved component identity")
        from .observability import owner_root

        for component in self.components:
            if component.legacy_state_dir and Path(component.local_root) != owner_root(
                component.legacy_state_dir, self.owner_uid
            ):
                raise ValueError("legacy state must bind the selected owner's kernel namespace")
        routes = [(c.local_root, c.reader.url if c.reader else "") for c in self.components]
        if len(set(routes)) != len(routes):
            raise ValueError("duplicate component route")
        if self.watchdog and not re.fullmatch(
            r"/(?:[A-Za-z0-9_-]{1,64}/)*heartbeat", urlsplit(self.watchdog.url).path
        ):
            raise ValueError("watchdog endpoint must end in a fixed /heartbeat route")
        return self


class WatchdogConfig(Strict):
    schema_version: int = Field(default=1, ge=1, le=1)
    monitor_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner_uid: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    state_dir: str
    token_env: str = Field(pattern=r"^[A-Z_][A-Z0-9_]{0,95}$")
    expected_start_utc: int = Field(ge=0)
    grace_seconds: int = Field(default=300, ge=1, le=300)
    daily_alert_limit: int = Field(default=3, ge=1, le=6)
    alert: Endpoint
    port: int = Field(default=8127, ge=0, le=65535)

    @field_validator("state_dir")
    @classmethod
    def absolute(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("absolute watchdog state directory required")
        return value


def load(path: str | Path, *, watchdog: bool = False):
    """Read bounded private deployment configuration without echoing inputs."""
    from .observability_store import _check, _open

    try:
        target = Path(path).absolute()
        _check(target)
        fd = _open(target, os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("configuration limit")
        return (WatchdogConfig if watchdog else MonitorConfig).model_validate(json.loads(raw))
    except Exception:
        raise ValueError("Invalid or inaccessible private monitoring configuration") from None
