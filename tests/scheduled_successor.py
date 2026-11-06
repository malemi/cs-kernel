"""Exact MCP permission successor for the immutable bootstrap comparison."""
import hashlib
import json
from pathlib import Path
from scheduled_m5_successor import load_m5_successors, undo_m5_rendered

PATHS = ('.claude/settings.json', 'bin/cs_operator_cron.sh')
VARIANTS = ('generic/normal', 'generic/conditional', 'as-built/normal', 'as-built/conditional')
FORMS = ('.venv/bin/python -m cs', '.venv/bin/python3 -m cs', '.venv/bin/cs',
         'python -m cs', 'python3 -m cs', 'cs')
METHODS = ('operator.rules.decide', 'operator.rules.import_confirm')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def insertion(rel):
    if rel not in PATHS:
        raise ValueError('unknown successor path')
    prefix, suffix = ('      ', ',\n') if rel == PATHS[0] else ('    ', ' \\\n')
    return ''.join(prefix + '"Bash(' + form + ' rpc ' + method + ':*)"' + suffix
                   for method in METHODS for form in FORMS).encode()


def exact_undo(data, rel, hashes):
    if set(hashes) != {'before_sha256', 'after_sha256'}:
        raise ValueError('missing or extra stage hash')
    if digest(data) != hashes['after_sha256']:
        raise ValueError('stage postimage hash mismatch')
    block = insertion(rel)
    if data.count(block) != 1:
        raise ValueError('successor insertion must occur exactly once')
    before = data.replace(block, b'', 1)
    if digest(before) != hashes['before_sha256']:
        raise ValueError('stage preimage hash mismatch')
    return before


def load_successors(template_root, packet=None):
    if packet is None:
        packet = json.loads(Path(__file__).with_name('scheduled_successor.json').read_text())
    if set(packet) != {'schema_version', 'stages'} or packet['schema_version'] != 1:
        raise ValueError('invalid successor manifest')
    if not isinstance(packet['stages'], list) or len(packet['stages']) != len(PATHS):
        raise ValueError('wrong successor stage cardinality')
    result = {}
    for rel, stage in zip(PATHS, packet['stages']):
        if set(stage) != {'id', 'template', 'source', 'rendered'}:
            raise ValueError('missing or extra stage field')
        if stage['id'] != 'mcp-owner-denies:' + rel or stage['template'] != rel + '.j2':
            raise ValueError('wrong stage template binding')
        exact_undo((template_root / stage['template']).read_bytes(), rel, stage['source'])
        rendered = stage['rendered']
        if not isinstance(rendered, dict) or set(rendered) != set(VARIANTS):
            raise ValueError('wrong rendered variants')
        for key, row in rendered.items():
            if set(row) != {'variant', 'hashes'} or row['variant'] != key:
                raise ValueError('wrong rendered variant binding')
            if set(row['hashes']) != {'before_sha256', 'after_sha256'}:
                raise ValueError('missing or extra rendered hash')
        result[rel] = stage
    result["m5"] = load_m5_successors(template_root)
    return result


def undo_rendered(data, rel, shape, variant, stages):
    if rel not in PATHS:
        return undo_m5_rendered(data, rel, shape, variant, stages["m5"])
    return exact_undo(data, rel, stages[rel]['rendered'][shape + '/' + variant]['hashes'])
