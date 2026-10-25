#!/usr/bin/env python3
"""Prepare isolated per-runtime observability candidates; never activate services.

Reads the actual selected services, copies each complete package/resources and
applies reviewed observations. A rejected patch or business-AST difference aborts.
No live pin, service, profile database, network route or customer data is changed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import stat
import subprocess

from adoption_instrument import (
    patch_m2,
    peer_setup,
    instrument_ws,
    instrument_gmail,
    instrument_dispatch,
    instrument_methods,
)
from adoption_proof import business_equal

M2_FILES = (
    "cli/main.py",
    "agents/emailer_agent.py",
    "llm/client.py",
    "rpc/server_ws.py",
    "rpc/setup.py",
    "rpc/server.py",
    "tools/gmail_tools.py",
    "services/job_executor.py",
)
NEW_FILES = (
    "observability.py",
    "observability_context.py",
    "observability_profile.py",
    "observability_producers.py",
    "observability_reader.py",
    "observability_recent.py",
    "observability_retention.py",
    "observability_store.py",
    "rpc/diagnostics.py",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def private_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")
    path.chmod(0o600)


def manifest(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError("Symlink in runtime package")
        if path.is_file():
            result[str(path.relative_to(root))] = {
                "sha256": digest(path.read_bytes()),
                "mode": stat.S_IMODE(path.stat().st_mode),
            }
    return result


def prepare_package(baseline: Path, output: Path, before: Path, reviewed: Path) -> dict:
    original_manifest = manifest(baseline)
    if output.exists():
        raise ValueError("Candidate destination already exists")
    shutil.copytree(
        baseline,
        output,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        copy_function=shutil.copy2,
    )
    edits = {}
    for rel in M2_FILES:
        path = output / rel
        old = path.read_text()
        if rel == "tools/gmail_tools.py":
            new = instrument_gmail(old)
        elif rel == "rpc/server_ws.py":
            new = instrument_ws(old)
        elif rel == "rpc/setup.py" and "async def _sync_run(" not in old:
            new = peer_setup(old)
        else:
            new = patch_m2(old, rel, before, reviewed)
        approved_logging = None
        if rel == "cli/main.py":
            current = (reviewed / rel).read_text()
            fn = next(
                n for n in ast.parse(current).body if getattr(n, "name", None) == "_setup_log_file"
            )
            approved_logging = ast.get_source_segment(current, fn)
        if not business_equal(
            old, new, logger_redactions=rel == "rpc/server_ws.py", approved_logging=approved_logging
        ):
            raise ValueError("Business AST changed: " + rel)
        path.write_text(new)
        edits[rel] = {
            "before": digest(old.encode()),
            "after": digest(new.encode()),
            "business_ast_equal": True,
        }
    for rel, transform in (
        ("rpc/dispatch.py", instrument_dispatch),
        ("rpc/methods.py", instrument_methods),
    ):
        path = output / rel
        old = path.read_text()
        new = transform(old, reviewed)
        if not business_equal(old, new):
            raise ValueError("Business AST changed: " + rel)
        path.write_text(new)
        edits[rel] = {
            "before": digest(old.encode()),
            "after": digest(new.encode()),
            "business_ast_equal": True,
        }
    for rel in NEW_FILES:
        target = output / rel
        if target.exists():
            raise ValueError("Existing observer module would be overwritten")
        shutil.copy2(reviewed / rel, target)
    result = manifest(output)
    untouched = set(original_manifest) - set(edits)
    if any(original_manifest[p] != result.get(p) for p in untouched):
        raise ValueError("Untouched runtime bytes or modes changed")
    return {
        "baseline_manifest": original_manifest,
        "candidate_manifest": result,
        "edits": edits,
        "new_files": list(NEW_FILES),
        "untouched_files_verified": len(untouched),
    }


def runtime_inventory(excluded_uid: str) -> list[dict]:
    result = []
    raw = subprocess.check_output(
        ["systemctl", "list-units", "zylch-server@*", "--plain", "--no-legend"], text=True
    )
    for line in raw.splitlines():
        unit = line.split()[0]
        uid = unit.removeprefix("zylch-server@").removesuffix(".service")
        props = {
            p: subprocess.check_output(
                ["systemctl", "show", unit, "--property", p, "--value"], text=True
            ).strip()
            for p in ("MainPID", "User", "DropInPaths")
        }
        pid = int(props["MainPID"])
        environment = dict(
            e.split(b"=", 1)
            for e in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
            if b"=" in e
        )
        pythonpath = environment[b"PYTHONPATH"].decode()
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        pins = []
        for name in props["DropInPaths"].split():
            data = Path(name).read_bytes()
            for raw_line in data.decode().splitlines():
                line = raw_line.strip()
                if line.startswith("Environment="):
                    for entry in shlex.split(line.partition("=")[2]):
                        if entry.startswith("PYTHONPATH="):
                            pins.append((name, entry.partition("=")[2]))
        if not pins:
            raise ValueError("No explicit source pin for " + uid)
        if pins[-1][1] != pythonpath:
            raise ValueError("Running source differs from configured winning pin: " + uid)
        result.append(
            {
                "uid": uid,
                "excluded": uid == excluded_uid,
                "unit": unit,
                "pid": pid,
                "user": props["User"],
                "pythonpath": pythonpath,
                "interpreter": argv[0].decode(),
                "baseline": str(Path(pythonpath.split(":")[0]) / "zylch"),
                "winning_pin": pins[-1][0],
            }
        )
    return result


def render_pin(original: bytes, old_pythonpath: str, new_pythonpath: str) -> bytes:
    """Prepare one exact assignment replacement; never write a live unit file."""
    lines = original.splitlines(keepends=True)
    found = []
    for index, raw_line in enumerate(lines):
        line = raw_line.decode().strip()
        if line.startswith("Environment=") and "PYTHONPATH=" + old_pythonpath in shlex.split(
            line.partition("=")[2]
        ):
            found.append(index)
    if len(found) != 1 or lines[found[0]].count(old_pythonpath.encode()) != 1:
        raise ValueError("Winning pin differs from running source or is ambiguous")
    lines[found[0]] = lines[found[0]].replace(old_pythonpath.encode(), new_pythonpath.encode(), 1)
    return b"".join(lines)


def import_probe(row: dict, root: Path) -> dict:
    """Import only pure diagnostic modules, denying socket/SQLite entry points."""
    program = """
