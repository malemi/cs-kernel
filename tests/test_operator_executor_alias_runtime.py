"""Free recurring metadata renewal and canonical fallback runtime controls."""
from __future__ import annotations

import copy
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs import operator_recovery as recovery
from cs.operator_executor_config import check_executor_job,utc_datetime
import test_operator_executor as base
import test_operator_executor_integration as integration

SOURCE=base.SOURCE
RAW=(Path(__file__).parent/'fixtures/operator_executor_alias_metadata.json').read_bytes()
ALIAS='~anthropic/claude-sonnet-latest'
CANONICAL='anthropic/claude-sonnet-5.5'


def caps():
    return dict(provider='openrouter',model=ALIAS,source='standing free-control caps',response_models=[],
        input_upper_usd_per_million='2.50',output_upper_usd_per_million='10',maximum_context_tokens=1000000)


class Response:
    status=200
    def __init__(self,raw=RAW,url='https://openrouter.ai/api/v1/model/'+ALIAS):self.raw,self.url=raw,url
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def geturl(self):return self.url
    def read(self,count):return self.raw[:count]


class AliasRuntimeTests(base.ExecutorTests):
    def settings(self):
        return SimpleNamespace(cron_fallback_model=ALIAS,cron_fallback_budget_usd=4.0,
            engine_owner_uid='fixture-owner',state_dir=self.base/'state',cs_triage_mode='draft',pause_path=self.base/'PAUSE')

    def prepare(self,raw=RAW):
        os.environ.update(CS_EXECUTOR_FALLBACK_PRICING_JSON=json.dumps(caps()),CS_EXECUTOR_FALLBACK_CACHE_MODE='5m')
        with patch.object(recovery,'_fetch_fallback_metadata',side_effect=recovery._read_fallback_metadata),patch.object(recovery.urllib.request,'build_opener') as build:
            build.return_value.open.return_value=Response(raw)
            job,policy=recovery._prepare_executor_job(self.settings())
            call=build.return_value.open.call_args
            self.assertEqual(call.kwargs,dict(timeout=10))
            self.assertEqual(call.args[0].method,'GET')
            self.assertNotIn('authorization',{key.lower() for key in call.args[0].headers})
            self.assertEqual(build.return_value.open.call_count,1)
        return job,policy

    def test_retained_actual_metadata_free_get_and_immutable_projection(self):
        job,policy=self.prepare()
        self.assertEqual(policy.canonical_model,CANONICAL)
        self.assertEqual(policy.configured_alias,ALIAS)
        self.assertEqual(policy.pricing.input_usd_per_million,'2.000000')
        self.assertEqual(policy.pricing.cache_read_usd_per_million,'0.1000000')
        self.assertEqual(Path(policy.metadata.path).read_bytes(),RAW)
        self.assertEqual(policy.metadata.sha256,hashlib.sha256(RAW).hexdigest())
        self.assertEqual(policy.metadata.http_status,200)
        self.assertEqual(policy.response_models,(CANONICAL,))
        with self.assertRaises(ValueError):policy.canonical_model='anthropic/foreign'
        with self.assertRaises(ValueError):policy.pricing.model='anthropic/foreign'
        os.environ['CS_EXECUTOR_FALLBACK_PRICING_JSON']='{}'
        self.assertEqual(policy.pricing.model,CANONICAL)
        recovery._check_executor_resolution(job,policy)
        Path(policy.metadata.path).write_bytes(RAW+b' ')
        with self.assertRaisesRegex(ValueError,'retention_differs'):recovery._check_executor_resolution(job,policy)

    def test_metadata_negatives_hold_before_intake_or_any_executor(self):
        settings=self.settings()
        os.environ.update(CS_EXECUTOR_FALLBACK_PRICING_JSON=json.dumps(caps()),CS_EXECUTOR_FALLBACK_CACHE_MODE='5m')
        good=json.loads(RAW)
        for mode in ('missing','malformed','duplicate','wrong-alias','foreign-target','unresolved','price','request-fee','unknown-fee','context','missing-price','negative','nonfinite','oversize'):
            value=copy.deepcopy(good)
            if mode=='missing':raw=b''
            elif mode=='malformed':raw=b'not json'
            elif mode=='duplicate':raw=b'{"data":{},"data":{}}'
            else:
                if mode=='wrong-alias':value['data']['id']='foreign'
                elif mode=='foreign-target':value['data']['alias_target']['slug']='anthropic/claude-opus-5.5'
                elif mode=='unresolved':value['data']['alias_target']['slug']=ALIAS
                elif mode=='price':value['data']['pricing']['prompt']='0.01'
                elif mode=='request-fee':value['data']['pricing']['request']='0.1'
                elif mode=='unknown-fee':value['data']['pricing']['unknown_charge']='0.1'
                elif mode=='context':value['data']['context_length']=1000001
                elif mode=='missing-price':value['data']['pricing'].pop('input_cache_read')
                elif mode=='negative':value['data']['pricing']['input_cache_read']='-1'
                elif mode=='nonfinite':value['data']['pricing']['input_cache_read']='NaN'
                raw=b'x'*65537 if mode=='oversize' else json.dumps(value).encode()
            with self.subTest(mode=mode),patch.object(recovery.config,'load',return_value=settings), \
                    patch.object(recovery,'_read_state',return_value={}),patch.object(recovery,'_deliver_pending'), \
                    patch.object(recovery.diagnostics,'context',return_value={}),patch.object(recovery,'_notice') as notice, \
                    patch.object(recovery,'_fetch_fallback_metadata',side_effect=recovery._read_fallback_metadata), \
                    patch.object(recovery.urllib.request,'build_opener') as build, \
                    patch.object(recovery,'_mail_intake') as intake,patch.object(recovery,'_run') as launch:
                build.return_value.open.return_value=Response(raw)
                self.assertEqual(recovery._run_tick('unused',[],executor='pydantic'),1)
                self.assertEqual(launch.call_count,0);self.assertEqual(intake.call_count,0)
                self.assertEqual(build.return_value.open.call_count,1)
                self.assertEqual(notice.call_args.kwargs['reason'],'executor_metadata_held')
                self.assertIsNotNone(notice.call_args.kwargs['diagnostic']['executor_diagnostic']['run_id'])

    def test_explicit_fallback_one_hour_refuses_before_intake_or_inference(self):
        os.environ.update(CS_EXECUTOR_FALLBACK_PRICING_JSON=json.dumps(caps()),CS_EXECUTOR_FALLBACK_CACHE_MODE='1h')
        with patch.object(recovery.config,'load',return_value=self.settings()), \
                patch.object(recovery,'_read_state',return_value={}),patch.object(recovery,'_deliver_pending'), \
                patch.object(recovery.diagnostics,'context',return_value={}),patch.object(recovery,'_notice') as notice, \
                patch.object(recovery,'_fetch_fallback_metadata',return_value=RAW), \
                patch.object(recovery,'_mail_intake') as intake,patch.object(recovery,'_run') as launch:
            self.assertEqual(recovery._run_tick('unused',[],executor='pydantic'),1)
            self.assertEqual(intake.call_count,0);self.assertEqual(launch.call_count,0)
            self.assertEqual(notice.call_args.kwargs['reason'],'executor_metadata_held')

    def test_time_expiry_clock_rollback_fresh_renewal_and_separate_tick_nonce(self):
        job,policy=self.prepare()
        admitted=utc_datetime(job.admitted_at_utc)
        observed=utc_datetime(policy.metadata.observed_at_utc)
        check_executor_job(job,policy,now=observed,monotonic_ns=job.monotonic_start_ns)
        for mode in ('utc-rollback','mono-rollback','expiry','mono-expiry','future-observation','stale'):
            j,p=job,policy;now=observed;mono=job.monotonic_start_ns
            if mode=='utc-rollback':now=admitted-timedelta(seconds=1)
            elif mode=='mono-rollback':mono-=1
            elif mode=='expiry':now=utc_datetime(job.expires_at_utc)+timedelta(seconds=1)
            elif mode=='mono-expiry':mono+=10801*1000000000
            elif mode=='future-observation':p=p.model_copy(update={'metadata':p.metadata.model_copy(update={'observed_at_utc':(now+timedelta(seconds=1)).isoformat()})})
            else:p=p.model_copy(update={'metadata':p.metadata.model_copy(update={'observed_at_utc':(now-timedelta(hours=25)).isoformat()})})
            with self.subTest(mode=mode),self.assertRaises(ValueError):check_executor_job(j,p,now=now,monotonic_ns=mono)
        next_job,next_policy=self.prepare()
        self.assertNotEqual(job.nonce,next_job.nonce)
        self.assertNotEqual(job.primary_run_id,next_job.primary_run_id)
        self.assertNotEqual(policy.resolution_id,next_policy.resolution_id)
        check_executor_job(next_job,next_policy)
        with patch.object(recovery,'_fetch_fallback_metadata',side_effect=recovery._read_fallback_metadata),patch.object(recovery.urllib.request,'build_opener') as build:
            build.return_value.open.side_effect=OSError('fixture failure')
            with self.assertRaisesRegex(ValueError,'metadata_request_failed'):recovery._prepare_executor_job(self.settings())
            self.assertEqual(build.return_value.open.call_count,1)

    def test_extreme_decimal_representations_hold_without_expansion(self):
        for key in ('prompt','input_cache_write_1h','unknown_zero'):
            for value in ('1e-1000000','1e1000000','0e-1000000','1'*129,'0.'+'1'*65):
                data=json.loads(RAW);data['data']['pricing'][key]=value
                with self.subTest(key=key,value=value[:20]),self.assertRaisesRegex(ValueError,'metadata_price'):
                    self.prepare(json.dumps(data).encode())

        data=json.loads(RAW);digits='1234567890'*5
        data['data']['pricing']['prompt']='0.000002'+digits
        _,policy=self.prepare(json.dumps(data).encode())
        self.assertEqual(policy.pricing.input_usd_per_million,'2.'+digits+'000000')

    def test_absolute_job_deadline_does_not_restart_at_child_start(self):
        import time
        from cs.operator_executor_config import AdmissionError
        config=self.config.model_copy(update={'deadline_seconds':10800,'job_deadline_monotonic_ns':time.monotonic_ns()+2000000000})
        self.assertLessEqual(config.remaining_seconds(),2)
        job,_=self.prepare()
        shorter=job.model_copy(update={'expires_at_utc':(utc_datetime(job.admitted_at_utc)+timedelta(seconds=2)).isoformat()})
        self.assertEqual(shorter.deadline_monotonic_ns,job.monotonic_start_ns+2000000000)
        expired=config.model_copy(update={'job_deadline_monotonic_ns':time.monotonic_ns()-1})
        with self.assertRaisesRegex(AdmissionError,'executor_job_expired'):expired.remaining_seconds()

    def test_actual_child_uses_absolute_deadline_and_reaps_existing_cli_control(self):
        import time
        absolute=time.monotonic_ns()+2000000000
        with patch.object(self,'runtime',side_effect=lambda **kwargs:base.ExecutorTests.runtime(self,
                deadline_seconds=10800,job_deadline_monotonic_ns=absolute)):
            base.ExecutorTests.test_executor_deadline_has_finite_diagnostic_and_reaps_child(self)

    def test_real_trickling_http_and_dns_abort_reap_owned_worker_before_ten_seconds(self):
        import http.server,threading,time,subprocess
        from cs.operator_health import identity
        stop=threading.Event()
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Length','100');self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b'x');self.wfile.flush()
                        if stop.wait(1):break
                except (BrokenPipeError,ConnectionResetError):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever);worker.start()
        owned=[];results=[];original=subprocess.Popen
        def spawn(*args,**kwargs):
            proc=original(*args,**kwargs);owned.append((proc,identity(proc.pid)[0]));return proc
        try:
            for mode in ('trickle','dns-abort'):
                with self.subTest(mode=mode):
                    environment={}
                    url='http://127.0.0.1:'+str(server.server_port)+'/'
                    if mode=='dns-abort':
                        bootstrap=self.base/'slow-dns';bootstrap.mkdir()
                        (bootstrap/'sitecustomize.py').write_text('import socket,time\ndef slow(*args,**kwargs):\n time.sleep(30)\n raise OSError("controlled DNS abort")\nsocket.getaddrinfo=slow\n')
                        environment['PYTHONPATH']=str(bootstrap)+os.pathsep+str(SOURCE)
                    start=time.monotonic()
                    with patch.dict(os.environ,environment),patch.object(recovery.subprocess,'Popen',side_effect=spawn):
                        if mode=='trickle':
                            fetch=recovery._fetch_fallback_metadata
                            os.environ['CS_EXECUTOR_FALLBACK_PRICING_JSON']=json.dumps(caps())
                            with patch.object(recovery,'_fetch_fallback_metadata',side_effect=lambda ignored:fetch(url)), \
                                    patch.object(recovery.config,'load',return_value=self.settings()), \
                                    patch.object(recovery,'_read_state',return_value={}),patch.object(recovery,'_deliver_pending'), \
                                    patch.object(recovery.diagnostics,'context',return_value={}),patch.object(recovery,'_notice') as notice, \
                                    patch.object(recovery,'_mail_intake') as intake,patch.object(recovery,'_run') as launch:
                                self.assertEqual(recovery._run_tick('unused',[],executor='pydantic'),1)
                                self.assertEqual(notice.call_args.kwargs['diagnostic']['executor_diagnostic']['cause'],'metadata_deadline')
                                self.assertEqual(intake.call_count,0);self.assertEqual(launch.call_count,0)
                        else:
                            with self.assertRaisesRegex(ValueError,'metadata_deadline'):recovery._fetch_fallback_metadata(url)
                    duration=time.monotonic()-start
                    self.assertLess(duration,10)
                    results.append(dict(case=mode,elapsed_seconds=duration,limit_seconds=10,owned_remaining=0))
                    self.assertIsNotNone(owned[-1][0].returncode)
                    self.assertFalse(Path('/proc/'+str(owned[-1][1]['pid'])).exists())
        finally:
            stop.set();server.shutdown();server.server_close();worker.join()
        self.assertEqual(len(owned),2)
        from operator_executor_test_support import evidence_path
        evidence_path('m4-alias-runtime','metadata-deadline-results.json').write_text(json.dumps(results))

    def test_missing_caps_or_changed_alias_and_job_hold_before_provider_work(self):
        settings=self.settings()
        with patch.dict(os.environ,{'CS_EXECUTOR_FALLBACK_PRICING_JSON':'{}'}), \
                patch.object(recovery,'_fetch_fallback_metadata') as fetch:
            with self.assertRaises(ValueError):recovery._prepare_executor_job(settings)
            self.assertEqual(fetch.call_count,0)
        job,policy=self.prepare()
        for mode in ('changed-alias','foreign-primary'):
            current=copy.copy(settings)
            if mode=='changed-alias':current.cron_fallback_model='~anthropic/claude-opus-latest'
            primary=recovery.Attempt(3,[],executor_proof={'expected':{'run_id':job.primary_run_id if mode=='changed-alias' else 'foreign'}})
            with self.subTest(mode=mode),patch.object(recovery,'_executor_fallback_admission',return_value={}), \
                    patch.object(recovery.config,'load',return_value=current),patch.object(recovery,'_notice') as notice, \
                    patch.object(recovery,'_saved_openrouter_key') as key,patch.object(recovery,'_run') as launch:
                self.assertEqual(recovery._executor_fallback(settings,{},primary,{}, {},'unused',[],None,[],job,policy),3)
                self.assertEqual(notice.call_args.kwargs['reason'],'fallback_resolution_invalid')
                self.assertEqual(key.call_count,0);self.assertEqual(launch.call_count,0)

    def test_fetch_rejects_redirect_non200_and_native_or_disabled_unchanged(self):
        for status,url in ((302,'https://openrouter.ai/other'),(200,'https://foreign.invalid/')):
            response=Response();response.status=status;response.url=url
            with patch.object(recovery,'_fetch_fallback_metadata',side_effect=recovery._read_fallback_metadata),patch.object(recovery.urllib.request,'build_opener') as build:
                build.return_value.open.return_value=response
                with self.assertRaisesRegex(ValueError,'metadata_http_status_or_url'):recovery._read_fallback_metadata('https://openrouter.ai/api/v1/model/'+ALIAS)
                self.assertEqual(build.return_value.open.call_count,1)
        settings=self.settings();settings.cron_fallback_model=''
        with patch.object(recovery,'_fetch_fallback_metadata') as fetch:
            self.assertEqual(recovery._prepare_executor_job(settings),(None,None));self.assertEqual(fetch.call_count,0)


