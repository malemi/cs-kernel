"""Bounded fixed-route proxy for two owner-bound loopback monitoring services."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import socket
import threading
from urllib.parse import urlsplit

LIMIT = 262144


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, *, watchdog_port=8127, notify_port=8130):
        self.watchdog_port, self.notify_port = watchdog_port, notify_port
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, ProxyHandler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class ProxyHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(2)
        self.timer = threading.Timer(5, self._expire)
        self.timer.daemon = True
        self.timer.start()

    def _expire(self):
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def finish(self):
        self.timer.cancel()
        try:
            super().finish()
        except OSError:
            pass

    def log_message(self, *_args):
        pass

    def _reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _forward(self):
        connection = None
        try:
            route = urlsplit(self.path)
            ports = {
                "/heartbeat": self.server.watchdog_port,
                "/status": self.server.watchdog_port,
                "/events": self.server.watchdog_port,
                "/alerts": self.server.notify_port,
                "/inbox": self.server.notify_port,
            }
            allowed = {"POST": {"/heartbeat", "/alerts"}, "GET": {"/status", "/events", "/inbox"}}
            if (
                len(self.path) > 4096
                or route.scheme
                or route.netloc
                or route.fragment
                or route.path not in allowed[self.command]
                or self.command == "POST"
                and route.query
            ):
                self._reply(404, b'{"error":"unknown_route"}')
                return
            token = self.headers.get("Authorization", "")
            if len(token) > 300 or not token.startswith("Bearer "):
                self._reply(401, b'{"error":"authentication_required"}')
                return
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Unsupported framing")
            size = self.headers.get("Content-Length", "0")
            if not size.isdecimal() or len(size) > 7 or int(size) > LIMIT:
                raise ValueError("Invalid request size")
            size = int(size)
            if self.command == "GET" and size:
                raise ValueError("Unexpected body")
            body = self.rfile.read(size)
            if len(body) != size:
                raise ValueError("Incomplete body")
            connection = http.client.HTTPConnection("127.0.0.1", ports[route.path], timeout=4)
            connection.request(
                self.command,
                self.path,
                body=body,
                headers={"Authorization": token, "Content-Type": "application/json"},
            )
            response = connection.getresponse()
            result = response.read(LIMIT + 1)
            if len(result) > LIMIT:
                raise ValueError("Response limit")
            # Only JSON responses from the fixed services may leave this boundary.
            value = json.loads(result)
            if not isinstance(value, dict):
                raise ValueError("Invalid response")
            self._reply(response.status, result)
        except Exception:
            try:
                self._reply(503, b'{"error":"monitoring_route_unavailable"}')
            except OSError:
                pass
        finally:
            if connection:
                connection.close()

    do_GET = _forward
    do_POST = _forward


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--watchdog-port", type=int, default=8127)
    parser.add_argument("--notify-port", type=int, default=8130)
    args = parser.parse_args(argv)
    server = ProxyServer(
        (args.listen, args.port), watchdog_port=args.watchdog_port, notify_port=args.notify_port
    )
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
