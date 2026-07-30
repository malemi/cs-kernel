"""The model catalog: which models exist, when they shipped, what they cost.

Why this is fetched and not a constant
--------------------------------------
A hand-written list of model ids is wrong within weeks. Measured on
2026-07-28 against the live OpenRouter catalog, a curated list written eight
days earlier already named ``anthropic/claude-opus-4-8`` (superseded by
``claude-opus-5`` on 07-24), ``moonshotai/kimi-k2.6`` (superseded by
``kimi-k3`` on 07-16) and ``google/gemini-3.5-flash`` (superseded by
``gemini-3.6-flash`` on 07-21). Its prices had drifted too: it priced
``z-ai/glm-5.2`` at $0.45/$3.31 when the real rates were $0.77/$2.42 — a
number used for cost accounting, wrong by 37% on input.

So the catalog is refreshed from ``GET /v1/models``, which needs **no API
key**, and reports for every model an id, a ``created`` timestamp and the
real per-token prices. An operator picks a FAMILY (":= a product line") and
the newest member of that family is resolved at call time. Pinning an exact
id still works and still wins — a family is the default, not a cage.

The static tables below are the offline fallback and nothing else. They are
consulted only when the network is unavailable and no cache exists.

What this module deliberately does NOT do
-----------------------------------------
Choose *for* you on quality. ``/v1/models`` carries no capability score, so
the only machine-readable ranking here is recency and price. The
``FAMILY_NOTES`` hints are hand-maintained operator guidance, dated, and
explicitly not a benchmark — see the note on that table.
"""

from __future__ import annotations

import fnmatch
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

# No API key required for this endpoint — it is the public model index.
MODELS_URL = "https://openrouter.ai/api/v1/models"

# A day. Model lines ship on the order of weeks, so a daily refresh is far
# more often than the data changes, and one stale day never picks a model
# that does not exist (ids are never recycled).
CACHE_TTL_SECONDS = 24 * 3600

FAMILY_PREFIX = "@"


# --------------------------------------------------------------------- types


@dataclass(frozen=True)
class ModelInfo:
    """One catalog entry, normalized. Prices are USD per 1M tokens."""

    id: str
    name: str
    created: int  # unix seconds
    input_per_m: float
    output_per_m: float
    context_length: int

    @property
    def blended_per_m(self) -> float:
        """A single comparable number: the mean of input and output rates.

        Crude on purpose — the real blend depends on the workload's token
        ratio. Used only to order a menu, never to bill anything.
        """
        return (self.input_per_m + self.output_per_m) / 2


@dataclass(frozen=True)
class Family:
    """A product line, matched by glob over the model id.

    ``exclude`` removes the variants that share a line's name but are not
    the line: batch endpoints, ``:free`` mirrors, previews, and the
    modality spin-offs (``-image``). Without them "newest anthropic opus"
    resolves to ``claude-opus-5-fast``, which is the same model at double
    the price.
    """

    name: str
    match: str
    exclude: tuple[str, ...] = ()

    def members(self, models: Iterable[ModelInfo]) -> list[ModelInfo]:
        """Every model in this family, newest first; ties broken by id so the
        result is deterministic when a vendor ships a line on one day."""
        hits = [
            m for m in models
            if fnmatch.fnmatch(m.id, self.match)
            and not any(fnmatch.fnmatch(m.id, e) for e in self.exclude)
        ]
        hits.sort(key=lambda m: (-m.created, m.id))
        return hits


# Variants that are never what "the newest model of this line" means.
_COMMON_EXCLUDES = ("*:*", "*-preview", "*-preview-*", "*-image", "*-image-*")


def _fam(name: str, match: str, *extra: str) -> Family:
    return Family(name=name, match=match, exclude=_COMMON_EXCLUDES + extra)


