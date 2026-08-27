"""
Module for initializing a new company clone from templates.
"""
import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
import hashlib
from datetime import datetime
import jinja2
from dotenv import dotenv_values

from ._version import kernel_version, kernel_version_bare
from . import login
from . import manifest as manifest_mod

# Removed from the interactive wizard entirely (never prompted, in any
# mode). `cs cron install` will own scheduling; these are inert today —
# manifest.py's Manifest model has no [cron] table at all ("template-only,
# tolerated and ignored at runtime") — so a fixed default renders the same
# valid TOML the prompt used to produce.
DEFAULT_CRON_SCHEDULE = "0 6-18/2 * * 2-5"
DEFAULT_CRON_COMMENT = "cs-operator"

def descriptor_defaults() -> dict:
    """Prefill `cs init`'s engine-identity prompts from a mrcall-desktop
    sign-in already on this machine.

    Scans `login.descriptor_root()` via `login.scan_descriptors()` +
    `login.parse_descriptor()`. Returns `{}` when there is no valid
    descriptor. When there is EXACTLY ONE valid descriptor, returns it
    mapped onto config keys: `email_address`, `engine_ws_url`,
    `engine_owner_uid`, `default_uid`, `descriptor_email`. When there is
    MORE THAN ONE valid descriptor, also returns `{}` — `cs init` stays
    neutral in that case; picking among several signed-in profiles is `cs
    login`'s job, not this wizard's. An unparsable descriptor found during
    the scan is skipped silently: this runs unconditionally at the top of
    every `cs init`, and a stray or corrupt file already on the machine
    must never crash the wizard.
    """
    root = login.descriptor_root()
    valid = []
    for path in login.scan_descriptors(root):
        try:
            valid.append(login.parse_descriptor(path))
        except ValueError:
            continue
    if len(valid) != 1:
        return {}
    d = valid[0]
    return {
        "email_address": d["email"],
        "engine_ws_url": login.descriptor_ws_base(d),
        "engine_owner_uid": d["uid"],
        "default_uid": d["uid"],
        "descriptor_email": d["email"],
        # Public web API key of the engine's Firebase project (the descriptor
        # requires it) — lets the wizard write a ready `.env` instead of
        # sending the operator to hunt the key down by hand.
        "firebase_web_api_key": d["firebase_web_api_key"],
    }

def load_existing_config(target_dir: Path) -> dict:
    """Read an existing `manifest.toml` (+ its state-dir `.env`) at
    `target_dir` — normally the directory `cs init` is invoked FROM — and
    flatten it into a `collect_config()`-shaped defaults dict.

    `{}` when there is no manifest there: the caller's cue that this is a
    first-time init with nothing to prefill from, so `cs init` shows every
    prompt (see `cmd_init`). This is what makes a re-run of `cs init` inside
    an already-stamped clone read the CURRENT values instead of starting
    from "Acme Corp" again.

    `manifest.toml` is the primary source. `~/.<slug>-cs/.env`'s
    `CS_ACCOUNTS` wins for account uids specifically — `cs/config.py`'s own
    contract is "REAL uids live in the env layer," so the manifest's
    `[engine.accounts]` table (seeded once at init time) can go stale the
    moment an account is added or re-keyed by hand afterward.

    `[repo]` and `[cron]` are template-only tables the `Manifest` model
    does not even define a field for (unknown top-level tables are
    dropped by `extra="ignore"`) — read straight off the parsed TOML
    instead, and only for `git_remote`: the one such value worth not
    resetting to "" on a re-run (`docs_shape` is always recomputed fresh
    — see `collect_config` — and `[cron]` is being retired from this
    wizard entirely).

    Everything the template stamps but the wizard does not prompt for must
    still be carried here, or the wizard destroys it on a re-run. That is
    not hypothetical: `posture_note` held real prose on both clones while
    `collect_config` hardcoded it back to "" and this function did not
    return it at all.
    """
    manifest_path = target_dir / "manifest.toml"
    if not manifest_path.exists():
        return {}
    try:
        m = manifest_mod.load_manifest(manifest_path)
    except manifest_mod.ManifestError:
        return {}
    try:
        with open(manifest_path, "rb") as fh:
            raw = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        raw = {}

    accounts = {k: v for k, v in m.engine.accounts.items() if k != "default"}
    accounts_default = m.engine.accounts.get("default", "")

    slug = m.company.slug
    if slug:
        env_path = Path.home() / f".{slug}-cs" / ".env"
        if env_path.exists():
            env_accounts = (dotenv_values(env_path).get("CS_ACCOUNTS") or "").strip()
            if env_accounts:
                accounts = {}
                for pair in env_accounts.split(","):
                    pair = pair.strip()
                    if ":" in pair:
                        name, uid = pair.split(":", 1)
                        accounts[name] = uid

    out = {
        "company_name": m.company.name,
        "company_display_name": m.company.display_name,
        "company_from_name": m.company.from_name,
        "company_slug": slug,
        "company_prog_name": m.company.prog_name,
        "email_address": m.operator.email_address,
        "imap_host": m.operator.imap_host,
        "imap_port": m.operator.imap_port,
        "smtp_host": m.operator.smtp_host,
        "smtp_port": m.operator.smtp_port,
        "engine_owner_uid": m.engine.owner_uid,
        "engine_ws_url": m.engine.ws_url,
        "accounts": accounts,
        "accounts_default": accounts_default,
        "founder_sweep_enabled": m.engine.founder_sweep.enabled,
        "founder_sweep_account": m.engine.founder_sweep.account,
        "crm_adapter": m.crm.adapter,
        "dedup_days": m.knobs.dedup_days,
        "cs_triage_mode": m.knobs.cs_triage_mode,
        "timezone": m.knobs.timezone,
        "sms_hour": m.knobs.sms_hour,
        "reminder_max": m.knobs.reminder_max,
        "system_senders": m.knobs.system_senders,
        "send_guard_min_chars": m.knobs.send_guard_min_chars,
        "send_guard_banned_phrases": m.knobs.send_guard_banned_phrases,
        "sms_enabled": m.sms.enabled,
        "repo_git_remote": raw.get("repo", {}).get("git_remote", ""),
    }
    if m.crm.shopify is not None:
        out["crm_shopify"] = {
            "api_version": m.crm.shopify.api_version,
            "env_prefix": m.crm.shopify.env_prefix,
        }
    return out


