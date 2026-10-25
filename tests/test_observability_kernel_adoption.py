"""Offline adoption rejects business drift and preserves clone-specific behavior."""

import ast
import importlib.util
from pathlib import Path
import unittest
import tempfile

PATH = Path(__file__).resolve().parents[1] / "scripts/observability/adopt_kernel.py"
SPEC = importlib.util.spec_from_file_location("kernel_adopter", PATH)
adopter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adopter)


class AdoptionTests(unittest.TestCase):
    def test_business_ast_preserves_guard_and_rejects_mutation(self):
        before = """def send(args):
    if args.blocked:
        return 3
    return existing_send(args)
"""
        after = """from .observability_producers import observe as _diagnostic_observe
@_diagnostic_observe("provider")
def send(args):
    if args.blocked:
        return 3
    from .observability_producers import emit as diagnostic_emit
    diagnostic_emit(settings, 'provider', 'start', count=len(args.rows))
    return existing_send(args)
"""
        self.assertTrue(adopter.business_equal(before, after))
        self.assertFalse(adopter.business_equal(before, after.replace("return 3", "return 0")))
        self.assertFalse(
            adopter.business_equal(before, after.replace("len(args.rows)", "new_customer_send()"))
        )

    def test_cleanup_observer_keeps_original_body_and_reraise(self):
        before = "def cleanup(settings):\n    retire_exact_mirror(settings)\n"
        after = "def cleanup(settings):\n    try:\n        retire_exact_mirror(settings)\n    except BaseException as exc:\n        diagnostic_emit(settings, 'cleanup', 'failed', **error_metadata(exc))\n        raise\n"
        self.assertTrue(adopter.business_equal(before, after))
        self.assertFalse(
            adopter.business_equal(
                before, after.replace("retire_exact_mirror", "retire_every_mirror")
            )
        )
        self.assertFalse(
            adopter.business_equal(before, after.replace("        raise\n", "        return 0\n"))
        )

    def test_output_inside_source_is_refused_before_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline = Path(temp) / "baseline"
            reviewed = Path(temp) / "reviewed"
            baseline.mkdir()
            reviewed.mkdir()
            with self.assertRaises(ValueError):
                adopter.prepare_package(baseline, baseline / "new", Path(temp), reviewed, baseline)
            self.assertFalse((baseline / "new").exists())

    def test_exact_patch_rejects_unknown_old_context(self):
        self.assertEqual(adopter.exact_patch("old\n", "old\n", "new\n"), "new\n")
        with self.assertRaises(ValueError):
            adopter.exact_patch("unexpected\n", "old\n", "new\n")

    def test_rpc_class_replacement_preserves_cafe_chat_body(self):
        before = """import sys
class EngineClient:
    def __init__(self, config):
        self.config = config
    async def __aenter__(self):
        return self
    async def call(self, method):
        return method
    async def unchanged(self):
        return 1
async def chat():
    return "cafe-specific-standing-authority"
"""
        current = before.replace(
            "self.config = config", "self.config = config\n        self.observer = False"
        )
        actual = adopter.rpc_class(before, current)
        self.assertIn('return "cafe-specific-standing-authority"', actual)
        self.assertIn("import time", actual)
        self.assertEqual(
            ast.dump(adopter.definition(before, "chat")),
            ast.dump(adopter.definition(actual, "chat")),
        )
        with self.assertRaises(ValueError):
            adopter.rpc_class(before, current.replace("return 1", "return 2"))
        with self.assertRaises(ValueError):
            adopter.rpc_class(
                before.replace("self.config = config", "self.config = changed(config)"),
                current,
                before,
            )

    def test_new_smtp_helper_keeps_original_prefix(self):
        original = "def send(settings):\n    return original_send(settings)\n"
        reviewed = (
            original
            + "\ndef send_operational_notice(settings, ref, kind, count):\n    return ref\n"
        )
        candidate = adopter.add_notice_helper(original, reviewed)
        self.assertTrue(candidate.startswith(original))
        self.assertEqual(
            ast.dump(adopter.definition(candidate, "send")),
            ast.dump(adopter.definition(original, "send")),
        )
        with self.assertRaises(ValueError):
            adopter.add_notice_helper(
                original, reviewed + "\ndef unrelated_replacement():\n    return 1\n"
            )
