"""Authenticated nonexecution is prospective and grants no business credit."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_operator_native_composition import constructed, producer, seal
from cs.operator_native_composition import composition, _DENIAL_MESSAGE

C33 = Path('/home/mal/.local/share/mrcall-operational-evidence/2026-10-19/ordinary-assignment-recovery-v33')
C34 = Path('/home/mal/.local/share/mrcall-operational-evidence/2026-10-20/ordinary-assignment-recovery-v34')


def fixture(count=1, command='grep -n "heading" instructions.md'):
    events = constructed()
    terminal = events.pop()
    denied = []
    for number in range(count):
        tool = 'denied-' + str(number)
        arguments = dict(command=command, description='Native request')
        events += [dict(type='assistant', message={'content': [dict(type='tool_use', id=tool, name='Bash', input=arguments)]}),
            dict(type='system', subtype='permission_check_status', tool_use_id=tool, status='checking'),
            dict(type='system', subtype='permission_check_status', tool_use_id=tool, status='done'),
            dict(type='system', subtype='permission_denied', tool_use_id=tool, tool_name='Bash',
                 decision_reason_type='classifier', decision_reason='[Auto-Mode Bypass]', message=_DENIAL_MESSAGE),
            dict(type='user', message={'content': [dict(type='tool_result', tool_use_id=tool, is_error=True, content=_DENIAL_MESSAGE)]},
                 tool_use_result='Error: ' + _DENIAL_MESSAGE, tool_result_meta=[dict(id=tool, non_execution_kind='automode-blocked',
                     permission_decision=dict(decision='reject', source='config', reason_type='classifier'))])]
        denied.append(dict(tool_name='Bash', tool_use_id=tool, tool_input=copy.deepcopy(arguments)))
    terminal['permission_denials'] = denied
    return seal(events + [terminal])


class MetadataDenialTests(unittest.TestCase):
    def test_bounded_multiple_original_nonexecutions(self):
        for count in range(1, 17):
            events = fixture(count)
            before = copy.deepcopy(events)
            actual = composition(events, producer())
            self.assertIs(actual['terminal'], events[-1])
            proof = actual['proof']
            self.assertEqual(events, before)
            self.assertEqual(proof['denied_tool_count'], count)
            self.assertTrue(all(row['execution_credit'] is False and 'producer' not in row
                for row in proof['optional_nonexecution_denials']))
            removed = {row['index'] for row in proof['removed']}
            self.assertTrue(all(i not in removed for i in range(5, len(events))))
            self.assertEqual(proof['event_sha256'], hashlib.sha256(json.dumps(events, sort_keys=True,
                separators=(',', ':'), ensure_ascii=True).encode()).hexdigest())
        self.assertIsNone(composition(fixture(17), producer()))

    def test_opaque_input_is_neither_execution_nor_harmlessness(self):
        for command in ['wc -l $(id)', 'rm -rf /tmp/requested', 'cat x; true', '\n',
                'python -c pass', '"unterminated', '`unknown` | other > output', 'wc -l /unrelated/file']:
            with self.subTest(command=command):
                proof = composition(fixture(command=command), producer())['proof']
                row = proof['optional_nonexecution_denials'][0]
                self.assertEqual(row['command_sha256'], hashlib.sha256(command.encode()).hexdigest())
                self.assertFalse(row['execution_credit'])
                self.assertNotIn('harmless', row)
        for command in ['', None, 1, {}]:
            self.assertIsNone(composition(fixture(command=command), producer()))

    def test_canonical_business_denials_and_failed_read_consumer(self):
        from cs.operator_health import native_read_failed
        from cs.operator_recovery import Attempt
        for prefix in ['.venv/bin/python -m cs', '.venv/bin/python3 -m cs', '.venv/bin/cs', 'cs']:
            for suffix in ['whoami', 'config', 'tasks --json', 'unanswered --json', 'review --json',
                    'assignment-status x', 'dossier x', 'draft-reply x', 'draft-send x', 'campaign pending']:
                events = fixture(command=prefix + ' ' + suffix)
                with self.subTest(prefix=prefix, suffix=suffix):
                    self.assertIsNone(composition(events, producer()))
                    self.assertIsNone(Attempt(0, events, ordinary_native=True, native_producer=producer()).result)
                    self.assertTrue(native_read_failed(events))

    def test_every_required_component(self):
        base = fixture()
        cases = []
        for i in range(5, 10):
            changed = copy.deepcopy(base); del changed[i]; cases.append(changed)
        for i in range(1, len(base)):
            changed = copy.deepcopy(base); changed[i]['session_id'] = 'foreign'; cases.append(changed)
        for key in base[8]:
            changed = copy.deepcopy(base); del changed[8][key]; cases.append(changed)
        for i, key, value in [(8,'tool_use_id','foreign'),(8,'tool_name','Read'),
            (8,'decision_reason_type','rule'),(8,'decision_reason','other'),(8,'message','other'),
            (8,'extra',True),(6,'extra',True),(7,'extra',True),
            (9,'tool_result_meta',[]),(9,'tool_use_result','stdout'),(-1,'permission_denials',[])]:
            changed=copy.deepcopy(base); changed[i][key]=value; cases.append(changed)
        for key,value in [('non_execution_kind','executed'),('id','other'),('permission_decision',dict(decision='accept',source='config',reason_type='classifier'))]:
            changed=copy.deepcopy(base); changed[9]['tool_result_meta'][0][key]=value; cases.append(changed)
        changed=copy.deepcopy(base); changed[9]['message']['content'][0]['is_error']=False; cases.append(changed)
        changed=copy.deepcopy(base); changed[5]['message']['content'][0]['input']['run_in_background']=True; cases.append(changed)
        changed=copy.deepcopy(base); changed[5]['message']['content'][0]['name']='Read'; cases.append(changed)
        changed=copy.deepcopy(base); changed.insert(9,dict(base[8],uuid='duplicate')); cases.append(changed)
        changed=copy.deepcopy(base); changed[6],changed[7]=changed[7],changed[6]; cases.append(changed)
        changed=copy.deepcopy(base); changed[-1]['permission_denials'][0]['tool_input']['command']='different'; cases.append(changed)
        changed=copy.deepcopy(base); changed[-1]['permission_denials'].append(copy.deepcopy(changed[-1]['permission_denials'][0])); cases.append(changed)
        for key in base[9]['tool_result_meta'][0]:
            changed=copy.deepcopy(base); del changed[9]['tool_result_meta'][0][key]; cases.append(changed)
        for key in base[9]['tool_result_meta'][0]['permission_decision']:
            changed=copy.deepcopy(base); del changed[9]['tool_result_meta'][0]['permission_decision'][key]; cases.append(changed)
        for position in [6,8,9,10]:
            changed=copy.deepcopy(base); changed.insert(position,dict(type='tool_progress',tool_use_id='denied-0-heartbeat-0',parent_tool_use_id='denied-0',tool_name='Bash',heartbeat=True,elapsed_time_seconds=1,session_id='session',uuid='progress')); cases.append(changed)
            changed=copy.deepcopy(base); changed.insert(position,dict(type='system',subtype='task_started',task_id='evil',run_id='evil',tool_use_id='denied-0',task_type='local_bash',is_backgrounded=False,session_id='session',uuid='evil')); cases.append(changed)
        for i,events in enumerate(cases):
            with self.subTest(case=i): self.assertIsNone(composition(events, producer()))

    def test_ordinary_permission_cycles_and_automatic_output(self):
        events = constructed()
        events[2:2] = [dict(type='system', subtype='permission_check_status', tool_use_id='tool', status=status)
            for status in ['checking', 'done', 'checking', 'done']]
        self.assertIsNotNone(composition(seal(events), producer()))
        denied = fixture()
        denied[8:8] = [dict(type='system', subtype='permission_check_status', tool_use_id='denied-0', status=status)
            for status in ['checking', 'done']]
        self.assertIsNone(composition(seal(denied), producer()))
        events = constructed('automatic', True)
        result = next(e for e in events if e['type'] == 'user')
        result['tool_use_result'].update(persistedOutputPath='/opaque/output', unknown_future_field=True)
        self.assertIsNotNone(composition(events, producer()))

    def test_permission_activity_after_denial_is_fatal(self):
        for position in [8, 9, 10, 11]:
            for statuses in [['checking'], ['done'], ['checking', 'done']]:
                events = fixture()
                events[position:position] = [dict(type='system', subtype='permission_check_status',
                    tool_use_id='denied-0', status=status) for status in statuses]
                with self.subTest(position=position, statuses=statuses):
                    self.assertIsNone(composition(seal(events), producer()))
        events = fixture()
        events[6:6] = [dict(type='system', subtype='permission_check_status',
            tool_use_id='denied-0', status=status) for status in ['checking', 'done']]
        self.assertIsNone(composition(seal(events), producer()))

    def test_mandatory_context_and_effect_consumers(self):
        from cs.operator_health import inspection_failure
        events = fixture()
        self.assertEqual(inspection_failure(events, {}, []), 'execution_phase_incomplete')
        phases = [dict(phase=phase) for phase in ['identity','configuration','tasks','discovery','review','campaigns']]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'discovery.json'
            path.write_text(json.dumps(dict(discovery={},exit_code=0)))
            path.chmod(0o600)
            self.assertEqual(inspection_failure(events,dict(directory=directory),phases), 'execution_phase_incomplete')
            events = fixture(command='.venv/bin/python -m cs unanswered --days 7 --json')
            self.assertEqual(inspection_failure(events,dict(directory=directory),phases), 'execution_phase_incomplete')
            events = fixture(command='.venv/bin/python -m cs draft-reply x')
            self.assertEqual(inspection_failure(events,dict(directory=directory),phases), 'execution_operation_failed')

    def test_genuine_prospective_boundaries_only(self):
        from cs.operator_health import native_read_failed
        from cs.operator_recovery import Attempt
        for case,relative,supervisor,denial_index in [(C33,'native-preserved/cafe/native-stream.jsonl','cafe-operator.supervisor.json',1537),
                (C34,'native-preserved/native-stream.jsonl','mrcall-operator.supervisor.json',627)]:
            path=case/relative
            if not path.exists(): self.skipTest('Private genuine capture unavailable: '+str(path))
            raw=path.read_bytes()
            events=[json.loads(line) for line in raw.splitlines()]
            before=copy.deepcopy(events)
            receipt=json.loads((case/supervisor).read_text())[-1]
            actual=composition(events,receipt['native_producer'])
            self.assertIsNotNone(actual)
            self.assertEqual(events,before)
            self.assertEqual(actual['proof']['denied_tool_count'],1)
            self.assertEqual(actual['proof']['optional_nonexecution_denials'][0]['denial_index'],denial_index)
            self.assertIs(Attempt(0,events,ordinary_native=True,native_producer=receipt['native_producer']).result,events[-1])
            self.assertEqual(native_read_failed(events, receipt['business_read_proofs'], discovery_proven=True), case == C34)
            self.assertEqual(path.read_bytes(),raw)


if __name__=='__main__': unittest.main()
