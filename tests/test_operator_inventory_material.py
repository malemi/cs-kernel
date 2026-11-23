import copy
import hashlib
import json
import unittest
from cs import operator_inventory_material as material

# A non-empty value at any of these list paths fails discovery publication until
# its element shape is declared.
LIST_PATHS_WITHOUT_ELEMENT_SHAPE = frozenset({
    'workset-review.json:/payload/assignment_audit',
    'workset-review.json:/payload/assignment_coverage/roots/*/projection/covered_inbound',
    'workset-review.json:/payload/assignment_coverage/roots/*/projection/covered_message_ids',
    'workset-review.json:/payload/assignment_coverage/roots/*/projection/current_inbound',
    'workset-review.json:/payload/assignment_coverage/roots/*/projection/events',
    'workset-review.json:/payload/assignments',
    'workset-review.json:/payload/campaigns/*/flagged',
    'workset-review.json:/payload/human_work/*/assignment/covered_inbound',
    'workset-review.json:/payload/human_work/*/assignment/covered_message_ids',
    'workset-review.json:/payload/human_work/*/assignment/current_inbound',
    'workset-review.json:/payload/human_work/*/assignment/events',
    'workset-review.json:/payload/tasks/*/sources/calendar_events',
    'workset-tasks.json:/payload/*/sources/calendar_events',
    'workset-tasks.json:/payload/tasks/*/sources/calendar_events',
})


