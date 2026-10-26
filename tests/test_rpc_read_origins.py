"""Observed timeout boundaries survive real transport and isolated processes."""
import asyncio
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cs import rpc_reads
from test_rpc_reads import TOKEN, settings
import test_rpc_reads as transport_fixture

class Origins(unittest.IsolatedAsyncioTestCase):
    run_batch = transport_fixture.Transport.run_batch
    async def test_request_and_batch_expiry_are_distinct(self):
        for request, batch, expected in ((.04, 2, 'request_timeout'), (2, .04, 'batch_deadline')):
            rows, _, _, _ = await self.run_batch(['a'], {'a': 5}, request_timeout=request, batch_timeout=batch)
            self.assertIsInstance(rows['a'].error, TimeoutError)
            self.assertEqual(rows['a'].diagnostic['cause'], expected)
            self.assertGreaterEqual(rows['a'].diagnostic['elapsed_ms'], 0)

    async def test_connection_and_success_are_not_deadline_failures(self):
        rows,_,_,_=await self.run_batch(['a'],{'a':.001},disconnected=True)
        self.assertIsNotNone(rows['a'].error)
        self.assertIn(rows['a'].diagnostic['cause'],{'connection_failure','transport_unavailable'})
        rows,_,_,_=await self.run_batch(['a'],{'a':.001})
        self.assertIsNone(rows['a'].error)
        self.assertIsNone(rows['a'].diagnostic)

    async def test_real_isolated_worker_expiry_has_parent_boundary(self):
        command=(sys.executable,'-c','import sys,time;sys.stdin.read();time.sleep(9)')
        with patch.object(rpc_reads,'READ_COMMAND',command), patch.object(rpc_reads,'CLOSE_SECONDS',.01):
            row=(await asyncio.to_thread(rpc_reads.read_many,settings(),'tasks.assignment.project',{'a':{}},deadline=time.monotonic()+.3))['a']
        self.assertIsInstance(row.error,TimeoutError)
        self.assertEqual(row.diagnostic['cause'],'worker_timeout')
        self.assertEqual(row.diagnostic['bound_origin'],'shared_deadline')


