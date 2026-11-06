"""Refutation controls for exact M5 intermediate source and rendered stages."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scheduled_m5_successor import load_m5_successors, undo_m5_rendered, TRIAGE, CAMPAIGN, VARIANTS, digest
from test_capabilities_skill import pi, _FULL_INIT_DATA, TPL


class M5SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(Path(__file__).with_name('scheduled_m5_successor.json').read_text())
        env = pi.build_jinja_env(TPL)
        self.rendered = {}
        for key in VARIANTS:
            shape, variant = key.split('/')
            config = {**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA, 'repo_docs_shape': shape}
            if variant == 'conditional':
                config.update(accounts={'support': 'UID123', 'founder@acme.example': 'UID999'},
                              accounts_default='support', founder_sweep_enabled=True,
                              founder_sweep_account='founder@acme.example',
                              excluded_campaign='synthetic-paused-campaign',
                              local_scripts_cron_denied=['bin/synthetic_local.py'])
            for rel in (TRIAGE, CAMPAIGN):
                self.rendered[key, rel] = env.get_template(rel + '.j2').render(**config).encode()

    def exercise(self, packet, root=TPL, rendered=None):
        stages = load_m5_successors(root, packet)
        for (key, rel), data in (rendered or self.rendered).items():
            shape, variant = key.split('/')
            before = undo_m5_rendered(data, rel, shape, variant, stages)
            self.assertEqual(digest(before), packet['rendered'][rel][key]['stages'][0]['hashes']['before_sha256'])

    def test_valid(self):
        self.exercise(self.packet)

    def test_every_intermediate_hash_rejects_corrupt_missing_and_swapped(self):
        locations = [('source', i) for i in range(3)]
        locations += [(rel, key, i) for rel in (TRIAGE, CAMPAIGN) for key in VARIANTS
                      for i in range(3 if rel == TRIAGE else 1)]
        count = 0
        for loc in locations:
            for field in ('before_sha256', 'after_sha256'):
                for mutation in ('missing', 'corrupt', 'swapped'):
                    packet = copy.deepcopy(self.packet)
                    hashes = (packet['sources'][loc[1]] if loc[0] == 'source' else
                              packet['rendered'][loc[0]][loc[1]]['stages'][loc[2]])['hashes']
                    if mutation == 'missing':
                        del hashes[field]
                    elif mutation == 'corrupt':
                        hashes[field] = '0' * 64
                    else:
                        hashes['before_sha256'], hashes['after_sha256'] = hashes['after_sha256'], hashes['before_sha256']
                    with self.subTest(location=loc, field=field, mutation=mutation), self.assertRaises(ValueError):
                        self.exercise(packet)
                    count += 1
        print('M5 hash mutation controls rejected:', count)

    def test_stage_and_variant_bindings(self):
        cases = []
        for path in [('sources',)] + [('rendered', rel, key, 'stages') for rel in (TRIAGE, CAMPAIGN) for key in VARIANTS]:
            for operation in ('remove', 'duplicate', 'reverse', 'wrong-id', 'missing-field', 'extra-field'):
                packet = copy.deepcopy(self.packet); stages = packet
                for k in path: stages = stages[k]
                if operation == 'remove': stages.pop()
                elif operation == 'duplicate': stages.append(copy.deepcopy(stages[0]))
                elif operation == 'reverse':
                    if len(stages) == 1: continue
                    stages.reverse()
                elif operation == 'wrong-id': stages[0]['id'] = 'foreign'
                elif operation == 'missing-field': del stages[0]['undo_old']
                else: stages[0]['extra'] = True
                cases.append(packet)
        for rel in (TRIAGE, CAMPAIGN):
            packet = copy.deepcopy(self.packet); del packet['rendered'][rel][VARIANTS[0]]; cases.append(packet)
            packet = copy.deepcopy(self.packet); packet['rendered'][rel][VARIANTS[0]]['variant'] = VARIANTS[1]; cases.append(packet)
        for i, packet in enumerate(cases):
            with self.subTest(index=i), self.assertRaises(ValueError): self.exercise(packet)
        print('M5 stage/variant mutation controls rejected:', len(cases))

    def test_unrelated_and_duplicate_bytes(self):
        for (key, rel), original in self.rendered.items():
            for data in (original + b'\nunapproved\n', original + self.packet['rendered'][rel][key]['stages'][-1]['undo_old'].encode()):
                rendered = dict(self.rendered); rendered[key, rel] = data
                with self.subTest(key=key, rel=rel), self.assertRaises(ValueError):
                    self.exercise(self.packet, rendered=rendered)
        for rel in {stage['template'] for stage in self.packet['sources']}:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for source in {stage['template'] for stage in self.packet['sources']}:
                    dest = root / source; dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes((TPL.parent / source).read_bytes())
                target = root / rel
                target.write_bytes(target.read_bytes() + b'\nunapproved\n')
                with self.assertRaises(ValueError): self.exercise(self.packet, root / 'project')


if __name__ == '__main__':
    unittest.main(verbosity=2)
