"""Unit gate: `toml_quote` (cs/project_init.py) — always a valid, single-line
TOML basic string, quotes included, safe as either a key or a value.

Written after the live 2026-08-21 incident: an unquoted bare TOML key
(`mario.alemi@mrcall.ai = "…"`) broke `manifest.toml` the moment `cs
update` re-rendered it — `@` is illegal in a bare key, and the account-name
shape the kernel's own docs recommend (the mailbox address) is exactly the
shape that breaks.
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cs.project_init import toml_quote  # noqa: E402


def _round_trips_as_key(name: str, expect: str) -> None:
    line = f"{toml_quote(name)} = 1\n"
    parsed = tomllib.loads(line)
    assert parsed == {expect: 1}, f"{name!r} -> {line!r} parsed as {parsed!r}, expected {{{expect!r}: 1}}"


def _round_trips_as_value(value: str) -> None:
    line = f"k = {toml_quote(value)}\n"
    parsed = tomllib.loads(line)
    assert parsed == {"k": value}, f"{value!r} -> {line!r} parsed as {parsed!r}"


def main() -> None:
    # The exact shape that broke live: an email as an account name/key.
    _round_trips_as_key("mario.alemi@mrcall.ai", "mario.alemi@mrcall.ai")
    _round_trips_as_key("jane.doe@acme.example", "jane.doe@acme.example")
    # Bare-safe names must still round-trip once quoted.
    _round_trips_as_key("support", "support")
    _round_trips_as_key("founder-sweep_1", "founder-sweep_1")
    # Characters that need escaping inside the basic string itself.
    _round_trips_as_key('has"quote', 'has"quote')
    _round_trips_as_key("has\\backslash", "has\\backslash")
    # Values (not just keys) go through the same filter in the template.
    _round_trips_as_value("wss://desktop.acme.example")
    _round_trips_as_value("<uid-placeholder>")
    _round_trips_as_value("")

    assert toml_quote("a\nb") == '"a\\nb"', toml_quote("a\nb")
    parsed = tomllib.loads(f"k = {toml_quote('a' + chr(10) + 'b')}\n")
    assert parsed == {"k": "a\nb"}, parsed

    print("test_toml_quote: all assertions passed")


if __name__ == "__main__":
    main()
