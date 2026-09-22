"""A Shopify fact that is MISSING must never be reported as a value.

The defect this gate exists to prevent (2026-09-22): the adapter read the
order count as ``str(node.get("numberOfOrders") or "0")``. When Shopify
renamed, removed or unscoped that field, ``.get`` returned ``None``, ``None or
"0"`` returned ``"0"``, and a customer with ten orders was reported as having
none — with ``ok=True`` and no note, so no caller could tell "this customer has
never ordered" from "the field moved". The engine parsing the same envelope
fails CLOSED two repositories away; this parser answered anyway.

Semantic, not mock theatre: a local HTTP fixture serves the Admin API envelope
and the adapter runs unchanged — its own URL, headers, GraphQL query, JSON
parse, projection and degradation. Only the transport is redirected, because
Shopify speaks HTTPS and the fixture does not. The rendering assertions go
through ``cs.cli._print_crm_section``, the code the operator actually sees, so
the claim being tested is "the dossier shows a gap", not "a dict lacks a key".
"""
import contextlib
import io
import json
import sys
import threading
import unittest
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cs import cli
from cs.config import Settings
from cs.crm import shopify

# A customer node carrying everything Shopify's schema declares non-null.
# `numberOfOrders: UnsignedInt64!`, `amountSpent: MoneyV2!`,
# `state: CustomerState!`, `tags: [String!]!` — verified against
# https://shopify.dev/docs/api/admin-graphql/latest/objects/Customer (2026-09-22).
FULL_NODE = {
    "id": "gid://shopify/Customer/1",
    "email": "buyer@example.com",
    "firstName": "Ada",
    "lastName": "Lovelace",
    "numberOfOrders": "10",
    "state": "ENABLED",
    "tags": ["vip"],
    "amountSpent": {"amount": "420.00", "currencyCode": "EUR"},
    "lastOrder": {"name": "#1042"},
}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.calls.append({
            "path": self.path,
            "token": self.headers.get("X-Shopify-Access-Token"),
            "body": json.loads(body or b"{}"),
        })
        payload = json.dumps(self.server.reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def envelope(*nodes: dict) -> dict:
    return {"data": {"customers": {"edges": [{"node": n} for n in nodes]}}}


def node_without(field: str) -> dict:
    return {k: v for k, v in FULL_NODE.items() if k != field}


@contextlib.contextmanager
def transport_to(port: int):
    """Redirect ONLY the transport. The adapter still builds its own URL from
    the store domain and API version, sends its own headers and query, and
    parses what comes back; the scheme and host are rewritten on the way out
    because the fixture speaks HTTP and Shopify speaks HTTPS."""
    real = urllib.request.urlopen

    def redirected(req, *args, **kwargs):
        parts = urllib.parse.urlsplit(req.full_url)
        req.full_url = urllib.parse.urlunsplit(
            ("http", f"127.0.0.1:{port}", parts.path, parts.query, parts.fragment))
        return real(req, *args, **kwargs)

    urllib.request.urlopen = redirected
    try:
        yield
    finally:
        urllib.request.urlopen = real


class AbsentIsNotZero(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        self.server.calls = []
        self.server.reply = envelope(FULL_NODE)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.settings = Settings(
            _env_file=(),
            slug="acme",
            prog_name="acme-cs",
            crm_adapter="shopify",
            shopify_store_domain="acme.myshopify.com",
            shopify_admin_token="fixture-admin-token",
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def lookup(self, *nodes: dict):
        self.server.reply = envelope(*nodes)
        with transport_to(self.server.server_port):
            return shopify.lookup(
                shopify.CrmCtx(settings=self.settings, call_rpc=None), "buyer@example.com")

    def render(self, *nodes: dict) -> str:
        """What the operator sees in `cs dossier`, produced by the real one."""
        self.server.reply = envelope(*nodes)
        out = io.StringIO()
        with transport_to(self.server.server_port), contextlib.redirect_stdout(out):
            cli._print_crm_section(self.settings, "buyer@example.com")
        return out.getvalue()

    # --- the regression itself -------------------------------------------

    def test_absent_order_count_is_never_reported_as_zero(self):
        res = self.lookup(node_without("numberOfOrders"))
        facts = res.rows[0].facts
        self.assertNotEqual(
            facts.get("orders"), "0",
            "an absent numberOfOrders was reported as zero orders — the exact "
            "defect this gate exists to prevent; absent is not zero")
        self.assertNotIn(
            "orders", facts,
            "a fact the response did not carry must be OMITTED, not given a value")

    def test_an_absent_required_fact_degrades_the_result(self):
        res = self.lookup(node_without("numberOfOrders"))
        self.assertFalse(
            res.ok, "the answer is not authoritative, so ok must not claim it is")
        self.assertIsNotNone(res.note, "a degraded result carries an actionable note")
        self.assertIn("orders", res.note)

    def test_the_dossier_shows_the_gap_and_never_a_number(self):
        printed = self.render(node_without("numberOfOrders"))
        self.assertIn("orders=", printed)
        self.assertNotIn("orders=0", printed)
        self.assertIn("MISSING, not zero", printed,
                      "the operator must be told the count is absent, not read it as a fact")

    # --- and the other half: a real zero is still a real zero -------------

    def test_a_genuine_zero_stays_zero_and_stays_authoritative(self):
        for raw in ("0", 0):
            with self.subTest(raw=raw):
                res = self.lookup({**FULL_NODE, "numberOfOrders": raw,
                                   "amountSpent": {"amount": "0.00", "currencyCode": "EUR"},
                                   "lastOrder": None})
                self.assertEqual(res.rows[0].facts["orders"], "0")
                self.assertTrue(res.ok, "a customer with no orders is a fact, not a failure")
                self.assertIsNone(res.note)

    def test_a_customer_who_never_ordered_is_not_a_broken_response(self):
        # lastOrder is `Order` — nullable — so its absence is an answer.
        res = self.lookup({**FULL_NODE, "lastOrder": None})
        self.assertTrue(res.ok)
        self.assertIsNone(res.note)
        self.assertEqual(res.rows[0].facts["last_order"], "")

    # --- the same posture for the fields two lines away -------------------

    def test_every_non_null_field_degrades_when_it_goes_missing(self):
        for field, fact in (("numberOfOrders", "orders"), ("amountSpent", "spent"),
                            ("state", "state"), ("tags", "tags")):
            with self.subTest(field=field):
                res = self.lookup(node_without(field))
                self.assertFalse(res.ok, f"a missing {field} must degrade the result")
                self.assertNotIn(fact, res.rows[0].facts)
                self.assertIn(fact, res.note)

    # --- proof the real adapter ran, rather than a stub ------------------

    def test_the_adapter_really_called_the_admin_api(self):
        self.lookup(FULL_NODE)
        call = self.server.calls[-1]
        self.assertEqual(call["path"],
                         f"/admin/api/{self.settings.shopify_api_version}/graphql.json")
        self.assertEqual(call["token"], "fixture-admin-token")
        self.assertIn("numberOfOrders", call["body"]["query"])
        self.assertEqual(call["body"]["variables"], {"q": "email:buyer@example.com"})


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
