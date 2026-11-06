"""Refutation controls for the exact scheduled permission successor."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from scheduled_successor import PATHS, VARIANTS, load_successors, undo_rendered
from test_capabilities_skill import pi, _FULL_INIT_DATA, TPL


class SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(Path(__file__).with_name('scheduled_successor.json').read_text())

    def exercise(self, packet, root=TPL):
        stages = load_successors(root, packet)
        env = pi.build_jinja_env(root)
        for key in VARIANTS:
            shape, variant = key.split('/')
            config = {**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA, 'repo_docs_shape': shape}
            if variant == 'conditional':
                config.update(accounts={'support': 'UID123', 'founder@acme.example': 'UID999'},
                              accounts_default='support', founder_sweep_enabled=True,
                              founder_sweep_account='founder@acme.example',
                              excluded_campaign='synthetic-paused-campaign',
                              local_scripts_cron_denied=['bin/synthetic_local.py'])
            for rel in PATHS:
                raw = env.get_template(rel + '.j2').render(**config).encode()
                before = undo_rendered(raw, rel, shape, variant, stages)
                self.assertNotIn(b'operator.rules.decide', before)
                self.assertNotIn(b'operator.rules.import_confirm', before)

    def test_valid_exact_successors(self):
        self.exercise(self.packet)

    def test_each_source_and_rendered_hash_is_mandatory_and_enforced(self):
        for index in range(2):
            for scope in ('source', *VARIANTS):
                for field in ('before_sha256', 'after_sha256'):
                    for mutation in ('missing', 'corrupt'):
                        packet = copy.deepcopy(self.packet)
                        stage = packet['stages'][index]
                        hashes = stage['source'] if scope == 'source' else stage['rendered'][scope]['hashes']
                        if mutation == 'missing':
                            del hashes[field]
                        else:
                            hashes[field] = '0' * 64
                        with self.subTest(index=index, scope=scope, field=field, mutation=mutation):
                            with self.assertRaises(ValueError):
                                self.exercise(packet)

    def test_cardinality_template_and_variant_bindings(self):
        cases = []
        packet = copy.deepcopy(self.packet); packet['stages'].reverse(); cases.append(packet)
        packet = copy.deepcopy(self.packet); packet['stages'].pop(); cases.append(packet)
        packet = copy.deepcopy(self.packet); packet['stages'].append(copy.deepcopy(packet['stages'][0])); cases.append(packet)
        packet = copy.deepcopy(self.packet); packet['stages'][1] = copy.deepcopy(packet['stages'][0]); cases.append(packet)
        for index in range(2):
            packet = copy.deepcopy(self.packet); packet['stages'][index]['template'] = 'foreign.j2'; cases.append(packet)
            packet = copy.deepcopy(self.packet)
            rows = packet['stages'][index]['rendered']; a, b = VARIANTS[:2]
            rows[a], rows[b] = rows[b], rows[a]; cases.append(packet)
            packet = copy.deepcopy(self.packet); del packet['stages'][index]['rendered'][VARIANTS[0]]; cases.append(packet)
            packet = copy.deepcopy(self.packet); packet['stages'][index]['rendered']['extra'] = {}; cases.append(packet)
            packet = copy.deepcopy(self.packet)
            hashes = packet['stages'][index]['source']
            hashes['before_sha256'], hashes['after_sha256'] = hashes['after_sha256'], hashes['before_sha256']
            cases.append(packet)
            for key in VARIANTS:
                packet = copy.deepcopy(self.packet)
                hashes = packet['stages'][index]['rendered'][key]['hashes']
                hashes['before_sha256'], hashes['after_sha256'] = hashes['after_sha256'], hashes['before_sha256']
                cases.append(packet)
        for index, packet in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.exercise(packet)

    def test_unapproved_source_mutation(self):
        for changed in PATHS:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for rel in PATHS:
                    target = root / (rel + '.j2')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((TPL / (rel + '.j2')).read_bytes() + (b'\nunauthorized\n' if rel == changed else b''))
                with self.assertRaisesRegex(ValueError, 'postimage hash'):
                    load_successors(root, self.packet)


if __name__ == '__main__':
    unittest.main(verbosity=2)
