"""Real private-store logging-health failures, recovery and retained uncertainty."""

import contextlib
import fcntl
import io
import json
import multiprocessing
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from cs.observability import EventStore, span
from cs import observability_logging as logging
from cs import observability_store as persistence


def concurrent_append(root):
    store = EventStore(root, "owner")
    for _ in range(8):
        store.emit("rpc", "result")


class LoggingHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "events"
        self.store = EventStore(self.root, "owner")
        self.assertIsNotNone(self.store.emit("cli", "start"))

    def tearDown(self):
        self.temp.cleanup()

    def failure(self, exc=None):
        with contextlib.redirect_stderr(io.StringIO()), patch.object(persistence, "append", side_effect=exc or OSError(28, "SECRET_CANARY")):
            self.assertIsNone(self.store.emit("rpc", "result"))
        return self.store.health()["logging"]

    def test_failure_recovery_failure_and_restart(self):
        failed = self.failure()
        self.assertEqual(failed["current_state"], "failed")
        self.assertEqual(failed["observed_failures"], 1)
        self.assertFalse(failed["lost_events_unknown"])
        self.assertEqual(failed["last_failure"]["error_code"], 28)
        event = self.store.emit("rpc", "result")
        recovered = EventStore(self.root, "owner").health()["logging"]
        self.assertEqual(recovered["current_state"], "recovered")
        self.assertEqual(recovered["recovery"]["event_id"], event["event_id"])
        self.assertTrue((self.root / ".logging-failed").exists())
        self.store.emit("cli", "result")
        self.assertEqual(recovered, self.store.health()["logging"])
        renewed = self.failure()
        self.assertEqual(renewed["current_state"], "failed")
        self.assertEqual(renewed["observed_failures"], 2)
        self.assertIsNone(renewed["recovery"])
        self.assertEqual(renewed["first_failure_at"], failed["first_failure_at"])

    def test_legacy_unknown_recovery_retains_unknown_loss(self):
        marker = self.root / ".logging-failed"
        marker.write_bytes(b'{"reason":"logging","coverage_lost":true}')
        marker.chmod(0o600)
        original = marker.read_bytes()
        unknown = self.store.health()["logging"]
        self.assertEqual(unknown["current_state"], "unknown")
        self.assertEqual(unknown["observed_failures"], 0)
        self.assertIsNone(unknown["last_failure"])
        self.store.prune()
        self.assertEqual(unknown, self.store.events()["coverage"]["logging"])
        self.assertIsNotNone(self.store.emit("rpc", "result"))
        recovered = self.store.health()["logging"]
        self.assertEqual(recovered["current_state"], "recovered")
        self.assertTrue(recovered["lost_events_unknown"])
        self.assertEqual(marker.read_bytes(), original)
        self.assertTrue(any(g["reason"] == "logging" for g in self.store.health()["gaps"]))

    def test_legacy_writer_rewrite_invalidates_recovery(self):
        self.failure()
        self.store.emit("rpc", "result")
        marker = self.root / ".logging-failed"
        marker.write_bytes(marker.read_bytes())
        self.assertEqual(EventStore(self.root, "owner").health()["logging"]["current_state"], "unknown")
        self.store.emit("rpc", "result")
        self.assertEqual(self.store.health()["logging"]["current_state"], "recovered")

    def test_no_history_omits_object_and_read_does_not_recover(self):
        self.assertNotIn("logging", self.store.health())
        self.failure()
        before = (self.root / logging.STATE_FILE).read_bytes()
        for _ in range(3):
            self.assertEqual(EventStore(self.root, "owner").health()["logging"]["current_state"], "failed")
            self.store.events()
            self.store.recent()
            self.store.locations()
            self.store.prune()
        self.assertEqual(before, (self.root / logging.STATE_FILE).read_bytes())

    def test_concurrent_append_recovery_stable_and_delayed_failure_wins(self):
        self.failure()
        workers = [multiprocessing.Process(target=concurrent_append, args=(self.root,)) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(5)
            self.assertEqual(worker.exitcode, 0)
        recovered = self.store.health()["logging"]
        self.assertEqual(recovered["current_state"], "recovered")
        logging.record_failure(self.store, TimeoutError("SECRET_CANARY"))
        self.assertEqual(self.store.health()["logging"]["current_state"], "failed")
        self.assertGreaterEqual(self.store.health()["logging"]["observed_failures"], 2)

    def test_state_write_failure_never_proves_recovery(self):
        self.failure()
        with contextlib.redirect_stderr(io.StringIO()), patch.object(logging, "_save", side_effect=OSError("SECRET_CANARY")):
            self.assertIsNone(self.store.emit("rpc", "result"))
        self.assertEqual(self.store.health()["logging"]["current_state"], "failed")
        self.assertNotEqual(EventStore(self.root, "owner").health()["logging"]["current_state"], "recovered")
        self.assertNotIn("SECRET_CANARY", json.dumps(self.store.health()))

    def test_unsafe_malformed_and_foreign_state_fail_closed(self):
        self.failure()
        path = self.root / logging.STATE_FILE
        original = path.read_bytes()
        for contents in (b"{", b"x" * 4097, original.replace(b'"owner"', b'"foreign"')):
            path.write_bytes(contents)
            self.assertEqual(EventStore(self.root, "owner").health()["logging"]["current_state"], "unknown")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertIsNone(self.store.emit("rpc", "result"))
            self.assertEqual(EventStore(self.root, "owner").health()["logging"]["current_state"], "unknown")
        path.unlink()
        target = Path(self.temp.name) / "foreign"
        target.write_bytes(original)
        target.chmod(0o600)
        path.symlink_to(target)
        before = target.read_bytes()
        self.assertEqual(EventStore(self.root, "owner").health()["logging"]["current_state"], "unknown")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(self.store.emit("rpc", "result"))
        self.assertEqual(target.read_bytes(), before)

    def test_lock_failure_is_nonthrowing_and_not_recovery(self):
        self.failure()
        with (self.root / ".lock").open("rb") as locked:
            fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertIsNone(self.store.emit("rpc", "result"))
        self.assertEqual(self.store.health()["logging"]["current_state"], "failed")

    def test_partial_append_is_failed_then_gap_remains_after_recovery(self):
        original_open = persistence._open
        def partial_open(path, flags, mode=0o600):
            fd = original_open(path, flags, mode)
            if path.name.startswith("events-") and flags & os.O_APPEND:
                os.write(fd, b'{"partial":')
                os.close(fd)
                raise OSError(28, "SECRET_CANARY")
            return fd
        with contextlib.redirect_stderr(io.StringIO()), patch.object(persistence, "_open", side_effect=partial_open):
            self.assertIsNone(self.store.emit("rpc", "result"))
        self.assertEqual(self.store.health()["logging"]["current_state"], "failed")
        self.store.emit("rpc", "result")
        page = self.store.events()
        self.assertEqual(page["coverage"]["logging"]["current_state"], "recovered")
        self.assertTrue(any(g["reason"] == "malformed-event" for g in page["coverage"]["gaps"]))

    def test_safe_metadata_and_business_exception_preserved(self):
        class SecretException(Exception):
            pass
        failure = self.failure(SecretException("SECRET_CANARY /private/full/path"))
        self.assertEqual(failure["last_failure"]["error_class"], "UnknownError")
        self.assertNotIn("SECRET_CANARY", json.dumps(self.store.health()))
        self.assertNotIn("/private", (self.root / logging.STATE_FILE).read_text())
        with self.assertRaisesRegex(RuntimeError, "business unchanged"):
            with span(self.store, "rpc"):
                raise RuntimeError("business unchanged")

    def test_invalid_enum_is_failure(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(self.store.emit("invalid-stage", "result"))
        self.assertEqual(self.store.health()["logging"]["current_state"], "failed")

    def test_validator_rejects_unsafe_or_unordered_metadata(self):
        valid = self.failure()
        self.assertEqual(logging.validate_logging(valid), valid)
        for key, value in (("current_state", "healthy"), ("observed_failures", True), ("extra", "SECRET_CANARY")):
            candidate = json.loads(json.dumps(valid))
            candidate[key] = value
            with self.assertRaises(ValueError):
                logging.validate_logging(candidate)
        candidate = json.loads(json.dumps(valid))
        candidate["last_failure"]["error_file"] = "/private/secret.py"
        with self.assertRaises(ValueError):
            logging.validate_logging(candidate)

    def test_marker_change_during_append_does_not_recover(self):
        self.failure()
        original = logging._fingerprint
        calls = []
        def changed(store):
            value = original(store)
            calls.append(value)
            if len(calls) == 2:
                return [value[0], value[1], value[2] + 1, value[3]]
            return value
        with patch.object(logging, "_fingerprint", side_effect=changed):
            self.store.emit("rpc", "result")
        self.assertEqual(self.store.health()["logging"]["current_state"], "failed")

    def test_threshold_filtered_emission_does_not_recover(self):
        self.failure()
        self.store.log_level = "ERROR"
        self.assertIsNone(self.store.emit("rpc", "result"))
        self.assertEqual(self.store.health()["logging"]["current_state"], "failed")
        self.assertIsNotNone(self.store.emit("rpc", "failed"))
        self.assertEqual(self.store.health()["logging"]["current_state"], "recovered")

    def test_root_failure_fallback_recovers_after_real_append(self):
        with contextlib.redirect_stderr(io.StringIO()), patch.object(persistence, "_root", side_effect=PermissionError("SECRET_CANARY")):
            self.assertIsNone(self.store.emit("rpc", "result"))
            self.assertEqual(self.store.health()["logging"]["current_state"], "failed")
        event = self.store.emit("rpc", "result")
        self.assertIsNotNone(event)
        health = EventStore(self.root, "owner").health()["logging"]
        self.assertEqual(health["current_state"], "recovered")
        self.assertEqual(health["recovery"]["event_id"], event["event_id"])

    def test_older_append_preserves_newer_same_store_lock_failure(self):
        self.failure()
        entered, release = threading.Event(), threading.Event()
        original = persistence.after_append
        def delayed(*args):
            entered.set()
            self.assertTrue(release.wait(2))
            return original(*args)
        with patch.object(persistence, "after_append", side_effect=delayed), contextlib.redirect_stderr(io.StringIO()):
            older = threading.Thread(target=lambda: self.store.emit("rpc", "result"))
            older.start()
            self.assertTrue(entered.wait(2))
            self.assertIsNone(self.store.emit("rpc", "result"))
            pending = self.store._logging_failure
            self.assertIsNotNone(pending)
            release.set()
            older.join(2)
            self.assertFalse(older.is_alive())
        health = EventStore(self.root, "owner").health()["logging"]
        self.assertEqual(health["current_state"], "failed")
        self.assertEqual(health["observed_failures"], 2)
        self.assertEqual(health["last_failure"]["timestamp"], pending["timestamp"])
        self.assertIsNone(health["recovery"])
        later = self.store.emit("rpc", "result")
        health = EventStore(self.root, "owner").health()["logging"]
        self.assertEqual(health["current_state"], "recovered")
        self.assertEqual(health["recovery"]["event_id"], later["event_id"])

    def test_failure_arriving_during_persistence_is_not_cleared(self):
        original = logging._save
        injected = []
        def newer_failure(*args):
            original(*args)
            if not injected:
                injected.append(True)
                self.assertIsNone(self.store.emit("invalid-stage", "result"))
        with patch.object(logging, "_save", side_effect=newer_failure), contextlib.redirect_stderr(io.StringIO()):
            logging.record_failure(self.store, OSError(28, "SECRET_CANARY"))
        self.assertIsNotNone(self.store._logging_failure)
        self.assertNotEqual(EventStore(self.root, "owner").health()["logging"]["current_state"], "recovered")
        later = self.store.emit("rpc", "result")
        self.assertIsNotNone(later)
        health = EventStore(self.root, "owner").health()["logging"]
        self.assertEqual(health["current_state"], "recovered")
        self.assertEqual(health["observed_failures"], 2)

    def test_independent_writer_marker_cannot_be_adopted_by_older_append(self):
        other = EventStore(self.root, "owner")
        with persistence._locked(self.store, write=True), contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(self.store.emit("rpc", "result"))
        entered, release = threading.Event(), threading.Event()
        original = logging._write_marker
        def delayed(store):
            owned = original(store)
            if store is self.store:
                entered.set()
                self.assertTrue(release.wait(2))
            return owned
        with patch.object(logging, "_write_marker", side_effect=delayed), contextlib.redirect_stderr(io.StringIO()):
            older = threading.Thread(target=lambda: self.store.emit("rpc", "result"))
            older.start()
            self.assertTrue(entered.wait(2))
            self.assertIsNone(other.emit("rpc", "result"))
            newest = other._logging_failure
            self.assertIsNotNone(newest)
            release.set()
            older.join(2)
            self.assertFalse(older.is_alive())
        health = EventStore(self.root, "owner").health()["logging"]
        self.assertEqual(health["current_state"], "unknown")
        self.assertTrue(health["lost_events_unknown"])
        self.assertIsNone(health["recovery"])
        later = other.emit("rpc", "result")
        health = EventStore(self.root, "owner").health()["logging"]
        self.assertEqual(health["current_state"], "recovered")
        self.assertEqual(health["last_failure"]["timestamp"], newest["timestamp"])
        self.assertEqual(health["recovery"]["event_id"], later["event_id"])
