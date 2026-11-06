"""Connector archives run the bundled executable without exposing workspace files."""

from pathlib import Path
import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cs.desktop_packages import export_packages


class PackagesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="operator packages ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "company workspace"
        self.workspace.mkdir()
        (self.workspace / ".env").write_text("TOKEN=workspace-secret\n")
        (self.workspace / ".cs-desktop.json").write_text('{"descriptor":"private-descriptor"}')
        self.runtime = self.root / "candidate runtime"
        self.runtime.write_text("#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
        self.runtime.chmod(0o755)

    def export(self, provider, filename=None):
        path = self.root / (filename or ("operator.mcpb" if provider == "claude" else "operator.zip"))
        result = export_packages(self.workspace, self.runtime, provider, path)
        self.assertEqual(result["acceptance"], "unverified")
        self.assertEqual(result["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        return path

    def test_manifests_launch_bundled_runtime_after_original_removed(self):
        for provider in ("claude", "chatgpt"):
            with self.subTest(provider=provider):
                artifact = self.export(provider)
                unpack = self.root / (provider + " installed with spaces")
                unpack.mkdir()
                with zipfile.ZipFile(artifact) as archive:
                    self.assertTrue(all(not n.startswith("/") and ".." not in Path(n).parts for n in archive.namelist()))
                    self.assertFalse(any(".env" in n or "desktop.json" in n for n in archive.namelist()))
                    self.assertNotIn(b"workspace-secret", b"".join(archive.read(n) for n in archive.namelist()))
                    archive.extractall(unpack)
                    if provider == "claude":
                        manifest = json.loads(archive.read("manifest.json"))
                        self.assertEqual(manifest["manifest_version"], "0.3")
                        self.assertEqual(manifest["server"]["type"], "binary")
                        self.assertEqual(manifest["compatibility"]["platforms"], [sys.platform])
                        config = manifest["server"]["mcp_config"]
                        token = "${__dirname}"
                    else:
                        manifest = json.loads(archive.read("plugin.json"))
                        self.assertEqual(manifest["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
                        config = json.loads(archive.read("mcp.json"))["mcpServers"]["company-operator"]
                        self.assertEqual(config["type"], "stdio")
                        token = "${PLUGIN_ROOT}"
                    executable = Path(config["command"].replace(token, str(unpack)))
                    mode = archive.getinfo(str(executable.relative_to(unpack))).external_attr >> 16
                    self.assertTrue(mode & stat.S_IXUSR)
                    executable.chmod(mode & 0o777)
                original = self.runtime.with_suffix(".removed")
                self.runtime.rename(original)
                try:
                    ran = subprocess.run([str(executable), *config["args"]], capture_output=True, text=True, check=True, cwd=self.root)
                finally:
                    original.rename(self.runtime)
                self.assertEqual(json.loads(ran.stdout), ["mcp", "--workspace", str(self.workspace)])

    def test_packages_bind_each_workspace_without_copying_its_data(self):
        other = self.root / "other company workspace"
        other.mkdir()
        (other / "private-mail.txt").write_text("other-company-secret")
        artifact = self.root / "other.zip"
        export_packages(other, self.runtime, "chatgpt", artifact)
        with zipfile.ZipFile(artifact) as archive:
            config = json.loads(archive.read("mcp.json"))["mcpServers"]["company-operator"]
            self.assertEqual(config["args"], ["mcp", "--workspace", str(other)])
            self.assertNotIn(str(self.workspace), archive.read("mcp.json").decode())
            self.assertNotIn(b"other-company-secret", b"".join(archive.read(n) for n in archive.namelist()))

    def test_deterministic_and_no_overwrite(self):
        one = self.export("claude")
        two = self.export("claude", "second.mcpb")
        self.assertEqual(one.read_bytes(), two.read_bytes())
        with self.assertRaises(ValueError):
            export_packages(self.workspace, self.runtime, "claude", one)
        self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_rejects_symlinks_traversal_variables_and_workspace_output(self):
        alias = self.root / "alias"
        alias.symlink_to(self.workspace, target_is_directory=True)
        paths = [alias, self.root / ".." / self.root.name / self.workspace.name,
                 Path("relative"), self.root / "${HOME}"]
        paths[-1].mkdir()
        for workspace in paths:
            with self.subTest(path=workspace), self.assertRaises(ValueError):
                export_packages(workspace, self.runtime, "claude", self.root / "bad.mcpb")
        with self.assertRaises(ValueError):
            export_packages(self.workspace, self.runtime, "claude", self.workspace / "bad.mcpb")
        linked_runtime = self.root / "linked-runtime"
        linked_runtime.symlink_to(self.runtime)
        with self.assertRaises(ValueError):
            export_packages(self.workspace, linked_runtime, "claude", self.root / "bad.mcpb")
        outside = self.root / "outside"
        outside.mkdir()
        link_dir = self.root / "link-dir"
        link_dir.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            export_packages(self.workspace, self.runtime, "claude", link_dir / "bad.mcpb")

    def test_invalid_provider_extension_and_nonexecutable(self):
        for provider, extension in (("unknown", ".zip"), ("claude", ".zip"), ("chatgpt", ".mcpb")):
            with self.assertRaises(ValueError):
                export_packages(self.workspace, self.runtime, provider, self.root / ("bad" + extension))
        self.runtime.chmod(0o600)
        with self.assertRaises(ValueError):
            export_packages(self.workspace, self.runtime, "claude", self.root / "bad.mcpb")


if __name__ == "__main__":
    unittest.main()
