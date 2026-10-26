"""Assignment lane summaries distinguish shared time exhaustion from request expiry."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cs import observability_causal as causal, task_assignment, rpc_reads
from cs.observability import EventStore
from cs.monitor_config import Component, MonitorConfig
import test_rpc_reads as rpc_cases
from test_task_assignment import settings, projection, KEY


class AssignmentBudget(unittest.IsolatedAsyncioTestCase):
    scheduled_fixture = rpc_cases.Transport.scheduled_fixture

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stores = {}
        def selected_store(selected):
            uid = selected.engine_owner_uid
            return self.stores.setdefault(uid, EventStore(self.root / uid, uid))
        self.patcher = patch('cs.observability_producers.store_for', side_effect=selected_store)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def summaries(self):
        result = {}
        for uid, store in self.stores.items():
            events = store.events(limit=200)['events']
            summaries = [event for event in events if event.get('method') == 'tasks.assignment.budget']
            self.assertEqual(len(summaries), 1)
            value = summaries[0]['causal']
            self.assertIsNotNone(value)
            causal.validate(value)
            self.assertEqual(value['check'], 'assignment_time_budget')
            self.assertNotIn('@example.test', json.dumps(events))
            self.assertNotIn('fixture.', json.dumps(events))
            result[uid] = (summaries[0], events)
            if retained := os.environ.get('ASSIGNMENT_BUDGET_EVIDENCE_DIR'):
                directory = Path(retained); directory.mkdir(parents=True, exist_ok=True)
                (directory / (self._testMethodName + '-' + uid + '.json')).write_text(json.dumps({'events': events}, indent=2))
        return result

    async def test_cumulative_healthy_serial_reads_exhaust_shared_allowance(self):
        result, stats, keys = await self.scheduled_fixture(count=8, budget=0.9)
        self.assertEqual(list(result), keys)
        self.assertEqual(result[keys[0]]['state'], 'normal')
        self.assertTrue(any(result[key]['hold_auto_reply'] for key in keys))
        for uid, (event, events) in self.summaries().items():
            value = event['causal']; facts = value['facts']
            self.assertEqual(value['cause'], 'shared_deadline_exhausted')
            sent = sum(actor == uid for actor,key in stats['dispatch'])
            received = sum(actor == uid for actor,key in stats['complete'])
            self.assertEqual([facts[name] for name in ('expected_roots','scheduler_dispatched','returned_values','read_timeouts','scheduler_deferred')], [8,sent,received,1,8-sent])
            self.assertEqual(sent, received+1)
            self.assertEqual((facts['global_concurrency'], facts['account_concurrency']), (4,1))
            self.assertEqual(facts['effective_entry_ms'], 900)
            self.assertGreater(facts['serial_read_ms'], 650)
            self.assertLess(facts['remaining_ms'], 15)
            self.assertTrue(facts['shared_deadline_selected'])
            timeouts = [e for e in events if e.get('causal',{}).get('check') == 'assignment_read' and e['causal']['cause'] == 'shared_deadline' and e.get('error_class') == 'TimeoutError']
            self.assertEqual(value['refs']['cause_event_id'], timeouts[0]['event_id'])
            deferred = [e for e in events if e.get('causal',{}).get('cause') == 'account_timeout_deferred']
            self.assertTrue(all(e['causal']['refs']['cause_event_id'] == timeouts[0]['event_id'] for e in deferred))
            self.assertEqual(len([pair for pair in stats['dispatch'] if pair[0] == uid]), facts['scheduler_dispatched'])

    async def test_individual_request_timeout_has_ample_shared_time(self):
        result, stats, keys = await self.scheduled_fixture(count=6, stalled=True, budget=4)
        for uid, (event, events) in self.summaries().items():
            value = event['causal']; facts = value['facts']
            if uid == 'peer':
                self.assertEqual(value['cause'], 'request_timeout')
                self.assertTrue(facts['request_timeout_selected'])
                self.assertGreater(facts['remaining_ms'], 3000)
                self.assertEqual([facts[name] for name in ('scheduler_dispatched','returned_values','read_timeouts','scheduler_deferred')], [2,1,1,4])
                self.assertIsNotNone(value['refs']['cause_event_id'])
            else:
                self.assertEqual(value['cause'], 'complete')
                self.assertEqual(event['level'], 'DEBUG')
                self.assertEqual(facts['scheduler_dispatched'], len(keys))
                self.assertEqual(facts['read_timeouts'], 0)

    async def test_read_batch_expiry_is_distinct_with_ample_shared_time(self):
        result, stats, keys = await self.scheduled_fixture(count=3,budget=2,read_batch=0.08)
        self.assertTrue(all(row['hold_auto_reply'] for row in result.values()))
        for event, events in self.summaries().values():
            value = event['causal']; facts = value['facts']
            self.assertEqual(value['cause'],'batch_deadline')
            self.assertTrue(facts['batch_deadline_selected'])
            self.assertFalse(facts['shared_deadline_selected'])
            self.assertGreater(facts['remaining_ms'],1500)
            self.assertEqual([facts[key] for key in ('scheduler_dispatched','returned_values','read_timeouts','scheduler_deferred')],[1,0,1,2])
            first = next(e for e in events if e.get('causal',{}).get('check')=='assignment_read')
            self.assertEqual(value['refs']['cause_event_id'],first['event_id'])

    async def test_held_and_zero_work_are_debug_and_sink_failure_preserves_result(self):
        result, _, _ = await self.scheduled_fixture(count=1, response=lambda uid,key,attempt,value: value | {
            'state':'needs-assignment','hold_auto_reply':True,'complete':False,'reason':'NEEDS_HUMAN_VERIFICATION'})
        self.assertTrue(all(row['hold_auto_reply'] for row in result.values()))
        self.assertTrue(all(e['level'] == 'DEBUG' for e,_ in self.summaries().values()))
        self.stores.clear()
        self.root = self.root / 'zero'
        with patch.object(rpc_reads,'read_many') as read:
            self.assertEqual(task_assignment.projections(settings(), []), {})
        read.assert_not_called()
        event = self.summaries()['operator'][0]
        self.assertEqual((event['causal']['cause'],event['level']),('no_work','DEBUG'))
        with patch('cs.observability_producers.emit', side_effect=OSError('PRIVATE_CANARY')):
            result, stats, keys = await self.scheduled_fixture(count=2)
        self.assertTrue(all(row['state']=='normal' for row in result.values()))
        self.assertEqual(len(stats['dispatch']),4)

    async def test_effective_entry_allowance_and_unattempted_deadline(self):
        with patch.object(rpc_reads, 'CLOSE_SECONDS', 0.001), patch.object(rpc_reads, 'read_many', return_value={KEY: rpc_reads.ReadOutcome(value=projection())}) as read:
            result = task_assignment.projections(settings(), [KEY], deadline=time.monotonic()+1.234)
        self.assertEqual(result[KEY]['state'], 'normal')
        self.assertEqual(read.call_count,1)
        value = self.summaries()['operator'][0]['causal']
        self.assertGreater(value['facts']['effective_entry_ms'],1200)
        self.assertLessEqual(value['facts']['effective_entry_ms'],1234)
        self.stores.clear(); self.root = self.root/'expired'
        with patch.object(rpc_reads, 'read_many') as read:
            result = task_assignment.projections(settings(), [KEY], deadline=time.monotonic()-1)
        read.assert_not_called()
        event = self.summaries()['operator'][0]
        self.assertEqual(event['causal']['cause'],'deadline_capacity_deferred')
        self.assertIsNone(event['causal']['refs']['cause_event_id'])
        self.assertEqual([event['causal']['facts'][key] for key in ('scheduler_dispatched','returned_values','read_timeouts','scheduler_deferred')],[0,0,0,1])

    async def test_global_reservation_deferral_references_first_observed_timeout(self):
        from cs import config
        selected = settings().model_copy(update={'accounts':'p1:p1,p2:p2,p3:p3,p4:p4'})
        diagnostic = rpc_reads.diagnostic('request_timeout',time.monotonic(),0.1,10,bound_origin='request_timeout')
        def many(account,method,requests,**kwargs):
            return {key:rpc_reads.ReadOutcome(error=TimeoutError('PRIVATE_CANARY'),diagnostic=diagnostic) for key in requests}
        with patch.object(config,'load',side_effect=lambda **kw:selected.model_copy(update=kw)), patch.object(rpc_reads,'read_many',side_effect=many) as read:
            result=task_assignment.projections(selected,[KEY,'<later@example.test>'])
        self.assertEqual(read.call_count,4)
        self.assertTrue(all(row['hold_auto_reply'] for row in result.values()))
        summaries=self.summaries()
        event=summaries['p4'][0]; facts=event['causal']['facts']
        self.assertEqual(event['causal']['cause'],'capacity_deferred')
        self.assertEqual([facts[key] for key in ('scheduler_dispatched','returned_values','read_timeouts','scheduler_deferred')],[0,0,0,2])
        first=next(e for store in self.stores.values() for e in store.events(limit=200)['events']
                   if e['event_id']==event['causal']['refs']['cause_event_id'])
        self.assertEqual(first['causal']['cause'],'request_timeout')

    async def test_real_cli_collector_problem_inbox_retains_summary(self):
        await self.scheduled_fixture(count=6,budget=0.65)
        summaries = self.summaries()
        source = self.stores['operator']
        with tempfile.TemporaryDirectory() as home:
            manifest = Path(home)/'manifest.toml'
            manifest.write_text('[company]\nslug="budget"\n[engine]\nowner_uid="operator"\n')
            from cs.observability import owner_root
            import shutil
            target = owner_root(Path(home)/'.budget-cs','operator')
            target.parent.mkdir(parents=True,mode=0o700)
            shutil.copytree(source.root,target)
            env={k:v for k,v in os.environ.items() if not k.startswith(('CS_','ENGINE_','EMAIL_'))}
            env.update(HOME=home,CS_MANIFEST=str(manifest),CS_ENGINE_OWNER_UID='operator')
            command=[sys.executable,'-m','cs','logs','events','--local','--json','--limit','200']
            process=await asyncio.to_thread(subprocess.run,command,env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(process.returncode,0,process.stderr)
            value=summaries['operator'][0]['causal']
            self.assertIn(value,[e.get('causal') for e in json.loads(process.stdout)['local']['events']])
            cfg=MonitorConfig(mode='filesystem',monitor_id='a'*32,owner_uid='operator',state_dir=str(Path(home)/'monitor'),
                              expected_start_utc=int(time.time()),components=[Component(id='operator',kind='kernel',local_root=str(target))])
            path=Path(home)/'monitor.json'; path.write_text(cfg.model_dump_json());path.chmod(0o600)
            done=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','cs','monitor','once','--config',str(path)],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(done.returncode,1,done.stdout+done.stderr)
            inbox=json.loads((Path(home)/'monitor'/'problems.json').read_text())
            self.assertTrue(any(p['evidence'].get('causal')==value for p in inbox['problems']))
            self.assertNotIn('@example.test',json.dumps(inbox))
            if retained := os.environ.get('ASSIGNMENT_BUDGET_EVIDENCE_DIR'):
                (Path(retained)/'actual-cli.json').write_text(process.stdout)
                (Path(retained)/'actual-inbox.json').write_text(json.dumps(inbox,indent=2))


if __name__=='__main__':
    unittest.main()
