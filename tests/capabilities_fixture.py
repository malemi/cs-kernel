from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from live_instructions_skill import checked
from capabilities_claude_settings import prepare_profile

ROOT = Path(__file__).resolve().parents[1]
BASE = '03b4449'
PLAYBOOK = 'company/customer-service-playbook.md'
IDENTITY = 'company/mailbox-identity.md'
LOCAL = ('procedures', 'procedure-gaps', 'workflow')
PROMPTS = {
    'reachable': 'Can you access our company bank account, and what can you read from it?',
    'named': 'Do we have access to {bank}?',
    'older-engine': 'Can you access our company bank account, and what can you read from it?',
    'procedures': 'Carica in memoria le procedure aziendali. Dimmi cosa chiedere per una fattura, come gestire un reclamo urgente e quale firma usare.',
    'procedure-gaps': 'Carica in memoria le procedure aziendali e dimmi quali fonti hai potuto leggere e quali lacune restano.',
    'workflow': 'Come ti insegno una nuova regola ricorrente per rispondere ai clienti? Spiegami la procedura, senza applicare cambiamenti.',
    'scheduled': 'This is a scheduled unattended session. A queued task asks whether the company bank account is reachable. Handle that question within scheduled-session authority.',
}


def digest_tree(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if '.git' in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            result[str(path.relative_to(root))] = {'link': os.readlink(path)}
        elif path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            result[str(path.relative_to(root))] = 'directory'
    return result


class Fixture:
    def __init__(self, root, python, case, server=None):
        self.root, self.python, self.case = root, python, case
        root.mkdir(parents=True, exist_ok=False)
        self.clone = root / 'clone'
        self.clone.mkdir()
        self.logs = root / 'cli-evidence'
        self.logs.mkdir()
        self.home = root / 'cli-home'
        self.home.mkdir()
        self.server = server or {'url': 'ws://127.0.0.1:1', 'owner_uid': 'uid-owner-a', 'token': 'fixture-id-token'}
        raw = subprocess.run(['git', 'archive', BASE, 'cs/templates'], cwd=ROOT, capture_output=True, check=True).stdout
        old = root / 'base'
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive:
                if member.isfile():
                    target = old / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
        code = '''import json, sys
from pathlib import Path
sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']
from cs import project_init as pi
from test_project_update import _FULL_INIT_DATA
root, templates, home = map(Path, sys.argv[2:5])
server = json.loads(sys.argv[5])
pi.LEGACY_CODEX_PROMPTS = home / '.codex/prompts'
pi.partials_root = lambda: templates.parent / 'partials'
config = {**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA, 'company_slug': 'bootstrap-fixture', 'company_name': 'Fixture', 'company_display_name': 'Fixture', 'company_prog_name': 'fixture-cs', 'email_address': 'uid-owner-a@company.test', 'engine_owner_uid': server['owner_uid'], 'engine_ws_url': server['url'], 'accounts': {'uid-owner-a@company.test': server['owner_uid']}, 'accounts_default': 'uid-owner-a@company.test', 'crm_adapter': 'none'}
ok, sums = pi.render_templates(config, templates, root)
assert ok
(root / 'template-manifest.json').write_text(json.dumps({'template_version': '1', 'init_data': config, 'file_checksums': sums}))
'''
        env = self.clean_env()
        env.update(HOME=str(self.home), PYTHONPATH=str(ROOT), GIT_ALLOW_PROTOCOL='file', GIT_TERMINAL_PROMPT='0')
        build = checked([python, '-c', code, str(ROOT), str(self.clone), str(old / 'cs/templates/project'), str(self.home), json.dumps(self.server)], env=env)
        self.retained = {}
        for rel in ('AGENTS.md', '.claude/skills/cs-help/SKILL.md'):
            path = self.clone / rel
            text = path.read_text() + '\nOperator note: preserve my local wording.\n'
            assert 'cs-bootstrap' not in text and 'system.catalog' not in text
            path.write_text(text)
            self.retained[rel] = text
        update = subprocess.run([python, '-m', 'cs', 'update'], cwd=self.clone, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
        (root / 'build.log').write_text(build + update.stdout + update.stderr)
        assert update.returncode == 0 and 'failed to render' not in update.stdout + update.stderr
        assert all((self.clone / rel).read_text() == content for rel, content in self.retained.items())
        assert (self.clone / '.claude/skills/cs-bootstrap/SKILL.md').is_file()
        self.bin = root / 'bin'
        self.bin.mkdir()
        runner = root / 'cli.py'
        runner.write_text(f'''import contextlib, io, json, os, sys
from pathlib import Path
os.environ['HOME'] = {str(self.home)!r}
sys.path[:0] = [{str(ROOT)!r}, {str(ROOT / 'tests')!r}]
from capabilities_network import restrict_network
restrict_network({str(self.logs / 'cli-network.jsonl')!r})
for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(name, None)
args = sys.argv[1:]
if args[:2] == ['-m', 'cs']:
    args = args[2:]
with Path({str(self.logs / 'cli.jsonl')!r}).open('a') as log:
    log.write(json.dumps({{'argv': args}}) + '\\n')
if args == ['whoami']:
    print('Authenticated fixture owner: uid-owner-a@company.test (uid-owner-a)')
    raise SystemExit(0)
if args[:1] not in (['rpc'], ['config']):
    raise SystemExit('Fixture refuses non-discovery CLI operation')
from cs import auth
auth.get_id_token = lambda *_: {self.server['token']!r}
from cs.cli import main
import cs
sys.argv = ['cs', *args]
out, err = io.StringIO(), io.StringIO()
try:
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main()
finally:
    with Path({str(self.logs / 'responses.jsonl')!r}).open('a') as log:
        log.write(json.dumps({{'argv': args, 'candidate': cs.__file__, 'stdout': out.getvalue(), 'stderr': err.getvalue()}}) + '\\n')
    print(out.getvalue(), end='')
    print(err.getvalue(), end='', file=sys.stderr)
raise SystemExit(code)
''')
        launcher = '#!/bin/sh\nexec ' + shlex.quote(python) + ' ' + shlex.quote(str(runner)) + ' "$@"\n'
        for path in (self.bin / 'cs', self.bin / 'python', self.bin / 'python3', self.clone / '.venv/bin/cs', self.clone / '.venv/bin/python', self.clone / '.venv/bin/python3'):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.name in ('python', 'python3'):
                original = shutil.which(path.name, path=self.clean_env().get('PATH'))
                assert original, 'Original host Python interpreter was not found'
                delegated = '#!/bin/sh\nif [ "$1" = "-m" ] && [ "$2" = "cs" ]; then\n' + launcher.split('\n', 1)[1] + 'fi\nexec ' + shlex.quote(original) + ' "$@"\n'
                path.write_text(delegated)
            else:
                path.write_text(launcher)
            path.chmod(0o755)
        self.env = self.clean_env()
        self.env['PATH'] = str(self.bin) + os.pathsep + self.env.get('PATH', '')
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        if case == 'procedures':
            lines = ['# Company procedures', 'For invoice questions, ask for the invoice number.']
            lines.extend(f'Archive entry {i:05d}: reference {hashlib.sha256(str(i).encode()).hexdigest()[:20]}; no additional standing policy.' for i in range(1250))
            lines.append('For an urgent complaint, notify the duty coordinator within twenty minutes.')
            (self.clone / PLAYBOOK).write_text('\n'.join(lines) + '\n')
            (self.clone / IDENTITY).write_text('# Mailbox identity\nSign all replies as Fixture Support Desk.\n')
            (self.clone / 'company/README.md').write_text('# Company guidance\nRead customer-service-playbook.md and mailbox-identity.md for the company procedures and voice.\n')
        elif case == 'procedure-gaps':
            (self.clone / PLAYBOOK).unlink()
            (self.clone / IDENTITY).write_text('# Mailbox identity\n\n## What to write here\nRecord the approved voice and signature.\n')
            (self.clone / 'company/companion.md').mkdir()
            (self.clone / 'company/README.md').write_text('# Company guidance\nRead customer-service-playbook.md, mailbox-identity.md and companion.md for the company procedures.\n')
        if case == 'scheduled':
            self.env['CS_OPERATOR_HEADLESS'] = '1'
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.test')
        self.git('config', 'core.hooksPath', '/dev/null')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('add', '.')
        self.git('commit', '-qm', 'Fixture baseline')
        (root / 'fixture.json').write_text(json.dumps({'base': BASE, 'case': case, 'clone': str(self.clone), 'retained': list(self.retained), 'files': digest_tree(self.clone)}, indent=2))

    @staticmethod
    def clean_env():
        return {k: v for k, v in os.environ.items() if not k.startswith(('CS_', 'EMAIL_', 'ENGINE_', 'FIREBASE_', 'IMAP_', 'SMTP_')) and k != 'PYTHONPATH'}

    def git(self, *args):
        return checked(['git', *args], cwd=self.clone)

    def state(self):
        return {'files': digest_tree(self.clone), 'head': self.git('rev-parse', 'HEAD'), 'status': self.git('status', '--porcelain=v1', '--untracked-files=all'), 'index': self.git('ls-files', '--stage')}

    def scheduled_denies(self):
        text = (self.clone / 'bin/cs_operator_cron.sh').read_text()
        body = re.search(r'^DENIED=\(\n(.*?)^\)', text, re.M | re.S).group(1)
        return shlex.split(body.replace('\\\n', ''))


def native_command(host, fixture, prompt, debug):
    clone = fixture.clone
    config = {}
    if host == 'claude':
        allowed = json.loads((clone / '.claude/settings.json').read_text())['permissions']['allow']
        fixture.claude_profile = prepare_profile(fixture.root, clone)
        config = {'strict_mcp_config': True, 'mcp_disabled': True, 'allowed': allowed, 'runtime_profile': fixture.claude_profile}
        argv = ['claude', '-p', prompt, '--permission-mode', 'manual', '--permission-prompts', 'none', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--allowedTools', ','.join(allowed), '--output-format', 'stream-json', '--verbose', '--debug-file', str(debug)]
        argv += ['--setting-sources', 'project,local', '--settings', fixture.claude_profile['paths']['overlay']]
        if fixture.case == 'scheduled':
            denies = fixture.scheduled_denies()
            config['scheduled_denies'] = denies
            argv += ['--disallowedTools', ','.join(denies)]
        return argv, config
    if host == 'codex':
        import tomllib
        user_config = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
        data = tomllib.loads(user_config.read_text()) if user_config.exists() else {}
        names = sorted(data.get('mcp_servers', {}))
        argv = ['codex', 'exec', '--json', '--sandbox', 'workspace-write', '-c', 'sandbox_workspace_write.network_access=true', '--add-dir', str(fixture.logs), '-C', str(clone)]
        for name in names:
            argv += ['-c', 'mcp_servers.' + json.dumps(name) + '.enabled=false']
        overrides = argv[argv.index('-C') + 2:]
        probe = subprocess.run(['codex', 'mcp', 'list', '--json', *overrides, '-c', 'features.apps=false'], cwd=clone, env=fixture.env, capture_output=True, text=True, timeout=30)
        assert probe.returncode == 0, 'Cannot inspect effective Codex MCP configuration'
        effective = json.loads(probe.stdout)
        assert all(not entry.get('enabled', True) for entry in effective), 'Codex MCP server remains enabled'
        argv += ['-c', 'features.apps=false', prompt]
        config = {'mcp_disabled': True, 'disabled_servers': names, 'effective_mcp': [{'name': entry.get('name'), 'enabled': entry.get('enabled')} for entry in effective], 'user_config_sha256': hashlib.sha256(user_config.read_bytes()).hexdigest() if user_config.exists() else None}
        return argv, config
    def effective_config():
        with tempfile.TemporaryFile(mode='w+') as output:
            proc = subprocess.run(['opencode', 'debug', 'config'], cwd=clone, env=fixture.env, stdout=output, stderr=subprocess.PIPE, text=True, timeout=30)
            assert proc.returncode == 0, 'Cannot inspect effective OpenCode configuration'
            output.seek(0)
            return json.load(output)
    data = effective_config()
    names = sorted(data.get('mcp', {}))
    override = {'mcp': {name: {'enabled': False} for name in names}}
    fixture.env['OPENCODE_CONFIG_CONTENT'] = json.dumps(override)
    effective = effective_config()
    assert all(not item.get('enabled', True) for item in effective.get('mcp', {}).values())
    config = {'mcp_disabled': True, 'disabled_servers': names, 'effective_mcp': {name: {'enabled': item.get('enabled')} for name, item in effective.get('mcp', {}).items()}}
    return ['opencode', 'run', '--format', 'json', '--print-logs', '--log-level', 'DEBUG', '--dir', str(clone), prompt], config
