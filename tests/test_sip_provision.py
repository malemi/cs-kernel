"""Provisioning against a stateful HTTP server, never a live provider account."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from cs.config import ConfigError, load
from cs.sip_provision import allow_ip, provision
from cs.vonage import Client


APP = "11111111-1111-4111-8111-111111111111"
OTHER_APP = "22222222-2222-4222-8222-222222222222"
KERNEL_ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "alpha-sip"
USER = "pbx-user"


class SIPFixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        size = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(size)) if size else None
        server = self.server
        server.calls.append((self.command, self.path, body))
        status, result = 200, {}
        domain_path = "/v1/psip/" + DOMAIN
        if self.command == "GET" and self.path == "/v2/applications/" + APP:
            result = {"id": APP, "name": "Trial voice app", "capabilities": {"voice": {}}}
        elif self.command == "GET" and self.path == domain_path:
            server.domain_reads += 1
            if server.domain_reads == server.pause_on_read:
                server.pause_path.touch()
            if server.race_domain is not None and server.domain_reads == 2:
                server.domain = dict(server.race_domain)
            if server.domain is None:
                status = 404
            else:
                result = dict(server.domain)
                if server.corrupt_readback and server.mutated:
                    result["acl"] = []
        elif self.command == "GET" and self.path == domain_path + "/users":
            result = list(server.users)
        elif self.command == "POST" and self.path == "/v1/psip/":
            if server.conflict:
                status, result = 409, {"secret": "error-secret-not-for-logs"}
            else:
                server.domain = dict(body)
                server.mutated = True
                status, result = 201, dict(body)
        elif self.command == "POST" and self.path == domain_path + "/users":
            if server.fail_user:
                status, result = 500, {"secret": body["secret"]}
            else:
                server.users.append({"key": body["key"], "domain": DOMAIN, "secret": body["secret"]})
                status, result = 201, server.users[-1]
        elif self.command == "PUT" and self.path == domain_path:
            server.domain.update(body)
            server.mutated = True
            result = dict(server.domain)
        else:
            status, result = 404, {"error": "unexpected fixture request"}
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    do_GET = handle_request
    do_POST = handle_request
    do_PUT = handle_request


class SIPProvisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        old_cwd = Path.cwd()
        self.addCleanup(os.chdir, old_cwd)
        os.chdir(self.repo)
        env = patch.dict(os.environ, {"HOME": str(self.home)}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        (self.repo / "manifest.toml").write_text(
            '[company]\nslug="alpha"\n[connections.vonage]\nenabled=true\n'
            'api_key_env="ALPHA_KEY"\napi_secret_env="ALPHA_SECRET"\n'
            f'application_ids=["{APP}"]\nregion="eu"\n')
        self.settings = load()
        self.settings.state_dir.mkdir(mode=0o700)
        self.secret_file = self.settings.state_dir / "sip-credentials.json"
        tty = patch("sys.stdin.isatty", return_value=True)
        tty.start()
        self.addCleanup(tty.stop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SIPFixture)
        self.server.calls = []
        self.server.domain = None
        self.server.users = []
        self.server.fail_user = False
        self.server.conflict = False
        self.server.corrupt_readback = False
        self.server.mutated = False
        self.server.domain_reads = 0
        self.server.race_domain = None
        self.server.pause_on_read = None
        self.server.pause_path = self.settings.pause_path
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.client = Client("fixture-key", "fixture-secret")
        self.addCleanup(self.client._session.close)
        request = self.client._session.request
        self.client._session.request = lambda method, url, **kw: request(
            method, url.replace("https://api.nexmo.com", f"http://127.0.0.1:{self.server.server_port}"), **kw)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def provision(self, **kwargs):
        params = dict(name=DOMAIN, app_id=APP, ips=["8.8.8.8"], username=USER,
                      secret_file=str(self.secret_file), commit=False)
        params.update(kwargs)
        return provision(self.client, self.settings, **params)

    def writes(self):
        return [call for call in self.server.calls if call[0] != "GET"]

    def existing_domain(self):
        self.server.domain = {
            "name": DOMAIN, "application_id": APP, "domain_type": "app",
            "digest_auth": True, "acl": ["8.8.8.8/32"], "tls": "always", "srtp": "always",
        }

    def test_preview_has_no_secret_file_or_http_writes(self):
        before = set(self.settings.state_dir.iterdir())
        with patch("cs.sip_provision.secrets.token_urlsafe", side_effect=AssertionError("preview generated a secret")):
            result = self.provision()
        self.assertIsInstance(result, dict)
        self.assertEqual(set(self.settings.state_dir.iterdir()), before)
        self.assertFalse(self.writes())
        self.assertIsNone(self.server.domain)
        self.assertNotIn("fixture-secret", json.dumps(result))

    def test_success_creates_domain_then_user_and_verifies_both(self):
        result = self.provision(commit=True)
        writes = self.writes()
        self.assertEqual([(c[0], c[1]) for c in writes], [
            ("POST", "/v1/psip/"), ("POST", "/v1/psip/" + DOMAIN + "/users")])
        self.assertEqual(self.server.domain["application_id"], APP)
        self.assertTrue(self.server.domain["digest_auth"])
        self.assertEqual(self.server.domain["acl"], ["8.8.8.8/32"])
        self.assertEqual(self.server.users[0]["key"], USER)
        password = writes[1][2]["secret"]
        self.assertGreaterEqual(len(password), 16)
        self.assertIn(password, self.secret_file.read_text())
        self.assertEqual(stat.S_IMODE(self.secret_file.stat().st_mode), 0o600)
        self.assertNotIn(password, json.dumps(result))
        self.assertIn(("GET", "/v1/psip/" + DOMAIN + "/users", None), self.server.calls)
        self.assertEqual(self.server.calls[-1][0], "GET")

    def test_existing_domain_refuses_even_with_same_inputs(self):
        self.existing_domain()
        for commit in (False, True):
            with self.subTest(commit=commit), self.assertRaises(ConfigError):
                self.provision(commit=commit)
        self.assertFalse(self.writes())
        self.assertFalse(self.secret_file.exists())

    def test_partial_user_failure_keeps_recovery_secret_and_does_not_retry(self):
        self.server.fail_user = True
        with self.assertRaises(ConfigError) as caught:
            self.provision(commit=True)
        self.assertIsNotNone(self.server.domain)
        self.assertEqual(len(self.writes()), 2)
        password = self.writes()[1][2]["secret"]
        self.assertIn(password, self.secret_file.read_text())
        self.assertNotIn(password, str(caught.exception))
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertEqual(len(self.writes()), 2)

    def test_conflict_does_not_retry_or_create_user(self):
        self.server.conflict = True
        with self.assertRaises(ConfigError) as caught:
            self.provision(commit=True)
        self.assertEqual(len(self.writes()), 1)
        self.assertFalse(self.server.users)
        self.assertNotIn("error-secret-not-for-logs", str(caught.exception))

    def test_domain_appearing_during_preflight_refuses_before_secret_creation(self):
        self.existing_domain()
        self.server.race_domain = self.server.domain
        self.server.domain = None
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertFalse(self.writes())
        self.assertFalse(self.secret_file.exists())

    def test_readback_mismatch_is_failure(self):
        self.server.corrupt_readback = True
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertTrue(self.secret_file.exists())

    def test_unknown_application_refuses_before_remote_or_local_writes(self):
        with self.assertRaises(ConfigError):
            self.provision(app_id=OTHER_APP, commit=True)
        self.assertFalse(self.server.calls)
        self.assertFalse(self.secret_file.exists())

    def test_private_reserved_ipv6_and_mixed_cidrs_are_rejected(self):
        for ip in ("10.0.0.1", "127.0.0.1", "192.0.2.1", "0.0.0.0/0", "8.0.0.0/6", "::1", "8.8.8.8;bad"):
            with self.subTest(ip=ip), self.assertRaises(ConfigError):
                self.provision(ips=[ip], commit=True)
        self.assertFalse(self.writes())
        self.assertFalse(self.secret_file.exists())

    def test_secret_file_exclusive_private_and_inside_state_dir(self):
        self.secret_file.write_text("existing-secret")
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertEqual(self.secret_file.read_text(), "existing-secret")
        self.secret_file.unlink()
        outside = self.root / "outside.json"
        for commit in (False, True):
            with self.subTest(commit=commit), self.assertRaises(ConfigError):
                self.provision(secret_file=str(outside), commit=commit)
        self.assertFalse(outside.exists())
        self.settings.state_dir.chmod(0o755)
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertFalse(self.writes())

    def test_secret_symlink_is_rejected(self):
        target = self.root / "target"
        target.write_text("keep")
        self.secret_file.symlink_to(target)
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertEqual(target.read_text(), "keep")
        self.assertFalse(self.writes())

    def test_headless_noninteractive_and_pause_refuse_mutation(self):
        for flag in ("CS_OPERATOR_HEADLESS", "CS_HEADLESS_SEND"):
            with self.subTest(flag=flag), patch.dict(os.environ, {flag: "1"}), self.assertRaises(ConfigError):
                self.provision(commit=True)
        with patch("sys.stdin.isatty", return_value=False), self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.settings.pause_path.touch()
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertFalse(self.writes())
        self.assertFalse(self.secret_file.exists())

    def test_pause_arriving_during_preflight_blocks_secret_and_remote_writes(self):
        self.server.pause_on_read = 1
        with self.assertRaises(ConfigError):
            self.provision(commit=True)
        self.assertFalse(self.writes())
        self.assertFalse(self.secret_file.exists())

    def test_pause_after_domain_creation_preserves_recovery_without_user_post(self):
        self.server.pause_on_read = 3
        with self.assertRaises(ConfigError) as caught:
            self.provision(commit=True)
        self.assertEqual([(c[0], c[1]) for c in self.writes()], [("POST", "/v1/psip/")])
        self.assertTrue(self.secret_file.exists())
        self.assertFalse(self.server.users)
        self.assertIn("partial", str(caught.exception))

    def test_pause_arriving_during_acl_preflight_blocks_put(self):
        self.existing_domain()
        self.server.pause_on_read = 1
        with self.assertRaises(ConfigError):
            allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        self.assertFalse(self.writes())

    def test_acl_update_preserves_all_other_domain_settings_and_verifies(self):
        self.existing_domain()
        before = dict(self.server.domain)
        preview = allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=False)
        self.assertIsInstance(preview, dict)
        self.assertEqual(self.server.domain, before)
        self.assertFalse(self.writes())
        result = allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][0], "PUT")
        self.assertEqual(self.server.domain["acl"], ["8.8.8.8/32", "1.1.1.1/32"])
        for field, value in before.items():
            if field != "acl":
                self.assertEqual(self.server.domain[field], value)
        self.assertEqual(self.server.calls[-1], ("GET", "/v1/psip/" + DOMAIN, None))
        self.assertFalse(self.secret_file.exists())

    def test_acl_open_to_world_or_incomplete_domain_refuses(self):
        self.existing_domain()
        self.server.domain["acl"] = ["0.0.0.0/0"]
        with self.assertRaises(ConfigError):
            allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        for field in ("digest_auth", "application_id", "tls", "srtp", "acl", "domain_type"):
            self.existing_domain()
            del self.server.domain[field]
            with self.subTest(field=field), self.assertRaises(ConfigError):
                allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        self.assertFalse(self.writes())

    def test_acl_readback_failure_surfaces_after_one_put(self):
        self.existing_domain()
        self.server.corrupt_readback = True
        with self.assertRaises(ConfigError):
            allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        self.assertEqual(len(self.writes()), 1)

    def test_acl_changed_during_preflight_is_not_overwritten(self):
        self.existing_domain()
        self.server.race_domain = {**self.server.domain, "acl": ["9.9.9.9/32"]}
        with self.assertRaises(ConfigError):
            allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        self.assertFalse(self.writes())
        self.assertEqual(self.server.domain["acl"], ["9.9.9.9/32"])

    def test_acl_duplicate_is_verified_without_a_put(self):
        self.existing_domain()
        result = allow_ip(self.client, self.settings, name=DOMAIN, ips=["8.8.8.8"], commit=True)
        self.assertFalse(result["changed"])
        self.assertFalse(self.writes())

    def test_acl_update_also_refuses_headless_and_unknown_application(self):
        self.existing_domain()
        with patch.dict(os.environ, {"CS_OPERATOR_HEADLESS": "1"}), self.assertRaises(ConfigError):
            allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        self.server.domain["application_id"] = OTHER_APP
        with self.assertRaises(ConfigError):
            allow_ip(self.client, self.settings, name=DOMAIN, ips=["1.1.1.1"], commit=True)
        self.assertFalse(self.writes())

    def test_cli_headless_commits_refuse_before_network_and_secret_creation(self):
        # Audit hook proves the real CLI never reaches socket.connect, and
        # also prevents this test from reaching the public provider on failure.
        (self.repo / "sitecustomize.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "def audit(event, args):\n"
            "    if event == 'socket.connect':\n"
            "        Path('network-attempted').touch()\n"
            "        raise RuntimeError('test forbids external sockets')\n"
            "sys.addaudithook(audit)\n")
        env = dict(os.environ, ALPHA_KEY="fixture-key", ALPHA_SECRET="fixture-secret",
                   CS_OPERATOR_HEADLESS="1", PYTHONPATH=str(self.repo) + os.pathsep + str(KERNEL_ROOT))
        commands = [
            ["connection", "vonage", "provision", DOMAIN, "--application", APP,
             "--ip", "8.8.8.8", "--username", USER, "--secret-file", str(self.secret_file), "--commit"],
            ["connection", "vonage", "allow-ip", DOMAIN, "--ip", "1.1.1.1", "--commit"],
        ]
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, "-m", "cs", *command],
                                        capture_output=True, text=True, env=env, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("headless", result.stderr)
                self.assertNotIn("fixture-secret", result.stdout + result.stderr)
                self.assertFalse((self.repo / "network-attempted").exists())
                self.assertFalse(self.secret_file.exists())


if __name__ == "__main__":
    unittest.main()
