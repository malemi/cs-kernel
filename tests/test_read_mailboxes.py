#!/usr/bin/env python3
"""The declared read-only mailboxes: loud config, masked secret, no send path.

A company answers customers from several mailboxes, and the people who own them
contribute nothing — no engine profile, no daemon, no maintenance, ever. That
constraint is the spec, so those mailboxes are declared by ADDRESS in
`manifest.toml [operator].read_mailboxes` and opened with an ordinary IMAP
password kept in the clone's own env file (`CS_READ_MAILBOX_PASSWORDS`), in no
repo.

The credential is real and it can also send. Read-only is a property of the
calling code, not of the password, so the properties that contain it are
gated here rather than asserted in a comment:

  1. EVERY malformed declaration fails at CONFIG LOAD, loudly, as ONE actionable
     line with no traceback — a foreign mail domain, a mangled address, a
     credential entry with no colon, an empty password, a credential for a
     mailbox nobody declared, the same mailbox declared twice, and the
     operator's OWN mailbox (already read first-class; declaring it again gives
     the identity mailbox a second credential and makes it count twice in the
     scope line). This is the anti-lesson of the parser that killed the first
     version of this idea: it dropped a malformed pair silently, and a dropped
     credential renders a mailbox as an absence — "nobody here ever wrote to
     them" — which is the one wrong answer this whole surface exists to prevent.
  2. A password containing the list separator is REFUSED, never truncated to a
     wrong password.
 2b. The env form of the declaration (`CS_READ_MAILBOXES`) is READ, layers over
     the manifest and reports its own provenance — a key that exists in the
     field and would otherwise have been ignored in silence. Given the
     `address:password` shape by mistake, it refuses with the password withheld
     and both key names in the message.
  3. A declared mailbox with NO credential does NOT fail load. It is not a
     configuration error; it is an `unreadable` mailbox, and gate 44 holds what
     the fan-out then reports.
  4. `cs config` — the verb an operator runs the moment a mailbox comes back
     unreadable, and whose output is pasted into chats — prints the KEY and its
     presence, never a password, in the report, in `--json` and under `--all`.
     The declared addresses themselves are not secret and ARE printed, with the
     manifest table and key that declares them.
  5. The read credential never reaches the send path: `send_mail.send` logs in
     with the operator mailbox's own pair and nothing else, and its module does
     not so much as name the setting.

Sections 1-4 run against a REAL `python -m cs config` subprocess with a sandbox
HOME and a trial manifest — the same harness `tests/test_config_report.py` uses,
and the only way to prove the failure is loud at LOAD rather than at first use.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cs import config as config_mod
from cs import send_mail
from cs.config import Settings

MANIFEST = """\
[company]
name = "Acme"
display_name = "Acme"
from_name = "Acme Ops"
slug = "acme"
prog_name = "acme-cs"

[operator]
email_address = "ops@acme.example"
read_mailboxes = [{read_mailboxes}]

[engine]
owner_uid = "uid-ops-acme"
ws_url = "wss://engine.example"

[crm]
adapter = "none"

