"""Deployment initialization is checked with its real restricted Linux capabilities."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "observability"))
from deployment_init import INIT_SCRIPT


class InitializationTests(unittest.TestCase):
    def test_first_and_second_start_with_chown_capability_only(self):
        if subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode:
            self.skipTest("Local restricted-capability check requires existing noninteractive sudo")
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            base.chmod(0o755)
            state = base / "state"
            state.mkdir(mode=0o755)
            source = base / "configuration"
            source.mkdir(mode=0o755)
            for name in ("watchdog.json", "notify.json"):
                (source / name).write_text(json.dumps({"reference": name}))
                (source / name).chmod(0o644)
            try:
                for iteration in range(2):
                    result = subprocess.run(
                        [
                            "sudo",
                            "-n",
                            "setpriv",
                            "--bounding-set=-all,+chown",
                            "--inh-caps=+chown",
                            "--ambient-caps=+chown",
                            "/usr/bin/python3",
                            "-c",
                            "import os;os.environ.update(OPERATOR_INIT_STATE="
                            + repr(str(state))
                            + ",OPERATOR_INIT_SOURCE="
                            + repr(str(source))
                            + ");"
                            + INIT_SCRIPT,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(state.stat().st_uid, 10001)
                    self.assertEqual(state.stat().st_mode & 0o777, 0o700)
                    check = subprocess.run(
                        [
                            "sudo",
                            "-n",
                            "python3",
                            "-c",
                            "from pathlib import Path;import json;p=Path("
                            + repr(str(state))
                            + ")/'config';"
                            "print(json.dumps([(x.stat().st_uid,x.stat().st_mode&511) for x in p.iterdir()]))",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    self.assertEqual(json.loads(check.stdout), [[10001, 0o600], [10001, 0o600]])
            finally:
                # Remove only this test's private files, whose intended owner is UID10001.
                subprocess.run(["sudo", "-n", "rm", "-rf", "--", str(state)], check=True)
