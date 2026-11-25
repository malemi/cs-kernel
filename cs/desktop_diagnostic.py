"""Credential-free connection trial; separate from the managed business server."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import hashlib
from pathlib import Path
from typing import Any
import uuid


def create_server(transport='stdio', port=8766):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    from mcp.server.transport_security import TransportSecuritySettings

    if transport not in ('stdio', 'streamable-http'):
        raise ValueError('Unsupported diagnostic transport')

    class DiagnosticMCP(FastMCP):
        async def call_tool(self, name, arguments):
            if name != 'operator_diagnostic' or arguments:
                raise ValueError('invalid_request: Only operator_diagnostic with no arguments is available.')
            return await super().call_tool(name, arguments)

    server = DiagnosticMCP(
        'Operator connection diagnostic',
        host='127.0.0.1', port=port,
        streamable_http_path='/operator-diagnostic/mcp',
        stateless_http=True, json_response=True,
        max_request_body_size=65536,
        transport_security=TransportSecuritySettings(
            allowed_hosts=['127.0.0.1:*', 'localhost:*'],
            allowed_origins=[],
        ),
        instructions='Use operator_diagnostic to test this actual MCP connection. '
        'Report the returned invocation_id and called_at_utc. '
        'This temporary diagnostic has no authenticated engine, business data or paid tools. '
        'A successful call proves this connection only; Desktop setup and real operator acceptance remain pending.',
    )
    instance = uuid.uuid4().hex
    source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:
        kernel_version = version('cs-kernel')
    except PackageNotFoundError:
        kernel_version = 'not installed; standalone developer helper'

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
    async def operator_diagnostic() -> dict[str, Any]:
        """Test this connection without accessing an account, engine, mailbox or company."""
        return {
            'diagnostic_version': 1,
            'instance_id': instance,
            'invocation_id': uuid.uuid4().hex,
            'called_at_utc': datetime.now(timezone.utc).isoformat(),
            'transport': transport,
            'sdk_version': version('mcp'),
            'kernel_distribution_version': kernel_version,
            'diagnostic_source_sha256': source_sha256,
            'engine_authenticated': False,
            'business_tools_enabled': False,
            'acceptance': 'connection only; real engine and Desktop acceptance pending',
        }

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=('stdio', 'streamable-http'), default='stdio')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    create_server(args.transport, args.port).run(transport=args.transport)


if __name__ == '__main__':
    main()
