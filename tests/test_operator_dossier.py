"""Free selected dossier primitives; real private captures/processes, no services."""
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cs import task_assignment as assignment,rpc_reads
from cs.operator_health import identity

SCOPE_WORKER=r'''
import hashlib,json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
from cs import cli, operator_workset as w, task_assignment
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch
ctx=json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT']);base=Path(ctx['directory']);settings=SimpleNamespace(engine_owner_uid='owner',state_dir=base/'state')
w.observe(settings,'tasks',[]);w.observe(settings,'review',{'drafts':[],'drafts_notes':[]})
value={'open':[{'email':'a@example.test','thread_key':'<a@example.test>','_workset_revision':'a'*64,'last_inbound_date':'2026-10-19'}, {'email':'b@example.test','thread_key':'<b@example.test>','_workset_revision':'b'*64,'last_inbound_date':'2026-10-18'}], 'resumed':[], 'human_work':[{'email':'a@example.test','thread_key':'<old-held@example.test>'}], 'assignment_audit':[], 'escalated':[], 'read_incomplete':None,'assignment_incomplete':False}
first_root = '<' + 'm' * 90 + '$part@example.test>'
value['open'][0]['thread_key'] = first_root
value['triage_workset']=w.reserve(settings,value)
code="import json,sys;from cs.operator_health import ARGV,capture;sys.argv=['fixture']+ARGV;d=json.load(sys.stdin);capture((json.dumps(d,ensure_ascii=False,indent=2)+'\\n').encode(),d,0,'owner')"
subprocess.run([sys.executable,'-B','-c',code],input=json.dumps(value),text=True,check=True)
assert [x['thread_key']for x in w.selected_contact_roots(settings,'a@example.test')]==[first_root]
assert [x['thread_key']for x in w.selected_contact_roots(settings,'B@example.test')]==['<b@example.test>']
checks=['A contact excludes B selected root and old held sibling','case-insensitive exact contact']
settings.prog_name = 'cs'
def assignment_status(*argv):
 with patch.object(cli.config, 'load', return_value=settings), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
  return cli.main(['assignment', 'status', *argv])
with patch.object(task_assignment, 'project', return_value={'complete': True}) as project:
 for position, expected in enumerate([first_root, '<b@example.test>'], 1):
  assert assignment_status('--selected', str(position), '--json') == 0
  project.assert_called_with(settings, expected)
 assert project.call_count == 2
 for extra in [('--selected', '3', '--json'), ('--selected', '1', first_root, '--json')]:
  try: assignment_status(*extra)
  except SystemExit as exc: assert exc.code == 2
  else: raise AssertionError('invalid arguments accepted')
 assert assignment_status('--selected', '1') == 2
 assert project.call_count == 2
files={p:p.read_bytes()for p in [base/'discovery.json',base/'workset-tasks.json',base/'workset-reserved.json',settings.state_dir/'operator-workset/cursor.json']}
def denied(label):
 try:w.selected_contact_roots(settings,'a@example.test')
 except w.WorksetError:checks.append(label)
 else:raise AssertionError(label)
for path,mutate,label in [
 (base/'discovery.json',lambda d:d.update(nonce='foreign'),'foreign nonce'),
 (base/'discovery.json',lambda d:d.update(owner_uid='foreign'),'foreign owner'),
 (base/'discovery.json',lambda d:d['ancestry'].__setitem__(-2,ctx['supervisor']),'foreign native child'),
 (base/'discovery.json',lambda d:d['ancestry'][-2].update(started_ticks=d['ancestry'][-2]['started_ticks']+1),'changed native start'),
 (base/'discovery.json',lambda d:d['discovery']['open'][0].update(_workset_revision='e'*64),'changed source revision'),
 (base/'discovery.json',lambda d:d['discovery']['triage_workset']['selected'][0].update(revision='f'*64),'changed public revision'),
 (base/'discovery.json',lambda d:d['discovery']['triage_workset'].update(complete=1),'nonboolean public completeness'),
 (base/'discovery.json',lambda d:d['discovery']['triage_workset'].update(limit=2.0),'noninteger public limit'),
 (settings.state_dir/'operator-workset/cursor.json',lambda d:d.update(version=True),'noninteger cursor version'),
 (base/'workset-tasks.json',lambda d:d.update(digest='0'*64),'changed observation digest'),
 (base/'workset-reserved.json',lambda d:d.update(digest='0'*64),'changed reservation digest'),
 (settings.state_dir/'operator-workset/cursor.json',lambda d:d['roots'][w._hash(first_root)].update(revision='f'*64),'changed cursor revision')]:
 data=json.loads(path.read_text());mutate(data)
 if path.name=='discovery.json':data['output_sha256']=hashlib.sha256((json.dumps(data['discovery'],ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
 path.write_text(json.dumps(data));denied(label)
 with patch.object(task_assignment, 'project', side_effect=AssertionError('unexpected projection')):
  assert assignment_status('--selected', '1', '--json') == 3
 path.write_bytes(files[path])
p=base/'discovery.json';p.chmod(0o644);denied('nonprivate capture');p.chmod(0o600)
original=base/'original-discovery';p.rename(original);p.symlink_to(original);denied('symlink capture');p.unlink();original.rename(p)
p.rename(original);denied('missing capture');original.rename(p)
try:w.selected_contact_roots(settings,'foreign@example.test')
except w.WorksetError:checks.append('unselected contact')
else:raise AssertionError('foreign contact')
reservation_path=base/'workset-reserved.json';cursor_path=settings.state_dir/'operator-workset/cursor.json'
reservation=json.loads(reservation_path.read_text());cursor=json.loads(cursor_path.read_text());reservation['contacts'].append(w._hash('foreign@example.test'));cursor['runs'][w._hash(ctx['nonce'])]['contacts']=reservation['contacts'];reservation_path.write_text(json.dumps(reservation));cursor_path.write_text(json.dumps(cursor));denied('forged contact union');reservation_path.write_bytes(files[reservation_path]);cursor_path.write_bytes(files[cursor_path])
nextdir=base/'takeover';nextdir.mkdir(mode=0o700);nextctx={**ctx,'directory':str(nextdir),'nonce':'b'*32};os.environ['CS_OPERATOR_HEALTH_CONTEXT']=json.dumps(nextctx)
w.observe(settings,'tasks',[]);w.observe(settings,'review',{'drafts':[],'drafts_notes':[]});taken={k:v for k,v in value.items()if k!='triage_workset'};taken['escalated']=[{'email':'a@example.test'}];taken['triage_workset']=w.reserve(settings,taken);subprocess.run([sys.executable,'-B','-c',code],input=json.dumps(taken),text=True,check=True)
denied('address takeover blocks contact A')
assert [r['thread_key']for r in w.selected_contact_roots(settings,'b@example.test')]==['<b@example.test>'];checks.append('unrelated contact B remains eligible')
with patch.object(task_assignment, 'project', side_effect=AssertionError('unexpected projection')):
 assert assignment_status('--selected', '2', '--json') == 3
 with patch.dict(os.environ, {'CS_OPERATOR_HEALTH_CONTEXT': ''}):
  assert assignment_status('--selected', '1', '--json') == 3
print(json.dumps({'scope_checks':checks,'no_authority_returned':all(set(r)=={'thread_key','revision','sources'}for r in w.selected_contact_roots(settings,'b@example.test'))}))
'''

