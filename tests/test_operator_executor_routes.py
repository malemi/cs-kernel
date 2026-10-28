"""Free provider-route checks through the pinned Anthropic SDK and supervisor."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

import httpx2
from pydantic_ai import models
from cs import operator_executor as executor, operator_recovery as recovery
from cs.operator_executor_config import AdmissionError, ExecutorConfig
from cs.operator_executor_protocol import decode, parse_journal
from test_operator_executor import ExecutorTests
from test_operator_executor_integration import IntegrationTests

models.ALLOW_MODEL_REQUESTS = False


class RouteTests(ExecutorTests):
    def exercise(self, provider='anthropic', *, actual='fixture-model', aliases=None, status=200, kind=None):
        value = self.config.model_dump(mode='json')
        value.update(provider=provider, base_url='https://openrouter.ai/api' if provider == 'openrouter' else None)
        value['pricing'].update(provider=provider, response_models=aliases or [])
        runtime = executor.ExecutorRuntime(ExecutorConfig.model_validate(value))
        calls = []
        original = httpx2.AsyncClient
        async def transport(request):
            self.assertEqual(request.headers.get('authorization'), 'Bearer fixture-nonsecret')
            calls.append((str(request.url), bool(request.headers.get('x-api-key')),
                request.headers.get('authorization', '').split(' ', 1)[0], decode(request.content)['model']))
            if status != 200:
                return httpx2.Response(status, headers={'request-id':'fixture-safe-request'},
                    json={'type':'error','error':{'type':kind,'message':'REMOTE_SECRET_MUST_NOT_PERSIST'}})
            return httpx2.Response(200, headers={'request-id':'fixture-safe-request'}, json={
                'id':'fixture-response','type':'message','role':'assistant','model':actual,
                'content':[{'type':'text','text':'Fixture done'}],'stop_reason':'end_turn',
                'usage':{'input_tokens':10,'output_tokens':1}})
        class Client(original):
            def __init__(self, *args, **kwargs):
                kwargs['transport'] = httpx2.MockTransport(transport)
                super().__init__(*args, **kwargs)
        with patch.dict(os.environ, {self.config.api_key_env:'fixture-nonsecret',
                'ANTHROPIC_API_KEY':'inherited-key-conflict', 'ANTHROPIC_AUTH_TOKEN':'inherited-token-conflict'}), \
                patch('socket.socket.connect', side_effect=AssertionError('network disabled')), \
                patch('socket.socket.connect_ex', side_effect=AssertionError('network disabled')), \
                patch('httpx2.AsyncClient', Client), \
                patch('pydantic_ai.models.anthropic.check_allow_model_requests', lambda: None):
            terminal = asyncio.run(runtime.run('Fixture route only'))
        rows = [r.payload for r in parse_journal(Path(value['journal_path']))]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], (runtime.config.messages_endpoint, False, 'Bearer', 'fixture-model'))
        raw = Path(value['journal_path']).read_bytes()
        for forbidden in (b'fixture-nonsecret', b'inherited-key-conflict', b'inherited-token-conflict', b'REMOTE_SECRET'):
            self.assertNotIn(forbidden, raw)
        self.assertFalse(any(r.kind == 'tool_spawn' for r in rows))
        return runtime, rows, terminal

    def test_primary_actual_sdk_url_auth_and_usage(self):
        runtime, rows, terminal = self.exercise()
        response = next(r for r in rows if r.kind == 'model_response')
        self.assertEqual((response.status,response.model,response.input_tokens,response.output_tokens), ('ok','fixture-model',10,1))
        self.assertGreater(runtime.admission.accounted, 0)
        self.assertEqual(runtime.admission.uncertain, 0)
        self.assertEqual(terminal, 'held')

    def test_fallback_actual_sdk_bearer_and_finite_alias(self):
        runtime, rows, _ = self.exercise('openrouter', actual='anthropic/fixture-version', aliases=['anthropic/fixture-version'])
        response = next(r for r in rows if r.kind == 'model_response')
        self.assertEqual((response.status,response.model), ('ok','anthropic/fixture-version'))
        self.assertEqual(runtime.admission.uncertain, 0)

    def test_unbound_model_keeps_reservation(self):
        runtime, rows, _ = self.exercise('openrouter', actual='arbitrary-foreign-model')
        self.assertEqual(next(r for r in rows if r.kind == 'model_response').status, 'unknown')
        self.assertGreater(runtime.admission.uncertain, 0)
        with self.assertRaisesRegex(AdmissionError, 'unknown_previous_cost'):
            runtime.admission.reserve(10)

    def test_402_retains_original_finite_error_without_zero_charge_invention(self):
        runtime, rows, _ = self.exercise(status=402, kind='billing_error')
        response = next(r for r in rows if r.kind == 'model_response')
        self.assertEqual((response.http_status,response.error_kind,response.provider_request_id),
            (402,'billing','fixture-safe-request'))
        self.assertIsNone(response.accounted_cost_usd)
        self.assertGreater(runtime.admission.uncertain, 0)
        self.assertEqual(len(rows[-1].outstanding_request_ids), 1)

    def test_429_retains_requestid_and_unknown_cost(self):
        runtime, rows, _ = self.exercise('openrouter', status=429, kind='rate_limit_error')
        response = next(r for r in rows if r.kind == 'model_response')
        self.assertEqual((response.http_status,response.error_kind), (429,'rate_limit'))
        self.assertGreater(runtime.admission.uncertain, 0)

    def test_original_error_metadata_survives_supervisor_validation(self):
        import sys
        from cs import operator_executor_evidence as evidence
        from cs.operator_executor_tools import identity
        from cs.operator_executor_protocol import canonical
        runtime, rows, _ = self.exercise(status=402, kind='billing_error')
        launch = self.private/'launch.json'
        launch.write_bytes(canonical(runtime.config.model_dump(mode='json')))
        launch.chmod(0o600)
        proof = dict(schema_version=evidence.CODEC,launch_config=evidence.reference(launch),
            journal=evidence.reference(Path(runtime.config.journal_path)),
            expected=evidence.expected_binding(runtime.config,identity().model_dump(),Path(sys.executable).resolve()),
            process_exit=3,timed_out=False)
        context = dict(directory=str(self.private),nonce=runtime.config.nonce,owner_uid=runtime.config.owner,
            supervisor=runtime.config.supervisor.model_dump())
        facts = evidence.validate(proof,context,diagnostic_only=True)
        self.assertEqual(facts['provider_failures'][0]['http_status'],402)
        self.assertEqual(facts['fallback_hold'],'zero_charge_unproven')
        self.assertEqual(facts['uncertain_cost_usd'],rows[-1].uncertain_cost_usd)
        with self.assertRaises(ValueError):
            evidence.validate(proof,context)

    def primary_proof(self):
        import sys
        from cs import operator_executor_evidence as evidence
        from cs.operator_executor_tools import identity
        from cs.operator_executor_protocol import canonical
        runtime, rows, _ = self.exercise(status=402, kind='billing_error')
        launch = self.private/'launch.json'
        launch.write_bytes(canonical(runtime.config.model_dump(mode='json')))
        launch.chmod(0o600)
        proof = dict(schema_version=evidence.CODEC,launch_config=evidence.reference(launch),
            journal=evidence.reference(Path(runtime.config.journal_path)),
            expected=evidence.expected_binding(runtime.config,identity().model_dump(),Path(sys.executable).resolve()),
            process_exit=3,timed_out=False)
        context = dict(directory=str(self.private),nonce=runtime.config.nonce,owner_uid=runtime.config.owner,
            supervisor=runtime.config.supervisor.model_dump())
        return recovery.Attempt(3,[],executor_proof=proof,health_context=context),runtime

    def test_retained_reservation_reduces_original_ceiling_and_narrower_cap(self):
        from decimal import Decimal
        primary,runtime = self.primary_proof()
        admission = recovery._executor_fallback_admission(primary)
        self.assertEqual(Decimal(admission['fallback_admitted_ceiling_usd'])+runtime.admission.uncertain,
            Decimal(runtime.config.admitted_ceiling_usd))
        self.assertEqual(admission['primary_uncertain_cost_usd'],format(runtime.admission.uncertain,'f'))
        with patch.dict(os.environ,{'CS_EXECUTOR_FALLBACK_ADMITTED_CEILING_USD':'0.01'}):
            self.assertEqual(recovery._executor_fallback_admission(primary)['fallback_admitted_ceiling_usd'],'0.01')
        with patch.dict(os.environ,{'CS_EXECUTOR_FALLBACK_ADMITTED_CEILING_USD':'0'}):
            with self.assertRaisesRegex(ValueError,'admission_exhausted'):
                recovery._executor_fallback_admission(primary)
        primary.executor_fallback_chain={'already':'fallback'}
        with self.assertRaisesRegex(ValueError,'capture_ambiguous'):
            recovery._executor_fallback_admission(primary)

    def test_prework_any_work_unknown_response_timeout_or_missing_identity_refuse(self):
        from cs import operator_executor_protocol as protocol
        primary,runtime = self.primary_proof()
        original = protocol.parse_journal(Path(runtime.config.journal_path))
        for mode in ('tool','unknown','status429','zero-reserve','completed','missing-id','reordered'):
            rows = copy.deepcopy(original)
            response = rows[-2].payload
            if mode=='tool':
                rows.insert(-1, rows[1].model_copy(update={'payload':protocol.ToolStart(tool_id=rows[-3].payload.request_id,
                    parent_request_id=None,name='pause_status',argv=None,path=None,offset=None,length=None,
                    decision='allow',cause=None,producer=rows[0].payload.executor)}))
            elif mode=='unknown':response.status='unknown'
            elif mode=='status429':response.http_status=429;response.error_kind='rate_limit'
            elif mode=='zero-reserve':rows[-1].payload.uncertain_cost_usd='0'
            elif mode=='completed':rows[-1].payload.model_completed=True
            elif mode=='missing-id':response.provider_request_id=None
            else:rows[-3],rows[-2]=rows[-2],rows[-3]
            with self.subTest(mode=mode),patch.object(protocol,'parse_journal',return_value=rows):
                with self.assertRaises(ValueError):recovery._executor_fallback_admission(primary)
        primary.timed_out=True
        with self.assertRaises(ValueError):recovery._executor_fallback_admission(primary)
        primary.timed_out=False
        primary.executor_proof['expected']['executor']['started_ticks']+=1
        with self.assertRaises(ValueError):recovery._executor_fallback_admission(primary)

    def test_refusal_or_unknown_cost_never_routes_into_saved_fallback(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(cs_triage_mode='draft',pause_path=self.base/'PAUSE')
        attempt = recovery.Attempt(3,[],health_failure='executor_evidence_invalid',executor_proof={},
            executor_facts=dict(fallback_hold='zero_charge_unproven',uncertain_cost_usd='0.25',
                diagnostic={'cause':'ModelHTTPError'},provider_failures=[dict(http_status=402,error_kind='billing')]))
        async def intake(settings):
            return None
        with patch.object(recovery.config,'load',return_value=settings), \
                patch.object(recovery,'_read_state',return_value={}), \
                patch.object(recovery,'_deliver_pending'), \
                patch.object(recovery.diagnostics,'context',return_value={}), \
                patch.object(recovery,'_mail_intake',intake), \
                patch.object(recovery,'_run',return_value=attempt) as run, \
                patch.object(recovery,'_saved_openrouter_key') as saved, \
                patch.object(recovery,'_notice',return_value=True) as notice:
            self.assertEqual(recovery._run_tick('unused',[],executor='pydantic'),3)
            self.assertEqual(run.call_count,1)
            self.assertEqual(saved.call_count,0)
            self.assertEqual(notice.call_args.kwargs['diagnostic']['fallback_status'],'zero_charge_unproven')
            settings.pause_path.touch()
            run.reset_mock()
            self.assertEqual(recovery._run_tick('unused',[],executor='pydantic'),0)
            self.assertEqual(run.call_count,0)

    def test_endpoint_and_wildcard_alias_bindings_refuse(self):
        value = self.config.model_dump(mode='json')
        for provider, base_url in (('anthropic','https://openrouter.ai/api'),
                ('openrouter',None), ('openrouter','https://arbitrary.invalid')):
            changed = copy.deepcopy(value)
            changed.update(provider=provider, base_url=base_url)
            changed['pricing']['provider'] = provider
            with self.assertRaises(ValueError):
                ExecutorConfig.model_validate(changed)
        value['pricing']['response_models'] = ['*']
        with self.assertRaises(ValueError):
            ExecutorConfig.model_validate(value)

    def test_fallback_configuration_preserves_ceiling_soft_target_and_saved_key_source(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(founder_sweep_enabled=False, engine_owner_uid='fixture-owner', cs_triage_mode='draft')
        context = dict(nonce=self.config.nonce,supervisor=self.config.supervisor.model_dump())
        pricing = self.config.pricing.model_dump(mode='json')
        pricing.update(provider='openrouter',model='~anthropic/claude-sonnet-latest',response_models=['anthropic/fixture-version'])
        with patch.dict(os.environ, {'CS_EXECUTOR_ADMITTED_CEILING_USD':'1.25',
                'CS_EXECUTOR_FALLBACK_PRICING_JSON':json.dumps(pricing)}), patch('pathlib.Path.cwd',return_value=self.root):
            config = recovery._executor_configuration(settings,self.private,context,[],[],
                model='~anthropic/claude-sonnet-latest',budget=4.0,key='fixture-saved-key')
        self.assertEqual((config.provider,config.api_key_env,config.soft_budget_usd,config.admitted_ceiling_usd),
            ('openrouter','CS_EXECUTOR_FALLBACK_API_KEY','4.0','1.25'))
        self.assertNotIn('fixture-saved-key', config.model_dump_json())


class ControllerRouteTests(IntegrationTests):
    def test_actual_prework_fallback_retains_primary_reservation(self):
        self.setup_integration()
        pricing = json.loads(os.environ['CS_EXECUTOR_PRICING_JSON'])
        pricing.update(provider='openrouter',model='~anthropic/claude-sonnet-latest',response_models=['anthropic/fixture-version'])
        os.environ.update(CS_EXECUTOR_FALLBACK_PRICING_JSON=json.dumps(pricing),
            CRON_FALLBACK_MODEL='~anthropic/claude-sonnet-latest',CRON_FALLBACK_BUDGET_USD='4.0')
        backend = self.base/'fixture-services/fixture_backend.py'
        backend.write_text(backend.read_text().replace("import cs.operator_executor as executor\n", "")+"""
