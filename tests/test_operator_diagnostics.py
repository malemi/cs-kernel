"""Diagnostic evidence and read-only identity probes never authorize a replay."""
import copy
import io
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from cs import operator_diagnostics as diagnostics, operator_recovery as recovery


def describe(result=None, *, events=(), identity=None, **flags):
    rows = list(events)
    if result is not None:
        rows.append({"type": "result", **result})
    return diagnostics.describe(recovery.Attempt(1, rows, **flags), identity or {"provider": "Unknown"}, {})


for status, cause in ((401, "auth_failed"), (403, "auth_failed"), (402, "credit_refusal"),
                      (429, "rate_limit"), (503, "provider_unavailable"), (422, "request_rejected")):
    result = describe({"is_error": True, "api_error_status": status, "result": "private message"})
    assert result["cause"] == cause and result["http_status"] == status
    assert "private message" not in json.dumps(result)

for terminal, cause in (("error_max_budget_usd", "budget_exhausted"), ("budget_exhausted", "budget_exhausted"),
                        ("error_max_turns", "max_turns"), ("max_turns", "max_turns")):
    assert describe({"subtype": terminal})["cause"] == cause

assert describe(timed_out=True)["cause"] == "timeout"
assert describe(malformed=True)["cause"] == "invalid_output"
assert describe(overflow=True)["cause"] == "output_limit"
assert describe()["cause"] == "no_result"
assert describe({"is_error": True, "result": "Customer mentioned API Error: 402 yesterday"})["cause"] == "unknown_failure"
assert describe({"is_error": False, "result": "API Error: 402 quoted example"})["cause"] == "unknown_failure"
assert describe({"is_error": True, "result": "API Error: 402 provider refusal"})["cause"] == "credit_refusal"
assert describe({"is_error": True}, events=[{"type": "assistant", "error": "billing_error"}])["cause"] == "unknown_failure"

quota = describe({"api_error_status": 429}, events=[{
    "type": "rate_limit_event", "rate_limit_info": {
        "status": "rejected", "rateLimitType": "five_hour", "resetsAt": 1791892800}}])
assert quota["cause"] == "quota" and quota["limit_window"] == "five_hour"
assert quota["reset_at"] == "2026-10-13T12:00:00+00:00"
for remaining in (0, -1, 0.0):
    assert describe({"api_error_status": 402}, identity={"provider": "OpenRouter", "key_limit_remaining": remaining})["cause"] == "key_limit"
for remaining in (None, True, float("nan"), float("inf"), "0", 1):
    assert describe({"api_error_status": 402}, identity={"provider": "OpenRouter", "key_limit_remaining": remaining})["cause"] == "credit_refusal"
assert describe({"api_error_status": 402}, identity={"provider": "Anthropic API", "key_limit_remaining": 0})["cause"] == "credit_refusal"

clean_refusal = recovery.Attempt(1, [
    {"type": "system", "subtype": "init", "session_id": "session-safe"},
    {"type": "assistant", "is_api_error_message": True, "error": "billing_error",
     "message": {"content": [{"type": "text", "text": "private raw provider error"}]}},
    {"type": "result", "terminal_reason": "api_error", "api_error_status": 402,
     "is_error": True, "total_cost_usd": 0, "modelUsage": {},
     "usage": {"input_tokens": 0, "output_tokens": 0}, "subagent_stats": {"spawned": 0}},
])
assert recovery._prework_refusal(clean_refusal)
worked = copy.deepcopy(clean_refusal)
worked.events.insert(1, {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}})
assert diagnostics.describe(worked, {}, {})["cause"] == "credit_refusal"
assert not recovery._prework_refusal(worked)
private = describe({"is_error": True, "result": "sk-secret-customers", "terminal_reason": "<unsafe>"},
                   events=[{"type": "system", "session_id": "session-safe"},
                           {"type": "assistant", "session_id": "sk-secret-id", "error": "private error"}])
assert private["session_id"] == "session-safe"
assert "sk-secret" not in json.dumps(private) and "<unsafe>" not in json.dumps(private)
assert "private error" not in json.dumps(private)

base = {"cause": "quota", "provider": "Claude subscription", "account_email": "payer@example.test",
        "time_utc": "old", "session_id": "old-session"}
assert diagnostics.signature(base) == diagnostics.signature({**base, "time_utc": "new", "session_id": "new-session"})
assert diagnostics.signature(base) != diagnostics.signature({**base, "account_email": "other@example.test"})
assert diagnostics.signature({"provider": "OpenRouter", "primary": base}) != diagnostics.signature({
    "provider": "OpenRouter", "primary": {**base, "cause": "auth_failed"}})

