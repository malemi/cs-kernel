#!/usr/bin/env python3
"""Semantic guard for `cs memory` (`cs/memory_report.py`).

Guards:
  (i)   `build()` prints exactly the ten registry ids, in registry order,
        and `render()`'s text names every one of them.
  (ii)  No store's CONTENTS ever reach the report. A marker string is
        written into the file/dir backing every filesystem-resolved store
        (ledger, operator log, `company/`, dossiers, campaign packs,
        `template-manifest.json`) and must never appear in the rendered
        text or the `--json` payload — only the path and a presence verdict
        may.
  (iii) The engine row degrades HONESTLY, never a path: with no
        `engine_ws_url` configured it reports `unknown: engine_ws_url not
        configured` and an empty location; pointed at a closed local port
        (nothing listening — no real network egress) it reports
        `unreachable: …` with the resolved `wss://…/ws/<uid>` URL as its
        location, never a filesystem path; and a CONFIGURED but unparseable
        value (no scheme — the manifest does not validate the field's
        shape) reports the fourth, distinct verdict `unknown: engine_ws_url
        not parseable` — never the not-configured verdict — with the raw
        unparseable value never surfacing as a location either.
  (iv)  Filesystem-resolved stores report `present` once their backing
        file/dir exists and `absent` when it does not; `gmail-sent` always
        reports `declared` (mapped, never IMAP-probed) and `user-notes`
        always reports "not probed" (it would need an authenticated
        session, which this verb refuses to open).
  (v)   `cc-memory`'s own claimed encoding — both `/` and `.` in the clone
        root map to `-` — is exercised directly: a clone root whose own
        basename contains a `.` resolves to a directory whose encoded name
        carries the expected `-`-joined tail, not the literal dot.
"""
from __future__ import annotations

import os
import socket
import tempfile
from pathlib import Path

from cs import memory_report
from cs.config import Settings

MARKER = "SECRET-STORE-CONTENT-MUST-NEVER-BE-PRINTED"

EXPECTED_IDS = (
    "engine-memory",
    "user-notes",
    "gmail-sent",
    "ledger",
    "company-notes",
    "dossiers",
    "campaign-packs",
    "operator-log",
    "template-manifest",
    "cc-memory",
)


def _settings(**overrides) -> Settings:
    fields = {"slug": "acme", "email_address": "ops@acme.example"}
    fields.update(overrides)
    # _env_file=() disables the dotenv layer — the report must resolve from
    # the Settings object handed to it, not from whatever sits at the
    # invoking process's cwd (same reasoning as tests/test_login.py's
    # `_settings()`).
    return Settings(_env_file=(), **fields)


def _with_cwd_and_home(td: str):
    """A clone root (cwd) and a HOME, both fresh under one temp dir."""
    home = Path(td, "home"); home.mkdir()
    clone = Path(td, "clone"); clone.mkdir()
    return home, clone


def _test_ten_ids_in_order() -> None:
    with tempfile.TemporaryDirectory() as td:
        home, clone = _with_cwd_and_home(td)
        old_cwd = os.getcwd()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(home)
            os.chdir(clone)
            rep = memory_report.build(_settings())
        finally:
            os.chdir(old_cwd)
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

        ids = tuple(s["id"] for s in rep["stores"])
        assert ids == EXPECTED_IDS, ids

        text = memory_report.render(rep)
        for sid in EXPECTED_IDS:
            assert f"[{sid}]" in text, f"{sid!r} missing from rendered report:\n{text}"

    print("OK: build() emits exactly the ten registry ids in order; render() names every one")


def _test_no_store_contents_leak() -> None:
    with tempfile.TemporaryDirectory() as td:
        home, clone = _with_cwd_and_home(td)
        state_dir = home / ".acme-cs"; state_dir.mkdir()
        (state_dir / "cs.db").write_text(MARKER)
        (state_dir / "cs_operator.log").write_text(MARKER)
        (clone / "company").mkdir()
        (clone / "company" / "notes.md").write_text(MARKER)
        (clone / "docs" / "projects").mkdir(parents=True)
        (clone / "docs" / "projects" / "acme-corp.md").write_text(MARKER)
        (clone / "campaigns" / "winback").mkdir(parents=True)
        (clone / "campaigns" / "winback" / "mail_first.md").write_text(MARKER)
        (clone / "template-manifest.json").write_text(MARKER)

        old_cwd = os.getcwd()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(home)
            os.chdir(clone)
            rep = memory_report.build(_settings())
        finally:
            os.chdir(old_cwd)
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

        text = memory_report.render(rep)
        assert MARKER not in text, f"store contents leaked into render():\n{text}"

        import json
        blob = json.dumps(rep)
        assert MARKER not in blob, f"store contents leaked into --json:\n{blob}"

        # Presence must have flipped to "present" for every filesystem row
        # whose backing file/dir the fixture just created — proving the
        # absence of the marker is not just an absence of the FILE too.
        by_id = {s["id"]: s for s in rep["stores"]}
        for sid in ("ledger", "operator-log", "company-notes", "dossiers",
                    "campaign-packs", "template-manifest"):
            assert by_id[sid]["presence"] == "present", (sid, by_id[sid])

    print("OK: no store's file/dir contents reach render() or --json — path + "
          "presence only, even when every backing file/dir exists")


