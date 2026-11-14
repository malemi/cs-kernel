from __future__ import annotations

import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from . import gmail_drafts
from .draft_identity import authored_message, canonical_message_id
from .thread_key import thread_key

_FIELDS = ('id', 'owner_id', 'thread_id', 'in_reply_to', 'references', 'to_addresses',
           'cc_addresses', 'bcc_addresses', 'subject', 'body', 'body_format',
           'attachment_paths', 'attachments', 'reply_binding')
_LIMIT = 65536
_ID = re.compile(r'<[^<>\s"\\]+@[^<>\s"\\]+>')


def material(row):
    return {key: row.get(key) for key in _FIELDS}


def _one(message, name, *, required=True):
    values = message.get_all(name, [])
    if len(values) > 1 or (required and len(values) != 1):
        raise ValueError(f'Gmail Sent {name} is missing or ambiguous')
    value = values[0] if values else None
    if value is not None and getattr(value, 'defects', ()):
        raise ValueError(f'Gmail Sent {name} is malformed')
    return value


def _addresses(message, name):
    value = _one(message, name, required=name in ('From', 'To'))
    if value is None:
        return ()
    addresses = value.addresses
    result = tuple(sorted(address.addr_spec.lower() for address in addresses))
    if not result or len(set(result)) != len(result) or any('@' not in item for item in result):
        raise ValueError(f'Gmail Sent {name} is malformed or duplicated')
    return result


def _expected_addresses(row, name):
    values = row.get(name) or []
    if not isinstance(values, list) or any(not isinstance(v, str) or '@' not in v for v in values):
        raise ValueError('engine recipients are malformed')
    message = EmailMessage()
    if values:
        message['To'] = ', '.join(values)
        return _addresses(message, 'To')
    return ()


def _body(draft):
    message = EmailMessage()
    message.set_content(draft.get('body') or '', subtype='html' if draft.get('body_format') == 'html' else 'plain')
    body, note = authored_message(message.as_bytes())
    if note or not body:
        raise ValueError('engine authored body is unverifiable')
    return body


def _sent_mime(message, draft):
    parts = list(message.walk())
    if any(part.get_filename() or part.get_content_disposition() is not None
           or part.defects or any(len(part.get_all(name, [])) > 1
               or any(getattr(value, 'defects', ()) for value in part.get_all(name, [])) for name in
               ('Content-Type', 'Content-Disposition', 'Content-Transfer-Encoding', 'MIME-Version')) for part in parts):
        raise ValueError('Gmail Sent contains added or ambiguous MIME material')
    types = [part.get_content_type() for part in parts]
    if types == ['text/plain']:
        text = message.get_content(errors='strict').replace('\r\n', '\n').rstrip('\n')
        if text != draft['body'].replace('\r\n', '\n').rstrip('\n'):
            raise ValueError('Gmail Sent complete plain content differs')
        return
    if draft.get('body_format') != 'html':
        raise ValueError('Gmail Sent plain draft has additional MIME representations')
    if types not in (['text/html'], ['multipart/alternative', 'text/plain', 'text/html']):
        raise ValueError('Gmail Sent HTML draft has unsupported MIME structure')
    rich = next(part for part in parts if part.get_content_type() == 'text/html')
    text = rich.get_content(errors='strict').replace('\r\n', '\n').rstrip('\n')
    if text != draft['body'].replace('\r\n', '\n').rstrip('\n'):
        raise ValueError('Gmail Sent HTML content or links differ')


from .observability_producers import observe as _diagnostic_observe


