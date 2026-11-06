"""Retirement orchestration with independent provider and engine effect journals."""

import copy

import io

import os

from contextlib import redirect_stdout, redirect_stderr

from types import SimpleNamespace

from unittest.mock import patch

from cs import draft_lifecycle as lifecycle

DRAFT = 'draft-full-opaque-123'

OWNER = 'owner-full-opaque-456'

MIME = 'a' * 64

SNAPSHOT = 'b' * 64

SETTINGS = SimpleNamespace(engine_owner_uid=OWNER, email_address='operator@example.test')

class Stores:
    def __init__(self):
        self.events = []
        self.effects = []
        self.draft = {'id': DRAFT, 'to_addresses': ['person@example.test'],
                      'cc_addresses': ['copy@example.test'], 'thread_id': '<thread@example.test>',
                      'body': 'An independently written draft body.'}
        self.rows = [{'uid': '17', 'uidvalidity': '9', 'engine_draft_id': DRAFT,
                      'engine_owner_uid': OWNER, 'to': 'person@example.test',
                      'cc': 'copy@example.test', 'thread_key': '<thread@example.test>',
                      'fingerprint': MIME, 'body_complete': True, 'body': self.draft['body']}]
        self.inspect = dict(self.bound(), draft=self.draft, expected_snapshot=SNAPSHOT)
        self.preflight = dict(self.bound(), would_discard=True, discarded=False, expected_snapshot=SNAPSHOT)
        self.ack = dict(self.bound(), discarded=True, consumed_snapshot=SNAPSHOT)
        target = {'uid': '17', 'uidvalidity': '9', 'engine_draft_id': DRAFT,
                  'engine_owner_uid': OWNER, 'fingerprint': MIME}
        self.preview = {'ok': True, 'dry_run': True, 'target': target, 'would_move_to': 'Trash'}
        self.move = {'ok': True, 'target': copy.deepcopy(target), 'moved_to': 'Trash'}

    def bound(self):
        return {'ok': True, 'draft_id': DRAFT, 'engine_owner_uid': OWNER, 'owner_id': SETTINGS.email_address}

    def rpc(self, settings, method, params, **kwargs):
        self.events.append((method, copy.deepcopy(params), settings.engine_owner_uid))
        if method == 'drafts.inspect':
            return copy.deepcopy(self.inspect)
        assert method == 'drafts.discard_exact'
        assert params['draft_id'] == DRAFT
        if params['dry_run']:
            return copy.deepcopy(self.preflight)
        self.effects.append(('engine-discard', copy.deepcopy(params)))
        if isinstance(self.ack, Exception):
            raise self.ack
        return copy.deepcopy(self.ack)

    def listing(self, settings):
        self.events.append(('gmail-list', settings.engine_owner_uid))
        return copy.deepcopy(self.rows)

    def deletion(self, settings, **kwargs):
        self.events.append(('gmail-delete', copy.deepcopy(kwargs)))
        if kwargs['commit']:
            self.effects.append(('gmail-move', copy.deepcopy(kwargs)))
            if isinstance(self.move, Exception):
                raise self.move
            return copy.deepcopy(self.move)
        return copy.deepcopy(self.preview)

    def run(self, commit=False, settings=SETTINGS, **overrides):
        args = dict(commit=commit)
        if commit:
            args.update(gmail_fingerprint=MIME, engine_snapshot=SNAPSHOT)
        args.update(overrides)
        with patch.object(lifecycle.rpc, 'call_sync', self.rpc), \
             patch.object(lifecycle.gmail_drafts, 'list_drafts', self.listing), \
             patch.object(lifecycle.gmail_drafts, 'delete_draft', self.deletion), \
             patch.dict(os.environ, {}, clear=True):
            return lifecycle.retire(settings, DRAFT, '17', '9', **args)

