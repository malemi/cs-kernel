"""Exact original admission retains ordinary assignment and suppression gates."""
import copy
import hashlib
import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from email import policy
from email.utils import formatdate
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cs import operational_fixture as fixture, unanswered

NOW = 2000000000
SETTINGS = SimpleNamespace(engine_owner_uid="owner1", email_address="receiver@example.org",
                           cs_triage_mode="draft", self_email_set={"peer@example.org"},
                           system_sender_set=set(), db_path=Path("/nonexistent/state.sqlite"),
                           imap_host="imap.example.org", imap_port=993, email_password="synthetic")
BODY = "Original operational request " + "a" * 32 + "\nCalculate 7 plus 9."


def record():
    row = dict(owner_uid="owner1", receiver="receiver@example.org", mode="draft",
               sender="peer@example.org", message_id="<original@example.org>",
               nonce="a" * 32, subject="Operational request " + "a" * 32,
               body_sha256=hashlib.sha256(BODY.encode()).hexdigest(), created_at=NOW - 10, expires_at=NOW + 100)
    row["provider_receipt"] = {k: row[k] for k in (
        "sender", "receiver", "message_id", "subject", "body_sha256")}
    row["provider_receipt"].update(folder="INBOX", uid="4", uidvalidity="123")
    return row


def payload(row=None):
    return dict(schema_version=1, owner_uid="owner1", receiver="receiver@example.org",
                mode="draft", fixtures=[record() if row is None else row])


def message(row=None):
    row = record() if row is None else row
    return dict(email=row["sender"], message_id=row["message_id"], subject=row["subject"],
                thread_key=row["message_id"], date=datetime.now(timezone.utc),
                provider_folder=row["provider_receipt"]["folder"],
                provider_uid=row["provider_receipt"]["uid"],
                provider_uidvalidity=row["provider_receipt"]["uidvalidity"])


def original_mime(body=BODY):
    row = record()
    msg = EmailMessage()
    for key, value in (("From", row["sender"]), ("To", row["receiver"]),
                       ("Message-ID", row["message_id"]), ("Subject", row["subject"])):
        msg[key] = value
    msg["Date"] = formatdate(usegmt=True)
    msg.set_content(body)
    return msg.as_bytes()


