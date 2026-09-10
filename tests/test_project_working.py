#!/usr/bin/env python3
"""Filesystem safety, CAS failure recovery and hostile-response tests in temp companies."""
from __future__ import annotations

import base64
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cs.project_documents import Documents, ProjectError, META, MAX_FILE, digest, load_state, scan
from cs.project_working import checkout, import_projects, save
from cs.rpc import EngineError


class FakeEngine:
    """Small persistent revision model; exercises client behavior, not server correctness."""
    def __init__(self):
        self.records = {}
        self.space = 'space-one'
        self.writes = 0
        self.fail_write = None
        self.lose_ack = False

    def item(self, project, path, revision=None, content=False):
        revisions = self.records[project][path]
        revision = revision or len(revisions)
        data = revisions[revision - 1]
        result = dict(project=project, path=path, revision=revision, sha256=digest(data),
                      size=len(data), author_uid='owner-one', created_at='2026-09-10T12:00:00Z')
        if content:
            result['content_base64'] = base64.b64encode(data).decode()
        return result

    def __call__(self, settings, method, params):
        action = method.removeprefix('projects.')
        p = params.get('project')
        path = params.get('path')
        if action in ('write', 'create') and params['space_id'] != self.space:
            raise EngineError(-32041, 'space mismatch')
        if action == 'list':
            items = [dict(project=name, file_count=len(files)) for name, files in sorted(self.records.items())]
        elif action in ('files', 'history', 'read'):
            if p not in self.records or action != 'files' and path not in self.records[p]:
                raise EngineError(-32044, 'missing')
            if action == 'files':
                items = [self.item(p, name) for name in sorted(self.records[p])]
            elif action == 'history':
                items = [self.item(p, path, rev) for rev in range(1, len(self.records[p][path]) + 1)]
            else:
                return dict(space_id=self.space, **self.item(p, path, params.get('revision'), True))
        elif action == 'create':
            if p in self.records:
                raise EngineError(-32040, 'exists')
            self.records[p] = {name: [base64.b64decode(data)] for name, data in params['files'].items()}
            return dict(space_id=self.space, project=p, files=[self.item(p, name) for name in self.records[p]])
        elif action == 'write':
            self.writes += 1
            if self.writes == self.fail_write:
                raise ConnectionError('simulated connection lost')
            revisions = self.records.setdefault(p, {}).setdefault(path, [])
            data = base64.b64decode(params['content_base64'])
            if not revisions or revisions[-1] != data:
                if params['expected_revision'] != len(revisions):
                    raise EngineError(-32040, 'conflict')
                revisions.append(data)
            if self.lose_ack:
                self.lose_ack = False
                raise ConnectionError('simulated lost acknowledgement')
            return dict(space_id=self.space, **self.item(p, path))
        else:
            raise AssertionError(method)
        offset, limit = params['offset'], params['limit']
        return dict(space_id=self.space, items=items[offset:offset + limit], total=len(items), limit=limit, offset=offset)


class ProjectWorkingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.engine = FakeEngine()
        self.engine.records['trial'] = {'status.md': [b'original\n'], 'attachment.bin': [b'\x00\xff\x80']}

    def client(self, call=None):
        return Documents(None, call or self.engine)

    def checkout(self, name='work'):
        dest = self.root / name
        checkout(self.client(), 'trial', dest)
        return dest

    def test_binary_round_trip_and_preview(self):
        dest = self.checkout()
        self.assertEqual((dest / 'attachment.bin').read_bytes(), b'\x00\xff\x80')
        state = load_state(dest)
        self.assertNotIn('content_base64', state['files']['attachment.bin'])
        self.assertEqual((dest / META).stat().st_mode & 0o777, 0o600)
        (dest / 'status.md').write_bytes(b'changed\n')
        save(self.client(), dest)
        self.assertEqual(self.engine.writes, 0)
        save(self.client(), dest, True)
        self.assertEqual(self.engine.records['trial']['status.md'], [b'original\n', b'changed\n'])
        self.assertEqual(load_state(dest)['files']['status.md']['revision'], 2)
        save(self.client(), dest, True)
        self.assertEqual(self.engine.writes, 1)

    def test_conflicts_preflight_all_files(self):
        dest = self.checkout()
        (dest / 'a-new.md').write_bytes(b'new')
        (dest / 'status.md').write_bytes(b'mine')
        self.engine.records['trial']['status.md'].append(b'theirs')
        with self.assertRaises(ProjectError):
            save(self.client(), dest, True)
        self.assertEqual(self.engine.writes, 0)
        self.assertEqual((dest / 'status.md').read_bytes(), b'mine')

    def test_space_changed_refuses_without_writes(self):
        dest = self.checkout()
        (dest / 'status.md').write_bytes(b'changed')
        self.engine.space = 'space-two'
        with self.assertRaises(ProjectError):
            save(self.client(), dest, True)
        self.assertEqual(self.engine.writes, 0)

    def test_partial_save_and_ack_lost_recovery(self):
        dest = self.checkout()
        (dest / 'a-new.md').write_bytes(b'new')
        (dest / 'status.md').write_bytes(b'changed')
        self.engine.fail_write = 2
        with self.assertRaises(ConnectionError):
            save(self.client(), dest, True)
        self.assertIn('a-new.md', load_state(dest)['files'])
        self.assertEqual(load_state(dest)['files']['status.md']['revision'], 1)
        self.engine.fail_write = None
        self.engine.lose_ack = True
        with self.assertRaises(ConnectionError):
            save(self.client(), dest, True)
        self.assertEqual(load_state(dest)['files']['status.md']['revision'], 1)
        save(self.client(), dest, True)
        self.assertEqual(load_state(dest)['files']['status.md']['revision'], 2)
        self.assertEqual(len(self.engine.records['trial']['status.md']), 2)

    def test_delete_and_unchanged_local_do_not_overwrite(self):
        dest = self.checkout()
        (dest / 'attachment.bin').unlink()
        self.engine.records['trial']['status.md'].append(b'colleague')
        save(self.client(), dest, True)
        self.assertEqual(self.engine.writes, 0)
        self.assertIn('attachment.bin', self.engine.records['trial'])
        self.assertEqual(load_state(dest)['files']['status.md']['revision'], 1)

    def test_import_all_preserves_bytes_and_retries(self):
        source = self.root / 'legacy'
        (source / 'one' / 'nested').mkdir(parents=True)
        (source / 'two').mkdir()
        (source / 'README.md').write_text('conventions')
        (source / 'one' / 'nested' / 'file.bin').write_bytes(bytes(range(256)))
        (source / 'two' / 'status.md').write_bytes(b'status')
        (source / 'two' / '.DS_Store').write_bytes(b'generated')
        before = {str(p): p.read_bytes() for p in source.rglob('*') if p.is_file()}
        import_projects(self.client(), source, all_projects=True)
        self.assertEqual(self.engine.writes, 0)
        self.engine.fail_write = 2
        with self.assertRaises(ConnectionError):
            import_projects(self.client(), source, all_projects=True, commit=True)
        self.engine.fail_write = None
        import_projects(self.client(), source, all_projects=True, commit=True)
        self.assertEqual(self.engine.records['one']['nested/file.bin'], [bytes(range(256))])
        self.assertEqual(self.engine.records['two']['status.md'], [b'status'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in source.rglob('*') if p.is_file()})

    def test_import_all_enforces_aggregate_file_limit_before_rpc(self):
        source = self.root / 'legacy'
        for name in ('one', 'two'):
            project = source / name
            project.mkdir(parents=True)
            for filename in ('a.md', 'b.md'):
                (project / filename).write_bytes(b'content')
        calls = []
        def observed(*args):
            calls.append(args)
            return self.engine(*args)
        with patch('cs.project_working.MAX_FILES', 2):
            with self.assertRaisesRegex(ProjectError, 'file limit'):
                import_projects(self.client(observed), source, all_projects=True, commit=True)
        self.assertEqual(calls, [])
        self.assertEqual(self.engine.writes, 0)

    def test_import_preflights_every_tree_and_remote_conflict(self):
        source = self.root / 'source'
        (source / 'aaa').mkdir(parents=True)
        (source / 'trial').mkdir()
        (source / 'aaa' / 'safe.md').write_bytes(b'safe')
        (source / 'trial' / 'status.md').write_bytes(b'different')
        with self.assertRaises(ProjectError):
            import_projects(self.client(), source, all_projects=True, commit=True)
        self.assertEqual(self.engine.writes, 0)
        (source / 'trial' / 'status.md').unlink()
        (source / 'trial' / '.env').write_text('secret')
        with self.assertRaises(ProjectError):
            import_projects(self.client(), source, all_projects=True, commit=True)
        self.assertEqual(self.engine.writes, 0)

    def test_unsafe_source_and_destinations(self):
        target = self.root / 'target'
        target.mkdir()
        link = self.root / 'link'
        link.symlink_to(target, target_is_directory=True)
        for dest in (target, link / 'work'):
            with self.assertRaises(ProjectError):
                checkout(self.client(), 'trial', dest)
        (target / 'symlink').symlink_to(self.root / 'missing')
        with self.assertRaises(ProjectError):
            scan(target)
        (target / 'symlink').unlink()
        os.mkfifo(target / 'pipe')
        with self.assertRaises(ProjectError):
            scan(target)
        (target / 'pipe').unlink()
        with (target / 'large').open('wb') as stream:
            stream.truncate(MAX_FILE + 1)
        with self.assertRaises(ProjectError):
            scan(target)

    def test_hostile_metadata_and_response_hash(self):
        dest = self.checkout()
        original = json.loads((dest / META).read_text())
        for key in ('../escape', '/absolute', 'a\\b', '.env', '.cs-project.json', 'a//b'):
            changed = copy.deepcopy(original)
            changed['files'][key] = changed['files'].pop('status.md')
            (dest / META).write_text(json.dumps(changed))
            with self.assertRaises(ProjectError):
                save(self.client(), dest, True)
        (dest / META).write_text(json.dumps(original))
        changed = copy.deepcopy(original)
        changed['files']['status.md']['revision'] = True
        (dest / META).write_text(json.dumps(changed))
        with self.assertRaises(ProjectError):
            save(self.client(), dest, True)
        def corrupt(settings, method, params):
            response = self.engine(settings, method, params)
            if method == 'projects.read':
                response['content_base64'] = base64.b64encode(b'corrupt').decode()
            return response
        with self.assertRaises(ProjectError):
            checkout(self.client(corrupt), 'trial', self.root / 'corrupt')
        self.assertFalse((self.root / 'corrupt').exists())
        self.assertEqual(self.engine.writes, 0)

    def test_pagination_company_change_and_repeated_items(self):
        self.engine.records['trial'] = {f'file-{n:03}.md': [b'x'] for n in range(101)}
        self.assertEqual(len(self.client().files('trial')), 101)
        def changed(settings, method, params):
            response = self.engine(settings, method, params)
            if params.get('offset'):
                response['space_id'] = 'other-space'
            return response
        with self.assertRaises(ProjectError):
            self.client(changed).files('trial')
        def duplicate(settings, method, params):
            response = self.engine(settings, method, params)
            if params.get('offset'):
                response['items'] = [self.engine.item('trial', 'file-000.md')]
            return response
        with self.assertRaises(ProjectError):
            self.client(duplicate).files('trial')

    def test_old_engine_actionable_without_local_fallback(self):
        def old(*args):
            raise EngineError(-32601, 'method not found')
        with self.assertRaisesRegex(ProjectError, 'Upgrade the engine'):
            self.client(old).page('list')


if __name__ == '__main__':
    unittest.main()
