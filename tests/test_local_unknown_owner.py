import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cs import task_assignment, unanswered, review, rpc_reads
from cs.config import Settings
from cs.operator_workset import _inventory, WorksetError


class LocalUnknownOwnerTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, engine_owner_uid='selected-owner')
        self.root = '<held@example.test>'
        self.now = datetime.now(timezone.utc)
        self.inbound = [dict(email='held@example.test', thread_key=self.root,
                             date=self.now, message_id=self.root)]

    def assert_hold(self, row):
        self.assertEqual(row['actor_uid'], self.settings.engine_owner_uid)
        self.assertEqual(row['source_owner_uid'], self.settings.engine_owner_uid)
        self.assertEqual(row['thread_key'], self.root)
        self.assertFalse(row['complete'])
        self.assertTrue(row['hold_auto_reply'])
        self.assertEqual(row['state'], 'unknown')
        self.assertIsNone(row['task'])
        self.assertNotIn('space_id', row)
        for field in ['events', 'covered_inbound', 'reply_evidence']:
            self.assertEqual(row[field], [])

    def split(self, projections):
        return task_assignment.split_inbound(self.inbound, projections, {}, set(), set(), self.now,
                                             owner_uid=self.settings.engine_owner_uid)

    def discovery(self, projection=None):
        normal, held, audit, reopened = self.split({} if projection is None else {self.root: projection})
        return dict(open=[dict(thread_key='<independent@example.test>',
                              email='independent@example.test', _workset_revision='a'*64)],
                    resumed=[], human_work=held, assignment_audit=audit, escalated=[],
                    handled=[], automatic=[], courtesy=[], operational_fixture_discovery=[],
                    assignment_incomplete=True, read_incomplete=None, note=None, crm_note=None)

    def inventory(self, discovery):
        return _inventory(discovery, {'tasks': [], 'review': {'drafts': [], 'drafts_notes': []}},
                          self.settings.engine_owner_uid)

    def test_primary_failure_and_invalid_identity_are_bound(self):
        with patch.object(task_assignment, '_project_one', side_effect=ConnectionError('local failure')):
            self.assert_hold(task_assignment.project(self.settings, self.root))
            invalid = task_assignment.project(self.settings, '')
        self.assertEqual(invalid['actor_uid'], self.settings.engine_owner_uid)
        self.assertEqual(invalid['thread_key'], '')
        self.assertTrue(invalid['hold_auto_reply'])

    def test_expired_capacity_and_primary_read_failure_are_bound(self):
        self.assert_hold(task_assignment.projections(self.settings, [self.root], deadline=0)[self.root])
        with patch.object(rpc_reads, 'read_many', return_value={self.root: rpc_reads.ReadOutcome(error=ConnectionError())}):
            self.assert_hold(task_assignment.projections(self.settings, [self.root])[self.root])

    def test_omitted_projection_split_inventory_preserves_independent_work(self):
        discovery = self.discovery()
        self.assert_hold(discovery['human_work'][0]['assignment'])
        before = copy.deepcopy(discovery)
        candidates, held = self.inventory(discovery)
        self.assertEqual(set(candidates), {'<independent@example.test>'})
        self.assertTrue(any(row['thread_key'] == self.root for row in held))
        self.assertEqual(discovery, before)

    def test_mixed_normal_and_local_hold_production_split_inventory(self):
        from assignment_fixture import normal_projection
        independent = dict(self.inbound[0], email='independent@example.test',
                           thread_key='<independent@example.test>', message_id='<message@example.test>')
        projection = normal_projection(self.settings, {'thread_key': independent['thread_key']})
        normal, held, audit, reopened = task_assignment.split_inbound(
            self.inbound + [independent], {independent['thread_key']: projection}, {},
            set(), set(), self.now, owner_uid=self.settings.engine_owner_uid)
        buckets = unanswered._partition(normal, [], set(), set(), self.now, {})
        discovery = dict(zip(('open', 'handled', 'escalated', 'resumed', 'automatic', 'courtesy'), buckets))
        discovery.update(human_work=held, assignment_audit=audit, assignment_incomplete=True, read_incomplete=None)
        discovery['open'][0]['_workset_revision'] = 'a' * 64
        candidates, holds = self.inventory(discovery)
        self.assertEqual(set(candidates), {independent['thread_key']})
        self.assert_hold(held[0]['assignment'])
        self.assertNotIn(self.root, candidates)
        self.assertTrue(any(row['thread_key'] == self.root for row in holds))

    def test_received_foreign_and_missing_owners_are_not_repaired(self):
        bound = task_assignment._unknown(self.root, 'retained', owner_uid=self.settings.engine_owner_uid)
        for field in ['actor_uid', 'source_owner_uid']:
            for missing in [False, True]:
                row = copy.deepcopy(bound)
                if missing:
                    del row[field]
                else:
                    row[field] = 'foreign-owner'
                before = copy.deepcopy(row)
                discovery = self.discovery(row)
                self.assertEqual(discovery['human_work'][0]['assignment'][field] if not missing else
                                 field in discovery['human_work'][0]['assignment'], 'foreign-owner' if not missing else False)
                with self.assertRaisesRegex(ValueError, 'foreign or malformed held assignment'):
                    self.inventory(discovery)
                self.assertEqual(row, before)

    def test_review_interruption_and_coverage_use_selected_owner(self):
        out = {'_known_roots': [self.root]}
        review._incomplete(out, 'interrupted', owner_uid=self.settings.engine_owner_uid)
        self.assert_hold(out['assignments'][0])
        public = review._public(out, owner_uid=self.settings.engine_owner_uid)
        self.assert_hold(public['assignment_coverage']['roots'][0]['projection'])
        unbound = review._incomplete({'_known_roots': [self.root]}, 'no settings')
        self.assertNotIn('actor_uid', unbound['assignments'][0])

    def test_discovery_interruption_uses_checkpoint_configuration_only(self):
        observation = dict(inbound=self.inbound, sent=[], roots=[self.root], assignment={})
        out = dict(observation=observation, configuration=unanswered._discovery_configuration(self.settings))
        value = unanswered._discovery_incomplete(out, 'interrupted')
        self.assert_hold(value['human_work'][0]['assignment'])
        self.assertTrue(value['assignment_incomplete'])
        self.assertIsNotNone(value['read_incomplete'])
        unbound = unanswered._discovery_incomplete(dict(observation=observation), 'no configuration')
        self.assertNotIn('actor_uid', unbound['human_work'][0]['assignment'])
        with self.assertRaisesRegex(ValueError, 'foreign or malformed held assignment'):
            self.inventory(dict(unbound, read_incomplete=None))

    def test_sweep_omitted_projection_uses_selected_settings(self):
        from test_scheduled_discovery_budget import ScheduledDiscoveryTests
        from cs import gmail_archive, engine_view
        settings, inbound, state = ScheduledDiscoveryTests().fixture()
        with patch.object(gmail_archive, 'inbound_recent', return_value=inbound), \
             patch.object(gmail_archive, 'sent_recent', return_value=[]), \
             patch('cs.state.State', return_value=state), \
             patch('cs.operational_fixture.admit_originals', side_effect=lambda s, rows, own, **kw: (rows, own)), \
             patch.object(engine_view, 'classify', return_value=({}, None)), \
             patch.object(engine_view, 'settled', return_value=({}, None)), \
             patch.object(task_assignment, 'projections', return_value={}):
            value = unanswered.sweep(settings, 14)
        row = value['human_work'][0]['assignment']
        self.assertEqual(row['actor_uid'], settings.engine_owner_uid)
        self.assertEqual(row['source_owner_uid'], settings.engine_owner_uid)
        self.assertFalse(row['complete'])
        self.assertTrue(value['assignment_incomplete'])

    def test_actual_review_parent_interruption_binds_held_root(self):
        command = [sys.executable, '-B', '-c', """import json,sys,time
from pathlib import Path
from cs.review import _save_checkpoint
p=json.load(sys.stdin)
_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out={'_known_roots':['<held@example.test>']},phase='projection',complete=False))
time.sleep(10)
"""]
        value = review._supervise(self.settings, worker_command=command, work_seconds=.8,
                                 cleanup_seconds=.4, total_seconds=1.5)
        self.assert_hold(value['assignments'][0])
        self.assert_hold(value['assignment_coverage']['roots'][0]['projection'])
        self.assertTrue(value['review_coverage']['cleanup_complete'])

    def test_actual_discovery_parent_interruption_binds_checkpoint_owner(self):
        from test_scheduled_discovery_budget import ScheduledDiscoveryTests
        value = ScheduledDiscoveryTests().run_worker("""obs['inbound']=[dict(email='held@example.test',thread_key='<held@example.test>',date=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))]
obs['roots']=['<held@example.test>']
_save_checkpoint(Path(p['path']),dict(binding=p['binding'],out=_discovery_encode(out),phase='projection',complete=False))
time.sleep(10)
""")
        self.assertFalse(value['normal'])
        self.assertTrue(value['cleanup_complete'])
        row = value['value']['human_work'][0]['assignment']
        self.assertEqual(row['actor_uid'], 'local-owner')
        self.assertEqual(row['source_owner_uid'], 'local-owner')
        self.assertTrue(row['hold_auto_reply'])
        self.assertFalse(row['complete'])

    def test_actual_canonical_publication_preserves_technical_hold(self):
        from test_scheduled_discovery_budget import ScheduledDiscoveryTests
        fixture = ScheduledDiscoveryTests()
        with fixture.reservation_publication_fixture() as (environment, original, result, workset):
            owner = environment.settings.engine_owner_uid
            normal, held, audit, reopened = task_assignment.split_inbound(
                self.inbound, {}, {}, set(), set(), self.now, owner_uid=owner)
            result['value']['human_work'] = held
            result['value']['assignment_incomplete'] = True
            result['code'] = 3
            text, code = unanswered._publish_discovery(result)
            self.assertEqual(code, 3)
            value = json.loads(text.split('\nOrdinary discovery artifact:')[0])
            self.assertEqual(value['human_work'][0]['assignment']['actor_uid'], owner)
            self.assertFalse(value['human_work'][0]['assignment']['complete'])
            selected = value['triage_workset']['selected']
            self.assertTrue(selected)
            self.assertNotIn(self.root, {row['thread_key'] for row in selected})
            self.assertTrue((environment.directory/'discovery.json').exists())


if __name__ == '__main__':
    unittest.main()
