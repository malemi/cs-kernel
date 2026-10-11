from __future__ import annotations

import ast
import copy
import json
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from capabilities_codex_config import capture_user_config, compare_config
from capabilities_shell import shell_parts, command_targets

from capabilities_engine import validate_catalog_journey
from capabilities_codex_session import capture_command_context
from live_capabilities_skill import check_case
from capabilities_events import (audit_tools, final_text, loaded, read_coverage, require_host_success,
    require_debug_file, require_no_mcp, require_safe_requests, require_private_channels, require_scheduled, require_unchanged, secret_audit_text, source_snapshot, validate_cli_args)


class CodexConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clone = self.root / 'clone'
        self.clone.mkdir()
        self.source = self.root / 'config.toml'
        self.index = 0

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self, body):
        self.source.write_text(body)
        self.index += 1
        return capture_user_config(self.root / 'private' / f'{self.index}.toml', self.source)

    def addition(self, path=None, fields='trust_level = "trusted"'):
        return '\n[projects.' + json.dumps(str(path or self.clone)) + ']\n' + fields + '\n'

    def test_owned_addition_unchanged_and_public_receipts(self):
        before = self.snapshot('model = "synthetic-private"\n')
        after = self.snapshot('model = "synthetic-private"\n' + self.addition())
        receipt = compare_config(before, after, [self.clone])
        self.assertEqual(receipt['added_owned_projects'], [str(self.clone.resolve())])
        self.assertEqual(compare_config(after, after, [self.clone])['added_owned_projects'], [])
        self.assertEqual(set(before), {'source_path', 'private_path', 'raw_sha256', 'semantic_sha256'})
        self.assertNotIn('synthetic-private', json.dumps([before, after, receipt]))
        self.assertEqual(Path(before['private_path']).stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(before['private_path']).parent.stat().st_mode & 0o777, 0o700)
        empty = self.snapshot('[projects]\n')
        self.assertEqual(compare_config(empty, self.snapshot(self.addition()), [self.clone])['added_owned_projects'], [str(self.clone)])

    def test_semantics_ignore_comments_order_and_preserve_types(self):
        before = self.snapshot('model = "same"\nvalue = 1\n')
        after = self.snapshot('# comment\nvalue = 1\nmodel = "same"\n')
        self.assertNotEqual(before['raw_sha256'], after['raw_sha256'])
        self.assertEqual(before['semantic_sha256'], after['semantic_sha256'])
        compare_config(before, after, [])
        for value in ('true', '1.0', '"1"'):
            with self.subTest(value=value), self.assertRaisesRegex(AssertionError, 'nonproject'):
                compare_config(before, self.snapshot('model = "same"\nvalue = ' + value), [])
        typed = self.snapshot('nested = [true, {value = 1}]')
        with self.assertRaisesRegex(AssertionError, 'nonproject'):
            compare_config(typed, self.snapshot('nested = [1, {value = true}]'), [])

    def test_rejects_all_nonproject_changes_additions_and_removals(self):
        for key in ('model', 'auth', 'hooks', 'permissions', 'mcp_servers', 'model_provider'):
            with self.subTest(key=key):
                before = self.snapshot(key + ' = "private-old"\n')
                for body in (key + ' = "private-new"\n', '', key + ' = "private-old"\nextra = true\n'):
                    with self.assertRaisesRegex(AssertionError, 'nonproject'):
                        compare_config(before, self.snapshot(body), [self.clone])

    def test_prior_projects_changes_removals_and_types_fail(self):
        body = '[projects."/prior"]\ntrust_level = "untrusted"\nvalue = 1\n'
        before = self.snapshot(body)
        for changed in ('', body.replace('untrusted', 'trusted'), body.replace('1', 'true'), '[projects]\n'):
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                compare_config(before, self.snapshot(changed), [self.clone])
        compare_config(before, self.snapshot(body + self.addition()), [self.clone])
        for prior, changed in (('', '[projects]\n'), ('[projects]\n', ''), ('projects = []', 'projects = []')):
            with self.assertRaises(AssertionError):
                compare_config(self.snapshot(prior), self.snapshot(changed), [])

    def test_rejects_outside_sibling_prefix_relative_and_alias_keys(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.clone, target_is_directory=True)
        before = self.snapshot('')
        for key in (self.root, self.root / 'sibling', str(self.clone) + '-prefix', 'clone', alias,
                    str(self.clone) + '/', str(self.clone) + '/.', str(self.clone) + '/../clone'):
            with self.subTest(key=str(key)), self.assertRaisesRegex(AssertionError, 'exact owned'):
                compare_config(before, self.snapshot(self.addition(key)), [self.clone])
        with self.assertRaises(AssertionError):
            compare_config(before, self.snapshot(self.addition()), [alias])
        with self.assertRaises(AssertionError):
            compare_config(before, self.snapshot(self.addition()), [self.root / 'missing'])

    def test_only_sole_trusted_field_allowed(self):
        before = self.snapshot('')
        for fields in ('trust_level = "untrusted"', 'trust_level = true', 'trust_level = 1',
                       'trust_level = "trusted"\nextra = true', 'other = "trusted"'):
            with self.subTest(fields=fields), self.assertRaisesRegex(AssertionError, 'sole trusted'):
                compare_config(before, self.snapshot(self.addition(fields=fields)), [self.clone])

    def test_group_permits_only_finite_owned_clones(self):
        second = self.root / 'second'
        second.mkdir()
        before = self.snapshot('')
        after = self.snapshot(self.addition() + self.addition(second))
        self.assertEqual(len(compare_config(before, after, [self.clone, second])['added_owned_projects']), 2)
        with self.assertRaises(AssertionError):
            compare_config(before, after, [self.clone])

    def test_rejects_corrupted_hashes_and_private_modes(self):
        before = self.snapshot('model = "same"')
        for key in ('raw_sha256', 'semantic_sha256'):
            changed = dict(before, **{key: '0' * 64})
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, 'hash drift'):
                compare_config(before, changed, [])
        path = Path(before['private_path'])
        path.write_text('model = "changed"')
        with self.assertRaisesRegex(AssertionError, 'raw hash drift'):
            compare_config(before, before, [])
        before = self.snapshot('model = "same"')
        path = Path(before['private_path'])
        path.chmod(0o644)
        with self.assertRaisesRegex(AssertionError, 'mode0600'):
            compare_config(before, before, [])
        path.chmod(0o600)
        path.parent.chmod(0o755)
        with self.assertRaisesRegex(AssertionError, 'mode0700'):
            compare_config(before, before, [])

    def test_private_snapshot_cannot_be_inside_owned_clone(self):
        (self.clone / '.git').mkdir()
        self.source.write_text('')
        destination = self.clone / 'private' / 'rejected.toml'
        with self.assertRaisesRegex(AssertionError, 'inside a Git clone'):
            capture_user_config(destination, self.source)
        self.assertFalse(destination.exists())
        (self.clone / '.git').rmdir()
        before = self.snapshot('')
        after = capture_user_config(self.clone / 'private' / 'after.toml', self.source)
        with self.assertRaisesRegex(AssertionError, 'inside owned clone'):
            compare_config(before, after, [self.clone])

    def test_rejects_existing_symlink_missing_invalid_and_capture_drift(self):
        before = self.snapshot('model = "same"')
        path = Path(before['private_path'])
        with self.assertRaisesRegex(AssertionError, 'already exists'):
            capture_user_config(path, self.source)
        linked = path.parent / 'linked'
        linked.symlink_to(path)
        with self.assertRaisesRegex(AssertionError, 'Symlink'):
            capture_user_config(linked, self.source)
        receipt = dict(before, private_path=str(linked))
        with self.assertRaisesRegex(AssertionError, 'Symlink'):
            compare_config(before, receipt, [])
        with self.assertRaisesRegex(AssertionError, 'Missing'):
            capture_user_config(path.parent / 'missing', self.root / 'missing')
        for body in ('model = [', 'model = "private"\nmodel = "duplicate"'):
            self.source.write_text(body)
            with self.assertRaisesRegex(AssertionError, '^Invalid Codex user configuration TOML$'):
                capture_user_config(path.parent / 'invalid', self.source)
        self.source.write_text('model = "same"')
        with patch.object(Path, 'read_bytes', side_effect=[b'model = "same"', b'model = "drift"']):
            with self.assertRaisesRegex(AssertionError, 'changed during capture'):
                capture_user_config(path.parent / 'drift', self.source)



