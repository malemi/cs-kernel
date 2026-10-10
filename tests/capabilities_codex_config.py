from __future__ import annotations

import hashlib
import json
import os
import stat
import tomllib
from datetime import date, datetime, time
from pathlib import Path


def _typed(value):
    if isinstance(value, dict):
        return ['dict', [[key, _typed(item)] for key, item in sorted(value.items())]]
    if isinstance(value, list):
        return ['list', [_typed(item) for item in value]]
    if type(value) is float:
        return ['float', value.hex()]
    if type(value) in (str, int, bool):
        return [type(value).__name__, value]
    if type(value) in (date, datetime, time):
        return [type(value).__name__, value.isoformat()]
    raise AssertionError('Unsupported Codex configuration value type')


def _canonical(value):
    return json.dumps(_typed(value), separators=(',', ':'), ensure_ascii=True).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _parse(raw):
    try:
        return tomllib.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise AssertionError('Invalid Codex user configuration TOML') from None


def _no_symlinks(path):
    assert not any(part.is_symlink() for part in (path, *path.parents)), 'Symlink in Codex snapshot path'


def _private_directory(path):
    _no_symlinks(path)
    info = path.stat()
    assert stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700, 'Codex snapshot directory must be mode0700'
    assert info.st_uid == os.getuid(), 'Codex snapshot directory owner mismatch'


def _read_snapshot(receipt):
    assert set(receipt) == {'source_path', 'private_path', 'raw_sha256', 'semantic_sha256'}, 'Malformed Codex snapshot receipt'
    path = Path(receipt['private_path'])
    assert path.is_absolute(), 'Codex private snapshot path must be absolute'
    _private_directory(path.parent)
    _no_symlinks(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600, 'Codex snapshot must be a mode0600 regular file'
        assert info.st_uid == os.getuid() and info.st_nlink == 1, 'Codex snapshot owner or hardlink mismatch'
        raw = stream.read()
    assert _sha(raw) == receipt['raw_sha256'], 'Codex snapshot raw hash drift'
    config = _parse(raw)
    assert _sha(_canonical(config)) == receipt['semantic_sha256'], 'Codex snapshot semantic hash drift'
    return config


def capture_user_config(destination: Path, user_config: Path | None = None):
    source = Path(user_config) if user_config is not None else Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
    source = source.absolute()
    assert source.is_file(), 'Missing Codex user configuration file'
    _no_symlinks(source)
    raw = source.read_bytes()
    config = _parse(raw)
    destination = Path(destination).absolute()
    _no_symlinks(destination)
    assert not any((parent / '.git').exists() for parent in destination.parents), 'Codex private snapshot destination is inside a Git clone'
    assert not destination.exists(), 'Codex private snapshot already exists'
    if not destination.parent.exists():
        destination.parent.mkdir(mode=0o700)
    _private_directory(destination.parent)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(raw)
    assert source.read_bytes() == raw, 'Codex user configuration changed during capture'
    receipt = {'source_path': str(source), 'private_path': str(destination), 'raw_sha256': _sha(raw),
               'semantic_sha256': _sha(_canonical(config))}
    _read_snapshot(receipt)
    return receipt


def compare_config(before, after, owned_roots: list[Path]):
    old, new = _read_snapshot(before), _read_snapshot(after)
    assert before['source_path'] == after['source_path'], 'Codex user configuration source changed'
    owned = set()
    for root in owned_roots:
        root = Path(root)
        assert root.is_dir(), 'Owned Codex clone directory missing'
        _no_symlinks(root)
        owned.add(str(root.resolve()))
        assert not any(Path(receipt['private_path']).is_relative_to(root.resolve()) for receipt in (before, after)), 'Codex private snapshot is inside owned clone'
    old_other = {key: value for key, value in old.items() if key != 'projects'}
    new_other = {key: value for key, value in new.items() if key != 'projects'}
    assert _canonical(old_other) == _canonical(new_other), 'Codex nonproject configuration changed'
    old_projects, new_projects = old.get('projects', {}), new.get('projects', {})
    assert isinstance(old_projects, dict) and isinstance(new_projects, dict), 'Codex projects configuration must be a table'
    assert 'projects' not in old or 'projects' in new, 'Codex projects table removed'
    for key, value in old_projects.items():
        assert key in new_projects and _canonical(value) == _canonical(new_projects[key]), 'Prior Codex project changed or removed'
    added = sorted(set(new_projects) - set(old_projects))
    assert 'projects' in old or 'projects' not in new or added, 'Empty Codex projects table added'
    for key in added:
        assert key in owned, 'Added Codex project is not an exact owned clone path'
        assert _canonical(new_projects[key]) == _canonical({'trust_level': 'trusted'}), 'Added Codex project is not sole trusted field'
    return {'before_raw_sha256': before['raw_sha256'], 'after_raw_sha256': after['raw_sha256'],
            'before_semantic_sha256': before['semantic_sha256'], 'after_semantic_sha256': after['semantic_sha256'],
            'added_owned_projects': added}
