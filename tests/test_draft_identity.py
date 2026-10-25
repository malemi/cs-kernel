"""Controlled mirror evidence, exact pairing and same-session guarded retirement."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace
from email.message import EmailMessage
from unittest.mock import patch
from cs import draft_state, gmail_drafts
from cs.draft_identity import authored_message, authored_plain, fingerprint, BODY_BYTES


def engine(i):
    return {'id': i, 'to_addresses': ['person@example.test'], 'thread_id': '<thread@example.test>', 'body': 'Original authored body that is comfortably over forty characters.', 'created_at': '2026-10-01T00:00:00Z'}


def mirror(i, uid, owner='owner'):
    return {'uid': uid, 'engine_draft_id': i, 'engine_owner_uid': owner, 'to': 'person@example.test', 'thread_key': '<thread@example.test>', 'date': 'Thu, 01 Oct 2026 00:00:00 +0000'}


def pair(gs, es):
    return draft_state._pair([draft_state._gmail_row(x) for x in gs] + [draft_state._engine_row(x) for x in es], 'owner')


def test_pair():
    rows = pair([mirror('b', '1'), mirror('a', '2')], [engine('a'), engine('b')])
    assert [(r['gmail_uid'], r['engine_id'], r['identity_evidence']) for r in rows] == [('1', 'b', 'exact'), ('2', 'a', 'exact')]
    for gs in ([mirror('a', '1', None)], [mirror('a', '1', 'forged')], [mirror('a', '1'), mirror('a', '2')]):
        rows = pair(gs, [engine('a')])
        assert len(rows) == len(gs) + 1
        assert all(r['identity_conflict'] for r in rows)
        assert all(not (r['gmail_uid'] and r['engine_id']) for r in rows)
    g = mirror('a', '1'); g['to'] = 'other@example.test'
    assert all(r['identity_conflict'] for r in pair([g], [engine('a')]))
    extra = engine('a'); extra['to_addresses'].append('second@example.test')
    assert all(r['identity_conflict'] for r in pair([mirror('a', '1')], [extra]))
    full_g = mirror('a', '1'); full_g['to'] = 'second@example.test, person@example.test'
    full_e = engine('a'); full_e['to_addresses'] = ['person@example.test', 'second@example.test']
    exact = pair([full_g], [full_e])
    assert len(exact) == 1 and exact[0]['identity_evidence'] == 'exact'
    assert exact[0]['to'] == 'person@example.test'
    full_e['to_addresses'].reverse()
    assert pair([full_g], [full_e])[0]['identity_evidence'] == 'exact'
    legacy = mirror(None, '1', None)
    assert pair([legacy], [engine('a')])[0]['identity_evidence'] == 'legacy-inferred'


def test_authored():
    old = 'Old message with a long quoted history. ' * 50
    msg = EmailMessage(); msg.set_content('New short follow-up\n\nOn Monday someone wrote:\n> ' + old)
    body, note = authored_message(msg.as_bytes())
    assert body == 'New short follow-up' and note is None
    assert body != authored_plain(old)[0]
    msg = EmailMessage(); msg.set_content('<div>New follow-up</div><blockquote>' + old + '</blockquote>', subtype='html')
    assert authored_message(msg.as_bytes()) == ('New follow-up', None)
    assert authored_message(b'x' * BODY_BYTES)[1]
    original = 'The previous authored message is long enough for duplicate comparisons.'
    for suffix in (
        '\n\nOn Monday someone wrote:\n> Older quoted history\n\nA new material term applies now.',
        '\n\nOn Monday someone wrote:\n> Earlier quote\nInline answer\n> Later quote',
        '\n\nOn Monday someone wrote:\nUnprefixed old history is ambiguous.',
    ):
        authored, note = authored_plain(original + suffix)
        assert authored == '' and note and 'ambiguous' in note
        msg = EmailMessage(); msg.set_content(original + suffix)
        assert authored_message(msg.as_bytes())[1]
    assert authored_plain(original + '\nOn Monday someone wrote:\n> Pure old quote') == (original, None)
    continuation = original + '\n-----\nA new material term applies now.'
    assert authored_plain(continuation)[0] != authored_plain(original)[0]
    msg = EmailMessage(); msg.set_content(continuation)
    assert authored_message(msg.as_bytes())[0] != authored_plain(original)[0]
    msg = EmailMessage(); msg.set_content(original)
    msg.add_alternative('<div>A new material term applies now.</div>', subtype='html')
    body, note = authored_message(msg.as_bytes())
    assert body == '' and note and 'divergent' in note
    msg = EmailMessage(); msg.set_content('Same authored text')
    msg.add_alternative('<div>Same authored text</div>', subtype='html')
    assert authored_message(msg.as_bytes()) == ('Same authored text', None)
    msg = EmailMessage(); msg.set_content('Clean text'); msg.add_attachment(old.encode(), maintype='text', subtype='plain', filename='history.txt')
    assert authored_message(msg.as_bytes()) == ('Clean text', None)


class IMAP:
    def __init__(self):
        m = EmailMessage(); m['To'] = 'person@example.test'; m['X-CS-Engine-Draft-ID'] = 'a'; m['X-CS-Engine-Owner-UID'] = 'owner'; m.set_content('Actual editable mirror')
        self.raw = m.as_bytes(); self.validity = b'5'; self.moves = []; self.calls = []; self.change = False; self.reads = 0
    def list(self): return 'OK', [b'(\\Drafts) "/" "Drafts"', b'(\\Trash) "/" "Trash"']
    def select(self, *args, **kwargs): return 'OK', [b'1']
    def response(self, name): return name, [self.validity]
    def logout(self): pass
    def uid(self, cmd, *args):
        self.calls.append((cmd, args))
        if cmd == 'SEARCH': return 'OK', [b'1']
        if cmd == 'MOVE': self.moves.append(args); return 'OK', []
        query = args[1]
        if 'RFC822.SIZE' in query:
            self.reads += 1
            raw = self.raw + (b'changed' if self.change and self.reads > 1 else b'')
            return 'OK', [(b'1 (UID 1 FLAGS (\\Draft) RFC822.SIZE ' + str(len(raw)).encode() + b')', raw)]
        return 'OK', [(b'1 (FLAGS (\\Draft))', self.raw)]


def test_delete():
    m = IMAP()
    expectations = dict(expected_engine_draft_id='a', expected_owner_uid='owner', expected_uidvalidity='5')
    with patch.object(gmail_drafts, '_imap', return_value=m):
        preview = gmail_drafts.delete_draft(None, '1', **expectations)
        assert preview['ok'] and not m.moves
        assert preview['target']['fingerprint'] == fingerprint(m.raw)
        expectations['expected_fingerprint'] = preview['target']['fingerprint']
        m.change = True; m.reads = 0
        assert not gmail_drafts.delete_draft(None, '1', commit=True, **expectations)['ok']
        assert not m.moves
        m.change = False
        assert gmail_drafts.delete_draft(None, '1', commit=True, **expectations)['ok']
        assert len(m.moves) == 1
        m.validity = b'6'
        assert not gmail_drafts.delete_draft(None, '1', commit=True, **expectations)['ok']
        assert len(m.moves) == 1
        assert all('BODY.PEEK' in args[1] for cmd, args in m.calls if cmd == 'FETCH')


def test_coherent_mime_observation():
    class RacingIMAP(IMAP):
        def uid(self, cmd, *args):
            result = super().uid(cmd, *args)
            if cmd == 'FETCH' and 'HEADER.FIELDS' in args[1]:
                # Deliver the old header observation, edit before full MIME fetch.
                self.raw = self.raw.replace(b'person@example.test', b'other@example.test')
            return result
    m = RacingIMAP()
    with patch.object(gmail_drafts, '_imap', return_value=m):
        row = gmail_drafts.list_drafts(None)[0]
        assert row['to'] == 'other@example.test'
        assert row['fingerprint'] == fingerprint(m.raw)
        assert not any(k.startswith('_') for k in row)
    m = RacingIMAP()
    with patch.object(gmail_drafts, '_imap', return_value=m):
        result = gmail_drafts.delete_draft(None, '1', commit=True,
                    expected_engine_draft_id='a', expected_owner_uid='owner', expected_uidvalidity='5')
        assert not result['ok'] and 'headers changed' in result['refused']
        assert not m.moves
    m = IMAP()
    m.raw = m.raw.replace(b'To: person@example.test', b'To: person@example.test\nTo: second@example.test\nCc: firstcc@example.test\nCc: secondcc@example.test')
    with patch.object(gmail_drafts, '_imap', return_value=m):
        row = gmail_drafts.list_drafts(None)[0]
        assert row['to'] == 'person@example.test, second@example.test'
        assert row['cc'] == 'firstcc@example.test, secondcc@example.test'
        assert all(r['identity_conflict'] for r in pair([dict(row, thread_key='<thread@example.test>')], [engine('a')]))


def test_append_headers():
    m = IMAP(); captured = []
    m.append = lambda *args: (captured.append(args[-1]) or ('OK', []))
    with patch.object(gmail_drafts, '_imap', return_value=m):
        gmail_drafts.append_draft(SimpleNamespace(email_address='sender@example.test'), 'person@example.test', 'Subject', 'Body', engine_draft_id='full-opaque-id', engine_owner_uid='owner')
        assert b'X-CS-Engine-Draft-ID: full-opaque-id' in captured[0]
        assert b'X-CS-Engine-Owner-UID: owner' in captured[0]
        for bad in ('a\r\nb', 'a\x00b', ' a'):
            try:
                gmail_drafts.append_draft(None, '', '', '', engine_draft_id=bad)
            except ValueError: pass
            else: raise AssertionError('invalid identity accepted')


if __name__ == '__main__':
    for test in (test_pair, test_authored, test_delete, test_coherent_mime_observation, test_append_headers):
        test()
    print('test_draft_identity: all assertions passed (controlled fixtures; provider preservation unverified)')
