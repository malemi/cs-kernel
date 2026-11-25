from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from . import auth, login, project_init, rpc
from ._version import kernel_version_bare
from .config import Settings
from .project_documents import _read_bounded, safe_ancestors

META = '.cs-desktop.json'


class ManagedError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def json_read(path, limit=65536):
    try:
        value = json.loads(_read_bounded(path, limit, 'Managed metadata'))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except Exception:
        raise ManagedError('invalid_metadata', 'Cannot read managed configuration; reconnect in Desktop.') from None


def atomic_json(path, value):
    safe_ancestors(path)
    fd, temporary = tempfile.mkstemp(prefix='.cs-managed-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def descriptor_read(path):
    path = safe_ancestors(path)
    data = json_read(path)
    if data.get('version') != 1 or not all(isinstance(data.get(k), str) and data[k] for k in login.REQUIRED_STRING_FIELDS):
        raise ManagedError('invalid_descriptor', 'Desktop sign-in is unavailable; sign in again in Desktop.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', data['uid']):
        raise ManagedError('invalid_identity', 'Desktop identity is invalid; sign in again.')
    endpoint = login.descriptor_ws_base(data)
    parsed = urlsplit(endpoint)
    if (parsed.scheme not in ('ws', 'wss') or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')
            or (parsed.scheme == 'ws' and parsed.hostname not in ('127.0.0.1', 'localhost', '::1'))):
        raise ManagedError('invalid_endpoint', 'Use a secure engine endpoint or a loopback development engine.')
    if not re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', data['email']):
        raise ManagedError('invalid_identity', 'Desktop mailbox identity is invalid.')
    data['endpoint'] = endpoint.rstrip('/')
    return data


def public_status(workspace, binding):
    return {'ok': True, 'workspace': str(workspace), **{k: binding[k] for k in ('uid', 'email', 'endpoint', 'company', 'state', 'kernel_version')}}


def load_binding(workspace, *, active=True):
    workspace = safe_ancestors(workspace)
    value = json_read(workspace / META)
    if value.get('version') != 1 or not all(isinstance(value.get(k), str) and value[k] for k in ('uid', 'email', 'endpoint', 'descriptor', 'company', 'kernel_version', 'generation', 'space_id')):
        raise ManagedError('invalid_binding', 'Workspace binding is invalid; reconnect in Desktop.')
    if active and value.get('state') != 'ready':
        raise ManagedError('revoked', 'Workspace access was revoked; reconnect in Desktop.')
    return value


def check_descriptor(workspace, binding):
    current = load_binding(workspace)
    if current['generation'] != binding['generation']:
        raise ManagedError('revoked', 'Workspace connection changed; restart the client connector.')
    descriptor_path = safe_ancestors(binding['descriptor'])
    if safe_ancestors(workspace) != descriptor_path.parent / 'operator-workspace':
        raise ManagedError('unsafe_workspace', 'Workspace is outside its Desktop profile directory.')
    descriptor = descriptor_read(descriptor_path)
    if any(descriptor[k] != binding[k] for k in ('uid', 'email', 'endpoint')):
        raise ManagedError('binding_changed', 'Desktop profile or endpoint changed; reconnect the workspace.')
    return descriptor


def settings_for(descriptor):
    class BoundSettings(Settings):
        @classmethod
        def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
            return (init_settings,)
    return BoundSettings(_env_file=None, engine_owner_uid=descriptor['uid'], engine_ws_url=descriptor['endpoint'],
                    firebase_web_api_key=descriptor['firebase_web_api_key'], email_address=descriptor['email'],
                    accounts='', read_mailboxes='', read_mailbox_passwords='', email_password='', slug='desktop-managed')


async def authenticated_client(descriptor):
    import asyncio
    settings = settings_for(descriptor)
    try:
        session = await asyncio.to_thread(auth._exchange, settings, descriptor['refresh_token'])
        if session.get('user_id') != descriptor['uid'] or not session.get('id_token'):
            raise ManagedError('identity_mismatch', 'Engine authentication does not match the selected Desktop profile.')
        client = rpc.EngineClient(settings, id_token=session['id_token'])
        await client.__aenter__()
        try:
            identity = await client.call('account.who_am_i', {}, timeout=20)
            if not login.identity_verified(identity, descriptor['uid']):
                raise ManagedError('identity_mismatch', 'Engine identity does not match the selected Desktop profile.')
        except BaseException:
            await client.__aexit__()
            raise
        return client
    except ManagedError:
        raise
    except Exception:
        raise ManagedError('engine_unavailable', 'Cannot authenticate the engine; check its connection and sign in again.') from None


def render_config(company, descriptor):
    name = company.strip()
    if not name or len(name) > 120 or any(ord(c) < 32 or c in '\\"' for c in name):
        raise ManagedError('invalid_company', 'Use a company name of 1–120 characters without quotes or control characters.')
    slug = project_init.get_company_slug(name)
    if not slug or len(slug) > 80:
        raise ManagedError('invalid_company', 'Use a company name containing letters or numbers.')
    return dict(project_init.TEMPLATE_DEFAULTS, company_name=name, company_display_name=name, company_from_name=name,
                company_slug=slug, company_prog_name=slug + '-cs', email_address=descriptor['email'],
                imap_host='', imap_port=993, smtp_host='', smtp_port=587, engine_ws_url=descriptor['endpoint'],
                engine_owner_uid=descriptor['uid'], accounts={'operator': descriptor['uid']}, accounts_default='operator',
                founder_sweep_enabled=False, founder_sweep_account='', crm_adapter='none', crm_shopify=None,
                producer_adapter='none', producer_mrcall_tracking=None, excluded_campaign='', drive_scope='',
                sms_enabled=False, cron_schedule=project_init.DEFAULT_CRON_SCHEDULE, cron_comment=project_init.DEFAULT_CRON_COMMENT,
                timezone='UTC', sms_hour=18, reminder_max=3, dedup_days=30, cs_triage_mode='draft',
                system_senders='', send_guard_min_chars=80, send_guard_banned_phrases='', platform_env_path='',
                repo_git_remote='', repo_kernel_version=kernel_version_bare(), repo_docs_shape='as-built')


@contextlib.contextmanager
def workspace_lock(workspace):
    lock = safe_ancestors(workspace.parent / ('.' + workspace.name + '.init-lock'))
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    acquired = False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ManagedError('unsafe_workspace', 'Workspace lock must be a regular private file.')
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b'\0')
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise ManagedError('workspace_busy', 'Workspace operation is already running; retry after it finishes.') from None
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                import msvcrt
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


