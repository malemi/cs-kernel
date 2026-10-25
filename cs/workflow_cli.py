"""Thin authenticated client for engine-owned private workflows and transfers."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

from . import config, rpc

FINANCE = "cs-financial-statements"
MAX_BYTES = 16 * 1024 * 1024
CHUNK = 256 * 1024
TERMINAL = {"completed", "failed", "cancelled", "expired", "interrupted"}


class WorkflowClientError(RuntimeError):
    """A constant, safe operator-facing failure."""


async def call(client, method, params=None):
    try:
        result = await client.call(method, params or {})
    except rpc.EngineError as exc:
        if exc.code == -32601:
            raise WorkflowClientError("The engine does not support this workflow command; update the engine.") from None
        raise WorkflowClientError("The engine refused the workflow operation; check sign-in, authority and run state.") from None
    if not isinstance(result, dict):
        raise WorkflowClientError("The engine returned an unsupported workflow response.")
    return result


async def discover(client):
    result = await call(client, "workflows.list")
    if type(result.get("schema_version")) is not int or result["schema_version"] != 1 or not isinstance(result.get("workflows"), list):
        raise WorkflowClientError("The engine does not support workflow schema version 1.")
    return result


def emit(event, result):
    print(json.dumps({"event": event, "result": result}, ensure_ascii=False), flush=True)


def metadata(row, identifier, key):
    size, digest = row.get("size"), row.get("sha256")
    if (row.get(key) != identifier or type(size) is not int or not 0 <= size <= MAX_BYTES
            or not isinstance(digest, str) or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)):
        raise WorkflowClientError("The workflow transfer metadata is invalid.")
    return size, digest


async def transfer(client, identifier, *, document=False, destination=None):
    key = "document_id" if document else "artifact_id"
    method = "workflows.documents.download" if document else "workflows.artifacts.get"
    offset, expected, digest = 0, None, hashlib.sha256()
    scratch = None
    stream = None
    try:
        if destination is not None:
            target = Path(destination).absolute()
            fd, scratch = tempfile.mkstemp(prefix=".workflow-", dir=target.parent)
            stream = os.fdopen(fd, "wb")
        while True:
            row = await call(client, method, {key: identifier, "offset": offset, "limit": CHUNK})
            current = metadata(row, identifier, key)
            if expected is not None and current != expected:
                raise WorkflowClientError("The workflow transfer metadata changed.")
            expected = current
            try:
                part = base64.b64decode(row["content_base64"], validate=True)
            except (KeyError, ValueError, TypeError):
                raise WorkflowClientError("The workflow transfer contains invalid bytes.") from None
            end = offset + len(part)
            next_offset = row.get("next_offset")
            if (type(row.get("offset")) is not int or row["offset"] != offset
                    or len(part) > CHUNK or end > expected[0]
                    or (end < expected[0] and (not part or type(next_offset) is not int or next_offset != end))
                    or (end == expected[0] and next_offset is not None)):
                raise WorkflowClientError("The workflow transfer is incomplete or out of order.")
            if "chunk_sha256" in row and row["chunk_sha256"] != hashlib.sha256(part).hexdigest():
                raise WorkflowClientError("The workflow transfer checksum failed.")
            digest.update(part)
            if stream is not None:
                stream.write(part)
            offset = end
            if next_offset is None:
                break
        if offset != expected[0] or digest.hexdigest() != expected[1]:
            raise WorkflowClientError("The workflow transfer checksum failed.")
        if stream is not None:
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            stream = None
            os.replace(scratch, target)
            scratch = None
        return {key: identifier, "size": offset, "sha256": digest.hexdigest(),
                **({"output": str(target)} if destination is not None else {})}
    finally:
        if stream is not None:
            stream.close()
        if scratch is not None:
            Path(scratch).unlink(missing_ok=True)


async def upload(client, filename):
    path = Path(filename)
    with path.open("rb") as source:
        content = source.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise WorkflowClientError("The original document exceeds the upload size limit.")
    digest = hashlib.sha256(content).hexdigest()
    row = await call(client, "workflows.documents.prepare_upload", {
        "name": path.name, "size": len(content), "sha256": digest,
    })
    identifier = row.get("document_id")
    if not isinstance(identifier, str) or not identifier or metadata(row, identifier, "document_id") != (len(content), digest):
        raise WorkflowClientError("The workflow upload metadata is invalid.")
    for offset in range(0, len(content), CHUNK):
        part = content[offset:offset + CHUNK]
        reply = await call(client, "workflows.documents.upload_chunk", {
            "document_id": identifier, "offset": offset,
            "content_base64": base64.b64encode(part).decode("ascii"),
        })
        if reply.get("document_id") != identifier or type(reply.get("received")) is not int or reply["received"] != offset + len(part):
            raise WorkflowClientError("The workflow upload acknowledgement is invalid.")
    row = await call(client, "workflows.documents.finish_upload", {"document_id": identifier})
    if metadata(row, identifier, "document_id") != (len(content), digest) or row.get("state") != "ready":
        raise WorkflowClientError("The workflow upload did not retain the complete original.")
    verified = await transfer(client, identifier, document=True)
    if (verified["size"], verified["sha256"]) != (len(content), digest):
        raise WorkflowClientError("The workflow upload checksum failed.")
    return row


def stdin_queue():
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    ended = asyncio.Event()

    def deliver(line):
        queue.put_nowait(line)
        if line is None:
            ended.set()

    def read():
        try:
            for line in sys.stdin:
                loop.call_soon_threadsafe(deliver, line)
        finally:
            if not loop.is_closed():
                loop.call_soon_threadsafe(deliver, None)

    threading.Thread(target=read, daemon=True).start()
    return queue, ended


def request(args):
    return {"message": args.message, "document_ids": args.document,
            "public_queries": json.loads(args.public_queries), "approved_urls": args.approved_url}


def check_session(result):
    if (type(result.get("schema_version")) is not int or result["schema_version"] != 1
            or type(result.get("protocol_version")) is not int or result["protocol_version"] != 2
            or not isinstance(result.get("session_id"), str) or not result["session_id"]
            or result.get("authenticated") is not True or result.get("direct_start") is not True):
        raise WorkflowClientError("The engine does not support authenticated interactive workflow protocol version 2.")
    return result



def check_run(result):
    run, state = result.get("run_id"), result.get("state")
    if (type(result.get("schema_version")) is not int or result["schema_version"] != 1
            or not isinstance(run, str) or not run
            or result.get("workflow_id") != "cs-legal-research"
            or state not in TERMINAL | {"queued", "running", "waiting"}):
        raise WorkflowClientError("The engine returned an invalid workflow run.")
    return run, state


async def legal(client, args):
    queue, ended = stdin_queue()
    body = legal_terminal if args.protocol == "terminal" else legal_session
    session_task = asyncio.create_task(body(client, args, queue))
    eof_task = asyncio.create_task(ended.wait())
    try:
        done, _ = await asyncio.wait({session_task, eof_task, client._recv_task}, return_when=asyncio.FIRST_COMPLETED)
        if session_task in done:
            return await session_task
        session_task.cancel()
        try:
            await asyncio.wait_for(session_task, timeout=1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        if eof_task in done:
            emit("closed", {"reason": "stdin_eof"})
            return 1
        raise WorkflowClientError("The interactive engine connection closed; start a new command.")
    finally:
        eof_task.cancel()
        if not session_task.done():
            session_task.cancel()
            await asyncio.gather(session_task, return_exceptions=True)


async def legal_session(client, args, queue):
    session = check_session(await call(client, "workflows.interactive.session"))
    emit("session", session)
    run, state = None, None
    try:
        result = await call(client, "workflows.interactive.start", request(args))
        run, state = check_run(result)
        emit("started", result)
        while True:
            try:
                line = await asyncio.wait_for(queue.get(), timeout=1)
            except asyncio.TimeoutError:
                if client._recv_task is not None and client._recv_task.done():
                    raise WorkflowClientError("The interactive engine connection closed; start a new command.")
                if run and state not in TERMINAL:
                    result = await call(client, "workflows.status", {"run_id": run})
                    state = result.get("state")
                    emit("status", result)
                continue
            if line is None:
                emit("closed", {"reason": "stdin_eof"})
                return 1
            try:
                action = json.loads(line)
                if not isinstance(action, dict):
                    raise ValueError
            except ValueError:
                raise WorkflowClientError("Send one JSON action object per input line.") from None
            verb = action.get("action")
            if verb == "respond" and run and state == "waiting":
                result = await call(client, "workflows.interactive.respond", {"run_id": run, "message": action.get("message")})
                state = result.get("state")
                emit("responded", result)
            elif verb == "status" and run:
                result = await call(client, "workflows.status", {"run_id": run})
                state = result.get("state")
                emit("status", result)
            elif verb == "download" and run and isinstance(action.get("output"), str) and action["output"]:
                result = await call(client, "workflows.status", {"run_id": run})
                if action.get("artifact_id") not in result.get("artifact_ids", []):
                    raise WorkflowClientError("Select an artifact from this workflow run.")
                emit("downloaded", await transfer(client, action["artifact_id"], destination=action["output"]))
            elif verb in {"cancel", "close"}:
                emit("closed", {"reason": verb})
                return 0
            else:
                raise WorkflowClientError("The action is unavailable in this interactive workflow state.")
    finally:
        if run and state not in TERMINAL:
            try:
                emit("cancelled", await call(client, "workflows.cancel", {"run_id": run}))
            except Exception:
                emit("cancellation_unverified", {"message": "Workflow cancellation could not be verified; inspect the run before continuing."})


async def terminal_input(queue, prompt):
    print(prompt, end="", flush=True)
    line = await queue.get()
    return line.rstrip("\r\n") if line is not None else None


async def legal_terminal(client, args, queue):
    session = check_session(await call(client, "workflows.interactive.session"))
    emit("session", session)
    run, state = None, None
    try:
        result = await call(client, "workflows.interactive.start", request(args))
        run, state = check_run(result)
        emit("started", result)
        while state not in TERMINAL:
            result = await call(client, "workflows.status", {"run_id": run})
            state = result.get("state")
            emit("status", result)
            if state == "waiting":
                answer = await terminal_input(queue, "Answer the engine question above, or type /cancel: ")
                if answer is None or answer.strip() == "/cancel":
                    return 1
                if not answer.strip():
                    continue
                result = await call(client, "workflows.interactive.respond", {"run_id": run, "message": answer})
                state = result.get("state")
                emit("responded", result)
            elif state not in TERMINAL:
                await asyncio.sleep(1)
        return 0 if state == "completed" else 1
    finally:
        if run and state not in TERMINAL:
            try:
                emit("cancelled", await call(client, "workflows.cancel", {"run_id": run}))
            except Exception:
                emit("cancellation_unverified", {"message": "Workflow cancellation could not be verified; inspect the run before continuing."})


async def execute(args):
    if args.workflow_action == "legal" and args.protocol == "terminal" and not sys.stdin.isatty():
        raise WorkflowClientError("Terminal workflow mode requires an interactive terminal; use --protocol json for a persistent coding-agent shell.")
    async with rpc.EngineClient(config.load()) as client:
        catalog = await discover(client)
        action = args.workflow_action
        if action == "legal":
            emit("catalog", catalog)
            return await legal(client, args)
        if action == "list":
            result = catalog
        elif action == "upload":
            result = await upload(client, args.path)
        elif action == "download":
            result = await transfer(client, args.identifier, document=args.document_original, destination=args.output)
        elif action == "suggest":
            result = await call(client, "workflows.suggest", {"message": args.message})
        elif action == "start":
            result = await call(client, "workflows.start", {"workflow_id": FINANCE, "message": args.message, "document_ids": args.document, "qonto": args.qonto})
        else:
            params = {"run_id": args.run_id}
            if action == "respond":
                params["message"] = args.message
            if action == "respond":
                previous = await call(client, "workflows.status", {"run_id": args.run_id})
                if previous.get("workflow_id") != FINANCE:
                    raise WorkflowClientError("Legal clarification requires its original interactive workflow command.")
            result = await call(client, "workflows." + action, params)
        emit(action, result)
        if getattr(args, "wait", False):
            run = result.get("run_id", getattr(args, "run_id", None))
            if not run:
                raise WorkflowClientError("The engine returned an invalid workflow run.")
            while result.get("state") not in TERMINAL | {"waiting"}:
                await asyncio.sleep(1)
                result = await call(client, "workflows.status", {"run_id": run})
                emit("status", result)
        return 1 if result.get("state") in TERMINAL - {"completed"} else 0


def command(args):
    try:
        return asyncio.run(execute(args))
    except WorkflowClientError as exc:
        emit("error", {"message": str(exc)})
    except (Exception, KeyboardInterrupt):
        emit("error", {"message": "The workflow operation failed. Check engine availability, sign-in, input and local file access."})
    return 1


def register(sub):
    parser = sub.add_parser("workflow", help="run private finance and interactive legal workflows on the engine")
    actions = parser.add_subparsers(dest="workflow_action", required=True)
    for name in ("list", "suggest", "upload", "start", "status", "respond", "cancel", "download", "legal"):
        child = actions.add_parser(name)
        child.set_defaults(func=command)
        if name in {"suggest", "start", "respond", "legal"}:
            child.add_argument("message")
        if name in {"status", "respond", "cancel"}:
            child.add_argument("run_id")
        if name in {"start", "legal"}:
            child.add_argument("--document", action="append", default=[], help="opaque uploaded document ID; repeatable")
        if name == "start":
            child.add_argument("--qonto", action="store_true", help="request the engine's existing managed bank authority")
        if name in {"start", "status", "respond"}:
            child.add_argument("--wait", action="store_true", help="poll until completion or a question")
        if name == "upload":
            child.add_argument("path", help="explicit local original document")
        if name == "download":
            child.add_argument("identifier", help="opaque artifact or document ID")
            child.add_argument("--output", required=True, help="explicit local output filename")
            child.add_argument("--document-original", action="store_true")
        if name == "legal":
            child.add_argument("--protocol", choices=["json", "terminal"], default="json", help="persistent JSON-lines input/output on one authenticated connection")
            child.add_argument("--public-queries", default="{}", help="explicitly scoped public query object")
            child.add_argument("--approved-url", action="append", default=[])