GROUP_WORKER=r'''
import json,os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from cs import rpc_reads as r
s=SimpleNamespace(engine_owner_uid='owner',model_dump=lambda **kw:{'engine_owner_uid':'owner'})
normal="import json,os,sys;p=json.load(sys.stdin);print(json.dumps({'outcomes':{k:{'value':{'pid':os.getpid(),'group':os.getpgrp()},'error':None}for k in p['requests']},'token':None}))"
r.READ_COMMAND=(sys.executable,'-B','-c',normal)
a=r.read_many(s,'tasks.assignment.project',{'root':{}},owned_process_group=os.getpid())['root'];assert a.error is None and a.value['group']==os.getpid()
b=r.read_many(s,'tasks.assignment.project',{'root':{}})['root'];assert b.error is None and b.value['group']==b.value['pid'] and b.value['group']!=os.getpid()
with tempfile.TemporaryDirectory()as temp:
 marker=Path(temp)/'child.json';slow="import json,os,sys,time;open(sys.argv[1],'w').write(json.dumps({'pid':os.getpid(),'group':os.getpgrp()}));json.load(sys.stdin);time.sleep(10)"
 r.READ_COMMAND=(sys.executable,'-B','-c',slow,str(marker));r.CLOSE_SECONDS=.005
 got=r.read_many(s,'tasks.assignment.project',{'root':{}},batch_timeout=.2,owned_process_group=os.getpid())['root'];assert isinstance(got.error,TimeoutError)
 child=json.loads(marker.read_text());assert child['group']==os.getpid() and not Path('/proc/'+str(child['pid'])).exists()
print('actual inherited-group/default-isolation/timeout-reap PASS')
'''