async def initialize(descriptor_path, workspace, company):
    descriptor_path = safe_ancestors(descriptor_path)
    workspace = safe_ancestors(workspace)
    if workspace != descriptor_path.parent / 'operator-workspace':
        raise ManagedError('unsafe_workspace', 'Use the managed workspace in the selected Desktop profile directory.')
    descriptor = descriptor_read(descriptor_path)
    config = render_config(company, descriptor)
    client = await authenticated_client(descriptor)
    try:
        company_scope = await client.call('projects.list', {'limit': 1, 'offset': 0}, timeout=20)
        space_id = company_scope.get('space_id') if isinstance(company_scope, dict) else None
        if not isinstance(space_id, str) or not space_id:
            raise ManagedError('company_unavailable', 'Join company memory before creating the operator workspace.')
    finally:
        await client.__aexit__()
    current = descriptor_read(descriptor_path)
    if any(current[k] != descriptor[k] for k in ('uid', 'email', 'endpoint')):
        raise ManagedError('binding_changed', 'Desktop profile changed during setup; retry from Desktop.')
    workspace.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with workspace_lock(workspace):
        if workspace.exists():
            binding = load_binding(workspace, active=False)
            if any(binding[k] != descriptor[k] for k in ('uid', 'email', 'endpoint')) or binding['descriptor'] != str(descriptor_path) or binding['company'] != company.strip() or binding['space_id'] != space_id:
                raise ManagedError('binding_mismatch', 'This workspace belongs to a different profile, endpoint, or company.')
            if binding['state'] != 'ready':
                binding.update(state='ready', generation=uuid.uuid4().hex)
                atomic_json(workspace / META, binding)
            return public_status(workspace, binding)
        staging = Path(tempfile.mkdtemp(prefix='.cs-workspace-', dir=workspace.parent))
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                success, checksums = project_init.render_templates(config, Path(project_init.__file__).parent / 'templates' / 'project', staging)
            if not success:
                raise ManagedError('render_failed', 'Could not prepare operator templates; reinstall the operator runtime.')
            binding = {'version': 1, 'uid': descriptor['uid'], 'email': descriptor['email'], 'endpoint': descriptor['endpoint'],
                       'descriptor': str(descriptor_path), 'company': company.strip(), 'kernel_version': kernel_version_bare(),
                       'state': 'ready', 'generation': uuid.uuid4().hex, 'space_id': space_id}
            atomic_json(staging / META, binding)
            atomic_json(staging / 'template-manifest.json', {'file_checksums': checksums, 'init_data': config})
            os.rename(staging, workspace)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return public_status(workspace, binding)


