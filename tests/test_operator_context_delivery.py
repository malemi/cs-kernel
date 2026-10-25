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
for bad in (b'<system-reminder>', b'</system-reminder>', b'x' * (delivery.SLOTS*delivery.CHARS+1), ('𐍈'*7000).encode()):
    try: delivery.parts(bad, raw, envelope, 'constructed-session')
    except ValueError: pass
    else: raise AssertionError('unsafe/capacity payload accepted')
stale = {**envelope, 'source_identity': 'd' * 64}
try:
    delivery.delivered(fixture(values), view, raw, stale)
except ValueError:
    pass
else:
    raise AssertionError('stale source accepted')
from unittest.mock import patch
with patch('cs.config.load', return_value=object()), patch('cs.observability_producers.emit') as record:
    diagnostic = delivery.capacity_failure(delivery.CapacityError(49), emit=True)
    assert record.call_count == 1
    metadata = record.call_args.kwargs
    assert metadata['causal']['facts'] == {'required': 49, 'available': 48}
    assert metadata['error_file'] == 'cs/operator_context_delivery.py'
    assert metadata['method'] == 'operator.discovery.context'
full_view = b'x' * ((delivery.SLOTS - 1) * delivery.CHARS)
full_values = delivery.parts(full_view, raw, envelope, 'constructed-session')
assert len(full_values) == 48
assert ''.join(value.split('\n', 1)[1] for value in full_values).encode() == raw + full_view
assert all(len(value.encode('utf-16-le')) // 2 < 10000 for value in full_values)
assert delivery.delivered(fixture(full_values), full_view, raw, envelope)
assert not delivery.delivered(fixture(full_values)[:-2], full_view, raw, envelope)
try:
    delivery.parts(b'x' * (48 * delivery.CHARS), raw, envelope, 'constructed-session')
except delivery.CapacityError as exc:
    assert exc.required == 49
    diagnostic = delivery.capacity_failure(exc)
    assert diagnostic['facts'] == {'required': 49, 'available': 48}
    assert diagnostic['cause'] == 'context_slots_exhausted'
else:
    raise AssertionError('49 parts accepted')
with tempfile.TemporaryDirectory() as folder:
    settings = json.loads(delivery.overlay(folder, '/usr/bin/python3').read_text())
    assert set(settings) == {'hooks'}
    assert len(settings['hooks']['PostToolUse'][0]['hooks']) == 48
    assert len(settings['hooks']['UserPromptSubmit'][0]['hooks']) == 48
    import shlex
    commands = settings['hooks']['PostToolUse'][0]['hooks']
    assert [shlex.split(item['command'])[-1] for item in commands] == [str(index) for index in range(48)]
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
def hook(extra=0, slot=0):
 return subprocess.run([sys.executable,'-B','-m','cs.operator_context_delivery',str(slot)],input=json.dumps({'hook_event_name':'PostToolUse','session_id':'real-process-control','tool_response':'x'*extra}),text=True,capture_output=True,check=True).stdout
assert hook()==''
cli="""
import json,os,sys
from cs.operator_health import ARGV,capture
sys.argv=['constructed-cli']+ARGV
value={'triage_workset':{'complete':True,'limit':2,'selected':[],'deferred':[],'held':[]},'note':'x'*326000}
output=json.dumps(value,ensure_ascii=False,indent=2)+'\\n'
capture(output.encode(),value,0,'constructed-owner')
from cs.operator_inventory_view import capture as legacy_capture
legacy_capture(json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT']))
"""
subprocess.run([sys.executable,'-B','-c',cli],check=True)
path,values=current_snapshot(ctx,'real-process-control')
assert len(values)==48,len(values)
assert hook(slot=48)==''
from cs.operator_context_delivery import overlay
import shlex
settings=json.loads(overlay(path,sys.executable).read_text())
commands=settings['hooks']['PostToolUse'][0]['hooks']
for index,item in enumerate(commands):
 result=subprocess.run(shlex.split(item['command']),input=json.dumps({'hook_event_name':'PostToolUse','session_id':'real-process-control'}),text=True,capture_output=True,check=True)
 actual=json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
 assert actual==values[index]
assert hook()==''
assert hook(4*1024*1024+1)==''
assert hook(131298)==''
assert hook()==''
for key,value in [('nonce','foreign'),('owner_uid','foreign')]:
 try:current_snapshot({**ctx,key:value},'real-process-control')
 except ValueError:pass
 else:raise AssertionError('foreign snapshot accepted')
print('constructed48 snapshot, real supervisor/CLI/hook processes; all48 bound settings commands exact; absent/oversize/dedup/foreign guards PASS')
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