@_diagnostic_observe("verification", success="verified", effect="verified")
def _sent(settings, draft, message_id):
    if not isinstance(message_id, str) or not _ID.fullmatch(message_id):
        raise ValueError('engine Sent Message-ID is unavailable or malformed')
    client = gmail_drafts._imap(settings)
    try:
        folder = gmail_drafts._find_special(client, '\\sent')
        if not folder or client.select(f'"{folder}"', readonly=True)[0] != 'OK':
            raise ValueError('Gmail Sent folder is unavailable')
        typ, values = client.uid('SEARCH', None, 'HEADER', 'Message-ID', f'"{message_id}"')
        if typ != 'OK' or not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], bytes):
            raise ValueError('Gmail Sent identity search is incomplete')
        uids = values[0].split()
        if len(uids) != 1 or not uids[0].isdigit():
            raise ValueError('Gmail Sent exact message is missing or ambiguous')
        typ, values = client.uid('FETCH', uids[0], f'(UID RFC822.SIZE BODY.PEEK[]<0.{_LIMIT}>)')
        parts = [part for part in (values or []) if isinstance(part, tuple) and len(part) == 2
                 and isinstance(part[0], bytes) and isinstance(part[1], bytes)] if typ == 'OK' else []
        if len(parts) != 1:
            raise ValueError('Gmail Sent complete MIME is unavailable')
        metadata, raw = parts[0]
        found_uids = re.findall(rb'\bUID\s+(\d+)', metadata, re.I)
        if found_uids != [uids[0]]:
            raise ValueError('Gmail Sent MIME UID is missing or differs')
        sizes = re.findall(rb'RFC822.SIZE\s+(\d+)', metadata, re.I)
        if len(sizes) != 1 or int(sizes[0]) != len(raw) or len(raw) >= _LIMIT:
            raise ValueError('Gmail Sent MIME exceeds bound or is incomplete')
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if any(part.defects for part in message.walk()):
            raise ValueError('Gmail Sent MIME is malformed')
        if canonical_message_id(_one(message, 'Message-ID')) != message_id:
            raise ValueError('Gmail Sent Message-ID differs')
        if _addresses(message, 'From') != (settings.email_address.lower(),):
            raise ValueError('Gmail Sent sender differs')
        for header, key in (('To', 'to_addresses'), ('Cc', 'cc_addresses'), ('Bcc', 'bcc_addresses')):
            if _addresses(message, header) != _expected_addresses(draft, key):
                raise ValueError(f'Gmail Sent {header} differs')
        refs = str(_one(message, 'References', required=False) or '')
        target = canonical_message_id(_one(message, 'In-Reply-To'))
        expected_refs = draft.get('references') or [draft.get('in_reply_to')]
        root = draft.get('thread_id') or thread_key(None, ' '.join(expected_refs), draft.get('in_reply_to'))
        if (not root or target != draft.get('in_reply_to') or refs.split() != expected_refs
                or thread_key(None, refs, target) != root):
            raise ValueError('Gmail Sent reply binding differs')
        if str(_one(message, 'Subject')) != draft.get('subject'):
            raise ValueError('Gmail Sent subject differs')
        _sent_mime(message, draft)
        body, note = authored_message(raw)
        if note or body != _body(draft):
            raise ValueError('Gmail Sent authored body differs or is incomplete')
        return root
    finally:
        try:
            client.logout()
        except Exception:
            pass


def complete(settings, draft, sent):
    matches = [row for row in sent if row.get('id') == draft['id']]
    if (len(matches) != 1 or matches[0].get('status') != 'sent'
            or material(matches[0]) != material(draft)
            or draft.get('owner_id') != settings.email_address
            or not settings.engine_owner_uid or draft.get('attachment_paths') or draft.get('attachments')):
        raise ValueError('exact engine Sent row differs from the approved draft')
    root = _sent(settings, draft, matches[0].get('sent_message_id'))
    from .observability_producers import emit as diagnostic_emit, error_metadata
    diagnostic_emit(settings, 'cleanup', 'start', reason='none', draft_id=draft['id'], root_id=root)
    try:
        observed = {}
        rows = gmail_drafts.list_drafts(settings, observation=observed)
        if observed.get('complete') is not True:
            raise ValueError('Gmail draft inventory is incomplete')
        mirrors = [row for row in rows if row.get('engine_draft_id') == draft['id']]
        if len(mirrors) != 1:
            raise ValueError('exact Gmail review mirror is missing or ambiguous')
        mirror = mirrors[0]
        from .draft_state import _recipient_set
        if (mirror.get('mime_plain_only') is not True or mirror.get('identity_headers_valid') is not True or mirror.get('is_draft') is not True or mirror.get('engine_owner_uid') != settings.engine_owner_uid
                or mirror.get('from') != settings.email_address or 'bcc' not in mirror
                or _recipient_set(mirror.get('to')) != _expected_addresses(draft, 'to_addresses')
                or _recipient_set(mirror.get('cc')) != _expected_addresses(draft, 'cc_addresses')
                or _recipient_set(mirror.get('bcc')) != _expected_addresses(draft, 'bcc_addresses')
                or mirror.get('thread_key') != root or mirror.get('in_reply_to') != draft.get('in_reply_to')
                or (mirror.get('references') or '').split() != (draft.get('references') or [draft.get('in_reply_to')])
                or mirror.get('subject') != draft.get('subject') or mirror.get('body_complete') is not True
                or mirror.get('body_note') or mirror.get('body') != _body(draft)
                or not mirror.get('fingerprint') or not mirror.get('uidvalidity')):
            raise ValueError('Gmail review mirror changed or is unverifiable; preserved')
        result = gmail_drafts.delete_draft(settings, uid=mirror['uid'], commit=True,
            expected_engine_draft_id=draft['id'], expected_owner_uid=settings.engine_owner_uid,
            expected_uidvalidity=mirror['uidvalidity'], expected_fingerprint=mirror['fingerprint'])
        if result.get('ok') is not True:
            raise RuntimeError('Gmail mirror retirement failed or outcome is unknown')
        after_observed = {}
        after = gmail_drafts.list_drafts(settings, observation=after_observed)
        if after_observed.get('complete') is not True:
            raise RuntimeError('Gmail mirror retirement readback is incomplete')
        if any(row.get('engine_draft_id') == draft['id'] for row in after):
            raise RuntimeError('Gmail mirror remains after retirement; no further cleanup attempted')
    except BaseException as exc:
        diagnostic_emit(settings, 'cleanup', 'delivered-cleanup-incomplete', reason='unknown', effect_certainty='verified', draft_id=draft['id'], root_id=root, **error_metadata(exc))
        raise
    diagnostic_emit(settings, 'cleanup', 'verified', reason='none', effect_certainty='verified', draft_id=draft['id'], root_id=root)
