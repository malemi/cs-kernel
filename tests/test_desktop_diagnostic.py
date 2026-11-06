"""Exercise the isolated diagnostic through actual SDK subprocess transport."""

import asyncio
from datetime import datetime
import hashlib
import json
import os
import socket
import subprocess

import httpx
from mcp.client.streamable_http import streamable_http_client
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SOURCE = Path(__file__).resolve().parents[1] / 'cs' / 'desktop_diagnostic.py'


class DiagnosticTest(unittest.TestCase):
    def test_isolated_actual_transport(self):
        asyncio.run(self.exercise())

    def test_actual_http_transport(self):
        asyncio.run(self.exercise_http())

    async def exercise_http(self):
        with tempfile.TemporaryDirectory(prefix='diagnostic-http-') as directory:
            root = Path(directory)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            env = {**os.environ, 'ZYLCH_HOME': str(root / 'absent-profile'),
                   'FIREBASE_REFRESH_TOKEN': 'secret-canary',
                   'CS_ENGINE_URL': 'wss://must-not-connect.invalid'}
            process = subprocess.Popen(
                [sys.executable, str(SOURCE), '--transport', 'streamable-http', '--port', str(port)],
                env=env, cwd=directory, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            url = f'http://127.0.0.1:{port}/operator-diagnostic/mcp'
            try:
                async with httpx.AsyncClient(timeout=2) as http:
                    for attempt in range(100):
                        if process.poll() is not None:
                            self.fail('HTTP diagnostic exited before readiness')
                        try:
                            await http.get(url)
                            break
                        except httpx.ConnectError:
                            await asyncio.sleep(0.05)
                    else:
                        self.fail('HTTP diagnostic readiness timed out')
                    self.assertEqual((await http.get(url, headers={'Host': 'foreign.invalid'})).status_code, 421)
                    self.assertEqual((await http.get(url, headers={'Host': 'desktop.mrcall.ai'})).status_code, 421)
                    self.assertEqual((await http.get(url, headers={'Origin': 'https://desktop.mrcall.ai'})).status_code, 403)
                    self.assertEqual((await http.get(url, headers={'Origin': 'https://foreign.invalid'})).status_code, 403)
                    self.assertEqual((await http.post(url, content=b'x' * 65537,
                        headers={'Content-Type': 'application/json'})).status_code, 413)
                    self.assertEqual((await http.get(f'http://127.0.0.1:{port}/mcp')).status_code, 404)
                    async with streamable_http_client(url, http_client=http) as (read, write, _):
                        async with ClientSession(read, write) as client:
                            await client.initialize()
                            self.assertEqual([t.name for t in (await client.list_tools()).tools], ['operator_diagnostic'])
                            first = await client.call_tool('operator_diagnostic', {})
                            second = await client.call_tool('operator_diagnostic', {})
                            self.assertFalse(first.isError)
                            self.assertFalse(second.isError)
                            one, two = first.structuredContent, second.structuredContent
                            self.assertEqual(one['transport'], 'streamable-http')
                            self.assertEqual(one['instance_id'], two['instance_id'])
                            self.assertNotEqual(one['invocation_id'], two['invocation_id'])
                            datetime.fromisoformat(one['called_at_utc'])
                            self.assertFalse(one['engine_authenticated'])
                            self.assertFalse(one['business_tools_enabled'])
                            for value in ('secret-canary', str(root), 'must-not-connect'):
                                self.assertNotIn(value, json.dumps(one))
                            for tool in ('prepare_reply', 'operator_context', 'propose_rule', 'send_mail'):
                                self.assertTrue((await client.call_tool(tool, {})).isError)
                            self.assertTrue((await client.call_tool('operator_diagnostic', {'profile': 'other'})).isError)
                            self.assertEqual((await client.list_resources()).resources, [])
                            self.assertEqual((await client.list_prompts()).prompts, [])
                self.assertEqual(list(root.iterdir()), [])
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    async def exercise(self):
        with tempfile.TemporaryDirectory(prefix='diagnostic unrelated directory ') as directory:
            root = Path(directory)
            env = {**os.environ, 'ZYLCH_HOME': str(root / 'absent-profile'),
                   'CS_COMPANY_NAME': 'private-company-canary',
                   'FIREBASE_REFRESH_TOKEN': 'secret-canary',
                   'CS_ENGINE_URL': 'wss://must-not-connect.invalid'}
            params = StdioServerParameters(command=sys.executable, args=[str(SOURCE)], env=env, cwd=directory)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    initialized = await client.initialize()
                    self.assertIn('connection only', initialized.instructions)
                    catalog = await client.list_tools()
                    self.assertEqual([tool.name for tool in catalog.tools], ['operator_diagnostic'])
                    self.assertTrue(catalog.tools[0].annotations.readOnlyHint)
                    one = await client.call_tool('operator_diagnostic', {})
                    two = await client.call_tool('operator_diagnostic', {})
                    self.assertFalse(one.isError)
                    self.assertFalse(two.isError)
                    first, second = one.structuredContent, two.structuredContent
                    self.assertEqual(first['instance_id'], second['instance_id'])
                    self.assertNotEqual(first['invocation_id'], second['invocation_id'])
                    datetime.fromisoformat(first['called_at_utc'])
                    self.assertEqual(first['diagnostic_source_sha256'], hashlib.sha256(SOURCE.read_bytes()).hexdigest())
                    self.assertFalse(first['engine_authenticated'])
                    self.assertFalse(first['business_tools_enabled'])
                    self.assertEqual(first['transport'], 'stdio')
                    encoded = json.dumps(first)
                    for value in ('private-company-canary', 'secret-canary', str(root), 'must-not-connect'):
                        self.assertNotIn(value, encoded)
                    for tool in ('prepare_reply', 'operator_context', 'propose_rule', 'send_mail'):
                        refused = await client.call_tool(tool, {})
                        self.assertTrue(refused.isError)
                    refused = await client.call_tool('operator_diagnostic', {'profile': 'other-person'})
                    self.assertTrue(refused.isError)
                    self.assertEqual((await client.list_resources()).resources, [])
                    self.assertEqual((await client.list_prompts()).prompts, [])
            self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
