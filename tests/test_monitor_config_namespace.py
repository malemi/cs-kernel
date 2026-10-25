"""Monitor configuration binds legacy retention to the actual selected UID namespace."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from pydantic import ValidationError

from cs.monitor import _read_component
from cs.monitor_config import Component, MonitorConfig
from cs.observability import owner_root, store_for


class NamespaceConfigurationTests(unittest.TestCase):
    def config(self, base, owner, root):
        return MonitorConfig(
            monitor_id="a" * 32,
            owner_uid=owner,
            state_dir=str(base / "monitor"),
            expected_start_utc=1,
            components=[
                Component(
                    id="kernel",
                    kind="kernel",
                    local_root=str(root),
                    legacy_state_dir=str(base / "clone"),
                )
            ],
        )

    def test_binding_uses_config_owner_not_component_without_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            state = base / "clone"
            selected = owner_root(state, "owner-a")
            config = self.config(base, "owner-a", selected)
            self.assertEqual(config.components[0].local_root, str(selected))
            self.assertFalse(state.exists())
            for invalid in (state / "observability", owner_root(state, "owner-b")):
                with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                    self.config(base, "owner-a", invalid)
            with self.assertRaises(ValidationError):
                self.config(base, "owner-b", selected)

    def test_sources_selected_from_same_clone_are_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            state = base / "clone"
            stores = {
                owner: store_for(SimpleNamespace(state_dir=state, engine_owner_uid=owner))
                for owner in ("owner-a", "owner-b")
            }
            for owner, store in stores.items():
                store.emit("rpc", "failed", reason="permission")
                config = self.config(base, owner, store.root)
                self.assertEqual(config.owner_uid, owner)
                observed = _read_component(config.components[0], owner, None)
                self.assertEqual({event["owner_uid"] for event in observed["events"]}, {owner})
                self.assertEqual(observed["coverage"]["gaps"], [])
            for owner, store in stores.items():
                page = store.events()
                self.assertEqual(page["coverage"]["gaps"], [])
                self.assertEqual({event["owner_uid"] for event in page["events"]}, {owner})

    def test_example_placeholder_namespace_is_consistent(self):
        payload = json.loads(Path("scripts/observability/monitor.example.json").read_text())
        config = MonitorConfig.model_validate(payload)
        kernel = next(component for component in config.components if component.kind == "kernel")
        self.assertEqual(
            Path(kernel.local_root), owner_root(kernel.legacy_state_dir, config.owner_uid)
        )


if __name__ == "__main__":
    unittest.main()
