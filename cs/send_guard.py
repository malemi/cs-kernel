"""Refuse to put a model's own deliberation on the wire as a customer mail.

Every model-composed customer mail funnels through one call:
``send_mail.send(..., body_md=...)``. ``body_md`` is markdown, and markdown is
the shape *generated* text arrives in — every fixed-template path hands
``send()`` a ``plain``/``html`` pair built by a campaign pack instead. So
``body_md is not None`` is the de-facto marker "a model wrote this", and that
call is the one place a single check can stand between generated text and the
SMTP socket.

Why it exists (2026-07-28): a campaign loop mailed a customer the model's own
meta-deliberation verbatim — a paragraph reasoning about what the customer had
just written, then "here is the reply:" with the reply wrapped in ``---``
rules, then a question aimed at the OPERATOR asking whether to prepare the mail
to send to that customer's address. The loop had a guard, and the guard passed
it: it checked length, unfilled placeholders and AI-self-outing phrases, and
nothing in it asked WHO the text was addressed to.

Two layers, deterministic first:

* **Structural tells** — a markdown horizontal rule or a code fence (the
  wrappers a model puts around "the answer"), the recipient's own address
  written inside the body (the "…to send to X" tell), a trailing question that
  follows one of those wrappers, plus the ported length / placeholder /
  banned-phrase checks. Each is a named reason and any one of them refuses,
  except the ones listed in :data:`SOFT_TELLS`, which only add to another
  tell's case — a legitimate reply is allowed to end on a question, because
  that question is addressed to the customer.

* **Register judgment** — one worker-tier classification (:mod:`cs.worker_llm`):
  is this text a message addressed to the recipient, or a model talking about
  the recipient to its operator? Anything but ``customer_reply`` refuses. This
  is the layer that generalizes: the tells above recognise the shape that has
  already gone wrong, this one recognises the mistake.

Availability. The register judgment needs a configured provider credential.
Without one — a clone that never opted into kernel-side LLM calls — the
deterministic tells still run and ONE loud WARNING line names the degraded mode
on stderr. The same happens when a configured provider *fails*: a gateway
hiccup must not turn into a mail outage, and the deterministic layer is the one
that caught the real incident. Degraded is always announced, never silent, and
never fatal.

There is deliberately no off switch. A body that legitimately contains a rule
or a fence is not a generated reply — it is fixed-template copy, and that path
(``plain=``/``html=``, authored in a campaign pack by a human) is not guarded
because a human wrote it.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from email.utils import getaddresses
from typing import Callable, Iterable, Optional

# ------------------------------------------------------------------- defaults

# Ported from the campaign loop whose guard let the 2026-07-28 body through:
# they are the checks that DID work, and they belong at the chokepoint rather
# than in one loop. A clone extends the phrase list from its manifest
# ([knobs].send_guard_banned_phrases); the kernel list is not company-shaped.
BANNED_PHRASES: tuple[str, ...] = ("as an ai", "come assistente ai", "non posso")
MIN_BODY_CHARS = 40
PLACEHOLDER_RE = re.compile(r"\{[a-z_][a-z0-9_]*\}", re.I)

# A markdown thematic break on a line of its own: three or more of the same
# marker, spaces allowed between them. The kernel's own md→html renderer does
# not implement thematic breaks, so such a line reaches the customer as literal
# punctuation — it is never something a reply wants and always something a
# wrapper leaves behind.
HR_RE = re.compile(r"^[ \t]*(?:-[ \t]*){3,}$|^[ \t]*(?:\*[ \t]*){3,}$|^[ \t]*(?:_[ \t]*){3,}$")
FENCE_RE = re.compile(r"^[ \t]*(?:`{3,}|~{3,})")
QUOTE_RE = re.compile(r"^[ \t]*>")

# Tell names — stable strings, because they are what a caller logs and what an
# operator greps for when a send was refused at 03:00.
TELL_TOO_SHORT = "too_short"
TELL_PLACEHOLDER = "unfilled_placeholder"
TELL_BANNED = "banned_phrase"
TELL_HR = "horizontal_rule"
TELL_FENCE = "code_fence"
TELL_RECIPIENT_IN_BODY = "recipient_address_in_body"
TELL_TRAILING_QUESTION = "trailing_operator_question"
TELL_REGISTER = "register_not_customer_reply"

#: Tells that never refuse on their own — they corroborate, they do not decide.
#: A real reply may well end on a question; what makes a trailing question a
#: tell is the deliberation wrapper in front of it, and that wrapper is already
#: a hard tell. Keeping this soft is what stops the guard from bouncing an
#: ordinary "va bene per giovedì?".
SOFT_TELLS: frozenset[str] = frozenset({TELL_TRAILING_QUESTION})

# The register labels. `mixed` exists so a body that is a real reply with a
# sentence of deliberation stapled on is not forced into `customer_reply`:
# that body is exactly the one that went out.
LABEL_OK = "customer_reply"
LABEL_META = "meta_deliberation"
LABEL_MIXED = "mixed"
REGISTER_LABELS: tuple[str, ...] = (LABEL_OK, LABEL_META, LABEL_MIXED)

REGISTER_SYSTEM = (
    "You inspect outbound email bodies and answer with exactly one label. "
    "You never write email, never comment, never explain."
)


class SendGuardRefusal(RuntimeError):
    """The body must not go out. Carries the machine-readable tells.

    Raised BEFORE the message is built and long before a socket is opened, so a
    caller that lets it propagate has, by construction, sent nothing and
    written no state.
    """

    def __init__(self, reason: str, tells: Iterable["Tell"] = ()):
        super().__init__(reason)
        self.reason = reason
        self.tells = tuple(tells)

    @property
    def tell_names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tells)


@dataclass(frozen=True)
class Tell:
    """One named thing found in the body, with the evidence that found it."""

    name: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.name}: {self.detail}" if self.detail else self.name


@dataclass
class Verdict:
    """The full outcome, so a caller can log more than a boolean."""

    ok: bool
    tells: list[Tell] = field(default_factory=list)
    reason: str = ""
    register: Optional[str] = None      # the label, when the LLM leg ran
    degraded: str = ""                  # why the LLM leg did not run, if it did not

    @property
    def tell_names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tells)


# ------------------------------------------------------------------- helpers


def _warn(message: str) -> None:
    sys.stderr.write(f"[send_guard] WARNING: {message}\n")


def _addresses(to: str) -> list[str]:
    """Every bare address in a To value — ``"Name <a@x>, b@y"`` → two."""
    out = []
    for _name, addr in getaddresses([to or ""]):
        a = (addr or "").strip().lower()
        if "@" in a:
            out.append(a)
    return out


def _unquoted(body: str) -> str:
    """*body* with quoted-thread lines removed.

    The recipient's address legitimately appears inside a quoted thread (their
    own headers, their own signature), so that region cannot count as evidence.
    Quoting in the text we send is ``>``-prefixed lines — the only marker that
    survives markdown → plain/html here — and anything else is treated as ours.
    """
    return "\n".join(ln for ln in body.splitlines() if not QUOTE_RE.match(ln))


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n[ \t]*\n", body or "") if p.strip()]


def _has_wrapper(text: str) -> bool:
    """A horizontal rule or a fence line anywhere in *text*."""
    return any(HR_RE.match(ln) or FENCE_RE.match(ln) for ln in text.splitlines())


def banned_phrases(settings=None) -> tuple[str, ...]:
    """The kernel list plus whatever the clone's manifest adds.

    Extends, never replaces: the three kernel phrases are AI-self-outing, which
    is a property of the writer and not of the company, so no clone has a
    reason to want them gone.
    """
    extra = str(getattr(settings, "send_guard_banned_phrases", "") or "")
    added = tuple(p.strip().lower() for p in extra.split(",") if p.strip())
    return BANNED_PHRASES + added


def min_chars(settings=None) -> int:
    try:
        return int(getattr(settings, "send_guard_min_chars", MIN_BODY_CHARS))
    except (TypeError, ValueError):
        return MIN_BODY_CHARS


# --------------------------------------------------------- deterministic tells


def inspect(body: str, to: str = "", *, settings=None) -> list[Tell]:
    """Every deterministic tell in *body*. Pure: no network, no config reads
    beyond the two knobs, no side effects."""
    text = (body or "").strip()
    tells: list[Tell] = []

    floor = min_chars(settings)
    if len(text) < floor:
        tells.append(Tell(TELL_TOO_SHORT, f"{len(text)} chars < {floor}"))

    hole = PLACEHOLDER_RE.search(text)
    if hole:
        tells.append(Tell(TELL_PLACEHOLDER, hole.group(0)))

    low = text.lower()
    for phrase in banned_phrases(settings):
        if phrase in low:
            tells.append(Tell(TELL_BANNED, repr(phrase)))

    for line in text.splitlines():
        if HR_RE.match(line):
            tells.append(Tell(TELL_HR, repr(line.strip())))
            break
    for line in text.splitlines():
        if FENCE_RE.match(line):
            tells.append(Tell(TELL_FENCE, repr(line.strip())))
            break

    # "…da inviare a <address>?" — a body that NAMES its own recipient is
    # talking about them, not to them. Quoted thread text is excluded, since
    # their address is legitimately all over it.
    visible = _unquoted(text).lower()
    for addr in _addresses(to):
        if addr in visible:
            tells.append(Tell(TELL_RECIPIENT_IN_BODY, addr))
            break

    # A trailing question AFTER a deliberation wrapper: "Vuoi che prepari…?".
    # Soft by design — see SOFT_TELLS. The wrapper must come BEFORE the final
    # paragraph, or an ordinary question is enough to trip it.
    paras = _paragraphs(text)
    if paras and paras[-1].endswith("?"):
        head = text[: text.rfind(paras[-1])] if paras[-1] in text else ""
        if _has_wrapper(head):
            tells.append(Tell(TELL_TRAILING_QUESTION, paras[-1][-80:]))

    return tells


def refusing(tells: Iterable[Tell]) -> list[Tell]:
    """The tells that actually decide, given :data:`SOFT_TELLS`."""
    tells = list(tells)
    hard = [t for t in tells if t.name not in SOFT_TELLS]
    return tells if hard else []


# --------------------------------------------------------- register judgment


def register_prompt(body: str, to: str) -> str:
    """The classification prompt. Lives here, not in ``worker_llm``: the kernel
    keeps prompts at their call site so the worker module stays neutral."""
    return (
        "The text below is the body of an email that is about to be SENT to a "
        "recipient. A language model wrote it. Decide WHO the text is "
        "addressed to.\n\n"
        f"{LABEL_OK}\n"
        "    The whole text is the message itself, addressed to the recipient: "
        "one person writing to another. It may quote them, answer them, or ask "
        "THEM a question.\n"
        f"{LABEL_META}\n"
        "    The text is the model talking about the task or to its operator: "
        "reasoning about what the recipient said, announcing or wrapping the "
        "reply (\"here is the reply:\"), asking whether to proceed, or naming "
        "the recipient as a third party to send something to.\n"
        f"{LABEL_MIXED}\n"
        "    Both: a real message with any amount of that second-audience text "
        "attached to it.\n\n"
        f"RECIPIENT: {to}\n\n"
        "<<<BODY\n"
        f"{body}\n"
        "BODY>>>\n\n"
        f"Answer with exactly one word: {LABEL_OK}, {LABEL_META} or "
        f"{LABEL_MIXED}."
    )


def llm_available() -> tuple[bool, str]:
    """``(True, "")`` when a provider credential resolves, else the reason.

    Checked before the call so the degraded mode names the configuration, not
    a downstream symptom.
    """
    try:
        import importlib.util

        if importlib.util.find_spec("anthropic") is None:
            return False, ("the anthropic SDK is missing — it is a base "
                           "dependency since v0.9.5, so this install is "
                           "broken: uv pip install -r requirements.txt")
        from .model_config import llm_env
    except Exception as e:  # noqa: BLE001 - availability probe, never fatal
        return False, f"{type(e).__name__}: {e}"
    try:
        endpoint = llm_env()
    except Exception as e:  # noqa: BLE001 - e.g. a custom provider with no base URL
        return False, f"{type(e).__name__}: {e}"
    if not endpoint.api_key:
        return False, (f"no provider credential resolved ({endpoint.source}) — "
                       "set OPENROUTER_API_KEY or CS_LLM_API_KEY")
    return True, ""


def judge_register(body: str, to: str, *, timeout: float = 60.0) -> tuple[Optional[str], str]:
    """``(label, "")`` or ``(None, why_it_could_not_run)``. NEVER raises.

    A failure here is an availability problem, not a verdict: it degrades the
    guard to its deterministic layer and says so. Turning a gateway 500 into a
    refusal would stop every send in the clone the first time a provider has a
    bad afternoon.
    """
    ready, why = llm_available()
    if not ready:
        return None, why
    try:
        from . import worker_llm

        return worker_llm.classify(
            register_prompt(body, to),
            REGISTER_LABELS,
            system=REGISTER_SYSTEM,
            timeout=timeout,
            # `temperature=None` omits the parameter. worker_llm defaults it to
            # 0.0, and the WORKER tier's own default model rejects it outright
            # — verified live 2026-08-01, Anthropic direct, claude-sonnet-5:
            # HTTP 400 "`temperature` is deprecated for this model". Left at
            # the default, every register judgment fails, and the guard degrades
            # to deterministic-only in exactly the configuration a clone gets
            # out of the box. The determinism a 3-label call loses here is worth
            # far less than the leg running at all.
            temperature=None,
        ), ""
    except Exception as e:  # noqa: BLE001 - the call, not the body, failed
        return None, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------- the verdict


def evaluate(body: str, to: str, *, settings=None, use_llm: bool = True,
             warn: Callable[[str], None] = _warn) -> Verdict:
    """Full verdict for a model-composed *body* addressed to *to*.

    Deterministic tells run first and short-circuit: a body already refused
    does not get billed for a classification.
    """
    tells = inspect(body, to, settings=settings)
    deciding = refusing(tells)
    if deciding:
        return Verdict(ok=False, tells=tells, reason=_reason(deciding))

    if not use_llm:
        return Verdict(ok=True, tells=tells, degraded="LLM leg not requested")

    label, why = judge_register(body or "", to or "")
    if label is None:
        warn(f"register judgment SKIPPED — {why}. Deterministic tells only: "
             f"a body that talks ABOUT {to or 'the recipient'} instead of to "
             f"them can pass this send.")
        return Verdict(ok=True, tells=tells, degraded=why)

    if label != LABEL_OK:
        tells.append(Tell(TELL_REGISTER, label))
        return Verdict(ok=False, tells=tells, register=label,
                       reason=_reason([tells[-1]]))
    return Verdict(ok=True, tells=tells, register=label)


def _reason(tells: list[Tell]) -> str:
    detail = "; ".join(str(t) for t in tells)
    return (f"refusing to send a model-composed body: {detail}. "
            "This text reads as the model's own deliberation rather than a "
            "message to the recipient — escalate, do not send.")


def check(settings, to: str, body: str, *, use_llm: bool = True,
          warn: Callable[[str], None] = _warn) -> Verdict:
    """:func:`evaluate`, raising :class:`SendGuardRefusal` on a refusal.

    This is what ``send_mail.send`` calls, and it is called before the MIME
    message is even built.
    """
    v = evaluate(body, to, settings=settings, use_llm=use_llm, warn=warn)
    if not v.ok:
        raise SendGuardRefusal(v.reason, v.tells)
    return v