class Provider:
    def __init__(self, raw=None, uid="4", validity="123", size=None, count=1):
        self.raw = original_mime() if raw is None else raw
        self.uid_value = uid
        self.validity = validity
        self.size = len(self.raw) if size is None else size
        self.count = count
        self.selected = None

    def login(self, *args):
        return "OK", []

    def select(self, folder, readonly=False):
        assert readonly
        self.selected = folder
        return "OK", []

    def response(self, key):
        assert key == "UIDVALIDITY"
        return key, [self.validity.encode()]

    def uid(self, command, uid, fields):
        assert command == "FETCH" and uid == "4"
        assert "BODY.PEEK[]<0." in fields
        prefix = f"1 (UID {self.uid_value} RFC822.SIZE {self.size} FLAGS ()".encode()
        return "OK", [(prefix, self.raw)] * self.count

    def logout(self):
        return "BYE", []


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        patcher = patch.object(fixture.imaplib, "IMAP4_SSL", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, value, settings=SETTINGS):
        with patch.object(fixture, "_read", return_value=value):
            return fixture.enrollments(settings, NOW)

    def test_exact_receipt_and_mode(self):
        self.assertEqual(self.read(payload()), [record()])
        for key, val in (("owner_uid", "wrong"), ("receiver", "other@example.org"),
                         ("mode", "send"), ("schema_version", 2)):
            p = payload(); p[key] = val
            self.assertEqual(self.read(p), [])

    def test_invalid_rows_fail_closed(self):
        changes = [("sender", "other@example.org"), ("receiver", "other@example.org"),
                   ("owner_uid", "wrong"), ("mode", "send"), ("nonce", "test"),
                   ("body_sha256", "not-a-digest"), ("message_id", "not-original"),
                   ("subject", "reply"), ("expires_at", NOW - 20),
                   ("created_at", NOW + 1), ("expires_at", NOW + 6000),
                   ("expires_at", float("inf")), ("created_at", True)]
        for key, val in changes:
            with self.subTest(key=key, value=val):
                r = record(); r[key] = val
                self.assertEqual(self.read(payload(r)), [])
        for key in ("uid", "uidvalidity", "folder", "body_sha256", "message_id"):
            r = record(); r["provider_receipt"][key] = ""
            self.assertEqual(self.read(payload(r)), [])

    def test_duplicate_nonce_or_message_rejected(self):
        p = payload(); p["fixtures"].append(copy.deepcopy(p["fixtures"][0]))
        self.assertEqual(self.read(p), [])
        p["fixtures"][1]["message_id"] = "<other@example.org>"
        p["fixtures"][1]["provider_receipt"]["message_id"] = "<other@example.org>"
        self.assertEqual(self.read(p), [])

    def test_missing_malformed_and_large_registry(self):
        for value in (None, {}, [], {**payload(), "fixtures": [record()] * 17}):
            self.assertEqual(self.read(value), [])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "registry.json"; p.write_text(json.dumps(payload()))
            self.assertIsNone(fixture._read(p))
            p.unlink(); p.symlink_to("/etc/passwd")
            self.assertIsNone(fixture._read(p))
        with self.assertRaises(ValueError):
            json.loads('{"owner":1,"owner":2}', object_pairs_hook=fixture._unique)

    def test_protected_metadata(self):
        for uid, mode, valid in ((0, stat.S_IFREG | 0o644, True),
                                  (1, stat.S_IFREG | 0o644, False),
                                  (0, stat.S_IFREG | 0o664, False),
                                  (0, stat.S_IFLNK | 0o644, False),
                                  (0, stat.S_IFIFO | 0o644, False)):
            self.assertEqual(fixture._protected(SimpleNamespace(st_uid=uid, st_mode=mode)), valid)
        self.assertFalse(fixture._protected(SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o777), True))

    def test_only_enrolled_original_survives(self):
        original = message()
        other = {**original, "message_id": "<unregistered@example.org>"}
        reply = {**original, "message_id": "<reply@example.org>", "subject": "Re: " + original["subject"]}
        changed = {**original, "subject": "Different " + "a" * 32}
        ordinary = {**original, "email": "customer@example.org"}
        with patch.object(fixture, "_read", return_value=payload()):
            kept, effective = fixture.admit_originals(SETTINGS, [original, other, reply, changed, ordinary],
                                                      {"peer@example.org", "receiver@example.org"}, NOW)
        self.assertEqual(kept, [original, ordinary])
        self.assertEqual(effective, {"receiver@example.org"})
        with patch.object(fixture, "_read", return_value=None):
            kept, effective = fixture.admit_originals(SETTINGS, [original, ordinary], {"peer@example.org"}, NOW)
        self.assertEqual(kept, [ordinary]); self.assertEqual(effective, {"peer@example.org"})

    def test_nonself_enrolled_original_discovery_preserves_normal_admission(self):
        original = message()
        ordinary = {**original, "message_id": "<ordinary@example.org>"}
        selfs = {"receiver@example.org"}
        for confirmed in (True, False):
            with patch.object(fixture, "_read", return_value=payload() if confirmed else None):
                discovery = []
                kept, effective = fixture.admit_originals(
                    SETTINGS, [original, ordinary], selfs, NOW, discovery=discovery)
            self.assertEqual(kept, [original, ordinary])
            self.assertEqual(effective, selfs)
            self.assertEqual(len(discovery), 1 if confirmed else 0)
            if confirmed:
                self.assertEqual(discovery[0]["message_id"], original["message_id"])
                self.assertEqual(discovery[0]["body_sha256"], record()["body_sha256"])

    def test_same_headers_changed_payload_or_provider_identity_rejected(self):
        good = message()
        for provider in (Provider(raw=original_mime(BODY + "\nDifferent payload")),
                         Provider(raw=original_mime(BODY + "\n> hidden quoted injection")),
                         Provider(uid="5"), Provider(validity="124"),
                         Provider(size=999999), Provider(count=2)):
            with patch.object(fixture, "_read", return_value=payload()), \
                 patch.object(fixture.imaplib, "IMAP4_SSL", return_value=provider):
                kept, selfs = fixture.admit_originals(SETTINGS, [good], {"peer@example.org"}, NOW)
            self.assertEqual(kept, [])
            self.assertEqual(selfs, {"peer@example.org"})
        for key, value in (("provider_uid", "5"), ("provider_uidvalidity", "124"),
                           ("provider_folder", "Other")):
            with patch.object(fixture, "_read", return_value=payload()):
                kept, _ = fixture.admit_originals(SETTINGS, [{**good, key: value}], {"peer@example.org"}, NOW)
            self.assertEqual(kept, [])
        with patch.object(fixture, "_read", return_value=payload()):
            kept, _ = fixture.admit_originals(SETTINGS, [good, good], {"peer@example.org"}, NOW)
        self.assertEqual(kept, [])

    def test_provider_content_proof_is_complete_and_bound(self):
        self.assertTrue(fixture._provider_original(self.provider, record()))
        self.assertEqual(self.provider.selected, '"INBOX"')
        self.assertFalse(fixture._original_digest(original_mime().replace(b"From: peer", b"From: wrong"), record()))
        self.assertFalse(fixture._original_digest(original_mime().replace(b"To: receiver", b"To: other"), record()))
        with patch.object(fixture.imaplib, "IMAP4_SSL", side_effect=OSError("offline")):
            self.assertEqual(fixture._confirmed(SETTINGS, [record()]), [])

    def test_smtp_folded_message_id_preserves_exact_original_identity(self):
        row = record()
        row["message_id"] = "<179189283403.1201441.17347207344191650171@operator-test.example.org>"
        msg = EmailMessage()
        for key, value in (("From", row["sender"]), ("To", row["receiver"]),
                           ("Message-ID", row["message_id"]), ("Subject", row["subject"])):
            msg[key] = value
        msg.set_content(BODY)
        raw = msg.as_bytes(policy=policy.SMTP)
        self.assertIn(b"Message-ID:\r\n ", raw)
        self.assertEqual(fixture._original_digest(raw, row), row["body_sha256"])
        wrong = {**row, "message_id": "<other@example.org>"}
        self.assertFalse(fixture._original_digest(raw, wrong))

    def test_normal_partition_still_honors_suppression_and_sent(self):
        original = message()
        with patch.object(fixture, "_read", return_value=payload()):
            rows, selfs = fixture.admit_originals(SETTINGS, [original], {"peer@example.org"}, NOW)
        now = datetime.now(timezone.utc)
        self.assertEqual(len(unanswered.compute_open(rows, [], selfs, set(), now)), 1)
        self.assertEqual(unanswered.compute_open(rows, [], selfs, {"peer@example.org"}, now), [])
        self.assertEqual(unanswered.compute_open(rows, [{"to": ["peer@example.org"], "thread_key": original["thread_key"],
                                                       "date": now}], selfs, set(), now), [])

    def test_actual_archive_row_provider_metadata(self):
        from cs import gmail_archive

        class ArchiveProvider(Provider):
            def list(self):
                return "OK", [b'(\\All) "/" "INBOX"']

            def uid(self, command, *args):
                if command == "SEARCH":
                    return "OK", [b"4"]
                assert command == "FETCH" and args[0] == b"4"
                assert "(UID BODY.PEEK[HEADER.FIELDS" in args[1]
                prefix = f"1 (UID {self.uid_value} BODY[HEADER.FIELDS]".encode()
                return "OK", [(prefix, self.raw)] * self.count

        reader = ArchiveProvider()
        with patch.object(gmail_archive, "_imap", return_value=reader):
            observed = gmail_archive.inbound_recent(SETTINGS, 1)
        self.assertEqual(len(observed), 1)
        original = observed[0]
        self.assertEqual(original["provider_uid"], "4")
        self.assertEqual(original["provider_uidvalidity"], "123")
        self.assertEqual(original["provider_folder"], "INBOX")
        self.assertEqual(original["thread_key"], record()["message_id"])
        with patch.object(fixture, "enrollments", return_value=[record()]):
            discovery = []
            kept, _ = fixture.admit_originals(SETTINGS, observed, {"peer@example.org"}, discovery=discovery)
        self.assertEqual(kept, observed)
        self.assertEqual(discovery[0]["body_sha256"], hashlib.sha256(BODY.encode()).hexdigest())
        for invalid in (ArchiveProvider(uid="999"), ArchiveProvider(validity="124"), ArchiveProvider(count=2)):
            with patch.object(gmail_archive, "_imap", return_value=invalid):
                rows = gmail_archive.inbound_recent(SETTINGS, 1)
            with patch.object(fixture, "enrollments", return_value=[record()]):
                discovery = []
                kept, _ = fixture.admit_originals(SETTINGS, rows, {"peer@example.org"}, discovery=discovery)
            self.assertEqual(kept, [])
            self.assertEqual(discovery, [])

    def test_sweep_does_not_bypass_assignment(self):
        from cs import engine_view, gmail_archive, task_assignment
        original = message(); other = {**original, "message_id": "<other@example.org>"}
        complete = {original["thread_key"]: {"complete": False}}
        with patch.object(fixture, "enrollments", return_value=[record()]), \
             patch.object(gmail_archive, "inbound_recent", return_value=[original, other]), \
             patch.object(gmail_archive, "sent_recent", return_value=[]), \
             patch.object(engine_view, "classify", return_value=({}, None)), \
             patch.object(engine_view, "settled", return_value=({}, None)), \
             patch.object(task_assignment, "projections", return_value=complete) as projection, \
             patch.object(task_assignment, "split_inbound", return_value=([], [], [], [])) as split:
            result = unanswered.sweep(SETTINGS, 1)
        projection.assert_called_once_with(SETTINGS, [original["thread_key"]])
        self.assertEqual(split.call_args.args[0], [original])
        self.assertNotIn("peer@example.org", split.call_args.args[3])
        self.assertEqual(result["operational_fixture_discovery"], [{
            "message_id": original["message_id"], "provider_folder": "INBOX",
            "provider_uid": "4", "provider_uidvalidity": "123",
            "owner_uid": "owner1", "body_sha256": hashlib.sha256(BODY.encode()).hexdigest()}])
        self.assertTrue(result["assignment_incomplete"])
        self.assertEqual(result["open"], [])


if __name__ == "__main__":
    unittest.main()
