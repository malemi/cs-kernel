"""Private scheduled reservations for a bounded ordinary conversation queue."""
from __future__ import annotations

import fcntl
from datetime import datetime, timezone
from email.utils import getaddresses
import hashlib
import json
import os
from pathlib import Path
import re

from .operator_health import identity, private, LIMIT


class WorksetError(RuntimeError):
    def __init__(self, message, *, reason='workset_invalid', key=None):
        super().__init__(message)
        self.reason = reason
        self.key = key


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str).encode()


def _hash(value):
    return hashlib.sha256(_encode(value)).hexdigest()


def _timestamp(value):
    try:
        date = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _context(settings):
    raw = os.environ.get('CS_OPERATOR_HEALTH_CONTEXT')
    if raw is None:
        return None
    try:
        context = json.loads(raw)
        if context.get('workset_enabled') is not True:
            return None
        directory = Path(context['directory'])
        if not directory.is_absolute() or directory.resolve() != directory:
            raise ValueError('context path differs')
        private(directory, True)
        if not isinstance(context['nonce'], str) or not context['nonce'] or len(context['nonce']) > 256:
            raise ValueError('invalid nonce')
        owner = settings.engine_owner_uid
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError('missing owner')
        if context.get('owner_uid') != owner:
            raise ValueError('context owner differs')
        pid = os.getpid()
        for _ in range(32):
            row, pid = identity(pid)
            if row == context['supervisor']:
                break
        else:
            raise ValueError('supervisor differs')
        context['owner_uid'] = owner
        return context
    except Exception as exc:
        raise WorksetError('invalid scheduled workset context', reason='context_invalid') from exc


def _read(path):
    private(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        data = stream.read(LIMIT * 2 + 1)
    if len(data) > LIMIT * 2:
        raise ValueError('workset record too large')
    return json.loads(data)


def _write_new(path, value):
    data = _encode(value)
    if len(data) > LIMIT * 2:
        raise ValueError('workset record too large')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _rows(source, payload):
    typed_inventory = False
    if isinstance(payload, dict):
        # A review also reports unrelated assignment/campaign/freshness work.
        # Its named UNKNOWN roots stay held in discovery; they do not make an
        # independently complete draft inventory unreadable.
        if source == 'tasks' and any(value for key, value in payload.items()
                                   if key.endswith('_error') or key.endswith('_incomplete')):
            raise WorksetError('incomplete source', reason='tasks_inventory_incomplete')
        if source == 'review':
            for key in ('drafts_error', 'gmail_drafts_error', 'engine_drafts_error', 'drafts_incomplete'):
                if payload.get(key):
                    raise WorksetError('incomplete source', reason='review_inventory_incomplete', key=key)
            if 'drafts_inventory' in payload:
                from .draft_state import inventory_proof
                actual = inventory_proof(payload.get('gmail_drafts'), payload.get('engine_drafts'),
                                         payload.get('drafts'), payload.get('gmail_drafts_observation'))
                if actual.get('complete') is not True or payload['drafts_inventory'] != actual:
                    raise WorksetError('incomplete source', reason='review_inventory_incomplete',
                                       key='drafts_inventory')
                typed_inventory = True
        for key in ('error', 'errors', 'truncated', 'has_more', 'next_cursor', 'next_page', 'next_page_token', 'drafts_notes'):
            if key == 'drafts_notes' and source == 'review' and typed_inventory:
                continue
            if payload.get(key):
                raise WorksetError('incomplete source', reason='source_marked_incomplete', key=key)
        if payload.get('complete', True) is not True:
            raise WorksetError('incomplete source', reason='source_not_complete')
        rows = payload.get('tasks' if source == 'tasks' else 'drafts')
        if 'total' in payload and (type(payload['total']) is not int or payload['total'] != len(rows or [])):
            raise WorksetError('truncated source', reason='source_total_mismatch')
    else:
        rows = payload if source == 'tasks' else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows) or len(rows) > 10000:
        raise WorksetError('unknown source shape', reason='source_shape_invalid')
    return rows


