"""Command-local review supervision, using local fixtures only."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cs import cli, review, task_assignment, unanswered, gmail_archive, engine_view
from cs.config import Settings
from cs.operator_health import identity


class BudgetTests(unittest.TestCase):
    def test_production_lifecycle_envelope(self):
        self.assertEqual((review.WORK_SECONDS, review.CLEANUP_SECONDS, review.TOTAL_SECONDS), (2700, 10, 2715))
        self.assertEqual(review._supervise.__kwdefaults__["work_seconds"], 2700)
        self.assertEqual(review._supervise.__kwdefaults__["total_seconds"], 2715)
        self.assertEqual(task_assignment.PROJECTION_SECONDS, 3600)
        from cs import rpc_reads
        self.assertEqual((rpc_reads.ASSIGNMENT_REQUEST_SECONDS, rpc_reads.ASSIGNMENT_BATCH_SECONDS,
                          rpc_reads.CONCURRENCY, task_assignment.PER_ACCOUNT_CONCURRENCY), (150, 180, 4, 1))
        self.assertEqual(review.WORK_SECONDS, unanswered.DISCOVERY_SWEEP_SECONDS)
        self.assertLess(2715 + 2730 + 687, 6600)

    def settings(self):
        return Settings(_env_file=None, engine_owner_uid="budget-owner")

    def test_fake_clock_stage_deadlines_preserve_completed_data(self):
        for phase in ("Gmail draft listing", "draft reconcile", "assignment listing", "inbound discovery",
                      "inbound classification", "inbound settlement", "inbound assignment projection"):
            now = [0.0]
            checkpoints = []
            out = {"tasks": [{"id": "kept"}], "_known_roots": ["<one@test>", "<two@test>"]}
            token = review._CONTEXT.set({"deadline": 5, "out": out,
                "checkpoint": lambda data, stage: checkpoints.append(json.loads(json.dumps(data)))})
            try:
                with patch.object(review.time, 'monotonic', side_effect=lambda: now[0]):
                    with review._stage(phase):
                        now[0] = 6
                    with self.assertRaises(TimeoutError):
                        with review._stage("next"):
                            self.fail("expired stage ran")
            finally:
                review._CONTEXT.reset(token)
            result = review._incomplete(checkpoints[-1], phase)
            self.assertEqual(result['tasks'], [{'id': 'kept'}])
            self.assertEqual({r['thread_key'] for r in result['assignments']}, {'<one@test>', '<two@test>'})
            self.assertTrue(all(r['hold_auto_reply'] and not r['complete'] for r in result['assignments']))
            self.assertFalse(result['drafts_inventory']['complete'])

    def test_real_aggregation_fake_clock_at_every_late_seam(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        for stalled in ('gmail', 'reconcile', 'listing', 'discovery', 'classification', 'settlement', 'projection'):
            clock = [0.0]
            saved = []
            def delay(name, value):
                if name == stalled:
                    clock[0] = 6
                return value
            settings = SimpleNamespace(engine_owner_uid='owner', excluded_campaign_set=set(),
                db_path=Path('/unused'), timezone='UTC', log_path=Path('/missing-review-budget-log'),
                self_email_set=set(), email_address='owner@test', system_sender_set=set())
            state = MagicMock()
            state.escalated_to_human.return_value = {}
            state.handled_out_of_band.return_value = {}
            state.do_not_contact_set.return_value = set()
            inbound = [{'thread_key': '<inbound@test>', 'email': 'person@test',
                        'date': datetime.now(timezone.utc), 'subject': 'retained'}]
            def gmail(*args, observation):
                observation.update(version=1, complete=True, search_complete=True,
                                   expected_uids=[], observed_uids=[], uidvalidity='6')
                return delay('gmail', [])
            def rpc(settings, method, *args, **kwargs):
                if method == 'drafts.list':
                    return [{'id': 'raw-kept'}]
                if method == 'tasks.list':
                    return [{'id': 'task-kept', 'thread_key': '<task@test>'}]
                raise AssertionError(method)
            def projections(settings, roots, **kwargs):
                return delay('projection', {key: task_assignment._unknown(key, 'simulated') for key in roots})
            with patch.object(review.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(review.gmail_drafts, 'list_drafts', side_effect=gmail), \
                 patch.object(review.rpc, 'call_sync', side_effect=rpc), \
                 patch.object(review.draft_state, 'reconcile', side_effect=lambda *a, **kw: delay('reconcile', ([], []))), \
                 patch.object(review.campaign, 'list_campaigns', return_value=[]), \
                 patch('cs.state.State', return_value=state), \
                 patch.object(task_assignment, 'listing', side_effect=lambda *a: delay('listing', {'items': [{'thread_key': '<listed@test>'}]})), \
                 patch.object(task_assignment, 'projections', side_effect=projections), \
                 patch.object(gmail_archive, 'inbound_recent', side_effect=lambda *a: delay('discovery', inbound)), \
                 patch.object(gmail_archive, 'sent_recent', return_value=[]), \
                 patch('cs.operational_fixture.admit_originals', side_effect=lambda s, rows, own, **kw: (rows, own)), \
                 patch.object(engine_view, 'classify', side_effect=lambda *a, **kw: delay('classification', ({}, None))), \
                 patch.object(engine_view, 'settled', side_effect=lambda *a, **kw: delay('settlement', ({}, None))):
                try:
                    result = review._aggregate(settings, deadline=5, checkpoint=lambda out, phase:
                        saved.append(json.loads(json.dumps(out, default=str))))
                except TimeoutError:
                    result = saved[-1]
            self.assertTrue(saved)
            result = review._incomplete(result, stalled)
            self.assertFalse(result.get('drafts_inventory', {}).get('complete'))
            if stalled != 'gmail':
                self.assertEqual(result['engine_drafts'], [{'id': 'raw-kept'}])
            for root in result.get('_known_roots', []):
                self.assertIn(root, {row['thread_key'] for row in result['assignments']})

    def test_completed_inventory_and_projection_survive_later_failure(self):
        projection = {'thread_key': '<complete@test>', 'complete': True, 'hold_auto_reply': False}
        proof = {'version': 1, 'complete': True}
        out = dict(drafts_inventory=proof, drafts=[{'engine_id': 'kept'}], assignments=[projection],
                   _known_roots=['<complete@test>', '<deferred@test>'])
        result = review._incomplete(out, 'late timeout')
        self.assertIs(result['drafts_inventory'], proof)
        self.assertIs(result['assignments'][0], projection)
        self.assertTrue(result['assignments'][1]['hold_auto_reply'])
        self.assertNotIn('_known_roots', review._public(result))
        review._incomplete(out, 'cleanup failed', cleanup_complete=False)
        self.assertFalse(out['drafts_inventory']['complete'])

    def worker(self, behavior):
        code = '''import json,os,sys,time,subprocess
from pathlib import Path
from cs.review import _save_checkpoint
p=json.loads(sys.stdin.buffer.read())
''' + behavior
        return (sys.executable, '-B', '-c', code)

    def run_worker(self, behavior, **kwargs):
        with contextlib.redirect_stderr(io.StringIO()):
            return review._supervise(self.settings(), worker_command=self.worker(behavior),
                                     total_seconds=1.4, work_seconds=.6, cleanup_seconds=.3, **kwargs)

    def test_real_worker_checkpoint_and_stdout_containment(self):
        result = self.run_worker('''print("untrusted worker stdout")
_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out={'tasks':[{'id':'kept'}]},phase='complete',complete=True))
''')
        self.assertEqual(result, {'tasks': [{'id': 'kept'}], 'assignment_coverage': {'requested_order': [], 'roots': []}})
        self.assertIsInstance(json.loads(json.dumps(result)), dict)

    def test_real_crash_missing_malformed_and_foreign_binding_fail_closed(self):
        for behavior in ("raise SystemExit(7)", "Path(p['path']).write_text('{partial')",
                         "p['binding']['worker']['started_ticks']+=1\n_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out={'drafts_inventory':{'complete':True}},phase='complete',complete=True))",
                         "p['binding']['owner_uid']='foreign'\n_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out={},phase='complete',complete=True))"):
            with self.subTest(behavior=behavior):
                result = self.run_worker(behavior)
                self.assertFalse(result['drafts_inventory']['complete'])
                self.assertIn('review_incomplete', result)

    def test_real_stalled_owned_child_and_descendant_do_not_kill_bystander(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / 'pids'
            bystander = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(20)'],
                                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            try:
                started = time.monotonic()
                result = self.run_worker(f'''child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(20)'])
Path({str(receipt)!r}).write_text(json.dumps([os.getpid(),child.pid]))
_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out={{'tasks':[{{'id':'kept'}}],'_known_roots':['<known@test>']}},phase='inbound discovery',complete=False))
time.sleep(20)
''')
                self.assertLess(time.monotonic()-started, 2)
                self.assertEqual(result['tasks'], [{'id': 'kept'}])
                self.assertIsNone(bystander.poll())
                for pid in json.loads(receipt.read_text()):
                    path = Path(f'/proc/{pid}/stat')
                    if path.exists():
                        self.assertEqual(path.read_text().rsplit(')', 1)[1].split()[0], 'Z')
            finally:
                bystander.kill()
                bystander.wait(timeout=2)

    def test_cleanup_failure_invalidates_success(self):
        from cs import operator_dossier
        actual = operator_dossier._stop
        def failed(*args):
            actual(*args)
            return False
        with patch.object(operator_dossier, '_stop', side_effect=failed):
            result = self.run_worker("_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out={'drafts_inventory':{'complete':True}},phase='complete',complete=True))")
        self.assertFalse(result['drafts_inventory']['complete'])
        self.assertFalse(result['review_coverage']['cleanup_complete'])

    def test_pid_identity_mismatch_never_signals_foreign_process(self):
        from cs.operator_dossier import _stop
        proc = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(20)'],
                                start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        try:
            stamp = identity(proc.pid)[0]
            stamp['started_ticks'] += 1
            self.assertFalse(_stop(proc, stamp, time.monotonic()+.1))
            self.assertIsNone(proc.poll())
        finally:
            proc.kill()
            proc.wait(timeout=2)

    def test_production_worker_cli_deadline_rejects_draft_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            evidence = directory / 'scheduled'
            evidence.mkdir(mode=0o700)
            receipt = directory / 'owned.json'
            bootstrap = directory / 'worker.py'
            bootstrap.write_text(r'''
import json, os, subprocess, sys, time
from pathlib import Path
from cs import review, mailboxes
from cs.operator_health import identity

def gmail(settings, *, observation):
    observation.update(version=1, complete=True, search_complete=True,
                       expected_uids=['17'], observed_uids=['17'], uidvalidity='6')
    return [{'uid':'17', 'uidvalidity':'6', 'thread_key':'<gmail-known@test>',
             'to':'person@test', 'date':'Mon, 19 Oct 2026 00:00:00 +0000',
             'body':'Retained local draft', 'body_complete':True}]

def rpc(settings, method, params, **kwargs):
    if method == 'drafts.list':
        return [{'id':'engine-raw-kept', 'thread_id':'<engine-known@test>',
                 'to_addresses':['another@test'], 'created_at':'2026-10-19T00:00:00Z',
                 'body':'Retained engine draft'}]
    if method == 'emails.needs_reply':
        return {'threads':{}}
    raise AssertionError('unexpected read '+method)

def stall(*args, **kwargs):
    child = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(30)'])
    Path(os.environ['M1_OWNED_RECEIPT']).write_text(json.dumps({
        'worker':identity(os.getpid())[0], 'descendant':identity(child.pid)[0],
        'group':os.getpgrp(), 'stage':'draft reconciliation mailbox read'}))
    time.sleep(30)

review.gmail_drafts.list_drafts = gmail
review.rpc.call_sync = rpc
mailboxes.headers_since_across = stall
sys.argv = ['cs.review', '--worker']
raise SystemExit(review.main())
''')
            runner = r'''
import argparse, os, sys
from cs import cli, review
from cs.config import Settings
settings = Settings(_env_file=None, slug='budget-integration', engine_owner_uid='budget-owner')
cli.config.load = lambda: settings
review._supervise.__kwdefaults__.update(worker_command=(sys.executable,'-B',sys.argv[1]),
    total_seconds=3.5, work_seconds=2, cleanup_seconds=1)
raise SystemExit(cli.cmd_review(argparse.Namespace(json=True)))
'''
            context = dict(directory=str(evidence), nonce='b'*32, supervisor=identity(os.getpid())[0],
                           workset_enabled=True, owner_uid='budget-owner')
            env = dict(os.environ, HOME=str(directory), PYTHONDONTWRITEBYTECODE='1',
                       CS_OPERATOR_HEALTH_CONTEXT=json.dumps(context), M1_OWNED_RECEIPT=str(receipt))
            bystander = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(30)'], env=env)
            started = time.monotonic()
            try:
                result = subprocess.run([sys.executable, '-B', '-c', runner, str(bootstrap)],
                                        env=env, capture_output=True, text=True, timeout=7)
                artifact_directory = os.environ.get('M1_TEST_EVIDENCE_DIRECTORY')
                if artifact_directory:
                    artifacts = Path(artifact_directory)
                    artifacts.mkdir(parents=True, exist_ok=True)
                    (artifacts/'production-cli.stdout.json').write_text(result.stdout)
                    (artifacts/'production-cli.stderr.log').write_text(result.stderr)
                    (artifacts/'production-cli-receipt.json').write_text(json.dumps({
                        'exit':result.returncode, 'elapsed_seconds':time.monotonic()-started,
                        'argv':[sys.executable, '-B', '-c', runner, str(bootstrap)],
                        'owned':json.loads(receipt.read_text()), 'bystander_alive':bystander.poll() is None}, indent=2))
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertLess(time.monotonic()-started, 5)
                payload = json.loads(result.stdout)
                self.assertFalse(payload['drafts_inventory']['complete'])
                self.assertEqual(payload['gmail_drafts'][0]['uid'], '17')
                self.assertEqual(payload['engine_drafts'][0]['id'], 'engine-raw-kept')
                self.assertEqual(payload['review_coverage']['assignment_listing'], 'unknown')
                self.assertEqual(payload['review_coverage']['mailbox_discovery'], 'unknown')
                self.assertEqual(payload['review_coverage']['aggregation'], 'incomplete')
                held = {row['thread_key']:row for row in payload['assignments']}
                self.assertEqual(set(held), {'<gmail-known@test>', '<engine-known@test>'})
                self.assertTrue(all(row['hold_auto_reply'] and not row['complete'] for row in held.values()))
                failure = json.loads((evidence/'workset-review-failure.json').read_text())
                self.assertEqual((failure['reason'], failure['key']), ('review_inventory_incomplete', 'drafts_inventory'))
                self.assertFalse((evidence/'workset-review.json').exists())
                self.assertIn('draft reconcile: starting', result.stderr)
                self.assertIn('draft reconcile: incomplete', result.stderr)
                self.assertTrue(payload['review_incomplete'].endswith('during draft reconcile'))
                self.assertTrue(payload['review_coverage']['cleanup_complete'])
                self.assertIn('Scheduled workset observation incomplete', result.stderr)
                self.assertIsNone(bystander.poll())
                owned = json.loads(receipt.read_text())
                self.assertEqual(owned['worker']['pid'], owned['group'])
                for stamp in (owned['worker'], owned['descendant']):
                    path = Path('/proc')/str(stamp['pid'])/'stat'
                    if path.exists() and identity(stamp['pid'])[0] == stamp:
                        self.assertEqual(path.read_text().rsplit(')',1)[1].split()[0], 'Z')
                print('Production worker CLI interruption: exit 3; raw stores retained; both known roots held; observer rejected incomplete drafts; owned group has no live survivors; bystander alive.')
            finally:
                bystander.kill()
                bystander.wait(timeout=2)

    def test_actual_scheduled_observer_rejects_interrupted_drafts(self):
        from cs.operator_workset import observe, WorksetError
        with tempfile.TemporaryDirectory() as directory:
            context = dict(directory=directory, nonce='a'*32, supervisor=identity(os.getpid())[0],
                           workset_enabled=True, owner_uid='budget-owner')
            with patch.dict(os.environ, {'CS_OPERATOR_HEALTH_CONTEXT': json.dumps(context)}):
                with self.assertRaises(WorksetError):
                    observe(self.settings(), 'review', review._public(review._incomplete({}, 'draft timeout')))


class CumulativeTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_review_worker_healthy_cumulative_red_green(self):
        import asyncio
        import base64
        import websockets
        calls = []
        token = 'fixture.' + base64.urlsafe_b64encode(json.dumps({'exp': int(time.time()) + 3600}).encode()).decode().rstrip('=') + '.fixture'
        async def handler(ws):
            try:
                async for raw in ws:
                    frame = json.loads(raw)
                    calls.append(frame['params']['thread_key'])
                    await asyncio.sleep(.2)
                    await ws.send(json.dumps({'jsonrpc': '2.0', 'id': frame['id'], 'result': {'healthy': True}}))
            except websockets.ConnectionClosed:
                pass
        async with websockets.serve(handler, '127.0.0.1', 0) as server:
            selected = Settings(_env_file=None, engine_owner_uid='budget-owner',
                engine_ws_url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
            code = r"""import json,sys,time
