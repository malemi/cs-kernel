#!/usr/bin/env python3
"""`cs update` must not crash when stdin has no tty (agent, cron,
`stdin </dev/null`) and it hits a template conflict.

Reproduced live 2026-08-04 during a re-pin: the conflict prompt
`input("    Overwrite? [y/N/diff] ")` raised EOFError and the whole `cs
update` run died with a traceback instead of applying the default the
prompt itself declares — the capital N in `[y/N/diff]` means "keep the
local file".

Two levels, because a passing unit check does not prove the CLI actually
takes this path:

  - characterization: `_read_overwrite_choice` — the helper `cmd_update`
    calls at both conflict prompts — fed a stdin that raises EOFError, must
    return the declared default instead of propagating the exception.
  - end-to-end: a REAL `python -m cs update` subprocess, stdin closed, run
    against a scratch stamped clone with a manufactured conflict (a rendered
    file edited locally, and its stored template-manifest checksum forced to
    a value matching neither the local edit nor the current template
    render). This is the exact "modified locally AND template changed"
    branch that used to crash on EOF.

2026-08-09: widened past the EOF regression to the two other operator
decisions `cmd_update` makes about WHICH files may hit that conflict branch
at all — also end-to-end, same closed-stdin subprocess technique:

  - `requirements.txt` is the operator's pin, never cs update's: it must be
    skipped outright (no write, no prompt, no manifest entry) even when its
    stored checksum differs from today's render.
  - SECURITY_CRITICAL templates (`.claude/settings.json`,
    `bin/cs_operator_cron.sh`) must never reach the interactive prompt at
    all: on conflict the new render is applied unconditionally, the
    operator's prior local content is preserved as `<file>.local-bak`, and a
    message says so.

2026-08-16 (Task 3, backlog `cs-kernel: a clone cannot tell that a newer
kernel tag exists`): `cs update --check` / `cs update --pin <tag>`. Real
`python -m cs update …` subprocesses throughout, against a REAL local git
repo standing in for the kernel's remote origin (`_make_kernel_origin`
below) — `git ls-remote --tags`/`git show <tag>:CHANGELOG.md` behave
identically against a local path, so this needs no network and no fixture
faking git's own output format. Guards:

  - `--check` with no requirements.txt in the cwd: exit 1, one-line error,
    no traceback.
  - `--check` against a requirements.txt whose pin line does not match the
    `cs-kernel @ git+<url>@<tag>` shape: exit 1, names the expected shape.
  - `--check` already at the latest tag: "up to date.", writes NOTHING
    (requirements.txt byte-identical before/after).
  - `--check` with a newer tag on the origin: prints installed, pinned and
    latest, AND the newer tag's re-collaudo tier — read from that tag's
    OWN CHANGELOG.md via `git show`, not hardcoded — writes NOTHING.
  - `--check` against an unreachable origin (a local path that is not a
    git repo — deterministic, no real network wait): one handled line
    naming the origin, exit 1, no traceback.
  - `--pin <tag>`: rewrites ONLY the kernel pin line, prints the exact
    before/after line, says installing it is a separate step, and leaves
    every other line of requirements.txt byte-identical.
  - bare `cs update` (no flags): unaffected — still walks the template
    tree exactly as before Task 3.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import jinja2

from cs import project_update
from cs._version import kernel_version_bare

# The smallest real template in cs/templates/project: `.gitignore.j2`
# interpolates exactly one variable (company_slug), so a minimal init_data
# renders it with no other moving parts. Not in project_update.SECURITY_CRITICAL
# — it stays the neutral file that exercises the interactive prompt.
CONFLICT_REL = ".gitignore"
BOGUS_CHECKSUM = "sha256:" + "0" * 64

# One of the two project_update.SECURITY_CRITICAL paths. Renders from four
# variables (company_slug, company_name, company_prog_name, email_address) —
# enough to exercise a real conflict without needing every template's full
# variable set: cmd_update renders the WHOLE template tree on every run, and
# templates outside a given test's concern simply fail to render individually
# under a minimal init_data — the same tolerance the scenario above already
# relies on.
SECURITY_CRITICAL_REL = "bin/cs_operator_cron.sh"


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "SHOPIFY", "EMAIL_", "ENGINE_"))
           and k not in ("RATE_CAP", "DEDUP_DAYS", "DRY_RUN")}
    env["HOME"] = str(home)
    return env


def _input_with_closed_stdin(prompt: str) -> str:
    """Call project_update._read_overwrite_choice with sys.stdin swapped for
    an already-exhausted stream, the same condition `input()` hits against
    `/dev/null` or a closed pipe — and capture what it prints."""
    real_stdin, real_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO("")  # readline() -> "" -> input() raises EOFError
    captured = io.StringIO()
    sys.stdout = captured
    try:
        return project_update._read_overwrite_choice(prompt, default="n"), captured.getvalue()
    finally:
        sys.stdin, sys.stdout = real_stdin, real_stdout


def _characterize_eof_default() -> None:
    # First conflict prompt: "modified locally AND template changed."
    result, printed = _input_with_closed_stdin("    Overwrite? [y/N/diff] ")
    assert result == "n", f"EOF must resolve to the declared default 'n', got {result!r}"
    assert "no tty" in printed and "keeping local file" in printed, (
        f"the keep-local decision must be printed to stdout, got: {printed!r}"
    )

    # Second prompt in the same flow (after the user asks for `diff`) declares
    # the same default and must degrade the same way — this is the "any OTHER
    # input() call in the same flow" the fix also had to cover.
    result2, printed2 = _input_with_closed_stdin("    Overwrite? [y/N] ")
    assert result2 == "n", f"the second prompt's EOF must also default to 'n', got {result2!r}"
    assert "no tty" in printed2 and "keeping local file" in printed2, (
        f"the second prompt must also print the keep-local decision, got: {printed2!r}"
    )


def _e2e_conflict_keeps_local_with_closed_stdin() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        local_content = "# locally edited — must survive the update\ndist/\n"
        (clone / CONFLICT_REL).write_text(local_content)

        # Manufacture the conflict: the stored checksum matches neither the
        # local edit (so "clone was modified") nor what .gitignore.j2 renders
        # to today (so "template changed") — i.e. cmd_update's ask branch.
        manifest = {
            "template_version": "1",
            "init_data": {"company_slug": "acme"},
            "file_checksums": {CONFLICT_REL: BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, (
            f"`cs update` must exit 0 on a closed stdin, got {proc.returncode}:\n{out}"
        )
        assert (clone / CONFLICT_REL).read_text() == local_content, (
            "the locally-modified file must be UNCHANGED when stdin has no tty:\n" + out
        )
        assert "modified locally AND template changed" in out, (
            f"the manufactured conflict must actually be hit by the real code path:\n{out}"
        )
        assert "no tty" in out and "keeping local file" in out, (
            f"the run's output must name the keep-local decision:\n{out}"
        )


def _render_current_template(rel: str, init_data: dict) -> str:
    """Render `<template_root>/<rel>.j2` with the SAME jinja settings
    cmd_update uses, independently of cs/project_update.py, so a test can
    know what "the new render" is without trusting the code under test to
    report its own output correctly."""
    import cs as cs_mod

    tpl_path = Path(cs_mod.__file__).parent / "templates" / "project" / f"{rel}.j2"
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True,
    )
    return env.from_string(tpl_path.read_text()).render(**init_data)


def _e2e_already_current_no_prompt_no_diff() -> None:
    """When the file on disk already IS today's render — content brought in
    sync by some means other than `cs update` itself (a hand-edit that
    converged, a one-off re-render) — the stored checksum can still be
    stale, which used to read as "modified locally AND template changed"
    and prompt anyway. Confirmed confusing live 2026-08-21: the operator
    typed "diff" and saw NOTHING (clone_content == rendered, so the diff is
    empty by construction), left staring at a conflict with no way to tell
    what to decide. Guards: no "Overwrite?" prompt appears at all, the file
    is untouched, and the manifest's checksum is refreshed to match. stdin
    stays closed like every other subprocess test here — if the fix
    regressed and a prompt reappeared, EOF resolving to "N" would still
    leave the "Overwrite?"/"already current" assertions telling them apart,
    without risking a hang on inherited stdin."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        current_render = _render_current_template(CONFLICT_REL, {"company_slug": "acme"})
        (clone / CONFLICT_REL).write_text(current_render)

        manifest = {
            "template_version": "1",
            "init_data": {"company_slug": "acme"},
            "file_checksums": {CONFLICT_REL: BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, f"expected exit 0:\n{out}"
        assert "Overwrite?" not in out, f"an already-current file must never prompt:\n{out}"
        assert (clone / CONFLICT_REL).read_text() == current_render, "file must be untouched"
        assert f"{CONFLICT_REL} (already current)" in out, out

        updated_manifest = json.loads((clone / "template-manifest.json").read_text())
        assert updated_manifest["file_checksums"].get(CONFLICT_REL) not in (None, BOGUS_CHECKSUM), (
            "the stale checksum must be refreshed, not left as the bogus stored value:\n"
            f"{updated_manifest['file_checksums']}"
        )


def _e2e_company_slot_authored_never_prompts_never_overwrites() -> None:
    """`company/**` is prose the operator is TOLD to author, so an authored
    slot differs from its stored checksum permanently. Tracking it in
    `file_checksums` therefore produced a conflict that could never be
    resolved: every clone was asked "modified locally AND template changed.
    Overwrite? [y/N/diff]" about every slot, at every single update, for ever
    — and one wrong "y" destroys prose no template can regenerate.

    This runs against the shape BOTH existing clones are actually in: a
    manifest that still carries the stale `company/…` checksum entries `cs
    init` wrote before the fix, plus authored files on disk. It must need no
    migration — no prompt, no write, and the stale entries gone from the
    ledger afterwards. Stdin closed, like every other subprocess test here:
    if a prompt reappeared, EOF would resolve it to "keep local" and the file
    assertions alone would not tell the two behaviours apart, so the
    "Overwrite?" assertion is the one that matters.
    """
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        authored_rel = "company/team-conventions.md"
        untouched_rel = "company/triage-domain-examples.md"
        missing_rel = "company/campaign-product-notes.md"

        authored = (
            "# Team conventions — who answers from where\n\n"
            "Jane answers billing from billing@acme.example; the Sent archive\n"
            "of the support box never sees those threads.\n"
        )
        (clone / "company").mkdir()
        (clone / authored_rel).write_text(authored)
        # A slot still holding exactly what the OLD template stamped: it must
        # be left alone too. "Unmodified" is not a licence to re-stamp — the
        # operator may simply not have written it yet, and a silent rewrite
        # would move a file they are about to open.
        old_stamp = "Examples of domain-specific topics for Acme Corp:\n"
        (clone / untouched_rel).write_text(old_stamp)

        manifest = {
            "template_version": "1",
            "init_data": {
                "company_slug": "acme", "company_name": "Acme Corp",
                "company_prog_name": "acme-cs", "company_display_name": "Acme",
                "email_address": "support@acme.example",
                "accounts_default": "support", "drive_scope": "",
            },
            # Exactly what a pre-fix `cs init` left behind, and what both live
            # clones' manifests carry today.
            "file_checksums": {
                authored_rel: BOGUS_CHECKSUM,
                untouched_rel: BOGUS_CHECKSUM,
                missing_rel: BOGUS_CHECKSUM,
            },
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, f"expected exit 0:\n{out}"
        assert "Overwrite?" not in out, (
            f"a company/ slot must never reach the conflict prompt:\n{out}"
        )
        for present in (authored_rel, untouched_rel):
            assert present not in out, (
                "a slot the clone already has is not an event: it must not "
                f"appear in the default output at all ({present}):\n{out}"
            )
        assert (clone / authored_rel).read_text() == authored, (
            f"authored company prose must be byte-identical after the update:\n{out}"
        )
        assert (clone / untouched_rel).read_text() == old_stamp, (
            f"an unmodified slot must not be re-stamped either:\n{out}"
        )
        # Create-if-missing: the slot the clone did not have is stamped, so a
        # new slot added by a kernel release still reaches every clone.
        assert (clone / missing_rel).exists(), (
            f"a missing company slot must be created by cs update:\n{out}"
        )

        updated = json.loads((clone / "template-manifest.json").read_text())
        stale = [k for k in updated["file_checksums"] if k.startswith("company/")]
        assert not stale, (
            "the stale company/ entries must be dropped from the ledger, not "
            f"refreshed: {stale}"
        )

        # Second run, now that the ledger is clean and one more slot exists on
        # disk: still silent, still no prompt. This is the state every clone
        # lands in, and it is the one the operator sees at every future update.
        proc2 = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120,
        )
        out2 = proc2.stdout + proc2.stderr
        assert proc2.returncode == 0, f"expected exit 0 on the second run:\n{out2}"
        assert "Overwrite?" not in out2, f"second run must not prompt either:\n{out2}"
        assert (clone / authored_rel).read_text() == authored, (
            f"authored prose must survive a second update too:\n{out2}"
        )

        # -v is where a non-event is allowed to be reported (CLAUDE.md rule 6).
        proc3 = subprocess.run(
            [sys.executable, "-m", "cs", "update", "-v"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120,
        )
        out3 = proc3.stdout + proc3.stderr
        assert f"{authored_rel} is yours" in out3, (
            f"-v must account for the slots it deliberately left alone:\n{out3}"
        )


def _e2e_security_critical_conflict_applies_with_backup() -> None:
    """A SECURITY_CRITICAL file (project_update.SECURITY_CRITICAL) must never
    be gated behind the interactive prompt: on a "modified locally AND
    template changed" conflict the new render is applied unconditionally, the
    operator's prior local content is preserved next to it as
    `<file>.local-bak`, and a loud message names both facts. Manufactured the
    same way as the neutral-file scenario above: the stored checksum matches
    neither the local edit nor what the template renders today."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        (clone / "bin").mkdir()
        local_content = (
            "#!/usr/bin/env bash\n"
            "# locally edited cron — must be BACKED UP, not silently discarded\n"
            "echo legacy\n"
        )
        (clone / SECURITY_CRITICAL_REL).write_text(local_content)

        init_data = {
            "company_slug": "acme",
            "company_name": "Acme Corp",
            "company_prog_name": "acme-cs",
            "email_address": "support@acme.example",
        }
        manifest = {
            "template_version": "1",
            "init_data": init_data,
            "file_checksums": {SECURITY_CRITICAL_REL: BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, (
            f"`cs update` must exit 0 on a SECURITY_CRITICAL conflict, got {proc.returncode}:\n{out}"
        )
        assert "Overwrite?" not in out and "modified locally AND template changed" not in out, (
            f"a SECURITY_CRITICAL conflict must never show the interactive prompt:\n{out}"
        )

        expected_new = _render_current_template(SECURITY_CRITICAL_REL, init_data)
        actual_new = (clone / SECURITY_CRITICAL_REL).read_text()
        assert actual_new == expected_new, (
            "the SECURITY_CRITICAL file must hold the NEW template render after update:\n"
            f"--- expected ---\n{expected_new}\n--- actual ---\n{actual_new}"
        )

        backup_path = clone / f"{SECURITY_CRITICAL_REL}.local-bak"
        assert backup_path.exists(), f".local-bak backup was not created:\n{out}"
        assert backup_path.read_text() == local_content, (
            "the .local-bak backup must hold the EXACT prior local content, unchanged"
        )

        assert (
            f"{SECURITY_CRITICAL_REL}: SECURITY-CRITICAL template updated — new version applied."
            in out
        ), f"the SECURITY-CRITICAL message must name the file and state it was applied:\n{out}"
        assert (
            f"Your locally-edited version was saved to {SECURITY_CRITICAL_REL}.local-bak." in out
        ), f"the message must name the backup path:\n{out}"
        assert (
            "Re-apply any clone-specific entries on top of the new file, then delete the backup."
            in out
        ), f"the message must tell the operator what to do next:\n{out}"


def _e2e_requirements_txt_never_touched() -> None:
    """requirements.txt is the operator's pin, not a render target: cmd_update
    must never write it, never prompt on it, and never record it in the
    updated manifest's file_checksums — even though its stored checksum here
    differs from today's template render, which for any OTHER file would be
    exactly the "template changed" trigger."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        pinned_content = "cs-kernel==0.4.7\nrequests>=2.31\n"
        (clone / "requirements.txt").write_text(pinned_content)

        manifest = {
            "template_version": "1",
            "init_data": {
                "company_slug": "acme",
                "company_name": "Acme Corp",
                "company_prog_name": "acme-cs",
                "repo_kernel_version": "0.5.2",
            },
            "file_checksums": {"requirements.txt": BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr

        assert proc.returncode == 0, (
            f"`cs update` must exit 0 past a requirements.txt entry, got {proc.returncode}:\n{out}"
        )
        assert (clone / "requirements.txt").read_text() == pinned_content, (
            "requirements.txt must be byte-identical to what it held before the update:\n" + out
        )
        # Silent by default (2026-08-21: a file that was NOT touched is not
        # an event — the two "· … never touches it" notices were noise on
        # every single run); the explanation is there under --verbose.
        assert "requirements.txt" not in out, (
            f"a left-alone file must not be announced on a normal run:\n{out}"
        )
        vproc = subprocess.run(
            [sys.executable, "-m", "cs", "update", "--verbose"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        vout = vproc.stdout + vproc.stderr
        assert "requirements.txt is yours" in vout, (
            f"--verbose must explain what it left alone:\n{vout}"
        )

        updated_manifest = json.loads((clone / "template-manifest.json").read_text())
        assert "requirements.txt" not in updated_manifest["file_checksums"], (
            "requirements.txt must be absent from the updated manifest's file_checksums:\n"
            f"{updated_manifest['file_checksums']}"
        )


# manifest.toml.j2 is the one template that needs nearly the FULL init_data
# shape (every [company]/[operator]/[engine]/[knobs]/… field) — unlike
# requirements.txt.j2 (one variable) or the SECURITY_CRITICAL templates, the
# other minimal fixtures in this file tolerate a 4-key init_data because
# their templates barely read it. This one may not: an incomplete init_data
# makes manifest.toml.j2 itself raise UndefinedError, which render_templates
# catches, prints, and skips BEFORE ever reaching the "clone-owned, never
# touched" exemption check below it — that would silently pass this test
# for the wrong reason (the file was skipped because rendering crashed, not
# because the exemption fired). The account name is email-shaped
# (`jane.doe@acme.example`) to also exercise the exact bare-TOML-key shape
# that broke live, end to end, through this fixture.
_FULL_INIT_DATA = {
    "company_slug": "acme", "company_name": "Acme Corp",
    "company_display_name": "Acme", "company_from_name": "Acme Support",
    "company_prog_name": "acme-cs",
    "email_address": "support@acme.example",
    "imap_host": "imap.example.com", "imap_port": "993",
    "smtp_host": "smtp.example.com", "smtp_port": "587",
    "engine_owner_uid": "UID123", "engine_ws_url": "wss://engines.example.com",
    "firebase_sa_path": "~/.acme-cs/firebase-sa.json",
    "accounts": {"support": "UID123", "jane.doe@acme.example": "UID999"},
    "accounts_default": "support",
    "founder_sweep_enabled": False, "founder_sweep_account": "",
    "crm_adapter": "none", "crm_shopify": False,
    "producer_adapter": "none", "producer_mrcall_tracking": False,
    "excluded_campaign": "", "posture_note": "",
    "dedup_days": "30", "rate_cap": "25", "cs_triage_mode": "draft",
    "dry_run": True, "autonomous": False, "timezone": "Europe/Rome",
    "sms_hour": "18", "reminder_max": "2",
    "sms_enabled": False, "sms_proxy_base": "",
    "drive_scope": "", "cron_schedule": "0 8 * * *", "cron_comment": "acme-cs",
    "platform_env_path": "", "repo_git_remote": "git@example.com:acme/acme-cs.git",
    "repo_kernel_version": "0.5.2", "repo_docs_shape": "generic",
    "posture_note": "", "name": "Acme", "dest_dir": "acme-cs",
}


def _e2e_manifest_toml_never_touched() -> None:
    """manifest.toml is clone-owned by charter (CLAUDE.md.j2, "Editing this
    clone"), the ONE place values change — same class as requirements.txt.
    Confirmed live 2026-08-21: offering it through the normal diff/overwrite
    flow let an operator "y" their own hand-authored manifest away, and the
    bare re-render was invalid TOML the moment an account name was an email
    (the documented recommended shape). `cs update` must never write it,
    never prompt on it, and never record it in the updated manifest's
    file_checksums — even with a garbage stored checksum, which for any
    OTHER file would be exactly the "template changed" trigger."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        hand_authored = (
            '# hand-authored, never touch\n'
            '[engine.accounts]\n'
            'support = "UID1"\n'
            '"jane.doe@acme.example" = "UID2"\n'
        )
        (clone / "manifest.toml").write_text(hand_authored)

        manifest = {
            "template_version": "1",
            "init_data": _FULL_INIT_DATA,
            "file_checksums": {"manifest.toml": BOGUS_CHECKSUM},
        }
        (clone / "template-manifest.json").write_text(json.dumps(manifest))

        proc = subprocess.run(
            [sys.executable, "-m", "cs", "update"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr

        assert "failed to render" not in out, (
            f"init_data must be complete enough to render every template — a "
            f"render failure would skip manifest.toml's exemption check for "
            f"the wrong reason:\n{out}"
        )
        assert proc.returncode == 0, (
            f"`cs update` must exit 0 past a manifest.toml entry, got {proc.returncode}:\n{out}"
        )
        assert (clone / "manifest.toml").read_text() == hand_authored, (
            "manifest.toml must be byte-identical to what it held before the update:\n" + out
        )
        assert "manifest.toml" not in out, (
            f"a left-alone file must not be announced on a normal run:\n{out}"
        )
        vproc = subprocess.run(
            [sys.executable, "-m", "cs", "update", "--verbose"],
            cwd=clone, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        vout = vproc.stdout + vproc.stderr
        assert "manifest.toml is yours" in vout, (
            f"--verbose must explain what it left alone:\n{vout}"
        )

        updated_manifest = json.loads((clone / "template-manifest.json").read_text())
        assert "manifest.toml" not in updated_manifest["file_checksums"], (
            "manifest.toml must be absent from the updated manifest's file_checksums:\n"
            f"{updated_manifest['file_checksums']}"
        )


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30,
    )


def _make_kernel_origin(root: Path, releases: list[tuple[str, str]]) -> Path:
    """A REAL local git repo standing in for the kernel's remote origin,
    one commit + one semver tag per `(tag, changelog_body)` pair in
    `releases`, oldest first. `git ls-remote --tags`/`git show
    <tag>:CHANGELOG.md` behave identically against a local repo path, so
    `cs update --check` needs no network and no fixture faking git's own
    output format — it is exercised against a real one."""
    origin = root / "kernel-origin"
    origin.mkdir()
    _git("init", "-q", cwd=origin)
    for tag, body in releases:
        (origin / "CHANGELOG.md").write_text(body)
        _git("add", "CHANGELOG.md", cwd=origin)
        _git(
            "-c", "user.email=test@example.com", "-c", "user.name=test",
            "commit", "-q", "-m", tag, cwd=origin,
        )
        _git("tag", tag, cwd=origin)
    return origin


def _write_requirements(clone: Path, origin: Path | str, tag: str) -> Path:
    path = clone / "requirements.txt"
    path.write_text(
        "# The clone's ONLY dependency: the pinned cs-kernel.\n"
        f"cs-kernel @ git+{origin}@{tag}\n"
    )
    return path


def _run_update(argv: list[str], clone: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cs", "update", *argv],
        cwd=clone, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=60,
    )


def _e2e_check_no_requirements_txt() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        proc = _run_update(["--check"], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}:\n{out}"
        assert "no requirements.txt found" in out, out
        assert "Traceback" not in out, out


def _e2e_check_malformed_pin() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)
        (clone / "requirements.txt").write_text("cs-kernel==0.4.7\n")

        proc = _run_update(["--check"], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}:\n{out}"
        assert "no recognizable cs-kernel pin line" in out, out
        assert "git+<url>@<tag>" in out, out
        assert "Traceback" not in out, out


def _e2e_check_up_to_date() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        origin = _make_kernel_origin(
            Path(td), [("v0.1.0", "## 0.1.0\n\n- **Re-collaudo:** static\n")],
        )
        before = _write_requirements(clone, origin, "v0.1.0").read_text()

        proc = _run_update(["--check"], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}:\n{out}"
        assert "up to date." in out, out
        assert (clone / "requirements.txt").read_text() == before, (
            "--check must write NOTHING, ever"
        )


def _e2e_check_newer_tag_with_tier() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        origin = _make_kernel_origin(
            Path(td),
            [
                ("v0.1.0", "## 0.1.0\n\n- **Re-collaudo:** static\n"),
                (
                    "v0.2.0",
                    "## 0.2.0 — 2026-08-16\n\n"
                    "### Added — something\n"
                    "- **Why:** because.\n"
                    "- **What:** this.\n"
                    "- **Re-collaudo:** full, both clones — because it touches "
                    "the send boundary.\n",
                ),
            ],
        )
        before = _write_requirements(clone, origin, "v0.1.0").read_text()

        proc = _run_update(["--check"], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}:\n{out}"
        assert "pinned:     v0.1.0" in out, out
        assert "latest:     v0.2.0" in out, out
        assert "newer tag available: v0.2.0" in out, out
        assert "full, both clones" in out, (
            f"the newer tag's OWN CHANGELOG.md re-collaudo line must be read "
            f"and printed, not hardcoded:\n{out}"
        )
        # --check must point at the ONE-COMMAND upgrade, not the manual
        # three-step it used to recommend (`--pin <tag>` + pip install):
        # since v0.9.2 bare `cs update` re-pins, installs and re-stamps on a
        # single "y", so telling the operator to do it by hand was actively
        # wrong advice (caught live 2026-08-21, "istruzione errata").
        assert "run `cs update` and answer y" in out, (
            f"--check must recommend the one-command upgrade:\n{out}"
        )
        assert "--pin" in out and "rollback" in out, (
            f"--pin must be presented as the specific-version/rollback hatch:\n{out}"
        )
        assert (clone / "requirements.txt").read_text() == before, (
            "--check must write NOTHING, ever"
        )


def _e2e_check_installed_version_reported() -> None:
    """The "installed" half of installed-vs-latest is the ACTUAL installed
    package (importlib.metadata via cs._version.kernel_version_bare),
    independently computed here so the test does not trust the code under
    test to report its own truth."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        origin = _make_kernel_origin(
            Path(td), [("v0.1.0", "## 0.1.0\n\n- **Re-collaudo:** static\n")],
        )
        _write_requirements(clone, origin, "v0.1.0")

        proc = _run_update(["--check"], clone, env)
        out = proc.stdout + proc.stderr
        installed = kernel_version_bare()
        expect = installed or "(unknown — package not installed)"
        assert f"installed:  {expect}" in out, out


def _e2e_check_unreachable_origin() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        # A local path that does NOT exist / is not a git repo — git
        # fails fast against it (no network wait either way), exercising
        # the handled-failure branch deterministically.
        not_a_repo = str(Path(td, "does-not-exist"))
        _write_requirements(clone, not_a_repo, "v0.1.0")

        proc = _run_update(["--check"], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}:\n{out}"
        assert "could not reach" in out, out
        assert not_a_repo in out, out
        assert "Traceback" not in out, out


def _e2e_pin_rewrites_only_the_pin_line() -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        origin_url = "https://github.com/malemi/cs-kernel"
        req_path = clone / "requirements.txt"
        req_path.write_text(
            "# The clone's ONLY dependency: the pinned cs-kernel.\n"
            "# Upgrade = bump the pin, pip install, re-collaudo.\n"
            f"cs-kernel @ git+{origin_url}@v0.6.1\n"
        )

        proc = _run_update(["--pin", "v0.7.0"], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}:\n{out}"
        assert f"- cs-kernel @ git+{origin_url}@v0.6.1" in out, out
        assert f"+ cs-kernel @ git+{origin_url}@v0.7.0" in out, out
        assert "pip install -r requirements.txt" in out, (
            f"must say installing it is a separate, deliberate step:\n{out}"
        )

        new_text = req_path.read_text()
        assert new_text == (
            "# The clone's ONLY dependency: the pinned cs-kernel.\n"
            "# Upgrade = bump the pin, pip install, re-collaudo.\n"
            f"cs-kernel @ git+{origin_url}@v0.7.0\n"
        ), (
            "--pin must rewrite ONLY the pin line — every other byte of "
            f"requirements.txt must be unchanged:\n{new_text}"
        )


def _e2e_bare_update_unaffected() -> None:
    """Bare `cs update` (no --check/--pin) must be untouched by Task 3 —
    still requires template-manifest.json and still walks the template
    tree exactly as before."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        env = _clean_env(home)

        proc = _run_update([], clone, env)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}:\n{out}"
        assert "no template-manifest.json found" in out, out


def _minimal_manifest(clone: Path) -> None:
    (clone / "template-manifest.json").write_text(json.dumps({
        "template_version": "1",
        "init_data": {
            "company_slug": "acme",
            "company_name": "Acme Corp",
            "company_prog_name": "acme-cs",
            "repo_kernel_version": "0.5.2",
        },
        "file_checksums": {},
    }))


def _e2e_bare_update_offers_upgrade_eof_keeps_pin() -> None:
    """Bare `cs update` against an origin with a newer tag OFFERS the
    upgrade; a closed stdin resolves the prompt to the declared No (the
    v0.5.2 EOF contract), the pin is byte-identical afterwards, and the
    template refresh still runs (exit 0)."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        origin = _make_kernel_origin(Path(td), [
            ("v0.1.0", "## v0.1.0 — old\n"),
            ("v0.2.0", "## v0.2.0 — new\n- **Re-collaudo:** static\n"),
        ])
        req = _write_requirements(clone, origin, "v0.1.0")
        pinned = req.read_text()
        _minimal_manifest(clone)

        proc = _run_update([], clone, _clean_env(home))
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, f"expected exit 0:\n{out}"
        assert "Found new tag (v0.2.0" in out, out
        assert "keeping the current pin" in out, out
        assert req.read_text() == pinned, "EOF on the offer must not rewrite the pin"


def _e2e_bare_update_offline_offer_skipped() -> None:
    """An unreachable origin must not block the template refresh: the offer
    prints one skip line and bare `cs update` proceeds to exit 0."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        clone = Path(td, "clone"); clone.mkdir()
        _write_requirements(clone, Path(td, "no-such-origin"), "v0.1.0")
        _minimal_manifest(clone)

        proc = _run_update([], clone, _clean_env(home))
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0, f"expected exit 0:\n{out}"
        assert "release check skipped" in out, out


def _offer_yes_path_repins_installs_reexecs() -> None:
    """The accepted offer, in-process with the two irreversible seams
    stubbed (pip install, execv — a real execv would replace this test
    runner): the pin line is rewritten to the new tag, pip is invoked on
    requirements.txt in this interpreter, and the re-exec targets
    `python -m cs update`."""
    import builtins
    from cs import project_update as pu

    with tempfile.TemporaryDirectory() as td:
        clone = Path(td, "clone"); clone.mkdir()
        origin = _make_kernel_origin(Path(td), [
            ("v0.1.0", "## v0.1.0 — old\n"),
            ("v0.2.0", "## v0.2.0 — new\n- **Re-collaudo:** static\n"),
        ])
        req = _write_requirements(clone, origin, "v0.1.0")

        calls: dict = {}
        real_run = pu.subprocess.run

        def fake_run(cmd, *a, **kw):
            if cmd[:2] == ["git", "ls-remote"] or cmd[0] == "git":
                return real_run(cmd, *a, **kw)
            calls["pip"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        old_input, old_execv = builtins.input, pu.os.execv
        builtins.input = lambda *a, **kw: "y"
        pu.subprocess.run = fake_run
        pu.os.execv = lambda exe, argv: calls.__setitem__("execv", (exe, argv))
        try:
            rc = pu._offer_release_upgrade(clone)
        finally:
            builtins.input = old_input
            pu.subprocess.run = real_run
            pu.os.execv = old_execv

        assert rc == 0, f"stubbed-execv path must return 0, got {rc}"
        assert f"@v0.2.0" in req.read_text(), "pin must be rewritten to the new tag"
        # `uv pip install --python <this interpreter>`, never `python -m pip`:
        # a venv made per README Step 2 (`uv venv .venv`) ships NO pip module,
        # so the old form died with "No module named pip" on exactly the
        # clones this flow exists for (confirmed live 2026-08-21).
        assert calls["pip"] == ["uv", "pip", "install", "--python", sys.executable,
                                "-q", "-r", "requirements.txt"], calls.get("pip")
        assert "-m" not in calls["pip"], (
            f"must not shell out to `python -m pip` — uv-made venvs have no pip: {calls['pip']}"
        )
        assert calls["execv"] == (sys.executable,
                                  [sys.executable, "-m", "cs", "update"]), calls.get("execv")


def main() -> int:
    _characterize_eof_default()
    _e2e_bare_update_offers_upgrade_eof_keeps_pin()
    _e2e_bare_update_offline_offer_skipped()
    _offer_yes_path_repins_installs_reexecs()
    _e2e_conflict_keeps_local_with_closed_stdin()
    _e2e_already_current_no_prompt_no_diff()
    _e2e_company_slot_authored_never_prompts_never_overwrites()
    _e2e_security_critical_conflict_applies_with_backup()
    _e2e_requirements_txt_never_touched()
    _e2e_manifest_toml_never_touched()
    _e2e_check_no_requirements_txt()
    _e2e_check_malformed_pin()
    _e2e_check_up_to_date()
    _e2e_check_newer_tag_with_tier()
    _e2e_check_installed_version_reported()
    _e2e_check_unreachable_origin()
    _e2e_pin_rewrites_only_the_pin_line()
    _e2e_bare_update_unaffected()
    print("test_project_update: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
