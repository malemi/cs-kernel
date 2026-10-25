"""Fixed reverse-proxy prefixes preserve separate owner-bound watchdog routes."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from cs.monitor_config import Component, Endpoint, MonitorConfig
from cs.monitor_transport import _get
from cs.config import observability_credential
from types import SimpleNamespace
from pathlib import Path


class PrefixTests(unittest.TestCase):
    def test_config_accepts_fixed_prefix_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            values = dict(
                monitor_id="a" * 32,
                owner_uid="owner",
                state_dir=temp,
                expected_start_utc=1,
                components=[Component(id="operator", kind="kernel", local_root=temp)],
            )
            for path in ("/heartbeat", "/_ops/" + "a" * 32 + "/heartbeat"):
                config = MonitorConfig(
                    **values,
                    watchdog=Endpoint(url="https://watch.invalid" + path, token_env="WATCH"),
                )
                self.assertTrue(config.watchdog.url.endswith("/heartbeat"))
            for path in ("/../heartbeat", "/x//heartbeat", "/x/%2e/heartbeat", "/elsewhere"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    MonitorConfig(
                        **values,
                        watchdog=Endpoint(url="https://watch.invalid" + path, token_env="WATCH"),
                    )

    def test_actual_get_preserves_prefix_for_status_and_event_reads(self):
        paths = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                paths.append((self.path, self.headers.get("Authorization")))
                body = json.dumps({"status": "observed"}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        endpoint = Endpoint.model_construct(
            url=f"http://127.0.0.1:{server.server_port}/_ops/owner/heartbeat", token_env="WATCH"
        )
        with patch.dict(os.environ, {"WATCH": "x" * 32}):
            for view in ("status", "events"):
                thread = threading.Thread(target=server.handle_request, daemon=True)
                thread.start()
                self.assertEqual(_get(endpoint, view, {"limit": 2})["status"], "observed")
                thread.join(3)
                self.assertFalse(thread.is_alive())
        self.assertEqual(
            paths,
            [
                ("/_ops/owner/status?limit=2", "Bearer " + "x" * 32),
                ("/_ops/owner/events?limit=2", "Bearer " + "x" * 32),
            ],
        )

    def test_selected_clone_credential_reaches_wire_without_ambient_export(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.headers.get('Authorization'))
                raw=b'{"status":"observed"}'
                self.send_response(200);self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        self.addCleanup(server.server_close)
        endpoint=Endpoint.model_construct(url=f'http://127.0.0.1:{server.server_port}/heartbeat',token_env='WATCH')
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            for label in ('a','b'):
                path=Path(temp)/(label+'.env');path.write_text('WATCH='+label*32+'\n');path.chmod(0o600)
                settings=SimpleNamespace(_connection_env_files=(str(path),),observability=SimpleNamespace(reader_token_env='READER'))
                credential=observability_credential(settings,credential_env='WATCH')
                thread=threading.Thread(target=server.handle_request,daemon=True);thread.start()
                self.assertEqual(_get(endpoint,'events',{},credential)['status'],'observed')
                thread.join(3);self.assertFalse(thread.is_alive())
                self.assertNotIn('WATCH',os.environ)
        self.assertEqual(received,['Bearer '+'a'*32,'Bearer '+'b'*32])
