"""Bounded newest-first failure inspection without scanning full retained history."""
from __future__ import annotations

import json
import os
import time

from .observability import MAX_EVENT_BYTES, MAX_RESPONSE_BYTES, event_level, LEVELS
from .observability_store import _locked, _segments, _segment_time, _open, _validate_event


def read_recent(store, limit=100):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('limit must be between 1 and 200')
    result = {'schema_version':1, 'owner_uid':store.owner_uid, 'component':store.component,
              'events':[], 'next_cursor':None, 'coverage':store.health()}
    remaining = MAX_RESPONSE_BYTES-16384
    failures = {'failed','unknown-effect','delivered-cleanup-incomplete','held'}
    incomplete, malformed = False, 0
    try:
        with _locked(store):
            files = [p for p in reversed(_segments(store)) if time.time()-_segment_time(p) < store.retention_seconds]
            for index,path in enumerate(files):
                size = path.stat().st_size
                amount = min(size,remaining)
                fd = _open(path,os.O_RDONLY)
                try:
                    raw = os.pread(fd,amount,size-amount)
                finally:
                    os.close(fd)
                remaining -= len(raw)
                if amount < size:
                    incomplete = True
                    raw = raw.partition(b'\n')[2]
                for line in reversed(raw.splitlines()):
                    try:
                        if len(line) >= MAX_EVENT_BYTES:
                            raise ValueError('large event')
                        event=json.loads(line)
                        if not _validate_event(event,store):
                            raise ValueError('invalid event')
                        event.setdefault('level', event_level(event))
                    except Exception:
                        malformed += 1
                        continue
                    if event['status'] in failures or LEVELS[event['level']] >= LEVELS['ERROR']:
                        result['events'].append(event)
                    if len(result['events']) >= limit:
                        incomplete = True
                        break
                if remaining <= MAX_EVENT_BYTES or len(result['events']) >= limit:
                    incomplete = incomplete or index+1<len(files)
                    break
    except FileNotFoundError:
        pass
    except Exception:
        result['coverage'].update(status='unavailable',available=False)
        result['coverage']['gaps'].append({'reason':'unreadable','count':1})
    if malformed:
        result['coverage']['gaps'].append({'reason':'malformed-event','count':malformed})
    if incomplete:
        result['coverage']['gaps'].append({'reason':'recent-window-limit','count':1})
    if result['coverage']['gaps'] and result['coverage']['status']=='observed':
        result['coverage']['status']='degraded'
    result['coverage']['continuation_required']=incomplete
    result['coverage']['scanned_bytes']=MAX_RESPONSE_BYTES-16384-remaining
    while len(json.dumps(result).encode()) > MAX_RESPONSE_BYTES and result['events']:
        result['events'].pop()
        result['coverage']['continuation_required']=True
    return result
