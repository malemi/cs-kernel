"""Provider / tier / role resolution for the kernel's own LLM calls.

The kernel used to make **zero** LLM calls of its own: every generation went
through the engine (``cs/rpc.py`` → ``chat.send``), whose provider is decided
downstream. This module adds the other half — a small, direct, *mechanical*
call path the kernel owns, so a one-word classification does not have to pay a
customer-facing model routed through the engine.

Two rules make it safe to have both:

* **No call site ever hardcodes a model id.** A call site declares a
  :class:`Role`; :func:`model_for` resolves the id from the environment, the
  tier default, or the provider default. Changing provider or model is a
  configuration change, never a code change.
* **Only the worker tier lives here.** Contextual, customer-facing generation
  stays an engine call (kernel charter §4). The tier split is what keeps a
  cheap model away from the text a customer reads.

Configuration (all optional; the layered env chain of :mod:`cs.config`, plus
the process environment on top):

===========================  ==================================================
``CS_LLM_PROVIDER``          ``anthropic`` | ``openrouter`` | ``custom`` —
                             explicit override; wins over every inference below.
``CS_LLM_BASE_URL``          gateway base URL. For OpenRouter this is
                             ``https://openrouter.ai/api`` — **not** ``/api/v1``:
                             the anthropic SDK appends ``/v1/messages`` itself
                             (verified 2026-07-27; ``/api/v1`` 404s on an HTML
                             page). Falls back to ``ANTHROPIC_BASE_URL``.
``CS_LLM_API_KEY``           credential for that base URL. Falls back to
                             ``OPENROUTER_API_KEY`` (OpenRouter) or
                             ``ANTHROPIC_API_KEY`` (Anthropic direct).
``MODEL_<ROLE>``             per-role model, e.g. ``MODEL_CLASSIFIER``.
``MODEL_<TIER>``             per-tier model, e.g. ``MODEL_WORKER``.
===========================  ==================================================

Either model key takes a **pinned id** (``deepseek/deepseek-v4-pro``) or a
**family reference** (``@deepseek-pro``), which resolves to the newest member
of that product line against the live OpenRouter catalog — so a clone tracks a
vendor's current model without anyone editing a constant. ``cs llm`` lists the
families; :mod:`cs.model_catalog` explains why a static list is wrong.

With nothing configured but an ``OPENROUTER_API_KEY`` present, the resolution
below selects OpenRouter — a key for a gateway is the operator saying which
gateway to use, and the alternative (silently falling back to Anthropic direct
and the bill this work exists to cut) is the worse surprise. ``CS_LLM_PROVIDER``
makes it explicit either way.
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Mapping

# The anthropic SDK's own hardcoded default. We pass it explicitly whenever no
# base_url is configured, so the SDK never re-reads ANTHROPIC_BASE_URL from the
# process env — which a config writer may have left as "" (an explicit, broken,
# empty host rather than a missing one).
ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"

# OpenRouter's Anthropic-compatible endpoint, as the anthropic SDK wants it:
# the SDK appends "/v1/messages", so the base stops at "/api".
OPENROUTER_BASE_URL = "https://openrouter.ai/api"


class LLMEnvError(RuntimeError):
    """The env layers describe an endpoint that cannot be used safely."""


class Provider(Enum):
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"


class Tier(Enum):
    """Capability tier a role needs. Every role maps to exactly one."""

    LEAD = "lead"      # judgment / tool-driving. Reserved; nothing uses it yet.
    WORKER = "worker"  # single-shot, mechanical, no tool use, no caching need.


class Role(Enum):
    """Every kernel-owned LLM call site, named.

    Deliberately tiny. A role is added when a real call site appears, never in
    advance: the list is the audit surface for "what does the kernel spend
    money on", and a speculative entry makes that answer a lie.
    """

    CLASSIFIER = "classifier"  # map one message to one label from a fixed set


ROLE_TIER: dict[Role, Tier] = {
    Role.CLASSIFIER: Tier.WORKER,
}

# Built-in FAMILY per (provider, tier) — not a pinned id. Resolved against the
# live catalog at call time (see cs/model_catalog.py for why a constant list of
# ids is wrong within weeks). Overridable by env — see model_for().
#
# Both tiers default to a frontier-class family on purpose. Choosing a smaller
# model to save money is a decision that has to be EARNED by a measurement on
# the real task, per role; until a role has been measured, its default is a
# model that is known to do the job. The whole point of the tier indirection is
# that moving a measured role down is then a one-line env change.
TIER_FAMILIES: dict[Provider, dict[Tier, str]] = {
    Provider.ANTHROPIC: {
        Tier.LEAD: "@claude-opus",
        Tier.WORKER: "@claude-sonnet",
    },
    Provider.OPENROUTER: {
        Tier.LEAD: "@claude-opus",
        Tier.WORKER: "@claude-sonnet",
    },
}

# A role whose EARNED measurement moved it off its tier default. Consulted
# before TIER_FAMILIES, and per provider because a family only exists where
# the gateway serves it.
#
# CLASSIFIER → @glm on OpenRouter: measured 2026-07-28 on the real task (61
# live replies, engine baseline, hand-adjudicated gold, scored through the
# clone's own parser) — ties the engine's accuracy on the calls both
# completed (56/58), zero unagreed schedule writes, answered 61/61 where the
# engine's transport failed 3, 3.1s vs 33s median, $1.17/1k calls. Full
# record: meta-repo docs/briefs/2026-07-28-multi-provider-llm-ab.md. The
# measurement was left unapplied for three weeks while every classification
# billed a frontier model; wiring it is what the tier indirection is FOR.
#
# Anthropic direct keeps @claude-sonnet: @glm is not served there, and a
# default that cannot resolve is worse than a dearer one that can.
# Every KNOWN provider is listed explicitly, empty included: for role
# overrides "absent" must mean "no earned override here", never "borrow
# another provider's" — borrowing sent @glm to the Anthropic-direct wire,
# where it does not exist (caught by the resolution test below this change).
# Only a genuinely unknown provider (`custom`) borrows OpenRouter's, matching
# how TIER_FAMILIES treats it.
ROLE_FAMILIES: dict[Provider, dict[Role, str]] = {
    Provider.OPENROUTER: {
        Role.CLASSIFIER: "@glm",
    },
    Provider.ANTHROPIC: {},
}

# --------------------------------------------------------------- price catalog
#
# OpenRouter prices come from the live catalog (cs/model_catalog.py) — they are
# published per model and they move. Only Anthropic-DIRECT ids need a table
# here, because the OpenRouter index does not carry them (there they are
# "anthropic/…"-prefixed, here they are bare).
#
# USD per 1M tokens (input, output). Anthropic's public price sheet, 2026-07-28.
ANTHROPIC_DIRECT_RATES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5": (1.00, 5.00),  # what resolve_spec emits for the direct wire
    "claude-haiku-4.5": (1.00, 5.00),  # the OpenRouter spelling, kept for lookups
}


def token_rates(model_id: str) -> tuple[float, float] | None:
    """(input, output) USD per 1M tokens for *model_id*, or ``None``.

    Exact match only, live catalog first. A prefix-stripped fallback would let
    ``someone-else/claude-sonnet-5`` inherit Anthropic's price sheet, and a
    price that is confidently wrong is worse than a price that is missing —
    octopus priced unknown OpenRouter ids at Opus rates and over-counted spend
    by 24-80x, which warps every budget decision downstream while looking fine.
    """
    from . import model_catalog

    direct = ANTHROPIC_DIRECT_RATES.get(model_id)
    if direct is not None:
        return direct
    return model_catalog.token_rates(model_id)


def call_cost(response, model_id: str) -> float | None:
    """USD for one Messages call, or ``None`` when it cannot be established.

    OpenRouter reports the actual cost of the call on ``usage.cost``; when present
    that is authoritative (it already accounts for the upstream provider it
    routed to). Otherwise fall back to the catalog rates, and to ``None`` when
    the model is not in the catalog.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    reported = getattr(usage, "cost", None)
    if isinstance(reported, (int, float)) and reported > 0:
        return float(reported)
    rates = token_rates(model_id)
    if rates is None:
        return None
    # getattr(...) or 0: a gateway may omit a field entirely. Note that a zero
    # here means "not reported", not "free" — callers summing these must say so.
    tin = getattr(usage, "input_tokens", 0) or 0
    tout = getattr(usage, "output_tokens", 0) or 0
    return (tin * rates[0] + tout * rates[1]) / 1_000_000


