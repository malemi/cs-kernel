"""cs login — the human-run verb that turns a desktop sign-in into a usable
session for THIS clone.

The desktop app (mrcall-desktop) owns the interactive Firebase sign-in. At
sign-in it writes a JSON descriptor to
``~/.zylch/profiles/<uid>/cs-descriptor.json`` (root overridable via
``$CS_ZYLCH_ROOT`` — sandboxed tests point this at a temp tree). `cs login`:

  1. finds that descriptor (scanning the profile root, or via
     ``--descriptor PATH`` directly),
  2. lets the operator confirm (or pick, if more than one profile is
     present),
  3. refuses if the descriptor's identity does not match what THIS clone is
     already stamped for (a clone must never silently switch to another
     company's profile — see `_identity_conflict`),
  4. stores the refresh token at ``settings.refresh_token_path`` (mode
     0600, via `cs.auth._write_refresh` — the same file every subsequent
     `cs.auth.get_id_token` call reads),
  5. proves the stored session with one live ``account.who_am_i`` call.

What it deliberately does NOT do: it never writes or edits ``.env`` or
``manifest.toml`` — those are operator-owned files. When the descriptor
disagrees with what this clone has configured (the Firebase web API key,
the engine WS URL), `cs login` only PRINTS the line/field to fix by hand.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import auth
from . import config
from . import manifest as manifest_mod
from .config import Settings

DESCRIPTOR_FILENAME = "cs-descriptor.json"
REQUIRED_STRING_FIELDS = (
    "email",
    "uid",
    "engine_ws_url",
    "firebase_web_api_key",
    "refresh_token",
)


def descriptor_root() -> Path:
    """Where the desktop app writes profile descriptors.

    ``$CS_ZYLCH_ROOT`` overrides it (sandboxed tests point this at a temp
    tree); otherwise it is the app's own default, ``~/.zylch``.
    """
    override = os.environ.get("CS_ZYLCH_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".zylch"


def scan_descriptors(root: Path) -> list[Path]:
    """Every ``cs-descriptor.json`` under ``<root>/profiles/*/``, sorted for
    a stable pick-by-number order. A missing ``profiles/`` dir is zero
    results, not an error — nobody has signed in from this machine yet."""
    profiles = Path(root) / "profiles"
    if not profiles.is_dir():
        return []
    return sorted(profiles.glob(f"*/{DESCRIPTOR_FILENAME}"))


def parse_descriptor(path: Path | str) -> dict:
    """Parse and validate one profile descriptor JSON file.

    Pure — never prints. Raises `ValueError` with a one-line reason on any
    problem: an unreadable file, invalid JSON, a JSON value that is not an
    object, an unsupported ``version``, or a missing/empty required field
    (`email`, `uid`, `engine_ws_url`, `firebase_web_api_key`,
    `refresh_token`).
    """
    p = Path(path)
    try:
        raw = p.read_text()
    except OSError as e:
        raise ValueError(f"cannot read {p}: {e}") from None
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise ValueError(f"{p} is not valid JSON: {e}") from None
    if not isinstance(data, dict):
        raise ValueError(f"{p} is not a JSON object")
    version = data.get("version")
    if version != 1:
        raise ValueError(
            f"{p} has unsupported descriptor version {version!r} (expected 1)"
        )
    for field in REQUIRED_STRING_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{p} is missing required field {field!r}")
    return data


def descriptor_ws_base(descriptor: dict) -> str:
    """The descriptor's `engine_ws_url` is the FULL per-uid socket URL
    (`<base>/ws/<uid>` — what the desktop app's own transport dials).
    `Settings.engine_ws_url` / manifest `[engine].ws_url` is the BASE:
    `cs/rpc.py::EngineClient.url` appends `/ws/<uid>` itself. Strip the
    suffix so the two are comparable — and so `cs init` never stamps a
    base that already carries it (that yields `/ws/<uid>/ws/<uid>`, which
    the engine's Caddy rule `^/ws/([^/]+)$` will not route)."""
    url = descriptor["engine_ws_url"].rstrip("/")
    suffix = f"/ws/{descriptor['uid']}"
    return url[: -len(suffix)] if url.endswith(suffix) else url


def _identity_conflict(settings: Settings, descriptor: dict) -> str | None:
    """Return a one-line refusal reason if THIS clone's configured identity
    conflicts with the descriptor's, or None when it is safe to store the
    session.

    Pure — never prints, never touches the filesystem — so a test can call
    it directly with a hand-built Settings and descriptor dict. The
    invariant being protected: a clone must never silently switch to
    another company's profile.
    """
    configured_uid = (settings.engine_owner_uid or "").strip()
    if not configured_uid:
        return (
            "this clone has no engine identity yet — run `cs init` first "
            "(it can prefill from the descriptor)"
        )
    descriptor_uid = descriptor["uid"]
    if configured_uid != descriptor_uid:
        return (
            "this clone is stamped for a different profile (configured "
            f"engine_owner_uid={configured_uid!r}, descriptor uid="
            f"{descriptor_uid!r}) — fix manifest.toml [engine].owner_uid "
            "deliberately, or pick the matching descriptor"
        )
    configured_email = (settings.email_address or "").strip()
    descriptor_email = descriptor["email"].strip()
    if configured_email and configured_email.lower() != descriptor_email.lower():
        return (
            "this clone is stamped for a different profile (configured "
            f"email_address={configured_email!r}, descriptor email="
            f"{descriptor_email!r}) — fix manifest.toml [operator].email_address "
            "deliberately, or pick the matching descriptor"
        )
    return None


