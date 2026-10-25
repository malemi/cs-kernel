"""Scheduled discovery orchestration against explicitly simulated local observations."""
import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from cs import unanswered, gmail_archive, engine_view, task_assignment, cli
from cs.operator_health import identity


class ScheduledDiscoveryTests(unittest.TestCase):
    def fixture(self):
        settings = SimpleNamespace(engine_owner_uid='local-owner', email_address='owner@example.test',
            self_email_set=set(), system_sender_set=set(), db_path=Path('/unused'))
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        inbound = [dict(email='person@example.test', date=now, thread_key='<one@example.test>', subject='Kept')]
        state = MagicMock()
        state.do_not_contact_set.return_value = set()
        state.handled_out_of_band.return_value = {}
        state.escalated_to_human.return_value = {}
        return settings, inbound, state

    def test_absolute_deadline_stops_every_subsequent_dispatch(self):
        for stalled in ['inbound', 'sent', 'classify', 'settled', 'project']:
            settings, inbound, state = self.fixture()
            clock = [0.0]
            calls = []
            checkpoints = []
            def call(name, value):
                calls.append(name)
                if name == stalled:
                    clock[0] = 6
                return value
            with patch.object(unanswered.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(gmail_archive, 'inbound_recent', side_effect=lambda *a: call('inbound', inbound)), \
                 patch.object(gmail_archive, 'sent_recent', side_effect=lambda *a: call('sent', [])), \
                 patch('cs.state.State', return_value=state), \
                 patch('cs.operational_fixture.admit_originals', side_effect=lambda s, rows, own, **kw: (rows, own)), \
                 patch.object(engine_view, 'classify', side_effect=lambda *a, **kw: call('classify', ({}, None))), \
                 patch.object(engine_view, 'settled', side_effect=lambda *a, **kw: call('settled', ({}, None))), \
                 patch.object(task_assignment, 'projections', side_effect=lambda s, roots, **kw:
                     call('project', {root: task_assignment._unknown(root, 'local fixture') for root in roots})):
                with self.assertRaises(TimeoutError):
                    unanswered.sweep(settings, 14, deadline=5,
                        checkpoint=lambda value, phase: checkpoints.append(
                            {'observation':unanswered._discovery_decode(unanswered._discovery_encode(value))}))
            self.assertEqual(calls[-1], stalled)
            fallback = unanswered._discovery_incomplete(checkpoints[-1], 'simulated timeout')
            self.assertTrue(fallback['assignment_incomplete'])
            self.assertIsNotNone(fallback['read_incomplete'])
            self.assertIn('<one@example.test>', {row['thread_key'] for row in fallback['human_work']})
            self.assertEqual(fallback['human_work'][0]['last_inbound_date'], inbound[0]['date'])

    def test_date_codec_roundtrip(self):
        value = {'date':datetime(2026, 10, 20, tzinfo=timezone.utc), 'nested':[None, False, 5]}
        self.assertEqual(unanswered._discovery_decode(json.loads(json.dumps(unanswered._discovery_encode(value)))), value)
        with self.assertRaises(ValueError):
            unanswered._discovery_encode(object())

    def run_worker(self, body, **kwargs):
        code = '''import json,os,sys,time,subprocess
from pathlib import Path
from cs.review import _save_checkpoint
from cs.unanswered import _discovery_encode
with os.fdopen(int(sys.argv[1]),'rb') as stream:p=json.loads(stream.read())
obs={'inbound':[],'sent':[],'inbound_complete':True,'sent_complete':True,'roots':[],'assignment':{}}
out={'configuration':{'owner_uid':'local-owner','sha256':'a'*64},'observation':obs}
value={'open':[],'handled':[],'escalated':[],'human_work':[],'assignment_audit':[],'operational_fixture_discovery':[],'resumed':[],'automatic':[],'courtesy':[],'assignment_incomplete':False,'read_incomplete':None,'note':None,'crm_note':None}
''' + body
        with contextlib.redirect_stderr(io.StringIO()):
            return unanswered._scheduled_discovery(worker_command=lambda fd:
                [sys.executable,'-B','-c',code,str(fd)], observation_seconds=.8,
                cleanup_seconds=.4, publication_seconds=.1, final_seconds=.1,total_seconds=1.5, **kwargs)

    def test_completed_worker_stdout_is_buffered(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = self.run_worker('''print('untrusted worker stdout')
out.update(result=value,code=0)
_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=_discovery_encode(out),phase='complete',complete=True))
''')
        self.assertEqual(stdout.getvalue(), '')
        self.assertTrue(result['normal'])
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['code'], 0)
        self.assertAlmostEqual(result['observation_deadline'] - result['started'], .8)
        self.assertAlmostEqual(result['cleanup_deadline'] - result['started'], 1.2)
        self.assertLessEqual(result['publication_deadline'] - result['cleanup_finished'], .100001)
        self.assertLessEqual(result['publication_deadline'] - result['started'], 1.300001)
        self.assertLessEqual(result['final_deadline'] - result['publication_deadline'], .100001)

    def test_normal_logical_three_propagates_exactly(self):
        result = self.run_worker('''value['assignment_incomplete']=True
out.update(result=value,code=3)
_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=_discovery_encode(out),phase='complete',complete=True))
raise SystemExit(3)
''')
        self.assertTrue(result['normal'])
        self.assertEqual(result['code'], 3)
        self.assertIsNone(result['value']['read_incomplete'])

    def test_missing_malformed_foreign_and_crashed_workers_refuse_credit(self):
        for body in ["raise SystemExit(7)", "Path(p['path']).write_text('{partial')",
            "p['binding']['worker']['started_ticks']+=1\n_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=out,phase='complete',complete=True))",
            "obs['inbound_complete']='true'\nout.update(result=value,code=0)\n_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=out,phase='complete',complete=True))"]:
            with self.subTest(body=body):
                result = self.run_worker(body)
                self.assertFalse(result['normal'])
                self.assertEqual(result['code'],3)
                self.assertIsNotNone(result['value']['read_incomplete'])
                self.assertIsNone(result['observation'])

    def test_cleanup_failure_refuses_even_completed_terminal(self):
        from cs import operator_dossier
        actual = operator_dossier._stop
        def failed(*args):
            actual(*args)
            return False
        with patch.object(operator_dossier, '_stop', side_effect=failed):
            result = self.run_worker("out.update(result=value,code=0)\n_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=out,phase='complete',complete=True))")
        self.assertFalse(result['normal'])
        self.assertFalse(result['cleanup_complete'])

    def test_real_owned_stall_keeps_bystander_alive(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory)/'owned.json'
            bystander = subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(10)'])
            try:
                started = time.monotonic()
                result = self.run_worker(f'''child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(10)'])
Path({str(receipt)!r}).write_text(json.dumps([os.getpid(),child.pid]))
_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=out,phase='inbound discovery',complete=False))
time.sleep(10)
''')
                self.assertLess(time.monotonic()-started,1.8)
                self.assertFalse(result['normal'])
                self.assertIsNone(bystander.poll())
                for pid in json.loads(receipt.read_text()):
                    path=Path('/proc')/str(pid)/'stat'
                    if path.exists():
                        self.assertEqual(path.read_text().rsplit(')',1)[1].split()[0],'Z')
            finally:
                bystander.kill()
                bystander.wait(timeout=2)

    def test_pid_mismatch_never_signals_other_identity(self):
        from cs.operator_dossier import _stop
        proc=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(10)'],start_new_session=True)
        try:
            stamp=identity(proc.pid)[0]
            stamp['started_ticks']+=1
            self.assertFalse(_stop(proc,stamp,time.monotonic()+.1))
            self.assertIsNone(proc.poll())
        finally:
            proc.kill()
            proc.wait(timeout=2)

    def test_canonical_scheduled_dispatch_precedes_config(self):
        argv=['unanswered','--days','14','--json','--all-buckets']
        with patch.dict(os.environ,{'CS_OPERATOR_HEALTH_CONTEXT':'{"workset_enabled":true}'}), \
             patch.object(cli.config,'load',side_effect=AssertionError('early config load')), \
             patch.object(unanswered,'scheduled_command',return_value=3) as command:
            self.assertEqual(cli.main(argv),3)
            command.assert_called_once_with()


    def test_exact_owned_withdrawal_and_foreign_preservation(self):
        for foreign in ('none', 'replacement', 'update', 'unproven', 'expired'):
            with self.subTest(foreign=foreign), tempfile.TemporaryDirectory() as directory:
                directory=Path(directory)
                expected={name: ('fixture-'+name).encode() for name in unanswered._PUBLICATION_PATHS}
                for name, raw in expected.items():
                    path=directory/name
                    path.write_bytes(raw)
                    path.chmod(0o600)
                cursor=directory/'cursor.json'
                cursor.write_bytes(b'preexisting foreign cursor')
                before_cursor=cursor.stat()
                snapshots=unanswered._publication_snapshot(directory,expected)
                info=directory.stat()
                target=directory/'inventory-view-progress.json'
                if foreign=='replacement':
                    new=directory/'foreign'
                    new.write_bytes(expected[target.name])
                    new.chmod(0o600)
                    new.replace(target)
                if foreign=='update':
                    target.write_bytes(b'foreign update')
                before=target.read_bytes()
                contained=unanswered._publication_withdraw(directory,(info.st_dev,info.st_ino),expected,
                    snapshots,time.monotonic()+(-1 if foreign=='expired' else 1),
                    exclusive_writer=foreign!='unproven')
                self.assertEqual(contained,foreign=='none')
                if foreign!='none':
                    self.assertEqual(target.read_bytes(),before)
                self.assertEqual(cursor.read_bytes(),b'preexisting foreign cursor')
                self.assertEqual(cursor.stat().st_ino,before_cursor.st_ino)
                self.assertEqual(cursor.stat().st_mtime_ns,before_cursor.st_mtime_ns)

    def test_partial_publication_is_not_owned(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            path=directory/'discovery.json'
            path.write_bytes(b'{partial')
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                unanswered._publication_snapshot(directory,{'discovery.json':b'complete expected'})
            self.assertEqual(path.read_bytes(),b'{partial')

    def test_production_worker_standard_loader_and_complete_empty_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap=Path(directory)/'worker.py'
            bootstrap.write_text("""import os,sys
from unittest.mock import MagicMock
from cs import unanswered,config,gmail_archive,engine_view,task_assignment
settings=config.Settings(_env_file=None,engine_owner_uid='local-owner')
config.load=lambda:settings
gmail_archive.inbound_recent=lambda *a:[]
gmail_archive.sent_recent=lambda *a:[]
engine_view.classify=lambda *a,**kw:({},None)
engine_view.settled=lambda *a,**kw:({},None)
task_assignment.projections=lambda *a,**kw:{}
import cs.state,cs.operational_fixture
state=MagicMock()
state.do_not_contact_set.return_value=set()
state.handled_out_of_band.return_value={}
state.escalated_to_human.return_value={}
cs.state.State=lambda *a:state
cs.operational_fixture.admit_originals=lambda settings,rows,own,**kw:(rows,own)
sys.argv=['cs.unanswered','--worker',sys.argv[1]]
raise SystemExit(unanswered._discovery_main())
""")
            result=unanswered._scheduled_discovery(worker_command=lambda fd:
                [sys.executable,'-B',str(bootstrap),str(fd)],observation_seconds=2,
                cleanup_seconds=.5,publication_seconds=.1,final_seconds=.1,total_seconds=3)
            self.assertTrue(result['normal'])
            self.assertTrue(result['cleanup_complete'])
            self.assertEqual(result['value']['open'],[])
            self.assertFalse(result['value']['assignment_incomplete'])
            self.assertIsNone(result['value']['read_incomplete'])
            self.assertEqual(result['configuration']['owner_uid'],'local-owner')
            source=bootstrap.read_text().replace('import os,sys', 'import os,sys,time\nfrom datetime import datetime,timezone')
            source=source.replace('gmail_archive.inbound_recent=lambda *a:[]',
                "gmail_archive.inbound_recent=lambda *a:[dict(email='person@example.test',thread_key='<one@example.test>',date=datetime.now(timezone.utc),subject='retained')]")
            source=source.replace('task_assignment.projections=lambda *a,**kw:{}',
                "def projections(settings,roots,**kwargs):\n while time.monotonic()<kwargs['deadline']:time.sleep(.005)\n return {root:task_assignment._unknown(root,'cooperative local cutoff') for root in roots}\ntask_assignment.projections=projections")
            bootstrap.write_text(source)
            result=unanswered._scheduled_discovery(worker_command=lambda fd:
                [sys.executable,'-B',str(bootstrap),str(fd)],observation_seconds=2,
                cleanup_seconds=.5,publication_seconds=.1,final_seconds=.1,total_seconds=3)
            self.assertTrue(result['normal'])
            self.assertEqual(result['code'],3)
            self.assertIsNone(result['value']['read_incomplete'])
            self.assertEqual(result['value']['human_work'][0]['thread_key'],'<one@example.test>')
            observed=result['observation']
            self.assertTrue(observed['inbound_complete'])
            self.assertTrue(observed['sent_complete'])
            self.assertEqual(observed['roots'],['<one@example.test>'])
            self.assertEqual(set(observed['assignment']),set(observed['roots']))
            self.assertIsInstance(observed['inbound'][0]['date'],datetime)
            self.assertFalse(observed['assignment']['<one@example.test>']['complete'])

    def test_worker_failure_never_calls_publication(self):
        result={'normal':False}
        with patch.object(unanswered,'_scheduled_discovery',return_value=result), \
             patch.object(unanswered,'_publish_discovery',side_effect=AssertionError('publication ran')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(unanswered.scheduled_command(),3)
        self.assertIsNotNone(json.loads(output.getvalue())['read_incomplete'])

    def test_initial_configuration_stall_is_inside_owned_budget(self):
        code="""import sys,time
from cs import unanswered,config
config.load=lambda:time.sleep(10)
sys.argv=['cs.unanswered','--worker',sys.argv[1]]
raise SystemExit(unanswered._discovery_main())
"""
        started=time.monotonic()
        result=unanswered._scheduled_discovery(worker_command=lambda fd:
            [sys.executable,'-B','-c',code,str(fd)],observation_seconds=.4,
            cleanup_seconds=.3,publication_seconds=.1,final_seconds=.1,total_seconds=1)
        self.assertLess(time.monotonic()-started,1.1)
        self.assertFalse(result['normal'])
        self.assertTrue(result['cleanup_complete'])
        self.assertIsNotNone(result['value']['read_incomplete'])

    def test_sent_failure_retains_completed_inbound_provenance(self):
        settings,inbound,state=self.fixture()
        saved=[]
        with patch.object(gmail_archive,'inbound_recent',return_value=inbound), \
             patch.object(gmail_archive,'sent_recent',side_effect=gmail_archive.ChunkFetchFailed('local failed chunk')), \
             patch('cs.state.State',return_value=state), \
             patch('cs.operational_fixture.admit_originals',side_effect=lambda settings,rows,own,**kw:(rows,own)), \
             patch.object(engine_view,'classify',return_value=({},None)), \
             patch.object(engine_view,'settled',return_value=({},None)), \
             patch.object(task_assignment,'projections',side_effect=lambda s,roots,**kw:
                 {root:task_assignment._unknown(root,'unavailable') for root in roots}):
            value=unanswered.sweep(settings,14,deadline=time.monotonic()+5,
                checkpoint=lambda out,phase:saved.append(unanswered._discovery_decode(unanswered._discovery_encode(out))))
        self.assertEqual(saved[-1]['inbound'],inbound)
        self.assertFalse(saved[-1]['sent_complete'])
        self.assertIsNotNone(value['read_incomplete'])
        self.assertEqual(value['human_work'][0]['last_inbound_date'],inbound[0]['date'])

    def test_real_directory_lock_contender_refuses_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            directory.chmod(0o700)
            code="""import sys
from pathlib import Path
from cs.unanswered import _publication_lock
try:
 with _publication_lock(Path(sys.argv[1])):raise SystemExit(9)
except BlockingIOError:raise SystemExit(0)
"""
            with unanswered._publication_lock(directory):
                result=subprocess.run([sys.executable,'-B','-c',code,str(directory)],capture_output=True,text=True,timeout=2)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(list(directory.iterdir()),[])

    def test_cooperative_projection_cutoff_allows_held_terminal_render(self):
        settings,inbound,state=self.fixture()
        clock=[0.0]
        calls=[]
        def projected(settings,roots,**kwargs):
            self.assertEqual(kwargs['deadline'],5)
            clock[0]=5
            calls.append('project')
            return {root:task_assignment._unknown(root,'cooperative deadline') for root in roots}
        with patch.object(unanswered.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(gmail_archive,'inbound_recent',return_value=inbound), \
             patch.object(gmail_archive,'sent_recent',return_value=[]), \
             patch('cs.state.State',return_value=state), \
             patch('cs.operational_fixture.admit_originals',side_effect=lambda s,rows,own,**kw:(rows,own)), \
             patch.object(engine_view,'classify',return_value=({},None)), \
             patch.object(engine_view,'settled',return_value=({},None)), \
             patch.object(task_assignment,'projections',side_effect=projected):
            value=unanswered.sweep(settings,14,deadline=5,completion_deadline=6,checkpoint=lambda *a:None)
        self.assertEqual(calls,['project'])
        self.assertTrue(value['assignment_incomplete'])
        self.assertIsNone(value['read_incomplete'])
        self.assertEqual(value['human_work'][0]['thread_key'],'<one@example.test>')

    def test_actual_health_publication_and_each_partial_failure_contained(self):
        from cs import operator_health,operator_inventory_view as view,operator_inventory_material as material,operator_workset
        from cs.config import Settings
        for failed in ('none','discovery','view','envelope','progress','overrun'):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as directory:
                directory=Path(directory)
                directory.chmod(0o700)
                parent=identity(os.getppid())[1]
                context={'nonce':'f'*32,'owner_uid':'local-owner','supervisor':identity(parent)[0],
                         'directory':str(directory),'workset_enabled':True}
                settings=Settings(_env_file=None,engine_owner_uid='local-owner')
                value={name:[] for name in ('open','handled','escalated','human_work','assignment_audit',
                    'operational_fixture_discovery','resumed','automatic','courtesy')}
                value.update(assignment_incomplete=False,read_incomplete=None,note=None,crm_note=None)
                result={'normal':True,'cleanup_complete':True,'configuration':unanswered._discovery_configuration(settings),
                    'value':value,'code':0,'publication_deadline':time.monotonic()+4,'final_deadline':time.monotonic()+5}
                original_capture=operator_health.capture
                original_exclusive=view.exclusive
                actual_clock=time.monotonic
                clock=[None]
                def capture(*args):
                    if failed=='discovery':
                        with patch.object(view,'capture',side_effect=OSError('simulated after discovery')):
                            original_capture(*args)
                        raise OSError('simulated capture failure')
                    capture_path=original_capture(*args)
                    if failed=='progress':
                        raise OSError('simulated after complete publication')
                    if failed=='overrun':
                        clock[0]=result['publication_deadline']+.01
                    return capture_path
                def exclusive(path,raw):
                    original_exclusive(path,raw)
                    match={'view':'inventory-view.jsonl','envelope':'inventory-view-envelope.json','progress':'inventory-view-progress.json'}
                    if failed in match and path.name==match[failed]:
                        raise OSError('simulated after artifact')
                with patch.dict(os.environ,{'CS_OPERATOR_HEALTH_CONTEXT':json.dumps(context),'CS_OPERATOR_ACCEPTANCE_RECEIPT':''}), \
                     patch.object(sys,'argv',['cs',*operator_health.ARGV]), \
                     patch.object(cli.config,'load',return_value=settings), \
                     patch.object(operator_workset,'reserve',return_value={'complete':True,'limit':2,'selected':[],'deferred':[],'held':[]}), \
                     patch.object(view,'produce',return_value='fixture'), \
                     patch.object(material,'parse',side_effect=json.loads), \
                     patch.object(material,'load_sources',return_value=([],{})), \
                     patch.object(material,'append',side_effect=lambda text,records:text), \
                     patch.object(operator_health,'capture',side_effect=capture), \
                     patch.object(view,'exclusive',side_effect=exclusive), \
                     patch.object(unanswered.time,'monotonic',side_effect=lambda:actual_clock() if clock[0] is None else clock[0]):
                    if failed=='none':
                        text,code=unanswered._publish_discovery(result)
                        self.assertEqual(code,0)
                        self.assertIn('Ordinary discovery artifact:',text)
                        self.assertTrue((directory/'discovery.json').exists())
                    else:
                        with contextlib.redirect_stderr(io.StringIO()) as stderr:
                            with self.assertRaises(ValueError) as failure:
                                unanswered._publish_discovery(result)
                        self.assertIn('containment complete',stderr.getvalue())
                        if failed=='overrun':
                            self.assertGreater(clock[0],result['publication_deadline'])
                            self.assertIsInstance(failure.exception.__cause__,TimeoutError)
                        self.assertTrue(all(not (directory/name).exists() for name in unanswered._PUBLICATION_PATHS))

    def test_legacy_enabled_parent_uses_actual_fork_helper_with_simulated_native_record(self):
        from cs import operator_health,operator_inventory_view as view,operator_inventory_material as material,operator_workset
        from cs import operator_discovery_receipt as legacy
        from cs.config import Settings
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            run=directory/'run'
            run.mkdir(mode=0o700)
            ancestry=[]
            pid=os.getpid()
            for unused in range(32):
                try:
                    row=legacy.proc(pid)
                except PermissionError:
                    stamp,parent=identity(pid)
                    row={**stamp,'ppid':parent,'argv':['simulated-inaccessible-ancestor'],'executable':'/simulated'}
                ancestry.append(row)
                if row['ppid']==0:break
                pid=row['ppid']
            self.assertGreaterEqual(len(ancestry),4)
            supervisor={key:ancestry[-1][key] for key in ('pid','started_ticks')}
            context={'nonce':'a'*32,'owner_uid':'local-owner','supervisor':supervisor,
                'directory':str(run),'workset_enabled':True}
            settings=Settings(_env_file=None,engine_owner_uid='local-owner')
            value={key:[] for key in ('open','handled','escalated','human_work','assignment_audit',
                'operational_fixture_discovery','resumed','automatic','courtesy')}
            value.update(assignment_incomplete=False,read_incomplete=None,note=None,crm_note=None)
            result={'normal':True,'cleanup_complete':True,'configuration':unanswered._discovery_configuration(settings),
                'value':value,'code':0,'publication_deadline':time.monotonic()+4,'final_deadline':time.monotonic()+5}
            def simulated_record(output,value,code,owner,cli_pid,deadline,status_fd,business):
                destination=legacy.directory_path()
                stamp={key:ancestry[0][key] for key in ('pid','started_ticks')}
                record={'nonce':'b'*32,'owner_uid':owner,'argv':operator_health.ARGV,
                    'cli_identity':stamp,'supervisor_identity':supervisor,
                    'native_identity':{key:ancestry[2][key] for key in ('pid','started_ticks')},
                    'kernel_source_digest':legacy.package_digest(),'output':output.decode(),
                    'output_length':len(output),'output_sha256':legacy.sha(output),'exit_code':code,
                    'discovery':json.loads(output),'ancestry':ancestry,'wrapper':{'simulated':True},
                    'claude_sha256':legacy.CLAUDE_SHA256,'claude_version':legacy.CLAUDE_VERSION,
                    'capture_worker_identity':identity(os.getpid())[0]}
                target=destination/(str(stamp['pid'])+'-'+str(stamp['started_ticks'])+'.json')
                target.write_text(json.dumps(record))
                target.chmod(0o600)
            env={'CS_OPERATOR_HEALTH_CONTEXT':json.dumps(context),'CS_OPERATOR_ACCEPTANCE_RECEIPT':str(directory/'receipt.json'),
                 'CS_OPERATOR_ACCEPTANCE_NONCE':'b'*32,'CS_OPERATOR_DISCOVERY_SUPERVISOR':json.dumps(supervisor)}
            with patch.dict(os.environ,env), patch.object(sys,'argv',['cs',*operator_health.ARGV]), \
                 patch.object(cli.config,'load',return_value=settings), \
                 patch.object(operator_workset,'reserve',return_value={'complete':True,'limit':2,'selected':[],'deferred':[],'held':[]}), \
                 patch.object(view,'produce',return_value='fixture'), \
                 patch.object(material,'parse',side_effect=json.loads), \
                 patch.object(material,'load_sources',return_value=([],{})), \
                 patch.object(material,'append',side_effect=lambda text,records:text), \
                 patch.object(legacy,'_capture',side_effect=simulated_record), \
                 patch.object(legacy,'extract_wrapper',return_value={'simulated':True}):
                text,code=unanswered._publish_discovery(result)
                final=legacy.directory_path()/(str(os.getpid())+'-'+str(identity(os.getpid())[0]['started_ticks'])+'.json')
                record=json.loads(final.read_text())
                self.assertEqual(code,0)
                self.assertNotIn('Ordinary discovery artifact:',text)
                self.assertEqual(json.loads(text),record['discovery'])
                self.assertFalse(Path('/proc',str(record['capture_worker_identity']['pid'])).exists())
                raw_final=final.read_bytes()
                original_legacy_capture=legacy.capture
                for path in [*(run/name for name in unanswered._PUBLICATION_PATHS), final]:
                    path.unlink()
                result.update(publication_deadline=time.monotonic()+4,final_deadline=time.monotonic()+5)
                def raised_after_final(*args):
                    original_legacy_capture(*args)
                    raise OSError('simulated after legacy final publication')
                with patch.object(legacy,'capture',side_effect=raised_after_final), \
                     contextlib.redirect_stderr(io.StringIO()) as stderr:
                    with self.assertRaises(ValueError):
                        unanswered._publish_discovery(result)
                self.assertIn('containment complete',stderr.getvalue())
                self.assertFalse(final.exists())
                self.assertTrue(all(not (run/name).exists() for name in unanswered._PUBLICATION_PATHS))
                result.update(publication_deadline=time.monotonic()+4,final_deadline=time.monotonic()+5)
                with patch.object(legacy,'capture',return_value=None), \
                     contextlib.redirect_stderr(io.StringIO()) as stderr:
                    with self.assertRaises(ValueError):
                        unanswered._publish_discovery(result)
                self.assertIn('containment complete',stderr.getvalue())
                self.assertTrue(all(not (run/name).exists() for name in unanswered._PUBLICATION_PATHS))
                final.write_bytes(raw_final)
                final.chmod(0o600)
                metadata=final.stat()
                with patch.object(operator_workset,'reserve',side_effect=AssertionError('preexisting target mutated')):
                    with self.assertRaises(ValueError):
                        unanswered._publish_discovery(result)
                self.assertEqual(final.read_bytes(),raw_final)
                self.assertEqual(final.stat().st_ino,metadata.st_ino)
                self.assertEqual(final.stat().st_mtime_ns,metadata.st_mtime_ns)

    @contextlib.contextmanager
    def reservation_publication_fixture(self):
        import copy
        from test_operator_workset_cli import CliWorksetTests
        from cs import operator_health,operator_inventory_view as view,operator_inventory_material as material,operator_workset
        fixture=CliWorksetTests('test_custom_prompt_context_keeps_its_independent_scope')
        fixture.setUp()
        try:
            fixture.context['supervisor']=identity(identity(os.getppid())[1])[0]
            discovery=copy.deepcopy(fixture.discovery)
            discovery.update(automatic=[],courtesy=[],crm_note=None,note=None,operational_fixture_discovery=[])
            result={'normal':True,'cleanup_complete':True,'configuration':unanswered._discovery_configuration(fixture.settings),
                'value':copy.deepcopy(discovery),'code':0,'publication_deadline':time.monotonic()+4,'final_deadline':time.monotonic()+5}
            with patch.dict(os.environ,{'CS_OPERATOR_HEALTH_CONTEXT':json.dumps(fixture.context),'CS_OPERATOR_ACCEPTANCE_RECEIPT':''}), \
                 patch.object(sys,'argv',['cs',*operator_health.ARGV]), \
                 patch.object(view,'produce',return_value='fixture'), \
                 patch.object(material,'parse',side_effect=json.loads), \
                 patch.object(material,'load_sources',return_value=([],{})), \
                 patch.object(material,'append',side_effect=lambda text,records:text):
                operator_workset.observe(fixture.settings,'tasks',[])
                operator_workset.observe(fixture.settings,'review',{'drafts':[]})
                yield fixture,discovery,result,operator_workset
        finally:
            fixture.tearDown()

    def test_actual_same_nonce_reservation_reentry_before_parent_publication(self):
        with self.reservation_publication_fixture() as (fixture,discovery,result,workset):
            first=workset.reserve(fixture.settings,discovery)
            cursor=fixture.settings.state_dir/'operator-workset'/'cursor.json'
            before=cursor.read_bytes(),cursor.stat().st_mtime_ns
            marker=fixture.directory/'workset-reserved.json'
            marker_before=marker.read_bytes(),marker.stat().st_mtime_ns
            text,code=unanswered._publish_discovery(result)
            self.assertEqual(code,0)
            self.assertEqual(result['value']['triage_workset'],first)
            self.assertEqual((cursor.read_bytes(),cursor.stat().st_mtime_ns),before)
            self.assertEqual((marker.read_bytes(),marker.stat().st_mtime_ns),marker_before)

    def test_foreign_cursor_update_before_deferred_parent_publication_is_preserved(self):
        import copy
        with self.reservation_publication_fixture() as (fixture,discovery,result,workset):
            workset.reserve(fixture.settings,discovery)
            cursor=fixture.settings.state_dir/'operator-workset'/'cursor.json'
            foreign=json.loads(cursor.read_text())
            foreign['order']+=1
            foreign['runs']['f'*64]={'digest':'c'*64,'selected':[],'contacts':[]}
            cursor.write_bytes(workset._encode(foreign))
            before=cursor.read_bytes(),cursor.stat().st_mtime_ns
            with patch.object(unanswered,'_scheduled_discovery',return_value=result),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(unanswered.scheduled_command(),0)
            self.assertEqual((cursor.read_bytes(),cursor.stat().st_mtime_ns),before)
            self.assertEqual(json.loads(cursor.read_text())['runs']['f'*64],foreign['runs']['f'*64])

    def test_cursor_replaced_then_marker_failure_never_captures_or_retries(self):
        from cs import operator_health
        with self.reservation_publication_fixture() as (fixture,discovery,result,workset):
            actual=workset._write_new
            writes=[]
            def fail_marker(path,value):
                writes.append(path.name)
                if path.name=='workset-reserved.json':raise OSError('simulated marker failure')
                return actual(path,value)
            with patch.object(workset,'_write_new',side_effect=fail_marker), \
                 patch.object(operator_health,'capture',side_effect=AssertionError('capture after failed reserve')), \
                 patch.object(unanswered,'_scheduled_discovery',return_value=result),contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(unanswered.scheduled_command(),3)
            cursor=fixture.settings.state_dir/'operator-workset'/'cursor.json'
            self.assertTrue(cursor.exists())
            self.assertIn(workset._hash(fixture.context['nonce']),json.loads(cursor.read_text())['runs'])
            self.assertEqual(writes.count('workset-reserved.json'),1)
            self.assertFalse((fixture.directory/'discovery.json').exists())
            self.assertFalse((fixture.directory/'workset-reserved.json').exists())
            self.assertIsNotNone(json.loads(stdout.getvalue())['read_incomplete'])

    def test_cleanup_failure_leaves_actual_preexisting_cursor_and_marker_exact(self):
        with self.reservation_publication_fixture() as (fixture,discovery,result,workset):
            workset.reserve(fixture.settings,discovery)
            paths=[fixture.settings.state_dir/'operator-workset'/'cursor.json',fixture.directory/'workset-reserved.json']
            before={path:(path.read_bytes(),path.stat().st_ino,path.stat().st_mtime_ns) for path in paths}
            result.update(normal=False,cleanup_complete=False)
            with patch.object(unanswered,'_scheduled_discovery',return_value=result),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(unanswered.scheduled_command(),3)
            self.assertEqual({path:(path.read_bytes(),path.stat().st_ino,path.stat().st_mtime_ns) for path in paths},before)

    def test_rich_bucket_scheduled_and_unscheduled_sweep_are_exactly_equal(self):
        from datetime import timedelta
        from assignment_fixture import normal_projection
        settings,inbound,state=self.fixture()
        now=inbound[0]['date']
        names=['open','handled','escalated','resumed','automatic','courtesy','closed','later','held']
        inbound=[dict(email=name+'@example.test',name=name,thread_key='<'+name+'@example.test>',date=now,
            subject=name,message_id='<message-'+name+'@example.test>') for name in names]
        sent=[dict(to=[name+'@example.test'],thread_key='<'+name+'@example.test>',date=now-timedelta(days=1))
            for name in ['resumed','courtesy']]
        state.handled_out_of_band.return_value={'handled@example.test':{'handled_at':now,'reason':'handled'}}
        state.escalated_to_human.return_value={'escalated@example.test':{'escalated_at':now,'owner':'human','reason':'active'}}
        auto=SimpleNamespace(is_auto=lambda date:True)
        settled=SimpleNamespace(needs_reply=lambda date:False,reason='finished')
        def project(settings,roots,**kwargs):
            projections={root:normal_projection(settings,{'thread_key':root}) for root in roots}
            projections['<closed@example.test>'].update(state='closed',covered_message_ids=['<message-closed@example.test>'])
            projections['<later@example.test>'].update(state='later-inbound')
            projections['<held@example.test>']=task_assignment._unknown('<held@example.test>','simulated unavailable peer')
            return projections
        with patch.object(gmail_archive,'inbound_recent',return_value=inbound),patch.object(gmail_archive,'sent_recent',return_value=sent), \
             patch('cs.state.State',return_value=state),patch('cs.operational_fixture.admit_originals',side_effect=lambda s,rows,own,**kw:(rows,own)), \
             patch.object(engine_view,'classify',return_value=({'<automatic@example.test>':auto},None)), \
             patch.object(engine_view,'settled',return_value=({'<courtesy@example.test>':settled},None)), \
             patch.object(task_assignment,'projections',side_effect=project):
            baseline=unanswered.sweep(settings,14)
            scheduled=unanswered.sweep(settings,14,deadline=time.monotonic()+5,completion_deadline=time.monotonic()+6,checkpoint=lambda *a:None)
        self.assertEqual(scheduled,baseline)
        for bucket in ['open','handled','escalated','resumed','automatic','courtesy','assignment_audit','human_work']:
            self.assertTrue(scheduled[bucket],bucket)

    def test_real_mime_header_subclasses_survive_inbound_and_atomic_checkpoint(self):
        from email.message import EmailMessage
        from email.policy import SMTP
        from email.utils import format_datetime
        from cs.config import Settings
        from cs import review
        instant=datetime.now(timezone.utc).replace(microsecond=0)
        message=EmailMessage(policy=SMTP)
        message['From']='Customer <customer@example.test>'
        message['To']='owner@example.test'
        message['Date']=format_datetime(instant)
        message['Subject']='Caffè, città — preventivo € e 日本語'
        message['Message-ID']='<mime-source@example.test>'
        message['References']='<mime-root@example.test>'
        message.set_content('Retained MIME body; the production reader uses header fields only.')
        raw=message.as_bytes()
        class Imap:
            def list(self):return 'OK',[b'(\\All) "/" "[Gmail]/All Mail"']
            def select(self,*args,**kwargs):return 'OK',[b'1']
            def response(self,*args):return 'UIDVALIDITY',[b'42']
            def uid(self,method,*args):
                if method=='SEARCH':return 'OK',[b'17']
                if method=='FETCH':return 'OK',[(b'1 (UID 17 BODY[HEADER.FIELDS])',raw)]
                raise AssertionError(method)
            def logout(self):return 'BYE',[]
        headers=gmail_archive._fetch_headers(Imap(),[b'17'],provider_identity=True)
        self.assertIsInstance(headers[0]['Subject'],str)
        self.assertIsNot(type(headers[0]['Subject']),str)
        self.assertIsInstance(headers[0]['Message-ID'],str)
        self.assertIsNot(type(headers[0]['Message-ID']),str)
        settings=Settings(_env_file=None,engine_owner_uid='mime-owner',email_address='owner@example.test')
        with patch.object(gmail_archive,'_imap',return_value=Imap()):
            rows=gmail_archive.inbound_recent(settings,14)
        self.assertEqual(len(rows),1)
        original=json.dumps(rows,ensure_ascii=False,sort_keys=True,default=str)
        encoded=unanswered._discovery_encode(rows)
        self.assertIs(type(encoded[0]['subject']),str)
        self.assertIs(type(encoded[0]['message_id']),str)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'checkpoint.json'
            binding={'attempt':'local-raw-MIME-fixture','worker':identity(os.getpid())[0]}
            review._save_checkpoint(path,{'binding':binding,'out':{'rows':encoded},'phase':'inbound discovered','complete':False})
            record=review._read_checkpoint(path,binding)
            restored=unanswered._discovery_decode(record['out']['rows'])
        self.assertEqual(json.dumps(restored,ensure_ascii=False,sort_keys=True,default=str),original)
        self.assertEqual(restored[0]['subject'],'Caffè, città — preventivo € e 日本語')
        self.assertEqual(restored[0]['message_id'],'<mime-source@example.test>')
        self.assertEqual(restored[0]['thread_key'],'<mime-root@example.test>')
        self.assertEqual(restored[0]['date'],instant)
        self.assertEqual(restored[0]['provider_uid'],'17')
        self.assertEqual(restored[0]['provider_uidvalidity'],'42')



    def test_precapture_material_error_retains_source_cause_through_cli_fallback(self):
        from cs import operator_inventory_material as material
        with self.reservation_publication_fixture() as (fixture, discovery, result, workset):
            def invalid(*args):
                material.validate({'foreign': 'PRIVATE_SENTINEL'},
                    'workset-review.json:/payload/gmail_drafts/*')
            with patch.object(material, 'load_sources', side_effect=invalid), \
                 patch.object(unanswered, '_scheduled_discovery', return_value=result), \
                 contextlib.redirect_stdout(io.StringIO()) as output, \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(['unanswered', '--days', '14', '--json', '--all-buckets']), 3)
            self.assertTrue(json.loads(output.getvalue())['assignment_incomplete'])
            self.assertTrue(all(not (fixture.directory/name).exists() for name in unanswered._PUBLICATION_PATHS))
            events=[]
            for path in (fixture.settings.state_dir/'observability').rglob('events-*.jsonl'):
                events.extend(json.loads(line) for line in path.read_text().splitlines())
            failed=[row for row in events if row.get('stage')=='discovery' and row.get('status')=='failed']
            self.assertTrue(failed)
            row=failed[-1]
            self.assertEqual(row['causal']['cause'], 'material_unknown_field')
            self.assertEqual(row['method'], 'operator.discovery.material')
            self.assertTrue(row['causal']['facts']['gmail_draft_material'])
            self.assertEqual(row['error_file'], 'cs/operator_inventory_material.py')
            self.assertNotIn('PRIVATE_SENTINEL', json.dumps(failed))


if __name__ == '__main__':
    unittest.main()
