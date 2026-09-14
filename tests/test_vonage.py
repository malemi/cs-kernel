"""Real local HTTP contract checks; no live account mutations."""
import base64
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cs.vonage import Client, ProviderError


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.calls.append((self.command, self.path, self.headers.get("Authorization")))
        status, body = self.server.reply
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        self.server.calls = []
        self.server.reply = (200, [])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client("fixture-key", "fixture-secret")
        original = self.client._session.request
        # Only the transport URL is redirected to the local fixture. Actual
        # requests, authentication, parsing, status handling all run unchanged.
        self.client._session.request = lambda method, url, **kw: original(
            method, url.replace("https://api.nexmo.com", f"http://127.0.0.1:{self.server.server_port}"), **kw)

    def tearDown(self):
        self.client._session.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_auth_and_redaction(self):
        self.server.reply = (200, [{"name": "trial-domain", "secret": "hidden", "acl": []}])
        self.assertEqual(self.client.domains(), [{"name": "trial-domain", "acl": []}])
        self.assertEqual(self.server.calls[0][2], "Basic " + base64.b64encode(b"fixture-key:fixture-secret").decode())

    def test_http_error_never_echoes_body(self):
        self.server.reply = (401, {"detail": "fixture-secret"})
        with self.assertRaisesRegex(ProviderError, "HTTP 401") as ctx:
            self.client.domains()
        self.assertNotIn("fixture-secret", str(ctx.exception))
        self.assertEqual(len(self.server.calls), 1)

    def test_redirect_refused_and_not_followed(self):
        self.server.reply = (302, {})
        with self.assertRaisesRegex(ProviderError, "HTTP 302"):
            self.client.domains()
        self.assertEqual(len(self.server.calls), 1)

    def test_absence_differs_from_failure(self):
        self.server.reply = (404, {})
        self.assertIsNone(self.client.domain("trial-domain"))
        self.server.reply = (500, {})
        with self.assertRaises(ProviderError):
            self.client.domain("trial-domain")

    def test_empty_success_is_not_absence(self):
        for status, body in ((200, b""), (204, b""), (200, None)):
            with self.subTest(status=status, body=body):
                self.server.reply = (status, body)
                with self.assertRaises(ProviderError):
                    self.client.domain("trial-domain")

    def test_malformed_and_cross_domain_user_refused(self):
        self.server.reply = (200, {"items": []})
        with self.assertRaises(ProviderError):
            self.client.domains()
        self.server.reply = (200, [{"key": "trial", "domain": "other-domain"}])
        with self.assertRaises(ProviderError):
            self.client.users("trial-domain")

    def test_path_injection_stops_before_network(self):
        with self.assertRaises(ProviderError):
            self.client.domain("../../applications")
        self.assertFalse(self.server.calls)


if __name__ == "__main__":
    unittest.main()
