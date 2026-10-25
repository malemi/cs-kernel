"""Real CLI subprocess output preservation and strict optional discovery boundaries."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from cs import operator_discovery_receipt as receipt

command=receipt.COMMAND
wrapper=receipt.CLEANUP+" && eval '"+command+"' < /dev/null && pwd -P >| /tmp/claude-test-cwd"
assert receipt.extract_wrapper(['/bin/bash','-c',wrapper])['payload']==command
for text in [wrapper+' && true', 'echo '+wrapper,wrapper.replace('eval ', 'eval "true" && eval ',1),wrapper.replace(command,'echo '+command),wrapper.replace(command,command+' --help'),wrapper.replace('pwd -P','echo pwd -P'),wrapper.replace('/tmp/claude-test-cwd','/tmp/../elsewhere')]:
 try:receipt.extract_wrapper(['/bin/bash','-c',text])
 except ValueError:pass
 else:raise AssertionError(text)
for held in [False,True]:
 data={'open':[],'handled':[],'escalated':[],'human_work':[{'assignment':{'complete':False,'hold_auto_reply':True}}] if held else [],'assignment_audit':[],'operational_fixture_discovery':[],'read_incomplete':None,'assignment_incomplete':held,'padding':'x'*40000}
 script="""import json,sys
from types import SimpleNamespace
from unittest.mock import patch
from cs import cli,unanswered
value=json.loads(sys.argv[1])
args=SimpleNamespace(json=True,all_buckets=True,days=14,crm=False)
settings=SimpleNamespace(engine_owner_uid='fixture-owner')
with patch.object(cli.config,'load',return_value=settings),patch.object(unanswered,'sweep',return_value=value):
 raise SystemExit(cli.cmd_unanswered(args))
