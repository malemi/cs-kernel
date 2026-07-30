"""Kernel-owned worker calls: single-shot, mechanical, cheap by construction.

This is the only place in the kernel that talks to an LLM directly. Everything
contextual or customer-facing stays an engine call (charter §4) — what belongs
here is the work that has a *fixed, checkable output*: one label out of a known
set, an extraction, a yes/no. Those do not need a customer-facing model, and
routing them through the engine's brain is the waste this module removes.

Call sites never name a model. They name a :class:`cs.model_config.Role`;
``model_for(role)`` resolves the id from env → tier default → provider default.
No prompt text lives here either: the prompt belongs to the caller, so the
kernel stays company-neutral.

    from cs import worker_llm
    from cs.model_config import Role

    label = worker_llm.classify(prompt, {"YES", "NO", "MAYBE"})
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable

from . import llm_client
from .model_config import Provider, Role, call_cost, llm_env, model_for


@dataclass(frozen=True)
class Completion:
    """One worker call: the text plus what it cost to get it."""

    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None  # None = not established; NEVER a guessed price
    latency_ms: float
    stop_reason: str | None


# Sized for a REASONING model, not for the answer. On an Anthropic-shaped API
# max_tokens is a ceiling, not a reservation — unused budget is not billed — so
# the only cost of a generous default is the worst case, while a tight one is a
# guaranteed failure.
#
# Measured 2026-07-28 on the batch-2 verdict task (one line of output, ~1k-token
# prompt): the models worth recommending spend most of the budget thinking
# before they emit anything. Median OUTPUT tokens for a single-line answer —
# claude-sonnet-5 39, glm-5.2 123, deepseek-v4-pro 434, gpt-5.6-luna-pro 488,
# qwen3.7-max 2013. At 512 the recommended `@glm` truncates on this very
# prompt; at 2048 it did not truncate once in 61 calls. An earlier round at 64
# lost two models entirely (61/61 truncated) and a third on 34 of 61.
#
# Truncation raises rather than returning a partial answer (see `text_of`), so
# a too-small budget is loud — but the default should not need discovering.
DEFAULT_MAX_TOKENS = 2048


class LLMConfigError(RuntimeError):
    """The provider/model/credential combination cannot work as configured.

    Raised BEFORE any request goes out, so the message names the configuration
    mistake instead of leaving the provider to report a downstream symptom.
    """


class NoLabelError(ValueError):
    """The model answered, but with nothing from the allowed label set."""


def call(
    prompt: str,
    *,
    role: Role = Role.CLASSIFIER,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float | None = 0.0,
    timeout: float = 60.0,
    max_retries: int = 2,
) -> Completion:
    """One Messages round trip, with the truncation check applied first.

    Raises :class:`cs.llm_client.TruncatedResponseError` when the model hit
    ``max_tokens`` (a paid call that produced nothing must fail loudly), and
    ``ValueError`` when the response carries no text block at all. Callers that
    must not crash — a campaign loop, say — catch those explicitly rather than
    receiving a silent default.
    """
    endpoint = llm_env()
    resolved_model = model or model_for(role)

    # A gateway-style id ("vendor/model") can never resolve on the Anthropic
    # direct wire, where ids are bare. Reaching here with both means the
    # credential lookup silently fell through to Anthropic — most often because
    # no manifest was found, so ~/.<slug>-cs/.env was never in the env chain and
    # OPENROUTER_API_KEY was invisible. Left alone the request goes out and
    # comes back a bare 404 naming the model, which sends the reader hunting a
    # model that exists and is fine. Say what is actually wrong instead.
    if endpoint.provider is Provider.ANTHROPIC and "/" in resolved_model:
        raise LLMConfigError(
            f"model {resolved_model!r} is a gateway id, but the resolved "
            f"provider is Anthropic direct ({endpoint.source}). No gateway "
            f"credential was found: set OPENROUTER_API_KEY (or CS_LLM_PROVIDER "
            f"+ CS_LLM_BASE_URL + CS_LLM_API_KEY), and check that the manifest "
            f"is discoverable so ~/.<slug>-cs/.env is in the env chain."
        )

    client = llm_client.build_client(
        base_url=endpoint.base_url, api_key=endpoint.api_key
    ).with_options(timeout=timeout, max_retries=max_retries)

    kwargs: dict = {
        "model": resolved_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    if temperature is not None:
        kwargs["temperature"] = temperature

    started = time.time()
    response = client.messages.create(**kwargs)
    latency_ms = (time.time() - started) * 1000

    text = llm_client.text_of(response)  # truncation checked BEFORE extraction
    usage = getattr(response, "usage", None)
    return Completion(
        text=text,
        model=resolved_model,
        provider=endpoint.provider.value,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cost_usd=call_cost(response, resolved_model),
        latency_ms=latency_ms,
        stop_reason=getattr(response, "stop_reason", None),
    )


def complete(prompt: str, **kwargs) -> str:
    """:func:`call` when only the text matters."""
    return call(prompt, **kwargs).text


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def match_label(text: str, labels: Iterable[str]) -> str | None:
    """The first token of *text* that is one of *labels*, else ``None``.

    Token-based rather than ``text.strip() == label``: a small model asked for
    one word still answers "CONFERMA." or "Label: CONFERMA", and a whole
    classification is not worth discarding over a full stop. Matching is
    case-insensitive; the label is returned in the caller's own casing.
    """
    by_upper = {str(label).upper(): label for label in labels}
    for token in _TOKEN_RE.findall(text or ""):
        hit = by_upper.get(token.upper())
        if hit is not None:
            return hit
    return None


def classify_detailed(
    prompt: str,
    labels: Iterable[str],
    *,
    role: Role = Role.CLASSIFIER,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = 60.0,
    max_retries: int = 2,
) -> tuple[str, Completion]:
    """Resolve *prompt* to one of *labels*, returning the call's cost too.

    ``max_tokens`` is sized for the model's THINKING, not for the one word this
    expects back. Budgeting for the answer is the intuitive mistake and it is a
    guaranteed failure on a reasoning model: at 64 tokens — which reads like
    generous headroom for a single label — two of seven candidates truncated on
    all 61 items of the 2026-07-28 A/B and a third on 34 of them, having spent
    the entire budget before emitting a single text block.

    Raises :class:`NoLabelError` when the answer contains no allowed label —
    never a default. A wrong-but-plausible label written into campaign state is
    worse than an error the caller has to handle, because it looks decided.
    """
    labels = list(labels)
    if not labels:
        raise ValueError("classify() needs a non-empty label set")
    result = call(
        prompt,
        role=role,
        model=model,
        system=system,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
    )
    hit = match_label(result.text, labels)
    if hit is None:
        raise NoLabelError(
            f"model {result.model} answered {result.text[:120]!r}, "
            f"which contains none of {sorted(labels)}"
        )
    return hit, result


def classify(prompt: str, labels: Iterable[str], **kwargs) -> str:
    """:func:`classify_detailed` when only the label matters."""
    return classify_detailed(prompt, labels, **kwargs)[0]
