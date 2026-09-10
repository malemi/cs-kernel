"""Installed package + real stamped workspace + controlled local WebSocket.

No production descriptors, credentials, services, mailbox, or model is used.
Auth exchange alone is substituted with a test ID token; the RPC transport,
stamping, settings loading, login storage, and CLI JSON subprocess are real.
"""
from __future__ import annotations

import base64
import builtins
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

from websockets.sync.server import serve
from cs import auth, config, login, project_init, setup

UID = "fixture-owner"
TOKEN = "fixture-refresh-secret"
PASSWORD = "fixture-mail-secret"


def main():
    with tempfile.TemporaryDirectory(prefix="cs-setup-test-") as td:
        base = Path(td)
        home = base / "home"
        home.mkdir()
        workspace = base / "operator's workspace"
        seen = []
        state = {"has_synced": True, "has_trained": True, "emails_count": 2,
                 "agents_trained": ["memory_message", "task_email", "emailer"],
                 "emails_analyzed_count": 2, "emails_pending_analysis": 0,
                 "last_email_analyzed_at": "2026-09-10T10:00:00Z"}
        identity = {"signed_in": True, "uid": UID}

        def handler(ws):
            for raw in ws:
                request = json.loads(raw)
                method = request["method"]
                seen.append(method)
                results = {"account.who_am_i": identity, "setup.state": state,
                           "memory.status": {"has_key": True, "available": True, "private": TOKEN},
                           "settings.get": {"values": {"IMAP_HOST": "mail.example", "IMAP_PORT": "993",
                                                       "SMTP_HOST": "out.example", "SMTP_PORT": "587", "PRIVATE": TOKEN}},
                           "settings.get_secret": {"value": PASSWORD}}
                assert method in results, method
                ws.send(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": results[method]}))

        with serve(handler, "127.0.0.1", 0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"ws://127.0.0.1:{server.socket.getsockname()[1]}"
            descriptor = {"version": 1, "email": "support@fixture.example", "uid": UID,
                          "engine_ws_url": url + "/ws/" + UID,
                          "firebase_web_api_key": "fixture-public", "refresh_token": TOKEN}
            handoff = base / "selected.json"
            handoff.write_text(json.dumps(descriptor))
            profiles = base / "profiles"
            foreign = profiles / "profiles" / "wrong" / "cs-descriptor.json"
            foreign.parent.mkdir(parents=True)
            foreign.write_text(json.dumps({**descriptor, "uid": "wrong", "refresh_token": "wrong-secret"}))
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("CS_", "EMAIL_", "FIREBASE_", "IMAP_", "SMTP_"))}
            env.update(HOME=str(home), CS_ZYLCH_ROOT=str(profiles))
            token = "x." + base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + 3600}).encode()).decode().rstrip("=") + ".x"
            old_cwd = Path.cwd()
            out = io.StringIO()

            def answer(prompt):
                if prompt.startswith("Company name"):
                    return "Fixture"
                if prompt.startswith("Destination directory"):
                    return str(workspace)
                if prompt.startswith("Proceed with"):
                    return "y"
                return ""

            try:
                os.chdir(base)
                with patch.dict(os.environ, env, clear=True), patch.object(builtins, "input", answer), \
                     patch.object(auth, "_exchange", return_value={"id_token": token, "user_id": UID}), \
                     contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    assert project_init.cmd_init(["--descriptor", str(base / "missing")]) == 1
                    assert not workspace.exists()
                    assert project_init.cmd_init(["--descriptor", str(handoff)]) == 0
                    os.chdir(workspace)
                    settings = config.load()
                    assert settings.engine_owner_uid == UID
                    assert settings.imap_host == "mail.example"
                    assert settings.smtp_host == "out.example"
                    assert settings.email_password == PASSWORD
                    assert (workspace / ".agents/skills").resolve() == (workspace / ".claude/skills").resolve()
                    assert (workspace / ".opencode/skills").resolve() == (workspace / ".claude/skills").resolve()
                    auth._write_cache(settings, token)
                    identity["uid"] = "wrong"
                    assert login.cmd_login(["--descriptor", str(handoff)]) == 1
                    identity["uid"] = UID
                    assert login.cmd_login(["--descriptor", str(handoff)]) == 0
                    report = setup.build(settings, which=lambda _: "/fixture/agent")
                    assert report["ready"], report
                    for evidence in ({**state, "emails_count": 0, "emails_analyzed_count": 0},
                                     {k: v for k, v in state.items() if not k.startswith("emails_")},
                                     {**state, "agents_trained": ["memory_message"]},
                                     {**state, "emails_analyzed_count": 1, "emails_pending_analysis": 1}):
                        original = state.copy()
                        state.clear(); state.update(evidence)
                        assert not setup.build(settings, which=lambda _: "/fixture/agent")["ready"]
                        state.clear(); state.update(original)
                    identity["signed_in"] = False
                    assert not setup.build(settings, which=lambda _: "/fixture/agent")["ready"]
                    identity["signed_in"] = True
                    # The released pin predates this unreleased surface. Prove
                    # the changed source install explicitly, never mislabel the
                    # generated public requirements pin as containing it.
                    source = Path(__file__).resolve().parents[1]
                    clone_python = project_init._venv_python(workspace)
                    for command in (["uv", "venv", str(workspace / ".venv")],
                                    ["uv", "pip", "install", "--python", str(clone_python), str(source)]):
                        install = subprocess.run(command, cwd=workspace, env=env,
                                                 capture_output=True, text=True, timeout=180)
                        assert install.returncode == 0, install.stdout + install.stderr
                    # Real workspace-installed CLI; no cs/ source in clone.
                    binary = base / "bin"
                    binary.mkdir()
                    agent = binary / "codex"
                    agent.write_text("#!/bin/sh\nexit 0\n"); agent.chmod(0o700)
                    cli_env = dict(env, PATH=str(binary) + os.pathsep + env.get("PATH", ""))
                    origin = subprocess.run([str(clone_python), "-c", "import cs; print(cs.__file__)"],
                                            cwd=workspace, env=cli_env, capture_output=True, text=True, timeout=15)
                    assert origin.returncode == 0 and "site-packages" in origin.stdout, origin.stdout
                    proc = subprocess.run([str(clone_python), "-m", "cs", "setup", "--json"],
                                          cwd=workspace, env=cli_env, capture_output=True, text=True, timeout=40)
                    assert proc.returncode == 0, proc.stdout + proc.stderr
                    assert json.loads(proc.stdout)["ready"]
                    assert TOKEN not in proc.stdout and PASSWORD not in proc.stdout
                    for path in workspace.rglob("*"):
                        if path.is_file() and ".git" not in path.parts and ".venv" not in path.parts:
                            content = path.read_bytes()
                            assert TOKEN.encode() not in content and PASSWORD.encode() not in content, path
                    assert TOKEN not in out.getvalue() and PASSWORD not in out.getvalue()
            finally:
                os.chdir(old_cwd)
                server.shutdown()
            assert set(seen) <= {"settings.get", "settings.get_secret", "account.who_am_i", "setup.state", "memory.status"}
    print("test_setup_journey: all assertions passed")


if __name__ == "__main__":
    main()
