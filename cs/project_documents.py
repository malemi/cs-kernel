"""Validated project transport and local byte-preserving working-copy primitives."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path, PurePosixPath

from . import rpc

MAX_FILE = 4 * 1024 * 1024
MAX_FILES = 10000
MAX_TREE = 128 * 1024 * 1024
META = '.cs-project.json'
SLUG = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


class ProjectError(ValueError):
    """An actionable refusal that does not disclose document contents."""


def slug(value):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise ProjectError('Use a project slug of 1–100 lowercase letters, digits and hyphens.')
    return value


def path_name(value):
    if (not isinstance(value, str) or not value or len(value.encode('utf-8')) > 512
            or '\\' in value or ':' in value or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ProjectError('Invalid project document path.')
    if any(p == '.env' or p.startswith('.env.') for p in value.split('/')):
        raise ProjectError('Sensitive .env files cannot be stored as project documents.')
    if value == META or value.startswith(META + '/'):
        raise ProjectError('The working-copy metadata name is reserved.')
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def space(value):
    if not isinstance(value, str) or not value or len(value) > 128 or not value.isascii() or not value.isprintable():
        raise ProjectError('Invalid company-space response.')
    return value


def integer(value, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ProjectError('Invalid project revision, size or pagination metadata.')
    return value


def metadata(item, project=None, path=None):
    if not isinstance(item, dict):
        raise ProjectError('Invalid document metadata response.')
    slug(item.get('project'))
    path_name(item.get('path'))
    integer(item.get('revision'), 1)
    integer(item.get('size'), 0, MAX_FILE)
    if not isinstance(item.get('sha256'), str) or not HASH.fullmatch(item['sha256']):
        raise ProjectError('Invalid document hash.')
    for key in ('author_uid', 'created_at'):
        if not isinstance(item.get(key), str) or not item[key]:
            raise ProjectError('Invalid document provenance.')
    if project is not None and item['project'] != project or path is not None and item['path'] != path:
        raise ProjectError('Engine returned a different document.')
    return {key: item[key] for key in ('project', 'path', 'revision', 'sha256', 'size', 'author_uid', 'created_at')}


class Documents:
    def __init__(self, settings, call=None):
        self.settings = settings
        self.call = call or rpc.call_sync
        self.space_id = None

    def request(self, method, **params):
        try:
            result = self.call(self.settings, 'projects.' + method, params)
        except rpc.EngineError as exc:
            messages = {
                -32601: 'Upgrade the engine to use shared projects; legacy folders can then be imported with cs project import.',
                -32040: 'Project conflict: fetch a new checkout and reconcile your edits.',
                -32041: 'Company membership changed. Keep your edits and check out the project again.',
                -32044: 'Project or document is missing. Use cs project list, or import its legacy directory.',
                -32043: 'Company memory is unavailable. Check the engine and company-memory connection.',
                -32602: 'Engine refused invalid project parameters.',
            }
            error = ProjectError(messages.get(exc.code, 'The engine could not complete the project operation.'))
            error.code = exc.code
            raise error from exc
        if not isinstance(result, dict):
            raise ProjectError('Invalid project response.')
        current = space(result.get('space_id'))
        if self.space_id is not None and current != self.space_id:
            raise ProjectError('Company membership changed. Keep your edits and check out the project again.')
        self.space_id = current
        return result

    def page(self, method, limit=50, offset=0, **params):
        integer(limit, 1, 100)
        integer(offset)
        result = self.request(method, limit=limit, offset=offset, **params)
        integer(result.get('total'))
        integer(result.get('limit'), 1, 100)
        integer(result.get('offset'))
        if result.get('limit') != limit or result.get('offset') != offset:
            raise ProjectError('Invalid project pagination response.')
        items = result.get('items')
        if not isinstance(items, list) or len(items) > limit or len(items) > max(0, result['total'] - offset):
            raise ProjectError('Invalid project page.')
        if method in ('files', 'history'):
            for item in items:
                metadata(item, params['project'], params.get('path'))
        else:
            for item in items:
                if not isinstance(item, dict):
                    raise ProjectError('Invalid project summary.')
                slug(item.get('project'))
                integer(item.get('file_count'))
        return result

    def files(self, project, missing_ok=False):
        items = {}
        offset = 0
        total = None
        while True:
            try:
                page = self.page('files', limit=100, offset=offset, project=slug(project))
            except ProjectError as exc:
                if missing_ok and offset == 0 and getattr(exc, 'code', None) == -32044:
                    self.page('list', limit=1)
                    return {}
                raise
            if total is not None and page['total'] != total:
                raise ProjectError('Project changed during listing. Retry the operation.')
            total = page['total']
            if total > MAX_FILES:
                raise ProjectError('Project exceeds the 10000-file working-copy limit.')
            for item in page['items']:
                if item['path'] in items:
                    raise ProjectError('Project changed during listing. Retry the operation.')
                items[item['path']] = item
            offset += len(page['items'])
            if offset >= total:
                return items
            if not page['items']:
                raise ProjectError('Incomplete project listing.')

    def read(self, project, path, revision=None):
        params = dict(project=slug(project), path=path_name(path))
        if revision is not None:
            params['revision'] = integer(revision, 1)
        result = self.request('read', **params)
        metadata(result, project, path)
        if revision is not None and result['revision'] != revision:
            raise ProjectError('Engine returned a different revision.')
        encoded = result.get('content_base64')
        if not isinstance(encoded, str) or len(encoded) > ((MAX_FILE + 2) // 3) * 4:
            raise ProjectError('Invalid document payload size.')
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            raise ProjectError('Invalid document encoding.') from None
        if len(data) != result['size'] or digest(data) != result['sha256']:
            raise ProjectError('Document verification failed: hash or size mismatch.')
        return result, data

    def write(self, project, path, data, expected):
        if len(data) > MAX_FILE:
            raise ProjectError('Document exceeds 4 MiB.')
        result = self.request('write', space_id=self.space_id, project=slug(project),
                              path=path_name(path), content_base64=base64.b64encode(data).decode('ascii'),
                              expected_revision=integer(expected))
        metadata(result, project, path)
        if result['sha256'] != digest(data) or result['size'] != len(data):
            raise ProjectError('Saved document metadata failed verification.')
        verified, stored = self.read(project, path, result['revision'])
        if stored != data:
            raise ProjectError('Saved document read-back failed verification.')
        return metadata(verified, project, path)


def safe_ancestors(path):
    """Inspect without resolving away a symlink before checking it."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ProjectError('Symlinks are not supported in working-copy paths.')
    return path


