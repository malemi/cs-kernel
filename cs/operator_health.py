"""Private ordinary discovery transport and deterministic scheduled health."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import stat
import sys

from .observability_causal import decision

VERSION = 1

LIMIT = 2 * 1024 * 1024
ARGV = ['unanswered', '--days', '14', '--json', '--all-buckets']


def _ancestry_conflict(result, thread_key):
    return (isinstance(result, dict) and type(result.get("version")) is int and result["version"] == VERSION
            and all(isinstance(result.get(key), str) and result[key].strip() for key in ("actor_uid", "space_id"))
            and isinstance(thread_key, str) and re.fullmatch(r"<[^<>\s@]+@[^<>\s@]+>", thread_key) is not None
            and result.get("thread_key") == thread_key
            and result.get("reason") == "RFC_ANCESTRY_CONFLICT"
            and result.get("complete") is False and result.get("state") == "conflict"
            and result.get("hold_auto_reply") is True and "task" in result and result["task"] is None
            and result.get("component_scope_present") is False
            and result.get("authoritative_thread_key") == thread_key
            and result.get("component_thread_keys") == [thread_key]
            and result.get("source_owner_uid") == result.get("actor_uid")
            and not {"authority_complete", "hold_scope"}.intersection(result)
            and all(result.get(key) == [] for key in ("events", "covered_inbound", "current_inbound",
                "covered_message_ids", "current_message_ids", "reply_evidence")))



def identity(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'started_ticks': int(fields[19])}, int(fields[1])


def private(path, directory=False):
    meta = path.lstat()
    if (meta.st_uid != os.getuid() or stat.S_IMODE(meta.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode))
            or (not directory and (meta.st_nlink != 1 or meta.st_size > LIMIT * 2))):
        raise ValueError('ordinary discovery artifact is not private')


def capture(output, value, code, owner):
    context = json.loads(os.environ['CS_OPERATOR_HEALTH_CONTEXT'])
    directory = Path(context['directory'])
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ValueError('ordinary discovery path differs')
    private(directory, True)
    if sys.argv[1:] != ARGV or len(output) > LIMIT:
        raise ValueError('ordinary discovery command or size differs')
    chain = []
    pid = os.getpid()
    for _ in range(32):
        row, pid = identity(pid)
        chain.append(row)
        if row == context['supervisor']:
            break
    else:
        raise ValueError('ordinary discovery supervisor differs')
    if len(chain) < 3:
        raise ValueError('ordinary discovery child missing')
    payload = {'nonce': context['nonce'], 'owner_uid': owner, 'ancestry': chain,
               'exit_code': code, 'output_sha256': hashlib.sha256(output).hexdigest(),
               'discovery': value}
    encoded = json.dumps(payload, ensure_ascii=False, default=str).encode()
    if len(encoded) > LIMIT * 2:
        raise ValueError('ordinary discovery record too large')
    target = directory / 'discovery.json'
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    if context.get("workset_enabled") is True:
        from .operator_inventory_view import capture as capture_view
        try:
            capture_view(context)
        except (ValueError, KeyError, TypeError, OSError, RecursionError):
            pass
    return target


def assess(context, child, owner):
    check, cause = 'discovery_artifact_access', 'artifact_unreadable'
    try:
        directory = Path(context['directory'])
        if directory.resolve() != directory:
            raise ValueError('foreign directory')
        private(directory, True)
        path = directory / 'discovery.json'
        check, cause = ('discovery_artifact_access', 'artifact_unreadable') if path.exists() else ('discovery_artifact_presence', 'artifact_missing')
        private(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            raw = stream.read(LIMIT * 2 + 1)
        check, cause = 'discovery_artifact_encoding', 'artifact_invalid'
        if len(raw) > LIMIT * 2:
            raise ValueError('oversized record')
        record = json.loads(raw)
        check, cause = 'discovery_identity', 'identity_mismatch'
        chain = record['ancestry']
        if (record['nonce'] != context['nonce'] or record['owner_uid'] != owner
                or not isinstance(chain, list) or len(chain) < 3 or len(chain) > 32
                or chain[-1] != context['supervisor'] or child not in chain[:-1]):
            raise ValueError('foreign run identity')
        check, cause = 'discovery_payload_digest', 'digest_mismatch'
        value = record['discovery']
        payload = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n').encode()
        if len(payload) > LIMIT or hashlib.sha256(payload).hexdigest() != record['output_sha256']:
            raise ValueError('discovery payload differs')
        check, cause = 'discovery_payload_shape', 'shape_invalid'
        if (not isinstance(value, dict) or 'read_incomplete' not in value
                or type(value.get('assignment_incomplete')) is not bool
                or any(not isinstance(value.get(key), list) for key in
                       ('open', 'human_work', 'assignment_audit', 'operational_fixture_discovery'))):
            raise ValueError('discovery shape differs')
        check, cause = 'discovery_exit', 'exit_mismatch'
        expected = 3 if value['read_incomplete'] or value['assignment_incomplete'] else 0
        if type(record['exit_code']) is not int or record['exit_code'] != expected:
            raise ValueError('discovery exit differs')
        if value['read_incomplete'] is not None:
            decision('ordinary_health_result', 'mailbox_read_incomplete', phase='discovery', command='unanswered', method='operator.health.assess')
            return 'mailbox_read_incomplete'
        incomplete_rows = 0
        for row in value['human_work']:
            assignment = row.get('assignment') if isinstance(row, dict) else None
            if (not isinstance(assignment, dict) or type(assignment.get('complete')) is not bool
                    or assignment.get('hold_auto_reply') is not True
                    or assignment.get('state') not in ('needs-assignment', 'assigned', 'conflict')
                    or (assignment.get('reason') == 'RFC_ANCESTRY_CONFLICT'
                        and not _ancestry_conflict(assignment, row.get('thread_key')))):
                decision('ordinary_health_result', 'assignment_read_incomplete', phase='discovery', command='unanswered', method='operator.health.assess')
                return 'assignment_read_incomplete'
            if assignment['complete'] is False:
                incomplete_rows += 1
                if assignment['state'] != 'needs-assignment' and not _ancestry_conflict(assignment, row.get('thread_key')):
                    decision('ordinary_health_result', 'assignment_read_incomplete', phase='discovery', command='unanswered', method='operator.health.assess')
                    return 'assignment_read_incomplete'
        if value['assignment_incomplete'] != bool(incomplete_rows):
            decision('ordinary_health_result', 'assignment_read_incomplete', phase='discovery', command='unanswered', method='operator.health.assess')
            return 'assignment_read_incomplete'
        if context.get('workset_enabled') is True:
            check, cause = 'workset_identity', 'workset_invalid'
            from .operator_workset import _read, _hash
            workset = value.get('triage_workset')
            if (context.get('owner_uid') != owner or not isinstance(workset, dict)
                    or workset.get('complete') is not True
                    or type(workset.get('limit')) is not int or workset['limit'] != 2
                    or not isinstance(workset.get('selected'), list) or len(workset['selected']) > 2):
                raise ValueError('workset incomplete')
            roots = [row['thread_key'] for row in workset['selected']]
            if any(not isinstance(root, str) for root in roots) or len(set(roots)) != len(roots):
                raise ValueError('workset roots differ')
            check, cause = 'workset_reservation', 'reservation_mismatch'
            reserved = _read(directory / 'workset-reserved.json')
            if (reserved['owner_uid'] != owner or reserved['nonce'] != context['nonce']
                    or reserved['selected'] != [_hash(root) for root in roots]):
                raise ValueError('workset reservation differs')
        if not value['open'] and not value['human_work']:
            decision('ordinary_health_result', 'complete_empty', outcome='accepted', phase='discovery', command='unanswered', method='operator.health.assess')
        elif not value['open'] and value['human_work'] and all(row['assignment']['hold_auto_reply'] is True for row in value['human_work']):
            decision('ordinary_health_result', 'legitimate_hold', outcome='accepted', phase='discovery', command='unanswered', method='operator.health.assess')
        return ''
    except Exception:
        decision(check, cause, phase='discovery', command='unanswered', method='operator.health.assess')
        return 'discovery_evidence_invalid'


def _read_decision(check, cause, command, tool=None, session=None, **facts):
    import shlex
    from .observability_causal import COMMANDS
    words = shlex.split(command)
    words = words[3:] if words[:3] in (['.venv/bin/python', '-m', 'cs'], ['.venv/bin/python3', '-m', 'cs']) else words[1:]
    if words[:1] == ['--account']:
        words = words[2:]
    known = words[0] if words and words[0] in COMMANDS else None
    phase = {'whoami':'identity', 'config':'configuration', 'tasks':'tasks', 'unanswered':'discovery', 'review':'review', 'campaign':'campaigns'}.get(known)
    return decision(check, cause, phase=phase, command=known, method='operator.health.native_read', tool=tool, session=session, **facts)


def native_read_failed(events, business_proofs=(), discovery_proven=False):
    import shlex
    from .operator_discovery_receipt import COMMAND
    reads = {}
    completed = set()
    for event in events:
        message = event.get('message')
        blocks = message.get('content', []) if isinstance(message, dict) else []
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                arguments = block.get('input')
                command = arguments.get('command') if isinstance(arguments, dict) else None
                if not isinstance(command, str):
                    continue
                try:
                    words = shlex.split(command)
                except ValueError:
                    continue
                canonical = (words[:3] in (['.venv/bin/python', '-m', 'cs'],
                    ['.venv/bin/python3', '-m', 'cs']) or words[:1] in (['.venv/bin/cs'], ['cs']))
                if canonical:
                    tool = block.get('id')
                    if not isinstance(tool, str) or not tool or tool in reads:
                        _read_decision('read_tool_identity', 'read_tool_id_duplicate' if isinstance(tool, str) and tool in reads else 'read_tool_id_invalid', command, tool=tool if isinstance(tool, str) and tool else None, session=event.get('session_id'))
                        return True
                    reads[tool] = (command, event.get('session_id'))
            elif block.get('type') == 'tool_result' and block.get('tool_use_id') in reads:
                tool = block['tool_use_id']
                if tool in completed:
                    _read_decision('read_result_uniqueness', 'read_result_duplicate', reads[tool][0], tool=tool, session=reads[tool][1])
                    return True
                completed.add(tool)
                if block.get('is_error', False) is False:
                    continue
                command, session = reads[tool]
                if command == COMMAND and discovery_proven:
                    continue
                matching = [proof for proof in business_proofs if proof.get('tool_use_id') == tool
                    and proof.get('session_id') == session
                    and proof.get('command_digest') == hashlib.sha256(command.encode()).hexdigest()]
                if len(matching) != 1:
                    _read_decision('read_error_proof_cardinality', 'read_error_unproved', command, tool=tool, session=session, expected=1, matching_proofs=len(matching))
                    return True
    if set(reads) != completed:
        tool = next(tool for tool in reads if tool not in completed)
        _read_decision('read_result_completeness', 'read_result_missing', reads[tool][0], tool=tool, session=reads[tool][1], reads=len(reads), completed=len(completed))
    return set(reads) != completed


def inspection_failure(events, context, phases, founder=False):
    import shlex
    from .operator_inventory_view import effect_words
    required = ['identity', 'configuration', 'tasks', 'discovery', 'review', 'campaigns']
    if founder:
        required.extend(('founder_tasks', 'founder_ask'))
    missing = [phase for phase in required if not any(row.get('phase') == phase for row in phases)]
    if missing:
        commands = dict(identity='whoami', configuration='config', tasks='tasks', discovery='unanswered', review='review', campaigns='campaign', founder_tasks='tasks', founder_ask='ask')
        decision('required_phase_presence', 'required_phase_absent', phase=missing[0], command=commands[missing[0]], method='operator.health.inspection', required=True, present=False, observed=len(missing))
        return 'execution_phase_incomplete'
    path = Path(context['directory']) / 'discovery.json'
    try:
        private(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            raw = stream.read(LIMIT * 2 + 1)
        if len(raw) > LIMIT * 2:
            return 'discovery_evidence_invalid'
        record = json.loads(raw)
        payload = json.dumps(record['discovery'], ensure_ascii=False, indent=2, default=str) + '\n'
        uses = {}
        discovery_uses = []
        discovery_results = 0
        covered = 0
        inspected = False
        early_draft = False
        for event in events:
            message = event.get('message')
            blocks = message.get('content', []) if isinstance(message, dict) else []
            for block in blocks if isinstance(blocks, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                    arguments = block.get('input')
                    command = arguments.get('command') if isinstance(arguments, dict) else None
                    if not isinstance(command, str):
                        continue
                    try:
                        words = shlex.split(command)
                    except ValueError:
                        continue
                    if effect_words(words):
                        early_draft = early_draft or not inspected
                    if arguments.get('run_in_background', False) is not False:
                        continue
                    if words == ['.venv/bin/python', '-m', 'cs', *ARGV]:
                        discovery_uses.append(block.get('id'))
                        uses[block.get('id')] = ('discovery', None)
                    elif effect_words(words):
                        early_draft = early_draft or not inspected
                        uses[block.get('id')] = ('operation', None)
                    elif (len(words) == 6 and words[0] == 'dd' and words[1] == 'if=' + str(path)
                          and words[2] == 'bs=1' and words[3].startswith('skip=')
                          and words[4].startswith('count=') and words[5] == 'status=none'):
                        try:
                            start, count = int(words[3][5:]), int(words[4][6:])
                        except ValueError:
                            continue
                        if start >= 0 and 0 < count <= 8192:
                            uses[block.get('id')] = ('part', (start, count))
                elif block.get('type') == 'tool_result' and block.get('tool_use_id') in uses:
                    kind, bounds = uses.pop(block['tool_use_id'])
                    if kind == 'operation':
                        if block.get('is_error', False) is not False:
                            decision('ordinary_health_result', 'execution_operation_failed', method='operator.health.inspection')
                            return 'execution_operation_failed'
                        continue
                    output = block.get('content', '')
                    if isinstance(output, list):
                        output = '\n'.join(row.get('text', '') for row in output
                                           if isinstance(row, dict) and row.get('type') == 'text')
                    if not isinstance(output, str):
                        continue
                    if kind == 'discovery':
                        discovery_results += 1
                        if record['exit_code'] == 3:
                            for prefix in ('Error: Exit code 3\n', 'Exit code 3\n'):
                                if output.startswith(prefix):
                                    output = output[len(prefix):]
                                    break
                        suffix = 'Ordinary discovery artifact: ' + str(path)
                        if output.strip() in (payload.strip(), (payload + suffix).strip()):
                            inspected = True
                    elif block.get('is_error', False) is False and bounds:
                        start, count = bounds
                        expected = raw[start:start + count].decode('utf-8', 'replace')
                        if start <= covered and expected and output.strip() == expected.strip():
                            covered = max(covered, min(len(raw), start + count))
                            if covered == len(raw):
                                inspected = True
        if any(kind == 'operation' for kind, _ in uses.values()):
            decision('ordinary_health_result', 'execution_operation_failed', method='operator.health.inspection')
            return 'execution_operation_failed'
        if len(discovery_uses) != 1 or discovery_results != 1:
            decision('discovery_tool_cardinality', 'discovery_cardinality_invalid', phase='discovery', command='unanswered', method='operator.health.inspection', expected=1, uses=len(discovery_uses), results=discovery_results)
            return 'execution_phase_incomplete'
        if not inspected or early_draft:
            from .operator_inventory_view import audit
            try:
                if audit(events, context):
                    return ''
            except (ValueError, KeyError, TypeError, OSError, RecursionError):
                pass
            decision('ordinary_health_result', 'discovery_inspection_incomplete', phase='discovery', command='unanswered', method='operator.health.inspection')
            return 'discovery_inspection_incomplete'
        return ''
    except Exception:
        decision('discovery_artifact_access', 'artifact_unreadable', phase='discovery', command='unanswered', method='operator.health.inspection')
        return 'discovery_evidence_invalid'