# ------------------------------------------------------------ env resolution


def detect_provider(base_url: str | None) -> Provider:
    """Provider implied by *base_url*. Empty / missing means Anthropic direct.

    ``""`` must collapse to Anthropic BEFORE this is called (see
    :func:`llm_env`): treating an empty string as CUSTOM routes the credential
    onto the wrong auth header *and* hands the SDK a broken host.

    Matched on the HOST, not by substring: ``https://proxy.corp/anthropic``
    is a custom gateway that happens to mention the word, and a substring
    match would put its Bearer credential on ``X-Api-Key``. The provider
    decides the auth header, so a wrong detection is a wrong header — the
    401 the whole builder exists to prevent.
    """
    if not base_url:
        return Provider.ANTHROPIC
    from urllib.parse import urlsplit

    host = (urlsplit(base_url).hostname or "").lower()
    if host == "api.anthropic.com" or host.endswith(".anthropic.com"):
        return Provider.ANTHROPIC
    if host == "openrouter.ai" or host.endswith(".openrouter.ai"):
        return Provider.OPENROUTER
    return Provider.CUSTOM


def env_layers() -> dict[str, str]:
    """The kernel's env chain merged into one mapping, process env highest.

    Same layers, same order as :func:`cs.config.load` (platform env file →
    ``~/.<slug>-cs/.env`` → repo-local ``.env`` → process environment), so a
    key read here and a key read by ``Settings`` resolve identically. Values
    are returned, never exported: nothing in the kernel mutates ``os.environ``.
    """
    from dotenv import dotenv_values

    from . import config as config_mod

    merged: dict[str, str] = {}
    for f in config_mod.env_file_chain():
        p = Path(f).expanduser()
        if p.exists():
            merged.update(
                {k.upper(): v for k, v in dotenv_values(p).items() if v is not None}
            )
    merged.update({k.upper(): v for k, v in os.environ.items()})
    return merged