def test_preview_and_commit():
    s = Stores()
    result = s.run()
    assert result['ok'] and result['dry_run'] and result['gmail_fingerprint'] == MIME
    assert result['engine_snapshot'] == SNAPSHOT and not s.effects
    result = s.run(commit=True)
    assert result['ok'] and result['engine_discarded'] and result['gmail_moved']
    assert [e[0] for e in s.effects] == ['gmail-move', 'engine-discard']
    assert s.effects[1][1] == {'draft_id': DRAFT, 'expected_snapshot': SNAPSHOT, 'dry_run': False}
    assert s.effects[0][1]['expected_fingerprint'] == MIME
    s = Stores(); s.draft['to_addresses'].append('second@example.test'); s.rows[0]['to'] += ', second@example.test'
    assert s.run()['ok'], 'matching full multi-recipient context must remain valid'
    for missing in ('gmail_fingerprint', 'engine_snapshot'):
        s = Stores()
        assert not s.run(commit=True, **{missing: None})['ok']
        assert not s.events and not s.effects

def test_identity_and_context_refusals():
    for stage in ('inspect', 'preflight'):
        for field in ('draft_id', 'engine_owner_uid', 'owner_id'):
            s = Stores()
            getattr(s, stage)[field] = 'different'
            assert not s.run(commit=True)['ok'], (stage, field)
            assert not s.effects
    s = Stores(); s.inspect['draft']['id'] = 'different'
    assert not s.run(commit=True)['ok'] and not s.effects
    for field, value in (
        ('engine_owner_uid', 'different'), ('engine_draft_id', None),
        ('to', 'person@example.test, second@example.test'), ('cc', 'different@example.test'),
        ('thread_key', '<different@example.test>'), ('uidvalidity', '10'),
        ('fingerprint', 'c' * 64),
    ):
        s = Stores(); s.rows[0][field] = value
        assert not s.run(commit=True)['ok'], field
        assert not s.effects
    for rows in ([], [dict(Stores().rows[0], uid='18')], Stores().rows * 2):
        s = Stores(); s.rows = rows
        assert not s.run(commit=True)['ok'] and not s.effects
    s = Stores(); s.inspect['expected_snapshot'] = 'c' * 64
    assert not s.run(commit=True)['ok'] and not s.effects
    s = Stores(); s.preflight['would_discard'] = False
    assert not s.run(commit=True)['ok'] and not s.effects
    s = Stores(); s.preview['target']['engine_owner_uid'] = 'different'
    assert not s.run(commit=True)['ok'] and not s.effects
    s = Stores()
    switched = SimpleNamespace(engine_owner_uid='another-owner', email_address='another@example.test')
    assert not s.run(commit=True, settings=switched)['ok'] and not s.effects

def test_partial_effects():
    for move in ({'ok': False}, None, [], RuntimeError('transport failed')):
        s = Stores(); s.move = move
        result = s.run(commit=True)
        assert not result['ok'] and result['engine_discarded'] is False
        assert [e[0] for e in s.effects] == ['gmail-move']
    for field in ('engine_draft_id', 'engine_owner_uid', 'uidvalidity', 'fingerprint'):
        s = Stores(); s.move['target'][field] = 'different'
        result = s.run(commit=True)
        assert not result['ok'] and result['engine_discarded'] is False, field
        assert [e[0] for e in s.effects] == ['gmail-move']
    for ack in ({'ok': False}, {}, None, [], RuntimeError('lost ack')):
        s = Stores(); s.ack = ack
        result = s.run(commit=True)
        assert not result['ok'] and result['partial'] and result['gmail_moved']
        assert result['draft_id'] == DRAFT and result['gmail_uid'] == '17' and result['uidvalidity'] == '9'
        assert result['check'] and [e[0] for e in s.effects] == ['gmail-move', 'engine-discard']
    for field in ('draft_id', 'engine_owner_uid', 'owner_id', 'consumed_snapshot'):
        s = Stores(); s.ack[field] = 'different'
        result = s.run(commit=True)
        assert not result['ok'] and result['partial'] and result['engine_discarded'] is None
        assert result['surviving_engine_id'] == DRAFT