class SelectedDossierPrimitives(unittest.TestCase):
 def test_real_capture_selection_and_refusals(self):
  with tempfile.TemporaryDirectory()as temp:
   ctx={'directory':temp,'nonce':'a'*32,'owner_uid':'owner','supervisor':identity(os.getpid())[0],'workset_enabled':True}
   r=subprocess.run([sys.executable,'-B','-c',SCOPE_WORKER],env={**os.environ,'CS_OPERATOR_HEALTH_CONTEXT':json.dumps(ctx)},text=True,capture_output=True,timeout=10)
   self.assertEqual(r.returncode,0,r.stderr);data=json.loads(r.stdout);self.assertEqual(len(data['scope_checks']),21);self.assertTrue(data['no_authority_returned'])
   from cs.operator_workset import selected_root, WorksetError
   settings = SimpleNamespace(engine_owner_uid='owner', state_dir=Path(temp) / 'state')
   discovery = json.loads((Path(temp) / 'discovery.json').read_bytes())
   child = discovery['ancestry'][-2]
   for position, row in enumerate(discovery['discovery']['triage_workset']['selected'], 1):
    self.assertEqual(selected_root(settings, position, context=ctx, child_identity=child), row['thread_key'])
   with self.assertRaises(WorksetError):
    selected_root(settings, 1, context=ctx, child_identity={**child, 'started_ticks': child['started_ticks'] + 1})
 def test_missing_scheduled_context_refuses(self):
  from cs.operator_workset import selected_contact_roots,WorksetError
  env={k:v for k,v in os.environ.items()if k!='CS_OPERATOR_HEALTH_CONTEXT'}
  with patch.dict(os.environ,env,clear=True):
   with self.assertRaises(WorksetError):selected_contact_roots(SimpleNamespace(engine_owner_uid='owner'),'a@example.test')
 def test_expired_deadline_issues_no_read(self):
  settings=SimpleNamespace(engine_owner_uid='owner',account_map={})
  with patch.object(rpc_reads,'read_many',side_effect=AssertionError('unexpected upstream')):
   result=assignment.projections(settings,['<a@example.test>','<b@example.test>'],deadline=time.monotonic()-1)
  self.assertEqual(len(result),2);self.assertTrue(all(x['hold_auto_reply']and not x['complete']for x in result.values()))
 def test_invalid_deadline_or_group_refuses(self):
  settings=SimpleNamespace(engine_owner_uid='owner',account_map={})
  for deadline in (True,float('nan'),float('inf'),'1'):
   with self.assertRaises(ValueError):assignment.projections(settings,['<a@example.test>'],deadline=deadline)
  with self.assertRaises(ValueError):assignment.projections(settings,[],owned_process_group=-1)
  with self.assertRaises(ValueError):rpc_reads.read_many(settings,'tasks.assignment.project',{},owned_process_group=-1)
 def test_absolute_deadline_is_forwarded(self):
  settings=SimpleNamespace(engine_owner_uid='owner',account_map={});deadline=time.monotonic()+20;seen=[]
  def read(*args,**kwargs):seen.append(kwargs['deadline']);return {'<a@example.test>':rpc_reads.ReadOutcome(error=RuntimeError('CONSTRUCTED unavailable'))}
  with patch.object(rpc_reads,'read_many',side_effect=read):result=assignment.projections(settings,['<a@example.test>'],deadline=deadline)
  self.assertEqual(seen,[deadline]);self.assertTrue(result['<a@example.test>']['hold_auto_reply'])
 def test_owned_and_default_worker_groups_real_processes(self):
  r=subprocess.run([sys.executable,'-B','-c',GROUP_WORKER],text=True,capture_output=True,start_new_session=True,timeout=10)
  self.assertEqual(r.returncode,0,r.stderr)


