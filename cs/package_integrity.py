"""Read-only accidental-drift verification against immutable release Git objects."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import sysconfig
import tempfile
import tomllib


class IntegrityError(Exception):
    pass


def _git(repo, *args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1')
    for key in list(env):
        if key.startswith('GIT_') and key not in {'GIT_TERMINAL_PROMPT', 'GIT_NO_REPLACE_OBJECTS'}:
            del env[key]
    try:
        result = subprocess.run(['git', '-C', str(repo), *args], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise IntegrityError('reference_unavailable') from None
    if result.returncode:
        raise IntegrityError('reference_unavailable')
    return result.stdout


def _cache(path):
    return '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'}


def _reference(repo, tag, expected):
    commit = _git(repo, 'rev-parse', '--verify', 'refs/tags/' + tag + '^{commit}').decode().strip()
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
        raise IntegrityError('invalid_reference_commit')
    if expected and expected.lower() != commit:
        raise IntegrityError('commit_mismatch')
    project = tomllib.loads(_git(repo, 'show', commit + ':pyproject.toml').decode())
    version = project['project']['version']
    if tag != 'v' + version:
        raise IntegrityError('tag_version_mismatch')
    files = {}
    for entry in _git(repo, 'ls-tree', '-rz', commit, '--', 'cs/').split(b'\0'):
        if not entry:
            continue
        header, raw_path = entry.split(b'\t', 1)
        mode, kind, oid = header.split()
        path = raw_path.decode()
        if mode not in {b'100644', b'100755'} or kind != b'blob':
            raise IntegrityError('unsafe_reference_file')
        if _cache(Path(path)):
            continue
        files[path[3:]] = hashlib.sha256(_git(repo, 'cat-file', 'blob', oid.decode())).hexdigest()
    if '__init__.py' not in files or 'package_integrity.py' not in files:
        raise IntegrityError('incomplete_reference')
    return commit, version, files


def verify(args):
    import cs
    root = Path(cs.__file__).absolute().parent
    report = {'ok': False, 'package_root': str(root), 'mismatches': []}
    try:
        explicit = (args.reference_repo, args.tag, args.expected_commit)
        if any(explicit) and not all(explicit):
            raise IntegrityError('explicit_reference_requires_repo_tag_commit')
        from .project_update import _find_pin_line
        pin = None
        requirements = Path.cwd() / 'requirements.txt'
        if requirements.is_file():
            pin = _find_pin_line(requirements.read_text())
        if all(explicit):
            tag, expected = args.tag, args.expected_commit
        elif pin:
            tag, expected = pin[3], None
        else:
            raise IntegrityError('clone_pin_unavailable')
        if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
            raise IntegrityError('release_tag_required')
        if expected and not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', expected):
            raise IntegrityError('invalid_expected_commit')
        report['tag'] = tag
        with tempfile.TemporaryDirectory(prefix='cs-integrity-') as temporary:
            if all(explicit):
                repo = Path(args.reference_repo).absolute()
            else:
                repo = Path(temporary)
                _git(repo, 'init', '--bare', '--quiet')
                _git(repo, 'fetch', '--quiet', '--depth=1', '--no-tags', '--', pin[2],
                     'refs/tags/' + tag + ':refs/tags/' + tag)
            commit, version, reference = _reference(repo, tag, expected)
        report.update(commit=commit, reference_version=version, reference_files=len(reference))
        dist = importlib.metadata.distribution('cs-kernel')
        report['installed_version'] = dist.version
        if dist.version != version:
            raise IntegrityError('installed_version_mismatch')
        direct = json.loads(dist.read_text('direct_url.json') or '{}')
        if not isinstance(direct, dict):
            raise IntegrityError('integrity_unavailable')
        directory = direct.get('dir_info', {})
        vcs = direct.get('vcs_info', {})
        if not isinstance(directory, dict) or not isinstance(vcs, dict):
            raise IntegrityError('integrity_unavailable')
        if (any(key in direct and not isinstance(direct[key], str) for key in ('url',))
                or any(key in vcs and not isinstance(vcs[key], str)
                       for key in ('vcs', 'commit_id', 'requested_revision'))
                or 'editable' in directory and type(directory['editable']) is not bool):
            raise IntegrityError('integrity_unavailable')
        if directory.get('editable'):
            raise IntegrityError('editable_install')
        if vcs and (vcs.get('vcs') != 'git' or vcs.get('commit_id') != commit):
            raise IntegrityError('installed_commit_mismatch')
        if vcs.get('requested_revision') and vcs['requested_revision'] not in {tag, commit}:
            raise IntegrityError('installed_revision_mismatch')
        if pin and pin[3] != tag:
            raise IntegrityError('clone_pin_mismatch')
        lock = Path.cwd() / 'requirements.lock'
        if lock.is_file():
            lock_pin = _find_pin_line(lock.read_text())
            if lock_pin and lock_pin[3] not in {tag, commit}:
                raise IntegrityError('lock_commit_mismatch')
        installed_root = Path(dist.locate_file('cs')).absolute()
        site_roots = {Path(sysconfig.get_path(key)).resolve() for key in ('purelib', 'platlib')}
        if root != installed_root or root.parent.resolve() not in site_roots:
            raise IntegrityError('import_origin_mismatch')
        if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
            raise IntegrityError('symlink_package_root')
        for name, module in tuple(sys.modules.items()):
            if name == 'cs' or name.startswith('cs.'):
                origin = getattr(module, '__file__', None)
                if origin and not Path(origin).absolute().is_relative_to(root):
                    raise IntegrityError('import_origin_mismatch')
        actual = {}
        mismatches = []
        def unreadable(error):
            raise error
        for directory, dirs, names in os.walk(root, followlinks=False, onerror=unreadable):
            base = Path(directory)
            for name in list(dirs):
                path = base / name
                if path.is_symlink():
                    mismatches.append({'path': path.relative_to(root).as_posix(), 'reason': 'symlink'})
                    dirs.remove(name)
                elif name == '__pycache__':
                    dirs.remove(name)
            for name in names:
                path = base / name
                relative = path.relative_to(root).as_posix()
                if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                    mismatches.append({'path': relative, 'reason': 'unsafe_file'})
                elif not _cache(path):
                    actual[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(reference.keys() | actual.keys()):
            reason = ('extra' if path not in reference else 'missing' if path not in actual
                      else 'modified' if reference[path] != actual[path] else None)
            if reason:
                mismatches.append({'path': path, 'reason': reason})
        report.update(installed_files=len(actual), mismatch_count=len(mismatches),
                      mismatches=mismatches[:100], ok=not mismatches)
        if mismatches:
            report['error'] = 'package_drift'
    except IntegrityError as error:
        report['error'] = str(error)
    except (OSError, ValueError, KeyError, UnicodeError, importlib.metadata.PackageNotFoundError):
        report['error'] = 'integrity_unavailable'
    return report


def cmd_verify_install(args):
    report = verify(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print('Installation verified' if report['ok'] else 'Installation verification failed: ' + report['error'])
        for mismatch in report['mismatches']:
            print(mismatch['reason'] + ': ' + mismatch['path'])
    return 0 if report['ok'] else 1


def register(sub):
    parser = sub.add_parser('verify-install', help='verify installed package bytes against an immutable Git release; remote reference needs network access')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--reference-repo', metavar='PATH', help='offline Git object reference; requires --tag and --expected-commit')
    parser.add_argument('--tag', metavar='TAG')
    parser.add_argument('--expected-commit', metavar='SHA')
    parser.set_defaults(func=cmd_verify_install)
