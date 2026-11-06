"""Private, bounded diagnostic events; these observations grant no business authority."""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import itertools
import functools
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
MAX_EVENT_BYTES = 8192
MAX_RESPONSE_BYTES = 262144
_IDS = ('trace_id', 'span_id', 'parent_span_id', 'run_id', 'attempt_id')
_CONTEXT: contextvars.ContextVar[dict] = contextvars.ContextVar('diagnostics', default={})
_SEQUENCE = itertools.count(1)
STAGES = frozenset('launch cli rpc acquisition discovery selection authority context generation persistence provider verification cleanup job monitor alert'.split())
STATUSES = frozenset('start result not-attempted deferred held running failed accepted verified unknown unknown-effect delivered-cleanup-incomplete paused disabled lock-skipped cancelled completed'.split())
REASONS = frozenset('auth quota permission timeout cancelled incomplete-input policy-hold provider-rejection persistence logging unknown none unsupported'.split())
CERTAINTY = frozenset(('none', 'unknown', 'accepted', 'verified', 'recipient-received'))
LEVELS = {'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}


def event_level(event: dict) -> str:
    """Interpret legacy records without changing their recorded business outcome."""
    if 'level' in event:
        level = event['level']
        if not isinstance(level, str) or level not in LEVELS:
            raise ValueError('invalid diagnostic level')
        return level
    status = event.get('status')
    if status in {'start', 'running'}:
        return 'DEBUG'
    if status in {'held', 'deferred', 'paused', 'disabled', 'lock-skipped', 'not-attempted'}:
        return 'WARNING'
    if status in {'failed', 'unknown', 'unknown-effect', 'delivered-cleanup-incomplete', 'cancelled'}:
        return 'ERROR'
    return 'INFO'


def diagnostic_id(value: Any) -> str | None:
    """Accept only opaque UUID diagnostic identities."""
    if not isinstance(value, str) or len(value) not in (32, 36):
        return None
    try:
        return uuid.UUID(value).hex
    except ValueError:
        return None


def current_context() -> dict:
    """Return a copy so callers cannot mutate another async task's context."""
    return dict(_CONTEXT.get())


def diagnostic_envelope() -> dict:
    """Export correlation only, never a tenant or business parameter."""
    return {'version': 1, **current_context()}


@contextlib.contextmanager
def context(metadata: dict | None = None) -> Iterator[dict]:
    """Scope validated identifiers and restore them even on cancellation."""
    source = metadata if isinstance(metadata, dict) else current_context()
    selected = {key: valid for key in _IDS if (valid := diagnostic_id(source.get(key)))}
    selected.setdefault('trace_id', uuid.uuid4().hex)
    selected.setdefault('span_id', uuid.uuid4().hex)
    token = _CONTEXT.set(selected)
    try:
        yield dict(selected)
    finally:
        _CONTEXT.reset(token)


def safe_metadata(values: dict) -> dict:
    """Allow operational metadata without message text, exceptions or credentials."""
    out: dict[str, Any] = {}
    for key in ('rpc_id', 'exit_code', 'error_code', 'error_line', 'count', 'pending_count', 'deadline_seconds'):
        value = values.get(key)
        if type(value) is int and -(2**53) < value < 2**53:
            out[key] = value
    for key in ('elapsed_ms',):
        value = values.get(key)
        if type(value) in (int, float) and 0 <= value <= 10**12:
            out[key] = value
    for key in ('complete', 'available'):
        if type(values.get(key)) is bool:
            out[key] = values[key]
    for key in ('command', 'method'):
        value = values.get(key)
        if isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_.-]{0,79}', value):
            out[key] = value
    for key in ('draft_id', 'job_id', 'root_id', 'request_revision', 'provider_id', 'evidence_ref', 'operation_id'):
        value = values.get(key)
        if isinstance(value, str) and 0 < len(value) <= 4096:
            out[key] = hashlib.sha256(value.encode()).hexdigest()
    stages = values.get('achieved_stages')
    if isinstance(stages, list) and len(stages) <= 5 and len(stages) == len(set(stages)) and all(item in {'engine-saved', 'review-visible', 'sent', 'residual-copy-retired'} for item in stages):
        out['achieved_stages'] = stages
    value = values.get('error_class')
    if value in {'TimeoutError', 'PermissionError', 'ConnectionError', 'OSError', 'ValueError', 'RuntimeError', 'CancelledError', 'EngineError', 'UnknownError'}:
        out['error_class'] = value
    value = values.get('error_file')
    if isinstance(value, str) and len(value) <= 180 and re.fullmatch(r'[a-zA-Z0-9_/.-]+\.py', value) and not value.startswith('/') and '..' not in value.split('/'):
        out['error_file'] = value
    if 'causal' in values:
        from .observability_causal import validate
        out['causal'] = validate(values['causal'])
    return out


