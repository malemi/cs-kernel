import email
from email.message import EmailMessage

from cs import gmail_drafts
from cs.draft_identity import authored_message, fingerprint


def mirror_message(draft, owner):
    message = EmailMessage()
    message['From'] = draft['owner_id']
    message['To'] = ', '.join(draft['to_addresses'])
    message['Subject'] = draft['subject']
    message['X-CS-Engine-Draft-ID'] = draft['id']
    message['X-CS-Engine-Owner-UID'] = owner
    message['In-Reply-To'] = draft['in_reply_to']
    message['References'] = ' '.join(draft.get('references') or [draft['in_reply_to']])
    if draft.get('cc_addresses'):
        message['Cc'] = ', '.join(draft['cc_addresses'])
    message.set_content(draft['body'])
    return message


def mirror_evidence(draft, owner):
    raw = mirror_message(draft, owner).as_bytes()
    body, note = authored_message(raw)
    return {**gmail_drafts._header_evidence(email.message_from_bytes(raw)),
            **gmail_drafts._mime_evidence(raw), 'body':body, 'body_note':note,
            'body_complete':True, 'is_draft':True, 'fingerprint':fingerprint(raw)}


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