original_transport=transport
async def transport(request):
 if request.url.host=='api.anthropic.com':
  return httpx2.Response(402,headers={'request-id':'fixture-primary-refusal'},json={'type':'error','error':{'type':'billing_error','message':'fixture refused'}})
 response=await original_transport(request)
 value=json.loads(response.content);value['model']='anthropic/fixture-version'
 return httpx2.Response(200,json=value)
import cs.operator_recovery as recovery
recovery._read_state=lambda settings:{}
recovery._deliver_pending=lambda *a:True
recovery._notice=lambda *a,**kw:True
async def fixture_intake(settings):
 return None
async def fixture_saved_key(settings):
 return 'fixture-saved-key'
recovery._mail_intake=fixture_intake
recovery._saved_openrouter_key=fixture_saved_key
""")
        fixture=self.base/'fixture-services'
        for name in ('sitecustomize.py','fixture_backend.py'):
            compile((fixture/name).read_text(),str(fixture/name),'exec')
        import threading,time,subprocess,importlib.metadata
        from cs.operator_health import identity
        from cs.operator_inventory_view import source_identity
        from cs.operator_executor_evidence import digest
        from test_operator_executor_integration import SDK
        from test_operator_executor import SOURCE
        policy=dict(provider='anthropic',model='fixture-model',api_key_env='CS_FIXTURE_EXECUTOR_KEY',
            base_url=None,pricing=json.loads(os.environ['CS_EXECUTOR_PRICING_JSON']),
            send_mode='draft',founder_enabled=False,campaign_enabled=True,admitted_ceiling_usd='20',max_output_tokens=100)
        binding=dict(clone_root=str(self.root),interpreter=dict(path=str(SDK.resolve()),
            bytes=SDK.resolve().stat().st_size,sha256=digest(SDK.resolve().read_bytes())),
            executor_module_digest=digest((SOURCE/'cs/operator_executor.py').read_bytes()),
            dependency_version=importlib.metadata.version('pydantic-ai-slim'),launch_policy=policy)
        fallback_binding=copy.deepcopy(binding)
        fallback_binding['launch_policy'].update(provider='openrouter',model='~anthropic/claude-sonnet-latest',
            api_key_env='CS_EXECUTOR_FALLBACK_API_KEY',base_url='https://openrouter.ai/api',pricing=pricing)
        source=dict(kernel_package_root=str(SOURCE/'cs'),pythonpath=os.environ['PYTHONPATH'],
            kernel_source_digest=source_identity(),executor_binding=binding,executor_fallback_binding=fallback_binding)
        command=[str(SDK),'-c',"from cs import operator_recovery as r; raise SystemExit(r._run_tick('unused',['Write','Edit'],executor='pydantic'))"]
        observed={};stop=threading.Event()
        proc=subprocess.Popen(command,cwd=self.root,env=dict(os.environ),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        def observe():
            while not stop.is_set():
                pending=[proc.pid]
                for pid in pending:
                    try:
                        row,_=identity(pid);observed[str(pid)]=row['started_ticks']
                        pending.extend(int(value) for value in Path(f'/proc/{pid}/task/{pid}/children').read_text().split())
                    except (OSError,ValueError):pass
                time.sleep(.02)
        watcher=threading.Thread(target=observe);watcher.start()
        try:stdout,stderr=proc.communicate(timeout=90)
        finally:stop.set();watcher.join()
        self.assertEqual(proc.returncode,0,stdout+stderr)
        receipts=json.loads(self.receipt.read_text())
        self.assertEqual(len(receipts),2)
        chain=receipts[-1]['executor_fallback_chain']
        from decimal import Decimal
        self.assertGreater(Decimal(chain['primary_uncertain_cost_usd']),0)
        self.assertEqual(Decimal(chain['fallback_admitted_ceiling_usd'])+Decimal(chain['primary_uncertain_cost_usd'])+
            Decimal(chain['primary_accounted_cost_usd']),Decimal(chain['original_admitted_ceiling_usd']))
        self.assertNotEqual(chain['primary_attempt_id'],chain['fallback_attempt_id'])
        self.assertEqual(chain['primary_proof'],receipts[0]['executor_proof'])
        self.assertEqual(chain['fallback_proof'],receipts[-1]['executor_proof'])
        self.assertTrue(receipts[-1]['clean_terminal'])
        self.assertFalse((self.base/'socket-attempts.txt').exists())
        from operator_executor_test_support import evidence_path
        target=evidence_path('m4-routes', 'fallback-receipts.json')
        target.write_text(json.dumps(receipts,sort_keys=True));target.chmod(0o600)
        source['executor_attempt_receipts']=receipts
        packet=dict(receipt=receipts[-1],receipts=receipts,nonce='e'*32,owner='fixture-owner',owned=observed,
            required_phases=['identity','configuration','tasks','review','discovery','campaigns'],source=source)
        packet_path=target.with_name('fallback-packet.json')
        packet_path.write_text(json.dumps(packet,sort_keys=True));packet_path.chmod(0o600)

    def test_openrouter_controller_actual_child_alias(self):
        self.setup_integration()
        pricing = json.loads(os.environ['CS_EXECUTOR_PRICING_JSON'])
        pricing.update(provider='openrouter',response_models=['anthropic/fixture-version'])
        os.environ.update(CS_EXECUTOR_PROVIDER='openrouter',CS_EXECUTOR_BASE_URL='https://openrouter.ai/api',
            CS_EXECUTOR_PRICING_JSON=json.dumps(pricing))
        backend = self.base/'fixture-services/fixture_backend.py'
        backend.write_text(backend.read_text().replace("model='fixture-model',content=content", "model='anthropic/fixture-version',content=content"))
        self.integration_case = 'm4-openrouter-route'
        receipt = self.launch()
        self.assertEqual(receipt['executor_facts']['model_names'], ['anthropic/fixture-version'])
        self.assertFalse((self.base/'socket-attempts.txt').exists())


for name in list(vars(ExecutorTests)):
    if name.startswith('test_') and name not in vars(RouteTests):
        setattr(RouteTests, name, None)
for cls in (ExecutorTests, IntegrationTests):
    for name in list(vars(cls)):
        if name.startswith('test_') and name not in vars(ControllerRouteTests):
            setattr(ControllerRouteTests, name, None)

del ExecutorTests, IntegrationTests, cls

if __name__ == '__main__':
    unittest.main()
