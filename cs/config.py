"""Runtime config — kernel Settings fed by manifest + layered env files.

Value layers, later wins (see cs/manifest.py):

  1. kernel defaults              (neutral — NO company value in this file)
  2. manifest.toml                (the declared per-company variance)
  3. platform env file            (manifest [env].platform_env_path, optional)
  4. ~/.<slug>-cs/.env            (the clone's state dir; secrets live here)
  5. repo-local .env              (developer override)
  6. process environment          (highest; how `--account` overrides the uid)

Every state path derives from ONE ``settings.state_dir`` (``~/.<slug>-cs``),
itself derived from the manifest slug: db, token cache, SA key, CS_PAUSE,
operator log. Overriding ``HOME`` therefore relocates ledger + token cache +
env + SA **atomically** — the sandbox-HOME test strategy relies on this.

Shopify env keys honour the manifest prefix (``[crm.shopify].env_prefix`` →
``<PREFIX>_STORE_DOMAIN`` …), falling back to the bare ``SHOPIFY_*`` names —
the per-company AliasChoices convention, generalized.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from . import manifest as manifest_mod


class ConfigError(RuntimeError):
    """A required setting is missing or unusable.

    The CLI catches these at dispatch and prints them as one-line actionable
    errors (no traceback): configuration absence is a product state, not a bug.
    """


# Set by load() just before Settings is instantiated (single-threaded CLI):
# the manifest layer + the shopify prefix + the resolved env-file chain.
_LOAD_CTX: dict[str, Any] = {"overrides": {}, "prefix": "", "env_files": ()}


class _ManifestSource(PydanticBaseSettingsSource):
    """Manifest values as a settings source ABOVE kernel defaults and BELOW
    every env layer (see the layer table in the module docstring)."""

    def get_field_value(self, field, field_name):  # pragma: no cover - unused
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        overrides: dict = _LOAD_CTX["overrides"]
        return {k: v for k, v in overrides.items() if k in self.settings_cls.model_fields}


class _ShopifyPrefixSource(PydanticBaseSettingsSource):
    """Prefixed Shopify keys (``<PREFIX>_STORE_DOMAIN`` …) from the process
    env and the dotenv layers, mapped onto the ``shopify_*`` fields. A
    prefixed key beats the bare ``SHOPIFY_*`` fallback (which the normal
    env/dotenv sources handle via the field aliases).

    Values are emitted under the field's ALIAS key (the bare env name):
    pydantic prefers the alias over the field name when both survive the
    source merge, so emitting the alias is what makes this source actually
    override a bare value coming from a lower-priority source."""

    _KEYS = {
        "SHOPIFY_STORE_DOMAIN": "STORE_DOMAIN",   # alias key -> prefix suffix
        "SHOPIFY_ADMIN_TOKEN": "ADMIN_TOKEN",
        "SHOPIFY_CLIENT_ID": "CLIENT_ID",
        "SHOPIFY_SECRET": "SECRET",
    }

    def get_field_value(self, field, field_name):  # pragma: no cover - unused
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        prefix = (_LOAD_CTX["prefix"] or "").strip().upper().rstrip("_")
        if not prefix or prefix == "SHOPIFY":  # bare names: normal sources handle them
            return {}
        merged: dict[str, str] = {}
        for f in _LOAD_CTX["env_files"]:  # ordered lowest → highest precedence
            p = Path(f)
            if p.exists():
                merged.update(
                    {k.upper(): v for k, v in dotenv_values(p).items() if v is not None}
                )
        merged.update({k.upper(): v for k, v in os.environ.items()})
        out: dict[str, Any] = {}
        for alias_key, suffix in self._KEYS.items():
            v = merged.get(f"{prefix}_{suffix}")
            if v:
                out[alias_key] = v
        return out


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),  # load() passes the full per-clone chain via _env_file
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,  # manifest layer feeds values by FIELD NAME
    )

    # --- company / operator identity (manifest [company] / [operator]) ---
    company_name: str = ""
    company_display_name: str = ""
    email_from_name: str = ""     # From: display-name on fixed-template bulk
    slug: str = ""                # derives state_dir and every state path
    prog_name: str = "cs"         # argparse prog — DISPLAY ONLY (module path frozen)
    email_address: str = ""       # the operator mailbox; also SELF cc + identity prints
    email_password: str = ""      # app password: Gmail Drafts APPEND + fixed-template SMTP only
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    # --- engine daemon (the body; Claude Code is the brain) ---
    engine_owner_uid: str = Field(
        default="",
        validation_alias=AliasChoices("CS_ENGINE_OWNER_UID", "ENGINE_OWNER_UID"),
    )
    engine_ws_url: str = ""       # manifest [engine].ws_url; client appends /ws/<uid>
    firebase_web_api_key: str = ""  # public web API key of the engine's Firebase project
    token_cache_path: str = ""    # empty → <state_dir>/id_token-<uid>.json
    refresh_token_path: str = ""  # empty → <state_dir>/refresh_token-<uid>.json
    firebase_sa_path: str = ""    # empty → <state_dir>/firebase-sa.json

    # multi-account (THIS project only): registry name->uid in env CS_ACCOUNTS,
    # e.g. "ops:uidA,founder:uidB". The manifest carries NAMES only; real uids
    # stay in the env layer. NEVER mix another project's domain (invariant).
    accounts: str = Field(
        default="", validation_alias=AliasChoices("CS_ACCOUNTS", "ACCOUNTS")
    )
    accounts_default: str = ""    # manifest [engine.accounts].default (a name)

    # founder-inbox sweep (cs-operator step 4b): logic is kernel/skill-side;
    # on/off + which account is per-company.
    founder_sweep_enabled: bool = False
    founder_sweep_account: str = ""

    # --- CRM port (cs/crm) ---
    crm_adapter: str = "none"     # starchat | shopify | none (registry-validated)
    shopify_api_version: str = "2025-10"
    shopify_env_prefix: str = ""  # manifest [crm.shopify].env_prefix
    shopify_store_domain: str = Field(
        default="", validation_alias=AliasChoices("SHOPIFY_STORE_DOMAIN")
    )
    shopify_admin_token: str = Field(
        default="", validation_alias=AliasChoices("SHOPIFY_ADMIN_TOKEN")
    )
    shopify_client_id: str = Field(
        default="", validation_alias=AliasChoices("SHOPIFY_CLIENT_ID")
    )
    shopify_secret: str = Field(
        default="", validation_alias=AliasChoices("SHOPIFY_SECRET")
    )

    # --- producer port (cs/ingest) ---
    producer_adapter: str = "none"  # mrcall-tracking | none (registry-validated)
    agent_prompt_py: str = ""       # manifest [producer.mrcall_tracking].script_path
    agent_prompt_python: str = ""   # manifest [producer.mrcall_tracking].python_path

    # --- campaigns ---
    # Campaigns a dedicated process owns, so the general operator leaves them
    # alone. Comma-separated, like every other multi-value knob here
    # (self_emails, system_senders, send_guard_banned_phrases); "" = none, and a
    # single bare name is the one-element case, so a clone written before the
    # list existed keeps working with no edit. Matching is EXACT per name — see
    # excluded_campaign_set.
    excluded_campaign: str = ""

    # --- behaviour knobs ---
    dedup_days: int = 30
    # No `dry_run` / `autonomous` field: neither ever gated anything. Dry-run
    # is the `commit` argument on every send function, fed by the `--commit`
    # CLI flag; autonomy is `cs_triage_mode` plus the clone's
    # `.claude/settings.json` permission surface. Both were removed in v0.18.0.
    # graduated autonomy: free-form engine sends stay DRAFTS until "send";
    # fixed-template bulk is autonomous (CS_TRIAGE_MODE=send). The global
    # kill-switch is a FILE (<state_dir>/CS_PAUSE), checked by wrappers and
    # send paths.
    cs_triage_mode: str = "draft"  # draft | send
    timezone: str = "Europe/Rome"  # market-local windows (cs/_time.py)
    sms_hour: int = 18
    reminder_max: int = 3

    # --- model-output send guard (cs/send_guard.py) ---
    # Only the two knobs that are legitimately per-company: how short a
    # composed body may be, and extra phrases this company never wants to send.
    # The tells themselves are code, not config — a guard with an off switch is
    # a guard that is off.
    send_guard_min_chars: int = Field(
        default=40, validation_alias=AliasChoices("CS_SEND_GUARD_MIN_CHARS")
    )
    send_guard_banned_phrases: str = Field(
        default="", validation_alias=AliasChoices("CS_SEND_GUARD_BANNED")
    )

    # --- SMS capability (optional; manifest [sms]) ---
    sms_enabled: bool = False
    # The send endpoint of the mrcall-desktop engine's SMS proxy. Shared
    # infrastructure the kernel drives, not a per-clone value: the proxy is
    # Vonage behind one engine, and the traffic bills against the platform
    # credit pool whichever clone sent it. It is a KERNEL DEFAULT rather than
    # a manifest field a clone must supply, because `settings_overrides` skips
    # empty strings — so a manifest that leaves `[sms].proxy_base` blank, which
    # is what every clone stamped before v0.19.0 literally contains, lands
    # here. Declare `[sms].proxy_base` to point a clone somewhere else; declare
    # it EMPTY in the env layer to turn the endpoint off and make `cs/sms.py`
    # refuse. Recorded in tests/reviewed_literals.txt (charter rule 1).
    sms_proxy_base: str = "https://zylch.mrcall.ai/api/desktop/sms/send"
    sms_business_id: str = ""     # env SMS_BUSINESS_ID — which business is billed

    # --- exclusions (comma-separated in env) ---
    self_uids: str = ""
    self_emails: str = ""
    # System / no-reply senders to ignore in the `unanswered` sweep (notifications,
    # transactional, internal tooling). An entry may be a literal address or an
    # fnmatch pattern — see system_sender_set. NEVER hardcode company addresses in
    # the kernel — the clone declares them in its own env/manifest (charter gate).
    system_senders: str = Field(
        default="", validation_alias=AliasChoices("CS_SYSTEM_SENDERS")
    )

    # --- Google Drive scope (read-only operator Drive access, cs/drive.py).
    # `cs drive search` defaults to THIS company's Shared Drive ONLY; explicit
    # `all` is the test-time override. Manifest [drive].scope / env CS_DRIVE.
    drive_scope: str = Field(
        default="",
        validation_alias=AliasChoices("CS_DRIVE", "CS_DRIVE_SCOPE"),
    )

    # --- state ---
    db_path: str = ""             # empty → <state_dir>/cs.db
    platform_env_path: str = ""   # manifest [env].platform_env_path (informational)

    # ------------------------------------------------------------- derived

    @property
    def state_dir(self) -> Path:
        """THE single state dir: ~/.<slug>-cs (computed from HOME at access
        time, so a sandbox HOME relocates everything atomically)."""
        return Path.home() / (f".{self.slug}-cs" if self.slug else ".cs")

    @property
    def pause_path(self) -> Path:
        """Global kill-switch file — its presence pauses every send surface."""
        return self.state_dir / "CS_PAUSE"

    @property
    def log_path(self) -> Path:
        return self.state_dir / "cs_operator.log"

    @model_validator(mode="after")
    def _derive_paths(self) -> "Settings":
        sd = self.state_dir
        if not self.db_path:
            self.db_path = str(sd / "cs.db")
        # Per-uid session files are what keep `--account <name>` working:
        # cs/cli.py swaps CS_ENGINE_OWNER_UID into the env before
        # config.load() runs, so this derivation follows whichever account
        # was selected for that invocation. This uid is operator-written
        # (manifest [engine].owner_uid, CS_ENGINE_OWNER_UID, or a CS_ACCOUNTS
        # entry — never the descriptor's own uid, which cs login only reads
        # for the identity cross-check) and kernel-unvalidated; the
        # derivation trusts it as a filename component, which is fine for
        # every real uid and every value the operator has any reason to
        # type. An empty uid keeps the un-suffixed legacy names — auth.py
        # raises its own "uid not set" ConfigError before either file is
        # ever read or written, so an empty uid never actually reaches
        # these paths.
        uid = (self.engine_owner_uid or "").strip()
        if not self.token_cache_path:
            self.token_cache_path = str(
                sd / (f"id_token-{uid}.json" if uid else "id_token.json")
            )
        if not self.refresh_token_path:
            self.refresh_token_path = str(
                sd / (f"refresh_token-{uid}.json" if uid else "refresh_token.json")
            )
        if not self.firebase_sa_path:
            self.firebase_sa_path = str(sd / "firebase-sa.json")
        self.db_path = os.path.expanduser(self.db_path)
        self.token_cache_path = os.path.expanduser(self.token_cache_path)
        self.refresh_token_path = os.path.expanduser(self.refresh_token_path)
        self.firebase_sa_path = os.path.expanduser(self.firebase_sa_path)
        return self

    @property
    def self_uid_set(self) -> set[str]:
        return {u.strip() for u in self.self_uids.split(",") if u.strip()}

    @property
    def self_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.self_emails.split(",") if e.strip()}

    @property
    def system_sender_set(self) -> set[str]:
        """Senders the `unanswered` sweep must not raise as people waiting.

        Each entry is EITHER a literal address OR an fnmatch pattern —
        `mail-daemon@*`, `mailer-daemon@*`, `postmaster@*`, `*@notify.<domain>`.
        Patterns exist because bounce daemons cannot be enumerated: the sending
        host rotates per bounce, so one undeliverable address emits a new
        `mail-daemon@<host-NN>…` sender every time and a literal list is never
        finished. An entry carrying no wildcard is matched exactly, exactly as
        before patterns existed; the matcher is `cs/unanswered._is_ignored`.

        Write patterns as narrowly as the noise allows. This list decides who is
        never a customer, and nothing downstream re-checks it.
        """
        return {e.strip().lower() for e in self.system_senders.split(",") if e.strip()}

    @property
    def excluded_campaign_set(self) -> set[str]:
        """Campaign names the general operator must not touch. EXACT names, never
        prefixes: an excluded `<name>` would otherwise swallow `<name>-batch2`,
        and a substring rule silently excludes campaigns nobody meant to
        exclude. List both if you mean both. Case is preserved — engine
        campaign names are identifiers, not prose."""
        return {c.strip() for c in self.excluded_campaign.split(",") if c.strip()}

    @property
    def account_map(self) -> dict:
        """name -> uid, parsed from CS_ACCOUNTS (this project's accounts only)."""
        out: dict[str, str] = {}
        for pair in self.accounts.split(","):
            if ":" in pair:
                name, uid = pair.split(":", 1)
                if name.strip() and uid.strip():
                    out[name.strip()] = uid.strip()
        return out

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            _ShopifyPrefixSource(settings_cls),  # prefixed key beats bare fallback
            env_settings,
            dotenv_settings,
            _ManifestSource(settings_cls),       # manifest above kernel defaults
            file_secret_settings,
        )