def _prompt_yes_no(prompt: str, default: bool) -> bool:
    """Mirrors `project_init.prompt_yes_no`'s loop-until-valid style. Lets
    EOFError/KeyboardInterrupt propagate — the caller handles both exactly
    like `cs init` does."""
    while True:
        value = input(prompt).strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("Please enter y/yes or n/no.")


def _prompt_choice(n: int) -> int:
    """Pick one of `n` numbered profiles. Lets EOFError/KeyboardInterrupt
    propagate, same as `_prompt_yes_no`."""
    while True:
        raw = input(f"Pick a profile [1-{n}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= n:
            return int(raw)
        print(f"Please enter a number between 1 and {n}.")


def cmd_login(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cs login",
        description="Sign in this clone: read the mrcall-desktop app's "
        "profile descriptor, store the refresh-token session, and prove it "
        "with one account.who_am_i call.",
    )
    parser.add_argument(
        "--descriptor",
        metavar="PATH",
        help="use this cs-descriptor.json directly, skipping the ~/.zylch profile scan",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 1)

    # `login` runs from a clone root and needs Settings for its identity
    # cross-checks. A ManifestError is already handled loudly elsewhere in
    # cli.main for every other verb (`print(f"manifest error: {e}")`,
    # exit 2) — `login` dispatches before that catch ever runs, so it needs
    # its own, but the wording must not diverge.
    try:
        settings = config.load()
    except manifest_mod.ManifestError as e:
        print(f"manifest error: {e}", file=sys.stderr)
        return 2

    root = descriptor_root()
    if args.descriptor:
        raw_candidates = [Path(args.descriptor).expanduser()]
    else:
        raw_candidates = scan_descriptors(root)

    found: list[tuple[Path, dict]] = []
    for path in raw_candidates:
        try:
            found.append((path, parse_descriptor(path)))
        except ValueError as e:
            print(f"cs login: skipping {path}: {e}", file=sys.stderr)

    if not found:
        if args.descriptor:
            print(
                f"cs login: {args.descriptor} is not a usable descriptor "
                "(see the reason above)",
                file=sys.stderr,
            )
        else:
            print(
                f"cs login: no profile descriptor found under {root}/profiles/ — "
                "sign in to the mrcall-desktop app first (it writes the "
                "descriptor at sign-in)",
                file=sys.stderr,
            )
        return 1

    try:
        if len(found) == 1:
            _, descriptor = found[0]
            print(f"{descriptor['email']} ({descriptor['uid']})")
            if not _prompt_yes_no("Proceed? [Y/n] ", default=True):
                print("cs login: cancelled")
                return 1
        else:
            print("Multiple profiles found:")
            for i, (_, d) in enumerate(found, 1):
                print(
                    f"  {i}. {d['email']}  ({d['uid']})  "
                    f"written_at={d.get('written_at', '?')}"
                )
            choice = _prompt_choice(len(found))
            _, descriptor = found[choice - 1]
    except EOFError:
        print(
            "cs login: input ended before a profile was chosen — run it in "
            "an interactive terminal and answer the prompt",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\ncs login: cancelled", file=sys.stderr)
        return 130

    conflict = _identity_conflict(settings, descriptor)
    if conflict:
        print(f"cs login: {conflict}", file=sys.stderr)
        return 1

    auth._write_refresh(settings, descriptor["refresh_token"])

    # Config-drift advisories — print, never mutate: .env and manifest.toml
    # are operator-owned files, not something a sign-in verb rewrites.
    if settings.firebase_web_api_key != descriptor["firebase_web_api_key"]:
        print(
            "note: this clone's FIREBASE_WEB_API_KEY is missing or does not "
            "match the descriptor — add this line to .env:\n"
            f"  FIREBASE_WEB_API_KEY={descriptor['firebase_web_api_key']}"
        )
    if settings.engine_ws_url.rstrip("/") != descriptor_ws_base(descriptor):
        print(
            f"note: configured engine_ws_url ({settings.engine_ws_url!r}) "
            f"differs from the descriptor's ({descriptor_ws_base(descriptor)!r}) "
            "— fix manifest.toml [engine].ws_url if this is stale"
        )

    from . import rpc  # lazy: keeps `import cs.login` light

    try:
        result = rpc.call_sync(settings, "account.who_am_i")
    except KeyboardInterrupt:
        raise
    except Exception as e:  # noqa: BLE001 — the proof call has many transports
        # The session IS stored; only the proof failed. The commonest cause is
        # the expected one: the vendor engine has no daemon for this profile
        # yet, so the WS upgrade is refused. That must read as one line, not a
        # traceback — it is the first thing a new customer sees.
        print(
            f"cs login: stored the session, but the proof call to "
            f"{settings.engine_ws_url!r} failed: {type(e).__name__}: {e}\n"
            "  If this profile has not been provisioned on the engine yet, "
            "that is expected — the stored session is still valid.",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"signed in: {descriptor['email']} ({descriptor['uid']})")
    return 0


if __name__ == "__main__":
    sys.exit(cmd_login())
