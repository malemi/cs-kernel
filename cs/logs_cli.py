"""Read-only operator access to local and authenticated remote diagnostic evidence."""
from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request

from . import config, rpc
from .observability import MAX_RESPONSE_BYTES, LEVELS, event_level, store_for


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_remote(settings, view: str, result: dict) -> dict:
    """Refuse malformed remote metadata before any display or analyst input."""
    import math
    import re
    from types import SimpleNamespace
    from .observability_store import _parse_cursor, _validate_event

    def integer(value, maximum=2**53-1):
        return type(value) is int and 0 <= value <= maximum

    def stamp(value):
        return value is None or (type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10**12)

    def path(value, *, pattern=False):
        if not isinstance(value, str) or not 1 <= len(value) <= 4096 or not value.startswith('/'):
            return False
        expression = r"/[A-Za-z0-9_./+@ -]+" if not pattern else r"/[A-Za-z0-9_./+@ *-]+"
        return re.fullmatch(expression, value) is not None and not {'..', '.'}.intersection(value.split('/'))

    common = {'schema_version', 'owner_uid', 'component'}
    if not isinstance(result, dict) or type(result.get('schema_version')) is not int or result['schema_version'] != 1 or result.get('owner_uid') != settings.engine_owner_uid or result.get('component') != 'engine':
        raise ValueError('diagnostic owner mismatch')
    coverage_keys = common | {'status', 'available', 'failed_writes', 'dropped_events', 'gaps', 'oldest_at', 'newest_at', 'bytes', 'scanned_bytes', 'continuation_required', 'logging'}

    def validate_coverage(value):
        if not isinstance(value, dict) or set(value)-coverage_keys:
            raise ValueError('invalid diagnostic coverage')
        if value.get('status') not in ('observed', 'absent', 'degraded', 'unavailable', 'unsupported') or type(value.get('available')) is not bool:
            raise ValueError('invalid diagnostic coverage state')
        for name in common.intersection(value):
            if value[name] != result[name] or type(value[name]) is not type(result[name]):
                raise ValueError('diagnostic coverage owner mismatch')
        for name in ('failed_writes', 'dropped_events', 'bytes', 'scanned_bytes'):
            if name in value and not integer(value[name]):
                raise ValueError('invalid diagnostic count')
        for name in ('oldest_at', 'newest_at'):
            if name in value and not stamp(value[name]):
                raise ValueError('invalid diagnostic timestamp')
        if 'continuation_required' in value and type(value['continuation_required']) is not bool:
            raise ValueError('invalid diagnostic continuation')
        if 'logging' in value:
            from .observability_logging import validate_logging

            validate_logging(value['logging'])
        gaps = value.get('gaps')
        if not isinstance(gaps, list) or len(gaps) > 32:
            raise ValueError('invalid diagnostic gaps')
        for gap in gaps:
            if not isinstance(gap, dict) or set(gap)-{'reason', 'count', 'evicted_segments', 'last_eviction_at'}:
                raise ValueError('invalid diagnostic gap')
            if gap.get('reason') not in ('retention', 'retention-expired', 'cursor-evicted', 'cursor-truncated', 'malformed-event', 'unreadable', 'logging', 'response-limit', 'recent-window-limit'):
                raise ValueError('invalid diagnostic gap reason')
            for key in ('count', 'evicted_segments'):
                if key in gap and not integer(gap[key]):
                    raise ValueError('invalid diagnostic gap count')
            if 'last_eviction_at' in gap and not stamp(gap['last_eviction_at']):
                raise ValueError('invalid diagnostic gap timestamp')

    if view == 'events':
        if set(result)-common-{'events', 'next_cursor', 'coverage'}:
            raise ValueError('unknown diagnostic fields')
        events = result.get('events')
        if not isinstance(events, list) or len(events) > 200 or not all(_validate_event(e, SimpleNamespace(owner_uid=settings.engine_owner_uid)) and e['component'] == 'engine' for e in events):
            raise ValueError('invalid diagnostic events')
        for event in events:
            event.setdefault('level', event_level(event))
        if result.get('next_cursor') is not None:
            _parse_cursor(result['next_cursor'])
        validate_coverage(result.get('coverage'))
    elif view == 'health':
        validate_coverage(result)
    elif view == 'locations':
        if set(result)-common-{'package_root', 'version', 'source_digest', 'source_digest_scope', 'workflow_revision', 'pid', 'process_start', 'root', 'events', 'coverage', 'legacy_log', 'native_log_root', 'legacy_retention_days', 'legacy_max_bytes', 'log_level'}:
            raise ValueError('unknown diagnostic fields')
        if 'log_level' in result and (not isinstance(result['log_level'], str) or result['log_level'] not in LEVELS):
            raise ValueError('invalid diagnostic log threshold')
        if not all(path(result.get(key), pattern=key == 'events') for key in ('package_root', 'root', 'events')):
            raise ValueError('invalid diagnostic location')
        for name in ('legacy_log', 'native_log_root'):
            if name in result and not path(result[name]):
                raise ValueError('invalid diagnostic legacy location')
        for name in ('legacy_retention_days', 'legacy_max_bytes'):
            if name in result and not integer(result[name]):
                raise ValueError('invalid diagnostic retention budget')
        if not isinstance(result.get('version'), str) or not re.fullmatch(r'[a-zA-Z0-9.+_-]{1,80}', result['version']):
            raise ValueError('invalid diagnostic version')
        if result.get('source_digest_scope') != 'observability-module' or not isinstance(result.get('source_digest'), str) or not re.fullmatch(r'[a-f0-9]{64}', result['source_digest']):
            raise ValueError('invalid diagnostic source')
        if result.get('workflow_revision') is not None and (not isinstance(result['workflow_revision'], str) or not re.fullmatch(r'[a-f0-9]{64}', result['workflow_revision'])):
            raise ValueError('invalid diagnostic revision')
        if not integer(result.get('pid')) or result.get('process_start') is not None and (not isinstance(result['process_start'], str) or not re.fullmatch(r'[0-9]{1,32}', result['process_start'])):
            raise ValueError('invalid diagnostic process')
        validate_coverage(result.get('coverage'))
    else:
        raise ValueError('invalid diagnostic view')
    if len(json.dumps(result, allow_nan=False).encode()) > MAX_RESPONSE_BYTES:
        raise ValueError('diagnostic response exceeds byte limit')
    return result


