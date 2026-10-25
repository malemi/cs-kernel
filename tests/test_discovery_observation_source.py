import copy
import hashlib
import json
import unittest
from cs import operator_inventory_view as producer


def record(source):
    return {'nonce': 'a' * 32, 'owner_uid': 'neutral-owner',
            'ancestry': [{'pid': 2, 'started_ticks': 20}, {'pid': 1, 'started_ticks': 10}],
            'exit_code': 0, 'output_sha256': 'b' * 64,
            'discovery': {'human_work': [{'assignment': {'complete': False,
                'authority_complete': False, 'hold_auto_reply': True,
                'reply_evidence': [{'source': source, 'digest': None}]}}],
                'triage_workset': {'complete': True, 'limit': 2,
                                  'selected': [], 'deferred': [], 'held': []}}}


def projection(value):
    raw = json.dumps(value).encode()
    native = {'child_identity': value['ancestry'][-2]}
    binding = {'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
               'owner_uid': value['owner_uid'], 'nonce': value['nonce'],
               'ancestry': value['ancestry'], 'source_identity': 'neutral-source',
               'native_invocation': native, 'current_native_invocation': native}
    view = producer.produce(value, binding).encode()
    return raw, view, {'view_sha256': hashlib.sha256(view).hexdigest(),
                       'view_bytes': len(view)}, binding


class DiscoveryObservationSourceTests(unittest.TestCase):
    def test_presence_empty_null_and_ordered_raw_details(self):
        for source in [None, {}, {'in_reply_to': ''}, {'recipients': []},
                       {'in_reply_to': '<parent@example.test>',
                        'recipients': ['second@example.test', 'first@example.test']}]:
            value = record(source)
            original = copy.deepcopy(value)
            raw, view, envelope, binding = projection(value)
            self.assertEqual(value, original)
            note = json.loads(view.splitlines()[0])
            self.assertEqual(note['raw_reference_paths']['source'][-2:],
                             ['in_reply_to', 'recipients'])
            self.assertIn('UNINSPECTED', note['legend'])
            self.assertEqual(json.loads(raw), original)
            if source and 'recipients' in source:
                self.assertNotIn(b'second@example.test', view)
                self.assertEqual(json.loads(raw)['discovery']['human_work'][0]
                    ['assignment']['reply_evidence'][0]['source']['recipients'], source['recipients'])

    def test_wrong_types_unknown_fields_and_absent_source_refuse(self):
        for source in [{'in_reply_to': x} for x in [None, 0, False, [], {}]] + [
                {'recipients': x} for x in [None, '', 0, False, {}, [None], [0], [True], [{}]]
                ] + [{'future_authority': True}]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                projection(record(source))
        value = record({})
        del value['discovery']['human_work'][0]['assignment']['reply_evidence'][0]['source']
        with self.assertRaises(ValueError):
            projection(value)


if __name__ == '__main__':
    unittest.main()
