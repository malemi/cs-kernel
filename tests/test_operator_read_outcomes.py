"""Constructed read controls with real local subprocess ancestry and private capture."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from cs import operator_discovery_receipt as transport
from cs import operator_read_outcomes as outcomes

ROOT = '<read@example.test>'


def projection():
    return dict(version=1, actor_uid='owner', space_id='space', thread_key=ROOT,
        authoritative_thread_key=ROOT, component_thread_keys=[ROOT], component_scope_present=False,
        source_owner_uid='owner', complete=False, state='conflict', hold_auto_reply=True, task=None,
        events=[], covered_inbound=[], current_inbound=[], current_message_ids=[], covered_message_ids=[],
        reply_evidence=[], reason='RFC_ANCESTRY_CONFLICT')


class ReadOutcomeTests(unittest.TestCase):
    def test_finite_scope_and_projection(self):
        command = '.venv/bin/python -m cs assignment status ' + shlex.quote(ROOT) + ' --json'
        self.assertEqual(outcomes.command_scope(command)['exit_code'], 3)
        for value in ['cs assignment status ' + ROOT + ' --json', command + ' && true',
                      command + ' --json', '.venv/bin/python -m cs assignment status --json',
                      '.venv/bin/python -m cs draft-send ' + shlex.quote(ROOT)]:
            self.assertIsNone(outcomes.command_scope(value))
        self.assertTrue(outcomes.assignment_hold(projection(), 'owner', ROOT))
        for key, value in [('actor_uid','foreign'), ('source_owner_uid','foreign'), ('complete',True),
                           ('hold_auto_reply',False), ('state','unknown'), ('task',{})]:
            changed = projection(); changed[key] = value
            self.assertFalse(outcomes.assignment_hold(changed, 'owner', ROOT))
        self.assertFalse(outcomes.assignment_hold(projection(), 'owner', '<other@example.test>'))
        member = projection()
        member.update(state='needs-assignment',reason='NEEDS_HUMAN_VERIFICATION',reply_evidence=[dict(
            version=1,actor_uid='owner',space_id='space',thread_key=ROOT,complete=True,
            judgement='MEMBER_ACTIVITY_REQUIRES_HUMAN_VERIFICATION',reason='NEEDS_HUMAN_VERIFICATION',
            source_id='source',digest='a'*64,source=dict(actor_uid='owner',thread_key=ROOT,message_id=ROOT,
                observation_only=True,mailbox_id='mailbox',provider=dict(folder='Sent',uidvalidity=1,uid=2),
                route_digest='b'*64,raw_header_digest='c'*64))])
        self.assertTrue(outcomes.assignment_hold(member,'owner',ROOT))
        peer = copy.deepcopy(member)
        peer['reason'] = 'peer reply requires explicit human verification and assignment'
        peer['reply_evidence'][0]['actor_uid'] = 'peer'
        peer['reply_evidence'][0]['source']['actor_uid'] = 'peer'
        self.assertTrue(outcomes.assignment_hold(peer,'owner',ROOT,{'colleague':'peer'}))
        self.assertFalse(outcomes.assignment_hold(peer,'owner',ROOT,{'colleague':'foreign'}))
        self.assertFalse(outcomes.assignment_hold(peer,'owner',ROOT))
        for key, value in [('complete',False),('actor_uid','foreign'),('space_id','foreign'),
                           ('thread_key','<foreign@example.test>'),('judgement','UNKNOWN'),('digest','bad')]:
            changed = copy.deepcopy(member); changed['reply_evidence'][0][key]=value
            self.assertFalse(outcomes.assignment_hold(changed,'owner',ROOT))
        for key, value in [('actor_uid','foreign'),('observation_only',False),('message_id','<foreign@example.test>'),
                           ('provider',dict(folder='Sent',uidvalidity=True,uid=2)),('raw_header_digest','bad')]:
            changed = copy.deepcopy(member); changed['reply_evidence'][0]['source'][key]=value
            self.assertFalse(outcomes.assignment_hold(changed,'owner',ROOT))

    def test_absence_requires_complete_bound_mailbox_scope(self):
        for command in ('.venv/bin/python -m cs contacted contact@example.test --days 14',
                        '.venv/bin/python -m cs history contact@example.test --json'):
            scope = outcomes.command_scope(command)
            value = dict(owner_uid='owner',kind=scope['kind'],contact=scope['contact'],window=scope['window'],
                query=scope['query'],configured=dict(operator_mailbox='owner@example.test',account_map={},read_mailboxes=[]),
                fanout=dict(rows=[],scope=dict(read=['owner@example.test'],unreadable=[],skipped=[],complete=True),note=None))
            self.assertTrue(outcomes.absence(value,scope,'owner'))
            for field, replacement in [('owner_uid','foreign'),('contact','foreign@example.test'),
                                       ('query',dict(contact='contact@example.test',directions=['in'],days=14))]:
                changed = copy.deepcopy(value); changed[field] = replacement
                self.assertFalse(outcomes.absence(changed,scope,'owner'))
            for field, replacement in [('read',[]),('unreadable',[dict(address='other@example.test')]),
                                       ('complete',False),('read',['owner@example.test','owner@example.test'])]:
                changed = copy.deepcopy(value); changed['fanout']['scope'][field] = replacement
                self.assertFalse(outcomes.absence(changed,scope,'owner'))
            changed = copy.deepcopy(value); changed['fanout']['rows'] = [dict(subject='present')]
            self.assertFalse(outcomes.absence(changed,scope,'owner'))
            changed = copy.deepcopy(value); changed['fanout']['note'] = 'UNKNOWN'
            self.assertFalse(outcomes.absence(changed,scope,'owner'))

    def _real_control(self, case):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); root.chmod(0o700)
            if case in ('deferral','search_deferral'):
                state = root
                root = state / 'operator-runs' / 'run-control'
                root.mkdir(mode=0o700, parents=True)
                root.parent.chmod(0o700)
                (state / 'operator-workset').mkdir(mode=0o700)
            binary = root / 'versions' / 'offline-read-control'
            binary.parent.mkdir(); shutil.copyfile(Path(sys.executable).resolve(), binary); binary.chmod(0o700)
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            (root / '.venv').symlink_to(Path(sys.prefix), target_is_directory=True)
            code = 3 if case in ('assignment','deferral','search_deferral') else 1
            (root / 'cs.py').write_text('''import os,sys,json
from types import SimpleNamespace
from unittest.mock import patch
sys.path=[p for p in sys.path if p not in ('',os.getcwd())]
from cs import assignment_cli,cli,mailboxes,operator_discovery_receipt as transport
from cs.config import Settings
transport.CLAUDE_VERSION=os.environ['CONTROL_VERSION']
transport.CLAUDE_SHA256=os.environ['CONTROL_DIGEST']
value=json.loads(os.environ['CONTROL_VALUE'])
case=os.environ['CONTROL_CASE']
if case in ('deferral','search_deferral'):
 from cs.operator_workset import require_contact, OutsideSelectedWorkset
 from cs.operator_read_outcomes import capture_workset_deferral
 settings=SimpleNamespace(engine_owner_uid='owner',state_dir=os.environ['CONTROL_STATE'])
 if case == 'search_deferral':
  with patch.object(cli.config,'load',return_value=settings),patch.object(cli.rpc,'call_sync',side_effect=AssertionError('RPC forbidden')):
   raise SystemExit(cli.cmd_rpc(SimpleNamespace(method='emails.search',params=sys.argv[3],timeout=30)))
 try:require_contact(settings,'excluded@example.test',typed_exclusion=True)
 except OutsideSelectedWorkset as exc:
  capture_workset_deferral(settings,exc.value)
  print('Scheduled work deferred outside selected workset',file=sys.stderr)
  raise SystemExit(3)
 raise SystemExit(99)
if case != 'assignment':
 settings=Settings(engine_owner_uid='owner',email_address='owner@example.test')
 fan=mailboxes.Fanout([],['owner@example.test'],[])
 with patch.object(cli.config,'load',return_value=settings),patch.object(mailboxes,'sent_to_here',return_value=fan),patch.object(mailboxes,'sent_to_across',return_value=fan),patch.object(mailboxes,'inbound_since_across',return_value=fan):
  args=SimpleNamespace(email='contact@example.test',days=14,json=case=='history_json')
  raise SystemExit(cli.cmd_contacted(args) if case=='contacted' else cli.cmd_history(args))
with patch.object(assignment_cli.config,'load',return_value=SimpleNamespace(engine_owner_uid='owner')),patch.object(assignment_cli.authority,'project',return_value=value):
 raise SystemExit(assignment_cli.run(SimpleNamespace(assignment_action='status',thread_key=sys.argv[3],json=True)))
''')
            command = ('.venv/bin/python -m cs assignment status ' + shlex.quote(ROOT) + ' --json'
                       if case == 'assignment' else '.venv/bin/python -m cs contacted contact@example.test --days 14'
                       if case == 'contacted' else '.venv/bin/python -m cs history contact@example.test'
                       + (' --json' if case == 'history_json' else ''))
            if case in ('deferral','search_deferral'):
                command = ('.venv/bin/python -m cs rpc emails.search ' + shlex.quote(json.dumps(dict(query='excluded@example.test',limit=5))) if case == 'search_deferral' else '.venv/bin/python -m cs dossier excluded@example.test')
            if case == 'history_json':
                command = command.replace('contact@example.test', '"contact@example.test"')
            marker = '/tmp/claude-' + uuid.uuid4().hex + '-cwd'
            wrapper = transport.CLEANUP + ' && eval ' + shlex.quote(command) + ' < /dev/null && pwd -P >| ' + marker
            supervisor = {k:transport.proc(os.getpid())[k] for k in ('pid','started_ticks')}
            context = dict(directory=str(root), nonce='a'*32, supervisor=supervisor, owner_uid='owner', workset_enabled=False)
            if case in ('deferral','search_deferral'):
                context['workset_enabled'] = True
                def hashed(v):
                    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                run = dict(digest='b'*64,selected=[hashed('<selected@example.test>')],contacts=[hashed('selected@example.test')])
                reservation = dict(nonce=context['nonce'],owner_uid='owner',**run)
                for path,value in [(root/'workset-reserved.json',reservation),(state/'operator-workset/cursor.json',dict(version=1,owner=hashed('owner'),order=1,roots={hashed('<selected@example.test>'):dict(revision='c'*64,order=1)},runs={hashed(context['nonce']):run}))]:
                    path.write_text(json.dumps(value));path.chmod(0o600)
            env = dict(os.environ, CONTROL_STATE=str(root.parent.parent), PYTHONPATH=str(repo), PYTHONHOME=sys.base_prefix,
                       CS_OPERATOR_HEALTH_CONTEXT=json.dumps(context), CONTROL_VERSION=binary.name,
                       CONTROL_DIGEST=digest, CONTROL_VALUE=json.dumps(projection()), CONTROL_WRAPPER=wrapper, CONTROL_CASE=case)
            for key in list(env):
                if key.startswith('CS_OPERATOR_ACCEPTANCE'):
                    env.pop(key)
            driver = '''import subprocess,os,sys
print('READY',flush=True)
sys.stdin.readline()
env=dict(os.environ);env.pop('PYTHONHOME',None)
p=subprocess.run(['/bin/bash','-c',os.environ['CONTROL_WRAPPER']],env=env,capture_output=True)
sys.stdout.buffer.write(p.stdout);sys.stdout.buffer.flush()
sys.stderr.buffer.write(p.stderr);sys.stderr.buffer.flush()
sys.exit(p.returncode)
'''
            with patch.object(transport,'CLAUDE_VERSION',binary.name), patch.object(transport,'CLAUDE_SHA256',digest), patch.dict(os.environ,env,clear=True):
                pinned = transport.pin_native(str(binary)); self.assertIsNotNone(pinned)
                with subprocess.Popen([str(binary),'-c',driver],cwd=root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as child:
                    self.assertEqual(child.stdout.readline(), b'READY\n')
                    live = transport.proc(child.pid)
                    identity = {k:live[k] for k in ('pid','started_ticks')}
                    producer = transport.bind_native(pinned,identity)
                    stdout, stderr = child.communicate(b'continue\n',timeout=15)
                    self.assertEqual(child.returncode,code,stderr.decode())
                Path(marker).unlink(missing_ok=True)
                if case in ('deferral','search_deferral'):
                    self.assertEqual(stdout,b'')
                    self.assertEqual(stderr,outcomes.workset_deferral_output(outcomes.command_scope(command)))
                    # Native result joins stderr for this CLI; historical stdout remains unchanged.
                    stdout = stderr
                else:
                    baseline_env = dict(env); baseline_env.pop('CS_OPERATOR_HEALTH_CONTEXT'); baseline_env.pop('PYTHONHOME',None)
                    baseline = subprocess.run(['/bin/bash','-c',wrapper],cwd=root,env=baseline_env,capture_output=True,timeout=15)
                    self.assertEqual(baseline.returncode,code,baseline.stderr.decode())
                    expected = baseline.stdout
                    self.assertEqual(stdout,expected); self.assertEqual(stderr,b'')
                paths = list((root/'business-reads').glob('*.json'))
                self.assertEqual(len(paths),1)
                output = 'Exit code ' + str(code) + '\n' + stdout.decode()
                if case in ('deferral','search_deferral'):
                    actual_render = json.loads((repo/'tests/fixtures/workset_deferral_native_render.json').read_text())
                    if case == 'deferral':
                        self.assertEqual(output,actual_render['native_content']+'\n')
                        output = actual_render['native_content']
                        self.assertEqual('Error: '+output,actual_render['native_metadata'])
                    else:
                        output = output.rstrip('\n')
                events = [dict(type='system',subtype='init',session_id='session'),
                    dict(type='assistant',session_id='session',message={'content':[dict(type='tool_use',id='tool',name='Bash',input={'command':command})]}),
                    dict(type='user',session_id='session',tool_use_result='Error: '+output,message={'content':[dict(type='tool_result',tool_use_id='tool',is_error=True,content=output)]}),
                    dict(type='result',session_id='session',is_error=False,terminal_reason='completed')]
                events[0]['claude_code_version'] = binary.name
                for index, event in enumerate(events):
                    event['uuid'] = 'constructed-' + str(index)
                self.assertEqual(len(outcomes.join(events,identity,'owner',producer)),1)
                from cs.operator_native_composition import composition
                events[0]['claude_code_version'] = binary.name
                events.insert(2, dict(type='system',subtype='task_started',session_id='session',
                    task_id='task',run_id='run',tool_use_id='tool',task_type='local_bash',is_backgrounded=False))
                events.insert(3, dict(type='system',subtype='task_notification',session_id='session',
                    task_id='task',run_id='run',tool_use_id='tool',status='failed'))
                events[-1].update(subtype='success',result_index=0,num_turns=1,safety_stops=0,origin=None)
                for index, event in enumerate(events):
                    event['uuid'] = 'constructed-' + str(index)
                lifecycle = composition(events,producer)
                self.assertIsNotNone(lifecycle)
                self.assertEqual(lifecycle['proof']['tasks'][0]['exit_code'],code)
                proofs = outcomes.join(events,identity,'owner',producer,lifecycle)
                self.assertEqual(len(proofs),1)
                self.assertEqual((proofs[0]['task_id'],proofs[0]['run_id']),('task','run'))
                from cs.operator_health import native_read_failed
                self.assertFalse(native_read_failed(events,proofs))
                self.assertTrue(native_read_failed(events))
                rpc_events = copy.deepcopy(events)
                rpc_events[1]['message']['content'][0]['input']['command'] = '.venv/bin/python -m cs rpc emails.list_by_thread \'{}\''
                self.assertTrue(native_read_failed(rpc_events,proofs))
                deferred = copy.deepcopy(events)
                deferred[4]['message']['content'][0]['content'] = 'Exit code 3\nScheduled work deferred outside selected workset' + ('\n' if case in ('deferral','search_deferral') else '')
                self.assertEqual(outcomes.join(deferred,identity,'owner',producer),[])
                for index in (2,3):
                    changed = copy.deepcopy(events); changed[index]['run_id']='foreign'
                    self.assertEqual(outcomes.join(changed,identity,'owner',producer,lifecycle),[])
                from cs import operator_recovery as recovery
                from types import SimpleNamespace
                attempt = recovery.Attempt(0,events,native_producer=producer,ordinary_native=True,health_context=context)
                destination = root / 'acceptance.json'
                with patch.dict(os.environ,{'CS_OPERATOR_ACCEPTANCE_RECEIPT':str(destination),
                        'CS_OPERATOR_ACCEPTANCE_NONCE':'b'*32}), patch.object(recovery.config,'load',
                        return_value=SimpleNamespace(engine_owner_uid='owner',founder_sweep_enabled=False)):
                    recovery._write_acceptance_receipt(attempt,identity)
                self.assertTrue(json.loads(destination.read_text())[-1]['clean_terminal'])
                self.assertEqual(len(attempt.business_read_proofs),1)
                if os.environ.get('CS_NATIVE_BUSINESS_READ_CONTROLS'):
                    export = Path(os.environ['CS_NATIVE_BUSINESS_READ_CONTROLS'])
                    controls = json.loads(export.read_text()) if export.exists() else []
                    controls.append(dict(case=case,qualification='Real local source-owned protocol child and constructed native events; no model/provider calls and not full operational acceptance',
                        receipt=json.loads(destination.read_text())[-1],events=events,lifecycle=lifecycle,context=context))
                    export.write_text(json.dumps(controls,indent=2)+'\n')
                    export.chmod(0o600)
                original = paths[0].read_bytes()
                for key, value in [('nonce','b'*32), ('owner_uid','foreign'), ('exit_code',1 if code == 3 else 3), ('output','changed')]:
                    changed = json.loads(original); changed[key]=value; paths[0].write_text(json.dumps(changed))
                    self.assertEqual(outcomes.join(events,identity,'owner',producer),[])
                for field in ('cli_identity','native_identity','supervisor_identity'):
                    changed = json.loads(original); changed[field]['started_ticks'] += 1
                    paths[0].write_text(json.dumps(changed))
                    self.assertEqual(outcomes.join(events,identity,'owner',producer,lifecycle),[])
                changed = json.loads(original); changed['argv'] = ['draft-send','foreign']
                paths[0].write_text(json.dumps(changed))
                self.assertEqual(outcomes.join(events,identity,'owner',producer,lifecycle),[])
                paths[0].write_bytes(original)
                duplicate = paths[0].parent / '1-1.json'
                duplicate.write_bytes(original); duplicate.chmod(0o600)
                self.assertEqual(outcomes.join(events,identity,'owner',producer,lifecycle),[])
                duplicate.unlink()
                changed = copy.deepcopy(events); changed[4]['message']['content'][0]['content'] += 'changed'
                self.assertEqual(outcomes.join(changed,identity,'owner',producer),[])
                changed = copy.deepcopy(events); changed[4]['session_id']='foreign'
                self.assertEqual(outcomes.join(changed,identity,'owner',producer),[])
                self.assertEqual(outcomes.join(events,identity,'foreign',producer),[])
                paths[0].chmod(0o644)
                self.assertEqual(outcomes.join(events,identity,'owner',producer),[])
                paths[0].chmod(0o600)
                backup = root / 'retained-capture.json'
                paths[0].rename(backup)
                paths[0].symlink_to(backup)
                self.assertEqual(outcomes.join(events,identity,'owner',producer,lifecycle),[])

    def test_real_private_reads_without_acceptance_environment(self):
        for case in ('assignment','contacted','history','history_json','deferral','search_deferral'):
            with self.subTest(case=case):
                self._real_control(case)


if __name__ == '__main__':
    unittest.main()
