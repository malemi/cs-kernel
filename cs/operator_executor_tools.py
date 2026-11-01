"""Finite scheduled tools dispatching the canonical CLI as real subprocesses.

No shell, unrestricted RPC, file mutation or model-selected environment is
exposed. Private artifact retention and paging are infrastructure operations.
"""
from __future__ import annotations

import asyncio
import base64
import os
import posixpath
import re
import signal
import stat
import sys
from pathlib import Path
from uuid import uuid4

from .operator_executor_protocol import (Artifact, ContextPage, Identity, Phase, ToolStart,
    ToolSpawn, ToolEnd, canonical, decode, sha256)

WORKFLOWS = ('cs-operator', 'cs-triage-mail', 'cs-campaign-tick')
DENIED = frozenset(('chat', 'monitor', 'instructions', 'handled', 'escalated', 'draft-delete',
    'draft-retire', 'rm', 'Write', 'Edit', 'Agent', 'Task'))
DENIED_RPC = frozenset(('chat', 'settings.update', 'instructions.store', 'drafts.discard',
    'drafts.discard_exact', 'drafts.reconcile_external', 'operator.rules.decide',
    'operator.rules.import_confirm', 'tasks.assignment.commit', 'update.run',
    'memory.reconsolidate_now', 'memory.join', 'memory.reset', 'memory.restore_version',
    'preparation.resume'))
PREFIXES = (('.venv/bin/python', '-m', 'cs'), ('python', '-m', 'cs'),
            ('.venv/bin/python3', '-m', 'cs'), ('python3', '-m', 'cs'), ('.venv/bin/cs',), ('cs',))
# Exact workflow argument grammar: positionals, boolean switches, value switches.
GRAMMAR = {
    ('--version',): (0, set(), set()),
    ('standing-instructions',): (0, {'--json'}, set()),
    ('whoami',): (0, {'--json'}, set()),
    ('config',): (0, {'--json', '--all', '--strict'}, set()),
    ('memory',): (0, {'--json'}, set()),
    ('review',): (0, {'--json'}, set()),
    ('cron', 'status'): (0, set(), set()),
    ('catchup',): (0, {'--check', '--json'}, {'--timeout'}),
    ('unanswered',): (0, {'--json', '--all-buckets', '--crm'}, {'--days'}),
    ('tasks',): (0, {'--json', '--all'}, {'--limit'}),
    ('tasks', 'create'): (0, {'--json'}, {'--email', '--title', '--event-id', '--event-type',
        '--name', '--phone', '--urgency', '--reason', '--suggested-action', '--thread-id'}),
    ('thread',): (1, {'--json', '--full'}, {'--limit'}),
    ('contacted',): (1, set(), {'--days'}),
    ('history',): (1, {'--json'}, set()),
    ('dossier',): (1, set(), {'--dedup-days'}),
    ('assignment', 'status'): ((0, 1), {'--json'}, set()),
    ('business',): (1, set(), set()),
    ('plan',): (0, {'--verbose', '-v'}, {'--period'}),
    ('ask',): (1, set(), {'--timeout'}),
    ('draft-reply',): (1, set(), {'--thread-id', '--source-id', '--timeout'}),
    ('draft-send',): (1, set(), {'--timeout'}),
    ('campaign', 'list'): (0, set(), set()),
    ('campaign', 'pending'): (0, set(), {'--name'}),
    ('campaign', 'reconcile'): (1, {'--commit'}, set()),
    ('campaign', 'mark'): (1, {'--commit'}, {'--state', '--dossier'}),
    ('campaign', 'queue-draft'): (1, {'--commit'}, set()),
}


class Refusal(ValueError):
    pass


def identity(pid=None):
    pid = os.getpid() if pid is None else pid
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return Identity(pid=pid, started_ticks=int(fields[19]))


def normalize(argv):
    if not isinstance(argv, list) or not argv or any(type(a) is not str or not a or '\x00' in a for a in argv):
        raise Refusal('invalid_argv')
    if any(a in (';', '|', '||', '&&', '&', '>', '>>', '<', '\n') or '`' in a or '$(' in a for a in argv):
        raise Refusal('shell_expression')
    for prefix in PREFIXES:
        if tuple(argv[:len(prefix)]) == prefix:
            argv = argv[len(prefix):]
            break
    return argv


