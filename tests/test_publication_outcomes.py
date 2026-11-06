"""Actual draft-reply argument dispatch preserves saved IDs without local publication."""
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch
from cs import cli, config, interactive_draft, rpc, gmail_drafts
from test_contextual_email import settings
from test_interactive_draft_continuity import DRAFT, ROOT, SOURCE_ID, TARGET


class Outcomes(unittest.TestCase):
    def invoke(self, mode, resume=False):
        calls=[]
        def call(s, method, params, timeout=None):
            calls.append(method)
            if method=='system.capabilities':
                return {} if mode=='unsupported' else {'exact_draft_publication':1}
            if method=='drafts.inspect':
                return {'ok':True,'draft':DRAFT,'expected_snapshot':'snapshot'}
            if method=='drafts.list':
                return [] if calls.count(method)==1 else [DRAFT]
            if method=='drafts.publish_review':
                if mode=='transport':raise TimeoutError()
                return {'version':1,'ok':True,'draft_id':DRAFT['id'],
                        'state':'review-visible','achieved_stages':['engine-saved','review-visible']}
            raise AssertionError(method)
        async def chat(*args,**kwargs):
            calls.append('generation')
            if resume:raise AssertionError('resume generated')
            if mode=='generation-error':raise RuntimeError('after create')
            return {'result':{}}
        verified={'id':SOURCE_ID,'target':TARGET,'sender':'customer@example.test',
                  'provider_body':'Source','provider_alternatives':[]}
        args=['draft-reply','--thread-id',ROOT,'--json']
        args+=['--resume-draft',DRAFT['id']] if resume else ['Prepare answer']
        output=io.StringIO()
        with patch.dict(os.environ,{},clear=True),patch.object(config,'load',return_value=settings()), \
             patch.object(rpc,'call_sync',side_effect=call),patch.object(rpc,'chat',side_effect=chat), \
             patch.object(interactive_draft,'source',return_value=verified), \
             patch.object(gmail_drafts,'append_draft',side_effect=AssertionError('local append')), \
             contextlib.redirect_stdout(output):
            rc=cli.main(args)
        return rc,json.loads(output.getvalue()),calls

    def test_resume_does_not_generate(self):
        rc,result,calls=self.invoke('ok',resume=True)
        self.assertEqual(rc,0)
        self.assertEqual(result['draft_id'],DRAFT['id'])
        self.assertNotIn('generation',calls)

    def test_old_engine_retains_engine_saved_identity(self):
        for resume in (False,True):
            rc,result,calls=self.invoke('unsupported',resume=resume)
            self.assertEqual(rc,3)
            self.assertEqual(result['draft_id'],DRAFT['id'])
            self.assertEqual(result['cause'],'publication-unsupported')
            self.assertEqual(result['achieved_stages'],['engine-saved'])
            self.assertNotIn('drafts.publish_review',calls)

    def test_generation_error_after_save_preserves_id_without_repeat(self):
        rc,result,calls=self.invoke('generation-error')
        self.assertEqual(rc,3)
        self.assertEqual(result['draft_id'],DRAFT['id'])
        self.assertEqual(calls.count('generation'),1)
        self.assertNotIn('drafts.publish_review',calls)

    def test_publication_transport_failure_preserves_id(self):
        rc,result,calls=self.invoke('transport')
        self.assertEqual(rc,3)
        self.assertEqual(result['draft_id'],DRAFT['id'])
        self.assertEqual(result['effect_certainty'],'unknown')
        self.assertEqual(calls.count('drafts.publish_review'),1)


    def test_resume_timeout_retains_operation_identity_and_uncertainty(self):
        with patch.object(interactive_draft, 'uuid4', return_value='operation-fixture'):
            rc,result,calls=self.invoke('transport',resume=True)
        self.assertEqual(rc,3)
        self.assertEqual(result['effect_certainty'],'unknown')
        self.assertEqual(result['operation_id'],'operation-fixture')
        self.assertEqual(result['next_action'],'inspect-operation')
        self.assertNotIn('generation',calls)

    def test_current_main_scheduled_mirror_requires_both_assignment_guards(self):
        from cs import task_assignment
        for second_refusal in (False, True):
            calls=[]
            def call(s,method,params,timeout=None):
                calls.append(method)
                if method=='drafts.list':return [] if calls.count(method)==1 else [DRAFT]
                raise AssertionError(method)
            async def chat(*a,**kw):return {'result':{}}
            def append(*a,**kw):
                self.assertEqual(guard.call_count,2)
                calls.append('append')
                return 'Drafts',[]
            effects=[None,task_assignment.AssignmentUnavailable('Held')] if second_refusal else [None,None]
            with patch.dict(os.environ,{'CS_OPERATOR_HEADLESS':'1'},clear=True), \
                 patch.object(config,'load',return_value=settings()), \
                 patch.object(task_assignment,'guard',side_effect=effects) as guard, \
                 patch.object(rpc,'call_sync',side_effect=call),patch.object(rpc,'chat',side_effect=chat), \
                 patch.object(gmail_drafts,'append_draft',side_effect=append) as publication, \
                 contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                rc=cli.main(['draft-reply','Answer','--thread-id',ROOT,'--source-id',SOURCE_ID])
            self.assertEqual(rc,3 if second_refusal else 0)
            self.assertEqual(guard.call_count,2)
            self.assertEqual(publication.call_count,0 if second_refusal else 1)
            self.assertEqual(calls,['drafts.list','drafts.list']+([] if second_refusal else ['append']))


if __name__=='__main__':unittest.main()
