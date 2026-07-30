"""The anthropic SDK client, built so the provider is a configuration value.

One construction path for Anthropic direct, OpenRouter, and any Anthropic-wire
gateway, plus the two response-shape helpers that stop a provider swap from
turning into silent data loss. Ported from ``octopus`` (``src/octopus/
llm_client.py``), whose scars are the reason each line here exists — every
comment below names a failure that actually happened in production, not a
hypothetical.

The SDK is imported lazily inside :func:`build_client` so that a kernel
installed without ``anthropic`` still runs every non-LLM verb and fails with an
actionable message only when a call is genuinely attempted.
"""
from __future__ import annotations

from typing import Any

from .model_config import (
    ANTHROPIC_DEFAULT_BASE_URL,
    Provider,
    detect_provider,
    llm_env,
)


class LLMDependencyError(RuntimeError):
    """The ``anthropic`` SDK is not installed in this environment."""


class TruncatedResponseError(RuntimeError):
    """The model hit ``max_tokens`` before finishing its output.

    A reasoning model reached through a gateway can spend its whole budget
    inside a thinking block and come back with no text block at all. That is a
    failed call, never an empty answer: returning ``""`` is how a paid-for turn
    silently disappears and a caller records a default label it never earned.
    """


def _credential_kwargs(base_url: str | None, api_key: str | None) -> dict[str, str]:
    """Route the credential onto the kwarg the provider authenticates with.

    Anthropic direct → ``api_key=`` (emits ``X-Api-Key``). OpenRouter / custom
    gateway → ``auth_token=`` (emits ``Authorization: Bearer``). Putting the
    credential on the wrong kwarg is exactly the 401 "Missing Authentication
    header" this function exists to prevent — and note that a **402** from a
    gateway is proof the auth worked, since it is only reachable after it.

    An empty credential returns no kwarg at all, leaving the SDK's own
    default-credential resolution intact for callers that rely on pure env
    fallback. *base_url* must already be normalized (``""`` → ``None``).
    """
    if not api_key:
        return {}
    if detect_provider(base_url) is Provider.ANTHROPIC:
        return {"api_key": api_key}
    return {"auth_token": api_key}


def build_client(*, base_url: str | None = None, api_key: str | None = None) -> Any:
    """An ``anthropic.Anthropic`` with provider-correct auth.

    Unset arguments fall back to the resolved kernel endpoint
    (:func:`cs.model_config.llm_env`), so ``build_client()`` with no arguments
    is the configured provider.

    Three things this does that a bare ``anthropic.Anthropic(...)`` does not:

    * **Empty string collapses to None.** A config writer that "returns to
      Anthropic" by writing ``ANTHROPIC_BASE_URL=""`` otherwise produces a
      CUSTOM detection (wrong auth header) against an empty, broken host.
    * **``base_url=`` is always passed explicitly** — the resolved gateway, or
      the SDK's own default constant. Omitting it lets the SDK re-read
      ``ANTHROPIC_BASE_URL`` from the process env, which may be that same
      broken ``""``.
    * **The unchosen credential attribute is nulled after construction.** Not
      every anthropic version guards this: 0.97.0 resolves each credential
      kwarg independently from ``os.environ`` when it was not passed, with no
      awareness that the other one was — so an ambient ``ANTHROPIC_API_KEY``
      rode along as a second ``X-Api-Key`` header next to the intended Bearer.
      Setting the attribute post-construction bypasses every version's own
      env-resolution logic instead of depending on its details, which is what
      makes this behave identically across SDK versions (verified here on the
      exact installed version — see ``tests/test_llm_client.py``).
    """
    try:
        import anthropic
    except ModuleNotFoundError as e:  # pragma: no cover - environment-dependent
        raise LLMDependencyError(
            "the anthropic SDK is required for kernel-owned LLM calls "
            "(pip install 'anthropic>=0.107')"
        ) from e

    endpoint = llm_env()
    resolved_base = (base_url if base_url is not None else endpoint.base_url) or None
    resolved_key = (api_key if api_key is not None else endpoint.api_key) or None

    kwargs: dict[str, Any] = _credential_kwargs(resolved_base, resolved_key)
    kwargs["base_url"] = resolved_base or ANTHROPIC_DEFAULT_BASE_URL

    client = anthropic.Anthropic(**kwargs)
    if "auth_token" in kwargs:
        client.api_key = None
    elif "api_key" in kwargs:
        client.auth_token = None
    return client


def extract_text(response: Any) -> str:
    """Concatenate the text block(s) of a Messages response.

    Never ``content[0].text``. An Anthropic-direct non-thinking reply is a
    single text block at position 0, which is why call sites everywhere index
    it — but a reasoning model reached through a gateway prepends a
    ``ThinkingBlock``, so position 0 has no ``.text`` and the call raises
    ``AttributeError``. In octopus that shape change silently dropped 141
    items before anyone noticed.

    Raises :class:`ValueError` when there is no text block at all, so an empty
    answer cannot be mistaken for a valid one.
    """
    parts = [
        block.text
        for block in getattr(response, "content", []) or []
        if getattr(block, "type", None) == "text"
    ]
    if not parts:
        raise ValueError("Messages response contained no text content block")
    return "".join(parts).strip()


def text_of(response: Any) -> str:
    """``extract_text`` with the truncation check FIRST.

    ``stop_reason == "max_tokens"`` must be inspected *before* the text is
    read: a model that spent its whole budget thinking returns a truncated (or
    absent) text block, and extracting it first turns a truncation into a
    plausible-looking short answer. This is the function call sites should use.
    """
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise TruncatedResponseError(
            "model stopped at max_tokens before completing its answer "
            f"(model={getattr(response, 'model', '?')})"
        )
    return extract_text(response)
