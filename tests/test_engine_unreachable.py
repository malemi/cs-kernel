#!/usr/bin/env python3
"""An unreachable engine must fail as ONE clean line, never a raw traceback.

`cs login` already handles this cleanly (see `cs/login.py`'s proof-call
except clause) — but every OTHER engine-backed verb went through
`cli.main()`'s dispatch with no such guard, so the exact same failure
(the mrcall-desktop app not running, or its engine on another machine)
surfaced as `ConnectionRefusedError: [Errno 111] Connect call failed
('127.0.0.1', 1)` straight out of `websockets.connect` — a traceback is the
first thing a new customer sees when the desktop app simply is not running
yet, and per the charter, configuration/environment absence is a product
state, not a bug.

No real network egress: `engine_ws_url` points at a closed local port
(bind + close, same trick as `tests/test_login.py`'s proof-call guard), so
the TCP connect is refused immediately by the OS, on this machine only.
`auth.get_id_token` is stubbed so the failure exercised is the connect
itself, not a missing credential (already covered by
`tests/test_auth_boundary.py`).

Guards:
  (i)  `cs whoami` against a closed local port: `cli.main` returns non-zero,
       stderr names the configured engine URL and the mrcall-desktop app,
       and stderr contains NO "Traceback".
  (ii) the caught exception family is narrow (ConnectionError + DNS/timeout +
       websockets.exceptions.WebSocketException), not bare `Exception` — a
       `config.ConfigError` and an ordinary `ValueError` raised inside a verb
       must still propagate as a real, unhandled failure (proving the fix
       does not mask real bugs).
"""
from __future__ import annotations

import contextlib
import io
import socket
import sys
from pathlib import Path

from cs import auth as auth_mod
from cs import cli
from cs import config as config_mod
from cs import rpc as rpc_mod
from cs.config import Settings

UID = "uid-test-abc123"


def _closed_port_url() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"ws://127.0.0.1:{port}"


def _run_main_with_stubbed_config(argv: list[str], settings: Settings) -> tuple[int, str, str]:
    orig_load = config_mod.load
    orig_get_id_token = auth_mod.get_id_token
    config_mod.load = lambda: settings
    auth_mod.get_id_token = lambda *a, **k: "fake-id-token"
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
    finally:
        config_mod.load = orig_load
        auth_mod.get_id_token = orig_get_id_token
    return code, out.getvalue(), err.getvalue()


def _test_whoami_against_unreachable_engine() -> None:
    closed_url = _closed_port_url()
    settings = Settings(
        _env_file=(),
        engine_owner_uid=UID,
        email_address="ops@acme.example",
        engine_ws_url=closed_url,
        prog_name="acme-cs",
    )

    code, out, err = _run_main_with_stubbed_config(["whoami"], settings)

    assert code != 0, f"expected a non-zero exit, got {code}:\nstdout={out}\nstderr={err}"
    assert "Traceback" not in err and "Traceback" not in out, (
        f"an unreachable engine must never surface a raw traceback:\nstdout={out}\nstderr={err}"
    )
    assert closed_url in err, (
        f"the message must name the configured engine URL:\nstderr={err}"
    )
    assert "mrcall-desktop" in err, (
        f"the message must name the mrcall-desktop app as the likely cause:\nstderr={err}"
    )


def _test_other_exceptions_still_propagate() -> None:
    """The fix must catch ONLY the connection-failure family. A verb that
    raises something else entirely (here: a plain ValueError standing in for
    a real bug, injected via a stubbed `rpc.call_sync`) must still blow up
    loud out of `cli.main`, proving the handler was not widened to bare
    `Exception` — a broad catch there would silently turn real bugs into a
    misleading "engine unreachable" message.

    The FileNotFoundError case below guards the specific over-catch this fix
    was born with: `except OSError` looks right, but FileNotFoundError and
    PermissionError are OSError subclasses, so a missing file in ANY verb
    would have been reported as "cannot reach the engine" — a confidently
    wrong diagnosis, worse than the traceback it replaced. The handler must
    catch ConnectionError (refused/reset/aborted) and the DNS/timeout cases,
    never OSError wholesale."""
    settings = Settings(
        _env_file=(),
        engine_owner_uid=UID,
        email_address="ops@acme.example",
        engine_ws_url="ws://127.0.0.1:1",
        prog_name="acme-cs",
    )
    orig_load = config_mod.load
    orig_call_sync = rpc_mod.call_sync
    config_mod.load = lambda: settings
    rpc_mod.call_sync = lambda *a, **k: (_ for _ in ()).throw(
        ValueError("simulated real bug, not a connection failure")
    )
    try:
        raised = False
        try:
            cli.main(["whoami"])
        except ValueError as e:
            raised = True
            assert "simulated real bug" in str(e)
        assert raised, (
            "a non-connection exception raised inside a verb must propagate "
            "out of cli.main, not be swallowed by the new connection-failure handler"
        )

        # -- the over-catch guard: an OSError that is NOT a connection failure --
        rpc_mod.call_sync = lambda *a, **k: (_ for _ in ()).throw(
            FileNotFoundError(2, "No such file or directory", "/some/missing/file")
        )
        raised = False
        try:
            cli.main(["whoami"])
        except FileNotFoundError as e:
            raised = True
            assert "missing/file" in str(e)
        assert raised, (
            "a FileNotFoundError (an OSError subclass, but NOT a connection "
            "failure) must propagate — catching OSError wholesale would report "
            "a missing file as 'cannot reach the engine', which is a "
            "confidently wrong diagnosis"
        )
    finally:
        config_mod.load = orig_load
        rpc_mod.call_sync = orig_call_sync


def main() -> int:
    _test_whoami_against_unreachable_engine()
    _test_other_exceptions_still_propagate()
    print("test_engine_unreachable: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
