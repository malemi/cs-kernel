"""manifest.toml — the COMPLETE declared per-company variance, loaded here.

The manifest is the ONLY place a company value (mailbox, brand, slug,
scope, adapter choice, campaign carve-out…) may live: the kernel package
carries none (charter + CI grep gate). `cs.config.load()` finds it at the
stamped-repo root (`./manifest.toml`, overridable via `$CS_MANIFEST` for
sandboxed tests), validates it, and feeds it to `Settings` as the
lowest-priority value layer:

    process env  >  repo .env  >  ~/.<slug>-cs/.env  >  platform env file
                 >  manifest.toml  >  kernel defaults

Hard exclusions (kernel invariants, deliberately NOT manifest fields):
the send boundary, the cron deny-list, the Gmail-Sent dedup ground truth,
engine RPC shapes, the module path `cs` (`prog_name` is display-only),
USER_NOTES policy (engine-side), and secret VALUES (the manifest names
required env KEYS only).

Template-only tables ([skills], [extensions], [repo], [cron]) are
tolerated and ignored at runtime — they are consumed by the stamping
template, not by the kernel.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, ValidationError


class ManifestError(RuntimeError):
    """manifest.toml is missing-but-required, unparsable, or invalid.
    Raised LOUD at config load — never at the first dossier."""


class _Table(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Company(_Table):
    name: str = ""
    display_name: str = ""
    from_name: str = ""          # From: display-name on fixed-template bulk
    slug: str = ""               # derives ~/.<slug>-cs and every state path
    prog_name: str = ""          # argparse prog — DISPLAY ONLY (module path stays `cs`)


class Operator(_Table):
    email_address: str = ""      # also derives SELF cc + dedup identity prints
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587


class FounderSweep(_Table):
    enabled: bool = False
    account: str = ""


class Engine(_Table):
    owner_uid: str = ""          # daemon gates token.sub == this
    ws_url: str = ""             # e.g. wss://<engine-host>; client appends /ws/<uid>
    sa_path: str = ""            # service-account key; default derives from slug
    # names + default; REAL uids live in the env layer (CS_ACCOUNTS)
    accounts: dict[str, str] = {}
    founder_sweep: FounderSweep = FounderSweep()


class CrmShopify(_Table):
    api_version: str = "2025-10"
    env_prefix: str = ""         # env keys <PREFIX>_STORE_DOMAIN/_CLIENT_ID/_SECRET
                                 # (+ optional <PREFIX>_ADMIN_TOKEN); bare SHOPIFY_* fallback


class Crm(_Table):
    adapter: str = "none"        # validated against cs.crm registry at config load
    shopify: Optional[CrmShopify] = None


class ProducerMrcallTracking(_Table):
    script_path: str = ""
    python_path: str = ""


class Producer(_Table):
    adapter: str = "none"        # validated against cs.ingest registry at config load
    mrcall_tracking: Optional[ProducerMrcallTracking] = None


class Campaigns(_Table):
    # Comma-separated campaign names a dedicated process owns; "" = none. A
    # single bare name is the one-element case, so clones written before the
    # list existed need no edit. Matching is exact per name, never by prefix.
    excluded_campaign: str = ""
    posture_note: str = ""       # prose for humans, not code-consumed


class Knobs(_Table):
    dedup_days: int = 30
    cs_triage_mode: str = "draft"   # draft | send — bounded by the send-boundary invariant
    dry_run: bool = True
    autonomous: bool = False
    timezone: str = "Europe/Rome"
    sms_hour: int = 18
    reminder_max: int = 3
    system_senders: str = ""        # comma-separated no-reply/system addresses the
                                    # `unanswered` sweep ignores (env CS_SYSTEM_SENDERS wins)
    # cs/send_guard.py — the only two per-company knobs of the model-output
    # send guard. The banned list EXTENDS the kernel's (it never replaces it:
    # the kernel phrases out the writer as an AI, which no company wants sent).
    send_guard_min_chars: int = 40
    send_guard_banned_phrases: str = ""   # comma-separated (env CS_SEND_GUARD_BANNED wins)


class Sms(_Table):
    enabled: bool = False
    proxy_base: str = ""         # full send-endpoint URL of the SMS proxy
                                 # (env key SMS_BUSINESS_ID iff enabled)


class Drive(_Table):
    scope: str = ""              # Shared Drive name/id; `all` stays a test-only CLI override


class EnvTable(_Table):
    platform_env_path: str = ""  # optional lowest-precedence env layer


class Manifest(_Table):
    company: Company = Company()
    operator: Operator = Operator()
    engine: Engine = Engine()
    crm: Crm = Crm()
    producer: Producer = Producer()
    campaigns: Campaigns = Campaigns()
    knobs: Knobs = Knobs()
    sms: Sms = Sms()
    drive: Drive = Drive()
    env: EnvTable = EnvTable()


def find_manifest_path() -> Path | None:
    """Locate manifest.toml: `$CS_MANIFEST` (must exist if set — never silently
    substituted), else `./manifest.toml` in the cwd (the stamped-repo root,
    where every permission string runs from). None = no manifest (identity-
    bearing verbs will fail loudly downstream; `--help` still works)."""
    explicit = os.environ.get("CS_MANIFEST", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise ManifestError(f"CS_MANIFEST points to a missing file: {p}")
        return p
    p = Path("manifest.toml")
    return p if p.exists() else None


def load_manifest(path: Path) -> Manifest:
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as e:
        raise ManifestError(f"cannot read {path}: {e}") from None
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"{path} is not valid TOML: {e}") from None
    try:
        return Manifest.model_validate(data)
    except ValidationError as e:
        raise ManifestError(f"{path} failed validation:\n{e}") from None


def settings_overrides(m: Manifest) -> dict:
    """Flatten the manifest into Settings field values (the manifest layer).

    Empty strings mean "not declared" and are skipped, so kernel defaults
    (e.g. imap.gmail.com) survive a sparse manifest; numeric/bool knobs are
    always carried (their sub-model defaults equal the kernel defaults, so
    an omitted table is a no-op)."""
    out: dict = {}

    def put(key: str, val) -> None:
        if isinstance(val, str):
            if val:
                out[key] = val
        elif val is not None:
            out[key] = val

    put("company_name", m.company.name)
    put("company_display_name", m.company.display_name)
    put("email_from_name", m.company.from_name)
    put("slug", m.company.slug)
    put("prog_name", m.company.prog_name)

    put("email_address", m.operator.email_address)
    put("imap_host", m.operator.imap_host)
    put("imap_port", m.operator.imap_port)
    put("smtp_host", m.operator.smtp_host)
    put("smtp_port", m.operator.smtp_port)

    put("engine_owner_uid", m.engine.owner_uid)
    put("engine_ws_url", m.engine.ws_url)
    put("firebase_sa_path", m.engine.sa_path)
    put("accounts_default", m.engine.accounts.get("default", ""))
    put("founder_sweep_enabled", m.engine.founder_sweep.enabled)
    put("founder_sweep_account", m.engine.founder_sweep.account)

    put("crm_adapter", m.crm.adapter)
    if m.crm.shopify is not None:
        put("shopify_api_version", m.crm.shopify.api_version)
        put("shopify_env_prefix", m.crm.shopify.env_prefix)

    put("producer_adapter", m.producer.adapter)
    if m.producer.mrcall_tracking is not None:
        put("agent_prompt_py", m.producer.mrcall_tracking.script_path)
        put("agent_prompt_python", m.producer.mrcall_tracking.python_path)

    put("excluded_campaign", m.campaigns.excluded_campaign)

    put("dedup_days", m.knobs.dedup_days)
    put("cs_triage_mode", m.knobs.cs_triage_mode)
    put("dry_run", m.knobs.dry_run)
    put("autonomous", m.knobs.autonomous)
    put("timezone", m.knobs.timezone)
    put("sms_hour", m.knobs.sms_hour)
    put("reminder_max", m.knobs.reminder_max)
    put("system_senders", m.knobs.system_senders)
    put("send_guard_min_chars", m.knobs.send_guard_min_chars)
    put("send_guard_banned_phrases", m.knobs.send_guard_banned_phrases)

    put("sms_enabled", m.sms.enabled)
    put("sms_proxy_base", m.sms.proxy_base)

    put("drive_scope", m.drive.scope)
    put("platform_env_path", m.env.platform_env_path)
    return out