M2_RENDERER=r'''
import contextlib,json,os,socket,sys
from pathlib import Path
from types import SimpleNamespace
from cs import cli,gmail_archive,mailboxes,task_assignment as ta,operator_dossier as d
payload=json.load(sys.stdin);mode=sys.argv[1]
def factory(data):
 data=dict(data);data['state_dir']=Path(data['state_dir']);settings=SimpleNamespace(**data);settings.model_dump=lambda **kw:{**data,'state_dir':str(data['state_dir'])};return settings
settings=factory(payload['settings'])
def block():
 a,b=socket.socketpair();a.recv(1)
def correspondence(*args,**kw):
 assert kw=={'assignment_metadata':True}
 if mode=='correspondence':block()
 return [{'direction':'in','date':'Mon, 19 Oct 2026 00:00:00 +0000','subject':'CONSTRUCTED HISTORICAL FACT','thread_key':key,'message_id':key}for key in ['<a@example.test>','<b@example.test>','<old@example.test>']]
def dedup(*a,**kw):
 assert kw['days']is None
 if mode=='dedup':block()
 return mailboxes.Fanout(rows=[],read=['support@example.test'],unreadable=[],skipped=[])
def normal(key):return {'version':1,'actor_uid':'owner','space_id':'space','thread_key':key,'complete':True,'state':'normal','hold_auto_reply':False,'task':None,'reason':'CONSTRUCTED','current_inbound':[],'covered_inbound':[],'current_message_ids':[],'covered_message_ids':[],'events':[],'reply_evidence':[]}
def project(s,keys,**kw):
 assert kw['owned_process_group']==os.getpid()and kw['deadline']==payload['work_deadline']
 Path(payload['attempt_directory'],'constructed-roots.json').write_text(json.dumps(list(keys)))
 if mode in ('authority','in_progress'):block()
 if mode=='selection_changed':
  p=settings.state_dir/'operator-workset/cursor.json';cursor=json.loads(p.read_text());from cs.operator_workset import _hash;cursor['roots'][_hash('<a@example.test>')]['revision']='f'*64;p.write_text(json.dumps(cursor))
 result={key:normal(key)for key in keys}
 if mode=='partial':result['<a@example.test>'].update(complete=False,state='unknown',hold_auto_reply=True)
 return result
def tasks(*a,**kw):
 assert a[1]=='tasks.list'
 if mode=='tasks':block()
 if mode=='tasks_incomplete':return {'tasks':[],'complete':False}
 if mode=='tasks_empty_object':return {}
 if mode=='tasks_bad_row':return [{}]
 if mode=='tasks_rpc_error':raise RuntimeError('CONSTRUCTED RPC error')
 if mode in ('tasks_cap','tasks_filtered'):return [{'id':str(i),'contact_email':'a@example.test','title':'RETAINED TASK '+str(i)}for i in range(500 if mode=='tasks_cap'else 2)]
 return []
gmail_archive.correspondence=correspondence;mailboxes.sent_to_across=dedup;mailboxes.close_sessions=lambda:None;ta.projections=project;cli.rpc.call_sync=tasks;d._bounded_crm=lambda *a,**kw:'\n-- CRM constructed --\n'
if mode=='overflow':sys.stdout.write('X'*(d.MAX_BYTES+1));raise SystemExit(0)
raise SystemExit(d._worker(payload,settings_factory=factory))
'''

