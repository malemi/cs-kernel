"""Deterministic supervision of the scheduled Claude Code operator tick.

The generated cron wrapper and authorized clone launchers invoke this module.
It owns the second process launch and owner notices so a quota refusal cannot
ask an LLM to repair itself.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.request
import hashlib
import shlex
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import auth, config, operator_diagnostics as diagnostics, operator_notices, send_mail
from .rpc import EngineClient
from . import observability_causal as causal
from .operator_native_lifecycle import continuation

MAX_CAPTURE_BYTES = 2_000_000
RUN_TIMEOUT_SECONDS = 3 * 3600
MAIL_INTAKE_SECONDS = 180
MAIL_INTAKE_CLOSE_SECONDS = 2
GATEWAY_BASE_URL = "https://openrouter.ai/api"
KEY_INFO_URL = "https://openrouter.ai/api/v1/key"
MODEL_RE = re.compile(r"~?anthropic/claude-[A-Za-z0-9._-]+\Z")
SEND_ALLOW_RULES = frozenset(
    f"Bash({prefix}cs chat:*)" for prefix in
    (".venv/bin/python -m ", ".venv/bin/python3 -m ", ".venv/bin/",
     "python -m ", "python3 -m ", "")
)
EXACT_SEND_ALLOW_RULES = frozenset(
    rule.replace("cs chat:", "cs draft-send:") for rule in SEND_ALLOW_RULES
)


@dataclass
class Attempt:
    code: int
    events: list[dict[str, Any]]
    malformed: bool = False
    overflow: bool = False
    stderr_present: bool = False
    timed_out: bool = False
    health_failure: str = ""
    native_producer: dict[str, Any] | None = None
    ordinary_native: bool = False
    health_context: dict[str, Any] | None = None
    business_read_proofs: list[dict[str, Any]] | None = None

    @property
    def needs_composition(self):
        if not self.ordinary_native:
            return False
        for event in self.events:
            if event.get("type") == "system" and event.get("subtype") != "init":
                return True
            if event.get("type") not in ("system", "assistant", "user", "result"):
                return True
            if event.get("type") in ("assistant", "user"):
                message = event.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("content"), list):
                    return True
                for block in message["content"]:
                    if not isinstance(block, dict) or (block.get("type") == "tool_use" and
                                                     block.get("name") in ("Agent", "Task")):
                        return True
        return False

    @property
    def lifecycle(self):
        if self.needs_composition:
            from .operator_native_composition import composition
            return composition(self.events, self.native_producer)
        return continuation(self.events)

    @property
    def result(self) -> dict[str, Any] | None:
        results = [event for event in self.events if event.get("type") == "result"]
        lifecycle = self.lifecycle
        if self.needs_composition:
            return lifecycle["terminal"] if lifecycle is not None else None
        if len(results) == 1:
            return results[0]
        return lifecycle["terminal"] if lifecycle is not None else None


class _NativeStreamCapture:
    """Private bounded diagnostics; recording never changes execution authority."""

    def __init__(self, directory: Path):
        self.directory_fd = None
        self.stream = None
        self.failed = False
        self.size = 0
        self.digest = hashlib.sha256()
        try:
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                meta = os.fstat(directory_fd)
                if meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != 0o700:
                    raise ValueError("native stream directory is not private")
            except (OSError, ValueError):
                os.close(directory_fd)
                raise
            self.directory_fd = directory_fd
            fd = os.open("native-stream.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=self.directory_fd)
            self.stream = os.fdopen(fd, "wb")
        except (OSError, ValueError):
            self.failed = True

    def append(self, raw: bytes, key: str):
        if self.failed:
            return
        data = raw.replace(key.encode(), b"[redacted]") if key else raw
        try:
            if self.size + len(data) > MAX_CAPTURE_BYTES:
                raise ValueError("native stream diagnostic limit")
            self.stream.write(data)
            self.digest.update(data)
            self.size += len(data)
        except (OSError, ValueError):
            self.failed = True

    def finish(self, attempt: Attempt, child_identity, stdout_bytes: int, redacted: bool):
        try:
            if self.stream is not None:
                try:
                    self.stream.close()
                except (OSError, ValueError):
                    self.failed = True
            manifest = {"schema_version": 1, "retention_complete": not self.failed and not attempt.overflow,
                        "retention_failed": self.failed, "stdout_bytes_seen": stdout_bytes,
                        "retained_bytes": self.size, "stream_sha256": self.digest.hexdigest(),
                        "fallback_key_redaction_enabled": redacted, "overflow": attempt.overflow,
                        "malformed": attempt.malformed, "timed_out": attempt.timed_out,
                        "child_identity": child_identity, "process_exit": attempt.code,
                        "accepted_event_count": len(attempt.events)}
            if self.directory_fd is not None:
                fd = os.open("native-stream.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.directory_fd)
                with os.fdopen(fd, "w") as stream:
                    json.dump(manifest, stream, sort_keys=True)
        except (OSError, ValueError):
            self.failed = True
        finally:
            if self.directory_fd is not None:
                try:
                    os.close(self.directory_fd)
                except OSError:
                    self.failed = True
        if self.failed:
            print("operator: native diagnostic stream retention failed", flush=True)


def _phase_receipts(events):
    uses = {}
    native_uses = []
    receipts = []
    for event in events:
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                tool_input = block.get("input")
                if not isinstance(tool_input, dict):
                    continue
                command = tool_input.get("command", "")
                if not isinstance(command, str) or "\n" in command or "\r" in command:
                    continue
                try:
                    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
                    lexer.whitespace_split = True
                    words = list(lexer)
                except ValueError:
                    continue
                if any(word and all(char in ";&|()<>" for char in word) for word in words) or any(
                        "$" in word or "`" in word for word in words):
                    continue
                if words[:3] in ([".venv/bin/python", "-m", "cs"], [".venv/bin/python3", "-m", "cs"]):
                    words = words[3:]
                elif words[:1] in ([".venv/bin/cs"], ["cs"]):
                    words = words[1:]
                else:
                    continue
                account = ""
                if words[:1] == ["--account"] and len(words) > 2:
                    account, words = words[1], words[2:]
                phase = {("whoami",): "identity", ("config",): "configuration",
                         ("tasks",): "tasks", ("tasks", "--json"): "tasks",
                         ("review", "--json"): "review", ("campaign", "pending"): "campaigns"}.get(tuple(words))
                if (len(words) == 5 and words[0] == "unanswered"
                        and all(words.count(flag) == 1 for flag in ("--days", "--json", "--all-buckets"))
                        and words.index("--days") < len(words) - 1
                        and words[words.index("--days") + 1] == "14"):
                    phase = "discovery"
                settings = config.load()
                if account:
                    founder_question = (f"List the mail to {settings.founder_sweep_account} from the last 4 days that still looks unanswered by a human. "
                                        "For each: sender, subject. List only, no drafts.")
                    phase = ("founder_tasks" if phase == "tasks" else
                             "founder_ask" if words == ["ask", founder_question] else None) if account == settings.founder_sweep_account else None
                if phase:
                    native_uses.append({"tool_use_id": block.get("id"), "phase": phase,
                                        "session_id": event.get("session_id"),
                                        "command_digest": hashlib.sha256(command.encode()).hexdigest()})
                    if isinstance(block.get("id"), str) and block["id"]:
                        uses[block["id"]] = (phase, hashlib.sha256(command.encode()).hexdigest())
            elif (block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str)
                  and block["tool_use_id"] in uses):
                phase, command_digest = uses[block["tool_use_id"]]
                output = block.get("content", "")
                if isinstance(output, list):
                    output = "\n".join(part.get("text", "") for part in output if isinstance(part, dict) and part.get("type") == "text")
                output = output if isinstance(output, str) else ""
                discovery_complete = None
                discovery = []
                held_count = 0
                error_status = None
                if phase == "discovery":
                    candidates = []
                    decoder = json.JSONDecoder()
                    for index, char in enumerate(output):
                        if char != "{":
                            continue
                        try:
                            value, _ = decoder.raw_decode(output[index:])
                        except ValueError:
                            continue
                        if isinstance(value, dict) and all(k in value for k in ("open", "human_work", "assignment_audit", "operational_fixture_discovery", "read_incomplete", "assignment_incomplete")):
                            candidates.append(value)
                    if len(candidates) == 1 and isinstance(candidates[0]["human_work"], list):
                        held_count = sum(isinstance(row, dict) and isinstance(row.get("assignment"), dict)
                                         and row["assignment"].get("complete") is False
                                         and row["assignment"].get("hold_auto_reply") is True
                                         for row in candidates[0]["human_work"])
                    status = re.match(r"(?:Error: )?Exit code (\d+)\n", output)
                    error_status = int(status[1]) if status else None
                    discovery_complete = len(candidates) == 1 and candidates[0]["read_incomplete"] is None and all(
                        isinstance(candidates[0][k], list) for k in ("open", "human_work", "assignment_audit", "operational_fixture_discovery")) and (
                        block.get("is_error", False) is False or (
                            candidates[0]["assignment_incomplete"] is True and held_count > 0 and error_status == 3 and
                            re.fullmatch(r"(?:Error: )?Exit code 3\n.*", output, re.S) is not None))
                    if discovery_complete:
                        discovery = [{k: row.get(k) for k in ("message_id", "provider_folder", "provider_uid", "provider_uidvalidity", "owner_uid", "body_sha256")}
                                     for row in candidates[0]["operational_fixture_discovery"] if isinstance(row, dict)]
                receipts.append({"phase": phase, "tool_use_id": block["tool_use_id"],
                                 "session_id": event.get("session_id"),
                                 "command_digest": command_digest, "output_digest": hashlib.sha256(output.encode()).hexdigest(),
                                 "is_error": block.get("is_error", False), "discovery_complete": discovery_complete,
                                 "discovery": discovery, "held_count": held_count, "error_status": error_status})
    return native_uses, receipts


def _write_acceptance_receipt(attempt, child_identity):
    value = os.environ.get("CS_OPERATOR_ACCEPTANCE_RECEIPT", "")
    nonce = os.environ.get("CS_OPERATOR_ACCEPTANCE_NONCE", "")
    if not value:
        return
    path = Path(value)
    parent = path.parent
    if (not path.is_absolute() or parent.resolve() != parent or path.is_symlink()
            or parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o077
            or not re.fullmatch(r"[a-f0-9]{32}", nonce)):
        raise ValueError("invalid private acceptance receipt destination")
    if not isinstance(attempt.events, list) or any(not isinstance(event, dict) for event in attempt.events):
        raise ValueError("invalid acceptance event sequence")
    settings = config.load()
    native_uses, phases = _phase_receipts(attempt.events)
    from .operator_discovery_receipt import join
    join(native_uses, phases, attempt.events, child_identity, settings.engine_owner_uid,
         attempt.native_producer, lifecycle=attempt.lifecycle)
    from .operator_read_outcomes import join as join_reads
    attempt.business_read_proofs = join_reads(attempt.events, child_identity, settings.engine_owner_uid,
        attempt.native_producer, attempt.lifecycle, attempt.health_context)
    result = attempt.result or {}
    sessions = [e.get("session_id") for e in attempt.events if e.get("type") == "system" and e.get("subtype") == "init"]
    lifecycle = attempt.lifecycle
    foreground_holds = ([task for task in lifecycle['proof']['tasks']
                         if task['kind'] == 'foreground' and task['exit_code'] in (1, 3)]
                        if lifecycle is not None and lifecycle['proof'].get('version') == 2 else [])
    for task in foreground_holds:
        business = [proof for proof in attempt.business_read_proofs
                    if proof.get('tool_use_id') == task['tool_use_id']
                    and proof.get('task_id') == task['task_id'] and proof.get('run_id') == task['run_id']
                    and proof.get('exit_code') == task['exit_code']]
        if len(business) == 1:
            continue
        matched = [row for row in phases if row.get('phase') == 'discovery' and
                   row.get('tool_use_id') == task['tool_use_id'] and
                   row.get('session_id') == lifecycle['proof']['session_id']]
        if (len(matched) != 1 or matched[0].get('discovery_complete') is not True or
                not isinstance(matched[0].get('transport'), dict) or
                matched[0]['transport'].get('exit_code') != 3):
            attempt.health_failure = 'discovery_transport_invalid'
    from .operator_health import native_read_failed
    discovery_proven = bool([row for row in phases if row.get('phase') == 'discovery']) and all(
        row.get('discovery_complete') is True and isinstance(row.get('transport'), dict)
        for row in phases if row.get('phase') == 'discovery')
    if native_read_failed(attempt.events, attempt.business_read_proofs, discovery_proven):
        attempt.health_failure = attempt.health_failure or 'execution_read_failed'
    stat = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    package_root = Path(__file__).parent
    package = [[str(p.relative_to(package_root)), hashlib.sha256(p.read_bytes()).hexdigest()]
               for p in sorted(package_root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    from .operator_health import inspection_failure
    inspection_status = (inspection_failure(attempt.events, attempt.health_context, phases,
                         settings.founder_sweep_enabled)
                         if attempt.ordinary_native and attempt.health_context else "unavailable")
    receipt = {"nonce": nonce, "owner_uid": settings.engine_owner_uid,
               "kernel_package_root": str(package_root), "pythonpath": os.environ.get("PYTHONPATH", ""),
               "kernel_source_digest": hashlib.sha256(json.dumps(package, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
               "supervisor_pid": os.getpid(), "supervisor_started_ticks": int(stat[19]),
               "child_identity": child_identity, "session_ids": sessions,
               "native_lifecycle": lifecycle["proof"] if lifecycle is not None else None,
               "native_rejection": None,
               "native_producer": attempt.native_producer,
               "terminal": {k: result.get(k) for k in ("session_id", "is_error", "terminal_reason", "num_turns")},
               "exit_code": attempt.code, "clean_terminal": _successful(attempt) and not attempt.health_failure,
               "native_tool_uses": native_uses, "phases": phases,
               "business_read_proofs": attempt.business_read_proofs,
               "business_read_context": attempt.health_context,
               "ordinary_inspection_status": inspection_status}
    if attempt.needs_composition and lifecycle is None:
        from .operator_native_composition import rejection
        receipt["native_rejection"] = rejection(attempt.events, attempt.native_producer)
    prior = json.loads(path.read_text()) if path.exists() else []
    if not isinstance(prior, list) or any(not isinstance(row, dict) or row.get("nonce") != nonce for row in prior):
        raise ValueError("acceptance receipt binding differs")
    fd, temp = tempfile.mkstemp(prefix=".acceptance-", dir=parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(prior + [receipt], stream, sort_keys=True)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@causal.attempt_scope
def _run(claude_bin: str, denies: list[str], *, prompt: str = "/cs-operator",
         allows: list[str] | None = None, model: str = "",
         budget: float = 0, key: str = "") -> Attempt:
    """Run one bounded-output process; never echo a credential from its output."""
    cmd = [claude_bin, "-p", prompt, "--verbose", "--output-format",
           "stream-json"]
    env = os.environ.copy()
    from . import operator_discovery_receipt
    ordinary_native = prompt.split(maxsplit=1)[0:1] == ["/cs-operator"]
    native_binary = env.get("CS_OPERATOR_NATIVE_BINARY", "")
    pinned = (operator_discovery_receipt.pin_native(native_binary or claude_bin)
              if ordinary_native or os.environ.get("CS_OPERATOR_ACCEPTANCE_RECEIPT") else None)
    if pinned is not None and not native_binary:
        cmd[0] = pinned['path']
    producer = None
    producer_checked = False
    from . import operator_health
    settings = config.load()
    run_root = settings.state_dir / "operator-runs"
    run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if run_root.resolve() != run_root.absolute():
        raise ValueError("ordinary run directory contains a symlink")
    operator_health.private(run_root, True)
    from .observability_retention import maintain, active
    maintain(settings)
    run_directory = tempfile.mkdtemp(prefix="run-", dir=run_root)
    active(run_directory)
    from .observability import context as diagnostic_context, current_context
    with diagnostic_context(current_context()):
        env['CS_DIAGNOSTIC_CONTEXT'] = json.dumps(current_context())
        from .observability_producers import emit as diagnostic_emit
        diagnostic_emit(settings, 'job', 'start', reason='none', evidence_ref=run_directory)
    supervisor, _ = operator_health.identity(os.getpid())
    health_context = {"directory": run_directory, "nonce": secrets.token_hex(16),
                      "supervisor": supervisor,
                      "owner_uid": settings.engine_owner_uid,
                      "workset_enabled": prompt.split(maxsplit=1)[0:1] == ["/cs-operator"]}
    env["CS_OPERATOR_HEALTH_CONTEXT"] = json.dumps(health_context)
    if ordinary_native:
        from .operator_context_delivery import overlay
        cmd.extend(["--include-hook-events", "--settings",
                    str(overlay(run_directory, sys.executable))])
    if os.environ.get("CS_OPERATOR_ACCEPTANCE_RECEIPT"):
        own_stat = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
        env["CS_OPERATOR_DISCOVERY_SUPERVISOR"] = json.dumps({"pid": os.getpid(), "started_ticks": int(own_stat[19])})
    if key:
        cmd.extend(["--model", model, "--max-budget-usd", format(budget, ".2f")])
        env.update(ANTHROPIC_BASE_URL=GATEWAY_BASE_URL, ANTHROPIC_AUTH_TOKEN=key,
                   ANTHROPIC_API_KEY="")
        env.pop("CLAUDE_CONFIG_DIR", None)
        for name in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                     "CLAUDE_CODE_USE_FOUNDRY"):
            env.pop(name, None)
    if allows:
        cmd.extend(["--allowedTools", *allows])
    # Scheduled mail has a symbolic shared workset. Native evidence agents
    # would bypass that scope and spend independently while the tick waits.
    scheduled_denies = ["Agent", "Task"] if prompt.split(maxsplit=1)[0:1] == ["/cs-operator"] else []
    cmd.extend(["--disallowed-tools", *denies, *scheduled_denies])
    events: list[dict[str, Any]] = []
    malformed = False
    overflow = False
    total = 0
    timed_out = False
    with tempfile.TemporaryFile() as stderr_file:
        with subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=stderr_file,
                              start_new_session=True) as proc:
            child_identity, _ = operator_health.identity(proc.pid)
            native_capture = _NativeStreamCapture(Path(run_directory))
            def stop_expired() -> None:
                nonlocal timed_out
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        return
                    timed_out = True

            watchdog = threading.Timer(RUN_TIMEOUT_SECONDS, stop_expired)
            watchdog.start()
            assert proc.stdout is not None
            try:
                for raw in proc.stdout:
                    if not producer_checked:
                        producer_checked = True
                        producer = operator_discovery_receipt.bind_native(pinned, child_identity)
                    total += len(raw)
                    if total > MAX_CAPTURE_BYTES:
                        overflow = True
                        continue
                    native_capture.append(raw, key)
                    line = raw.decode("utf-8", "replace").strip()
                    if key:
                        line = line.replace(key, "[redacted]")
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        malformed = True
                        print(line, flush=True)
                        continue
                    if not isinstance(event, dict):
                        malformed = True
                        continue
                    events.append(event)
                    if event.get("type") == "user":
                        from .operator_inventory_view import update_progress
                        try:
                            update_progress(events, health_context)
                        except (ValueError, KeyError, TypeError, OSError, RecursionError):
                            pass
                    if event.get("type") == "result":
                        summary = str(event.get("result") or "").strip()
                        if summary:
                            print(summary, flush=True)
                code = proc.wait()
            finally:
                watchdog.cancel()
        stderr_file.seek(0)
        stderr = stderr_file.read(MAX_CAPTURE_BYTES + 1)
    if len(stderr) > MAX_CAPTURE_BYTES:
        overflow = True
    stderr_text = stderr[:MAX_CAPTURE_BYTES].decode("utf-8", "replace").strip()
    if key:
        stderr_text = stderr_text.replace(key, "[redacted]")
    if stderr_text:
        print(stderr_text, flush=True)
    if overflow:
        print("operator: Claude event output exceeded the capture limit", flush=True)
    if timed_out:
        print("operator: Claude process exceeded its three-hour limit", flush=True)
    attempt = Attempt(code, events, malformed, overflow, bool(stderr_text), timed_out)
    attempt.native_producer = producer
    attempt.ordinary_native = ordinary_native
    attempt.health_context = health_context
    from .operator_read_outcomes import join as join_reads
    attempt.business_read_proofs = join_reads(events, child_identity, settings.engine_owner_uid,
        producer, attempt.lifecycle, health_context)
    native_capture.finish(attempt, child_identity, total, bool(key))
    from .observability_producers import emit as diagnostic_emit
    with diagnostic_context(json.loads(env['CS_DIAGNOSTIC_CONTEXT'])):
        child_event = diagnostic_emit(settings, 'job', 'failed' if code or timed_out else 'result',
                        reason='timeout' if timed_out else 'unknown' if code else 'none',
                        exit_code=code, evidence_ref=run_directory)
        causal.child(child_event)
    maintain(settings, active_directory=run_directory)
    _write_acceptance_receipt(attempt, child_identity)
    if _successful(attempt) and prompt.split(maxsplit=1)[0:1] == ["/cs-operator"]:
        attempt.health_failure = attempt.health_failure or operator_health.assess(
            health_context, child_identity, settings.engine_owner_uid)
        _, phase_results = _phase_receipts(attempt.events)
        if not attempt.health_failure:
            attempt.health_failure = operator_health.inspection_failure(
                attempt.events, health_context, phase_results, settings.founder_sweep_enabled)
        if operator_health.native_read_failed(attempt.events, attempt.business_read_proofs,
                discovery_proven=not operator_health.assess(health_context, child_identity, settings.engine_owner_uid)) or any(
                row.get("is_error") is True and row.get("phase") != "discovery"
                for row in phase_results):
            attempt.health_failure = attempt.health_failure or "execution_read_failed"
        if attempt.health_failure:
            with diagnostic_context(json.loads(env['CS_DIAGNOSTIC_CONTEXT'])):
                cause_event = diagnostic_emit(settings, 'context', 'failed', reason='incomplete-input', complete=False, method='operator.health.'+attempt.health_failure, **({'causal': causal.selected()} if causal.selected() else {}))
                causal.cause(cause_event)
        print(f"operator: ordinary discovery artifact directory {run_directory}", flush=True)
    return attempt


def _prework_refusal(attempt: Attempt) -> bool:
    """Accept a structured 402/429 with zero usage and no tool event."""
    if (attempt.code == 0 or attempt.malformed or attempt.overflow or
            attempt.stderr_present or attempt.timed_out):
        return False
    events = attempt.events
    if any(e.get("type") == "system" and str(e.get("subtype", "")).startswith("hook_") for e in events):
        from .operator_native_hooks import hook_indices
        try:
            indices = hook_indices(events)
            session = next(e["session_id"] for e in events if e.get("type") == "system" and e.get("subtype") == "init")
            if any(e.get("session_id") != session for e in events):
                return False
            for index in indices:
                event = events[index]
                if event["hook_event"] not in ("UserPromptSubmit", "MessageDisplay"):
                    return False  # Any tool boundary prevents pre-work replay.
                if event["subtype"] == "hook_response":
                    if event["stderr"]:
                        return False
                    text = event["stdout"]
                    # Only the observed fixed datetime hook may add pre-work text.
                    # Arbitrary output or structured additionalContext is not safe.
                    if text and (event["hook_event"] != "UserPromptSubmit" or re.fullmatch(
                            r"Now: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC  \|  [0-9]{2}:[0-9]{2} (?:EDT|EST) New York  \|  [0-9]{2}:[0-9]{2} (?:CEST|CET) Roma\n", text) is None):
                        return False
            events = [event for index, event in enumerate(events) if index not in indices]
        except (ValueError, KeyError, TypeError, StopIteration):
            return False
    types = [event.get("type") for event in events]
    if types not in (["system", "rate_limit_event", "assistant", "result"],
                     ["system", "assistant", "result"]):
        return False
    rate = events[1] if len(events) == 4 else None
    assistant, result = events[-2:]
    status = result.get("api_error_status")
    if status not in (402, 429):
        return False
    if status == 429:
        if rate is None or rate.get("rate_limit_info", {}).get("status") != "rejected":
            return False
        if rate.get("rate_limit_info", {}).get("rateLimitType") not in ("seven_day", "five_hour"):
            return False
        if assistant.get("error") != "rate_limit":
            return False
    elif rate is not None or assistant.get("error") not in ("billing_error", "api_error"):
        return False
    if not assistant.get("is_api_error_message") or assistant.get("parent_tool_use_id"):
        return False
    message = assistant.get("message") or {}
    if message.get("model") not in (None, "<synthetic>"):
        return False
    message_usage = message.get("usage") or {}
    if message_usage.get("input_tokens", 0) or message_usage.get("output_tokens", 0):
        return False
    blocks = message.get("content", [])
    if len(blocks) != 1 or blocks[0].get("type") != "text":
        return False
    if result.get("terminal_reason") != "api_error":
        return False
    if result.get("is_error") is not True or result.get("total_cost_usd") != 0:
        return False
    if result.get("modelUsage") != {}:
        return False
    usage = result.get("usage") or {}
    if any(usage.get(name, 0) != 0 for name in
           ("input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens")):
        return False
    if result.get("subagent_stats", {}).get("spawned", 0) != 0:
        return False
    if result.get("num_turns", 1) != 1:
        return False
    return True


def _successful(attempt: Attempt) -> bool:
    """A zero exit without a clean terminal result is not completed work."""
    result = attempt.result
    facts = dict(process_exit=attempt.code, malformed=attempt.malformed, overflow=attempt.overflow, timed_out=attempt.timed_out)
    checks = ((attempt.code != 0, 'process_exit', 'process_nonzero', 'process'),
              (attempt.malformed, 'native_capture_json', 'native_capture_malformed', 'native'),
              (attempt.overflow, 'native_capture_capacity', 'native_capture_overflow', 'native'),
              (attempt.timed_out, 'process_wait', 'process_wait_timeout', 'process'),
              (result is None, 'native_terminal_presence', 'terminal_unavailable', 'native'),
              (result is not None and result.get('is_error') is not False, 'native_terminal_error', 'terminal_error', 'native'),
              (result is not None and result.get('terminal_reason') in ('api_error', 'budget_exhausted', 'max_turns', 'error'), 'native_terminal_reason', 'terminal_rejected', 'native'))
    for failed, check, cause, layer in checks:
        if failed:
            if not getattr(attempt, 'causal', None):
                attempt.causal = causal.decision(check, cause, layer=layer, method='operator.native.terminal', replace=True, **facts)
            return False
    return True


def _effective_models(attempt: Attempt) -> str:
    """Names actually used by Claude, not the requested alias."""
    models = set()
    for event in attempt.events:
        if event.get("type") == "assistant":
            model = (event.get("message") or {}).get("model")
            if isinstance(model, str) and model and model != "<synthetic>":
                models.add(model)
    result = attempt.result or {}
    usage = result.get("modelUsage") or {}
    if isinstance(usage, dict):
        models.update(str(model) for model in usage if model)
    return ", ".join(sorted(models))


def _fallback_failure_reason(attempt: Attempt) -> str:
    """Classify only process metadata and HTTP codes, never agent-written text."""
    if attempt.timed_out:
        return "fallback_timeout"
    result = attempt.result or {}
    if result.get("terminal_reason") == "budget_exhausted":
        return "fallback_budget_exhausted"
    status = result.get("api_error_status")
    if status not in (402, 429):
        summary = result.get("result")
        match = re.search(r"\bAPI Error:\s*(402|429)\b", summary) if isinstance(summary, str) else None
        status = int(match.group(1)) if match else None
    return {402: "fallback_credit_refusal", 429: "fallback_rate_limited"}.get(
        status, "fallback_failed")


async def _mail_intake(settings: config.Settings) -> None:
    token = auth.get_id_token(settings)
    client = EngineClient(settings, id_token=token)

    async def request():
        await client.__aenter__()
        return await client.call("sync.run", {"scope": "email", "days_back": 14},
                                 timeout=MAIL_INTAKE_SECONDS + 60)

    try:
        result = await asyncio.wait_for(request(), MAIL_INTAKE_SECONDS)
        if (not isinstance(result, dict) or result.get("scope") != "email"
                or type(result.get("success")) is not bool
                or result["success"] is not True
                or not isinstance(result.get("errors"), list)
                or result["errors"] or result.get("warnings") or result.get("busy")):
            raise ValueError("mail intake result rejected")
    finally:
        tasks = [task for task in [client._recv_task, *client._handlers] if task is not None]
        try:
            await asyncio.wait_for(client.__aexit__(None, None, None), MAIL_INTAKE_CLOSE_SECONDS)
        except (Exception, asyncio.CancelledError):
            transport = getattr(client._ws, "transport", None)
            if transport is not None:
                transport.abort()
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True),
                                       MAIL_INTAKE_CLOSE_SECONDS)


async def _saved_openrouter_key(settings: config.Settings) -> str:
    async with EngineClient(settings) as client:
        result = await client.call("settings.get_secret", {"key": "OPENROUTER_API_KEY"},
                                   timeout=15)
    return str(result.get("value") or "").strip()


def _key_fingerprint(key: str) -> str:
    """Show a few key characters for identification, never a usable key."""
    return f"{key[:13]}…{key[-4:]}" if len(key) >= 24 else "[short key hidden]"


def _openrouter_identity(key: str) -> dict[str, Any]:
    """Read the current key's own metadata; no management credential is used."""
    identity: dict[str, Any] = {"key": _key_fingerprint(key), "workspace": "unavailable",
                "creator": "unavailable", "organization": "unavailable"}
    request = urllib.request.Request(
        KEY_INFO_URL, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read(16385)
            if len(raw) > 16384:
                raise ValueError("oversized key metadata")
            payload = json.loads(raw)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("invalid key metadata")
        for field, source in (("workspace", "workspace_id"),
                              ("creator", "creator_user_id"),
                              ("organization", "organization_id")):
            value = data.get(source)
            if (diagnostics.identifier(value) and isinstance(value, str)
                    and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value)):
                identity[field] = value
        for field, source in (("key_limit_remaining", "limit_remaining"), ("key_limit", "limit")):
            value = diagnostics.number(data.get(source))
            if value is not None:
                identity[field] = value
    except Exception as exc:
        print(f"operator: OpenRouter key metadata unavailable ({type(exc).__name__})",
              flush=True)
    return identity


