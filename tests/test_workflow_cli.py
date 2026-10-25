"""Real CLI subprocess and controlled authenticated WebSocket workflow checks."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import io
import json
import os
import pty
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cs import project_init
from cs.workflow_cli import CHUNK

RUNNER = """
import sys
from cs import config, rpc
settings = config.Settings(_env_file=None, engine_ws_url=sys.argv[1], engine_owner_uid='fixture-owner')
config.load = lambda: settings
rpc.auth.get_id_token = lambda settings: 'controlled-token'
from cs.cli import main
raise SystemExit(main(sys.argv[2:]))
"""


def events(stdout):
    return [json.loads(line) for line in stdout.decode().splitlines()]


class WorkflowCLI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.connections = 0
        self.session_override = {}
        self.run_override = {}
        self.cancel_refused = False
        self.server_cancelled_pending = False
        self.state = "running"
        self.responded = False
        self.content = b"private original\n" * 22000
        self.uploaded = bytearray()
        self.upload_metadata = None
        self.corrupt = None
        self.old = False
        self.legal_run = False
        self.disconnect_start = False
        self.block_start = False
        self.start_entered = asyncio.Event()
        self.start_closed = asyncio.Event()
        self.sockets = {}
        self.server = await websockets.serve(self.handler, "127.0.0.1", 0)
        self.url = "ws://127.0.0.1:" + str(self.server.sockets[0].getsockname()[1])
        self.tmp = tempfile.TemporaryDirectory()
        self.processes = []

    async def asyncTearDown(self):
        for process in self.processes:
            if process.returncode is None:
                process.kill()
                await process.wait()
        self.server.close()
        await self.server.wait_closed()
        self.tmp.cleanup()

    async def handler(self, socket):
        self.connections += 1
        connection = self.connections
        self.sockets[connection] = socket
        self.assertEqual(socket.request.headers.get("Authorization"), "Bearer controlled-token")
        self.assertEqual(socket.request.path, "/ws/fixture-owner")
        async for wire in socket:
            frame = json.loads(wire)
            method, params = frame["method"], frame["params"]
            self.calls.append((connection, method, params))
            if method == "workflows.interactive.start" and self.disconnect_start:
                await socket.close()
                return
            if method == "workflows.interactive.start" and self.block_start:
                self.legal_run = True
                self.state = "running"
                self.start_entered.set()
                await socket.wait_closed()
                self.state = "cancelled"
                self.server_cancelled_pending = True
                self.start_closed.set()
                return
            response = {"jsonrpc": "2.0", "id": frame["id"]}
            if self.old or (method == "workflows.cancel" and self.cancel_refused):
                response["error"] = {"code": -32601, "message": "SECRET raw server error"}
            else:
                response["result"] = self.result(method, params, connection)
            with contextlib.suppress(websockets.ConnectionClosed):
                await socket.send(json.dumps(response))

    def result(self, method, params, connection):
        if method == "workflows.list":
            return {"schema_version": 1, "workflows": [{"name": name, "version": "controlled-version"} for name in ("cs-financial-statements", "cs-legal-research")]}
        if method == "workflows.suggest":
            return {"schema_version": 1, "state": "selected", "candidates": ["cs-financial-statements"], "launch": False}
        if method == "workflows.interactive.session":
            return {"schema_version": 1, "protocol_version": 2, "session_id": f"session-{connection}",
                    "authenticated": True, "direct_start": True, **self.session_override}
        if method == "workflows.interactive.start":
            self.legal_run = True
            return {**self.run_result(), **self.run_override}
        if method == "workflows.start":
            self.assertEqual(params["workflow_id"], "cs-financial-statements")
            return self.run_result()
        if method == "workflows.status":
            self.state = "completed" if self.responded else "waiting"
            return self.run_result()
        if method in {"workflows.respond", "workflows.interactive.respond"}:
            self.assertEqual(params["message"], "actual answer")
            self.responded = True
            return {"schema_version": 1, "run_id": "run", "state": "running"}
        if method == "workflows.cancel":
            self.state = "cancelled"
            return self.run_result()
        if method == "workflows.documents.prepare_upload":
            self.upload_metadata = {"document_id": "document", **params, "state": "uploading"}
            return self.upload_metadata
        if method == "workflows.documents.upload_chunk":
            self.assertEqual(params["offset"], len(self.uploaded))
            self.uploaded.extend(base64.b64decode(params["content_base64"]))
            return {"document_id": "document", "received": len(self.uploaded)}
        if method == "workflows.documents.finish_upload":
            self.assertEqual(hashlib.sha256(self.uploaded).hexdigest(), self.upload_metadata["sha256"])
            return {**self.upload_metadata, "state": "ready", "limitations": ["Controlled extraction limitation."]}
        if method in {"workflows.artifacts.get", "workflows.documents.download"}:
            document = method.endswith("download")
            data = bytes(self.uploaded) if document else self.content
            offset = params["offset"]
            part = data[offset:offset + CHUNK]
            row = {"document_id" if document else "artifact_id": "document" if document else "artifact",
                   "name": "../../never-use-this-path", "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                   "offset": offset, "next_offset": offset + len(part) if offset + len(part) < len(data) else None,
                   "content_base64": base64.b64encode(part).decode()}
            if self.corrupt == "offset":
                row["offset"] += 1
            if self.corrupt == "digest":
                row["sha256"] = "0" * 64
            if self.corrupt == "size":
                row["size"] += 1
            if self.corrupt == "chunk":
                row["chunk_sha256"] = "0" * 64
            if self.corrupt == "truncated":
                row["next_offset"] = None
            return row
        raise AssertionError(method)

    def run_result(self):
        return {"schema_version": 1, "run_id": "run", "workflow_id": "cs-legal-research" if self.legal_run else "cs-financial-statements",
                "version": "controlled-version", "state": self.state,
                "artifact_ids": ["artifact"], "output": {"question": "Question from engine"}}

    async def process(self, *args):
        process = await asyncio.create_subprocess_exec(sys.executable, "-c", RUNNER, self.url, "workflow", *args,
            cwd=ROOT, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.processes.append(process)
        return process

    async def command(self, *args):
        process = await self.process(*args)
        out, err = await asyncio.wait_for(process.communicate(), 15)
        self.assertEqual(err, b"")
        return process.returncode, events(out)

    async def receive(self, process, event):
        for _ in range(20):
            line = await asyncio.wait_for(process.stdout.readline(), 8)
            self.assertTrue(line, "process exited before " + event)
            row = json.loads(line)
            if row["event"] == event:
                return row["result"]
        self.fail("event missing: " + event)

    async def send(self, process, action):
        process.stdin.write(json.dumps(action).encode() + b"\n")
        await process.stdin.drain()

    async def test_finance_real_cli_wait_clarification_and_download(self):
        code, rows = await self.command("start", "financial statements", "--wait")
        self.assertEqual(code, 0)
        self.assertEqual(rows[-1]["result"]["state"], "waiting")
        code, rows = await self.command("respond", "actual answer", "run", "--wait")
        self.assertEqual(code, 0)
        self.assertEqual(rows[-1]["result"]["state"], "completed")
        output = Path(self.tmp.name) / "report.bin"
        code, rows = await self.command("download", "artifact", "--output", str(output))
        self.assertEqual(code, 0)
        self.assertEqual(output.read_bytes(), self.content)
        self.assertEqual(len([p for _, m, p in self.calls if m == "workflows.artifacts.get"]), 2)

    async def test_upload_retains_basename_and_checks_original_bytes(self):
        path = Path(self.tmp.name) / "original.txt"
        path.write_bytes(self.content)
        code, rows = await self.command("upload", str(path))
        self.assertEqual(code, 0)
        self.assertEqual(self.upload_metadata["name"], "original.txt")
        self.assertEqual(self.uploaded, self.content)
        self.assertEqual(rows[-1]["result"]["limitations"], ["Controlled extraction limitation."])
        self.assertTrue(any(method == "workflows.documents.download" for _, method, _ in self.calls))

    async def test_legal_real_non_tty_direct_start_wait_and_clarification(self):
        process = await self.process("legal", "company legal question", "--protocol", "json",
                                     "--document", "doc-a", "--public-queries", '{"official":"example query"}',
                                     "--approved-url", "https://example.org/public")
        await self.receive(process, "started")
        starts = [params for _, method, params in self.calls if method == "workflows.interactive.start"]
        self.assertEqual(starts, [{"message": "company legal question", "document_ids": ["doc-a"],
                                 "public_queries": {"official": "example query"},
                                 "approved_urls": ["https://example.org/public"]}])
        self.assertFalse(any(method.endswith(("prepare", "confirm", "register")) for _, method, _ in self.calls))
        waiting = await self.receive(process, "status")
        self.assertEqual(waiting["state"], "waiting")
        await self.send(process, {"action": "respond", "message": "actual answer"})
        await self.receive(process, "responded")
        result = await self.receive(process, "status")
        self.assertEqual(result["state"], "completed")
        output = Path(self.tmp.name) / "legal-report.bin"
        await self.send(process, {"action": "download", "artifact_id": "artifact", "output": str(output)})
        await self.receive(process, "downloaded")
        self.assertEqual(output.read_bytes(), self.content)
        await self.send(process, {"action": "close"})
        await asyncio.wait_for(process.wait(), 8)
        self.assertEqual(process.returncode, 0)
        self.assertEqual({connection for connection, _, _ in self.calls}, {1})

    async def test_malformed_or_old_session_never_dispatches(self):
        for change in ({"protocol_version": 1}, {"protocol_version": True}, {"schema_version": True},
                       {"session_id": ""}, {"authenticated": False}, {"authenticated": 1},
                       {"direct_start": False}, {"direct_start": "true"}):
            with self.subTest(change=change):
                self.session_override = change
                process = await self.process("legal", "question")
                await self.receive(process, "error")
                await asyncio.wait_for(process.wait(), 8)
                self.assertEqual(process.returncode, 1)
        self.assertFalse(any(method == "workflows.interactive.start" for _, method, _ in self.calls))

    async def test_malformed_start_result_never_emits_started(self):
        for change in ({"run_id": ""}, {"schema_version": True}, {"workflow_id": "other"}, {"state": "unknown"}):
            self.run_override = change
            process = await self.process("legal", "question")
            await self.receive(process, "error")
            await asyncio.wait_for(process.wait(), 8)
            self.assertEqual(process.returncode, 1)
        self.assertEqual(len([m for _, m, _ in self.calls if m == "workflows.interactive.start"]), 4)

    async def test_failed_cancellation_is_explicit(self):
        self.cancel_refused = True
        process = await self.process("legal", "question")
        await self.receive(process, "started")
        await self.send(process, {"action": "close"})
        await self.receive(process, "cancellation_unverified")
        await asyncio.wait_for(process.wait(), 8)
        self.assertEqual(self.connections, 1)

    async def test_eof_cancels_active_legal_run(self):
        process = await self.process("legal", "question")
        await self.receive(process, "started")
        process.stdin.close()
        await asyncio.wait_for(process.wait(), 8)
        self.assertEqual(process.returncode, 1)
        self.assertTrue(any(method == "workflows.cancel" for _, method, _ in self.calls))

    async def test_eof_closes_socket_during_start(self):
        self.block_start = True
        process = await self.process("legal", "question")
        await asyncio.wait_for(self.start_entered.wait(), 5)
        process.stdin.close()
        await asyncio.wait_for(self.start_closed.wait(), 5)
        self.assertTrue(self.server_cancelled_pending)
        self.assertEqual(self.state, "cancelled")
        await asyncio.wait_for(process.wait(), 5)
        self.assertEqual(process.returncode, 1)

    async def test_disconnect_stops_session_without_reconnect(self):
        self.disconnect_start = True
        process = await self.process("legal", "question")
        await asyncio.wait_for(process.wait(), 8)
        output = await process.stdout.read()
        self.assertEqual(process.returncode, 1)
        self.assertNotIn(b"SECRET", output)
        self.assertEqual(self.connections, 1)
        self.assertFalse(any(method.endswith("confirm") for _, method, _ in self.calls))

    async def test_legal_generic_respond_refuses_before_dispatch(self):
        self.legal_run = True
        code, _ = await self.command("respond", "actual answer", "run")
        self.assertEqual(code, 1)
        self.assertFalse(any(method == "workflows.respond" for _, method, _ in self.calls))

    async def test_download_corruption_preserves_existing_destination(self):
        output = Path(self.tmp.name) / "report.bin"
        for corrupt in ("offset", "digest", "size", "chunk", "truncated"):
            with self.subTest(corrupt=corrupt):
                self.corrupt = corrupt
                output.write_bytes(b"existing")
                code, _ = await self.command("download", "artifact", "--output", str(output))
                self.assertEqual(code, 1)
                self.assertEqual(output.read_bytes(), b"existing")
                self.assertEqual(sorted(p.name for p in output.parent.iterdir()), ["report.bin"])

    async def terminal(self):
        master, slave = pty.openpty()
        try:
            item = await asyncio.create_subprocess_exec(sys.executable, "-c", RUNNER, self.url,
                "workflow", "legal", "question", "--protocol", "terminal", cwd=ROOT,
                stdin=slave, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        finally:
            os.close(slave)
        self.processes.append(item)
        return item, master

    async def test_terminal_pty_direct_start_and_clarification(self):
        item, master = await self.terminal()
        try:
            await asyncio.wait_for(item.stdout.readuntil(b"or type /cancel: "), 8)
            os.write(master, b"actual answer\n")
            output, error = await asyncio.wait_for(item.communicate(), 8)
            self.assertEqual(item.returncode, 0, output)
            self.assertEqual(error, b"")
            self.assertIn(b'"state": "completed"', output)
            self.assertTrue(any(method == "workflows.interactive.respond" for _, method, _ in self.calls))
            starts = [params for _, method, params in self.calls if method == "workflows.interactive.start"]
            self.assertEqual(starts, [{"message": "question", "document_ids": [], "public_queries": {}, "approved_urls": []}])
            self.assertEqual({connection for connection, _, _ in self.calls}, {1})
        finally:
            os.close(master)

    async def test_terminal_pty_eof_during_start_closes_socket(self):
        self.block_start = True
        item, master = await self.terminal()
        try:
            await asyncio.wait_for(self.start_entered.wait(), 5)
            os.write(master, b"\x04")
            await asyncio.wait_for(self.start_closed.wait(), 5)
            await asyncio.wait_for(item.wait(), 5)
            self.assertEqual(item.returncode, 1)
        finally:
            os.close(master)

    async def test_terminal_pty_disconnect_while_prompt_exits(self):
        item, master = await self.terminal()
        try:
            await asyncio.wait_for(item.stdout.readuntil(b"or type /cancel: "), 8)
            await self.sockets[1].close()
            await asyncio.wait_for(item.wait(), 5)
            self.assertEqual(item.returncode, 1)
        finally:
            os.close(master)

    async def test_terminal_mode_refuses_pipe_before_connecting(self):
        code, rows = await self.command("legal", "question", "--protocol", "terminal")
        self.assertEqual(code, 1)
        self.assertIn("requires an interactive terminal", rows[-1]["result"]["message"])
        self.assertEqual(self.calls, [])

    async def test_old_engine_has_safe_explicit_refusal(self):
        self.old = True
        code, rows = await self.command("list")
        self.assertEqual(code, 1)
        self.assertIn("does not support", rows[0]["result"]["message"])
        self.assertNotIn("SECRET", json.dumps(rows))
        self.assertEqual([method for _, method, _ in self.calls], ["workflows.list"])


class SkillSurfaces(unittest.TestCase):
    def test_all_hosts_resolve_canonical_render_and_copy_fallback(self):
        from test_project_update import _FULL_INIT_DATA
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = ROOT / "cs/templates/project"
            for copy in (False, True):
                clone = root / str(copy)
                clone.mkdir()
                with contextlib.redirect_stdout(io.StringIO()):
                    project_init.render_templates({**project_init.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}, template, clone)
                    with patch.object(project_init, "LEGACY_CODEX_PROMPTS", root / "prompts"):
                        if copy:
                            with patch.object(Path, "symlink_to", side_effect=OSError("unsupported")):
                                project_init.install_agent_surfaces(clone)
                        else:
                            project_init.install_agent_surfaces(clone)
                canonical = clone / ".claude/skills/cs-engine-workflow/SKILL.md"
                for host in (".claude", ".agents", ".opencode"):
                    self.assertEqual((clone / host / "skills/cs-engine-workflow/SKILL.md").read_bytes(), canonical.read_bytes())
                self.assertIn("starts once directly", canonical.read_text())
                self.assertIn("old local", canonical.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
