"""Closed, payload-free provider connection diagnostics shared by event readers."""

from __future__ import annotations

import json
import math
import re


_ENUMS = {
    'operation': frozenset('observation connect tls login examine search fetch guard timer abort dispose unknown'.split()),
    'phase': frozenset('enter exit failed armed fired cancelled joined'.split()),
    'command': frozenset(('CAPABILITY', 'LOGIN', 'EXAMINE', 'SELECT', 'UID_SEARCH', 'UID_FETCH', 'NOOP', 'OTHER')),
    'socket_state': frozenset(('absent', 'open', 'closed', 'unknown')),
    'imap_state': frozenset(('DISCONNECTED', 'NONAUTH', 'AUTH', 'SELECTED', 'LOGOUT', 'UNKNOWN')),
    'tls_state': frozenset(('absent', 'negotiating', 'established', 'closed', 'unknown')),
    'cause': frozenset(('none', 'deadline', 'cancelled', 'socket_error', 'protocol_error', 'cleanup', 'normal', 'unknown')),
}
_INTEGERS = {
    'generation': (1, 2147483647, True),
    'sequence': (1, 2147483647, False),
    'operation_id': (1, 2147483647, True),
    'inbound_progress_count': (0, 2147483647, True),
    'pending_tags': (0, 65535, True),
    'pending_commands': (0, 65535, True),
}
_TIMES = frozenset(('offset_ms', 'duration_ms', 'remaining_ms', 'socket_timeout_ms', 'last_inbound_progress_offset_ms'))
_KEYS = frozenset(_ENUMS) | frozenset(_INTEGERS) | _TIMES | frozenset(('version', 'connection_id', 'pin_match', 'deadline_match', 'overflow'))


def validate(value: object) -> dict:
    """Reject incomplete or unsafe observations without inventing missing state."""
    if type(value) is not dict or set(value) != _KEYS:
        raise ValueError('Invalid provider diagnostic shape')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid provider diagnostic version')
    identity = value['connection_id']
    if identity is not None and (type(identity) is not str or re.fullmatch(r'[a-f0-9]{32}', identity) is None):
        raise ValueError('Invalid provider diagnostic identity')
    for key, allowed in _ENUMS.items():
        item = value[key]
        if key == 'command' and item is None:
            continue
        if type(item) is not str or item not in allowed:
            raise ValueError('Invalid provider diagnostic enum')
    for key, (low, high, nullable) in _INTEGERS.items():
        item = value[key]
        if nullable and item is None:
            continue
        if type(item) is not int or not low <= item <= high:
            raise ValueError('Invalid provider diagnostic count')
    for key in _TIMES:
        item = value[key]
        if key != 'offset_ms' and item is None:
            continue
        if type(item) not in (int, float) or not 0 <= item <= 3600000 or not math.isfinite(item):
            raise ValueError('Invalid provider diagnostic timing')
    for key in ('pin_match', 'deadline_match'):
        if value[key] is not None and type(value[key]) is not bool:
            raise ValueError('Invalid provider diagnostic comparison')
    if type(value['overflow']) is not bool:
        raise ValueError('Invalid provider diagnostic overflow')
    if len(json.dumps(value, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')) > 4096:
        raise ValueError('Provider diagnostic exceeds byte limit')
    return dict(value)
