"""The kernel's own installed-package version — ONE source, reused by every
place that prints or compares it: the root parser's `cs --version`, the
`cs init --version` / `cs update --version` stubs, and `cs update --check`'s
installed-vs-latest comparison (`cs/project_update.py`). Before this module
existed, `cs/project_init.py` and `cs/project_update.py` each carried their
own copy of the same `importlib.metadata` try/except; a third copy for the
root parser would have made it three. Reading it live off the installed
distribution (rather than a string baked at release time) means the number
printed always matches what `pip show cs-kernel` reports, in a clean venv
or a developer's editable install alike.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

DIST_NAME = "cs-kernel"


def kernel_version_bare() -> str:
    """Just the installed version string (e.g. "0.6.1"), or "" when the
    package metadata is not installed (a source checkout with no `pip
    install -e .` yet) — the shape `cs update --check` needs to compare
    against a git tag."""
    try:
        return _pkg_version(DIST_NAME)
    except PackageNotFoundError:
        return ""


def kernel_version() -> str:
    """"cs-kernel X.Y.Z" for `argparse`'s `action="version"` — the exact
    string `cs init --version` / `cs update --version` have always printed;
    an explicit "(version unknown …)" fallback replaces a bare KeyError
    when the metadata is missing, so the message stays one readable line
    either way."""
    bare = kernel_version_bare()
    if bare:
        return f"{DIST_NAME} {bare}"
    return f"{DIST_NAME} (version unknown — package not installed)"