from pathlib import Path
from cs import config,review,rpc_reads
p=json.load(sys.stdin)
rpc_reads.CLOSE_SECONDS=.01
s=config.Settings.model_validate(p['settings'])
out={'_known_roots':['<one@test>','<two@test>','<three@test>'],'tasks':[]}
review._save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=out,phase='reads',complete=False))
for root in out['_known_roots']:
    result=rpc_reads.read_many(s,'tasks.assignment.project',{root:{'thread_key':root}},
        request_timeout=1,batch_timeout=1,deadline=p['deadline'],token_cache={'budget-owner':TOKEN})[root]
    if result.error:raise RuntimeError('healthy inventory not completed')
    out['tasks'].append({'id':root})
    review._save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=out,phase='reads',complete=False))
review._save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=out,phase='complete',complete=True))
"""
            command = (sys.executable, '-B', '-c', 'TOKEN=' + repr(token) + '\n' + code)
            for allowance, complete in ((.65, False), (2.5, True)):
                calls.clear()
                result = await asyncio.to_thread(review._supervise, selected, worker_command=command,
                    work_seconds=allowance, cleanup_seconds=.3, total_seconds=allowance + .8)
                if complete:
                    self.assertNotIn('review_incomplete', result)
                    self.assertEqual([row['id'] for row in result['tasks']], ['<one@test>', '<two@test>', '<three@test>'])
                    self.assertEqual(calls, ['<one@test>', '<two@test>', '<three@test>'])
                else:
                    self.assertIn('review_incomplete', result)
                    self.assertTrue(all(row['hold_auto_reply'] for row in result['assignments']))
                    self.assertLess(len(result['tasks']), 3)


if __name__ == '__main__':
    unittest.main()