def validate_argv(argv, config):
    argv = normalize(argv)
    if not argv or argv[0] in DENIED:
        raise Refusal('denied_command')
    # Additional legacy script policies are deliberately unsupported. They must
    # be translated by the supervisor, never interpreted as shell prefixes.
    if config.additional_denied:
        raise Refusal('unsupported_launcher_policy')
    if argv[:1] == ['--account']:
        if (not config.founder_enabled or len(argv) < 4 or argv[1] != config.founder_account
                or argv[2:] not in (['tasks', '--json'], ['ask', config.founder_question])):
            raise Refusal('unsupported_secondary_account_command')
        return argv, False
    if argv[0] == 'rpc':
        if len(argv) not in (2, 3) or argv[1] in DENIED_RPC:
            raise Refusal('denied_rpc')
        method = argv[1]
        params = decode(argv[2]) if len(argv) == 3 else {}
        if not isinstance(params, dict):
            raise Refusal('invalid_rpc_arguments')
        if method == 'emails.list_by_thread':
            if set(params) != {'thread_id'} or not isinstance(params['thread_id'], str) or not params['thread_id']:
                raise Refusal('invalid_rpc_arguments')
        elif method == 'tasks.list':
            if set(params) - {'include_completed'} or any(type(v) is not bool for v in params.values()):
                raise Refusal('invalid_rpc_arguments')
        else:
            raise Refusal('unsupported_rpc')
        return ['rpc', method, canonical(params).decode()], False
    key = next((k for k in sorted(GRAMMAR, key=len, reverse=True) if tuple(argv[:len(k)]) == k), None)
    if key is None:
        raise Refusal('unsupported_command')
    positions, switches, values = GRAMMAR[key]
    positional, flags = [], {}
    i = len(key)
    while i < len(argv):
        part = argv[i]
        if part in switches:
            if part in flags:
                raise Refusal('duplicate_flag')
            flags[part] = True
        elif part in values:
            if part in flags or i + 1 == len(argv) or argv[i + 1].startswith('-'):
                raise Refusal('invalid_flag')
            i += 1
            flags[part] = argv[i]
        elif part.startswith('-'):
            raise Refusal('unsupported_flag')
        else:
            positional.append(part)
        i += 1
    if len(positional) not in (positions if isinstance(positions, tuple) else (positions,)):
        raise Refusal('invalid_positionals')
    for flag in ('--timeout', '--days', '--limit', '--dedup-days'):
        if flag in flags and not re.fullmatch(r'[1-9][0-9]{0,4}', flags[flag]):
            raise Refusal('invalid_bound')
    if key == ('catchup',) and '--check' not in flags:
        raise Refusal('catchup_requires_check')
    if key == ('tasks', 'create') and not {'--email', '--title', '--event-id'} <= flags.keys():
        raise Refusal('missing_task_identity')
    if key == ('draft-reply',) and '--thread-id' not in flags:
        raise Refusal('missing_exact_thread')
    if key == ('draft-send',):
        if (config.send_mode != 'send' or os.environ.get('CS_HEADLESS_SEND') != '1'
                or positional[0] not in config.exact_send_ids):
            raise Refusal('send_not_authorized')
    effect = key in (('tasks', 'create'), ('draft-reply',), ('draft-send',),
        ('campaign', 'reconcile'), ('campaign', 'mark'), ('campaign', 'queue-draft'))
    if key==('campaign','mark') and not flags and positional:
        effect=False  # Canonical no-argument mark is a read-only dry-run.
    return argv, effect


def safe_context_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts):
        raise Refusal('context_path_outside_scope')
    allowed = (path in (Path('AGENTS.md'), Path('README.md')) or
        (len(path.parts) >= 2 and path.parts[0] in ('company', 'projects', 'docs', 'campaigns') and path.suffix == '.md') or
        (len(path.parts) == 4 and path.parts[:2] == ('.claude', 'skills')
         and path.parts[2] in WORKFLOWS and path.name == 'SKILL.md'))
    if not allowed or any(re.search(r'(secret|credential|token|password|\.env)', p, re.I) for p in path.parts):
        raise Refusal('context_path_secret_or_unsupported')
    target = root / path
    if target.resolve() != target or not target.is_file():
        raise Refusal('context_path_symlink_or_missing')
    return target


def read_context_bytes(root: Path, relative: str) -> bytes:
    safe_context_path(root, relative)
    # Walk with O_NOFOLLOW for each component, avoiding a checked-path symlink
    # replacement between validation and open.
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = Path(relative).parts
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(parts) - 1:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Refusal('context_not_regular')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read(67108865)
    finally:
        os.close(fd)


