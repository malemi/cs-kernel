"""Rendered provider denies reach the actual cron process and all skill hosts."""
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
        wrapper = clone / "bin/cs_operator_cron.sh"
        wrapper.write_text(self.render("bin/cs_operator_cron.sh.j2"))
        fake = self.root / "fake-claude"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\nfrom pathlib import Path\n"
            "Path(os.environ['CAPTURE']).write_text(json.dumps({"
            "'args': sys.argv[1:], 'marker': os.environ.get('CS_OPERATOR_HEADLESS')}))\n")
        fake.chmod(0o700)
        capture = self.root / "invocation.json"
        runtime_env = dict(os.environ, HOME=str(self.root / "home"),
                           CLAUDE_BIN=str(fake), CAPTURE=str(capture), CS_OPERATOR_HEADLESS="0")
        result = subprocess.run(["bash", str(wrapper)], env=runtime_env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        invocation = json.loads(capture.read_text())
        self.assertEqual(invocation["marker"], "1")
        args = invocation["args"]
        self.assertEqual(args[:3], ["-p", "/cs-operator", "--disallowed-tools"])
        for entry in self.expected_denies():
            self.assertEqual(args[3:].count(entry), 1)

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