def _default(existing: dict, key: str, fallback):
    """`existing` (an already-stamped clone's own manifest/.env) wins over
    the generic fallback; `None`/`""` in `existing` count as "not declared"
    so a sparse or first-time-init `existing` (`{}`) never masks a real
    default with a blank."""
    val = existing.get(key)
    if val is None or val == "":
        return fallback
    return val


def _prompt_or_default(show_all: bool, prompt: str, value, essential: bool = False):
    """Ask when this field is currently visible (`essential` or
    `show_all`); otherwise silently take `value` — the resolved existing
    manifest/.env value or its generic fallback, already computed by the
    caller via `_default`."""
    if essential or show_all:
        return prompt_input(prompt, value)
    return value


def _prompt_or_default_yn(show_all: bool, prompt: str, value: bool, essential: bool = False):
    if essential or show_all:
        return prompt_yes_no(prompt, default=value)
    return value


def _prompt_or_default_int(show_all: bool, prompt: str, value, essential: bool = False):
    if not (essential or show_all):
        return int(value)
    try:
        return int(prompt_input(prompt, str(value)))
    except ValueError:
        print(f"Invalid number, using default {value}")
        return int(value)


def validate_slug(slug: str) -> bool:
    """Validate slug is lowercase alphanumeric with hyphens only."""
    return bool(re.match(r"^[a-z0-9-]+$", slug))

