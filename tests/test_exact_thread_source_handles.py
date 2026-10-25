import asyncio
from types import SimpleNamespace
from unittest.mock import patch
import os
from uuid import uuid4

from cs import cli, gmail_drafts, rpc, task_assignment

ROOT = '<neutral-source-4a9@example.test>'
INTENT = 'Compose a reply based on the message.'
IDS = [str(uuid4()), str(uuid4())]


def invoke(response, *, source_id=None, hold=None, scheduled=True, chat_impl=None):
    calls = []
    settings = SimpleNamespace(engine_owner_uid='alice', email_address='alice@example.test')
    args = SimpleNamespace(thread_id=ROOT, message=INTENT, timeout=37, source_id=source_id)

    def call(settings, method, params, timeout=None):
        calls.append((method, params, timeout))
        if method == 'emails.list_by_thread':
            if isinstance(response, Exception):
                raise response
            return response
        assert method == 'drafts.list'
        return []

    def guard(settings, root):
        calls.append(('guard', root))
        if hold:
            raise task_assignment.AssignmentUnavailable('held')

    async def chat(settings, message, **kwargs):
        calls.append(('chat', message, kwargs))
        if chat_impl:
            return await chat_impl(settings, message, **kwargs)
        return {'result': {'response': 'Source-context test only'}}

    with patch.dict(os.environ, {'CS_OPERATOR_HEADLESS': '1'}), patch.object(cli.config, 'load', return_value=settings), patch.object(cli, '_scheduled_workset_scope', return_value=scheduled), patch.object(task_assignment, 'guard', side_effect=guard), patch.object(rpc, 'call_sync', side_effect=call), patch.object(rpc, 'chat', side_effect=chat), patch.object(gmail_drafts, 'append_draft', side_effect=AssertionError('unexpected mirror')):
        return cli.cmd_draft_reply(args), calls


def test_valid_context_only():
    rc, calls = invoke({'emails': [{'id': i, 'body_plain': 'SECRET BODY', 'subject': 'SECRET SUBJECT'} for i in IDS]})
    assert rc == 0
    assert [c[0] for c in calls] == ['guard', 'emails.list_by_thread', 'drafts.list', 'chat', 'drafts.list']
    assert calls[1] == ('emails.list_by_thread', {'thread_id': ROOT}, 37)
    message, kwargs = calls[3][1:]
    assert message.endswith(INTENT) and ROOT in message and 'read_email' in message
    assert all(message.count(i) == 1 for i in IDS) and 'SECRET' not in message
    assert message.index(IDS[0]) < message.index(IDS[1])
    assert kwargs['assignment_thread_key'] == ROOT and kwargs['email_context'] is None and kwargs['allow_tools'] == set()


def test_upper_bound_and_uuid_forms():
    handles = [str(uuid4()) for _ in range(100)]
    rc, calls = invoke({'emails': [{'id': value} for value in handles]})
    assert rc == 0 and all(value in calls[3][1] for value in handles)
    for value in ('not-a-uuid', '{' + IDS[0] + '}', 'urn:uuid:' + IDS[0], ' ' + IDS[0], IDS[0] + '\n', None, True):
        rc, calls = invoke({'emails': [{'id': value}]})
        assert rc == 3 and [c[0] for c in calls] == ['guard', 'emails.list_by_thread']


def test_bad_reads_hold_before_generation():
    invalid = [None, [], {}, {'emails': None}, {'emails': []}, {'emails': {}}, {'emails': [None]}, {'emails': [{}]}, {'emails': [{'id': 4}]}, {'emails': [{'id': IDS[0].upper()}]}, {'emails': [{'id': IDS[0].replace('-', '')}]}, {'emails': [{'id': IDS[0]}, {'id': IDS[0]}]}, {'emails': [{'id': str(uuid4())} for _ in range(101)]}, RuntimeError('read unavailable')]
    for response in invalid:
        rc, calls = invoke(response)
        assert rc == 3 and [c[0] for c in calls] == ['guard', 'emails.list_by_thread'], response


def test_admission_and_explicit_context_unchanged():
    rc, calls = invoke({}, scheduled=False)
    assert rc == 3 and calls == []
    rc, calls = invoke({}, hold=True)
    assert rc == 3 and [c[0] for c in calls] == ['guard']
    rc, calls = invoke({}, source_id=IDS[0])
    assert rc == 0 and 'emails.list_by_thread' not in [c[0] for c in calls]
    assert calls[2][1] == INTENT and calls[2][2]['email_context'] == {'thread_key': ROOT, 'source_email_id': IDS[0]}

    async def refuse(*a, **k):
        raise RuntimeError('contextual email capability unavailable')

    rc, calls = invoke({}, source_id=IDS[0], chat_impl=refuse)
    assert rc == 3 and [c[0] for c in calls] == ['guard', 'drafts.list', 'chat']


if __name__ == '__main__':
    test_valid_context_only()
    test_upper_bound_and_uuid_forms()
    test_bad_reads_hold_before_generation()
    test_admission_and_explicit_context_unchanged()
    print('PASS: actual CLI source handles, 14 malformed/error holds, admission, explicit-context capability refusal')
