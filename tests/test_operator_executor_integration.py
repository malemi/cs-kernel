"""Real recovery → executor → canonical CLI controls with network disabled."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from test_operator_executor import ExecutorTests, SOURCE
from cs import operator_recovery as recovery
from cs.operator_executor_evidence import validate
from cs.operator_executor_protocol import canonical, decode, sha256

SDK = Path('/tmp/mrcall-ai-kit/pydantic-headless-20261028/venv/bin/python')

FIXTURE_MODEL = '''
import cs.operator_executor as executor
from pydantic_ai import models
models.ALLOW_MODEL_REQUESTS = False
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
queue = [['whoami','--json'],['config','--json'],['tasks','--json'],['review','--json'],['unanswered','--days','14','--json','--all-buckets'],['standing-instructions','--json'],['campaign','list'],['campaign','pending']]
seen = set()
reads = []
def scan(value):
 if isinstance(value,dict):
  for art in value.get('required_inventory_artifacts',[]):
   if art['artifact_id'] not in seen:
    seen.add(art['artifact_id']); reads.append((art['artifact_id'],art['bytes']))
  for item in value.values(): scan(item)
 elif isinstance(value,list):
  for item in value: scan(item)
 elif isinstance(value,str) and value.startswith('{'):
  try: scan(json.loads(value))
  except ValueError: pass
import httpx2
import pydantic_ai.models.anthropic as anthropic_model
count=0
async def transport(request):
 global count
 body=json.loads(request.content)
 scan(body)
 if queue:
  content=[dict(type='tool_use',id='tool-'+str(count),name='run_cs',input={'argv':queue.pop(0)})]
 elif reads:
  aid,size=reads.pop(0)
  content=[dict(type='tool_use',id='page-'+str(count),name='read_artifact',input=dict(artifact_id=aid,offset=0,length=16384))]
 else:content=[dict(type='text',text='Fixture complete')]
 count+=1
 return httpx2.Response(200,json=dict(id='fixture-'+str(count),type='message',role='assistant',model='fixture-model',content=content,stop_reason='tool_use' if content[0]['type']=='tool_use' else 'end_turn',usage=dict(input_tokens=100,output_tokens=10)))
original_client=httpx2.AsyncClient
class FixtureClient(original_client):
 def __init__(self,*args,**kwargs):
  kwargs['transport']=httpx2.MockTransport(transport)
  super().__init__(*args,**kwargs)
httpx2.AsyncClient=FixtureClient
anthropic_model.check_allow_model_requests=lambda:None
'''

class IntegrationTests(ExecutorTests):
    # Reuse fixture setup, not the M1 test methods as a second suite.
    def setup_integration(self, case=None):
        self.temp._finalizer.detach()
        self.temp.cleanup=lambda:None
        self.install_services()
        (self.root/'.venv').unlink()
        (self.root/'.venv').symlink_to(SDK.parent.parent,target_is_directory=True)
        site=self.base/'fixture-services/sitecustomize.py'
        text=site.read_text().replace("raw = (json.dumps(value)+'\\n').encode()", "raw = (json.dumps(value,ensure_ascii=False,indent=2)+'\\n').encode()")
        text=text.replace("'assignment_audit':[]","'assignment_audit':[], 'operational_fixture_discovery':[]")
        self.integration_case=case
        model=FIXTURE_MODEL
        if case in ('held-root','held-member','held-malformed','held-peer','r3-already-classified'):
            text=text.replace("'open':[]", "'open':[{'thread_key':'<fixture-root@fixture.test>','email':'contact@fixture.test','_workset_revision':'f'*64}]")
            text+='''
from cs import task_assignment
projection=dict(version=1,actor_uid='fixture-owner',source_owner_uid='fixture-owner',space_id='fixture-space',thread_key='<fixture-root@fixture.test>',state='conflict',reason='RFC_ANCESTRY_CONFLICT',complete=False,hold_auto_reply=True,task=None,component_scope_present=False,authoritative_thread_key='<fixture-root@fixture.test>',component_thread_keys=['<fixture-root@fixture.test>'],events=[],covered_inbound=[],current_inbound=[],covered_message_ids=[],current_message_ids=[],reply_evidence=[])
task_assignment.project=lambda settings,root:projection
'''
            model=model.replace("seen = set()", "queue.append(['assignment','status','<fixture-root@fixture.test>','--json'])\nseen = set()")
            if case in ('held-member','held-malformed','held-peer'):
                actor='fixture-peer' if case=='held-peer' else 'fixture-owner'
                judgement='MALFORMED_OWN_SENT_REQUIRES_HUMAN_VERIFICATION' if case=='held-malformed' else 'MEMBER_ACTIVITY_REQUIRES_HUMAN_VERIFICATION'
                text+='''
projection.update(state='needs-assignment',reason=__REASON__,reply_evidence=[dict(version=1,actor_uid=__ACTOR__,space_id='fixture-space',thread_key='<fixture-root@fixture.test>',complete=True,judgement=__JUDGEMENT__,reason='NEEDS_HUMAN_VERIFICATION',source_id='fixture-source',digest='a'*64,source=dict(actor_uid=__ACTOR__,thread_key='<fixture-root@fixture.test>',message_id='<fixture-root@fixture.test>',observation_only=True,mailbox_id='fixture-mailbox',provider=dict(folder='Sent',uidvalidity=1,uid=2),route_digest='b'*64,raw_header_digest='c'*64))])
'''.replace('__ACTOR__',repr(actor)).replace('__JUDGEMENT__',repr(judgement)).replace('__REASON__',repr('peer reply requires explicit human verification and assignment' if case=='held-peer' else 'NEEDS_HUMAN_VERIFICATION'))
                if case=='held-peer':os.environ['CS_ACCOUNTS']='colleague:fixture-peer'
                if case=='held-malformed':text+="\nprojection.update(authority_complete=False,hold_scope='exact_observed_message')\n"

        if case in ('worked-root','draft-root','send-root','repair-mark'):
            text=text.replace('cli.cmd_tasks_create = effect','original_tasks_create = cli.cmd_tasks_create\ncli.cmd_tasks_create = effect')
            text=text.replace("'open':[]", "'open':[{'thread_key':'<fixture-root@fixture.test>','email':'contact@fixture.test','_workset_revision':'f'*64}]")
            text+='''
from cs import task_assignment,mailboxes,gmail_archive,operator_dossier
root='<fixture-root@fixture.test>'
def normal(root):
 return dict(version=1,actor_uid='fixture-owner',source_owner_uid='fixture-owner',space_id='fixture-space',thread_key=root,state='normal',reason='fixture current unheld source',complete=True,hold_auto_reply=False,task=None,events=[],covered_inbound=[],current_inbound=[],covered_message_ids=[],current_message_ids=[root],reply_evidence=[])
task_assignment.project=lambda settings,root:normal(root)
task_assignment.projections=lambda settings,roots,**kw:{root:normal(root) for root in roots}
gmail_archive.correspondence=lambda settings,email,**kw:[dict(direction='in',thread_key=root,message_id=root,date='Wed, 28 Oct 2026 00:00:00 +0000',subject='Fixture request')]
def empty(settings,*a,**kw):return mailboxes.Fanout(rows=[],read=[settings.email_address],unreadable=[],skipped=[])
mailboxes.sent_to_across=empty
mailboxes.sent_to_here=empty
mailboxes.inbound_since_across=empty
mailboxes.close_sessions=lambda:None
original_call=cli.rpc.call_sync
def worked_call(settings,method,params=None,**kw):
 if method=='emails.list_by_thread':return dict(emails=[dict(id='71993202-46d4-4431-ac39-43fd0b68b051',message_id=root,body='Fixture full original message body')])
 if method=='tasks.create':return dict(ok=True,task_id='fixture-recorded-task',created=True)
 return original_call(settings,method,params,**kw)
cli.rpc.call_sync=worked_call
cli.cmd_tasks_create=original_tasks_create
'''
            model=model.replace("seen = set()", "queue.extend([['assignment','status','<fixture-root@fixture.test>','--json'],['rpc','emails.list_by_thread','{\"thread_id\":\"<fixture-root@fixture.test>\"}'],['dossier','contact@fixture.test'],['history','contact@fixture.test','--json'],['contacted','contact@fixture.test']])\nseen = set()")
            model=model.replace("else:content=[dict(type='text',text='Fixture complete')]", "elif not globals().get('did_task'):\n  globals()['did_task']=True\n  content=[dict(type='tool_use',id='record-task',name='run_cs',input={'argv':['tasks','create','--email','contact@fixture.test','--title','Needs human answer','--event-id','<fixture-root@fixture.test>','--thread-id','<fixture-root@fixture.test>','--json']})]\n else:content=[dict(type='text',text='Fixture complete')]")
        if case in ('draft-root','send-root'):
            state_path=str(self.base/'draft-backend.json')
            text+='''
from cs import gmail_drafts
from pathlib import Path
from datetime import datetime,timezone
state_path=Path(__STATE_PATH__)
def load_draft():return json.loads(state_path.read_text()) if state_path.exists() else None
prior_call=cli.rpc.call_sync
def draft_call(settings,method,params=None,**kw):
 if method=='drafts.list':
  row=load_draft();return [row] if row and row['status']==(params or {}).get('status','draft') else []
 return prior_call(settings,method,params,**kw)
cli.rpc.call_sync=draft_call
async def draft_chat(settings,message,**kw):
 draft_id='452ddb83-69c9-479c-98ab-b6f690eab2a7'
 if kw['allow_tools']==set():
  assert kw['assignment_thread_key']==root
  now=datetime.now(timezone.utc).isoformat()
  row=dict(id=draft_id,owner_id=settings.email_address,thread_id=root,to_addresses=['contact@fixture.test'],cc_addresses=[],bcc_addresses=[],subject='Re: Fixture',body='Fixture grounded reply.',body_format='plain',in_reply_to=root,references=[root],original_message_id=root,attachment_paths=[],status='draft',created_at=now,updated_at=now)
  state_path.write_text(json.dumps(row));return dict(result={'response':'Fixture composed'},approvals=[],notifications=[])
 assert kw['allow_tools']=={'send_draft'}
 assert kw['approval_predicate']('send_draft',{'draft_id':draft_id}) is True
 row=load_draft();row['status']='sent';state_path.write_text(json.dumps(row))
 return dict(result={'response':'Fixture sent'},approvals=[dict(tool='send_draft',mode='once',input={'draft_id':draft_id})],notifications=[])
cli.rpc.chat=draft_chat
gmail_drafts.append_draft=lambda *a,**kw:('Drafts',[])
gmail_drafts.list_drafts=lambda *a,**kw:[]
'''.replace('__STATE_PATH__',repr(state_path))
            task="['tasks','create','--email','contact@fixture.test','--title','Needs human answer','--event-id','<fixture-root@fixture.test>','--thread-id','<fixture-root@fixture.test>','--json']"
            model=model.replace(task,"['draft-reply','Reply grounded in the fixture body','--thread-id','<fixture-root@fixture.test>']")
            if case=='send-root':
                os.environ.update(CS_TRIAGE_MODE='send',CS_HEADLESS_SEND='1',CS_EXECUTOR_EXACT_SEND_IDS=json.dumps(['452ddb83-69c9-479c-98ab-b6f690eab2a7']))
                model=model.replace("else:content=[dict(type='text',text='Fixture complete')]", "elif not globals().get('did_send'):\n  globals()['did_send']=True\n  content=[dict(type='tool_use',id='send-exact',name='run_cs',input={'argv':['draft-send','452ddb83-69c9-479c-98ab-b6f690eab2a7']})]\n else:content=[dict(type='text',text='Fixture complete')]")
        if case=='r3-already-classified':
            text=text.replace("campaign.list_campaigns = lambda settings: []","real_campaign_list = campaign.list_campaigns\ncampaign.list_campaigns = lambda settings: []")
            text=text.replace("campaign.pending = lambda settings, **kw: {'campaigns':[]}","real_campaign_pending = campaign.pending\ncampaign.pending = lambda settings, **kw: {'campaigns':[]}")
            text+='''
from pathlib import Path
from cs import mailboxes
backend=Path(__BACKEND__)
if not backend.exists():backend.write_text(json.dumps(dict(updates=0,contact=dict(id='fixture-contact',email='contact@fixture.test',state='sent',sent_at='2026-10-01T00:00:00+00:00',draft_subject='Fixture prior outreach',draft_body='Fixture prior outreach body',dossier={'classified_upto':'2026-10-28T01:00:00+00:00'}))))
prior_preview_call=cli.rpc.call_sync
def preview_call(settings,method,params=None,**kw):
 data=json.loads(backend.read_text())
 if method=='campaign.list':return [dict(id='fixture-campaign',name='fixture-campaign',contacts_by_state={'sent':1})]
 if method=='campaign.contacts':return [data['contact']]
 if method=='campaign.update_contact':
  data['updates']+=1;backend.write_text(json.dumps(data));raise AssertionError('already classified must not mutate')
 if method=='emails.search':return dict(threads=[dict(thread_id='<fixture-root@fixture.test>',subject='Fixture reply')])
 if method=='emails.list_by_thread':return dict(emails=[dict(body='Already classified fixture full body.',from_email='contact@fixture.test',date='2026-10-28T00:00:00+00:00')])
 return prior_preview_call(settings,method,params,**kw)
cli.rpc.call_sync=preview_call
campaign.list_campaigns=real_campaign_list
campaign.pending=real_campaign_pending
mailboxes.inbound_since_across=lambda settings,*a,**kw:mailboxes.Fanout(rows=[dict(date='Wed, 28 Oct 2026 00:00:00 +0000',subject='Fixture reply')],read=[settings.email_address],unreadable=[],skipped=[])
mailboxes.close_sessions=lambda:None
'''.replace('__BACKEND__',repr(str(self.base/'classified-backend.json')))
            model=model.replace("seen = set()", "queue.extend([['thread','contact@fixture.test','--json'],['campaign','mark','fixture-contact'],['rpc','emails.list_by_thread','{\"thread_id\":\"<fixture-root@fixture.test>\"}']])\nseen = set()")
        if case=='repair-mark':
            text=text.replace("campaign.list_campaigns = lambda settings: []","real_campaign_list = campaign.list_campaigns\ncampaign.list_campaigns = lambda settings: []")
            text=text.replace("campaign.pending = lambda settings, **kw: {'campaigns':[]}","real_campaign_pending = campaign.pending\ncampaign.pending = lambda settings, **kw: {'campaigns':[]}")
            text=text.replace("message_id=root,body='Fixture full original message body'", "message_id=root,body='Fixture full original message body',from_email='contact@fixture.test',date='2026-10-28T00:00:00+00:00'")
            text+='''
from pathlib import Path
backend=Path(__BACKEND__)
if not backend.exists():backend.write_text(json.dumps(dict(contact=dict(id='fixture-contact',email='contact@fixture.test',state='sent',sent_at='2026-10-01T00:00:00+00:00',draft_subject='Fixture prior outreach',draft_body='Fixture prior outreach body',dossier={}))))
prior_mark_call=cli.rpc.call_sync
def mark_call(settings,method,params=None,**kw):
 data=json.loads(backend.read_text())
 if method=='campaign.list':return [dict(id='fixture-campaign',name='fixture-campaign',contacts_by_state={'sent':1})]
 if method=='campaign.contacts':return [data['contact']]
 if method=='campaign.update_contact':
  data['contact'].update({k:v for k,v in params.items() if k!='contact_id'});backend.write_text(json.dumps(data));return dict(updated=True)
 if method=='emails.search':return dict(threads=[dict(thread_id=root,subject='Fixture reply')])
 return prior_mark_call(settings,method,params,**kw)
cli.rpc.call_sync=mark_call
campaign.list_campaigns=real_campaign_list
campaign.pending=real_campaign_pending
def replies(settings,*a,**kw):return mailboxes.Fanout(rows=[dict(date='Wed, 28 Oct 2026 00:00:00 +0000',subject='Fixture reply',direction='in',mailbox=settings.email_address)],read=[settings.email_address],unreadable=[],skipped=[])
mailboxes.inbound_since_across=replies
'''.replace('__BACKEND__',repr(str(self.base/'mark-backend.json')))
            model=model.replace("queue.extend([['assignment'", "queue.extend([['thread','contact@fixture.test','--json'],['assignment'")
            mark=['campaign','mark','fixture-contact','--dossier',json.dumps(dict(escalated=True,escalate_reason='Fixture needs human review',classified_upto='2026-10-28T00:00:00+00:00')),'--commit']
            model=model.replace("else:content=[dict(type='text',text='Fixture complete')]", "elif not globals().get('did_mark'):\n  globals()['did_mark']=True\n  content=[dict(type='tool_use',id='mark-reply',name='run_cs',input={'argv':"+repr(mark)+"})]\n else:content=[dict(type='text',text='Fixture complete')]")
        if case in ('repair-queue','repair-queue-fallback'):
            text=text.replace("campaign.list_campaigns = lambda settings: []","real_campaign_list = campaign.list_campaigns\ncampaign.list_campaigns = lambda settings: []")
            text=text.replace("campaign.pending = lambda settings, **kw: {'campaigns':[]}","real_campaign_pending = campaign.pending\ncampaign.pending = lambda settings, **kw: {'campaigns':[]}")
            text+='''
from pathlib import Path
from cs import mailboxes,gmail_drafts
backend=Path(__BACKEND__)
if not backend.exists():backend.write_text(json.dumps(dict(lookups=0,contact=dict(id='fixture-contact',email='contact@fixture.test',state='drafted',draft_subject='Fixture outreach',draft_body='Fixture prewritten outreach.',dossier={}))))
prior_campaign_call=cli.rpc.call_sync
def campaign_call(settings,method,params=None,**kw):
 data=json.loads(backend.read_text())
 if method=='campaign.list':return [dict(id='fixture-campaign',name='fixture-campaign',contacts_by_state={'drafted':1})]
 if method=='campaign.contacts':return [data['contact']]
 if method=='campaign.update_contact':
  data['contact'].update({k:v for k,v in params.items() if k!='contact_id'})
  backend.write_text(json.dumps(data));return dict(updated=True)
 return prior_campaign_call(settings,method,params,**kw)
cli.rpc.call_sync=campaign_call
campaign.list_campaigns=real_campaign_list
campaign.pending=real_campaign_pending
def campaign_sent(settings,*a,**kw):
 data=json.loads(backend.read_text());data['lookups']+=1;backend.write_text(json.dumps(data))
 rows=[dict(thread_id='fixture-already-sent',subject='Fixture prior message',date='Wed, 28 Oct 2026 00:00:00 +0000')] if __FALLBACK__ and data['lookups']>=2 else []
 return mailboxes.Fanout(rows=rows,read=[settings.email_address],unreadable=[],skipped=[])
mailboxes.sent_to_across=campaign_sent
mailboxes.close_sessions=lambda:None
gmail_drafts.append_draft=lambda *a,**kw:('Drafts',[])
'''.replace('__BACKEND__',repr(str(self.base/'campaign-backend.json'))).replace('__FALLBACK__',repr(case=='repair-queue-fallback'))
            actions=[['campaign','queue-draft','fixture-contact','--commit']]
            if case=='repair-queue-fallback':actions.append(['campaign','reconcile','fixture-contact','--commit'])
            model=model.replace('seen = set()', 'work_actions='+repr(actions)+'\nseen = set()')
            model=model.replace("else:content=[dict(type='text',text='Fixture complete')]", "elif work_actions:\n  content=[dict(type='tool_use',id='campaign-action-'+str(count),name='run_cs',input={'argv':work_actions.pop(0)})]\n else:content=[dict(type='text',text='Fixture complete')]")
        if case=='outside-workset':
            model=model.replace("seen = set()", "queue.append(['dossier','excluded@fixture.test'])\nseen = set()")
        if case == 'campaign-reconcile':
            text+='''
campaign.list_campaigns=lambda settings:[dict(id='fixture-campaign',name='fixture-campaign')]
campaign.pending=lambda settings,**kw:dict(campaigns=[dict(campaign='fixture-campaign',id='fixture-campaign',items=[dict(action='reconcile',contact_id='fixture-contact',email='contact@fixture.test')])])
campaign.reconcile=lambda settings,contact_id,**kw:dict(ok=True,email='contact@fixture.test',result={'state':'sent'})
'''
            # Delay the actual commit until inventory pages entered a successful
            # request. The tested command still uses real policy/argparse/CLI.
            model=model.replace("else:content=[dict(type='text',text='Fixture complete')]", "elif not globals().get('did_commit'):\n  globals()['did_commit']=True\n  content=[dict(type='tool_use',id='commit',name='run_cs',input={'argv':['campaign','reconcile','fixture-contact','--commit']})]\n else:content=[dict(type='text',text='Fixture complete')]")
        (site.parent/'fixture_backend.py').write_text(text+model)
        site.write_text("import socket\nfrom pathlib import Path\ntrap=Path("+repr(str(self.base/'socket-attempts.txt'))+")\ndef blocked(*a,**kw):\n with trap.open('a') as out:out.write('attempt\\n')\n raise RuntimeError('fixture network disabled')\nsocket.socket.connect=blocked\nsocket.socket.connect_ex=blocked\nfrom pydantic_ai import models\nmodels.ALLOW_MODEL_REQUESTS=False\nimport fixture_backend\n")
        pricing=dict(provider='anthropic',model='fixture-model',source='free fixture worst-case rates',
            input_upper_usd_per_million='1',output_upper_usd_per_million='1',maximum_context_tokens=1000000)
        os.environ.update(CS_EXECUTOR_PROVIDER='anthropic',CS_EXECUTOR_MODEL='fixture-model',
            CS_EXECUTOR_API_KEY_ENV='CS_FIXTURE_EXECUTOR_KEY',CS_FIXTURE_EXECUTOR_KEY='fixture-nonsecret',CS_EXECUTOR_PRICING_JSON=json.dumps(pricing),
            CS_EXECUTOR_ADMITTED_CEILING_USD='20',CS_EXECUTOR_MAX_OUTPUT_TOKENS='100')
        self.receipt=self.private/'supervisor.json'
        os.environ.update(CS_OPERATOR_ACCEPTANCE_RECEIPT=str(self.receipt),CS_OPERATOR_ACCEPTANCE_NONCE='e'*32)

    def launch(self):
        # Reject malformed bootstrap/backend before any executor launch.
        fixture=self.base/'fixture-services'
        for name in ('sitecustomize.py','fixture_backend.py'):
            compile((fixture/name).read_text(),str(fixture/name),'exec')
        launch_code="import sys; from cs import operator_recovery as r; a=r._run('unused',['Write','Edit'],executor='pydantic',allows=sorted(r.EXACT_SEND_ALLOW_RULES) if __SEND__ else None); sys.exit(0 if a.executor_facts and not a.health_failure else 1)".replace('__SEND__',repr(self.integration_case=='send-root'))
        command=[str(SDK),'-c',launch_code]
        import threading,time,importlib.metadata
        from cs.operator_health import identity
        from cs.operator_inventory_view import source_identity
        from cs.operator_executor_evidence import digest
        preflight=dict(kernel_package_root=str(SOURCE/'cs'),pythonpath=os.environ['PYTHONPATH'],
            kernel_source_digest=source_identity(),executor_binding=dict(clone_root=str(self.root),
                interpreter=dict(path=str(SDK.resolve()),bytes=SDK.resolve().stat().st_size,sha256=digest(SDK.resolve().read_bytes())),
                executor_module_digest=digest((SOURCE/'cs/operator_executor.py').read_bytes()),
                dependency_version=importlib.metadata.version('pydantic-ai-slim'),
                launch_policy=dict(provider='anthropic',model='fixture-model',api_key_env='CS_FIXTURE_EXECUTOR_KEY',
                    send_mode='send' if self.integration_case=='send-root' else 'draft',founder_enabled=False,campaign_enabled=True,admitted_ceiling_usd='20',max_output_tokens=100)))
        observed={};stop=threading.Event()
        proc=subprocess.Popen(command,cwd=self.root,env=dict(os.environ),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        def observe():
            while not stop.is_set():
                pids=[proc.pid]
                for pid in pids:
                    try:
                        row,_=identity(pid);observed[str(pid)]=row['started_ticks']
                        pids.extend(int(p) for p in Path(f'/proc/{pid}/task/{pid}/children').read_text().split())
                    except (OSError,ValueError):pass
                time.sleep(.02)
        observer=threading.Thread(target=observe);observer.start()
        try:
            stdout,stderr=proc.communicate(timeout=90)
        finally:
            stop.set();observer.join()
        result=subprocess.CompletedProcess(command,proc.returncode,stdout,stderr)
        if result.returncode != 0 and self.receipt.exists():
            failed=json.loads(self.receipt.read_text())[-1]
            path=Path(failed['executor_proof']['journal']['path'])
            rows=[decode(r)['payload'] for r in path.read_bytes().splitlines()]
            result.stdout += '\n'+str({k:rows[-1][k] for k in ('terminal','phase_outcomes','diagnostic')})+' retained='+str(self.base)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        receipt=json.loads(self.receipt.read_text())[-1]
        self.assertTrue(receipt['clean_terminal'],receipt.get('executor_facts'))
        packet=dict(receipt=receipt,nonce='e'*32,owner='fixture-owner',owned=observed,
            required_phases=['identity','configuration','tasks','review','discovery','campaigns'],source=preflight)
        packet_path=Path('/tmp/mrcall-ai-kit/pydantic-headless-20261028/m2/real-packet'+('-'+self.integration_case if self.integration_case else '')+'.json')
        packet_path.write_text(json.dumps(packet,sort_keys=True));packet_path.chmod(0o600)
        return receipt

    def test_recovery_child_cli_and_independent_mutations(self):
        self.setup_integration()
        receipt=self.launch()
        proof,context=receipt['executor_proof'],receipt['business_read_context']
        self.assertEqual(proof['expected']['executor'],receipt['child_identity'])
        self.assertGreater(len(receipt['executor_facts']['tool_proofs']),7)
        # Parent assertions survive while validation independently rejects the
        # mutated joins; no process/model booleans grant acceptance.
        for name in ('nonce','owner','kernel_source_digest'):
            bad=copy.deepcopy(proof); bad['expected'][name]='foreign'
            with self.subTest(binding=name), self.assertRaises(ValueError): validate(bad,context)
        for name in ('executor','supervisor'):
            bad=copy.deepcopy(proof); bad['expected'][name]['started_ticks']+=1
            with self.subTest(process=name), self.assertRaises(ValueError): validate(bad,context)
        journal=Path(proof['journal']['path']); original=journal.read_bytes()
        for mode in ('empty','missing_terminal','bad_chain','missing_submission_page','early_effect'):
            rows=[decode(raw) for raw in original.splitlines()]
            if mode=='empty': rows=[]
            elif mode=='missing_terminal': rows=rows[:-1]
            elif mode=='bad_chain': rows[1]['previous_digest']='f'*64
            elif mode=='missing_submission_page':
                row=next(r for r in rows if r['payload']['kind']=='model_request' and r['payload']['page_ids'])
                row['payload']['page_ids']=[]
            elif mode=='early_effect':
                row=next(r for r in rows if r['payload']['kind']=='tool_start' and r['payload']['name']=='run_cs')
                row['payload']['argv']=['tasks','create','--email','x@fixture.test','--title','x','--event-id','x']
            if mode not in ('bad_chain','empty'):
                previous='0'*64
                for i,row in enumerate(rows):
                    row['sequence']=i;row['previous_digest']=previous
                    if row['payload']['kind']=='run_end':row['payload']['final_journal_digest']=previous
                    previous=sha256(canonical(row))
            raw=b''.join(canonical(row)+b'\n' for row in rows);journal.write_bytes(raw)
            bad=copy.deepcopy(proof);bad['journal'].update(bytes=len(raw),sha256=sha256(raw))
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate(bad,context)
        journal.write_bytes(original)
        # Retain one real complete free transport fixture for the independent
        # consumer worker; tests never place a provider key in this receipt.
        import shutil
        destination=Path('/tmp/mrcall-ai-kit/pydantic-headless-20261028/m2/free-fixture')
        if destination.exists():shutil.rmtree(destination)
        shutil.copytree(self.base,destination)
        # Original paths are valid until tearDown. Rebase exact local references
        # in a separate copy without claiming it is the genuine parent fixture.
        self.assertNotIn('native_lifecycle',receipt)

    def test_outer_deadline_terminates_detached_group_and_reaps(self):
        import time,signal
        from cs.operator_health import identity
        marker=self.base/'detached-child'
        child_code="import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(90)"
        host_code=("import subprocess,sys,signal; from pathlib import Path; "
            "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            "p=subprocess.Popen([sys.executable,'-c',"+repr(child_code)+"],start_new_session=True); "
            "Path("+repr(str(marker))+").write_text(str(p.pid)); p.wait()")
        proc=subprocess.Popen([str(SDK),'-c',host_code],start_new_session=True)
        try:
            deadline=time.monotonic()+3
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(marker.exists())
            pid=int(marker.read_text());child,_=identity(pid)
            time.sleep(.1)
            expected=identity(proc.pid)[0]
            with patch('cs.operator_health.identity',return_value=({'pid':proc.pid,'started_ticks':expected['started_ticks']+1},os.getpid())),patch('os.killpg') as kill:
                with self.assertRaises(ValueError):recovery._stop_executor(proc,expected,grace_seconds=.2)
                self.assertEqual(kill.call_count,0)
            self.assertEqual(recovery._stop_executor(proc,expected,grace_seconds=.2),0)
            self.assertIsNotNone(proc.returncode)
            self.assertFalse(Path(f'/proc/{child["pid"]}').exists(),'detached child not reaped')
        finally:
            if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()

    def test_backend_syntax_failure_prevents_executor_and_network(self):
        self.setup_integration()
        (self.base/'fixture-services/fixture_backend.py').write_text('def broken(:\n')
        with patch('subprocess.Popen',side_effect=AssertionError('executor must not launch')) as spawn:
            with self.assertRaises(SyntaxError):self.launch()
        self.assertEqual(spawn.call_count,0)
        self.assertFalse((self.base/'socket-attempts.txt').exists())
        self.assertFalse(self.receipt.exists())

    def test_repaired_queue_actual_canonical_producers(self):
        self.setup_integration('repair-queue');receipt=self.launch()
        state=json.loads((self.base/'campaign-backend.json').read_text())
        self.assertTrue(state['contact']['dossier']['gmail_draft_pushed'])
        self.assertEqual(receipt['executor_facts']['phases']['campaign_work'],'completed')

    def test_repaired_queue_reconcile_fallback_actual_canonical_producers(self):
        self.setup_integration('repair-queue-fallback');receipt=self.launch()
        state=json.loads((self.base/'campaign-backend.json').read_text())
        self.assertEqual(state['contact']['state'],'sent')
        self.assertTrue(state['contact']['dossier']['reconciled'])
        self.assertEqual(receipt['executor_facts']['phases']['campaign_work'],'completed')

    def test_submitted_call_canonical_policy_compatibility(self):
        from types import SimpleNamespace
        from cs.operator_executor_evidence import run_call_matches
        from cs.operator_executor_tools import PREFIXES,validate_argv
        calls=[['campaign','mark','fixture-contact'],
            ['rpc','emails.list_by_thread','{ "thread_id" : "fixture-root" }']]
        count=0
        for raw in calls:
            canonical_argv,effect=validate_argv(raw,self.config)
            self.assertFalse(effect)
            start=SimpleNamespace(argv=canonical_argv,decision='allow')
            end=SimpleNamespace(effect=effect)
            for prefix in ((),*PREFIXES):
                with self.subTest(raw=raw,prefix=prefix):
                    self.assertTrue(run_call_matches({'argv':list(prefix)+raw},start,end,self.config))
                    count+=1
            foreign=list(canonical_argv);foreign[-1]='foreign-contact' if raw[0]=='campaign' else '{"thread_id":"foreign-root"}'
            self.assertFalse(run_call_matches({'argv':foreign},start,end,self.config))
            self.assertFalse(run_call_matches({'argv':raw,'extra':True},start,end,self.config))
            self.assertFalse(run_call_matches({'argv':raw},start,SimpleNamespace(effect=True),self.config))
        denied=SimpleNamespace(argv=['rpc','forbidden','{}'],decision='deny')
        self.assertTrue(run_call_matches({'argv':denied.argv},denied,SimpleNamespace(effect=False),self.config))
        self.assertFalse(run_call_matches({'argv':['rpc','other','{}']},denied,SimpleNamespace(effect=False),self.config))
        self.assertGreaterEqual(count,4)

    def test_repaired_submitted_lifecycle_and_result_mutations(self):
        self.setup_integration('r3-already-classified');self.integration_case='r4-call-join'
        receipt=self.launch()
        from cs import operator_executor_evidence as evidence,operator_executor_protocol as protocol
        original_parse=protocol.parse_journal;original_read=evidence.read_private
        proof=receipt['executor_proof'];context=receipt['business_read_context']
        rows=[decode(raw) for raw in Path(proof['journal']['path']).read_bytes().splitlines()]
        target=['campaign','mark','fixture-contact']
        tool=next(r['payload']['tool_id'] for r in rows if r['payload']['kind']=='tool_start' and r['payload'].get('argv')==target)
        self.assertFalse(any(r['payload'].get('effect') for r in rows))
        run_directory=Path(proof['journal']['path']).parent
        for mode in ('deleted-lifecycle','sdk-foreign-result','sdk-changed-result','wire-foreign-result','wire-changed-result','sdk-missing-id','wire-missing-id','sdk-no-metadata','wire-no-metadata','sdk-foreign-call','wire-foreign-call','wire-renamed-missing-id','wire-call-args','wire-call-id','wire-duplicate-call','both-call-args'):
            mutated=copy.deepcopy(rows)
            if mode=='deleted-lifecycle':
                mutated=[r for r in mutated if not(r['payload']['kind'] in ('tool_start','tool_spawn','tool_end') and r['payload'].get('tool_id')==tool)]
            else:
                def alter(value):
                    if isinstance(value,dict):
                        wire=value.get('type')=='tool_use' and value.get('input',{}).get('argv')==target
                        sdk=value.get('part_kind')=='tool-call' and value.get('args',{}).get('argv')==target
                        if wire:
                            if mode=='wire-renamed-missing-id':value['name']='read_artifact'
                            elif mode in ('wire-call-args','both-call-args'):value['input']['argv']=['campaign','mark','foreign-contact']
                            elif mode=='wire-call-id':value['id']='foreign-call-id'
                        if sdk and mode=='both-call-args':value['args']['argv']=['campaign','mark','foreign-contact']
                        if mode.endswith('foreign-call') and (value.get('part_kind')=='tool-return' or value.get('type')=='tool_result') and tool.encode() in canonical(value.get('content')):
                            key='tool_call_id' if value.get('part_kind')=='tool-return' else 'tool_use_id'
                            value[key]='foreign-call-id'
                        if value.get('tool_id')==tool and 'status' in value:
                            if mode.endswith('missing-id'):value.pop('tool_id')
                            elif mode.endswith('no-metadata'):
                                value={key:child for key,child in value.items() if key not in ('tool_id','status','exit_code','stdout','stderr')}
                            elif mode.endswith('foreign-result'):value['tool_id']='11111111-1111-4111-8111-111111111111'
                            elif mode.endswith('changed-result'):value['status']='error'
                        return {key:alter(child) for key,child in value.items()}
                    if isinstance(value,list):
                        result=[]
                        for child in value:
                            result.append(alter(child))
                            if mode=='wire-duplicate-call' and isinstance(child,dict) and child.get('type')=='tool_use' and child.get('input',{}).get('argv')==target:
                                result.append(copy.deepcopy(child))
                        return result
                    if isinstance(value,str) and value.lstrip().startswith('{'):
                        try:return canonical(alter(decode(value))).decode()
                        except ValueError:return value
                    return value
                kind='model_request' if mode.startswith('sdk-') else 'provider_submission'
                for index,row in enumerate(mutated):
                    payload=row['payload']
                    if payload['kind'] not in (('model_request','provider_submission') if mode=='both-call-args' else (kind,)):continue
                    key='messages' if payload['kind']=='model_request' else 'body'
                    data=decode(original_read(payload[key]['path']))
                    changed=canonical(alter(data));path=run_directory/(mode+'-'+str(index)+'.json')
                    path.write_bytes(changed);path.chmod(0o600)
                    payload[key].update(path=str(path),bytes=len(changed),sha256=sha256(changed))
                    if payload['kind']=='model_request':payload['payload_sha256']=sha256(changed)
            previous='0'*64
            for i,row in enumerate(mutated):
                row['sequence']=i;row['previous_digest']=previous
                if row['payload']['kind']=='run_end':row['payload']['final_journal_digest']=previous
                previous=sha256(canonical(row))
            raw=b''.join(canonical(r)+b'\n' for r in mutated)
            scratch=self.private/(mode+'.jsonl');scratch.write_bytes(raw);scratch.chmod(0o600)
            bad=copy.deepcopy(proof);bad['journal'].update(bytes=len(raw),sha256=sha256(raw))
            with patch.object(evidence,'read_private',side_effect=lambda path,*a,**kw:raw if str(path)==proof['journal']['path'] else original_read(path,*a,**kw)),patch.object(protocol,'parse_journal',side_effect=lambda ignored:original_parse(scratch)):
                with self.subTest(mode=mode),self.assertRaises(ValueError):validate(bad,context)

    def test_actual_already_classified_preview_without_mutation(self):
        self.setup_integration('r3-already-classified');self.integration_case='r3-already-classified-final';receipt=self.launch()
        from cs.operator_executor_work import campaign_work
        state=json.loads((self.base/'classified-backend.json').read_text())
        self.assertEqual(state['updates'],0)
        self.assertEqual(state['contact']['dossier'],{'classified_upto':'2026-10-28T01:00:00+00:00'})
        rows=[decode(raw)['payload'] for raw in Path(receipt['executor_proof']['journal']['path']).read_bytes().splitlines()]
        self.assertFalse(any(r['effect'] for r in rows if r['kind']=='tool_end'))
        starts={r['tool_id']:r for r in rows if r['kind']=='tool_start'}
        results=[dict(tool_id=r['tool_id'],argv=starts[r['tool_id']]['argv'],exit_code=r['exit_code'],stdout=Path(r['stdout']['path']).read_bytes()) for r in rows if r['kind']=='tool_end' and r['stdout'] and starts[r['tool_id']]['name']=='run_cs']
        value=decode(next(r['stdout'] for r in results if r['argv']==['campaign','pending']))
        pending=[item for campaign in value['campaigns'] for item in campaign['items']]
        self.assertNotIn('dossier',pending[0]);self.assertNotIn('classified_upto',pending[0])
        outcome=campaign_work(pending,results)[0]
        self.assertEqual(outcome['reason'],'already_classified');self.assertEqual(len(outcome['tool_ids']),3)
        for mode in ('foreign-email','foreign-contact','stale-cutoff','late-preview','synthetic-pending','newer-body'):
            altered=copy.deepcopy(results);items=copy.deepcopy(pending)
            preview=next(r for r in altered if r['argv']==['campaign','mark','fixture-contact'])
            data=decode(preview['stdout'])
            if mode=='foreign-email':data['email']='foreign@fixture.test'
            elif mode=='foreign-contact':data['would_set']['contact_id']='foreign'
            elif mode=='stale-cutoff':data['would_set']['dossier']['classified_upto']='2026-10-27T01:00:00+00:00'
            elif mode=='late-preview':altered.remove(preview);altered.append(preview)
            elif mode=='newer-body':
                body=copy.deepcopy(next(r for r in altered if r['argv'][:2]==['rpc','emails.list_by_thread']))
                data2=decode(body['stdout']);data2['emails'][0]['date']='2026-10-28T02:00:00+00:00'
                body.update(tool_id='newer-body',stdout=canonical(data2));altered.append(body)
            else:
                altered.remove(preview);items[0]['dossier']={'classified_upto':'2026-10-28T01:00:00+00:00'}
            preview['stdout']=canonical(data)
            with self.subTest(mode=mode),self.assertRaises(ValueError):campaign_work(items,altered)

    def test_repaired_mark_actual_body_and_disposition(self):
        self.setup_integration('repair-mark');receipt=self.launch()
        state=json.loads((self.base/'mark-backend.json').read_text())
        self.assertTrue(state['contact']['dossier']['escalated'])
        self.assertEqual(state['contact']['dossier']['classified_upto'],'2026-10-28T00:00:00+00:00')
        from cs.operator_executor_work import campaign_work
        rows=[decode(raw)['payload'] for raw in Path(receipt['executor_proof']['journal']['path']).read_bytes().splitlines()]
        starts={r['tool_id']:r for r in rows if r['kind']=='tool_start'}
        results=[dict(tool_id=r['tool_id'],argv=starts[r['tool_id']]['argv'],exit_code=r['exit_code'],stdout=Path(r['stdout']['path']).read_bytes()) for r in rows if r['kind']=='tool_end' and r['stdout'] and starts[r['tool_id']]['name']=='run_cs']
        pending_value=decode(next(r['stdout'] for r in results if r['argv']==['campaign','pending']))
        pending=[item for campaign in pending_value['campaigns'] for item in campaign['items']]
        self.assertNotIn('thread_id',pending[0])
        self.assertEqual(campaign_work(pending,results)[0]['reason'],'escalated')
        for mode in ('missing-body','unrelated-root','no-change-mark'):
            mutated=copy.deepcopy(results)
            if mode=='missing-body':
                body=next(r for r in mutated if r['argv'][:2]==['rpc','emails.list_by_thread'])
                value=decode(body['stdout']);value['emails'][0].pop('body');body['stdout']=canonical(value)
            elif mode=='unrelated-root':
                read=next(r for r in mutated if r['argv'][:1]==['thread']);read['stdout']=canonical([dict(thread_id='<foreign@fixture.test>')])
            else:
                mark=next(r for r in mutated if r['argv'][:2]==['campaign','mark']);mark['argv']=['campaign','mark','fixture-contact','--commit']
            with self.subTest(mode=mode),self.assertRaises(ValueError):campaign_work(pending,mutated)

    def test_unproved_mark_noop_and_reply_provenance_refuse(self):
        from cs.operator_executor_work import campaign_work
        pending=[dict(action='handle_reply',contact_id='fixture-contact',email='contact@fixture.test')]
        mark=dict(tool_id='mark',argv=['campaign','mark','fixture-contact','--commit'],exit_code=0,stdout=canonical(dict(ok=True,email='contact@fixture.test',result={'updated':True})))
        with self.assertRaisesRegex(ValueError,'campaign_reply_full_body_provenance_missing'):campaign_work(pending,[mark])

    def test_member_hold_actual_source_capture(self):
        self.setup_integration('held-member');self.launch()

    def test_peer_hold_actual_source_capture(self):
        self.setup_integration('held-peer');self.launch()

    def test_malformed_observation_hold_actual_source_capture(self):
        self.setup_integration('held-malformed');self.launch()

    def test_outside_workset_actual_source_capture(self):
        self.setup_integration('outside-workset');self.launch()

    def test_selected_root_actual_draft_disposition(self):
        self.setup_integration('draft-root')
        receipt=self.launch()
        self.assertEqual(receipt['executor_facts']['work_outcomes'][0]['reason'],'draft_prepared')

    def test_selected_root_actual_exact_send_disposition(self):
        self.setup_integration('send-root')
        receipt=self.launch()
        self.assertEqual(receipt['executor_facts']['work_outcomes'][0]['reason'],'draft_sent')

    def test_selected_root_actual_task_disposition_with_dossier_guards(self):
        self.setup_integration('worked-root')
        receipt=self.launch()
        facts=receipt['executor_facts']
        self.assertEqual(facts['selected_root_count'],1)
        self.assertEqual(facts['work_outcomes'][0]['reason'],'task_recorded')
        self.assertEqual(facts['phases']['selected_root_work'],'completed')

    def test_selected_root_legitimate_hold_has_real_exit3_proof(self):
        self.setup_integration('held-root')
        receipt=self.launch()
        facts=receipt['executor_facts']
        self.assertEqual(facts['selected_root_count'],1)
        self.assertEqual(facts['work_outcomes'][0]['outcome'],'held')
        self.assertEqual(facts['phases']['selected_root_work'],'completed')
        self.assertEqual(sum(r['exit_code']==3 for r in facts['tool_proofs']),1)

    def test_nonempty_campaign_actual_committed_action(self):
        self.setup_integration('campaign-reconcile')
        receipt=self.launch()
        self.assertEqual(receipt['executor_facts']['phases']['campaign_work'],'completed')
        self.assertEqual(sum(r['argv']==['campaign','reconcile','fixture-contact','--commit'] for r in receipt['executor_facts']['tool_proofs']),1)

    def test_selector_and_native_default(self):
        with patch.object(sys,'argv',['recovery','unused','--executor','pydantic','Write']),patch.object(recovery,'run',return_value=0) as run:
            self.assertEqual(recovery.main(),0)
            self.assertEqual(run.call_args.kwargs['executor'],'pydantic')
        with patch.object(sys,'argv',['recovery','unused','Write']),patch.object(recovery,'run',return_value=0) as run:
            self.assertEqual(recovery.main(),0)
            self.assertNotIn('executor',run.call_args.kwargs)

# Do not inherit and rerun M1 acceptance tests.
for name in list(vars(ExecutorTests)):
    if name.startswith('test_') and name not in vars(IntegrationTests):setattr(IntegrationTests,name,None)

if __name__=='__main__':unittest.main()