def read_bytes(path):
    safe_ancestors(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ProjectError('Only regular project files are supported.')
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        mode = os.fstat(stream.fileno()).st_mode
        if not stat.S_ISREG(mode):
            raise ProjectError('Only regular project files are supported.')
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ProjectError('Document exceeds the 4 MiB limit.')
    return data


def scan(root, working=False):
    root = safe_ancestors(root)
    if not root.is_dir():
        raise ProjectError('Project source must be a directory.')
    files, excluded, total_size = {}, [], 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in sorted(dirs + names):
            path = Path(directory, name)
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise ProjectError('Source contains a symlink; import/save refused.')
            if name == '.env' or name.startswith('.env.'):
                raise ProjectError('Source contains a sensitive .env path; import/save refused.')
            if name in ('.git', '__pycache__', '.DS_Store') or name.endswith('.pyc'):
                excluded.append(rel)
                if name in dirs:
                    dirs.remove(name)
                continue
            if working and rel == META:
                continue
            path_name(rel)
            if path.is_dir():
                continue
            files[rel] = read_bytes(path)
            total_size += len(files[rel])
            if total_size > MAX_TREE:
                raise ProjectError('Project exceeds the 128 MiB working-copy limit.')
            if len(files) > MAX_FILES:
                raise ProjectError('Project exceeds the 10000-file working-copy limit.')
    return files, excluded


def load_state(root):
    target = safe_ancestors(Path(root) / META)
    try:
        state = json.loads(read_bytes(target))
    except (ValueError, OSError):
        raise ProjectError('Cannot read working-copy metadata. Make a new checkout and preserve your edits.') from None
    if not isinstance(state, dict) or state.get('version') != 1 or type(state.get('version')) is not int:
        raise ProjectError('Invalid working-copy metadata version.')
    space(state.get('space_id'))
    slug(state.get('project'))
    entries = state.get('files')
    if not isinstance(entries, dict) or len(entries) > MAX_FILES:
        raise ProjectError('Invalid working-copy file metadata.')
    for path, item in entries.items():
        path_name(path)
        metadata(item, state['project'], path)
    return state


def write_state(root, state):
    safe_ancestors(root)
    target = safe_ancestors(Path(root) / META)
    fd, name = tempfile.mkstemp(prefix='.cs-project-', dir=root)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
