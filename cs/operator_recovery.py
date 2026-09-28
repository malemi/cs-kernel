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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config, send_mail
from .rpc import EngineClient

MAX_CAPTURE_BYTES = 2_000_000
RUN_TIMEOUT_SECONDS = 3 * 3600
GATEWAY_BASE_URL = "https://openrouter.ai/api"
KEY_INFO_URL = "https://openrouter.ai/api/v1/key"
MODEL_RE = re.compile(r"~?anthropic/claude-[A-Za-z0-9._-]+\Z")
SEND_ALLOW_RULES = frozenset(
    f"Bash({prefix}cs chat:*)" for prefix in
    (".venv/bin/python -m ", ".venv/bin/python3 -m ", ".venv/bin/",
     "python -m ", "python3 -m ", "")
)


@dataclass
class Attempt:
    code: int
    events: list[dict[str, Any]]
    malformed: bool = False
    overflow: bool = False
    stderr_present: bool = False
    timed_out: bool = False

    @property
    def result(self) -> dict[str, Any] | None:
        results = [event for event in self.events if event.get("type") == "result"]
        return results[-1] if len(results) == 1 else None


def _run(claude_bin: str, denies: list[str], *, prompt: str = "/cs-operator",
         allows: list[str] | None = None, model: str = "",
         budget: float = 0, key: str = "") -> Attempt:
    """Run one bounded-output process; never echo a credential from its output."""
    cmd = [claude_bin, "-p", prompt, "--verbose", "--output-format",
           "stream-json"]
    env = os.environ.copy()
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
    cmd.extend(["--disallowed-tools", *denies])
    events: list[dict[str, Any]] = []
    malformed = False
    overflow = False
    total = 0
    timed_out = False
    with tempfile.TemporaryFile() as stderr_file:
        with subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=stderr_file,
                              start_new_session=True) as proc:
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
                    total += len(raw)
                    if total > MAX_CAPTURE_BYTES:
                        overflow = True
                        continue
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
    return Attempt(code, events, malformed, overflow, bool(stderr_text), timed_out)


def _prework_refusal(attempt: Attempt) -> bool:
    """Accept a structured 402/429 with zero usage and no tool event."""
    if (attempt.code == 0 or attempt.malformed or attempt.overflow or
            attempt.stderr_present or attempt.timed_out):
        return False
    types = [event.get("type") for event in attempt.events]
    if types not in (["system", "rate_limit_event", "assistant", "result"],
                     ["system", "assistant", "result"]):
        return False
    rate = attempt.events[1] if len(attempt.events) == 4 else None
    assistant, result = attempt.events[-2:]
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
    return (attempt.code == 0 and not attempt.malformed and not attempt.overflow
            and not attempt.timed_out
            and result is not None and result.get("is_error") is False
            and result.get("terminal_reason") not in
            ("api_error", "budget_exhausted", "max_turns", "error"))


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


async def _saved_openrouter_key(settings: config.Settings) -> str:
    async with EngineClient(settings) as client:
        result = await client.call("settings.get_secret", {"key": "OPENROUTER_API_KEY"},
                                   timeout=15)
    return str(result.get("value") or "").strip()


def _key_fingerprint(key: str) -> str:
    """Show a few key characters for identification, never a usable key."""
    return f"{key[:13]}…{key[-4:]}" if len(key) >= 24 else "[short key hidden]"


