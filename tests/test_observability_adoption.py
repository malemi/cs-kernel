"""Adoption rejects business drift and unsafe source/pin selection."""

import importlib.util
from pathlib import Path
import tempfile
import sys
import unittest

SPEC = importlib.util.spec_from_file_location(
    "adopt_engine", Path(__file__).resolve().parents[1] / "scripts/observability/adopt_engine.py"
)
adopt = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(Path(SPEC.origin).parent))
try:
    SPEC.loader.exec_module(adopt)
finally:
    sys.path.pop(0)


class AdoptionTests(unittest.TestCase):
    def test_observations_preserve_business_body_and_reject_changed_effect(self):
        old = "async def send(value):\n    return await transport(value)\n"
        candidate = 'from zylch.observability_producers import observed, observe\n@observed("provider", "send")\nasync def send(value):\n    observe("provider", "start")\n    return await transport(value)\n'
        self.assertTrue(adopt.business_equal(old, candidate))
        self.assertFalse(
            adopt.business_equal(
                old, candidate.replace("transport(value)", "transport('different recipient')")
            )
        )

    def test_legacy_setup_does_not_adopt_new_sync_algorithm(self):
        old = 'import logging\nasync def sync_run(params, notify):\n    try:\n        return await old_pipeline(params)\n    except Exception as e:\n        logger.error("failed")\n        raise\n'
        new = adopt.peer_setup(old)
        self.assertTrue(adopt.business_equal(old, new))
        self.assertIn("old_pipeline(params)", new)
        self.assertNotIn("email_only", new)

    def test_capability_supports_inline_and_multiline_dict_without_other_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "rpc").mkdir()
            (root / "rpc/methods.py").write_text(
                "from zylch.rpc.diagnostics import METHODS as _DIAGNOSTIC_METHODS\nfor _name, _fn in _DIAGNOSTIC_METHODS.items():\n    METHODS[_name] = _fn\n"
            )
            for old in (
                'async def system_capabilities(p, n):\n    return {"existing": 1}\n',
                'async def system_capabilities(p, n):\n    return {\n        "existing": 1,\n    }\n',
            ):
                new = adopt.instrument_methods(old, root)
                self.assertTrue(adopt.business_equal(old, new))
                compile(new, "candidate", "exec")

    def test_log_retention_replacement_needs_exact_reviewed_function(self):
        old = "def _setup_log_file():\n    original_logging()\n"
        new = "def _setup_log_file():\n    unexpected_business_effect()\n"
        self.assertFalse(adopt.business_equal(old, new))
        approved = "def _setup_log_file():\n    bounded_logging()\n"
        self.assertFalse(adopt.business_equal(old, new, approved_logging=approved))
        self.assertTrue(adopt.business_equal(old, approved, approved_logging=approved))

    def test_exact_pin_replacement_preserves_other_directives_and_refuses_drift(self):
        old = b"[Service]\nEnvironment=UNCHANGED=yes\nEnvironment=PYTHONPATH=/old:/deps\nRestart=on-failure\n"
        new = adopt.render_pin(old, "/old:/deps", "/new:/old:/deps")
        self.assertEqual(new.replace(b"/new:/old:/deps", b"/old:/deps"), old)
        quoted = b'[Service]\nEnvironment="PYTHONPATH=/old:/deps"\n'
        self.assertEqual(
            adopt.render_pin(quoted, "/old:/deps", "/new:/old:/deps"),
            b'[Service]\nEnvironment="PYTHONPATH=/new:/old:/deps"\n',
        )
        with self.assertRaises(ValueError):
            adopt.render_pin(old, "/unexpected", "/new")

    def test_runtime_package_rejects_symlinks_and_records_mode_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = root / "source.py"
            p.write_text("pass\n")
            p.chmod(0o640)
            first = adopt.manifest(root)
            p.chmod(0o600)
            self.assertNotEqual(first, adopt.manifest(root))
            (root / "other.py").symlink_to(p)
            with self.assertRaises(ValueError):
                adopt.manifest(root)
