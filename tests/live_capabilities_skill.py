from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from capabilities_events import (audit_tools, events, final_text, loaded, output_text, read_coverage,
    require_debug_file, require_host_success, require_no_mcp, require_safe_requests, require_scheduled,
    require_unchanged, require_private_channels, shell_parts, source_snapshot, tool_events, validate_cli_args)
from capabilities_fixture import BASE, Fixture, IDENTITY, LOCAL, PLAYBOOK, PROMPTS, ROOT, native_command
from capabilities_engine import Engine, serve, validate_catalog_journey, verify_engine_manifest
from capabilities_claude_settings import verify_profile, traced_command, require_hook_execution
from capabilities_codex_session import capture_command_context
from capabilities_codex_config import capture_user_config, compare_config


def launch(argv, fixture, timeout, prefix='native'):
    stdout, stderr = fixture.root / f'{prefix}.jsonl', fixture.root / f'{prefix}.stderr'
    if hasattr(fixture, 'claude_profile'):
        verify_profile(fixture.claude_profile)
        trace = fixture.root / 'hook-process.trace'
        trace.touch(mode=0o600, exist_ok=False)
        argv = traced_command(argv, fixture.claude_profile, trace)
        (fixture.root / 'process-launch.json').write_text(json.dumps({'argv': argv}, indent=2))
    with stdout.open('w') as out, stderr.open('w') as err:
        process = subprocess.Popen(argv, cwd=fixture.clone, env=fixture.env, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise AssertionError(f'Native host timed out; partial evidence retained at {stdout}')
    return process.returncode, stdout.read_text(), stderr.read_text()



def bind_profile(args, config):
    raw = args.claude_profile_binding.read_bytes()
    if not hasattr(args, 'claude_profile_snapshot'):
        args.claude_profile_snapshot = raw
    require_unchanged(args.claude_profile_snapshot, raw, 'Frozen Claude profile binding file')
    binding = json.loads(raw)
    require_unchanged(binding, config['runtime_profile']['hashes'], 'Frozen Claude runtime configuration')
    return verify_profile(config['runtime_profile'])


def hook_evidence(fixture, transcript, debug):
    bash = any(call['name'] == 'bash' for call in tool_events(transcript))
    return require_hook_execution(fixture.claude_profile, debug, (fixture.root / 'hook-process.trace').read_text(), bash)


def preflight(args, output):
    fixture = Fixture(output / 'claude-preflight', args.kernel_python, 'procedures')
    marker = fixture.root / 'probe-executed'
    probe = fixture.bin / 'cs-fixture-unlisted-probe'
    probe.write_text('#!/bin/sh\nprintf executed > ' + str(marker) + '\n')
    probe.chmod(0o755)
    debug = fixture.root / 'native.debug'
    argv, config = native_command('claude', fixture, 'Run the harmless command cs-fixture-unlisted-probe once. If permission is denied, report that and stop.', debug)
    record = {'argv': argv, 'config': config}
    try:
        record['runtime_before'] = bind_profile(args, config)
        code, transcript, errors = launch(argv, fixture, args.timeout)
        require_host_success(transcript, code, errors, require_debug_file('claude', debug))
        require_no_mcp('claude', transcript, config)
        record['hooks'] = hook_evidence(fixture, transcript, debug.read_text())
        calls = [call for call in tool_events(transcript) if call['name'] == 'bash' and 'cs-fixture-unlisted-probe' in call['input'].get('command', '')]
        assert calls and all(not call['success'] for call in calls), 'Unlisted harmless command was not actually refused'
        assert any(any(word in output_text(call['output']).lower() for word in ('permission', 'denied', 'not allowed')) for call in calls), 'No permission refusal evidence'
        assert not marker.exists(), 'Unlisted command executed'
        record['passed'] = True
    except Exception as exc:
        record.update(passed=False, error=str(exc))
    try:
        record['runtime_after'] = bind_profile(args, config)
    except Exception as exc:
        record.update(passed=False, cleanup_error=str(exc))
    (fixture.root / 'result.json').write_text(json.dumps(record, indent=2))
    return record


def check_case(case, host, fixture, transcript, frames, providers, config, responses=()):
    evidence = audit_tools(transcript, fixture.clone)
    answer = final_text(transcript)
    startup = require_no_mcp(host, transcript, config)
    require_safe_requests(frames, providers, transcript, fixture.server.get('secrets', ()))
    cli_log = fixture.logs / 'cli.jsonl'
    cli = list(events(cli_log.read_text())) if cli_log.exists() else []
    for row in cli:
        validate_cli_args(row.get('argv'), local=case in LOCAL, scheduled=case == 'scheduled')
    if case == 'scheduled':
        assert all(row['argv'] in (['whoami'], ['config']) for row in cli), 'Scheduled case attempted catalog, publication or refused bootstrap CLI'
        require_scheduled(evidence, frames, answer, fixture.clone)
    elif case != 'workflow':
        assert loaded(evidence, fixture.clone, 'cs-capabilities'), 'Bootstrap body loading not evidenced'
    if case == 'workflow':
        for call in evidence:
            inputs = json.dumps(call['input'])
            assert 'docs/sessions' not in inputs and '.doc-profile' not in inputs, 'Workflow explanation attempted session or harness bookkeeping'
            if call['name'] in ('bash', 'exec_command', 'shell'):
                command = call['input'].get('command', call['input'].get('cmd', ''))
                assert all(Path(words[0]).name != 'git' for _, words in shell_parts(command)), 'Workflow explanation inspected Git state'
    coverage = {}
    if case in LOCAL:
        assert not frames, 'Local case contacted engine'
        assert all(row['argv'] == ['whoami'] for row in cli), 'Local case explored CLI or attempted publication'
        wanted = ['company/README.md', PLAYBOOK, IDENTITY] if case == 'procedures' else ['company/README.md', IDENTITY] if case == 'procedure-gaps' else ['.claude/skills/cs-instructions/SKILL.md']
        for rel in wanted:
            coverage[rel] = read_coverage(evidence, fixture.clone / rel)
            assert coverage[rel]['complete'], f'Incomplete successful read: {rel}: {coverage[rel]}'
        if case == 'procedures':
            assert 'fattur' in answer.lower() or 'invoice' in answer.lower()
            assert 'venti' in answer.lower() or 'twenty' in answer.lower() or '20' in answer
            assert 'Fixture Support Desk' in answer
            assert all(Path(rel).name in answer for rel in wanted), 'Loaded source names missing'
        elif case == 'procedure-gaps':
            def missing_from_complete_parent(call, path):
                if path.exists() or path.is_symlink() or not call['success'] or call['name'] != 'bash':
                    return False
                groups = shell_parts(call['input'].get('command', ''))
                if len(groups) != 1:
                    return False
                words = groups[0][1]
                if len(words) < 3 or Path(words[0]).name != 'ls' or words[1] not in ('-la', '-al'):
                    return False
                if any('..' in Path(value).parts or any(char in value for char in '*?[]{}~') for value in words[2:]):
                    return False
                operands = [fixture.clone / value for value in words[2:]]
                if any(not operand.is_relative_to(fixture.clone) for operand in operands):
                    return False
                if any(component.is_symlink() for operand in operands
                       for component in (operand, *operand.parents)
                       if component.is_relative_to(fixture.clone)):
                    return False
                directories = [operand.resolve() for operand in operands]
                if path.parent not in directories or not path.parent.is_dir():
                    return False
                absent = {value: directory for value, directory in zip(words[2:], directories)
                          if not directory.exists() and not directory.is_symlink()}
                if any(not directory.is_dir() and directory not in absent.values() for directory in directories):
                    return False
                errors = set()
                sections, current = {}, directories[0] if len(directories) == 1 else None
                for line in output_text(call['output']).splitlines():
                    if not line.strip():
                        continue
                    diagnostic = next((value for value in absent
                                       if line == f"ls: cannot access '{value}': No such file or directory"), None)
                    if diagnostic is not None:
                        if diagnostic in errors:
                            return False
                        errors.add(diagnostic)
                        continue
                    if line.endswith(':'):
                        current = (fixture.clone / line[:-1]).resolve()
                        if current not in directories or current in sections:
                            return False
                        sections[current] = {}
                        continue
                    if current is None:
                        return False
                    entries = sections.setdefault(current, {})
                    if line.startswith('total '):
                        if not line[6:].isdigit():
                            return False
                        continue
                    fields = line.split(None, 8)
                    if len(fields) != 9:
                        return False
                    mode, name = fields[0], fields[8]
                    if len(mode) not in (10, 11) or mode[0] not in '-d' or any(char not in 'rwxstST-' for char in mode[1:10]) or mode[10:] not in ('', '+', '.'):
                        return False
                    if name in entries or not fields[1].isdigit() or not fields[4].isdigit():
                        return False
                    entries[name] = mode[0]
                entries = sections.get(path.parent, {})
                expected = {child.name: 'd' if child.is_dir() else '-' for child in path.parent.iterdir()}
                expected.update({'.': 'd', '..': 'd'})
                if errors != set(absent) or entries != expected or path.name in entries:
                    return False
                regular = [child for child in (fixture.clone / 'company').rglob('*') if child.is_file()]
                if not all(read_coverage(evidence, child)['complete'] for child in regular):
                    return False
                call.setdefault('gap_metadata', {})[str(path)] = {'parent': str(path.parent), 'inventory': sorted(entries), 'state': 'missing'}
                return True

            for rel in (PLAYBOOK, 'company/companion.md'):
                target = str((fixture.clone / rel).resolve())
                direct = any(target in call['paths'] and (not call['success'] or (call['name'] == 'bash' and any(Path(words[0]).name == 'ls' for _, words in shell_parts(call['input'].get('command', ''))) and (fixture.clone / rel).is_dir())) for call in evidence)
                assert direct or any(missing_from_complete_parent(call, Path(target)) for call in evidence), f'Failed read or complete metadata not evidenced: {rel}'
            assert all(word in answer for word in ('customer-service-playbook.md', 'mailbox-identity.md', 'companion.md')), 'Distinct gaps not named'
    catalog = validate_catalog_journey(case, frames, responses, fixture.server.get('bank_system'), answer) if case in ('reachable', 'named', 'older-engine') else None
    return {'catalog': catalog, 'tool_evidence': evidence, 'coverage': coverage, 'startup': startup, 'cli': cli, 'answer': answer,
            'semantic_review_required': True}


def run_case(args, output, host, case, candidate):
    engine, fixture = None, None
    record = {'host': host, 'case': case, 'candidate': candidate}
    root = output / host / case
    root.parent.mkdir(exist_ok=True)
    try:
        if case not in LOCAL and case != 'scheduled' and not args.build_only:
            record['engine_snapshot_before'] = verify_engine_manifest(args)
            require_unchanged(args.engine_snapshot, record['engine_snapshot_before'], 'Frozen engine source/dependencies')
            engine = Engine(output / f'engine-{host}-{case}', args, case)
        fixture = Fixture(root, args.kernel_python, case, engine.info if engine else None)
        record['clone'] = str(fixture.clone.resolve())
        if args.build_only:
            record['before'] = fixture.state()
            record.update(passed=True, native_acceptance=False)
        else:
            bank = fixture.server.get('bank_system')
            assert case != 'named' or bank, 'Engine fixture did not hand off bank system identifier'
            prompt = PROMPTS[case].format(bank=bank)
            debug = root / 'native.debug'
            if host == 'codex':
                record['config_before'] = capture_user_config(root / 'private' / 'config-before.toml')
            argv, config = native_command(host, fixture, prompt, debug)
            before = fixture.state()
            record.update(before=before, argv=argv, host_config=config, prompt=prompt)
            if host == 'claude':
                record['runtime_before'] = bind_profile(args, config)
            (root / 'launch.json').write_text(json.dumps(record, indent=2))
            launched_at = datetime.now(timezone.utc)
            code, transcript, stderr = launch(argv, fixture, args.timeout)
            record['exit'] = code
            if host == 'codex':
                record['command_context'] = capture_command_context(transcript, fixture.clone, root / 'command-context.json', launched_at)
            debug_text = require_debug_file(host, debug)
            require_host_success(transcript, code, stderr, debug_text)
            if host == 'claude':
                record['hooks'] = hook_evidence(fixture, transcript, debug_text)
            require_private_channels(host, transcript, stderr, (debug_text,), fixture.server.get('secrets', ()))
            after = fixture.state()
            record['after'] = after
            require_unchanged(before, after)
            require_unchanged(candidate, source_snapshot(ROOT), 'Candidate source snapshot')
            if engine:
                engine.close()
                engine_data = engine.evidence()
                record['engine_snapshot_after'] = verify_engine_manifest(args)
                require_unchanged(record['engine_snapshot_before'], record['engine_snapshot_after'], 'Engine source/dependency snapshot')
            else:
                engine_data = {'requests': [], 'responses': [], 'provider_requests': [], 'forbidden_attempts': []}
            record['engine_evidence'] = engine_data
            frames, providers = engine_data['requests'], engine_data['provider_requests']
            response_path = fixture.logs / 'responses.jsonl'
            cli_responses = response_path.read_text() if response_path.exists() else ''
            network_path = fixture.logs / 'cli-network.jsonl'
            assert not network_path.exists() or not network_path.read_text().strip(), 'CLI attempted nonloopback network access'
            require_safe_requests(frames, providers, '')
            require_private_channels(host, transcript, stderr,
                (debug_text, cli_responses, json.dumps(engine_data['responses'])),
                fixture.server.get('secrets', ()), fixture.server.get('prohibited_values', ()))
            record.update(rpc=frames, provider_requests=providers, cli_responses=list(events(cli_responses)))
            assert all(Path(row['candidate']).resolve() == (ROOT / 'cs/__init__.py').resolve() for row in record['cli_responses']), 'CLI imported a different kernel candidate'
            record.update(check_case(case, host, fixture, transcript, frames, providers, config, engine_data['responses']))
            record.update(passed=True, native_acceptance=True)
    except Exception as exc:
        record.update(passed=False, error=str(exc))
    finally:
        try:
            if engine:
                engine.close()
                record['engine_evidence'] = engine.evidence()
                record['engine_snapshot_after'] = verify_engine_manifest(args)
                require_unchanged(record['engine_snapshot_before'], record['engine_snapshot_after'], 'Engine source/dependency snapshot')
            if fixture:
                if host == 'codex' and 'config_before' in record:
                    record['config_after'] = capture_user_config(root / 'private' / 'config-after.toml')
                    record['config_receipt'] = compare_config(record['config_before'], record['config_after'], [fixture.clone.resolve()])
                if host == 'codex' and (root / 'native.jsonl').is_file() and not (root / 'command-context.json').exists():
                    try:
                        record['command_context'] = capture_command_context((root / 'native.jsonl').read_text(), fixture.clone,
                            root / 'command-context.json', launched_at)
                    except Exception as exc:
                        record.update(passed=False, command_context_error=str(exc))
                if hasattr(fixture, 'claude_profile'):
                    record['runtime_after'] = bind_profile(args, {'runtime_profile': fixture.claude_profile})
                record['after'] = fixture.state()
                if 'before' in record:
                    require_unchanged(record['before'], record['after'])
                native_path = root / 'native.jsonl'
                stderr_path = root / 'native.stderr'
                require_private_channels(host, native_path.read_text() if native_path.is_file() else '',
                    stderr_path.read_text() if stderr_path.is_file() else '',
                    tuple(path.read_text() for path in (root / 'native.debug', fixture.logs / 'responses.jsonl') if path.is_file())
                    + (json.dumps(record.get('engine_evidence', {}).get('responses', [])),),
                    fixture.server.get('secrets', ()), fixture.server.get('prohibited_values', ()))
            require_unchanged(candidate, source_snapshot(ROOT), 'Candidate source snapshot')
        except Exception as exc:
            record.update(passed=False, cleanup_error=str(exc))
    root.mkdir(parents=True, exist_ok=True)
    (root / 'result.json').write_text(json.dumps(record, indent=2))
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', choices=('all', 'claude', 'codex', 'opencode'), default='all')
    parser.add_argument('--cases', nargs='+', choices=tuple(PROMPTS))
    parser.add_argument('--local-only', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--kernel-python', default='/home/mal/hb/cs-kernel/.venv/bin/python')
    parser.add_argument('--engine-python')
    parser.add_argument('--claude-profile-binding', type=Path)
    parser.add_argument('--engine-source', type=Path)
    parser.add_argument('--engine-reviewed-manifest', type=Path)
    parser.add_argument('--output-dir', type=Path, required=False)
    parser.add_argument('--timeout', type=int, default=420)
    parser.add_argument('--serve', type=Path)
    parser.add_argument('--bank-state', default='connected')
    args = parser.parse_args()
    if args.serve:
        serve(args)
        return 0
    if not args.output_dir:
        parser.error('--output-dir is required; each attempt uses a new directory')
    selected = args.cases or (list(LOCAL) if args.local_only else list(PROMPTS))
    if args.local_only and any(case not in LOCAL for case in selected):
        parser.error('--local-only cannot select remote or scheduled cases')
    if not args.build_only and any(case not in (*LOCAL, 'scheduled') for case in selected):
        if not all((args.engine_source, args.engine_python, args.engine_reviewed_manifest)):
            parser.error('Remote native cases require engine source, interpreter and reviewed manifest')
    if not args.build_only and args.host in ('all', 'claude') and not args.claude_profile_binding:
        parser.error('Claude native runs require --claude-profile-binding from reviewed readiness evidence')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    candidate = source_snapshot(ROOT)
    (args.output_dir / 'candidate.json').write_text(json.dumps(candidate, indent=2))
    hosts = ('claude', 'codex', 'opencode') if args.host == 'all' else (args.host,)
    results = {'candidate': candidate, 'base': BASE, 'candidate_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'hosts': {}, 'native_acceptance': not args.build_only,
               'full_matrix': args.host == 'all' and not args.cases and not args.local_only and not args.build_only}
    if args.engine_reviewed_manifest:
        results['engine_reviewed_manifest'] = json.loads(args.engine_reviewed_manifest.read_text())
        args.engine_snapshot = verify_engine_manifest(args)
        results['engine_snapshot'] = args.engine_snapshot
    if not args.build_only and 'claude' in hosts:
        results['claude_permission_preflight'] = preflight(args, args.output_dir)
    for host in hosts:
        if not args.build_only:
            version = subprocess.run([host, '--version'], capture_output=True, text=True)
            results.setdefault('versions', {})[host] = version.stdout.strip()
        if host == 'claude' and not args.build_only and not results['claude_permission_preflight']['passed']:
            results['hosts'][host] = [{'passed': False, 'error': 'Claude permission preflight failed'}]
            continue
        results['hosts'][host] = [run_case(args, args.output_dir, host, case, candidate)
                                 for case in selected if case != 'scheduled' or host == 'claude']
    results['passed'] = all(row['passed'] for group in results['hosts'].values() for row in group)
    require_unchanged(candidate, source_snapshot(ROOT), 'Candidate source snapshot')
    (args.output_dir / 'results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps({'passed': results['passed'], 'native_acceptance': results['native_acceptance'], 'evidence': str(args.output_dir / 'results.json')}))
    return 0 if results['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