def _openrouter_identity(key: str) -> dict[str, str]:
    """Read the current key's own metadata; no management credential is used."""
    identity = {"key": _key_fingerprint(key), "workspace": "unavailable",
                "creator": "unavailable", "organization": "unavailable"}
    request = urllib.request.Request(
        KEY_INFO_URL, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.load(response)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("invalid key metadata")
        for field, source in (("workspace", "workspace_id"),
                              ("creator", "creator_user_id"),
                              ("organization", "organization_id")):
            value = data.get(source)
            if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
                identity[field] = value
    except Exception as exc:
        print(f"operator: OpenRouter key metadata unavailable ({type(exc).__name__})",
              flush=True)
    return identity


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
            json.dump(state, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _notice(settings: config.Settings, state: dict[str, Any], status: str,
            model: str = "", reason: str = "",
            identity: dict[str, str] | None = None) -> bool:
    """Queue a transition, deliver pending notices, and retain failed sends."""
    signature = "|".join((status, model, reason, (identity or {}).get("key", "")))
    if state.get("current") != signature:
        previous = str(state.get("current") or "")
        state["current"] = signature
        if status != "primary" or state.get("seen_primary"):
            state["pending"].append({"status": status, "model": model,
                                     "reason": reason,
                                     "identity": identity or {},
                                     "model_only": status == "primary" and
                                     previous.startswith("primary|")})
        _write_state(settings, state)
    state["seen_primary"] = True
    _write_state(settings, state)
    while state["pending"]:
        item = state["pending"][0]
        kind = item["status"]
        cause = {
            "weekly_limit": "the Claude Code account reached its weekly limit",
            "payment_required": "the primary provider refused payment",
            "unknown_failure": "the primary run failed without proof that no work occurred",
            "fallback_failed": "the alternate provider or model failed",
            "fallback_credit_refusal": "OpenRouter returned HTTP 402 (payment or credit refusal)",
            "fallback_rate_limited": "OpenRouter returned HTTP 429 (rate limit)",
            "fallback_budget_exhausted": "the configured fallback budget was exhausted",
            "fallback_timeout": "the OpenRouter process exceeded its three-hour limit",
            "fallback_unconfigured": "the alternate model or per-tick budget is not configured",
            "credential_unavailable": "the alternate credential was unavailable",
            "mode_mismatch": "the cron permissions do not match its configured triage mode",
        }.get(item.get("reason"), "the scheduled operator could not complete its run")
        if kind == "fallback":
            detail = (f"Primary access failed because {cause}. Scheduled operator "
                      f"switched to OpenRouter. Model: {item['model']}.")
        elif kind == "primary":
            if item.get("model_only"):
                detail = f"Primary Claude Code model changed. Effective model: {item['model'] or 'unknown'}."
            else:
                detail = ("Scheduled operator returned to its primary Claude Code route. "
                          f"Effective model: {item['model'] or 'unknown'}.")
        else:
            detail = (f"Scheduled operator stopped because {cause}. "
                      "The next tick will try the primary route again.")
        detail += (f"\nOperator workspace: {settings.company_name or settings.slug or 'unknown'} "
                   f"(slug: {settings.slug or 'unknown'})."
                   f"\nOwner mailbox: {settings.email_address}."
                   f"\nEngine profile UID: {settings.engine_owner_uid or 'unavailable'}.")
        key_identity = item.get("identity") or {}
        if key_identity:
            detail += (f"\nOpenRouter key: {key_identity.get('key', 'unavailable')}."
                       f"\nOpenRouter workspace ID: {key_identity.get('workspace', 'unavailable')}."
                       f"\nOpenRouter key creator user ID: {key_identity.get('creator', 'unavailable')}."
                       f"\nOpenRouter organization ID: {key_identity.get('organization', 'unavailable')}.")
        plain = detail + "\n"
        html = ("<p>" + detail.replace("&", "&amp;").replace("<", "&lt;")
                .replace("\n", "<br>") + "</p>")
        try:
            send_mail.send(settings, settings.email_address, "URGENT: operator LLM route",
                           plain=plain, html=html)
        except Exception as exc:
            print(f"operator: owner alert failed ({type(exc).__name__}); will retry", flush=True)
            return False
        state["pending"].pop(0)
        _write_state(settings, state)
    return True


def run(claude_bin: str, denies: list[str], *, prompt: str = "/cs-operator",
        allows: list[str] | None = None) -> int:
    settings = config.load()
    state = _read_state(settings)
    allows = allows or []
    mode = settings.cs_triage_mode.lower()
    send_authorized = (len(allows) == len(SEND_ALLOW_RULES) and
                       set(allows) == SEND_ALLOW_RULES and
                       not SEND_ALLOW_RULES.intersection(denies))
    if (mode not in ("draft", "send") or
            (mode == "send") != send_authorized or
            (mode == "draft" and bool(allows)) or
            (mode == "send" and os.environ.get("CS_HEADLESS_SEND") != "1") or
            (mode == "draft" and os.environ.get("CS_HEADLESS_SEND") == "1")):
        print("operator: cron permissions disagree with cs_triage_mode", flush=True)
        _notice(settings, state, "stopped", reason="mode_mismatch")
        return 1
    primary = _run(claude_bin, denies, prompt=prompt, allows=allows)
    if _successful(primary):
        return 0 if _notice(settings, state, "primary", _effective_models(primary)) else 1
    if not _prework_refusal(primary):
        _notice(settings, state, "stopped", reason="unknown_failure")
        return primary.code or 1
    refusal = ("payment_required" if primary.result and
               primary.result.get("api_error_status") == 402 else "weekly_limit")
    if settings.pause_path.exists():
        print("operator: paused before fallback", flush=True)
        return 0
    model = settings.cron_fallback_model.strip()
    budget = settings.cron_fallback_budget_usd
    if not MODEL_RE.fullmatch(model) or not math.isfinite(budget) or budget < 0.01:
        print("operator: fallback model or budget is not configured", flush=True)
        _notice(settings, state, "stopped", reason="fallback_unconfigured")
        return 1
    try:
        key = asyncio.run(_saved_openrouter_key(settings))
    except Exception as exc:
        print(f"operator: alternate credential unavailable ({type(exc).__name__})", flush=True)
        _notice(settings, state, "stopped", reason="credential_unavailable")
        return 1
    if not key:
        print("operator: alternate credential is absent", flush=True)
        _notice(settings, state, "stopped", reason="credential_unavailable")
        return 1
    if settings.pause_path.exists():
        print("operator: paused before fallback", flush=True)
        return 0
    identity = _openrouter_identity(key)
    if settings.pause_path.exists():
        print("operator: paused before fallback", flush=True)
        return 0
    fallback = _run(claude_bin, denies, prompt=prompt, allows=allows,
                    model=model, budget=budget, key=key)
    if _successful(fallback):
        used_model = _effective_models(fallback)
        if not used_model:
            print("operator: alternate route did not report its effective model", flush=True)
            _notice(settings, state, "stopped", reason="unknown_failure")
            return 1
        return 0 if _notice(settings, state, "fallback", used_model, refusal,
                            identity=identity) else 1
    print("operator: alternate route failed", flush=True)
    _notice(settings, state, "stopped", reason=_fallback_failure_reason(fallback),
            identity=identity)
    return fallback.code or 1


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
        print(f"operator: supervisor failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
