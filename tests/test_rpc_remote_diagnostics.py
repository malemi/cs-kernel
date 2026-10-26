"""Structured remote provenance survives isolated reads without payload leakage."""
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import websockets
from cs import rpc_reads, task_assignment
from cs.observability import EventStore
from cs.monitor_config import Component, MonitorConfig
from test_task_assignment import settings, projection

TOKEN = 'fixture.' + base64.urlsafe_b64encode(json.dumps({'exp': int(time.time())+3600}).encode()).decode().rstrip('=') + '.fixture'
REQUIRED = {'cause', 'bound_origin', 'elapsed_ms', 'bound_ms', 'remaining_ms'}


class RemoteDiagnostics(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, mode, *, projected=False):
        calls = []
        async def handler(ws):
            async for raw in ws:
                frame = json.loads(raw)
                calls.append(frame)
                if mode == 'connection':
                    await ws.close()
                elif mode == 'timeout':
                    await asyncio.sleep(1)
                else:
                    key = frame['params']['thread_key']
                    value = projection() | {'thread_key': key}
                    if mode == 'held':
                        value.update(state='needs-assignment', complete=False, hold_auto_reply=True)
                    response = {'result': value} if mode in {'success', 'held'} else {'error': {
                        'code': -32602 if mode == 'invalid' else -32091,
                        'message': 'PRIVATE_MESSAGE_CANARY', 'data': {'secret': 'PRIVATE_DATA_CANARY'}}}
                    await ws.send(json.dumps({'jsonrpc':'2.0', 'id':frame['id'], **response}))
        async with websockets.serve(handler, '127.0.0.1', 0) as server:
            with tempfile.TemporaryDirectory() as directory:
                token = Path(directory)/'token.json'
                token.write_text(json.dumps({'uid':'operator','id_token':TOKEN}))
                selected = settings().model_copy(update={'engine_ws_url':f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}',
                    'token_cache_path': str(token), 'firebase_web_api_key':'fixture-key'})
                keys = ['<first@example.test>'] if mode == 'timeout' else ['<first@example.test>', '<next@example.test>']
                store = EventStore(Path(directory)/'events', 'operator')
                with patch.object(rpc_reads,'CLOSE_SECONDS',0.01), patch('cs.observability_producers.store_for',return_value=store):
                    if projected:
                        result = await asyncio.to_thread(task_assignment.projections, selected, keys)
                    else:
                        result = await asyncio.to_thread(rpc_reads.read_many, selected, 'tasks.assignment.project',
                            {key:{'thread_key':key} for key in keys}, request_timeout=0.2, batch_timeout=3,
                            token_cache={'operator':TOKEN})
                events = store.events(limit=200)['events']
                if projected:
                    await self.forward(store, events, mode)
        self.assertEqual([frame['method'] for frame in calls], ['tasks.assignment.project']*len(calls))
        self.assertEqual([frame['params']['thread_key'] for frame in calls], keys[:len(calls)])
        if mode != 'connection' or not projected:
            self.assertEqual(len(calls),len(keys))
        self.assertEqual(list(result), keys)
        return result, events

    async def forward(self, store, events, mode):
        import shutil
        from cs.observability import owner_root
        with tempfile.TemporaryDirectory() as home:
            manifest = Path(home)/'manifest.toml'
            manifest.write_text('[company]\nslug="remote"\n[engine]\nowner_uid="operator"\n')
            target = owner_root(Path(home)/'.remote-cs','operator')
            target.parent.mkdir(parents=True,mode=0o700)
            shutil.copytree(store.root,target)
            env={key:value for key,value in os.environ.items() if not key.startswith(('CS_','ENGINE_','EMAIL_'))}
            env.update(HOME=home,CS_MANIFEST=str(manifest),CS_ENGINE_OWNER_UID='operator')
            pages=[]; cursor=None
            while True:
                args=[sys.executable,'-m','cs','logs','events','--local','--json','--limit','1']
                if cursor:
                    args += ['--cursor',cursor]
                done=await asyncio.to_thread(subprocess.run,args,env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(done.returncode,0,done.stderr)
                page=json.loads(done.stdout)['local']; pages.extend(page['events'])
                cursor=page.get('next_cursor')
                if not cursor:
                    break
            expected=[event for event in events if event.get('causal',{}).get('check')=='assignment_read']
            self.assertTrue(expected)
            self.assertTrue(all(event in pages for event in expected))
            cfg=MonitorConfig(mode='filesystem',monitor_id='b'*32,owner_uid='operator',state_dir=str(Path(home)/'monitor'),
                expected_start_utc=int(time.time()),components=[Component(id='operator',kind='kernel',local_root=str(target))])
            path=Path(home)/'monitor.json';path.write_text(cfg.model_dump_json());path.chmod(0o600)
            done=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','cs','monitor','once','--config',str(path)],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(done.returncode,1,done.stdout+done.stderr)
            inbox=json.loads((Path(home)/'monitor'/'problems.json').read_text())
            self.assertTrue(any(problem['evidence'].get('causal')==expected[0]['causal'] for problem in inbox['problems']))
            retained=os.environ.get('REMOTE_DIAGNOSTIC_EVIDENCE_DIR')
            if retained:
                root=Path(retained);root.mkdir(parents=True,exist_ok=True)
                (root/(mode+'-events.json')).write_text(json.dumps(pages,indent=2))
                (root/(mode+'-inbox.json')).write_text(json.dumps(inbox,indent=2))
            serialized=json.dumps([pages,inbox])
            for private in ('PRIVATE_MESSAGE_CANARY','PRIVATE_DATA_CANARY','@example.test','fixture.'):
                self.assertNotIn(private,serialized)

    async def test_real_worker_remote_and_transport_controls(self):
        for mode,cause,error in [('invalid','remote_invalid_params',RuntimeError),('other','remote_error',RuntimeError),
                                 ('connection','connection_failure',TimeoutError),('timeout','request_timeout',TimeoutError),
                                 ('success',None,None),('held',None,None)]:
            with self.subTest(mode=mode):
                results,_=await self.exercise(mode)
                for row in results.values():
                    if cause is None:
                        self.assertIsNone(row.error)
                        self.assertIsNone(row.diagnostic)
                        self.assertEqual(row.value['state'],'needs-assignment' if mode == 'held' else 'normal')
                        self.assertEqual(row.value['hold_auto_reply'],mode == 'held')
                    else:
                        if mode == 'connection':
                            self.assertIn(type(row.error),(TimeoutError,ConnectionError))
                        else:
                            self.assertIs(type(row.error),error)
                        self.assertEqual(row.diagnostic['cause'],cause)
                        if mode == 'timeout':
                            self.assertEqual(row.diagnostic['bound_origin'],'request_timeout')
                            self.assertGreater(row.diagnostic['remaining_ms'],row.diagnostic['bound_ms'])
                        self.assertEqual(set(row.diagnostic), REQUIRED | ({'remote_error_code'} if mode in {'invalid','other'} else set()))
                        if mode in {'invalid','other'}:
                            self.assertEqual(row.diagnostic['remote_error_code'],-32602 if mode=='invalid' else -32091)
                        self.assertNotIn('PRIVATE_',json.dumps(row.diagnostic))

    async def test_remote_provenance_reaches_paged_cli_collector_and_inbox(self):
        for mode,code in [('invalid',-32602),('other',-32091),('connection',None)]:
            with self.subTest(mode=mode):
                results,events=await self.exercise(mode,projected=True)
                self.assertTrue(all(row['state']=='unknown' and row['hold_auto_reply'] for row in results.values()))
                reads=[event for event in events if event.get('causal',{}).get('check')=='assignment_read']
                self.assertEqual(len(reads),2)
                for event in reads:
                    if code is None:
                        self.assertIn(event['error_class'],{'ConnectionError','TimeoutError','UnknownError'})
                    else:
                        self.assertEqual(event['error_class'],'EngineError')
                    if code is not None:
                        self.assertEqual(event['error_code'],code)

    async def test_early_connection_failure_summary_does_not_claim_bound_expired(self):
        _,events=await self.exercise('connection',projected=True)
        first=next(event for event in events if event.get('causal',{}).get('cause')=='connection_failure')
        facts=first['causal']['facts']
        self.assertLess(facts['elapsed_ms'],facts['bound_ms'])
        self.assertGreater(facts['remaining_ms'],0)
        self.assertTrue(facts['batch_deadline_selected'])
        summary=next(event for event in events if event.get('method')=='tasks.assignment.budget')
        self.assertEqual(summary['causal']['cause'],'read_failed')
        self.assertEqual(summary['causal']['refs']['cause_event_id'],first['event_id'])
        self.assertGreater(summary['causal']['facts']['remaining_ms'],0)

    def test_parent_rejects_adversarial_worker_metadata(self):
        base=rpc_reads.diagnostic('request_timeout',time.monotonic(),1,bound_origin='request_timeout')
        for extra in ({'remote_error_code':True},{'remote_error_code':2**53},{'message':'PRIVATE_CANARY'}):
            output=json.dumps({'outcomes':{'key':{'value':None,'error':'unavailable','diagnostic':base|extra}},'token':None})
            command=(sys.executable,'-c','import sys; sys.stdin.read(); print('+repr(output)+')')
            with patch.object(rpc_reads,'READ_COMMAND',command):
                row=rpc_reads.read_many(settings(),'tasks.assignment.project',{'key':{}})['key']
            self.assertIs(type(row.error),ValueError)
            self.assertIsNone(row.diagnostic)

    def test_strict_optional_schema(self):
        base=rpc_reads.diagnostic('request_timeout',time.monotonic(),1,bound_origin='request_timeout')
        self.assertEqual(set(base),REQUIRED)
        for code in (-32602,0,2**53-1,-2**53+1):
            candidate={**base,'remote_error_code':code}
            self.assertEqual(rpc_reads.validate_diagnostic(candidate),candidate)
        for code in (True,False,None,'-32602',1.5,2**53,-2**53):
            with self.subTest(code=code),self.assertRaises(ValueError):
                rpc_reads.validate_diagnostic({**base,'remote_error_code':code})
        for extra in ('message','data','error_class','root_id'):
            with self.assertRaises(ValueError):
                rpc_reads.validate_diagnostic({**base,extra:'PRIVATE_CANARY'})


if __name__=='__main__':
    unittest.main()