def _backup_identity(identity: dict[str, Any]) -> dict[str, Any]:
    result = {"provider": "OpenRouter", "key_fingerprint": identity.get("key", "unavailable")}
    for old, new in (("workspace", "workspace_id"), ("creator", "creator_user_id"),
                     ("organization", "organization_id")):
        if identity.get(old) not in (None, "", "unavailable"):
            result[new] = identity[old]
    for name in ("key_limit_remaining", "key_limit"):
        if name in identity:
            result[name] = identity[name]
    return result


def _state_path(settings: config.Settings) -> Path:
    return settings.state_dir / "operator-route-notices.json"


def _read_state(settings: config.Settings) -> dict[str, Any]:
    path = _state_path(settings)
    if not path.exists():
        return {"current": "", "pending": []}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("pending"), list):
        raise ValueError("invalid operator notice state")
    return data


def _write_state(settings: config.Settings, state: dict[str, Any]) -> None:
    path = _state_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".operator-route-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump({key: value for key, value in state.items() if not key.startswith("_")}, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _notice(settings: config.Settings, state: dict[str, Any], status: str,
            model: str = "", reason: str = "",
            identity: dict[str, Any] | None = None,
            diagnostic: dict[str, Any] | None = None) -> bool:
    """Queue a transition, deliver pending notices, and retain failed sends."""
    if state.get("_delivery_failed") and status in ("primary", "fallback"):
        return False
    selected = causal.selected()
    signature = "|".join((status, model, reason, (identity or {}).get("key", "")))
    if diagnostic:
        signature += "|" + diagnostics.signature(diagnostic)
    if state.get("current") != signature:
        previous = str(state.get("current") or "")
        state["current"] = signature
        if status != "primary" or state.get("seen_primary"):
            state["pending"].append({"status": status, "model": model,
                                     "reason": reason,
                                     "identity": identity or {},
                                     "diagnostic": diagnostic or {},
                                     "causal": selected,
                                     "model_only": status == "primary" and
                                     previous.startswith("primary|")})
        _write_state(settings, state)
    state["seen_primary"] = True
    _write_state(settings, state)
    return _deliver_pending(settings, state)


