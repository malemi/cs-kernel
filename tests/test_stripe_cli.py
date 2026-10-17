"""Real CLI over controlled authenticated WebSocket and skill distribution."""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cs import project_init

RUNNER = """
import sys
from cs import config, rpc
settings = config.Settings(_env_file=None, engine_ws_url=sys.argv[1], engine_owner_uid='fixture-owner')
config.load = lambda: settings
rpc.auth.get_id_token = lambda settings: 'controlled-token'
from cs.cli import main
raise SystemExit(main(['stripe', *sys.argv[2:]]))
"""


class StripeCLI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.status = 'connected'
        self.error = None
        self.mode = 'test'
        self.generation = 4
        self.account = 'acct_fixture'
        self.server = await websockets.serve(self.handler, '127.0.0.1', 0)
        self.url = 'ws://127.0.0.1:' + str(self.server.sockets[0].getsockname()[1])

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def handler(self, socket):
        self.assertEqual(socket.request.headers.get('Authorization'), 'Bearer controlled-token')
        self.assertEqual(socket.request.path, '/ws/fixture-owner')
        async for wire in socket:
            frame = json.loads(wire)
            method, params = frame['method'], frame['params']
            self.calls.append((method, params))
            response = {'jsonrpc': '2.0', 'id': frame['id']}
            if self.error:
                response['error'] = {'code': self.error, 'message': 'SECRET provider error', 'data': 'SECRET'}
            elif method == 'stripe.status':
                response['result'] = {'status': self.status, 'generation': 4,
                    'account': {'id': 'acct_fixture', 'name': 'Fixture'}, 'mode': 'test',
                    'capabilities': ['customers', 'payments', 'invoices', 'subscriptions']}
            else:
                row = {'id': params.get('id', 'pi_fixture'), 'amount': 12345678901234567,
                    'currency': 'jpy', 'status': 'succeeded'}
                response['result'] = {'data': row if method == 'stripe.detail' else [row],
                    'has_more': True, 'next_cursor': row['id'], 'retrieved_at_utc': '2026-10-16T00:00:00Z',
                    'account_id': self.account, 'mode': self.mode, 'generation': self.generation}
            await socket.send(json.dumps(response))

    async def command(self, *args, cwd=ROOT, runner=RUNNER):
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', runner, self.url, *args,
            cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(process.communicate(), 15)
        return process.returncode, out.decode(), err.decode()

    async def test_existing_rpc_transport_needs_no_finance_conversation(self):
        runner = RUNNER.replace("main(['stripe',", "main(['rpc',")
        code, out, err = await self.command('stripe.status', runner=runner)
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out)['status'], 'connected')
        code, out, err = await self.command('stripe.invoices', '{"limit":1}', runner=runner)
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out)['account_id'], 'acct_fixture')
        self.assertEqual(self.calls, [('stripe.status', {}), ('stripe.invoices', {'limit': 1})])

    async def test_typed_reads_preserve_exact_money_pagination_and_filters(self):
        for action in ('customers', 'payments', 'invoices', 'subscriptions'):
            filter_args = ['--email', 'person@example.org'] if action == 'customers' else ['--customer', 'cus_fixture']
            code, out, err = await self.command(action, '--limit', '3', '--starting-after', 'cursor', *filter_args)
            self.assertEqual((code, err), (0, ''))
            row = json.loads(out)
            self.assertEqual(row['data'][0]['amount'], 12345678901234567)
            self.assertTrue(row['has_more'])
            self.assertEqual(self.calls[-1], ('stripe.' + action,
                {'limit': 3, 'starting_after': 'cursor', 'email' if action == 'customers' else 'customer': filter_args[-1]}))
        code, out, err = await self.command('detail', 'charges', 'ch_fixture')
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(json.loads(out)['data']['id'], 'ch_fixture')
        self.assertEqual(self.calls[-1], ('stripe.detail', {'resource': 'charges', 'id': 'ch_fixture'}))
        self.assertTrue(all(method.startswith('stripe.') and method not in {'stripe.connect', 'stripe.test'} for method, _ in self.calls))

    async def test_disconnected_old_revoked_and_changed_context_never_disclose(self):
        self.status = 'disconnected'
        code, out, _ = await self.command('customers')
        self.assertEqual(code, 1)
        self.assertIn('Desktop Settings', out)
        self.assertEqual([method for method, _ in self.calls], ['stripe.status'])
        self.status = 'connected'
        for error in (-32601, -32000):
            self.error = error
            code, out, _ = await self.command('customers')
            self.assertEqual(code, 1)
            self.assertNotIn('SECRET', out)
            self.assertIn('Desktop Settings', out)
        self.error = None
        for field, value in (('mode', 'live'), ('generation', 5), ('account', 'acct_other')):
            previous = getattr(self, field)
            setattr(self, field, value)
            code, out, _ = await self.command('customers')
            self.assertEqual(code, 1)
            self.assertNotIn('pi_fixture', out)
            setattr(self, field, previous)

    async def test_invalid_limits_and_write_or_key_verbs_rejected_before_rpc(self):
        for args in (('customers', '--limit', '0'), ('customers', '--limit', '51'),
                     ('connect',), ('refund',), ('detail', 'arbitrary', 'x'), ('customers', '--api-key', 'SECRET')):
            code, out, _ = await self.command(*args)
            self.assertEqual(code, 2)
            self.assertEqual(out, '')
        self.assertEqual(self.calls, [])

    async def test_canonical_skill_distribution_link_and_copy_three_hosts(self):
        from test_project_update import _FULL_INIT_DATA
        template = ROOT / 'cs/templates/project'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for copy in (False, True):
                clone = root / str(copy)
                clone.mkdir()
                with contextlib.redirect_stdout(io.StringIO()):
                    ok, checksums = project_init.render_templates(
                        {**project_init.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}, template, clone)
                    with patch.object(project_init, 'LEGACY_CODEX_PROMPTS', root / 'no-prompts'):
                        if copy:
                            with patch.object(Path, 'symlink_to', side_effect=OSError('unsupported')):
                                project_init.install_agent_surfaces(clone)
                        else:
                            project_init.install_agent_surfaces(clone)
                self.assertTrue(ok)
                self.assertIn('.claude/skills/cs-stripe/SKILL.md', checksums)
                canonical = (clone / '.claude/skills/cs-stripe/SKILL.md').read_bytes()
                for host in ('.claude', '.agents', '.opencode'):
                    path = clone / host / 'skills/cs-stripe/SKILL.md'
                    self.assertEqual(path.read_bytes(), canonical)
                    code, out, err = await self.command('customers', '--email', 'person@example.org')
                    self.assertEqual((code, err), (0, ''))
                    self.assertEqual(json.loads(out)['account_id'], 'acct_fixture')
                bootstrap = (clone / '.claude/skills/cs-bootstrap/SKILL.md').read_text()
                self.assertIn('An advertised capability and its installed system workflow are independent', bootstrap)
                self.assertIn('Missing or unknown general catalog support does not invalidate', bootstrap)
                self.assertIn('existing project-scoped workflow', bootstrap)
                self.assertIn('cs rpc stripe.status', canonical.decode())
                for marker in ('host transcript', 'untrusted evidence', 'shared memory', 'Interactive-only'):
                    self.assertIn(marker, canonical.decode())
                for rel in ('.claude/settings.json', 'bin/cs_operator_cron.sh'):
                    self.assertNotIn('cs-stripe', (clone / rel).read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
