"""Explicit project checkout, compare-and-swap save and non-destructive import."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from .project_documents import (
    Documents, ProjectError, MAX_TREE, digest, load_state, metadata, path_name, read_bytes,
    safe_ancestors, scan, slug, write_state,
)


def _excluded(paths):
    for path in paths:
        print(f'Excluded generated cache: {path}')


def checkout(client, project, directory):
    project = slug(project)
    dest = safe_ancestors(directory)
    if dest.exists():
        raise ProjectError('Checkout destination already exists. Choose a new directory.')
    dest.parent.mkdir(parents=True, exist_ok=True)
    safe_ancestors(dest.parent)
    files = client.files(project)
    if sum(item['size'] for item in files.values()) > MAX_TREE:
        raise ProjectError('Project exceeds the 128 MiB working-copy limit.')
    if not files:
        raise ProjectError('Project has no documents. Import its legacy directory first.')
    # Fetch into a sibling private directory. An interrupted fetch cannot appear
    # to be a complete checkout or overwrite a pre-existing user directory.
    scratch = Path(tempfile.mkdtemp(prefix='.cs-checkout-', dir=dest.parent))
    try:
        verified = {}
        for path, item in files.items():
            fetched, data = client.read(project, path, item['revision'])
            if fetched['sha256'] != item['sha256']:
                raise ProjectError('Project changed during checkout. Retry.')
            target = scratch / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
            verified[path] = metadata(fetched, project, path)
        write_state(scratch, dict(version=1, space_id=client.space_id, project=project, files=verified))
        # mkdir reserves the final pathname; rename cannot replace a directory
        # created by another process while the download was running.
        dest.mkdir(mode=0o700)
        for child in scratch.iterdir():
            os.rename(child, dest / child.name)
        print(f'Checked out {project}: {len(files)} files in {dest}.')
    finally:
        shutil.rmtree(scratch)


def _preflight(client, project, files, base=None):
    remote = client.files(project, missing_ok=base is None)
    changes, converged = [], {}
    for path, data in sorted(files.items()):
        current = remote.get(path)
        previous = (base or {}).get(path)
        checksum = digest(data)
        if current and current['sha256'] == checksum:
            # Verify existing bytes too: a retry trusts neither a stale cached
            # metadata file nor an acknowledgement whose body was lost.
            verified, stored = client.read(project, path, current['revision'])
            if stored != data:
                raise ProjectError('Existing document read-back failed verification.')
            converged[path] = metadata(verified, project, path)
            continue
        if previous is not None and checksum == previous['sha256']:
            # Untouched local files never overwrite a colleague's newer work.
            continue
        expected = previous['revision'] if previous else 0
        if (current['revision'] if current else 0) != expected:
            raise ProjectError(f'Conflict in {project}/{path}. Keep your edits and reconcile with a new checkout.')
        changes.append((path, data, expected))
    return changes, converged


def save(client, directory, commit=False):
    root = safe_ancestors(directory)
    state = load_state(root)
    client.space_id = state['space_id']
    files, excluded = scan(root, working=True)
    _excluded(excluded)
    deleted = sorted(set(state['files']) - set(files))
    for path in deleted:
        print(f'Local deletion is not propagated: {path}')
    changes, converged = _preflight(client, state['project'], files, state['files'])
    for path, data, expected in changes:
        print(f'{"Update" if expected else "Create"}: {path} ({len(data)} bytes)')
    if not commit:
        print(f'Preview: {len(changes)} changes. Run cs project save {directory!s} --commit to save.')
        return
    # A previous response may have been lost. Persist every read-back-verified
    # convergence before new writes, so subsequent retries start accurately.
    state['files'].update(converged)
    write_state(root, state)
    completed = 0
    try:
        for path, data, expected in changes:
            # Recheck local bytes after preview, before persisting remote state.
            if read_bytes(root / path) != data:
                raise ProjectError('Local files changed during save. Retry without discarding your edits.')
            stored = client.write(state['project'], path, data, expected)
            state['files'][path] = stored
            write_state(root, state)
            completed += 1
    except Exception:
        print(f'Save incomplete: {completed} of {len(changes)} changes verified. Local edits remain; retry is safe.')
        raise
    print(f'Saved {completed} changes to {state["project"]}.')


def import_projects(client, directory, name=None, all_projects=False, commit=False):
    root = safe_ancestors(directory)
    if not root.is_dir():
        raise ProjectError('Import source must be a directory.')
    selections = []
    if all_projects:
        for item in sorted(root.iterdir()):
            if item.is_symlink():
                raise ProjectError('Import source contains a symlink.')
            if item.name == '.env' or item.name.startswith('.env.'):
                raise ProjectError('Import source contains a sensitive .env path.')
            if item.name in ('.git', '__pycache__', '.DS_Store') or item.name.endswith('.pyc'):
                _excluded([item.name])
            elif item.is_dir():
                selections.append((slug(item.name), item))
            elif item.name in ('README.md', '_meeting-template.md', '_dossier-template.md'):
                print(f'Legacy convention, not a project: {item.name}')
            else:
                raise ProjectError('Unexpected top-level file: import it within a named project directory.')
    else:
        selections.append((slug(name or root.name), root))
    # Every selected tree is scanned BEFORE any RPC mutation. No attachments are
    # silently omitted because of extension, encoding, traversal or file type.
    scanned, total_size = [], 0
    for project, source in selections:
        files, excluded = scan(source)
        _excluded([f'{project}/{path}' for path in excluded])
        if not files:
            raise ProjectError('An empty directory cannot be imported as a project.')
        total_size += sum(map(len, files.values()))
        if total_size > MAX_TREE:
            raise ProjectError('Import exceeds 128 MiB. Import project directories separately.')
        scanned.append((project, files))
    operations, identical = [], 0
    for project, files in scanned:
        changes, converged = _preflight(client, project, files)
        identical += len(converged)
        for path, data, expected in changes:
            print(f'Import: {project}/{path} ({len(data)} bytes, sha256 {digest(data)})')
            operations.append((project, path, data, expected))
    if not commit:
        print(f'Preview: {len(operations)} new files, {identical} already identical. Add --commit to import.')
        return
    completed = 0
    try:
        for project, path, data, expected in operations:
            client.write(project, path, data, expected)
            completed += 1
    except Exception:
        print(f'Import incomplete: {completed} of {len(operations)} new files verified. Sources preserved; retry is safe.')
        raise
    print(f'Imported {completed} files; {identical} already identical. Source directories preserved.')
