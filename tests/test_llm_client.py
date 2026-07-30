#!/usr/bin/env python3
"""Provider-swap semantics — the gates that decide whether a model change is
config or a 401.

Every assertion here is about a failure that has actually happened in
production (octopus, 2026-07): the credential on the wrong kwarg, an ambient
env key riding along as a second auth header, an empty ``base_url`` detected as
a custom gateway, a ThinkingBlock at ``content[0]``, and a truncated answer read
as a valid one.

The header assertions are made against the ACTUAL request the installed
anthropic SDK would send (``_build_request``), not against our own kwargs —
"no new dependency" is not the same as "version-independent behaviour", so the
check has to run through whichever SDK version is really installed.

No network. Run: python tests/test_llm_client.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs import llm_client, worker_llm  # noqa: E402
from cs.model_config import (  # noqa: E402
    ANTHROPIC_DEFAULT_BASE_URL,
    OPENROUTER_BASE_URL,
    ROLE_TIER,
    LLMEndpoint,
    Provider,
    Role,
    Tier,
    call_cost,
    detect_provider,
    llm_env,
    mask_key,
    model_for,
    read_env,
    token_rates,
    write_env,
)

FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global FAIL
    if cond:
        print(f"  ok   {label}")
    else:
        FAIL = 1
        print(f"  FAIL {label} {detail}")


def _raises(exc, fn) -> bool:
    """True iff *fn* raises *exc*. A gate that must fail LOUD is only proven by
    catching the specific type — `except Exception` would pass on a typo."""
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def request_headers(client) -> tuple[dict, str]:
    """The auth headers + URL of the request this client would really send."""
    from anthropic._models import FinalRequestOptions

    req = client._build_request(
        FinalRequestOptions.construct(method="post", url="/v1/messages", json_data={})
    )
    auth = {
        k.lower(): v
        for k, v in req.headers.items()
        if k.lower() in ("x-api-key", "authorization")
    }
    return auth, str(req.url)


# --------------------------------------------------------------- detection
print("detect_provider")
check("None -> anthropic", detect_provider(None) is Provider.ANTHROPIC)
check('"" -> anthropic (never CUSTOM)', detect_provider("") is Provider.ANTHROPIC)
check("api.anthropic.com -> anthropic",
      detect_provider("https://api.anthropic.com") is Provider.ANTHROPIC)
check("openrouter -> openrouter",
      detect_provider(OPENROUTER_BASE_URL) is Provider.OPENROUTER)
check("other host -> custom",
      detect_provider("https://gateway.example.test/api") is Provider.CUSTOM)
# Host match, not substring: a corp proxy that MENTIONS a provider in its path
# is a custom gateway, and misdetecting it flips the auth header (Bearer ->
# X-Api-Key), which is a 401 at best and a credential on the wrong wire at worst.
check("a path mentioning anthropic is NOT Anthropic",
      detect_provider("https://proxy.corp/anthropic") is Provider.CUSTOM)
check("a lookalike host is NOT OpenRouter",
      detect_provider("https://openrouter.ai.evil.test") is Provider.CUSTOM)
check("a real subdomain still matches",
      detect_provider("https://gateway.anthropic.com/v1") is Provider.ANTHROPIC)

# The two wire dialects: OpenRouter writes claude-haiku-4.5, Anthropic direct
# only accepts claude-haiku-4-5 (dotted form 404s — verified live 2026-07-30).
from cs.model_config import resolve_spec  # noqa: E402

check("dotted version normalized for the direct wire",
      resolve_spec("anthropic/claude-haiku-4.5", Provider.ANTHROPIC)
      == "claude-haiku-4-5")
check("the OpenRouter wire keeps the dotted id untouched",
      resolve_spec("anthropic/claude-haiku-4.5", Provider.OPENROUTER)
      == "anthropic/claude-haiku-4.5")
check("...and the normalized direct id is priced",
      token_rates("claude-haiku-4-5") is not None)

# ------------------------------------------------------------ build_client
print("build_client (against the installed anthropic SDK)")
import anthropic  # noqa: E402

print(f"  (anthropic {anthropic.__version__})")

# An ambient key of BOTH kinds, so a leak in either direction is visible.
# Pre-existing values are restored afterwards: on the operator's machine a real
# ANTHROPIC_API_KEY is legitimately in the environment, and a test runner that
# deletes it would break whatever runs in the same process next.
_saved_ambient = {k: os.environ.get(k)
                  for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
os.environ["ANTHROPIC_API_KEY"] = "ambient-x-api-key"
os.environ["ANTHROPIC_AUTH_TOKEN"] = "ambient-bearer"

c = llm_client.build_client(base_url=OPENROUTER_BASE_URL, api_key="sk-or-test")
auth, url = request_headers(c)
check("openrouter -> Bearer only", auth == {"authorization": "Bearer sk-or-test"}, auth)
check("openrouter url keeps /api + SDK's /v1/messages",
      url == "https://openrouter.ai/api/v1/messages", url)
check("openrouter -> api_key attribute nulled", c.api_key is None)

c = llm_client.build_client(base_url=ANTHROPIC_DEFAULT_BASE_URL, api_key="sk-ant-test")
auth, url = request_headers(c)
check("anthropic -> X-Api-Key only", auth == {"x-api-key": "sk-ant-test"}, auth)
check("anthropic default base_url passed explicitly",
      url == f"{ANTHROPIC_DEFAULT_BASE_URL}/v1/messages", url)
check("anthropic -> auth_token attribute nulled", c.auth_token is None)

# `base_url=None` means "whatever the clone is configured for", NOT "Anthropic"
# — the two are the same only on a machine with no gateway configured, and
# asserting Anthropic here made this file pass or fail depending on the
# directory it was run from. Pin the endpoint instead of inheriting one.
_real_llm_env = llm_client.llm_env
llm_client.llm_env = lambda: LLMEndpoint(
    Provider.OPENROUTER, OPENROUTER_BASE_URL, "sk-or-configured", "test")
try:
    c = llm_client.build_client()
    auth, url = request_headers(c)
    check("no arguments -> the CONFIGURED endpoint, not a hardcoded default",
          url == "https://openrouter.ai/api/v1/messages", url)
    check("no arguments -> the configured credential on the right header",
          auth == {"authorization": "Bearer sk-or-configured"}, auth)
finally:
    llm_client.llm_env = _real_llm_env

c = llm_client.build_client(base_url="", api_key="sk-ant-test")
auth, url = request_headers(c)
check('empty base_url collapses to the Anthropic default (not a broken host)',
      url == f"{ANTHROPIC_DEFAULT_BASE_URL}/v1/messages", url)
check('empty base_url still uses X-Api-Key', auth == {"x-api-key": "sk-ant-test"}, auth)

c = llm_client.build_client(base_url="https://gateway.example.test/api", api_key="tok")
auth, url = request_headers(c)
check("custom gateway -> Bearer", auth == {"authorization": "Bearer tok"}, auth)

for _k, _v in _saved_ambient.items():
    if _v is None:
        os.environ.pop(_k, None)
    else:
        os.environ[_k] = _v

# ----------------------------------------------------------- response shape
print("extract_text / text_of")


class _Block:
    def __init__(self, type_, text=None):
        self.type = type_
        if text is not None:
            self.text = text


class _Resp:
    def __init__(self, blocks, stop_reason="end_turn", model="m", usage=None):
        self.content = blocks
        self.stop_reason = stop_reason
        self.model = model
        self.usage = usage


thinking_first = _Resp([_Block("thinking"), _Block("text", "CONFERMA")])
check("skips a leading ThinkingBlock",
      llm_client.extract_text(thinking_first) == "CONFERMA")
check("joins multiple text blocks",
      llm_client.extract_text(_Resp([_Block("text", "A "), _Block("text", "B")])) == "A B")
try:
    llm_client.extract_text(_Resp([_Block("thinking")]))
    check("no text block raises", False)
except ValueError:
    check("no text block raises", True)

try:
    llm_client.text_of(_Resp([_Block("text", "CONF")], stop_reason="max_tokens"))
    check("max_tokens raises BEFORE extracting", False)
except llm_client.TruncatedResponseError:
    check("max_tokens raises BEFORE extracting", True)
check("text_of passes a normal response through",
      llm_client.text_of(thinking_first) == "CONFERMA")

# ------------------------------------------------------------- label match
print("match_label")
labels = {"CONFERMA", "RIPROGRAMMA", "DOMANDA", "DISDETTA", "AUTORESPONDER", "ALTRO"}
check("bare word", worker_llm.match_label("CONFERMA", labels) == "CONFERMA")
check("trailing punctuation", worker_llm.match_label("CONFERMA.", labels) == "CONFERMA")
check("prefixed sentence",
      worker_llm.match_label("The answer is: DOMANDA", labels) == "DOMANDA")
check("case-insensitive", worker_llm.match_label("conferma", labels) == "CONFERMA")
check("no label -> None", worker_llm.match_label("boh", labels) is None)
check("first label wins",
      worker_llm.match_label("ALTRO not CONFERMA", labels) == "ALTRO")

# -------------------------------------------------------- model resolution
print("model_for / llm_env")

# HERMETIC from here on: the tier defaults are `@family` refs, so model_for()
# reaches the catalog. Left alone it would fetch the LIVE catalog and rewrite
# the operator's real cache file (~/.<slug>-cs/model_catalog.json) as a side
# effect of running the tests — observed once: the suite refreshed production
# state and its outcome could drift with whatever the vendor shipped that day.
# Point the fetch at an unroutable host and the cache at a temp file so every
# resolution below lands on the static snapshot, deterministically.
from cs import model_catalog as _mc  # noqa: E402

_mc.MODELS_URL = "http://127.0.0.1:9/unroutable"
_hermetic_dir = tempfile.TemporaryDirectory()
_mc.default_cache_path = lambda: Path(_hermetic_dir.name) / "cache.json"

E_OR = {"OPENROUTER_API_KEY": "sk-or-x"}
check("OpenRouter key alone selects OpenRouter",
      llm_env(E_OR).provider is Provider.OPENROUTER)
check("...at the canonical base", llm_env(E_OR).base_url == OPENROUTER_BASE_URL)
check("worker default is an OpenRouter id",
      "/" in model_for(Role.CLASSIFIER, E_OR))
check("MODEL_WORKER overrides the default",
      model_for(Role.CLASSIFIER, {**E_OR, "MODEL_WORKER": "w/x"}) == "w/x")
check("MODEL_CLASSIFIER beats MODEL_WORKER",
      model_for(Role.CLASSIFIER,
                {**E_OR, "MODEL_WORKER": "w/x", "MODEL_CLASSIFIER": "c/y"}) == "c/y")
check("empty override is ignored",
      model_for(Role.CLASSIFIER, {**E_OR, "MODEL_CLASSIFIER": ""}) != "")

E_ANT = {"ANTHROPIC_API_KEY": "sk-ant-x"}
check("no gateway key -> Anthropic direct",
      llm_env(E_ANT).provider is Provider.ANTHROPIC)
check("...with the Anthropic key",
      llm_env(E_ANT).api_key == "sk-ant-x")
check("anthropic worker default is a bare id",
      "/" not in model_for(Role.CLASSIFIER, E_ANT))
check("CS_LLM_PROVIDER=anthropic wins over a present OpenRouter key",
      llm_env({**E_OR, **E_ANT, "CS_LLM_PROVIDER": "anthropic"}).provider
      is Provider.ANTHROPIC)
check("CS_LLM_BASE_URL selects the gateway",
      llm_env({**E_OR, "CS_LLM_BASE_URL": "https://gw.example.test"}).provider
      is Provider.CUSTOM)
check('ANTHROPIC_BASE_URL="" does not select a custom gateway',
      llm_env({**E_ANT, "ANTHROPIC_BASE_URL": ""}).provider is Provider.ANTHROPIC)
# The dangerous typo: a forced custom provider with no host would fall through
# to Anthropic's default base_url with the credential on X-Api-Key — a gateway
# secret sent to a third party. It must refuse to resolve instead.
from cs.model_config import LLMEnvError  # noqa: E402

check("custom provider without a base URL refuses to resolve",
      _raises(LLMEnvError,
              lambda: llm_env({"CS_LLM_PROVIDER": "custom",
                               "CS_LLM_API_KEY": "tok-x"})))
check("custom provider WITH a base URL resolves normally",
      llm_env({"CS_LLM_PROVIDER": "custom",
               "CS_LLM_BASE_URL": "https://gw.example.test",
               "CS_LLM_API_KEY": "tok-x"}).base_url == "https://gw.example.test")
check("every role has a tier", all(r in ROLE_TIER for r in Role))
check("the classifier is a WORKER", ROLE_TIER[Role.CLASSIFIER] is Tier.WORKER)

# ---------------------------------------------------------------- pricing
print("price catalog")
check("Anthropic-direct id has rates", token_rates("claude-sonnet-5") is not None)
check("unknown id -> None (never an Opus fallback)",
      token_rates("someone/unknown-model") is None)
check("no prefix-stripped inheritance",
      token_rates("someone-else/claude-sonnet-5") is None)


class _Usage:
    def __init__(self, i, o, cost=None):
        self.input_tokens = i
        self.output_tokens = o
        if cost is not None:
            self.cost = cost


check("gateway-reported cost wins",
      call_cost(_Resp([], usage=_Usage(10, 10, cost=0.000123)), "x") == 0.000123)
priced = call_cost(_Resp([], usage=_Usage(1_000_000, 0)), "claude-sonnet-5")
check("catalog pricing when the gateway reports none", priced == 3.00, priced)
check("unknown model -> None, not a guess",
      call_cost(_Resp([], usage=_Usage(1000, 1000)), "someone/unknown") is None)

# ---------------------------------------------------------------- env file
print("read_env / write_env / mask_key")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / ".env"
    p.write_text("# comment\nA=1\n\nB=2\n", encoding="utf-8")
    write_env(p, {"B": "9", "C": "3"})
    lines = read_env(p)
    check("comment preserved", lines[0] == "# comment")
    check("blank line preserved", "" in lines)
    check("existing key updated in place", "B=9" in lines)
    check("untouched key kept", "A=1" in lines)
    check("new key appended", lines[-1] == "C=3")
    missing = Path(td) / "sub" / ".env"
    write_env(missing, {"K": "V"})
    check("missing file is created", read_env(missing) == ["K=V"])

check("mask hides the middle", mask_key("sk-or-v1-abcdefghijklmnop") == "sk-or...mnop")
check("no key", mask_key("") == "(not set)")
check("short key is not partially revealed", mask_key("short") == "(set)")

# ------------------------------------------------------------ model catalog
# Offline behaviour only: pointed at an unroutable host with an empty cache, so
# the suite never depends on the network and never spends a cent. The LIVE
# resolution of every family is exercised separately (AB-REPORT §6) because it
# asserts against a catalog that legitimately changes under us.
print("model catalog (offline paths)")
from cs import model_catalog as mc  # noqa: E402

mc.MODELS_URL = "http://127.0.0.1:9/unroutable"
with tempfile.TemporaryDirectory() as td:
    empty = Path(td) / "none.json"

    check("a pinned id passes through untouched",
          mc.resolve("deepseek/deepseek-v4-pro", cache_path=empty)
          == "deepseek/deepseek-v4-pro")
    check("@family falls back to the offline snapshot",
          mc.resolve("@deepseek-pro", cache_path=empty) == "deepseek/deepseek-v4-pro")
    check("an unknown family fails LOUD, never silently",
          _raises(KeyError, lambda: mc.resolve("@nonesuch", cache_path=empty)))
    check("no live catalog and no cache raises",
          _raises(mc.CatalogUnavailable, lambda: mc.load_models(cache_path=empty)))
    check("every family has an offline fallback id",
          all(f in mc.STATIC_FALLBACK for f in mc.FAMILIES))
    check("every family has an operator note",
          all(f in mc.FAMILY_NOTES for f in mc.FAMILIES))

    # A stale cache beats no catalog: an id from last month resolves, an
    # exception resolves nothing.
    fresh = [mc.ModelInfo("v/m-2", "m2", 200, 1.0, 2.0, 1000),
             mc.ModelInfo("v/m-1", "m1", 100, 1.0, 2.0, 1000)]
    cached = Path(td) / "cache.json"
    mc._write_cache(cached, fresh)
    check("cache round-trips through the ONE parser",
          [m.id for m in mc.load_models(cache_path=cached)] == ["v/m-2", "v/m-1"])
    check("a stale cache is still served when the fetch fails",
          len(mc.load_models(refresh=True, cache_path=cached)) == 2)

    # A damaged cache must read as a MISSING cache, not as an error: any shape
    # that decodes but is not what we wrote used to raise straight through
    # resolve()'s CatalogUnavailable handling, and one corrupt file took out
    # every @family resolution until deleted by hand.
    for label, body in (("a JSON array", "[1, 2, 3]"),
                        ("a non-numeric fetched_at", '{"fetched_at": "boom"}'),
                        ("truncated JSON", '{"fetched_at": 1, "models": [{"i')):
        corrupt = Path(td) / "corrupt.json"
        corrupt.write_text(body, encoding="utf-8")
        check(f"corrupt cache ({label}) degrades to the static fallback",
              mc.resolve("@glm", cache_path=corrupt) == mc.STATIC_FALLBACK["glm"][0])

    fam = mc.Family("t", "v/m-*")
    check("newest wins inside a family", fam.members(fresh)[0].id == "v/m-2")
    excl = mc.Family("t", "v/m-*", exclude=("*-2",))
    check("excluded variants are not the newest", excl.members(fresh)[0].id == "v/m-1")

    check("live prices beat the static table",
          mc.token_rates("v/m-2", models=fresh) == (1.0, 2.0))
    check("an unknown id is unknown, not guessed",
          mc.token_rates("v/nope", models=fresh) is None)
    check("a price-less entry is skipped, never defaulted to zero",
          mc._parse({"id": "x/y"}) is None)

# The tier defaults must be families, not pinned ids — that is the whole point.
from cs.model_config import TIER_FAMILIES  # noqa: E402

check("every tier default is a family reference",
      all(mc.is_family_ref(spec)
          for table in TIER_FAMILIES.values() for spec in table.values()))
check("every tier default names a known family",
      all(mc.family_name(spec) in mc.FAMILIES
          for table in TIER_FAMILIES.values() for spec in table.values()))

# ------------------------------------------------------------------ routing
print("routing opt-in")
from cs.model_config import route_direct  # noqa: E402

check("routing is OFF unless asked for", route_direct({}) is False)
check("CS_LLM_ROUTE=engine keeps the engine", route_direct({"CS_LLM_ROUTE": "engine"}) is False)
check("CS_LLM_ROUTE=direct opts in", route_direct({"CS_LLM_ROUTE": "direct"}) is True)
check("the opt-in is not case- or space-sensitive",
      route_direct({"CS_LLM_ROUTE": "  Direct "}) is True)

# The routing SEAM in rpc.chat — the boundary between charter-safe mechanical
# traffic and customer-facing generation. Exercised with a stubbed worker (no
# network) in the three states that matter: no role must never touch the
# worker even with the opt-in set; role + opt-in must serve from the worker
# with the engine response shape preserved; role WITHOUT the opt-in must leave
# the worker untouched (the resulting engine connection fails in this sandbox,
# which is fine — the assertion is about what was NOT called).
print("routing seam (rpc.chat, stubbed worker)")
import asyncio  # noqa: E402

from cs import rpc, worker_llm as _wl  # noqa: E402

_calls: list = []


def _stub_call(message, *, role, timeout):
    _calls.append({"message": message, "role": role, "timeout": timeout})
    return _wl.Completion(text="STUBBED", model="stub/model", provider="test",
                          input_tokens=1, output_tokens=1, cost_usd=None,
                          latency_ms=1.0, stop_reason="end_turn")


_real_call = _wl.call
_wl.call = _stub_call
os.environ["CS_LLM_ROUTE"] = "direct"
try:
    out = asyncio.run(rpc.chat(None, "classify this", allow_tools=set(),
                               role=Role.CLASSIFIER, echo=lambda m: None))
    check("role + opt-in serves from the worker", len(_calls) == 1)
    check("...with the prompt passed through verbatim",
          _calls and _calls[0]["message"] == "classify this")
    check("...preserving the engine response shape",
          out == {"result": {"response": "STUBBED"}, "approvals": [],
                  "notifications": []})

    _calls.clear()
    os.environ["CS_LLM_ROUTE"] = "engine"
    try:
        asyncio.run(rpc.chat(None, "x", allow_tools=set(),
                             role=Role.CLASSIFIER, echo=lambda m: None))
    except Exception:  # noqa: BLE001 — settings=None cannot reach an engine
        pass
    check("role WITHOUT the opt-in never touches the worker", not _calls)

    os.environ["CS_LLM_ROUTE"] = "direct"
    try:
        asyncio.run(rpc.chat(None, "x", allow_tools=set(), echo=lambda m: None))
    except Exception:  # noqa: BLE001 — same: the engine path fails here, by design
        pass
    check("no role never touches the worker, even with the opt-in set",
          not _calls)
finally:
    _wl.call = _real_call
    del os.environ["CS_LLM_ROUTE"]

print()
print("RESULT:", "FAIL" if FAIL else "all llm-client gates green")
sys.exit(FAIL)
