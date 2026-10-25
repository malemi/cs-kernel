"""Constructed protocol controls; no native/model/provider invocation."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from cs import operator_context_delivery as delivery
from cs.operator_native_hooks import hook_indices


def fixture(values, kind='PostToolUse'):
    events = [{'type': 'system', 'subtype': 'init', 'session_id': 'constructed-session'}]
    for index, value in enumerate(reversed(values)):
        common = {'type': 'system', 'session_id': 'constructed-session', 'hook_id': str(index),
                  'hook_name': 'PostToolUse:Read' if kind == 'PostToolUse' else kind, 'hook_event': kind}
        events.append({**common, 'subtype': 'hook_started', 'uuid': 'start-' + str(index)})
        output = json.dumps({'hookSpecificOutput': {'hookEventName': kind, 'additionalContext': value}})
        events.append({**common, 'subtype': 'hook_response', 'uuid': 'end-' + str(index),
                       'output': output, 'stdout': output, 'stderr': '', 'exit_code': 0, 'outcome': 'success'})
    return events


envelope = {'owner_uid': 'constructed-owner', 'nonce': 'a'*32, 'source_identity': 'b'*64,
            'supervisor': {'pid': 1, 'started_ticks': 10},
            'native_invocation': {'child_identity': {'pid': 2, 'started_ticks': 20}},
            'raw_sha256': 'c'*64, 'view_sha256': ''}
view = ('visible é☕𐍈\n' * 1600).encode()
envelope['view_sha256'] = hashlib.sha256(view).hexdigest()
raw = json.dumps(envelope).encode()
values = delivery.parts(view, raw, envelope, 'constructed-session')
assert len(values) > 1 and all(len(v) < 10000 for v in values)
for kind in ('PostToolUse', 'UserPromptSubmit'):
    events = fixture(values, kind)
    assert delivery.delivered(events, view, raw, envelope)
    assert not delivery.delivered(events[:-2], view, raw, envelope)
    effect = {'message': {'content': [{'type': 'tool_use', 'name': 'Bash', 'input': {'command': 'cs draft-send exact'}}]}}
    assert not delivery.delivered([effect] + events, view, raw, envelope)
    assert delivery.delivered(events + [effect], view, raw, envelope)
    for mutate in (lambda e: e[-1].update(session_id='foreign'),
                   lambda e: e[-1].update(output='transformed'),
                   lambda e: e[-1].update(exit_code=2),
                   lambda e: e[-1].update(subtype='hook_progress')):
        bad = copy.deepcopy(events); mutate(bad)
        try: assert not delivery.delivered(bad, view, raw, envelope)
        except ValueError: pass
    duplicate = events + fixture(values)[1:]
    try: delivery.delivered(duplicate, view, raw, envelope)
    except ValueError: pass
    else: raise AssertionError('duplicate accepted')
for bad in (b'<system-reminder>', b'</system-reminder>', b'x' * (16*7000+1), ('𐍈'*7000).encode()):
    try: delivery.parts(bad, raw, envelope, 'constructed-session')
    except ValueError: pass
    else: raise AssertionError('unsafe/capacity payload accepted')
with tempfile.TemporaryDirectory() as folder:
    settings = json.loads(delivery.overlay(folder, '/usr/bin/python3').read_text())
    assert set(settings) == {'hooks'}
    assert len(settings['hooks']['PostToolUse'][0]['hooks']) == 16
    assert len(settings['hooks']['UserPromptSubmit'][0]['hooks']) == 16
    assert (Path(folder) / 'inventory-context-settings.json').stat().st_mode & 0o777 == 0o600
print('Constructed multipart UTF-8/order/limits/reserved/partial/session/duplicate/early-effects/additive-overlay PASS')

# Real separate supervisor/native/CLI/hook process ancestry; no native AI binary.
import os
import subprocess
import sys
from cs.operator_health import identity
worker = r'''
import json,os,subprocess,sys
from cs.operator_context_delivery import current_snapshot
ctx=json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
def hook(extra=0):
 return subprocess.run([sys.executable,'-B','-m','cs.operator_context_delivery','0'],input=json.dumps({'hook_event_name':'PostToolUse','session_id':'real-process-control','tool_response':'x'*extra}),text=True,capture_output=True,check=True).stdout
assert hook()==''
cli="""
import json,os,sys
from cs.operator_health import ARGV,capture
sys.argv=['constructed-cli']+ARGV
value={'triage_workset':{'complete':True,'limit':2,'selected':[],'deferred':[],'held':[]}}
output=json.dumps(value,ensure_ascii=False,indent=2)+'\\n'
capture(output.encode(),value,0,'constructed-owner')
from cs.operator_inventory_view import capture as legacy_capture
legacy_capture(json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT']))
"""
subprocess.run([sys.executable,'-B','-c',cli],check=True)
path,values=current_snapshot(ctx,'real-process-control')
assert len(values)==1
assert hook(4*1024*1024+1)==''
assert json.loads(hook(131298))['hookSpecificOutput']['additionalContext']==values[0]
assert hook()==''
for key,value in [('nonce','foreign'),('owner_uid','foreign')]:
 try:current_snapshot({**ctx,key:value},'real-process-control')
 except ValueError:pass
 else:raise AssertionError('foreign snapshot accepted')
print('real native/CLI/hook ancestry; absent then available capture; exact delivery and dedup PASS')
'''
with tempfile.TemporaryDirectory() as folder:
    context = {'directory': folder, 'owner_uid': 'constructed-owner', 'nonce': 'a'*32,
               'supervisor': identity(os.getpid())[0], 'workset_enabled': False}
    env = {**os.environ, 'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(context)}
    result = subprocess.run([sys.executable, '-B', '-c', worker],env=env,text=True,capture_output=True)
    assert result.returncode == 0, result.stderr
    print(result.stdout.strip())
    from cs.operator_context_delivery import current_snapshot
    try: current_snapshot(context, 'real-process-control')
    except (ValueError, OSError): pass
    else: raise AssertionError('foreign/exited native accepted')