def observe(settings, source, payload, *, complete=True):
    context = _context(settings)
    if context is None:
        return None
    stage = 'source_invalid'
    try:
        if source not in ('tasks', 'review'):
            raise ValueError('unknown source')
        directory = Path(context['directory'])
        stage = 'reservation_read_failed'
        reservation = directory / 'workset-reserved.json'
        if reservation.exists() or reservation.is_symlink():
            record = _read(reservation)
            if record['nonce'] != context['nonce'] or record['owner_uid'] != context['owner_uid']:
                raise WorksetError('foreign reservation', reason='reservation_binding_invalid')
            return None
        if complete is not True:
            raise WorksetError('incomplete source', reason='source_not_complete')
        stage = 'source_shape_invalid'
        _rows(source, payload)
        value = {'nonce': context['nonce'], 'owner_uid': context['owner_uid'], 'source': source,
                 'digest': _hash(payload), 'payload': payload}
        path = directory / ('workset-' + source + '.json')
        stage = 'observation_read_failed'
        if path.exists() or path.is_symlink():
            if _encode(_read(path)) != _encode(value):
                raise WorksetError('source changed before reservation', reason='observation_changed')
        else:
            stage = 'observation_write_failed'
            _write_new(path, value)
    except Exception as exc:
        raise WorksetError('workset observation incomplete or unsafe',
                           reason=exc.reason if isinstance(exc, WorksetError) else stage,
                           key=exc.key if isinstance(exc, WorksetError) else None) from exc


def observation_failure(settings, source, error):
    """Retain bounded diagnostic codes only; never grant inventory authority."""
    reasons = {'workset_invalid', 'context_invalid', 'source_invalid', 'tasks_inventory_incomplete',
               'review_inventory_incomplete', 'source_marked_incomplete', 'source_not_complete',
               'source_total_mismatch', 'source_shape_invalid', 'reservation_read_failed',
               'reservation_binding_invalid', 'observation_read_failed', 'observation_changed',
               'observation_write_failed'}
    reason = error.reason if isinstance(error, WorksetError) else 'workset_invalid'
    record = {'event': 'scheduled_workset_observation_rejected', 'version': 1,
              'source': source if source in ('tasks', 'review') else 'unknown',
              'reason': reason if reason in reasons else 'workset_invalid'}
    keys = {'drafts_error', 'gmail_drafts_error', 'engine_drafts_error', 'drafts_incomplete',
            'error', 'errors', 'truncated', 'has_more', 'next_cursor', 'next_page',
            'next_page_token', 'drafts_notes', 'drafts_inventory'}
    record['key'] = error.key if isinstance(error, WorksetError) and error.key in keys else None
    try:
        context = _context(settings)
        if context is not None and source in ('tasks', 'review'):
            _write_new(Path(context['directory']) / ('workset-' + source + '-failure.json'), record)
    except Exception:
        pass  # Diagnostic retention cannot replace or weaken the original refusal.
    return record


def _root(row):
    sources = row.get('sources')
    values = [row.get('thread_key'), row.get('thread_id')]
    if isinstance(sources, dict):
        values.append(sources.get('thread_id'))
    values = [value for value in values if value is not None and value != '']
    if not values or any(not isinstance(value, str) or re.fullmatch(r'<[^<>\s@]+@[^<>\s@]+>', value) is None for value in values):
        return None
    return values[0] if len(set(values)) == 1 else None


def _stable(row, source=None):
    keys = ('id', 'task_id', 'draft_id', 'uid', 'status', 'state', 'verdict', 'updated_at',
            'composed_at', 'composed_iso', 'version', 'sources', 'thread_key', 'thread_id', 'message_id', 'engine_id', 'gmail_uid')
    if source == 'tasks':
        keys += ('last_signal_at', 'created_at', 'source_root_state')
    return {key: row[key] for key in keys if key in row}


def _row_addresses(row):
    addresses = set()
    for field in ('email', 'sender', 'from_email', 'contact_email', 'to', 'to_addresses',
                  'to_display', 'recipients', 'cc', 'cc_addresses', 'cc_recipients',
                  'bcc', 'bcc_addresses'):
        raw = row.get(field)
        values = raw if isinstance(raw, (list, tuple)) else [raw]
        for _, address in getaddresses([value for value in values if isinstance(value, str)]):
            if re.fullmatch(r'[^\s@<>]+@[^\s@<>]+', address):
                addresses.add(address.lower())
    return addresses


