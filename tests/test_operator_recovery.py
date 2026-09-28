"""A real child process at the cron supervisor's retry boundary."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from cs import operator_recovery
from cs.config import Settings

IDENTITY = {"key": "sk-or-v1-ABCD…WXYZ", "workspace": "workspace-1",
            "creator": "user-2", "organization": "unavailable"}
assert operator_recovery._key_fingerprint(
    "sk-or-v1-ABCDreallysecretWXYZ") == IDENTITY["key"]
with patch.object(operator_recovery.urllib.request, "urlopen", side_effect=OSError):
    missing = operator_recovery._openrouter_identity("sk-or-v1-ABCDreallysecretWXYZ")
    assert missing["key"] == IDENTITY["key"]
    assert missing["workspace"] == "unavailable"

assert operator_recovery._fallback_failure_reason(
    operator_recovery.Attempt(1, [{"type": "result", "result": "API Error: 402 credits"}])
) == "fallback_credit_refusal"


FAKE_CLAUDE = '''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
assert args[:3] == ['-p', '/cs-operator', '--verbose']
assert args[args.index('--disallowed-tools') + 1:] == ['Write', 'Bash(cs draft-send:*)']
assert 'sample-key' not in args
fallback = bool(os.environ.get('ANTHROPIC_BASE_URL'))
if fallback:
    model = os.environ.get('FAKE_FALLBACK_MODEL', 'anthropic/claude-sonnet-5')
    assert os.environ.get('ANTHROPIC_AUTH_TOKEN') == 'sample-key'
    assert os.environ.get('ANTHROPIC_API_KEY') == ''
    assert args.index('--model') < args.index('--disallowed-tools')
    assert not os.environ.get('CLAUDE_CONFIG_DIR')
    print('gateway warning', file=sys.stderr)
    if os.environ.get('FAKE_FALLBACK') == 'fail':
        print(json.dumps({'type': 'result', 'result': 'alternate failed', 'is_error': True}))
        sys.exit(1)
    if os.environ.get('FAKE_FALLBACK') == 'credit':
        print(json.dumps({'type': 'result', 'result': 'API Error: 402 available credits',
              'api_error_status': 402, 'is_error': True, 'terminal_reason': 'api_error'}))
        sys.exit(1)
    print(json.dumps({'type': 'assistant', 'message': {'model': model,
          'content': [{'type': 'text', 'text': 'alternate worked'}]}}))
    print(json.dumps({'type': 'result', 'result': 'alternate worked', 'is_error': False,
          'modelUsage': {model: {}}}))
    sys.exit(0)
case = os.environ.get('FAKE_PRIMARY')
if case == 'hang':
    time.sleep(10)
if case == 'success':
    model = os.environ.get('FAKE_PRIMARY_MODEL', 'claude-sonnet-5')
    print(json.dumps({'type': 'assistant', 'message': {'model': model,
          'content': [{'type': 'text', 'text': 'primary worked'}]}}))
    print(json.dumps({'type': 'result', 'result': 'primary worked', 'is_error': False,
          'modelUsage': {model: {}}}))
    sys.exit(0)
events = [
    {'type': 'system', 'subtype': 'init'},
    {'type': 'rate_limit_event', 'rate_limit_info': {'status': 'rejected', 'rateLimitType': 'seven_day'}},
    {'type': 'assistant', 'error': 'rate_limit', 'is_api_error_message': True,
     'message': {'content': [{'type': 'text', 'text': "You've hit your weekly limit"}]}},
    {'type': 'result', 'terminal_reason': 'api_error', 'api_error_status': 429,
     'is_error': True, 'total_cost_usd': 0, 'modelUsage': {},
     'usage': {'input_tokens': 0, 'output_tokens': 0}, 'subagent_stats': {'spawned': 0}},
]
if case == 'tool':
    events.insert(2, {'type': 'assistant', 'message': {'content': [{'type': 'tool_use'}]}})
if case == 'ambiguous':
    events[1]['rate_limit_info']['status'] = 'allowed'
if case == 'payment':
    events.pop(1)
    events[1]['error'] = 'billing_error'
    events[2]['api_error_status'] = 402
for event in events: print(json.dumps(event), flush=True)
sys.exit(1)
'''


def _setup(root: Path):
    binary = root / "fake-claude"
    binary.write_text(FAKE_CLAUDE)
    binary.chmod(0o755)
    settings = Settings(slug="sample", email_address="owner@example.test",
                        email_password="sample-mail-password",
                        cron_fallback_model="~anthropic/claude-sonnet-latest",
                        cron_fallback_budget_usd=2.0)
    sent = []

    async def key(_settings):
        return "sample-key"

    def send(_settings, to, subject, **kwargs):
        assert to == "owner@example.test"
        assert subject.startswith("URGENT")
        assert kwargs.get("body_md") is None
        sent.append(kwargs["plain"])
        return "<notice@example.test>"

    return binary, settings, sent, key, send


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch.object(operator_recovery.send_mail, "send", send):
            denies = ["Write", "Bash(cs draft-send:*)"]
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 1 and "OpenRouter" in sent[-1]
            assert "weekly limit" in sent[-1]
            assert "anthropic/claude-sonnet-5" in sent[-1]
            assert "sk-or-v1-ABCD…WXYZ" in sent[-1]
            assert "OpenRouter workspace ID: workspace-1" in sent[-1]
            assert "OpenRouter key creator user ID: user-2" in sent[-1]
            assert "Operator workspace: sample" in sent[-1]
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 1  # same failure must not flood
            os.environ["FAKE_FALLBACK_MODEL"] = "anthropic/claude-sonnet-6"
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 2 and "anthropic/claude-sonnet-6" in sent[-1]
            os.environ["FAKE_PRIMARY"] = "success"
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 3 and "primary" in sent[-1]
            os.environ["FAKE_PRIMARY_MODEL"] = "claude-sonnet-6"
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 4 and "model changed" in sent[-1]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "tool"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch.object(operator_recovery.send_mail, "send", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert len(sent) == 1 and "stopped" in sent[-1]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "payment"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch.object(operator_recovery.send_mail, "send", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 0
            assert len(sent) == 1 and "OpenRouter" in sent[-1]
            assert "payment" in sent[-1]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit",
                              "FAKE_FALLBACK": "credit"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch.object(operator_recovery.send_mail, "send", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert len(sent) == 1 and "HTTP 402" in sent[-1]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "hang"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "RUN_TIMEOUT_SECONDS", 0.1), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch.object(operator_recovery.send_mail, "send", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) != 0
            assert len(sent) == 1 and "stopped" in sent[-1]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit",
                              "FAKE_FALLBACK": "fail"}):
        binary, settings, sent, key, send = _setup(root)

        def pause_during_metadata(_key):
            settings.pause_path.parent.mkdir(parents=True, exist_ok=True)
            settings.pause_path.touch()
            return IDENTITY

        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", pause_during_metadata), \
             patch.object(operator_recovery.send_mail, "send", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 0
            assert not sent

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit"}):
        binary, settings, sent, key, send = _setup(root)
        attempts = [0]

        def flaky(*args, **kwargs):
            attempts[0] += 1
            if attempts[0] == 1:
                raise OSError("SMTP unavailable")
            return send(*args, **kwargs)

        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch.object(operator_recovery.send_mail, "send", flaky):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 0
            assert len(sent) == 1

print("operator recovery: pre-work-only retry, same denies, notice transitions and retry OK")
