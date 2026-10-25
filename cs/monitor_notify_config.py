"""Private fixed-owner delivery configuration; credentials are environment references."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import Field, model_validator

from .monitor_config import Strict
from .observability_store import _check, _open


class NotifyConfig(Strict):
    schema_version: int = Field(default=1, ge=1, le=1)
    backend: str = Field(pattern=r"^(smtp|ntfy)$")
    monitor_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner_uid: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    state_dir: str
    token_env: str = Field(pattern=r"^[A-Z_][A-Z0-9_]{0,95}$")
    topic_env: str = Field(default="", pattern=r"^([A-Z_][A-Z0-9_]{0,95})?$")
    signing_key_env: str = Field(default="", pattern=r"^([A-Z_][A-Z0-9_]{0,95})?$")
    port: int = Field(default=8130, ge=0, le=65535)
    daily_limit: int = Field(default=100, ge=1, le=100)

    @model_validator(mode="after")
    def bindings(self):
        if not Path(self.state_dir).is_absolute():
            raise ValueError("absolute private state path required")
        if self.backend == "ntfy" and not (self.topic_env and self.signing_key_env):
            raise ValueError("notification credential references required")
        return self

    def credential(self, name: str) -> str:
        value = os.environ.get(name, "")
        if not 32 <= len(value) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("Notification credential unavailable")
        return value


def load(path: str | Path) -> NotifyConfig:
    try:
        target = Path(path).absolute()
        _check(target)
        descriptor = _open(target, os.O_RDONLY)
        with os.fdopen(descriptor, "rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("configuration limit")
        return NotifyConfig.model_validate(json.loads(raw))
    except Exception:
        raise ValueError("Invalid private notification configuration") from None