class MaterialTests(unittest.TestCase):
    def test_every_list_path_declares_its_element_shape(self):
        undeclared = {path for path, (types, _) in material.SCHEMA.items()
                      if 'list' in types and path + '/*' not in material.SCHEMA}
        self.assertEqual(undeclared, LIST_PATHS_WITHOUT_ELEMENT_SHAPE)
        for path in sorted(LIST_PATHS_WITHOUT_ELEMENT_SHAPE):
            with self.subTest(path=path):
                material.validate([], path)
                with self.assertRaises(material.MaterialValidationError) as failure:
                    material.validate(['element'], path)
                self.assertEqual(failure.exception.cause, 'material_type_invalid')

    def test_unreadable_mailbox_gaps_on_ready_drafts_are_valid_review_material(self):
        # The real producer: one declared mailbox fails authentication, so
        # draft_state.reconcile qualifies every `ready` row with that mailbox's
        # description, and the review material carries those strings.
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime
        from unittest.mock import patch
        from cs import draft_state, mailboxes
        from cs.config import Settings
        gap = mailboxes.Unreadable(account='declared', address='colleague@example.com',
                                   reason="IMAP: b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'")
        def bulk(unreadable, skipped, notes):
            def read(settings, addrs, since):
                unreadable.setdefault(gap.address, gap.describe())
                return {}, {}
            return read
        selected = Settings(_env_file=None)
        selected.email_address = 'support@example.com'
        selected.email_password = 'pw'
        now = datetime.now(timezone.utc)
        drafts = [{'id': '9', 'mailbox_id':'box', 'to_addresses':['customer@example.com'], 'subject': 're: your request',
                   'created_at': format_datetime(now - timedelta(days=1)), 'body': 'short',
                   'thread_key': '', 'message_id': '<m@example.com>'}]
        with patch.object(draft_state, '_bulk_across', bulk):
            rows, _ = draft_state.reconcile(selected, drafts,
                                            settled=lambda settings, keys: ({}, None),
                                            delivered=lambda settings, addr, body: (None, None), now=now)
        self.assertEqual([row['verdict'] for row in rows], ['ready'])
        self.assertEqual(rows[0]['evidence_incomplete'], [gap.describe()])
        # `cs review --json` serializes with default=str (cs.cli._print_json).
        rows = json.loads(json.dumps(rows, ensure_ascii=False, default=str))
        value = {'digest': 'x', 'nonce': 'n', 'owner_uid': 'o', 'source': 'review',
                 'payload': {'drafts': rows}}
        material.validate(value, 'workset-review.json:')
        material.validate({**value, 'payload': {'drafts': [{**rows[0], 'evidence_incomplete': []}]}},
                          'workset-review.json:')
        for bad in ([None], [1], [{'mailbox': gap.address}], [[gap.describe()]]):
            with self.subTest(bad=bad), self.assertRaises(material.MaterialValidationError) as failure:
                material.validate({**value, 'payload': {'drafts': [{**rows[0], 'evidence_incomplete': bad}]}},
                                  'workset-review.json:')
            self.assertEqual(failure.exception.cause, 'material_type_invalid')

    def test_strict_json(self):
        for raw in ('{"x":1,"x":2}', '[NaN]', '[Infinity]'):
            with self.assertRaises(ValueError):material.parse(raw)

    def test_native_mailbox_material(self):
        path = 'workset-review.json:/payload/mailbox_drafts/*'
        material.validate({'id':'native','mailbox_id':'box','attachments':[{'name':'a','content_type':'text/plain'}],
            'bcc_addresses':['person@example.test'],'source_id':None,'body_editable':False},path)
        for invalid in ({'bcc_addresses':42},{'attachments':[{'foreign':True}]},{'body_editable':1}):
            with self.assertRaises(material.MaterialValidationError):
                material.validate(invalid,path)

    def test_exact_types_unknown_fields(self):
        value={'digest':'x','nonce':'n','owner_uid':'o','source':'tasks','payload':[]}
        material.validate(value,'workset-tasks.json:')
        for bad in ({**value,'foreign':True},{**value,'payload':[{'pinned':0}]},{**value,'payload':[{'sources':{'body':'not approved'}}]}):
            with self.assertRaises(ValueError):material.validate(bad,'workset-tasks.json:')
        for field in ('close_actor','close_note','completed_at'):
            material.validate({**value,'payload':[{field:'neutral'}]},'workset-tasks.json:')
            material.validate({**value,'payload':[{field:None}]},'workset-tasks.json:')

    def test_material_definitions_are_visible_and_typed(self):
        rows=[{'table':'neutral','columns':['value']},[{'thread_key':'<neutral@example.test>','hold_auto_reply':False}]]*5
        result=material.pack(rows)
        self.assertEqual(result[0]['columns'],['typed_values','object_columns'])
        self.assertIn('neutral',json.dumps(result))

    def test_raw_boundary(self):
        self.assertTrue(material.raw_detail('payload/drafts/0/body'))
        self.assertFalse(material.raw_detail('payload/tasks/0/sources/body'))
        self.assertTrue(material.raw_detail('payload/human_work/0/assignment/current_message_ids'))
        self.assertFalse(material.raw_detail('payload/human_work/0/assignment/reason'))

    def test_scheduled_sources_binding_and_no_missing_input_fallback(self):
        import tempfile
        from pathlib import Path
        from cs import operator_inventory_view as view
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            context={'directory':temp,'owner_uid':'neutral','nonce':'a'*32,'supervisor':{'pid':1,'started_ticks':10},'workset_enabled':True}
            discovery={'triage_workset':{'complete':True,'limit':2,'selected':[],'deferred':[],'held':[]}}
            record={'nonce':context['nonce'],'owner_uid':'neutral','ancestry':[{'pid':3,'started_ticks':30},{'pid':2,'started_ticks':20},context['supervisor']],'exit_code':0,'output_sha256':'neutral','discovery':discovery}
            view.exclusive(path/'discovery.json',json.dumps(record).encode())
            with self.assertRaises(OSError):view.capture(context)
            review={'mailbox_drafts':[],'drafts':[],
                    'drafts_inventory':{'version':2,'complete':True,'mailbox_count':0,'row_count':0,'identity_sha256':hashlib.sha256(b'[]').hexdigest()}}
            observations={'tasks':[],'review':review}
            for source,payload in observations.items():
                value={'digest':material.commitment(payload),'nonce':context['nonce'],'owner_uid':'neutral','source':source,'payload':payload}
                view.exclusive(path/('workset-'+source+'.json'),json.dumps(value).encode())
            reservation={'nonce':context['nonce'],'owner_uid':'neutral','digest':material.commitment([{},observations]),'selected':[],'contacts':[]}
            view.exclusive(path/'workset-reserved.json',json.dumps(reservation).encode())
            view.capture(context)
            _,data,envelope=view.load(context)
            self.assertEqual(envelope['schema'],'cs.semantic_inventory.envelope.v2')
            self.assertEqual(len(envelope['workset_sources']),2)
            original=(path/'workset-tasks.json').read_bytes()
            for field,value in [('nonce','foreign'),('owner_uid','foreign'),('source','review'),('digest','0'*64)]:
                changed=json.loads(original);changed[field]=value;(path/'workset-tasks.json').write_text(json.dumps(changed))
                with self.assertRaises(ValueError):view.load(context)
            (path/'workset-tasks.json').write_bytes(original)
            (path/'workset-tasks.json').chmod(0o644)
            with self.assertRaises(ValueError):view.load(context)
            (path/'workset-tasks.json').chmod(0o600)
            view.load(context)

    def test_task_container_scalar_empty_lists(self):
        for payload in ({'tasks':[],'complete':True},{'tasks':[{'id':'neutral'}],'errors':[]}):
            records={material.NAMES[0]:{'payload':payload},material.NAMES[1]:{'payload':{}}}
            rows=material.project(records)
            name='tasks' if not payload.get('errors') and 'errors' not in payload else 'errors'
            index=next(i for i,row in enumerate(rows)if type(row)is dict and row.get('table')==material.NAMES[0]+':'+name)
            if not payload.get(name):self.assertEqual(rows[index]['columns'],['value'])
            self.assertEqual(rows[index+1],[payload[name]])

    def test_task_completeness_before_compact_coverage(self):
        from pathlib import Path
        review={'mailbox_drafts':[],'drafts':[],
                'drafts_inventory':{'version':2,'complete':True,'mailbox_count':0,'row_count':0,'identity_sha256':hashlib.sha256(b'[]').hexdigest()}}
        good={'tasks':[{'id':'neutral'}]}
        variants=[{'tasks':[],'complete':True},{'tasks':[{'id':'neutral'}],'errors':[]}]
        invalid=[{**good,'complete':False},{**good,'total':2},{**good,'error':'unavailable'},
                 {**good,'errors':['unavailable']},{**good,'truncated':True},{**good,'has_more':True},
                 {**good,'next_cursor':'more'},{**good,'next_page':1},{**good,'next_page_token':'more'},
                 {'complete':True},{'tasks':{}},{'tasks':['wrong']}]
        for payload in variants+invalid:
            observations={'tasks':payload,'review':review};context={'nonce':'n','owner_uid':'neutral'}
            files={}
            for source,value in observations.items():files['workset-'+source+'.json']=json.dumps({**context,'source':source,'payload':value,'digest':material.commitment(value)}).encode()
            files['workset-reserved.json']=json.dumps({**context,'digest':material.commitment([{},observations]),'selected':[],'contacts':[]}).encode()
            if payload in invalid:
                with self.assertRaises(ValueError):material.load_sources(Path('.'),context,{'triage_workset':{}},lambda path:files[path.name])
            else:material.load_sources(Path('.'),context,{'triage_workset':{}},lambda path:files[path.name])