def _inventory(discovery, observations, owner):
    if (not isinstance(discovery, dict) or 'read_incomplete' not in discovery
            or discovery['read_incomplete'] is not None or type(discovery.get('assignment_incomplete')) is not bool
            or any(not isinstance(discovery.get(key), list) for key in ('open', 'resumed', 'human_work', 'assignment_audit'))):
        raise ValueError('discovery incomplete')
    candidates, held, blocked, addresses = {}, [], set(), set()
    for bucket in ('human_work', 'assignment_audit', 'escalated'):
        rows = discovery.get(bucket, [])
        if not isinstance(rows, list):
            raise ValueError('invalid held inventory')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('invalid held row')
            assignment = row.get('assignment')
            if assignment is not None and (not isinstance(assignment, dict)
                    or assignment.get('actor_uid') != owner or assignment.get('source_owner_uid') != owner):
                raise ValueError('foreign or malformed held assignment')
            root = _root(row)
            if root:
                blocked.add(root)
            if bucket == 'escalated':
                addresses.update(_row_addresses(row))
            held.append({'thread_key': root, 'reason': bucket, 'source': 'discovery'})
    def add(row, source, revision):
        root = _root(row)
        if (source == 'tasks' and 'source_root_state' in row
                and (type(row['source_root_state']) is not str or row['source_root_state'] != 'resolved')):
            held.append({'thread_key': root, 'reason': 'unresolved_task_source_root', 'source': source,
                         'identity': str(row.get('id') or row.get('uid') or row.get('task_id') or '')})
            return
        if root is None:
            held.append({'thread_key': None, 'reason': 'missing_exact_root', 'source': source,
                         'identity': str(row.get('id') or row.get('uid') or row.get('task_id') or '')})
            return
        if root in blocked or _row_addresses(row) & addresses:
            held.append({'thread_key': root, 'reason': 'fresh_discovery_hold', 'source': source})
            return
        item = candidates.setdefault(root, {'revisions': [], 'sources': [], 'date': 0.0, 'contacts': []})
        for field in ('email', 'contact_email', 'to', 'to_addresses', 'to_display'):
            raw = row.get(field)
            values = raw if isinstance(raw, list) else [raw]
            for _, address in getaddresses([value for value in values if isinstance(value, str)]):
                if re.fullmatch(r'[^\s@<>]+@[^\s@<>]+', address):
                    item['contacts'].append(_hash(address.lower()))
        item['revisions'].append(revision)
        if source not in item['sources']:
            item['sources'].append(source)
        date = row.get('last_inbound_date') or row.get('updated_at') or row.get('composed_at')
        if source == 'tasks' and not date:
            date = row.get('last_signal_at') or row.get('created_at')
        item['date'] = max(item['date'], _timestamp(date))
    for row in _rows('review', observations['review']):
        if row.get('workset_hold_reasons'):
            root = _root(row)
            if root:
                blocked.add(root)
            else:
                addresses.update(_row_addresses(row))
            held.append({'thread_key': root, 'reason': 'review_evidence_incomplete', 'source': 'review'})
    for bucket in ('open', 'resumed'):
        rows = discovery.get(bucket, [])
        if not isinstance(rows, list):
            raise ValueError('invalid discovery inventory')
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('_workset_revision'), str) or not re.fullmatch('[0-9a-f]{64}', row['_workset_revision']):
                raise ValueError('missing discovery revision')
            add(row, 'discovery', row['_workset_revision'])
    for source, payload in observations.items():
        for row in _rows(source, payload):
            if source == 'review' and row.get('workset_hold_reasons'):
                continue
            if source == 'review' and row.get('verdict') == 'ready':
                continue
            if source == 'tasks' and row.get('status') in ('completed', 'closed', 'cancelled'):
                continue
            add(row, source, _hash(_stable(row, source)))
    if len(candidates) > 10000:
        raise ValueError('workset capacity exceeded')
    for item in candidates.values():
        item['revision'] = _hash(sorted(set(item.pop('revisions'))))
        item['sources'].sort()
    return candidates, held


