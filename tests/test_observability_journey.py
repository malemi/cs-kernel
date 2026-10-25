"""Ordinary diagnostic entry points and controlled producer failures."""
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

from cs.config import Settings
from cs.observability import EventStore, context, store_for
from cs.observability_producers import observe
from cs.observability_retention import maintain
from cs.rpc import EngineClient


class JourneyTests(unittest.TestCase):
    def test_actual_shell_pause_and_cli_preserve_exit(self):
        from jinja2 import Environment, StrictUndefined
        template = Path('cs/templates/project/bin/cs_operator_cron.sh.j2').read_text()
        rendered = Environment(undefined=StrictUndefined).from_string(template).render(company_name='Trial',email_address='ops@example.test',company_slug='trial',company_prog_name='cs',local_scripts_cron_denied=[])
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);repo=base/'repo';(repo/'bin').mkdir(parents=True)
            (repo/'.venv').symlink_to(Path(sys.executable).parent.parent, target_is_directory=True)
            (repo/'manifest.toml').write_text('[company]\nslug="trial"\n[engine]\nowner_uid="owner"\n')
            script=repo/'bin/cs_operator_cron.sh';script.write_text(rendered)
            state=base/'.trial-cs';state.mkdir();(state/'CS_PAUSE').touch()
            env={**{k:v for k,v in os.environ.items() if not k.startswith(('CS_','EMAIL_','ENGINE_','SHOPIFY_')) and k not in {'SLUG','READ_MAILBOXES','READ_MAILBOX_PASSWORDS'}},'HOME':str(base),'PYTHONPATH':str(Path.cwd()),'CS_MANIFEST':str(repo/'manifest.toml')}
            result=subprocess.run(['bash',str(script)],env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            from types import SimpleNamespace
            events=store_for(SimpleNamespace(state_dir=state,engine_owner_uid='owner')).events()['events']
            self.assertTrue({'start','paused','result'} <= {e['status'] for e in events}, (result.stderr,events))
            # Retention health observations have their own background traces.
            launch_events=[e for e in events if e['stage']!='cleanup']
            self.assertEqual(len({e['trace_id'] for e in launch_events}),1)

    def test_logging_does_not_replace_business_result_or_exception(self):
        @observe('provider')
        def operation(settings, value):
            if isinstance(value,Exception):
                raise value
            return value
        settings=Settings(_env_file=None)
        error=PermissionError('CANARY_SECRET')
        with patch('cs.observability_producers.emit',return_value=None):
            self.assertEqual(operation(settings,17),17)
            with self.assertRaises(PermissionError) as raised:
                operation(settings,error)
            self.assertIs(raised.exception,error)

    def test_real_retention_budget_and_active_evidence(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HOME':temp}):
            settings=Settings(_env_file=None,slug='trial',engine_owner_uid='owner')
            settings.state_dir.mkdir(mode=0o700)
            settings.log_path.write_bytes(b'x'*4096)
            root=settings.state_dir/'operator-runs';root.mkdir()
            inactive=root/'run-old';inactive.mkdir();old=inactive/'native-stream.jsonl';old.write_bytes(b'x'*800)
            current=root/'run-current';current.mkdir();live=current/'native-stream.jsonl';live.write_bytes(b'live')
            result=maintain(settings,active_directory=current,log_bytes=1024,native_bytes=100)
            self.assertTrue(result['complete'])
            self.assertLessEqual(settings.log_path.stat().st_size+(settings.state_dir/'cs_operator.log.1').stat().st_size,1024)
            self.assertFalse(old.exists())
            self.assertEqual(live.read_bytes(),b'live')

    def test_recent_returns_latest_failure_only(self):
        with tempfile.TemporaryDirectory() as temp:
            store=EventStore(Path(temp)/'store','owner')
            earlier=store.emit('rpc','failed',reason='auth')
            store.emit('rpc','result',reason='none')
            latest=store.emit('rpc','failed',reason='permission')
            page=store.recent()
            self.assertEqual([e['event_id'] for e in page['events']],[latest['event_id'],earlier['event_id']])

    def test_nested_capture_retention_preserves_live_and_unknown_evidence(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HOME':temp}):
            settings=Settings(_env_file=None,slug='trial',engine_owner_uid='owner')
            settings.state_dir.mkdir(mode=0o700)
            root=settings.state_dir/'operator-runs';root.mkdir()
            current=root/'run-current';current.mkdir()
            live=current/'business-reads';live.mkdir();(live/'1-2.json').write_bytes(b'live')
            old=root/'run-old';old.mkdir()
            nested=old/'dossier-attempt-test';nested.mkdir()
            expired=nested/'result.json';expired.write_bytes(b'x'*200)
            unknown=nested/'unrecognized';unknown.write_bytes(b'keep')
            result=maintain(settings,active_directory=current,native_bytes=20)
            self.assertTrue(result['complete'])
            self.assertFalse(expired.exists())
            self.assertEqual((live/'1-2.json').read_bytes(),b'live')
            self.assertEqual(unknown.read_bytes(),b'keep')
            before=time.time()-8*86400;os.utime(unknown,(before,before))
            self.assertFalse(maintain(settings,active_directory=current,native_bytes=20)['complete'])

    def test_nested_capture_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HOME':temp}):
            settings=Settings(_env_file=None,slug='trial',engine_owner_uid='owner')
            directory=settings.state_dir/'operator-runs'/'run-test'/'business-reads'
            directory.mkdir(parents=True,mode=0o700)
            target=Path(temp)/'outside';target.write_bytes(b'preserve')
            (directory/'1-2.json').symlink_to(target)
            self.assertFalse(maintain(settings)['complete'])
            self.assertEqual(target.read_bytes(),b'preserve')


    def test_retention_preserves_actual_locked_writer(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HOME':temp}):
            settings=Settings(_env_file=None,slug='trial',engine_owner_uid='owner')
            settings.state_dir.mkdir(mode=0o700)
            settings.log_path.write_bytes(b'live-output'*1024)
            lock=settings.state_dir/'cs_operator.lock'
            code="import fcntl,sys; f=open(sys.argv[1],'w'); fcntl.flock(f,fcntl.LOCK_EX); print('ready',flush=True); input()"
            process=subprocess.Popen([sys.executable,'-c',code,str(lock)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(),'ready')
                before=settings.log_path.read_bytes()
                result=maintain(settings,log_bytes=1024)
                self.assertFalse(result['complete'])
                self.assertEqual(settings.log_path.read_bytes(),before)
            finally:
                process.communicate('stop\n',timeout=5)

    def test_oversized_recent_archive_migrates_with_small_main(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HOME':temp}):
            settings=Settings(_env_file=None,slug='trial',engine_owner_uid='owner')
            settings.state_dir.mkdir(mode=0o700)
            settings.log_path.write_bytes(b'x')
            archive=settings.state_dir/'cs_operator.log.1'
            archive.write_bytes(b'y'*4096)
            result=maintain(settings,log_bytes=1024)
            self.assertTrue(result['complete'])
            self.assertLessEqual(settings.log_path.stat().st_size+archive.stat().st_size,1024)
            self.assertEqual(settings.log_path.read_bytes(),b'x')
            old=time.time()-8*86400
            os.utime(archive,(old,old))
            self.assertTrue(maintain(settings,log_bytes=1024)['complete'])
            self.assertFalse(archive.exists())

    def test_busy_writer_overlarge_archive_reports_incomplete(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HOME':temp}):
            settings=Settings(_env_file=None,slug='trial',engine_owner_uid='owner')
            settings.state_dir.mkdir(mode=0o700)
            settings.log_path.write_bytes(b'x')
            archive=settings.state_dir/'cs_operator.log.1';archive.write_bytes(b'y'*4096)
            lock=settings.state_dir/'cs_operator.lock'
            code="import fcntl,sys; f=open(sys.argv[1],'w'); fcntl.flock(f,fcntl.LOCK_EX); print('ready',flush=True); input()"
            process=subprocess.Popen([sys.executable,'-c',code,str(lock)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(),'ready')
                result=maintain(settings,log_bytes=1024)
                self.assertFalse(result['complete'])
                self.assertEqual(settings.log_path.read_bytes(),b'x')
                self.assertEqual(archive.read_bytes(),b'y'*4096)
            finally:
                process.communicate('stop\n',timeout=5)

    def test_standalone_structured_prune_without_new_work_events(self):
        with tempfile.TemporaryDirectory() as temp:
            store=EventStore(Path(temp)/'store','owner',retention_days=1)
            store.emit('cli','result')
            with patch('cs.observability_store.time.time',return_value=time.time()+3*86400):
                result=store.prune()
            self.assertTrue(result['complete'])
            self.assertEqual(result['removed'],1)
            self.assertEqual(list(store.root.glob('events-*')),[])


class RpcJourneyTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_local_websocket_join_and_no_payload_persistence(self):
        import websockets
        seen=[]
        async def handler(socket):
            async for raw in socket:
                request=json.loads(raw);seen.append(request)
                result={'observability':1} if request['method']=='system.capabilities' else {'ok':True}
                await socket.send(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}))
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'HOME':temp}):
            async with websockets.serve(handler,'127.0.0.1',0) as server:
                port=server.sockets[0].getsockname()[1]
                settings=Settings(_env_file=None,slug='trial',engine_owner_uid='owner',engine_ws_url=f'ws://127.0.0.1:{port}')
                with context() as active:
                    async with EngineClient(settings,id_token='CANARY_SECRET') as client:
                        self.assertEqual(await client.call('emails.search',{'query':'CANARY_SECRET'},timeout=3),{'ok':True})
                self.assertEqual(seen[0]['method'],'system.capabilities')
                self.assertEqual(seen[1]['diagnostics']['trace_id'],active['trace_id'])
                events=store_for(settings).events()['events']
                self.assertTrue(events)
                self.assertNotIn('CANARY_SECRET',json.dumps(events))
                self.assertEqual([e['status'] for e in events],['start','result'])
