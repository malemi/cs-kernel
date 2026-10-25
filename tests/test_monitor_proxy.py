"""The deployment proxy forwards only fixed routes to bound owner services."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from cs.monitor_proxy import ProxyServer


class ProxyTests(unittest.TestCase):
    def test_fixed_routes_auth_framing_and_bounded_response(self):
        requests = []

        class Backend(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, self.headers.get("Authorization")))
                if self.path == "/status?slow=1":
                    time.sleep(2.2)
                body = json.dumps({"status": "observed"}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        backend = HTTPServer(("127.0.0.1", 0), Backend)
        proxy = ProxyServer(("127.0.0.1", 0), watchdog_port=backend.server_port)
        for server in (backend, proxy):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 3)
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)

        def read(path, token=True):
            request = urllib.request.Request(
                f"http://127.0.0.1:{proxy.server_port}" + path,
                headers={"Authorization": "Bearer " + "x" * 32} if token else {},
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                return json.load(response)

        self.assertEqual(read("/status?limit=2")["status"], "observed")
        self.assertEqual(requests, [("/status?limit=2", "Bearer " + "x" * 32)])
        for path in ("/../status", "/other", "/events/../status"):
            with self.assertRaises(urllib.error.HTTPError) as error:
                read(path)
            self.assertEqual(error.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as error:
            read("/status", token=False)
        self.assertEqual(error.exception.code, 401)
        self.assertEqual(len(requests), 1)
        # The fixed notification service can validly finish after two seconds;
        # its outer proxy must leave room for that bounded acknowledgement.
        self.assertEqual(read("/status?slow=1")["status"], "observed")
