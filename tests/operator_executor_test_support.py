"""Private, non-overwriting evidence exports for free executor controls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

# Capture before a fixture deliberately clears its subprocess environment.
EVIDENCE_ROOT = Path(os.environ.get('CS_EXECUTOR_TEST_EVIDENCE_ROOT')
                     or tempfile.mkdtemp(prefix='cs-executor-evidence-')).resolve()
EVIDENCE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)


def evidence_path(group: str, name: str) -> Path:
    """Allocate a new private directory, including for repeated same-case runs."""
    path = Path(tempfile.mkdtemp(prefix=group + '-', dir=EVIDENCE_ROOT)) / name
    record = json.dumps({'group': group, 'path': str(path)}) + '\n'
    descriptor = os.open(EVIDENCE_ROOT / 'artifact-index.jsonl',
                         os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(descriptor, record.encode())
    finally:
        os.close(descriptor)
    return path
