"""Real read workers preserve diagnostic identities without changing business work."""
from __future__ import annotations
import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import websockets
from cs import config, review, unanswered, rpc_reads
from cs.observability import context, current_context

IDS = dict(trace_id='a'*32, span_id='b'*32, run_id='c'*32, attempt_id='d'*32)
TOKEN = 'fixture.' + base64.urlsafe_b64encode(json.dumps({'exp':int(time.time())+3600}).encode()).decode().rstrip('=') + '.fixture'
KEY = '<context@example.test>'
BOOTSTRAP = '''
import json,os,sys
from cs import config,review,unanswered,rpc_reads,task_assignment
from cs.observability import current_context
from pathlib import Path
config.Settings.state_dir=property(lambda self:Path(os.environ['CONTEXT_TEST_STATE_DIRECTORY']))
rpc_reads.CLOSE_SECONDS=.05
rpc_reads.READ_COMMAND=(sys.executable,'-c',"import os;from pathlib import Path;from cs import auth,config,rpc_reads;config.Settings.state_dir=property(lambda s:Path(os.environ['CONTEXT_TEST_STATE_DIRECTORY']));auth.get_id_token=lambda s:"+repr(TOKEN)+";rpc_reads._isolated_main()")
def aggregate(settings,**kwargs):
    return {'diagnostic_seen':current_context(),'projection':task_assignment.projections(settings,[KEY],deadline=kwargs['deadline'],owned_process_group=kwargs['owned_process_group'])}
review._aggregate=aggregate
def sweep(settings,days,**kwargs):
    seen=current_context()
    result=aggregate(settings,**kwargs)
    kwargs['checkpoint']({'inbound':[],'sent':[],'inbound_complete':True,'sent_complete':True,'roots':[],'assignment':{}},'fixture')
    return dict(open=[],handled=[],escalated=[],human_work=[],assignment_audit=[],operational_fixture_discovery=[],resumed=[],automatic=[],courtesy=[],assignment_incomplete=False,read_incomplete=None,diagnostic_seen=seen,projection=result['projection'])
unanswered.sweep=sweep
if sys.argv[1]=='review':
    sys.argv=['review','--worker']
    raise SystemExit(review.main())
config.load=lambda:config.Settings.model_validate(json.loads(os.environ['CONTEXT_TEST_SETTINGS']))
raise SystemExit(unanswered._discovery_main())
'''

class Workers(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, kind, ids=IDS, override=None, linked=True):
        frames=[]
        async def handler(ws):
            async for raw in ws:
                frame=json.loads(raw);frames.append(frame)
                value={'observability':1} if frame['method']=='system.capabilities' else dict(version=1,actor_uid='operator',space_id='company',complete=False,thread_key=KEY,state='unknown',hold_auto_reply=True,task=None,events=[],covered_inbound=[],covered_message_ids=[],current_inbound=[],current_message_ids=[],reply_evidence=[],reason='REPLY_SOURCE_UNAVAILABLE')
                await ws.send(json.dumps({'jsonrpc':'2.0','id':frame['id'],'result':value}))
        with tempfile.TemporaryDirectory() as directory:
            async with websockets.serve(handler,'127.0.0.1',0) as server:
                selected=config.Settings(_env_file=(),slug='context-test',engine_owner_uid='operator',accounts='',engine_ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}',db_path=str(Path(directory)/'state.db'))
                bootstrap='TOKEN='+repr(TOKEN)+'\nKEY='+repr(KEY)+'\n'+BOOTSTRAP
                if override is not None:
                    bootstrap=bootstrap.replace("if sys.argv[1]=='review':","os.environ['CS_DIAGNOSTIC_CONTEXT']="+repr(override)+"\nif sys.argv[1]=='review':")
                with patch.dict(os.environ, {'CONTEXT_TEST_STATE_DIRECTORY':str(Path(directory)/'state'),'CONTEXT_TEST_SETTINGS':selected.model_dump_json(),'CS_OPERATOR_HEALTH_CONTEXT':''}):
                    with context(ids):
                        before=current_context()
                        if kind=='review':
                            result=await asyncio.to_thread(review._supervise,selected,worker_command=(sys.executable,'-B','-c',bootstrap,'review'),work_seconds=8,cleanup_seconds=.3,total_seconds=9)
                        else:
                            result=(await asyncio.to_thread(unanswered._scheduled_discovery,worker_command=lambda fd:(sys.executable,'-B','-c',bootstrap,'--worker',str(fd)),observation_seconds=8,cleanup_seconds=.3,publication_seconds=.2,final_seconds=.2,total_seconds=9))['value']
                        self.assertEqual(current_context(),before)
        self.assertEqual(result['projection'][KEY]['state'],'unknown')
        self.assertEqual(result['projection'][KEY]['reason'],'assignment account scope unreadable: primary account: REPLY_SOURCE_UNAVAILABLE')
        requests=[f for f in frames if f['method']=='tasks.assignment.project']
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0]['params'],{'thread_key':KEY})
        self.assertEqual(result['projection'][KEY]['actor_uid'],'operator')
        if linked:
            for key in ('trace_id','run_id','attempt_id'):
                self.assertEqual(result['diagnostic_seen'][key],ids[key])
                self.assertEqual(requests[0].get('diagnostics',{}).get(key),ids[key])
            diagnostic=requests[0]['diagnostics']
            self.assertNotEqual(diagnostic['span_id'],result['diagnostic_seen']['span_id'])
            self.assertIsNotNone(diagnostic.get('parent_span_id'))
            self.assertEqual(set(diagnostic)-{'version'},set(IDS)|{'parent_span_id'})
        else:
            self.assertEqual(result['diagnostic_seen'],{})
            self.assertNotIn('diagnostics',requests[0])
        self.assertEqual(current_context(),{})
        return result,frames

    async def test_review_actual_worker_thread_and_rpc_process(self):
        await self.exercise('review')

    async def test_scheduled_actual_worker_thread_and_rpc_process(self):
        await self.exercise('discovery')

    async def test_invalid_optional_metadata_does_not_change_business_results(self):
        for value in ('', '{', '[]', json.dumps({'trace_id':'invalid','owner_uid':'foreign'}), 'x'*1025):
            with self.subTest(value=value[:30]):
                await self.exercise('review',override=value,linked=False)
                await self.exercise('discovery',override=value,linked=False)

    async def test_extra_fields_cannot_select_business_owner_or_method(self):
        value=json.dumps(IDS | {'owner_uid':'foreign','method':'forbidden','token':'secret'})
        await self.exercise('review',override=value)
        await self.exercise('discovery',override=value)

