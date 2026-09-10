"""cs login — the human-run verb that turns a desktop sign-in into a usable
session for THIS clone.

The desktop app (mrcall-desktop) owns the interactive Firebase sign-in. At
sign-in it writes a JSON descriptor to
``~/.zylch/profiles/<uid>/cs-descriptor.json`` (root overridable via
``$CS_ZYLCH_ROOT`` — sandboxed tests point this at a temp tree). `cs login`:

  1. finds that descriptor (scanning the profile root, or via
     ``--descriptor PATH`` directly),
  2. resolves WHICH one: when this clone already has a configured engine
     identity (``settings.engine_owner_uid`` — always true under
     ``--account``, and true for any stamped clone), it auto-selects the
     descriptor whose uid matches and never prompts, or fails immediately
     naming the uid when none matches. Only the genuinely ambiguous case —
     no configured uid at all, e.g. a brand-new clone before `cs init` has
     stamped one — falls back to letting the operator confirm (one
     descriptor) or numbered-pick (more than one). See the dedicated
     comment at the branch in `cmd_login` below for why: offering a menu
     that already contains only wrong answers, and refusing the pick
     afterwards, reads as a misconfiguration rather than as a menu the
     operator should never have been shown,
  3. refuses if the descriptor's identity does not match what THIS clone is
     already stamped for (a clone must never silently switch to another
     company's profile — see `_identity_conflict`),
  4. stores the refresh token at ``settings.refresh_token_path`` (mode
     0600, via `cs.auth._write_refresh` — the same file every subsequent
     `cs.auth.get_id_token` call reads). That path is derived per account
     uid (`cs/config.py::_derive_paths`), so signing in a secondary account
     (`cs --account <name> login`) never overwrites the primary's session,
  5. proves the stored session with one live ``account.who_am_i`` call.

What it deliberately does NOT do: it never writes or edits ``.env`` or
``manifest.toml`` — those are operator-owned files. When the descriptor
disagrees with what this clone has configured (the Firebase web API key,
the engine WS URL), `cs login` only PRINTS the line/field to fix by hand.

``--mint`` is the other way in: instead of reading a descriptor, it
synthesizes one from this clone's own Firebase service-account key
(`_cmd_login_mint`, `auth.mint_refresh_token`) for a uid already declared
in ``CS_ACCOUNTS``. It opens a session for a colleague's engine profile
that has never signed in to the desktop app interactively — the profiles
this kernel actually needs are provisioned headless and write no
descriptor at all — behind its own guard order (registry, then an
interactive-terminal check, then the resolved email, then an explicit
confirmation) before rejoining steps 3-5 above.
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
from .config import ConfigError, Settings

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


def _mint_check_registry(uid: str, settings: Settings) -> None:
    """Guard 1 of the mint path: `uid` must already be a value in
    `settings.account_map` (`CS_ACCOUNTS`). Raises `ConfigError` naming the
    uid and the registry; a no-op otherwise. Pure — no key, no network —
    so this is the guard `cmd_login`'s `--mint` branch runs BEFORE the tty
    check: kernel code cannot mint a session for a uid the operator has
    not written into this clone's own configuration, and that refusal is
    provable with no credential at all.
    """
    if uid not in settings.account_map.values():
        raise ConfigError(
            f"uid {uid!r} is not declared in this clone's CS_ACCOUNTS "
            "registry — add it there (CS_ACCOUNTS=name:uid) before minting "
            "a session for it"
        )


def _mint_resolve_email(uid: str, settings: Settings, resolve_email=None) -> str:
    """Guard 2 of the mint path: resolve `uid`'s email through
    `resolve_email`, an injectable seam (``None`` binds
    `resolve.resolve_email` lazily, so importing this module never pulls in
    `firebase_admin`). Raises `ConfigError` naming the uid when the
    resolver returns `None` — `cs/resolve.py::resolve_email` returns
    `None` both for "no Firebase user with this uid" and "a user with no
    email address", and the two are indistinguishable from here, so the
    message covers both causes.
    """
    if resolve_email is None:
        # Lazy for the same reason `mint_refresh_token`'s app is lazy in
        # cs/auth.py: cs/rpc.py imports this module for the `login` stub,
        # so every verb — `--help` included — would otherwise pay the
        # `firebase_admin` import cost.
        from . import resolve

        resolve_email = resolve.resolve_email

    try:
        email = resolve_email(uid, settings)
    except ConfigError:
        raise
    except Exception as e:  # noqa: BLE001 — the Admin SDK raises many types (missing/unreadable key file, transport)
        # `cs/resolve.py::resolve_email` catches only `UserNotFoundError`; a
        # missing key file surfaces as `FileNotFoundError`, a transport
        # failure as `FirebaseError`. Neither is a `ConfigError`, so without
        # this wrap they would traceback here while the very same key file
        # is reported in one handled line by `mint_refresh_token` one step
        # later. Same shape as that wrap, for the same reason.
        raise ConfigError(
            f"could not resolve the email for uid {uid!r}: {type(e).__name__}: {e} "
            "— check that this clone's Firebase service-account key "
            f"({settings.firebase_sa_path}) exists and is readable"
        ) from None
    if email is None:
        raise ConfigError(
            f"no Firebase user with an email for uid {uid!r} — cannot mint "
            "a session without a resolvable address"
        )
    return email


def _assemble_descriptor(
    uid: str, settings: Settings, email: str, refresh_token: str
) -> dict:
    """The same five `REQUIRED_STRING_FIELDS` `cmd_login` reads from a
    desktop-app-written descriptor, built from already-resolved pieces.
    Shared by `mint_descriptor` (the pure, prompt-free composition below)
    and `cmd_login`'s `--mint` branch, which resolves the email once — to
    echo it in the confirmation prompt — and must not resolve it again
    here."""
    return {
        "email": email,
        "uid": uid,
        "engine_ws_url": settings.engine_ws_url,
        "firebase_web_api_key": settings.firebase_web_api_key,
        "refresh_token": refresh_token,
    }


def mint_descriptor(
    uid: str,
    settings: Settings,
    *,
    resolve_email=None,
) -> dict:
    """Synthesize a descriptor for `uid` — the same five fields `cmd_login`
    reads from a desktop-app-written ``cs-descriptor.json``
    (`REQUIRED_STRING_FIELDS`) — from this clone's own Firebase
    service-account key instead. Lets a clone open a session for a
    colleague's engine profile that has never signed in to the desktop app
    interactively; the profiles this kernel actually needs are provisioned
    headless and write no descriptor at all.

    The pure, prompt-free composition of the mint path's three guards,
    each raising ONE handled `ConfigError`: `_mint_check_registry` ->
    `_mint_resolve_email` -> `auth.mint_refresh_token`. `cmd_login`'s
    `--mint` branch calls the first two individually instead, with the tty
    check and the interactive confirmation interleaved between them — this
    function stays the composed shape the unit tests exercise directly,
    with neither a terminal nor a live engine.
    """
    _mint_check_registry(uid, settings)
    email = _mint_resolve_email(uid, settings, resolve_email)
    refresh_token = auth.mint_refresh_token(settings, uid)
    return _assemble_descriptor(uid, settings, email, refresh_token)


def _identity_conflict(
    settings: Settings,
    descriptor: dict,
    *,
    account_switched: bool = False,
    account_name: str | None = None,
    minted: bool = False,
) -> str | None:
    """Return a one-line refusal reason if THIS clone's configured identity
    conflicts with the descriptor's, or None when it is safe to store the
    session.

    Pure — never prints, never touches the filesystem — so a test can call
    it directly with a hand-built Settings and descriptor dict. The
    invariant being protected: a clone must never silently switch to
    another company's profile.

    The uid checks (empty configured uid, uid mismatch) are ALWAYS active:
    uid equality with the `CS_ACCOUNTS` registry entry IS the identity
    statement for a secondary account, so `account_switched` never relaxes
    them. The email comparison binds the clone's operator mailbox to its
    PRIMARY profile only — it is skipped when `account_switched` is true,
    because `cs --account X login` is a deliberate registry selection whose
    descriptor mailbox is that secondary account's own, and legitimately
    differs from the operator mailbox.

    `account_name` is cosmetic: it only changes the WORDING of the email
    refusal, never the outcome. When `--account <name>` was given but did
    NOT switch the uid away from this clone's own default (the registry
    entry resolved to the same uid the clone is already configured for —
    the only way to reach the email check with `account_name` set, since an
    actual switch already returned None above), the usual "run `cs
    --account <name> login` instead" pointer would be actively wrong
    advice: `--account` WAS already used. The message names the real cause
    instead — the resolved uid IS the primary, so the primary-identity
    email check correctly applies, and a mismatch there points at a
    CS_ACCOUNTS/CS_ENGINE_OWNER_UID configuration error, not a missing flag.

    `minted` marks a descriptor `cmd_login`'s `--mint` branch synthesized
    rather than read from a file. The uid check can never fire for one —
    `_assemble_descriptor` builds `descriptor["uid"]` from the very same
    `settings.engine_owner_uid` this function reads as `configured_uid`, so
    that comparison is a self-comparison by construction — but the email
    check can, and its usual wording ("pick the matching descriptor", "run
    `cs --account <name> login` instead") names a file that does not exist
    and omits `--mint` entirely; `minted=True` swaps in wording that names
    the two real fixes instead.
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
    if account_switched:
        return None
    configured_email = (settings.email_address or "").strip()
    descriptor_email = descriptor["email"].strip()
    if configured_email and configured_email.lower() != descriptor_email.lower():
        if minted:
            return (
                "this clone is stamped for a different profile (configured "
                f"email_address={configured_email!r}, minted session email="
                f"{descriptor_email!r}) — fix manifest.toml "
                "[operator].email_address if it is stale, or this clone's "
                "CS_ACCOUNTS/CS_ENGINE_OWNER_UID registry pin if it points "
                "at the wrong uid; `--mint` synthesized this session and "
                "cannot resolve the mismatch on its own"
            )
        if account_name is None:
            pointer = (
                "; for a registered secondary account run `cs --account "
                "<name> login` instead"
            )
        else:
            pointer = (
                f" (--account {account_name!r} resolved to this clone's own "
                "default uid, so the primary-identity check applies — if it "
                "is meant to be a secondary account, its CS_ACCOUNTS uid or "
                "this clone's CS_ENGINE_OWNER_UID pin is wrong)"
            )
        return (
            "this clone is stamped for a different profile (configured "
            f"email_address={configured_email!r}, descriptor email="
            f"{descriptor_email!r}) — fix manifest.toml [operator].email_address "
            "deliberately, or pick the matching descriptor"
            f"{pointer}"
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


def _finish_login(
    settings: Settings,
    descriptor: dict,
    *,
    account_switched: bool,
    account_name: str | None,
    minted: bool = False,
) -> int:
    """The shared tail for both `cmd_login` entry points — a descriptor
    read from the mrcall-desktop app's file and `--mint`'s synthesized
    one: the identity cross-check, the refresh-token store, the
    config-drift advisories, and the `account.who_am_i` proof. `descriptor`
    carries the same five `REQUIRED_STRING_FIELDS` either way, so nothing
    from here on can tell which entry point produced it — except the
    refusal wording `_identity_conflict` picks when `minted` is set (a
    synthesized descriptor has no file to "pick" instead)."""
    conflict = _identity_conflict(
        settings,
        descriptor,
        account_switched=account_switched,
        account_name=account_name,
        minted=minted,
    )
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


def _cmd_login_mint(
    settings: Settings,
    *,
    account_switched: bool,
    account_name: str | None,
) -> int:
    """The `--mint` branch of `cmd_login`: synthesizes a descriptor instead
    of reading one from the mrcall-desktop app, then rejoins
    `_finish_login` — the same store/prove tail a descriptor-based login
    uses, so the two entry points are indistinguishable from there on.

    Guard order (load-bearing, do not reorder): registry -> tty -> email ->
    confirmation -> mint. Registry and tty are checked before any
    credential is spent, so both refuse provably with no key and no
    network; only email resolution and the mint itself touch Firebase, and
    only after a human has confirmed at an interactive terminal.

    Every `ConfigError` from the three credential-touching guards
    (registry, email, mint) is caught here and printed as one line — bare
    `cs login --mint` dispatches before `cli.main`'s own `ConfigError`
    handlers ever run, so an uncaught one would traceback on that spelling
    while `cs --account <name> login --mint` (routed through the argparse
    tree) prints cleanly; catching it here makes both spellings fail
    identically.
    """
    uid = (settings.engine_owner_uid or "").strip()
    try:
        _mint_check_registry(uid, settings)

        if not sys.stdin.isatty():
            print(
                "cs login: --mint needs a human at a terminal — run it in "
                "an interactive terminal, not from a script, a cron tick "
                "or an agent session",
                file=sys.stderr,
            )
            return 1

        email = _mint_resolve_email(uid, settings)

        if account_name:
            prompt = (
                f"Mint a session for account {account_name!r} (uid {uid!r}, "
                f"email {email!r})? [y/N] "
            )
        else:
            prompt = f"Mint a session for uid {uid!r} (email {email!r})? [y/N] "
        try:
            if not _prompt_yes_no(prompt, default=False):
                print("cs login: cancelled", file=sys.stderr)
                return 1
        except EOFError:
            print(
                "cs login: input ended before confirmation — run --mint in "
                "an interactive terminal and answer the prompt",
                file=sys.stderr,
            )
            return 1
        except KeyboardInterrupt:
            print("\ncs login: cancelled", file=sys.stderr)
            return 130

        refresh_token = auth.mint_refresh_token(settings, uid)
    except ConfigError as e:
        print(f"cs login: {e}", file=sys.stderr)
        return 1

    descriptor = _assemble_descriptor(uid, settings, email, refresh_token)
    return _finish_login(
        settings,
        descriptor,
        account_switched=account_switched,
        account_name=account_name,
        minted=True,
    )


def cmd_login(
    argv: list[str] | None = None,
    *,
    account_switched: bool = False,
    account_name: str | None = None,
) -> int:
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
    parser.add_argument(
        "--mint",
        action="store_true",
        help="mint a session for this account from this clone's own "
        "Firebase service-account key instead of reading a descriptor — "
        "needs a human at an interactive terminal to confirm",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 1)

    if args.mint and args.descriptor:
        print(
            "cs login: --mint and --descriptor are mutually exclusive",
            file=sys.stderr,
        )
        return 1

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

    if args.mint:
        # Before any descriptor scan: a machine this feature exists for —
        # a colleague's profile that has never signed in to the desktop
        # app — has no descriptor at all, so scanning first would refuse
        # with "no profile descriptor found" before the mint path ever ran.
        return _cmd_login_mint(
            settings, account_switched=account_switched, account_name=account_name
        )

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

    configured_uid = (settings.engine_owner_uid or "").strip()
    if configured_uid:
        # The uid is already known — always true under `--account`, and
        # true for any stamped clone — so there is exactly one CORRECT
        # answer among `found`, and every other entry is a trap: picking
        # one for a different uid used to be accepted here and only
        # refused AFTERWARDS by `_identity_conflict` below, with a message
        # ("fix manifest.toml [engine].owner_uid deliberately") that reads
        # like a misconfiguration rather than "you picked the wrong menu
        # item." On a machine with several signed-in profiles that menu is
        # a trap, not a convenience. Resolve deterministically instead:
        # auto-select the descriptor whose uid matches — printing which one,
        # never prompting — or fail immediately naming the uid when none
        # matches, instead of offering a list in which every option is
        # wrong. This only changes WHICH descriptor is offered; the
        # identity cross-check below still runs exactly as it always has,
        # unchanged, and is what actually decides whether the session gets
        # stored.
        matches = [(p, d) for p, d in found if d["uid"] == configured_uid]
        if not matches:
            if account_name:
                print(
                    f"cs login: no descriptor for uid {configured_uid} "
                    f"(account {account_name!r}) — sign in to the "
                    "mrcall-desktop app as that account",
                    file=sys.stderr,
                )
            else:
                print(
                    f"cs login: no descriptor for uid {configured_uid} — "
                    "sign in to the mrcall-desktop app as that account",
                    file=sys.stderr,
                )
            return 1
        _, descriptor = matches[0]
        print(f"selected: {descriptor['email']} ({descriptor['uid']})")
    else:
        # Genuinely ambiguous: no engine identity is configured yet (a
        # brand-new clone before `cs init` has stamped one) to resolve
        # the choice against, so the operator has to pick.
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
                "cs login: input ended before a profile was chosen — run it "
                "in an interactive terminal and answer the prompt",
                file=sys.stderr,
            )
            return 1
        except KeyboardInterrupt:
            print("\ncs login: cancelled", file=sys.stderr)
            return 130

    return _finish_login(
        settings, descriptor, account_switched=account_switched, account_name=account_name
    )


if __name__ == "__main__":
    sys.exit(cmd_login())