def reserve(settings, discovery):
    context = _context(settings)
    if context is None:
        return None
    try:
        directory = Path(context['directory'])
        observations = {}
        for source in ('tasks', 'review'):
            record = _read(directory / ('workset-' + source + '.json'))
            if (record['nonce'] != context['nonce'] or record['owner_uid'] != context['owner_uid']
                    or record['source'] != source or record['digest'] != _hash(record['payload'])):
                raise ValueError('foreign source')
            observations[source] = record['payload']
        candidates, held = _inventory(discovery, observations, context['owner_uid'])
        digest = _hash([discovery, observations])
        base = Path(settings.state_dir)
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        if base.is_symlink() or base.resolve() != base or base.stat().st_uid != os.getuid():
            raise ValueError('unsafe state directory')
        cursor_dir = base / 'operator-workset'
        cursor_dir.mkdir(mode=0o700, exist_ok=True)
        private(cursor_dir, True)
        lock = cursor_dir / 'lock'
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'r+b') as stream:
            private(lock)
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = cursor_dir / 'cursor.json'
            owner = _hash(context['owner_uid'])
            if path.exists() or path.is_symlink():
                cursor = _read(path)
            else:
                cursor = {'version': 1, 'owner': owner, 'order': 0, 'roots': {}, 'runs': {}}
            if (set(cursor) != {'version', 'owner', 'order', 'roots', 'runs'} or cursor['version'] != 1
                    or cursor['owner'] != owner or type(cursor['order']) is not int or cursor['order'] < 0
                    or not isinstance(cursor['roots'], dict) or not isinstance(cursor['runs'], dict)
                    or len(cursor['roots']) > 10000 or len(cursor['runs']) > 10000):
                raise ValueError('invalid cursor')
            for key, value in cursor['roots'].items():
                if (not re.fullmatch('[0-9a-f]{64}', key) or not isinstance(value, dict)
                        or set(value) != {'revision', 'order'} or not re.fullmatch('[0-9a-f]{64}', str(value['revision']))
                        or type(value['order']) is not int or not 0 < value['order'] <= cursor['order']):
                    raise ValueError('invalid cursor roots')
            for key, value in cursor['runs'].items():
                if (not re.fullmatch('[0-9a-f]{64}', key) or not isinstance(value, dict)
                        or set(value) != {'digest', 'selected', 'contacts'} or not re.fullmatch('[0-9a-f]{64}', str(value['digest']))
                        or not isinstance(value['selected'], list) or len(value['selected']) > 2
                        or any(not isinstance(item, str) or not re.fullmatch('[0-9a-f]{64}', item) for item in value['selected'])
                        or len(set(value['selected'])) != len(value['selected'])
                        or not isinstance(value['contacts'], list)
                        or any(not isinstance(item, str) or not re.fullmatch('[0-9a-f]{64}', item) for item in value['contacts'])):
                    raise ValueError('invalid cursor runs')
            run = _hash(context['nonce'])
            previous = cursor['runs'].get(run)
            if previous is not None:
                if previous['digest'] != digest:
                    raise ValueError('same-run inventory changed')
                selected = previous['selected']
                if not isinstance(selected, list) or len(selected) > 2 or len(set(selected)) != len(selected):
                    raise ValueError('invalid reservation')
            else:
                hashed = {_hash(root): root for root in candidates}
                fresh = [root for key, root in hashed.items() if cursor['roots'].get(key, {}).get('revision') != candidates[root]['revision']]
                chosen = sorted(fresh, key=lambda root: (candidates[root]['date'], root), reverse=True)[:1]
                remaining = sorted((root for root in candidates if root not in chosen),
                                   key=lambda root: (cursor['roots'].get(_hash(root), {}).get('order', 0), root))
                chosen.extend(remaining[:2 - len(chosen)])
                selected = [_hash(root) for root in chosen]
                cursor['order'] += 1
                for root in chosen:
                    cursor['roots'][_hash(root)] = {'revision': candidates[root]['revision'], 'order': cursor['order']}
                cursor['runs'][run] = {'digest': digest, 'selected': selected,
                    'contacts': sorted({contact for root in chosen for contact in candidates[root]['contacts']})}
                if len(cursor['roots']) > 10000 or len(cursor['runs']) > 10000:
                    raise ValueError('cursor capacity exceeded')
                temporary = cursor_dir / ('cursor-' + os.urandom(12).hex())
                _write_new(temporary, cursor)
                os.replace(temporary, path)
            mapping = {_hash(root): root for root in candidates}
            if any(key not in mapping for key in selected):
                raise ValueError('reservation inventory differs')
            chosen = [mapping[key] for key in selected]
            result = {'complete': True, 'limit': 2,
                      'selected': [{'thread_key': root, 'revision': candidates[root]['revision'], 'sources': candidates[root]['sources']} for root in chosen],
                      'deferred': [{'thread_key': root, 'reason': 'workset_limit', 'sources': candidates[root]['sources']} for root in sorted(candidates) if root not in chosen],
                      'held': held}
            receipt = {'nonce': context['nonce'], 'owner_uid': context['owner_uid'], 'digest': digest,
                       'selected': selected, 'contacts': cursor['runs'][run]['contacts']}
            marker = directory / 'workset-reserved.json'
            if marker.exists() or marker.is_symlink():
                if _read(marker) != receipt:
                    raise ValueError('reservation receipt differs')
            else:
                _write_new(marker, receipt)
            from .observability_producers import emit as diagnostic_emit
            diagnostic_emit(settings, 'discovery', 'result', complete=True, pending_count=len(candidates), count=len(held))
            for selected_row in result['selected']:
                diagnostic_emit(settings, 'selection', 'result', reason='none', root_id=selected_row['thread_key'], request_revision=selected_row['revision'])
            for deferred_row in result['deferred']:
                diagnostic_emit(settings, 'selection', 'deferred', reason='none', root_id=deferred_row['thread_key'], request_revision=candidates[deferred_row['thread_key']]['revision'])
            for held_row in held:
                diagnostic_emit(settings, 'authority', 'held', reason='policy-hold' if held_row.get('reason') in {'human_work','escalated','fresh_discovery_hold'} else 'incomplete-input', root_id=held_row.get('thread_key'))
            return result
    except Exception as exc:
        raise WorksetError('workset reservation incomplete or unsafe') from exc


