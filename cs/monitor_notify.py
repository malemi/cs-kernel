"""Fixed-owner operational notice service and independent durable recipient.

Run directly with ``python -m cs.monitor_notify --config PRIVATE_JSON``.
The loopback listener requires a bounded authenticated TLS reverse proxy.
"""

from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
from urllib.parse import parse_qs, urlsplit

from .monitor_notify_config import NotifyConfig, load
from .monitor_notify_io import Subscriber, UPSTREAM, publish
from .monitor_notify_protocol import summary
from .monitor_notify_store import Inbox


class NotifyServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, config: NotifyConfig, *, base: str = UPSTREAM):
        self.config, self.base = config, base
        self.token = config.credential(config.token_env)
        self.inbox = Inbox(config.state_dir, config.owner_uid, config.monitor_id)
        self.slots = threading.BoundedSemaphore(8)
        self.subscriber = Subscriber(config, base=base) if config.backend == "ntfy" else None
        super().__init__(("127.0.0.1", config.port), NotifyHandler)
        if self.subscriber:
            self.subscriber.start()

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

    def server_close(self):
        if self.subscriber:
            self.subscriber.stop_event.set()
        super().server_close()


class NotifyHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(1)
        self.timer = threading.Timer(10 if self.server.config.backend == "smtp" else 3, self._expire)
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

    def log_message(self, *args):
        pass

    def reply(self, status: int, value: dict):
        raw = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def authenticated(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.token
        if len(supplied) > 300 or not hmac.compare_digest(supplied.encode(), expected.encode()):
            self.reply(401, {"error": "notification_authentication_required"})
            return False
        return True

    def do_POST(self):
        if not self.authenticated():
            return
        try:
            if self.path != "/alerts" or self.headers.get("Transfer-Encoding"):
                raise ValueError("Invalid notification route")
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 262144:
                raise ValueError("Notification input limit")
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Incomplete notification")
            item = summary(self.server.config, json.loads(raw))
            result = publish(self.server.config, item, base=self.server.base)
            self.reply(200 if result.get("accepted") is True else 503, result)
        except (ValueError, TypeError, KeyError):
            self.reply(400, {"error": "invalid_notification"})
        except Exception:
            self.reply(503, {"error": "notification_unconfirmed"})

    def do_GET(self):
        if not self.authenticated():
            return
        try:
            if len(self.path) > 256:
                raise ValueError("Notification query limit")
            route = urlsplit(self.path)
            query = parse_qs(route.query, max_num_fields=1, keep_blank_values=True)
            if (
                route.path != "/inbox"
                or set(query) - {"nonce"}
                or any(len(v) != 1 for v in query.values())
            ):
                raise ValueError("Invalid notification query")
            value = self.server.inbox.view(query.get("nonce", [None])[0])
            value.update(
                monitor_id=self.server.config.monitor_id,
                backend=self.server.config.backend,
                subscriber_connected=bool(
                    self.server.subscriber and self.server.subscriber.connected.is_set()
                ),
                diagnostic_action="Inspect cs logs health and the matching trace; do not resend uncertain work",
            )
            self.reply(200, value)
        except (ValueError, TypeError, KeyError):
            self.reply(400, {"error": "invalid_notification_query"})
        except Exception:
            self.reply(503, {"error": "notification_inbox_unavailable"})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    try:
        server = NotifyServer(load(args.config))
        try:
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except Exception:
        print(
            "Notification delivery unavailable; inspect private configuration and recipient health"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