def route_direct(env: Mapping[str, str] | None = None) -> bool:
    """Should a role-declared kernel call bypass the engine? Default: NO.

    ``CS_LLM_ROUTE=direct`` opts a clone into the provider path; anything else
    (including unset) keeps every call on the engine, so installing this kernel
    changes no clone's behavior until someone flips one env var. That variable
    is also the kill switch: routing goes wrong at 03:00, an operator sets it
    back to ``engine`` and the next cron tick is on the old path — no code
    change, no re-pin, no deploy.
    """
    e = dict(env) if env is not None else env_layers()
    return (e.get("CS_LLM_ROUTE") or "").strip().lower() == "direct"


class LLMEndpoint:
    """A resolved (provider, base_url, credential) triple + why it was chosen."""

    __slots__ = ("provider", "base_url", "api_key", "source")

    def __init__(self, provider: Provider, base_url: str | None, api_key: str | None,
                 source: str):
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key
        self.source = source

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return (f"LLMEndpoint(provider={self.provider.value}, "
                f"base_url={self.base_url!r}, api_key={mask_key(self.api_key)}, "
                f"source={self.source!r})")


def llm_env(env: Mapping[str, str] | None = None) -> LLMEndpoint:
    """Resolve which provider the kernel's own calls go to, and with what key.

    Order (first hit wins), all values from :func:`env_layers`:

      1. ``CS_LLM_PROVIDER`` — explicit. ``openrouter`` uses
         ``CS_LLM_BASE_URL`` or the canonical OpenRouter base; ``anthropic``
         forces the Anthropic default base even if a gateway URL is lying around.
      2. ``CS_LLM_BASE_URL`` / ``ANTHROPIC_BASE_URL`` — provider by detection.
      3. ``OPENROUTER_API_KEY`` present — OpenRouter at its canonical base.
      4. nothing — Anthropic direct with ``ANTHROPIC_API_KEY``.

    Every empty string is normalized to ``None`` on the way through, and the
    returned ``base_url`` is always a real URL — never ``None``, never ``""``.
    """
    e = dict(env) if env is not None else env_layers()

    def val(key: str) -> str | None:
        v = (e.get(key) or "").strip()
        return v or None

    forced = (val("CS_LLM_PROVIDER") or "").lower() or None
    configured_base = val("CS_LLM_BASE_URL") or val("ANTHROPIC_BASE_URL")
    or_key = val("CS_LLM_API_KEY") or val("OPENROUTER_API_KEY")
    anthropic_key = val("CS_LLM_API_KEY") or val("ANTHROPIC_API_KEY")

    if forced == Provider.OPENROUTER.value:
        return LLMEndpoint(Provider.OPENROUTER, configured_base or OPENROUTER_BASE_URL,
                           or_key, "CS_LLM_PROVIDER=openrouter")
    if forced == Provider.ANTHROPIC.value:
        return LLMEndpoint(Provider.ANTHROPIC, ANTHROPIC_DEFAULT_BASE_URL,
                           anthropic_key, "CS_LLM_PROVIDER=anthropic")
    if forced == Provider.CUSTOM.value:
        # A forced custom provider with no base URL must fail HERE, not fall
        # through: `build_client` would default the missing host to Anthropic's
        # and `detect_provider(None)` would put the gateway credential on
        # X-Api-Key — i.e. a config typo would send a custom-gateway secret to
        # a third party's API. Refusing to resolve is the only safe reading.
        if not configured_base:
            raise LLMEnvError(
                "CS_LLM_PROVIDER=custom requires CS_LLM_BASE_URL: without a "
                "host there is nowhere safe to send the credential"
            )
        return LLMEndpoint(Provider.CUSTOM, configured_base,
                           val("CS_LLM_API_KEY"), "CS_LLM_PROVIDER=custom")

    if configured_base:
        provider = detect_provider(configured_base)
        key = or_key if provider is not Provider.ANTHROPIC else anthropic_key
        return LLMEndpoint(provider, configured_base, key, "CS_LLM_BASE_URL")

    if val("OPENROUTER_API_KEY") or (val("CS_LLM_API_KEY") or "").startswith("sk-or-"):
        return LLMEndpoint(Provider.OPENROUTER, OPENROUTER_BASE_URL, or_key,
                           "OPENROUTER_API_KEY present")

    return LLMEndpoint(Provider.ANTHROPIC, ANTHROPIC_DEFAULT_BASE_URL, anthropic_key,
                       "default (Anthropic direct)")


