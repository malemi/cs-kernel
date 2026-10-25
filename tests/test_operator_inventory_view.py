"""Constructed neutral inventory controls exercise real private files and dd results."""
import copy
import hashlib
import json
import os
import shlex
from pathlib import Path
import subprocess
import tempfile

from cs import operator_inventory_view as view


def control(owner):
    root = '<conversation@example.test>'
    discovery = {'open': [{'email': 'contact@example.test', 'thread_key': root, 'subject': 'Question', '_workset_revision': 'revision'}],
                 'human_work': [], 'assignment_audit': [], 'operational_fixture_discovery': [],
                 'read_incomplete': None, 'assignment_incomplete': False,
                 'triage_workset': {'complete': True, 'limit': 2, 'selected': [{'thread_key': root, 'revision': 'revision', 'sources': ['open']}], 'deferred': [], 'held': []}}
    return {'owner_uid': owner, 'nonce': 'nonce', 'ancestry': [{'pid': 3, 'started_ticks': 30}, {'pid': 2, 'started_ticks': 20}, {'pid': 1, 'started_ticks': 10}],
            'exit_code': 0, 'output_sha256': hashlib.sha256((json.dumps(discovery, ensure_ascii=False, indent=2) + '\n').encode()).hexdigest(), 'discovery': discovery}


