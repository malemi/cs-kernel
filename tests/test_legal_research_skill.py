#!/usr/bin/env python3
"""Closed legal retirement preserves originals before refreshing discovery."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cs import project_init as pi

LEGAL_FILES = (
    "PROVENANCE.md", "SKILL.md", "references/administrative-remedies.md",
    "references/deadlines.md", "references/evidence.md", "references/sources.md",
    "scripts/count_days.py",
)
HOSTS = (".claude", ".agents", ".opencode")


def snapshot(tree):
    result = {}
    for path in [tree, *sorted(tree.rglob("*"))]:
        mode = stat.S_IMODE(path.lstat().st_mode)
        result[path.relative_to(tree).as_posix()] = (
            ("link", mode, os.readlink(path)) if path.is_symlink() else
            ("directory", mode) if path.is_dir() else
            ("file", mode, hashlib.sha256(path.read_bytes()).hexdigest()))
    return result


def seed(root, copied=False, edited=False, extra=False):
    canonical = root / ".claude/skills/cs-legal-research"
    for rel in LEGAL_FILES:
        path = canonical / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"original {rel}\n")
    (canonical / "scripts/count_days.py").chmod(0o751)
    (canonical / "references").chmod(0o750)
    if edited:
        (canonical / "SKILL.md").write_bytes(b"edited canonical\n")
    if extra:
        (canonical / "private.txt").write_bytes(b"unknown local bytes\x00\xff")
        (canonical / "local-link").symlink_to("private.txt")
    other = canonical.parent / "other/SKILL.md"
    other.parent.mkdir()
    other.write_text("unrelated skill\n")
    for host in HOSTS[1:]:
        skills = root / host / "skills"
        skills.parent.mkdir()
        if copied:
            shutil.copytree(canonical.parent, skills, symlinks=True)
            if edited:
                (skills / "cs-legal-research/SKILL.md").write_text(f"edited {host}\n")
        else:
            skills.symlink_to("../.claude/skills")
    ledger = {f".claude/skills/cs-legal-research/{rel}": "old" for rel in LEGAL_FILES}
    ledger.update({"unrelated/key": "keep", ".claude/skills/cs-legal-research/unknown.txt": "keep"})
    (root / "template-manifest.json").write_text(json.dumps({"file_checksums": ledger}))
    for rel in ("company/sentinel", "requirements.txt", ".claude/settings.json", "bin/cron"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"unchanged {rel}\n")
    return canonical


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.prompts = patch.object(pi, "LEGACY_CODEX_PROMPTS", self.root / "no-prompts")
        self.prompts.start()

    def tearDown(self):
        self.prompts.stop()
        self.tmp.cleanup()

    def test_matrix_and_idempotence(self):
        for copied in (False, True):
            for edited in (False, True):
                for extra in (False, True):
                    with self.subTest(copied=copied, edited=edited, extra=extra):
                        root = self.root / f"{copied}-{edited}-{extra}"
                        root.mkdir()
                        seed(root, copied, edited, extra)
                        hosts = HOSTS if copied else HOSTS[:1]
                        before = {host: snapshot(root / host / "skills/cs-legal-research") for host in hosts}
                        sentinels = {rel: (root / rel).read_bytes() for rel in
                                     ("company/sentinel", "requirements.txt", ".claude/settings.json", "bin/cron")}
                        collision = root / ".claude/retired-skills/cs-legal-research"
                        collision.mkdir(parents=True)
                        (collision / "keep").write_text("previous archive")
                        refusal = patch.object(Path, "symlink_to", side_effect=OSError("forced copy"))
                        with refusal if copied else contextlib.nullcontext():
                            pi.install_agent_surfaces(root)
                            pi.install_agent_surfaces(root)
                        self.assertEqual((collision / "keep").read_text(), "previous archive")
                        for host in HOSTS:
                            self.assertFalse((root / host / "skills/cs-legal-research").exists())
                            self.assertEqual((root / host / "skills/other/SKILL.md").read_text(), "unrelated skill\n")
                        for host in hosts:
                            name = "cs-legal-research.1" if host == ".claude" else f"cs-legal-research.{host[1:]}"
                            archive = root / ".claude/retired-skills" / name
                            self.assertEqual(snapshot(archive), before[host])
                            restored = root / ("restored" + host)
                            shutil.copytree(archive, restored, symlinks=True)
                            self.assertEqual(snapshot(restored), before[host])
                        for rel, data in sentinels.items():
                            self.assertEqual((root / rel).read_bytes(), data)
                        ledger = json.loads((root / "template-manifest.json").read_text())["file_checksums"]
                        self.assertEqual(ledger, {"unrelated/key": "keep", ".claude/skills/cs-legal-research/unknown.txt": "keep"})
                        self.assertEqual(len(list((root / ".claude/retired-skills").iterdir())), len(hosts) + 1)

    def test_stale_only_and_absent_ledger(self):
        ledger = self.root / "template-manifest.json"
        ledger.write_text(json.dumps({"file_checksums": {key: "stale" for key in pi.RETIRED_LEGAL_KEYS}}))
        self.assertEqual(pi.retire_legal_research(self.root), 0)
        self.assertEqual(json.loads(ledger.read_text())["file_checksums"], {})
        ledger.unlink()
        seed(self.root)
        ledger.unlink()
        pi.retire_legal_research(self.root)
        self.assertFalse(ledger.exists())

    def test_archive_failure_keeps_all_originals_and_ledger(self):
        seed(self.root, copied=True, edited=True, extra=True)
        before = snapshot(self.root)
        real_copy = shutil.copytree
        calls = 0
        def fail(source, dest, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected archive failure")
            return real_copy(source, dest, *args, **kwargs)
        with patch.object(pi.shutil, "copytree", side_effect=fail):
            with self.assertRaisesRegex(OSError, "injected archive failure"):
                pi.install_agent_surfaces(self.root)
        after = snapshot(self.root)
        for rel, data in before.items():
            self.assertEqual(after[rel], data)

    def test_archive_verification_failure_keeps_originals(self):
        canonical = seed(self.root, copied=True)
        ledger = (self.root / "template-manifest.json").read_bytes()
        real_copy = shutil.copytree
        def corrupt(source, dest, *args, **kwargs):
            result = real_copy(source, dest, *args, **kwargs)
            (Path(dest) / "SKILL.md").write_text("corrupt archive")
            return result
        with patch.object(pi.shutil, "copytree", side_effect=corrupt):
            with self.assertRaisesRegex(OSError, "verification failed"):
                pi.retire_legal_research(self.root)
        self.assertEqual((canonical / "SKILL.md").read_text(), "original SKILL.md\n")
        self.assertEqual((self.root / "template-manifest.json").read_bytes(), ledger)

    def test_external_links_and_shared_ancestors_are_rejected(self):
        for location in ("leaf", "skills", "host", "archive", "canonical", "internal-view"):
            with self.subTest(location=location):
                root = self.root / location
                root.mkdir()
                canonical = seed(root)
                ledger = (root / "template-manifest.json").read_bytes()
                external = self.root / (location + "-external")
                external.mkdir()
                (external / "sentinel").write_text("outside")
                if location == "leaf":
                    (canonical / "unsafe").symlink_to(external)
                elif location == "skills":
                    (root / ".agents/skills").unlink()
                    (root / ".agents/skills").symlink_to(external)
                elif location == "host":
                    (root / ".agents/skills").unlink()
                    (root / ".agents").rmdir()
                    (root / ".agents").symlink_to(external)
                elif location == "archive":
                    (root / ".claude/retired-skills").symlink_to(external)
                elif location == "internal-view":
                    (root / ".agents/skills").unlink()
                    (root / ".agents/skills").mkdir()
                    (root / ".agents/skills/cs-legal-research").symlink_to("../../.claude/skills/cs-legal-research")
                else:
                    shutil.rmtree(canonical)
                    canonical.symlink_to(external)
                with self.assertRaisesRegex(OSError, "Unsafe"):
                    pi.retire_legal_research(root)
                self.assertEqual((external / "sentinel").read_text(), "outside")
                self.assertEqual((root / "template-manifest.json").read_bytes(), ledger)

    def test_init_and_update_stop_before_ledger_mutation_on_archive_failure(self):
        from cs import project_update
        seed(self.root, copied=True, edited=True)
        before = snapshot(self.root)
        with patch.object(pi.shutil, "copytree", side_effect=OSError("archive unavailable")):
            ok, checksums = pi.render_templates({}, ROOT / "cs/templates/project", self.root)
            self.assertFalse(ok)
            self.assertEqual(checksums, {})
            previous = Path.cwd()
            try:
                os.chdir(self.root)
                self.assertEqual(project_update.cmd_update([]), 1)
            finally:
                os.chdir(previous)
        after = snapshot(self.root)
        for rel, data in before.items():
            self.assertEqual(after[rel], data)

    def test_source_has_only_thin_route(self):
        templates = ROOT / "cs/templates/project"
        self.assertFalse(any((templates / ".claude/skills/cs-legal-research").rglob("*.j2")))
        self.assertTrue((templates / ".claude/skills/cs-engine-workflow/SKILL.md.j2").is_file())
        for rel in ("AGENTS.md.j2", ".claude/skills/cs-help/SKILL.md.j2"):
            text = (templates / rel).read_text()
            self.assertNotIn("cs-legal-research", text)
            self.assertIn("cs-engine-workflow", text)


if __name__ == "__main__":
    unittest.main()