"""
 expected=data.copy();expected['crm_note']=None;emitted=(json.dumps(expected,ensure_ascii=False,indent=2,default=str)+'\n').encode()
 with tempfile.TemporaryDirectory() as tmp:
  env=dict(os.environ);env.pop('CS_OPERATOR_ACCEPTANCE_RECEIPT',None)
  off=subprocess.run([sys.executable,'-c',script,json.dumps(data)],env=env,capture_output=True)
  env.update(CS_OPERATOR_ACCEPTANCE_RECEIPT=str(Path(tmp)/'receipt.json'),CS_OPERATOR_ACCEPTANCE_NONCE='a'*32)
  enabled=subprocess.run([sys.executable,'-c',script,json.dumps(data)],env=env,capture_output=True)
  assert off.stdout==enabled.stdout==emitted and off.stderr==enabled.stderr==b''
  assert off.returncode==enabled.returncode==(3 if held else 0)
  assert not list(Path(tmp).iterdir())
with tempfile.TemporaryDirectory() as tmp:
 parent=Path(tmp);parent.chmod(0o700)
 with patch.dict(os.environ,{'CS_OPERATOR_ACCEPTANCE_RECEIPT':str(parent/'receipt'),'CS_OPERATOR_ACCEPTANCE_NONCE':'a'*32}):
  fd=receipt.private_dir(receipt.directory_path(),create=True);os.close(fd)
  (parent/'receipt.discovery').chmod(0o777)
  try:receipt.private_dir(receipt.directory_path())
  except ValueError:pass
  else:raise AssertionError('writable directory accepted')
  (parent/'receipt.discovery').chmod(0o700);(parent/'receipt.discovery').rmdir();(parent/'receipt.discovery').symlink_to('/tmp')
  try:receipt.private_dir(receipt.directory_path())
  except OSError:pass
  else:raise AssertionError('symlink accepted')
print('PASS: real CLI subprocess >40KB exit0/held3 exact stdout/stderr/exit preservation; strict wrapper and private path negatives.')
print('Controlled sweep fixture is code evidence, not native clean-mailbox proof.')

from datetime import datetime,timezone
from types import SimpleNamespace
from cs import cli,unanswered

sample={'open':[],'handled':[],'escalated':[],'human_work':[{'assignment':{'complete':False,'hold_auto_reply':True}}],'assignment_audit':[],'operational_fixture_discovery':[],'read_incomplete':None,'assignment_incomplete':True,'last_inbound_date':datetime(2026,10,13,tzinfo=timezone.utc)}
args=SimpleNamespace(json=True,all_buckets=True,days=14,crm=False)
settings=SimpleNamespace(engine_owner_uid='fixture-owner')
expected=(json.dumps({**sample,'crm_note':None},ensure_ascii=False,indent=2,default=str)+'\n')
with patch.dict(os.environ,{'CS_OPERATOR_ACCEPTANCE_RECEIPT':''}),patch.object(cli.config,'load',return_value=settings),patch.object(unanswered,'sweep',return_value=sample.copy()),patch.object(receipt,'proc',side_effect=AssertionError('optional process IO')),patch.object(Path,'read_text',side_effect=AssertionError('optional file IO')),patch.object(Path,'stat',side_effect=AssertionError('optional file IO')),patch('builtins.open',side_effect=AssertionError('optional file IO')),patch.object(sys,'stdout',io.StringIO()) as stdout,patch.object(sys,'stderr',io.StringIO()) as stderr:
 assert cli.cmd_unanswered(args)==3 and stdout.getvalue()==expected and stderr.getvalue()==''
with patch.dict(os.environ,{'CS_OPERATOR_ACCEPTANCE_RECEIPT':'enabled'}),patch.object(cli.config,'load',return_value=settings),patch.object(unanswered,'sweep',return_value=sample.copy()),patch.object(receipt,'capture',side_effect=OSError('private capture unavailable')),patch.object(sys,'stdout',io.StringIO()) as stdout,patch.object(sys,'stderr',io.StringIO()) as stderr:
 assert cli.cmd_unanswered(args)==3 and stdout.getvalue()==expected and stderr.getvalue()==''
print('PASS: disabled optional file/process IO spies and enabled capture failure preserve datetime-shaped real CLI bytes and semantic exit3.')

# Synthetic native events plus real executable/ancestry/capture composition.
# This is offline source evidence, never a genuine native model acceptance.
import copy
import hashlib
import shutil
import uuid

native_root = Path('/tmp') / ('claude-' + str(os.getuid()))
native_root.mkdir(mode=0o700, exist_ok=True)
assert native_root.stat().st_uid == os.getuid() and native_root.stat().st_mode & 0o777 == 0o700
repo = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=native_root, prefix='offline-discovery-') as temporary:
 root = Path(temporary); root.chmod(0o700)
 version = 'offline-test-native'
 binary = root / 'versions' / version; binary.parent.mkdir()
 shutil.copyfile(Path(sys.executable).resolve(), binary); binary.chmod(0o700)
 digest = hashlib.sha256(binary.read_bytes()).hexdigest()
 (root / '.venv').symlink_to(Path(sys.prefix), target_is_directory=True)
 cli_fixture = '''import sys,os,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path=[p for p in sys.path if p not in ('',os.getcwd())]
from cs import cli,unanswered,operator_discovery_receipt as receipt
receipt.CLAUDE_VERSION=os.environ['OFFLINE_VERSION']
receipt.CLAUDE_SHA256=os.environ['OFFLINE_SHA256']
value=json.loads(os.environ['OFFLINE_DISCOVERY'])
with patch.object(cli.config,'load',return_value=SimpleNamespace(engine_owner_uid='offline-owner')),patch.object(unanswered,'sweep',return_value=value):
 raise SystemExit(cli.cmd_unanswered(SimpleNamespace(json=True,all_buckets=True,days=14,crm=False)))
'''
 (root/'cs.py').write_text(cli_fixture)
 driver = '''import sys,subprocess,json,os
print('READY',flush=True)
sys.stdin.readline()
cli_env=dict(os.environ);cli_env.pop('PYTHONHOME',None)
p=subprocess.run(['/bin/bash','-c',os.environ['OFFLINE_WRAPPER']],capture_output=True,env=cli_env)
sys.stdout.buffer.write(p.stdout);sys.stdout.buffer.flush()
sys.stderr.buffer.write(p.stderr);sys.stderr.buffer.flush()
sys.exit(p.returncode)
'''
 for held in (False, True):
  case=root/('held' if held else 'clean');case.mkdir(mode=0o700)
  destination=case/'receipt';nonce=uuid.uuid4().hex
  value={'open':[], 'resumed':[], 'handled':[], 'escalated':[], 'human_work':[{'assignment':{'complete':False,'hold_auto_reply':True}}] if held else [], 'assignment_audit':[], 'operational_fixture_discovery':[], 'read_incomplete':None, 'assignment_incomplete':held}
  cwd_marker=Path('/tmp')/('claude-'+uuid.uuid4().hex+'-cwd')
  shell=receipt.CLEANUP+" && eval '"+receipt.COMMAND+"' < /dev/null && pwd -P >| "+str(cwd_marker)
  env=dict(os.environ,CS_OPERATOR_ACCEPTANCE_RECEIPT=str(destination),CS_OPERATOR_ACCEPTANCE_NONCE=nonce,
   CS_OPERATOR_DISCOVERY_SUPERVISOR=json.dumps({k:receipt.proc(os.getpid())[k] for k in ('pid','started_ticks')}),
   OFFLINE_VERSION=version,OFFLINE_SHA256=digest,OFFLINE_DISCOVERY=json.dumps(value),OFFLINE_WRAPPER=shell,
   PYTHONPATH=str(repo),PYTHONHOME=sys.base_prefix)
  env.pop('CS_OPERATOR_HEALTH_CONTEXT',None)
  with patch.object(receipt,'CLAUDE_VERSION',version),patch.object(receipt,'CLAUDE_SHA256',digest),patch.dict(os.environ,env):
   pinned=receipt.pin_native(str(binary));assert pinned
   with subprocess.Popen([pinned['path'],'-c',driver],cwd=root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as child_process:
    ready=child_process.stdout.readline()
    assert ready==b'READY\n',(ready,child_process.stderr.read().decode())
    live=receipt.proc(child_process.pid); child={k:live[k] for k in ('pid','started_ticks')}
    producer=receipt.bind_native(pinned,child);assert producer
    assert receipt.bind_native(pinned,{**child,'started_ticks':child['started_ticks']+1}) is None
    assert receipt.bind_native({**pinned,'sha256':'0'*64},child) is None
    stdout,stderr=child_process.communicate(b'continue\n',timeout=15)
    cwd_marker.unlink(missing_ok=True)
    assert child_process.returncode==(3 if held else 0),(child_process.returncode,stderr.decode())
   captures=list((case/'receipt.discovery').glob('*.json'));assert len(captures)==1
   record=json.loads(captures[0].read_text());assert record['native_identity']==child
   assert record['kernel_package_root']==str(repo / 'cs')
   assert record['pythonpath']==env['PYTHONPATH']
   session=str(uuid.uuid4());task='offline-task';run='offline-run';tool='offline-tool'
   taskdir=root/session/'tasks';taskdir.mkdir(parents=True)
   output=taskdir/(task+'.output');code=3 if held else 0
   output.write_bytes(stdout+('\n[exited with code '+str(code)+']\n').encode());output.chmod(0o664)
   raw_use={'type':'tool_use','id':tool,'name':'Bash','input':{'command':receipt.COMMAND,'description':'Offline discovery','timeout':600000}}
   raw_result={'type':'tool_result','tool_use_id':tool,'is_error':False,'content':'Command did not complete within its 600s timeout and was moved to the background'}
   membership={'task_id':task,'run_id':run,'task_type':'local_bash'}
   events=[{'type':'system','subtype':'init','claude_code_version':version},
    {'type':'assistant','message':{'content':[raw_use]}},
    {'type':'system','subtype':'task_started','task_id':task,'run_id':run,'tool_use_id':tool,'task_type':'local_bash','is_backgrounded':False},
    {'type':'system','subtype':'background_tasks_changed','tasks':[membership]},
    {'type':'system','subtype':'task_updated','task_id':task,'run_id':run,'patch':{'is_backgrounded':True}},
    {'type':'user','message':{'content':[raw_result]},'tool_use_result':{'backgroundTaskId':task,'interrupted':False}},
    {'type':'system','subtype':'task_updated','task_id':task,'run_id':run,'patch':{'status':'failed' if held else 'completed','end_time':1}},
    {'type':'system','subtype':'task_notification','task_id':task,'run_id':run,'tool_use_id':tool,'status':'failed' if held else 'completed','output_file':str(output),'summary':'Background command "Offline discovery" '+('failed with exit code 3' if held else 'completed (exit code 0)')},
    {'type':'system','subtype':'background_tasks_changed','tasks':[]},
    {'type':'result','subtype':'success','is_error':False,'terminal_reason':'completed','num_turns':2,'safety_stops':0,'result_index':0,'origin':None}]
   for index,event in enumerate(events):event.update(uuid=str(index),session_id=session)
   use={'phase':'discovery','tool_use_id':tool,'session_id':session,'command_digest':receipt.sha(receipt.COMMAND.encode())}
   phase={**use,'is_error':False,'error_status':None,'discovery_complete':False}
   phases=[copy.deepcopy(phase)];receipt.join([use],phases,events,child,'offline-owner',producer)
   assert phases[0]['discovery_complete'] is True,phases
   assert phases[0]['is_error'] is False and phases[0]['error_status'] is None
   assert phases[0]['automatic_completion']['exit_code']==code
   assert phases[0]['transport']['exit_code']==code
   assert phases[0]['transport']['kernel_package_root']==record['kernel_package_root']
   assert phases[0]['transport']['pythonpath']==record['pythonpath']
   # Real physical capture plus explicitly constructed complete control segments.
   from cs.operator_native_composition import composition
   from cs import operator_recovery as recovery
   for callback in (False, True):
    composed=copy.deepcopy(events)
    if callback:
     composed.insert(6,copy.deepcopy(composed[-1]))
     composed[-1:]=[copy.deepcopy(composed[0]),copy.deepcopy(composed[-1])]
     composed[-1].update(result_index=1,origin={'kind':'task-notification','producer':'session-task','runId':run})
    for index,event in enumerate(composed):event['uuid']='composed-'+str(index)
    lifecycle=composition(composed,producer);assert lifecycle is not None
    phases=[copy.deepcopy(phase)]
    receipt.join([use],phases,composed,child,'offline-owner',producer,lifecycle=lifecycle)
    assert phases[0]['discovery_complete'] is True,(callback,phases)
    assert phases[0]['automatic_completion']['exit_code']==code
    attempt=recovery.Attempt(0,composed,native_producer=producer,ordinary_native=True)
    with patch.object(recovery.config,'load',return_value=SimpleNamespace(engine_owner_uid='offline-owner')):
     recovery._write_acceptance_receipt(attempt,child)
    envelope=json.loads(destination.read_text())[-1]
    assert envelope['native_lifecycle']==lifecycle['proof'] and envelope['clean_terminal'] is True
    discovery=[row for row in envelope['phases'] if row['phase']=='discovery'][0]
    assert discovery['discovery_complete'] is True and discovery['is_error'] is False
    assert discovery['automatic_completion']['exit_code']==code
    if os.environ.get('CS_COMPOSITION_OFFLINE_PACKETS'):
     packet_path=Path(os.environ['CS_COMPOSITION_OFFLINE_PACKETS'])
     packets=json.loads(packet_path.read_text()) if packet_path.exists() else []
     packets.append({'qualification':'Real local ELF/capture and synthetic native events; not genuine native/provider acceptance',
                     'case':code,'callback':callback,'receipt':envelope})
     packet_path.write_text(json.dumps(packets,indent=2)+'\n')
    forged=copy.deepcopy(lifecycle);forged['proof']['event_sha256']='0'*64
    phases=[copy.deepcopy(phase)]
    receipt.join([use],phases,composed,child,'offline-owner',producer,lifecycle=forged)
    assert phases[0]['discovery_complete'] is False
    missing=composed[:-1]
    phases=[copy.deepcopy(phase)]
    receipt.join([use],phases,missing,child,'offline-owner',producer,lifecycle=lifecycle)
    assert phases[0]['discovery_complete'] is False
   # Original foreground failure results are native strings, not background
   # launch dictionaries. Lifecycle recognition still needs this real capture.
   foreground_result=copy.deepcopy(raw_result)
   foreground_result.update(is_error=held,content=('Exit code 3\n' if held else '')+stdout.decode())
   foreground=[copy.deepcopy(events[i]) for i in (0,1,2,7,5,9)]
   foreground[3].pop('output_file',None)
   foreground[4]={'type':'user','message':{'content':[foreground_result]},
                  'tool_use_result':'Error: '+foreground_result['content'] if held else {'interrupted':False}}
   for index,event in enumerate(foreground):event.update(uuid='foreground-'+str(index),session_id=session)
   lifecycle=composition(foreground,producer);assert lifecycle is not None
   foreground_phase={**use,'is_error':held,'error_status':3 if held else None,'discovery_complete':False}
   phases=[copy.deepcopy(foreground_phase)]
   receipt.join([use],phases,foreground,child,'offline-owner',producer,lifecycle=lifecycle)
   assert phases[0]['discovery_complete'] is True and phases[0]['transport']['exit_code']==code
   assert 'automatic_completion' not in phases[0]
   attempt=recovery.Attempt(0,foreground,native_producer=producer,ordinary_native=True)
   with patch.object(recovery.config,'load',return_value=SimpleNamespace(engine_owner_uid='offline-owner')):
    recovery._write_acceptance_receipt(attempt,child)
   envelope=json.loads(destination.read_text())[-1]
   assert envelope['clean_terminal'] is True and not attempt.health_failure
   if os.environ.get('CS_COMPOSITION_OFFLINE_PACKETS'):
    packet_path=Path(os.environ['CS_COMPOSITION_OFFLINE_PACKETS'])
    packets=json.loads(packet_path.read_text()) if packet_path.exists() else []
    packets.append({'qualification':'Real local ELF/capture and constructed foreground events; not genuine native/provider acceptance',
                    'case':code,'kind':'foreground','receipt':envelope})
    packet_path.write_text(json.dumps(packets,indent=2)+'\n')
   if held:
    missing=recovery.Attempt(0,foreground,native_producer=producer,ordinary_native=True)
    with patch.object(recovery.config,'load',return_value=SimpleNamespace(engine_owner_uid='offline-owner')),patch.object(receipt,'join'):
     recovery._write_acceptance_receipt(missing,child)
    assert missing.health_failure=='discovery_transport_invalid'
    assert json.loads(destination.read_text())[-1]['clean_terminal'] is False
   negatives=[]
   for index,key,replacement in [(0,'claude_code_version','unknown'),(2,'is_backgrounded',True),(2,'run_id','foreign'),(7,'run_id','foreign'),(7,'summary','failed'),(7,'status','killed')]:
    changed=copy.deepcopy(events);changed[index][key]=replacement;negatives.append(changed)
   negatives.extend([events[:-1],events+[copy.deepcopy(events[0])],events[:7]+[copy.deepcopy(events[7])]+events[7:],events[:4]+events[5:]])
   for changed in negatives:
    phases=[copy.deepcopy(phase)];receipt.join([use],phases,changed,child,'offline-owner',producer)
    assert phases[0]['discovery_complete'] is False
   phases=[copy.deepcopy(phase)];receipt.join([use],phases,events,child,'offline-owner',None)
   assert phases[0]['discovery_complete'] is False
   output.write_bytes(b'UNRELATED OUTPUT'+('\n[exited with code '+str(code)+']\n').encode())
   phases=[copy.deepcopy(phase)];receipt.join([use],phases,events,child,'offline-owner',producer)
   assert phases[0]['discovery_complete'] is False
   output.write_bytes(stdout+b'\n[exited with code 1]\n')
   phases=[copy.deepcopy(phase)];receipt.join([use],phases,events,child,'offline-owner',producer)
   assert phases[0]['discovery_complete'] is False
   output.unlink();output.symlink_to(captures[0])
   phases=[copy.deepcopy(phase)];receipt.join([use],phases,events,child,'offline-owner',producer)
   assert phases[0]['discovery_complete'] is False
print('PASS: offline real pinned executable/child ancestry/canonical capture join for exit0 and held3; synthetic automatic task events, identity/protocol/trailer/symlink negatives. No genuine native acceptance claimed.')
