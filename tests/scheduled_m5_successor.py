"""Exact M5 workflow successors to the immutable scheduled comparison."""
import hashlib
import json
from pathlib import Path

VARIANTS = ('generic/normal', 'generic/conditional', 'as-built/normal', 'as-built/conditional')
IDS = ('m5-interactive-preparation', 'm5-composition-outcome', 'm5-shared-partial')
TRIAGE = '.claude/skills/cs-triage-mail/SKILL.md'
CAMPAIGN = '.claude/skills/cs-campaign-tick/SKILL.md'
SOURCES = ('project/' + TRIAGE + '.j2', 'project/' + TRIAGE + '.j2',
           'partials/outbound-fact-sourcing.md.j2')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def undo_stage(data, stage):
    hashes = stage['hashes']
    if not isinstance(hashes, dict) or set(hashes) != {'before_sha256', 'after_sha256'}:
        raise ValueError('missing or extra M5 stage hash')
    if digest(data) != hashes['after_sha256']:
        raise ValueError('M5 stage postimage hash mismatch')
    old, new = stage['undo_old'], stage['undo_new']
    if not isinstance(old, str) or not old or not isinstance(new, str):
        raise ValueError('invalid M5 reversal bytes')
    old, new = old.encode(), new.encode()
    if data.count(old) != 1:
        raise ValueError('M5 reversal must occur exactly once')
    before = data.replace(old, new, 1)
    if digest(before) != hashes['before_sha256']:
        raise ValueError('M5 stage preimage hash mismatch')
    return before


def validate_stages(stages, ids, source=False):
    if not isinstance(stages, list) or len(stages) != len(ids):
        raise ValueError('wrong M5 stage cardinality')
    fields = {'id', 'hashes', 'undo_old', 'undo_new'} | ({'template'} if source else set())
    for stage, identity in zip(stages, ids):
        if not isinstance(stage, dict) or set(stage) != fields or stage['id'] != identity:
            raise ValueError('wrong M5 stage binding')
        hashes = stage['hashes']
        if not isinstance(hashes, dict) or set(hashes) != {'before_sha256', 'after_sha256'}:
            raise ValueError('missing or extra M5 stage hash')
        if any(not isinstance(v, str) or len(v) != 64 or
               any(c not in '0123456789abcdef' for c in v) for v in hashes.values()):
            raise ValueError('invalid M5 stage hash')


def load_m5_successors(template_root, packet=None):
    if packet is None:
        packet = json.loads(Path(__file__).with_name('scheduled_m5_successor.json').read_text())
    if not isinstance(packet, dict) or set(packet) != {'schema_version', 'sources', 'rendered'} or packet['schema_version'] != 1:
        raise ValueError('invalid M5 successor manifest')
    sources = packet['sources']
    validate_stages(sources, IDS, source=True)
    for stage, rel in zip(sources, SOURCES):
        if stage['template'] != rel:
            raise ValueError('wrong M5 source path')
    data = {}
    for stage in reversed(sources):
        rel = stage['template']
        current = data.get(rel)
        if current is None:
            current = (template_root.parent / rel).read_bytes()
        data[rel] = undo_stage(current, stage)
    rendered = packet['rendered']
    if not isinstance(rendered, dict) or set(rendered) != {TRIAGE, CAMPAIGN}:
        raise ValueError('wrong M5 rendered paths')
    for rel, rows in rendered.items():
        if not isinstance(rows, dict) or set(rows) != set(VARIANTS):
            raise ValueError('wrong M5 rendered variants')
        for key, row in rows.items():
            if not isinstance(row, dict) or set(row) != {'variant', 'stages'} or row['variant'] != key:
                raise ValueError('wrong M5 rendered variant binding')
            validate_stages(row['stages'], IDS if rel == TRIAGE else IDS[2:])
    return rendered


def undo_m5_rendered(data, rel, shape, variant, stages):
    if rel not in (TRIAGE, CAMPAIGN):
        return data
    for stage in reversed(stages[rel][shape + '/' + variant]['stages']):
        data = undo_stage(data, stage)
    return data