def _deliver_pending(settings: config.Settings, state: dict[str, Any]) -> bool:
    if state.get("_delivery_failed"):
        return False
    while state["pending"]:
        item = state["pending"][0]
        try:
            from .operational_inbox import record_notice

            record_notice(settings, item)
        except Exception as exc:
            from .observability_producers import emit, error_metadata, error_reason
            observation = causal.decision('notice_persistence', 'record_write_failed', layer='notice', method='operator.notice', delivery_ok=False)
            if observation is not None:
                observation['refs']['cause_event_id'] = None
                observation['missing_refs'] = [key for key in causal.REFS if observation['refs'][key] is None]
            failure_event = emit(settings, 'alert', 'failed', reason=error_reason(exc), effect_certainty='none',
                 method='operator.notice', **({'causal': observation} if observation else {}), **error_metadata(exc))
            if observation is not None and causal.selected() is observation:
                causal.cause(failure_event)
                causal.retain_notice()
            print(f"operator: problem recording failed ({type(exc).__name__}); will retry", flush=True)
            state["_delivery_failed"] = True
            return False
        state["pending"].pop(0)
        from .observability_producers import emit
        emit(settings, 'alert', 'result', reason='none', effect_certainty='accepted',
             method='operator.notice', pending_count=len(state['pending']))
        _write_state(settings, state)
    return True


