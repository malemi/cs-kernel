"""Turn the raw producer payload into a worklist: apply self-filter
(operator's own accounts), suppression, dedup, and basic eligibility.

leads        -> key = firebase uid (email resolved later, via Firebase SA)
signups      -> key = business_id (email already in payload)
cancellations-> key = business_id (email already in payload)

Suppression is matched through `cs/addr_match.py`, the same matcher the
`unanswered` sweep uses, so an entry means one thing wherever it is read. The
alternative is not a style preference: while this gate matched exactly and the
sweep matched patterns, `cs suppress '*@<domain>'` produced a quieter queue AND
kept mailing the domain — protection the operator could see working and that
was not there.
"""
from __future__ import annotations

from .addr_match import AddrSet
from .config import Settings
from .state import State


def _norm(s) -> str:
    return (s or "").strip().lower()


def _filter_business(rows, category, settings, state, dnc, taken, seen_emails, out, skipped):
    for b in rows:
        bid = b.get("business_id")
        email = _norm(b.get("email_address"))
        if b.get("is_deleted"):
            skipped.append({"category": category, "key": bid, "reason": "deleted"})
            continue
        if email in settings.self_email_set or b.get("owner") in settings.self_uid_set:
            skipped.append({"category": category, "key": bid, "reason": "self"})
            continue
        if not email:
            skipped.append({"category": category, "key": bid, "reason": "no_email"})
            continue
        if email in dnc:
            skipped.append({"category": category, "key": bid, "reason": "suppressed"})
            continue
        if email in taken:
            # A human is mid-conversation with them (`cs escalated`). Outreach
            # on top of that is the same two-hands failure as a second reply,
            # and it arrives as a template, which is worse. Skipped, never
            # silently: the reason is counted in `cs plan`'s skip table.
            skipped.append({"category": category, "key": bid, "reason": "escalated"})
            continue
        if state.already_contacted(bid, category, settings.dedup_days):
            skipped.append({"category": category, "key": bid, "reason": "dedup"})
            continue
        if email in seen_emails:
            skipped.append({"category": category, "key": bid, "reason": "dup_in_batch"})
            continue
        out[category].append(b)
        seen_emails.add(email)


def build_worklist(payload: dict, settings: Settings, state: State) -> dict:
    # AddrSet, not the raw set: `email in dnc` below then honours a wildcard
    # entry instead of quietly missing it.
    dnc = AddrSet(state.do_not_contact_set())
    # Leads are keyed by uid with no email yet, so this gate can only apply to
    # the two business categories — which is also where it matters: a lead a
    # human has taken over is by definition already a conversation, so it has
    # an address and reaches the same check one step later, in the dossier.
    taken = state.escalated_set()
    out = {"lead": [], "signup": [], "cancellation": []}
    skipped: list[dict] = []
    seen_emails: set[str] = set()

    for l in payload.get("leads", []):
        uid = l.get("uid")
        if uid in settings.self_uid_set:
            skipped.append({"category": "lead", "key": uid, "reason": "self"})
            continue
        if state.already_contacted(uid, "lead", settings.dedup_days):
            skipped.append({"category": "lead", "key": uid, "reason": "dedup"})
            continue
        out["lead"].append(l)

    _filter_business(
        payload.get("signups", []), "signup", settings, state, dnc, taken,
        seen_emails, out, skipped
    )
    _filter_business(
        payload.get("cancellations", []),
        "cancellation",
        settings,
        state,
        dnc,
        taken,
        seen_emails,
        out,
        skipped,
    )

    return {"to_contact": out, "skipped": skipped}
