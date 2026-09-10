#!/usr/bin/env python3
"""Real template rendering and CLI parser validation without engine credentials."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cs import project_memory
from cs.project_documents import Documents
from test_project_working import FakeEngine


TZ = "Europe/Madrid"

MANIFEST = f"""\
[company]
name = "Acme"
display_name = "Acme Group"
from_name = "Acme Ops"
slug = "acme"
prog_name = "acme-cs"

[operator]
email_address = "ops@acme.example"

[engine]
owner_uid = "uid-ops-acme"
ws_url = "wss://engine.example"

[engine.accounts]
default = "ops"
ops = "uid-ops-acme"

[crm]
adapter = "none"

[producer]
adapter = "none"

[knobs]
timezone = "{TZ}"

[repo]
kernel_version = "v0.1.0"
"""


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN")}
    env["HOME"] = str(home)
    return env


def _run(repo: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "cs", *args], cwd=repo, env=env,
                          capture_output=True, text=True)



def main():
    settings = SimpleNamespace(timezone='Europe/Madrid', email_address='ops@acme.example',
                               founder_sweep_account='')
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        original = Path.cwd()
        os.chdir(root)
        try:
            engine = FakeEngine()
            client = Documents(settings, engine)
            args = SimpleNamespace(name='acme-corp', title='Acme Corp S.p.A.')
            project_memory._new(client, settings, args)
            assert not (root / 'docs').exists(), 'new project must live in engine, not docs/'
            expected = {'README.md', 'status.md', 'timeline.md', 'meetings/.gitkeep'}
            assert expected <= set(engine.records['acme-corp'])
            for path in ('README.md', 'status.md', 'timeline.md'):
                _, data = client.read('acme-corp', path)
                text = data.decode()
                assert text.startswith('---\n') and '## Abstract' in text
                assert 'project: acme-corp' in text
                assert '{{' not in text and '{%' not in text
            _, data = client.read('acme-corp', 'README.md')
            text = data.decode()
            assert 'Acme Corp S.p.A.' in text and 'S.p.A..' not in text
            assert 'ops@acme.example' in text
            today = datetime.now(timezone.utc).astimezone(ZoneInfo(settings.timezone)).strftime('%Y-%m-%d')
            assert f'created: {today}' in text
            settings.founder_sweep_account = 'founder@acme.example'
            args.name = 'second-project'
            project_memory._new(client, settings, args)
            assert 'founder@acme.example' in client.read(args.name, 'README.md')[1].decode()
            before = repr(engine.records)
            try:
                project_memory._new(client, settings, args)
                raise AssertionError('duplicate creation accepted')
            except ValueError:
                pass
            assert repr(engine.records) == before
            args.paction = 'new'
            assert project_memory.cmd_project(args) == 1
            assert not (root / 'docs').exists()
        finally:
            os.chdir(original)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')
    project_memory.add_subparsers(sub)
    for command in ('list', 'files acme-corp', 'show acme-corp', 'history acme-corp status.md',
                    'checkout acme-corp work', 'save work', 'import legacy --all', 'new acme-corp'):
        args = parser.parse_args(('project ' + command).split())
        assert args.func is project_memory.cmd_project
        if args.paction in ('save', 'import'):
            assert args.commit is False
    # Preserve the unrelated historical account-boundary regression checks.
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, 'home'); home.mkdir()
        repo = Path(td, 'repo'); repo.mkdir()
        (repo / 'manifest.toml').write_text(MANIFEST)
        env = _clean_env(home)
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
        env['CS_ACCOUNTS'] = 'ops:uid-ops-acme,other:uid-other-acme'
        for verb, extra in (('contacted', ['x@acme.example']), ('unanswered', []),
                            ('dossier', ['x@acme.example']), ('draft-reply', ['say hello'])):
            result = _run(repo, env, '--account', 'other', verb, *extra)
            assert result.returncode == 2, result.stderr
            assert 'engine profile' in result.stderr + result.stdout
    print('test_project_memory: engine scaffold, rendered bytes and parser assertions passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