def _run_tick(claude_bin: str, denies: list[str], *, prompt: str = "/cs-operator",
        allows: list[str] | None = None) -> int:
    settings = config.load()
    state = _read_state(settings)
    _deliver_pending(settings, state)
    allows = allows or []
    mode = settings.cs_triage_mode.lower()
    ctx = diagnostics.context(settings, claude_bin)
    send_authorized = any(
        len(allows) == len(rules) and set(allows) == rules and not rules.intersection(denies)
        for rules in (SEND_ALLOW_RULES, EXACT_SEND_ALLOW_RULES)
    )
    if (mode not in ("draft", "send") or
            (mode == "send") != send_authorized or
            (mode == "draft" and bool(allows)) or
            (mode == "send" and os.environ.get("CS_HEADLESS_SEND") != "1") or
            (mode == "draft" and os.environ.get("CS_HEADLESS_SEND") == "1")):
        causal.decision('mode_authority', 'mode_mismatch', layer='configuration', method='operator.tick')
        print("operator: cron permissions disagree with cs_triage_mode", flush=True)
        ctx['mode_error'] = (f"configured mode={ctx['triage_mode']}; send tool permissions="
                             f"{send_authorized}; CS_HEADLESS_SEND="
                             f"{os.environ.get('CS_HEADLESS_SEND') == '1'}")
        _notice(settings, state, "stopped", reason="mode_mismatch",
                diagnostic=diagnostics.stopped('mode_mismatch', {}, ctx, no_work_proven=True))
        return 1
    if settings.pause_path.exists():
        causal.decision('pause_state', 'paused', layer='configuration', outcome='held', method='operator.tick')
        print("operator: paused before mail intake", flush=True)
        return 1 if state.get("_delivery_failed") else 0
    try:
        asyncio.run(_mail_intake(settings))
    except Exception as exc:
        causal.decision('mail_intake', 'intake_failed', layer='intake', method='sync.run')
        print(f"operator: mail intake failed ({type(exc).__name__})", flush=True)
        _notice(settings, state, "stopped", reason="mail_intake_failed",
                diagnostic=diagnostics.stopped('mail_intake_failed', {'provider': 'Engine'}, ctx))
        return 1
    if settings.pause_path.exists():
        causal.decision('pause_state', 'paused', layer='configuration', outcome='held', method='operator.tick')
        print("operator: paused after mail intake", flush=True)
        return 1 if state.get("_delivery_failed") else 0
    primary_identity = diagnostics.primary_identity(claude_bin)
    primary = _run(claude_bin, denies, prompt=prompt, allows=allows)
    if _successful(primary):
        causal.select(primary)
        if primary.health_failure:
            _notice(settings, state, "stopped", reason=primary.health_failure,
                    diagnostic=diagnostics.stopped(primary.health_failure, {"provider": "Engine"}, ctx))
            return 1
        delivered = _notice(settings, state, "primary", _effective_models(primary),
                            diagnostic={**primary_identity, 'context': ctx})
        if delivered:
            causal.decision('supervisor_completion', 'run_verified', layer='supervisor', outcome='accepted', method='operator.tick', replace=True)
        return 0 if delivered else 1
    prework = _prework_refusal(primary)
    source = primary_identity.get('credential_source')
    if (primary_identity.get('provider') == 'OpenRouter'
            and primary_identity.get('key_fingerprint')
            and source in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN')):
        primary_key = os.environ.get(source, '')
        if primary_key:
            primary_identity.update(_backup_identity(_openrouter_identity(primary_key)))
    primary_diagnostic = diagnostics.describe(primary, primary_identity, ctx, no_work_proven=prework)
    if not prework:
        causal.select(primary)
        _notice(settings, state, "stopped", reason=primary_diagnostic['cause'],
                diagnostic=primary_diagnostic)
        return primary.code or 1
    refusal = ("payment_required" if primary.result and
               primary.result.get("api_error_status") == 402 else "usage_limit")
    if settings.pause_path.exists():
        causal.decision('pause_state', 'paused', layer='configuration', outcome='held', method='operator.tick')
        print("operator: paused before fallback", flush=True)
        return 1 if state.get("_delivery_failed") else 0
    model = settings.cron_fallback_model.strip()
    budget = settings.cron_fallback_budget_usd
    if not MODEL_RE.fullmatch(model) or not math.isfinite(budget) or budget < 0.01:
        causal.decision('fallback_configuration', 'fallback_unconfigured', layer='configuration', method='operator.tick')
        print("operator: fallback model or budget is not configured", flush=True)
        _notice(settings, state, "stopped", reason="fallback_unconfigured",
                diagnostic=diagnostics.stopped('fallback_unconfigured', {'provider': 'OpenRouter'}, ctx,
                                               primary=primary_diagnostic, no_work_proven=True))
        return 1
    try:
        key = asyncio.run(_saved_openrouter_key(settings))
    except Exception as exc:
        causal.decision('fallback_credential', 'credential_unavailable', layer='configuration', method='operator.tick')
        print(f"operator: alternate credential unavailable ({type(exc).__name__})", flush=True)
        _notice(settings, state, "stopped", reason="credential_unavailable",
                diagnostic=diagnostics.stopped('credential_unavailable', {'provider': 'OpenRouter'}, ctx,
                                               primary=primary_diagnostic, no_work_proven=True))
        return 1
    if not key:
        causal.decision('fallback_credential', 'credential_unavailable', layer='configuration', method='operator.tick')
        print("operator: alternate credential is absent", flush=True)
        _notice(settings, state, "stopped", reason="credential_missing",
                diagnostic=diagnostics.stopped('credential_missing', {'provider': 'OpenRouter'}, ctx,
                                               primary=primary_diagnostic, no_work_proven=True))
        return 1
    if settings.pause_path.exists():
        causal.decision('pause_state', 'paused', layer='configuration', outcome='held', method='operator.tick')
        print("operator: paused before fallback", flush=True)
        return 1 if state.get("_delivery_failed") else 0
    identity = _openrouter_identity(key)
    if settings.pause_path.exists():
        causal.decision('pause_state', 'paused', layer='configuration', outcome='held', method='operator.tick')
        print("operator: paused before fallback", flush=True)
        return 1 if state.get("_delivery_failed") else 0
    fallback = _run(claude_bin, denies, prompt=prompt, allows=allows,
                    model=model, budget=budget, key=key)
    causal.select(fallback)
    if _successful(fallback):
        if fallback.health_failure:
            _notice(settings, state, "stopped", reason=fallback.health_failure,
                    diagnostic=diagnostics.stopped(fallback.health_failure, {"provider": "Engine"}, ctx))
            return 1
        used_model = _effective_models(fallback)
        if not used_model:
            causal.decision('fallback_model_report', 'model_unreported', layer='configuration', method='operator.tick')
            print("operator: alternate route did not report its effective model", flush=True)
            _notice(settings, state, "stopped", reason="fallback_model_unknown",
                    identity=identity,
                    diagnostic=diagnostics.stopped('model_unknown', _backup_identity(identity), ctx,
                                                   primary=primary_diagnostic, no_work_proven=False))
            return 1
        delivered = _notice(settings, state, "fallback", used_model, refusal,
                            identity=identity,
                            diagnostic={**_backup_identity(identity), 'context': ctx,
                                        'primary': primary_diagnostic})
        if delivered:
            causal.decision('supervisor_completion', 'run_verified', layer='supervisor', outcome='accepted', method='operator.tick', replace=True)
        return 0 if delivered else 1
    print("operator: alternate route failed", flush=True)
    # Re-read the key limit after the failed attempt; a pre-run balance cannot
    # establish which spending limit stopped this request.
    identity = _openrouter_identity(key)
    failure = diagnostics.describe(fallback, _backup_identity(identity), ctx, budget=budget)
    failure['credential_source'] = 'engine_saved_openrouter_key'
    failure['primary'] = primary_diagnostic
    _notice(settings, state, "stopped", reason=failure['cause'],
            identity=identity, diagnostic=failure)
    return fallback.code or 1



from .observability_producers import observe as _diagnostic_observe


@_diagnostic_observe("launch")
def run(claude_bin: str, denies: list[str], *, prompt: str = "/cs-operator",
        allows: list[str] | None = None) -> int:
    try:
        return _run_tick(claude_bin, denies, prompt=prompt, allows=allows)
    except Exception as exc:
        causal.decision('supervisor_exception', 'supervisor_exception', layer='supervisor', method='operator.tick')
        print(f"operator: supervisor failed ({type(exc).__name__})", flush=True)
        try:
            settings = config.load()
            state = _read_state(settings)
            _notice(settings, state, "stopped", reason="supervisor_failed",
                    diagnostic=diagnostics.stopped('supervisor_failed', {},
                                                  diagnostics.context(settings, claude_bin)))
        except Exception as alert_error:
            print(f"operator: supervisor alert unavailable ({type(alert_error).__name__})", flush=True)
        return 1


def main() -> int:
    if len(sys.argv) < 2:
        print("operator: missing Claude executable", file=sys.stderr)
        return 2
    try:
        args = sys.argv[2:]
        prompt = "/cs-operator"
        allows: list[str] = []
        if args[:1] == ["--prompt-env"]:
            if len(args) < 2 or not args[1].startswith("CS_OPERATOR_"):
                raise ValueError("invalid operator prompt environment variable")
            prompt = os.environ.get(args[1], "")
            if not prompt:
                raise ValueError("operator prompt is empty")
            args = args[2:]
        if args[:1] == ["--allowed-tools"]:
            if "--disallowed-tools" not in args:
                raise ValueError("missing disallowed-tools separator")
            split = args.index("--disallowed-tools")
            allows = args[1:split]
            args = args[split + 1:]
            if not allows:
                raise ValueError("empty allowed-tools list")
        if not args:
            raise ValueError("empty disallowed-tools list")
        return run(sys.argv[1], args, prompt=prompt, allows=allows)
    except Exception as exc:
        causal.decision('supervisor_exception', 'supervisor_exception', layer='supervisor', method='operator.tick')
        print(f"operator: supervisor failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
