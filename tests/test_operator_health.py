"""Real subprocess discovery transport and model-independent health notices."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from cs import operator_health as health, operator_recovery as recovery
from cs.config import Settings
from cs.operational_inbox import record_notice as persist_notice, location

FAKE = '''#!/usr/bin/env python3
import json, os, subprocess, sys, shlex
if sys.argv[1:] == ['auth','status','--json']:
    print(json.dumps({'authMethod':'none'})); raise SystemExit(0)
if os.environ.get('NATIVE_CALLS'):
    with open(os.environ['NATIVE_CALLS'],'a') as stream: stream.write('model\\n')
if os.environ.get('HEALTH_CASE') != 'missing':
    code = """
import argparse,hashlib,json,os,sys
from unittest.mock import patch
from cs import cli,operator_health
from cs.config import Settings
value={'open':[], 'resumed':[], 'handled':[], 'escalated':[], 'human_work':[], 'assignment_audit':[], 'operational_fixture_discovery':[], 'read_incomplete':None, 'assignment_incomplete':False}
case=os.environ.get('HEALTH_CASE')
if case in ('large','large_unread','partial','early_draft','early_chat','early_send','late_chat'): value['open']=[{'subject':'x'*1000,'thread_key':str(i)} for i in range(70)]
if case=='human': value['human_work']=[{'assignment':{'complete':True,'hold_auto_reply':True,'state':'assigned'}}]
if case=='candidate':
    value['assignment_incomplete']=True
    value['human_work']=[{'assignment':{'complete':False,'hold_auto_reply':True,'state':'needs-assignment'}}]
if case in ('ancestry','ancestry_bad'):
    value['assignment_incomplete']=True
    value['human_work']=[{'thread_key':'<root@example.test>','assignment':{'version':1,'actor_uid':'owner','space_id':'space','thread_key':'<root@example.test>','complete':False,'state':'conflict','hold_auto_reply':True,'reason':'RFC_ANCESTRY_CONFLICT','task':None,'authoritative_thread_key':'<root@example.test>','component_thread_keys':['<root@example.test>'],'component_scope_present':False,'source_owner_uid':'owner','events':[],'covered_inbound':[],'current_inbound':[],'current_message_ids':[],'covered_message_ids':[],'reply_evidence':[]}}]
    if case=='ancestry_bad': value['human_work'][0]['assignment']['source_owner_uid']='foreign'
if case in ('technical','mixed','mixed_send','technical_unread','technical_workset'):
    value['assignment_incomplete']=True
    value['human_work']=[{'assignment':{'complete':False,'hold_auto_reply':True,'state':'unknown'}}]
if case=='mixed': value['human_work'].append({'assignment':{'complete':False,'hold_auto_reply':True,'state':'needs-assignment'}})
if case=='mailbox': value['read_incomplete']={'source':'unavailable'}
args=argparse.Namespace(days=14,json=True,all_buckets=True,crm=False)
sys.argv=['cs',*operator_health.ARGV]
for row in value['open']:
    row['thread_key']='<'+row['thread_key']+'@example.test>'
    row['_workset_revision']=hashlib.sha256(row['thread_key'].encode()).hexdigest()
for row in value['human_work']:
    row['assignment'].setdefault('actor_uid','owner')
    row['assignment'].setdefault('source_owner_uid','owner')
from cs.operator_workset import observe
observe(Settings(engine_owner_uid='owner'),'tasks',[])
observe(Settings(engine_owner_uid='owner'),'review',{'drafts':[]})
with patch.object(cli.config,'load',return_value=Settings(engine_owner_uid='owner')),patch('cs.unanswered.sweep',return_value=value):
    raise SystemExit(cli.cmd_unanswered(args))
