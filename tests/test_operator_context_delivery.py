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
# Same size as the failed paired inventory, without private business material.
large_view = b'x' * (362049 - len(raw))
large_values = delivery.parts(large_view, raw, envelope, 'constructed-session')
assert len(large_values) == 46
assert ''.join(v.split('\n', 1)[1] for v in large_values).encode() == raw + large_view
assert delivery.delivered(fixture(large_values), large_view, raw, envelope)
# Enlarged character chunks must not reject previously supported Unicode input.
unicode_view = ('𐍈' * 2000 + 'x' * 6000).encode()
legacy_values = delivery._parts(raw.decode() + unicode_view.decode(), unicode_view,
                               raw, envelope, 'constructed-session', 7000)
assert legacy_values is not None
unicode_values = delivery.parts(unicode_view, raw, envelope, 'constructed-session')
assert unicode_values == legacy_values
assert all(len(v.encode('utf-16-le')) // 2 < 10000 for v in unicode_values)
assert delivery.delivered(fixture(unicode_values), unicode_view, raw, envelope)
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
progress_events = fixture(values)
for index in range(len(progress_events) - 1, 0, -1):
    final = progress_events[index]
    if final.get('subtype') == 'hook_response':
        progress = {key: value for key, value in final.items() if key not in ('exit_code', 'outcome')}
        progress.update(subtype='hook_progress', uuid=final['uuid'] + '-progress')
        progress_events.insert(index, progress)
assert delivery.delivered(progress_events, view, raw, envelope)
progress_index = next(i for i, event in enumerate(progress_events) if event.get('subtype') == 'hook_progress')
for mutation in ('empty', 'repeat', 'altered', 'foreign', 'before', 'after', 'missing_final', 'wrong_final', 'unknown', 'stderr', 'duplicate_uuid'):
    bad = copy.deepcopy(progress_events)
    item = bad[progress_index]
    if mutation == 'empty': item.update(stdout='', output='')
    elif mutation == 'repeat': bad.insert(progress_index, {**item, 'uuid': 'repeat-progress'})
    elif mutation == 'altered': item.update(stdout='prefix', output='prefix')
    elif mutation == 'foreign': item['session_id'] = 'foreign'
    elif mutation == 'before': bad[progress_index-1], bad[progress_index] = bad[progress_index], bad[progress_index-1]
    elif mutation == 'after': bad[progress_index+1], bad[progress_index] = bad[progress_index], bad[progress_index+1]
    elif mutation == 'missing_final': del bad[progress_index+1]
    elif mutation == 'wrong_final': bad[progress_index+1]['exit_code'] = 2
    elif mutation == 'unknown': item['unknown'] = True
    elif mutation == 'stderr': item['stderr'] = 'x'
    elif mutation == 'duplicate_uuid': item['uuid'] = bad[progress_index-1]['uuid']
    try:
        assert not delivery.delivered(bad, view, raw, envelope), mutation
    except ValueError:
        pass
first_final = progress_index + 1
assert not delivery.delivered(progress_events[:first_final] + [effect] + progress_events[first_final:], view, raw, envelope)
print('Observed full-output progress: exact final required;11 nearby mutations and pre-final effect refusal PASS')
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
from cs.operator_context_delivery import SLOTS, CHARS
ctx=json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
def hook(extra=0, slot=0):
 return subprocess.run([sys.executable,'-B','-m','cs.operator_context_delivery',str(slot)],input=json.dumps({'hook_event_name':'PostToolUse','session_id':'real-process-control','tool_response':'x'*extra}),text=True,capture_output=True,check=True).stdout
assert hook()==''
cli="""
import json,os,sys
from cs.operator_health import ARGV,capture
from cs.operator_context_delivery import SLOTS, CHARS
sys.argv=['constructed-cli']+ARGV
value={'triage_workset':{'complete':True,'limit':2,'selected':[],'deferred':[],'held':[]},'note':'x'*((SLOTS-2)*CHARS+4000)}
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

capacity_checks = r'''
from pathlib import Path
from cs import operator_inventory_view as inventory, observability_causal as causal
from cs.operator_context_delivery import CapacityError, delivered
from cs.operator_health import inspection_failure, ARGV
from cs.observability import context as diagnostic_context
path,view,envelope=inventory.load(ctx)
try:current_snapshot(ctx,'real-process-control')
except CapacityError as exc:
 assert exc.required==50,exc.required
 assert exc.path==path and exc.snapshot_digest==__import__('hashlib').sha256(inventory.read_private(path/'inventory-view-envelope.json')+view).hexdigest()
else:raise AssertionError('overflow accepted')
assert hook(slot=47)==''
notice_output=hook()
notice=json.loads(json.loads(notice_output)['hookSpecificOutput']['additionalContext'])
assert notice['notice']=='context_slots_exhausted' and notice['required']==50 and notice['available']==48
assert notice['run_id']=='1'*32 and notice['attempt_id']=='2'*32
assert notice['directory']==str(path)
assert (notice['event_id'] is None) == (os.environ.get('OVERFLOW_SINK_FAILURE')=='1')
assert (path/notice['envelope_path']).exists() and (path/notice['progress_path']).exists()
assert len(notice_output.encode('utf-16-le'))//2<10000 and 'x'*80 not in notice_output
assert hook()=='' and hook(slot=47)==''
assert len(list(path.glob('context-capacity-notice-*')))==1 and not list(path.glob('context-delivered-*'))
assert not delivered([{'type':'system','subtype':'init','session_id':'real-process-control'}],view,inventory.read_private(path/'inventory-view-envelope.json'),envelope)
phases=[{'phase':name} for name in ('identity','configuration','tasks','discovery','review','campaigns')]
events=[{'type':'system','subtype':'init','session_id':'real-process-control'},
 {'session_id':'real-process-control','message':{'content':[{'type':'tool_use','name':'Bash','id':'discovery','input':{'command':'.venv/bin/python -m cs '+' '.join(ARGV)}}]}},
 {'session_id':'real-process-control','message':{'content':[{'type':'tool_result','tool_use_id':'discovery','content':'incomplete'}]}}]
with causal.scope(), diagnostic_context({'run_id':'1'*32,'attempt_id':'2'*32}):
 assert inspection_failure(events,ctx,phases)=='discovery_inspection_incomplete'
 selected=causal.selected()
 assert selected['cause']=='context_slots_exhausted' and selected['facts']=={'required':50,'available':48}
 assert selected['refs']['run_id']=='1'*32 and selected['refs']['attempt_id']=='2'*32
for key in ('nonce','owner_uid'):
 with causal.scope():
  assert inspection_failure(events,{**ctx,key:'foreign'},phases)=='discovery_inspection_incomplete'
  assert causal.selected()['cause']=='discovery_inspection_incomplete'
for target in (path/'inventory-view-envelope.json',path/'inventory-view.jsonl'):
 data=inventory.read_private(target)
 for begin,end in inventory._pages(data):
  command=inventory._page_text(target,begin,end)
  result=subprocess.run(command,shell=True,text=True,capture_output=True,check=True)
  tool='page-'+str(len(events))
  events.extend([{'session_id':'real-process-control','message':{'content':[{'type':'tool_use','name':'Bash','id':tool,'input':{'command':command}}]}},
   {'session_id':'real-process-control','message':{'content':[{'type':'tool_result','tool_use_id':tool,'content':result.stdout}]}}])
with causal.scope():
 assert inventory.audit(events,ctx)
 assert inspection_failure(events,ctx,phases)==''
 assert causal.selected() is None
original=(path/'inventory-view-envelope.json').read_bytes()
(path/'inventory-view-envelope.json').write_bytes(original.replace(envelope['source_identity'].encode(),b'd'*64))
with causal.scope():
 assert inspection_failure(events[:3],ctx,phases)=='discovery_inspection_incomplete'
 assert causal.selected()['cause']=='discovery_inspection_incomplete'
assert hook()==''
(path/'inventory-view-envelope.json').write_bytes(original)
print('Real ancestry overflow50/48: bounded notice once, no delivery markers, current-run causal counts, foreign/stale refusal, complete literal paging PASS')
'''
overflow_worker = worker[:worker.index("path,values=current_snapshot")] + capacity_checks
overflow_worker = overflow_worker.replace('(SLOTS-2)*CHARS+4000', 'SLOTS*CHARS+4000')
for sink_failure in (False, True):
    with tempfile.TemporaryDirectory() as folder:
        context = {'directory': folder, 'owner_uid': 'constructed-owner', 'nonce': 'a'*32,
                   'supervisor': identity(os.getpid())[0], 'workset_enabled': False}
        env = {**os.environ, 'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(context),
               'CS_DIAGNOSTIC_CONTEXT': json.dumps({'run_id': '1'*32, 'attempt_id': '2'*32}),
               'HOME': folder, 'CS_MANIFEST': str(Path(folder)/'manifest.toml'),
               'CS_ENGINE_OWNER_UID': 'constructed-owner'}
        (Path(folder)/'manifest.toml').write_text('[company]\nslug="overflow"\n[engine]\nowner_uid="constructed-owner"\n')
        candidate = overflow_worker
        if sink_failure:
            env['OVERFLOW_SINK_FAILURE']='1'
            shim = "import runpy; from unittest.mock import patch; p=patch('cs.observability_producers.emit',side_effect=OSError('sink unavailable')); p.start(); runpy.run_module('cs.operator_context_delivery',run_name='__main__')"
            candidate = candidate.replace("'-m','cs.operator_context_delivery'", "'-c'," + repr(shim))
        result = subprocess.run([sys.executable, '-B', '-c', candidate],env=env,text=True,capture_output=True)
        assert result.returncode == 0, result.stderr
        print(result.stdout.strip(), 'sink_failure=' + str(sink_failure))
        if not sink_failure:
            from cs.observability import owner_root
            from cs.monitor_config import Component, MonitorConfig
            import time
            command = [sys.executable, '-m', 'cs', 'logs', 'events', '--local', '--json', '--limit', '200']
            logged = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
            assert logged.returncode == 0, logged.stderr
            rows = json.loads(logged.stdout)['local']['events']
            capacity = [row for row in rows if row.get('causal', {}).get('cause') == 'context_slots_exhausted']
            assert len(capacity) == 1, rows
            value = capacity[0]['causal']
            assert value['facts'] == {'required': 50, 'available': 48}
            assert value['refs']['run_id'] == '1'*32 and value['refs']['attempt_id'] == '2'*32
            target = owner_root(Path(folder)/'.overflow-cs', 'constructed-owner')
            cfg = MonitorConfig(mode='filesystem', monitor_id='a'*32, owner_uid='constructed-owner',
                state_dir=str(Path(folder)/'monitor'), expected_start_utc=int(time.time()),
                components=[Component(id='operator', kind='kernel', local_root=str(target))])
            config_path = Path(folder)/'monitor.json'
            config_path.write_text(cfg.model_dump_json()); config_path.chmod(0o600)
            monitored = subprocess.run([sys.executable, '-m', 'cs', 'monitor', 'once', '--config', str(config_path)],
                env=env, capture_output=True, text=True, timeout=10)
            assert monitored.returncode == 1, monitored.stdout + monitored.stderr
            inbox = json.loads((Path(folder)/'monitor'/'problems.json').read_text())
            assert any(row['evidence'].get('causal') == value for row in inbox['problems'])
            print('Ordinary logs CLI and filesystem monitor inbox preserve single capacity event, counts and current references PASS')

import ast
from cs import operator_recovery as recovery
from cs.config import Settings
from cs.operational_inbox import record_notice as persist_notice
source = ast.parse((Path(__file__).with_name('test_operator_health.py')).read_text())
native = ast.literal_eval(next(node.value for node in source.body
    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'FAKE' for target in node.targets)))
native = native.replace("observe(Settings(engine_owner_uid='owner'),'review',{'drafts':[]})", "from cs.draft_state import inventory_proof\nreview={'drafts':[],'gmail_drafts':[],'engine_drafts':[],'gmail_drafts_observation':{'version':1,'complete':True,'search_complete':True,'expected_uids':[],'observed_uids':[],'uidvalidity':'1'}}\nreview['drafts_inventory']=inventory_proof([],[],[],review['gmail_drafts_observation'])\nobserve(Settings(engine_owner_uid='owner'),'review',review)")
native = native.replace("args=argparse.Namespace", "value['note']='x'*388000\nargs=argparse.Namespace")
native = native.replace("    clipped=case in (", "    clipped=True or case in (")
native = native.replace("    if clipped and case!='large_unread':", "    if False:")
native = native.replace("    case=os.environ.get('HEALTH_CASE')", "    print(json.dumps({'type':'system','subtype':'init','session_id':'supervisor-capacity'}))\n    case=os.environ.get('HEALTH_CASE')")
native = native.replace("{'type':'assistant'", "{'session_id':'supervisor-capacity','type':'assistant'")
native = native.replace("{'type':'user'", "{'session_id':'supervisor-capacity','type':'user'")
async def no_intake(settings):
    return None
with tempfile.TemporaryDirectory() as folder:
    binary = Path(folder)/'native'
    binary.write_text(native); binary.chmod(0o700)
    settings = Settings(slug='overflow', engine_owner_uid='owner', email_address='owner@example.test')
    recorded = []
    def record(actual, item):
        recorded.append(item)
        return persist_notice(actual, item)
    with patch.dict(os.environ, {'HOME': folder, 'HEALTH_PYTHON': sys.executable, 'HEALTH_CASE': 'empty'}), \
            patch.object(recovery.config, 'load', return_value=settings), \
            patch.object(recovery, '_mail_intake', no_intake), \
            patch('cs.operational_inbox.record_notice', record), \
            patch.object(recovery.send_mail, 'send', side_effect=AssertionError('SMTP forbidden')):
        assert recovery.run(str(binary), ['Write']) == 1
        if retained := os.environ.get('OVERFLOW_EVIDENCE_DIR'):
            (Path(retained)/'supervisor-capacity-notice.json').write_text(json.dumps(recorded[-1], indent=2))
        assert recorded[-1]['causal']['cause'] == 'context_slots_exhausted', recorded[-1]
        assert recorded[-1]['causal']['facts']['required'] > 48
        assert recorded[-1]['causal']['facts']['available'] == 48
        assert recorded[-1]['causal']['refs']['run_id']
        assert recorded[-1]['causal']['refs']['attempt_id']
        rendered = recovery.operator_notices.render(settings, recorded[-1])[1]
        assert 'context_slots_exhausted' in rendered and 'required' in rendered and '48' in rendered
        assert recorded[-1]['causal']['refs']['run_id'] in rendered
        assert recorded[-1]['causal']['refs']['cause_event_id'] in rendered
        subject, plain, rich = recovery.operator_notices.render(settings, recorded[-1])
        assert 'inventory exceeds automatic delivery capacity' in subject
        import html
        assert html.escape(plain).replace('\n', '<br>') in rich
        for changed in ({'causal': {'invalid': True}}, {'status': 'primary'}, {'status': 'fallback'}):
            other = recovery.operator_notices.render(settings, {**recorded[-1], **changed})
            assert 'Capacity cause: context_slots_exhausted' not in other[1]
print('Actual supervisor run and ordinary persisted/rendered notice retain capacity cause, counts and current run/attempt PASS')