def reader_read(settings, view: str, params: dict) -> dict:
    """Read the independent HTTPS reader without leaking credentials on redirects."""
    binding = getattr(settings, "observability", None)
    if binding is None or not binding.reader_url:
        return {'coverage': {'status': 'unsupported', 'available': False, 'gaps': [{'reason': 'reader-not-configured'}]}}
    credential = getattr(config, "observability_credential", None)
    if not callable(credential):
        raise ValueError("Independent reader credentials unavailable")
    token = credential(settings)
    query = urllib.parse.urlencode({key: str(value).lower() if type(value) is bool else value
                                    for key, value in params.items() if value is not None})
    url = binding.reader_url.rstrip('/') + '/' + view + ('?' + query if query else '')
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=3) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('diagnostic response exceeds byte limit')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('invalid diagnostic response')
    return _validate_remote(settings, view, result)


async def _engine_read(settings, view: str, params: dict) -> dict:
    async with rpc.EngineClient(settings) as client:
        caps = await client.call('system.capabilities', {}, timeout=3)
        version = caps.get('observability') if isinstance(caps, dict) else None
        if type(version) is not int or version != 1:
            return {'coverage': {'status': 'unsupported', 'available': False, 'gaps': [{'reason': 'engine-observability-unsupported'}]}}
        return _validate_remote(settings, view, await client.call('diagnostics.' + view, params, timeout=3))


