"""Simulated observational transport; no live provider or effect authority."""
import contextlib
import copy
from collections import Counter
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cs import config, engine_view, gmail_archive, review, rpc, task_assignment as assignment, unanswered
from cs.operator_health import identity
from cs.operator_workset import observe, reserve, WorksetError
from assignment_fixture import normal_projection

A, B, C = '<a@test>', '<b@test>', '<canonical@test>'


class Reuse(unittest.TestCase):
    def selected(self):
        return config.Settings(_env_file=(), engine_owner_uid='owner', accounts='peer:peer', db_path=':memory:')

    def test_original_canonical_reuse_matches_uncached_and_stays_command_local(self):
        selected = self.selected()
        calls = Counter()
        def value(account, key):
            row = normal_projection(account, {'thread_key': key})
            if account.engine_owner_uid == 'owner':
                row.update(authoritative_thread_key=C, component_thread_keys=sorted([A, B, C]), component_scope_present=True)
            row['reply_evidence'] = [{'requested':key, 'actor':account.engine_owner_uid}]
            return row
        def many(account, method, requests, **kwargs):
            self.assertEqual(method, 'tasks.assignment.project')
            for key in requests:
                calls[(account.engine_owner_uid, key)] += 1
            return {key:assignment.rpc_reads.ReadOutcome(value=value(account,key)) for key in requests}
        with patch.object(config, 'load', side_effect=lambda **kw:selected.model_copy(update=kw)), \
             patch.object(assignment.rpc_reads, 'read_many', side_effect=many), \
             patch.object(rpc, 'call_sync', side_effect=lambda account, method, params, **kw:value(account,params['thread_key'])):
            expected = {key:assignment.project(selected,key) for key in (A,B,C)}
            actual = assignment.projections(selected,[A,B,C,A])
            self.assertEqual(actual, expected)
            self.assertEqual(calls, Counter({(uid,key):1 for uid in ('owner','peer') for key in (A,B,C)}))
            assignment.projections(selected,[A,B,C])
            self.assertEqual(calls, Counter({(uid,key):2 for uid in ('owner','peer') for key in (A,B,C)}))
            other = selected.model_copy(update={'engine_ws_url':'ws://different.invalid'})
            assignment.projections(other,[A,B,C])
            self.assertEqual(calls, Counter({(uid,key):3 for uid in ('owner','peer') for key in (A,B,C)}))

    def test_canonical_failures_and_recovery_remain_shared_and_held(self):
        for mode in ('malformed','foreign-company','conflicting-authority','source-unavailable','transport'):
            selected = self.selected()
            calls = Counter()
            def many(account, method, requests, **kwargs):
                results = {}
                for key in requests:
                    uid = account.engine_owner_uid
                    calls[(uid,key)] += 1
                    row = normal_projection(account, {'thread_key':key})
                    if uid == 'owner':
                        row.update(authoritative_thread_key=C, component_thread_keys=sorted([A,B,C]), component_scope_present=True)
                    if uid == 'peer' and key == C:
                        if mode == 'transport':
                            results[key] = assignment.rpc_reads.ReadOutcome(error=TimeoutError('simulated'))
                            continue
                        if mode == 'malformed':row = {}
                        if mode == 'foreign-company':row['space_id'] = 'foreign'
                        if mode == 'conflicting-authority':
                            row.update(authoritative_thread_key=A,component_thread_keys=sorted([A,C]),component_scope_present=True)
                        if mode == 'source-unavailable':
                            row.update(state='unknown',complete=False,hold_auto_reply=True,reason='SOURCE_UNAVAILABLE')
                    results[key] = assignment.rpc_reads.ReadOutcome(value=row)
                return results
            with self.subTest(mode=mode), patch.object(config,'load',side_effect=lambda **kw:selected.model_copy(update=kw)), \
                 patch.object(assignment.rpc_reads,'read_many',side_effect=many):
                result = assignment.projections(selected,[A,B,C])
            self.assertEqual(set(result),{A,B,C})
            self.assertTrue(all(row['hold_auto_reply'] for row in result.values()))
            self.assertEqual(calls[('peer',C)],2 if mode == 'source-unavailable' else 1)

    def test_expired_deadline_preserves_all_roots_without_reads(self):
        with patch.object(assignment.rpc_reads,'read_many') as read:
            rows = assignment.projections(self.selected(),[A,B,C],deadline=time.monotonic()-1)
        read.assert_not_called()
        self.assertEqual(set(rows),{A,B,C})
        self.assertTrue(all(not row['complete'] and row['hold_auto_reply'] for row in rows.values()))


