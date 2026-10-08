import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from live_instructions_skill import clarification_requested, final_text, native_command, PublicationGuard, publication_guard_state, read_evidenced, require_publication_guard, skill_loaded


class NativeEvidenceTests(unittest.TestCase):
    def test_plain_assertion_is_not_skill_loading(self):
        transcript = json.dumps({'type': 'result', 'result': 'I loaded cs-instructions and published everything.'})
        self.assertFalse(skill_loaded(transcript))

    def test_claude_skill_tool_and_codex_file_read(self):
        request = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'skill-call', 'name': 'Skill', 'input': {'skill': 'cs-instructions'}}]}})
        self.assertFalse(skill_loaded(request))
        reply = json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'skill-call', 'content': 'Loaded skill', 'is_error': False}]}})
        self.assertTrue(skill_loaded(request + '\n' + reply))
        self.assertTrue(skill_loaded(json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'cat .agents/skills/cs-instructions/SKILL.md', 'status': 'completed', 'exit_code': 0}})))

    def test_opencode_skill_and_read_tools(self):
        for tool, inputs in [('skill', {'name': 'cs-instructions'}), ('read', {'filePath': '/fixture/.opencode/skills/cs-instructions/SKILL.md'})]:
            self.assertTrue(skill_loaded(json.dumps({'type': 'tool_use', 'part': {'type': 'tool', 'tool': tool, 'state': {'input': inputs, 'status': 'completed'}}})))

    def test_tool_error_is_not_final_failure_report(self):
        transcript = '\n'.join([json.dumps({'type': 'tool_result', 'content': 'Publication failed'}), json.dumps({'type': 'result', 'result': 'Successfully published'})])
        self.assertEqual(final_text(transcript), 'Successfully published')

    def test_skill_tool_content_is_not_assistant_final_text(self):
        transcript = '\n'.join([json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': [{'type': 'text', 'text': 'Skill instructions say publication failed'}]}]}}), json.dumps({'type': 'result', 'result': 'Actual final answer'})])
        self.assertEqual(final_text(transcript), 'Actual final answer')
        self.assertTrue(clarification_requested('I need to know which one of these rules should apply.'))
        self.assertFalse(clarification_requested('Done.'))

    def test_untrusted_content_must_actually_be_retrieved(self):
        assertion = json.dumps({'type': 'result', 'result': 'I read customer-message.txt'})
        self.assertFalse(read_evidenced(assertion, 'customer-message.txt'))
        actual = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'read-call', 'name': 'Read', 'input': {'file_path': '/fixture/customer-message.txt'}}]}})
        self.assertFalse(read_evidenced(actual, 'customer-message.txt'))
        reply = json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'read-call', 'is_error': False, 'content': 'Customer text'}]}})
        self.assertTrue(read_evidenced(actual + '\n' + reply, 'customer-message.txt'))

    def test_native_process_does_not_inherit_an_open_input_pipe(self):
        module_dir = str(Path(__file__).resolve().parent)
        program = """import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import live_instructions_skill as harness
with tempfile.TemporaryDirectory() as td:
    class Fixture:
        root = Path(td)
        clone = root
        engine_root = root
        env = dict(os.environ)
        sentinels = {}
        def write(self, path, content):
            (self.clone / path).write_text(content)
        def state(self):
            return {'sentinels': {}}
    fixture = Fixture()
    (fixture.root / 'rpc.jsonl').write_text('')
    host = "import json,sys; value=sys.stdin.read(); print(json.dumps({'type':'result','result':'EOF received:'+repr(value)}))"
    harness.native_command = lambda *args: [sys.executable, '-c', host]
    rows = harness.native_cases(fixture, 'codex', 1, (('hypothetical', 'Discuss only', None, None),))
    assert rows[0]['passed'], rows
    assert rows[0]['final_text'] == "EOF received:''", rows
"""
        process = subprocess.Popen([sys.executable, '-c', program, module_dir], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process.wait(timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr.read().decode())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def test_publication_guard_survives_reads_and_rejects_real_tampering(self):
        for mutation in ('remove', 'replace', 'content', 'mode', 'restore-content'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as td:
                guard = Path(td) / 'fail-publication'
                guard.write_bytes(b'original')
                observer = PublicationGuard(guard)
                self.addCleanup(observer.close)
                before = observer.before
                guard.read_bytes()
                require_publication_guard(before, observer.state())
                if mutation == 'remove':
                    guard.unlink()
                elif mutation == 'replace':
                    replacement = guard.with_name('replacement')
                    replacement.write_bytes(b'original')
                    replacement.chmod(guard.stat().st_mode)
                    replacement.replace(guard)
                elif mutation == 'content':
                    guard.write_bytes(b'changed')
                elif mutation == 'mode':
                    guard.chmod(guard.stat().st_mode ^ 0o100)
                else:
                    guard.write_bytes(b'changed')
                    guard.write_bytes(b'original')
                with self.assertRaisesRegex(AssertionError, 'changed the publication-failure control'):
                    require_publication_guard(before, observer.state())

    def test_host_commands_preserve_native_discovery(self):
        from pathlib import Path
        for host in ('claude', 'codex', 'opencode'):
            command = native_command(host, Path('/fixture'), 'ordinary user request')
            self.assertEqual(command[0], host)
            self.assertNotIn('--bare', command)
            self.assertNotIn('--dangerously-skip-permissions', command)
            self.assertNotIn('resume', command)
            if host == 'claude':
                self.assertIn('--allowedTools', command)
                self.assertIn('--permission-prompts', command)
                self.assertIn('none', command)
                self.assertNotIn('bypassPermissions', command)
            if host == 'codex':
                self.assertIn('workspace-write', command)
                self.assertIn('sandbox_workspace_write.network_access=true', command)
                self.assertNotIn('danger-full-access', command)


if __name__ == '__main__':
    unittest.main(verbosity=2)