def env_file_chain(overrides: dict[str, Any] | None = None) -> tuple[str, ...]:
    """The dotenv layers, ordered LOWEST → HIGHEST precedence.

    Split out of ``load()`` so anything that must read the same values without
    building a full ``Settings`` (``cs/model_config.py`` resolves the LLM
    provider this way) uses ONE definition of the chain. Pass *overrides* when
    the manifest has already been loaded; otherwise it is read here.
    """
    if overrides is None:
        mpath = manifest_mod.find_manifest_path()
        m = manifest_mod.load_manifest(mpath) if mpath is not None else None
        overrides = manifest_mod.settings_overrides(m) if m else {}

    env_files: list[str] = []
    plat = overrides.get("platform_env_path", "")
    if plat:
        env_files.append(str(Path(plat).expanduser()))
    slug = overrides.get("slug", "")
    if slug:
        env_files.append(str(Path.home() / f".{slug}-cs" / ".env"))
    env_files.append(".env")  # repo-local override, highest dotenv layer
    return tuple(env_files)


def load(engine_owner_uid: str | None = None) -> Settings:
    """Read the manifest (if any), validate its adapters LOUDLY, then build
    Settings over the layered env chain. Tolerates a MISSING manifest (so
    `python -m cs --help` works in a bare install); an invalid one raises
    ManifestError.

    `engine_owner_uid` targets ANOTHER account of this project (a `CS_ACCOUNTS`
    uid) without touching the process environment: it is passed as an init
    value, the highest-priority source, and the `_derive_paths` validator then
    derives THAT uid's own session files — which is what makes the resulting
    Settings authenticate as that profile's owner. `cs --account` does the same
    thing for a whole invocation by swapping the env key; this is the in-process
    form, for code that must speak to two profiles in one run
    (`cs/mailboxes.py`). Everything else — mailbox address and password, state
    dir, knobs — still resolves from the clone's own layers, so this is a
    change of engine identity, never of company."""
    mpath = manifest_mod.find_manifest_path()
    m = manifest_mod.load_manifest(mpath) if mpath is not None else None
    overrides = manifest_mod.settings_overrides(m) if m else {}

    if m is not None:
        # Unknown adapter = loud startup error, not a surprise at the first
        # dossier (the registries are the single source of valid names).
        from . import crm as crm_mod
        from . import ingest as ingest_mod

        try:
            crm_mod.resolve(m.crm.adapter)
            ingest_mod.resolve(m.producer.adapter)
        except RuntimeError as e:
            raise manifest_mod.ManifestError(str(e)) from None
        if m.producer.adapter == "mrcall-tracking":
            mt = m.producer.mrcall_tracking
            if not (mt and mt.script_path and mt.python_path):
                raise manifest_mod.ManifestError(
                    "[producer].adapter = \"mrcall-tracking\" requires "
                    "[producer.mrcall_tracking] script_path + python_path in manifest.toml"
                )

    env_files = env_file_chain(overrides)

    _LOAD_CTX["overrides"] = overrides
    _LOAD_CTX["prefix"] = overrides.get("shopify_env_prefix", "")
    _LOAD_CTX["env_files"] = tuple(env_files)
    uid = (engine_owner_uid or "").strip()
    if uid:
        return Settings(_env_file=tuple(env_files), engine_owner_uid=uid)
    return Settings(_env_file=tuple(env_files))
