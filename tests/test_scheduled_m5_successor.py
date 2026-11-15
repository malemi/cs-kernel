"""Refutation controls for the exact interactive-reply scheduled-source successors."""
import copy
import json
import unittest

from scheduled_m5_successor import MANIFEST, ROOT, STAGES, digest, load, undo

SPELLINGS = (".venv/bin/python -m cs", ".venv/bin/python3 -m cs", ".venv/bin/cs",
             "python -m cs", "python3 -m cs", "cs")
RETIRE = ["Bash(%s draft-retire:*)" % spelling for spelling in SPELLINGS]
SETTINGS = "cs/templates/project/.claude/settings.json.j2"


class SuccessorTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(MANIFEST.read_text())
        self.current = {template: (ROOT / template).read_bytes() for _, template in STAGES}

    def exercise(self, packet=None, current=None):
        for template, data in (current or self.current).items():
            before = undo(template, data, packet or self.packet)
            stage = load(packet or self.packet)[template]
            self.assertEqual(digest(before), stage["hashes"]["before_sha256"])

    def test_valid_stages_reverse_exactly(self):
        self.exercise()

    def test_permission_stage_only_moves_draft_retire_from_deny_to_ask(self):
        after = json.loads(self.current[SETTINGS])["permissions"]
        before = json.loads(undo(SETTINGS, self.current[SETTINGS]))["permissions"]
        self.assertNotIn("ask", before)
        self.assertEqual(set(after), {"allow", "ask", "deny"})
        self.assertEqual(after["ask"], RETIRE)
        self.assertEqual(after["allow"], before["allow"])
        self.assertEqual(after["deny"], [entry for entry in before["deny"] if entry not in RETIRE])
        self.assertEqual([entry for entry in before["deny"] if entry in RETIRE], RETIRE)
        for entry in ("rpc drafts.discard_exact", "rpc drafts.reconcile_external"):
            for spelling in SPELLINGS:
                self.assertIn("Bash(%s %s:*)" % (spelling, entry), after["deny"])

    def test_every_hash_rejects_corrupt_missing_and_swapped(self):
        count = 0
        for index in range(len(STAGES)):
            for field in ("before_sha256", "after_sha256"):
                for mutation in ("missing", "corrupt", "swapped"):
                    packet = copy.deepcopy(self.packet)
                    hashes = packet["stages"][index]["hashes"]
                    if mutation == "missing":
                        del hashes[field]
                    elif mutation == "corrupt":
                        hashes[field] = "0" * 64
                    else:
                        hashes["before_sha256"], hashes["after_sha256"] = hashes["after_sha256"], hashes["before_sha256"]
                    with self.subTest(index=index, field=field, mutation=mutation), self.assertRaises(AssertionError):
                        self.exercise(packet)
                    count += 1
        print("successor hash mutation controls rejected:", count)

    def test_stage_and_edit_bindings(self):
        cases = []
        for operation in ("remove", "duplicate", "reverse", "wrong-id", "wrong-template",
                          "missing-field", "extra-field", "drop-edit", "change-edit", "empty-after",
                          "review-state", "extra-key"):
            packet = copy.deepcopy(self.packet)
            stages = packet["stages"]
            if operation == "remove":
                stages.pop()
            elif operation == "duplicate":
                stages.append(copy.deepcopy(stages[0]))
            elif operation == "reverse":
                stages.reverse()
            elif operation == "wrong-id":
                stages[0]["id"] = "foreign"
            elif operation == "wrong-template":
                stages[0]["template"] = stages[1]["template"]
            elif operation == "missing-field":
                del stages[0]["edits"]
            elif operation == "extra-field":
                stages[0]["extra"] = True
            elif operation == "drop-edit":
                stages[0]["edits"].pop()
            elif operation == "change-edit":
                stages[2]["edits"][0]["before"] += "unreviewed"
            elif operation == "empty-after":
                stages[1]["edits"][0]["after"] = ""
            elif operation == "review-state":
                packet["review_state"] = "APPROVED"
            else:
                packet["extra"] = True
            cases.append((operation, packet))
        for operation, packet in cases:
            with self.subTest(operation=operation), self.assertRaises(AssertionError):
                self.exercise(packet)
        print("successor stage/edit mutation controls rejected:", len(cases))

    def test_unrelated_and_duplicate_bytes(self):
        for template, original in self.current.items():
            stage = load(self.packet)[template]
            for data in (original + b"\nunapproved\n",
                         original + stage["edits"][-1]["after"].encode(),
                         original.replace(stage["edits"][0]["after"].encode()[:40], b"X" * 40, 1)):
                current = dict(self.current)
                current[template] = data
                with self.subTest(template=template), self.assertRaises(AssertionError):
                    self.exercise(current=current)


if __name__ == "__main__":
    unittest.main(verbosity=2)
