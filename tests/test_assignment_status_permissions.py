"""Read-only status permissions and dispatch boundaries; no services/models."""
import contextlib,io,json,os,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cs import assignment_cli,operator_workset
ROOT=Path(__file__).resolve().parents[1]
FOUR=('.venv/bin/python -m cs','.venv/bin/cs','python -m cs','cs')
SIX=('.venv/bin/python -m cs','.venv/bin/python3 -m cs','.venv/bin/cs','python -m cs','python3 -m cs','cs')
class StatusPermissions(unittest.TestCase):
 def test_exact_four_read_grants_and_retained_mutation_denies(self):
  d=json.loads((ROOT/'cs/templates/project/.claude/settings.json.j2').read_text())['permissions'];expected={'Bash('+x+' assignment status:*)'for x in FOUR}
  self.assertEqual({r for r in d['allow']if 'assignment'in r},expected)
  for verb in ('campaign send-draft','draft-retire','rpc drafts.discard_exact','rpc drafts.reconcile_external'):
   for prefix in SIX:self.assertIn('Bash('+prefix+' '+verb+':*)',d['deny'])
  self.assertNotIn('Bash(python:*)',d['allow']);self.assertNotIn('Bash(cs assignment:*)',d['allow'])
 def test_status_calls_only_read_projection_after_scope(self):
  settings=SimpleNamespace(engine_owner_uid='owner');args=SimpleNamespace(assignment_action='status',thread_key='<selected@example.test>',json=True);order=[]
  with patch.dict(os.environ,{'CS_OPERATOR_HEALTH_CONTEXT':'fixture'}),patch.object(assignment_cli.config,'load',return_value=settings),patch.object(operator_workset,'require_root',side_effect=lambda s,r:order.append('scope')),patch.object(assignment_cli.authority,'project',side_effect=lambda s,r:order.append('read')or{'complete':True}),patch.object(assignment_cli.rpc,'call_sync',side_effect=AssertionError('mutation RPC')),patch.object(assignment_cli.authority,'commit',side_effect=AssertionError('commit')),contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(assignment_cli.run(args),0);self.assertEqual(order,['scope','read'])
 def test_scope_refusal_precedes_any_upstream(self):
  settings=SimpleNamespace(engine_owner_uid='owner');args=SimpleNamespace(assignment_action='status',thread_key='<foreign@example.test>',json=True)
  with patch.dict(os.environ,{'CS_OPERATOR_HEALTH_CONTEXT':'fixture'}),patch.object(assignment_cli.config,'load',return_value=settings),patch.object(operator_workset,'require_root',side_effect=operator_workset.WorksetError('foreign')),patch.object(assignment_cli.authority,'project',side_effect=AssertionError('upstream')),contextlib.redirect_stderr(io.StringIO()):self.assertEqual(assignment_cli.run(args),3)
if __name__=='__main__':unittest.main()