class Union(unittest.TestCase):
    def test_current_roots_first_complete_union_and_original_listed_order(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            selected = config.Settings(_env_file=(),engine_owner_uid='owner',accounts='',
                db_path=str(Path(directory)/'state.db'),log_path=str(Path(directory)/'log'))
            inbound = [{'thread_key':B,'email':'new@test','date':now},
                       {'thread_key':A,'email':'old@test','date':now-timedelta(days=2)}]
            sent = [{'thread_key':B,'to':['new@test'],'date':now+timedelta(seconds=1)}]
            calls=[]
            actual_projections=assignment.projections
            def capture(settings, roots, **kwargs):
                calls.append(list(roots))
                return actual_projections(settings,roots,**kwargs)
            def many(account, method, requests, **kwargs):
                return {key:assignment.rpc_reads.ReadOutcome(value=normal_projection(account,params)) for key,params in requests.items()}
            def gmail(settings, *, observation):
                observation.update(version=1,complete=True,search_complete=True,expected_uids=[],observed_uids=[],uidvalidity='6')
                return []
            def call(settings,method,params,**kwargs):
                if method in ('drafts.list','tasks.list'):return []
                if method=='tasks.assignment.list':
                    return {'version':1,'actor_uid':'owner','space_id':'fixture-space','complete':True,
                            'items':[{'id':root,'space_id':'fixture-space','thread_key':root,'assignee_uid':'human',
                                      'state':'assigned','revision':1,'covered_inbound':[]} for root in (C,B)]}
                raise AssertionError(method)
            with patch.object(review.rpc,'call_sync',side_effect=call), \
                 patch.object(review.campaign,'list_campaigns',return_value=[]), \
                 patch.object(gmail_archive,'inbound_recent',return_value=inbound), \
                 patch.object(gmail_archive,'sent_recent',return_value=sent), \
                 patch.object(engine_view,'classify',return_value=({},None)), \
                 patch.object(engine_view,'settled',return_value=({},None)), \
                 patch.object(assignment,'projections',side_effect=capture), \
                 patch.object(assignment.rpc_reads,'read_many',side_effect=many), \
                 contextlib.redirect_stderr(io.StringIO()):
                result=review._aggregate(selected,deadline=time.monotonic()+60)
            self.assertEqual(calls,[[A,B,C]])
            self.assertEqual([row['thread_key'] for row in result['assignments']],[C,B])
            self.assertTrue(result['drafts_inventory']['complete'])
            self.assertEqual(set(result['_completed_projections']),{A,B,C})

    def test_judgment_allocations_leave_projection_time_and_expired_calls_defer(self):
        for expired in (False,True):
            clock=[100.0]
            deadline=99 if expired else 200
            selected=config.Settings(_env_file=(),engine_owner_uid='owner',accounts='',db_path=':memory:')
            now=datetime.now(timezone.utc)
            def classify(settings,roots,**kwargs):
                self.assertEqual(kwargs['deadline'],125)
                self.assertEqual(kwargs['timeout'],25)
                clock[0]=125
                return {},'simulated classification deadline'
            def settled(settings,roots,**kwargs):
                self.assertEqual(kwargs['timeout'],18.75)
                clock[0]=143.75
                return {},'simulated settlement deadline'
            def project(settings,roots,**kwargs):
                self.assertEqual(kwargs['deadline'],deadline)
                if not expired:self.assertEqual(deadline-clock[0],56.25)
                return {key:assignment._unknown(key,'simulated deferred') for key in roots}
            with patch.object(unanswered.time,'monotonic',side_effect=lambda:clock[0]), \
                 patch.object(gmail_archive,'inbound_recent',return_value=[{'thread_key':A,'email':'customer@test','date':now}]), \
                 patch.object(gmail_archive,'sent_recent',return_value=[]), \
                 patch.object(engine_view,'classify',side_effect=classify) as classified, \
                 patch.object(engine_view,'settled',side_effect=settled) as settlement, \
                 patch.object(assignment,'projections',side_effect=project),contextlib.redirect_stderr(io.StringIO()):
                result=unanswered.sweep(selected,14,deadline=deadline)
            self.assertTrue(result['assignment_incomplete'])
            if expired:
                classified.assert_not_called();settlement.assert_not_called()
            else:
                classified.assert_called_once();settlement.assert_called_once()

    def test_classification_receives_aggregate_deadline_and_owned_group(self):
        selected=config.Settings(_env_file=(),engine_owner_uid='owner')
        limit=time.monotonic()+10
        with patch.object(assignment.rpc_reads,'read_many',return_value={}) as read:
            engine_view.classify(selected,[A],deadline=limit,owned_process_group=123)
        self.assertEqual(read.call_args.kwargs['deadline'],limit)
        self.assertEqual(read.call_args.kwargs['owned_process_group'],123)



class FrozenC32(unittest.TestCase):
    def test_constructed_complete_review_replays_actual_task_and_discovery(self):
        import hashlib
        import subprocess
        frozen = os.environ.get('M2_FROZEN_C32_DIRECTORY')
        if not frozen:
            self.skipTest('requires explicitly supplied immutable C32 evidence; draft reads remain constructed')
        frozen=Path(frozen)
        manifest=json.loads((frozen/'manifest.json').read_text())
        for relative in ('cafe/workset-tasks.json','cafe/discovery.json'):
            expected=next(row['sha256'] for row in manifest['files'] if row['copy']==relative)
            self.assertEqual(hashlib.sha256((frozen/relative).read_bytes()).hexdigest(),expected)
        tasks_record=json.loads((frozen/'cafe/workset-tasks.json').read_text())
        discovery=json.loads((frozen/'cafe/discovery.json').read_text())['discovery']
        target='<179244264351.1832872.14378365271212943800@operator-test.mrcall.ai>'
        fixture=next(row for row in tasks_record['payload'] if row['id']=='500048b9-3628-454f-a127-652ef9875b48')
        self.assertEqual(fixture['thread_key'],target)
        self.assertEqual(fixture['source_root_state'],'resolved')
        code=r'''
import argparse,contextlib,copy,io,json,os,sys,time
from pathlib import Path
from cs import cli,config,review,task_assignment as assignment,operator_workset as workset
from cs.operator_health import identity
base=Path(sys.argv[1]);mode=sys.argv[2]
tasks=json.loads((base/'tasks.json').read_text());original=json.loads((base/'discovery.json').read_text())
target='<179244264351.1832872.14378365271212943800@operator-test.mrcall.ai>'
owner=sys.argv[3]
settings=config.Settings(_env_file=(),slug='c32-semantic-replay',engine_owner_uid=owner,accounts='',db_path=str(base/'state.db'),email_address='production@cafe124.it',system_senders='')
cli.config.load=lambda:settings
review._supervise.__kwdefaults__.update(worker_command=(sys.executable,'-B',str(base/'worker.py')),total_seconds=10,work_seconds=7,cleanup_seconds=2)
out=io.StringIO()
with contextlib.redirect_stdout(out): rc=cli.cmd_review(argparse.Namespace(json=True))
payload=json.loads(out.getvalue());(base/'review-output.json').write_text(json.dumps(payload,indent=2))
if mode=='incomplete-drafts':
 assert rc==3 and not payload['drafts_inventory']['complete'];raise SystemExit(0)
assert rc==0 and payload['drafts_inventory']['complete']
workset.observe(settings,'tasks',tasks)
actual=copy.deepcopy(original)
actual['human_work']=payload['human_work'];actual['assignment_audit']=payload['assignment_audit']
actual['open']=[];actual['resumed']=[]
rows=workset._inventory(actual,{'tasks':tasks,'review':payload},owner)
result=workset.reserve(settings,actual)
if mode in ('all-unknown','unresolved'):
 assert target not in rows[0] and target not in {row['thread_key'] for row in result['selected']}
else:
 assert target in rows[0] and target in {row['thread_key'] for row in result['selected']}
 assert result['held']
(base/'replay-result.json').write_text(json.dumps(result,indent=2))
'''
        bootstrap=r'''
import json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
from cs import review,gmail_archive,engine_view,task_assignment as assignment
base=Path(os.environ['M2_REPLAY_DIRECTORY']);mode=os.environ['M2_REPLAY_MODE']
tasks=json.loads((base/'tasks.json').read_text());original=json.loads((base/'discovery.json').read_text())
target='<179244264351.1832872.14378365271212943800@operator-test.mrcall.ai>'
def gmail(settings,*,observation):
 observation.update(version=1,complete=mode!='incomplete-drafts',search_complete=True,expected_uids=[],observed_uids=[],uidvalidity='12');return []
def rpc(settings,method,params,**kwargs):
 if method=='drafts.list':return []
 if method=='tasks.list':return tasks
 if method=='tasks.assignment.list':
  return {'version':1,'actor_uid':settings.engine_owner_uid,'space_id':'constructed-replay-space','complete':True,'items':[{'id':row['id'],'space_id':'constructed-replay-space','thread_key':row['thread_key'],'revision':1,'state':'assigned','assignee_uid':'simulated-human','covered_inbound':[]} for row in tasks if row.get('thread_key')]}
 raise AssertionError(method)
def many(settings,method,requests,**kwargs):
 outcomes={}
 for key in requests:
  complete=key==target and mode!='all-unknown'
  value={'version':1,'actor_uid':settings.engine_owner_uid,'source_owner_uid':settings.engine_owner_uid,'space_id':'constructed-replay-space','thread_key':key,'complete':complete,'state':'normal' if complete else 'unknown','hold_auto_reply':not complete,'task':None,'events':[],'covered_inbound':[],'current_inbound':[],'covered_message_ids':[],'current_message_ids':[],'reply_evidence':[],'reason':'SIMULATED_TRANSPORT_FOR_C32_SEMANTIC_REPLAY'}
  outcomes[key]=assignment.rpc_reads.ReadOutcome(value=value)
 return outcomes
def inbound(settings,days):
 rows=[]
 for row in original['open']+original['human_work']:
  rows.append({'thread_key':row['thread_key'],'email':row['email'],'date':datetime.fromisoformat(row['last_inbound_date']),'subject':row.get('subject','')})
 stamp=next(row for row in tasks if row.get('thread_key')==target)['last_signal_at']
 rows.append({'thread_key':target,'message_id':target,'email':'support@mrcall.ai','date':datetime.fromisoformat(stamp),'subject':'Constructed headers from retained task/fixture metadata'})
 return rows
review.rpc.call_sync=rpc;review.campaign.list_campaigns=lambda s:[]
gmail_archive.inbound_recent=inbound;gmail_archive.sent_recent=lambda *a:[]
engine_view.classify=lambda *a,**kw:({},'simulated classification unavailable')
engine_view.settled=lambda *a,**kw:({},'simulated settlement unavailable')
assignment.rpc_reads.read_many=many
sys.argv=['cs.review','--worker'];raise SystemExit(review.main())
'''
        for mode in ('resolved','all-unknown','unresolved','incomplete-drafts'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary:
                directory=Path(temporary)
                selected_tasks=copy.deepcopy(tasks_record['payload'])
                if mode=='unresolved':
                    next(row for row in selected_tasks if row['id']==fixture['id'])['source_root_state']='unresolved'
                (directory/'tasks.json').write_text(json.dumps(selected_tasks))
                (directory/'discovery.json').write_text(json.dumps(discovery))
                (directory/'worker.py').write_text(bootstrap)
                scheduled=directory/'scheduled';scheduled.mkdir(mode=0o700)
                context=dict(directory=str(scheduled),nonce='c'*32,supervisor=identity(os.getpid())[0],workset_enabled=True,owner_uid=tasks_record['owner_uid'])
                env=dict(os.environ,HOME=str(directory),PYTHONDONTWRITEBYTECODE='1',CS_OPERATOR_HEALTH_CONTEXT=json.dumps(context),M2_REPLAY_DIRECTORY=str(directory),M2_REPLAY_MODE=mode)
                result=subprocess.run([os.sys.executable,'-B','-c',code,str(directory),mode,tasks_record['owner_uid']],capture_output=True,text=True,env=env,timeout=15)
                artifacts=os.environ.get('M2_TEST_EVIDENCE_DIRECTORY')
                if artifacts:
                    destination=Path(artifacts)/('c32-replay-'+mode);destination.mkdir(parents=True,exist_ok=True)
                    (destination/'stdout').write_text(result.stdout);(destination/'stderr').write_text(result.stderr)
                    for name in ('review-output.json','replay-result.json'):
                        if (directory/name).exists():(destination/name).write_bytes((directory/name).read_bytes())
                self.assertEqual(result.returncode,0,result.stderr)
        print('C32 mixed semantic replay: actual frozen task/discovery; constructed empty complete draft stores and header/projection transport; resolved reserves; unknown/unresolved/incomplete drafts refuse. Historical C32 remains failed.')

if __name__=='__main__':
    unittest.main()
