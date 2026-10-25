"""Real local children preserve diagnostic evidence without granting authority."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from unittest.mock import patch

from cs import operator_discovery_receipt, operator_recovery as recovery
from cs.config import Settings


def encoded(events):
    return b"".join(json.dumps(event).encode() + b"\n" for event in events)


INIT = {"type": "system", "subtype": "init", "session_id": "same-session"}
RESULT = {"type": "result", "session_id": "same-session", "is_error": False}


def run_child(root, raw, *, key="", fail_recording=False):
    # Constructed stdout is a fixture, not a claimed actual Claude lifecycle.
    binary = root / "stream-child"
    binary.write_text("#!" + sys.executable + "\nimport sys\nsys.stdout.buffer.write(" + repr(raw) + ")\n")
    binary.chmod(0o700)
    settings = Settings(slug="native-stream-test")
    before = set(settings.state_dir.glob("operator-runs/run-*"))
    output = io.StringIO()
    with patch.object(recovery.config, "load", return_value=settings), \
         patch.dict(os.environ, {"CS_OPERATOR_ACCEPTANCE_RECEIPT": ""}), \
         contextlib.redirect_stdout(output), contextlib.ExitStack() as stack:
        if fail_recording:
            original = recovery.os.open

            def deny_stream(path, *args, **kwargs):
                if path == "native-stream.jsonl":
                    raise OSError("do not expose this diagnostic exception")
                return original(path, *args, **kwargs)

            stack.enter_context(patch.object(recovery.os, "open", side_effect=deny_stream))
        attempt = recovery._run(str(binary), [], prompt="/diagnostic-fixture", key=key,
                                model="fixture-model" if key else "")
    directory, = set(settings.state_dir.glob("operator-runs/run-*")) - before
    manifest = json.loads((directory / "native-stream.json").read_text())
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "native-stream.json").stat().st_mode) == 0o600
    return attempt, directory, manifest, output.getvalue()


with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"HOME": tmp}):
    root = Path(tmp)
    old_umask = os.umask(0)
    try:
        raw = encoded([INIT, RESULT])
        attempt, directory, manifest, _ = run_child(root, raw)
        retained = (directory / "native-stream.jsonl").read_bytes()
        assert retained == raw and recovery._successful(attempt)
        assert stat.S_IMODE((directory / "native-stream.jsonl").stat().st_mode) == 0o600
        assert manifest["retention_complete"] and manifest["process_exit"] == 0
        assert manifest["retained_bytes"] == len(raw)
        assert manifest["stream_sha256"] == hashlib.sha256(raw).hexdigest()
        assert manifest["child_identity"]["pid"] > 0

        medium = encoded([INIT, {'type': 'assistant', 'text': 'x' * 2_023_527}, RESULT])
        assert 2_000_000 < len(medium) < recovery.MAX_CAPTURE_BYTES == 4_000_000
        attempt, directory, manifest, _ = run_child(root, medium)
        assert not attempt.overflow and manifest['retention_complete']
        assert (directory / 'native-stream.jsonl').read_bytes() == medium
        with patch.object(recovery, 'MAX_CAPTURE_BYTES', 2_000_000):
            attempt, directory, manifest, _ = run_child(root, medium)
            assert attempt.overflow and not manifest['retention_complete']
        lifecycle = [INIT, RESULT, {"type": "system", "subtype": "task_notification"}, INIT, RESULT]
        raw = encoded(lifecycle)
        attempt, directory, manifest, _ = run_child(root, raw)
        assert (directory / "native-stream.jsonl").read_bytes() == raw
        assert attempt.events == lifecycle and manifest["accepted_event_count"] == 5
        assert attempt.result is None and not recovery._successful(attempt)
        phase = {"phase": "discovery", "discovery_complete": True, "discovery": ["untrusted"]}
        with patch.object(operator_discovery_receipt, "private_dir", side_effect=AssertionError("join must stop")):
            operator_discovery_receipt.join([{"phase": "discovery"}], [phase], lifecycle, {}, "")
        assert phase["discovery_complete"] is False and phase["discovery"] == []

        key = "secret-fallback-key-for-test"
        raw = encoded([INIT, {"type": "assistant", "text": key}, RESULT])
        attempt, directory, manifest, _ = run_child(root, raw, key=key)
        assert key.encode() not in (directory / "native-stream.jsonl").read_bytes()
        assert (directory / "native-stream.jsonl").read_bytes() == raw.replace(key.encode(), b"[redacted]")
        assert manifest["fallback_key_redaction_enabled"] and recovery._successful(attempt)

        raw = b"not-json\n" + encoded([INIT, RESULT])
        attempt, directory, manifest, _ = run_child(root, raw)
        assert attempt.malformed and not recovery._successful(attempt)
        assert (directory / "native-stream.jsonl").read_bytes() == raw
        assert manifest["retention_complete"] and manifest["malformed"]

        raw = encoded([INIT]) + b"x" * (recovery.MAX_CAPTURE_BYTES + 1) + b"\n" + encoded([RESULT])
        attempt, directory, manifest, _ = run_child(root, raw)
        assert attempt.overflow and not recovery._successful(attempt)
        assert (directory / "native-stream.jsonl").read_bytes() == encoded([INIT])
        assert manifest["overflow"] and not manifest["retention_complete"]
        assert manifest["stdout_bytes_seen"] == len(raw)

        attempt, directory, manifest, output = run_child(root, encoded([INIT, RESULT]), fail_recording=True)
        assert recovery._successful(attempt) and manifest["retention_failed"]
        assert not manifest["retention_complete"] and "retention failed" in output
        assert "do not expose" not in output

        private = root / "private"
        private.mkdir(mode=0o700)
        target = root / "do-not-overwrite"
        target.write_bytes(b"preserve")
        (private / "native-stream.jsonl").symlink_to(target)
        sink = recovery._NativeStreamCapture(private)
        sink.append(b"replacement", "")
        sink.finish(recovery.Attempt(0, []), {}, 11, False)
        assert sink.failed and target.read_bytes() == b"preserve"
        public = root / "public"
        public.mkdir(mode=0o755)
        sink = recovery._NativeStreamCapture(public)
        sink.finish(recovery.Attempt(0, []), {}, 0, False)
        assert sink.failed and not list(public.iterdir())
        with patch.object(recovery.os, "fstat", side_effect=OSError("unverified directory")):
            sink = recovery._NativeStreamCapture(public)
        sink.finish(recovery.Attempt(0, []), {}, 0, False)
        assert sink.failed and sink.directory_fd is None and not list(public.iterdir())
        alias = root / "directory-link"
        alias.symlink_to(private, target_is_directory=True)
        sink = recovery._NativeStreamCapture(alias)
        sink.finish(recovery.Attempt(0, []), {}, 0, False)
        assert sink.failed and target.read_bytes() == b"preserve"

        bounded = root / "redaction-expansion"
        bounded.mkdir(mode=0o700)
        sink = recovery._NativeStreamCapture(bounded)
        sink.append(b"x" * recovery.MAX_CAPTURE_BYTES, "x")
        sink.finish(recovery.Attempt(0, []), {}, recovery.MAX_CAPTURE_BYTES, True)
        assert sink.failed and (bounded / "native-stream.jsonl").stat().st_size == 0
        assert not json.loads((bounded / "native-stream.json").read_text())["retention_complete"]
    finally:
        os.umask(old_umask)

print("private native stream: ordering, strict lifecycle refusal, byte cap, malformed input, redaction, privacy and recording failure OK")