def claude(name, inputs, output, failed=False, ident='t1'):
    return '\n'.join(json.dumps(event) for event in (
        {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': ident, 'name': name, 'input': inputs}]}},
        {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': ident, 'is_error': failed, 'content': output}]}}))


def codex(command, output, code=0):
    return json.dumps({'type': 'item.completed', 'item': {'id': 'cmd1', 'type': 'command_execution', 'command': command,
        'status': 'completed', 'exit_code': code, 'aggregated_output': output}})


def opencode(name, inputs, output, status='completed'):
    return json.dumps({'type': 'tool_use', 'part': {'type': 'tool', 'tool': name,
        'state': {'status': status, 'input': inputs, 'output': output}}})


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'company').mkdir()
        self.file = self.root / 'company/rules.md'
        self.file.write_text('Distinct start rule.\nUnique middle rule.\nDistinct final rule.\n')
        for skill in ('cs-bootstrap', 'cs-instructions'):
            path = self.root / '.claude/skills' / skill / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text(f'# {skill}\nComplete workflow body for {skill}.\n')
        (self.root / '.agents').mkdir()
        (self.root / '.agents/skills').symlink_to('../.claude/skills')

    def tearDown(self):
        self.tmp.cleanup()

    def test_claim_and_command_without_output_do_not_prove_read(self):
        transcript = json.dumps({'type': 'result', 'result': 'I read company/rules.md fully.'})
        self.assertFalse(read_coverage(audit_tools(transcript, self.root), self.file)['complete'])
        self.assertFalse(read_coverage(audit_tools(codex('cat company/rules.md', ''), self.root), self.file)['complete'])

    def test_native_skill_complete_body_has_explicit_scope_without_metadata_credit(self):
        path = self.root / '.claude/skills/cs-instructions/SKILL.md'
        body = '# cs-instructions\n\nDistinct first rule.\nUnique middle rule.\nDistinct last rule.\n'
        path.write_text('---\nname: cs-instructions\ndescription: Workflow explanation.\n---\n' + body)
        alias = self.root / '.opencode/skills'
        alias.parent.mkdir()
        alias.symlink_to('../.claude/skills')
        output = ('<skill_content name="cs-instructions">\n# Skill: cs-instructions\n\n' + body +
                  f'\nBase directory for this skill: {alias / "cs-instructions"}\n' +
                  'Relative paths are relative to this directory.\n<skill_files>\n</skill_files>\n</skill_content>')
        evidence = audit_tools(opencode('skill', {'name': 'cs-instructions'}, output), self.root)
        self.assertEqual(read_coverage(evidence, path), {'covered': 4, 'total': 4, 'complete': True,
            'scope': 'canonical-skill-body', 'file_covered': 4, 'file_total': 8})
        read = claude('Read', {'file_path': str(path)}, body)
        self.assertFalse(read_coverage(audit_tools(read, self.root), path)['complete'])
        full = claude('Read', {'file_path': str(path)}, path.read_text())
        self.assertEqual(read_coverage(audit_tools(full, self.root), path),
                         {'covered': 8, 'total': 8, 'complete': True})
        head = claude('Read', {'file_path': str(path)}, path.read_text().split(body)[0], ident='head')
        self.assertTrue(read_coverage(audit_tools(head + '\n' + read, self.root), path)['complete'])

    def test_native_skill_body_rejects_partial_wrong_identity_base_and_envelope(self):
        path = self.root / '.claude/skills/cs-instructions/SKILL.md'
        body = '# cs-instructions\nDistinct first rule.\nUnique middle rule.\nDistinct last rule.\n'
        path.write_text('---\nname: cs-instructions\ndescription: Workflow explanation.\n---\n' + body)
        output = ('<skill_content name="cs-instructions">\n# Skill: cs-instructions\n\n' + body +
                  f'\nBase directory for this skill: {path.parent}\n</skill_content>')
        variants = [output.replace(line, '') for line in body.splitlines(keepends=True)]
        variants += [output.replace('Unique middle rule.\n', 'Distinct last rule.\nUnique middle rule.\n'),
                     output.replace('name="cs-instructions"', 'name="cs-bootstrap"'),
                     output.replace('# Skill: cs-instructions', '# Skill: cs-bootstrap'),
                     output.replace(str(path.parent), str(self.root / '.claude/skills/cs-bootstrap')),
                     output.replace(str(path.parent), '/outside/skills/cs-instructions'),
                     output.replace(str(path.parent), 'cs-instructions'),
                     output.replace('\n</skill_content>', '\nBase directory for this skill: duplicate\n</skill_content>'),
                     output.replace('</skill_content>', ''),
                     output.replace('<skill_content', '<broken_skill_content'), body]
        for variant in variants:
            with self.subTest(output=variant):
                evidence = audit_tools(opencode('skill', {'name': 'cs-instructions'}, variant), self.root)
                self.assertFalse(read_coverage(evidence, path)['complete'])
        failed = audit_tools(opencode('skill', {'name': 'cs-instructions'}, output, status='error'), self.root)
        self.assertFalse(read_coverage(failed, path)['complete'])
        wrong = audit_tools(opencode('skill', {'name': 'cs-bootstrap'}, output), self.root)
        self.assertFalse(read_coverage(wrong, path)['complete'])
        self.assertFalse(read_coverage(audit_tools(codex('cat company/rules.md', output), self.root), self.file)['complete'])

    def codex_context(self, cwd, session_id='thread1', session_cwd=None, identifiers=('cmd1',)):
        launched = datetime.now(timezone.utc)
        directory = self.root / 'sessions' / launched.strftime('%Y/%m/%d')
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / 'rollout-fixture-thread1.jsonl'
        rows = [{'type': 'session_meta', 'payload': {'id': session_id, 'cwd': session_cwd or str(self.root),
                 'timestamp': launched.isoformat()}}]
        rows += [{'type': 'turn_context', 'payload': {'turn_id': 'turn1', 'model': 'fixture-model', 'effort': 'low',
                  'private': 'private-synthetic-value'}}]
        rows += [{'type': 'event_msg', 'payload': {'item': {'type': 'CommandExecution', 'id': ident, 'cwd': cwd,
                  'command': ['cat', 'company/rules.md'], 'exit_code': 0}}}
                 for ident in identifiers]
        source.write_text('\n'.join(json.dumps(row) for row in rows))
        transcript = json.dumps({'type': 'thread.started', 'thread_id': 'thread1'}) + '\n' + codex('cat company/rules.md', self.file.read_text())
        return transcript, self.root, self.root / 'context.json', launched, self.root / 'sessions'

    def test_codex_rollout_root_alias_and_file_uri(self):
        alias = self.root / 'clone-alias'
        alias.symlink_to(self.root, target_is_directory=True)
        for cwd in (str(self.root), str(alias), self.root.as_uri(), '.'):
            with self.subTest(cwd=cwd):
                receipt = capture_command_context(*self.codex_context(cwd))
                self.assertEqual(receipt['thread_id'], 'thread1')
                self.assertEqual(receipt['commands'][0]['cwd'], cwd)
                self.assertEqual(receipt['turns'][0]['model'], 'fixture-model')
                self.assertNotIn('private-synthetic-value', json.dumps(receipt))
                self.assertEqual(json.loads((self.root / 'context.json').read_text()), receipt)

    def test_codex_rollout_rejects_unknown_missing_and_external_cwd(self):
        for cwd in (None, '', '/etc', str(self.root / 'missing'), 'https://example.invalid/', '$PWD', 'file://remote/etc'):
            with self.subTest(cwd=cwd), self.assertRaises(AssertionError):
                capture_command_context(*self.codex_context(cwd))
            self.assertTrue((self.root / 'context.json').is_file())

    def test_codex_subdirectory_cwd_is_explicitly_unverifiable(self):
        with self.assertRaisesRegex(AssertionError, '^UNVERIFIABLE:'):
            capture_command_context(*self.codex_context(str(self.root / 'company')))
        self.assertEqual(json.loads((self.root / 'context.json').read_text())['commands'][0]['cwd'], str(self.root / 'company'))

    def test_codex_rollout_identity_and_command_cardinality(self):
        for inputs in ({'session_id': 'other'}, {'session_cwd': '/etc'}, {'identifiers': ()},
                       {'identifiers': ('cmd1', 'cmd1')}, {'identifiers': (None,)}):
            with self.subTest(inputs=inputs), self.assertRaises(AssertionError):
                capture_command_context(*self.codex_context(str(self.root), **inputs))

    def test_codex_rollout_matches_real_separate_identifier_namespaces(self):
        args = self.codex_context(str(self.root), identifiers=('exec-unique',))
        self.assertEqual(capture_command_context(*args)['commands'][0]['stdout_id'], 'cmd1')
        source = next(args[4].rglob('*.jsonl'))
        for field, changed in (('command', ['cat', '/etc/passwd']), ('exit_code', -1)):
            args = self.codex_context(str(self.root))
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            rows[-1]['payload']['item'][field] = changed
            source.write_text('\n'.join(json.dumps(row) for row in rows))
            with self.subTest(field=field), self.assertRaisesRegex(AssertionError, 'Mismatched Codex rollout command'):
                capture_command_context(*args)

    def test_codex_rollout_requires_unique_thread_and_source(self):
        args = list(self.codex_context(str(self.root)))
        original = args[0]
        for transcript in (codex('cat company/rules.md', ''), original + '\n' + json.dumps({'type': 'thread.started', 'thread_id': 'thread1'})):
            args[0] = transcript
            with self.assertRaises(AssertionError):
                capture_command_context(*args)
        args[0] = original
        source = next(args[4].rglob('*.jsonl'))
        duplicate = source.with_name('rollout-duplicate-thread1.jsonl')
        duplicate.write_bytes(source.read_bytes())
        with self.assertRaises(AssertionError):
            capture_command_context(*args)
        duplicate.unlink()
        source.unlink()
        with self.assertRaises(AssertionError):
            capture_command_context(*args)

    def test_codex_rollout_lookup_retains_launch_date_across_midnight(self):
        args = list(self.codex_context(str(self.root)))
        from datetime import timedelta
        previous = args[3] - timedelta(days=1)
        source = next(args[4].rglob('*.jsonl'))
        directory = args[4] / previous.strftime('%Y/%m/%d')
        directory.mkdir(parents=True)
        source.rename(directory / source.name)
        args[3] = previous
        self.assertEqual(capture_command_context(*args)['thread_id'], 'thread1')

    def test_codex_rollout_requires_model_evidence(self):
        args = self.codex_context(str(self.root))
        source = next(args[4].rglob('*.jsonl'))
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        source.write_text('\n'.join(json.dumps(row) for row in rows if row['type'] != 'turn_context'))
        with self.assertRaisesRegex(AssertionError, 'Missing Codex session model'):
            capture_command_context(*args)

    def test_successful_chunks_and_failed_tail(self):
        first = claude('Read', {'file_path': 'company/rules.md', 'offset': 1, 'limit': 2}, '1→Distinct start rule.\n2→Unique middle rule.')
        tail = claude('Read', {'file_path': 'company/rules.md', 'offset': 3}, '3→Distinct final rule.', ident='t2')
        self.assertFalse(read_coverage(audit_tools(first, self.root), self.file)['complete'])
        self.assertTrue(read_coverage(audit_tools(first + '\n' + tail, self.root), self.file)['complete'])
        failed = claude('Read', {'file_path': 'company/rules.md'}, self.file.read_text(), failed=True)
        self.assertFalse(read_coverage(audit_tools(failed, self.root), self.file)['complete'])

    def test_codex_and_opencode_outputs(self):
        for transcript in (codex("/bin/bash -lc 'cat company/rules.md'", self.file.read_text()), opencode('read', {'filePath': str(self.file)}, self.file.read_text())):
            self.assertTrue(read_coverage(audit_tools(transcript, self.root), self.file)['complete'])

    def test_skill_identity_and_alias(self):
        evidence = audit_tools(claude('Skill', {'skill': 'cs-instructions'}, 'Launching skill'), self.root)
        self.assertTrue(loaded(evidence, self.root, 'cs-instructions'))
        self.assertFalse(loaded(evidence, self.root, 'cs-bootstrap'))
        skill = self.root / '.claude/skills/cs-bootstrap/SKILL.md'
        alias = codex('cat .agents/skills/cs-bootstrap/SKILL.md', skill.read_text())
        self.assertTrue(loaded(audit_tools(alias, self.root), self.root, 'cs-bootstrap'))
        (self.root / 'company/escape.md').symlink_to('/etc/passwd')
        with self.assertRaises(AssertionError):
            audit_tools(claude('Read', {'file_path': 'company/escape.md'}, 'data'), self.root)

    def test_whole_run_forbidden_search_after_catalog(self):
        discovery = codex('cs rpc system.catalog', '{}')
        for forbidden in ('cat .venv/lib/source.py', 'rg bank tests', 'cat /etc/passwd', 'python -c "print(1)"', 'cat $TARGET', 'git log -p', 'git diff', 'git diff -- .venv/source.py', 'git log -- cs/cli.py', 'git ls-files .venv'):
            with self.subTest(command=forbidden), self.assertRaises(AssertionError):
                audit_tools(discovery + '\n' + codex(forbidden, ''), self.root)
        with self.assertRaises(AssertionError):
            audit_tools(claude('WebSearch', {'query': 'bank'}, 'hit'), self.root)

    def test_shell_short_circuit_does_not_invent_external_read(self):
        command = 'cat company/rules.md; test ! -f docs/.doc-profile || cat /external/SKILL.md'
        evidence = audit_tools(codex(command, self.file.read_text()), self.root)
        self.assertTrue(read_coverage(evidence, self.file)['complete'])
        (self.root / 'docs').mkdir()
        (self.root / 'docs/.doc-profile').touch()
        with self.assertRaises(AssertionError):
            audit_tools(codex(command, self.file.read_text()), self.root)

    def test_observed_if_guard_does_not_hide_an_executed_read(self):
        command = 'if [ -f docs/.doc-profile ]; then cat /outside/SKILL.md; fi'
        self.assertEqual(audit_tools(codex(command, ''), self.root)[0]['paths'], [])
        for unsafe in ('if [ -f company/rules.md ]; then cat /outside/SKILL.md; fi',
                       'if [ -f docs/.doc-profile ]; then cat company/rules.md; fi; cat /outside/SKILL.md'):
            with self.assertRaises(AssertionError):
                audit_tools(codex(unsafe, ''), self.root)
        (self.root / 'docs').mkdir()
        (self.root / 'docs/.doc-profile').touch()
        with self.assertRaises(AssertionError):
            audit_tools(codex(command, ''), self.root)

    def test_python_wrapper_preserves_normal_hook_execution(self):
        from capabilities_fixture import Fixture
        fixture = Fixture(self.root / 'fixture', sys.executable, 'workflow')
        hook = fixture.root / 'normal-hook.py'
        hook.write_text('import sys; print("hook ran", sys.argv[1])')
        before = fixture.state()
        body = (fixture.clone / '.claude/skills/cs-instructions/SKILL.md').read_text()
        guard = ' '.join(body.split('Run commands from the clone root', 1)[0].split())
        self.assertIn('Once the complete body is loaded, answer from it and stop: make no further tool calls.', guard)
        self.assertIn("Routine startup or session-memory reminders do not expand the user's explanation-only request.", guard)
        self.assertIn('look up command help, or create, edit, publish or persist anything.', guard)
        for wrapper in ('python', 'python3'):

            result = subprocess.run([str(fixture.bin / wrapper), str(hook), 'normal'], cwd=fixture.clone, env=fixture.env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'hook ran normal')
        self.assertFalse((fixture.logs / 'cli.jsonl').exists())
        result = subprocess.run([str(fixture.bin / 'python'), '-m', 'cs', 'whoami'], cwd=fixture.clone, env=fixture.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((fixture.logs / 'cli.jsonl').read_text())['argv'], ['whoami'])
        self.assertEqual(before, fixture.state())

    def test_explanation_guard_preserves_all_original_teaching_bytes(self):
        from capabilities_fixture import ROOT, BASE
        rel = 'cs/templates/project/.claude/skills/cs-instructions/SKILL.md.j2'
        previous = subprocess.check_output(['git', 'show', BASE + ':' + rel], cwd=ROOT)
        current = (ROOT / rel).read_bytes()
        # The reviewed explanation trigger changes frontmatter, not teaching.
        previous = previous.split(b'---', 2)[2]
        current = current.split(b'---', 2)[2]
        start = current.index(b'For an explanation-only question')
        end = current.index(b'Run commands from the clone root', start)
        self.assertEqual(current[:start] + current[end:], previous)
        source = 'cs/instructions.py'
        self.assertEqual((ROOT / source).read_bytes(), subprocess.check_output(['git', 'show', BASE + ':' + source], cwd=ROOT))
        # Contextual-email policy evolves chat independently of instruction
        # publication. Keep every other RPC definition, import and constant
        # identical, including call_sync, EngineClient and read-only transport.
        source = 'cs/rpc.py'
        previous = subprocess.check_output(['git', 'show', BASE + ':' + source], cwd=ROOT)
        modules = [ast.parse(previous), ast.parse((ROOT / source).read_bytes())]
        for module in modules:
            module.body = [node for node in module.body if not (
                isinstance(node, ast.AsyncFunctionDef) and node.name == 'chat')]
        self.assertEqual(ast.dump(modules[0], include_attributes=False),
                         ast.dump(modules[1], include_attributes=False))

    def test_listing_is_not_a_body_read(self):
        evidence = audit_tools(opencode('glob', {'path': 'company', 'pattern': '*.md'}, self.file.read_text()), self.root)
        self.assertFalse(read_coverage(evidence, self.file)['complete'])

    def test_error_quota_timeout_and_empty_final_fail(self):
        for transcript, code in ((json.dumps({'type': 'result', 'is_error': True, 'result': 'Failed'}), 0),
                                 (json.dumps({'type': 'result', 'result': 'Usage limit reached'}), 0),
                                 (json.dumps({'type': 'error', 'error': 'rate limit'}), 0),
                                 ('', 0), (json.dumps({'type': 'result', 'result': 'ok'}), -9)):
            with self.subTest(transcript=transcript), self.assertRaises(AssertionError):
                require_host_success(transcript, code)
        with self.assertRaises(AssertionError):
            require_host_success(json.dumps({'type': 'result', 'result': 'ok'}), 0, debug='Skill listing over budget')

    def test_request_secret_and_provider_failures(self):
        require_safe_requests([{'method': 'system.catalog'}], [], '{}')
        for frames, providers, output in (([{'method': 'bank.read'}], [], '{}'), ([], ['attempt'], '{}'), ([], [], 'secret-value')):
            with self.assertRaises(AssertionError):
                require_safe_requests(frames, providers, output, ('secret-value',))

    def test_opencode_clock_coincidence_only(self):
        stamp = 1723456789012
        pairs = {'step_start': 'step-start', 'step_finish': 'step-finish',
                 'text': 'text', 'tool_use': 'tool'}
        for kind, part_kind in pairs.items():
            event = {'type': kind, 'timestamp': stamp, 'sessionID': 'ses_' + 'a' * 26,
                     'part': {'type': part_kind, 'sessionID': 'ses_' + 'a' * 26,
                              'id': 'prt_' + 'a' * 26, 'messageID': 'msg_' + 'a' * 26}}
            if kind == 'text':
                event['part'].update(text='Answer', time={'start': stamp, 'end': stamp})
            if kind == 'tool_use':
                event['part'].update(tool='bash', callID='call_' + 'a' * 24, state={'input': {}, 'output': 'ok',
                    'status': 'completed', 'time': {'start': stamp, 'end': stamp}})
            raw = json.dumps(event) + '\n'
            with self.subTest(kind=kind):
                with self.assertRaises(AssertionError):
                    require_safe_requests([], [], raw, ('3456',))
                safe = secret_audit_text(raw, 'opencode')
                require_safe_requests([], [], safe, ('3456',))
                self.assertEqual(json.loads(safe.splitlines()[0])['part'].get('text'), event['part'].get('text'))
                self.assertEqual(secret_audit_text(raw, 'claude'), raw)
                self.assertEqual(secret_audit_text(raw, 'codex'), raw)
                self.assertEqual(json.loads(raw), event)

    def test_opencode_clock_exemption_preserves_all_other_leaks(self):
        stamp = 1723456789012
        base = {'type': 'tool_use', 'timestamp': stamp, 'sessionID': 'ses_' + 'a' * 26,
                'part': {'type': 'tool', 'sessionID': 'ses_' + 'a' * 26, 'id': 'prt_' + 'a' * 26,
                         'messageID': 'msg_' + 'a' * 26, 'tool': 'bash', 'callID': 'call_' + 'a' * 24, 'state': {
                             'input': {}, 'output': 'ok', 'status': 'completed',
                             'time': {'start': stamp, 'end': stamp}}}}
        cases = []
        for container, key, value in (
            ('input', 'command', 'read secret3456'), ('input', 'account', 3456),
            ('state', 'output', 'secret3456'), ('state', 'output', {'account': 3456}),
            ('state', 'output', {'timestamp': stamp}), ('state', 'error', 'secret3456'),
            ('part', 'text', 'secret3456'), ('part', 'time', {'start': stamp}),
            ('event', 'timestamp', str(stamp)), ('event', 'other_clock', stamp),
            ('event', 'type', 'unknown'), ('part', 'sessionID', 'other'),
            ('part', 'id', None), ('part', 'type', 'text')):
            event = copy.deepcopy(base)
            target = event if container == 'event' else event['part']
            if container in ('state', 'input'):
                target = target['state']
            if container == 'input':
                target = target['input']
            target[key] = value
            cases.append((f'{container}/{key}', json.dumps(event)))
        event = copy.deepcopy(base)
        event['part']['state']['time']['start'] = str(stamp)
        cases += [('string state clock', json.dumps(event)), ('malformed', '{3456'),
                  ('non-object', '[3456]')]
        for label, raw in cases:
            with self.subTest(label=label), self.assertRaises(AssertionError):
                require_safe_requests([], [], secret_audit_text(raw, 'opencode'), ('3456',))
        # These channels remain raw at driver call sites, including business clocks.
        safe = secret_audit_text(json.dumps(base), 'opencode')
        for raw_channel in ('secret3456', json.dumps({'timestamp': stamp})):
            with self.assertRaises(AssertionError):
                require_safe_requests([], [], safe + raw_channel, ('3456',))

    def test_opencode_metadata_short_marker_and_unconditional_raw_secrets(self):
        session = 'ses_' + 'a' * 26
        message = 'msg_' + 'a' * 10 + '3456' + 'b' * 12
        event = {'type': 'text', 'timestamp': 1723456789012, 'sessionID': session,
                 'part': {'type': 'text', 'sessionID': session, 'id': 'prt_' + 'a' * 26,
                          'messageID': message, 'text': 'Answer',
                          'time': {'start': 1723456789012, 'end': 1723456789012}}}
        raw = json.dumps(event)
        stderr = f'timestamp=2026-10-10T12:14:43.706Z level=INFO run=2fe6d1e3 message=process session.id={session} messageID={message}\n'
        require_private_channels('opencode', raw, stderr, (), ('full-secret',), ('3456',))
        for secret in (message, session, '3456', '1723456789012'):
            with self.subTest(secret=secret), self.assertRaises(AssertionError):
                require_private_channels('opencode', raw, stderr, (), (secret,), ('3456',))
        for host in ('claude', 'codex'):
            with self.assertRaises(AssertionError):
                require_private_channels(host, raw, stderr, (), (), ('3456',))
        for target, value in (('text', '3456'), ('other', '3456'), ('business', 3456)):
            changed = copy.deepcopy(event)
            changed['part'][target] = value
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', json.dumps(changed), '', (), (), ('3456',))
        for changed in ('other', 'malformed3456'):
            broken = copy.deepcopy(event)
            broken['part']['sessionID'] = changed
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', json.dumps(broken), '', (), (), ('3456',))
        for bad in (stderr.replace('message=process', 'message=other'), stderr.replace(session, 'ses_' + 'b' * 26), stderr + 'other3456', stderr.replace('level=INFO', 'level=DEBUG')):
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', raw, bad, (), (), ('3456',))
        for channel in ('cli3456', 'engine3456', json.dumps({'timestamp': 1723456789012})):
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', raw, stderr, (channel,), (), ('3456',))

    def test_opencode_unknown_identity_schema_and_tool_payload_remain_raw(self):
        base = {'type': 'tool_use', 'timestamp': 1723456789012, 'sessionID': 'ses_' + 'a' * 26,
                'part': {'type': 'tool', 'sessionID': 'ses_' + 'a' * 26,
                         'id': 'prt_' + 'a' * 26, 'messageID': 'msg_' + 'a' * 26,
                         'callID': 'call_' + 'a' * 24, 'tool': 'bash', 'state': {'status': 'completed', 'input': {}, 'output': 'ok',
                         'time': {'start': 1723456789012, 'end': 1723456789012}}}}
        for key, value in (('id', 'unknown3456'), ('messageID', 'msg_3456'), ('callID', 'call_3456'), ('type', 'unknown')):
            event = copy.deepcopy(base)
            event['part'][key] = value
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', json.dumps(event), '', (), (), ('3456',))
        for target in ('input', 'output'):
            event = copy.deepcopy(base)
            event['part']['state'][target] = {'business': 3456}
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', json.dumps(event), '', (), (), ('3456',))

    def test_malformed_opencode_envelopes_receive_no_metadata_exemption(self):
        session = 'ses_' + 'a' * 26
        message = 'msg_' + 'a' * 10 + '3456' + 'b' * 12
        stamp = 1720000000000
        base = {'type': 'text', 'timestamp': stamp, 'sessionID': session,
                'part': {'type': 'text', 'sessionID': session, 'id': 'prt_' + 'a' * 26,
                         'messageID': message, 'text': 'answer', 'time': {'start': stamp, 'end': stamp}}}
        cases = []
        for key, value in (('timestamp', 'malformed'), ('timestamp', True), ('timestamp', 1), ('other', 'value')):
            event = copy.deepcopy(base); event[key] = value; cases.append(event)
        for key, value in (('time', 'malformed'), ('time', {'start': stamp}), ('time', {'start': stamp, 'end': 'bad'}),
                           ('text', 123), ('other', 'value')):
            event = copy.deepcopy(base); event['part'][key] = value; cases.append(event)
        for event in cases:
            with self.subTest(event=event), self.assertRaises(AssertionError):
                require_private_channels('opencode', json.dumps(event), '', (), (), ('3456',))
        for state in ({'status': 'completed', 'input': {}, 'output': 123, 'time': {'start': stamp, 'end': stamp}},
                      {'status': 'unknown', 'input': {}, 'output': 'ok', 'time': {'start': stamp, 'end': stamp}},
                      {'status': 'completed', 'input': 'bad', 'output': 'ok', 'time': {'start': stamp, 'end': stamp}},
                      {'status': 'completed', 'input': {}, 'output': 'ok', 'time': 'bad'}):
            event = copy.deepcopy(base); event['type'] = 'tool_use'
            event['part'] = {key: value for key, value in event['part'].items() if key not in ('text', 'time')}
            event['part'].update(type='tool', tool='bash', callID='call_' + 'a' * 24, state=state)
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', json.dumps(event), '', (), (), ('3456',))

    def test_duplicate_json_keys_fail_closed_before_metadata_normalization(self):
        session = 'ses_' + 'a' * 26
        message = 'msg_' + 'a' * 26
        stamp = 1720000000000
        base = {'type': 'text', 'timestamp': stamp, 'sessionID': session,
                'part': {'type': 'text', 'sessionID': session, 'id': 'prt_' + 'a' * 26,
                         'messageID': message, 'text': 'Answer', 'time': {'start': stamp, 'end': stamp}}}
        raw = json.dumps(base)
        for original, duplicate in (('"text": "Answer"', '"text": "3456", "text": "Answer"'),
                                    ('"messageID": "' + message + '"', '"messageID": "3456", "messageID": "' + message + '"'),
                                    ('"timestamp": ' + str(stamp), '"timestamp": 3456, "timestamp": ' + str(stamp)),
                                    ('"text": "Answer"', '"text": "\\u0033\\u0034\\u0035\\u0036", "text": "Answer"')):
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', raw.replace(original, duplicate), '', (), (), ('3456',))
        for key in ('input', 'output'):
            tool = copy.deepcopy(base); tool['type'] = 'tool_use'
            tool['part'] = {k: v for k, v in tool['part'].items() if k not in ('text', 'time')}
            tool['part'].update(type='tool', tool='bash', callID='call_' + 'a' * 24,
                state={'status': 'completed', 'input': {'value': 'Answer'}, 'output': 'Answer', 'time': {'start': stamp, 'end': stamp}})
            text = json.dumps(tool)
            original = '"value": "Answer"' if key == 'input' else '"output": "Answer"'
            duplicate = '"value": "3456", "value": "Answer"' if key == 'input' else '"output": "3456", "output": "Answer"'
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', text.replace(original, duplicate), '', (), (), ('3456',))
        for constant in ('NaN', 'Infinity', '-Infinity'):
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', raw.replace('"text": "Answer"', '"text": ' + constant), '', (), (), ('3456',))

    def test_unicode_escaped_full_secrets_and_business_markers_still_fail(self):
        session = 'ses_' + 'a' * 26
        message = 'msg_' + 'a' * 26
        stamp = 1720000000000
        base = {'type': 'text', 'timestamp': stamp, 'sessionID': session,
                'part': {'type': 'text', 'sessionID': session, 'id': 'prt_' + 'a' * 26,
                         'messageID': message, 'text': 'fixture-secret-value', 'time': {'start': stamp, 'end': stamp}}}
        raw = json.dumps(base).replace('fixture-secret-value', 'fixture-\\u0073ecret-value')
        for host in ('opencode', 'claude', 'codex'):
            with self.assertRaises(AssertionError):
                require_private_channels(host, raw, '', (), ('fixture-secret-value',))
        base['part']['text'] = 'Answer'
        raw = json.dumps(base).replace(message, '\\u006d' + message[1:])
        with self.assertRaises(AssertionError):
            require_private_channels('opencode', raw, '', (), (message,))
        for channel in ('{"output":"fixture-\\u0073ecret-value"}', '{"response":{"token":"fixture-\\u0073ecret-value"}}',
                        '{"output":"fixture-\\u0073ecret-value","output":"safe"}', '{"broken":"fixture-\\u0073ecret-value"'):
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', json.dumps(base), '', (channel,), ('fixture-secret-value',))
        for key in ('text', 'other'):
            changed = copy.deepcopy(base); changed['part'][key] = '3456'
            escaped = json.dumps(changed).replace('3456', '\\u0033\\u0034\\u0035\\u0036')
            with self.assertRaises(AssertionError):
                require_private_channels('opencode', escaped, '', (), (), ('3456',))

    def test_decoded_actual_string_secrets_and_nonopencode_markers(self):
        for host, event in (
            ('claude', {'type': 'result', 'result': '3456'}),
            ('codex', {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '3456'}})):
            raw = json.dumps(event).replace('3456', '\\u0033\\u0034\\u0035\\u0036')
            with self.assertRaises(AssertionError):
                require_private_channels(host, raw, '', (), (), ('3456',))
        for secret in ('fixture"secret', 'fixture\\secret'):
            for host in ('claude', 'codex', 'opencode'):
                raw = json.dumps({'type': 'text', 'part': {'text': secret}})
                with self.assertRaises(AssertionError):
                    require_private_channels(host, raw, '', (), (secret,))
                with self.assertRaises(AssertionError):
                    require_private_channels(host, '{}', '', (json.dumps({'output': secret}),), (secret,))

    def test_numeric_json_overflow_is_ambiguous_native_evidence(self):
        for value in ('1e999', '-1e999'):
            for raw in ('{"type":"step_finish","part":{"cost":' + value + '}}',
                        '{"type":"text","part":{"business":{"value":' + value + '}}}'):
                with self.assertRaises(AssertionError):
                    require_private_channels('opencode', raw, '', (), (), ('3456',))

    def test_literal_previous_exit_status_diagnostics_have_no_file_targets(self):
        from capabilities_events import resolve_prose
        chain = '.venv/bin/python -m cs rpc system.catalog; echo "--- exit $?"; .venv/bin/python -m cs config; echo "--- exit $?"'
        for command in (chain, 'echo "$?"', '/bin/echo "--- exit $?"', '/usr/bin/echo "$?"',
                        'bash -lc ' + shlex.quote(chain)):
            with self.subTest(command=command):
                self.assertTrue(shell_parts(command))
                self.assertEqual(command_targets(command, self.root, resolve_prose), [])
                call = claude('Bash', {'command': command}, '--- exit 0')
                evidence = audit_tools(call, self.root)
                self.assertEqual(evidence[0]['paths'], [])

    def test_exit_status_support_preserves_all_other_shell_boundaries(self):
        from capabilities_events import resolve_prose
        bad = ('echo "$HOME"', 'echo "--- exit $? $HOME"', 'echo "${?}"',
               'echo "$((1))"', 'echo "$(cat company/README.md)"', 'echo "`pwd`"',
               'echo "$?"#$(cat /etc/passwd)', 'echo "$?" # $(cat /etc/passwd)',
               'echo -e "$?"', 'echo --- exit $?', 'echo "$? extra"',
               'cat "$?"', '.venv/bin/python -m cs rpc system.catalog "$?"',
               'echo "$?" > company/README.md', 'echo "$?" | head', 'pwd | echo "$?"',
               'echo "$?" &', 'echo "$?"\npwd', 'echo "$?"; rm company/README.md',
               'for f in company/*.md; do cat "$f"; done', 'echo "$?"; .venv/bin/python -m cs rpc instructions.store')
        for command in bad:
            with self.subTest(command=command), self.assertRaises(AssertionError):
                command_targets(command, self.root, resolve_prose)

    def test_inert_separator_and_stdin_filters_add_no_read_coverage(self):
        from capabilities_events import resolve_prose
        commands = (
            '.venv/bin/python -m cs rpc system.catalog \'{"system": "qonto"}\'; echo ---; .venv/bin/python -m cs config',
            '.venv/bin/python -m cs config 2>&1 | grep -inE \'qonto|bank|account|profile\'; echo "EXIT=${PIPESTATUS[0]}"',
            '.venv/bin/python -m cs config | rg -i bank; echo "EXIT=$?"',
            '/bin/echo ---', '/usr/bin/echo "EXIT=$?"',
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(command_targets(command, self.root, resolve_prose), [])
                evidence = audit_tools(claude('Bash', {'command': command}, '---'), self.root)
                self.assertEqual(evidence[0]['paths'], [])

    def test_output_filter_support_preserves_config_and_shell_rejections(self):
        from capabilities_events import resolve_prose
        commands = (
            'echo -n ---', 'echo "EXIT=$HOME"',
            'echo "EXIT=${PIPESTATUS[1]}"', 'echo "EXIT=${OTHER[0]}"',
            'echo "EXIT=$((1))"', 'echo "EXIT=$(cat company/README.md)"',
            'echo ---#$(cat /etc/passwd)', 'echo --- | head', 'pwd | echo ---',
            'echo --- > company/README.md', 'echo --- &', 'echo ---\npwd',
            '.venv/bin/python -m cs config | rg --files',
            '.venv/bin/python -m cs config | rg --files company',
            '.venv/bin/python -m cs config | grep -f company/README.md',
            '.venv/bin/python -m cs config | rg --pre cat bank',
            '.venv/bin/python -m cs config | grep *',
            '.venv/bin/python -m cs config | rg *',
            '.venv/bin/python -m cs config | grep {needle,/etc/passwd}',
            '.venv/bin/python -m cs config | rg {needle,/etc/passwd}',
            '.venv/bin/python -m cs config | grep ?source',
            '.venv/bin/python -m cs config | grep [ab]',
            '.venv/bin/python -m cs config | grep ~',
            '.venv/bin/python -m cs config | grep +(source)',
            '.venv/bin/python -m cs config | grep bank company/{README.md,../source.py}',
            '.venv/bin/python -m cs config | rg bank company/{README.md,../source.py}',
            '.venv/bin/python -m cs config | grep bank company/*',
            '.venv/bin/python -m cs config | rg bank company/*',
            'grep -i bank', 'rg -i bank', 'ls manifest.toml',
            '.venv/bin/python -m cs rpc instructions.store | grep -i bank',
            '.venv/bin/python -m cs config | grep -i bank; rm company/README.md',
        )
        for command in commands:
            with self.subTest(command=command), self.assertRaises(AssertionError):
                command_targets(command, self.root, resolve_prose)

    def test_literal_output_is_inert_without_read_coverage(self):
        from capabilities_events import resolve_prose
        for command in ('echo', 'echo ""', 'echo "--- config ---"',
                        'echo arbitrary', 'echo --- extra', 'echo config status: OK',
                        '/bin/echo "catalog_version=1"', '/usr/bin/echo ---',
                        '.venv/bin/python -m cs rpc system.catalog; echo "--- config ---"; .venv/bin/python -m cs config'):
            with self.subTest(command=command):
                self.assertEqual(command_targets(command, self.root, resolve_prose), [])
                evidence = audit_tools(claude('Bash', {'command': command}, 'config status: OK'), self.root)
                self.assertEqual(evidence[0]['paths'], [])

    def test_literal_output_preserves_expansion_and_command_boundaries(self):
        from capabilities_events import resolve_prose
        for command in ('/tmp/echo safe', './echo safe', 'echo -n', 'echo -e safe',
                        'echo -- safe', 'echo *', 'echo "[ab]"', 'echo "{a,b}"',
                        'echo ~', 'echo "(safe)"', 'echo "safe\\n"',
                        'echo safe $HOME', 'echo "safe$(pwd)"', 'echo safe#comment',
                        'echo safe | head', 'pwd | echo safe', 'echo safe > company/README.md',
                        'echo safe &', 'echo safe\npwd', 'echo safe; rm company/README.md',
                        'echo safe; ls manifest.toml', 'echo safe; .venv/bin/python -m cs rpc instructions.store'):
            with self.subTest(command=command), self.assertRaises(AssertionError):
                command_targets(command, self.root, resolve_prose)

    def test_fixture_and_candidate_drift(self):
        require_unchanged({'a': '1'}, {'a': '1'})
        with self.assertRaises(AssertionError):
            require_unchanged({'a': '1'}, {'a': '2'})
        (self.root / 'cs').mkdir()
        source = self.root / 'cs/example.py'
        source.write_text('a = 1\n')
        before = source_snapshot(self.root)
        source.write_text('a = 2\n')
        with self.assertRaises(AssertionError):
            require_unchanged(before, source_snapshot(self.root), 'Candidate source snapshot')

    def test_scheduled_cannot_pass_at_session_refusal(self):
        for answer in ('Cannot start because whoami permission was denied.', 'Quota exceeded.', 'No action taken.'):
            with self.assertRaises(AssertionError):
                require_scheduled([], [], answer, self.root)
        require_scheduled([], [], 'The bank availability question needs a human interactive session.', self.root)

    def test_duplicate_opencode_abort_retains_completed_output(self):
        success = {'type': 'tool_use', 'part': {'type': 'tool', 'tool': 'read', 'callID': 'call1',
            'state': {'status': 'completed', 'input': {'filePath': str(self.file)}, 'output': self.file.read_text()}}}
        abort = {'type': 'tool_use', 'part': {'type': 'tool', 'tool': 'unknown', 'callID': 'call1',
            'state': {'status': 'error', 'input': {}, 'raw': '', 'error': 'Tool execution aborted'}}}
        transcript = json.dumps(success) + '\n' + json.dumps(abort)
        evidence = audit_tools(transcript, self.root)
        self.assertTrue(read_coverage(evidence, self.file)['complete'])
        self.assertEqual(evidence[0]['duplicate_terminal_events'], [abort['part']])
        abort['part']['callID'] = 'different'
        with self.assertRaises(AssertionError):
            audit_tools(json.dumps(success) + '\n' + json.dumps(abort), self.root)
        abort['part']['callID'] = 'call1'
        abort['part']['state']['input'] = {'filePath': '/etc/passwd'}
        with self.assertRaises(AssertionError):
            audit_tools(json.dumps(success) + '\n' + json.dumps(abort), self.root)

    def test_missing_session_prose_is_not_permission_for_other_docs(self):
        audit_tools(claude('Read', {'file_path': 'docs/sessions/session.md'}, 'Missing', failed=True), self.root)
        (self.root / 'docs/sessions').mkdir(parents=True)
        (self.root / 'docs/sessions/session.md').write_text('Existing unseeded session')
        with self.assertRaises(AssertionError):
            audit_tools(claude('Read', {'file_path': 'docs/sessions/session.md'}, 'Existing'), self.root)
        with self.assertRaises(AssertionError):
            audit_tools(claude('Read', {'file_path': 'docs/arbitrary.md'}, 'Existing'), self.root)

    def test_denied_write_and_unbounded_grep_still_fail(self):
        with self.assertRaises(AssertionError):
            audit_tools(claude('Write', {'file_path': 'docs/sessions/session.md'}, 'Denied', failed=True), self.root)
        with self.assertRaises(AssertionError):
            audit_tools(claude('Grep', {'pattern': 'companion'}, 'company/README.md'), self.root)

    def test_scoped_metadata_and_wildcards(self):
        transcript = codex('wc -l company/*.md && ls -la company/ docs/sessions/ 2>&1; ls company/ 2>/dev/null;', '3 company/rules.md', 1)
        audit_tools(transcript, self.root)
        audit_tools(claude('Glob', {'pattern': 'company/**/*'}, 'company/rules.md'), self.root)
        (self.root / '.venv').mkdir()
        (self.root / '.venv/source.py').write_text('source')
        with self.assertRaises(AssertionError):
            audit_tools(claude('Glob', {'pattern': '**/*'}, '.venv/source.py'), self.root)

    def test_git_reads_are_scoped_to_known_prose(self):
        audit_tools(codex('git diff -- company/rules.md', ''), self.root)
        audit_tools(codex('git log --oneline -- company/rules.md', 'Fixture baseline'), self.root)
        audit_tools(codex('git ls-files company docs', 'company/rules.md'), self.root)
        audit_tools(codex('git status --short', ''), self.root)

    def test_count_and_filtered_tail_do_not_cover_middle(self):
        transcript = opencode('read', {'filePath': str(self.file)}, 'Distinct start rule.')
        transcript += '\n' + codex('wc -l company/rules.md', '3 company/rules.md')
        transcript += '\n' + codex('tail -1 company/rules.md', 'Distinct final rule.')
        self.assertFalse(read_coverage(audit_tools(transcript, self.root), self.file)['complete'])

    def test_reviewed_shell_false_passes_are_rejected(self):
        commands = (
            "sed -n '1r /etc/passwd' company/rules.md",
            "sed -n '1e touch /tmp/audit-write' company/rules.md",
            'sed -i 1,2p company/rules.md',
            'git log --format=%B --output=/tmp/bootstrap-review-write',
            'git diff --output=/tmp/bootstrap-review-write -- company/rules.md',
            'ls -R .', 'ls --recursive .', 'find company -exec cat /etc/passwd ;',
            'grep -f /etc/passwd company/rules.md',
            'rg --pre=/tmp/program pattern company',
            'head --bytes=10 /etc/passwd',
            'cat company/rules.md > /tmp/audit-write',
            'cat company/rules.md 2>/tmp/audit-write',
            '/tmp/custom/cat company/rules.md',
            'cat $(printf /etc/passwd)',
            'git check-ignore company/rules.md || cat /etc/passwd',
            'git ls-files --error-unmatch company/rules.md || cat /etc/passwd',
            'cat company/rules.md || cat /etc/passwd',
        )
        for command in commands:
            with self.subTest(command=command), self.assertRaises(AssertionError):
                audit_tools(codex(command, ''), self.root)

    def test_all_codex_actionable_items_are_classified(self):
        for kind in ('web_search', 'mcp_tool_call', 'file_change', 'collab_tool_call', 'unknown_action'):
            for lifecycle in ('item.started', 'item.updated', 'item.completed'):
                transcript = json.dumps({'type': lifecycle, 'item': {'id': 'id1', 'type': kind, 'status': 'failed', 'path': '/outside/note.md'}})
                with self.subTest(kind=kind, lifecycle=lifecycle), self.assertRaises(AssertionError):
                    audit_tools(transcript, self.root)
        with self.assertRaises(AssertionError):
            audit_tools('{malformed}\n' + codex('cat company/rules.md', ''), self.root)
        with self.assertRaises(AssertionError):
            audit_tools(json.dumps({'type': 'new_unknown_tool_envelope'}), self.root)

    def test_every_cli_attempt_rejects_help_trial_and_actions(self):
        for args in (['--help'], ['rpc', '--help'], ['rpc', 'system.catalog', '--help'],
                     ['rpc', 'bank.read'], ['instructions'], ['config', '--help'],
                     ['rpc', 'system.capabilities', '{"unexpected":1}']):
            with self.subTest(args=args), self.assertRaises(AssertionError):
                validate_cli_args(args)
        for command in ('cs --help', '.venv/bin/python -m cs rpc --help', 'cs rpc made.up'):
            with self.assertRaises(AssertionError):
                audit_tools(codex(command, ''), self.root)
        validate_cli_args(['rpc', 'system.catalog', '{"system":"bank"}'])
        with self.assertRaises(AssertionError):
            validate_cli_args(['rpc', 'system.catalog'], scheduled=True)
        with self.assertRaises(AssertionError):
            validate_cli_args(['config'], local=True)

    def test_claude_debug_evidence_must_exist_and_be_nonempty(self):
        debug = self.root / 'native.debug'
        with self.assertRaises(AssertionError):
            require_debug_file('claude', debug)
        debug.touch()
        with self.assertRaises(AssertionError):
            require_debug_file('claude', debug)
        debug.write_text('Debug evidence')
        self.assertEqual(require_debug_file('claude', debug), 'Debug evidence')

    def test_direct_workflow_needs_its_complete_body_not_bootstrap(self):
        path = self.root / '.claude/skills/cs-instructions/SKILL.md'
        fixture = SimpleNamespace(root=self.root, clone=self.root, logs=self.root / 'audit', server={})
        config = {'mcp_disabled': True, 'effective_mcp': []}
        direct = codex('cat .claude/skills/cs-instructions/SKILL.md', path.read_text())
        result = check_case('workflow', 'codex', fixture, direct, [], [], config)
        self.assertTrue(result['coverage']['.claude/skills/cs-instructions/SKILL.md']['complete'])
        extra = codex('cat .claude/skills/cs-bootstrap/SKILL.md', (self.root / '.claude/skills/cs-bootstrap/SKILL.md').read_text())
        check_case('workflow', 'codex', fixture, extra + '\n' + direct, [], [], config)
        for output in ('', '# cs-instructions'):
            with self.assertRaises(AssertionError):
                check_case('workflow', 'codex', fixture, extra + '\n' + codex('cat .claude/skills/cs-instructions/SKILL.md', output), [], [], config)

    def test_workflow_explanation_cannot_do_bookkeeping_after_body(self):
        path = self.root / '.claude/skills/cs-instructions/SKILL.md'
        fixture = SimpleNamespace(root=self.root, clone=self.root, logs=self.root / 'audit', server={})
        config = {'mcp_disabled': True, 'effective_mcp': []}
        direct = codex('cat .claude/skills/cs-instructions/SKILL.md', path.read_text())
        attempts = [codex('git status --short', ''), codex('ls docs/sessions', '', 1),
                    claude('Glob', {'pattern': 'docs/sessions/*'}, ''),
                    claude('Write', {'file_path': 'docs/sessions/a.md'}, 'Denied', failed=True),
                    codex('cs instructions', 'Denied', 1)]
        for attempt in attempts:
            with self.subTest(attempt=attempt), self.assertRaises(AssertionError):
                check_case('workflow', 'codex', fixture, direct + '\n' + attempt, [], [], config)

    def test_older_engine_rejects_observed_negative_headline_despite_caveat(self):
        requests = [{'id': 1, 'method': 'system.capabilities'}]
        responses = [{'id': 1, 'result': {}}]
        observed = '**No. I found no route to a company bank account from this session, and I have read nothing from one.** One of the checks is inconclusive rather than negative, so this is "not reachable as far as I can verify", not "it does not exist".'
        for answer in (observed, 'No access is available. The catalog is too old to know.', 'I cannot access the bank. Its existence remains unknown.'):
            with self.subTest(answer=answer), self.assertRaises(AssertionError):
                validate_catalog_journey('older-engine', requests, responses, 'bank', answer)
        for answer in ('I cannot determine bank availability: this engine cannot list its systems.', 'Cannot list the systems because this engine lacks the catalog; that does not establish absence.', 'Non posso verificare la disponibilità: questo motore non espone il catalogo.'):
            validate_catalog_journey('older-engine', requests, responses, 'bank', answer)

    def native_text(self, text, part='b', message='b'):
        stamp = 1723456789012
        return {'type': 'text', 'timestamp': stamp, 'sessionID': 'ses_' + 'a' * 26,
                'part': {'type': 'text', 'sessionID': 'ses_' + 'a' * 26,
                         'id': 'prt_' + part * 26, 'messageID': 'msg_' + message * 26,
                         'text': text, 'time': {'start': stamp, 'end': stamp}}}

    def test_terminal_opencode_answer_cannot_hide_behind_pretool_narration(self):
        pre = self.native_text('This is a question about the systems.\n', 'a', 'a')
        tool = json.loads(opencode('read', {'filePath': str(self.file)}, self.file.read_text()))
        negative = '**No bank access is configured or documented anywhere I can read.** The catalog is too old to know.'
        for chunks in ((negative,), ('**No bank ', negative[len('**No bank '):])):
            terminal = [self.native_text(chunk, chr(98 + i)) for i, chunk in enumerate(chunks)]
            raw = '\n'.join(json.dumps(e) for e in (pre, tool, *terminal))
            self.assertEqual(final_text(raw), negative)
            with self.assertRaises(AssertionError):
                validate_catalog_journey('older-engine', [{'id': 1, 'method': 'system.capabilities'}],
                                         [{'id': 1, 'result': {}}], 'bank', final_text(raw))
        good = 'I cannot determine bank availability: this engine cannot list its systems.'
        raw = '\n'.join(json.dumps(e) for e in (pre, tool, self.native_text(good)))
        self.assertEqual(require_host_success(raw, 0), good)
        validate_catalog_journey('older-engine', [{'id': 1, 'method': 'system.capabilities'}],
                                 [{'id': 1, 'result': {}}], 'bank', final_text(raw))

    def test_terminal_answer_rejects_missing_malformed_and_ambiguous_parts(self):
        text = self.native_text('Cannot list the systems.')
        tool = json.loads(opencode('read', {'filePath': str(self.file)}, self.file.read_text()))
        bad = []
        for key in ('id', 'messageID', 'sessionID', 'time', 'text'):
            changed = copy.deepcopy(text)
            changed['part'].pop(key)
            bad.append([tool, changed])
        changed = copy.deepcopy(text)
        changed['part']['sessionID'] = 'ses_' + 'c' * 26
        bad.extend(([tool, changed], [tool, text, text],
                    [tool, text, self.native_text('extra', 'c', 'c')],
                    [text, tool], [tool], [tool, self.native_text('')]))
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(AssertionError):
                final_text('\n'.join(json.dumps(e) for e in rows))

    def test_answer_selection_preserves_other_hosts_and_full_raw_privacy(self):
        for event in ({'type': 'result', 'result': 'Claude final'},
                      {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Codex final'}}):
            raw = json.dumps(event)
            self.assertEqual(final_text(raw), 'Claude final' if event['type'] == 'result' else 'Codex final')
        secret = 'full-private-secret'
        raw = '\n'.join((json.dumps(self.native_text(secret, 'a', 'a')),
                         opencode('read', {'filePath': str(self.file)}, self.file.read_text()),
                         json.dumps(self.native_text('Cannot list.'))))
        self.assertEqual(final_text(raw), 'Cannot list.')
        with self.assertRaises(AssertionError):
            require_private_channels('opencode', raw, '', (), (secret,))

    def gaps_capture(self):
        (self.root / 'company/README.md').write_text('Read the company guidance and companion.md.\n')
        (self.root / 'company/mailbox-identity.md').write_text('## What to write here\nUnwritten identity.\n')
        (self.root / 'company/companion.md').mkdir()
        reads = [claude('Read', {'file_path': str(path)}, path.read_text(), ident=str(i))
                 for i, path in enumerate(sorted((self.root / 'company').rglob('*'))) if path.is_file()]
        body = self.root / '.claude/skills/cs-bootstrap/SKILL.md'
        prefix = [claude('Read', {'file_path': str(body)}, body.read_text(), ident='body'), *reads]
        listing = subprocess.run(['ls', '-la', 'company/'], cwd=self.root, text=True, capture_output=True, check=True).stdout
        directory = subprocess.run(['ls', '-la', 'company/companion.md/'], cwd=self.root, text=True, capture_output=True, check=True).stdout
        suffix = [claude('Bash', {'command': 'ls -la company/companion.md/'}, directory, ident='directory'),
                  json.dumps({'type': 'result', 'result': 'customer-service-playbook.md absent; mailbox-identity.md unwritten; companion.md unreadable directory.'})]
        fixture = SimpleNamespace(root=self.root, clone=self.root, logs=self.root / 'audit', server={})
        return fixture, prefix, listing, suffix

    def test_complete_parent_inventory_proves_absence_without_fake_read_coverage(self):
        fixture, prefix, listing, suffix = self.gaps_capture()
        raw = '\n'.join([*prefix, claude('Bash', {'command': 'ls -la company/'}, listing, ident='listing'), *suffix])
        result = check_case('procedure-gaps', 'codex', fixture, raw, [], [], {'mcp_disabled': True, 'effective_mcp': []})
        missing = self.root / 'company/customer-service-playbook.md'
        metadata = [call for call in result['tool_evidence'] if 'gap_metadata' in call]
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0]['gap_metadata'][str(missing)]['state'], 'missing')
        self.assertFalse(any(str(missing) in call['paths'] for call in result['tool_evidence']))
        self.assertNotIn('company/customer-service-playbook.md', result['coverage'])
        self.assertFalse(missing.exists())

    def test_parent_inventory_rejects_failed_truncated_wrong_and_unread_inputs(self):
        fixture, prefix, listing, suffix = self.gaps_capture()
        row = next(line for line in listing.splitlines() if line.endswith('rules.md'))
        variants = [(listing, 'ls -la company/', True, prefix),
                    (listing.replace(row, ''), 'ls -la company/', False, prefix),
                    (listing + row + '\n', 'ls -la company/', False, prefix),
                    (listing + 'truncated output\n', 'ls -la company/', False, prefix),
                    (listing, 'ls -la company/companion.md/', False, prefix),
                    (listing, 'ls -la company/', False, [entry for entry in prefix if str(self.file) not in entry])]
        for output, command, failed, reads in variants:
            raw = '\n'.join([*reads, claude('Bash', {'command': command}, output, failed, ident='listing'), *suffix])
            with self.subTest(command=command, output=output), self.assertRaises(AssertionError):
                check_case('procedure-gaps', 'codex', fixture, raw, [], [], {'mcp_disabled': True, 'effective_mcp': []})
        missing = self.root / 'company/customer-service-playbook.md'
        missing.symlink_to(self.root / 'company/absent.md')
        output = subprocess.run(['ls', '-la', 'company/'], cwd=self.root, text=True, capture_output=True, check=True).stdout
        raw = '\n'.join([*prefix, claude('Bash', {'command': 'ls -la company/'}, output, ident='listing'), *suffix])
        with self.assertRaises(AssertionError):
            check_case('procedure-gaps', 'codex', fixture, raw, [], [], {'mcp_disabled': True, 'effective_mcp': []})

    def test_direct_failed_read_remains_valid_and_claim_alone_does_not(self):
        fixture, prefix, listing, suffix = self.gaps_capture()
        config = {'mcp_disabled': True, 'effective_mcp': []}
        raw = '\n'.join([*prefix, *suffix])
        with self.assertRaises(AssertionError):
            check_case('procedure-gaps', 'codex', fixture, raw, [], [], config)
        missing = self.root / 'company/customer-service-playbook.md'
        read = claude('Read', {'file_path': str(missing)}, 'File not found', True, ident='missing')
        check_case('procedure-gaps', 'codex', fixture, '\n'.join([*prefix, read, *suffix]), [], [], config)

    def test_complete_parent_section_survives_exact_missing_other_operand(self):
        fixture, prefix, listing, suffix = self.gaps_capture()
        command = 'ls -la company/ company/mailboxes/ 2>&1'
        run = subprocess.run(['bash', '-c', command], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn("ls: cannot access 'company/mailboxes/': No such file or directory", run.stdout)
        raw = '\n'.join([*prefix, claude('Bash', {'command': command}, run.stdout, ident='listing'), *suffix])
        result = check_case('procedure-gaps', 'codex', fixture, raw, [], [], {'mcp_disabled': True, 'effective_mcp': []})
        self.assertTrue(any('gap_metadata' in call for call in result['tool_evidence']))
        diagnostic = "ls: cannot access 'company/mailboxes/': No such file or directory"
        for output in (run.stdout.replace(diagnostic, ''), run.stdout + diagnostic + '\n',
                       run.stdout.replace(diagnostic, "ls: cannot access 'company/': Permission denied"),
                       run.stdout.replace(diagnostic, "ls: cannot access 'company/unlisted/': No such file or directory")):
            raw = '\n'.join([*prefix, claude('Bash', {'command': command}, output, ident='listing'), *suffix])
            with self.subTest(output=output), self.assertRaises(AssertionError):
                check_case('procedure-gaps', 'codex', fixture, raw, [], [], {'mcp_disabled': True, 'effective_mcp': []})

    def test_parent_inventory_rejects_broken_symlink_operand_and_ancestor(self):
        fixture, prefix, listing, suffix = self.gaps_capture()
        nested = self.root / 'company/nested'
        nested.mkdir()
        link = nested / 'mailboxes'
        link.symlink_to(nested / 'absent')
        absolute = str(self.root.parent / '..' / self.root.parent.name / self.root.name / 'company/nested/mailboxes') + '/'
        for operand in ('company/nested/mailboxes/', 'company/nested/mailboxes/child/',
                        absolute, '/' + str(link) + '/', 'company/nested/../nested/mailboxes/'):
            command = f'ls -la company/ {operand} 2>&1'
            run = subprocess.run(['bash', '-c', command], cwd=self.root, text=True, capture_output=True)
            self.assertEqual(run.returncode, 2)
            raw = '\n'.join([*prefix, claude('Bash', {'command': command}, run.stdout, ident='listing'), *suffix])
            with self.subTest(operand=operand), self.assertRaises(AssertionError):
                check_case('procedure-gaps', 'codex', fixture, raw, [], [], {'mcp_disabled': True, 'effective_mcp': []})

    def test_parent_inventory_rejects_expansion_capable_missing_operands(self):
        fixture, prefix, listing, suffix = self.gaps_capture()
        for operand in ('company/unmatched*', 'company/unmatched?', 'company/unmatched[abc]',
                        'company/unmatched{one,two}', 'company/~unmatched'):
            command = f'ls -la company/ {operand} 2>&1'
            run = subprocess.run(['bash', '-c', command], cwd=self.root, text=True, capture_output=True)
            self.assertEqual(run.returncode, 2)
            raw = '\n'.join([*prefix, claude('Bash', {'command': command}, run.stdout, ident='listing'), *suffix])
            with self.subTest(operand=operand), self.assertRaises(AssertionError):
                check_case('procedure-gaps', 'codex', fixture, raw, [], [], {'mcp_disabled': True, 'effective_mcp': []})

    def test_native_search_checks_entire_tree(self):
        helper = self.root / '.claude/skills/cs-instructions/helper.py'
        helper.write_text('print("source")')
        for name in ('Grep', 'list'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                audit_tools(claude(name, {'path': '.claude/skills', 'pattern': 'source'}, ''), self.root)

    def test_effective_other_host_mcp_requires_real_configuration(self):
        for host, empty, enabled in (('codex', [], [{'enabled': True}]), ('opencode', {}, {'server': {'enabled': True}})):
            require_no_mcp(host, '', {'mcp_disabled': True, 'effective_mcp': empty})
            for config in ({'mcp_disabled': True}, {'mcp_disabled': True, 'effective_mcp': enabled}):
                with self.assertRaises(AssertionError):
                    require_no_mcp(host, '', config)

    def test_actual_catalog_results_control_answer_validation(self):
        requests = [{'id': 1, 'method': 'system.capabilities'},
                    {'id': 2, 'method': 'system.catalog'},
                    {'id': 3, 'method': 'system.catalog', 'params': {'system': 'bank'}}]
        operation = {'method': 'bank.read', 'required': ['date_from'], 'effect': {'changes_state': False, 'paid': False, 'destructive': False, 'returns_secret': False}}
        responses = [{'id': 1, 'result': {'system_catalog': 1}},
                     {'id': 2, 'result': {'version': 1, 'systems': [{'id': 'bank'}]}},
                     {'id': 3, 'result': {'version': 1, 'system': {'id': 'bank'}, 'operations': [operation]}}]
        validate_catalog_journey('reachable', requests, responses, 'bank', 'cs rpc bank.read date_from')
        validate_catalog_journey('named', requests[:2], responses[:2], 'bank', 'The engine route is cs rpc.')
        for answer in ('cs rpc invented.read date_from', 'cs rpc bank.read'):
            with self.assertRaises(AssertionError):
                validate_catalog_journey('reachable', requests, responses, 'bank', answer)
        for broken in ('wrong_id', 'wrong_version', 'mutation', 'error'):
            changed = copy.deepcopy(responses)
            if broken == 'wrong_id':
                changed[0]['id'] = 20
            elif broken == 'wrong_version':
                changed[1]['result']['version'] = 2
            elif broken == 'mutation':
                changed[2]['result']['operations'][0]['effect']['changes_state'] = True
            else:
                changed[2] = {'id': 3, 'error': {'code': -32098}}
            with self.subTest(broken=broken), self.assertRaises(AssertionError):
                validate_catalog_journey('reachable', requests, changed, 'bank', 'cs rpc bank.read date_from')
        validate_catalog_journey('older-engine', requests[:1], [{'id': 1, 'result': {}}], 'bank', 'Cannot list')
        with self.assertRaises(AssertionError):
            validate_catalog_journey('older-engine', requests, responses, 'bank', 'Cannot list')

    def test_cli_network_guard_blocks_before_any_external_connection(self):
        code = """import json, socket, sys
from capabilities_network import restrict_network
restrict_network(sys.argv[1])
listener = socket.socket()
listener.bind(('127.0.0.1', 0))
listener.listen()
client = socket.create_connection(listener.getsockname())
peer, _ = listener.accept()
client.close(); peer.close(); listener.close()
for action in (lambda: socket.getaddrinfo('example.invalid', 443), lambda: socket.socket().connect(('192.0.2.1', 443)), lambda: socket.socket().connect_ex(('192.0.2.1', 443)), lambda: socket.socket(type=socket.SOCK_DGRAM).sendto(b'x', ('192.0.2.1', 53))):
    try:
        action()
    except RuntimeError:
        pass
    else:
        raise AssertionError('External network was not blocked')
print('loopback passed; four external attempts blocked')
"""
        log = self.root / 'network.jsonl'
        run = subprocess.run([sys.executable, '-c', code, str(log)], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('four external attempts blocked', run.stdout)
        self.assertEqual(len(log.read_text().splitlines()), 4)

    def test_standalone_filter_preserves_mixed_groups_and_settings(self):
        from capabilities_claude_settings import filtered_settings
        kit = str(self.root / '.config/mrcall-ai-kit/router-hook.py')
        Path(kit).parent.mkdir(parents=True)
        target = self.root / 'installed-router.py'
        target.write_text('router')
        Path(kit).symlink_to(target)
        retained = {'type': 'command', 'command': '/custom/retained-hook', 'timeout': 20}
        original = {'env': {'TOKEN': 'private-synthetic-value'}, 'permissions': {'allow': ['Bash(true)'], 'deny': ['Write']},
                    'hooks': {'UserPromptSubmit': [{'matcher': '*', 'timeout': 30, 'hooks': [retained, {'type': 'command', 'command': 'python3 ' + kit}]}]}, 'custom': [1, {'value': True}]}
        saved = copy.deepcopy(original)
        filtered, removed = filtered_settings(original, self.root)
        expected = copy.deepcopy(original)
        expected['hooks']['UserPromptSubmit'][0]['hooks'] = [retained]
        self.assertEqual(filtered, expected)
        self.assertEqual(original, saved)
        self.assertEqual(removed[0]['script'], kit)
        self.assertNotIn('private-synthetic-value', json.dumps(removed))

    def test_standalone_filter_refuses_unknown_and_mixed_kit_commands(self):
        from capabilities_claude_settings import filtered_settings
        path = str(self.root / '.config/mrcall-ai-kit/router-hook.py')
        for command in ('python3 ' + path + ' && /custom/retained-hook', 'python3 ' + path + ' extra',
                        'sh -c "python3 ' + path + '"', 'python3 ' + path.replace('router-hook.py', 'unknown.py'),
                        'TOKEN=value python3 ' + path):
            with self.subTest(command=command), self.assertRaises(AssertionError):
                filtered_settings({'hooks': {'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': command}]}]}}, self.root)

    def test_standalone_profile_is_private_and_detects_configuration_drift(self):
        from capabilities_claude_settings import prepare_profile, verify_profile
        home = self.root / 'home'
        (home / '.claude/hooks').mkdir(parents=True)
        hooks = home / '.claude/hooks'
        for name in ('inject-datetime.sh', 'cs-send-gate.py'):
            (hooks / name).write_text('unchanged hook')
        data = {'permissions': {'allow': ['Read'], 'deny': ['Write']}, 'env': {'SECRET': 'synthetic-private'}, 'hooks': {
            'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': str(hooks / 'inject-datetime.sh')}, {'type': 'command', 'command': 'python3 ' + str(home / '.config/mrcall-ai-kit/router-hook.py')}]}],
            'PreToolUse': [{'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': str(hooks / 'cs-send-gate.py')}]}]}}
        source = home / '.claude/settings.json'
        source.write_text(json.dumps(data))
        original = source.read_bytes()
        receipt = prepare_profile(self.root, self.root, home)
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue(verify_profile(receipt)['unchanged'])
        self.assertNotIn('synthetic-private', json.dumps(receipt))
        source.write_text('{}')
        with self.assertRaises(AssertionError):
            verify_profile(receipt)
        source.write_bytes(original)
        Path(receipt['paths']['overlay']).chmod(0o644)
        with self.assertRaises(AssertionError):
            verify_profile(receipt)

    def test_retained_hook_execution_requires_real_exit_and_no_kit_injection(self):
        from capabilities_claude_settings import require_hook_execution, traced_command
        first, second = self.root / 'datetime', self.root / 'send-gate'
        for path in (first, second):
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        receipt = {'paths': {'datetime': str(first), 'send_gate': str(second), 'tracer': shutil.which('strace')}}
        trace = self.root / 'trace'
        command = traced_command(['/bin/sh', '-c', str(first) + '; ' + str(second)], receipt, trace)
        run = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        debug = 'Hook UserPromptSubmit (UserPromptSubmit) success: Now: time'
        proof = require_hook_execution(receipt, debug, trace.read_text(), True)
        self.assertEqual(set(proof), {'datetime', 'send_gate'})
        for bad_debug, bad_trace in ((debug + ' Session memory:', trace.read_text()), (debug, ''), (debug, trace.read_text().replace('exited with 0', 'exited with 1')), (debug, trace.read_text() + f'999999 execve("{second}", [], 0) = 0\n999999 +++ exited with 1 +++\n')):
            with self.assertRaises(AssertionError):
                require_hook_execution(receipt, bad_debug, bad_trace, True)

    def test_effective_claude_mode_and_mcp(self):
        good = {'type': 'system', 'subtype': 'init', 'mcp_servers': [], 'permissionMode': 'manual'}
        require_no_mcp('claude', json.dumps(good), {})
        for update in ({'mcp_servers': ['external']}, {'permissionMode': 'bypassPermissions'}):
            with self.assertRaises(AssertionError):
                require_no_mcp('claude', json.dumps({**good, **update}), {})


if __name__ == '__main__':
    unittest.main()