"""
    child=subprocess.run([os.environ['HEALTH_PYTHON'],'-c',code],capture_output=True)
    if child.returncode not in (0,3): print(child.stderr.decode(),file=sys.stderr)
    case=os.environ.get('HEALTH_CASE')
    def use(command, output, identifier, error=False):
        print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':identifier,'name':'Bash','input':{'command':command}}]}}))
        print(json.dumps({'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':identifier,'is_error':error,'content':output}]}}))
    for index,command in enumerate(['whoami','config','tasks --json','review --json','campaign pending']):
        if case=='missing_phase' and command=='campaign pending': continue
        use('.venv/bin/python -m cs '+command,'{}','phase-'+str(index))
    clipped=case in ('large','large_unread','technical_unread','partial','early_draft','early_chat','early_send','late_chat')
    if case=='technical_workset':
        reserved=json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])['directory']+'/workset-reserved.json'
        record=json.load(open(reserved)); record['nonce']='foreign'
        open(reserved,'w').write(json.dumps(record))
    output='[native output clipped]' if clipped else child.stdout.decode()
    if child.returncode==3: output='Exit code 3'+chr(10)+output
    use('.venv/bin/python -m cs unanswered --days 14 --json --all-buckets',output,'discovery',child.returncode!=0)
    if case=='send_success': use('.venv/bin/python -m cs draft-send exact-full-id','sent and recorded','send')
    if case=='send_pending':
        print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','id':'send-pending','name':'Bash','input':{'command':'.venv/bin/python -m cs draft-send exact-full-id'}}]}}))
    if case in ('draft_failed','chat_failed','send_failed','mixed_send'):
        command=('.venv/bin/python -m cs draft-reply test --thread-id root' if case=='draft_failed'
                 else '.venv/bin/python -m cs draft-send exact-full-id' if case in ('send_failed','mixed_send')
                 else '.venv/bin/python -m cs chat --allow send_draft test')
        failed=subprocess.run([os.environ['HEALTH_PYTHON'],'-c',"import sys; print('engine generation refused',file=sys.stderr); raise SystemExit(1)"],capture_output=True)
        use(command,'Exit code '+str(failed.returncode)+chr(10)+failed.stderr.decode(),'operation',failed.returncode!=0)
    if case=='early_chat': use('.venv/bin/python -m cs chat generate reply','{}','chat')
    if case=='early_draft': use('.venv/bin/python -m cs draft-reply test --thread-id root','{}','draft')
    if case=='early_send': use('.venv/bin/python -m cs draft-send exact-full-id','{}','send')
    if clipped and case not in ('large_unread','technical_unread'):
        path=json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])['directory']+'/discovery.json'
        raw=open(path,'rb').read()
        end=len(raw)//2 if case=='partial' else len(raw)
        for offset in range(0,end,8064):
            command='dd if='+shlex.quote(path)+' bs=1 skip='+str(offset)+' count=8192 status=none'
            result=subprocess.run(shlex.split(command),capture_output=True,check=True)
            use(command,result.stdout.decode('utf-8','replace'),'part-'+str(offset))
    if case=='late_chat': use('.venv/bin/python -m cs chat generate reply','{}','chat')
print(json.dumps({'type':'result','is_error':False,'modelUsage':{'model':{}}}))
'''

async def intake(settings):
    return None

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    binary = root / 'native'
    binary.write_text(FAKE)
    binary.chmod(0o700)
    calls = root / 'calls'
    recorded = []
    settings = Settings(slug='health', engine_owner_uid='owner', email_address='owner@example.test')
    def record(actual, item):
        identity = persist_notice(actual, item)
        inbox, owner, _ = location(actual)
        evidence = inbox / 'notice-evidence' / (identity + '.json')
        assert json.loads(evidence.read_text()) == item
        assert evidence.stat().st_mode & 0o777 == 0o600
        assert json.loads((inbox / 'problems.json').read_text())['owner_uid'] == owner
        recorded.append(recovery.operator_notices.render(actual, item)[1])
        return identity
    with patch.dict(os.environ, {'HOME': str(root), 'NATIVE_CALLS': str(calls), 'HEALTH_PYTHON': sys.executable}), patch.object(
            recovery.config, 'load', return_value=settings), patch.object(
            recovery, '_mail_intake', intake), patch('cs.operational_inbox.record_notice', record), patch.object(
            recovery.send_mail, 'send', side_effect=AssertionError('technical SMTP forbidden')) as send, patch(
            'smtplib.SMTP', side_effect=AssertionError('SMTP socket forbidden')) as smtp:
        for case in ('empty', 'human', 'candidate', 'large', 'ancestry', 'late_chat', 'send_success'):
            os.environ['HEALTH_CASE'] = case
            assert recovery.run(str(binary), ['Write']) == 0, case
        artifacts = list((settings.state_dir / 'operator-runs').glob('*/discovery.json'))
        large = next(path for path in artifacts if len(path.read_bytes()) > 20000)
        assert len(json.loads(large.read_text())['discovery']['open']) == 70
        for case, cause in (('missing', 'discovery_evidence_invalid'),
                            ('ancestry_bad', 'assignment_read_incomplete'),
                            ('technical', 'assignment_read_incomplete'),
                            ('mixed', 'assignment_read_incomplete'),
                            ('mixed_send', 'assignment_read_incomplete'),
                            ('technical_unread', 'assignment_read_incomplete'),
                            ('technical_workset', 'assignment_read_incomplete'),
                            ('large_unread', 'discovery_inspection_incomplete'),
                            ('partial', 'discovery_inspection_incomplete'),
                            ('early_draft', 'discovery_inspection_incomplete'),
                            ('early_chat', 'discovery_inspection_incomplete'),
                            ('early_send', 'discovery_inspection_incomplete'),
                            ('missing_phase', 'execution_phase_incomplete'),
                            ('draft_failed', 'execution_operation_failed'),
                            ('chat_failed', 'execution_operation_failed'),
                            ('send_failed', 'execution_operation_failed'),
                            ('send_pending', 'execution_operation_failed'),
                            ('mailbox', 'mailbox_read_incomplete')):
            os.environ['HEALTH_CASE'] = case
            before = len(calls.read_text().splitlines())
            # An incomplete read that is the run's only defect keeps its notice
            # and exits 0; a malformed row, a failed operation, an uninspected
            # discovery or a foreign workset reservation beside it does not.
            assert recovery.run(str(binary), ['Write']) == (0 if case in ('technical', 'mixed', 'mailbox') else 1), case
            assert len(calls.read_text().splitlines()) == before + 1
            assert f'Notice code: stopped/{cause}' in recorded[-1]
        before = len(recorded)
        assert recovery.run(str(binary), ['Write']) == 0
        assert len(recorded) == before
        os.environ['HEALTH_CASE'] = 'missing'
        assert recovery.run(str(binary), ['Write']) == 1
        os.environ['HEALTH_CASE'] = 'empty'
        assert recovery.run(str(binary), ['Write']) == 0
        assert 'Resolved.' in recorded[-1]
        os.environ['HEALTH_CASE'] = 'technical'
        with patch('cs.operational_inbox.record_notice', side_effect=OSError('filesystem unavailable')):
            assert recovery.run(str(binary), ['Write']) == 1
        assert recovery._read_state(settings)['pending']
        before = len(calls.read_text().splitlines())
        with patch.object(recovery, '_run', side_effect=AssertionError('no model needed')):
            assert recovery._deliver_pending(settings, recovery._read_state(settings))
        assert len(calls.read_text().splitlines()) == before
        assert not recovery._read_state(settings)['pending']
        state = recovery._read_state(settings)
        state['pending'] = [{'status':'stopped','reason':'discovery_evidence_invalid'}]
        recovery._write_state(settings, state)
        os.environ['HEALTH_CASE'] = 'empty'
        before = len(calls.read_text().splitlines())
        with patch('cs.operational_inbox.record_notice', side_effect=OSError('filesystem unavailable')) as delivery:
            assert recovery.run(str(binary), ['Write']) == 1
            assert delivery.call_count == 1
        assert len(calls.read_text().splitlines()) == before + 1
        state = recovery._read_state(settings)
        assert len(state['pending']) == 1 and state['pending'][0]['status'] == 'stopped'
        assert recovery._deliver_pending(settings, state)
        with patch.dict(os.environ, {'CS_OPERATOR_ACCEPTANCE_RECEIPT': str(root / 'acceptance.json'),
                                     'CS_OPERATOR_ACCEPTANCE_NONCE': 'a' * 32, 'HEALTH_CASE': 'large'}):
            protected = recovery._run(str(binary), ['Write'])
            assert recovery._successful(protected) and not protected.health_failure
        custom = recovery._run(str(binary), ['Write'], prompt='signup processing')
        assert recovery._successful(custom) and not custom.health_failure
        settings.pause_path.touch()
        state = recovery._read_state(settings)
        state['pending'] = [{'status':'stopped','reason':'discovery_evidence_invalid'}]
        recovery._write_state(settings, state)
        with patch.object(recovery, '_run', side_effect=AssertionError('model forbidden')), patch.object(
                recovery, '_mail_intake', side_effect=AssertionError('intake forbidden')):
            assert recovery.run(str(binary), ['Write']) == 0
        assert not recovery._read_state(settings)['pending']
        settings.pause_path.unlink()
        with patch.object(recovery, '_mail_intake', side_effect=RuntimeError('secret')):
            assert recovery.run(str(binary), ['Write']) == 1
            assert 'secret' not in recorded[-1]
        with patch.object(recovery, '_run', side_effect=RuntimeError('secret')):
            assert recovery.run(str(binary), ['Write']) == 1
            assert 'Notice code: stopped/supervisor_failed' in recorded[-1]
            assert 'secret' not in recorded[-1]
        record_path = artifacts[0]
        record = json.loads(record_path.read_text())
        context = {'directory': str(record_path.parent), 'nonce': record['nonce'],
                   'supervisor': record['ancestry'][-1]}
        child = record['ancestry'][1]
        assert health.assess(context, child, 'foreign-owner') == 'discovery_evidence_invalid'
        assert health.assess({**context, 'nonce': 'stale'}, child, 'owner') == 'discovery_evidence_invalid'
        assert health.assess(context, {'pid': 0, 'started_ticks': 0}, 'owner') == 'discovery_evidence_invalid'
        record_path.chmod(0o644)
        assert health.assess(context, child, 'owner') == 'discovery_evidence_invalid'
        record_path.chmod(0o600)
        record_path.unlink()
        record_path.symlink_to(large)
        assert health.assess(context, child, 'owner') == 'discovery_evidence_invalid'
        send.assert_not_called()
        smtp.assert_not_called()
        assert recorded
events = [
    {'message': {'content': [{'type': 'tool_use', 'id': 'status', 'name': 'Bash',
                            'input': {'command': ".venv/bin/python -m cs assignment status '<root>' --json"}}]}},
    {'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'status', 'is_error': True}]}},
]
assert health.native_read_failed(events)
events[-1]['message']['content'][0]['is_error'] = False
assert not health.native_read_failed(events)
events[-1]['message']['content'][0].update(is_error=True, content='Exit code 3\n' + json.dumps({
    'version':1,'thread_key':'<root>','state':'needs-assignment','complete':False,'hold_auto_reply':True}))
assert health.native_read_failed(events)


root = '<root@example.test>'
partial = {'version':1, 'actor_uid':'owner', 'space_id':'space', 'thread_key':root,
    'complete':False, 'state':'conflict', 'hold_auto_reply':True, 'reason':'RFC_ANCESTRY_CONFLICT',
    'task':None, 'authoritative_thread_key':root, 'component_thread_keys':[root],
    'component_scope_present':False, 'source_owner_uid':'owner', 'events':[], 'covered_inbound':[],
    'current_inbound':[], 'current_message_ids':[], 'covered_message_ids':[], 'reply_evidence':[]}
from cs import task_assignment as assignment
changes = [('version',True),('version',2),('actor_uid',''),('actor_uid',None),('actor_uid','   '),('space_id',''),
    ('space_id',[]),('thread_key','<foreign@example.test>'),('complete',True),('state','unknown'),
    ('state','needs-assignment'),('reason','untyped'),('hold_auto_reply',False),('task',{}),('source_owner_uid','foreign'),
    ('component_scope_present',True),('authoritative_thread_key','<foreign@example.test>'),
    ('component_thread_keys',[root,'<foreign@example.test>']),('authority_complete',True)]
changes += [(key,['forged']) for key in ('events','covered_inbound','current_inbound',
    'current_message_ids','covered_message_ids','reply_evidence')]
invalid = [partial | {key:value} for key,value in changes]
invalid += [{key:value for key,value in partial.items() if key!=missing} for missing in partial]
for response in [partial] + invalid:
    expected = response is not partial
    block = {'type':'tool_result','tool_use_id':'status','is_error':True,'content':'Exit code 3\n'+json.dumps(response)}
    read = {'type':'tool_use','id':'status','name':'Bash','input':{'command':".venv/bin/python -m cs assignment status '<root@example.test>' --json"}}
    assert health.native_read_failed([{'message':{'content':[read]}},{'message':{'content':[block]}}])
    assert assignment._ancestry_conflict(response, root) is (not expected)
    with tempfile.TemporaryDirectory() as directory:
        import hashlib
        path = Path(directory)
        path.chmod(0o700)
        context = {'directory':directory,'nonce':'n','supervisor':{'pid':1,'started_ticks':1}}
        child = {'pid':2,'started_ticks':2}
        discovery = {'open':[],'human_work':[{'thread_key':root,'assignment':response}], 'assignment_audit':[],
            'operational_fixture_discovery':[],'read_incomplete':None,'assignment_incomplete':True}
        payload = (json.dumps(discovery,ensure_ascii=False,indent=2,default=str)+'\n').encode()
        record = {'nonce':'n','owner_uid':'owner','ancestry':[child,{'pid':3,'started_ticks':3},context['supervisor']],
            'exit_code':3,'discovery':discovery,'output_sha256':hashlib.sha256(payload).hexdigest()}
        evidence = path/'discovery.json'
        evidence.write_text(json.dumps(record));evidence.chmod(0o600)
        assert bool(health.assess(context,child,'owner')) is expected
assert not assignment._ancestry_conflict(partial | {'thread_key':'<root>','authoritative_thread_key':'<root>','component_thread_keys':['<root>']}, '<root>')

print('ordinary health: real CLI subprocess, large artifact, empty/human/technical distinction, failure dedup/recovery, queued zero-model filesystem recording and zero SMTP, supervisor exceptions and foreign/stale/private guards PASS')
