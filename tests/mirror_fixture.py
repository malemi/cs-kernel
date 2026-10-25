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
