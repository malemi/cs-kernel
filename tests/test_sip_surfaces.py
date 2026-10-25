"""Rendered provider denies reach the actual cron process and all skill hosts."""
import asyncio
import threading
import websockets
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cs import project_init


TEMPLATES = Path(project_init.__file__).parent / "templates/project"
SPELLINGS = (
    ".venv/bin/python -m cs", ".venv/bin/python3 -m cs", ".venv/bin/cs",
    "python -m cs", "python3 -m cs", "cs",
)
ACTIONS = ("connection vonage provision", "connection vonage allow-ip")
BASE = dict(
    company_name="Acme Corp", company_display_name="Acme", company_from_name="Acme Support",
    company_slug="acme", company_prog_name="acme-cs", email_address="support@acme.example",
    operator_voice=project_init.DEFAULT_OPERATOR_VOICE, local_scripts_cron_denied=[],
)


class SIPSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = project_init.build_jinja_env(TEMPLATES)

    def render(self, name):
        return self.env.get_template(name).render(**BASE)

    def expected_denies(self):
        return [f"Bash({spelling} {action}:*)" for action in ACTIONS for spelling in SPELLINGS]

    def test_settings_deny_both_actions_in_all_six_spellings(self):
        settings = json.loads(self.render(".claude/settings.json.j2"))
        deny = settings["permissions"]["deny"]
        allow = settings["permissions"]["allow"]
        for entry in self.expected_denies():
            self.assertIn(entry, deny)
            self.assertNotIn(entry, allow)
        # A broader connection allow would turn future provider actions into
        # unattended capabilities without an explicit permission decision.
        self.assertFalse(any("connection" in item for item in allow))

    def test_actual_wrapper_passes_denies_and_exports_headless_marker(self):
        clone = self.root / "clone"
        (clone / "bin").mkdir(parents=True)
        (clone / ".venv/bin").mkdir(parents=True)
        python = clone / ".venv/bin/python"
        python.write_text(f"#!/bin/sh\nexec {sys.executable} \"$@\"\n")
        python.chmod(0o755)
        wrapper = clone / "bin/cs_operator_cron.sh"
        wrapper.write_text(self.render("bin/cs_operator_cron.sh.j2"))
        fake = self.root / "fake-claude"
        fake.write_text(f"#!{sys.executable}\n" + 'import json, os, sys, subprocess\nfrom pathlib import Path\nPath(os.environ[\'CAPTURE\']).write_text(json.dumps({\'args\':sys.argv[1:],\'marker\':os.environ.get(\'CS_OPERATOR_HEADLESS\')}))\nif sys.argv[1:] == [\'auth\',\'status\',\'--json\']:\n    print(json.dumps({\'authMethod\':\'none\'})); raise SystemExit(0)\nscript="from cs import operator_health as h, operator_workset as w; from cs.config import Settings; import json,sys; sys.argv=[\'cs\',*h.ARGV]; value={\'open\':[],\'human_work\':[],\'assignment_audit\':[],\'operational_fixture_discovery\':[],\'assignment_incomplete\':False,\'read_incomplete\':None}; value[\'resumed\']=[]; settings=Settings(engine_owner_uid=\'local-fixture-owner\'); w.observe(settings,\'tasks\',[]); w.observe(settings,\'review\',{\'drafts\':[]}); value[\'triage_workset\']=w.reserve(settings,value); output=json.dumps(value,ensure_ascii=False,indent=2)+chr(10); h.capture(output.encode(),value,0,\'local-fixture-owner\'); print(output,end=\'\')"\noutput=subprocess.run([sys.executable,\'-c\',script],capture_output=True,check=True).stdout.decode()\nfor index,command in enumerate([\'whoami\',\'config\',\'tasks --json\',\'review --json\',\'campaign pending\',\'unanswered --days 14 --json --all-buckets\']):\n    tool_id=\'phase-\'+str(index)\n    print(json.dumps({\'type\':\'assistant\',\'message\':{\'content\':[{\'type\':\'tool_use\',\'id\':tool_id,\'name\':\'Bash\',\'input\':{\'command\':\'.venv/bin/python -m cs \'+command}}]}}))\n    print(json.dumps({\'type\':\'user\',\'message\':{\'content\':[{\'type\':\'tool_result\',\'tool_use_id\':tool_id,\'is_error\':False,\'content\':output if index==5 else \'{}\'}]}}))\nprint(json.dumps({\'type\':\'result\',\'result\':\'done\',\'is_error\':False}))\n')
        fake.chmod(0o700)
        capture = self.root / "invocation.json"
        runtime_env = dict(os.environ, HOME=str(self.root / "home"),
                           PYTHONPATH=str(Path(project_init.__file__).parent.parent),
                           CLAUDE_BIN=str(fake), CAPTURE=str(capture), CS_OPERATOR_HEADLESS="0")
        ready = threading.Event()
        stop = threading.Event()
        requests = []
        ports = []

        async def intake_server():
            async def handle(ws):
                async for raw in ws:
                    request = json.loads(raw)
                    requests.append(request)
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                              "result": {"scope": "email", "success": True, "errors": []}}))
            async with websockets.serve(handle, "127.0.0.1", 0) as server:
                ports.append(server.sockets[0].getsockname()[1])
                ready.set()
                while not stop.is_set():
                    await asyncio.sleep(.01)

        server_thread = threading.Thread(target=lambda: asyncio.run(intake_server()), daemon=True)
        server_thread.start()
        self.assertTrue(ready.wait(5))
        def cleanup_server():
            stop.set()
            server_thread.join(5)
        self.addCleanup(cleanup_server)
        bootstrap = self.root / "intake-bootstrap.py"
        bootstrap.write_text(
            "import runpy, sys\nfrom cs import auth\n"
            "auth.get_id_token = lambda settings: 'local-test-token'\n"
            "module = sys.argv[2]\n"
            "sys.argv = [module, *sys.argv[3:]]\n"
            "runpy.run_module(module, run_name='__main__')\n")
        python.write_text(f"#!/bin/sh\nexec {sys.executable} {bootstrap} \"$@\"\n")
        (clone / "manifest.toml").write_text(
            f'[engine]\nws_url = "ws://127.0.0.1:{ports[0]}"\nowner_uid = "local-fixture-owner"\n')
        result = subprocess.run(["bash", str(wrapper)], env=runtime_env,
                                capture_output=True, text=True, timeout=10)
        log = self.root / "home/.acme-cs/cs_operator.log"
        self.assertEqual(result.returncode, 0,
                         result.stderr + (log.read_text() if log.exists() else ""))
        self.assertEqual([request["method"] for request in requests],
                         ["system.capabilities", "sync.run"])
        self.assertEqual(requests[0]["params"], {})
        self.assertEqual(requests[1]["params"], {"scope": "email", "days_back": 14})
        invocation = json.loads(capture.read_text())
        self.assertEqual(invocation["marker"], "1")
        args = invocation["args"]
        self.assertEqual(args[:5], ["-p", "/cs-operator", "--verbose",
                                    "--output-format", "stream-json"])
        self.assertEqual(args.count("--disallowed-tools"), 1)
        deny_start = args.index("--disallowed-tools") + 1
        for entry in self.expected_denies():
            self.assertEqual(args[deny_start:].count(entry), 1)

    def check_skill_hosts(self, copy_fallback):
        clone = self.root / ("copy-clone" if copy_fallback else "link-clone")
        skill = clone / ".claude/skills/cs-sip-trunk/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(self.render(".claude/skills/cs-sip-trunk/SKILL.md.j2"))
        canonical = skill.read_bytes()
        self.assertIn(b"name: cs-sip-trunk", canonical)
        self.assertIn(b"connection vonage", canonical)
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(project_init, "LEGACY_CODEX_PROMPTS", self.root / "unused-prompts"))
            if copy_fallback:
                stack.enter_context(patch.object(Path, "symlink_to", side_effect=OSError("no symlink support")))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            project_init.install_agent_surfaces(clone)
            for host in (".agents", ".opencode"):
                directory = clone / host / "skills"
                self.assertEqual(directory.is_symlink(), not copy_fallback)
                self.assertEqual((directory / "cs-sip-trunk/SKILL.md").read_bytes(), canonical)
            # Reinstalling must preserve the same skill for every host.
            project_init.install_agent_surfaces(clone)
            for host in (".claude", ".agents", ".opencode"):
                self.assertEqual((clone / host / "skills/cs-sip-trunk/SKILL.md").read_bytes(), canonical)

    def test_skill_bytes_are_identical_across_all_hosts(self):
        self.check_skill_hosts(copy_fallback=False)

    def test_skill_bytes_are_identical_with_copy_fallback(self):
        self.check_skill_hosts(copy_fallback=True)


if __name__ == "__main__":
    unittest.main()
