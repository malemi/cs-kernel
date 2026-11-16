#!/usr/bin/env python3
"""Scheduled discovery syncs the engine's mail right before it reads the mailbox.

The sweep reads the mailbox live; every later thread read goes through the
engine. A message that arrives after the tick's first intake is discovered and
selected, so the engine must hold it before the sweep runs.
"""
import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cs import cli  # noqa: E402

DISCOVERY = {"open": [], "handled": [], "escalated": [], "read_incomplete": None, "assignment_incomplete": False}
ARGS = dict(days=14, json=True, all_buckets=True, crm=False)
WORKSET = {"complete": True, "limit": 2, "selected": [], "deferred": [], "held": []}


def run(scheduled, intake):
    order = []

    def call_sync(settings, method, params=None, timeout=60, id_token=None):
        order.append((method, params))
        if isinstance(intake, Exception):
            raise intake
        return intake

    def sweep(settings, days):
        order.append(("sweep", days))
        return json.loads(json.dumps(DISCOVERY))

    out, err = io.StringIO(), io.StringIO()
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("CS_OPERATOR_HEALTH_CONTEXT", "CS_OPERATOR_ACCEPTANCE_RECEIPT")}
    with patch.dict(os.environ, environment, clear=True), \
            patch.object(cli.config, "load", return_value=SimpleNamespace(engine_owner_uid="owner")), \
            patch.object(cli, "_scheduled_workset_enabled", return_value=scheduled), \
            patch.object(cli.rpc, "call_sync", side_effect=call_sync), \
            patch("cs.unanswered.sweep", side_effect=sweep), \
            patch("cs.operator_workset.reserve", return_value=dict(WORKSET)), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.cmd_unanswered(argparse.Namespace(**ARGS))
    return code, order, err.getvalue()


accepted = {"success": True, "scope": "email", "summary": "1 new emails", "errors": [], "busy": False}
code, order, err = run(True, accepted)
assert code == 0 and err == "", (code, err)
assert order == [("sync.run", {"scope": "email", "days_back": 14}), ("sweep", 14)], order

for refused in ({"success": False, "scope": "email"}, {"success": True, "scope": "all"}, [], ConnectionError("engine away")):
    code, order, err = run(True, refused)
    assert code == 0, code
    assert [step[0] for step in order] == ["sync.run", "sweep"], order
    assert err.startswith("unanswered: mail intake before discovery failed ("), err

code, order, err = run(False, accepted)
assert code == 0 and err == "" and order == [("sweep", 14)], (code, order, err)

print("OK: scheduled discovery syncs mail before the sweep, reports a refused intake and still sweeps")