def _reservation(settings):
    context = _context(settings)
    if context is None:
        return None
    try:
        record = _read(Path(context['directory']) / 'workset-reserved.json')
        base = Path(settings.state_dir)
        if base.is_symlink() or base.resolve() != base or base.stat().st_uid != os.getuid():
            raise ValueError('unsafe state directory')
        directory = base / 'operator-workset'
        private(directory, True)
        cursor = _read(directory / 'cursor.json')
        run = cursor['runs'][_hash(context['nonce'])]
        if (cursor['version'] != 1 or cursor['owner'] != _hash(context['owner_uid'])
                or record['nonce'] != context['nonce'] or record['owner_uid'] != context['owner_uid']
                or any(record[key] != run[key] for key in ('digest', 'selected', 'contacts'))
                or not isinstance(record['selected'], list) or len(record['selected']) > 2
                or not isinstance(record['contacts'], list)):
            raise ValueError('foreign reservation')
        return record
    except Exception as exc:
        raise WorksetError('scheduled workset reservation missing or unsafe') from exc


def require_root(settings, thread_key):
    record = _reservation(settings)
    if record is not None and (not isinstance(thread_key, str)
            or re.fullmatch(r'<[^<>\s@]+@[^<>\s@]+>', thread_key) is None
            or _hash(thread_key) not in record['selected']):
        raise WorksetError('conversation is outside the scheduled workset')


class OutsideSelectedWorkset(WorksetError):
    """Only a validated read exclusion carries source-bound business evidence."""
    def __init__(self, value):
        super().__init__('contact is outside the scheduled workset', reason='outside_selected_workset')
        self.value = value


def require_contact(settings, email, *, typed_exclusion=False):
    record = _reservation(settings)
    if record is not None and (not isinstance(email, str)
            or re.fullmatch(r'[^\s@<>]+@[^\s@<>]+', email) is None
            or _hash(email.lower()) not in record['contacts']):
        if typed_exclusion:
            from .operator_read_outcomes import outside_workset_value
            context = _context(settings)
            raw = (Path(context['directory']) / 'workset-reserved.json').read_bytes()
            value = {'version':1,'kind':'outside_selected_workset','reason':'OUTSIDE_SELECTED_WORKSET',
                     'owner_uid':settings.engine_owner_uid,'nonce':context['nonce'],'contact':email.lower(),
                     'reservation':record,'reservation_sha256':hashlib.sha256(raw).hexdigest(),
                     'cursor_run':{k:record[k] for k in ('digest','selected','contacts')}}
            scope = {'kind':'outside_selected_workset','contact':email.lower()}
            if outside_workset_value(value, scope, settings.engine_owner_uid, context):
                raise OutsideSelectedWorkset(value)
        raise WorksetError('contact is outside the scheduled workset')


