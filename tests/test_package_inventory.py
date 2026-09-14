"""Compare installed template paths and bytes with source, including extra files.

Run with the freshly installed environment's ``python -I`` so an ambient
PYTHONPATH or source checkout cannot substitute for the installed package.
This gate detects stale build output; it never cleans or repairs that output.
"""
from pathlib import Path
import sys
import tempfile
import unittest


def inventory(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*.j2") if path.is_file()}


def differences(source: Path, installed: Path) -> list[str]:
    expected, actual = inventory(source), inventory(installed)
    failures = []
    if not expected:
        failures.append("source template inventory is empty")
    failures.extend(f"extra installed template: {name}" for name in sorted(actual.keys() - expected.keys()))
    failures.extend(f"missing installed template: {name}" for name in sorted(expected.keys() - actual.keys()))
    failures.extend(f"different installed template: {name}"
                    for name in sorted(expected.keys() & actual.keys())
                    if expected[name] != actual[name])
    return failures


class InventoryTests(unittest.TestCase):
    def test_exact_and_broken_installed_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, installed = Path(tmp) / "source", Path(tmp) / "installed"
            source.mkdir()
            installed.mkdir()
            (source / "current.j2").write_bytes(b"current\n")
            (installed / "current.j2").write_bytes(b"current\n")
            self.assertEqual(differences(source, installed), [])
            # A removed nested template surviving a build must fail even when
            # all currently expected files are present and byte-identical.
            orphan = installed / "retired" / "orphan.j2"
            orphan.parent.mkdir()
            orphan.write_bytes(b"stale\n")
            self.assertEqual(differences(source, installed),
                             ["extra installed template: retired/orphan.j2"])
            (source / "missing.j2").write_bytes(b"required\n")
            (installed / "current.j2").write_bytes(b"different\n")
            self.assertEqual(differences(source, installed), [
                "extra installed template: retired/orphan.j2",
                "missing installed template: missing.j2",
                "different installed template: current.j2",
            ])


def main() -> int:
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(InventoryTests))
    if not result.wasSuccessful():
        return 1
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        return 0
    if len(sys.argv) != 2:
        print("usage: python -I tests/test_package_inventory.py SOURCE_ROOT", file=sys.stderr)
        return 2
    source_root = Path(sys.argv[1]).resolve()
    import cs
    installed_package = Path(cs.__file__).resolve().parent
    if not sys.flags.isolated or not installed_package.is_relative_to(Path(sys.prefix).resolve()):
        print("FAIL: inventory check requires an isolated installed-package interpreter")
        return 1
    if installed_package == source_root / "cs":
        print("FAIL: source package substituted for installed package")
        return 1
    failures = differences(source_root / "cs/templates", installed_package / "templates")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"OK: {len(inventory(installed_package / 'templates'))} installed templates match source paths and bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