M2_NATIVE=r'''
import json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
from cs import operator_workset as w,operator_dossier as d
ctx=json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT']);base=Path(ctx['directory']);mode=sys.argv[1];renderer=sys.argv[2]
settings=SimpleNamespace(engine_owner_uid='owner',state_dir=base/'state',email_address='support@example.test',email_password='',db_path=str(base/'state.db'),prog_name='cs',timezone='UTC')
settings.model_dump=lambda **kw:{k:str(v)if isinstance(v,Path)else v for k,v in vars(settings).items()if k!='model_dump'}
w.observe(settings,'tasks',[]);w.observe(settings,'review',{'drafts':[],'drafts_notes':[]})
value={'open':[{'email':'a@example.test','thread_key':'<a@example.test>','_workset_revision':'a'*64,'last_inbound_date':'2026-10-19'}, {'email':'a@example.test'if mode=='partial'else'b@example.test','thread_key':'<b@example.test>','_workset_revision':'b'*64,'last_inbound_date':'2026-10-18'}], 'resumed':[],'human_work':[{'email':'a@example.test','thread_key':'<old@example.test>'}],'assignment_audit':[],'escalated':[],'read_incomplete':None,'assignment_incomplete':False}
if mode=='identity_changed':value['open'][0]['assignment']={'version':1,'actor_uid':'owner','source_owner_uid':'owner','space_id':'space','thread_key':'<a@example.test>','complete':True,'state':'normal','hold_auto_reply':False,'reason':'CONSTRUCTED','task':None,'current_message_ids':['<fresh-source@example.test>'],'covered_message_ids':[],'current_inbound':[],'covered_inbound':[],'reply_evidence':[],'events':[]}
value['triage_workset']=w.reserve(settings,value)
code="import json,sys;from cs.operator_health import ARGV,capture;sys.argv=['fixture']+ARGV;d=json.load(sys.stdin);capture((json.dumps(d,ensure_ascii=False,indent=2)+'\\n').encode(),d,0,'owner')"
subprocess.run([sys.executable,'-B','-c',code],input=json.dumps(value),text=True,check=True)
foreign=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(10)'],start_new_session=True)
try:
 if mode=='setup_changed':
  cursor_path=settings.state_dir/'operator-workset/cursor.json';cursor=json.loads(cursor_path.read_text());cursor['roots'][w._hash('<a@example.test>')]['revision']='f'*64;cursor_path.write_text(json.dumps(cursor))
  from cs import cli
  from unittest.mock import patch
  with patch.object(cli.config,'load',return_value=settings),patch.object(cli.rpc,'chat',side_effect=AssertionError('must not compose')):
   assert cli.cmd_dossier(SimpleNamespace(email='a@example.test',dedup_days=30))==3
   assert cli.cmd_draft_reply(SimpleNamespace(thread_id='<a@example.test>'))==3
  assert (base/'dossier-context-failure.json').exists();print('M2_RESULT setup failure held before upstream');raise SystemExit(0)
 if mode=='in_progress':
  import concurrent.futures,time
  with concurrent.futures.ThreadPoolExecutor(max_workers=1)as pool:
   pending=pool.submit(d._supervise,settings,SimpleNamespace(email='a@example.test',dedup_days=30),worker_command=[sys.executable,'-B','-c',renderer,mode],total_seconds=2,cleanup_seconds=.5)
   until=time.monotonic()+1
   while not d._marker(base,'<a@example.test>').exists()and time.monotonic()<until:time.sleep(.01)
   try:d.require_effect_allowed(settings,'<a@example.test>')
   except Exception:pass
   else:raise AssertionError('in-progress effect admitted')
   d.require_effect_allowed(settings,'<b@example.test>');rc=pending.result(timeout=3)
 else:
  rc=d._supervise(settings,SimpleNamespace(email='a@example.test',dedup_days=30),worker_command=[sys.executable,'-B','-c',renderer,'success'if mode=='repeat'else mode],total_seconds=2,cleanup_seconds=.5)
 assert foreign.poll()is None,'foreign process signalled'
 attempts=list(base.glob('dossier-attempt-*'));assert len(attempts)==1;attempt=attempts[0];result=json.loads((attempt/'result.json').read_text());assert result['cleanup_complete'] and result['elapsed_seconds']<2.3
 def allowed(root):
  try:d.require_effect_allowed(settings,root)
  except Exception:return False
  return True
 if mode in ('success','repeat','tasks_cap','tasks_filtered','tasks_masked_db_empty'):
  assert result['task_context_completeness']=='unverified'
  assert json.loads(d._marker(base,'<a@example.test>').read_text())['task_context_completeness']=='unverified'
  assert rc==0 and allowed('<a@example.test>')and allowed('<b@example.test>')
  assert json.loads((attempt/'constructed-roots.json').read_text())==['<a@example.test>']
  from cs import cli,task_assignment
  from unittest.mock import patch
  with patch.object(cli.config,'load',return_value=settings),patch.object(task_assignment,'guard',side_effect=task_assignment.AssignmentUnavailable('CONSTRUCTED current hold'))as fresh,patch.object(cli.rpc,'chat',side_effect=AssertionError('must not compose')):
   assert cli.cmd_draft_reply(SimpleNamespace(thread_id='<a@example.test>'))==3;fresh.assert_called_once()
  if mode=='repeat':
   sentinel=base/'must-not-start';again=d._supervise(settings,SimpleNamespace(email='a@example.test',dedup_days=30),worker_command=[sys.executable,'-c',"open(__import__('sys').argv[1],'w').write('bad')",str(sentinel)],total_seconds=2,cleanup_seconds=.5);assert again==3 and not sentinel.exists()and not allowed('<a@example.test>')
  else:
   marker=d._marker(base,'<a@example.test>');marker.unlink();assert not allowed('<a@example.test>')
 elif mode=='partial':assert rc==3 and not allowed('<a@example.test>')and allowed('<b@example.test>')
 else:
  assert rc==3 and not allowed('<a@example.test>')
  if mode!='selection_changed':assert allowed('<b@example.test>')
 if mode in ('correspondence','dedup','authority','tasks'):assert json.loads((attempt/'phase.json').read_text())['phase']==mode
 print('M2_RESULT '+json.dumps({'mode':mode,'code':rc,'elapsed':result['elapsed_seconds'],'clean':result['cleanup_complete']}))
finally:foreign.terminate();foreign.wait(timeout=2)
'''