def selected_contact_roots(settings, email):
    """Resolve admitted scheduled roots/revisions; never return action authority."""
    if not isinstance(email, str) or re.fullmatch(r'[^\s@<>]+@[^\s@<>]+', email) is None:
        raise WorksetError('invalid scheduled contact', reason='selection_invalid')
    context = _context(settings)
    if context is None:
        raise WorksetError('scheduled reservation required', reason='selection_invalid')
    try:
        from .operator_inventory_view import read_private
        def read(path):
            return json.loads(read_private(path))
        directory = Path(context['directory'])
        reservation = _reservation(settings)
        if reservation != read(directory / 'workset-reserved.json'):
            raise ValueError('reservation changed')
        cursor = read(Path(settings.state_dir) / 'operator-workset' / 'cursor.json')
        if type(cursor.get('version')) is not int or cursor['version'] != 1:
            raise ValueError('invalid cursor version')
        run = cursor['runs'][_hash(context['nonce'])]
        if any(reservation[key] != run[key] for key in ('digest', 'selected', 'contacts')):
            raise ValueError('cursor changed')
        raw = read(directory / 'discovery.json')
        ancestry = raw['ancestry']
        if (set(raw) != {'nonce', 'owner_uid', 'ancestry', 'exit_code', 'output_sha256', 'discovery'}
                or not isinstance(ancestry, list) or any(not isinstance(row, dict)
                    or set(row) != {'pid', 'started_ticks'}
                    or any(type(v) is not int or v <= 0 for v in row.values()) for row in ancestry)):
            raise ValueError('invalid discovery identity')
        if (raw['owner_uid'] != context['owner_uid'] or raw['nonce'] != context['nonce']
                or type(raw['exit_code']) is not int or raw['exit_code'] not in (0, 3)
                or not isinstance(ancestry, list) or not 3 <= len(ancestry) <= 32
                or ancestry[-1] != context['supervisor']):
            raise ValueError('foreign discovery')
        chain, pid = [], os.getpid()
        for _ in range(32):
            row, pid = identity(pid)
            chain.append(row)
            if row == context['supervisor']:
                break
        else:
            raise ValueError('foreign process')
        if ancestry[-2] not in chain[:-1]:
            raise ValueError('foreign native child')
        discovery = raw['discovery']
        output = (json.dumps(discovery, ensure_ascii=False, indent=2, default=str) + '\n').encode()
        if len(output) > LIMIT or hashlib.sha256(output).hexdigest() != raw['output_sha256']:
            raise ValueError('discovery bytes changed')
        observations = {}
        for source in ('tasks', 'review'):
            item = read(directory / ('workset-' + source + '.json'))
            if (item['nonce'] != context['nonce'] or item['owner_uid'] != context['owner_uid']
                    or item['source'] != source or item['digest'] != _hash(item['payload'])):
                raise ValueError('foreign observation')
            observations[source] = item['payload']
        original = dict(discovery)
        public = original.pop('triage_workset')
        if reservation['digest'] != _hash([original, observations]):
            raise ValueError('discovery revision changed')
        candidates, held = _inventory(original, observations, context['owner_uid'])
        mapping = {_hash(root): root for root in candidates}
        selected = reservation['selected']
        if (not isinstance(selected, list) or not 1 <= len(selected) <= 2
                or len(set(selected)) != len(selected) or any(key not in mapping for key in selected)):
            raise ValueError('selected roots changed')
        roots = [mapping[key] for key in selected]
        expected = {'complete': True, 'limit': 2,
            'selected': [{'thread_key': root, 'revision': candidates[root]['revision'],
                          'sources': candidates[root]['sources']} for root in roots],
            'deferred': [{'thread_key': root, 'reason': 'workset_limit', 'sources': candidates[root]['sources']}
                         for root in sorted(candidates) if root not in roots], 'held': held}
        if (not isinstance(public, dict) or public.get('complete') is not True
                or type(public.get('limit')) is not int or public['limit'] != 2 or public != expected):
            raise ValueError('published selection changed')
        contacts = sorted({contact for root in roots for contact in candidates[root]['contacts']})
        if reservation['contacts'] != contacts:
            raise ValueError('contact associations changed')
        for root in roots:
            if cursor['roots'][_hash(root)]['revision'] != candidates[root]['revision']:
                raise ValueError('cursor revision changed')
        requested = _hash(email.lower())
        result = [row for row in expected['selected'] if requested in candidates[row['thread_key']]['contacts']]
        if not result:
            raise ValueError('contact outside selected roots')
        return result
    except Exception as exc:
        raise WorksetError('scheduled contact selection missing or changed', reason='selection_invalid') from exc