def test_headless_and_parser():
    s = Stores()
    with patch.dict(os.environ, {'CS_OPERATOR_HEADLESS': '1'}), \
         patch.object(lifecycle.rpc, 'call_sync', s.rpc), \
         patch.object(lifecycle.gmail_drafts, 'list_drafts', s.listing):
        result = lifecycle.retire(SETTINGS, DRAFT, '17', '9', commit=True,
                                  gmail_fingerprint=MIME, engine_snapshot=SNAPSHOT)
        assert not result['ok'] and not s.events
    from cs import cli
    for argv, status in ((['draft-retire', '--help'], 0), (['draft-retire', DRAFT], 2)):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            try:
                cli.main(argv)
            except SystemExit as exc:
                assert exc.code == status
            else:
                raise AssertionError('parser did not exit')
        assert '--gmail-uid' in output.getvalue() and '--uidvalidity' in output.getvalue()

def test_real_provider_move_lost_ack():
    import imaplib
    from email.message import EmailMessage
    from mirror_fixture import IMAP
    from cs import gmail_drafts

    class LostAck(IMAP):
        def uid(self, command, *args):
            result = super().uid(command, *args)
            if command == 'MOVE':
                raise imaplib.IMAP4.abort('connection lost after effect')
            return result

    stores = Stores(); provider = LostAck()
    msg = EmailMessage(); msg['To'] = 'person@example.test'; msg['Cc'] = 'copy@example.test'
    msg['X-CS-Engine-Draft-ID'] = DRAFT; msg['X-CS-Engine-Owner-UID'] = OWNER
    msg['References'] = '<thread@example.test>'; msg['In-Reply-To'] = '<thread@example.test>'
    msg.set_content(stores.draft['body']); provider.raw = msg.as_bytes()
    with patch.object(gmail_drafts, '_imap', return_value=provider), \
         patch.object(lifecycle.rpc, 'call_sync', stores.rpc), \
         patch.dict(os.environ, {}, clear=True):
        preview = lifecycle.retire(SETTINGS, DRAFT, '1', '5')
        assert preview['ok'] and not provider.moves
        result = lifecycle.retire(SETTINGS, DRAFT, '1', '5', commit=True,
                                 gmail_fingerprint=preview['gmail_fingerprint'],
                                 engine_snapshot=preview['engine_snapshot'])
    assert len(provider.moves) == 1 and not stores.effects
    assert not result['ok'] and result['partial'] and result['gmail_moved'] is None
    assert result['engine_discarded'] is False and 'Trash' in result['check']


def test_exact_pair_context_controls():
    stores = Stores()
    stores.draft['to_addresses'] = ['First <first@example.test>', 'second@example.test']
    stores.draft['cc_addresses'] = ['copy@example.test', 'Other <other@example.test>']
    stores.rows[0]['to'] = 'SECOND@example.test, first@example.test'
    stores.rows[0]['cc'] = 'other@example.test, COPY@example.test'
    result = stores.run()
    assert result['ok'] and not stores.effects, result
    result = stores.run(commit=True)
    assert result['ok'] and [effect[0] for effect in stores.effects] == ['gmail-move', 'engine-discard'], result
    for field, value in (('to', ''), ('to', 'person@example.test, extra@example.test'),
                         ('cc', ''), ('cc', 'copy@example.test, extra@example.test')):
        stores = Stores()
        stores.rows[0][field] = value
        result = stores.run(commit=True)
        assert not result['ok'] and not stores.effects, (field, value, result)
    stores = Stores()
    stores.rows[0]['thread_key'] = '&lt;thread@example.test&gt;'
    result = stores.run(commit=True)
    assert result['ok'] and len(stores.effects) == 2, result
    stores = Stores()
    stores.rows[0]['thread_key'] = '<different@example.test>'
    result = stores.run(commit=True)
    assert not result['ok'] and not stores.effects, result
    for subject, expected in (('  RE: billing question  ', True), ('Different subject', False)):
        stores = Stores()
        stores.draft['thread_id'] = None
        stores.rows[0]['thread_key'] = None
        stores.draft['subject'] = 'Re: billing question'
        stores.rows[0]['subject'] = subject
        result = stores.run(commit=True)
        assert result['ok'] is expected, (subject, result)
        assert len(stores.effects) == (2 if expected else 0), (subject, stores.effects)


if __name__ == '__main__':
    for test in (test_preview_and_commit, test_identity_and_context_refusals,
                 test_partial_effects, test_headless_and_parser,
                 test_real_provider_move_lost_ack, test_exact_pair_context_controls):
        test()
    print('ordinary draft retirement: five donor checks and context controls passed')
