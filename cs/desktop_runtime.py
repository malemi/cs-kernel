from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .desktop_managed import ManagedError, check_descriptor, configure, initialize, load_binding, public_status, revoke, status


def main(argv=None):
    parser = argparse.ArgumentParser(prog='cs-operator', description='Desktop-managed company operator runtime')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('desktop-init', 'desktop-status', 'desktop-revoke', 'desktop-configure', 'desktop-export', 'mcp'):
        command = commands.add_parser(name)
        command.add_argument('--workspace', required=True, type=Path)
        if name in ('desktop-init', 'desktop-status'):
            command.add_argument('--descriptor', required=True, type=Path)
        if name == 'desktop-init':
            command.add_argument('--company', required=True)
        if name == 'desktop-export':
            command.add_argument('--provider', required=True, choices=('claude', 'chatgpt'))
            command.add_argument('--runtime', required=True, type=Path)
            command.add_argument('--output', required=True, type=Path)
        if name != 'mcp':
            command.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'mcp':
            from .desktop_mcp import create_server
            create_server(args.workspace).run(transport='stdio')
            return 0
        if args.command == 'desktop-init':
            result = asyncio.run(initialize(args.descriptor, args.workspace, args.company))
        elif args.command == 'desktop-status':
            result = asyncio.run(status(args.descriptor, args.workspace))
        elif args.command == 'desktop-configure':
            raw = sys.stdin.buffer.read(131073)
            if len(raw) > 131072:
                raise ManagedError('invalid_instructions', 'Instruction input exceeds its size limit.')
            try:
                content = json.loads(raw)
            except Exception:
                raise ManagedError('invalid_instructions', 'Instruction input must be valid JSON.') from None
            result = asyncio.run(configure(args.workspace, content))
        elif args.command == 'desktop-revoke':
            result = revoke(args.workspace)
        else:
            from .desktop_packages import export_packages
            binding = load_binding(args.workspace)
            check_descriptor(args.workspace, binding)
            result = {**public_status(args.workspace.absolute(), binding), **export_packages(args.workspace, args.runtime, args.provider, args.output)}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except ManagedError as exc:
        error = {'code': exc.code, 'message': str(exc)}
    except ImportError:
        error = {'code': 'runtime_incomplete', 'message': 'Install the operator runtime with its MCP extra or use the packaged runtime.'}
    except Exception:
        error = {'code': 'operation_failed', 'message': 'Operator setup failed; check the selected profile, workspace permissions, and engine connection.'}
    print(json.dumps({'ok': False, 'error': error}), file=sys.stderr if args.command == 'mcp' else sys.stdout)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
