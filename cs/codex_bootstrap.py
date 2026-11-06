"""Command-free Codex hook configuration; pure construction and preserving merge."""
from __future__ import annotations

from copy import deepcopy
import re

TOOL = 'cs_bootstrap_hook'
EVENTS = ('SessionStart', 'UserPromptSubmit')


def recipe(server, profile_uid):
    if (not isinstance(server, str) or not 1 <= len(server) <= 128 or server != server.strip()
            or any(ord(c) < 32 or ord(c) > 126 for c in server)
            or not isinstance(profile_uid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', profile_uid)):
        raise ValueError('invalid_codex_bootstrap_binding')
    hooks = {}
    for event in EVENTS:
        values = {'session_id': '${session_id}', 'hook_event': event,
                  'expected_profile_uid': profile_uid}
        if event == 'SessionStart':
            values['source'] = '${source}'
        handler = {'type': 'mcp_tool', 'server': server, 'tool': TOOL, 'input': values,
                   'timeout': 15, 'statusMessage': 'Loading operator context'}
        group = {'hooks': [handler]}
        if event == 'SessionStart':
            group['matcher'] = '^(startup|resume|clear|compact|fork)$'
        hooks[event] = [group]
    return {'version': 1, 'target': '~/.codex/hooks.json', 'server': server,
            'expected_profile_uid': profile_uid, 'hook_fragment': {'hooks': hooks},
            'setup': [
                'Resolve the exact existing MCP server identifier from current Codex configuration/status; do not guess it or add a connection.',
                'Under the administrator\'s explicit setup request, read the existing hooks.json using native local file tools. If absent, start with an empty object. Invalid JSON or incompatible structures must stop without overwriting.',
                'Preserve every unrelated root key, event, matcher and handler. Add the two exact fragment groups; identical existing definitions are a no-op. Conflicting handlers for this same tool/server/profile require review instead of replacement.',
                'Keep a private local backup before an actual edit. Never read or copy credentials. No shell command, script, dependency, local skill or OAuth change is needed.',
                'Review and trust only these two MCP hook definitions through Codex\'s native hook review once. Do not disable trust or change other hooks.',
                'Open a fresh native Codex session and verify the actual bootstrap result. Server retrieval or hook configuration alone is not proof of model-visible context.',
            ],
            'limitations': [
                'Requires this native Codex build to support and trust mcp_tool hooks and the existing server identifier to resolve.',
                'SessionStart can precede MCP readiness; UserPromptSubmit is the retry path. Hook errors do not block the session.',
                'Large hook context can spill to a local Codex temporary file or be previewed. Read the full saved output or call cs_bootstrap before claiming complete rule coverage.',
            ]}


def merge(existing, server, profile_uid):
    """Reference merge for an administrator; never performs a file write."""
    if not isinstance(existing, dict):
        raise ValueError('invalid_existing_hook_configuration')
    result = deepcopy(existing)
    hooks = result.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('invalid_existing_hook_configuration')
    desired = recipe(server, profile_uid)['hook_fragment']['hooks']
    for event, additions in desired.items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError('invalid_existing_hook_configuration')
        found = False
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError('invalid_existing_hook_configuration')
            for handler in group['hooks']:
                if not isinstance(handler, dict):
                    raise ValueError('invalid_existing_hook_configuration')
                if (handler.get('type') == 'mcp_tool' and handler.get('tool') == TOOL
                        and handler.get('server') == server):
                    # A hook for another profile on this server would pollute or
                    # reject the same sessions: refuse rather than overwrite it.
                    if (handler != additions[0]['hooks'][0]
                            or {k: v for k, v in group.items() if k != 'hooks'} !=
                               {k: v for k, v in additions[0].items() if k != 'hooks'} or found):
                        raise ValueError('conflicting_codex_bootstrap_hook')
                    found = True
        if not found:
            groups.extend(deepcopy(additions))
    return result