import importlib,json,socket,sqlite3,sys
def denied(*args,**kwargs): raise RuntimeError('Forbidden network/database operation in adoption probe')
socket.create_connection=denied
socket.socket.connect=denied
socket.socket.connect_ex=denied
sqlite3.connect=denied
modules={}
for name in ('observability','observability_context','observability_profile','observability_producers','observability_reader','observability_recent','observability_retention','observability_store','rpc.diagnostics'):
 m=importlib.import_module('zylch.'+name)
 modules[name]=m.__file__
 if not m.__file__.startswith(sys.argv[1]+'/zylch/'):raise RuntimeError('Wrong observer import binding')
print(json.dumps(modules))
"""
    env = dict(os.environ, PYTHONPATH=str(root) + ":" + row["pythonpath"])
    result = subprocess.run(
        [row["interpreter"], "-c", program, str(root)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise ValueError(
            "Pure observer import probe failed: " + row["uid"] + ": " + result.stderr[-1200:]
        )
    return json.loads(result.stdout)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--before-m2", type=Path, required=True)
    parser.add_argument("--exclude-uid", required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, mode=0o700, exist_ok=True)
    args.output.chmod(0o700)
    inventory = runtime_inventory(args.exclude_uid)
    private_json(args.output / "inventory.json", inventory)
    prepared = []
    for row in inventory:
        if row["excluded"]:
            private_json(
                args.output / (row["uid"] + "-excluded.json"),
                {**row, "manifest": manifest(Path(row["baseline"]))},
            )
            continue
        root = args.output / row["uid"]
        root.mkdir(mode=0o700)
        pin = Path(row["winning_pin"])
        shutil.copy2(pin, root / "winning-pin.before")
        proof = prepare_package(
            Path(row["baseline"]), root / "zylch", args.before_m2, args.reviewed
        )
        proof.update(
            runtime=row,
            planned_pythonpath=str(root) + ":" + row["pythonpath"],
            winning_pin_sha256=digest(pin.read_bytes()),
            activated=False,
        )
        planned = root / "winning-pin.planned"
        shutil.copy2(pin, planned)
        planned.write_bytes(
            render_pin(pin.read_bytes(), row["pythonpath"], proof["planned_pythonpath"])
        )
        proof["rollback_pin"] = str(root / "winning-pin.before")
        proof["winning_pin_mode"] = stat.S_IMODE(pin.stat().st_mode)
        private_json(root / "proof.json", proof)
        compiled = subprocess.run(
            [row["interpreter"], "-m", "compileall", "-q", str(root / "zylch")],
            capture_output=True,
            text=True,
        )
        if compiled.returncode:
            raise ValueError("Candidate compilation failed")
        proof["pure_imports"] = import_probe(row, root)
        private_json(root / "proof.json", proof)
        prepared.append(
            {
                "uid": row["uid"],
                "candidate": str(root),
                "untouched": proof["untouched_files_verified"],
            }
        )
    private_json(args.output / "prepared.json", prepared)
    print(json.dumps({"prepared": prepared, "excluded": args.exclude_uid, "activated": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