class ToolRuntime:
    def __init__(self, config, journal):
        self.config, self.journal = config, journal
        self.root = Path(config.clone_root)
        self.directory = Path(config.journal_path).parent
        self.artifacts = {}
        self.artifact_sources = {}
        self.pages = {}
        self.covered = set()
        self.required = set()
        self.context_hashes = {}
        self.context_artifacts = {}
        self.phases = {}
        self.phase_tools = {}
        self.first_failure = None
        self.discovery_failed = False
        self.inventory_artifacts = []
        self.material_stdout = {}
        self.selected_pending = set()
        self.campaign_pending_items = []
        self.command_results = []
        self.work_outcomes = []
        self.outstanding = set()
        self.parent_request_id = None
        self.poisoned = False
        self.processes = set()
        self.lock = asyncio.Lock()

    def persist(self, raw: bytes, *, required=True):
        aid = str(uuid4())
        path = self.directory / (aid + '.bin')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        artifact = Artifact(artifact_id=aid, path=str(path), bytes=len(raw), sha256=sha256(raw))
        self.artifacts[aid] = artifact
        if required:
            self.required.add(aid)
        return artifact

    def register(self, path: Path):
        from .operator_inventory_view import read_private
        raw = read_private(path)
        artifact = self.persist(raw)
        self.artifact_sources[artifact.artifact_id] = str(path)
        return artifact

    def page(self, aid, offset, length):
        if aid not in self.artifacts or type(offset) is not int or type(length) is not int:
            raise Refusal('foreign_artifact')
        artifact = self.artifacts[aid]
        if not 0 < length <= self.config.page_bytes or not 0 <= offset <= artifact.bytes:
            raise Refusal('invalid_page_interval')
        raw = Path(artifact.path).read_bytes()
        if sha256(raw) != artifact.sha256 or len(raw) != artifact.bytes:
            raise Refusal('artifact_changed')
        if artifact.bytes > self.config.max_artifact_bytes:
            raise Refusal('artifact_capacity')
        end = min(artifact.bytes, offset + length)
        chunk, pid = raw[offset:end], str(uuid4())
        # Base64 is lossless even at UTF-8 code-point boundaries. Model-visible
        # text is supplied as well only when this interval is valid UTF-8.
        try:
            content, encoding = chunk.decode('utf-8'), 'utf-8'
        except UnicodeDecodeError:
            content, encoding = base64.b64encode(chunk).decode('ascii'), 'base64'
        page = ContextPage(page_id=pid, artifact_id=aid, source_path=self.artifact_sources.get(aid, artifact.path),
            source_sha256=artifact.sha256, owner=self.config.owner, start=offset, end=end,
            total_bytes=len(raw), eof=end == len(raw), sha256=sha256(chunk), decoding=encoding)
        self.journal.append(page)
        value = {'executor_page': page.model_dump(mode='json'), 'content': content}
        self.pages[pid] = value
        return value

    def context_closure(self):
        required = ['AGENTS.md'] + [f'.claude/skills/{name}/SKILL.md' for name in WORKFLOWS]
        required += ['company/operator-out-of-scope.md']
        required += self.config.context_paths
        hashes, pending = {}, list(dict.fromkeys(required))
        while pending:
            relative = pending.pop(0)
            if relative in hashes:
                continue
            if len(hashes) >= 64:
                raise Refusal('authoritative_context_reference_capacity')
            raw = read_context_bytes(self.root, relative)
            if len(raw) > self.config.max_artifact_bytes:
                raise Refusal('context_capacity')
            hashes[relative] = sha256(raw)
            text = raw.decode('utf-8')
            # Explicit current clone paths and Markdown links, including
            # references from referenced company notes. Placeholder examples
            # and external URLs confer no filesystem scope.
            refs = re.findall(r'(?<![A-Za-z0-9_/])(?:company|docs|campaigns)/[A-Za-z0-9_./@+-]+\.md', text)
            refs += re.findall(r'\]\(([^)#]+\.md)(?:#[^)]*)?\)', text)
            for ref in refs:
                if '://' in ref or '<' in ref or '>' in ref:
                    continue
                candidate = Path(ref)
                if not candidate.parts or candidate.parts[0] not in ('company', 'docs', 'campaigns', '.claude') and ref not in ('README.md', 'AGENTS.md'):
                    candidate = Path(relative).parent / candidate
                normalized = posixpath.normpath(str(candidate))
                linked = Path(posixpath.normpath(str(self.root / normalized)))
                if not linked.is_relative_to(self.root):
                    continue
                if not (self.root / normalized).exists() and relative != 'company/operator-out-of-scope.md':
                    # Conditional domain/team/architecture context is included
                    # when present; it is not invented as a new mandatory slot.
                    continue
                safe_context_path(self.root, normalized)
                if normalized not in hashes and normalized not in pending:
                    pending.append(normalized)
        if self.config.founder_enabled:
            command = f'--account {self.config.founder_account} ask "{self.config.founder_question}"'
            operator = read_context_bytes(self.root, '.claude/skills/cs-operator/SKILL.md').decode()
            if command not in operator:
                raise Refusal('founder_rendered_binding_differs')
        return hashes

    def bootstrap(self):
        result = []
        hashes = self.context_closure()
        if self.context_hashes and hashes != self.context_hashes:
            raise Refusal('authoritative_context_changed')
        self.context_hashes = hashes
        for relative in hashes:
            raw = read_context_bytes(self.root, relative)
            artifact = self.persist(raw)
            self.artifact_sources[artifact.artifact_id] = str(self.root / relative)
            self.context_artifacts[relative] = artifact.artifact_id
            for offset in range(0, max(1, len(raw)), self.config.page_bytes):
                result.append(self.page(artifact.artifact_id, offset, self.config.page_bytes))
        return result

    def assert_context(self):
        if self.discovery_failed:
            raise Refusal('assignment_read_incomplete')
        from .operator_inventory_view import source_identity
        if source_identity() != self.config.kernel_source_digest:
            raise Refusal('kernel_source_identity_changed')
        for relative, digest in self.context_hashes.items():
            if sha256(read_context_bytes(self.root, relative)) != digest:
                self.covered.clear()
                raise Refusal('authoritative_context_changed')

    def full_coverage(self, aid):
        size, intervals = self.artifacts[aid].bytes, []
        for pid in self.covered:
            page = self.pages[pid]['executor_page']
            if page['artifact_id'] == aid:
                intervals.append((page['start'], page['end']))
        end = 0
        for start, stop in sorted(intervals):
            if start > end:
                return False
            end = max(end, stop)
        return bool(intervals) and end == size

    def pause(self):
        from .config import load
        # Config is clone-owned and already the CLI's authoritative resolver.
        old = Path.cwd()
        try:
            os.chdir(self.root)
            settings = load()
        finally:
            os.chdir(old)
        if (settings.founder_sweep_enabled != self.config.founder_enabled or
                (self.config.founder_enabled and settings.founder_sweep_account != self.config.founder_account)):
            raise Refusal('founder_configuration_binding_differs')
        if settings.engine_owner_uid != self.config.owner:
            raise Refusal('owner_binding_differs')
        return settings.pause_path.exists()

    def required_workflow_context(self, workflow, relative):
        """Hold the relevant operation until its actual required notes arrived.

        Optional links remain optional. These two finite requirements come from
        the rendered workflow hard rules, not from arbitrary Markdown links.
        A newly added/read file supplies no authority until its exact hashed
        pages have entered a successful model request.
        """
        instruction = f'.claude/skills/{workflow}/SKILL.md'
        text = read_context_bytes(self.root, instruction).decode('utf-8')
        if relative not in text:
            return
        if relative not in self.context_hashes or relative not in self.context_artifacts:
            raise Refusal('required_workflow_context_missing:' + relative)
        if not self.full_coverage(self.context_artifacts[relative]):
            raise Refusal('required_workflow_context_undelivered:' + relative)

    def effects_allowed(self, *, final=False):
        if self.poisoned:
            raise Refusal('uncertain_previous_effect')
        self.assert_context()
        if self.pause():
            raise Refusal('paused')
        self.required_workflow_context('cs-triage-mail', 'company/team-conventions.md')
        if self.config.campaign_enabled:
            self.required_workflow_context('cs-campaign-tick', 'company/campaign-product-notes.md')
        if any(not self.full_coverage(aid) for aid in self.required):
            raise Refusal('incomplete_request_coverage')
        needed = {'identity', 'config', 'tasks', 'review', 'discovery', 'authority'}
        if final and self.selected_pending:
            from .operator_executor_work import selected_roots
            try:
                outcomes = selected_roots(self.directory,self.config.owner,self.config.nonce,
                    self.command_results,send_mode=self.config.send_mode)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                raise Refusal(str(exc)) from exc
            self.work_outcomes.extend(outcomes)
            self.selected_pending.clear()
            self.phases['selected_root_work'] = 'completed'
            self.journal.append(Phase(name='selected_root_work',prerequisites=['discovery','authority'],
                tool_ids=list(dict.fromkeys(t for outcome in outcomes for t in outcome['tool_ids'])),
                request_ids=[self.parent_request_id],outcome='completed'))
        if final and self.config.campaign_enabled and self.campaign_pending_items:
            from .operator_executor_work import campaign_work
            try:
                outcomes = campaign_work(self.campaign_pending_items,self.command_results)
            except (ValueError, KeyError, TypeError) as exc:
                raise Refusal(str(exc)) from exc
            self.work_outcomes.extend(outcomes)
            self.phases['campaign_work'] = 'completed'
            ids=list(dict.fromkeys(t for outcome in outcomes for t in outcome['tool_ids']))
            self.journal.append(Phase(name='campaign_work',prerequisites=['campaign_pending'],
                tool_ids=ids or [self.phase_tools['campaign_pending']],request_ids=[self.parent_request_id],outcome='completed'))
        if final and self.config.campaign_enabled:
            needed |= {'campaign_list', 'campaign_pending', 'campaign_work'}
        if final and self.config.founder_enabled:
            needed |= {'founder_tasks', 'founder_mail'}
        if not needed <= self.phases.keys() or any(self.phases[p] != 'completed' for p in needed):
            raise Refusal('incomplete_workflow_phases')

    def complete_phase(self, argv, tool_id, code, raw):
        exact = {('whoami', '--json'): ('identity', []),
            ('config', '--json'): ('config', ['identity']),
            ('tasks', '--json'): ('tasks', ['config']),
            ('review', '--json'): ('review', ['tasks']),
            ('unanswered', '--days', '14', '--json', '--all-buckets'): ('discovery', ['review']),
            ('standing-instructions', '--json'): ('authority', ['config']),
            ('campaign', 'list'): ('campaign_list', ['discovery']),
            ('campaign', 'pending'): ('campaign_pending', ['campaign_list'])}
        if self.config.founder_enabled:
            exact[('--account', self.config.founder_account, 'tasks', '--json')] = ('founder_tasks', ['discovery'])
            exact[('--account', self.config.founder_account, 'ask', self.config.founder_question)] = ('founder_mail', ['founder_tasks'])
        item = exact.get(tuple(argv))
        if item is None:
            return
        name, prerequisites = item
        valid = code == 0 and bool(self.parent_request_id) and all(self.phases.get(p) == 'completed' for p in prerequisites)
        cause = ('phase_exit_nonzero' if code != 0 else 'phase_request_missing' if not self.parent_request_id
            else 'phase_prerequisite_incomplete' if not all(self.phases.get(p) == 'completed' for p in prerequisites)
            else 'phase_validation_failed')
        try:
            value = raw.decode('utf-8').strip() if name == 'founder_mail' else decode(raw)
            if name == 'identity':
                from .config import load
                settings = load()
                valid &= (isinstance(value, dict) and value.get('signed_in') is True
                    and value.get('uid') == self.config.owner and value.get('email') == settings.email_address)
            elif name == 'config':
                fields = {r['name']: r for sec in value['sections'] for r in sec['settings']}
                mode = fields['cs_triage_mode']
                valid &= mode['value'] == self.config.send_mode and bool(mode['origin'])
            elif name in ('tasks', 'founder_tasks'):
                from .operator_workset import _rows
                rows = _rows('tasks', value)
                valid &= len(rows) < 200
            elif name == 'review':
                from .draft_state import inventory_proof
                proof = inventory_proof(value.get('gmail_drafts'), value.get('engine_drafts'),
                    value.get('drafts'), value.get('gmail_drafts_observation'))
                valid &= proof.get('complete') is True and proof == value.get('drafts_inventory')
            elif name == 'authority':
                from .config import load
                mailbox = load().email_address.strip().lower()
                docs = value['documents']
                valid &= (value['authority'] in ('legacy', 'managed') and bool(value['space_id']) and value['mailbox'] == mailbox
                    and {d['path'] for d in docs} == {'procedures.md', f'mail/{mailbox}.md'}
                    and len(docs) == 2 and all(type(d['revision']) is int and d['revision'] > 0
                        and sha256(d['text'].encode()) == d['sha256'] for d in docs))
            elif name == 'discovery':
                # All physical source/projection equivalence is checked before
                # this call by dynamic_inventory; raw stdout need not be paged.
                from .operator_health import assess
                context = decode(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
                if self.parent_request_id and self.inventory_artifacts:
                    health_cause = assess(context, identity().model_dump(), self.config.owner)
                    valid = health_cause == ''
                    if health_cause:
                        cause = health_cause
                else:
                    valid = False
                    cause = 'phase_request_missing' if not self.parent_request_id else 'discovery_inventory_missing'
            elif name == 'campaign_list':
                valid &= isinstance(value, list) and all(isinstance(row, dict) for row in value)
            elif name == 'campaign_pending':
                valid &= isinstance(value, dict) and isinstance(value.get('campaigns'), list)
                if valid:
                    self.campaign_pending_items = [item for row in value['campaigns'] for item in row['items']]
            elif name == 'founder_mail':
                valid &= bool(value)  # authenticated canonical ask JSON result
        except (ValueError, KeyError, TypeError, AttributeError):
            valid = False
            cause = 'phase_response_invalid'
        if not valid and self.first_failure is None:
            self.first_failure = dict(phase=name, cause=cause, tool_id=tool_id, run_id=self.config.run_id)
        self.phases[name] = 'completed' if valid else 'held'
        self.phase_tools[name] = tool_id
        self.journal.append(Phase(name=name, prerequisites=prerequisites, tool_ids=[tool_id],
            request_ids=[self.parent_request_id] if self.parent_request_id else [], outcome=self.phases[name]))
        if (name == 'discovery' and not valid and cause == 'assignment_read_incomplete'
                and code == (3 if value.get('read_incomplete') or value.get('assignment_incomplete') else 0)
                and all(self.phases.get(p) == 'completed' for p in prerequisites)
                and self.command_results and self.command_results[-1]['tool_id'] == tool_id
                and self.command_results[-1]['argv'] == argv
                and self.command_results[-1]['exit_code'] == code
                and self.command_results[-1]['stdout'] == raw):
            self.discovery_failed = True
            raise Refusal('assignment_read_incomplete')
        if name == 'campaign_pending' and valid and not self.campaign_pending_items:
            self.phases['campaign_work'] = 'completed'
            self.journal.append(Phase(name='campaign_work', prerequisites=['campaign_pending'], tool_ids=[tool_id],
                request_ids=[self.parent_request_id], outcome=self.phases['campaign_work']))

    def dynamic_inventory(self, stdout, child):
        if not os.environ.get('CS_OPERATOR_HEALTH_CONTEXT'):
            raise Refusal('discovery_context_missing')
        from .operator_inventory_view import load, read_private
        context = decode(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
        if (context['owner_uid'] != self.config.owner or context['nonce'] != self.config.nonce
                or context['supervisor'] != self.config.supervisor.model_dump()):
            raise Refusal('discovery_context_binding_differs')
        directory, view, envelope = load(context)
        if envelope['native_invocation']['child_identity'] != identity().model_dump():
            raise Refusal('discovery_executor_binding_differs')
        if envelope['schema'] != 'cs.semantic_inventory.envelope.v2' or context.get('workset_enabled') is not True:
            raise Refusal('complete_recurring_material_v2_required')
        from .operator_inventory_material import load_sources
        record = decode(read_private(directory / 'discovery.json'))
        if (record['output_sha256'] != stdout.sha256 or record['exit_code'] not in (0, 3)
                or record['ancestry'][0] != child.model_dump()
                or decode(Path(stdout.path).read_bytes()) != record['discovery']):
            raise Refusal('discovery_cli_result_binding_differs')
        records, sources = load_sources(directory, context, record['discovery'], read_private)
        self.selected_pending = {row['thread_key'] for row in record['discovery']['triage_workset']['selected']}
        for name, source in (('tasks', 'workset-tasks.json'), ('review', 'workset-review.json')):
            aid = self.material_stdout.get(name)
            if aid is None or decode(Path(self.artifacts[aid].path).read_bytes()) != records[source]['payload']:
                raise Refusal('recurring_cli_stdout_binding_differs')
        artifacts = [self.register(directory / name).model_dump() for name in
                     ('inventory-view-envelope.json', 'inventory-view.jsonl')]
        self.inventory_artifacts = [a['artifact_id'] for a in artifacts]
        # The verified semantic view subsumes raw recurring stdout. Originals
        # remain private, byte-for-byte committed by tool_end and envelope.
        self.required.difference_update(self.material_stdout.values())
        return artifacts

    async def _reap(self, proc):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
        # The leader may exit while a descendant remains alive.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()

    async def run_cs(self, argv: list[str]) -> dict:
        """Invoke one permitted canonical CLI command, preserving full private output."""
        async with self.lock:
            return await self._run_cs(argv)

    async def _run_cs(self, argv):
        tid, effect, normalized = str(uuid4()), False, None
        try:
            normalized, effect = validate_argv(argv, self.config)
            self.assert_context()
            if normalized[:1] == ['campaign']:
                self.required_workflow_context('cs-campaign-tick', 'company/campaign-product-notes.md')
            if effect:
                self.effects_allowed()
                if self.selected_pending and normalized[:1] != ['campaign']:
                    from .operator_executor_work import selected_roots
                    target = None
                    if '--thread-id' in normalized:
                        target = normalized[normalized.index('--thread-id')+1]
                    elif normalized[:1] == ['draft-send']:
                        for path in self.directory.glob('workset-draft-*.json'):
                            snapshot=decode(path.read_bytes())
                            if snapshot.get('draft_id') == normalized[1]:
                                target=snapshot['root']
                    if target not in self.selected_pending:
                        raise Refusal('effect_exact_selected_root_missing')
                    outcomes=selected_roots(self.directory,self.config.owner,self.config.nonce,
                        self.command_results,send_mode=self.config.send_mode,final=False,target_root=target)
                    if any(o['outcome']=='held' for o in outcomes):
                        raise Refusal('selected_root_assignment_hold')
            self.assert_context()
        except (ValueError, OSError) as exc:
            cause = str(exc) if isinstance(exc, Refusal) else type(exc).__name__
            self.journal.append(ToolStart(tool_id=tid, parent_request_id=self.parent_request_id,
                name='run_cs', argv=normalized if normalized is not None else argv, path=None,
                offset=None, length=None, decision='deny', cause=cause, producer=identity()))
            self.journal.append(ToolEnd(tool_id=tid, status='denied', exit_code=None, stdout=None,
                stderr=None, effect=effect, unknown_effect=False, business_result='held'))
            return {'status': 'denied', 'cause': cause, 'tool_id': tid}
        self.journal.append(ToolStart(tool_id=tid, parent_request_id=self.parent_request_id,
            name='run_cs', argv=normalized, path=None, offset=None, length=None,
            decision='allow', cause=None, producer=identity()))
        started_sequence=self.journal.sequence-1
        self.outstanding.add(tid)
        out_path, err_path = self.directory / (tid + '.stdout'), self.directory / (tid + '.stderr')
        status, code, proc, spawned = 'error', None, None, None
        interrupted = None
        try:
            with os.fdopen(os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as out, \
                 os.fdopen(os.open(err_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as err:
                executable = self.root / '.venv/bin/python'
                if not executable.is_file():
                    raise Refusal('clone_interpreter_missing')
                child_env = dict(os.environ)
                if os.environ.get('CS_OPERATOR_EXECUTOR_CODEC') == 'pydantic-executor-v1':
                    child_env.update(CS_OPERATOR_EXECUTOR_CODEC='pydantic-executor-v1',
                    CS_OPERATOR_EXECUTOR_TOOL_ID=tid,
                    CS_OPERATOR_EXECUTOR_IDENTITY=canonical(identity().model_dump()).decode())
                proc = await asyncio.create_subprocess_exec(str(executable), '-m', 'cs', *normalized,
                    cwd=self.root, env=child_env, stdin=asyncio.subprocess.DEVNULL,
                    stdout=out, stderr=err, start_new_session=True)
                self.processes.add(proc)
                spawned = identity(proc.pid)
                self.journal.append(ToolSpawn(tool_id=tid, child=spawned, parent=identity()))
                try:
                    code = await asyncio.wait_for(proc.wait(), self.config.tool_timeout_seconds)
                    status = 'ok' if code == 0 or (code == 1 and normalized[0] in ('contacted', 'history')) else 'error'
                except asyncio.TimeoutError:
                    status = 'timeout'
                    await self._reap(proc)
                except asyncio.CancelledError as exc:
                    status, interrupted = 'cancelled', exc
                    await self._reap(proc)
        except asyncio.CancelledError as exc:
            interrupted, status = exc, 'cancelled'
            if proc:
                await self._reap(proc)
        except (ValueError, OSError):
            status = 'error'
            if proc:
                await self._reap(proc)
        finally:
            if proc:
                self.processes.discard(proc)
        def artifact(path):
            raw = path.read_bytes() if path.exists() else b''
            return self.persist(raw, required=bool(raw))
        stdout, stderr = artifact(out_path), artifact(err_path)
        unknown = effect and status != 'ok'
        self.poisoned |= unknown
        if code in (1, 3) and not effect and os.environ.get('CS_OPERATOR_EXECUTOR_CODEC') == 'pydantic-executor-v1':
            from .operator_executor_evidence import known_read
            try:
                if known_read(self.directory, tid, normalized, code, Path(stdout.path).read_bytes(),
                        self.config.owner, self.config.nonce, spawned.model_dump(),stderr=Path(stderr.path).read_bytes()):
                    status = 'ok'
            except (ValueError, KeyError, TypeError, OSError):
                pass
        self.journal.append(ToolEnd(tool_id=tid, status=status, exit_code=code, stdout=stdout,
            stderr=stderr, effect=effect, unknown_effect=unknown,
            business_result='success' if status == 'ok' and code == 0 else 'held' if code in (1, 3) else 'error'))
        self.outstanding.remove(tid)
        result = {'status': status, 'exit_code': code, 'tool_id': tid,
                  'stdout': stdout.model_dump(), 'stderr': stderr.model_dump()}
        if normalized == ['unanswered', '--days', '14', '--json', '--all-buckets'] and code in (0, 3):
            self.required.discard(stdout.artifact_id)
            result['required_inventory_artifacts'] = self.dynamic_inventory(stdout, spawned)
        if normalized in (['tasks', '--json'], ['review', '--json']):
            self.material_stdout[normalized[0]] = stdout.artifact_id
        self.command_results.append(dict(tool_id=tid,argv=normalized,exit_code=code,stdout=Path(stdout.path).read_bytes(),start_sequence=started_sequence,end_sequence=self.journal.sequence-1))
        self.complete_phase(normalized, tid, code, Path(stdout.path).read_bytes())
        recurring = normalized in (['tasks', '--json'], ['review', '--json'], ['unanswered', '--days', '14', '--json', '--all-buckets'])
        if recurring:
            result['semantic_view_delivery_required'] = True
        elif stdout.bytes <= self.config.page_bytes:
            result['page'] = self.page(stdout.artifact_id, 0, self.config.page_bytes)
        else:
            result['paging_required'] = True
        if stderr.bytes and stderr.bytes <= self.config.page_bytes:
            result['stderr_page'] = self.page(stderr.artifact_id,0,self.config.page_bytes)
        if interrupted:
            raise interrupted
        if unknown:
            raise Refusal('uncertain_effect_stops_run')
        return result

    async def read_artifact(self, artifact_id: str, offset: int = 0, length: int = 16384) -> dict:
        """Read an exact bounded byte page of an artifact produced in this run."""
        return await self._read('read_artifact', artifact_id, offset, length)

    async def read_context(self, path: str, offset: int = 0, length: int = 16384) -> dict:
        """Read permitted clone workflow/company/project Markdown context."""
        return await self._read('read_context', path, offset, length)

    async def load_workflow(self, name: str, offset: int = 0, length: int = 16384) -> dict:
        """Load a current rendered workflow through the sole workflow tree."""
        if name not in WORKFLOWS:
            return await self._read('load_workflow', name, offset, length)
        return await self._read('load_workflow', f'.claude/skills/{name}/SKILL.md', offset, length)

    async def _read(self, name, path, offset, length):
        tid = str(uuid4())
        def start(decision, cause=None):
            self.journal.append(ToolStart(tool_id=tid, parent_request_id=self.parent_request_id,
                name=name, argv=None, path=path, offset=max(0, offset), length=max(0, length),
                decision=decision, cause=cause, producer=identity()))
        def finish(status):
            self.journal.append(ToolEnd(tool_id=tid, status=status, exit_code=0 if status == 'ok' else None,
                stdout=None, stderr=None, effect=False, unknown_effect=False,
                business_result='success' if status == 'ok' else 'held'))
        try:
            self.assert_context()
            if not 0 <= offset or not 0 < length <= self.config.page_bytes:
                raise Refusal('invalid_page_interval')
            if name == 'read_artifact':
                if path not in self.artifacts:
                    raise Refusal('foreign_artifact')
            else:
                safe_context_path(self.root, path)
        except (ValueError, OSError) as exc:
            cause = str(exc) if isinstance(exc, Refusal) else type(exc).__name__
            start('deny', cause)
            finish('denied')
            return {'status': 'denied', 'cause': cause}
        start('allow')
        try:
            if name == 'read_artifact':
                aid = path
            elif path in self.context_artifacts:
                aid = self.context_artifacts[path]
            else:
                raw = read_context_bytes(self.root, path)
                self.context_hashes[path] = sha256(raw)
                artifact = self.persist(raw)
                aid = self.context_artifacts[path] = artifact.artifact_id
                self.artifact_sources[aid] = str(self.root / path)
            value = self.page(aid, offset, length)
        except (ValueError, OSError) as exc:
            finish('error')
            return {'status': 'denied', 'cause': str(exc) if isinstance(exc, Refusal) else type(exc).__name__}
        finish('ok')
        return value

    async def pause_status(self) -> dict:
        """Check the authoritative clone pause marker and owner binding."""
        tid = str(uuid4())
        self.journal.append(ToolStart(tool_id=tid, parent_request_id=self.parent_request_id,
            name='pause_status', argv=None, path=None, offset=None, length=None,
            decision='allow', cause=None, producer=identity()))
        try:
            paused = self.pause()
        except Exception:
            self.journal.append(ToolEnd(tool_id=tid, status='error', exit_code=None, stdout=None,
                stderr=None, effect=False, unknown_effect=False, business_result='held'))
            raise
        self.journal.append(ToolEnd(tool_id=tid, status='ok', exit_code=0, stdout=None,
            stderr=None, effect=False, unknown_effect=False, business_result='success'))
        return {'paused': paused}
