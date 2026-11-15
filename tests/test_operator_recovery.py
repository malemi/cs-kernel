"""A real child process at the cron supervisor's retry boundary."""
import os
import asyncio
import json
import sys
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
import json, os, sys, time, subprocess

def discovery():
    script = """
from cs import operator_health as h, operator_workset as w
from cs.config import Settings
import json,sys,os
sys.argv=['cs',*h.ARGV]
owner=json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])['owner_uid']
s=Settings(slug='sample',engine_owner_uid=owner)
w.observe(s,'tasks',[])
w.observe(s,'review',{'drafts':[]})
v={'open':[],'resumed':[],'human_work':[],'assignment_audit':[],'operational_fixture_discovery':[],'assignment_incomplete':False,'read_incomplete':None}
v['triage_workset']=w.reserve(s,v)
out=json.dumps(v,ensure_ascii=False,indent=2)+chr(10)
h.capture(out.encode(),v,0,owner)
print(out,end='')
"""
    completed=subprocess.run([os.environ['FAKE_RUNTIME_PYTHON'],'-c',script],capture_output=True)
    if completed.returncode:
        print(completed.stderr.decode(),file=sys.stderr)
        raise SystemExit(completed.returncode)
    output=completed.stdout.decode()
    for index,command in enumerate(['whoami','config','tasks --json','review --json','campaign pending','unanswered --days 14 --json --all-buckets']):
        tool_id='phase-'+str(index)
        print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':tool_id,'name':'Bash','input':{'command':'.venv/bin/python -m cs '+command}}]}}))
        print(json.dumps({'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':tool_id,'is_error':False,'content':output if index==5 else '{}'}]}}))

args = sys.argv[1:]
if os.environ.get('FAKE_CALL_LOG'):
    with open(os.environ['FAKE_CALL_LOG'], 'a') as out:
        out.write(json.dumps(args) + chr(10))
if args == ['auth', 'status', '--json']:
    if os.environ.get('FAKE_AUTH') == 'unavailable':
        print('metadata unavailable')
        sys.exit(1)
    print(json.dumps({'authMethod': os.environ.get('FAKE_AUTH', 'claude.ai'),
          'apiProvider': 'firstParty', 'email': os.environ.get('FAKE_PAYER', 'payer@example.test'),
          'orgId': 'payer-organization', 'apiKeySource': 'ANTHROPIC_API_KEY',
          'untrusted': 'sk-do-not-persist-this-secret'}))
    sys.exit(0)
assert {os.environ.get(name) for name in ('BASH_DEFAULT_TIMEOUT_MS', 'BASH_MAX_TIMEOUT_MS')} == {'2730000'}
operator_rules = set(os.environ.get('FAKE_ALLOW_RULES', '').split('|'))
assert args[0] == '-p' and args[2] == '--verbose'
if os.environ.get('FAKE_SEND'):
    assert args[1] == '/cs-operator send briefing'
    assert set(args[args.index('--allowedTools') + 1:args.index('--disallowed-tools')]) == operator_rules
    assert os.environ.get('CS_HEADLESS_SEND') == '1'
    assert args[args.index('--disallowed-tools') + 1:] == ['Write', 'Agent', 'Task']
else:
    assert args[1] == '/cs-operator'
    assert '--allowedTools' not in args
    assert args[args.index('--disallowed-tools') + 1:] == ['Write', 'Bash(cs draft-send:*)', 'Agent', 'Task']
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
    if os.environ.get('FAKE_FALLBACK') in ('auth', 'rate', 'budget'):
        case = os.environ['FAKE_FALLBACK']
        print(json.dumps({'type': 'result', 'is_error': True,
              'api_error_status': {'auth': 401, 'rate': 429}.get(case),
              'terminal_reason': 'budget_exhausted' if case == 'budget' else 'api_error'}))
        sys.exit(1)
    if os.environ.get('FAKE_FALLBACK') == 'no_model':
        discovery()
        print(json.dumps({'type': 'result', 'result': 'completed', 'is_error': False}))
        sys.exit(0)
    discovery()
    print(json.dumps({'type': 'assistant', 'message': {'model': model,
          'content': [{'type': 'text', 'text': 'alternate worked'}]}}))
    print(json.dumps({'type': 'result', 'result': 'alternate worked', 'is_error': False,
          'modelUsage': {model: {}}}))
    sys.exit(0)
