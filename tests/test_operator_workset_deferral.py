"""Real private reservation exclusion, independent consumer, no external reads."""
import copy
import hashlib
import importlib.util
import io
import json
import os
import shlex
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr
from cs import operator_read_outcomes as outcomes, operator_workset as workset, cli
from cs.operator_health import identity

ACTOR = os.environ.get('CS_DEFERRAL_ACTOR_COMMON')

def hashed(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

class DeferralTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.state=Path(self.tmp.name);(self.state/'operator-runs').mkdir(mode=0o700)
        self.directory=self.state/'operator-runs'/'run-test';self.directory.mkdir(mode=0o700)
        (self.state/'operator-workset').mkdir(mode=0o700)
        self.ctx=dict(directory=str(self.directory),nonce='a'*32,owner_uid='owner',supervisor=identity(os.getpid())[0],workset_enabled=True)
        self.settings=SimpleNamespace(engine_owner_uid='owner',state_dir=str(self.state))
        self.reservation=dict(nonce=self.ctx['nonce'],owner_uid='owner',digest='b'*64,selected=[hashed('<selected@example.test>')],contacts=[hashed('selected@example.test')])
        self.run={k:self.reservation[k]for k in ['digest','selected','contacts']}
        self.cursor=dict(version=1,owner=hashed('owner'),order=1,roots={hashed('<selected@example.test>'):dict(revision='c'*64,order=1)},runs={hashed(self.ctx['nonce']):self.run})
        self.write(self.directory/'workset-reserved.json',self.reservation);self.write(self.state/'operator-workset/cursor.json',self.cursor)
        self.env=patch.dict(os.environ,CS_OPERATOR_HEALTH_CONTEXT=json.dumps(self.ctx));self.env.start();self.addCleanup(self.env.stop)
        self.scope=outcomes.command_scope('.venv/bin/python -m cs dossier excluded@example.test')
        self.verifiers=[outcomes.outside_workset_value]
        if ACTOR:
            spec=importlib.util.spec_from_file_location('deferral_independent_actor',ACTOR);actor=importlib.util.module_from_spec(spec);spec.loader.exec_module(actor);self.verifiers.append(actor.outside_workset_value)
    def write(self,path,v):
        path.write_text(json.dumps(v));path.chmod(0o600)
    def value(self):
        with self.assertRaises(workset.OutsideSelectedWorkset) as error:
            workset.require_contact(self.settings,'excluded@example.test',typed_exclusion=True)
        return error.exception.value
    def test_valid_exclusion_and_selected_behavior(self):
        value=self.value()
        for verifier in self.verifiers:
            self.assertTrue(verifier(value,self.scope,'owner',self.ctx))
        self.assertIsNone(workset.require_contact(self.settings,'selected@example.test',typed_exclusion=True))
        for command in ['cs dossier excluded@example.test','.venv/bin/python -m cs dossier excluded@example.test --json','.venv/bin/python -m cs dossier excluded@example.test && true']:
            self.assertIsNone(outcomes.command_scope(command))
    def test_tampered_values_and_current_state_fail_both_consumers(self):
        value=self.value()
        for key,item in [('owner_uid','foreign'),('nonce','b'*32),('contact','selected@example.test'),('reservation_sha256','0'*64),('reason','OTHER'),('version',True)]:
            changed=copy.deepcopy(value);changed[key]=item
            for verifier in self.verifiers:self.assertFalse(verifier(changed,self.scope,'owner',self.ctx),key)
        self.cursor['runs'][hashed(self.ctx['nonce'])]['digest']='c'*64;self.write(self.state/'operator-workset/cursor.json',self.cursor)
        for verifier in self.verifiers:self.assertFalse(verifier(value,self.scope,'owner',self.ctx))
    def test_generic_errors_never_become_typed_exclusion(self):
        for email in ['not-email','bad@example.test && true']:
            with self.assertRaises(workset.WorksetError)as error:workset.require_contact(self.settings,email,typed_exclusion=True)
            self.assertNotIsInstance(error.exception,workset.OutsideSelectedWorkset)
        (self.directory/'workset-reserved.json').unlink()
        with self.assertRaises(workset.WorksetError)as error:workset.require_contact(self.settings,'excluded@example.test',typed_exclusion=True)
        self.assertNotIsInstance(error.exception,workset.OutsideSelectedWorkset)
    def test_excluded_cli_zero_deep_reads_and_capture_exact_value(self):
        with patch.object(cli.config,'load',return_value=self.settings),patch('cs.operator_dossier.run',side_effect=AssertionError('deep read forbidden'))as deep,patch.object(outcomes,'capture_workset_deferral')as capture,redirect_stderr(io.StringIO())as stderr:
            self.assertEqual(cli.cmd_dossier(SimpleNamespace(email='excluded@example.test')),3)
        deep.assert_not_called();capture.assert_called_once();self.assertEqual(stderr.getvalue(),'Scheduled work deferred outside selected workset\n')
        self.assertTrue(outcomes.outside_workset_value(capture.call_args.args[1],self.scope,'owner',self.ctx))
    def test_complete_cursor_schema_and_trusted_layout(self):
        value=self.value();path=self.state/'operator-workset/cursor.json';original=copy.deepcopy(self.cursor)
        variants=[]
        for key in ['order','roots','runs','owner','version']:
            changed=copy.deepcopy(original);del changed[key];variants.append(changed)
        for key,item in [('order',-1),('order',True),('roots',{'bad':'bad'}),('runs',{'bad':'bad'}),('version',True)]:
            changed=copy.deepcopy(original);changed[key]=item;variants.append(changed)
        changed=copy.deepcopy(original);changed['runs']['d'*64]=dict(digest='e'*64,selected=[],contacts=['f'*64,'f'*64]);variants.append(changed)
        changed=copy.deepcopy(original);changed['roots']['d'*64]=dict(revision='e'*64,order=2);variants.append(changed)
        for changed in variants:
            self.write(path,changed)
            for verifier in self.verifiers:self.assertFalse(verifier(value,self.scope,'owner',self.ctx))
            with self.assertRaises(workset.WorksetError)as error:workset.require_contact(self.settings,'excluded@example.test',typed_exclusion=True)
            self.assertNotIsInstance(error.exception,workset.OutsideSelectedWorkset)
        later=copy.deepcopy(original);later['runs']['d'*64]=dict(digest='e'*64,selected=[],contacts=[]);self.write(path,later)
        for verifier in self.verifiers:self.assertTrue(verifier(value,self.scope,'owner',self.ctx))
        moved=self.directory.parent/'not-a-run';self.directory.rename(moved);ctx={**self.ctx,'directory':str(moved)}
        for verifier in self.verifiers:self.assertFalse(verifier(value,self.scope,'owner',ctx))

    def test_search_producer_requires_genuine_exclusion_and_never_rpc(self):
        for contact, expected in [('excluded@example.test', True), ('selected@example.test', False)]:
            params=json.dumps(dict(query=contact,limit=5))
            argv=['rpc','emails.search',params]
            with patch.object(cli.config,'load',return_value=self.settings), patch.object(sys,'argv',['cs',*argv]), patch.object(cli.rpc,'call_sync',side_effect=AssertionError('RPC forbidden')) as rpc, patch.object(outcomes.transport,'capture') as capture, redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(cli.cmd_rpc(SimpleNamespace(method='emails.search',params=params,timeout=30)),3)
            rpc.assert_not_called()
            self.assertEqual(stderr.getvalue(),'Scheduled deep mail read deferred outside selected workset\n')
            self.assertEqual(capture.call_count,int(expected))
            if expected:
                output,value,code,owner=capture.call_args.args
                scope=outcomes.command_scope('.venv/bin/python -m cs '+shlex.join(argv))
                self.assertEqual(output,outcomes.workset_deferral_output(scope))
                self.assertEqual(code,3)
                for verifier in self.verifiers:self.assertTrue(verifier(value,scope,owner,self.ctx))
        for bad in ['{', '{"query":"excluded@example.test","limit":true}', '{"query":"excluded@example.test","query":"excluded@example.test","limit":5}']:
            with patch.object(cli.config,'load',return_value=self.settings),patch.object(sys,'argv',['cs','rpc','emails.search',bad]),patch.object(cli.rpc,'call_sync',side_effect=AssertionError('RPC forbidden')) as rpc,patch.object(outcomes.transport,'capture') as capture,redirect_stderr(io.StringIO()):
                self.assertEqual(cli.cmd_rpc(SimpleNamespace(method='emails.search',params=bad,timeout=30)),3)
            rpc.assert_not_called();capture.assert_not_called()
        for change in ['foreign','corrupt','missing']:
            self.reservation['owner_uid']='owner'
            self.write(self.directory/'workset-reserved.json',self.reservation)
            self.write(self.state/'operator-workset/cursor.json',self.cursor)
            params=json.dumps(dict(query='excluded@example.test',limit=5))
            if change=='foreign':
                self.reservation['owner_uid']='foreign';self.write(self.directory/'workset-reserved.json',self.reservation)
            elif change=='corrupt':(self.state/'operator-workset/cursor.json').write_text('{}')
            else:(self.directory/'workset-reserved.json').unlink()
            with patch.object(cli.config,'load',return_value=self.settings),patch.object(sys,'argv',['cs','rpc','emails.search',params]),patch.object(cli.rpc,'call_sync',side_effect=AssertionError('RPC forbidden')) as rpc,patch.object(outcomes.transport,'capture') as capture,redirect_stderr(io.StringIO()):
                self.assertEqual(cli.cmd_rpc(SimpleNamespace(method='emails.search',params=params,timeout=30)),3)
            rpc.assert_not_called();capture.assert_not_called()

    def test_search_scope_strict_json_and_independent_parsers(self):
        parsers=[outcomes.command_scope]
        if ACTOR:
            spec=importlib.util.spec_from_file_location('search_actor',ACTOR);actor=importlib.util.module_from_spec(spec);spec.loader.exec_module(actor);parsers.append(actor.business_read_scope)
        prefix='.venv/bin/python -m cs rpc emails.search '
        good=json.dumps(dict(query='Excluded@Example.test',limit=5))
        expected=outcomes.command_scope(prefix+shlex.quote(good))
        for parser in parsers:
            self.assertEqual(parser(prefix+shlex.quote(good)),expected)
            for limit in [1,100]:self.assertIsNotNone(parser(prefix+shlex.quote(json.dumps(dict(query='x@example.test',limit=limit)))))
            for raw in ['{', '[]', '{"query":"x@example.test","limit":NaN}', '{"query":"x@example.test","limit":5,"limit":6}', *[json.dumps(dict(query='x@example.test',limit=v))for v in [True,False,0,101,1.0,'5',None]],json.dumps(dict(query='from:x@example.test',limit=5)),json.dumps(dict(query='x@example.test',limit=5,folder='all')),json.dumps(dict(query='.x@example.test',limit=5)),json.dumps(dict(query='x@-example.test',limit=5)),json.dumps(dict(query='x@example.test && true',limit=5))]:
                self.assertIsNone(parser(prefix+shlex.quote(raw)),raw)
            for suffix in [' --timeout 5',' && true',';true',' | cat'," '"]:
                self.assertIsNone(parser(prefix+shlex.quote(good)+suffix))

    def test_private_metadata_and_duplicate_json_reject(self):
        value=self.value();p=self.directory/'workset-reserved.json';p.chmod(0o644)
        for verifier in self.verifiers:self.assertFalse(verifier(value,self.scope,'owner',self.ctx))
        p.chmod(0o600);p.write_text('{"nonce":"x","nonce":"y"}')
        with self.assertRaises(workset.WorksetError)as error:workset.require_contact(self.settings,'excluded@example.test',typed_exclusion=True)
        self.assertNotIsInstance(error.exception,workset.OutsideSelectedWorkset)

if __name__=='__main__':unittest.main()
