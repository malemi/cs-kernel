"""Published-rule reader and scheduled confirmation exclusion checks."""
import argparse
import base64
import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cs import standing_instructions as reader
from cs.project_init import build_jinja_env, install_agent_surfaces, TEMPLATE_DEFAULTS
from test_project_update import _FULL_INIT_DATA

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'cs/templates/project'
SETTINGS = SimpleNamespace(email_address='Support@Acme.example')
RENDER = {**TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}


def doc(path='procedures.md', text='Published rule.\n', revision=1):
    raw = text.encode()
    return dict(path=path, revision=revision, sha256=hashlib.sha256(raw).hexdigest(),
                content_base64=base64.b64encode(raw).decode())


def payload(authority='legacy'):
    return dict(authority=authority, space_id='company-space',
                documents=[doc(), doc('mail/support@acme.example.md', 'Sign as Support.\n')])


class ReaderTests(unittest.TestCase):
    def read(self, response, **kw):
        calls = []
        def call(settings, method, params):
            calls.append((method, params))
            return response
        result = reader.read(SETTINGS, call=call, **kw)
        self.assertEqual(calls, [('instructions.preview', {})])
        return result

    def test_legacy_managed_and_updated_remote_revision(self):
        for authority in ('legacy', 'managed'):
            result = self.read(payload(authority))
            self.assertEqual(result['authority'], authority)
            self.assertEqual(result['documents'][1]['text'], 'Published rule.\n')
        response = payload('managed')
        response['documents'][0] = doc(text='New rule.\n', revision=2)
        result = self.read(response)
        self.assertEqual(result['documents'][1]['revision'], 2)
        self.assertEqual(result['documents'][1]['text'], 'New rule.\n')

    def test_empty_legacy_bootstrap_is_only_allowed_for_authority(self):
        response = dict(authority='legacy', space_id='company-space', documents=[])
        self.assertEqual(self.read(response, authority_only=True)['authority'], 'legacy')
        with self.assertRaises(ValueError):
            self.read(response)
        response['authority'] = 'managed'
        with self.assertRaises(ValueError):
            self.read(response, authority_only=True)

    def test_each_missing_applicable_path_holds_normal_and_managed_authority_reads(self):
        for index in range(2):
            response = payload()
            missing = response['documents'].pop(index)['path']
            with self.assertRaisesRegex(ValueError, missing):
                self.read(response)
            self.assertEqual(self.read(response, authority_only=True)['authority'], 'legacy')
            response['authority'] = 'managed'
            with self.assertRaisesRegex(ValueError, missing):
                self.read(response, authority_only=True)

    def test_malformed_foreign_duplicate_oversize_and_failed_integrity_refuse(self):
        cases = []
        for key, value in [('authority', 'unknown'), ('space_id', None), ('documents', None)]:
            response = payload(); response[key] = value; cases.append(response)
        for key, value in [('path', 'mail/foreign@other.example.md'), ('path', '../procedures.md'),
                           ('revision', True), ('revision', 0), ('sha256', '0' * 64),
                           ('content_base64', '%%%'), ('content_base64', '/w=='),
                           ('content_base64', 'A' * (reader.MAX_DOCUMENT_BYTES * 2))]:
            response = payload(); response['documents'][0][key] = value; cases.append(response)
        response = payload(); response['documents'].append(copy.deepcopy(response['documents'][0])); cases.append(response)
        response = payload(); response['documents'] = [doc(text='')]; cases.append(response)
        for response in cases:
            with self.subTest(response=str(response)[:100]), self.assertRaises(ValueError):
                self.read(response)

    def test_read_failure_never_prints_local_fallback(self):
        args = argparse.Namespace(authority_only=False, json=False)
        with patch.object(reader.config, 'load', return_value=SETTINGS), \
             patch.object(reader.rpc, 'call_sync', side_effect=RuntimeError('offline')) as call, \
             redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(reader.cmd_standing_instructions(args), 1)
        self.assertEqual(out.getvalue(), '')
        self.assertIn('offline', err.getvalue())
        self.assertEqual(call.call_count, 1)

    def test_exact_text_printed_once_json_has_validated_metadata(self):
        args = argparse.Namespace(authority_only=False, json=False)
        with patch.object(reader.config, 'load', return_value=SETTINGS), \
             patch.object(reader.rpc, 'call_sync', return_value=payload()), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(reader.cmd_standing_instructions(args), 0)
        self.assertEqual(out.getvalue().count('Published rule.\n'), 1)
        args.json = True
        with patch.object(reader.config, 'load', return_value=SETTINGS), \
             patch.object(reader.rpc, 'call_sync', return_value=payload()), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(reader.cmd_standing_instructions(args), 0)
        self.assertEqual(json.loads(out.getvalue())['mailbox'], 'support@acme.example')

    def test_protected_decisions_denied_in_settings_and_cron_all_six_spellings(self):
        env = build_jinja_env(TEMPLATES)
        settings = json.loads(env.get_template('.claude/settings.json.j2').render(**RENDER))
        cron = env.get_template('bin/cs_operator_cron.sh.j2').render(**RENDER)
        forms = ['.venv/bin/python -m cs', '.venv/bin/python3 -m cs', '.venv/bin/cs',
                 'python -m cs', 'python3 -m cs', 'cs']
        for method in ['operator.rules.decide', 'operator.rules.import_confirm']:
            for form in forms:
                spelling = 'Bash(%s rpc %s:*)' % (form, method)
                self.assertIn(spelling, settings['permissions']['deny'])
                self.assertIn(spelling, cron)
        self.assertFalse(any('standing-instructions' in row for row in settings['permissions']['deny']))



if __name__ == '__main__':
    unittest.main(verbosity=2)
