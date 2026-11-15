"""Free cache-request and disjoint usage-price controls through the actual SDK."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx2
from pydantic_ai import models
from pydantic_ai.messages import ModelRequest,UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.usage import RequestUsage
from cs import operator_executor as executor
from cs.operator_executor_config import Admission,AdmissionError,ExecutorConfig
from cs.operator_executor_protocol import canonical,decode,parse_journal
from test_operator_executor import ExecutorTests
from operator_executor_test_support import evidence_path

models.ALLOW_MODEL_REQUESTS=False


class CacheTests(ExecutorTests):
    def config_with_cache(self,provider='anthropic',mode='5m'):
        value=self.config.model_dump(mode='json')
        value.update(cache_mode='5m',provider=provider,base_url='https://openrouter.ai/api' if provider=='openrouter' else None)
        value['pricing'].update(provider=provider,input_upper_usd_per_million='4',output_upper_usd_per_million='12',
            input_usd_per_million='2',output_usd_per_million='10',cache_read_usd_per_million='0.2',cache_write_5m_usd_per_million='3')
        value['cache_mode']=mode
        if mode=='1h':value['pricing'].update(input_upper_usd_per_million='8',cache_write_1h_usd_per_million='8')
        return ExecutorConfig.model_validate(value)

    def two_turns(self,provider,invalid=False,mode='5m'):
        config=self.config_with_cache(provider,mode)
        runtime=executor.ExecutorRuntime(config)
        bodies=[]
        wire_usage=[dict(input_tokens=10,output_tokens=2,cache_creation_input_tokens=100,cache_read_input_tokens=0,
            cache_creation=dict(ephemeral_5m_input_tokens=100,ephemeral_1h_input_tokens=0)),
            dict(input_tokens=20,output_tokens=3,cache_creation_input_tokens=0,cache_read_input_tokens=100,
                cache_creation=dict(ephemeral_5m_input_tokens=0,ephemeral_1h_input_tokens=0))]
        if mode=='1h':
            wire_usage[0]['cache_creation']=dict(ephemeral_5m_input_tokens=25,ephemeral_1h_input_tokens=75)
        if invalid:
            if mode=='1h':wire_usage[0].pop('cache_creation')
            else:wire_usage[0]['cache_creation']=dict(ephemeral_5m_input_tokens=0,ephemeral_1h_input_tokens=100)
        original=httpx2.AsyncClient
        async def transport(request):
            bodies.append(decode(request.content))
            return httpx2.Response(200,json=dict(id='cache-'+str(len(bodies)),type='message',role='assistant',
                model='fixture-model',content=[dict(type='text',text='Fixture answer')],stop_reason='end_turn',usage=wire_usage[len(bodies)-1]))
        class Client(original):
            def __init__(self,*args,**kwargs):
                kwargs['transport']=httpx2.MockTransport(transport)
                super().__init__(*args,**kwargs)
        async def control():
            model=executor.instrument_model(executor.build_model(config,runtime),runtime)
            messages=[ModelRequest(parts=[UserPromptPart('Fixture stable prefix Ω '*100)])]
            settings=executor.executor_model_settings(config)
            first=await model.request(messages,settings,ModelRequestParameters())
            messages.extend([first,ModelRequest(parts=[UserPromptPart('Fixture followup')])])
            second=await model.request(messages,settings,ModelRequestParameters())
            return first,second
        with patch.dict(os.environ,{config.api_key_env:'fixture-cache-key'}), \
                patch('socket.socket.connect',side_effect=AssertionError('network disabled')), \
                patch('socket.socket.connect_ex',side_effect=AssertionError('network disabled')), \
                patch('httpx2.AsyncClient',Client), \
                patch('pydantic_ai.models.anthropic.check_allow_model_requests',lambda:None):
            if invalid:
                with self.assertRaises(AdmissionError):asyncio.run(control())
            else:first,second=asyncio.run(control())
        runtime.journal.close()
        if invalid:
            rows=[decode(raw)['payload'] for raw in Path(config.journal_path).read_bytes().splitlines()]
            response=next(row for row in rows if row['kind']=='model_response')
            self.assertEqual(response['status'],'unknown')
            self.assertIsNone(response['accounted_cost_usd'])
            self.assertGreater(runtime.admission.uncertain,0)
            self.assertEqual(runtime.admission.accounted,0)
            self.assertEqual(len(bodies),1)
            with self.assertRaisesRegex(AdmissionError,'unknown_previous_cost'):runtime.admission.reserve(10)
            return
        self.assertEqual([first.usage.input_tokens,second.usage.input_tokens],[110,120])
        self.assertEqual([first.usage.cache_write_tokens,second.usage.cache_read_tokens],[100,100])
        self.assertEqual(runtime.admission.accounted,Decimal('0.000805') if mode=='1h' else Decimal('0.00043'))
        self.assertEqual(runtime.admission.uncertain,0)
        self.assertEqual(len(bodies),2)
        for body in bodies:
            self.assertEqual(body['cache_control'],dict(type='ephemeral',ttl=mode))
        rows=[decode(raw)['payload'] for raw in Path(config.journal_path).read_bytes().splitlines()]
        responses=[r for r in rows if r['kind']=='model_response']
        self.assertEqual([r['normal_input_tokens'] for r in responses],[10,20])
        self.assertEqual([r['accounted_cost_usd'] for r in responses],['0.000715','0.00009'] if mode=='1h' else ['0.00034','0.00009'])
        self.assertTrue(all(r['cost_basis']=='usage_price_estimate' for r in responses))
        from operator_executor_test_support import evidence_path
        artifact=evidence_path('m4-cache', provider+('-1h' if mode=='1h' else '')+'-two-turn.json')
        artifact.write_text(json.dumps(dict(provider=provider,
            config=config.model_dump(mode='json'),wire_usages=wire_usage,responses=responses,
            requests=bodies,model_settings=executor.executor_model_settings(config),
            reservation='conservative upper rates unchanged; response cost is usage-price estimate'),indent=2)+'\n')

    def test_one_hour_actual_sdk_write_read_anthropic(self):
        value=self.config_with_cache('anthropic','1h').model_dump(mode='json')
        value['journal_path']=str(self.private/'anthropic-1h.jsonl')
        with patch.object(self,'config_with_cache',return_value=ExecutorConfig.model_validate(value)):
            self.two_turns('anthropic',mode='1h')

    def test_one_hour_usage_split_and_prices_reject_ambiguity(self):
        config=self.config_with_cache(mode='1h')
        usage=RequestUsage(input_tokens=140,output_tokens=2,cache_read_tokens=30,cache_write_tokens=100,cache_write_1h_tokens=75)
        raw=dict(input_tokens=10,output_tokens=2,cache_read_input_tokens=30,cache_creation_input_tokens=100,
            cache_creation=dict(ephemeral_5m_input_tokens=25,ephemeral_1h_input_tokens=75))
        admission=Admission(config);bound=admission.reserve(140)
        self.assertGreaterEqual(bound,Decimal('0.000721'))
        buckets=executor.validate_usage(usage,raw,cache_mode='1h')
        self.assertEqual(config.pricing.estimate(140,2,**buckets),Decimal('0.000721'))
        self.assertEqual(admission.reconcile(140,2,**buckets),Decimal('0.000721'))
        admission.config=admission.config.model_copy(update={'soft_budget_usd':'0.000721'})
        with self.assertRaisesRegex(AdmissionError,'soft_target_reached'):admission.reserve(1)
        admission=Admission(config.model_copy(update={'admitted_ceiling_usd':'0.000721'}))
        with self.assertRaisesRegex(AdmissionError,'admitted_ceiling'):admission.reserve(140)
        for mode in ('missing','unknown','negative','boolean','over-total','sdk-disagrees','top-disagrees','raw-total'):
            u=copy.deepcopy(usage);wire=copy.deepcopy(raw)
            if mode=='missing':wire.pop('cache_creation')
            elif mode=='unknown':wire['cache_creation']['unknown']=0
            elif mode=='negative':wire['cache_creation']['ephemeral_1h_input_tokens']=-1
            elif mode=='boolean':wire['cache_creation']['ephemeral_1h_input_tokens']=True
            elif mode=='over-total':u.cache_write_1h_tokens=101
            elif mode=='sdk-disagrees':u.cache_write_1h_tokens=74
            elif mode=='top-disagrees':wire.update(ephemeral_5m_input_tokens=100,ephemeral_1h_input_tokens=0)
            else:wire['cache_creation_input_tokens']=99
            admission=Admission(config);bound=admission.reserve(1000)
            with self.subTest(mode=mode),self.assertRaises(AdmissionError):
                b=executor.validate_usage(u,wire,cache_mode='1h');admission.reconcile(u.input_tokens,u.output_tokens,**b)
            self.assertEqual(admission.uncertain,bound)
            with self.assertRaisesRegex(AdmissionError,'unknown_previous_cost'):admission.reserve(1)
        for rate in (None,'0','-1','9'):
            value=config.model_dump(mode='json');value['pricing']['cache_write_1h_usd_per_million']=rate
            with self.subTest(rate=rate),self.assertRaises(ValueError):ExecutorConfig.model_validate(value)
        from cs.operator_executor_config import cache_request_matches
        self.assertTrue(cache_request_matches(config,dict(cache_control=dict(type='ephemeral',ttl='1h'))))
        for marker in ({'type':'ephemeral'},{'type':'ephemeral','ttl':'5m'},{'type':'ephemeral','ttl':'2h'}):
            self.assertFalse(cache_request_matches(config,dict(cache_control=marker)))
        self.assertFalse(cache_request_matches(config,dict(cache_control=dict(type='ephemeral',ttl='1h'),
            messages=[dict(cache_control=dict(type='ephemeral',ttl='5m'))])))

    def test_anthropic_actual_sdk_two_turn_cache_write_read(self):
        self.two_turns('anthropic')

    def test_runtime_bootstrap_cache_point_survives_long_tool_history(self):
        for provider in ('anthropic','openrouter'):
            for mode in ('5m','disabled','1h'):
                enabled=mode!='disabled'
                with self.subTest(provider=provider,cache=enabled):
                    value=self.config_with_cache(provider,mode).model_dump(mode='json')
                    if not enabled:value['cache_mode']='disabled'
                    value['journal_path']=str(self.private/(provider+mode+'.jsonl'))
                    config=ExecutorConfig.model_validate(value)
                    runtime=executor.ExecutorRuntime(config)
                    bodies=[];bootstrap=[]
                    original_bootstrap=runtime.tools.bootstrap
                    def capture_bootstrap():
                        result=original_bootstrap();bootstrap.append(copy.deepcopy(result))
                        return result
                    async def transport(request):
                        bodies.append(decode(request.content))
                        turn=len(bodies)
                        content=([dict(type='tool_use',id='pause-'+str(turn),name='pause_status',input={})]
                            if turn<=12 else [dict(type='text',text='Local transport fixture only')])
                        return httpx2.Response(200,json=dict(id='runtime-'+str(turn),type='message',role='assistant',
                            model='fixture-model',content=content,stop_reason='tool_use' if turn<=12 else 'end_turn',
                            usage=dict(input_tokens=20,output_tokens=1)))
                    original=httpx2.AsyncClient
                    class Client(original):
                        def __init__(self,*args,**kwargs):
                            kwargs['transport']=httpx2.MockTransport(transport)
                            super().__init__(*args,**kwargs)
                    with patch.dict(os.environ,{config.api_key_env:'fixture-cache-key'}), \
                            patch('socket.socket.connect',side_effect=AssertionError('network disabled')), \
                            patch('socket.socket.connect_ex',side_effect=AssertionError('network disabled')), \
                            patch('socket.getaddrinfo',side_effect=AssertionError('network disabled')), \
                            patch('httpx2.AsyncClient',Client), \
                            patch.object(runtime.tools,'bootstrap',side_effect=capture_bootstrap), \
                            patch('pydantic_ai.models.anthropic.check_allow_model_requests',lambda:None):
                        terminal=asyncio.run(runtime.run('Transport-only fixture Ω'))
                    self.assertEqual(terminal,'held')
                    self.assertEqual(len(bodies),13)
                    self.assertGreater(len(bodies[-1]['messages']),20)
                    expected=canonical(dict(executor_bootstrap=bootstrap[0],operator_prompt='Transport-only fixture Ω')).decode()
                    def points(value):
                        found=[]
                        if isinstance(value,dict):
                            if 'cache_control' in value:found.append(value['cache_control'])
                            for item in value.values():found.extend(points(item))
                        elif isinstance(value,list):
                            for item in value:found.extend(points(item))
                        return found
                    from cs.operator_executor_evidence import page_archive_maps
                    rows=[r.payload for r in parse_journal(Path(config.journal_path))]
                    requests=[r for r in rows if r.kind=='model_request']
                    submissions=[r for r in rows if r.kind=='provider_submission']
                    responses=[r for r in rows if r.kind=='model_response']
                    self.assertEqual([r.request_id for r in requests],[r.request_id for r in submissions])
                    self.assertEqual([r.request_id for r in requests],[r.request_id for r in responses])
                    self.assertTrue(all(r.status=='ok' for r in responses))
                    for index,body in enumerate(bodies):
                        blocks=body['messages'][0]['content']
                        self.assertEqual([b['text'] for b in blocks],[expected])
                        self.assertEqual(blocks[0].get('cache_control'),dict(type='ephemeral',ttl=mode) if enabled else None)
                        markers=points(body)
                        self.assertEqual(bool(markers),enabled)
                        self.assertLessEqual(len(markers),4)
                        self.assertTrue(all(p==dict(type='ephemeral',ttl=mode) for p in markers))
                        self.assertEqual(body['messages'][1::2],[
                            dict(role='assistant',content=[dict(type='tool_use',id='pause-'+str(n),name='pause_status',input={})])
                            for n in range(1,index+1)])
                        sdk=decode(Path(requests[index].messages.path).read_bytes())
                        self.assertEqual(page_archive_maps(sdk),page_archive_maps(body))
                        self.assertEqual(len(Path(submissions[index].body.path).read_bytes())+1024<=requests[index].input_token_estimate,True)
                    from operator_executor_test_support import evidence_path
                    from cs.operator_executor_protocol import sha256
                    evidence_path('m4-cache',provider+'-'+mode+'-long-history.json').write_text(json.dumps(dict(
                        config=config.model_dump(mode='json'),requests=bodies,
                        body_sha256=[sha256(Path(row.body.path).read_bytes()) for row in submissions],
                        model_settings=executor.executor_model_settings(config),bootstrap_sha256=sha256(expected.encode()),
                        page_maps_equal=True,history_blocks=len(bodies[-1]['messages']))))
                    end=rows[-1]
                    self.assertEqual(end.outstanding_request_ids,[])
                    self.assertEqual(end.outstanding_tool_ids,[])
                    self.assertEqual(Decimal(end.uncertain_cost_usd),0)
                    self.assertIn('incomplete_workflow_phases',end.diagnostic.observed)

    def test_actual_sdk_unsupported_one_hour_write_retains_reservation(self):
        self.two_turns('anthropic',invalid=True)

    def test_actual_sdk_missing_one_hour_split_retains_reservation(self):
        self.two_turns('anthropic',invalid=True,mode='1h')

    def test_cache_miss_and_uncached_keep_categories_separate(self):
        config=self.config_with_cache()
        usage=RequestUsage(input_tokens=50,output_tokens=2)
        buckets=executor.validate_usage(usage,dict(input_tokens=50,output_tokens=2))
        admission=Admission(config);admission.reserve(100)
        self.assertEqual(admission.reconcile(50,2,**buckets),Decimal('0.00012'))
        self.assertEqual(config.pricing.estimate(50,2),Decimal('0.00012'))
        uncached=self.config.model_copy(deep=True)
        self.assertEqual(Admission(uncached).config.cache_mode,'disabled')
        self.assertEqual(executor.executor_model_settings(uncached),dict(max_tokens=100,parallel_tool_calls=False))
        self.assertEqual(uncached.pricing.estimate(50,2),Decimal('0.000052'))

    def test_invalid_cache_buckets_or_usage_retain_reservation(self):
        config=self.config_with_cache()
        good=RequestUsage(input_tokens=120,output_tokens=3,cache_read_tokens=100)
        raw=dict(input_tokens=20,output_tokens=3,cache_read_input_tokens=100,cache_creation_input_tokens=0)
        for mode in ('sum','negative','boolean','one-hour','missing-usage','missing-input','split','raw-mismatch','unmeasured','reasoning'):
            usage=copy.deepcopy(good);wire=copy.deepcopy(raw)
            if mode=='sum':usage.cache_write_tokens=21
            elif mode=='negative':usage.cache_read_tokens=-1
            elif mode=='boolean':usage.cache_read_tokens=True
            elif mode=='one-hour':usage.cache_write_1h_tokens=1
            elif mode=='missing-usage':wire={}
            elif mode=='missing-input':wire.pop('input_tokens')
            elif mode=='split':wire['cache_creation']=dict(ephemeral_5m_input_tokens=0,ephemeral_1h_input_tokens=1)
            elif mode=='raw-mismatch':wire['cache_read_input_tokens']=99
            elif mode=='unmeasured':usage.unmeasured_requests=1
            else:usage.output_reasoning_tokens=4
            admission=Admission(config);bound=admission.reserve(1000)
            with self.subTest(mode=mode),self.assertRaises(AdmissionError):
                buckets=executor.validate_usage(usage,wire)
                admission.reconcile(usage.input_tokens,usage.output_tokens,**buckets)
            self.assertEqual(admission.uncertain,bound)
            with self.assertRaisesRegex(AdmissionError,'unknown_previous_cost'):admission.reserve(10)

    def test_cache_directive_unknown_ttl_or_unrequested_marker_refuses(self):
        from cs.operator_executor_config import cache_request_matches
        config=self.config_with_cache()
        self.assertTrue(cache_request_matches(config,dict(cache_control=dict(type='ephemeral',ttl='5m'))))
        self.assertTrue(cache_request_matches(config,dict(cache_control=dict(type='ephemeral'))))
        for body in ({},dict(cache_control=dict(type='ephemeral',ttl='1h')),
                dict(cache_control=dict(type='ephemeral',ttl='5m',unknown=True)),dict(cache_control=False)):
            self.assertFalse(cache_request_matches(config,body))
        self.assertFalse(cache_request_matches(self.config,dict(cache_control=dict(type='ephemeral',ttl='5m'))))

    def test_explicit_prices_required_and_bound_unchanged(self):
        value=self.config.model_dump(mode='json');value['cache_mode']='5m'
        with self.assertRaises(ValueError):ExecutorConfig.model_validate(value)
        configured=self.config_with_cache()
        value=configured.model_dump(mode='json');value['pricing']['cache_write_5m_usd_per_million']='5'
        with self.assertRaises(ValueError):ExecutorConfig.model_validate(value)
        value=configured.model_dump(mode='json');value['pricing']['cache_read_usd_per_million']=None
        with self.assertRaises(ValueError):ExecutorConfig.model_validate(value)
        bound=Admission(configured).reserve(1000)
        self.assertEqual(bound,Decimal('0.0052'))
        self.assertEqual(configured.admitted_ceiling_usd,self.config.admitted_ceiling_usd)
        with self.assertRaises(AdmissionError):self.config.pricing.estimate(120,3,100)


for name in list(vars(ExecutorTests)):
    if name.startswith('test_') and name not in vars(CacheTests):setattr(CacheTests,name,None)
del ExecutorTests

if __name__=='__main__':unittest.main()