PROBE = '''#!/usr/bin/env python3
import json, os, sys, time
assert sys.argv[1:] == ['auth', 'status', '--json']
with open(os.environ['PROBE_AUDIT'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + chr(10))
mode = os.environ.get('PROBE_MODE')
if mode == 'timeout':
    time.sleep(10)
if mode == 'malformed':
    print('private metadata error')
    sys.exit(1)
if mode == 'oversized':
    print('x' * 20000)
    sys.exit(1)
print(os.environ['PROBE_JSON'])
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    executable = root / "fake cli"
    executable.write_text(PROBE)
    executable.chmod(0o755)
    audit = root / "probe.jsonl"
    reported = {"authMethod": "claude.ai", "apiProvider": "firstParty", "email": "payer@example.test",
                "orgId": "payer-org", "apiKeySource": "ANTHROPIC_API_KEY", "apiKey": "sk-secret-value"}
    with patch.dict(os.environ, {"PROBE_AUDIT": str(audit), "PROBE_JSON": json.dumps(reported),
                                 "ANTHROPIC_API_KEY": "sk-unrelated-parent-credential", "ANTHROPIC_BASE_URL": "https://openrouter.ai/api"}):
        identity = diagnostics.primary_identity(str(executable))
        assert identity["provider"] == "Claude subscription"
        assert identity["account_email"] == "payer@example.test" and identity["organization_id"] == "payer-org"
        assert "sk-secret" not in json.dumps(identity) and "key_fingerprint" not in identity
        os.environ["PROBE_JSON"] = json.dumps({**reported, "authMethod": "api_key"})
        api = diagnostics.primary_identity(str(executable))
        assert api["provider"] == "Unknown" and api["credential_source"] == "ANTHROPIC_API_KEY"
        assert "account_email" not in api and "organization_id" not in api
        assert "key_fingerprint" not in api
        os.environ["PROBE_JSON"] = json.dumps({**reported, "authMethod": "api_key_helper",
                                               "apiKeySource": "apiKeyHelper"})
        with patch.object(Path, "open", return_value=io.BytesIO(b'\x7fELF')):
            helper = diagnostics.primary_identity(str(executable))
        assert helper['provider'] == 'OpenRouter'
        assert 'account_email' not in helper and 'key_fingerprint' not in helper
        for mode in ("malformed", "oversized", "timeout"):
            os.environ["PROBE_MODE"] = mode
            started = time.monotonic()
            with patch.object(diagnostics, "AUTH_TIMEOUT_SECONDS", 0.1):
                missing = diagnostics.primary_identity(str(executable))
            assert missing == {"provider": "Unknown", "identity_status": "unavailable"}
            assert time.monotonic() - started < 2
        assert len(audit.read_text().splitlines()) == 6
        assert all(json.loads(line) == ["auth", "status", "--json"] for line in audit.read_text().splitlines())
    assert diagnostics.primary_identity(str(root / "absent")) == {"provider": "Unknown", "identity_status": "unavailable"}

metadata = {"data": {"limit_remaining": 0, "limit": 10, "workspace_id": "workspace-safe",
                     "organization_id": "sk-do-not-copy", "creator_user_id": "invalid<customer>", "key": "sk-private"}}
with patch.object(recovery.urllib.request, "urlopen", return_value=io.StringIO(json.dumps(metadata))) as request:
    identity = recovery._openrouter_identity("sk-or-v1-123456789-secret-1234")
assert request.call_args.args[0].full_url == "https://openrouter.ai/api/v1/key"
assert identity["key_limit_remaining"] == 0 and identity["key_limit"] == 10
assert identity["workspace"] == "workspace-safe" and identity["organization"] == "unavailable"
assert identity["creator"] == "unavailable"
assert "sk-private" not in json.dumps(identity) and "sk-do-not-copy" not in json.dumps(identity)
print("operator diagnostics: cause evidence, unchanged prework gate, safe fields, bounded read-only probes and account isolation OK")

for reason, expected in [('success', 'completed'), ('completed', 'completed'),
                         ('error_max_budget_usd', 'budget_exhausted'),
                         ('budget_exhausted', 'budget_exhausted'), ('max_turns', 'max_turns'),
                         ('api_error', 'api_error'), ('error', 'error'), ('private-model-prose', 'unknown')]:
    value = describe({'terminal_reason': reason, 'total_cost_usd': 3.158979, 'is_error': False})
    assert value['native_terminal_reason'] == expected
    assert value['native_total_cost_usd'] == 3.158979
    assert 'run_budget_usd' not in value
for invalid in [None, True, False, -1, float('nan'), float('inf'), '3.15', {}, 2**53, 10**999]:
    value = describe({'terminal_reason': 'completed', 'total_cost_usd': invalid})
    assert 'native_total_cost_usd' not in value
assert describe({'total_cost_usd': 0})['native_total_cost_usd'] == 0
print('PASS: native cost and closed terminal evidence; invalid cost unavailable; opaque limit unknown')