class IsolatedOrigins(unittest.IsolatedAsyncioTestCase):
    async def test_real_child_request_and_shared_bound_round_trip(self):
        import websockets
        async def handler(ws):
            try:
                async for raw in ws:
                    await asyncio.sleep(4)
            except websockets.ConnectionClosed:
                pass
        async with websockets.serve(handler,'127.0.0.1',0) as server:
            selected=settings().model_copy(update={'engine_ws_url':f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'})
            for request,batch,seconds,expected in ((.05,2,3,'request_timeout'),(3,3,2.5,'shared_deadline')):
                with patch.object(rpc_reads,'CLOSE_SECONDS',.1):
                    row=(await asyncio.to_thread(rpc_reads.read_many,selected,'tasks.assignment.project',{'a':{}},request_timeout=request,batch_timeout=batch,deadline=time.monotonic()+seconds,token_cache={'operator':TOKEN}))['a']
                self.assertIsInstance(row.error,TimeoutError)
                self.assertEqual(row.diagnostic['cause'],expected)

    async def test_actual_caller_cli_collector_retains_timeout_and_derived_deferral(self):
        import os, tempfile, subprocess, hashlib
        import websockets
        from cs import task_assignment
        from cs.observability import store_for
        from cs.monitor_config import MonitorConfig,Component
        async def handler(ws):
            try:
                async for raw in ws:
                    await asyncio.sleep(4)
            except websockets.ConnectionClosed:
                pass
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'manifest.toml';manifest.write_text('[company]\nslug="origin"\n[engine]\nowner_uid="operator"\n')
            env={**os.environ,'HOME':tmp,'CS_MANIFEST':str(manifest),'CS_ENGINE_OWNER_UID':'operator','PYTHONPATH':os.pathsep.join(str(Path.cwd()) if not x else x for x in sys.path)}
            async with websockets.serve(handler,'127.0.0.1',0) as server:
                selected=settings().model_copy(update={'slug':'origin','engine_ws_url':f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}','db_path':str(root/'state.db')})
                command=(sys.executable,'-c','from cs import auth,rpc_reads;auth.get_id_token=lambda s:'+repr(TOKEN)+';rpc_reads._isolated_main()')
                with patch.dict(os.environ,env),patch.object(rpc_reads,'READ_COMMAND',command),patch.object(rpc_reads,'ASSIGNMENT_REQUEST_SECONDS',.05),patch.object(rpc_reads,'CLOSE_SECONDS',.02):
                    result=await asyncio.to_thread(task_assignment.projections,selected,['<a@example.test>','<b@example.test>'])
                    store=store_for(selected);events=store.events(limit=200)['events']
                    self.assertTrue(all(x['state']=='unknown' and x['hold_auto_reply'] for x in result.values()))
                    causes=[x for x in events if x.get('causal',{}).get('check')=='assignment_read']
                    self.assertEqual([x['causal']['cause'] for x in causes],['request_timeout','account_timeout_deferred'],repr((result,events)))
                    self.assertEqual(causes[1]['causal']['refs']['cause_event_id'],causes[0]['event_id'])
                    self.assertTrue(causes[0]['causal']['facts']['request_timeout_selected'])
                    self.assertFalse(causes[0]['causal']['facts']['shared_deadline_selected'])
                    trace=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','cs','logs','trace','--trace-id',causes[0]['trace_id'],'--local','--json'],capture_output=True,text=True,env=env)
                    self.assertEqual(trace.returncode,0,trace.stderr)
                    self.assertIn('request_timeout',trace.stdout)
                    cfg=MonitorConfig(mode='filesystem',clone_label='origin',scan_seconds=600,monitor_id='a'*32,owner_uid='operator',state_dir=str(root/'monitor'),expected_start_utc=int(time.time()),components=[Component(id='operator',kind='kernel',local_root=str(store.root))])
                    cfgpath=root/'monitor.json';cfgpath.write_text(cfg.model_dump_json());cfgpath.chmod(0o600)
                    done=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','cs','monitor','once','--config',str(cfgpath)],capture_output=True,text=True,env=env)
                    self.assertEqual(done.returncode,1,done.stderr)
                    inbox=(root/'monitor/problems.json').read_text();self.assertIn('request_timeout',inbox);self.assertIn('account_timeout_deferred',inbox)
                    self.assertNotIn('<a@example.test>',inbox);self.assertNotIn(TOKEN,inbox)
                    self.assertIn('elapsed_ms',inbox)
                    retained=os.environ.get('TIMEOUT_ORIGIN_CORPUS')
                    if retained:
                        destination=Path(retained);destination.mkdir(parents=True,exist_ok=True,mode=0o700)
                        target=destination/'ordinary-inbox.json';target.write_text(inbox);target.chmod(0o600)
                        target=destination/'ordinary-trace.json';target.write_text(trace.stdout);target.chmod(0o600)
                    self.assertEqual(causes[0]['root_id'],hashlib.sha256(b'<a@example.test>').hexdigest())

class Validation(unittest.TestCase):
    def test_deferral_links_reservation_timeout_after_nonblocking_failure(self):
        import os,tempfile
        from cs import task_assignment
        from cs.observability import store_for
        from cs.observability_causal import scope
        failures=iter([
            rpc_reads.ReadOutcome(error=ConnectionError('PRIVATE'),diagnostic=rpc_reads.diagnostic('connection_failure',time.monotonic(),1,50,bound_origin='batch_deadline')),
            rpc_reads.ReadOutcome(error=TimeoutError('PRIVATE'),diagnostic=rpc_reads.diagnostic('request_timeout',time.monotonic(),1,50)),
        ])
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'HOME':directory}),scope():
            selected=settings()
            def read(account,method,rows,**kwargs):return {key:next(failures) for key in rows}
            with patch.object(rpc_reads,'read_many',side_effect=read) as mocked:
                result=task_assignment.projections(selected,['<a@example.test>','<b@example.test>','<c@example.test>'])
            events=[e for e in store_for(selected).events(limit=200)['events'] if e.get('causal',{}).get('check')=='assignment_read']
        self.assertEqual(mocked.call_count,2)
        self.assertEqual([e['causal']['cause'] for e in events],['connection_failure','request_timeout','account_timeout_deferred'])
        self.assertIsNone(events[0]['causal']['refs']['cause_event_id'])
        self.assertIsNone(events[1]['causal']['refs']['cause_event_id'])
        self.assertEqual(events[2]['causal']['refs']['cause_event_id'],events[1]['event_id'])
        facts=events[2]['causal']['facts']
        self.assertFalse(facts['shared_deadline_selected'])
        self.assertFalse(facts['batch_deadline_selected'])
        self.assertFalse(facts['request_timeout_selected'])
        self.assertFalse(facts['attempted'])
        self.assertGreater(facts['remaining_ms'],0)
        self.assertTrue(all(row['state']=='unknown' and row['hold_auto_reply'] for row in result.values()))

    def test_unavailable_sink_preserves_timeout_and_account_reservation(self):
        from cs import task_assignment
        failure=rpc_reads.ReadOutcome(error=TimeoutError('PRIVATE'),diagnostic=rpc_reads.diagnostic('request_timeout',time.monotonic(),.1,1))
        with patch.object(rpc_reads,'read_many',side_effect=lambda s,m,rows,**kw:{key:failure for key in rows}) as read,patch('cs.observability_producers.emit',side_effect=OSError('PRIVATE')):
            result=task_assignment.projections(settings(),['<a@example.test>','<b@example.test>'])
        self.assertEqual(read.call_count,1)
        self.assertTrue(all(row['state']=='unknown' and row['hold_auto_reply'] for row in result.values()))
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_timing_validator_rejects_nonfinite_negative_bool_and_unexpected(self):
        from cs.monitor_details import safe_detail
        from cs.observability_causal import decision
        for key in ('elapsed_ms','deadline_seconds'):
            for invalid in (float('nan'),float('inf'),-1,True,'private'):
                with self.subTest(key=key,invalid=repr(invalid)),self.assertRaises(ValueError):safe_detail({key:invalid})
        self.assertEqual(safe_detail({'elapsed_ms':1.5,'deadline_seconds':120}),{'elapsed_ms':1.5,'deadline_seconds':120})
        base=rpc_reads.diagnostic('worker_timeout',time.monotonic(),.1,.2,bound_origin='shared_deadline')
        for invalid in ({**base,'cause':'PRIVATE'}, {**base,'elapsed_ms':True},{**base,'bound_ms':-1},{**base,'token':'SECRET'}):
            with self.assertRaises(ValueError):rpc_reads.validate_diagnostic(invalid)

if __name__=='__main__':unittest.main()