def prompt_input(prompt: str, default: str | None = None) -> str:
    """Prompt user for input. `default=None` means the field is required
    (blank input re-prompts); any other value — including "" — is returned
    as-is on blank input, so callers pass `default=""` for a field that may
    be legitimately left empty."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    while True:
        value = input(prompt).strip()
        if not value:
            if default is not None:
                return default
            print("Please provide a value.")
            continue
        return value

def prompt_yes_no(prompt: str, default: bool = False) -> bool:
    """Prompt user for yes/no input."""
    default_str = "y" if default else "n"
    prompt = f"{prompt} [{default_str}]: "
    
    while True:
        value = input(prompt).strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("Please enter y/yes or n/no.")

def get_company_slug(name: str) -> str:
    """Convert company name to slug (lowercase, no spaces)."""
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")

def collect_config(advanced: bool = False, existing: dict | None = None) -> dict:
    """Collect configuration through interactive prompts.

    Two independent things decide what the operator actually sees:

    - `existing` (from `load_existing_config`) supplies DEFAULTS, always,
      first-time init or not. An already-stamped clone's own
      `manifest.toml` + state-dir `.env` win over the generic "Acme
      Corp"-style fallbacks baked into this function, so re-running `cs
      init` inside one never resets a real value back to a placeholder.
    - `advanced` alone decides the PROMPT SET: `show_all` is exactly
      `advanced`. Without it — first-time init or not — only the fields
      with no safe universal default are asked (identity basics, the
      mailbox address, the engine identity when nothing else answers it,
      a chosen CRM adapter, the destination directory); everything else
      is silently taken from `existing` (or its own hardcoded fallback) —
      a fast confirm pass instead of thirty re-typed answers. `--advanced`
      shows every prompt regardless of what is already known.

    The engine identity (WS URL, owner uid, the default account's uid) is
    the one place "essential" is computed PER FIELD rather than fixed: a
    unique mrcall-desktop descriptor on this machine, or a value already
    declared in `existing`, answers it with confidence, so a non-advanced
    run skips asking (descriptor) or silently reuses the declared value
    (existing) — but with NEITHER available (a genuinely first-time init,
    no descriptor, nothing declared yet) there is no safe default at all,
    so it is asked regardless of `--advanced`. `--advanced` always shows
    the prompt (prefilled from whichever of the two answered it), even
    when a unique descriptor would otherwise skip it silently — the whole
    point of `--advanced` is that nothing is silently assumed.

    Six phases, in order: identity -> mailbox -> engine -> accounts ->
    integrations (+ knobs) -> repo. Founder sweep is intentionally left
    exactly as it behaved before this refactor (pending a separate
    decision on what that feature becomes) — always asked, no
    existing-manifest prefill, no `--advanced` gating.
    """
    existing = existing or {}
    show_all = advanced

    print("Welcome to cs init - Let's set up your new company clone")
    print("=" * 60)
    if existing and not show_all:
        print(
            "Existing manifest.toml found — reusing its values; only asking "
            "what needs a fresh decision. Re-run with --advanced to see "
            "every prompt."
        )
    elif existing:
        print("Existing manifest.toml found — using its values as defaults below.")

    # A mrcall-desktop sign-in already on this machine prefills (and, when
    # it is the ONLY one and this is a fast pass, silently ANSWERS) the
    # engine-identity prompts below; the operator still sees and can
    # override every one of them under --advanced.
    defaults = descriptor_defaults()
    descriptor_unique = bool(defaults)
    if defaults:
        print(
            f"Found a mrcall-desktop profile: {defaults['descriptor_email']} "
            f"({defaults['engine_owner_uid']}) — using it for the engine identity."
        )

    config = {}

    # --- Phase 1: identity ---
    config["company_name"] = prompt_input(
        "Company name", _default(existing, "company_name", "Acme Corp")
    )
    config["company_display_name"] = _prompt_or_default(
        show_all, "Display name",
        _default(existing, "company_display_name", config["company_name"]),
    )
    config["company_from_name"] = _prompt_or_default(
        show_all, "From name for emails",
        _default(existing, "company_from_name", config["company_display_name"]),
    )

    # Derived slug — suggest the first word only: "ACME Corp" -> "acme"
    # (project folder "acme-cs/", state dir "~/.acme-cs/"). The full-name
    # slug ("acme-corp") made every reader of the old README learn why it
    # was a bad idea.
    full_slug = get_company_slug(config["company_name"])
    default_slug = _default(existing, "company_slug", full_slug.split("-")[0] or full_slug)
    while True:
        slug = prompt_input("Program slug for state dir", default_slug)
        if validate_slug(slug):
            config["company_slug"] = slug
            break
        else:
            print("Slug must contain only lowercase letters, numbers, and hyphens.")

    config["company_prog_name"] = _prompt_or_default(
        show_all, "Program name",
        _default(existing, "company_prog_name", f"{config['company_slug']}-cs"),
    )

    # --- Phase 2: mailbox ---
    config["email_address"] = prompt_input(
        "Operator email", _default(existing, "email_address", defaults.get("email_address"))
    )
    config["imap_host"] = _prompt_or_default(
        show_all, "IMAP host", _default(existing, "imap_host", "imap.gmail.com")
    )
    config["imap_port"] = _prompt_or_default_int(
        show_all, "IMAP port", _default(existing, "imap_port", 993)
    )
    config["smtp_host"] = _prompt_or_default(
        show_all, "SMTP host", _default(existing, "smtp_host", "smtp.gmail.com")
    )
    config["smtp_port"] = _prompt_or_default_int(
        show_all, "SMTP port", _default(existing, "smtp_port", 587)
    )

    # --- Phase 3: engine ---
    # No safe universal default exists for a company's own engine identity
    # (unlike imap_host, "wss://desktop.example.com" is not a working
    # fallback) — so these two are essential (asked regardless of
    # --advanced) UNLESS something already answers them with confidence:
    # a unique descriptor, or a value already declared in `existing`.
    existing_ws = existing.get("engine_ws_url") or ""
    existing_uid = existing.get("engine_owner_uid") or ""
    if descriptor_unique:
        ws_default, uid_default = defaults["engine_ws_url"], defaults["engine_owner_uid"]
    else:
        ws_default = existing_ws or "wss://desktop.example.com"
        uid_default = existing_uid

    if descriptor_unique and not show_all:
        config["engine_ws_url"] = ws_default
        config["engine_owner_uid"] = uid_default
    else:
        config["engine_ws_url"] = _prompt_or_default(
            show_all, "Engine WS URL", ws_default,
            essential=not (descriptor_unique or existing_ws),
        )
        # Skippable (blank = fill in manifest.toml by hand later) — matches
        # the mailbox-password contract; absence is a product state, not
        # a crash, everywhere downstream (ConfigError, printed once).
        config["engine_owner_uid"] = _prompt_or_default(
            show_all, "Engine owner UID", uid_default,
            essential=not (descriptor_unique or existing_uid),
        )
    # Not prompted: comes with the Step-0 descriptor (public key), consumed by
    # write_state_env; empty when there was no usable descriptor.
    config["firebase_web_api_key"] = defaults.get("firebase_web_api_key", "")

    # --- Phase 4: accounts ---
    existing_accounts = existing.get("accounts") or {}
    default_account_value = _default(existing, "accounts_default", "support")
    existing_default_uid = existing_accounts.get(default_account_value, "")
    default_uid_value = defaults.get("default_uid") or existing_default_uid

    if descriptor_unique and not show_all:
        default_account = default_account_value
        default_uid = defaults["default_uid"]
    else:
        default_account = _prompt_or_default(show_all, "Default account name", default_account_value)
        # Same "essential unless already answered" rule as the engine uid.
        default_uid = _prompt_or_default(
            show_all, f"Default account UID for '{default_account}'", default_uid_value,
            essential=not (descriptor_unique or existing_default_uid),
        )
    accounts = {default_account: default_uid}

    additional_default = ",".join(
        f"{n}:{u}" for n, u in existing_accounts.items() if n != default_account
    )
    additional = _prompt_or_default(
        show_all,
        "Additional accounts (comma-separated name:uid pairs, or empty)",
        additional_default,
    )
    if additional:
        for pair in additional.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if ":" not in pair:
                print(f"Invalid account format: {pair}, skipping")
                continue
            parts = pair.split(":", 1)
            if len(parts) != 2:
                print(f"Invalid account format: {pair}, skipping")
                continue
            name, uid = parts
            accounts[name] = uid

    config["accounts"] = accounts
    config["accounts_default"] = default_account

    # Founder sweep — left exactly as it behaved before this refactor.
    config["founder_sweep_enabled"] = prompt_yes_no("Enable founder sweep?", default=False)
    if config["founder_sweep_enabled"]:
        config["founder_sweep_account"] = prompt_input("Founder sweep account")
    else:
        config["founder_sweep_account"] = ""

    # --- Phase 5: integrations (+ knobs) ---
    # CRM adapter stays essential (always asked): a real clone can need a
    # non-default CRM (e.g. Shopify) wired at init time — unlike producer
    # below, "none" is not a safe universal assumption.
    while True:
        adapter = prompt_input(
            "CRM adapter (starchat, shopify, none)", _default(existing, "crm_adapter", "none")
        ).lower()
        if adapter in ("starchat", "shopify", "none"):
            config["crm_adapter"] = adapter
            break
        else:
            print("Please enter one of: starchat, shopify, none")

    existing_shopify = existing.get("crm_shopify") or {}
    if config["crm_adapter"] == "shopify":
        config["crm_shopify"] = {
            "api_version": _prompt_or_default(
                show_all, "Shopify API version", existing_shopify.get("api_version") or "2025-10"
            ),
            "env_prefix": _prompt_or_default(
                show_all, "Shopify environment prefix (optional)",
                existing_shopify.get("env_prefix", ""),
            ),
        }
    else:
        config["crm_shopify"] = None

    # Producer adapter — a producer's script/python entries are literal
    # filesystem paths on the host that runs it, so no clone can be wired
    # for one at init time. Hardcoded off, no prompt in any mode; a clone that
    # genuinely needs it edits manifest.toml by hand (clone-owned, never
    # touched by `cs update`).
    config["producer_adapter"] = "none"
    config["producer_mrcall_tracking"] = None

    # Campaign carve-out and Drive scope — niche knobs with no interactive
    # default worth asking for at init time. Hardcoded empty, no prompt in any
    # mode. (`posture_note` used to sit here; it was prose nothing read, and
    # the wizard reset it on every re-run — removed in v0.18.0.)
    config["excluded_campaign"] = ""
    config["drive_scope"] = ""

    # SMS — the proxy itself is Vonage, hardcoded, run from mrcall-desktop;
    # `cs init` never asks for its URL (nothing per-clone to configure).
    config["sms_enabled"] = _prompt_or_default_yn(
        show_all, "Enable SMS?", _default(existing, "sms_enabled", False)
    )

    # Cron — schedule/comment move to `cs cron install`; fixed values keep
    # manifest.toml and the rendered README self-consistent until then.
    config["cron_schedule"] = DEFAULT_CRON_SCHEDULE
    config["cron_comment"] = DEFAULT_CRON_COMMENT

    config["timezone"] = _prompt_or_default(
        show_all, "Timezone", _default(existing, "timezone", "Europe/Rome")
    )
    config["sms_hour"] = _prompt_or_default_int(
        show_all, "SMS hour", _default(existing, "sms_hour", 18)
    )
    config["reminder_max"] = _prompt_or_default_int(
        show_all, "Reminder max", _default(existing, "reminder_max", 3)
    )
    config["dedup_days"] = _prompt_or_default_int(
        show_all, "Dedup days", _default(existing, "dedup_days", 30)
    )
    # No "Rate cap" prompt: the per-day send quota was removed from the code in
    # v0.12.0 (it dropped contacts silently instead of stopping), and a wizard
    # that keeps asking for a number nothing reads sells control that does not
    # exist. CS_PAUSE is the stop; `cs config` is where the operator reads what
    # is actually in force.

    if show_all:
        while True:
            mode = prompt_input(
                "CS triage mode (draft, send)", _default(existing, "cs_triage_mode", "draft")
            ).lower()
            if mode in ("draft", "send"):
                config["cs_triage_mode"] = mode
                break
            else:
                print("Please enter one of: draft, send")
    else:
        config["cs_triage_mode"] = _default(existing, "cs_triage_mode", "draft")

    # No "Dry run" / "Autonomous" prompts: neither knob ever gated anything
    # (removed in v0.18.0). Dry-run is `--commit` on the send verbs; autonomy
    # is CS_TRIAGE_MODE plus the clone's own `.claude/settings.json`.

    # The two send-guard knobs and the system-sender exclusions are read by
    # live code (`cs/send_guard.py`, `cs/unanswered.py`) but are niche enough
    # that `cs init` does not ask. They are stamped at the kernel default so
    # the operator can SEE them in their own manifest.toml, and carried
    # through `existing` so a re-run of the wizard cannot silently reset an
    # operator's edit.
    _knob_defaults = manifest_mod.Knobs()
    config["system_senders"] = _default(
        existing, "system_senders", _knob_defaults.system_senders
    )
    config["send_guard_min_chars"] = _default(
        existing, "send_guard_min_chars", _knob_defaults.send_guard_min_chars
    )
    config["send_guard_banned_phrases"] = _default(
        existing, "send_guard_banned_phrases", _knob_defaults.send_guard_banned_phrases
    )

    config["platform_env_path"] = _prompt_or_default(
        show_all, "Platform environment path (optional)", ""
    )

    # No `firebase_sa_path` key: Settings derives ~/.<slug>-cs/firebase-sa.json
    # on its own the moment [engine].sa_path is empty, and manifest.toml.j2
    # writes that blank as a literal. The init_data key reached no template at
    # all, so it was pure weight in the frozen render input (removed v0.18.0).
    # The Settings field of the same name is very much alive — `cs/drive.py`
    # and `cs/resolve.py` load the service-account credential from it.

    # --- Phase 6: repo ---
    # Git remote — empty is a legitimate answer (local-only clone). The sole
    # consumer, manifest.toml.j2's [repo].git_remote, is a template-only field
    # (never parsed back into Settings — see manifest.py's module docstring)
    # and renders an empty string as valid TOML, so no downstream prose needs
    # adapting for the empty case.
    config["repo_git_remote"] = _prompt_or_default(
        show_all,
        "Git remote URL (empty = local-only, add one later with `git remote add`)",
        _default(existing, "repo_git_remote", ""),
    )

    # Destination directory (runtime only — stripped before template-manifest).
    # Re-running inside an already-stamped clone (`existing` non-empty)
    # defaults to "." (re-stamp in place); a first-time init still defaults
    # to a new `<slug>-cs` sibling directory.
    default_dest = "." if existing else f"{config['company_slug']}-cs"
    while True:
        dest = prompt_input("Destination directory", default_dest)
        dest_path = Path(dest).expanduser()
        if dest_path.exists():
            if dest_path.is_dir() and any(dest_path.iterdir()):
                overwrite = prompt_yes_no(
                    f"Directory '{dest}' exists and is not empty. Overwrite?",
                    default=False,
                )
                if overwrite:
                    break
                continue
            break
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        break
    config["dest_dir"] = str(dest_path.resolve())

    # Repo kernel version — the pin `cs init` stamps into the new clone's
    # requirements.txt. No longer a prompt, any mode: a hand-typed literal
    # here went stale twice in one day (2026-08-19: "0.6.1", then "0.7.1"
    # hours before v0.8.x shipped) before this became automatic. The only
    # correct value is the version of the kernel running this wizard,
    # always available except on a source checkout with no installed
    # metadata — that edge case now warns instead of looping forever.
    version = kernel_version_bare()
    if not version:
        print(
            "Warning: could not determine the installed cs-kernel version — "
            "requirements.txt will pin an empty version; edit the version "
            "pin in requirements.txt by hand."
        )
    config["repo_kernel_version"] = version

    # Repo docs shape (generic = mother/kernel-canonical; as-built = a
    # stamped clone). No longer a prompt: every `cs init` output IS a
    # stamped clone — "generic" only ever describes the kernel's own
    # reference copy, which this wizard never produces.
    config["repo_docs_shape"] = "as-built"

    # Show summary and confirm
    print("\n" + "=" * 60)
    print("Configuration Summary")
    print("=" * 60)
    for key, value in config.items():
        if key == 'accounts':
            print("  accounts:")
            for name, uid in value.items():
                print(f"    {name}: {uid}")
        elif key.endswith('_enabled') or key.endswith('_enabled') or isinstance(value, bool):
            print(f"  {key}: {value}")
        elif key == 'crm_shopify' and value is not None:
            print("  crm_shopify:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        elif key == 'producer_mrcall_tracking' and value is not None:
            print("  producer_mrcall_tracking:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    return config

def is_executable_target(rel_dir: Path, template_name: str) -> bool:
    """A rendered/copied file that lives under a `bin/` directory, or whose
    source template is named `*.sh.j2`, is a shell script the operator's
    crontab (or a doc) tells them to invoke directly. Shared by
    `render_templates` (cs init) and `cs update`'s write path so both leave
    the file executable — a non-executable cron wrapper fails SILENTLY in
    cron ("Permission denied"), which reads as "the product does nothing"
    rather than as a permissions bug.
    """
    return "bin" in rel_dir.parts or template_name.endswith(".sh.j2")


# Stamped paths whose CONTENT is meant to diverge per company. The kernel writes
# one only when the clone has none; from then on it is the operator's prose and
# nothing here touches it again — no overwrite, no prompt, no checksum.
#
# `company/` was tracked like every other render until 2026-08-24, and the
# arithmetic of that is unforgiving: the operator is TOLD to author these files,
# so every authored slot differs from its stored checksum permanently. Any
# release that reworded a slot then asked "modified locally AND template
# changed. Overwrite? [y/N/diff]" about each of them, at every single update,
# for ever — a prompt whose only correct answer is always No, which is exactly
# the kind of prompt an operator learns to answer without reading. And answering
# it wrong once destroys prose no template can regenerate.
#
# `docs/active-context.md` is the same class arrived at from the other end. Its
# template is a seven-line SEED — three empty headings and
# `doc_baseline_commit: INITIAL` — whose entire purpose is to be replaced by the
# clone's own live state on day one. A checksum for it therefore asserts a match
# that can never hold again on any clone, and it left one prompt on the table
# whose "y" deletes the clone's state document. The kernel has nothing to push
# into that file; it only has to make sure a new clone starts with one.
#
# Consequence for the checksum ledger: a path matched here is never written into
# `file_checksums`. A clone whose manifest still lists one (both existing clones
# do) drops that stale entry on its next `cs update`, and nothing reads it in
# the meantime — `cs update` returns from this class before it consults the
# stored checksums at all. Same treatment `requirements.txt` and `manifest.toml`
# already get.
#
# Entries are matched with `startswith`, so a member is either a directory
# prefix (`company/`) or one whole path (`docs/active-context.md`).
CLONE_AUTHORED_PREFIXES = ("company/", "docs/active-context.md")


def is_clone_authored(out_rel) -> bool:
    """True for a stamped path whose content belongs to the clone operator.

    `out_rel` is the path RELATIVE to the clone root, as a string or a Path.
    """
    return str(out_rel).replace(os.sep, "/").startswith(CLONE_AUTHORED_PREFIXES)


def toml_quote(value) -> str:
    """Render `value` as a TOML basic string, quotes included — safe as
    either a key or a value.

    A bare TOML key only allows `[A-Za-z0-9_-]`; an account name that is an
    email (e.g. `jane.doe@acme.example` — the documented, RECOMMENDED
    shape, "prefer the mailbox address, never a bare first name") breaks
    the parser the moment it renders unquoted (`@` is illegal in a bare
    key, confirmed live: "manifest.toml is not valid TOML"). Quoting every
    rendered key/value here is simpler than knowing in advance which
    strings happen to be bare-safe and getting it wrong once.
    """
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return f'"{s}"'


def render_templates(config: dict, template_dir: Path, dest_dir: Path):
    """Render Jinja2 templates and copy other files to destination."""
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined
    )
    jinja_env.filters["toml_quote"] = toml_quote

    # Create destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Track file checksums
    file_checksums = {}
    success = True
    
    # Walk through template directory
    for template_path in template_dir.rglob('*'):
        if template_path.is_dir():
            continue
        
        # Compute relative path and destination path
        rel_path = template_path.relative_to(template_dir)
        dest_path = dest_dir / rel_path
        
        # Remove .j2 extension if present
        if dest_path.suffix == '.j2':
            dest_path = dest_path.with_suffix('')
        
        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # A clone-authored file the operator already has is never re-stamped and
        # never checksummed — `cs init` re-run in place (the documented restamp,
        # dest_dir "." on an existing clone) would otherwise overwrite it with
        # the blank template, silently.
        rel_dest = dest_path.relative_to(dest_dir)
        if is_clone_authored(rel_dest) and dest_path.exists():
            print(f"Kept: {rel_dest} (yours — clone-authored, never re-stamped)")
            continue

        try:
            if template_path.suffix == '.j2':
                # Render template
                template = jinja_env.get_template(str(rel_path))
                render_vars = {k: v for k, v in config.items() if k != 'dest_dir'}
                content = template.render(**render_vars)
                dest_path.write_text(content, encoding='utf-8')
                print(f"Rendered: {rel_path} -> {dest_path.relative_to(dest_dir.parent)}")
            else:
                # Copy non-template file
                dest_path.write_bytes(template_path.read_bytes())
                print(f"Copied: {rel_path} -> {dest_path.relative_to(dest_dir.parent)}")

            # A file rendered/copied under bin/ (or sourced from a *.sh.j2
            # template) is a shell script the operator's crontab is told to
            # invoke directly. write_text/write_bytes leaves it mode 0644;
            # cron then fails SILENTLY with "Permission denied", which reads
            # to the operator as "the product does nothing" rather than as a
            # permissions bug. Make it executable.
            if is_executable_target(rel_path.parent, template_path.name):
                dest_path.chmod(0o755)

            # Calculate checksum for rendered/copy file. Clone-authored slots
            # are deliberately absent from the ledger: their content is meant
            # to diverge, so a stored checksum only ever produces a permanent
            # false conflict at `cs update` time.
            if not is_clone_authored(rel_dest):
                file_content = dest_path.read_bytes()
                file_hash = hashlib.sha256(file_content).hexdigest()
                file_checksums[str(rel_dest)] = f"sha256:{file_hash}"
        except jinja2.TemplateError as e:
            print(f"Template error rendering {rel_path}: {e}", file=sys.stderr)
            success = False
        except OSError as e:
            print(f"OS error copying {rel_path}: {e}", file=sys.stderr)
            success = False
            
    return success, file_checksums

def write_state_env(config: dict, dest_dir: Path) -> None:
    """Write `~/.<slug>-cs/.env` from the freshly rendered `.env.example`.

    The wizard already knows almost everything the secrets file asks for —
    `CS_ACCOUNTS` from the accounts registry, `FIREBASE_WEB_API_KEY` from the
    Step-0 descriptor — so the operator should not have to copy a file and
    hand-edit it. The mailbox app password is the ONE real secret; it is
    prompted here without echo. Contract:

    - an existing `.env` is operator-owned and NEVER touched (same rule as
      the clone's requirements.txt in `cs update`);
    - EOF / ^C on the password prompt resolves to writing the file with
      `EMAIL_PASSWORD` blank, and the decision is printed — the wizard never
      crashes on a closed stdin (the v0.5.2 EOF contract);
    - the file lands mode 0600 in a 0700 state dir, regardless of umask.
    """
    state_dir = Path.home() / f".{config['company_slug']}-cs"
    env_path = state_dir / ".env"
    if env_path.exists():
        print(f"Kept existing {env_path} untouched (operator-owned).")
        return
    example = Path(dest_dir) / ".env.example"
    try:
        content = example.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Skipped writing {env_path}: cannot read {example}: {e}", file=sys.stderr)
        return
    try:
        password = getpass.getpass(
            f"Mailbox app password for {config['email_address']} "
            f"(Enter to leave blank and fill {env_path} later): "
        )
    except (EOFError, KeyboardInterrupt):
        print(f"\nNo password given — writing {env_path} with EMAIL_PASSWORD blank.")
        password = ""
    values = {
        "EMAIL_PASSWORD": password,
        "FIREBASE_WEB_API_KEY": config.get("firebase_web_api_key", ""),
        "CS_ACCOUNTS": ",".join(f"{n}:{u}" for n, u in config["accounts"].items()),
    }
    lines = []
    filled = set()
    for line in content.splitlines():
        key = line.split("=", 1)[0]
        if "=" in line and key in values and not line.lstrip().startswith("#"):
            lines.append(f"{key}={values[key]}")
            filled.add(key)
        else:
            lines.append(line)
    # A missing anchor is a template regression; still land the value rather
    # than silently dropping a secret the operator just typed.
    for key, value in values.items():
        if key not in filled:
            lines.append(f"{key}={value}")
    state_dir.mkdir(parents=True, exist_ok=True)
    state_dir.chmod(0o700)
    env_path.touch(mode=0o600)
    env_path.chmod(0o600)  # touch honours umask; the mode must not
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    note = "" if password else " EMAIL_PASSWORD left blank — add it before SMTP/IMAP verbs."
    print(f"Wrote {env_path} (mode 0600).{note}")


def _venv_python(dest_dir: Path) -> Path:
    if os.name == "nt":
        return dest_dir / ".venv" / "Scripts" / "python.exe"
    return dest_dir / ".venv" / "bin" / "python"


def _manual_install_lines(dest_dir: Path) -> str:
    return (
        f"  cd {dest_dir}\n"
        f"  uv venv .venv && source .venv/bin/activate  # Windows: .venv\\Scripts\\activate\n"
        f"  uv pip install -r requirements.txt"
    )


CODEX_PROMPTS = Path("~/.codex/prompts").expanduser()


def _link_or_copy(link: Path, target: Path, rel: str) -> str:
    """Point *link* at *target*, preferring a symlink.

    Symlink, not copy, because a copy is a second source that drifts: this
    repo shipped `.opencode/commands/` as tracked copies for six weeks and
    they were still advertising the pre-rename command names long after
    `.claude/commands/` had been renamed. One content source is the only
    arrangement in which that cannot recur.

    Windows without Developer Mode refuses `os.symlink` — fall back to a
    copy there and SAY so, rather than failing a stamp over it.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        if link.is_symlink() and os.path.realpath(link) == os.path.realpath(target):
            return "ok"
        link.unlink() if link.is_symlink() or link.is_file() else shutil.rmtree(link)
    try:
        link.symlink_to(rel)
        return "ok"
    except OSError:
        if target.is_dir():
            shutil.copytree(target, link)
        else:
            shutil.copy2(target, link)
        return "copied"


def install_agent_surfaces(dest_dir: Path, *, ask: bool = True) -> None:
    """Give OpenCode and Codex the SAME commands Claude Code has.

    `.claude/` is the one place the kernel renders; every other agent's
    surface points back into it:

    - `.opencode/commands/*.md` and `.opencode/skills` → into `.claude/`
      (OpenCode reads project-level `.opencode/commands/`, plural);
    - `AGENTS.md` → `CLAUDE.md` (the file BOTH OpenCode and Codex read as
      their project instructions);
    - `~/.codex/prompts/*.md` → the clone's commands. Codex has no
      project-level prompt directory — its prompts are per-USER — so this
      is a home-global namespace shared by every clone on the machine.
      That is why it is the one place this function asks: pointing it at
      this clone silently would hijack another clone's `/cs-review`.
    """
    claude_cmds = dest_dir / ".claude" / "commands"
    if not claude_cmds.is_dir():
        return
    copied = False

    for src in sorted(claude_cmds.glob("*.md")):
        state = _link_or_copy(dest_dir / ".opencode" / "commands" / src.name,
                              src, f"../../.claude/commands/{src.name}")
        copied |= state == "copied"
    if (dest_dir / ".claude" / "skills").is_dir():
        copied |= _link_or_copy(dest_dir / ".opencode" / "skills",
                                dest_dir / ".claude" / "skills",
                                "../.claude/skills") == "copied"
    if (dest_dir / "CLAUDE.md").is_file():
        copied |= _link_or_copy(dest_dir / "AGENTS.md",
                                dest_dir / "CLAUDE.md", "CLAUDE.md") == "copied"
    print("Wired OpenCode (.opencode/) and AGENTS.md to the same commands"
          + (" — copied, this filesystem refuses symlinks" if copied else ""))

    # --- Codex: one shared home directory for every clone on this machine ---
    ours = [p for p in sorted(claude_cmds.glob("*.md"))]
    foreign = []
    for src in ours:
        dst = CODEX_PROMPTS / src.name
        if dst.exists() or dst.is_symlink():
            if os.path.realpath(dst) != os.path.realpath(src):
                foreign.append(dst)
    if foreign and ask:
        other = os.path.realpath(foreign[0])
        try:
            answer = input(
                f"Codex prompts (~/.codex/prompts) already point at another "
                f"project:\n  {other}\nPoint them at {dest_dir.name} instead? [y/N]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nNo answer — leaving Codex pointed where it was.")
            return
        if answer not in ("y", "yes"):
            print(f"Left Codex pointed at {other}.")
            return
    for src in ours:
        _link_or_copy(CODEX_PROMPTS / src.name, src, str(src.resolve()))
    print(f"Wired Codex prompts (~/.codex/prompts) to {dest_dir.name}.")


def offer_project_install(dest_dir: Path) -> None:
    """After `cs init` stamps the project, OFFER to create its venv and
    install the pinned kernel right here — collapsing the manual `cd
    <dir> && uv venv .venv && source … && uv pip install -r
    requirements.txt` (README step 3) into one confirmed step.

    EOF/^C on the prompt (closed stdin — the v0.5.2 EOF contract)
    resolves to No, prints the decision, and hands back the manual
    steps; nothing runs without an explicit "y". Uses `uv venv` +
    `uv pip install --python <venv>` (Step 1 already required `uv`) so
    no shell activation is needed for the install itself — the operator
    still sources the venv afterwards to actually use `cs`.
    """
    try:
        answer = input(
            f"\nInstall the project now (creates {dest_dir}/.venv and "
            f"installs the pinned kernel)? [y/N]: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo answer — skipping install. Run it yourself:")
        print(_manual_install_lines(dest_dir))
        return
    if answer not in ("y", "yes"):
        print("Skipping install. Run it yourself:")
        print(_manual_install_lines(dest_dir))
        return

    print(f"Creating venv in {dest_dir}/.venv …")
    proc = subprocess.run(["uv", "venv", ".venv"], cwd=dest_dir)
    if proc.returncode != 0:
        print(
            "uv venv FAILED — install by hand:\n" + _manual_install_lines(dest_dir),
            file=sys.stderr,
        )
        return

    print("Installing the pinned kernel …")
    proc = subprocess.run(
        ["uv", "pip", "install", "--python", str(_venv_python(dest_dir)),
         "-r", "requirements.txt"],
        cwd=dest_dir,
    )
    if proc.returncode != 0:
        print(
            "pip install FAILED — the venv exists; finish by hand:\n"
            f"  cd {dest_dir} && source .venv/bin/activate && "
            "uv pip install -r requirements.txt",
            file=sys.stderr,
        )
        return
    print(f"Installed. Next: cd {dest_dir} && source .venv/bin/activate && cs login")


def cmd_init(argv=None) -> int:
    """Main entry point for the init command."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(prog='cs init')
    parser.add_argument('--version', action='version', version=kernel_version())
    parser.add_argument(
        '--advanced', action='store_true',
        help="show every prompt, even ones with a known-good default (an "
             "existing manifest.toml's own values, or a unique mrcall-desktop "
             "descriptor's engine identity). Without it, cs init run inside an "
             "already-stamped clone only re-asks what has no safe default.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 1)

    # Import cs to find template directory
    try:
        import cs
        template_root = Path(cs.__file__).parent / 'templates' / 'project'
    except ImportError:
        print("Error: cannot import cs module to find templates", file=sys.stderr)
        return 1

    if not template_root.exists():
        print(f"Error: template directory not found at {template_root}", file=sys.stderr)
        return 1

    # An existing manifest.toml in the CURRENT directory means this is a
    # re-run inside an already-stamped clone, not a first-time init — see
    # collect_config's docstring for what that changes.
    existing = load_existing_config(Path.cwd())

    # Collect configuration
    try:
        config = collect_config(advanced=args.advanced, existing=existing)
        proceed = prompt_yes_no("Proceed with these settings?", default=True)
    except EOFError:
        print(
            "cs init: input ended before the wizard finished — run it in an "
            "interactive terminal and answer the prompts",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\ncs init: cancelled", file=sys.stderr)
        return 130

    # Confirm before proceeding
    if not proceed:
        print("Initialization cancelled.")
        return 1
    
    # Extract dest_dir from config
    dest_dir = Path(config['company_slug'] + '-cs')
    if 'dest_dir' in config:
        dest_dir = Path(config['dest_dir'])
    
    # Render templates
    success, file_checksums = render_templates(config, template_root, dest_dir)
    if not success:
        print("Failed to render templates", file=sys.stderr)
        return 1
    
    # Create template-manifest.json
    manifest = {
        "template_version": "1",
        "created": datetime.utcnow().isoformat() + "Z",
        "init_data": {k: v for k, v in config.items() if k != 'dest_dir'},
        "file_checksums": file_checksums
    }
    
    # Write manifest to destination
    manifest_path = dest_dir / "template-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Wrote template-manifest.json")
    
    # Initialize git repository
    git_dir = dest_dir / '.git'
    if not git_dir.exists():
        try:
            result = os.system(f"cd '{dest_dir}' && git init")
            if result != 0:
                print(f"Warning: failed to initialize git repository")
        except Exception as e:
            print(f"Warning: error during git init: {e}")
    
    # Secrets file — after the stamp so the rendered .env.example exists.
    write_state_env(config, dest_dir)

    # Every agent surface points at the one rendered set (.claude/).
    install_agent_surfaces(dest_dir)

    # Print post-init instructions
    print("\n" + "=" * 60)
    print("Initialization Complete")
    print("=" * 60)
    print(f"Done! Your secrets live in '~/.{config['company_slug']}-cs/.env' (never commit it)")
    print(f"Its reference copy is: {dest_dir}/.env.example")

    offer_project_install(dest_dir)

    return 0

if __name__ == "__main__":
    sys.exit(cmd_init())