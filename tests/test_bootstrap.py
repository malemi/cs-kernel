"""Shared bootstrap integrity, bounded continuation and authenticated clone adapter."""
import copy
import argparse
import io
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cs import bootstrap
from cs.project_init import build_jinja_env, install_agent_surfaces, TEMPLATE_DEFAULTS
from test_project_update import _FULL_INIT_DATA
from test_standing_instructions import doc

IDENTITY = dict(profile_uid='owner', email='support@acme.example', company_ref='company-space')
SETTINGS = SimpleNamespace(engine_owner_uid='owner', email_address='support@acme.example')


def instructions(text='Current rules.'):
    return dict(status='available', authority='managed', missing_paths=[], documents=[
        dict(path=path, revision=1, sha256=hashlib.sha256(text.encode()).hexdigest(), text=text)
        for path in ('procedures.md', 'mail/support@acme.example.md')])


class BootstrapTests(unittest.TestCase):
    def assemble(self, rules=None, **kw):
        return bootstrap.assemble(IDENTITY, rules or instructions(), ['emails', 'projects'], **kw)

    def test_full_context_exact_rules_and_fresh_digest(self):
        result = self.assemble()
        self.assertTrue(result['coverage']['instructions_complete'])
        self.assertEqual(result['instructions']['documents'][0]['text'], 'Current rules.')
        self.assertNotEqual(result['content_digest'], self.assemble(instructions('Changed.'))['content_digest'])
        self.assertEqual(result['operational_status']['tasks'], 'not_read')
        self.assertIn('customer_history', result['unread_sources'])

    def test_foreign_duplicate_integrity_revision_and_invalid_state_refuse(self):
        for field, value in [('path', 'mail/other@acme.example.md'), ('revision', True), ('sha256', '0'*64), ('text', '\ud800')]:
            row = instructions(); row['documents'][0][field] = value
            with self.subTest(field=field), self.assertRaises((ValueError, UnicodeError)):
                self.assemble(row)
        row = instructions(); row['documents'][1] = copy.deepcopy(row['documents'][0])
        with self.assertRaises(ValueError): self.assemble(row)
        row = instructions(); row['status'] = 'denied'
        with self.assertRaises(ValueError): self.assemble(row)

    def test_denied_unavailable_and_missing_are_explicit(self):
        for status in ('denied', 'unavailable'):
            result = self.assemble(dict(status=status, authority=None, documents=[], missing_paths=[]))
            self.assertFalse(result['coverage']['instructions_complete'])
            self.assertEqual(result['instructions']['documents'], [])
        row = instructions(); removed = row['documents'].pop(); row['missing_paths'] = [removed['path']]; row['status'] = 'missing'
        self.assertFalse(self.assemble(row)['coverage']['instructions_complete'])

    def test_oversize_unicode_and_ascii_escape_are_paged_exactly(self):
        for text in ('x'*20000, '😀'*10000, '\x01'*15000):
            row = instructions(text)
            result = self.assemble(row)
            self.assertFalse(result['coverage']['instructions_complete'])
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=True).encode()), bootstrap.MAX_RESPONSE_BYTES)
            for task in result['next_read']:
                chunks = []; offset = 0
                while offset is not None:
                    page = self.assemble(row, instruction_path=task['instruction_path'], offset=offset, sha256=task['sha256'])['instruction_page']
                    chunks.append(page['text']); offset = page['next_offset']
                self.assertEqual(''.join(chunks), text)

    def test_continuation_rejects_stale_hash_foreign_path_bad_offset(self):
        digest = instructions()['documents'][0]['sha256']
        for kw in [dict(instruction_path='procedures.md', sha256='0'*64), dict(instruction_path='foreign', sha256=digest), dict(offset=1), dict(instruction_path='procedures.md', sha256=digest, offset=True), dict(instruction_path='procedures.md', sha256=digest, offset=10000)]:
            with self.subTest(kw=kw), self.assertRaises(ValueError): self.assemble(**kw)

    def test_adapter_fixed_reads_safe_projection_and_final_identity(self):
        calls = []
        def call(settings, method, params):
            calls.append((method, params))
            if method == 'account.who_am_i': return dict(signed_in=True, uid='owner', email='support@acme.example', secret='never emitted')
            if method == 'instructions.preview': return dict(authority='managed', space_id='company-space', documents=[doc(), doc('mail/support@acme.example.md')])
            return dict(projects=1, config={'secret': 'never emitted'}, token='never emitted')
        result = bootstrap.read(SETTINGS, call=call)
        self.assertEqual(result['capabilities'], ['projects'])
        self.assertNotIn('never emitted', json.dumps(result))
        self.assertEqual([method for method, params in calls], ['account.who_am_i', 'instructions.preview', 'system.capabilities', 'account.who_am_i'])
        self.assertTrue(all(params == {} for method, params in calls))
        count = 0
        def changed(settings, method, params):
            nonlocal count
            value = call(settings, method, params)
            if method == 'account.who_am_i':
                count += 1
                if count == 2: value['uid'] = 'foreign'
            return value
        with self.assertRaises(ValueError): bootstrap.read(SETTINGS, call=changed)

    def test_cli_missing_managed_rules_refuses_without_stale_content(self):
        args = argparse.Namespace(instruction_path=None, offset=0, sha256=None, json=True)
        def call(settings, method, params):
            if method == 'account.who_am_i':
                return dict(signed_in=True, uid='owner', email='support@acme.example')
            return dict(authority='managed', space_id='company-space', documents=[])
        with patch.object(bootstrap.config, 'load', return_value=SETTINGS), patch.object(bootstrap.rpc, 'call_sync', side_effect=call), redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(bootstrap.cmd_bootstrap(args), 1)
        self.assertEqual(out.getvalue(), '')
        self.assertIn('could not be verified', err.getvalue())

    def test_three_host_canonical_skill_and_cli_registration(self):
        templates = Path(__file__).resolve().parents[1] / 'cs/templates/project'
        rendered = build_jinja_env(templates).get_template('.claude/skills/cs-bootstrap/SKILL.md.j2').render(**{**TEMPLATE_DEFAULTS, **_FULL_INIT_DATA})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / '.claude/skills/cs-bootstrap/SKILL.md'
            path.parent.mkdir(parents=True); path.write_text(rendered)
            with patch('cs.project_init._remove_retired_entries', return_value=0): install_agent_surfaces(root)
            self.assertEqual(len({(root / host / 'skills/cs-bootstrap/SKILL.md').read_bytes() for host in ('.claude', '.agents', '.opencode')}), 1)
        import argparse
        parser = argparse.ArgumentParser(); bootstrap.add_subparsers(parser.add_subparsers(dest='cmd'))
        args = parser.parse_args(['bootstrap', '--json'])
        self.assertIs(args.func, bootstrap.cmd_bootstrap)


if __name__ == '__main__': unittest.main(verbosity=2)