def remote_read(settings, view: str, params: dict) -> dict:
    """Prefer a separately running reader; engine reads are a compatible fallback."""
    try:
        binding = getattr(settings, "observability", None)
        if binding is not None and binding.reader_url:
            return reader_read(settings, view, params)
        if settings.engine_ws_url:
            return asyncio.run(asyncio.wait_for(_engine_read(settings, view, params), timeout=5))
        return {'coverage': {'status': 'unsupported', 'available': False, 'gaps': [{'reason': 'engine-not-configured'}]}}
    except Exception:
        return {'coverage': {'status': 'unavailable', 'available': False, 'gaps': [{'reason': 'remote-unreachable'}]}}


def collect(settings, view: str = 'locations', *, cursor=None, trace_id=None, limit=100, local=False, request_id=None) -> dict:
    """Collect bounded views without ingestion, provider reads or model calls."""
    if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 4096 or view not in {'events', 'trace', 'recent'}):
        raise ValueError('invalid diagnostic request identity')
    store = store_for(settings)
    actual = 'events' if view in {'recent', 'trace', 'events'} else view
    params = {'limit': limit}
    if cursor:
        params['cursor'] = cursor
    if trace_id:
        params['trace_id'] = trace_id
    if view == 'recent':
        here = store.recent(limit=limit)
        params['recent'] = True
    elif actual == 'events':
        here = store.events(**params)
    elif actual == 'health':
        here = store.health()
    else:
        here = store.locations()
    result = {'schema_version': 1, 'view': view, 'local': here}
    from . import monitor_access
    result['monitor'] = monitor_access.read(settings, view, trace_id=trace_id, limit=limit)
    if not local:
        result['remote'] = remote_read(settings, actual, params if actual == 'events' else {})
    if request_id is not None:
        import hashlib
        commitment = hashlib.sha256(request_id.encode()).hexdigest()
        related = set()
        def filter_page(page):
            if not isinstance(page, dict) or not isinstance(page.get('events'), list):
                return
            matches = [event for event in page['events'] if any(event.get(key) == commitment for key in ('root_id', 'draft_id', 'provider_id', 'request_revision'))]
            related.update(event['trace_id'] for event in matches)
            page['events'] = matches
        for name in ('local', 'remote', 'monitor'):
            filter_page(result.get(name))
        filter_page(result.get('monitor', {}).get('off_host'))
        result['request_lookup'] = {'commitment': commitment, 'related_trace_ids': sorted(related),
                                    'coverage': 'bounded-page-only; follow source next_cursor or inspect a related trace'}
    return result


def cmd_logs(args) -> int:
    try:
        result = collect(config.load(), args.logs_view, cursor=args.cursor, trace_id=args.trace_id,
                         limit=args.limit, local=args.local, request_id=getattr(args, 'request_id', None))
        raw = json.dumps(result, separators=(',', ':'), ensure_ascii=True)
        if len(raw.encode()) > MAX_RESPONSE_BYTES:
            result = {'schema_version': 1, 'coverage': {'status': 'unavailable', 'available': False,
                      'gaps': [{'reason': 'combined-response-limit', 'action': 'query-one-component'}]}}
            raw = json.dumps(result)
        rendered = raw if args.json else json.dumps(result, indent=2, ensure_ascii=False)
        if len(rendered.encode()) > MAX_RESPONSE_BYTES:
            rendered = json.dumps({'coverage': {'status': 'unavailable', 'available': False, 'gaps': [{'reason': 'response-limit'}]}})
        print(rendered)
        return 0
    except ValueError:
        print('Invalid diagnostic query; check identifier, cursor and limit (1 to 200)')
        return 2


def add_subparsers(sub) -> None:
    parser = sub.add_parser('logs', help='locate logs and inspect diagnostic traces (read-only)')
    parser.add_argument('logs_view', nargs='?', default='locations', choices=('locations', 'recent', 'events', 'trace', 'health'))
    parser.add_argument('--trace-id')
    parser.add_argument('--request-id', help='find an exact RFC/root, draft or provider handle in this bounded page')
    parser.add_argument('--cursor')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--local', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=cmd_logs)