# The curated families. Adding one is a kernel change on purpose: it is a
# statement that a product line is worth offering to every clone, and the
# glob has to be checked against the live catalog (tests/test_llm_client.py
# does exactly that when the network is up).
FAMILIES: dict[str, Family] = {
    # --- frontier / lead tier -------------------------------------------
    "claude-opus":    _fam("claude-opus", "anthropic/claude-opus-*", "*-fast"),
    "claude-sonnet":  _fam("claude-sonnet", "anthropic/claude-sonnet-*"),
    "gpt-flagship":   _fam("gpt-flagship", "openai/gpt-*-sol", "*-pro"),
    "kimi":           _fam("kimi", "moonshotai/kimi-k[0-9]*", "*-code", "*-thinking"),
    "qwen-max":       _fam("qwen-max", "qwen/qwen*-max"),
    # --- capable + cheap: the interesting middle ------------------------
    "deepseek-pro":   _fam("deepseek-pro", "deepseek/deepseek-v*-pro"),
    # "*v" and "*v-*" drop the vision line (glm-4.6v, glm-5v-turbo) — a
    # different product that shares the version numbering.
    "glm":            _fam("glm", "z-ai/glm-[0-9]*", "*-turbo", "*v", "*v-*", "*-flash"),
    "mimo-pro":       _fam("mimo-pro", "xiaomi/mimo-*-pro"),
    "gpt-worker":     _fam("gpt-worker", "openai/gpt-*-luna-pro"),
    "minimax":        _fam("minimax", "minimax/minimax-m[0-9]*", "*-her"),
    "mistral-medium": _fam("mistral-medium", "mistralai/mistral-medium-*"),
    "nemotron":       _fam("nemotron", "nvidia/nemotron-[0-9.]*-ultra*"),
    # --- small / fast ----------------------------------------------------
    "deepseek-flash": _fam("deepseek-flash", "deepseek/deepseek-v*-flash"),
    "gemini-flash":   _fam("gemini-flash", "google/gemini-[0-9.]*-flash", "*-lite*"),
    "gemini-lite":    _fam("gemini-lite", "google/gemini-[0-9.]*-flash-lite"),
    # fnmatch's `[0-9.]*` is one digit THEN any suffix — it admits
    # qwen3-coder-flash, a coding model, not the general line. Excluded by name.
    "qwen-flash":     _fam("qwen-flash", "qwen/qwen[0-9.]*-flash", "*coder*"),
    "claude-haiku":   _fam("claude-haiku", "anthropic/claude-haiku-*"),
}

# Hand-maintained operator guidance, NOT a benchmark. It says what a line is
# FOR, so someone choosing from `cs llm` has something to go on beyond price.
# Dated because it rots: re-read it before trusting it.
#   Last reviewed: 2026-07-28.
FAMILY_NOTES: dict[str, str] = {
    "claude-opus":    "Anthropic frontier — the quality ceiling, priced like it",
    "claude-sonnet":  "Anthropic balanced — the safe default for hard text work",
    "gpt-flagship":   "OpenAI flagship",
    "kimi":           "Strongest open-weights line; agentic/tool work",
    "qwen-max":       "Alibaba flagship; strong reasoning",
    "deepseek-pro":   "Frontier-class at ~1/20 the flagship price — best value",
    "glm":            "Near-frontier coding/reasoning, cheap",
    "mimo-pro":       "Multimodal reasoning, cheap",
    "gpt-worker":     "OpenAI's cheap reasoning variant",
    "minimax":        "Multimodal, long context, cheap",
    "mistral-medium": "European; mid-tier general purpose",
    "nemotron":       "NVIDIA open 550B",
    "deepseek-flash": "Ultra-cheap, 1M context — mechanical work only",
    "gemini-flash":   "Google's fast line",
    "gemini-lite":    "Google's cheapest",
    "qwen-flash":     "Cheapest capable model in the catalog",
    "claude-haiku":   "Anthropic small — cheap but rarely the right answer",
}

# Offline fallback ONLY. Snapshot of the live catalog taken 2026-07-28; used
# when the network is down AND no cache file exists, so that a clone without
# connectivity still resolves to a real id instead of crashing. Never
# consulted when live data or a cache is available.
STATIC_FALLBACK: dict[str, tuple[str, float, float]] = {
    # family:        (model id,                        input$/1M, output$/1M)
    "claude-opus":    ("anthropic/claude-opus-5", 5.00, 25.00),
    "claude-sonnet":  ("anthropic/claude-sonnet-5", 2.00, 10.00),
    "gpt-flagship":   ("openai/gpt-5.6-sol", 5.00, 30.00),
    "kimi":           ("moonshotai/kimi-k3", 3.00, 15.00),
    "qwen-max":       ("qwen/qwen3.7-max", 1.48, 4.42),
    "deepseek-pro":   ("deepseek/deepseek-v4-pro", 0.43, 0.87),
    "glm":            ("z-ai/glm-5.2", 0.77, 2.42),
    "mimo-pro":       ("xiaomi/mimo-v2.5-pro", 0.43, 0.87),
    "gpt-worker":     ("openai/gpt-5.6-luna-pro", 0.50, 3.00),
    "minimax":        ("minimax/minimax-m3", 0.30, 1.20),
    "mistral-medium": ("mistralai/mistral-medium-3-5", 1.50, 7.50),
    "nemotron":       ("nvidia/nemotron-3-ultra-550b-a55b", 0.50, 2.20),
    "deepseek-flash": ("deepseek/deepseek-v4-flash", 0.14, 0.28),
    "gemini-flash":   ("google/gemini-3.6-flash", 1.50, 7.50),
    "gemini-lite":    ("google/gemini-3.5-flash-lite", 0.30, 2.50),
    "qwen-flash":     ("qwen/qwen3.7-flash", 0.03, 0.13),
    "claude-haiku":   ("anthropic/claude-haiku-4.5", 1.00, 5.00),
}


