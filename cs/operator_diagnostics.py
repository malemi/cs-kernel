"""Bounded, non-generative evidence for operator repair notices.

Diagnostic classification never grants retry permission. Only allowlisted
metadata is retained; arbitrary model/tool output is not an email diagnostic.
"""
from __future__ import annotations

import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

AUTH_TIMEOUT_SECONDS = 5
AUTH_MAX_BYTES = 16384


def identifier(value: Any) -> str:
    if (isinstance(value, str) and not value.startswith(('sk-', 'Bearer '))
            and re.fullmatch(r'[A-Za-z0-9_.@+ -]{1,254}', value)):
        return value
    return ''


def fingerprint(key: str) -> str:
    return f'{key[:13]}…{key[-4:]}' if len(key) >= 24 else '[short key hidden]'


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def primary_identity(executable: str) -> dict[str, Any]:
    """Ask the same CLI entry point for auth metadata, never start an AI run."""
    result: dict[str, Any] = {'provider': 'Unknown', 'identity_status': 'unavailable'}
    try:
        with tempfile.TemporaryFile() as output:
            with subprocess.Popen([executable, 'auth', 'status', '--json'],
                                  stdin=subprocess.DEVNULL, stdout=output,
                                  stderr=subprocess.DEVNULL, start_new_session=True) as proc:
                try:
                    proc.wait(timeout=AUTH_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()
                    return result
                output.seek(0)
                raw = output.read(AUTH_MAX_BYTES + 1)
        if len(raw) > AUTH_MAX_BYTES:
            return result
        data = json.loads(raw)
        if not isinstance(data, dict):
            return result
    except (OSError, ValueError, TypeError):
        return result
    method = data.get('authMethod')
    if method not in ('none', 'claude.ai', 'oauth_token', 'api_key', 'api_key_helper', 'third_party'):
        return result
    result.update(auth_method=method, identity_status='reported')
    provider = str(data.get('apiProvider') or '').lower()
    providers = {'firstparty': 'Anthropic API', 'anthropic': 'Anthropic API',
                 'openrouter': 'OpenRouter', 'bedrock': 'Amazon Bedrock',
                 'vertex': 'Google Vertex', 'foundry': 'Microsoft Foundry'}
    result['provider'] = providers.get(provider, 'Unknown')
    # OAuth identity cannot identify the owner of an unrelated API key.
    if method == 'claude.ai' and provider == 'firstparty':
        result['provider'] = 'Claude subscription'
        for source, target in [('email', 'account_email'), ('orgId', 'organization_id')]:
            if value := identifier(data.get(source)):
                result[target] = value
    source = data.get('apiKeySource')
    if source in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'apiKeyHelper'):
        result['credential_source'] = source
    # Only a native executable guarantees there is no shell wrapper replacing
    # the inherited endpoint/key before invoking Claude. Opaque launchers must
    # leave unreported identity unknown, rather than borrowing the parent's key.
    try:
        with Path(shutil.which(executable) or executable).open('rb') as stream:
            native = stream.read(4) in (
                b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe')
    except OSError:
        native = False
    if not native and method in ('api_key', 'api_key_helper', 'third_party') and provider == 'firstparty':
        # Claude reports firstParty for compatible custom API endpoints too.
        # A launcher may replace the endpoint before forwarding auth status.
        result['provider'] = 'Unknown'
    if native and method in ('api_key', 'api_key_helper', 'third_party'):
        endpoint = os.environ.get('ANTHROPIC_BASE_URL', '')
        try:
            host = urlsplit(endpoint).hostname if endpoint else 'api.anthropic.com'
        except ValueError:
            host = None
        if host == 'openrouter.ai':
            result['provider'] = 'OpenRouter'
        elif host == 'api.anthropic.com' and provider == 'firstparty':
            result['provider'] = 'Anthropic API'
        elif endpoint:
            result['provider'] = 'Unknown'
        if source in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN') and os.environ.get(source):
            result['key_fingerprint'] = fingerprint(os.environ[source])
    return result


def context(settings: Any, executable: str, *, mode_error: str = '') -> dict[str, Any]:
    """Concrete paths and read-only commands from this scheduled workspace."""
    from .manifest import find_manifest_path
    workspace = str(Path.cwd())
    prefix = f'cd {shlex.quote(workspace)} && '
    manifest = find_manifest_path()
    return {
        'workspace': workspace, 'manifest_path': str(manifest.resolve()) if manifest else str(Path.cwd() / 'manifest.toml'),
        'engine_owner_uid': identifier(settings.engine_owner_uid),
        'log_path': str(settings.log_path), 'claude_bin': executable,
        'auth_command': prefix + shlex.join([executable, 'auth', 'status', '--json']),
        'doctor_command': prefix + shlex.join([executable, 'doctor']),
        'config_command': prefix + '.venv/bin/python -m cs config --all --json',
        'status_command': prefix + '.venv/bin/python -m cs cron status --json',
        'log_command': shlex.join(['tail', '-n', '80', str(settings.log_path)]),
        'fallback_model': (settings.cron_fallback_model if re.fullmatch(
            r'~?anthropic/claude-[A-Za-z0-9._-]+', settings.cron_fallback_model)
            else '(missing)' if not settings.cron_fallback_model else '(invalid value hidden)'),
        'fallback_budget_usd': settings.cron_fallback_budget_usd,
        'triage_mode': settings.cs_triage_mode if settings.cs_triage_mode in ('draft', 'send') else '(invalid)',
        'mode_error': mode_error,
    }


def describe(attempt: Any, identity: dict[str, Any], ctx: dict[str, Any],
             *, no_work_proven: bool = False, budget: float | None = None) -> dict[str, Any]:
    """Classify a failed attempt using native error markers, not assistant prose."""
    out = {**identity, 'context': ctx, 'exit_code': attempt.code,
           'no_work_proven': no_work_proven,
           'time_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    if budget is not None:
        out['run_budget_usd'] = budget
    result = attempt.result or {}
    terminal = result.get('terminal_reason') or result.get('subtype')
    if value := identifier(terminal):
        out['terminal_reason'] = value
    for event in attempt.events:
        if value := identifier(event.get('session_id')):
            out['session_id'] = value
        if event.get('type') == 'rate_limit_event':
            rate = event.get('rate_limit_info') or {}
            if isinstance(rate, dict) and rate.get('status') == 'rejected':
                if rate.get('rateLimitType') in ('five_hour', 'seven_day'):
                    out['limit_window'] = rate['rateLimitType']
                reset = number(rate.get('resetsAt'))
                if reset is not None:
                    try:
                        out['reset_at'] = datetime.fromtimestamp(reset, timezone.utc).isoformat()
                    except (ValueError, OverflowError, OSError):
                        pass
        if event.get('type') == 'assistant' and event.get('is_api_error_message') is True:
            if event.get('error') in ('billing_error', 'authentication_failed', 'authentication_error',
                                     'rate_limit', 'overloaded_error', 'api_error', 'invalid_request'):
                out['error_code'] = event['error']
    status = result.get('api_error_status')
    if type(status) is int and 400 <= status <= 599:
        out['http_status'] = status
    # Native CLI API-error results can omit the separate status field. Only
    # accept the anchored native prefix in an explicitly failed result.
    elif result.get('is_error') is True and isinstance(result.get('result'), str):
        match = re.match(r'^API Error:\s*(4\d\d|5\d\d)\b', result['result'])
        if match:
            out['http_status'] = int(match.group(1))
    status = out.get('http_status')
    error = out.get('error_code')
    cause = 'unknown_failure'
    if attempt.timed_out:
        cause = 'timeout'
    elif terminal in ('budget_exhausted', 'error_max_budget_usd'):
        cause = 'budget_exhausted'
    elif terminal in ('max_turns', 'error_max_turns'):
        cause = 'max_turns'
    elif status == 402 or error == 'billing_error':
        cause = 'credit_refusal'
        remaining = number(identity.get('key_limit_remaining'))
        if identity.get('provider') == 'OpenRouter' and remaining is not None and remaining <= 0:
            cause = 'key_limit'
    elif status in (401, 403) or error in ('authentication_failed', 'authentication_error'):
        cause = 'auth_failed'
    elif status == 429 or error == 'rate_limit':
        cause = 'quota' if 'limit_window' in out else 'rate_limit'
    elif status in (500, 502, 503, 504, 529) or error == 'overloaded_error':
        cause = 'provider_unavailable'
    elif status in (400, 404, 413, 422) or error == 'invalid_request':
        cause = 'request_rejected'
    elif attempt.overflow:
        cause = 'output_limit'
    elif attempt.malformed:
        cause = 'invalid_output'
    elif not result:
        cause = 'no_result'
    out['cause'] = cause
    return out


def stopped(cause: str, identity: dict[str, Any], ctx: dict[str, Any],
            **extra: Any) -> dict[str, Any]:
    return {**identity, 'cause': cause, 'context': ctx,
            'time_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'), **extra}


def signature(diagnostic: dict[str, Any]) -> str:
    """Only state/account changes notify again; time and session never do."""
    names = ('cause', 'provider', 'account_email', 'organization_id',
             'workspace_id', 'creator_user_id', 'key_fingerprint', 'limit_window')
    fields = {name: diagnostic[name] for name in names if diagnostic.get(name)}
    if isinstance(diagnostic.get('primary'), dict):
        fields['primary'] = signature(diagnostic['primary'])
    return json.dumps(fields, sort_keys=True, separators=(',', ':'))
