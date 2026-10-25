"""Canonical diagnostic workflow distribution and a real private incident fixture."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import runpy
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cs import project_init, project_update
from cs.monitor import scan
from cs.monitor_store import MonitorStore
from cs.operational_inbox import publish
from cs.monitor_config import Component, MonitorConfig
from cs.observability import EventStore

SKILL = Path('.claude/skills/cs-diagnose/SKILL.md')
POLICY = SKILL.parent / 'agents/openai.yaml'
HELPER = SKILL.parent / 'record_findings.py'
FILES = (SKILL, POLICY, HELPER)
TEMPLATES = ROOT / 'cs/templates/project'


@contextlib.contextmanager
def at(directory):
    previous = Path.cwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(previous)


def prepare_fixture(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    env = project_init.build_jinja_env(TEMPLATES)
    for rel in FILES:
        target = directory / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(env.get_template(str(rel) + '.j2').render())
    with patch.object(project_init, 'LEGACY_CODEX_PROMPTS', directory / 'unused-prompts'):
        with contextlib.redirect_stdout(io.StringIO()):
            project_init.install_agent_surfaces(directory)
    source = EventStore(directory / 'source', 'fixture-owner')
    event = source.emit('provider', 'unknown-effect', reason='timeout', method='drafts.send')
    config = MonitorConfig(mode='filesystem', clone_label='fixture-cs', scan_seconds=600,
        monitor_id='b' * 32, owner_uid='fixture-owner', state_dir=str(directory / 'monitor'),
        expected_start_utc=int(time.time()),
        components=[Component(id='operator', kind='kernel', local_root=str(source.root))])
    config_path = directory / 'monitor-config.json'
    config_path.write_text(config.model_dump_json())
    config_path.chmod(0o600)
    scan(config)
    inbox = Path(config.state_dir) / 'problems.json'
    content = json.loads(inbox.read_text())
    incident = next(p for p in content['problems'] if p['evidence'].get('event_id') == event['event_id'])
    result = {'root': str(directory), 'skill': str(directory / SKILL),
        'config': str(config_path), 'inbox': str(inbox), 'incident': incident['id'],
        'event_id': event['event_id'], 'findings': incident['investigation_path'],
        'helper': str(directory / HELPER),
        'expected': 'Observe provider timeout with unknown effect; retain uncertainty and next diagnostic step without a send or replay.'}
    (directory / 'fixture.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


class DiagnoseSkillTests(unittest.TestCase):
    def test_init_update_and_copy_fallback_expose_same_canonical_files(self):
        from test_project_update import _FULL_INIT_DATA
        data = {**project_init.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for copies in (False, True):
                clone = root / ('copy' if copies else 'links')
                clone.mkdir()
                with contextlib.redirect_stdout(io.StringIO()):
                    ok, checksums = project_init.render_templates(data, TEMPLATES, clone)
                self.assertTrue(ok)
                for rel in FILES:
                    self.assertIn(str(rel), checksums)
                manifest = {'init_data': data, 'file_checksums': checksums}
                (clone / 'template-manifest.json').write_text(json.dumps(manifest))
                canonical = {rel: (clone / rel).read_bytes() for rel in FILES}
                for rel in FILES:
                    (clone / rel).unlink()
                with patch.object(project_init, 'LEGACY_CODEX_PROMPTS', root / 'unused-prompts'), \
                     patch.object(project_update, '_offer_release_upgrade', return_value=None), \
                     contextlib.redirect_stdout(io.StringIO()), at(clone):
                    if copies:
                        with patch.object(Path, 'symlink_to', side_effect=OSError('unsupported')):
                            result = project_update.cmd_update([])
                    else:
                        result = project_update.cmd_update([])
                self.assertEqual(result, 0)
                ledger = json.loads((clone / 'template-manifest.json').read_text())['file_checksums']
                for rel, expected in canonical.items():
                    self.assertEqual(ledger[str(rel)], 'sha256:' + hashlib.sha256(expected).hexdigest())
                    for host in ('.claude', '.agents', '.opencode'):
                        target = clone / host / 'skills/cs-diagnose' / rel.relative_to(SKILL.parent)
                        self.assertEqual(target.read_bytes(), expected)
                self.assertEqual((clone / '.agents/skills').is_symlink(), not copies)
                self.assertEqual((clone / '.opencode/skills').is_symlink(), not copies)
                self.assertEqual((clone / POLICY).read_text(), 'policy:\n  allow_implicit_invocation: false\n')

    def test_helper_writes_private_exact_utc_headers_and_preserves_prior_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare_fixture(Path(temporary) / 'fixture')
            inbox = Path(result['inbox'])
            content = json.loads(inbox.read_text())
            problem = next(p for p in content['problems'] if p['id'] == result['incident'])
            problem['first_observed'] = 1792713600
            problem['last_observed'] = 1792713660
            content['generated_at'] = 1792713720
            inbox.write_text(json.dumps(content))
            before = inbox.read_bytes()
            analysis = Path(temporary) / 'analysis.json'
            analysis.write_text(json.dumps({'analysis': 'Observed timeout; provider effect remains unknown. Root cause is unverified.',
                                            'next_action': 'Inspect matching provider request evidence without retrying.'}))
            command = [sys.executable, result['helper'], '--inbox', str(inbox),
                       '--incident', result['incident'], '--analysis-file', str(analysis)]
            with patch.dict(os.environ, {}, clear=False):
                previous = os.umask(0o002)
                try:
                    first = subprocess.run(command, capture_output=True, text=True, timeout=10)
                finally:
                    os.umask(previous)
            self.assertEqual(first.returncode, 0, first.stderr)
            target = Path(result['findings'])
            retained = target.read_bytes()
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertIn('First observed UTC: 2026-10-23T00:00:00Z', retained.decode())
            self.assertIn('Last observed UTC: 2026-10-23T00:01:00Z', retained.decode())
            self.assertIn(result['event_id'], retained.decode())
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue(target.read_bytes().startswith(retained))
            self.assertEqual(inbox.read_bytes(), before)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_helper_refuses_foreign_destinations_symlinks_and_foreign_ownership(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare_fixture(Path(temporary) / 'fixture')
            inbox = Path(result['inbox'])
            content = json.loads(inbox.read_text())
            analysis = Path(temporary) / 'analysis.json'
            analysis.write_text(json.dumps({'analysis': 'Timeout; effect unknown.', 'next_action': 'Inspect evidence.'}))
            command = [sys.executable, result['helper'], '--inbox', str(inbox),
                       '--incident', result['incident'], '--analysis-file', str(analysis)]
            original = inbox.read_bytes()
            content['problems'][0]['investigation_path'] = str(Path(temporary) / 'foreign.md')
            inbox.write_text(json.dumps(content))
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=10).returncode, 2)
            self.assertFalse((Path(temporary) / 'foreign.md').exists())
            inbox.write_bytes(original)
            target = Path(result['findings'])
            outside = Path(temporary) / 'outside.md'
            outside.write_text('Preserve original.\n')
            target.symlink_to(outside)
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=10).returncode, 2)
            self.assertEqual(outside.read_text(), 'Preserve original.\n')
            target.unlink()
            module = runpy.run_path(result['helper'], run_name='diagnostic_helper_test')
            with patch.object(os, 'geteuid', return_value=os.geteuid() + 1):
                with self.assertRaises(ValueError):
                    module['record'](inbox, result['incident'], analysis)
            self.assertFalse(target.exists())

    def test_helper_records_omitted_exact_incident_read_only_and_refuses_foreign_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare_fixture(Path(temporary) / 'fixture')
            inbox = Path(result['inbox'])
            store = MonitorStore(inbox.parent, 'fixture-owner')
            omitted = None
            with store.connect() as db:
                for index in range(205):
                    identity = hashlib.sha256(('omitted-' + str(index)).encode()).hexdigest()
                    detail = json.dumps({'event_id': f'{index:032x}', 'stage': 'provider',
                                         'reason': 'timeout', 'level': 'ERROR', 'at': 1792713600 + index,
                                         'effect_certainty': 'unknown'})
                    db.execute('INSERT INTO incidents(id,component,cause,first,last,active,revision,detail) '
                               'VALUES (?, ?, ?, ?, ?, 1, 1, ?)',
                               (identity, 'operator', 'operation-failure', 1792713600 + index,
                                1792713600 + index, detail))
                    omitted = identity
            publish(store, clone_label='fixture-cs', now=1792713900)
            content = json.loads(inbox.read_text())
            self.assertEqual(content['problem_count'], 206)
            self.assertEqual(content['remaining_count'], 6)
            self.assertNotIn(omitted, {row['id'] for row in content['problems']})
            original_inbox = inbox.read_bytes()
            original_database = store.path.read_bytes()
            analysis = Path(temporary) / 'analysis.json'
            analysis.write_text(json.dumps({'analysis': 'Observed timeout; effect remains unknown.',
                                            'next_action': 'Read matching provider evidence without retrying.'}))
            command = [sys.executable, result['helper'], '--inbox', str(inbox),
                       '--incident', omitted, '--analysis-file', str(analysis)]
            saved = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            findings = inbox.parent / 'investigations' / (omitted + '.md')
            retained = findings.read_bytes()
            self.assertIn('First observed UTC: 2026-10-23T00:03:24Z', retained.decode())
            self.assertIn(omitted, retained.decode())
            self.assertEqual(findings.stat().st_mode & 0o777, 0o600)
            self.assertEqual(inbox.read_bytes(), original_inbox)
            self.assertEqual(store.path.read_bytes(), original_database)
            with store.connect() as db:
                db.execute('UPDATE identity SET owner=?', ('foreign-owner',))
            foreign_database = store.path.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=10).returncode, 2)
            self.assertEqual(store.path.read_bytes(), foreign_database)
            self.assertEqual(findings.read_bytes(), retained)
            original_path = store.path.with_name('retained.sqlite3')
            store.path.rename(original_path)
            store.path.symlink_to(original_path)
            self.assertEqual(subprocess.run(command, capture_output=True, timeout=10).returncode, 2)
            self.assertEqual(findings.read_bytes(), retained)
            self.assertEqual(inbox.read_bytes(), original_inbox)

    def test_native_fixture_retains_real_unknown_effect_and_private_findings_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare_fixture(Path(temporary) / 'fixture')
            inbox = Path(result['inbox'])
            content = json.loads(inbox.read_text())
            incident = next(p for p in content['problems'] if p['id'] == result['incident'])
            self.assertEqual(incident['evidence']['effect_certainty'], 'unknown')
            self.assertTrue(incident['evidence']['uncertain'])
            self.assertEqual(incident['reason'], 'timeout')
            self.assertEqual(incident['clone'], 'fixture-cs')
            self.assertEqual(inbox.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Path(result['findings']).parent.stat().st_mode & 0o777, 0o700)
            self.assertFalse(Path(result['findings']).exists())
            canonical = Path(result['skill']).read_bytes()
            for host in ('.agents', '.opencode'):
                self.assertEqual((Path(result['root']) / host / 'skills/cs-diagnose/SKILL.md').read_bytes(), canonical)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--prepare-fixture':
        print(json.dumps(prepare_fixture(Path(sys.argv[2]).absolute())))
    else:
        unittest.main(verbosity=2)
