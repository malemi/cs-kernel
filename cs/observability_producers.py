"""Best-effort source diagnostics preserving existing business results and authority."""
from __future__ import annotations

import contextlib
import functools
import inspect
import json
import os
import time
import uuid
from pathlib import Path

from .observability import context, current_context, store_for


def inherited_context() -> dict:
    """Read correlation IDs only; validation happens in the context boundary."""
    raw = os.environ.get('CS_DIAGNOSTIC_CONTEXT', '')
    if len(raw) > 1024:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def error_reason(exc: BaseException) -> str:
    name = type(exc).__name__
    if name in {'AuthenticationError', 'SMTPAuthenticationError', 'InvalidToken'}:
        return 'auth'
    if name in {'RateLimitError', 'InsufficientCreditsError'}:
        return 'quota'
    if isinstance(exc, PermissionError):
        return 'permission'
    if isinstance(exc, TimeoutError) or name in {'APITimeoutError', 'ReadTimeout'}:
        return 'timeout'
    if name in {'CancelledError', 'KeyboardInterrupt'}:
        return 'cancelled'
    if name in {'SMTPRecipientsRefused', 'SMTPDataError', 'SMTPSenderRefused'}:
        return 'provider-rejection'
    if name in {'OperationalError', 'IntegrityError'}:
        return 'persistence'
    return 'unknown'


def error_metadata(exc: BaseException) -> dict:
    """Preserve safe source provenance without messages, code lines or locals."""
    name = type(exc).__name__
    value = {'error_class': name if name in {'TimeoutError','PermissionError','ConnectionError','OSError','ValueError','RuntimeError','CancelledError','EngineError'} else 'UnknownError'}
    for attribute in ('code', 'status_code', 'smtp_code', 'sqlite_errorcode', 'errno'):
        try:
            code = getattr(exc, attribute, None)
            if type(code) is int and -(2**53) < code < 2**53:
                value['error_code'] = code
                break
        except Exception:
            pass
    trace = exc.__traceback__
    package = Path(__file__).resolve().parent
    while trace:
        try:
            relative = Path(trace.tb_frame.f_code.co_filename).resolve().relative_to(package)
            value.update(error_file='cs/'+relative.as_posix(), error_line=trace.tb_lineno)
        except (ValueError, OSError):
            pass
        trace = trace.tb_next
    return value


def emit(settings, stage, status, **metadata):
    """Drop diagnostic failure rather than changing the observed operation."""
    try:
        return store_for(settings).emit(stage, status, **metadata)
    except Exception:
        return None