[producer]
adapter = "none"
"""

OPERATOR_PW = "operator-app-password-never-print"
READ_PW = "colleague-app-password-never-print"
COLLEAGUE = "colleague@acme.example"
OTHER = "second@acme.example"


def _clean_env(home: Path) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_", "READ_"))
        and k not in ("SLUG", "TIMEZONE", "ACCOUNTS", "TOKEN_CACHE_PATH",
                      "REFRESH_TOKEN_PATH")
    }
    env["HOME"] = str(home)
    return env


def _sandbox(td: str, declared: list[str], env_lines: str) -> tuple[Path, dict]:
    """A clone root plus its state dir, exactly as a stamped clone has them: the
    addresses in manifest.toml (tracked), the credentials in ~/.acme-cs/.env
    (never in any repo)."""
    home, repo = Path(td, "home"), Path(td, "repo")
    state = home / ".acme-cs"
    for p in (home, repo, state):
        p.mkdir(parents=True, exist_ok=True)
    (repo / "manifest.toml").write_text(
        MANIFEST.format(read_mailboxes=", ".join(f'"{a}"' for a in declared))
    )
    (state / ".env").write_text(f"EMAIL_PASSWORD={OPERATOR_PW}\n{env_lines}")
    return repo, _clean_env(home)


def _config(repo: Path, env: dict, *argv: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "cs", "config", *argv],
        cwd=repo, env=env, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ------------------------------------------------- 1, 2. loud at config load


def _test_malformed_declarations_fail_loud() -> None:
    cases = [
        (
            "a mailbox on somebody else's mail domain",
            ["colleague@other-company.example"],
            "",
            ("own mail domain", "acme.example"),
        ),
        (
            "an entry that is not an address at all",
            ["colleague-at-acme"],
            "",
            ("read_mailboxes", "entry 1"),
        ),
        (
            "a credential entry with no colon",
            [COLLEAGUE],
            f"CS_READ_MAILBOX_PASSWORDS={COLLEAGUE}{READ_PW}\n",
            ("CS_READ_MAILBOX_PASSWORDS", "no ':'"),
        ),
        (
            "a credential entry with an empty password",
            [COLLEAGUE],
            f"CS_READ_MAILBOX_PASSWORDS={COLLEAGUE}:\n",
            ("empty password", COLLEAGUE),
        ),
        (
            "a credential for a mailbox nobody declared",
            [COLLEAGUE],
            f"CS_READ_MAILBOX_PASSWORDS=stranger@acme.example:{READ_PW}\n",
            ("read_mailboxes does not declare", "stranger@acme.example"),
        ),
        (
            "the same mailbox given two credentials",
            [COLLEAGUE],
            f"CS_READ_MAILBOX_PASSWORDS={COLLEAGUE}:{READ_PW},{COLLEAGUE}:other\n",
            ("twice", COLLEAGUE),
        ),
        (
            # The list separator inside a password: refused, never truncated to
            # a password that would then fail a login and read as a dead mailbox.
            "a password containing the separator",
            [COLLEAGUE],
            f"CS_READ_MAILBOX_PASSWORDS={COLLEAGUE}:pw-with,a-comma\n",
            ("CS_READ_MAILBOX_PASSWORDS", "entry 2"),
        ),
        (
            # The operator's own mailbox is read first-class, with the
            # credential the clone already holds. Declared again it would be a
            # SECOND credential for the identity mailbox — which invariant 4
            # reserves to the engine — and, whenever the operator mailbox is
            # itself unreadable, its address never enters the fan-out's `seen`
            # set, so the same mailbox would be opened twice, printed as both
            # read and unreadable, and counted twice in the one line this
            # feature exists to make trustworthy.
            "the operator's own mailbox in the declaration",
            ["ops@acme.example", COLLEAGUE],
            "",
            ("OWN operator mailbox", "remove it", "ops@acme.example"),
        ),
    ]
    for label, declared, env_lines, expected in cases:
        with tempfile.TemporaryDirectory() as td:
            repo, env = _sandbox(td, declared, env_lines)
            rc, out, err = _config(repo, env)
            assert rc == 2, f"{label}: expected a loud exit 2, got {rc}\n{out}{err}"
            assert "Traceback" not in err + out, (
                f"{label}: a bad declaration is a product state, not a bug — "
                f"it must never surface as a traceback:\n{err}"
            )
            for needle in expected:
                assert needle in err, (
                    f"{label}: the refusal must name {needle!r} so the operator "
                    f"knows what to fix:\n{err}"
                )
            assert READ_PW not in err + out, (
                f"{label}: the refusal echoed a password back:\n{err}"
            )
            assert len([ln for ln in err.strip().splitlines() if ln.strip()]) == 1, (
                f"{label}: one actionable line, not a report:\n{err}"
            )


# ------------------------------------------------- 2b. the env form of the
#                                                       declaration is not
#                                                       silently ignored


def _test_env_declaration_is_read_and_pairs_are_refused() -> None:
    """`CS_READ_MAILBOXES` layers over the manifest, and a value in the WRONG
    shape says so instead of doing nothing.

    An env key of this name is already in use in the field, holding
    `address:password` pairs — placed before this kernel had a name for either
    key. A field with no alias would read that key as absent and answer from a
    narrower scope without a word, which is the ancestral defect of this whole
    workstream: configuration that does nothing without saying so. So the alias
    exists, and the pairs shape is refused with the password WITHHELD and the
    right key named."""
    with tempfile.TemporaryDirectory() as td:
        # (a) the env form is genuinely read, and overrides the manifest
        repo, env = _sandbox(
            td, [COLLEAGUE],
            f"CS_READ_MAILBOXES={OTHER}\n"
            f"CS_READ_MAILBOX_PASSWORDS={OTHER}:{READ_PW}\n",
        )
        rc, out, err = _config(repo, env, "--json")
        assert rc == 0, f"CS_READ_MAILBOXES was not accepted:\n{err}"
        rep = json.loads(out)
        declared = {}
        for sec in rep["sections"]:
            for f in sec["settings"]:
                declared[f["name"]] = f
        f = declared["read_mailboxes"]
        assert OTHER in str(f["value"]), (
            f"the env key was ignored — it must layer over the manifest like "
            f"every other setting: {f}"
        )
        assert "CS_READ_MAILBOXES" in f["origin"], (
            f"provenance must name the env KEY the operator edits: {f['origin']}"
        )
        assert f["layer"] != "manifest", f
        assert len(rep["duplicates"]) >= 1, (
            "declaring the same setting in the manifest AND the env is a "
            "duplicate declaration and cs config must flag it"
        )

    with tempfile.TemporaryDirectory() as td:
        # (b) the pairs shape: refused, actionable, and no password anywhere
        repo, env = _sandbox(
            td, [],
            f"CS_READ_MAILBOXES={COLLEAGUE}:{READ_PW},{OTHER}:{READ_PW}\n",
        )
        rc, out, err = _config(repo, env)
        assert rc == 2, f"a pairs-shaped value must be refused, got {rc}\n{out}{err}"
        assert READ_PW not in err + out, f"the refusal echoed the password:\n{err}"
        assert COLLEAGUE in err, f"the refusal must name the entry it means:\n{err}"
        for key in ("CS_READ_MAILBOXES", "CS_READ_MAILBOX_PASSWORDS"):
            assert key in err, (
                f"the refusal must name BOTH keys — what belongs here and where "
                f"the passwords go — or the operator has to guess:\n{err}"
            )
        assert "Traceback" not in err + out, err


# ------------------------------------------------- 3. missing credential is
#                                                      NOT a config failure


def _test_declared_without_credential_still_loads() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo, env = _sandbox(td, [COLLEAGUE, OTHER],
                             f"CS_READ_MAILBOX_PASSWORDS={COLLEAGUE}:{READ_PW}\n")
        rc, out, err = _config(repo, env)
        assert rc == 0, (
            "a declared mailbox with no credential is an UNREADABLE mailbox, not "
            f"a broken configuration — the fan-out reports it by name:\n{err}"
        )
        assert COLLEAGUE in out and OTHER in out, (
            f"both declared mailboxes must be visible in the settings report:\n{out}"
        )

    # …and in-process, the same state: one credential, two declared mailboxes.
    settings = Settings(
        _env_file=(),
        email_address="ops@acme.example",
        read_mailboxes=f"{COLLEAGUE},{OTHER}",
        read_mailbox_passwords=f"{COLLEAGUE}:{READ_PW}",
    )
    assert settings.read_mailbox_list == [COLLEAGUE, OTHER]
    assert set(settings.read_mailbox_credentials) == {COLLEAGUE}


# ------------------------------------------------- 4. cs config: addresses
#                                                      yes, passwords never


def _test_cs_config_masks_the_credentials() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo, env = _sandbox(
            td, [COLLEAGUE],
            f"CS_READ_MAILBOX_PASSWORDS={COLLEAGUE}:{READ_PW}\n",
        )
        for argv in ((), ("--all",), ("--json",), ("--json", "--all")):
            rc, out, err = _config(repo, env, *argv)
            assert rc == 0, f"cs config {argv} exited {rc}:\n{err}"
            assert READ_PW not in out + err, (
                f"cs config {argv} printed a read mailbox's password — this "
                f"report is pasted into chats and cron logs:\n{out}"
            )
            assert OPERATOR_PW not in out + err, f"cs config {argv} printed a secret"
            assert "read_mailbox_passwords" in out, (
                f"the setting must be REPORTED (presence, not value) — an "
                f"operator debugging an unreadable mailbox needs to know whether "
                f"it is set at all:\n{out}"
            )

        rc, out, _ = _config(repo, env, "--json")
        rep = json.loads(out)
        by_name = {f["name"]: f for f in (rep["all"] or [])}
        for sec in rep["sections"]:
            for f in sec["settings"]:
                by_name[f["name"]] = f
        for f in rep["secrets"]:
            by_name[f["name"]] = f
        creds = by_name["read_mailbox_passwords"]
        assert creds["secret"] is True and creds["value"] == "set", creds
        assert all("value" not in d for d in creds["declarations"]), (
            f"a secret's declarations must carry WHERE, never the value: {creds}"
        )
        declared = by_name["read_mailboxes"]
        assert declared["secret"] is False and COLLEAGUE in str(declared["value"])
        assert declared["layer"] == "manifest", declared
        assert "[operator].read_mailboxes" in declared["origin"], (
            f"the report must name the file and key to EDIT: {declared['origin']}"
        )
        # The manifest holds a TOML LIST and Settings holds the comma-joined
        # string, so the report's mirror has to understand that flattening.
        # Until it did, a correctly declared list was printed with a `?` and a
        # NOTE saying its provenance was unverified — the verb blaming the
        # operator's configuration for its own blind spot.
        assert "read_mailboxes" not in rep["mismatched"], (
            f"a declared list must be EXPLAINED by its manifest declaration: "
            f"{rep['notes']}"
        )
        assert not any("read_mailboxes" in n for n in rep["notes"]), rep["notes"]
        rc, text, _ = _config(repo, env)
        assert "? " not in text, f"cs config reported unverified provenance:\n{text}"


# ------------------------------------------------- 5. never a send credential


def _test_read_credential_never_reaches_the_send_path() -> None:
    """`send_mail.send` logs in as the operator mailbox and nothing else.

    Structural first (the module cannot even name the setting), then behavioural
    against a real `send()` call with the SMTP and IMAP sockets replaced: the
    login pair is the operator's, and the read credential appears NOWHERE in the
    session — not in a login, not in a header, not in the body."""
    src = Path(send_mail.__file__).read_text()
    assert "read_mailbox" not in src, (
        "cs/send_mail.py names the read-mailbox credential — the isolation is "
        "meant to be structural, not a convention in the calling code"
    )

    settings = Settings(
        _env_file=(),
        email_address="ops@acme.example",
        email_password=OPERATOR_PW,
        email_from_name="Acme Ops",
        read_mailboxes=COLLEAGUE,
        read_mailbox_passwords=f"{COLLEAGUE}:{READ_PW}",
        smtp_host="smtp.acme.example",
        imap_host="imap.acme.example",
    )

    transcript: list[str] = []

    class FakeSMTP:
        def __init__(self, host, port):
            transcript.append(f"connect {host}:{port}")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            transcript.append("starttls")

        def login(self, user, password):
            transcript.append(f"login {user} {password}")

        def send_message(self, msg):
            transcript.append(msg.as_string())

    class FakeIMAP:
        def list(self):
            return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

        def append(self, folder, flags, date, raw):
            transcript.append(raw.decode(errors="replace"))
            return "OK", [b""]

        def logout(self):
            return "BYE", [b""]

    orig_smtp, orig_imap = send_mail.smtplib.SMTP, send_mail._imap
    send_mail.smtplib.SMTP = FakeSMTP
    send_mail._imap = lambda s: FakeIMAP()
    try:
        send_mail.send(
            settings, "customer@example.test", "Subject",
            plain="one line", html="<p>one line</p>",
        )
    finally:
        send_mail.smtplib.SMTP = orig_smtp
        send_mail._imap = orig_imap

    session = "\n".join(transcript)
    assert f"login ops@acme.example {OPERATOR_PW}" in session, (
        f"the send path must log in as the operator mailbox: {transcript[:3]}"
    )
    assert READ_PW not in session, (
        "a read-only mailbox's credential reached the send path — it can send, "
        "and nothing downstream would notice"
    )
    assert COLLEAGUE not in session, (
        "the send path must not even mention a read-only mailbox"
    )


def main() -> int:
    _test_malformed_declarations_fail_loud()
    _test_env_declaration_is_read_and_pairs_are_refused()
    _test_declared_without_credential_still_loads()
    _test_cs_config_masks_the_credentials()
    _test_read_credential_never_reaches_the_send_path()
    print("test_read_mailboxes: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
