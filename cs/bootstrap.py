"""Bounded, read-only interactive operator orientation shared by all transports."""
from __future__ import annotations

import hashlib
import json
import re
import sys

from . import config, rpc, standing_instructions

MAX_CONTEXT_BYTES = 32768
MAX_RESPONSE_BYTES = 131072
PAGE_CHARS = 8192
MAX_DOCUMENT_BYTES = standing_instructions.MAX_DOCUMENT_BYTES


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()


def _string(value, name, limit=256):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > limit:
        raise ValueError('Invalid bootstrap %s.' % name)
    return value


def assemble(identity, instructions, capabilities, *, instruction_path=None, offset=0, sha256=None):
    if not isinstance(identity, dict):
        raise ValueError('Invalid bootstrap identity.')
    account = {key: _string(identity.get(key), key) for key in ('profile_uid', 'email', 'company_ref')}
    if account['email'] != account['email'].strip().lower() or not standing_instructions.MAILBOX.fullmatch(account['email']):
        raise ValueError('Invalid bootstrap mailbox.')
    if not isinstance(capabilities, list) or len(capabilities) > 100:
        raise ValueError('Invalid bootstrap capabilities.')
    caps = sorted({_string(name, 'capability', 100) for name in capabilities})
    if any(not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.-]*', name) for name in caps):
        raise ValueError('Invalid bootstrap capability name.')
    if not isinstance(instructions, dict) or instructions.get('status') not in ('available', 'missing', 'denied', 'unavailable'):
        raise ValueError('Invalid bootstrap instruction state.')
    status = instructions['status']
    authority = instructions.get('authority')
    if authority not in ('managed', 'legacy', 'engine_published_copy', None) or (status in ('available', 'missing') and authority is None):
        raise ValueError('Invalid bootstrap instruction authority.')
    allowed = {'mail/%s.md' % account['email'], 'procedures.md'}
    rows = instructions.get('documents', [])
    missing = instructions.get('missing_paths', [])
    if not isinstance(rows, list) or len(rows) > 2 or not isinstance(missing, list):
        raise ValueError('Invalid bootstrap instruction documents.')
    seen = set()
    docs = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid bootstrap instruction document.')
        path = row.get('path')
        if not isinstance(path, str) or path not in allowed or path in seen:
            raise ValueError('Foreign or duplicate bootstrap instruction path.')
        seen.add(path)
        text = row.get('text')
        revision = row.get('revision')
        digest = row.get('sha256')
        if type(revision) is not int or revision < 1 or not isinstance(text, str):
            raise ValueError('Invalid bootstrap instruction revision or text.')
        raw = text.encode('utf-8')
        if not raw or len(raw) > MAX_DOCUMENT_BYTES or not isinstance(digest, str) or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Invalid bootstrap instruction integrity.')
        docs.append(dict(path=path, revision=revision, sha256=digest, text=text))
    if any(not isinstance(path, str) or path not in allowed for path in missing) or len(set(missing)) != len(missing):
        raise ValueError('Invalid bootstrap missing paths.')
    if status in ('denied', 'unavailable') and (docs or missing):
        raise ValueError('Unavailable instructions must not contain documents.')
    if status in ('available', 'missing') and set(missing) != allowed - seen:
        raise ValueError('Bootstrap instruction coverage does not match documents.')
    if status == 'available' and missing:
        raise ValueError('Available bootstrap instructions are incomplete.')
    docs.sort(key=lambda row: row['path'])
    current = dict(account=account, instructions=dict(status=status, authority=authority, documents=docs, missing_paths=sorted(missing)), capabilities=caps)
    digest = hashlib.sha256(_encoded(current)).hexdigest()
    result = dict(schema_version=1, **current, content_digest=digest,
                  coverage=dict(instructions_complete=status == 'available', instruction_pages_complete=True),
                  unread_sources=['customer_history', 'entity_memory', 'projects', 'attachments'],
                  operational_status=dict(tasks='not_read', queue='not_read', provider_connections='not_checked', budget='not_read'))
    if type(offset) is not int or offset < 0:
        raise ValueError('Invalid bootstrap instruction offset.')
    if instruction_path is not None:
        if instruction_path not in seen or not isinstance(sha256, str):
            raise ValueError('Unknown bootstrap continuation.')
        row = next(row for row in docs if row['path'] == instruction_path)
        if row['sha256'] != sha256:
            raise ValueError('Bootstrap instruction changed; restart bootstrap.')
        if offset >= len(row['text']):
            raise ValueError('Invalid bootstrap instruction offset.')
        page = row['text'][offset:offset + PAGE_CHARS]
        end = offset + len(page)
        result['instructions']['documents'] = [{key: value for key, value in item.items() if key != 'text'} for item in docs]
        result['instruction_page'] = dict(path=instruction_path, revision=row['revision'], sha256=sha256, offset=offset, text=page, next_offset=end if end < len(row['text']) else None)
        result['coverage']['instruction_pages_complete'] = False
        result['coverage']['instructions_complete'] = False
    elif offset or sha256 is not None:
        raise ValueError('Bootstrap continuation requires an instruction path.')
    elif sum(len(row['text'].encode('utf-8')) for row in docs) > MAX_CONTEXT_BYTES or len(_encoded(result)) > MAX_RESPONSE_BYTES:
        result['instructions']['documents'] = [{key: value for key, value in row.items() if key != 'text'} for row in docs]
        result['coverage']['instructions_complete'] = False
        result['coverage']['instruction_pages_complete'] = False
        result['next_read'] = [dict(instruction_path=row['path'], offset=0, sha256=row['sha256']) for row in docs]
    if len(_encoded(result)) > MAX_RESPONSE_BYTES:
        raise ValueError('Bootstrap metadata exceeds the bounded contract.')
    return result


def read(settings, *, instruction_path=None, offset=0, sha256=None, call=None):
    call = call or rpc.call_sync
    def identity():
        row = call(settings, 'account.who_am_i', {})
        if not isinstance(row, dict) or row.get('signed_in') is not True or row.get('uid') != settings.engine_owner_uid or row.get('email', '').lower() != settings.email_address.strip().lower():
            raise ValueError('Bootstrap account does not match the configured operator.')
        return dict(profile_uid=row['uid'], email=row['email'].lower())
    first = identity()
    published = standing_instructions.read(settings, authority_only=True, call=call)
    first['company_ref'] = published['space_id']
    expected = {'mail/%s.md' % first['email'], 'procedures.md'}
    missing = sorted(expected - {row['path'] for row in published['documents']})
    native = call(settings, 'system.capabilities', {})
    if not isinstance(native, dict) or len(native) > 100:
        raise ValueError('Invalid engine capability projection.')
    capabilities = [name for name, value in native.items() if isinstance(name, str) and (value is True or type(value) is int and value >= 1)]
    last = identity()
    if last != {key: first[key] for key in ('profile_uid', 'email')}:
        raise ValueError('Bootstrap account changed during the read.')
    return assemble(first, dict(status='missing' if missing else 'available', authority=published['authority'], documents=published['documents'], missing_paths=missing), capabilities,
                    instruction_path=instruction_path, offset=offset, sha256=sha256)


def cmd_bootstrap(args):
    try:
        result = read(config.load(), instruction_path=args.instruction_path, offset=args.offset, sha256=args.sha256)
    except Exception:
        print('Operator bootstrap unavailable: authenticated context could not be verified.', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def add_subparsers(sub):
    parser = sub.add_parser('bootstrap', help='load verified interactive operator context without taking action')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--instruction-path')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--sha256')
    parser.set_defaults(func=cmd_bootstrap)
