"""One bounded scheduled dossier; partial evidence can only hold its roots."""
from __future__ import annotations
import io,json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from . import operator_workset as workset
from .operator_health import identity,private
from .operator_inventory_view import exclusive,read_private,source_identity

TOTAL_SECONDS=600
CLEANUP_SECONDS=20
CRM_SECONDS=10
MAX_BYTES=4*1024*1024
WORKER_COMMAND=(sys.executable,'-B','-m','cs.operator_dossier','--worker')
CRM_COMMAND=(sys.executable,'-B','-m','cs.operator_dossier','--crm-worker')

class DossierError(RuntimeError):pass

def _read(path):return json.loads(read_private(path))
def _save(path,value):
 raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
 if len(raw)>MAX_BYTES:raise DossierError('capacity')
 fd,name=tempfile.mkstemp(prefix='.dossier-',dir=Path(path).parent)
 try:
  with os.fdopen(fd,'wb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def _scope(settings,contact):return workset.selected_contact_roots(settings,contact)
def _marker(directory,root):return Path(directory)/('dossier-root-'+workset._hash(root)+'.json')
def _bound(a,b):return all(a.get(k)==b.get(k)for k in ('schema','nonce','owner_uid','contact','roots','source_identity','attempt'))

def require_effect_allowed(settings,root):
 """A failed attempted read cannot be ignored; success grants no authority."""
 context=workset._context(settings)
 if context is None:return
 directory=Path(context['directory']);touched=[]
 if (directory/'dossier-context-failure.json').exists():
  failure=_read(directory/'dossier-context-failure.json')
  if failure.get('nonce')!=context['nonce']or failure.get('owner_uid')!=context['owner_uid']:raise workset.WorksetError('foreign dossier context failure')
  raise workset.WorksetError('scheduled dossier context could not be validated')
 attempts=list(directory.glob('dossier-attempt-*'))
 if len(attempts)>16:raise workset.WorksetError('dossier attempt capacity exceeded')
 for attempt in attempts:
  if attempt.is_symlink() or not attempt.is_dir():raise workset.WorksetError('unsafe dossier evidence')
  private(attempt,True)
  manifest=_read(attempt/'request.json')
  if manifest['nonce']!=context['nonce']or manifest['owner_uid']!=context['owner_uid']:raise workset.WorksetError('foreign dossier evidence')
  if any(row['thread_key']==root for row in manifest['roots']):touched.append((attempt,manifest))
 if not touched:return
 if len(touched)!=1:raise workset.WorksetError('repeated dossier attempt remains held')
 attempt,manifest=touched[0];marker=_read(_marker(directory,root));result=_read(attempt/'result.json')
 if (not _bound(marker,manifest)or not _bound(result,manifest)or marker.get('status')!='ready'
     or result.get('task_context_completeness')!='unverified' or marker.get('task_context_completeness')!='unverified'
     or result.get('report_complete')is not True or root not in result.get('ready_roots',[])
     or manifest['roots']!=_scope(settings,manifest['contact'])
     or manifest['source_identity']!=source_identity()):raise workset.WorksetError('dossier evidence incomplete or changed')


def _members(group):
 rows=[]
 for path in Path('/proc').iterdir():
  if not path.name.isdigit():continue
  try:
   fields=(path/'stat').read_text().rsplit(')',1)[1].split()
   if int(fields[2])==group:rows.append({'pid':int(path.name),'started_ticks':int(fields[19]),'state':fields[0]})
  except (OSError,ValueError,IndexError):pass
 return rows

def _stop(proc,stamp,deadline):
 try:
  actual,_=identity(proc.pid)
  if actual!=stamp:return False
 except FileNotFoundError:pass
 try:os.killpg(proc.pid,signal.SIGKILL)
 except ProcessLookupError:pass
 try:proc.wait(timeout=max(.001,deadline-time.monotonic()))
 except subprocess.TimeoutExpired:return False
 while time.monotonic()<deadline:
  if not _members(proc.pid):return True
  time.sleep(.01)
 return not _members(proc.pid)


def _supervise(settings,args,*,worker_command=WORKER_COMMAND,total_seconds=TOTAL_SECONDS,cleanup_seconds=CLEANUP_SECONDS):
 started=time.monotonic();deadline=started+total_seconds;work_deadline=deadline-cleanup_seconds
 if not 0<cleanup_seconds<total_seconds:raise ValueError('invalid dossier lifecycle')
 context=workset._context(settings);roots=_scope(settings,args.email);directory=Path(context['directory'])
 if len(list(directory.glob('dossier-attempt-*')))>=16:raise workset.WorksetError('dossier attempt capacity exceeded')
 attempt=Path(tempfile.mkdtemp(prefix='dossier-attempt-',dir=directory));attempt.chmod(0o700)
 manifest={'schema':1,'nonce':context['nonce'],'owner_uid':context['owner_uid'],'contact':args.email,
           'roots':roots,'source_identity':source_identity(),'attempt':attempt.name,'parent':identity(os.getpid())[0]}
 exclusive(attempt/'request.json',json.dumps(manifest).encode())
 claimed=[];proc=None;stamp=None;clean=True;code=3;reason='setup';ready=False;ready_roots=[];report_complete=False
 try:
  for row in roots:
   path=_marker(directory,row['thread_key']);exclusive(path,json.dumps({**manifest,'status':'in_progress'}).encode());claimed.append(path)
  if time.monotonic()>=work_deadline:raise DossierError('deadline')
  payload={'settings':settings.model_dump(mode='json'),'manifest':manifest,'attempt_directory':str(attempt),
           'work_deadline':work_deadline,'dedup_days':args.dedup_days}
  encoded=json.dumps(payload).encode()
  if len(encoded)>MAX_BYTES:raise DossierError('capacity')
  with tempfile.TemporaryFile()as out,tempfile.TemporaryFile()as err:
   proc=subprocess.Popen(worker_command,stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
   stamp,_=identity(proc.pid);payload['worker_identity']=stamp;encoded=json.dumps(payload).encode()
   try:
    proc.communicate(encoded,timeout=max(.001,work_deadline-time.monotonic()))
    reason='worker_failed'
   except subprocess.TimeoutExpired:reason='deadline'
   finally:clean=_stop(proc,stamp,deadline)
   out.seek(0);raw=out.read(MAX_BYTES+1)
   if len(raw)>MAX_BYTES:raise DossierError('capacity')
   text=raw.decode('utf-8');sys.stdout.write(text);sys.stdout.flush()
  if not clean:raise DossierError('cleanup_incomplete')
  outcome=_read(attempt/'worker-result.json')
  if (proc.returncode not in (0,3) or proc.returncode!=outcome.get('exit_code')
      or not _bound(outcome,manifest)or outcome.get('worker')!=stamp
      or outcome.get('task_context_completeness')!='unverified'
      or outcome.get('status')!='complete'or not isinstance(outcome.get('ready_roots'),list)
      or len(set(outcome['ready_roots']))!=len(outcome['ready_roots'])
      or any(root not in {r['thread_key']for r in roots}for root in outcome['ready_roots'])):raise DossierError(reason)
  if _scope(settings,args.email)!=roots or source_identity()!=manifest['source_identity']:raise DossierError('selection_changed')
  code=proc.returncode;ready_roots=outcome['ready_roots'];ready=len(ready_roots)==len(roots);report_complete=True;reason='complete'if code==0 else 'required_evidence_incomplete'
 except Exception as exc:
  if isinstance(exc,DossierError):reason=str(exc)if str(exc)in {'deadline','capacity','cleanup_incomplete','selection_changed','worker_failed'}else 'worker_failed'
  elif isinstance(exc,workset.WorksetError):reason='selection_changed'
  if proc is not None and proc.poll()is None:clean=_stop(proc,stamp,deadline)
 finally:
  phase_name='setup'
  if (attempt/'phase.json').exists():
   phase_record=_read(attempt/'phase.json')
   if _bound(phase_record,manifest)and phase_record.get('phase')in {'validate','correspondence','dedup','local_state','authority','tasks','crm','render','revalidate'}:phase_name=phase_record['phase']
  result={**manifest,'phase':phase_name,'status':'complete'if code==0 else 'failed','ready':ready and code==0,
          'task_context_completeness':'unverified','report_complete':report_complete,'ready_roots':ready_roots,'reason':reason,'cleanup_complete':clean,'elapsed_seconds':time.monotonic()-started}
  _save(attempt/'result.json',result)
  for path in claimed:
   prior=_read(path)
   if not _bound(prior,manifest)or prior.get('status')!='in_progress':raise DossierError('foreign marker')
   _save(path,{**manifest,'task_context_completeness':'unverified','status':'ready'if prior['roots'] and any(_marker(directory,r)==path for r in ready_roots) else 'held'if report_complete else 'failed'})
 if code:
  print('Dossier incomplete: '+reason+' during '+phase_name+'; selected conversations remain held.',file=sys.stderr)
 return code


def run(settings,args):
 try:return _supervise(settings,args)
 except Exception:
  context=workset._context(settings)
  if context is not None:_save(Path(context['directory'])/'dossier-context-failure.json',{'nonce':context['nonce'],'owner_uid':context['owner_uid'],'reason':'selection_invalid'})
  print('Dossier incomplete: invalid scheduled evidence; selected conversations remain held.',file=sys.stderr);return 3


def _bounded_crm(settings,contact,deadline,*,command=CRM_COMMAND):
 remaining=min(CRM_SECONDS,deadline-time.monotonic()-1)
 if remaining<=0:return '\n-- CRM unavailable: dossier read deadline --\n'
 payload=json.dumps({'settings':settings.model_dump(mode='json'),'contact':contact}).encode()
 with tempfile.TemporaryFile()as out,tempfile.TemporaryFile()as err:
  proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err)
  try:proc.communicate(payload,timeout=remaining)
  except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=1);return '\n-- CRM unavailable: auxiliary read deadline --\n'
  out.seek(0);raw=out.read(MAX_BYTES+1)
  if proc.returncode or len(raw)>MAX_BYTES:return '\n-- CRM unavailable: auxiliary read failed --\n'
  return raw.decode('utf-8')

