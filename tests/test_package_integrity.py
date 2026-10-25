"""Actual clean-wheel CLI verification and immutable-reference drift controls."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile


SOURCE = Path(__file__).resolve().parents[1]


def run(argv, cwd, env=None):
    result = subprocess.run([str(arg) for arg in argv], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, (argv, result.returncode, result.stdout, result.stderr)
    return result.stdout.strip()


with tempfile.TemporaryDirectory(prefix='cs-integrity-test-') as temporary:
    base = Path(temporary)
    repo = base / 'reference'
    repo.mkdir()
    shutil.copytree(SOURCE / 'cs', repo / 'cs', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(SOURCE / 'pyproject.toml', repo / 'pyproject.toml')
    run(['git', 'init', '-q'], repo)
    run(['git', 'add', 'cs', 'pyproject.toml'], repo)
    run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
         'commit', '-qm', 'immutable fixture'], repo)
    commit = run(['git', 'rev-parse', 'HEAD'], repo)
    import tomllib
    version = tomllib.loads((repo / 'pyproject.toml').read_text())['project']['version']
    tag = 'v' + version
    run(['git', 'tag', tag], repo)
    wheels = base / 'wheels'
    run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
         '--wheel-dir', wheels, repo], base)
    wheel = next(wheels.glob('*.whl'))
    tracked = set(run(['git', 'ls-tree', '-r', '--name-only', commit, '--', 'cs/'], repo).splitlines())
    with zipfile.ZipFile(wheel) as archive:
        packaged = {name for name in archive.namelist() if name.startswith('cs/') and not name.endswith('/')}
    assert packaged == tracked, {'missing': sorted(tracked-packaged), 'extra': sorted(packaged-tracked)}
    environment = base / 'venv'
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
    python = environment / 'bin/python'
    run([python, '-m', 'pip', 'install', '--no-deps', '--ignore-installed', wheel], base)
    clone = base / 'clone'
    clone.mkdir()
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'PYTHONHOME', 'CS_OPERATOR_HEALTH_CONTEXT'):
        env.pop(key, None)
    package = Path(run([python, '-c', 'import cs; print(cs.__file__)'], clone, env)).parent
    dist = next(package.parent.glob('cs_kernel-*.dist-info'))
    command = [environment / 'bin/cs', 'verify-install', '--json', '--reference-repo', repo,
               '--tag', tag, '--expected-commit', commit]

    def check(label, ok=False, error=None, options=None, environment_override=None):
        result = subprocess.run(options or command, cwd=clone, env=environment_override or env,
                                capture_output=True, text=True, timeout=90)
        value = json.loads(result.stdout)
        assert 'Traceback' not in result.stderr, (label, result.stderr)
        assert (result.returncode == 0) == ok and value['ok'] == ok, (label, result.returncode, value, result.stderr)
        if error:
            assert value.get('error') == error, (label, value)
        print('PASS:', label, value.get('error', 'clean'))
        return value

    check('clean wheel from tagged Git bytes', ok=True)
    (repo / 'cs/__init__.py').write_text('dirty reference must not become authority\n')
    check('dirty reference worktree ignored', ok=True)
    for relative in ('_version.py', 'templates/project/CLAUDE.md'):
        target = package / relative
        original = target.read_bytes()
        target.write_bytes(original + b'\n')
        value = check('modified ' + relative, error='package_drift')
        assert {'path': relative, 'reason': 'modified'} in value['mismatches']
        record = dist / 'RECORD'
        record_before = record.read_bytes()
        record.write_text('cs/' + relative + ',sha256=' + hashlib.sha256(target.read_bytes()).hexdigest() + ',' + str(target.stat().st_size) + '\n')
        check('rewritten RECORD cannot bless ' + relative, error='package_drift')
        record.write_bytes(record_before)
        target.write_bytes(original)
    target = package / 'unexpected.txt'
    target.write_text('extra')
    check('extra package resource', error='package_drift')
    target.unlink()
    target = package / 'templates/project/CLAUDE.md'
    original = target.read_bytes()
    target.unlink()
    check('missing package resource', error='package_drift')
    target.write_bytes(original)
    target = package / 'unsafe-link'
    target.symlink_to(base)
    check('unsafe directory symlink', error='package_drift')
    target.unlink()
    run(['git', 'tag', 'v99.0.0', commit], repo)
    wrong_tag = list(command)
    wrong_tag[6] = 'v99.0.0'
    check('tag version mismatch', error='tag_version_mismatch', options=wrong_tag)
    check('wrong expected immutable commit', error='commit_mismatch', options=command[:-1] + ['0'*40])
    check('unavailable reference', error='reference_unavailable', options=[*command[:4], base/'absent', *command[5:]])
    metadata = dist / 'METADATA'
    original = metadata.read_bytes()
    metadata.write_text(metadata.read_text().replace('Version: ' + version, 'Version: 99.0.0', 1))
    check('wrong installed version', error='installed_version_mismatch')
    metadata.write_bytes(original)
    direct = dist / 'direct_url.json'
    original = direct.read_bytes()
    direct.write_text(json.dumps({'url': repo.as_uri(), 'vcs_info': {'vcs':'git','commit_id':'0'*40}}))
    check('wrong installed direct URL commit', error='installed_commit_mismatch')
    direct.write_text(json.dumps({'url': repo.as_uri(), 'dir_info': {'editable':True}}))
    check('editable origin rejected', error='editable_install')
    for malformed in ([], None, {'dir_info': []}, {'dir_info': None},
                      {'vcs_info': []}, {'vcs_info': None},
                      {'vcs_info': {'requested_revision': []}}):
        direct.write_text(json.dumps(malformed))
        check('malformed direct URL metadata ' + json.dumps(malformed), error='integrity_unavailable')
    direct.write_bytes(original)
    shadow = base / 'shadow'
    shutil.copytree(package, shadow / 'cs', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    check('PYTHONPATH import shadow', error='import_origin_mismatch', environment_override={**env, 'PYTHONPATH':str(shadow)})
    (clone / 'requirements.txt').write_text('cs-kernel @ git+' + repo.as_uri() + '@' + tag + '\n')
    check('default clone pin independently fetched', ok=True, options=command[:3])
    (clone / 'requirements.lock').write_text('cs-kernel @ git+' + repo.as_uri() + '@' + '0'*40 + '\n')
    check('wrong lock commit rejected', error='lock_commit_mismatch')
    (clone / 'requirements.lock').unlink()
    check('restored installation remains clean', ok=True)
print('PASS: real tagged repository, complete wheel inventory, actual installed CLI and adversarial integrity controls')