def process_start() -> str | None:
    """Read the OS process start token without environment or command arguments."""
    try:
        return Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


@functools.lru_cache(maxsize=1)
def _source_identity() -> dict:
    from ._version import kernel_version_bare
    source = Path(__file__).resolve()
    return {"version": kernel_version_bare() or "unknown", "source_digest": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_digest_scope": "observability-module"}


def descriptor(component: str, owner_uid: str, root: Path, state_dir: Path | None = None) -> dict:
    """Describe loaded diagnostic source rather than a developer checkout HEAD."""
    from ._version import kernel_version
    source = Path(__file__).resolve()
    actual_state = state_dir or root.parent
    result = {'schema_version': 1, 'component': component, 'owner_uid': owner_uid,
            'package_root': str(source.parent), **_source_identity(),
            'source_digest': hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_digest_scope': 'observability-module', 'workflow_revision': None,
            'pid': os.getpid(), 'process_start': process_start(), 'root': str(root),
            'events': str(root / 'events-*.jsonl'),
            'legacy_log': str(actual_state / 'cs_operator.log'),
            'native_log_root': str(actual_state / 'operator-runs'),
            'legacy_retention_days': 7, 'legacy_max_bytes': 32*1024**2}
    if state_dir is not None:
        base = state_dir / 'observability'
        result['namespace_base'] = str(base)
        result['legacy_flat_root'] = str(base) if next(base.glob('events-*.jsonl'), None) is not None else None
    return result


class EventStore:
    """Safe bounded event storage shared by command processes in one selected runtime."""

    def __init__(self, root: Path | str, owner_uid: str, component: str = 'kernel', *, max_bytes: int = 512 * 1024**2, retention_days: int = 30, segment_bytes: int = 4 * 1024**2, state_dir: Path | str | None = None, log_level: str = 'DEBUG'):
        if not isinstance(log_level, str) or log_level not in LEVELS:
            raise ValueError('invalid diagnostic log threshold')
        self.log_level = log_level
        self.root = Path(root).absolute()
        self.state_dir = Path(state_dir).absolute() if state_dir is not None else None
        if self.state_dir is None and self.root.parent.name == 'observability' and re.fullmatch(r'owner-[a-f0-9]{64}', self.root.name):
            self.state_dir = self.root.parent.parent
        self.namespace_base = self.state_dir / 'observability' if self.state_dir is not None else None
        self.owner_uid = owner_uid
        self.component = component
        self.max_bytes = max(MAX_EVENT_BYTES, max_bytes)
        self.retention_seconds = max(1, retention_days) * 86400
        self.segment_bytes = max(MAX_EVENT_BYTES, min(segment_bytes, self.max_bytes))
        self.failed_writes = 0
        self.dropped_events = 0

    def emit(self, stage: str, status: str, *, reason: str = 'unknown', effect_certainty: str = 'unknown', level: str | None = None, **metadata: Any) -> dict | None:
        """Persist one safe event or report degraded logging without raising."""
        try:
            if stage not in STAGES or status not in STATUSES or reason not in REASONS or effect_certainty not in CERTAINTY:
                raise ValueError('invalid diagnostic enum')
            selected_level = event_level({'status': status, **({'level': level} if level is not None else {})})
            if LEVELS[selected_level] < LEVELS[self.log_level]:
                return None
            from .observability_store import append
            ctx = current_context()
            event = {'schema_version': 1, 'event_id': uuid.uuid4().hex,
                     'timestamp': datetime.now(timezone.utc).isoformat(),
                     'monotonic_ns': time.monotonic_ns(), 'sequence': next(_SEQUENCE),
                     'component': self.component, 'owner_uid': self.owner_uid,
                     **_source_identity(),
                     'pid': os.getpid(), 'process_start': process_start(),
                     'trace_id': ctx.get('trace_id') or uuid.uuid4().hex,
                     'span_id': ctx.get('span_id') or uuid.uuid4().hex,
                     **{k: v for k, v in ctx.items() if k in _IDS},
                     'stage': stage, 'status': status, 'reason': reason, 'level': selected_level,
                     'effect_certainty': effect_certainty, **safe_metadata(metadata)}
            append(self, event)
            return event
        except Exception as exc:
            self.failed_writes += 1
            self.dropped_events += 1
            try:
                from .observability_store import record_failure
                record_failure(self, exc)
            except Exception:
                pass
            try:
                sys.stderr.write('[diagnostics] CRITICAL event unavailable; logging coverage degraded\n')
            except Exception:
                pass
            return None

    def events(self, cursor: str | None = None, trace_id: str | None = None, limit: int = 100) -> dict:
        """Read a bounded owner-scoped page and explicit coverage gaps."""
        from .observability_store import read_events
        return read_events(self, cursor=cursor, trace_id=trace_id, limit=limit)

    def prune(self) -> dict:
        """Run explicit service retention maintenance, separate from read-only queries."""
        from .observability_store import prune
        return prune(self)

    def recent(self, limit: int = 100) -> dict:
        """Inspect the latest observed failures within a bounded tail window."""
        from .observability_recent import read_recent
        return read_recent(self, limit=limit)

    def locations(self) -> dict:
        """Expose stable loaded-component locations and actual coverage."""
        try:
            result = descriptor(self.component, self.owner_uid, self.root, self.state_dir)
            result['log_level'] = self.log_level
            result['coverage'] = self.health()
            return result
        except Exception:
            return {'schema_version': 1, 'component': self.component, 'coverage': {'status': 'unavailable', 'available': False}}

    def health(self) -> dict:
        """Read coverage without initializing an absent log or manufacturing health."""
        from .observability_store import health
        return health(self)


@contextlib.contextmanager
def span(store: EventStore, stage: str, **metadata: Any) -> Iterator[dict]:
    """Record an observed lifecycle without modifying business exception semantics."""
    old = current_context()
    with context({**old, 'parent_span_id': old.get('span_id'), 'span_id': uuid.uuid4().hex}) as active:
        started = time.monotonic()
        store.emit(stage, 'start', reason='none', **metadata)
        try:
            yield active
        except BaseException as exc:
            store.emit(stage, 'failed', reason='cancelled' if type(exc).__name__ == 'CancelledError' else 'unknown', error_class=type(exc).__name__, elapsed_ms=(time.monotonic()-started)*1000, **metadata)
            raise
        else:
            store.emit(stage, 'result', reason='none', elapsed_ms=(time.monotonic()-started)*1000, **metadata)


def owner_root(state_dir: Path | str, owner_uid: str) -> Path:
    """Map a selected owner into a private opaque namespace without filesystem I/O."""
    if not isinstance(owner_uid, str):
        raise ValueError('selected owner must be a string')
    name = 'owner-' + hashlib.sha256(owner_uid.encode()).hexdigest()
    return Path(state_dir).absolute() / 'observability' / name


def store_for(settings: Any) -> EventStore:
    """Bind local diagnostics to one actual selected owner, without mixed records."""
    return EventStore(owner_root(settings.state_dir, settings.engine_owner_uid), settings.engine_owner_uid,
                      state_dir=settings.state_dir,
                      log_level=getattr(getattr(settings, 'observability', None), 'log_level', 'DEBUG'))