class CatalogUnavailable(RuntimeError):
    """No live catalog, no cache — the caller must decide whether to fall back."""


# ------------------------------------------------------------------- fetching


def _parse(entry: Mapping) -> ModelInfo | None:
    """One raw ``/v1/models`` entry → :class:`ModelInfo`, or None if unusable.

    Prices arrive as per-token decimal STRINGS ("0.00000043"); float() on the
    string is exact enough and multiplying by 1e6 gives the per-1M rate the
    rest of the system speaks. An entry missing an id or a price is skipped
    rather than defaulted: a fabricated zero price is how a cost report ends
    up claiming a run was free.
    """
    model_id = entry.get("id")
    pricing = entry.get("pricing") or {}
    if not model_id:
        return None
    try:
        input_per_m = float(pricing["prompt"]) * 1e6
        output_per_m = float(pricing["completion"]) * 1e6
    except (KeyError, TypeError, ValueError):
        return None
    return ModelInfo(
        id=model_id,
        name=entry.get("name") or model_id,
        created=int(entry.get("created") or 0),
        input_per_m=input_per_m,
        output_per_m=output_per_m,
        context_length=int(entry.get("context_length") or 0),
    )


def fetch(timeout: float = 15.0) -> list[ModelInfo]:
    """GET the live catalog. Raises on any network/parse failure."""
    import httpx

    response = httpx.get(MODELS_URL, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    models = [m for m in (_parse(e) for e in payload.get("data") or []) if m]
    if not models:
        raise CatalogUnavailable(f"{MODELS_URL} returned no usable entries")
    return models


# --------------------------------------------------------------------- cache


def default_cache_path() -> Path:
    """``<state_dir>/model_catalog.json`` when a manifest is present.

    Every kernel state path derives from ``Settings.state_dir`` and this is no
    exception. But the LLM layer is also usable standalone — imported from a
    plain venv with only ``OPENROUTER_API_KEY`` set and no clone around it —
    and there ``config.load()`` legitimately has no manifest to find. That
    case gets an XDG cache dir; it is a cache, so a second location is not a
    second source of truth.
    """
    try:
        from .config import load

        return load().state_dir / "model_catalog.json"
    except Exception:  # noqa: BLE001 — no manifest is a normal standalone case
        return Path.home() / ".cache" / "cs-kernel" / "model_catalog.json"


def _read_cache(path: Path, ttl: float) -> list[ModelInfo] | None:
    """A damaged cache is a MISSING cache, never an error.

    The whole body sits under the except, not just the JSON parse: a file that
    decodes to a list instead of a dict, or carries a non-numeric
    ``fetched_at``, used to raise straight through ``load_models`` — past the
    ``CatalogUnavailable`` handling — and one corrupt file took out every
    ``@family`` resolution until someone deleted it by hand. Any unusable shape
    reads as "no cache", which lets the fetch/static-fallback chain do its job.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if ttl > 0 and time.time() - float(raw.get("fetched_at") or 0) > ttl:
            return None
        models = [m for m in (_parse(e) for e in raw.get("models") or []) if m]
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    return models or None


def _write_cache(path: Path, models: list[ModelInfo]) -> None:
    payload = {
        "fetched_at": time.time(),
        "source": MODELS_URL,
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "created": m.created,
                "context_length": m.context_length,
                # Stored back in the wire format so _parse is the ONE reader.
                "pricing": {
                    "prompt": repr(m.input_per_m / 1e6),
                    "completion": repr(m.output_per_m / 1e6),
                },
            }
            for m in models
        ],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replace: a crash mid-write must leave the old cache, not half
        # a JSON file (which would read as "no cache" — safe, but wasteful).
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # a cache we cannot write is a slow catalog, not a broken one


def load_models(*, refresh: bool = False, cache_path: Path | None = None,
                ttl: float = CACHE_TTL_SECONDS,
                timeout: float = 15.0) -> list[ModelInfo]:
    """The catalog: fresh cache, else live fetch, else stale cache.

    ``refresh=True`` skips the cache read and forces a fetch. A stale cache
    beats no catalog at all, so a fetch failure falls back to it regardless
    of age — an id from last month resolves; an exception resolves nothing.
    """
    path = cache_path or default_cache_path()

    if not refresh:
        cached = _read_cache(path, ttl)
        if cached:
            return cached

    try:
        models = fetch(timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — offline is a supported state
        stale = _read_cache(path, ttl=0)
        if stale:
            return stale
        raise CatalogUnavailable(f"no live catalog and no cache: {exc}") from exc

    _write_cache(path, models)
    return models


# ------------------------------------------------------------------ resolving


def is_family_ref(spec: str) -> bool:
    """``@deepseek-pro`` is a family reference; ``deepseek/deepseek-v4-pro`` is
    a pinned id. No model id starts with ``@``, so the marker is unambiguous."""
    return spec.startswith(FAMILY_PREFIX)


def family_name(spec: str) -> str:
    return spec[len(FAMILY_PREFIX):] if is_family_ref(spec) else spec


def newest(family: str, models: Iterable[ModelInfo]) -> ModelInfo | None:
    fam = FAMILIES.get(family_name(family))
    if fam is None:
        return None
    members = fam.members(models)
    return members[0] if members else None


def resolve(spec: str, *, models: Iterable[ModelInfo] | None = None,
            **load_kw) -> str:
    """Turn a model spec into a concrete model id.

    A pinned id passes through untouched — that is the escape hatch and it
    always wins. A ``@family`` reference resolves to the family's newest
    member; if the catalog is unreachable it falls back to the static
    snapshot, and only an unknown family name raises.
    """
    if not is_family_ref(spec):
        return spec

    name = family_name(spec)
    if name not in FAMILIES:
        raise KeyError(
            f"unknown model family {name!r}; known: {', '.join(sorted(FAMILIES))}"
        )

    if models is None:
        try:
            models = load_models(**load_kw)
        except CatalogUnavailable:
            models = None

    if models is not None:
        found = newest(name, models)
        if found is not None:
            return found.id

    return STATIC_FALLBACK[name][0]


def token_rates(model_id: str, *, models: Iterable[ModelInfo] | None = None,
                **load_kw) -> tuple[float, float] | None:
    """(input, output) USD per 1M tokens for *model_id*, or None if unknown.

    Exact id match only. A prefix-stripped or fuzzy match would silently
    price one model at another's rates, and an unknown model must read as
    unknown — a wrong cost is worse than an absent one.
    """
    if models is None:
        try:
            models = load_models(**load_kw)
        except CatalogUnavailable:
            models = []

    for m in models:
        if m.id == model_id:
            return (m.input_per_m, m.output_per_m)

    for fallback_id, input_per_m, output_per_m in STATIC_FALLBACK.values():
        if fallback_id == model_id:
            return (input_per_m, output_per_m)

    return None


def menu(tier_families: Iterable[str], *,
         models: Iterable[ModelInfo] | None = None,
         **load_kw) -> list[dict]:
    """Rows for an interactive picker: family, resolved id, date, price, note.

    Ordered by blended price ascending, so the cheapest capable option reads
    first and the operator sees what the extra money buys.
    """
    import datetime as dt

    if models is None:
        try:
            models = load_models(**load_kw)
        except CatalogUnavailable:
            models = []
    models = list(models)

    rows: list[dict] = []
    for name in tier_families:
        info = newest(name, models)
        if info is not None:
            shipped = dt.datetime.fromtimestamp(info.created, dt.timezone.utc)
            rows.append({
                "family": name,
                "model": info.id,
                "shipped": shipped.strftime("%Y-%m-%d"),
                "input_per_m": info.input_per_m,
                "output_per_m": info.output_per_m,
                "blended": info.blended_per_m,
                "context": info.context_length,
                "note": FAMILY_NOTES.get(name, ""),
                "live": True,
            })
        elif name in STATIC_FALLBACK:
            model_id, input_per_m, output_per_m = STATIC_FALLBACK[name]
            rows.append({
                "family": name,
                "model": model_id,
                "shipped": "(offline)",
                "input_per_m": input_per_m,
                "output_per_m": output_per_m,
                "blended": (input_per_m + output_per_m) / 2,
                "context": 0,
                "note": FAMILY_NOTES.get(name, ""),
                "live": False,
            })
    rows.sort(key=lambda r: r["blended"])
    return rows
