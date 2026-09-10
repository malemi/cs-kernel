#!/usr/bin/env python3
"""Semantic guard for `cs/login.py::mint_descriptor` — the pure, prompt-free
composition the CLI surface (`cs login --mint`, `tests/test_login_mint.py`)
calls its two guards from individually, with the tty check and the
confirmation prompt interleaved between them. Both guards here are the two
refusals the guard order puts BEFORE any credential is spent, so both run
unconditionally, with no key and no network:

  (i)  a uid absent from `settings.account_map` (`CS_ACCOUNTS`) refuses,
       naming the uid and the registry — proven with a resolver stub that
       raises if it is ever called, so this is a positive guard that the
       registry check runs FIRST, not just an assertion on the message.
  (ii) a registered uid whose resolver returns None (no Firebase user, or
       a user with no email — `cs/resolve.py:26-32` returns None for
       both) refuses, naming the uid — proven with a mint stub that
       raises if it is ever called, so this proves the no-email refusal
       is reached before any mint attempt.

The mint itself (`auth.mint_refresh_token`, a real Google round trip) is
deliberately out of scope for a gate that must always run — collaudo on a
real clone proves it live.
"""
from __future__ import annotations

from cs import auth as auth_mod
from cs import login
from cs.config import ConfigError, Settings

REGISTERED_UID = "uid-registered-abc123"
UNLISTED_UID = "uid-not-in-registry-xyz"


def _settings(**overrides) -> Settings:
    fields = {"accounts": f"colleague:{REGISTERED_UID}"}
    fields.update(overrides)
    # _env_file=() disables the dotenv layer entirely — same reasoning as
    # tests/test_auth_boundary.py's _settings(): this must not depend on
    # (or be broken by) whatever happens to sit at the invoking process's
    # CWD.
    return Settings(_env_file=(), **fields)


def _test_registry_refusal() -> None:
    def _no_resolve(*_a, **_k):
        raise AssertionError(
            "the registry refusal must be reachable with no email "
            "resolution attempted at all"
        )

    settings = _settings()
    try:
        login.mint_descriptor(UNLISTED_UID, settings, resolve_email=_no_resolve)
        raise AssertionError(
            "expected a ConfigError for a uid absent from CS_ACCOUNTS"
        )
    except ConfigError as e:
        reason = str(e)
        assert UNLISTED_UID in reason, f"refusal must name the uid: {reason}"
        assert "CS_ACCOUNTS" in reason, f"refusal must name the registry: {reason}"

    print(
        "OK: mint_descriptor registry refusal — a uid absent from "
        "CS_ACCOUNTS refuses naming the uid and the registry, with no "
        "email resolution attempted (no key, no network)"
    )


def _test_no_email_refusal() -> None:
    def _no_email(_uid, _settings):
        return None

    def _no_mint(*_a, **_k):
        raise AssertionError(
            "the no-email refusal must be reached before any mint is attempted"
        )

    settings = _settings()
    orig_mint = auth_mod.mint_refresh_token
    auth_mod.mint_refresh_token = _no_mint
    try:
        try:
            login.mint_descriptor(
                REGISTERED_UID, settings, resolve_email=_no_email
            )
            raise AssertionError(
                "expected a ConfigError when the resolver returns None"
            )
        except ConfigError as e:
            reason = str(e)
            assert REGISTERED_UID in reason, f"refusal must name the uid: {reason}"
    finally:
        auth_mod.mint_refresh_token = orig_mint

    print(
        "OK: mint_descriptor no-email refusal — a registered uid whose "
        "resolver returns None refuses naming the uid, with no mint "
        "attempted (no key, no network)"
    )


def _test_resolver_error_is_handled() -> None:
    """The resolver reaches the Firebase Admin SDK, which raises many types
    that are NOT `ConfigError`: a missing service-account key file surfaces
    as `FileNotFoundError`, a transport failure as `FirebaseError`. Left
    unwrapped they traceback out of the mint path while the very same key
    file is reported in one handled line by `mint_refresh_token` one step
    later. `_mint_resolve_email` must turn any such exception into one
    `ConfigError` naming the uid. Proven with an injected resolver that
    raises — no key, no network.
    """
    def _raises(_uid, _settings):
        raise FileNotFoundError(2, "No such file or directory", "/nonexistent/key.json")

    settings = _settings()
    try:
        login._mint_resolve_email(
            REGISTERED_UID, settings, resolve_email=_raises
        )
        raise AssertionError(
            "expected a ConfigError when the resolver raises a non-ConfigError"
        )
    except ConfigError as e:
        reason = str(e)
        assert REGISTERED_UID in reason, f"refusal must name the uid: {reason}"
    except FileNotFoundError:
        raise AssertionError(
            "the resolver's FileNotFoundError leaked unwrapped — it would "
            "traceback out of the mint path instead of one handled line"
        )

    print(
        "OK: mint_descriptor resolver-error wrap — a non-ConfigError from "
        "the resolver (missing key, transport) becomes one handled "
        "ConfigError naming the uid, never a leaked traceback (no key, "
        "no network)"
    )


def main() -> int:
    _test_registry_refusal()
    _test_no_email_refusal()
    _test_resolver_error_is_handled()
    print("test_mint_descriptor: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