class ScheduledDossierWorker(unittest.TestCase):
 def run_mode(self,mode):
  with tempfile.TemporaryDirectory()as temp:
   ctx={'directory':temp,'nonce':'c'*32,'owner_uid':'owner','supervisor':identity(os.getpid())[0],'workset_enabled':True}
   r=subprocess.run([sys.executable,'-B','-c',M2_NATIVE,mode,M2_RENDERER],env={**os.environ,'CS_OPERATOR_HEALTH_CONTEXT':json.dumps(ctx)},capture_output=True,text=True,timeout=8,start_new_session=True)
   self.assertEqual(r.returncode,0,r.stderr+'\n'+r.stdout)
   self.assertIn('M2_RESULT ',r.stdout)
   if mode in ('success','tasks_cap','tasks_filtered','tasks_masked_db_empty'):
    self.assertIn('completeness UNVERIFIED',r.stdout)
    if mode in ('tasks_cap','tasks_filtered'):self.assertIn('RETAINED TASK '+str(499 if mode=='tasks_cap'else 1),r.stdout)
 def test_success_scope_missing_marker_and_foreign_group(self):self.run_mode('success')
 def test_partial_root_does_not_hold_independent_root(self):self.run_mode('partial')
 def test_in_progress_cannot_be_ignored(self):self.run_mode('in_progress')
 def test_failed_selection_before_worker_blocks_effects(self):self.run_mode('setup_changed')
 def test_repeated_attempt_does_not_launch_worker(self):self.run_mode('repeat')
 def test_fresh_message_identity_change_refuses(self):self.run_mode('identity_changed')
 def test_blocked_correspondence_whole_deadline(self):self.run_mode('correspondence')
 def test_blocked_dedup_whole_deadline(self):self.run_mode('dedup')
 def test_blocked_authority_whole_deadline(self):self.run_mode('authority')
 def test_blocked_tasks_whole_deadline(self):self.run_mode('tasks')
 def test_malformed_empty_task_object_refuses(self):self.run_mode('tasks_empty_object')
 def test_malformed_task_row_refuses(self):self.run_mode('tasks_bad_row')
 def test_explicit_task_rpc_failure_refuses(self):self.run_mode('tasks_rpc_error')
 def test_capped_tasks_unknown_preserves_rows_and_fresh_guard(self):self.run_mode('tasks_cap')
 def test_filtered_tasks_unknown_preserves_rows_and_fresh_guard(self):self.run_mode('tasks_filtered')
 def test_masked_db_empty_unknown_and_fresh_guard(self):self.run_mode('tasks_masked_db_empty')
 def test_incomplete_task_context_refuses(self):self.run_mode('tasks_incomplete')
 def test_selection_changes_refuse_publication(self):self.run_mode('selection_changed')
 def test_pipe_overflow_refuses(self):self.run_mode('overflow')
 def test_auxiliary_crm_timeout_is_degraded(self):
  from cs import operator_dossier as d
  settings=SimpleNamespace(model_dump=lambda **kw:{})
  command=[sys.executable,'-B','-c','import socket;s,t=socket.socketpair();s.recv(1)']
  text=d._bounded_crm(settings,'a@example.test',time.monotonic()+1.15,command=command)
  self.assertIn('CRM unavailable',text)

if __name__=='__main__':unittest.main()