def observe(stage, *, success='result', effect='unknown', identities=()):
    """Trace an existing synchronous operation without changing its return contract."""
    def decorate(function):
        signature = inspect.signature(function)
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            if stage == 'cli':
                import sys
                argv = kwargs.get('argv', args[0] if args else None)
                argv = sys.argv[1:] if argv is None else argv
                selected = list(argv)
                account_alias = None
                if selected[:1] == ['--account'] and len(selected)>1:
                    account_alias = selected[1]
                    selected = selected[2:]
                elif selected and selected[0].startswith('--account='):
                    account_alias = selected[0].partition('=')[2]
                    selected = selected[1:]
                if selected[:1] in (['logs'], ['monitor']):
                    return function(*args, **kwargs)
            settings, metadata = None, {}
            if stage == 'cli' and selected:
                known = {'init','update','login','plan','whoami','rpc','thread','contacted','history','unanswered','tasks','handled','escalated','business','dossier','chat','draft-send','ask','draft-reply','draft-delete','draft-retire','review','catchup','drive','accounts','config','memory','campaign','llm','project','instructions','cron','assignment','connection','stripe'}
                metadata['command'] = selected[0] if selected[0] in known else 'unknown'
                if selected[0] in {'draft-send','draft-retire'} and len(selected)>1:
                    metadata['draft_id'] = selected[1]
                if '--thread-id' in selected:
                    index = selected.index('--thread-id')
                    if index+1<len(selected):
                        metadata['root_id'] = selected[index+1]
            try:
                bound = signature.bind_partial(*args, **kwargs).arguments
                candidate = bound.get('settings')
                if candidate is not None and hasattr(candidate, 'state_dir'):
                    settings = candidate
                else:
                    from . import config
                    settings = config.load()
                    if stage == 'cli' and account_alias is not None:
                        uid = settings.account_map.get(account_alias)
                        if uid:
                            settings = config.load(engine_owner_uid=uid)
                        else:
                            settings = None
                for source, destination in identities:
                    value = bound.get(source)
                    if isinstance(value, str):
                        metadata[destination] = value
                for key in ('root', 'thread_key', 'thread_id', 'draft_id'):
                    if isinstance(bound.get(key), str):
                        metadata['draft_id' if key == 'draft_id' else 'root_id'] = bound[key]
                arguments = bound.get('args')
                if arguments is not None:
                    for key in ('thread_id', 'draft_id'):
                        if isinstance(getattr(arguments, key, None), str):
                            metadata['root_id' if key == 'thread_id' else 'draft_id'] = getattr(arguments, key)
                draft = bound.get('draft')
                if isinstance(draft, dict):
                    metadata.update({key: value for key, value in {'draft_id': draft.get('id'), 'root_id': draft.get('thread_id')}.items() if isinstance(value, str)})
            except Exception:
                pass
            old = current_context() or inherited_context()
            from . import observability_causal as causal
            scope = causal.scope() if stage == 'launch' or (stage == 'cli' and causal._STATE.get() is None) else contextlib.nullcontext()
            with scope, context({**old, **({'run_id': old.get('run_id') or uuid.uuid4().hex} if stage == 'launch' else {}), 'parent_span_id': old.get('span_id'), 'span_id': uuid.uuid4().hex}):
                started = time.monotonic()
                emit(settings, stage, 'start', reason='none', **metadata)
                try:
                    result = function(*args, **kwargs)
                except BaseException as exc:
                    if function.__name__ == "mirror" and stage == "verification":
                        from .observability_operations import record, summary
                        record(settings, {"cause": "unknown", "ok": False, "draft_id": metadata.get("draft_id"), "operation_id": bound.get("operation_id"), "effect_certainty": "unknown", "achieved_stages": ["engine-saved"]}, command="draft-reply", root=metadata.get("root_id"))
                        if summary():
                            metadata.update(summary()["metadata"])
                            metadata["causal"] = causal.selected()
                            metadata["effect_certainty"] = summary()["effect_certainty"]
                    if isinstance(exc, SystemExit) and exc.code in (None, 0):
                        emit(settings, stage, 'result', reason='none', exit_code=0, **metadata)
                    else:
                        if isinstance(exc, SystemExit) and type(exc.code) is int:
                            metadata['exit_code'] = exc.code
                        emit(settings, stage, 'unknown-effect' if stage in {'provider','cleanup'} else 'failed', reason=error_reason(exc), **error_metadata(exc), **metadata)
                    raise
                status, certainty, reason = success, effect, 'none'
                if type(result) is int:
                    metadata['exit_code'] = result
                    if result == 3:
                        status, reason = 'held', 'incomplete-input'
                    elif result == 5:
                        status, certainty = 'unknown-effect', 'unknown'
                    elif result != 0:
                        status, reason = 'failed', 'unknown'
                elif isinstance(result, dict):
                    if result.get('outcome_uncertain') is True or result.get('partial') is True:
                        status, certainty, reason = 'unknown-effect', 'unknown', 'unknown'
                    elif result.get('ok') is False:
                        status, certainty, reason = 'failed', 'none', 'unknown'
                if status in {'failed','held','unknown-effect'}:
                    certainty = 'unknown'
                from .observability_operations import summary, record
                if isinstance(result, dict) and 'cause' in result:
                    record(settings, result, command='draft-retire' if stage == 'cleanup' else 'draft-reply', root=metadata.get('root_id'))
                operation = summary()
                if operation:
                    status, certainty, reason = operation['status'], operation['effect_certainty'], operation['reason']
                    metadata.update(operation['metadata'])
                selected_cause = causal.selected() if stage == 'launch' or operation else None
                if stage == 'launch' and selected_cause is None:
                    selected_cause = causal.decision('causal_evidence', 'unknown', layer='supervisor', outcome='unknown', method='operator.tick', **({'process_exit': result} if type(result) is int else {}))
                if selected_cause:
                    metadata.update(causal=selected_cause)
                    if stage == 'launch':
                        metadata['method'] = 'operator.tick'
                with context({**current_context(), **({'attempt_id': selected_cause['refs']['attempt_id']} if selected_cause and selected_cause['refs']['attempt_id'] else {})}):
                    emit(settings, stage, status, reason=reason, effect_certainty=certainty, elapsed_ms=(time.monotonic()-started)*1000, **metadata)
                return result
        return wrapped
    return decorate


def launch_main(argv=None):
    """Internal launcher adapter emitting only fixed statuses and validated IDs."""
    import sys
    argv = sys.argv[1:] if argv is None else argv
    status = argv[0] if argv else 'unknown'
    if status not in {'start','running','paused','lock-skipped','result','failed'}:
        return 2
    try:
        from . import config
        settings = config.load()
        from .observability_retention import maintain
        maintain(settings)
        original = inherited_context()
        original.setdefault('run_id', uuid.uuid4().hex)
        with context(original) as active:
            values = {}
            if len(argv) > 1 and argv[1].lstrip('-').isdigit():
                values['exit_code'] = int(argv[1])
            from .observability_causal import decision
            observation = decision('causal_evidence', 'unknown', layer='wrapper', outcome='unknown', **({'process_exit': values['exit_code']} if 'exit_code' in values else {}))
            emit(settings, 'launch', status, reason='none', **values, **({'causal': observation} if observation else {}))
            if status == 'start':
                print(json.dumps(active, separators=(',',':')))
        return 0
    except Exception:
        return 0


if __name__ == '__main__':
    raise SystemExit(launch_main())
