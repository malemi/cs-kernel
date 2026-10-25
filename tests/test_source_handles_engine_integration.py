import asyncio
import json
import subprocess
import importlib.util
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest

if not os.environ.get('MRCALL_TEST_ENGINE_ROOT'):
    pytest.skip('MRCALL_TEST_ENGINE_ROOT is required for the real engine integration', allow_module_level=True)
ENGINE = Path(os.environ['MRCALL_TEST_ENGINE_ROOT']).resolve()
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ENGINE / 'tests' / 'assignments'))
spec = importlib.util.spec_from_file_location('source_handles_assignment_fixtures', ENGINE / 'tests' / 'assignments' / 'conftest.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
env = fixtures.env

from mail_fixture import MailFixture, ROOT
from test_evidence_rpc import assign
from zylch.services import task_assignment_draft_policy as policy
from zylch.services.task_assignment_types import AssignmentError
from zylch.storage import database as db
from zylch.storage.models import Email, Draft
from zylch.storage.storage import Storage
from zylch.tools.read_email_tool import ReadEmailTool
from zylch.tools.base import ToolStatus
KERNEL = Path(__file__).resolve().parents[1]


@pytest.fixture
def mail(env, monkeypatch):
    value = MailFixture(monkeypatch)
    with db.get_session() as session:
        session.query(Email).filter(Email.id == value.reply_id).delete()
    value.messages['"Sent"'].clear()
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: pytest.fail('external socket forbidden'))
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('external socket forbidden'))
    return value


def values(root=ROOT, owner='alice@example.test'):
    return dict(owner_id=owner, to='customer@example.test', subject='Context fixture', body='Tool boundary fixture', thread_id=root, in_reply_to=root, references=[root])


def test_cli_context_enters_actual_guarded_process_and_read_tool(env, mail, monkeypatch):
    assert Path(policy.__file__).resolve().is_relative_to(ENGINE)
    storage = Storage.get_instance()
    original = storage.get_thread_emails('alice@example.test', ROOT)
    assert original and all(ROOT not in (row.get('body_plain') or '') and ROOT not in (row.get('subject') or '') for row in original)
    seen = []

    class Agent:
        def clear_history(self):
            pass

        async def process_message(self, user_message, context, **kwargs):
            assert mail.root_id in user_message and 'read_email' in user_message
            assert context == {'user_id': 'alice@example.test', 'thread_id': ROOT}
            result = await ReadEmailTool(storage, owner_id='alice@example.test').execute(email_id=mail.root_id)
            assert result.status == ToolStatus.SUCCESS and result.data['id'] == mail.root_id
            assert result.data['body_plain'] == 'A real reply\n' or result.data['body_plain'] == 'A real reply'
            seen.append(result.data['id'])
            return 'Source read completed; no business answer generated'

    service = SimpleNamespace(agent=Agent())

    async def initialize(**kwargs):
        assert kwargs['owner_id'] == 'alice@example.test'

    service._initialize_agent = initialize
    script = """
import contextlib, io, json, sys
import test_exact_thread_source_handles as fixture
fixture.ROOT = sys.argv[1]
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    rc, calls = fixture.invoke(json.loads(sys.argv[2]))
assert rc == 0
assert [c[0] for c in calls] == ['guard', 'emails.list_by_thread', 'drafts.list', 'chat', 'drafts.list']
print(json.dumps(calls[3][1]))
"""
    child_env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(KERNEL) + os.pathsep + str(KERNEL / 'tests'))
    completed = subprocess.run([str(KERNEL / '.venv' / 'bin' / 'python'), '-B', '-c', script, ROOT, json.dumps({'emails': original}, default=str)], env=child_env, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    message = json.loads(completed.stdout)
    with policy.scope(ROOT):
        result = asyncio.run(policy.process_chat(service, message, 'alice@example.test', None, 'fixture', None))
    assert seen == [mail.root_id] and result['metadata']['assignment_draft_policy'] == 1
    with db.get_session() as session:
        assert session.query(Draft).count() == 0


def test_context_never_grants_wrong_owner_thread_or_held_write(env, mail):
    storage = Storage.get_instance()
    with policy.scope(ROOT):
        for payload in (values('<wrong@example.test>'), values(owner='bob@example.test')):
            with pytest.raises(AssignmentError):
                storage.create_draft(**payload)
    assert asyncio.run(ReadEmailTool(storage, owner_id='bob@example.test').execute(email_id=mail.root_id)).status == ToolStatus.ERROR
    assign(env)
    with policy.scope(ROOT), pytest.raises(AssignmentError):
        storage.create_draft(**values())
    with db.get_session() as session:
        assert session.query(Draft).count() == 0


def test_concurrent_assignment_change_rechecked_before_write(env, mail, monkeypatch):
    storage = Storage.get_instance()
    original = policy.projection.project
    assigned = []

    def intervening(root):
        value = original(root)
        if not assigned:
            assigned.append(assign(env))
        return value

    monkeypatch.setattr(policy.projection, 'project', intervening)
    with policy.scope(ROOT), pytest.raises(AssignmentError, match='Assignment changed'):
        storage.create_draft(**values())
    with db.get_session() as session:
        assert session.query(Draft).count() == 0


def test_held_or_wrong_owner_process_stops_before_agent(env, mail):
    async def forbidden(**kwargs):
        pytest.fail('held routing reached agent')

    service = SimpleNamespace(_initialize_agent=forbidden)
    with policy.scope(ROOT), pytest.raises(AssignmentError, match='owner mismatch'):
        asyncio.run(policy.process_chat(service, 'Read source context', 'bob@example.test', None, 'fixture', None))
    assign(env)
    with policy.scope(ROOT), pytest.raises(AssignmentError, match='holds this draft before routing'):
        asyncio.run(policy.process_chat(service, 'Read source context', 'alice@example.test', None, 'fixture', None))
