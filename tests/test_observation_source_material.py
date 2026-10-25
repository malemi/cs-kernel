import copy
import json
import unittest
from cs import operator_inventory_material as material


BASES = (
    'workset-review.json:/payload/human_work/*/assignment/reply_evidence/*/source',
    'workset-review.json:/payload/assignment_coverage/roots/*/projection/reply_evidence/*/source',
)


def unpack(rows):
    definitions, shapes = rows[1]

    def decode(value):
        if type(value) is dict:
            if set(value) == {'VALUE'}:
                return definitions[value['VALUE']][1]
            if set(value) == {'OBJECT'}:
                index, cells = value['OBJECT']
                return dict(zip(shapes[index], map(decode, cells)))
            return {key: decode(item) for key, item in value.items()}
        if type(value) is list:
            return list(map(decode, value))
        return value

    return list(map(decode, rows[2:]))


def source():
    return {'actor_uid': 'owner', 'mailbox_id': 'mailbox',
            'thread_key': '<root@example.test>', 'observation_only': True,
            'in_reply_to': '<original@example.test>',
            'recipients': ['first@example.test', 'second@example.test'],
            'message_id': '<reply@example.test>', 'route_digest': 'route',
            'raw_header_digest': 'headers', 'content_digest': 'content',
            'provider': {'folder': 'Sent', 'uid': 12, 'uidvalidity': 34}}


class ObservationSourceMaterialTests(unittest.TestCase):
    def test_equivalent_typed_paths(self):
        for path in BASES:
            for recipients in ([], ['first@example.test'], source()['recipients']):
                value = {**source(), 'recipients': recipients}
                material.validate(value, path)
            material.validate(None, path)

    def test_unknown_fields_and_wrong_types_refuse(self):
        for path in BASES:
            bad_values = [{'send_authorized': True}, {'recipients': 'address'},
                          {'recipients': [None]}, {'recipients': [True]},
                          {'recipients': [{'address': 'first@example.test'}]},
                          {'in_reply_to': None}, {'in_reply_to': []},
                          {'observation_only': 1}]
            for change in bad_values:
                with self.subTest(path=path, change=change):
                    with self.assertRaises(ValueError):
                        material.validate({**source(), **change}, path)

    def test_projection_and_full_visible_pack_roundtrip(self):
        observation = {'complete': False, 'judgement': 'observation_only',
                       'reason': 'does not grant authority', 'source': source(),
                       'digest': None}
        assignment = {'authority_complete': False, 'hold_auto_reply': True,
                      'reply_evidence': [observation] * 5}
        records = {material.NAMES[0]: {'payload': []},
                   material.NAMES[1]: {'payload': {
                       'human_work': [{'assignment': copy.deepcopy(assignment)}],
                       'assignment_coverage': {'roots': [
                           {'projection': copy.deepcopy(assignment)}]}}}}
        material.validate(records[material.NAMES[1]]['payload'],
                          'workset-review.json:/payload')
        projected = material.project(records)
        self.assertEqual(unpack(material.pack(projected)), projected)
        index = next(i for i, row in enumerate(projected)
                     if type(row) is dict and row.get('table') ==
                     'workset-review.json:human_work')
        human = projected[index + 1][0]
        evidence = human['reply_evidence'][0]
        self.assertEqual(evidence['source']['in_reply_to'], source()['in_reply_to'])
        self.assertEqual(evidence['source']['recipients'], source()['recipients'])
        self.assertIs(evidence['source']['observation_only'], True)
        self.assertIs(human['authority_complete'], False)
        self.assertIs(human['hold_auto_reply'], True)
        self.assertEqual(evidence['source']['message_id'], {'RAW REF': True})
        for path in ('payload/human_work/0/assignment/reply_evidence/0/source/',
                     'payload/assignment_coverage/roots/0/projection/reply_evidence/0/source/'):
            self.assertFalse(material.raw_detail(path + 'in_reply_to'))
            self.assertFalse(material.raw_detail(path + 'recipients'))
            self.assertTrue(material.raw_detail(path + 'content_digest'))
        self.assertIn('grants no body inspection', material.NOTE)