class _BoundedOutput:
 def __init__(self,stream):self.stream=stream;self.size=0
 def write(self,text):
  self.size+=len(text.encode())
  if self.size>MAX_BYTES:raise DossierError('capacity')
  return self.stream.write(text)
 def flush(self):return self.stream.flush()


def _worker(payload,*,settings_factory=None):
 from . import config,cli
 settings=(settings_factory or config.Settings.model_validate)(payload['settings'])
 manifest=payload['manifest'];attempt=Path(payload['attempt_directory']);context=workset._context(settings)
 private(attempt,True)
 if (attempt.parent!=Path(context['directory'])or attempt.name!=manifest['attempt']
     or attempt.resolve()!=attempt or _read(attempt/'request.json')!=manifest
     or _scope(settings,manifest['contact'])!=manifest['roots']or source_identity()!=manifest['source_identity']
     or identity(os.getpid())[0]!=payload['worker_identity']or os.getpgrp()!=os.getpid()):raise DossierError('selection_changed')
 expected_ids={}
 raw=_read(Path(context['directory'])/'discovery.json')['discovery']
 for rows in raw.values():
  for row in rows if isinstance(rows,list)else []:
   if not isinstance(row,dict):continue
   root=workset._root(row);projection=row.get('assignment')
   if root in {r['thread_key']for r in manifest['roots']}and isinstance(projection,dict)and 'current_message_ids'in projection:
    ids=projection['current_message_ids']
    if not isinstance(ids,list)or any(not isinstance(x,str)for x in ids):raise DossierError('selection_changed')
    if root in expected_ids and expected_ids[root]!=set(ids):raise DossierError('selection_changed')
    expected_ids[root]=set(ids)
 state={'phase':'setup','ready_roots':[]}
 def phase(name):
  state['phase']=name;_save(attempt/'phase.json',{**manifest,'phase':name,'worker':payload['worker_identity']});sys.stdout.flush()
 def assessed(assignments,taken,corr_error,fan):
  if set(assignments)!={r['thread_key']for r in manifest['roots']}:raise DossierError('selection_changed')
  for root,ids in expected_ids.items():
   if set(assignments[root].get('current_message_ids',[]))!=ids:raise DossierError('selection_changed')
  state['ready_roots']=[root for root,value in assignments.items()if not taken and not corr_error and fan.complete and value.get('complete')is True and value.get('hold_auto_reply')is False]
 try:
  phase('validate');sys.stdout=_BoundedOutput(sys.stdout)
  code=cli._dossier_report(settings,SimpleNamespace(email=manifest['contact'],dedup_days=payload['dedup_days']),
      selected=manifest['roots'],deadline=payload['work_deadline'],owned_process_group=os.getpid(),phase=phase,
      authority_observer=assessed,crm_printer=lambda s,e:print(_bounded_crm(s,e,payload['work_deadline']),end=''))
  phase('revalidate')
  if _scope(settings,manifest['contact'])!=manifest['roots']:raise DossierError('selection_changed')
  _save(attempt/'worker-result.json',{**manifest,'worker':payload['worker_identity'],'status':'complete','task_context_completeness':'unverified','exit_code':code,'ready_roots':state['ready_roots'],'reason':'complete'if code==0 else 'required_evidence_incomplete'})
  return code
 except Exception:
  _save(attempt/'worker-result.json',{**manifest,'worker':payload['worker_identity'],'status':'failed','ready':False,'reason':'phase_failed','phase':state['phase']});return 3


def main():
 from . import config,cli
 raw=sys.stdin.buffer.read(MAX_BYTES+1)
 if len(raw)>MAX_BYTES:return 3
 try:
  value=json.loads(raw)
  if sys.argv[1:]==['--worker']:return _worker(value)
  if sys.argv[1:]==['--crm-worker']:
   settings=config.Settings.model_validate(value['settings']);sys.stdout=_BoundedOutput(sys.stdout);cli._print_crm_section(settings,value['contact']);return 0
 except Exception:return 3
 return 3
if __name__=='__main__':raise SystemExit(main())
