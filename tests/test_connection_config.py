"""Per-clone provider bindings, literal secret resolution and safe inspection."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs.config import ConfigError, connection_credentials, load
from cs.config_report import build, render
from cs.manifest import ManifestError


APP_A = "11111111-1111-4111-8111-111111111111"
APP_B = "22222222-2222-4222-8222-222222222222"


class ConnectionConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.old_cwd = Path.cwd()
        self.addCleanup(os.chdir, self.old_cwd)
        self.env = patch.dict(os.environ, {"HOME": str(self.home)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def clone(self, slug="alpha", binding=None):
        path = self.root / slug
        path.mkdir(exist_ok=True)
        platform = path / "platform.env"
        platform.touch()
        text = f'[company]\nslug = "{slug}"\n[env]\nplatform_env_path = "{platform}"\n'
        if binding is not None:
            text += "[connections.vonage]\n" + binding + "\n"
        (path / "manifest.toml").write_text(text)
        os.chdir(path)
        return path

    def binding(self, prefix="ALPHA", app=APP_A):
        return (f'enabled = true\napi_key_env = "{prefix}_KEY"\n'
                f'api_secret_env = "{prefix}_SECRET"\napplication_ids = ["{app}"]')

    def test_two_clones_remain_isolated_across_cwd_and_loads(self):
        os.environ.update(VONAGE_API_KEY="wrong-generic", VONAGE_API_SECRET="wrong-secret")
        alpha = self.clone(binding=self.binding())
        (alpha / "platform.env").write_text("ALPHA_KEY=platform-key\nALPHA_SECRET=platform-secret\n")
        home_env = self.home / ".alpha-cs"
        home_env.mkdir()
        (home_env / ".env").write_text("ALPHA_KEY=home-key\nALPHA_SECRET=home-secret\n")
        (alpha / ".env").write_text("ALPHA_KEY=repo-key\n")
        first = load()
        self.assertEqual(connection_credentials(first), ("repo-key", "home-secret"))
        beta = self.clone("beta", self.binding("BETA", APP_B))
        (beta / ".env").write_text("BETA_KEY=beta-key\nBETA_SECRET=beta-secret\n")
        second = load()
        self.assertEqual(connection_credentials(second), ("beta-key", "beta-secret"))
        self.assertEqual(connection_credentials(first), ("repo-key", "home-secret"))
        os.environ["ALPHA_KEY"] = "process-key"
        self.assertEqual(connection_credentials(first), ("process-key", "home-secret"))
        self.assertEqual(first.connections.vonage.application_ids, [APP_A])
        self.assertEqual(second.connections.vonage.application_ids, [APP_B])

    def test_disabled_ignores_ambient_bindings_and_credentials(self):
        path = self.clone()
        os.environ.update(CONNECTIONS="not even JSON", VONAGE_API_KEY="ambient", VONAGE_API_SECRET="ambient")
        (path / ".env").write_text('CONNECTIONS={"vonage":{"enabled":true}}\n')
        settings = load()
        self.assertFalse(settings.connections.vonage.enabled)
        with self.assertRaisesRegex(ConfigError, "disabled"):
            connection_credentials(settings)
        report = json.dumps(build(settings, include_all=True))
        self.assertNotIn("not even JSON", report)
        self.assertNotIn("ambient", report)

    def test_enabled_binding_cannot_be_overridden_by_ambient_json(self):
        self.clone(binding=self.binding())
        os.environ["CONNECTIONS"] = json.dumps({"vonage": {
            "enabled": False, "api_key_env": "OTHER_KEY", "application_ids": [APP_B]}})
        settings = load()
        self.assertTrue(settings.connections.vonage.enabled)
        self.assertEqual(settings.connections.vonage.api_key_env, "ALPHA_KEY")
        self.assertEqual(settings.connections.vonage.application_ids, [APP_A])

    def test_missing_or_empty_secret_never_falls_back(self):
        path = self.clone(binding=self.binding())
        os.environ.update(VONAGE_API_KEY="generic", VONAGE_API_SECRET="generic")
        with self.assertRaisesRegex(ConfigError, "ALPHA_KEY"):
            connection_credentials(load())
        (path / "platform.env").write_text("ALPHA_KEY=platform-key\nALPHA_SECRET=platform-secret\n")
        (path / ".env").write_text("ALPHA_SECRET=\n")
        with self.assertRaisesRegex(ConfigError, "ALPHA_SECRET"):
            connection_credentials(load())

    def test_literal_secret_is_not_interpolated(self):
        path = self.clone(binding=self.binding())
        os.environ["OTHER_SECRET"] = "must-not-inherit"
        (path / ".env").write_text("ALPHA_KEY=key\nALPHA_SECRET='literal-${OTHER_SECRET}'\n")
        self.assertEqual(connection_credentials(load()), ("key", "literal-${OTHER_SECRET}"))

    def test_invalid_bindings_fail_without_echoing_input(self):
        cases = [
            'enabled = "true"',
            'enabled = true',
            self.binding() + '\nregion = "invalid"',
            self.binding().replace(APP_A, "not-a-uuid"),
            self.binding().replace('"ALPHA_KEY"', '"pasted-sensitive-value"'),
            self.binding() + '\napi_secret = "pasted-sensitive-value"',
            self.binding().replace('"ALPHA_SECRET"', '"ALPHA_KEY"'),
            self.binding().replace(f'["{APP_A}"]', '[]'),
            self.binding().replace(f'["{APP_A}"]', f'["{APP_A}", "{APP_A}"]'),
        ]
        for declaration in cases:
            with self.subTest(declaration=declaration):
                self.clone(binding=declaration)
                with self.assertRaises(ManifestError) as caught:
                    load()
                self.assertNotIn("pasted-sensitive-value", str(caught.exception))

    def test_unknown_provider_is_rejected(self):
        path = self.clone()
        with (path / "manifest.toml").open("a") as stream:
            stream.write('[connections.typo]\nenabled = true\n')
        with self.assertRaises(ManifestError):
            load()

    def test_config_text_json_and_model_never_contain_credentials(self):
        self.clone(binding=self.binding())
        os.environ.update(ALPHA_KEY="private-key-value", ALPHA_SECRET="private-secret-value")
        settings = load()
        connection_credentials(settings)
        report = build(settings, include_all=True)
        text = render(report) + json.dumps(report) + repr(settings) + settings.model_dump_json()
        for secret in ("private-key-value", "private-secret-value"):
            self.assertNotIn(secret, text)
        self.assertIn("ALPHA_KEY", text)
        self.assertIn("ALPHA_SECRET", text)
        connection_row = next(row for row in report["all"] if row["name"] == "connections")
        self.assertEqual(connection_row["layer"], "manifest")
        self.assertNotIn("connections", report["mismatched"])


if __name__ == "__main__":
    unittest.main()
