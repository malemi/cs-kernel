"""Synthetic transport for the installed public module entry; no engine proof."""
import json
from pathlib import Path
import runpy
import socket
import sys
import sysconfig
from unittest.mock import patch

import cs
from cs import config, gmail_drafts, rpc
from assignment_fixture import normal_projection
from test_interactive_draft_continuity import DRAFT, ROOT, TARGET

mode, journal_name = sys.argv[1:3]
arguments = sys.argv[3:]
journal = Path(journal_name)
package = Path(cs.__file__).resolve().parent
assert package == Path(sysconfig.get_paths()['purelib']) / 'cs', package
settings = config.Settings(_env_file=(), email_address=DRAFT['owner_id'], engine_owner_uid='fixture-owner',
                           db_path=str(journal.with_suffix('.sqlite')))
state = json.loads(journal.read_text()) if journal.exists() else {'calls': [], 'dispatches': 0, 'operation': None, 'generation': 0}
state['package_root'] = str(package)
binding = {'root': ROOT, 'target': TARGET, 'recipients': DRAFT['to_addresses'], 'cc': []}
snapshot = 'a' * 64
handle = {'folder': 'Drafts', 'uid': '17', 'uidvalidity': '9', 'raw_fingerprint': 'b' * 64}


def forbidden(*args, **kwargs):
    raise AssertionError('provider, credential or socket operation forbidden')


async def no_generation(*args, **kwargs):
    state['generation'] += 1
    raise AssertionError('generation forbidden')


def call(selected, method, params, **kwargs):
    trace = {'method': method, 'params': params, 'scripted_reply': 'entered'}
    state['calls'].append(trace)
    if method == 'system.capabilities':
        trace['scripted_reply'] = 'capabilities'
        return {'exact_draft_publication': 1, 'sent_mirror_recovery': 1, 'interactive_exact_send': 1}
    if method == 'drafts.inspect':
        assert params == {'draft_id': DRAFT['id']}
        trace['scripted_reply'] = 'draft-inspection'
        return {'ok': True, 'draft_id': DRAFT['id'], 'engine_owner_uid': selected.engine_owner_uid,
                'owner_id': selected.email_address, 'draft': DRAFT, 'expected_snapshot': snapshot}
    if method == 'tasks.assignment.project':
        assert mode == 'send'
        trace['scripted_reply'] = 'normal-assignment'
        return normal_projection(selected, params)
    if method == 'drafts.operator_send_inspect':
        assert mode == 'send' and params == {'draft_id': DRAFT['id']}
        trace['scripted_reply'] = 'operator-inspection'
        return {'ok': True, 'draft_id': DRAFT['id'], 'owner_uid': selected.engine_owner_uid,
                'owner_id': selected.email_address, 'draft': DRAFT, 'binding': binding, 'expected_snapshot': snapshot}
    if method == 'drafts.operation_status':
        previous = None if state['operation'] is None else {
            'owner_uid': selected.engine_owner_uid, 'draft_id': DRAFT['id'],
            'operation_id': state['operation'], 'operation_type': 'send', 'canonical_root': ROOT,
            'expected_snapshot': snapshot, 'binding': {**binding, 'transport': {
                'message_id': '<sent@example.test>', 'mime_digest': 'c' * 64}},
            'stage': 'dispatch_possible', 'active': True, 'version': 1}
        trace['scripted_reply'] = 'operation-active' if previous is not None else 'operation-absent'
        return {'ok': previous is not None, 'operation': previous}
    expected_method = {'resume': 'drafts.publish_review', 'retire': 'drafts.retire_sent_mirror', 'send': 'drafts.send_operator'}[mode]
    assert method == expected_method, method
    assert params['draft_id'] == DRAFT['id'] and params['expected_snapshot'] == snapshot
    operation = params['operation_id']
    answer = {'version': 1, 'ok': False, 'draft_id': DRAFT['id'], 'operation_id': operation,
              'owner_uid': selected.engine_owner_uid, 'owner_id': selected.email_address,
              'root': ROOT, 'expected_snapshot': snapshot, 'effect_certainty': 'unknown',
              'achieved_stages': ['engine-saved'], 'next_action': 'inspect-operation'}
    if mode == 'retire':
        assert params['thread_id'] == ROOT
        if not params['commit']:
            assert params['target'] == {'uid': '17', 'uidvalidity': '9'}
            trace['scripted_reply'] = 'retirement-preview'
            return {**answer, 'ok': True, 'dry_run': True, 'target': handle,
                    'effect_certainty': 'not-dispatched', 'cause': 'preview'}
        assert params['target'] == handle
    elif mode == 'resume':
        assert params['thread_id'] == ROOT
    else:
        assert params['binding'] == binding and params['reason'] == 'explicit_operator_request' and params['version'] == 1
        answer.update(state='delivery-unknown', cause='exact_send_unconfirmed',
                      cleanup_certainty='not-dispatched', audit_reason='explicit_operator_request')
    if state['operation'] is None:
        state['operation'] = operation
        state['dispatches'] += 1
        trace['scripted_reply'] = 'dispatch-timeout'
        raise TimeoutError('synthetic transport acknowledgement lost')
    assert state['operation'] == operation
    if mode == 'resume':
        answer.update(state='publication-failed', cause='publication_outcome_unresolved')
    elif mode == 'retire':
        answer.update(cause='retirement_unconfirmed', engine_discarded=False)
    trace['scripted_reply'] = {'resume': 'publication-unknown', 'retire': 'retirement-unknown', 'send': 'send-unknown'}[mode]
    return answer


sys.argv = ['cs', *arguments]
try:
    with patch.object(config, 'load', return_value=settings), patch.object(rpc, 'call_sync', side_effect=call), \
         patch.object(rpc, 'chat', side_effect=no_generation), patch.object(gmail_drafts, '_imap', side_effect=forbidden), \
         patch.object(socket.socket, 'connect', side_effect=forbidden), patch.object(socket, 'create_connection', side_effect=forbidden):
        runpy.run_module('cs', run_name='__main__')
finally:
    journal.write_text(json.dumps(state, sort_keys=True))
