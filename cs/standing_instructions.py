"""Authenticated read-only access to the current mailbox's published rules."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import sys

from . import config, rpc

MAX_DOCUMENT_BYTES = 196608
MAX_TOTAL_BYTES = 393216
MAILBOX = re.compile(r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}')


def read(settings, *, authority_only=False, call=None):
    mailbox = settings.email_address.strip().lower()
    if not MAILBOX.fullmatch(mailbox):
        raise ValueError('The selected mailbox is invalid.')
    result = (call or rpc.call_sync)(settings, 'instructions.preview', {})
    if not isinstance(result, dict) or result.get('authority') not in ('legacy', 'managed'):
        raise ValueError('The engine did not provide instruction authority.')
    if not isinstance(result.get('space_id'), str) or not result['space_id']:
        raise ValueError('The engine did not provide company scope.')
    rows = result.get('documents')
    if not isinstance(rows, list) or len(rows) > 2:
        raise ValueError('The engine returned an invalid instruction document set.')
    allowed = {f'mail/{mailbox}.md', 'procedures.md'}
    seen = set()
    documents = []
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Malformed instruction document.')
        path = row.get('path')
        if not isinstance(path, str) or path not in allowed or path in seen:
            raise ValueError('Foreign or duplicate instruction document.')
        seen.add(path)
        revision = row.get('revision')
        checksum = row.get('sha256')
        encoded = row.get('content_base64')
        if type(revision) is not int or revision < 1:
            raise ValueError('Invalid instruction revision.')
        if not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise ValueError('Invalid instruction digest.')
        if not isinstance(encoded, str) or len(encoded) > ((MAX_DOCUMENT_BYTES + 2) // 3) * 4:
            raise ValueError('Instruction document exceeds the read limit.')
        try:
            raw = base64.b64decode(encoded, validate=True)
            text = raw.decode('utf-8')
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise ValueError('Invalid instruction encoding.') from exc
        total += len(raw)
        if not raw or len(raw) > MAX_DOCUMENT_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError('Instruction document is empty or exceeds the read limit.')
        if hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError('Instruction digest does not match its content.')
        documents.append(dict(path=path, revision=revision, sha256=checksum, text=text))
    missing = allowed - seen
    if missing and not (authority_only and result['authority'] == 'legacy'):
        raise ValueError('Published standing instructions are missing: %s.' % ', '.join(sorted(missing)))
    return dict(authority=result['authority'], space_id=result['space_id'], mailbox=mailbox,
                documents=sorted(documents, key=lambda row: row['path']))


def cmd_standing_instructions(args):
    try:
        result = read(config.load(), authority_only=args.authority_only)
    except Exception as exc:
        print('Standing instructions unavailable: %s' % exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.authority_only:
        print(result['authority'])
    else:
        print('Instruction authority: %s' % result['authority'])
        for row in result['documents']:
            print('\n%s · revision %d · sha256 %s' % (row['path'], row['revision'], row['sha256']))
            sys.stdout.write(row['text'])
            if not row['text'].endswith('\n'):
                sys.stdout.write('\n')
    return 0


def add_subparsers(sub):
    parser = sub.add_parser('standing-instructions', help='read current published standing instructions')
    parser.add_argument('--json', action='store_true', help='include validated document metadata and text as JSON')
    parser.add_argument('--authority-only', action='store_true', help='read authority; allow an empty legacy bootstrap')
    parser.set_defaults(func=cmd_standing_instructions)
