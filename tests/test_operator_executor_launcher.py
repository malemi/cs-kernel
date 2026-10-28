#!/usr/bin/env python3
"""Execute rendered launchers to prove host selection preserves cron guards.

The private supervisor stub records only invocation and selected headless flags;
it cannot run an agent, load credentials or contact a provider. Real controller
and CLI execution are covered separately by test_operator_executor_integration.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cs import operator_recovery, project_init
from test_render_permissions import BASE, TEMPLATE_ROOT


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.clone = self.base / 'clone with space'
        (self.clone / 'bin').mkdir(parents=True)
        (self.clone / '.venv/bin').mkdir(parents=True)
        self.home = self.base / 'isolated-home'
        self.state = self.home / '.acme-cs'
        self.state.mkdir(parents=True)
        self.capture = self.base / 'calls.jsonl'
        self.env = {**os.environ, 'HOME': str(self.home),
                    'STUB_CAPTURE': str(self.capture),
                    'CLAUDE_BIN': str(self.base / 'not-installed-claude')}
        for key in ('CS_OPERATOR_EXECUTOR', 'CS_OPERATOR_HEADLESS',
                    'CS_HEADLESS_SEND', 'STUB_EXIT'):
            self.env.pop(key, None)
        python = self.clone / '.venv/bin/python'
        python.write_text(f'#!{sys.executable}\n' + '''\
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ['-m', 'cs.observability_producers']:
    if args[2:] == ['start']:
        print('{}')
    raise SystemExit(0)
assert args[:2] == ['-m', 'cs.operator_recovery'], args
record = {'args': args[2:], 'cwd': os.getcwd(),
          'headless': os.environ.get('CS_OPERATOR_HEADLESS'),
          'send': os.environ.get('CS_HEADLESS_SEND'),
          'stdin': sys.stdin.read()}
with Path(os.environ['STUB_CAPTURE']).open('a') as output:
    output.write(json.dumps(record) + '\\n')
raise SystemExit(int(os.environ.get('STUB_EXIT', '0')))
''')
        python.chmod(0o755)
        env = project_init.build_jinja_env(TEMPLATE_ROOT)
        self.script = self.clone / 'bin/cs_operator_cron.sh'
        self.script.write_text(env.get_template('bin/cs_operator_cron.sh.j2').render(**BASE))
        self.script.chmod(0o755)

    def launch(self, **extra):
        return subprocess.run([str(self.script)], cwd=self.base,
                              env={**self.env, **extra}, capture_output=True,
                              text=True, timeout=10)

    def calls(self):
        return ([json.loads(line) for line in self.capture.read_text().splitlines()]
                if self.capture.exists() else [])

    def test_selector_preserves_denies_cwd_stdin_and_exit(self):
        for selected in ('claude', 'pydantic'):
            result = self.launch(CS_OPERATOR_EXECUTOR=selected, STUB_EXIT='7')
            self.assertEqual(result.returncode, 7, result.stderr)
        old, new = self.calls()
        self.assertEqual(old['args'][1:3], ['--executor', 'claude'])
        self.assertEqual(new['args'][1:3], ['--executor', 'pydantic'])
        self.assertEqual(old['args'][3:], new['args'][3:])
        self.assertIn('Bash(.venv/bin/python -m cs draft-send:*)', new['args'][3:])
        for call in (old, new):
            self.assertEqual(call['cwd'], str(self.clone))
            self.assertEqual(call['headless'], '1')
            self.assertIsNone(call['send'])
            self.assertEqual(call['stdin'], '')
        self.assertFalse(Path(new['args'][0]).exists())

    def test_default_pause_and_lock_preserve_admission(self):
        self.assertEqual(self.launch().returncode, 0)
        self.assertEqual(self.calls()[0]['args'][1:3], ['--executor', 'claude'])
        self.capture.unlink()
        pause = self.state / 'CS_PAUSE'
        pause.touch()
        self.assertEqual(self.launch(CS_OPERATOR_EXECUTOR='pydantic').returncode, 0)
        self.assertEqual(self.calls(), [])
        pause.unlink()
        with (self.state / 'cs_operator.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.launch(CS_OPERATOR_EXECUTOR='pydantic').returncode, 0)
            self.assertEqual(self.calls(), [])

    def test_actual_recovery_parser_preserves_send_launcher_arguments(self):
        grants = sorted(operator_recovery.SEND_ALLOW_RULES)
        denies = ['Write', 'Edit', 'Bash(cs campaign send-draft:*)']
        argv = ['operator_recovery', 'unused-claude', '--executor', 'pydantic',
                '--prompt-env', 'CS_OPERATOR_TEST_PROMPT', '--allowed-tools',
                *grants, '--disallowed-tools', *denies]
        with patch.object(sys, 'argv', argv), \
                patch.dict(os.environ, {'CS_OPERATOR_TEST_PROMPT': 'fixture prompt'}), \
                patch.object(operator_recovery, 'run', return_value=23) as run:
            self.assertEqual(operator_recovery.main(), 23)
        self.assertEqual(run.call_args.args, ('unused-claude', denies))
        self.assertEqual(run.call_args.kwargs,
                         {'prompt': 'fixture prompt', 'allows': grants,
                          'executor': 'pydantic'})
        with patch.object(sys, 'argv', ['operator_recovery', 'unused', '--executor', 'unknown']), \
                patch.object(operator_recovery, 'run') as run:
            self.assertEqual(operator_recovery.main(), 1)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
