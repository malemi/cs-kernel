"""
Module for initializing a new company clone from templates.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
import hashlib
from datetime import datetime
import jinja2

from ._version import kernel_version
from . import login

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
    }

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

def collect_config() -> dict:
    """Collect configuration through interactive prompts."""
    print("Welcome to cs init - Let's set up your new company clone")
    print("=" * 60)

    # A mrcall-desktop sign-in already on this machine prefills the
    # engine-identity prompts below; the operator still sees and can
    # override every one of them.
    defaults = descriptor_defaults()
    if defaults:
        print(
            f"Found a mrcall-desktop profile: {defaults['descriptor_email']} "
            f"({defaults['engine_owner_uid']}) — using it for defaults."
        )

    config = {}
    
    # Basic company info
    config["company_name"] = prompt_input("Company name", "Acme Corp")
    config["company_display_name"] = prompt_input("Display name", config["company_name"])
    config["company_from_name"] = prompt_input("From name for emails", config["company_display_name"])
    
    # Derived slug
    default_slug = get_company_slug(config["company_name"])
    while True:
        slug = prompt_input("Program slug for state dir", default_slug)
        if validate_slug(slug):
            config["company_slug"] = slug
            break
        else:
            print("Slug must contain only lowercase letters, numbers, and hyphens.")
    
    # Program name
    default_prog_name = f"{config['company_slug']}-cs"
    config["company_prog_name"] = prompt_input("Program name", default_prog_name)
    
    # Operator email
    config["email_address"] = prompt_input("Operator email", defaults.get("email_address"))
    
    # IMAP/SMTP settings
    config["imap_host"] = prompt_input("IMAP host", "imap.gmail.com")
    try:
        config["imap_port"] = int(prompt_input("IMAP port", "993"))
    except ValueError:
        print("Invalid port number, using default 993")
        config["imap_port"] = 993
    
    config["smtp_host"] = prompt_input("SMTP host", "smtp.gmail.com")
    try:
        config["smtp_port"] = int(prompt_input("SMTP port", "587"))
    except ValueError:
        print("Invalid port number, using default 587")
        config["smtp_port"] = 587
    
    # Engine settings
    config["engine_ws_url"] = prompt_input(
        "Engine WS URL", defaults.get("engine_ws_url", "wss://desktop.example.com")
    )
    config["engine_owner_uid"] = prompt_input("Engine owner UID", defaults.get("engine_owner_uid"))

    # Accounts
    default_account = prompt_input("Default account name", "support")
    default_uid = prompt_input(
        f"Default account UID for '{default_account}'", defaults.get("default_uid")
    )
    accounts = {default_account: default_uid}
    
    additional = prompt_input("Additional accounts (comma-separated name:uid pairs, or empty)", "")
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
    
    # Founder sweep
    config["founder_sweep_enabled"] = prompt_yes_no("Enable founder sweep?", default=False)
    if config["founder_sweep_enabled"]:
        config["founder_sweep_account"] = prompt_input("Founder sweep account")
    else:
        config["founder_sweep_account"] = ""
    
    # CRM adapter
    while True:
        adapter = prompt_input("CRM adapter (starchat, shopify, none)", "none").lower()
        if adapter in ("starchat", "shopify", "none"): 
            config["crm_adapter"] = adapter
            break
        else:
            print("Please enter one of: starchat, shopify, none")
            
    if config["crm_adapter"] == "shopify":
        shopify_config = {
            "api_version": prompt_input("Shopify API version", "2025-10"),
            "env_prefix": prompt_input("Shopify environment prefix (optional)", "")
        }
        config["crm_shopify"] = shopify_config
    else:
        config["crm_shopify"] = None
    
    # Producer adapter
    while True:
        adapter = prompt_input("Producer adapter (mrcall-tracking, none)", "none").lower()
        if adapter in ("mrcall-tracking", "none"): 
            config["producer_adapter"] = adapter
            break
        else:
            print("Please enter one of: mrcall-tracking, none")
            
    if config["producer_adapter"] == "mrcall-tracking":
        tracking_config = {
            "script_path": prompt_input("Producer script path"),
            "python_path": prompt_input("Producer Python path")
        }
        config["producer_mrcall_tracking"] = tracking_config
    else:
        config["producer_mrcall_tracking"] = None
    
    # Campaign settings
    config["excluded_campaign"] = prompt_input("Excluded campaign name (optional)", "")
    config["posture_note"] = prompt_input("Posture note (optional)", "")
    
    # Drive scope
    config["drive_scope"] = prompt_input("Drive scope (optional)", "")
    
    # SMS settings
    config["sms_enabled"] = prompt_yes_no("Enable SMS?", default=False)
    if config["sms_enabled"]:
        config["sms_proxy_base"] = prompt_input("SMS proxy base URL")
    else:
        config["sms_proxy_base"] = ""
    
    # Cron schedule
    config["cron_schedule"] = prompt_input("Cron schedule", "0 6-18/2 * * 2-5")
    config["cron_comment"] = prompt_input("Cron comment", "cs-operator")
    
    # Git remote — empty is a legitimate answer (local-only clone). The sole
    # consumer, manifest.toml.j2's [repo].git_remote, is a template-only field
    # (never parsed back into Settings — see manifest.py's module docstring)
    # and renders an empty string as valid TOML, so no downstream prose needs
    # adapting for the empty case.
    config["repo_git_remote"] = prompt_input(
        "Git remote URL (empty = local-only, add one later with `git remote add`)", ""
    )
    
    # Destination directory (runtime only — stripped before template-manifest)
    default_dest = f"{config['company_slug']}-cs"
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

    # Timezone and SMS settings
    config["timezone"] = prompt_input("Timezone", "Europe/Rome")
    try:
        config["sms_hour"] = int(prompt_input("SMS hour", "18"))
    except ValueError:
        print("Invalid hour, using default 18")
        config["sms_hour"] = 18
        
    try:
        config["reminder_max"] = int(prompt_input("Reminder max", "3"))
    except ValueError:
        print("Invalid number, using default 3")
        config["reminder_max"] = 3
    
    # Knobs with defaults
    config["dedup_days"] = int(prompt_input("Dedup days", "30"))
    config["rate_cap"] = int(prompt_input("Rate cap", "25"))
    
    while True:
        mode = prompt_input("CS triage mode (draft, send)", "draft").lower()
        if mode in ("draft", "send"): 
            config["cs_triage_mode"] = mode
            break
        else:
            print("Please enter one of: draft, send")
            
    config["dry_run"] = prompt_yes_no("Dry run mode?", default=True)
    config["autonomous"] = prompt_yes_no("Autonomous mode?", default=False)
    
    # Platform env path
    config["platform_env_path"] = prompt_input("Platform environment path (optional)", "")
    
    # Firebase SA path
    config["firebase_sa_path"] = prompt_input("Firebase service account path", f"~/.{config['company_slug']}-cs/firebase-sa.json")
    
    # Repo kernel version
    # Default = the current operational pin the wizard should hand a new clone.
    # Nothing enforces this automatically — no onboarding gate checks it against
    # README or CHANGELOG. Bump it by hand at each release, in lockstep with
    # README step 1 and the CHANGELOG entry.
    config["repo_kernel_version"] = prompt_input("Repository kernel version", "0.7.1")

    # Repo docs shape (generic = mother/kernel-canonical; as-built = a stamped clone)
    config["repo_docs_shape"] = prompt_input("Repository docs shape (generic, as-built)", "generic")
    
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


def render_templates(config: dict, template_dir: Path, dest_dir: Path):
    """Render Jinja2 templates and copy other files to destination."""
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined
    )
    
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

            # Calculate checksum for rendered/copy file
            file_content = dest_path.read_bytes()
            file_hash = hashlib.sha256(file_content).hexdigest()
            # Use relative path from dest_dir
            rel_dest_path = dest_path.relative_to(dest_dir)
            file_checksums[str(rel_dest_path)] = f"sha256:{file_hash}"
        except jinja2.TemplateError as e:
            print(f"Template error rendering {rel_path}: {e}", file=sys.stderr)
            success = False
        except OSError as e:
            print(f"OS error copying {rel_path}: {e}", file=sys.stderr)
            success = False
            
    return success, file_checksums

def cmd_init(argv=None) -> int:
    """Main entry point for the init command."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(prog='cs init')
    parser.add_argument('--version', action='version', version=kernel_version())
    
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
    
    # Collect configuration
    try:
        config = collect_config()
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
    
    # Print post-init instructions
    print("\n" + "=" * 60)
    print("Initialization Complete")
    print("=" * 60)
    print(f"Done! Enter '{dest_dir.name}/' and set up your secrets in '~/.{config['company_slug']}-cs/.env'")
    print(f"The .env.example file is at: {dest_dir}/.env.example")
    print(f"Run `pip install -r {dest_dir}/requirements.txt` to install the kernel")
    
    return 0

if __name__ == "__main__":
    sys.exit(cmd_init())