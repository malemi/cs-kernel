"""Real deterministic supervisor decisions through ordinary diagnostic consumers."""
import ast
import copy
import contextlib
import uuid
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cs import operator_recovery as recovery, operator_health as health
from cs import observability_causal as causal
from cs.config import Settings
from cs.monitor_config import Component, MonitorConfig
from cs.observability import context, store_for, safe_metadata
from cs.monitor_details import safe_detail
from cs.observability_store import _validate_event


class CausalTests(unittest.TestCase):
    def test_real_supervisor_cli_collector(self):
        source = ast.parse(Path('tests/test_operator_health.py').read_text())
        fixture = next(ast.literal_eval(node.value) for node in source.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'FAKE' for target in node.targets))
        fixture = fixture.replace("    if case=='send_success':", "    if case=='counts': use('.venv/bin/python -m cs unanswered --days 14 --json --all-buckets',output,'discovery2',child.returncode!=0)\n    if case=='send_success':")
        async def intake(settings):
            return None
        retained = os.environ.get('CAUSAL_EVIDENCE_DIR')
        if retained:
            Path(retained).mkdir(parents=True, mode=0o700, exist_ok=True)
        manager = contextlib.nullcontext(retained) if retained else tempfile.TemporaryDirectory()
        with manager as directory:
            root = Path(directory)
            binary = root / 'native'
            binary.write_text(fixture)
            binary.chmod(0o700)
            manifest = root / 'manifest.toml'
            manifest.write_text('[company]\nslug="causal"\n[engine]\nowner_uid="owner"\n')
            env = {**os.environ, 'HOME': directory, 'HEALTH_PYTHON': sys.executable, 'CS_MANIFEST': str(manifest), 'CS_ENGINE_OWNER_UID': 'owner', 'PYTHONPATH': str(Path.cwd()), 'CS_HEADLESS_SEND': '', 'CS_OPERATOR_HEADLESS': ''}
            with patch.dict(os.environ, env), patch.object(recovery.config, 'load', return_value=Settings(slug='causal', engine_owner_uid='owner')), patch.object(recovery, '_mail_intake', intake), patch('smtplib.SMTP', side_effect=AssertionError('no SMTP')):
                settings = recovery.config.load()
                store = store_for(settings)
                for case, check in [('missing_phase', 'required_phase_presence'), ('counts', 'discovery_tool_cardinality')]:
                    os.environ['HEALTH_CASE'] = case
                    self.assertEqual(recovery.run(str(binary), ['Write']), 1)
                    events = store.events(limit=200)['events']
                    terminal = [e for e in events if e['stage'] == 'launch' and e['status'] == 'failed'][-1]
                    value = terminal['causal']
                    self.assertEqual(value['check'], check)
                    self.assertEqual(value['refs']['attempt_id'], terminal['attempt_id'])
                    self.assertTrue(any(e['event_id'] == value['refs']['cause_event_id'] and e['stage'] == 'context' for e in events))
                    self.assertTrue(any(e['event_id'] == value['refs']['child_event_id'] and e['exit_code'] == 0 for e in events))
                    trace = subprocess.run([sys.executable, '-m', 'cs', 'logs', 'trace', '--trace-id', terminal['trace_id'], '--local', '--json'], capture_output=True, text=True, env=env)
                    self.assertEqual(trace.returncode, 0, trace.stderr)
                    self.assertIn(value, [e.get('causal') for e in json.loads(trace.stdout)['local']['events']])
                    if retained:
                        corpus = root/'corpus'; corpus.mkdir(mode=0o700, exist_ok=True)
                        keyroot = root/'private-truth'; keyroot.mkdir(mode=0o700, exist_ok=True)
                        identity = uuid.uuid4().hex
                        evidence = corpus/(identity+'.json')
                        evidence.write_text(trace.stdout); evidence.chmod(0o600)
                        key = keyroot/(identity+'.json')
                        key.write_text(json.dumps({'case':case,'actual_check':value['check'],'event_id':terminal['event_id'],'argv':trace.args,'exit':trace.returncode}))
                        key.chmod(0o600)
                    with context({'run_id': terminal['run_id']}):
                        store.emit('launch', 'result', reason='none', exit_code=1)
                    cfg = MonitorConfig(mode='filesystem', clone_label='sample', scan_seconds=600, monitor_id='a'*32, owner_uid='owner', state_dir=str(root/'monitor'), expected_start_utc=int(time.time()), components=[Component(id='operator',kind='kernel',local_root=str(store.root))])
                    cfgpath = root/'monitor.json'
                    cfgpath.write_text(cfg.model_dump_json()); cfgpath.chmod(0o600)
                    command = [sys.executable,'-m','cs','monitor','once','--config',str(cfgpath)]
                    done = subprocess.run(command,capture_output=True,text=True,env=env)
                    self.assertEqual(done.returncode,1,done.stderr)
                    inbox = json.loads((root/'monitor'/'problems.json').read_text())
                    self.assertTrue(any(p['evidence'].get('causal') == value for p in inbox['problems']))
                    repeat = subprocess.run(command,capture_output=True,text=True,env=env)
                    self.assertEqual(repeat.returncode,1,repeat.stderr)
                    self.assertTrue(any(p['evidence'].get('causal') == value for p in json.loads((root/'monitor'/'problems.json').read_text())['problems']))

                os.environ['HEALTH_CASE'] = 'late_chat'
                self.assertEqual(recovery.run(str(binary), ['Write']), 0)
                accepted = [e for e in store.events(limit=200)['events'] if e.get('method') == 'operator.tick'][-1]
                self.assertEqual(accepted['causal']['cause'], 'run_verified')
                self.assertEqual(accepted['causal']['outcome'], 'accepted')
                done = subprocess.run(command,capture_output=True,text=True,env=env)
                self.assertEqual(done.returncode,0,done.stdout+done.stderr)
                self.assertFalse(any(p['evidence'].get('causal') for p in json.loads((root/'monitor'/'problems.json').read_text())['problems']))
                os.environ['HEALTH_CASE'] = 'missing_phase'
                self.assertEqual(recovery.run(str(binary), ['Write']), 1)
                os.environ['HEALTH_CASE'] = 'late_chat'
                with patch('cs.operational_inbox.record_notice', side_effect=OSError('PRIVATE_CANARY')):
                    self.assertEqual(recovery.run(str(binary), ['Write']), 1)
                final = [e for e in store.events(limit=200)['events'] if e.get('method') == 'operator.tick'][-1]
                self.assertEqual(final['causal']['cause'], 'record_write_failed')
                self.assertIsNotNone(final['causal']['refs']['child_event_id'])
                self.assertTrue(recovery._read_state(settings)['pending'])
                self.assertNotIn('PRIVATE_CANARY', json.dumps(store.events(limit=200)))
                with patch('cs.operational_inbox.record_notice', side_effect=OSError('PENDING_PRIVATE_CANARY')):
                    self.assertEqual(recovery.run(str(binary), ['Write']), 1)
                events = store.events(limit=200)['events']
                pending_final = [e for e in events if e.get('method') == 'operator.tick'][-1]
                value = pending_final['causal']
                self.assertEqual(value['cause'], 'record_write_failed')
                self.assertEqual(value['refs']['attempt_id'], pending_final['attempt_id'])
                child = next(e for e in events if e['event_id'] == value['refs']['child_event_id'])
                origin = next(e for e in events if e['event_id'] == value['refs']['cause_event_id'])
                self.assertEqual(child['exit_code'], 0)
                self.assertEqual(origin['method'], 'operator.notice')
                self.assertEqual(origin['error_class'], 'OSError')
                self.assertIsNone(origin['causal']['refs']['child_event_id'])
                self.assertEqual(origin['run_id'], pending_final['run_id'])
                self.assertTrue(recovery._read_state(settings)['pending'])
                trace = subprocess.run([sys.executable, '-m', 'cs', 'logs', 'trace', '--trace-id', pending_final['trace_id'], '--local', '--json'], capture_output=True, text=True, env=env)
                self.assertEqual(trace.returncode, 0, trace.stderr)
                self.assertIn(value, [e.get('causal') for e in json.loads(trace.stdout)['local']['events']])
                self.assertNotIn('PENDING_PRIVATE_CANARY', trace.stdout)
                collected = subprocess.run(command, capture_output=True, text=True, env=env)
                self.assertEqual(collected.returncode, 1, collected.stderr)
                self.assertTrue(any(p['evidence'].get('causal') == value for p in json.loads((root/'monitor'/'problems.json').read_text())['problems']))


    def test_read_collisions_validation_and_context(self):
        def use(tool='one'):
            return {'session_id':'opaque-session','message':{'content':[{'type':'tool_use','id':tool,'name':'Bash','input':{'command':'cs tasks --json PRIVATE_CANARY'}}]}}
        def result(error=False):
            return {'message':{'content':[{'type':'tool_result','tool_use_id':'one','is_error':error}]}}
        for events, expected in [([use(),use()], 'read_tool_id_duplicate'),([use(),result(),result()], 'read_result_duplicate'),([use(),result(True)],'read_error_unproved'),([use()], 'read_result_missing')]:
            with causal.scope(), context({'run_id':'a'*32,'attempt_id':'b'*32}):
                self.assertTrue(health.native_read_failed(events))
                value = causal.selected()
                self.assertEqual(value['cause'],expected)
                self.assertNotIn('PRIVATE_CANARY',json.dumps(value))
                self.assertEqual(safe_metadata({'causal':value})['causal'],value)
                self.assertEqual(safe_detail({'causal':value})['causal'],value)
                for key, invalid in [('version',2),('layer',[]),('check',{}),('phase',[]),('missing_refs',[[]])]:
                    changed = copy.deepcopy(value); changed[key]=invalid
                    with self.assertRaises(ValueError): causal.validate(changed)
            self.assertIsNone(causal.selected())


if __name__ == '__main__':
    unittest.main()
