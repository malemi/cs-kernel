"""Installed CLI routes and outcome reporting against a synthetic engine."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = "<root@example.test>"
SOURCE = "452ddb83-69c9-479c-98ab-b6f690eab2a7"
HANDLE = "gmail:" + "a" * 64 + ":native"


class InstalledCLI(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)
        self.journal = self.home / "provider.json"
        self.save(dict(calls=[],generations=0,draft=False,answered=False,visible=True,dispatched=[]))

    def save(self, value):
        self.journal.write_text(json.dumps(value))

    def state(self):
        return json.loads(self.journal.read_text())

    def invoke(self, arguments, *, mode=None, code=0):
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.home),
               "PYTHONPATH": os.environ.get("CLI_TEST_HELPERS", str(HERE))}
        if mode:
            env.update(CS_OPERATOR_HEADLESS="1", LAUNCH_MODE=mode)
            if mode == "send":
                env["CS_HEADLESS_SEND"] = "1"
        p = subprocess.run([sys.executable, str(HERE / "installed_cli_adapter.py"), str(self.journal), *arguments],
                            cwd=self.home, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, code, (p.stdout,p.stderr))
        return json.loads(p.stdout)

    def test_two_draft_ticks_and_one_direct_send(self):
        args = ["--thread-id", ROOT, "--source-id", SOURCE]
        first = self.invoke(["draft-reply", *args], mode="draft")
        self.assertEqual(first["draft_id"], HANDLE)
        self.assertEqual(self.invoke(["draft-reply", *args], mode="draft")["state"], "draft_exists")
        self.assertEqual(self.invoke(["reply-send", *args], mode="send")["state"], "draft_exists")
        self.assertEqual(self.state()["generations"], 1)
        self.assertEqual(self.state()["dispatched"], [])
        self.save({**self.state(), "draft": False, "answered": True})
        self.assertEqual(self.invoke(["reply-send", *args], mode="send")["state"], "answered")
        self.save({**self.state(), "answered": False})
        self.assertEqual(self.invoke(["reply-send", *args], mode="send")["state"], "sent")
        self.assertFalse(self.state()["draft"])
        self.assertEqual(len(self.state()["dispatched"]), 1)
        self.assertFalse(any(method in ("drafts.create","drafts.send") for method,_ in self.state()["calls"]))

    def test_send_restarts_reuse_key_when_provider_is_unconfirmed(self):
        self.save({**self.state(), "draft": True, "visible": False})
        args = ["draft-send", HANDLE, "--operation-id", "fixture-send"]
        self.assertEqual(self.invoke(args, code=5)["state"], "unconfirmed")
        self.assertEqual(self.invoke(args, code=5)["request_key"], "fixture-send")
        self.save({**self.state(), "visible": True})
        self.assertEqual(self.invoke(args)["message_id"], "<sent@example.test>")
        self.assertEqual(self.state()["dispatched"], ["fixture-send"])

    def test_named_trash_and_launcher_boundaries(self):
        self.save({**self.state(), "draft": True})
        self.assertTrue(self.invoke(["draft-delete",HANDLE])["ok"])
        self.assertTrue(self.state()["draft"])
        self.invoke(["draft-delete", HANDLE,"--commit"],mode="send",code=3)
        self.invoke(["draft-send",HANDLE],mode="send",code=3)
        self.invoke(["reply-send","--thread-id",ROOT,"--source-id",SOURCE],mode="draft",code=3)
        self.assertTrue(self.state()["draft"])
        self.assertEqual(self.invoke(["draft-delete",HANDLE,"--commit"])["state"], "trashed")
        self.assertFalse(self.state()["draft"])
        self.assertEqual(self.state()["dispatched"], [])


if __name__ == "__main__":
    unittest.main()
