from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import websockets
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cs import auth
from cs.desktop_managed import ManagedError, configure, initialize, revoke, status, workspace_lock
from cs.desktop_mcp import Operator

ROOT = Path(__file__).resolve().parents[1]
UID = 'fixture-actor'
TOKEN = 'fixture-refresh-secret'


class TokenHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        data = json.dumps({'user_id': UID, 'id_token': 'fixture-id-token'}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class Fixture:
    def __init__(self):
        self.calls = []
        self.actor = UID
        self.space = 'fixture-company'
        self.hold = False
        self.bad_draft = False
        self.policy = True
        self.chat_error = False
        self.drafts = 0
        self.docs = {}
        self.draft_rows = []
        self.publish_failure = False
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), TokenHandler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    async def __aenter__(self):
        self.server = await websockets.serve(self.handle, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.exchange = f'http://127.0.0.1:{self.http.server_port}/token?key={{key}}'
        return self

    async def __aexit__(self, *exc):
        self.server.close()
        await self.server.wait_closed()
        self.http.shutdown()
        self.http.server_close()

    async def handle(self, socket):
        assert socket.request.headers['Authorization'] == 'Bearer fixture-id-token'
        async for raw in socket:
            frame = json.loads(raw)
            name, params = frame['method'], frame['params']
            self.calls.append((name, params))
            if name == 'account.who_am_i':
                result = {'signed_in': True, 'uid': self.actor}
            elif name == 'setup.state':
                result = {'mailbox_ready': True}
            elif name == 'system.capabilities':
                result = {'chat_read_only_policy': 1, 'contextual_email_policy': 1, 'assignment_draft_policy': 1} if self.policy else {}
            elif name == 'projects.read':
                data = self.docs.get(params['path'])
                if data is None:
                    await socket.send(json.dumps({'jsonrpc': '2.0', 'id': frame['id'], 'error': {'code': -32044, 'message': TOKEN}}))
                    continue
                result = {'space_id': self.space, 'project': params['project'], 'path': params['path'], 'revision': 1,
                          'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'author_uid': UID, 'created_at': '2026-10-08',
                          'content_base64': base64.b64encode(data).decode()}
            elif name == 'instructions.store':
                if self.publish_failure and params['path'] == 'phone.md':
                    await socket.send(json.dumps({'jsonrpc': '2.0', 'id': frame['id'], 'error': {'code': -32040, 'message': TOKEN}}))
                    continue
                data = base64.b64decode(params['content_base64'])
                self.docs[params['path']] = data
                result = {'space_id': self.space, 'project': 'operator-instructions', 'path': params['path'], 'revision': 1,
                          'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'author_uid': UID, 'created_at': '2026-10-08'}
            elif name == 'drafts.list':
                result = self.draft_rows
            elif name == 'emails.list_by_thread':
                result = {'emails': [{'id': 'source-1', 'subject': 'Fixture source', 'body_plain': 'Please help', 'is_user_sent': False}]}
            elif name == 'tasks.list':
                result = [{'id': 'fixture-task', 'title': 'Reply to fixture'}]
            elif name == 'emails.search':
                result = {'threads': [{'thread_id': '<fixture-thread>', 'source_email_id': 'source-1'}]}
            elif name == 'projects.list':
                result = {'space_id': self.space, 'items': [], 'total': 0, 'offset': 0, 'limit': params['limit']}
            elif name == 'chat.send':
                if self.hold:
                    await socket.send(json.dumps({'jsonrpc': '2.0', 'id': frame['id'], 'error': {'code': -32062, 'message': TOKEN}}))
                    continue
                if 'email_context' in params:
                    self.drafts += 1
                    self.draft_rows.append({'id': 'draft-' + str(self.drafts), 'status': 'draft', 'thread_id': '<fixture-thread>',
                        'in_reply_to': '<fixture-message>', 'to_addresses': ['customer@fixture.test'], 'body': 'Grounded fixture reply',
                        'reply_binding': {'root': '<fixture-thread>', 'target': '<fixture-message>', 'source': {'id': 'wrong-source' if self.bad_draft else 'source-1'}}})
                    assert params['email_context'] == {'thread_key': '<fixture-thread>', 'source_email_id': 'source-1'}
                    assert params['assignment_policy_version'] == 1
                    assert params['assignment_thread_key'] == '<fixture-thread>'
                else:
                    assert params['mutation_policy'] == 'read_only'
                result = {'response': 'A grounded fixture draft', 'metadata': {'error': 'fixture-refusal'}} if self.chat_error else {'response': 'Fixture answer ' + TOKEN}
            else:
                raise AssertionError(name)
            await socket.send(json.dumps({'jsonrpc': '2.0', 'id': frame['id'], 'result': result}))


class ManagedTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.profile = self.home / 'profiles' / UID
        self.profile.mkdir(parents=True)
        self.descriptor = self.profile / 'cs-descriptor.json'
        self.workspace = self.profile / 'operator-workspace'
        self.fixture = await Fixture().__aenter__()
        self.descriptor.write_text(json.dumps({'version': 1, 'uid': UID, 'email': 'operator@fixture.test',
            'engine_ws_url': f'ws://127.0.0.1:{self.fixture.port}/ws/{UID}', 'firebase_web_api_key': 'fixture-api-key', 'refresh_token': TOKEN}))
        self.environment = patch.dict(os.environ, {'HOME': str(self.home), 'CS_ENGINE_OWNER_UID': 'wrong-ambient', 'ENGINE_WS_URL': 'wss://wrong.test', 'EMAIL_PASSWORD': 'ambient-mail-secret'})
        self.environment.start()
        self.exchange = patch.object(auth, '_SECURE_TOKEN_URL', self.fixture.exchange)
        self.exchange.start()

    async def asyncTearDown(self):
        self.exchange.stop()
        self.environment.stop()
        await self.fixture.__aexit__()
        self.temp.cleanup()

    async def init(self):
        return await initialize(self.descriptor, self.workspace, 'Fixture Company')

    def authored(self):
        for path, data, local in [('procedures.md', b'Answer using fixture evidence only.\n', 'customer-service-playbook.md'),
                                  ('mail/operator@fixture.test.md', b'Identify as the fixture operator.\n', 'mailbox-identity.md')]:
            (self.workspace / 'company' / local).write_bytes(data)
            self.fixture.docs[path] = data
            if path == 'procedures.md':
                self.fixture.docs['phone.md'] = data

    async def test_managed_preserves_authored_and_scopes(self):
        result = await self.init()
        self.assertEqual(result['uid'], UID)
        self.authored()
        before = (self.workspace / 'company/customer-service-playbook.md').read_bytes()
        await self.init()
        self.assertEqual((self.workspace / 'company/customer-service-playbook.md').read_bytes(), before)
        await status(self.descriptor, self.workspace)
        self.assertNotIn(TOKEN, ''.join(p.read_text() for p in self.workspace.rglob('*') if p.is_file()))
        self.assertFalse((self.home / '.desktop-managed-cs').exists())
        self.assertFalse(any(name == 'settings.get_secret' for name, _ in self.fixture.calls))
        self.fixture.actor = 'wrong-actor'
        with self.assertRaises(ManagedError):
            await Operator(self.workspace).invoke('list_tasks', {'limit': 10})

    async def test_path_and_reuse_refusals(self):
        with self.assertRaises(ManagedError):
            await initialize(self.descriptor, self.home / 'escape', 'Fixture')
        await self.init()
        with self.assertRaises(ManagedError):
            await initialize(self.descriptor, self.workspace, 'Other Company')
        link = self.profile / 'link'
        link.symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaises(Exception):
            Operator(link)
        with workspace_lock(self.workspace):
            with self.assertRaises(ManagedError):
                await self.init()

    async def test_policy_source_publication_idempotency_revocation(self):
        await self.init()
        op = Operator(self.workspace)
        payload = {'thread_key': '<fixture-thread>', 'source_email_id': 'source-1', 'instruction': 'Draft the fixture answer', 'operation_id': 'fixture-operation'}
        with self.assertRaises(ManagedError):
            await op.invoke('prepare_reply', payload)
        self.authored()
        context = await op.invoke('operator_context', {})
        self.assertTrue(all(row['publication'] == 'current' for row in context['instructions']))
        self.fixture.policy = False
        with self.assertRaises(ManagedError):
            await op.invoke('prepare_reply', payload)
        self.fixture.policy = True
        with self.assertRaises(ManagedError):
            await op.invoke('prepare_reply', {**payload, 'source_email_id': 'wrong-source'})
        first = await op.invoke('prepare_reply', payload)
        second = await op.invoke('prepare_reply', payload)
        self.assertEqual(first, second)
        self.assertEqual(self.fixture.drafts, 1)
        self.assertNotIn(TOKEN, json.dumps(first))
        with self.assertRaises(ManagedError):
            await op.invoke('prepare_reply', {**payload, 'instruction': 'different'})
        self.fixture.chat_error = True
        with self.assertRaises(ManagedError):
            await op.invoke('ask_operator', {'question': 'What needs attention?'})
        revoke(self.workspace)
        with self.assertRaises(ManagedError):
            await op.invoke('list_tasks', {'limit': 5})
        await self.init()
        with self.assertRaises(ManagedError):
            await op.invoke('list_tasks', {'limit': 5})

    async def test_configure_publishes_and_recovers_partial_failure(self):
        await self.init()
        content = {'procedures': 'Use exact fixture source evidence.', 'mailbox_identity': 'Identify as fixture operator.'}
        self.fixture.publish_failure = True
        with self.assertRaises(ManagedError):
            await configure(self.workspace, content)
        self.assertEqual((self.workspace / 'company/customer-service-playbook.md').read_text(), content['procedures'])
        self.fixture.publish_failure = False
        result = await configure(self.workspace, content)
        self.assertEqual(result['publication'], 'current')
        self.assertEqual({row['path'] for row in result['instructions']}, {'procedures.md', 'phone.md', 'mail/operator@fixture.test.md'})
        with self.assertRaises(ManagedError):
            await configure(self.workspace, {**content, 'path': '/arbitrary'})
        with self.assertRaises(ManagedError):
            await configure(self.workspace, {**content, 'procedures': '## What to write here'})
        self.assertFalse(any(method == 'projects.write' for method, _ in self.fixture.calls))

    async def test_company_scope_and_uncertain_draft_refuse_replay(self):
        await self.init()
        self.authored()
        operator = Operator(self.workspace)
        self.fixture.space = 'different-company'
        with self.assertRaises(ManagedError):
            await operator.invoke('list_tasks', {'limit': 5})
        self.fixture.space = 'fixture-company'
        payload = {'thread_key': '<fixture-thread>', 'source_email_id': 'source-1', 'instruction': 'Draft fixture reply', 'operation_id': 'held-operation'}
        self.fixture.hold = True
        with self.assertRaises(ManagedError):
            await operator.invoke('prepare_reply', payload)
        self.assertEqual(self.fixture.drafts, 0)
        self.fixture.hold = False
        with self.assertRaises(ManagedError) as caught:
            await operator.invoke('prepare_reply', payload)
        self.assertEqual(caught.exception.code, 'outcome_unknown')
        self.fixture.bad_draft = True
        with self.assertRaises(ManagedError) as caught:
            await operator.invoke('prepare_reply', {**payload, 'operation_id': 'wrong-draft-operation'})
        self.assertEqual(caught.exception.code, 'draft_unverified')
        self.assertNotIn(TOKEN, str(caught.exception))

    async def test_concurrent_clients_create_one_draft(self):
        await self.init()
        self.authored()
        payload = {'thread_key': '<fixture-thread>', 'source_email_id': 'source-1', 'instruction': 'Draft fixture reply', 'operation_id': 'concurrent-operation'}
        first, second = Operator(self.workspace), Operator(self.workspace)
        results = await asyncio.gather(first.invoke('prepare_reply', payload), second.invoke('prepare_reply', payload), return_exceptions=True)
        self.assertTrue(any(isinstance(result, dict) for result in results), results)
        self.assertEqual(self.fixture.drafts, 1)
        recovered = await second.invoke('prepare_reply', payload)
        self.assertEqual(recovered['draft']['id'], 'draft-1')
        self.assertEqual(self.fixture.drafts, 1)
        self.descriptor.unlink()
        with self.assertRaises(ManagedError):
            await first.invoke('list_tasks', {'limit': 5})

    async def test_process_exit_releases_workspace_lock(self):
        await self.init()
        child = "import os,sys;from pathlib import Path;from cs.desktop_managed import workspace_lock;lock=workspace_lock(Path(sys.argv[1]));lock.__enter__();os._exit(0)"
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', child, str(self.workspace), env={**os.environ, 'PYTHONPATH': str(ROOT)})
        self.assertEqual(await process.wait(), 0)
        await self.init()
        with workspace_lock(self.workspace):
            self.assertTrue((self.profile / '.operator-workspace.init-lock').is_file())

    async def test_real_managed_cli(self):
        bootstrap = "import sys;from cs import auth;auth._SECURE_TOKEN_URL=sys.argv[1];from cs.desktop_runtime import main;raise SystemExit(main(sys.argv[2:]))"
        async def command(*args, content=None):
            process = await asyncio.create_subprocess_exec(sys.executable, '-c', bootstrap, self.fixture.exchange, *args,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env={**os.environ, 'HOME': str(self.home), 'PYTHONPATH': str(ROOT)})
            stdout, stderr = await process.communicate(json.dumps(content).encode() if content else None)
            self.assertNotIn(TOKEN.encode(), stdout + stderr)
            return process.returncode, json.loads(stdout)
        code, created = await command('desktop-init', '--descriptor', str(self.descriptor), '--workspace', str(self.workspace), '--company', 'Fixture Company', '--json')
        self.assertEqual(code, 0, created)
        code, configured = await command('desktop-configure', '--workspace', str(self.workspace), '--json', content={'procedures': 'Follow exact fixture evidence.', 'mailbox_identity': 'Sign as fixture operator.'})
        self.assertEqual(code, 0, configured)
        self.assertTrue(configured['instructions_ready'])
        code, ready = await command('desktop-status', '--descriptor', str(self.descriptor), '--workspace', str(self.workspace), '--json')
        self.assertEqual(code, 0, ready)
        self.assertTrue(ready['instructions_ready'])
        self.assertEqual(ready['configuration']['procedures'], 'Follow exact fixture evidence.')
        code, revoked = await command('desktop-revoke', '--workspace', str(self.workspace), '--json')
        self.assertEqual(code, 0, revoked)
        self.assertEqual(revoked['state'], 'revoked')

    @unittest.skipUnless(os.environ.get('CANDIDATE_RUNTIME'), 'Standalone candidate not selected')
    async def test_standalone_sdk_discovery(self):
        await self.init()
        parameters = StdioServerParameters(command=os.environ['CANDIDATE_RUNTIME'], args=['mcp', '--workspace', str(self.workspace)],
            env={'HOME': str(self.home), 'PATH': '/nonexistent'})
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertIn('prepare_reply', {tool.name for tool in tools.tools})
                revoke(self.workspace)
                self.assertTrue((await session.call_tool('list_tasks', {})).isError)

    async def test_official_sdk_real_stdio(self):
        await self.init()
        self.authored()
        bootstrap = "import sys;from cs import auth;auth._SECURE_TOKEN_URL=sys.argv[1];from cs.desktop_runtime import main;raise SystemExit(main(sys.argv[2:]))"
        parameters = StdioServerParameters(command=sys.executable, args=['-c', bootstrap, self.fixture.exchange, 'mcp', '--workspace', str(self.workspace)],
            env={'HOME': str(self.home), 'PATH': os.environ['PATH'], 'PYTHONPATH': str(ROOT), 'CS_ENGINE_OWNER_UID': 'wrong-ambient'})
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                self.assertIn('operator_context', initialized.instructions)
                tools = await session.list_tools()
                self.assertEqual({tool.name for tool in tools.tools}, {'operator_context', 'list_tasks', 'search_email', 'read_email', 'list_projects', 'read_project', 'list_drafts', 'ask_operator', 'prepare_reply'})
                for name, args in [('operator_context', {}), ('list_tasks', {'limit': 5}), ('search_email', {'query': 'fixture'}),
                                   ('read_email', {'thread_key': '<fixture-thread>', 'source_email_id': 'source-1'}),
                                   ('list_projects', {}), ('list_drafts', {}), ('read_project', {'project': 'operator-instructions', 'path': 'procedures.md'}),
                                   ('ask_operator', {'question': 'What needs attention?'}),
                                   ('prepare_reply', {'thread_key': '<fixture-thread>', 'source_email_id': 'source-1', 'instruction': 'Draft using fixture rules', 'operation_id': 'sdk-operation'})]:
                    result = await session.call_tool(name, args)
                    self.assertFalse(result.isError, (name, result))
                    self.assertNotIn(TOKEN, result.model_dump_json())
                resources = await session.list_resources()
                self.assertEqual(str(resources.resources[0].uri), 'operator://guidance')
                await session.read_resource('operator://guidance')
                for args in ({'limit': 101}, {'limit': 5, 'workspace': '/other'}, {'limit': '5'}):
                    result = await session.call_tool('list_tasks', args)
                    self.assertTrue(result.isError)
                self.fixture.policy = False
                self.assertTrue((await session.call_tool('ask_operator', {'question': 'Question?'})).isError)
                self.fixture.policy = True
                revoke(self.workspace)
                self.assertTrue((await session.call_tool('list_tasks', {})).isError)


if __name__ == '__main__':
    unittest.main()
