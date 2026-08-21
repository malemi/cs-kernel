"""Gate: `cs init`'s post-stamp install offer — `offer_project_install`.

Before this, README step 3 was a hand-typed `cd/uv venv/source/uv pip
install` the wizard could easily do itself once the operator says yes.
Hermetic (no real venv, no network): `subprocess.run` is stubbed so the
gate proves the CALL SHAPE (uv venv, then uv pip install --python
<venv>/bin/python -r requirements.txt, both with cwd=dest_dir), not a
real install. Guards:

1. EOF on the prompt (closed stdin — the v0.5.2 EOF contract) skips the
   install, prints the manual fallback, and calls subprocess.run ZERO
   times.
2. An explicit "n" does the same — no accidental install on the default.
3. "y" runs exactly two subprocess calls in order (venv, then install)
   with the right args and cwd; a venv failure stops before the second
   call.
"""
from __future__ import annotations

import builtins
import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cs import project_init as pi  # noqa: E402


def with_answer(answer):
    def fake(prompt=""):
        if isinstance(answer, BaseException):
            raise answer
        return answer
    return fake


@contextlib.contextmanager
def _stubbed(answer, returncodes=(0, 0)):
    calls = []

    class FakeCompleted:
        def __init__(self, rc):
            self.returncode = rc

    rcs = iter(returncodes)

    def fake_run(cmd, cwd=None, **kw):
        calls.append((cmd, cwd))
        return FakeCompleted(next(rcs, 0))

    old_input, old_run = builtins.input, pi.subprocess.run
    builtins.input = with_answer(answer)
    pi.subprocess.run = fake_run
    try:
        yield calls
    finally:
        builtins.input = old_input
        pi.subprocess.run = old_run


def _eof_and_no_skip_with_no_calls() -> None:
    dest = Path("/tmp/does-not-need-to-exist-acme-cs")
    for answer in (EOFError(), KeyboardInterrupt(), "n", "no", ""):
        with _stubbed(answer) as calls:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                pi.offer_project_install(dest)
            assert calls == [], f"answer {answer!r} must call subprocess.run 0 times, got {calls}"
            text = out.getvalue()
            assert "uv venv .venv" in text, f"manual fallback must be printed:\n{text}"
            assert "uv pip install -r requirements.txt" in text, text


def _yes_runs_venv_then_install_with_right_args() -> None:
    dest = Path("/tmp/does-not-need-to-exist-acme-cs")
    with _stubbed("y", returncodes=(0, 0)) as calls:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            pi.offer_project_install(dest)
    assert len(calls) == 2, f"expected exactly 2 subprocess calls, got {calls}"
    (venv_cmd, venv_cwd), (install_cmd, install_cwd) = calls
    assert venv_cmd == ["uv", "venv", ".venv"], venv_cmd
    assert venv_cwd == dest, venv_cwd
    assert install_cmd[:2] == ["uv", "pip"], install_cmd
    assert "install" in install_cmd and "-r" in install_cmd and "requirements.txt" in install_cmd, install_cmd
    assert "--python" in install_cmd, "must target the venv's own python, not the ambient one"
    py_idx = install_cmd.index("--python") + 1
    assert str(dest / ".venv") in install_cmd[py_idx], install_cmd[py_idx]
    assert install_cwd == dest, install_cwd
    assert "Installed." in out.getvalue()
    assert "cs login" in out.getvalue()


def _venv_failure_stops_before_install() -> None:
    dest = Path("/tmp/does-not-need-to-exist-acme-cs")
    with _stubbed("y", returncodes=(1,)) as calls:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            pi.offer_project_install(dest)
    assert len(calls) == 1, f"a failed venv must not attempt the install call, got {calls}"
    assert "uv venv FAILED" in out.getvalue()


def main() -> None:
    _eof_and_no_calls = _eof_and_no_skip_with_no_calls()
    _yes_runs_venv_then_install_with_right_args()
    _venv_failure_stops_before_install()
    print("test_init_install_offer: all assertions passed")


if __name__ == "__main__":
    main()