def resolve_spec(spec: str, provider: Provider) -> str:
    """A model spec (pinned id or ``@family``) → the id to put on the wire.

    Anthropic direct speaks BARE ids (``claude-opus-5``) while the catalog is
    OpenRouter's and speaks prefixed ones (``anthropic/claude-opus-5``). The
    same family therefore resolves to the same model under both providers, with
    the vendor prefix stripped for the direct wire.

    The two also disagree on version punctuation: OpenRouter writes
    ``claude-haiku-4.5``, Anthropic's own API only accepts ``claude-haiku-4-5``
    (verified live 2026-07-30: the dotted form 404s on the direct wire, the
    dashed form answers). Dots between digits are normalized to dashes for the
    direct wire only.
    """
    import re

    from . import model_catalog

    resolved = model_catalog.resolve(spec)
    if provider is Provider.ANTHROPIC and resolved.startswith("anthropic/"):
        bare = resolved.split("/", 1)[1]
        return re.sub(r"(?<=\d)\.(?=\d)", "-", bare)
    return resolved


def default_model_for(role: Role, provider: Provider) -> str:
    """The built-in model for *role* under *provider*, ignoring configuration.

    A role with an EARNED family (``ROLE_FAMILIES``, a measurement on that
    role's real task) uses it; otherwise the role falls back to its tier's
    family (``TIER_FAMILIES``).

    An unknown provider (``custom``) borrows the OpenRouter defaults: a custom
    gateway is far more likely to speak prefixed OpenRouter-style ids than
    Anthropic's bare ones, and either way the operator is expected to set
    ``MODEL_<ROLE>`` — this is only what keeps the resolver total.
    """
    roles = ROLE_FAMILIES.get(provider, ROLE_FAMILIES.get(Provider.OPENROUTER, {}))
    earned = roles.get(role)
    if earned:
        return resolve_spec(earned, provider)
    table = TIER_FAMILIES.get(provider, TIER_FAMILIES[Provider.OPENROUTER])
    return resolve_spec(table[ROLE_TIER[role]], provider)