class ConcurrentTransport(unittest.IsolatedAsyncioTestCase):
    async def test_distinct_request_spans_share_only_their_parent_identity(self):
        from cs import rpc
        frames=[]
        async def handler(ws):
            async for raw in ws:
                frame=json.loads(raw);frames.append(frame)
                if frame['method']=='system.capabilities':
                    await asyncio.sleep(.03)
                    value={'observability':1}
                else:value={'unchanged':frame['params']}
                await ws.send(json.dumps({'jsonrpc':'2.0','id':frame['id'],'result':value}))
        with tempfile.TemporaryDirectory() as directory:
            async with websockets.serve(handler,'127.0.0.1',0) as server:
                selected=config.Settings(_env_file=(),slug='context-test',engine_owner_uid='operator',accounts='',engine_ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
                with patch.object(config.Settings,'state_dir',property(lambda _:Path(directory))),patch.object(rpc.auth,'get_id_token',return_value=TOKEN):
                    with context(IDS):
                        result=await rpc_reads._read(selected,'emails.list_by_thread',{'one':{'thread_id':'one'},'two':{'thread_id':'two'}},2,3,None)
        requests=[f for f in frames if f['method']=='emails.list_by_thread']
        self.assertEqual([result[k].value for k in ('one','two')],[{'unchanged':{'thread_id':k}} for k in ('one','two')])
        self.assertTrue(all('diagnostics' in f for f in requests),requests)
        self.assertEqual({f['diagnostics']['trace_id'] for f in requests},{IDS['trace_id']})
        self.assertEqual(len({f['diagnostics']['span_id'] for f in requests}),2)
        self.assertEqual({f['diagnostics']['parent_span_id'] for f in requests},{IDS['span_id']})
        self.assertEqual(current_context(),{})

    async def test_unsupported_failed_and_stalled_negotiation_keep_business_calls(self):
        from cs import rpc
        for mode in ('unsupported','error','stalled'):
            frames=[]
            async def handler(ws):
                async for raw in ws:
                    frame=json.loads(raw);frames.append(frame)
                    if frame['method']=='system.capabilities':
                        if mode=='stalled':continue
                        response={'error':{'code':-32601,'message':'unsupported'}} if mode=='error' else {'result':{'observability':0}}
                    else:response={'result':frame['params']}
                    await ws.send(json.dumps({'jsonrpc':'2.0','id':frame['id'],**response}))
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                async with websockets.serve(handler,'127.0.0.1',0) as server:
                    selected=config.Settings(_env_file=(),engine_owner_uid='operator',engine_ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
                    with patch.object(config.Settings,'state_dir',property(lambda _:Path(directory))):
                        async with rpc.EngineClient(selected,id_token=TOKEN) as client:
                            with context(IDS):
                                values=await asyncio.gather(*(client.call('emails.list_by_thread',{'thread_id':key},timeout=3) for key in ('one','two')))
                            self.assertEqual(values,[{'thread_id':'one'},{'thread_id':'two'}])
                            self.assertIsNone(client._ws.close_code)
                            self.assertEqual(len([f for f in frames if f['method']=='system.capabilities']),1)
                            business=[f for f in frames if f['method']=='emails.list_by_thread']
                            self.assertEqual(len(business),2)
                            self.assertTrue(all('diagnostics' not in f for f in business))
                        self.assertFalse(client._pending)
            self.assertEqual(current_context(),{})

    async def test_cancelled_probe_waiter_does_not_cancel_shared_readiness(self):
        from cs import rpc
        probe_seen=asyncio.Event();release=asyncio.Event();frames=[]
        async def handler(ws):
            async for raw in ws:
                frame=json.loads(raw);frames.append(frame)
                if frame['method']=='system.capabilities':
                    probe_seen.set();await release.wait();value={'observability':1}
                else:value=frame['params']
                await ws.send(json.dumps({'jsonrpc':'2.0','id':frame['id'],'result':value}))
        with tempfile.TemporaryDirectory() as directory:
            async with websockets.serve(handler,'127.0.0.1',0) as server:
                selected=config.Settings(_env_file=(),engine_owner_uid='operator',engine_ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
                with patch.object(config.Settings,'state_dir',property(lambda _:Path(directory))):
                    async with rpc.EngineClient(selected,id_token=TOKEN) as client:
                        with context(IDS):
                            first=asyncio.create_task(client.call('emails.list_by_thread',{'thread_id':'cancelled'},timeout=3))
                            await probe_seen.wait()
                            second=asyncio.create_task(client.call('emails.list_by_thread',{'thread_id':'survivor'},timeout=3))
                            first.cancel()
                            with self.assertRaises(asyncio.CancelledError):await first
                            release.set()
                            self.assertEqual(await second,{'thread_id':'survivor'})
                            self.assertEqual(current_context()['trace_id'],IDS['trace_id'])
                        business=[f for f in frames if f['method']=='emails.list_by_thread']
                        self.assertEqual([f['params'] for f in business],[{'thread_id':'survivor'}])
                        self.assertEqual(business[0]['diagnostics']['trace_id'],IDS['trace_id'])
                        self.assertIsNone(client._ws.close_code)
                    self.assertFalse(client._pending)
        self.assertEqual(current_context(),{})

    async def test_concurrent_owners_and_runs_do_not_cross_link(self):
        from cs import rpc
        frames=[]
        async def handler(ws):
            owner=ws.request.path.rsplit('/',1)[-1]
            async for raw in ws:
                frame=json.loads(raw);frames.append((owner,frame))
                value={'observability':1} if frame['method']=='system.capabilities' else frame['params']
                await ws.send(json.dumps({'jsonrpc':'2.0','id':frame['id'],'result':value}))
        with tempfile.TemporaryDirectory() as directory:
            async with websockets.serve(handler,'127.0.0.1',0) as server:
                selected=config.Settings(_env_file=(),engine_owner_uid='operator',engine_ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
                async def run(owner,ids):
                    with context(ids):
                        return await rpc_reads._read(selected.model_copy(update={'engine_owner_uid':owner}),'emails.list_by_thread',{'one':{'thread_id':'one'},'two':{'thread_id':'two'}},3,4,None)
                other=IDS | {'trace_id':'e'*32,'run_id':'f'*32,'attempt_id':'1'*32}
                with patch.object(config.Settings,'state_dir',property(lambda _:Path(directory))),patch.object(rpc.auth,'get_id_token',return_value=TOKEN):
                    rows=await asyncio.gather(run('operator',IDS),run('other',other))
        self.assertTrue(all(row.error is None for batch in rows for row in batch.values()))
        for owner,ids in [('operator',IDS),('other',other)]:
            business=[frame for actual,frame in frames if actual==owner and frame['method']=='emails.list_by_thread']
            self.assertEqual(len(business),2)
            for frame in business:
                for key in ('trace_id','run_id','attempt_id'):self.assertEqual(frame['diagnostics'][key],ids[key])
        self.assertEqual(len({f['diagnostics']['span_id'] for _,f in frames if f['method']=='emails.list_by_thread'}),4)
        self.assertEqual(current_context(),{})

if __name__=='__main__':unittest.main()
