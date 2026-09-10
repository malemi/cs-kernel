"""Repeatable workspace readiness, using only business-read RPCs.

Authentication can refresh existing local token caches. This command does not
sync, train, generate, send, install, or launch an agent. Remote error payloads
are never echoed: they can contain credentials or business data.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import config, login, rpc

PROBE_TIMEOUT_SECONDS = 15


def _count(value):
    return value if type(value) is int and value >= 0 else None


def build(settings, *, root=None, call=None, which=None):
    root = Path.cwd() if root is None else Path(root)
    call = rpc.call_sync if call is None else call
    which = shutil.which if which is None else which
    checks = []

    def add(name, state, message, action=None, **evidence):
        row = {"id": name, "state": state, "message": message}
        if action:
            row["action"] = action
        if evidence:
            row["evidence"] = evidence
        checks.append(row)

    manifest = root / "manifest.toml"
    workspace = manifest.is_file() and (root / "AGENTS.md").is_file()
    add("workspace", "ready" if workspace else "incomplete",
        "Workspace files present." if workspace else "Workspace files are incomplete.",
        None if workspace else "Run cs init in the workspace.")
    mailbox = bool(settings.email_address and settings.email_password
                   and settings.imap_host and settings.smtp_host)
    add("mailbox", "configured" if mailbox else "incomplete",
        "Mailbox settings present; credential validity is not probed." if mailbox
        else "Mailbox settings or credentials are missing.",
        None if mailbox else "Complete mailbox setup in the desktop, then run cs init; existing state files require deliberate editing.")
    uid = settings.engine_owner_uid.strip()
    connected = False
    if uid and settings.engine_ws_url and settings.firebase_web_api_key:
        try:
            identity = call(settings, "account.who_am_i", timeout=PROBE_TIMEOUT_SECONDS)
            connected = login.identity_verified(identity, uid)
            add("engine", "ready" if connected else "incomplete",
                "Engine confirmed this workspace's identity." if connected
                else "Engine did not confirm the expected signed-in identity.",
                None if connected else "Check the desktop profile and endpoint, then run cs login.")
        except Exception:
            add("engine", "unverified", "Engine connection could not be verified.",
                "Check the remote service and desktop sign-in, then run cs login and cs setup.")
    else:
        add("engine", "incomplete", "Engine connection details are missing.",
            "Sign in to the desktop and run cs init --descriptor PATH with its handoff file.")
    if connected:
        try:
            state = call(settings, "setup.state", timeout=PROBE_TIMEOUT_SECONDS)
            total = _count(state.get("emails_count"))
            analyzed = _count(state.get("emails_analyzed_count"))
            pending = _count(state.get("emails_pending_analysis"))
            known = (total is not None and analyzed is not None and pending is not None
                     and analyzed + pending == total)
            if not known:
                add("preparation", "unverified", "Email preparation evidence is unavailable.",
                    "Update the engine if needed, then retry cs setup.")
            elif total == 0:
                add("preparation", "incomplete", "No email has been downloaded yet; the engine is connected.",
                    "Connect a mailbox and prepare its data in the desktop.", emails_count=0)
            else:
                trained = state.get("agents_trained")
                prepared = (analyzed > 0 and pending == 0 and isinstance(trained, list)
                            and {"memory_message", "task_email", "emailer"}.issubset(trained))
                add("preparation", "ready" if prepared else "incomplete",
                    "Downloaded emails have been processed into memory." if prepared
                    else "Email preparation is still incomplete.",
                    None if prepared else "Finish preparation in the desktop, then retry cs setup.",
                    emails_count=total, emails_analyzed_count=analyzed, emails_pending_analysis=pending)
        except Exception:
            add("preparation", "unverified", "Engine preparation could not be checked.",
                "Update older engines or reconnect, then retry cs setup.")
        try:
            memory = call(settings, "memory.status", timeout=PROBE_TIMEOUT_SECONDS)
            available = memory.get("has_key") is True and memory.get("available") is True
            add("memory", "ready" if available else "incomplete",
                "Company memory is available." if available else "Company memory is not available.",
                None if available else "Configure company memory in the desktop, then retry cs setup.")
        except Exception:
            add("memory", "unverified", "Company memory could not be checked.",
                "Check company memory in the desktop and retry cs setup.")
    else:
        add("preparation", "unverified", "Connect the engine to check email preparation.")
        add("memory", "unverified", "Connect the engine to check company memory.")
    agents = [name for name in ("codex", "claude") if which(name)]
    add("agent", "available" if agents else "incomplete",
        "Agent executable found; sign-in and subscription are unverified." if agents
        else "Codex or Claude Code was not found on this terminal's PATH.",
        "Open your separately paid agent in this workspace and sign in if required." if agents
        else "Install and sign in to Codex or Claude Code, then reopen this terminal.",
        executables=agents, sign_in="unverified")
    ready = all(row["state"] in ("ready", "configured", "available") for row in checks)
    return {"version": 1, "ready": ready, "checks": checks,
            "next_action": ("Open Codex or Claude Code in this workspace; agent sign-in is separate."
                            if ready else next((r["action"] for r in checks
                                               if r["state"] not in ("ready", "configured", "available")
                                               and "action" in r), "Complete setup in the desktop."))}


def cmd_setup(args):
    report = build(config.load())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Workspace checks passed." if report["ready"] else "Workspace needs attention.")
        for row in report["checks"]:
            print(f"  {row['id']}: {row['message']}")
        print(f"Next: {report['next_action']}")
        print("Memory processing does not prove reply quality or task completion.")
    return 0 if report["ready"] else 1