case = os.environ.get('FAKE_PRIMARY')
if case in ('auth', 'budget', 'unknown', 'invalid', 'no_result'):
    if case == 'invalid':
        print('invalid-secret-payload')
        sys.exit(1)
    if case == 'no_result':
        print(json.dumps({'type': 'system', 'subtype': 'init', 'session_id': 'safe-session-id'}))
        sys.exit(1)
    print(json.dumps({'type': 'result', 'is_error': True, 'session_id': 'safe-session-id',
          'api_error_status': 401 if case == 'auth' else None,
          'terminal_reason': 'error_max_budget_usd' if case == 'budget' else 'error',
          'result': 'private-customer-text sk-do-not-persist-this-secret'}))
    sys.exit(1)
if case == 'hang':
    time.sleep(10)
if case == 'success':
    model = os.environ.get('FAKE_PRIMARY_MODEL', 'claude-sonnet-5')
    discovery()
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
if case in ('payment', 'tool_payment'):
    events.pop(1)
    events[1]['error'] = 'billing_error'
    events[2]['api_error_status'] = 402
if case == 'tool_payment':
    events.insert(1, {'type': 'assistant', 'message': {'content': [{'type': 'tool_use'}]}})
for event in events: print(json.dumps(event), flush=True)
sys.exit(1)
'''


def _setup(root: Path):
    os.environ['FAKE_RUNTIME_PYTHON'] = sys.executable
    binary = root / "fake-claude"
    binary.write_text(FAKE_CLAUDE)
    binary.chmod(0o755)
    settings = Settings(slug="sample", engine_owner_uid="owner", email_address="owner@example.test",
                        email_password="sample-mail-password",
                        cron_fallback_model="~anthropic/claude-sonnet-latest",
                        cron_fallback_budget_usd=2.0)
    sent = []

    async def key(_settings):
        return "sample-key"

    def send(_settings, item):
        subject, plain, html = operator_recovery.operator_notices.render(_settings, item)
        kwargs = {"plain": plain, "html": html}
        assert subject.startswith(("INFO:", "RESOLVED:", "ACTION REQUIRED:"))
        assert kwargs.get("body_md") is None
        sent.append(kwargs["plain"])
        return "<notice@example.test>"

    return binary, settings, sent, key, send


async def successful_intake(_settings):
    return None


intake_fixture = patch.object(operator_recovery, "_mail_intake", successful_intake)
intake_fixture.start()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit", "FAKE_SEND": "1",
                              "CS_HEADLESS_SEND": "1",
                              "FAKE_ALLOW_RULES": "|".join(sorted(operator_recovery.SEND_ALLOW_RULES))}):
        binary, settings, sent, key, send = _setup(root)
        settings.cs_triage_mode = "send"
        send_allows = sorted(operator_recovery.SEND_ALLOW_RULES)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch("cs.operational_inbox.record_notice", send):
            assert operator_recovery.run(str(binary), ["Write"],
                                         prompt="/cs-operator send briefing",
                                         allows=send_allows) == 0
            assert len(sent) == 1 and "OpenRouter" in sent[0]
            assert operator_recovery.run(str(binary), ["Write"]) == 1
            assert len(sent) == 2 and "permissions" in sent[-1]
            del os.environ["CS_HEADLESS_SEND"]
            assert operator_recovery.run(str(binary), ["Write"],
                                         prompt="/cs-operator send briefing",
                                         allows=send_allows) == 1
            assert len(sent) == 2  # same mismatch is deduplicated

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exact = sorted(operator_recovery.EXACT_SEND_ALLOW_RULES)
    call_log = root / 'calls.jsonl'
    with patch.dict(os.environ, {'HOME': str(root), 'FAKE_PRIMARY': 'success', 'FAKE_SEND': '1',
                                'CS_HEADLESS_SEND': '1', 'FAKE_CALL_LOG': str(call_log),
                                'FAKE_ALLOW_RULES': '|'.join(exact)}):
        binary, settings, sent, key, send = _setup(root)
        settings.cs_triage_mode = 'send'
        with patch.object(operator_recovery.config, 'load', return_value=settings), \
                patch.object(operator_recovery, '_saved_openrouter_key', key), \
                patch.object(operator_recovery, '_openrouter_identity', return_value=IDENTITY), \
                patch('cs.operational_inbox.record_notice', send):
            assert operator_recovery.run(str(binary), ['Write'],
                prompt='/cs-operator send briefing', allows=exact) == 0
            def launches():
                return sum(json.loads(line)[0] == '-p' for line in call_log.read_text().splitlines())
            assert launches() == 1
            for invalid in (exact[:-1], exact + [exact[0]],
                            [*exact[:-1], sorted(operator_recovery.SEND_ALLOW_RULES)[0]],
                            exact + ['Bash(*)']):
                assert operator_recovery.run(str(binary), ['Write'],
                    prompt='/cs-operator send briefing', allows=invalid) == 1
            assert operator_recovery.run(str(binary), ['Write', exact[0]],
                prompt='/cs-operator send briefing', allows=exact) == 1
            settings.cs_triage_mode = 'draft'
            assert operator_recovery.run(str(binary), ['Write'],
                prompt='/cs-operator send briefing', allows=exact) == 1
            settings.cs_triage_mode = 'send'
            with patch.dict(os.environ, {'CS_HEADLESS_SEND': ''}):
                assert operator_recovery.run(str(binary), ['Write'],
                    prompt='/cs-operator send briefing', allows=exact) == 1
            assert launches() == 1, 'invalid mode/grants launched a model process'

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch("cs.operational_inbox.record_notice", send):
            denies = ["Write", "Bash(cs draft-send:*)"]
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 1 and "OpenRouter" in sent[-1]
            assert "usage allowance" in sent[-1]
            assert "anthropic/claude-sonnet-5" in sent[-1]
            assert "sk-or-v1-ABCD…WXYZ" in sent[-1]
            assert "Provider workspace ID: workspace-1" in sent[-1]
            assert "Provider key creator user ID: user-2" in sent[-1]
            assert f"Operator workspace: {Path.cwd()}" in sent[-1]
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 1  # same failure must not flood
            os.environ["FAKE_FALLBACK_MODEL"] = "anthropic/claude-sonnet-6"
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 2 and "anthropic/claude-sonnet-6" in sent[-1]
            os.environ["FAKE_PRIMARY"] = "success"
            assert operator_recovery.run(str(binary), denies) == 0
            assert len(sent) == 3 and "main service" in sent[-1]
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
             patch("cs.operational_inbox.record_notice", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert len(sent) == 1 and "Stopped." in sent[-1]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "payment"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch("cs.operational_inbox.record_notice", send):
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
             patch("cs.operational_inbox.record_notice", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert len(sent) == 1 and "http_status: 402" in sent[-1]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "hang"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "RUN_TIMEOUT_SECONDS", 0.1), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch("cs.operational_inbox.record_notice", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) != 0
            assert len(sent) == 1 and "Stopped." in sent[-1]

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
             patch("cs.operational_inbox.record_notice", send):
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
                raise OSError("Problem store unavailable")
            return send(*args, **kwargs)

        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch("cs.operational_inbox.record_notice", flaky):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 0
            assert len(sent) == 1

print("operator recovery: pre-work-only retry, same denies, notice transitions and retry OK")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit",
                                 "FAKE_FALLBACK": "no_model"}):
        binary, settings, sent, key, send = _setup(root)
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch.object(operator_recovery, "_saved_openrouter_key", key), \
             patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
             patch("cs.operational_inbox.record_notice", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert len(sent) == 1 and "without identifying the model" in sent[-1]
            assert "may already have happened" in sent[-1]
            assert IDENTITY["key"] in sent[-1]
            assert "Provider workspace ID: workspace-1" in sent[-1]
print("operator recovery: unreported backup model keeps account identity OK")

for case, cause in (("tool_payment", "credit_refusal"), ("tool", "quota"),
                    ("auth", "auth_failed"), ("budget", "budget_exhausted"),
                    ("unknown", "unknown_failure"), ("invalid", "invalid_output"),
                    ("no_result", "no_result")):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        calls = root / "calls.jsonl"
        with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": case,
                                     "FAKE_CALL_LOG": str(calls)}):
            binary, settings, sent, key, send = _setup(root)
            with patch.object(operator_recovery.config, "load", return_value=settings), \
                 patch.object(operator_recovery, "_saved_openrouter_key", key), \
                 patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
                 patch("cs.operational_inbox.record_notice", send):
                assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            launched = [json.loads(line) for line in calls.read_text().splitlines()]
            assert launched[0] == ["auth", "status", "--json"]
            assert len(launched) == 2 and launched[1][0] == "-p", (case, launched)
            assert len(sent) == 1 and f"Notice code: stopped/{cause}" in sent[0]
            assert "Provider account email: payer@example.test" in sent[0]
            assert "Provider account email: owner@example.test" not in sent[0]
            assert "Some actions may already have happened" in sent[0]
            assert "private-customer-text" not in sent[0]
            assert "sk-do-not-persist-this-secret" not in sent[0]
            assert "invalid-secret-payload" not in sent[0]
            assert "sk-do-not-persist-this-secret" not in operator_recovery._state_path(settings).read_text()
            if case in ("auth", "unknown", "no_result"):
                assert "safe-session-id" in sent[0]
            if case == "auth":
                assert f"{binary} auth login" in sent[0]

for case, cause in (("auth", "auth_failed"), ("rate", "rate_limit"),
                    ("budget", "budget_exhausted"), ("credit", "key_limit")):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        calls = root / "calls.jsonl"
        with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit",
                                     "FAKE_FALLBACK": case, "FAKE_CALL_LOG": str(calls)}):
            binary, settings, sent, key, send = _setup(root)
            metadata = [{**IDENTITY, "key_limit_remaining": 10}, {**IDENTITY, "key_limit_remaining": 0}]
            with patch.object(operator_recovery.config, "load", return_value=settings), \
                 patch.object(operator_recovery, "_saved_openrouter_key", key), \
                 patch.object(operator_recovery, "_openrouter_identity", side_effect=metadata) as read_key, \
                 patch("cs.operational_inbox.record_notice", send):
                assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert read_key.call_count == 2
            assert len(calls.read_text().splitlines()) == 3
            assert len(sent) == 1 and f"Notice code: stopped/{cause}" in sent[0]
            primary_body, backup_body = sent[0].split("Backup failure")
            assert "payer@example.test" in primary_body
            assert "payer@example.test" not in backup_body
            assert "Provider workspace ID: workspace-1" in backup_body
            assert "fixing the main service alone can restore" in sent[0]
            if case == "credit":
                assert "https://openrouter.ai/settings/keys" in backup_body
                assert "https://openrouter.ai/settings/credits" not in backup_body
            if case == "budget":
                assert "[knobs].cron_fallback_budget_usd" in backup_body
            if case == "auth":
                assert "In Desktop Settings for the engine profile" in backup_body
                assert "replace the saved OpenRouter API key" in backup_body
                assert "https://openrouter.ai/settings/keys" in backup_body

for auth in ("api_key", "unavailable"):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "auth", "FAKE_AUTH": auth}):
            binary, settings, sent, key, send = _setup(root)
            with patch.object(operator_recovery.config, "load", return_value=settings), \
                 patch("cs.operational_inbox.record_notice", send):
                assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
            assert "payer@example.test" not in sent[0]
            assert "Provider account email: owner@example.test" not in sent[0]
            assert f"{binary} auth status --json" in sent[0]
            assert "affected provider account could not be identified" in sent[0]
            if auth == "api_key":
                assert "ANTHROPIC_API_KEY" in sent[0]
            else:
                assert "Affected provider: Unknown" in sent[0]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "auth", "FAKE_PAYER": "old-payer@example.test"}):
        binary, settings, sent, key, send = _setup(root)
        settings.engine_owner_uid = 'old-engine-profile'
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch("cs.operational_inbox.record_notice", side_effect=OSError("Problem store unavailable")):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
        pending = operator_recovery._read_state(settings)["pending"]
        assert len(pending) == 1 and pending[0]["diagnostic"]["account_email"] == "old-payer@example.test"
        old_time = pending[0]["diagnostic"]["time_utc"]
        os.environ["FAKE_PAYER"] = "new-payer@example.test"
        settings.engine_owner_uid = 'new-engine-profile'
        with patch.object(operator_recovery.config, "load", return_value=settings), \
             patch("cs.operational_inbox.record_notice", send):
            assert operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"]) == 1
        assert len(sent) == 2
        assert "old-payer@example.test" in sent[0] and "new-payer@example.test" not in sent[0]
        assert old_time in sent[0]
        assert 'Engine profile UID: old-engine-profile' in sent[0]
        assert 'new-engine-profile' not in sent[0]
        assert 'Engine profile UID: new-engine-profile' in sent[1]
        assert "new-payer@example.test" in sent[1] and "old-payer@example.test" not in sent[1]
        assert not operator_recovery._read_state(settings)["pending"]

print("operator recovery: real child diagnostics, no replay after work, refreshed key cap, payer isolation and queued evidence OK")

intake_fixture.stop()

for case in ("success", "fallback", "invalid_permissions", "paused", "pause_during", "failure"):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        calls = root / "calls.jsonl"
        with patch.dict(os.environ, {"HOME": str(root), "FAKE_PRIMARY": "limit" if case == "fallback" else "success",
                                     "FAKE_CALL_LOG": str(calls)}):
            binary, settings, sent, key, send = _setup(root)
            seen = []

            async def intake(actual):
                assert actual is settings and not calls.exists()
                seen.append("intake")
                if case == "failure":
                    raise TimeoutError("private-body-secret")
                if case == "pause_during":
                    settings.pause_path.parent.mkdir(parents=True, exist_ok=True)
                    settings.pause_path.touch()

            if case == "paused":
                settings.pause_path.parent.mkdir(parents=True, exist_ok=True)
                settings.pause_path.touch()
            with patch.object(operator_recovery.config, "load", return_value=settings), \
                 patch.object(operator_recovery, "_mail_intake", intake), \
                 patch.object(operator_recovery, "_saved_openrouter_key", key), \
                 patch.object(operator_recovery, "_openrouter_identity", return_value=IDENTITY), \
                 patch("cs.operational_inbox.record_notice", send):
                code = operator_recovery.run(str(binary), ["Write", "Bash(cs draft-send:*)"],
                                            allows=["invalid"] if case == "invalid_permissions" else [])
            assert len(seen) == (0 if case in ("paused", "invalid_permissions") else 1)
            assert calls.exists() == (case in ("success", "fallback"))
            assert code == (1 if case in ("failure", "invalid_permissions") else 0)
            if case == "fallback":
                assert len(calls.read_text().splitlines()) == 3
            if case == "failure":
                assert "Neither assistant model was launched" in sent[0]
                assert "does not cancel engine ingestion" in sent[0]
                assert "private-body-secret" not in operator_recovery._state_path(settings).read_text()


async def intake_transport_checks():
    from cs.rpc import EngineClient
    from cs import rpc
    import websockets
    requests = []
    captured_clients = []
    secret = "private-provider-secret"
    result = {"scope": "email", "success": True, "errors": []}
    stall = False

    async def server(ws):
        async for raw in ws:
            request = json.loads(raw)
            requests.append(request)
            if stall:
                await ws.wait_closed()
                return
            await ws.send(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}))

    class CapturedClient(EngineClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured_clients.append(self)

    async with websockets.serve(server, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        settings = Settings(engine_ws_url=f"ws://127.0.0.1:{port}", engine_owner_uid="owner-only")
        with patch.object(operator_recovery.auth, "get_id_token", return_value=secret), \
             patch.object(operator_recovery, "EngineClient", CapturedClient), \
             patch.object(operator_recovery, "MAIL_INTAKE_SECONDS", .15), \
             patch.object(rpc.EngineClient, "_abandon", side_effect=AssertionError("inner deadline reached")):
            for value in ({"scope": "email", "success": True, "errors": []},
                          None, [], {"success": True, "errors": []},
                          {"scope": "all", "success": True, "errors": []},
                          {"scope": "email", "success": 1, "errors": []},
                          {"scope": "email", "success": False, "errors": []},
                          {"scope": "email", "success": True},
                          {"scope": "email", "success": True, "errors": ""},
                          {"scope": "email", "success": True, "errors": [secret]},
                          {"scope": "email", "success": True, "errors": [], "warnings": [secret]},
                          {"scope": "email", "success": True, "errors": [], "busy": True}):
                result = value
                try:
                    await operator_recovery._mail_intake(settings)
                    assert isinstance(value, dict) and type(value.get("success")) is bool and value == {"scope": "email", "success": True, "errors": []}
                except ValueError:
                    assert not (isinstance(value, dict) and type(value.get("success")) is bool and value == {"scope": "email", "success": True, "errors": []})
                client = captured_clients[-1]
                assert client._recv_task.done() and not client._pending and not client._handlers
            stall = True
            try:
                await operator_recovery._mail_intake(settings)
                raise AssertionError("stalled intake accepted")
            except TimeoutError:
                pass
            assert captured_clients[-1]._recv_task.done()
            assert all(row["method"] == "sync.run" and row["params"] == {"scope": "email", "days_back": 14}
                       for row in requests)

    class Transport:
        aborted = False
        def abort(self):
            self.aborted = True

    class StalledClose:
        def __init__(self, *args, **kwargs):
            self._recv_task = None
            self._handlers = set()
            self._ws = type("Socket", (), {"transport": Transport()})()
            captured_clients.append(self)
        async def __aenter__(self):
            self._recv_task = asyncio.create_task(asyncio.sleep(100))
            self._handlers.add(asyncio.create_task(asyncio.sleep(100)))
            return self
        async def call(self, method, params, timeout):
            return {"scope": "email", "success": True, "errors": []}
        async def __aexit__(self, *args):
            await asyncio.sleep(100)

    with patch.object(operator_recovery.auth, "get_id_token", return_value=secret), \
         patch.object(operator_recovery, "EngineClient", StalledClose), \
         patch.object(operator_recovery, "MAIL_INTAKE_CLOSE_SECONDS", .02):
        await operator_recovery._mail_intake(Settings())
        client = captured_clients[-1]
        assert client._ws.transport.aborted and client._recv_task.done()
        assert all(task.done() for task in client._handlers)


asyncio.run(intake_transport_checks())
print("mail intake: real child ordering, one intake across fallback, pause/refusal, real WebSocket strict contract and timeout, reader/handler cleanup and stalled-close abort OK")

# Constructed native protocol with real local prelaunch/live-child pin wiring.
# The child is a copied Python ELF, never a native model or provider acceptance.
import copy
import hashlib
import shutil
import shlex
from cs import operator_discovery_receipt as native_receipt, operator_health
from test_operator_native_composition import constructed, producer as constructed_producer

for kind, callback in [('foreground', False), ('automatic', False), ('automatic', True)]:
    events = constructed(kind, callback)
    attempt = operator_recovery.Attempt(0, events, native_producer=constructed_producer(), ordinary_native=True)
    assert attempt.result is events[-1] and attempt.lifecycle['proof']['version'] == 2
    attempt.native_producer = None
    assert attempt.result is None
    attempt.native_producer = constructed_producer()
    attempt.events = events[:-1]
    assert attempt.result is None
events = constructed()
events[1]['message']['content'][0]['name'] = 'Agent'
assert operator_recovery.Attempt(0, events, ordinary_native=True).result is None
for event in [dict(type='system',subtype='task_progress',task_type='local_agent'),
              dict(type='system',subtype='unknown-task'),dict(type='unknown-control'),
              dict(type='assistant',message={'content':None}),
              dict(type='rate_limit_event',rate_limit_info={'status':'rejected'}),
              dict(type='system',subtype='thinking_tokens',estimated_tokens=-1),
              dict(type='system',subtype='permission_check_status',status='checking'),
              dict(type='tool_progress',heartbeat=True)]:
    attempt=operator_recovery.Attempt(0,[event,{'type':'result','is_error':False}],ordinary_native=True)
    assert attempt.result is None and not operator_recovery._successful(attempt)

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    binary = root / 'versions' / 'offline-native-composition'
    binary.parent.mkdir()
    shutil.copyfile(Path(sys.executable).resolve(), binary)
    binary.chmod(0o700)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    settings = Settings(slug='sample', engine_owner_uid='offline-owner')
    actual_popen = operator_recovery.subprocess.Popen
    other = root / 'other' / 'versions' / binary.name
    other.parent.mkdir(parents=True)
    shutil.copyfile(binary, other); other.chmod(0o700)
    for case, ordinary, ambient in [(case, ordinary, ambient) for case, ordinary in [('direct', True), ('custom', False), ('wrapper', True), ('mismatch', True), ('killed', True), ('unknown', True)] for ambient in (None, '120000', 'invalid', '7200000')]:
        wrapped = case in ('wrapper', 'mismatch')
        ack = root / ('bound-' + case)
        argv_log = root / ('argv-' + case)
        env_log = root / ('env-' + case)
        events = constructed('automatic' if case in ('killed', 'unknown') else 'foreground')
        if case in ('killed', 'unknown'):
            events[1]['message']['content'][0]['input']['command'] = '.venv/bin/python -m cs review --json'
            next(e for e in events if e.get('patch', {}).get('status') == 'completed')['patch']['status'] = case
            next(e for e in events if e.get('subtype') == 'task_notification').update(status='stopped', summary='PRIVATE timeout text')
        events[0]['claude_code_version'] = binary.name
        driver = ('import json,time,pathlib,sys,os\n'
                  'pathlib.Path(' + repr(str(env_log)) + ').write_text(json.dumps({key:os.environ.get(key) for key in ("BASH_DEFAULT_TIMEOUT_MS","BASH_MAX_TIMEOUT_MS")}))\n'
                  'pathlib.Path(' + repr(str(argv_log)) + ').write_text(json.dumps(sys.argv[1:]))\n'
                  'events=json.loads(' + repr(json.dumps(events)) + ')\n'
                  'print(json.dumps(events[0]),flush=True)\n'
                  'deadline=time.monotonic()+2\n'
                  'while not pathlib.Path(' + repr(str(ack)) + ').exists() and time.monotonic()<deadline: time.sleep(.005)\n'
                  'for event in events[1:]: print(json.dumps(event),flush=True)\n')
        launcher = root / ('budget-' + case)
        launcher.write_text('#!/bin/bash\nexec ' + shlex.quote(str(binary)) + ' -c ' +
                            shlex.quote(driver) + ' --max-budget-usd 4.00 "$@"\n')
        launcher.chmod(0o700)
        commands = []
        def local_child(cmd, **kwargs):
            commands.append(cmd.copy())
            kwargs['env'] = dict(kwargs['env'], PYTHONHOME=sys.base_prefix)
            return actual_popen(cmd if wrapped else [cmd[0], '-c', driver], **kwargs)
        actual_bind = native_receipt.bind_native
        def bind_and_ack(pinned, child):
            bound = actual_bind(pinned, child)
            ack.touch()
            return bound
        with patch.object(native_receipt, 'CLAUDE_VERSION', binary.name), \
             patch.object(native_receipt, 'CLAUDE_SHA256', digest), \
             patch.object(native_receipt, 'pin_native', wraps=native_receipt.pin_native) as pins, \
             patch.object(native_receipt, 'bind_native', side_effect=bind_and_ack), \
             patch.object(operator_recovery.subprocess, 'Popen', side_effect=local_child), \
             patch.object(operator_recovery.config, 'load', return_value=settings), \
             patch.object(operator_health, 'assess', return_value=''), \
             patch.object(operator_health, 'inspection_failure', return_value=''), \
             patch.dict(os.environ, {'CS_OPERATOR_ACCEPTANCE_RECEIPT':'', 'HOME':str(root),
                        'CS_OPERATOR_NATIVE_BINARY':str(other if case == 'mismatch' else binary) if wrapped else ''}):
            for name in ('BASH_DEFAULT_TIMEOUT_MS', 'BASH_MAX_TIMEOUT_MS'):
                if ambient is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = ambient
            parent_environment = dict(os.environ)
            launch = str(launcher if wrapped else binary)
            attempt = operator_recovery._run(launch, ['Write'], prompt='/cs-operator' if ordinary else '/cs-signup')
            assert json.loads(env_log.read_text()) == {name: '2730000' if ordinary else ambient for name in ('BASH_DEFAULT_TIMEOUT_MS', 'BASH_MAX_TIMEOUT_MS')}
            assert dict(os.environ) == parent_environment
            assert commands[0][0] == launch
            assert attempt.ordinary_native is ordinary
            if wrapped:
                assert json.loads(argv_log.read_text())[:2] == ['--max-budget-usd', '4.00']
            if case == 'mismatch':
                assert pins.call_count >= 2 and attempt.native_producer is None and attempt.result is None
            elif case in ('killed', 'unknown'):
                assert attempt.code == 0 and attempt.result is None and not operator_recovery._successful(attempt)
                assert attempt.causal['cause'] == ('native_task_killed' if case == 'killed' else 'terminal_unavailable')
                if ambient is None:
                    from cs.observability_producers import store_for
                    source = store_for(settings)
                    records = source.events(limit=200)['events']
                    matching = [row for row in records if row.get('attempt_id') == attempt.diagnostic_context['attempt_id']]
                    if case == 'killed':
                        causes = [row['causal'] for row in matching if row.get('causal')]
                        assert causes and causes[-1]['cause'] == 'native_task_killed'
                        assert causes[-1]['refs']['child_event_id'] == attempt.child_event_id
                    retained = os.environ.get('BASH_TIME_EVIDENCE_DIR')
                    if retained:
                        Path(retained).mkdir(parents=True, exist_ok=True)
                        Path(retained, case + '.json').write_text(json.dumps(matching, indent=2))
                    if case == 'killed':
                        import subprocess, time
                        from cs.monitor_config import Component, MonitorConfig
                        manifest = root / 'manifest.toml'
                        manifest.write_text('[company]\nslug="sample"\n[engine]\nowner_uid="offline-owner"\n')
                        cli_env = {k:v for k,v in os.environ.items() if not k.startswith(('CS_', 'ENGINE_', 'EMAIL_'))}
                        cli_env.update(CS_MANIFEST=str(manifest), HOME=str(root), CS_ENGINE_OWNER_UID='offline-owner')
                        with patch.object(operator_recovery.subprocess, 'Popen', actual_popen):
                            cli = subprocess.run([sys.executable, '-m', 'cs', 'logs', 'events', '--local', '--json', '--limit', '200'], env=cli_env, capture_output=True, text=True, timeout=10)
                            assert cli.returncode == 0, cli.stderr
                            assert causes[-1] in [row.get('causal') for row in json.loads(cli.stdout)['local']['events']]
                            cfg = MonitorConfig(mode='filesystem', monitor_id='a'*32, owner_uid='offline-owner', state_dir=str(root/'monitor'), expected_start_utc=int(time.time()), components=[Component(id='operator', kind='kernel', local_root=str(source.root))])
                            cfgpath = root / 'monitor.json'; cfgpath.write_text(cfg.model_dump_json()); cfgpath.chmod(0o600)
                            collector = subprocess.run([sys.executable, '-m', 'cs', 'monitor', 'once', '--config', str(cfgpath)], env=cli_env, capture_output=True, text=True, timeout=10)
                        assert collector.returncode == 1, collector.stdout + collector.stderr
                        inbox = json.loads((root/'monitor'/'problems.json').read_text())
                        assert any(row['evidence'].get('causal') == causes[-1] for row in inbox['problems'])
                        diagnostic = operator_recovery.diagnostics.describe(attempt, {}, {})
                        assert diagnostic['cause'] == 'native_task_killed'
                        notice = operator_recovery.operator_notices.render(settings, {'status':'stopped', 'reason':diagnostic['cause'], 'diagnostic':diagnostic})[1]
                        assert 'upstream reason is unknown' in notice and 'BASH_DEFAULT_TIMEOUT_MS' in notice
                        assert 'PRIVATE' not in json.dumps(inbox) + cli.stdout + notice
                        if retained:
                            Path(retained, 'actual-cli.json').write_text(cli.stdout)
                            Path(retained, 'actual-inbox.json').write_text(json.dumps(inbox, indent=2))
            elif ordinary:
                assert pins.call_count >= 2 and attempt.native_producer
                assert attempt.lifecycle['proof']['version'] == 2 and attempt.result == events[-1]
                if case == 'direct' and ambient is None and os.environ.get('BASH_TIME_EVIDENCE_DIR'):
                    from cs.observability_producers import store_for
                    directory = Path(os.environ['BASH_TIME_EVIDENCE_DIR']); directory.mkdir(parents=True, exist_ok=True)
                    records = [row for row in store_for(settings).events(limit=200)['events'] if row.get('attempt_id') == attempt.diagnostic_context['attempt_id']]
                    (directory/'healthy.json').write_text(json.dumps(records, indent=2))
            else:
                assert pins.call_count == 0 and attempt.native_producer is None
                assert attempt.result == events[-1]
    for raw, expected in [('4', '4.00'), ('2.5', '2.50'), ('', None), ('0', ValueError), ('nan', ValueError), ('four', ValueError), ('fallback', '1.50')]:
        events = constructed('foreground')
        events[0]['claude_code_version'] = binary.name
        driver = 'import json\nfor event in json.loads(' + repr(json.dumps(events)) + '): print(json.dumps(event),flush=True)\n'
        commands = []
        def capped_child(cmd, **kwargs):
            commands.append(cmd.copy())
            kwargs['env'] = dict(kwargs['env'], PYTHONHOME=sys.base_prefix)
            return actual_popen([cmd[0], '-c', driver], **kwargs)
        with patch.object(operator_recovery.subprocess, 'Popen', side_effect=capped_child), \
             patch.object(operator_recovery.config, 'load', return_value=settings), \
             patch.object(operator_health, 'assess', return_value=''), \
             patch.object(operator_health, 'inspection_failure', return_value=''), \
             patch.dict(os.environ, {'CS_OPERATOR_ACCEPTANCE_RECEIPT':'', 'HOME':str(root), 'CS_OPERATOR_NATIVE_BINARY':'',
                        'CS_PRIMARY_BUDGET_USD':'9' if raw == 'fallback' else raw}):
            if expected is ValueError:
                runs_before = len(list((settings.state_dir / 'operator-runs').glob('run-*')))
                try:
                    operator_recovery._run(str(binary), ['Write'], prompt='/cs-signup')
                except ValueError as refused:
                    assert 'CS_PRIMARY_BUDGET_USD' in str(refused) and not commands
                    assert len(list((settings.state_dir / 'operator-runs').glob('run-*'))) == runs_before
                else:
                    raise AssertionError('an unusable primary budget ran: ' + raw)
                continue
            fallback = dict(model='provider/model', budget=1.5, key='offline-key') if raw == 'fallback' else {}
            attempt = operator_recovery._run(str(binary), ['Write'], prompt='/cs-signup', **fallback)
            assert attempt.result == events[-1]
            cmd = commands[0]
            assert cmd.count('--max-budget-usd') == (0 if expected is None else 1), cmd
            if expected is not None:
                assert cmd[cmd.index('--max-budget-usd') + 1] == expected, cmd
    print('PASS: CS_PRIMARY_BUDGET_USD caps the primary Claude run once; unset leaves the command unchanged; unusable refuses before launch; the fallback keeps its own cap')
print('PASS: ordinary metadata uses exact v2 terminal; real local ELF prelaunch/child pin, custom prompt compatibility. Constructed events, no native/provider acceptance.')

from jinja2 import Environment, FileSystemLoader
for skill in ('cs-operator', 'cs-triage-mail', 'cs-campaign-tick'):
    rendered = Environment(loader=FileSystemLoader([
        'cs/templates/project/.claude/skills/' + skill, 'cs/templates/partials'
    ])).get_template('SKILL.md.j2').render()
    assert 'Bash `timeout: 2730000` for discovery and review' in rendered, skill
    assert 'timeout: 600000' not in rendered, skill
    assert '`run_in_background`' in rendered and 'do not combine commands' in rendered
    assert 'pipe or redirect their output' in rendered and 'wrap them in another program' in rendered
    if skill == 'cs-operator':
        assert '.venv/bin/python -m cs review --json' in rendered
print('PASS: actual parent/triage/campaign discovery/review timeout 2730000; literal separate unwrapped commands')