async def status(descriptor_path, workspace):
    workspace = safe_ancestors(workspace)
    binding = load_binding(workspace, active=False)
    if str(safe_ancestors(descriptor_path)) != binding['descriptor']:
        raise ManagedError('binding_mismatch', 'Select the Desktop profile that created this workspace.')
    configuration = configuration_read(workspace)
    ready = False
    publication = []
    if binding['state'] == 'ready':
        descriptor = check_descriptor(workspace, binding)
        client = await authenticated_client(descriptor)
        try:
            await verify_company(client, binding)
            setup = await client.call('setup.state', {}, timeout=20)
            if not isinstance(setup, dict):
                raise ManagedError('readiness_unavailable', 'Engine setup evidence is unavailable; update the engine.')
            from .desktop_mcp import Operator
            from . import instructions
            context = await Operator(workspace).context(client, descriptor)
            publication = [{k: row[k] for k in ('path', 'sha256', 'publication')} for row in context['instructions']]
            required = {'procedures.md', 'phone.md', instructions.mailbox_path(descriptor['email'])}
            ready = required <= {row['path'] for row in publication if row['publication'] == 'current'}
            check_descriptor(workspace, binding)
        finally:
            await client.__aexit__()
    return {**public_status(workspace, binding), 'configuration': configuration, 'instructions_ready': ready, 'instructions': publication}


def revoke(workspace):
    workspace = safe_ancestors(workspace)
    binding = load_binding(workspace, active=False)
    binding.update(state='revoked', generation=uuid.uuid4().hex)
    atomic_json(workspace / META, binding)
    return public_status(workspace, binding)