class AliasControllerTests(integration.IntegrationTests):
    def exercise_tick(self,primary_success=False):
        self.setup_integration()
        self.integration_case='alias-runtime'
        primary_prices=json.loads(os.environ['CS_EXECUTOR_PRICING_JSON'])
        primary_prices.update(input_upper_usd_per_million='8',input_usd_per_million='4',output_usd_per_million='1',
            cache_read_usd_per_million='0.2',cache_write_5m_usd_per_million='5',cache_write_1h_usd_per_million='8')
        os.environ.update(CS_EXECUTOR_CACHE_MODE='1h',CS_EXECUTOR_PRICING_JSON=json.dumps(primary_prices))
        os.environ.update(CRON_FALLBACK_MODEL=ALIAS,CRON_FALLBACK_BUDGET_USD='4.0',
            CS_EXECUTOR_FALLBACK_PRICING_JSON=json.dumps(caps()),CS_EXECUTOR_FALLBACK_CACHE_MODE='5m')
        metadata=self.base/'metadata.json';metadata.write_bytes(RAW)
        counts=self.base/'metadata-count';intake=self.base/'intake-count'
        backend=self.base/'fixture-services/fixture_backend.py'
        text=backend.read_text().replace('import cs.operator_executor as executor\n','')
        text+='''
import urllib.request
from pathlib import Path
from cs import operator_recovery as recovery
metadata_path=Path(__META__)
class MetadataResponse:
 status=200
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def geturl(self):return 'https://openrouter.ai/api/v1/model/~anthropic/claude-sonnet-latest'
 def read(self,count):return metadata_path.read_bytes()[:count]
class MetadataOpener:
 def open(self,request,timeout):
  assert request.method=='GET' and timeout==10
  assert request.full_url=='https://openrouter.ai/api/v1/model/~anthropic/claude-sonnet-latest'
  assert not any(key.lower()=='authorization' for key in request.headers)
  with Path(__COUNT__).open('a') as out:out.write('GET\\n')
  return MetadataResponse()
recovery.urllib.request.build_opener=lambda *a:MetadataOpener()
original_transport=transport
async def transport(request):
 if request.url.host=='api.anthropic.com':
  if __PRIMARY_SUCCESS__:return await original_transport(request)
  return httpx2.Response(402,headers={'request-id':'fixture-primary-refusal'},json={'type':'error','error':{'type':'billing_error','message':'fixture refused'}})
 response=await original_transport(request)
 value=json.loads(response.content);value['model']='anthropic/claude-sonnet-5.5'
 return httpx2.Response(200,json=value)
recovery._read_state=lambda settings:{}
recovery._deliver_pending=lambda *a:True
recovery._notice=lambda *a,**kw:True
async def fixture_intake(settings):
 with Path(__INTAKE__).open('a') as out:out.write('intake\\n')
 os.environ['CS_EXECUTOR_FALLBACK_PRICING_JSON']='{}'
 os.environ['CS_EXECUTOR_FALLBACK_CACHE_MODE']='1h'
async def saved_key(settings):return 'fixture-saved-key'
recovery._mail_intake=fixture_intake
recovery._saved_openrouter_key=saved_key
'''.replace('__PRIMARY_SUCCESS__',repr(primary_success)).replace('__META__',repr(str(metadata))).replace('__COUNT__',repr(str(counts))).replace('__INTAKE__',repr(str(intake)))
        backend.write_text(text)
        fixture=self.base/'fixture-services'
        for name in ('sitecustomize.py','fixture_backend.py'):compile((fixture/name).read_text(),str(fixture/name),'exec')
        import subprocess,threading,time,importlib.metadata
        from cs.operator_health import identity
        from cs.operator_inventory_view import source_identity
        from cs.operator_executor_evidence import digest,reference
        primary_policy=dict(provider='anthropic',model='fixture-model',api_key_env='CS_FIXTURE_EXECUTOR_KEY',base_url=None,
            pricing=json.loads(os.environ['CS_EXECUTOR_PRICING_JSON']),cache_mode='1h',send_mode='draft',founder_enabled=False,
            campaign_enabled=True,admitted_ceiling_usd='20',max_output_tokens=100,deadline_seconds=10800,
            additional_denied=[],context_paths=[],exact_send_ids=[],founder_account=None,founder_question=None,
            max_artifact_bytes=16777216,max_requests=100,page_bytes=16384,soft_budget_usd='4.00',tool_timeout_seconds=2730)
        common=dict(clone_root=str(self.root),interpreter=dict(path=str(integration.SDK.resolve()),bytes=integration.SDK.resolve().stat().st_size,
            sha256=digest(integration.SDK.resolve().read_bytes())),executor_module_digest=digest((SOURCE/'cs/operator_executor.py').read_bytes()),
            dependency_version=importlib.metadata.version('pydantic-ai-slim'))
        primary_binding=dict(common,launch_policy=primary_policy)
        fallback_binding=dict(common,launch_policy=dict(primary_policy,provider='openrouter',model=ALIAS,api_key_env='CS_EXECUTOR_FALLBACK_API_KEY',
            base_url='https://openrouter.ai/api',pricing=caps(),cache_mode='5m',soft_budget_usd='4.0'))
        source=dict(kernel_package_root=str(SOURCE/'cs'),pythonpath=os.environ['PYTHONPATH'],kernel_source_digest=source_identity(),
            executor_binding=primary_binding,executor_fallback_binding=fallback_binding,
            executor_alias_preflight=dict(configured_alias=ALIAS,cap_policy=caps(),cache_mode='5m'))
        source['executor_job_observation']=dict(launch_before_utc=datetime.now(timezone.utc).isoformat(),launch_before_monotonic_ns=time.monotonic_ns())
        observed={};launches={};stop=threading.Event()
        command=[str(integration.SDK),'-c',"from cs import operator_recovery as r; raise SystemExit(r._run_tick('unused',['Write','Edit'],executor='pydantic'))"]
        proc=subprocess.Popen(command,cwd=self.root,env=dict(os.environ),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        def observe():
            while not stop.is_set():
                pending=[proc.pid]
                for pid in pending:
                    try:
                        row,_=identity(pid);observed[str(pid)]=row['started_ticks']
                        pending.extend(int(value) for value in Path(f'/proc/{pid}/task/{pid}/children').read_text().split())
                        argv=[part.decode() for part in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if part]
                        if 'cs.operator_executor' in argv and '--config' in argv:
                            launches[str(pid)]=dict(started_ticks=row['started_ticks'],argv=argv,
                                launch_config=reference(Path(argv[argv.index('--config')+1])))
                    except (OSError,ValueError):pass
                time.sleep(.02)
        watcher=threading.Thread(target=observe);watcher.start()
        try:stdout,stderr=proc.communicate(timeout=90)
        finally:stop.set();watcher.join()
        source['executor_job_observation'].update(launch_after_utc=datetime.now(timezone.utc).isoformat(),launch_after_monotonic_ns=time.monotonic_ns())
        self.assertEqual(proc.returncode,0,stdout+stderr)
        self.assertEqual(counts.read_text().splitlines(),['GET']);self.assertEqual(intake.read_text().splitlines(),['intake'])
        self.assertFalse((self.base/'socket-attempts.txt').exists())
        receipts=json.loads(self.receipt.read_text());self.assertEqual(len(receipts),1 if primary_success else 2)
        binding=receipts[0]['executor_alias_binding']
        if not primary_success:
            chain=receipts[-1]['executor_fallback_chain']
            from decimal import Decimal
            self.assertGreater(Decimal(chain['primary_uncertain_cost_usd']),0)
            self.assertEqual(Decimal(chain['fallback_admitted_ceiling_usd'])+Decimal(chain['primary_uncertain_cost_usd'])+
                Decimal(chain['primary_accounted_cost_usd']),Decimal(chain['original_admitted_ceiling_usd']))
            self.assertEqual(receipts[0]['executor_job']['expires_at_utc'],receipts[1]['executor_job']['expires_at_utc'])
            self.assertEqual(binding,chain['alias_binding']);self.assertEqual(binding,receipts[1]['executor_alias_binding'])
        self.assertEqual(binding['policy']['canonical_model'],CANONICAL)
        if not primary_success:self.assertEqual(receipts[0]['executor_job']['nonce'],receipts[1]['executor_job']['nonce'])
        self.assertEqual(binding['job']['primary_run_id'],receipts[0]['executor_proof']['expected']['run_id'])
        self.assertTrue(all(str(receipt['child_identity']['pid']) in launches for receipt in receipts))
        self.assertTrue(receipts[-1]['clean_terminal'])
        source.update(executor_attempt_receipts=receipts,executor_observed_launches=launches)
        packet=dict(receipt=receipts[-1],receipts=receipts,nonce='e'*32,owner='fixture-owner',owned=observed,
            required_phases=['identity','configuration','tasks','review','discovery','campaigns'],source=source)
        from operator_executor_test_support import evidence_path
        target=evidence_path('m4-alias-runtime','actual-primary-success-packet.json' if primary_success else 'actual-recurring-packet.json')
        target.write_text(json.dumps(packet,sort_keys=True));target.chmod(0o600)
        if not primary_success:
            from cs import operator_executor_evidence as evidence,operator_executor_protocol as protocol
            proof=receipts[0]['executor_proof']
            launch=json.loads(Path(proof['launch_config']['path']).read_bytes())
            context=dict(directory=str(Path(launch['journal_path']).parent),nonce=launch['nonce'],
                owner_uid=launch['owner'],supervisor=launch['supervisor'])
            rows=protocol.parse_journal(Path(launch['journal_path']))
            request=next(row.payload for row in rows if row.payload.kind=='model_request')
            original=evidence.artifact(request.messages)
            self.assertEqual(evidence.validate(proof,context,prework_only=True)['prework_refusal'],'payment_required')
            actual=evidence.artifact
            results=[]
            for setting in ('anthropic_cache','anthropic_cache_instructions','anthropic_cache_tool_definitions'):
                for replacement in ('5m',None):
                    value=protocol.decode(original)
                    self.assertEqual(value['settings'][setting],'1h')
                    if replacement is None:value['settings'].pop(setting)
                    else:value['settings'][setting]=replacement
                    changed=protocol.canonical(value)
                    if replacement=='5m':self.assertEqual(len(changed),len(original))
                    mutated=copy.deepcopy(rows)
                    next(row.payload for row in mutated if row.payload.kind=='model_request').payload_sha256=evidence.digest(changed)
                    def read(reference,directory=None):
                        path=reference.path if hasattr(reference,'path') else reference['path']
                        return changed if path==request.messages.path else actual(reference,directory)
                    with self.subTest(setting=setting,replacement=replacement), \
                            patch.object(evidence,'artifact',side_effect=read), \
                            patch.object(protocol,'parse_journal',return_value=mutated):
                        with self.assertRaisesRegex(ValueError,'executor_sdk_settings_binding'):
                            evidence.validate(proof,context,prework_only=True)
                        attempt=recovery.Attempt(3,[],executor_proof=proof,health_context=context)
                        with self.assertRaisesRegex(ValueError,'executor_sdk_settings_binding'):
                            recovery._executor_fallback_admission(attempt)
                        results.append(dict(setting=setting,replacement=replacement,rejected=True))
            evidence_path('m4-alias-runtime','prework-sdk-settings-rejections.json').write_text(json.dumps(results))


    def test_actual_tick_renews_and_freezes_canonical_fallback(self):
        self.exercise_tick()

    def test_actual_primary_success_retains_renewal_binding(self):
        self.exercise_tick(primary_success=True)


for cls,parent in ((AliasRuntimeTests,base.ExecutorTests),(AliasControllerTests,integration.IntegrationTests)):
    for ancestor in (base.ExecutorTests,parent):
        for name in vars(ancestor):
            if name.startswith('test_') and name not in vars(cls):setattr(cls,name,None)
del cls,parent,ancestor

if __name__=='__main__':unittest.main()
