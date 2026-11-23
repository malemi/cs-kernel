"""Local simulated transport through the production review worker and CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


BOOTSTRAP = r"""
import json,os,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from cs import review,gmail_archive,engine_view,task_assignment as assignment
from assignment_fixture import normal_projection
now=datetime.now(timezone.utc)
def gmail(settings,*,observation):
 observation.update(version=1,complete=True,search_complete=True,expected_uids=['17'],observed_uids=['17'],uidvalidity='6')
 return [{'uid':'17','uidvalidity':'6','thread_key':'<draft@test>','body':'local fixture','body_complete':True}]
def rpc(settings,method,params,**kw):
 if method=='drafts.list':return [{'id':'draft','mailbox_id':'box','owner_id':settings.email_address,'status':'draft','thread_id':'<draft@test>','body':'local fixture'}]
 if method=='tasks.list':return [{'id':'task','thread_key':'<task@test>'},{'id':'overlap','thread_key':'<listed@test>'}]
 raise AssertionError(method)
def listing(*args,**kwargs):return {'items':[{'thread_key':'<listed@test>'}]}
def projections(settings,roots,**kwargs):
 Path(os.environ['COVERAGE_CALLS']).write_text(json.dumps(list(roots)))
 return {root:(assignment._unknown(root,'simulated timeout') if root=='<task@test>' else normal_projection(settings,{'thread_key':root})) for root in roots if root!='<draft@test>'}
review.rpc.call_sync=rpc
review.draft_state.reconcile=lambda *a,**kw:([],[])
review.draft_state.inventory_proof=lambda *a,**kw:{'version':1,'complete':True}
review.campaign.list_campaigns=lambda s:[]
assignment.listing=listing
assignment.projections=projections
gmail_archive.inbound_recent=lambda *a:[{'thread_key':'<settled@test>','email':'customer@test','date':now}]
gmail_archive.sent_recent=lambda *a:[{'thread_key':'<settled@test>','to':['customer@test'],'date':now+timedelta(seconds=1)}]
engine_view.classify=lambda *a,**kw:({},None)
engine_view.settled=lambda *a,**kw:({},None)
sys.argv=['cs.review','--worker'];raise SystemExit(review.main())
"""
RUNNER = r"""
import argparse,sys
from cs import cli,review,config
settings=config.Settings(_env_file=(),engine_owner_uid='coverage-owner',accounts='',db_path=sys.argv[2]+'/state.db',log_path=sys.argv[2]+'/log')
cli.config.load=lambda:settings
review._supervise.__kwdefaults__.update(worker_command=(sys.executable,'-B',sys.argv[1]),total_seconds=10,work_seconds=7,cleanup_seconds=2)
raise SystemExit(cli.cmd_review(argparse.Namespace(json=True)))
"""

class Coverage(unittest.TestCase):
 def test_production_worker_cli_success_preserves_union_and_settled_observations(self):
  with tempfile.TemporaryDirectory() as name:
   directory=Path(name);worker=directory/'worker.py';worker.write_text(BOOTSTRAP)
   env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',COVERAGE_CALLS=str(directory/'calls.json'),PYTHONPATH=os.pathsep.join([str(Path.cwd()),str(Path.cwd()/'tests')]))
   result=subprocess.run([sys.executable,'-B','-c',RUNNER,str(worker),name],env=env,capture_output=True,text=True,timeout=12)
   artifacts=os.environ.get('COVERAGE_TEST_EVIDENCE_DIRECTORY')
   if artifacts:
    destination=Path(artifacts);destination.mkdir(parents=True,exist_ok=True)
    (destination/'production-cli.stdout.json').write_text(result.stdout)
    (destination/'production-cli.stderr.log').write_text(result.stderr)
    (destination/'production-cli.exit').write_text(str(result.returncode))
   self.assertEqual(result.returncode,0,result.stderr)
   payload=json.loads(result.stdout)
   self.assertEqual(payload['review_coverage']['aggregation'],'complete')
   calls=json.loads((directory/'calls.json').read_text())
   self.assertEqual(calls,['<settled@test>','<draft@test>','<task@test>','<listed@test>'])
   coverage=payload['assignment_coverage']
   self.assertEqual(coverage['requested_order'],calls)
   rows={row['thread_key']:row for row in coverage['roots']}
   self.assertEqual(len(rows),4)
   self.assertEqual(rows['<listed@test>']['sources'],['task','company_assignment'])
   self.assertEqual(rows['<draft@test>']['sources'],['mailbox_draft'])
   self.assertEqual(rows['<settled@test>']['sources'],['inbound'])
   for key in ('<draft@test>','<task@test>'):
    self.assertFalse(rows[key]['projection']['complete'])
    self.assertTrue(rows[key]['projection']['hold_auto_reply'])
   self.assertTrue(rows['<settled@test>']['projection']['complete'])
   self.assertFalse(rows['<settled@test>']['projection']['hold_auto_reply'])
   self.assertFalse(payload['human_work'])
   self.assertEqual([row['thread_key'] for row in payload['assignments']],['<listed@test>'])
   self.assertNotIn('_completed_projections',payload)
   print('Production worker/CLI success: exact union once; task/draft missing mailbox roots held; settled NORMAL observable outside human_work; source categories retained.')

if __name__=='__main__':unittest.main()
