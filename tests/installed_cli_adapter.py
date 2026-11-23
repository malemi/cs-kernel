"""Synthetic engine for child-process checks of the installed cs entry point."""
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import sysconfig
from unittest.mock import patch

import cs
from cs import config, rpc
from assignment_fixture import normal_projection

journal = Path(sys.argv[1])
sys.argv = ["cs", *sys.argv[2:]]
package = Path(cs.__file__).resolve().parent
assert package == Path(sysconfig.get_paths()["purelib"]) / "cs", package
settings = config.Settings(_env_file=(), email_address="support@example.test",
    engine_owner_uid="fixture-owner", db_path=str(journal.with_suffix(".sqlite")),
    cs_triage_mode=os.environ.get("LAUNCH_MODE", "draft"))
state = json.loads(journal.read_text())
handle = "gmail:" + "a" * 64 + ":native"
state["package_root"] = str(package)


def call(selected, method, params, **kwargs):
    state["calls"].append([method, params])
    key = params.get("request_key")
    if method == "system.capabilities":
        return {"mailbox_drafts": 1, "mailbox_reply": 1}
    if method == "tasks.assignment.project":
        return normal_projection(selected, params)
    if method == "drafts.get":
        return {"ok": state["draft"], "draft": {"id": handle} if state["draft"] else None}
    base = {"request_key": key, "operation_id": "fixture-op"}
    if method == "drafts.compose_reply":
        if params["mode"] == "send":
            assert params["operator_origin"] == "scheduled_operator"
        if state["answered"] or state["draft"]:
            return {**base, "ok": True, "state": "answered" if state["answered"] else "draft_exists",
                    "effect_certainty": "not-dispatched"}
        state["generations"] += 1
        if params["mode"] == "draft":
            state["draft"] = True
            return {**base, "ok": True, "state": "completed", "draft_id": handle, "current_draft": {"exists": True}}
    elif method == "drafts.trash":
        assert params["draft_id"] == handle
        state["draft"] = False
        return {**base, "ok": True, "state": "trashed", "draft_id": handle, "effect_certainty": "verified"}
    elif method == "drafts.send":
        assert params["draft_id"] == handle
        base["draft_id"] = handle
    else:
        raise AssertionError("unexpected RPC " + method)
    if key not in state["dispatched"]:
        state["dispatched"].append(key)
        state["draft"] = False
    return {**base, "ok": state["visible"], "state": "sent" if state["visible"] else "unconfirmed",
            "effect_certainty": "verified" if state["visible"] else "unconfirmed", "message_id": "<sent@example.test>"}


try:
    with patch.object(config, "load", return_value=settings), patch.object(rpc, "call_sync", side_effect=call), \
         patch.object(socket.socket, "connect", side_effect=AssertionError("network access")):
        runpy.run_module("cs", run_name="__main__")
finally:
    journal.write_text(json.dumps(state, sort_keys=True))