def atomic_text(path, data):
    safe_ancestors(path)
    fd, temporary = tempfile.mkstemp(prefix='.cs-instructions-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


async def configure(workspace, content):
    import base64
    from . import instructions
    from .desktop_mcp import Operator
    from .project_documents import metadata
    if not isinstance(content, dict) or set(content) != {'procedures', 'mailbox_identity'}:
        raise ManagedError('invalid_instructions', 'Provide company procedures and mailbox identity only.')
    for text in content.values():
        if (not isinstance(text, str) or not text.strip() or len(text.encode('utf-8')) > 32768
                or '\x00' in text or instructions.STAMPED_MARKER in text):
            raise ManagedError('invalid_instructions', 'Provide authored instructions of 1–32768 bytes per field without template headings.')
    operator = Operator(workspace)
    descriptor = check_descriptor(operator.workspace, operator.binding)
    client = await authenticated_client(descriptor)
    try:
        with workspace_lock(operator.workspace):
            await verify_company(client, operator.binding)
            for field, local in (('procedures', instructions.PLAYBOOK_FILE), ('mailbox_identity', instructions.IDENTITY_FILE)):
                check_descriptor(operator.workspace, operator.binding)
                atomic_text(operator.workspace / local, content[field].encode('utf-8'))
            documents = instructions.compile_documents(operator.workspace, settings_for(descriptor))
            expected_paths = {'procedures.md', 'phone.md', instructions.mailbox_path(descriptor['email'])}
            documents = {path: data for path, data in documents.items() if path in expected_paths}
            if set(documents) != expected_paths:
                raise ManagedError('invalid_instructions', 'Company instruction compilation is incomplete.')
            company = await operator.call(client, 'projects.list', {'limit': 1, 'offset': 0})
            space_id = company.get('space_id')
            if not isinstance(space_id, str) or not space_id:
                raise ManagedError('company_unavailable', 'Join company memory before publishing operator instructions.')
            publications = []
            for path, data in documents.items():
                check_descriptor(operator.workspace, operator.binding)
                try:
                    current = await operator.call(client, 'projects.read', {'project': 'operator-instructions', 'path': path})
                except rpc.EngineError as exc:
                    if exc.code != -32044:
                        raise
                    current = None
                revision = 0
                if current is not None:
                    if current.get('space_id') != space_id:
                        raise ManagedError('company_changed', 'Company membership changed; reconnect and retry publication.')
                    revision = metadata(current, 'operator-instructions', path)['revision']
                stored = await operator.call(client, 'instructions.store', {'space_id': space_id, 'path': path,
                    'content_base64': base64.b64encode(data).decode('ascii'), 'expected_revision': revision})
                record = metadata(stored, 'operator-instructions', path)
                if stored.get('space_id') != space_id or record['sha256'] != hashlib.sha256(data).hexdigest() or record['size'] != len(data):
                    raise ManagedError('publication_unverified', 'Instruction publication failed integrity verification; retry Save.')
                readback = await operator.call(client, 'projects.read', {'project': 'operator-instructions', 'path': path, 'revision': record['revision']})
                if readback.get('space_id') != space_id or metadata(readback, 'operator-instructions', path) != record or base64.b64decode(readback['content_base64'], validate=True) != data:
                    raise ManagedError('publication_unverified', 'Instruction read-back failed verification; retry Save.')
                publications.append({'path': path, 'sha256': record['sha256'], 'revision': record['revision'], 'publication': 'current'})
            check_descriptor(operator.workspace, operator.binding)
            return {**public_status(operator.workspace, operator.binding), 'publication': 'current', 'instructions': publications,
                    'configuration': configuration_read(operator.workspace), 'instructions_ready': True}
    except ManagedError:
        raise
    except Exception:
        raise ManagedError('publication_failed', 'Instructions were preserved locally but publication is unverified; check engine access and retry Save.') from None
    finally:
        await client.__aexit__()


def configuration_read(workspace):
    from . import instructions
    result = {}
    for field, local in (('procedures', instructions.PLAYBOOK_FILE), ('mailbox_identity', instructions.IDENTITY_FILE)):
        target = safe_ancestors(Path(workspace) / local)
        if not target.exists():
            result[field] = ''
            continue
        text = _read_bounded(target, 32768, 'Company instruction').decode('utf-8')
        result[field] = '' if instructions.STAMPED_MARKER in text else text
    return result


async def verify_company(client, binding):
    result = await client.call('projects.list', {'limit': 1, 'offset': 0}, timeout=20)
    if not isinstance(result, dict) or result.get('space_id') != binding['space_id']:
        raise ManagedError('company_changed', 'Company membership changed; reconnect the operator workspace for the intended company.')
