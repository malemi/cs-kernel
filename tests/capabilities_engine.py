from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def atomic_json(path, value):
    pending = path.with_suffix(path.suffix + '.pending')
    pending.write_text(json.dumps(value, indent=2))
    pending.replace(path)


def verify_engine_manifest(args):
    manifest_path = args.engine_reviewed_manifest.resolve()
    manifest = json.loads(manifest_path.read_text())
    assert Path(manifest['root']).resolve() / 'engine' == args.engine_source.resolve(), 'Engine manifest root mismatch'
    assert Path(manifest['engine']['python']).absolute() == Path(args.engine_python).absolute(), 'Engine interpreter differs from manifest'
    code = "import json, sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from tests.rpc.catalog_journey_manifest import verify; print(json.dumps(verify(Path(sys.argv[2]))))"
    env = {key: value for key, value in os.environ.items() if key in ('PATH', 'LANG', 'TZ', 'LC_ALL')}
    result = subprocess.run([args.engine_python, '-c', code, str(args.engine_source), str(manifest_path)],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, 'Engine source/dependency verification failed: ' + result.stderr
    return json.loads(result.stdout)


def serve(args):
    sys.path.insert(0, str(args.engine_source))
    from tests.rpc import catalog_journey_env
    fixture = None

    def save():
        atomic_json(args.serve / 'engine-evidence.json', {
            'rpc_log': fixture.rpc_log, 'requests': fixture.requests,
            'responses': fixture.responses, 'provider_requests': fixture.provider_requests,
            'forbidden_attempts': fixture.forbidden_attempts, 'closed': fixture.closed,
        })

    with catalog_journey_env.start(args.serve / 'state', bank_state=args.bank_state) as fixture:
        atomic_json(args.serve / 'ready.json', {
            'url': fixture.url, 'owner_uid': fixture.owner_uid, 'token': fixture.token,
            'bank_system': fixture.bank_system, 'secrets': list(fixture.seeded_secrets),
            'prohibited_values': list(fixture.prohibited_values),
            'fixture_source': str(Path(catalog_journey_env.__file__).resolve()),
        })
        while not (args.serve / 'stop').exists():
            save()
            time.sleep(.1)
    save()


class Engine:
    def __init__(self, root, args, case):
        self.root, self._closed = root, False
        root.mkdir()
        self.log = (root / 'engine.log').open('w')
        env = {key: value for key, value in os.environ.items() if key in ('PATH', 'LANG', 'TZ', 'LC_ALL')}
        driver = Path(__file__).with_name('live_capabilities_skill.py')
        self.process = subprocess.Popen([args.engine_python, str(driver), '--serve', str(root),
            '--engine-source', str(args.engine_source), '--bank-state', 'older_engine' if case == 'older-engine' else 'connected'],
            env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 90
        while not (root / 'ready.json').exists():
            if self.process.poll() is not None or time.monotonic() > deadline:
                self.close()
                raise AssertionError(f'Engine fixture failed: {root / "engine.log"}')
            time.sleep(.1)
        self.info = json.loads((root / 'ready.json').read_text())
        expected = (args.engine_source / 'tests/rpc/catalog_journey_env.py').resolve()
        assert Path(self.info['fixture_source']) == expected, 'Wrong engine fixture imported'

    def evidence(self):
        assert self._closed and self.process.returncode == 0, 'Engine fixture did not close normally'
        data = json.loads((self.root / 'engine-evidence.json').read_text())
        assert data['closed'] is True, 'Fixture cleanup was not completed'
        assert not data['forbidden_attempts'], 'Engine attempted forbidden network/model work'
        assert len(data['requests']) == len(data['responses']), 'Incomplete engine response evidence'
        assert data['rpc_log'] == [request.get('method') for request in data['requests']], 'Engine request log mismatch'
        return data

    def close(self):
        if self._closed:
            return
        (self.root / 'stop').touch()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.close()
        self._closed = True


def validate_catalog_journey(case, requests, responses, bank_system, answer):
    assert requests and requests[0]['method'] == 'system.capabilities', 'Capabilities negotiation was not first'
    assert len(requests) == len(responses), 'Incomplete catalog responses'
    capabilities = responses[0].get('result')
    assert isinstance(capabilities, dict), 'Capabilities failed'
    assert all(response.get('id') == request.get('id') and 'error' not in response for request, response in zip(requests, responses)), 'Failed or mismatched discovery response'
    if case == 'older-engine':
        headline = answer.lstrip('# *>_`-').splitlines()[0].strip().lower() if answer.strip() else ''
        negative = r"^(?:no(?:[.!,:—–-]|\s+(?:access|bank|connection|route)\b)|(?:i|we) (?:cannot|can't|do not|don't) (?:access|reach)\b)"
        assert headline and not re.search(negative, headline), 'Older engine answer begins with an unsupported negative availability headline'
        assert 'system_catalog' not in capabilities, 'Older engine still advertises catalog'
        assert all(request['method'] == 'system.capabilities' for request in requests), 'Older engine catalog was called'
        return {'capabilities': capabilities, 'read_operation': None}
    assert type(capabilities.get('system_catalog')) is int and capabilities['system_catalog'] == 1, 'Catalog version was not negotiated'
    summaries, details = [], []
    for index, (request, response) in enumerate(zip(requests, responses)):
        assert response.get('id') == request.get('id'), 'Response identifier mismatch'
        if request['method'] != 'system.catalog':
            continue
        result = response.get('result')
        assert isinstance(result, dict) and result.get('version') == 1, 'Catalog response failed or changed version'
        params = request.get('params') or {}
        if not params:
            summaries.append((index, result))
        elif params == {'system': bank_system}:
            details.append((index, result))
    assert summaries, 'Catalog summary missing'
    assert any(row.get('id') == bank_system for row in summaries[0][1]['systems']), 'Bank missing from real summary'
    assert 'cs rpc' in answer, 'Engine CLI route missing'
    if case == 'named':
        return {'capabilities': capabilities, 'summary': summaries[0][1], 'detail': details[-1][1] if details else None, 'read_operation': None}
    assert details and summaries[0][0] < details[0][0], 'Bank detail was not preceded by summary'
    detail = details[-1][1]
    assert detail.get('system', {}).get('id') == bank_system, 'Wrong bank detail returned'
    eligible = []
    for operation in detail['operations']:
        flags = operation['effect']
        if any(flags[key] for key in ('changes_state', 'paid', 'destructive', 'returns_secret')):
            continue
        if operation['method'] in answer and all(name in answer for name in operation['required']):
            eligible.append(operation)
    assert eligible, 'Answer contains no real read method with its required parameter names'
    assert 'cs rpc' in answer, 'Engine CLI route missing'
    return {'capabilities': capabilities, 'summary': summaries[0][1], 'detail': detail, 'read_operation': eligible[0]}