def _send_snapshot(settings, context, draft, root):
    """Integrity of observed draft data; never substitutes for engine authority."""
    from .thread_key import thread_key
    refs = draft.get('references')
    actual = draft.get('thread_id') or thread_key(
        None, ' '.join(refs) if isinstance(refs, list) else refs, draft.get('in_reply_to'))
    if (not isinstance(draft.get('id'), str) or not draft['id']
            or draft.get('owner_id') != settings.email_address or not settings.email_address
            or actual != root or draft.get('status') != 'draft'
            or not isinstance(draft.get('body'), str) or not draft['body'].strip()
            or not isinstance(draft.get('to_addresses'), list) or not draft['to_addresses']):
        raise WorksetError('scheduled draft identity is incomplete or foreign')
    fields = ('id', 'owner_id', 'thread_id', 'to_addresses', 'cc_addresses', 'bcc_addresses',
              'subject', 'body', 'body_format', 'in_reply_to', 'references',
              'original_message_id', 'attachment_paths', 'status')
    return {'version': 1, 'nonce': context['nonce'], 'owner_uid': context['owner_uid'],
            'root': root, 'draft_id': draft['id'],
            'snapshot': _hash({key: draft.get(key) for key in fields})}


def remember_draft(settings, draft, root):
    """Retain one actual scoped compose result in the current private run."""
    context = _context(settings)
    if context is None:
        return
    require_root(settings, root)
    value = _send_snapshot(settings, context, draft, root)
    path = Path(context['directory']) / ('workset-draft-' + _hash(draft['id']) + '.json')
    if path.exists() or path.is_symlink():
        if _read(path) != value:
            raise WorksetError('scheduled composed draft changed')
    else:
        _write_new(path, value)


def require_draft(settings, draft, root):
    """Bind exact send to a composed or ready-reviewed snapshot in this run."""
    context = _context(settings)
    if context is None:
        return
    require_root(settings, root)
    value = _send_snapshot(settings, context, draft, root)
    path = Path(context['directory']) / ('workset-draft-' + _hash(draft['id']) + '.json')
    if path.exists() or path.is_symlink():
        if _read(path) != value:
            raise WorksetError('scheduled composed draft changed')
        return
    review = _read(Path(context['directory']) / 'workset-review.json')
    if (review.get('nonce') != context['nonce'] or review.get('owner_uid') != context['owner_uid']
            or review.get('source') != 'review' or review.get('digest') != _hash(review.get('payload'))):
        raise WorksetError('scheduled review snapshot is foreign')
    payload = review['payload']
    rows = _rows('review', payload)
    if not isinstance(payload, dict) or payload.get('drafts_inventory', {}).get('complete') is not True:
        raise WorksetError('scheduled typed review snapshot is unavailable')
    ready = [row for row in rows if row.get('engine_id') == draft['id'] and row.get('thread_key') == root
             and row.get('verdict') == 'ready' and row.get('workset_hold_reasons') == []]
    raw = [row for row in payload['engine_drafts'] if row.get('id') == draft['id']]
    if len(ready) != 1 or len(raw) != 1 or _send_snapshot(settings, context, raw[0], root) != value:
        raise WorksetError('scheduled draft differs from its ready review snapshot')
