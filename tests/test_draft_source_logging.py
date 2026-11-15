"""Source decisions through real preparation, ordinary logs and durable collection."""
import contextlib
import copy
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
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from cs import cli, config, gmail_archive, gmail_drafts, interactive_draft as draft, rpc
from cs import observability_causal as causal
from cs.monitor_config import Component, MonitorConfig
from cs.monitor_evaluate import initial_state, observe
from cs.observability import context, current_context, safe_metadata, store_for
from cs.observability_store import _validate_event
from cs.monitor_details import safe_detail
from test_contextual_email import settings
from test_interactive_draft_continuity import SOURCE, GMAIL, DRAFT, COPY, ROOT

CANARY = 'PRIVATE_SOURCE_CANARY_86741'


class SourceLogging(unittest.TestCase):
    def invoke(self, selected, source=None, provider=None, unknown=False, sink=False, policy=False):
        calls = []
        copies = []
        def call(s, method, params, timeout=None):
            calls.append(method)
            if method == 'system.capabilities':
                return {'exact_draft_publication': 1}
            if method == 'emails.list_by_thread':
                if unknown:
                    raise RuntimeError(CANARY)
                return {'emails': [source or SOURCE]}
            if method == 'drafts.list':
                return [] if calls.count(method) == 1 else [copy.deepcopy(DRAFT)]
            if method == 'drafts.inspect':
                return {'ok': True, 'draft': copy.deepcopy(DRAFT), 'expected_snapshot': 'native-snapshot'}
            if method == 'drafts.publish_review':
                append(s)
                return {'version': 1, 'ok': True, 'draft_id': DRAFT['id'],
                        'achieved_stages': ['engine-saved', 'review-visible'],
                        'cause': 'exact_copy_published', 'next_action': 'review-draft'}
            raise AssertionError(method)
        async def chat(*args, **kwargs):
            calls.append('chat')
            self.assertEqual(kwargs['allow_tools'], set())
            return {'result': {'response': 'Prepared'}}
        def read(s, addr, **kwargs):
            kwargs['observation']['inventory_complete'] = True
            return [provider or GMAIL]
        def inventory(s, *, observation):
            observation['complete'] = True
            return copies
        def append(s, **kwargs):
            calls.append('append')
            copies.append(copy.deepcopy(COPY))
            return 'Drafts', []
        stderr = io.StringIO()
        with contextlib.ExitStack() as stack:
            for target, method, effect in ((rpc, 'call_sync', call), (rpc, 'chat', chat),
                    (gmail_archive, 'thread_with', read), (gmail_drafts, 'list_drafts', inventory),
                    (gmail_drafts, 'append_draft', append)):
                stack.enter_context(patch.object(target, method, side_effect=effect))
            stack.enter_context(patch.object(config, 'load', return_value=selected))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            if sink:
                stack.enter_context(patch('cs.observability.EventStore.emit', side_effect=OSError(CANARY)))
            if policy:
                from cs import task_assignment
                stack.enter_context(patch.dict(os.environ, {'CS_OPERATOR_HEADLESS':'1'}))
                stack.enter_context(patch.object(cli, '_scheduled_workset_scope', return_value=True))
                stack.enter_context(patch.object(task_assignment, 'guard', side_effect=task_assignment.AssignmentUnavailable('Held')))
            rc = cli.main(['draft-reply', 'Answer', '--thread-id', ROOT, '--timeout', '10'])
        return rc, calls, stderr.getvalue()

    # Expected failure: the preparation reuses the caller's causal scope, so its source decision replaces the caller's selected cause.
    @unittest.expectedFailure
    def test_real_preparation_cli_collector_corpus(self):
        retained = os.environ.get('DRAFT_SOURCE_EVIDENCE_DIR')
        manager = contextlib.nullcontext(retained) if retained else tempfile.TemporaryDirectory()
        with manager as directory:
            base = Path(directory)
            base.mkdir(parents=True, exist_ok=True, mode=0o700)
            corpus = base/'corpus'; corpus.mkdir(exist_ok=True, mode=0o700)
            truth = base/'private-truth'; truth.mkdir(exist_ok=True, mode=0o700)
            cases = [
                ('tail', None, {**GMAIL, 'body': 'Please answer.\nOn Tuesday someone wrote:\n> old\n'+CANARY}, 'provider_authored_unquoted_tail'),
                ('unequal', None, {**GMAIL, 'body': 'Different request. '+CANARY}, 'source_body_different'),
                ('identity', None, {**GMAIL, 'subject': CANARY, 'body': 'On Tuesday someone wrote:\nunquoted'}, 'source_identity_uncorroborated'),
                ('fallback', {**SOURCE, 'body_plain': 'Please answer.\n-----Messaggio originale-----'},
                    {**GMAIL, 'body': 'Please answer.\n-----Messaggio originale-----\nDa: support@fixture.example\nInviato: Yesterday\nA: customer@example.test\nOggetto: old\n'+CANARY}, None),
                ('equal', None, None, None), ('policy', None, None, None),
                ('unknown', None, None, 'unknown'), ('sink', None, {**GMAIL, 'body': CANARY}, None),
            ]
            for case, source, provider, expected in cases:
                identity = uuid.uuid4().hex
                root = base/identity; root.mkdir(mode=0o700)
                manifest = root/'manifest.toml'
                manifest.write_text('[company]\nslug="fixture"\n[engine]\nowner_uid="fixture-owner"\n')
                env = {**os.environ, 'HOME': str(root), 'CS_MANIFEST': str(manifest),
                       'CS_ENGINE_OWNER_UID': 'fixture-owner', 'PYTHONPATH': str(Path.cwd()),
                       'CS_OPERATOR_HEADLESS':'', 'CS_HEADLESS_SEND':''}
                with patch.dict(os.environ, env):
                    selected = settings().model_copy(update={'slug':'fixture'})
                    store = store_for(selected)
                    with causal.scope():
                        parent = causal.decision('pause_state', 'paused', outcome='held')
                        rc, calls, stderr = self.invoke(selected, source, provider,
                            unknown=case=='unknown', sink=case=='sink', policy=case=='policy')
                        self.assertEqual(causal.selected(), parent)
                    self.assertIsNone(draft._SOURCE.get())
                    events = store.events(limit=200)['events']
                    terminals = [e for e in events if e['stage']=='generation' and e['status']=='held']
                    failures = [e for e in events if e.get('causal', {}).get('layer')=='source' and e['status']=='failed']
                    if expected:
                        self.assertEqual(rc, 3)
                        self.assertIn('; nothing generated', stderr)
                        self.assertNotIn('chat', calls)
                        self.assertNotIn('drafts.list', calls)
                        self.assertNotIn('append', calls)
                        self.assertEqual(len(failures), 1)
                        self.assertEqual(len(terminals), 1)
                        event = failures[0]; value = event['causal']
                        self.assertEqual(value['cause'], expected)
                        self.assertEqual(event['error_class'], 'RuntimeError' if case=='unknown' else 'ValueError')
                        if case != 'unknown':
                            self.assertEqual(event['error_file'], 'cs/interactive_draft.py')
                        self.assertEqual(event['level'], 'ERROR')
                        self.assertEqual(event['effect_certainty'], 'none')
                        self.assertEqual(safe_metadata({'causal': value})['causal'], value)
                        self.assertEqual(safe_detail({'causal': value})['causal'], value)
                        self.assertTrue(_validate_event(event, store))
                        if case=='identity':
                            self.assertEqual(value['facts'], {'body_comparison_performed': False, 'generation_started': False})
                        if case=='tail':
                            self.assertTrue(value['facts']['provider_parse_ambiguous'])
                            self.assertEqual(value['facts']['provider_authored_chars'], 0)
                        if case=='unequal':
                            self.assertFalse(value['facts']['provider_parse_ambiguous'])
                    else:
                        self.assertFalse(failures)
                        self.assertEqual(rc, 3 if case in {'policy','sink'} else 0)
                    trace_id = (failures or events)[-1]['trace_id'] if events else None
                    command = [sys.executable, '-m', 'cs', 'logs', 'trace', '--trace-id', trace_id or 'a'*32, '--local', '--json']
                    logs = subprocess.run(command, capture_output=True, text=True, env=env)
                    self.assertEqual(logs.returncode, 0, logs.stderr)
                    log_data = json.loads(logs.stdout)
                    if expected:
                        self.assertIn(value, [e.get('causal') for e in log_data['local']['events']])
                    cfg = MonitorConfig(mode='filesystem', clone_label='sample', scan_seconds=600,
                        monitor_id='a'*32, owner_uid='fixture-owner', state_dir=str(root/'monitor'),
                        expected_start_utc=int(time.time()), components=[Component(id='operator',kind='kernel',local_root=str(store.root))])
                    cfgpath = root/'monitor.json'; cfgpath.write_text(cfg.model_dump_json()); cfgpath.chmod(0o600)
                    command = [sys.executable, '-m', 'cs', 'monitor', 'once', '--config', str(cfgpath)]
                    result = subprocess.run(command, capture_output=True, text=True, env=env)
                    self.assertIn(result.returncode, (0, 1), result.stderr)
                    inbox = json.loads((root/'monitor'/'problems.json').read_text())
                    if expected:
                        problem = next(p for p in inbox['problems'] if p['evidence'].get('causal')==value)
                        self.assertEqual(problem['evidence']['event_id'], event['event_id'])
                        repeated = subprocess.run(command, capture_output=True, text=True, env=env)
                        self.assertEqual(repeated.returncode, 1, repeated.stderr)
                        again = json.loads((root/'monitor'/'problems.json').read_text())
                        self.assertTrue(any(p['id']==problem['id'] and p['evidence'].get('causal')==value for p in again['problems']))
                    if case=='tail':
                        with causal.scope():
                            supervisor=causal.decision('supervisor_completion','run_verified',layer='supervisor',outcome='accepted',method='operator.tick')
                        store.emit('launch','result',reason='none',method='operator.tick',root_id=ROOT,causal=supervisor)
                        subprocess.run(command,capture_output=True,text=True,env=env,check=False)
                        unchanged=json.loads((root/'monitor'/'problems.json').read_text())
                        self.assertTrue(any(p['id']==problem['id'] for p in unchanged['problems']))
                        self.assertEqual(self.invoke(selected)[0],0)
                        recovered=subprocess.run(command,capture_output=True,text=True,env=env)
                        self.assertEqual(recovered.returncode,0,recovered.stdout+recovered.stderr)
                        cleared=json.loads((root/'monitor'/'problems.json').read_text())
                        self.assertFalse(any(p['id']==problem['id'] for p in cleared['problems']))
                    artifact = {'logs':log_data, 'inbox':inbox}
                    self.assertNotIn(CANARY, json.dumps(artifact))
                    path=corpus/(identity+'.json'); path.write_text(json.dumps(artifact)); path.chmod(0o600)
                    key=truth/(identity+'.json'); key.write_text(json.dumps({'case':case,'expected_cause':expected,'return_code':rc,'calls':calls,'event_ids':[e['event_id'] for e in events]})); key.chmod(0o600)

    def test_post_comparison_mime_bound_preserves_actual_fact(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'HOME':directory,
                'CS_OPERATOR_HEADLESS':'', 'CS_HEADLESS_SEND':''}):
            selected = settings()
            provider = {**GMAIL, 'body_alternatives':[{'type':'text/html','body':'x'*65536}]}
            rc, calls, stderr = self.invoke(selected, provider=provider)
            self.assertEqual(rc, 3)
            self.assertIn('total 65536 character prompt bound', stderr)
            self.assertIn('; nothing generated', stderr)
            self.assertNotIn('chat', calls)
            self.assertNotIn('drafts.list', calls)
            self.assertNotIn('append', calls)
            events = store_for(selected).events(limit=100)['events']
            failure = next(e for e in events if e.get('causal',{}).get('layer')=='source')
            self.assertEqual(failure['causal']['cause'], 'unknown')
            self.assertEqual(failure['causal']['facts'],
                {'body_comparison_performed':True, 'generation_started':False})
            self.assertEqual(failure['error_class'], 'ValueError')
            self.assertTrue(any(e['stage']=='generation' and e['status']=='held' and e['exit_code']==3 for e in events))
            self.assertIsNone(draft._SOURCE.get())

    def test_recovery_binding_and_concurrent_scope(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'HOME': directory}):
            selected = settings(); store=store_for(selected)
            self.invoke(selected, provider={**GMAIL, 'body':'Different'})
            event=next(e for e in store.events(limit=100)['events'] if e.get('causal',{}).get('layer')=='source')
            state=initial_state(); observe(state,event,time.time())
            with causal.scope():
                supervisor=causal.decision('supervisor_completion','run_verified',outcome='accepted',method='operator.tick')
            later={**event,'level':'INFO','status':'result','reason':'none','causal':supervisor,'method':'operator.tick'}
            observe(state,later,time.time())
            self.assertTrue(state['failures'])
            self.invoke(selected)
            accepted=next(e for e in store.events(limit=100)['events'] if e.get('causal',{}).get('cause')=='review_prepared')
            other={**accepted,'root_id':'<other@example.test>'}
            observe(state,other,time.time()); self.assertTrue(state['failures'])
            observe(state,accepted,time.time()); self.assertFalse(state['failures'])
        @draft._preparation_scope
        def classify(text):
            self.assertFalse(draft._same_source_body('plain',text,'owner','sender'))
            return causal.selected()['cause']
        texts=['other','answer\nOn Tuesday someone wrote:\nunquoted']*8
        with ThreadPoolExecutor(max_workers=4) as pool:
            causes=list(pool.map(classify,texts))
        self.assertEqual(causes,['source_body_different','provider_authored_unquoted_tail']*8)
        self.assertIsNone(draft._SOURCE.get())
        self.assertIsNone(causal.selected())


if __name__=='__main__':
    unittest.main()
