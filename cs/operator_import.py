from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from . import instructions, manifest

COMPILER = "cs.instructions.compile_documents/v1"


def compiler_sha256():
    return hashlib.sha256(Path(instructions.__file__).read_bytes()).hexdigest()


def _sources(root):
    if (root / "company").is_symlink():
        raise ValueError("Compiler source directory must not be a symlink")
    paths = ["manifest.toml", instructions.PLAYBOOK_FILE, instructions.IDENTITY_FILE]
    directory = root / instructions.MAILBOXES_DIR
    if directory.exists():
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("Invalid compiler source directory")
        paths.extend(str(path.relative_to(root)) for path in sorted(directory.glob("*.md")))
    out = {}
    for relative in paths:
        path = root / relative
        if path.is_symlink():
            raise ValueError("Compiler sources must not be symlinks")
        if path.exists():
            if not path.is_file() or path.stat().st_size > 65536:
                raise ValueError("Compiler source exceeds limit")
            out[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if "manifest.toml" not in out or len(out) > 100:
        raise ValueError("Compiler source inventory is incomplete")
    return out


def build_proof(clone_root, *, profile_uid, space_id, mailbox, published_documents):
    root = Path(clone_root).resolve(strict=True)
    before = _sources(root)
    declared = manifest.load_manifest(root / "manifest.toml")
    settings = SimpleNamespace(email_address=manifest.settings_overrides(declared).get("email_address", ""))
    if settings.email_address.strip().lower() != mailbox:
        raise ValueError("Clone mailbox does not match selected owner")
    compiled = instructions.compile_documents(root, settings)
    if not compiled or len(compiled) > 32 or _sources(root) != before:
        raise ValueError("Compiler inputs changed or complete snapshot is unavailable")
    published = {row["path"]: row for row in published_documents}
    if len(published) != len(published_documents) or set(published) != set(compiled):
        raise ValueError("Complete published and compiler path sets differ")
    documents = []
    for path, raw in sorted(compiled.items()):
        raw.decode("utf-8", errors="strict")
        if not 0 < len(raw) <= 65536:
            raise ValueError("Compiled document exceeds limit")
        row = published[path]
        sha = hashlib.sha256(raw).hexdigest()
        if (row["space_id"] != space_id or row["project"] != "operator-instructions"
                or type(row["revision"]) is not int or row["revision"] < 1
                or row["sha256"] != sha
                or base64.b64decode(row["content_base64"], validate=True) != raw):
            raise ValueError("Unpublished clone changes or conflicting published document")
        documents.append(dict(path=path, content_base64=base64.b64encode(raw).decode("ascii"),
            sha256=sha, base_revision=row["revision"], base_sha256=sha))
    now = time.time()
    return dict(version=2, profile_uid=profile_uid, space_id=space_id, mailbox=mailbox,
        created_at=now, expires_at=now+900, source_files=before, documents=documents,
        compiler=COMPILER, compiler_sha256=compiler_sha256(), compiled_paths=sorted(compiled))


def write_proof(destination, proof, *, tenant_gid):
    if os.geteuid() != 0:
        raise PermissionError("Protected compiler proof requires root")
    raw = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > 3 * 1024 * 1024:
        raise ValueError("Protected compiler proof exceeds limit")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, 0, tenant_gid)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fchmod(fd, 0o640)
    finally:
        os.close(fd)
