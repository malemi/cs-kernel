"""Bounded causal decisions at existing supervisor predicates."""
from __future__ import annotations

import contextlib
import contextvars
import functools
import hashlib
import re
import uuid

PAIRS = {
    'exact_draft_operation': {'thread_conflict', 'saved_unpublished', 'explicit_operator_request', 'automatic_manual_hold', 'assignment_hold', 'changed_snapshot', 'uncertain_provider_outcome', 'review_verified', 'sent_verified_cleanup_pending', 'mirror_retired', 'operation_held', 'operation_not_dispatched', 'unsupported_operation', 'local_send_hold'},
    'supervisor_completion': {'run_verified'},
    'required_phase_presence': {'required_phase_absent'},
    'discovery_tool_cardinality': {'discovery_cardinality_invalid'},
    'read_tool_identity': {'read_tool_id_invalid', 'read_tool_id_duplicate'},
    'read_result_uniqueness': {'read_result_duplicate'},
    'read_error_proof_cardinality': {'read_error_unproved'},
    'read_result_completeness': {'read_result_missing'},
    'process_exit': {'process_nonzero'}, 'native_capture_json': {'native_capture_malformed'},
    'native_capture_capacity': {'native_capture_overflow'}, 'process_wait': {'process_wait_timeout'},
    'native_terminal_presence': {'terminal_unavailable'}, 'native_terminal_error': {'terminal_error'},
    'native_terminal_reason': {'terminal_rejected'},
    'discovery_artifact_presence': {'artifact_missing'}, 'discovery_artifact_access': {'artifact_unreadable'},
    'discovery_artifact_encoding': {'artifact_invalid'}, 'discovery_identity': {'identity_mismatch'},
    'discovery_payload_digest': {'digest_mismatch'}, 'discovery_payload_shape': {'shape_invalid'},
    'discovery_exit': {'exit_mismatch'}, 'workset_identity': {'workset_invalid'},
    'workset_reservation': {'reservation_mismatch'},
    'ordinary_health_result': {'mailbox_read_incomplete', 'assignment_read_incomplete',
        'execution_operation_failed', 'discovery_inspection_incomplete', 'discovery_transport_invalid',
        'execution_read_failed', 'legitimate_hold', 'complete_empty'},
    'notice_persistence': {'record_write_failed'}, 'mode_authority': {'mode_mismatch'},
    'mail_intake': {'intake_failed'}, 'pause_state': {'paused'},
    'fallback_configuration': {'fallback_unconfigured'}, 'fallback_credential': {'credential_unavailable'},
    'fallback_model_report': {'model_unreported'}, 'supervisor_exception': {'supervisor_exception'},
    'causal_evidence': {'unknown'},
}
PHASES = {'identity', 'configuration', 'tasks', 'discovery', 'review', 'campaigns', 'founder_tasks', 'founder_ask'}
COMMANDS = {'whoami', 'config', 'tasks', 'unanswered', 'review', 'campaign', 'ask', 'dossier', 'contacted', 'history', 'assignment', 'draft-reply', 'draft-send', 'draft-retire', 'chat'}
METHODS = {'sync.run', 'operator.notice', 'operator.health.assess', 'operator.health.inspection', 'operator.health.native_read', 'operator.native.terminal', 'operator.tick'}
FACTS = {'required', 'present', 'expected', 'observed', 'uses', 'results', 'reads', 'completed', 'matching_proofs', 'process_exit', 'malformed', 'overflow', 'timed_out', 'native_is_error', 'delivery_ok', 'no_work_proven', 'engine_saved', 'review_visible', 'sent_verified', 'cleanup_verified', 'operator_requested'}
REFS = ('run_id', 'attempt_id', 'child_event_id', 'cause_event_id', 'tool_id_hash', 'session_id_hash')
_STATE = contextvars.ContextVar('causal_decision', default=None)