def _test_engine_row_unconfigured() -> None:
    with tempfile.TemporaryDirectory() as td:
        home, clone = _with_cwd_and_home(td)
        old_cwd = os.getcwd()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(home)
            os.chdir(clone)
            rep = memory_report.build(_settings(engine_ws_url=""))
        finally:
            os.chdir(old_cwd)
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

        row = next(s for s in rep["stores"] if s["id"] == "engine-memory")
        assert row["presence"] == "unknown: engine_ws_url not configured", row
        assert row["location"] == "", row

    print("OK: engine row with no ws_url configured — 'unknown', empty location, no path")


def _test_engine_row_unreachable() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    closed_port = s.getsockname()[1]
    s.close()
    closed_url = f"ws://127.0.0.1:{closed_port}"

    with tempfile.TemporaryDirectory() as td:
        home, clone = _with_cwd_and_home(td)
        old_cwd = os.getcwd()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(home)
            os.chdir(clone)
            rep = memory_report.build(
                _settings(engine_ws_url=closed_url, engine_owner_uid="uid-abc")
            )
        finally:
            os.chdir(old_cwd)
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

        row = next(s for s in rep["stores"] if s["id"] == "engine-memory")
        assert row["presence"].startswith("unreachable:"), row
        assert row["location"] == f"{closed_url}/ws/uid-abc", row
        assert row["location"].startswith("ws://"), (
            f"engine row must be the resolved ws:// endpoint, never a filesystem path: {row}"
        )
        assert str(home) not in row["location"], (
            f"engine row must never print a filesystem path: {row}"
        )

    print("OK: engine row against a closed local port — 'unreachable: …', "
          "location is the resolved ws:// URL, never a path")


def _test_engine_row_unparseable() -> None:
    """A configured-but-scheme-less `ws_url` ("localhost:8765" — the
    manifest's `ws_url` field carries no shape validation, so this reaches
    the resolver on real operator input) must NOT read as 'not configured':
    a fourth, distinct verdict, and the raw unparseable value must never
    surface as a location — an address nothing could connect to is not a
    location."""
    with tempfile.TemporaryDirectory() as td:
        home, clone = _with_cwd_and_home(td)
        old_cwd = os.getcwd()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(home)
            os.chdir(clone)
            rep = memory_report.build(_settings(engine_ws_url="localhost:8765"))
        finally:
            os.chdir(old_cwd)
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

        row = next(s for s in rep["stores"] if s["id"] == "engine-memory")
        assert row["presence"] == "unknown: engine_ws_url not parseable", row
        assert row["presence"] != "unknown: engine_ws_url not configured", row
        assert row["location"] == "", row
        assert "localhost:8765" not in row["location"], row

    print("OK: engine row with a scheme-less ws_url — the distinct "
          "'not parseable' verdict, never 'not configured', empty location "
          "(the raw unparseable value never surfaces)")


def _test_cc_memory_encoding() -> None:
    """The row's own claimed encoding, exercised directly: both `/` and `.`
    in the clone root map to `-`. A clone root whose basename carries a `.`
    (`acme.cs-clone`) must resolve to a directory whose encoded name ends in
    the `-`-joined tail `-acme-cs-clone`, never the literal dot."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "acme.cs-clone"); clone.mkdir()
        old_cwd = os.getcwd()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(home)
            os.chdir(clone)
            rep = memory_report.build(_settings())
        finally:
            os.chdir(old_cwd)
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

        by_id = {s["id"]: s for s in rep["stores"]}
        cc = by_id["cc-memory"]
        encoded_dir = Path(cc["location"]).parent.name
        assert encoded_dir.endswith("-acme-cs-clone"), cc
        assert "." not in encoded_dir, cc
        assert cc["presence"] == "absent", cc

    print("OK: cc-memory's [/.]→'-' encoding — a clone root basename "
          "containing a '.' resolves to the '-'-joined directory name, "
          "never the literal dot")


def _test_declared_and_not_probed_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        home, clone = _with_cwd_and_home(td)
        old_cwd = os.getcwd()
        old_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(home)
            os.chdir(clone)
            rep = memory_report.build(
                _settings(accounts="founder:uid-founder", read_mailboxes="")
            )
        finally:
            os.chdir(old_cwd)
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

        by_id = {s["id"]: s for s in rep["stores"]}
        gm = by_id["gmail-sent"]
        assert gm["presence"].startswith("declared"), gm
        assert "ops@acme.example" in gm["location"] and "founder" in gm["location"], gm

        un = by_id["user-notes"]
        assert "not probed" in un["presence"], un

        # cc-memory absent on a fresh HOME with no ~/.claude/projects tree
        assert by_id["cc-memory"]["presence"] == "absent", by_id["cc-memory"]

    print("OK: gmail-sent maps the mailbox scope as identifiers ('declared', "
          "never IMAP-probed); user-notes is 'not probed'; cc-memory absent "
          "is a normal answer")


def main() -> int:
    _test_ten_ids_in_order()
    _test_no_store_contents_leak()
    _test_engine_row_unconfigured()
    _test_engine_row_unreachable()
    _test_engine_row_unparseable()
    _test_cc_memory_encoding()
    _test_declared_and_not_probed_rows()
    print("test_memory_report: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
