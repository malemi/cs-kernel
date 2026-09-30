"""`cs instructions` — compile the clone's `company/` standing instructions
and store them in the engine's reserved `operator-instructions` company
project.

Mirrors the engine contract (kept in `mrcall-desktop/engine/docs/features/
project-memory.md`; the constants below are the kernel's own copy of it, not
a second definition):

  * reserved project slug: `operator-instructions`
    (`cs.project_documents.RESERVED_PROJECT_SLUG`);
  * paths: `procedures.md` (company procedures), `mail/<mailbox>.md` (one
    per mailbox identity, mailbox lower-cased), `phone.md` (company, the
    playbook alone);
  * `instructions.store(space_id, path, content_base64, expected_revision)`
    is the ONLY writer for this project — `projects.write`/`projects.create`
    refuse the reserved slug on the engine side, and this module never calls
    them either;
  * `projects.read` is the reader used for the dry-run/diff report.

Company inputs, all under `company/`, all clone-authored
(`cs/project_init.py` `CLONE_AUTHORED_PREFIXES`):

  * `customer-service-playbook.md` -> `procedures.md` and, alone, `phone.md`;
  * `mailbox-identity.md` -> `mail/<this clone's own email_address>.md`;
  * `mailboxes/<email>.md` -> `mail/<email>.md`, one file per OTHER mailbox
    of this company that has no clone of its own (not stamped — a clone
    author creates the directory and its files when such a mailbox exists).

A slot that is absent, empty, or still carrying the kernel's own
`## What to write here` heading compiles as ABSENT: it produces no document,
never a binding instruction nobody wrote. A single non-empty file is
returned byte-for-byte; the current mapping needs no multi-file
concatenation.

The untouched marker is the heading itself, never a checksum or a re-render:
gate 1b guarantees every stamped slot opens with a literal
`## What to write here` heading, and `company/README.md.j2` instructs the
operator to delete that section once the file says something real. The
heading survives every future wording change to a slot's instructions, so an
unedited slot stamped by an older kernel still compiles as absent.

Two collision rules a compile refuses outright, before any network call:
two different `company/` files compiling to the SAME engine path (in
particular `company/mailbox-identity.md` and a
`company/mailboxes/<own address>.md`, colliding case-insensitively), and a
`company/mailboxes/` file whose name is not a mailbox address in the
engine's own shape.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

from . import config, rpc
from .project_documents import (
    Documents, ProjectError, RESERVED_PROJECT_SLUG, digest, metadata, path_name,
)

PROCEDURES_PATH = 'procedures.md'
PHONE_PATH = 'phone.md'

PLAYBOOK_FILE = 'company/customer-service-playbook.md'
IDENTITY_FILE = 'company/mailbox-identity.md'
MAILBOXES_DIR = 'company/mailboxes'

# The heading gate 1b requires at the top of every stamped `company/` slot
# (`cs/templates/project/company/*.md.j2`). Its presence is the untouched
# marker this module compiles as absent; `company/README.md.j2` instructs
# the operator to delete it once the file says something real.
STAMPED_MARKER = '## What to write here'

# The engine's own mailbox-path shape (mirrors `normalize_mailbox` there),
# matched against the lower-cased filename stem — the part before `.md`.
MAILBOX_PATTERN = re.compile(r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}')


def mailbox_path(email):
    """The engine path for one mailbox's identity document."""
    return 'mail/%s.md' % email.strip().lower()


def _slot_bytes(root, rel):
    """The authored bytes of one `company/` slot, or None when it compiles
    as absent (missing, empty, or still carrying the kernel's own
    `## What to write here` heading)."""
    path = Path(root) / rel
    if not path.is_file():
        return None
    data = path.read_bytes()
    if not data:
        return None
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    if STAMPED_MARKER in text:
        return None
    return data


def compile_documents(root, settings):
    """Pure function: clone root -> {engine path: bytes}, per the contract
    above. Reads only; makes no network call. Refuses (raises ProjectError,
    naming the offending file) a collision between two source files or a
    malformed `company/mailboxes/` file name, before returning anything."""
    root = Path(root)
    docs = {}
    sources = {}

    def _assign(path, data, source):
        if path in sources and sources[path] != source:
            raise ProjectError(
                'Refused: %s and %s both compile to %s — rename one.'
                % (sources[path], source, path)
            )
        docs[path] = data
        sources[path] = source

    playbook = _slot_bytes(root, PLAYBOOK_FILE)
    if playbook is not None:
        _assign(PROCEDURES_PATH, playbook, PLAYBOOK_FILE)
        _assign(PHONE_PATH, playbook, PLAYBOOK_FILE)

    if settings.email_address:
        identity = _slot_bytes(root, IDENTITY_FILE)
        if identity is not None:
            _assign(mailbox_path(settings.email_address), identity, IDENTITY_FILE)

    mailboxes_dir = root / MAILBOXES_DIR
    if mailboxes_dir.is_dir():
        for entry in sorted(mailboxes_dir.glob('*.md')):
            rel = '%s/%s' % (MAILBOXES_DIR, entry.name)
            if not MAILBOX_PATTERN.fullmatch(entry.stem.lower()):
                raise ProjectError(
                    'Refused: %s is not a mailbox address (expected <address>.md).' % rel
                )
            data = _slot_bytes(root, rel)
            if data is not None:
                _assign(mailbox_path(entry.stem), data, rel)

    return docs


