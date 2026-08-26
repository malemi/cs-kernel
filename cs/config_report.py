"""`cs config` — the settings actually in force, and which layer declared each.

Reading `manifest.toml` and the `.env` files does not answer "what is this
operator configured to do": the answer is the RESOLUTION of six layers, and
mentally executing the precedence rules is exactly where readers go wrong.
Two consecutive headless operator ticks (2026-08-23) concluded the system was
in `draft` mode because no `CS_TRIAGE_MODE` environment variable existed —
while `manifest.toml` declared `send`, and `config.load()` returned `send`.
Neither tick read the manifest. So the kernel answers the question itself
instead of leaving it to be re-derived.

Two things are reported per setting, and the second one is the point:

  * the RESOLVED value — whatever ``cs.config.load()`` returns, authoritative;
  * the PROVENANCE — which layer declared the winning value, named as the
    place to EDIT it: ``manifest.toml [knobs].cs_triage_mode``,
    ``~/.<slug>-cs/.env (CS_TRIAGE_MODE)``, ``process env CS_TRIAGE_MODE``.

A setting declared in MORE THAN ONE layer is reported as a defect even when
the declarations agree today: two repositories of truth for one value is a
value that will eventually disagree with itself. (A fix that duplicated
``cs_triage_mode`` into the state-dir ``.env`` "so it is also visible there"
was reverted for exactly this reason.)

**Secret VALUES are never printed.** A password, token or service-account key
is reported as ``set`` / ``not set`` beside the env KEY that carries it, so the
output stays safe to paste into a report, a log, or a cron transcript.

The layer scan here MIRRORS what pydantic-settings does rather than asking it
(the library reports no provenance). A mirror can drift, so every reported
value is cross-checked against the real resolved ``Settings``: a winning
declaration that does not match what the settings object actually holds is
printed with a ``?`` and listed under NOTES, never silently narrated as fact.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import AliasChoices

from . import config as config_mod
from . import manifest as manifest_mod

# --------------------------------------------------------------- what to show

# The settings that decide BEHAVIOUR. Deliberately short: a wall of sixty
# lines is as unreadable as no output at all. `--all` dumps the rest.
SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Autonomy and safety", ("cs_triage_mode", "dedup_days")),
    (
        "Identity",
        ("slug", "email_address", "engine_owner_uid", "engine_ws_url",
         "accounts_default"),
    ),
    ("Ports (adapters)", ("crm_adapter", "producer_adapter")),
    ("Campaigns", ("excluded_campaign",)),
    # `system_senders` decides who is never a customer — it removes senders
    # from the support queue and from the outreach worklist alike. Since
    # v0.23.0 an entry may be an fnmatch PATTERN, so one line can hide a whole
    # domain, and the verb whose entire job is "the settings actually in force"
    # was silent about it: an invisible filter is indistinguishable from a bug.
    ("Never a customer", ("system_senders",)),
)

# Comma-separated settings. Printed with a space after each comma so several
# values stay readable on one line — a reader scanning for "is batch2 excluded?"
# must not have to parse `a,b` by eye. The stored value is untouched.
LIST_FIELDS: frozenset[str] = frozenset({"excluded_campaign", "system_senders"})

# Never print the value of these — presence only. `firebase_web_api_key` is a
# public Firebase key and `firebase_sa_path` is only a path, but presence is
# all a reader needs from either, and a value that turns out to be sensitive
# later must not already be sitting in a year of cron logs.
SECRET_FIELDS: frozenset[str] = frozenset(
    {
        "email_password",
        "firebase_web_api_key",
        "firebase_sa_path",
        "shopify_admin_token",
        "shopify_secret",
        "shopify_client_id",
    }
)

# Secret-shaped settings surfaced in the default report, in order.
SECRET_REPORT: tuple[str, ...] = ("email_password", "firebase_web_api_key")

# Field -> where the value lives in manifest.toml. Only a key PHYSICALLY
# present in the file counts as a manifest declaration: `settings_overrides`
# always emits the numeric/bool knobs (their sub-model defaults equal the
# kernel defaults), so trusting it would tell a reader to go edit a
# `[knobs].dedup_days` line that is not in their file. tests/test_config_report.py
# asserts this map stays in step with `manifest.settings_overrides`.
MANIFEST_KEYS: dict[str, tuple[str, ...]] = {
    "company_name": ("company", "name"),
    "company_display_name": ("company", "display_name"),
    "email_from_name": ("company", "from_name"),
    "slug": ("company", "slug"),
    "prog_name": ("company", "prog_name"),
    "email_address": ("operator", "email_address"),
    "imap_host": ("operator", "imap_host"),
    "imap_port": ("operator", "imap_port"),
    "smtp_host": ("operator", "smtp_host"),
    "smtp_port": ("operator", "smtp_port"),
    "engine_owner_uid": ("engine", "owner_uid"),
    "engine_ws_url": ("engine", "ws_url"),
    "firebase_sa_path": ("engine", "sa_path"),
    "accounts_default": ("engine", "accounts", "default"),
    "founder_sweep_enabled": ("engine", "founder_sweep", "enabled"),
    "founder_sweep_account": ("engine", "founder_sweep", "account"),
    "crm_adapter": ("crm", "adapter"),
    "shopify_api_version": ("crm", "shopify", "api_version"),
    "shopify_env_prefix": ("crm", "shopify", "env_prefix"),
    "producer_adapter": ("producer", "adapter"),
    "agent_prompt_py": ("producer", "mrcall_tracking", "script_path"),
    "agent_prompt_python": ("producer", "mrcall_tracking", "python_path"),
    "excluded_campaign": ("campaigns", "excluded_campaign"),
    "dedup_days": ("knobs", "dedup_days"),
    "cs_triage_mode": ("knobs", "cs_triage_mode"),
    "timezone": ("knobs", "timezone"),
    "sms_hour": ("knobs", "sms_hour"),
    "reminder_max": ("knobs", "reminder_max"),
    "system_senders": ("knobs", "system_senders"),
    "send_guard_min_chars": ("knobs", "send_guard_min_chars"),
    "send_guard_banned_phrases": ("knobs", "send_guard_banned_phrases"),
    "sms_enabled": ("sms", "enabled"),
    "sms_proxy_base": ("sms", "proxy_base"),
    "drive_scope": ("drive", "scope"),
    "platform_env_path": ("env", "platform_env_path"),
}

# The four Shopify credentials the prefixed source (`cs/config.py
# _ShopifyPrefixSource`) can override, and the suffix it looks for. That source
# sits ABOVE the process environment, so a prefixed key beats a bare one no
# matter which layer the bare one came from.
SHOPIFY_PREFIXED: dict[str, str] = {
    "shopify_store_domain": "STORE_DOMAIN",
    "shopify_admin_token": "ADMIN_TOKEN",
    "shopify_client_id": "CLIENT_ID",
    "shopify_secret": "SECRET",
}


# ------------------------------------------------------------------- the scan


@dataclass(frozen=True)
class Declaration:
    """One layer declaring one setting. `where` names the file to EDIT."""

    layer: str            # stable id: manifest | platform | home | repo | process | shopify-prefix
    where: str            # human location, e.g. "manifest.toml [knobs].cs_triage_mode"
    value: Any            # as declared (TOML-typed from the manifest, str from env)
    shadowed: tuple[str, ...] = ()   # other alias keys present in the SAME layer


@dataclass
class Setting:
    name: str
    resolved: Any
    secret: bool
    declarations: list[Declaration] = dc_field(default_factory=list)

    @property
    def winner(self) -> Declaration | None:
        return self.declarations[-1] if self.declarations else None

    @property
    def origin(self) -> str:
        w = self.winner
        return w.where if w else "kernel default"

    @property
    def duplicated(self) -> bool:
        return len(self.declarations) > 1 or any(d.shadowed for d in self.declarations)


def _tilde(p: str | os.PathLike) -> str:
    """`~`-shorten a path under HOME — shorter, and it survives a sandbox HOME."""
    s = str(p)
    home = str(Path.home())
    if s == home:
        return "~"
    return "~" + s[len(home):] if s.startswith(home + os.sep) else s


def _env_names(field_name: str, info) -> list[str]:
    """The env keys pydantic-settings will look for, in ITS order.

    AliasChoices first, then the field name (the model sets
    `populate_by_name=True`, which is what puts the bare name back in play).
    Upper-cased because the model is `case_sensitive=False`.
    """
    names: list[str] = []
    va = getattr(info, "validation_alias", None)
    if isinstance(va, AliasChoices):
        names += [c for c in va.choices if isinstance(c, str)]
    elif isinstance(va, str):
        names.append(va)
    names.append(field_name)
    seen: set[str] = set()
    out: list[str] = []
    for n in (n.upper() for n in names):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {k.upper(): v for k, v in dotenv_values(path).items() if v is not None}


def _toml_lookup(raw: dict, path: tuple[str, ...]) -> tuple[bool, Any]:
    """(present, value) for a dotted TOML path — presence, not truthiness."""
    node: Any = raw
    for part in path:
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _manifest_where(display: str, path: tuple[str, ...]) -> str:
    return f"{display} [{'.'.join(path[:-1])}].{path[-1]}"


def _same(declared: Any, resolved: Any) -> bool:
    """Does a raw declaration explain the resolved value?

    Tolerant of the two transformations `Settings` performs between reading a
    declaration and holding it: the str->int/bool coercion on the way out of a
    dotenv, and `_derive_paths`' `expanduser()` on the path fields (a manifest
    that declares `sa_path = "~/.<slug>-cs/firebase-sa.json"` resolves to the
    absolute form — the same declaration, not an unexplained value).
    """
    if isinstance(resolved, bool):
        if isinstance(declared, bool):
            return declared is resolved
        s = str(declared).strip().lower()
        return s in (("1", "true", "yes", "on") if resolved else ("0", "false", "no", "off"))
    if isinstance(resolved, int):
        try:
            return int(str(declared).strip()) == resolved
        except (TypeError, ValueError):
            return False
    d, r = str(declared).strip(), str(resolved).strip()
    return d == r or os.path.expanduser(d) == r


class Scan:
    """The layered declaration scan for one loaded `Settings`."""

    def __init__(self, settings) -> None:
        self.settings = settings
        mpath = manifest_mod.find_manifest_path()
        self.manifest_path: Path | None = mpath
        self.manifest_raw: dict = {}
        if mpath is not None:
            with open(mpath, "rb") as fh:
                self.manifest_raw = tomllib.load(fh)
        self.manifest_display = _tilde(mpath) if mpath is not None else ""

        # The dotenv chain, lowest -> highest. `config.env_file_chain` is the
        # ONE definition of it and is called here rather than re-implemented;
        # only the layer IDS are recovered locally, mirroring the two
        # conditions that build the chain (a platform entry iff the manifest
        # declares one, a home entry iff there is a slug).
        overrides = (
            manifest_mod.settings_overrides(manifest_mod.load_manifest(mpath))
            if mpath is not None
            else {}
        )
        self.manifest_overrides = overrides
        chain = config_mod.env_file_chain(overrides)
        ids: list[str] = []
        if overrides.get("platform_env_path", ""):
            ids.append("platform")
        if overrides.get("slug", ""):
            ids.append("home")
        ids.append("repo")
        if len(ids) != len(chain):
            # The chain grew a layer this mirror does not know a name for.
            # Fall back to positional ids rather than mislabel one: the name is
            # cosmetic, the PATH is what the reader edits and it comes straight
            # from env_file_chain either way.
            ids = [f"env-file-{i + 1}" for i in range(len(chain))]

        self.file_layers: list[tuple[str, str, bool]] = []
        self.env_layers: list[tuple[str, str, dict[str, str]]] = []
        for layer_id, f in zip(ids, chain):
            p = Path(f).expanduser()
            self.env_layers.append((layer_id, _tilde(p), _read_dotenv(p)))
            self.file_layers.append((layer_id, _tilde(p), p.exists()))
        self.env_layers.append(
            ("process", "process env", {k.upper(): v for k, v in os.environ.items()})
        )

    # -- one field ---------------------------------------------------------

    def setting(self, name: str) -> Setting:
        info = type(self.settings).model_fields[name]
        fld = Setting(
            name=name,
            resolved=getattr(self.settings, name),
            secret=name in SECRET_FIELDS,
        )

        tpath = MANIFEST_KEYS.get(name)
        if tpath and self.manifest_raw:
            present, val = _toml_lookup(self.manifest_raw, tpath)
            if present:
                fld.declarations.append(
                    Declaration(
                        "manifest", _manifest_where(self.manifest_display, tpath), val
                    )
                )

        names = _env_names(name, info)
        for layer_id, display, mapping in self.env_layers:
            hits = [n for n in names if n in mapping]
            if hits:
                fld.declarations.append(
                    Declaration(
                        layer_id,
                        f"{display} ({hits[0]})",
                        mapping[hits[0]],
                        tuple(hits[1:]),
                    )
                )

        suffix = SHOPIFY_PREFIXED.get(name)
        # The prefix comes from the MANIFEST layer, not from the resolved
        # Settings: `config.load()` seeds `_LOAD_CTX["prefix"]` out of the
        # manifest overrides, so an env-set SHOPIFY_ENV_PREFIX changes the
        # settings field without changing which prefixed keys are read.
        # Mirror what the source does, not what the field says.
        prefix = (
            str(self.manifest_overrides.get("shopify_env_prefix", "") or "")
            .strip()
            .upper()
            .rstrip("_")
        )
        if suffix and prefix and prefix != "SHOPIFY":
            key = f"{prefix}_{suffix}"
            for layer_id, display, mapping in self.env_layers:
                if mapping.get(key):
                    fld.declarations.append(
                        Declaration("shopify-prefix", f"{display} ({key})", mapping[key])
                    )
        return fld


# ------------------------------------------------------------------ the report


def build(settings=None, include_all: bool = False) -> dict:
    """The whole report as data — what `render()` prints and `--json` emits."""
    settings = settings if settings is not None else config_mod.load()
    scan = Scan(settings)

    # Scanned for EVERY setting, always — a second declaration is the failure
    # the charter bans, and it has to be visible the moment it appears, not
    # only when it happens to land on one of the curated lines below.
    fields: dict[str, Setting] = {
        n: scan.setting(n) for n in type(settings).model_fields
    }

    def as_dict(f: Setting) -> dict:
        d: dict[str, Any] = {
            "name": f.name,
            "origin": f.origin,
            "layer": f.winner.layer if f.winner else "default",
            "secret": f.secret,
            "declarations": [
                {
                    "layer": x.layer,
                    "where": x.where,
                    "shadowed": list(x.shadowed),
                    **({} if f.secret else {"value": x.value}),
                }
                for x in f.declarations
            ],
        }
        if f.secret:
            d["value"] = "set" if f.resolved else "not set"
        else:
            d["value"] = f.resolved
        return d

    # The scan MIRRORS pydantic-settings; where the mirror cannot explain the
    # value the settings object actually holds, say so instead of narrating a
    # provenance we have not established.
    mismatched: list[str] = []
    notes: list[str] = []
    for f in fields.values():
        w = f.winner
        if w is not None and not _same(w.value, f.resolved):
            mismatched.append(f.name)
            notes.append(
                f"{f.name}: the highest declaration ({w.where}) does not explain "
                "the resolved value — provenance is UNVERIFIED, shown as '?'"
            )

    duplicates = [as_dict(f) for f in fields.values() if f.duplicated]

    sa = Path(settings.firebase_sa_path) if settings.firebase_sa_path else None
    return {
        "manifest": str(scan.manifest_path) if scan.manifest_path else None,
        "state_dir": _tilde(settings.state_dir),
        "pause": {
            "path": _tilde(settings.pause_path),
            "present": settings.pause_path.exists(),
        },
        "service_account": {
            "env_key": "FIREBASE_SA_PATH",
            "present": bool(sa and sa.exists()),
        },
        "layers": [
            {"id": lid, "where": disp, "exists": ok} for lid, disp, ok in scan.file_layers
        ],
        "sections": [
            {"title": title, "settings": [as_dict(fields[n]) for n in names]}
            for title, names in SECTIONS
        ],
        "secrets": [as_dict(fields[n]) for n in SECRET_REPORT],
        "all": [as_dict(f) for f in fields.values()] if include_all else None,
        "duplicates": duplicates,
        "notes": notes,
        "mismatched": mismatched,
    }


def _cell(f: dict) -> str:
    if f["secret"]:
        return str(f["value"])
    v = f["value"]
    if isinstance(v, bool):
        return "true" if v else "false"
    if f["name"] in LIST_FIELDS and isinstance(v, str) and v.strip():
        parts = [p.strip() for p in v.split(",") if p.strip()]
        return ", ".join(parts)
    return str(v) if v != "" else "(empty)"


_NAME_W = 24
_VAL_W = 26


def _row(name: str, value: str, origin: str) -> str:
    """One report line. Columns pad but never TRUNCATE — a value clipped to fit
    is a value the reader now has to guess at, which is the whole disease."""
    return f"  {name:<{_NAME_W}}{value:<{_VAL_W}}  {origin}".rstrip()


def render(rep: dict) -> str:
    """The human- and agent-readable report: every line is meant to be read by
    whoever is about to act on this configuration."""
    out: list[str] = []
    add = out.append

    add("cs config — the settings actually IN FORCE, and which file declares each.")
    add("This is the answer: do not re-derive it from the files, and do not read")
    add("a missing environment variable as 'so the default applies'.")

    for sec in rep["sections"]:
        add("")
        add(sec["title"])
        for f in sec["settings"]:
            origin = f["origin"]
            if f["name"] in rep["mismatched"]:
                origin = f"? {origin}"
            add(_row(f["name"], _cell(f), origin))

    add("")
    add("Kill-switch")
    p = rep["pause"]
    status = "PRESENT — sends are PAUSED" if p["present"] else "absent — sends not paused"
    add(_row("CS_PAUSE", status, p["path"]))

    add("")
    add("Secrets (presence only — values are never printed)")
    for f in rep["secrets"]:
        add(_row(f["name"], _cell(f), f["origin"]))
    sa = rep["service_account"]
    add(
        _row(
            "firebase service acct",
            "present" if sa["present"] else "not present",
            sa["env_key"],
        )
    )

    if rep["all"] is not None:
        add("")
        add("All settings")
        for f in rep["all"]:
            origin = f["origin"]
            if f["name"] in rep["mismatched"]:
                origin = f"? {origin}"
            add(_row(f["name"], _cell(f), origin))

    add("")
    add("Layers, lowest to highest precedence:")
    add("  1  kernel defaults")
    add(f"  2  {rep['manifest'] or 'manifest.toml (none found)'}")
    n = 3
    for lay in rep["layers"]:
        add(f"  {n}  {lay['where']}{'' if lay['exists'] else '   (absent)'}")
        n += 1
    add(f"  {n}  process environment")

    add("")
    if rep["duplicates"]:
        add(
            f"DUPLICATE DECLARATIONS — {len(rep['duplicates'])} setting(s) declared in "
            "more than one place."
        )
        add(
            "Two repositories of truth for one value is a value that will eventually"
        )
        add("disagree with itself. Delete the losing declaration(s).")
        for f in rep["duplicates"]:
            add(f"  {f['name']}")
            decls = list(reversed(f["declarations"]))
            for i, d in enumerate(decls):
                mark = "IN FORCE" if i == 0 else "ignored"
                val = "(secret)" if f["secret"] else repr(d.get("value"))
                add(f"    {mark:<9}{val:<26}{d['where']}")
                for other in d["shadowed"]:
                    add(f"    {'ignored':<9}{'(same layer)':<26}{other}")
    else:
        add("No setting is declared in more than one place.")

    if rep["notes"]:
        add("")
        add("NOTES")
        for note in rep["notes"]:
            add(f"  {note}")
    return "\n".join(out)