def model_for(role: Role, env: Mapping[str, str] | None = None) -> str:
    """Resolve the model id for *role*. First hit wins:

      1. ``MODEL_<ROLE>``  — e.g. ``MODEL_CLASSIFIER``
      2. ``MODEL_<TIER>``  — e.g. ``MODEL_WORKER``
      3. the built-in default for the resolved provider — a role's EARNED
         family (``ROLE_FAMILIES``) if it has one, else its tier's

    Any of the three may be a pinned id (``deepseek/deepseek-v4-pro``) or a
    family reference (``@deepseek-pro``, resolved to the line's newest member
    against the live catalog). Pinning always wins and is never second-guessed:
    reproducing an incident means running the exact model that produced it.

    Read from the env layers rather than from a ``Settings`` field on purpose:
    roles are added by editing :class:`Role`, and a parallel settings field per
    role would be a second place to forget.
    """
    e = dict(env) if env is not None else env_layers()
    provider = llm_env(e).provider
    explicit = (e.get(f"MODEL_{role.value.upper()}") or "").strip()
    if explicit:
        return resolve_spec(explicit, provider)
    tier = ROLE_TIER[role]
    tier_override = (e.get(f"MODEL_{tier.value.upper()}") or "").strip()
    if tier_override:
        return resolve_spec(tier_override, provider)
    return default_model_for(role, provider)


# ------------------------------------------------------------------- env file


def read_env(path: Path) -> list[str]:
    """Read an .env file into lines, preserving comments and blank lines."""
    with path.open("r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Set key=value pairs in an .env file, preserving order and comments.

    Keys are matched case-insensitively; unknown keys are appended at the end.
    A missing file is created with just the updates.
    """
    try:
        lines = read_env(path)
    except FileNotFoundError:
        lines = []
    out: list[str] = []
    written = {k.upper(): False for k in updates}

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            match = next((u for u in updates if u.upper() == key.upper()), None)
            if match is not None:
                written[match.upper()] = True
                indent = line[: line.index(key)]
                out.append(f"{indent}{key}={updates[match]}")
                continue
        out.append(line)

    for key, value in updates.items():
        if not written[key.upper()]:
            out.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def mask_key(key: str | None) -> str:
    """Redact a credential for display / logs."""
    if not key:
        return "(not set)"
    if len(key) <= 12:
        return "(set)"
    return f"{key[:5]}...{key[-4:]}"


def current_config(env: Mapping[str, str] | None = None) -> dict:
    """What the kernel's own LLM calls resolve to right now — safe to print."""
    e = dict(env) if env is not None else env_layers()
    endpoint = llm_env(e)
    return {
        "provider": endpoint.provider.value,
        "base_url": endpoint.base_url,
        "api_key": mask_key(endpoint.api_key),
        "source": endpoint.source,
        "models": {role.value: model_for(role, e) for role in Role},
    }


def check_connection(base_url: str | None, api_key: str | None, model: str,
                     timeout: float = 10.0) -> dict:
    """One minimal round trip against *base_url*, for a config/health verb.

    ``max_retries=0``: this must fail fast and report a single attempt's
    latency. The SDK default (2 retries with backoff) would inflate
    ``latency_ms`` and hide an unreachable host behind the reported timeout.
    """
    import time

    from .llm_client import build_client

    started = time.time()
    try:
        client = build_client(base_url=base_url, api_key=api_key).with_options(
            timeout=timeout, max_retries=0
        )
        client.messages.create(
            model=model,
            max_tokens=4,
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
        )
        return {"success": True, "error": None,
                "latency_ms": (time.time() - started) * 1000}
    except Exception as e:  # noqa: BLE001 — a health check reports, never raises
        return {"success": False, "error": f"{type(e).__name__}: {e}",
                "latency_ms": (time.time() - started) * 1000}