def absent_slots(root, settings):
    """The candidate `company/` inputs that compiled as absent — for
    `--verbose` reporting only, never for the binding compile above. A
    malformed `company/mailboxes/` file name is skipped here (`compile_
    documents` is what refuses it) rather than raised a second time."""
    root = Path(root)
    absent = []
    if _slot_bytes(root, PLAYBOOK_FILE) is None:
        absent.append(PLAYBOOK_FILE)
    if settings.email_address and _slot_bytes(root, IDENTITY_FILE) is None:
        absent.append(IDENTITY_FILE)
    mailboxes_dir = root / MAILBOXES_DIR
    if mailboxes_dir.is_dir():
        for entry in sorted(mailboxes_dir.glob('*.md')):
            if not MAILBOX_PATTERN.fullmatch(entry.stem.lower()):
                continue
            rel = '%s/%s' % (MAILBOXES_DIR, entry.name)
            if _slot_bytes(root, rel) is None:
                absent.append(rel)
    return absent


def _write_local(base, path, data):
    target = Path(base) / path_name(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def _stored_metadata(client, path):
    """(revision, sha256) of the document currently stored at `path`, or
    None when the engine has none yet (a -32044 `projects.read`)."""
    try:
        result, _data = client.read(RESERVED_PROJECT_SLUG, path)
    except ProjectError as exc:
        if getattr(exc, 'code', None) == -32044:
            return None
        raise
    return result['revision'], result['sha256']


def diff_documents(client, docs):
    """[(path, status, checksum, stored_revision)] for the compiled `docs`,
    against what the engine currently holds. `status` is `new`, `unchanged`,
    or `changed (stored rev N)` — the vocabulary the dry-run print and
    `cs setup` both use. Shared so the two never disagree."""
    rows = []
    for path in sorted(docs):
        data = docs[path]
        checksum = digest(data)
        stored = _stored_metadata(client, path)
        if stored is None:
            rows.append((path, 'new', checksum, None))
        elif stored[1] == checksum:
            rows.append((path, 'unchanged', checksum, stored[0]))
        else:
            rows.append((path, 'changed (stored rev %d)' % stored[0], checksum, stored[0]))
    return rows


def _store(client, path, data, expected_revision):
    """Store one document through the engine's dedicated `instructions.store`
    RPC — the verb's only writer; never `projects.write`."""
    try:
        result = client.call(
            client.settings, 'instructions.store',
            {
                'space_id': client.space_id,
                'path': path_name(path),
                'content_base64': base64.b64encode(data).decode('ascii'),
                'expected_revision': expected_revision,
            },
        )
    except rpc.EngineError as exc:
        raise ProjectError(
            'Engine refused instructions.store for %s: %s' % (path, exc.message)
        ) from exc
    verified = metadata(result, RESERVED_PROJECT_SLUG, path)
    if verified['sha256'] != digest(data) or verified['size'] != len(data):
        raise ProjectError('Stored document metadata failed verification: %s.' % path)
    return verified


def cmd_instructions(args):
    try:
        root = Path.cwd()
        if not (root / 'manifest.toml').is_file():
            raise ProjectError('Run cs instructions from the clone directory containing manifest.toml.')
        settings = config.load()
        docs = compile_documents(root, settings)
        local_base = settings.state_dir / 'instructions'
        for path, data in docs.items():
            _write_local(local_base, path, data)

        if not docs:
            print(
                'No standing-instruction slots are authored yet in company/ '
                '(a slot still carrying its "## What to write here" section '
                'counts as unwritten; delete that section once the file says '
                'something real).'
            )
        else:
            client = Documents(settings)
            client.page('list', limit=1)
            rows = diff_documents(client, docs)
            for path, status, checksum, _revision in rows:
                print('%s  %d bytes  sha256 %s  %s' % (path, len(docs[path]), checksum, status))
            if args.commit:
                for path, _status, _checksum, revision in rows:
                    data = docs[path]
                    stored = _store(client, path, data, revision or 0)
                    _verified, readback = client.read(RESERVED_PROJECT_SLUG, path, stored['revision'])
                    if readback != data:
                        raise ProjectError('Stored document read-back failed verification: %s.' % path)
                    print('%s  stored revision %d' % (path, stored['revision']))

        if args.verbose:
            absent = absent_slots(root, settings)
            if absent:
                print('absent: ' + ', '.join(absent))
        return 0
    except (ProjectError, OSError) as exc:
        print('Instructions operation refused: %s' % exc, file=sys.stderr)
        return 1


def add_subparsers(sub):
    p = sub.add_parser(
        'instructions',
        help='compile company/ standing instructions and store them in the engine',
    )
    p.add_argument(
        '--commit', action='store_true',
        help='store the compiled documents through instructions.store (default: preview only)',
    )
    p.add_argument(
        '--verbose', action='store_true',
        help='also report which company/ slots compiled as absent',
    )
    p.set_defaults(func=cmd_instructions)