def events_for(path, data, commands=None, trim_transport=False):
    events = []
    commands = commands or [view.page_command(path, offset, data) for offset in range(0, len(data), 8064)]
    for index, command in enumerate(commands):
        result = subprocess.run(command, shell=True, capture_output=True, check=True).stdout.decode('utf-8', 'replace')
        if trim_transport:
            result = result.strip()  # CONSTRUCTED conservative native transport behavior.
        tool = path.name + '-page-' + str(index)
        events.extend([{'session_id': 'native', 'message': {'content': [{'type': 'tool_use', 'id': tool, 'name': 'Bash', 'input': {'command': command}}]}},
                       {'session_id': 'native', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': tool, 'is_error': False, 'content': result}]}}])
    return events


for owner in ('constructed-primary-actor', 'constructed-secondary-actor'):
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        context = {'directory': temp, 'owner_uid': owner, 'nonce': 'nonce', 'supervisor': {'pid': 1, 'started_ticks': 10}}
        raw = json.dumps(control(owner)).encode()
        view.exclusive(directory / 'discovery.json', raw)
        view.capture(context)
        path, data, envelope = view.load(context)
        assert envelope['raw_sha256'] == hashlib.sha256(raw).hexdigest()
        assert b'offline M0' not in data
        for key, value in [('nonce', 'stale'), ('owner_uid', 'foreign'), ('supervisor', {'pid': 1, 'started_ticks': 11})]:
            try:
                view.load({**context, key: value})
            except ValueError:
                pass
            else:
                raise AssertionError('foreign context accepted')
        view_events = events_for(path / 'inventory-view.jsonl', data)
        assert not view.audit(view_events, context)
        events = events_for(path / 'inventory-view-envelope.json', view.read_private(path / 'inventory-view-envelope.json')) + view_events
        assert view.audit(events, context)
        assert not data.endswith(b'\n')
        progress = json.loads(view.read_private(path / 'inventory-view-progress.json'))
        assert envelope['page_plan'] == progress['page_plan']
        trimmed = events_for(path / 'inventory-view-envelope.json', view.read_private(path / 'inventory-view-envelope.json'), trim_transport=True)
        trimmed += events_for(path / 'inventory-view.jsonl', data, envelope['page_plan'], trim_transport=True)
        assert view.audit(trimmed, context)
        assert not view.audit(trimmed[:-1], context)
        assert not view.audit(events[:-1], context)
        try:
            view.audit(events + [events[-1]], context)
        except ValueError:
            pass
        else:
            raise AssertionError('duplicate result accepted')
        bad = copy.deepcopy(events)
        bad[-1]['message']['content'][0]['content'] += 'clipped'
        assert not view.audit(bad, context)
        bad = copy.deepcopy(events)
        bad[-1]['session_id'] = 'stale'
        assert not view.audit(bad, context)
        effect = {'message': {'content': [{'type': 'tool_use', 'name': 'Bash', 'id': 'effect', 'input': {'command': 'cs draft-send exact-id'}}]}}
        assert not view.audit([effect] + events, context)
        before = copy.deepcopy(events)
        view.update_progress(events, context)
        assert events == before
        progress = json.loads(view.read_private(path / 'inventory-view-progress.json'))
        assert progress['covered'] == [[0, len(data)]] and progress['next_command'] is None
        literal = control(owner)
        literal['discovery']['triage_workset']['selected'][0]['sources'] = ['absent']
        assert '[\"literal\",[\"absent\"]]' in view.produce(literal, view.binding_for(json.dumps(literal).encode(), literal, context))
        target = path / 'inventory-view-progress.json'
        target.unlink()
        target.symlink_to(path / 'inventory-view-envelope.json')
        try:
            view.update_progress(events, context)
        except OSError:
            pass
        else:
            raise AssertionError('symlink progress accepted')
        target.unlink()
        os.link(path / 'inventory-view-envelope.json', target)
        try:
            view.update_progress(events, context)
        except ValueError:
            pass
        else:
            raise AssertionError('hardlink progress accepted')
        target.unlink()
        changed = bytearray(data)
        changed[-2] ^= 1
        (path / 'inventory-view.jsonl').write_bytes(changed)
        try:
            view.load(context)
        except ValueError:
            pass
        else:
            raise AssertionError('tampered view accepted')
        assert (path / 'discovery.json').read_bytes() == raw
        for mutate in (lambda d: d['discovery'].update(unknown=[]), lambda d: d['discovery']['triage_workset'].update(limit=True), lambda d: d['discovery']['open'][0].update(days_waiting=False)):
            record = control(owner)
            mutate(record)
            try:
                view.produce(record, view.binding_for(json.dumps(record).encode(), record, context))
            except ValueError:
                pass
            else:
                raise AssertionError('unclassified type accepted')
try:
    value = []
    for _ in range(66):
        value = [value]
    view.bounded(value)
except ValueError:
    pass
else:
    raise AssertionError('depth accepted')
print('semantic inventory: BOTH actor shapes CONSTRUCTED; projection/refusal/private files/exact native dd/early effect/progress/tamper PASS')

# Neutral synthetic boundaries: original dd bytes remain exact under a
# conservative CONSTRUCTED whitespace-trimming transport. No provider launched.
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'neutral-view.jsonl'
    synthetic = (b'{' + b'x' * 8190 + b'\n' + ('é☕ unicode \n' * 1800).encode() + b'}')
    view.exclusive(path, synthetic)
    ranges = view._pages(synthetic)
    assert len(ranges) > 2 and ranges[0][1] == 8191
    previous_end = 0
    previous_start = None
    commands = []
    for begin, end in ranges:
        text = synthetic[begin:end].decode('utf-8')
        assert text and not text[0].isspace() and not text[-1].isspace()
        assert 0 < end - begin <= 8192 and begin <= previous_end < end
        if previous_start is not None:
            assert 0 < begin - previous_start <= 8064 and previous_end - begin >= 128
        commands.append(view._page_text(path, begin, end))
        previous_start, previous_end = begin, end
    assert previous_end == len(synthetic)
    matched = events_for(path, synthetic, commands, trim_transport=True)
    assert view.coverage(matched, path, synthetic) == (len(synthetic), False)
    assert view.coverage(matched[:-1], path, synthetic)[0] < len(synthetic)
    try:
        view._pages(b'{' + b' ' * 20000 + b'}')
    except ValueError:
        pass
    else:
        raise AssertionError('undeliverable whitespace page plan accepted')
    try:
        view._pages(b'{\xff}')
    except UnicodeError:
        pass
    else:
        raise AssertionError('invalid UTF-8 plan accepted')
print('EOF framing: neutral BOTH actors, mandatory envelope plan, real dd with CONSTRUCTED trimming, interior LF/UTF-8, incomplete/unsafe plan PASS')

for owner in ('constructed-primary-actor', 'constructed-secondary-actor'):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary)
        record = control(owner)
        record['discovery']['open'][0]['subject'] = ' ' * 20000
        raw = json.dumps(record).encode()
        view.exclusive(path / 'discovery.json', raw)
        context = {'directory': temporary, 'owner_uid': owner, 'nonce': 'nonce',
                   'supervisor': {'pid': 1, 'started_ticks': 10}}
        try:
            view.capture(context)
        except ValueError:
            pass
        else:
            raise AssertionError('undeliverable compact capture accepted')
        assert sorted(x.name for x in path.iterdir()) == ['discovery.json']
        assert (path / 'discovery.json').read_bytes() == raw
print('Undeliverable compact transport: BOTH actors refuse before artifacts; full raw retained PASS')

for owner in ('constructed-primary-actor', 'constructed-secondary-actor'):
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary)
        record = control(owner)
        record['discovery']['open'][0]['subject'] = 'N' * 1000000
        view.exclusive(path / 'discovery.json', json.dumps(record).encode())
        context = {'directory': temporary, 'owner_uid': owner, 'nonce': 'nonce',
                   'supervisor': {'pid': 1, 'started_ticks': 10}}
        view.capture(context)
        _, data, envelope = view.load(context)
        wire = view.read_private(path / 'inventory-view-envelope.json')
        assert len(wire) > 8192 and wire.isascii()
        assert not any(chr(c).isspace() for c in wire)
        assert json.loads(wire) == envelope
        assert ' ' in envelope['page_plan'][0]  # Standard JSON preserves commands.
        envelope_events = events_for(path / 'inventory-view-envelope.json', wire, trim_transport=True)
        view_events = events_for(path / 'inventory-view.jsonl', data, envelope['page_plan'], trim_transport=True)
        assert view.audit(envelope_events + view_events, context)
        assert not view.audit(envelope_events[:2] + view_events, context)
print('Mandatory multi-page envelope: BOTH actors standard JSON parity, real bounded dd under CONSTRUCTED trimming, incomplete refusal PASS')


# Native denial/control messages are not tool-result evidence. Their shape must
# not crash inventory diagnostics or turn a failed dd into inspected bytes.
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'view.jsonl'
    data = b'{"neutral":true}'
    view.exclusive(path, data)
    success = events_for(path, data)
    denied = copy.deepcopy(success)
    denied[-1]['message']['content'][0]['is_error'] = True
    for message in ('Permission denied by classifier', {'content': []}, None,
                    {'content': None}, {'content': 'not tool blocks'}):
        control_event = {'type': 'system', 'subtype': 'permission_denied', 'message': message}
        assert view.coverage([control_event] + success, path, data) == (len(data), False)
        assert view.coverage([control_event] + denied, path, data) == (0, False)
        assert view.coverage([control_event], path, data) == (0, False)
print('Native message shapes: denial/control grants no coverage; failed dd stays uninspected PASS')

# A missing provenance object is literal null, never an empty object or absence.
def nullable_control(source):
    record = control('constructed-null-owner')
    record['discovery']['human_work'] = [{
        'thread_key': '<held@example.test>',
        'assignment': {'state': 'needs-assignment', 'complete': False,
                       'hold_auto_reply': True, 'task': None,
                       'reply_evidence': [{'version': 1, 'actor_uid': 'constructed-null-owner',
                                           'space_id': 'neutral-space', 'source_id': 'neutral-source',
                                           'thread_key': '<held@example.test>', 'complete': False,
                                           'judgement': 'HUMAN_VERIFICATION', 'reason': 'missing-source',
                                           'source': source}]}}]
    record['discovery']['assignment_incomplete'] = True
    return record


def observation_cells(record):
    context = {'owner_uid': record['owner_uid'], 'nonce': record['nonce'],
               'supervisor': record['ancestry'][-1]}
    raw = json.dumps(record).encode()
    text = view.produce(record, view.binding_for(raw, record, context))
    lines = [json.loads(line) for line in text.splitlines()]
    index = next(i for i, row in enumerate(lines)
                 if isinstance(row, dict) and row.get('table') == 'observations')
    return lines[index + 1][-4:], lines


cells, rows = observation_cells(nullable_control(None))
assert cells == [None] * 4
assert 'four null source.* cells mean source:null' in rows[0]['legend']
assert observation_cells(nullable_control({}))[0] == [['absent']] * 4
assert observation_cells(nullable_control({'observation_only': False}))[0][-1] is False
for wrong in (False, True, 0, 1, 1.5, '', 'source', [], [None]):
    try:
        view.check(nullable_control(wrong))
    except ValueError:
        pass
    else:
        raise AssertionError('wrong observation source type accepted')
for bad in (nullable_control({'provider': None}), nullable_control({'actor_uid': None}),
            nullable_control({'observation_only': None})):
    try:
        view.check(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('nested source null accepted')
missing = nullable_control(None)
del missing['discovery']['human_work'][0]['assignment']['reply_evidence'][0]['source']
other = nullable_control(None)
other['discovery']['triage_workset']['held'] = [
    {'thread_key': None, 'reason': 'missing_exact_root', 'source': None, 'identity': 'held-task'}]
for bad in (missing, other):
    try:
        view.check(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('missing or unrelated nullable source accepted')
print('Nullable observation source: literal null/object/absence distinction and strict wrong-type refusals PASS')

for source in (None, {}):
    for digest in (None, 'neutral-digest'):
        value = nullable_control(source)
        value['discovery']['human_work'][0]['assignment']['reply_evidence'][0]['digest'] = digest
        cells, tables = observation_cells(value)
        assert 'null observation digest means no verification digest and grants no authority' in tables[0]['legend']
        assert cells == ([None] * 4 if source is None else [['absent']] * 4)
for wrong in (False, True, 0, 1.5, [], {}, [None]):
    bad = nullable_control(None)
    bad['discovery']['human_work'][0]['assignment']['reply_evidence'][0]['digest'] = wrong
    try:
        view.check(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid observation digest accepted')
for bad in (nullable_control({'route_digest': None}), nullable_control(None)):
    if bad['discovery']['human_work'][0]['assignment']['reply_evidence'][0]['source'] is None:
        bad['discovery']['human_work'][0]['assignment']['route_digest'] = None
    try:
        view.check(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('unrelated null digest accepted')
print('Optional observation digest: null/string/absent preserve RAW REF policy; wrong types/paths refuse PASS')
