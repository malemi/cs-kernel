from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from . import config, rpc, task_assignment as authority

MAX_BYTES = 256 * 1024


def read_object(filename: str) -> dict:
    with Path(filename).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("assignment JSON exceeds 256 KiB")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("assignment JSON contains duplicate keys")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("assignment JSON must contain finite values")
    result = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(result, dict):
        raise ValueError("assignment JSON must be an object")
    return result


def write_object(filename: str, value: dict) -> None:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2).encode() + b"\n"
    descriptor = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def run(args) -> int:
    settings = config.load()
    try:
        if args.assignment_action == "status":
            if args.thread_key:
                result = authority.project(settings, args.thread_key)
                print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else authority.render(result))
                return 0 if result["complete"] else 3
            result = authority.listing(settings)
            result["projections"] = authority.projections(settings, [row["thread_key"] for row in result["items"]])
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if all(row["complete"] for row in result["projections"].values()) else 3
        if args.assignment_action in {"preview", "export"}:
            params = {"operation": args.operation, "thread_key": args.thread_key,
                      "expected_revision": args.revision, "reason": args.reason or ""}
            for name in ("assignee_uid", "task_id", "handled_ref", "source_id"):
                value = getattr(args, name, None)
                if value is not None:
                    params[name] = value
            result = rpc.call_sync(settings, "tasks.assignment.preview", params, timeout=60)
            if not isinstance(result, dict) or result.get("version") != 1 or result.get("actor_uid") != settings.engine_owner_uid:
                raise authority.AssignmentUnavailable("engine returned an invalid assignment intent")
            if result.get("thread_key") != args.thread_key or result.get("operation") != args.operation or result.get("expected_revision") != args.revision:
                raise authority.AssignmentUnavailable("engine intent differs from the requested operation")
            if args.assignment_action == "export":
                write_object(args.output, result)
                print(f"Exact assignment intent exported to {args.output}; approval requires the independent host operator.")
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        result = authority.commit(settings, read_object(args.intent), read_object(args.grant))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, authority.AssignmentUnavailable, rpc.EngineError) as exc:
        print(f"assignment UNKNOWN / not acknowledged: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


def register(sub) -> None:
    parser = sub.add_parser("assignment", help="engine-owned thread assignment; independent host approval required for writes")
    commands = parser.add_subparsers(dest="assignment_action", required=True)
    status = commands.add_parser("status", help="show authoritative assignment and held work")
    status.add_argument("thread_key", nargs="?")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=run)
    for name in ("preview", "export"):
        command = commands.add_parser(name, help="prepare an exact operation for independent human approval")
        command.add_argument("operation", choices=("assign", "reassign", "close"))
        command.add_argument("thread_key")
        command.add_argument("--revision", required=True, type=int)
        command.add_argument("--assignee-uid")
        command.add_argument("--task-id")
        command.add_argument("--reason")
        command.add_argument("--handled-ref")
        command.add_argument("--source-id", help="own-engine source ID; engine verifies reply evidence")
        if name == "export":
            command.add_argument("--output", required=True)
        command.set_defaults(func=run)
    commit = commands.add_parser("commit", help="submit an exact intent and independent host-signed grant")
    commit.add_argument("--intent", required=True)
    commit.add_argument("--grant", required=True)
    commit.set_defaults(func=run)
