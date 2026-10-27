"""Actual health predicate collisions retain bounded diagnostic distinctions."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch, PropertyMock

from cs import operator_health as health
from cs import operator_recovery as recovery
from cs import observability_causal as causal
from cs.observability import EventStore, context, current_context, safe_metadata
from cs.observability_store import _validate_event
from cs.monitor_details import safe_detail


class CausalContractEdges(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / 'discovery'
        self.directory.mkdir(mode=0o700)
        self.store = EventStore(self.root / 'events', 'owner')
        if evidence := os.environ.get('CAUSAL_EDGE_EVIDENCE_DIR'):
            self.addCleanup(self.save_evidence, Path(evidence))
        self.context = {'directory': str(self.directory), 'nonce': 'private-nonce', 'supervisor': {'pid': 1, 'started_ticks': 1}}
        self.child = {'pid': 2, 'started_ticks': 2}
        self.value = {'read_incomplete': None, 'assignment_incomplete': False, 'open': [], 'human_work': [], 'assignment_audit': [], 'operational_fixture_discovery': []}

    def save_evidence(self, directory):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / (self._testMethodName + '.json')
        path.write_text(json.dumps(self.store.events(limit=200)))
        path.chmod(0o600)

    def record(self, value=None, **changes):
        value = self.value if value is None else value
        digest = hashlib.sha256((json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n').encode()).hexdigest()
        record = {'nonce': 'private-nonce', 'owner_uid': 'owner', 'ancestry': [{'pid': 3}, self.child, self.context['supervisor']], 'exit_code': 0, 'output_sha256': digest, 'discovery': value}
        record.update(changes)
        path = self.directory / 'discovery.json'
        path.write_text(json.dumps(record))
        path.chmod(0o600)
        return path

    def emitted(self, check, cause):
        value = causal.selected()
        self.assertEqual((value['check'], value['cause']), (check, cause))
        self.assertEqual(value['refs']['run_id'], 'a' * 32)
        self.assertEqual(value['refs']['attempt_id'], 'b' * 32)
        event = self.store.emit('verification', 'failed', causal=value)
        self.assertIsNotNone(event)
        self.assertTrue(_validate_event(event, self.store))
        self.assertEqual(self.store.events()['events'][-1]['causal'], value)
        self.assertEqual(safe_detail({'causal': value})['causal'], value)
        self.assertNotIn('PRIVATE_CANARY', json.dumps(event))
        return value

    def test_assess_boundary_discriminators(self):
        cases = [
            ('missing', 'discovery_artifact_presence', 'artifact_missing'),
            ('access', 'discovery_artifact_access', 'artifact_unreadable'),
            ('encoding', 'discovery_artifact_encoding', 'artifact_invalid'),
            ('identity', 'discovery_identity', 'identity_mismatch'),
            ('digest', 'discovery_payload_digest', 'digest_mismatch'),
            ('shape', 'discovery_payload_shape', 'shape_invalid'),
            ('exit', 'discovery_exit', 'exit_mismatch'),
            ('workset', 'workset_identity', 'workset_invalid'),
            ('reservation', 'workset_reservation', 'reservation_mismatch'),
        ]
        for case, check, cause in cases:
            with self.subTest(case=case), causal.scope(), context({'run_id': 'a' * 32, 'attempt_id': 'b' * 32}):
                selected_context = dict(self.context)
                path = self.record()
                if case == 'missing':
                    path.unlink()
                elif case == 'access':
                    path.chmod(0o644)
                elif case == 'encoding':
                    path.write_text('PRIVATE_CANARY invalid json')
                elif case == 'identity':
                    self.record(nonce='PRIVATE_CANARY')
                elif case == 'digest':
                    self.record(output_sha256='0' * 64)
                elif case == 'shape':
                    self.record({'read_incomplete': None})
                elif case == 'exit':
                    self.record(exit_code=3)
                elif case in ('workset', 'reservation'):
                    selected_context.update(workset_enabled=True, owner_uid='owner')
                    if case == 'reservation':
                        value = {**self.value, 'triage_workset': {'complete': True, 'limit': 2, 'selected': []}}
                        self.record(value)
                self.assertEqual(health.assess(selected_context, self.child, 'owner'), 'discovery_evidence_invalid')
                self.emitted(check, cause)

    def test_required_phase_and_discovery_cardinality_collisions(self):
        self.record()
        phases = [{'phase': value} for value in ['identity', 'configuration', 'tasks', 'discovery', 'review', 'campaigns']]
        payload = json.dumps(self.value, ensure_ascii=False, indent=2) + '\n'
        def discovery(identity):
            return {'message': {'content': [{'type': 'tool_use', 'id': identity, 'name': 'Bash', 'input': {'command': '.venv/bin/python -m cs unanswered --days 14 --json --all-buckets'}}]}}
        def completed(identity):
            return {'message': {'content': [{'type': 'tool_result', 'tool_use_id': identity, 'content': payload}]}}
        cases = [([], phases[1:], 'required_phase_presence', 'required_phase_absent', {'required': True, 'present': False, 'observed': 1}), ([], phases, 'discovery_tool_cardinality', 'discovery_cardinality_invalid', {'expected': 1, 'uses': 0, 'results': 0}), ([discovery('one')], phases, 'discovery_tool_cardinality', 'discovery_cardinality_invalid', {'expected': 1, 'uses': 1, 'results': 0}), ([discovery('one'), completed('one'), discovery('two'), completed('two')], phases, 'discovery_tool_cardinality', 'discovery_cardinality_invalid', {'expected': 1, 'uses': 2, 'results': 2})]
        for events, selected_phases, check, cause, facts in cases:
            with self.subTest(check=check, facts=facts), causal.scope(), context({'run_id': 'a' * 32, 'attempt_id': 'b' * 32}):
                self.assertEqual(health.inspection_failure(events, self.context, selected_phases), 'execution_phase_incomplete')
                value = self.emitted(check, cause)
                self.assertEqual(value['phase'], 'identity' if check == 'required_phase_presence' else 'discovery')
                self.assertEqual(value['facts'], facts)
        with causal.scope():
            self.assertEqual(health.inspection_failure([discovery('one'), completed('one')], self.context, phases), '')
            self.assertIsNone(causal.selected())

    def use(self, identity='tool'):
        return {'session_id': 'PRIVATE_CANARY session', 'message': {'content': [{'type': 'tool_use', 'id': identity, 'name': 'Bash', 'input': {'command': 'cs tasks --json PRIVATE_CANARY'}}]}}

    def result(self, error=False):
        return {'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'tool', 'is_error': error}]}}

    def test_read_identity_result_proof_and_completion_collisions(self):
        command = 'cs tasks --json PRIVATE_CANARY'
        proof = {'tool_use_id': 'tool', 'session_id': 'PRIVATE_CANARY session', 'command_digest': hashlib.sha256(command.encode()).hexdigest()}
        cases = [([self.use(None)], [], 'read_tool_identity', 'read_tool_id_invalid', {}), ([self.use(), self.use()], [], 'read_tool_identity', 'read_tool_id_duplicate', {}), ([self.use(), self.result(), self.result()], [], 'read_result_uniqueness', 'read_result_duplicate', {}), ([self.use(), self.result(True)], [], 'read_error_proof_cardinality', 'read_error_unproved', {'expected': 1, 'matching_proofs': 0}), ([self.use(), self.result(True)], [proof, proof], 'read_error_proof_cardinality', 'read_error_unproved', {'expected': 1, 'matching_proofs': 2}), ([self.use()], [], 'read_result_completeness', 'read_result_missing', {'reads': 1, 'completed': 0})]
        for events, proofs, check, cause, facts in cases:
            with self.subTest(cause=cause, proofs=len(proofs)), causal.scope(), context({'run_id': 'a' * 32, 'attempt_id': 'b' * 32}):
                self.assertIs(health.native_read_failed(events, proofs), True)
                value = self.emitted(check, cause)
                self.assertEqual(value['facts'], facts)
                self.assertEqual(value['command'], 'tasks')
                self.assertEqual(value['phase'], 'tasks')
                self.assertEqual(value['refs']['tool_id_hash'] is None, cause == 'read_tool_id_invalid')
        with causal.scope():
            self.assertIs(health.native_read_failed([self.use(), self.result(True)], [proof]), False)
            self.assertIsNone(causal.selected())

    def test_real_successful_process_native_predicates_and_precedence(self):
        clean = [{'type': 'result', 'is_error': False, 'terminal_reason': 'success'}]
        error = [{'type': 'result', 'is_error': True, 'terminal_reason': 'api_error', 'result': 'PRIVATE_CANARY'}]
        cases = [
            ({'code': 7}, clean, 'process_exit', 'process_nonzero'),
            ({'malformed': True}, clean, 'native_capture_json', 'native_capture_malformed'),
            ({'overflow': True}, clean, 'native_capture_capacity', 'native_capture_overflow'),
            ({'timed_out': True}, clean, 'process_wait', 'process_wait_timeout'),
            ({}, [], 'native_terminal_presence', 'terminal_unavailable'),
            ({}, error, 'native_terminal_error', 'terminal_error'),
            ({'code': 7, 'malformed': True, 'overflow': True, 'timed_out': True}, [], 'process_exit', 'process_nonzero'),
            ({'malformed': True, 'overflow': True, 'timed_out': True}, [], 'native_capture_json', 'native_capture_malformed'),
            ({'overflow': True, 'timed_out': True}, [], 'native_capture_capacity', 'native_capture_overflow'),
            ({'timed_out': True}, [], 'process_wait', 'process_wait_timeout'),
        ]
        cases.extend(({}, [{'type': 'result', 'is_error': False, 'terminal_reason': reason}], 'native_terminal_reason', 'terminal_rejected') for reason in ('api_error', 'budget_exhausted', 'max_turns', 'error'))
        for changes, events, check, cause in cases:
            with self.subTest(changes=changes, check=check, events=events), causal.scope(), context({'run_id': 'a' * 32, 'attempt_id': 'b' * 32}):
                attempt = recovery.Attempt(**{'code': 0, 'events': events, **changes})
                self.assertIs(recovery._successful(attempt), False)
                value = self.emitted(check, cause)
                self.assertEqual(attempt.causal, value)
                self.assertEqual(value['facts'], {'process_exit': attempt.code, 'malformed': attempt.malformed, 'overflow': attempt.overflow, 'timed_out': attempt.timed_out, **recovery.diagnostics.native_facts(attempt.result)})
                self.assertEqual(value['method'], 'operator.native.terminal')
                self.assertIs(recovery._successful(attempt), False)
                self.assertEqual(attempt.causal, value)
        with causal.scope():
            attempt = recovery.Attempt(0, clean)
            self.assertIs(recovery._successful(attempt), True)
            self.assertIsNone(causal.selected())
            self.assertIsNone(getattr(attempt, 'causal', None))

    def test_concurrent_contexts_restore_and_failures_keep_first_cause(self):
        async def attempt(identity):
            with causal.scope(), context({'run_id': identity * 32, 'attempt_id': identity * 32}):
                health.native_read_failed([self.use()])
                await asyncio.sleep(0)
                health.native_read_failed([self.use(None)])
                value = causal.selected()
                self.assertEqual(value['cause'], 'read_result_missing')
                self.assertEqual(value['refs']['attempt_id'], identity * 32)
                return value
        async def execute():
            return await asyncio.gather(attempt('a'), attempt('b'))
        before = current_context()
        values = asyncio.run(execute())
        self.assertNotEqual(values[0]['refs']['attempt_id'], values[1]['refs']['attempt_id'])
        self.assertIsNone(causal.selected())
        self.assertEqual(current_context(), before)

    def test_native_cost_phase_precedence_and_closed_facts(self):
        self.record()
        with causal.scope(), context({'run_id': 'a' * 32, 'attempt_id': 'b' * 32}):
            attempt = recovery.Attempt(0, [{'type': 'result', 'terminal_reason': 'completed',
                'is_error': False, 'total_cost_usd': 3.158979, 'result': 'PRIVATE_CANARY'}])
            self.assertTrue(recovery._successful(attempt))
            causal.child(None, **recovery.diagnostics.native_facts(attempt.result))
            phases = [{'phase': x} for x in ['identity', 'configuration', 'tasks', 'discovery', 'review']]
            self.assertEqual(health.inspection_failure([], self.context, phases), 'execution_phase_incomplete')
            value = self.emitted('required_phase_presence', 'required_phase_absent')
            self.assertEqual(value['phase'], 'campaigns')
            self.assertEqual(value['facts']['native_total_cost_usd'], 3.158979)
            self.assertEqual(value['facts']['native_terminal_reason'], 'completed')
            self.assertFalse(value['facts']['native_is_error'])
            for key, invalid in [('native_total_cost_usd', True), ('native_total_cost_usd', -1),
                                 ('native_total_cost_usd', float('nan')), ('native_total_cost_usd', float('inf')),
                                 ('native_terminal_reason', 'PRIVATE_CANARY'), ('reads', 1.5)]:
                with self.assertRaises(ValueError):
                    causal.validate({**value, 'facts': {**value['facts'], key: invalid}})
        for reason in ['budget_exhausted', 'max_turns', 'api_error']:
            with causal.scope(), context({'run_id': 'a' * 32, 'attempt_id': 'b' * 32}):
                attempt = recovery.Attempt(0, [{'type': 'result', 'terminal_reason': reason,
                    'is_error': False, 'total_cost_usd': 4.1}])
                self.assertFalse(recovery._successful(attempt))
                health.inspection_failure([], self.context, [])
                self.assertEqual(causal.selected()['check'], 'native_terminal_reason')
                self.assertEqual(causal.selected()['facts']['native_terminal_reason'], reason)

    def test_real_run_refusal_observation_matches_native_predicate(self):
        from cs.config import Settings
        from cs.observability import store_for
        settings = Settings(slug='sample', engine_owner_uid='owner')
        binary = self.root / 'controlled-child'
        for reason in ['budget_exhausted', 'max_turns', 'api_error', 'error', 'completed']:
            result = {'type': 'result', 'terminal_reason': reason, 'is_error': False,
                      'total_cost_usd': 3.158979}
            binary.write_text('#!' + sys.executable + '\nimport json\nprint(' + repr(json.dumps(result)) + ')\n')
            binary.chmod(0o700)
            with self.subTest(reason=reason), patch.object(Settings, 'state_dir', new_callable=PropertyMock,
                    return_value=self.root), patch.object(recovery.config, 'load', return_value=settings), \
                    patch.dict(os.environ, {'CS_OPERATOR_ACCEPTANCE_RECEIPT': '', 'CS_OPERATOR_NATIVE_BINARY': ''}):
                attempt = recovery._run(str(binary), ['Write'], prompt='/controlled-observation')
                events = store_for(settings).events(limit=200)['events']
                event = next(row for row in events if row['event_id'] == attempt.child_event_id)
                observed = event['causal']
                expected = 'accepted' if reason == 'completed' else 'failed'
                self.assertEqual(observed['outcome'], expected)
                self.assertEqual(observed['facts']['native_terminal_reason'], reason)
                self.assertEqual(recovery._successful(attempt), reason == 'completed')
                if reason != 'completed':
                    with causal.scope():
                        causal.select(attempt)
                        health.inspection_failure([], self.context, [])
                        self.assertEqual(causal.selected()['check'], 'native_terminal_reason')

    def test_strict_payload_rejection_and_sink_failure(self):
        with causal.scope(), context({'run_id': 'a' * 32, 'attempt_id': 'b' * 32}):
            self.assertTrue(health.native_read_failed([self.use()]))
            value = copy.deepcopy(causal.selected())
            event = self.store.emit('verification', 'failed', causal=value)
            self.assertIsNotNone(event)
            for change in [{'version': 2}, {'cause': 'PRIVATE_CANARY'}, {'facts': {'reads': 'PRIVATE_CANARY'}}, {'facts': {'reads': -1}}, {'unexpected': True}]:
                invalid = {**value, **change}
                self.assertFalse(_validate_event({**event, 'causal': invalid}, self.store))
                with self.assertRaises(ValueError):
                    safe_metadata({'causal': invalid})
                with self.assertRaises(ValueError):
                    safe_detail({'causal': invalid})
            filtered = EventStore(self.root / 'filtered', 'owner', log_level='CRITICAL')
            self.assertIsNone(filtered.emit('verification', 'failed', causal=value))
            self.assertFalse(filtered.health()['available'])
            with patch('cs.observability_store.append', side_effect=OSError('PRIVATE_CANARY')), patch('cs.observability_store.record_failure', side_effect=OSError('PRIVATE_CANARY')), patch('cs.observability.sys.stderr.write', side_effect=OSError('PRIVATE_CANARY')):
                self.assertIsNone(self.store.emit('verification', 'failed', causal=value))
                self.assertEqual(self.store.failed_writes, 1)
                self.assertEqual(self.store.dropped_events, 1)
                self.assertEqual(causal.selected(), value)
            self.assertTrue(self.store.health()['available'])
            self.assertEqual(self.store.health()['status'], 'degraded')


if __name__ == '__main__':
    unittest.main()