def _validate(value):
    if not isinstance(value, dict) or set(value) != {'version', 'layer', 'check', 'cause', 'outcome', 'phase', 'command', 'method', 'facts', 'refs', 'missing_refs', 'evidence_complete'}:
        raise ValueError('Invalid causal shape')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid causal version')
    if value['layer'] not in {'process', 'native', 'ordinary_health', 'intake', 'configuration', 'notice', 'supervisor', 'wrapper', 'exact_draft'} or value['outcome'] not in {'accepted', 'failed', 'held', 'unknown'}:
        raise ValueError('Invalid causal outcome')
    if value['check'] not in PAIRS or value['cause'] not in PAIRS[value['check']]:
        raise ValueError('Invalid causal pair')
    for key, allowed in (('phase', PHASES), ('command', COMMANDS), ('method', METHODS)):
        if value[key] is not None and value[key] not in allowed:
            raise ValueError('Invalid causal source')
    facts = value['facts']
    if not isinstance(facts, dict) or len(facts) > 16 or set(facts) - FACTS:
        raise ValueError('Invalid causal facts')
    for key, item in facts.items():
        if type(item) not in (bool, int) or (type(item) is int and (not -(2**53) < item < 2**53 or (key != 'process_exit' and item < 0))):
            raise ValueError('Invalid causal fact')
    refs = value['refs']
    if not isinstance(refs, dict) or set(refs) != set(REFS):
        raise ValueError('Invalid causal references')
    for key, item in refs.items():
        if item is not None and (not isinstance(item, str) or not re.fullmatch('[a-f0-9]{64}' if key.endswith('_hash') else '[a-f0-9]{32}', item)):
            raise ValueError('Invalid causal reference')
    missing = value['missing_refs']
    if not isinstance(missing, list) or len(missing) != len(set(missing)) or set(missing) != {key for key in REFS if refs[key] is None}:
        raise ValueError('Invalid missing causal references')
    if type(value['evidence_complete']) is not bool or (not value['evidence_complete'] and value['cause'] != 'unknown') or (value['cause'] == 'unknown' and (value['outcome'] != 'unknown' or value['evidence_complete'])):
        raise ValueError('Invalid causal completeness')
    return value


def validate(value):
    try:
        return _validate(value)
    except (TypeError, KeyError) as exc:
        raise ValueError('Invalid causal value') from exc


@contextlib.contextmanager
def scope():
    state = {'causal': None, 'child_event_id': None}
    token = _STATE.set(state)
    try:
        yield state
    finally:
        _STATE.reset(token)


def decision(check, cause, *, layer='ordinary_health', phase=None, command=None, method=None, outcome='failed', tool=None, session=None, replace=False, **facts):
    try:
        from .observability import current_context, diagnostic_id
        state = _STATE.get()
        ctx = {**(state.get('selected_context', {}) if state else {}), **current_context()}
        if state and state.get('selected_context', {}).get('attempt_id'):
            ctx['attempt_id'] = state['selected_context']['attempt_id']
        refs = {key: None for key in REFS}
        if state is not None and state.get('causal'):
            refs.update(state['causal']['refs'])
        refs.update(run_id=ctx.get('run_id') or refs['run_id'], attempt_id=ctx.get('attempt_id') or refs['attempt_id'], child_event_id=(state.get('child_event_id') if state else None) or refs['child_event_id'])
        for key, item in (('tool_id_hash', tool), ('session_id_hash', session)):
            if isinstance(item, str) and item:
                refs[key] = hashlib.sha256(item.encode()).hexdigest()
        if state is not None and state.get('process_exit') is not None:
            facts.setdefault('process_exit', state['process_exit'])
        value = validate(dict(version=1, layer=layer, check=check, cause=cause, outcome=outcome, phase=phase, command=command, method=method, facts=facts, refs=refs, missing_refs=[key for key in REFS if refs[key] is None], evidence_complete=cause != 'unknown'))
        if state is not None and (replace or state['causal'] is None or (state['causal']['outcome'] in {'accepted', 'held'} and outcome == 'failed')):
            state['causal'] = value
        return value
    except Exception:
        return None


def selected():
    state = _STATE.get()
    return state.get('causal') if state else None


def select(attempt):
    state = _STATE.get()
    if state is not None:
        state['causal'] = state.get('fatal_notice') or getattr(attempt, 'causal', None)
        state['selected_context'] = getattr(attempt, 'diagnostic_context', {})
        state['child_event_id'] = getattr(attempt, 'child_event_id', None)
        if state.get('fatal_notice'):
            selected = state['fatal_notice']
            refs = {**selected['refs'], **{key: value for key, value in state['selected_context'].items() if key in {'run_id', 'attempt_id'}}, 'child_event_id': state['child_event_id']}
            state['causal'] = validate({**selected, 'refs': refs, 'missing_refs': [key for key in REFS if refs[key] is None]})


def retain_notice():
    state = _STATE.get()
    if state is not None and state.get('causal') and state['causal']['check'] == 'notice_persistence':
        state['fatal_notice'] = state['causal']


def child(event):
    state = _STATE.get()
    if state is not None and event:
        state['child_event_id'] = event['event_id']
        state['process_exit'] = event.get('exit_code')


def cause(event):
    try:
        from .observability import diagnostic_id
        state = _STATE.get()
        reference = diagnostic_id(event.get('event_id')) if isinstance(event, dict) else None
        if state is None or state.get('causal') is None or reference is None:
            return
        selected = state['causal']
        refs = {**selected['refs'], 'cause_event_id': reference}
        state['causal'] = validate({**selected, 'refs': refs, 'missing_refs': [key for key in REFS if refs[key] is None]})
    except Exception:
        return


def attempt_scope(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        from .observability import context, current_context
        with scope() as state, context({**current_context(), 'attempt_id': uuid.uuid4().hex}):
            result = function(*args, **kwargs)
            result.causal = state['causal']
            result.child_event_id = state['child_event_id']
            result.diagnostic_context = current_context()
            return result
    return wrapped
