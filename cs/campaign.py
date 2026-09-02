"""Campaign follow-up — shared logic for the `cs campaign …` verbs.

Two lifecycles, INFERRED from contact shape (the engine `campaigns` row has no
policy column):

  composed-draft  contacts carry draft_subject/draft_body. Per contact: dedup
                  against the Sent archive FIRST; if the mail already went out
                  (even by hand, out-of-band) reconcile the stale `drafted` row
                  to `sent` and NEVER re-send; otherwise the composed mail is a
                  real pending send (gated by CS_TRIAGE_MODE). Once sent,
                  handle the reply.

  fixed-template  contacts in `sent`; reminders (after the reminder hour,
                  capped) + evening SMS; replies classified. CONTENT comes from
                  the campaign PACK (campaigns/<name>/ in the clone repo — see
                  cs/campaign_pack.py); an action whose campaign has NO pack is
                  REFUSED loudly: the kernel never invents copy.

Dedup truth is Gmail's own Sent folder (cs/gmail_archive.py), NEVER the
campaign state and NEVER the engine archive — the state goes stale whenever
mail is sent out-of-band, and the engine search is blind to hand-sent mail
and drops a thread out of 'sent' the moment the customer replies last.

Every name in `settings.excluded_campaign_set` is skipped by the general
operator — campaigns owned by a dedicated process outside this module. The
manifest field is comma-separated, matching is by EXACT name, and a campaign
that merely shares a prefix with an excluded one is NOT excluded.

A campaign that is OVER delivers nothing, on any path. Its pack says so —
`[pack].status = "done"`, or an `ends_on` date now past (cs/campaign_pack.py)
— and every delivery site here asks the pack before acting: the worklist, and
each of `send_first` / `send_reminder` / `send_sms` / `send_draft` /
`queue_draft`, every one of which is reachable with a contact id WITHOUT
going through `pending()`. The pack carries the fact, so that ending a
campaign is a one-line edit where the campaign lives rather than a manual
entry in every clone's `excluded_campaign`.

The refusal is loud and dated. Observation actions (`handle_reply`,
`reconcile`) survive: a human who wrote to us is owed an answer whether or
not the campaign that prompted the mail is finished, and reconciling a stale
row sends nothing.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from . import _time, campaign_pack, rpc

# Default reminder window start (market-local hour). A pack's [windows]
# reminder_after_hour overrides it per campaign; it is deliberately not a
# manifest knob (the campaign, not the company, owns its windows).
REMINDER_AFTER_HOUR_DEFAULT = 12

# Worklist actions that put a message in front of a customer — the ones a
# finished campaign is refused. Everything else `pending()` can emit
# (`handle_reply`, `reconcile`) is an observation, and observations are not
# suppressed by a campaign being over.
DELIVERY_ACTIONS = ("send_draft", "send_first", "send_reminder", "send_sms")

# The worklist item for a contact whose evidence could not be read in full.
# NOT a delivery action — nothing is put in front of anybody — and not an
# omission either: it is the third outcome, printed with the mailbox to fix.
EVIDENCE_ACTION = "evidence_incomplete"


# ------------------------------------------------------------------ helpers


def _parse_dt(raw) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _is_it_mobile(phone: Optional[str]) -> bool:
    p = (phone or "").replace(" ", "")
    return bool(p) and (p.startswith("+393") or (p.startswith("3") and len(p) >= 9))


def _has_draft(c: dict) -> bool:
    return bool((c.get("draft_subject") or "").strip() or (c.get("draft_body") or "").strip())


def kind_of(contacts: list[dict]) -> str:
    """Infer the campaign lifecycle from contact shape (no engine policy field)."""
    return "composed-draft" if any(_has_draft(c) for c in contacts) else "fixed-template"


def _thread_id(t: dict):
    return t.get("thread_id") or t.get("id")


def list_campaigns(settings) -> list[dict]:
    return rpc.call_sync(settings, "campaign.list", {})


def _sent_threads_to(settings, email: str, days: int) -> tuple[list[dict], list[str]]:
    """`(threads, unreadable)` — messages SENT TO `email` within `days` from
    EVERY mailbox this company answers from, plus the mailboxes that could not
    be read.

    Ground truth is Gmail's own Sent folder, not the engine: the engine's
    `emails.search folder:sent` is blind to mail sent by hand and drops a
    thread out of 'sent' the moment the customer replies last (storage
    latest-sender bug), so it cannot safely gate sends.

    ONE mailbox was not enough either. A company answers from several, and a
    colleague's reply from his own address is on no header of the operator's
    mailbox — so "we have never written to them" was answered from evidence
    that could not have seen the answer, and four drafts were composed to a
    prospect a co-founder had answered the next day. The fan-out
    (`cs/mailboxes.py`) reads the operator mailbox, every account with an
    engine profile, and every mailbox declared in the manifest.

    `unreadable` is what makes the widening safe: a mailbox that could not be
    opened is NEVER an empty result. Callers must treat a non-empty
    `unreadable` as "cannot tell" (`_evidence_refusal`), never as "nobody
    wrote"."""
    from . import mailboxes

    fan = mailboxes.sent_to_across(settings, email, days=days)
    threads = [{"thread_id": m.get("message_id"), "subject": m.get("subject"),
                "date": m.get("date"), "mailbox": m.get("mailbox")}
               for m in fan.rows]
    return threads, [u.describe() for u in fan.unreadable]


def _inbound_since(settings, email: str,
                   after: Optional[datetime]) -> tuple[list[dict], list[str]]:
    """`(messages, unreadable)` — inbound from `email` after `after`, across the
    same set of mailboxes, read from Gmail All Mail rather than the engine.

    'Did they reply' must not depend on the engine's sync state, and it must not
    depend on WHICH of this company's mailboxes they replied to: a customer who
    answers a colleague has replied. A message FROM the customer can never be
    one of our drafts, so this is draft-free by nature — and it names no self,
    which is what makes it safe to run against a mailbox that is not the
    operator's."""
    from . import mailboxes

    fan = mailboxes.inbound_since_across(settings, email, after=after)
    return fan.rows, [u.describe() for u in fan.unreadable]


def _evidence_refusal(email: str, unreadable: list[str],
                      action: str) -> Optional[dict]:
    """The fail-closed refusal: a gate that could not read every mailbox does
    not send, and says which one to fix.

    Fail-open reproduces the incident at machine speed — an absence of evidence
    read as evidence of absence, once per contact, unattended. Fail-closed can
    halt outreach on one dead credential, which is the accepted cost: a contact
    not written to today is recoverable, a second cold mail to someone a
    colleague answered two months ago is not.

    Same `blocked` shape as the CS_PAUSE and escalation refusals, so every
    caller already reports it, and the sentence comes from the fan-out itself —
    it must never reach the CLI's engine-error handler, which would announce an
    IMAP failure as "cannot reach the engine"."""
    if not unreadable:
        return None
    from . import mailboxes

    return {
        "ok": False,
        "email": email,
        "blocked": (
            f"evidence incomplete — could not read {'; '.join(unreadable)}. "
            f"{mailboxes.INCOMPLETE} Refusing to {action}: fix that mailbox "
            f"(or drop it from the declaration) and re-run."
        ),
        "unreadable": unreadable,
    }


def _unjudgeable(c: dict, unreadable: list[str], question: str) -> dict:
    """The worklist item for a contact this run could not judge.

    A contact that simply disappears from a list when a mailbox is down is the
    incident's own shape, one level up: the worklist would look complete and be
    wrong. So the contact stays, as its own action, saying which question could
    not be answered and which mailbox to fix. Nothing downstream may read it as
    "safe to send" — it is not a delivery action, and the senders refuse the
    same contact for the same reason."""
    return {"action": EVIDENCE_ACTION, "contact_id": c["id"], "email": c["email"],
            "question": question, "unreadable": unreadable}


def _get_contact(settings, contact_id: str) -> Optional[dict]:
    """Find one contact by id across campaigns (the engine has no get-by-id).
    Annotates `_campaign_name`/`_campaign_id`."""
    for camp in list_campaigns(settings):
        for c in rpc.call_sync(settings, "campaign.contacts", {"campaign_id": camp["id"]}):
            if c["id"] == contact_id:
                c["_campaign_name"] = camp["name"]
                c["_campaign_id"] = camp["id"]
                return c
    return None


def _market_today(settings, now: Optional[datetime]) -> date:
    """The operator's market calendar day — the unit the end-of-campaign gate
    compares against, for the same reason the reminder/SMS windows are
    market-local: a campaign ends at the end of a business day where the
    business is, not at midnight UTC."""
    return date.fromisoformat(
        _time.local_date(now or _time.now_utc(), settings.timezone)
    )


def _finished_refusal(settings, pack: Optional[campaign_pack.Pack],
                      now: Optional[datetime] = None) -> Optional[str]:
    """Why `pack`'s campaign may not deliver right now, or None.

    A campaign with NO pack declares nothing about its own lifetime, so it is
    not refused here — the pack senders already refuse it, louder, for having
    no copy at all."""
    if pack is None:
        return None
    return pack.delivery_refusal(_market_today(settings, now))


def _resolve_pack(camp_name: str) -> tuple[Optional[campaign_pack.Pack], Optional[str]]:
    """(pack, load_error). A pack that cannot be LOADED is an error, never a
    None pack: "the pack is broken" must not be read as "there is no pack and
    therefore no end date", which would let a campaign whose status line is the
    broken part keep delivering."""
    try:
        return campaign_pack.find_pack(camp_name), None
    except campaign_pack.PackError as e:
        return None, str(e)


def _pack_windows(settings, pack: Optional[campaign_pack.Pack]) -> tuple[int, int, int]:
    """Effective (reminder_after_hour, sms_hour, reminder_max): the pack's
    [windows] override the [knobs] defaults."""
    rah = (pack.reminder_after_hour if pack and pack.reminder_after_hour is not None
           else REMINDER_AFTER_HOUR_DEFAULT)
    smsh = pack.sms_hour if pack and pack.sms_hour is not None else settings.sms_hour
    rmax = pack.reminder_max if pack and pack.reminder_max is not None else settings.reminder_max
    return rah, smsh, rmax


# ------------------------------------------------------------------ pending


def _composed_draft_items(settings, contacts, dedup_days) -> list[dict]:
    items = []
    for c in contacts:
        if c["state"] == "drafted":
            threads, unreadable = _sent_threads_to(settings, c["email"], dedup_days)
            if threads:  # already mailed (dedup truth) → reconcile, never re-send
                t = threads[0]
                items.append({"action": "reconcile", "contact_id": c["id"],
                              "email": c["email"], "thread_id": _thread_id(t),
                              "subject": t.get("subject")})
            elif unreadable:
                # NOT a send candidate and NOT dropped. A contact that vanishes
                # from a worklist because a mailbox was down is the same error
                # as an absence read as a fact — it just fails silently instead
                # of loudly. It appears as its own item, with the fix.
                items.append(_unjudgeable(c, unreadable, "prior contact"))
            else:  # genuinely unsent → a real pending outreach (CS_TRIAGE_MODE)
                items.append({"action": "send_draft", "contact_id": c["id"],
                              "email": c["email"], "draft_subject": c.get("draft_subject")})
        elif c["state"] == "sent":
            d = c.get("dossier") or {}
            # A reconciled contact carries a reconcile-time `sent_at` (LATER than
            # the real out-of-band send) — anchor on `created_at` (just before the
            # real send) so a reply that arrived before we reconciled is not
            # missed. A genuine send stamps the real send time in `sent_at`.
            after = (
                _parse_dt(c.get("created_at")) if d.get("reconciled")
                else _parse_dt(c.get("sent_at")) or _parse_dt(c.get("created_at"))
            )
            replies, unreadable = _inbound_since(settings, c["email"], after)
            if replies:
                items.append({"action": "handle_reply", "contact_id": c["id"],
                              "email": c["email"]})
            elif unreadable:
                items.append(_unjudgeable(c, unreadable, "a reply"))
    return items


def _fixed_template_items(settings, contacts, now,
                          pack: Optional[campaign_pack.Pack]) -> list[dict]:
    items = []
    tz = settings.timezone
    today = _time.local_date(now, tz)
    rah, smsh, rmax = _pack_windows(settings, pack)
    evening = _time.local_hour(now, tz) >= smsh
    past_window = _time.local_hour(now, tz) >= rah
    pack_name = pack.name if pack else None
    for c in contacts:
        if c["state"] != "sent":
            continue
        d = c.get("dossier") or {}
        after = _parse_dt(c.get("sent_at")) or _parse_dt(c.get("created_at"))
        replies, unreadable = _inbound_since(settings, c["email"], after)
        if replies:
            items.append({"action": "handle_reply", "contact_id": c["id"], "email": c["email"]})
        elif unreadable:
            # Before the SMS and reminder branches: a contact whose reply we
            # could not look for is not a contact to nudge.
            items.append(_unjudgeable(c, unreadable, "a reply"))
        elif evening and _is_it_mobile(d.get("phone")) and d.get("last_sms_sent_day") != today:
            items.append({"action": "send_sms", "contact_id": c["id"], "email": c["email"],
                          "pack": pack_name})
        elif (past_window and d.get("last_reminder_sent_day") != today
              and d.get("reminders", 0) < rmax):
            items.append({"action": "send_reminder", "contact_id": c["id"], "email": c["email"],
                          "pack": pack_name})
    return items


def _hold_deliveries(entry: dict, items: list[dict], reason: str) -> list[dict]:
    """Strip the delivery actions out of a finished campaign's worklist and say
    so, with the reason and the date, on the entry itself.

    Held items are reported as counts per action, never dropped in silence: a
    contact that simply vanishes from a worklist is the failure mode this whole
    gate exists to stop. Observation actions pass through untouched."""
    kept, held = [], {}
    for item in items:
        if item.get("action") in DELIVERY_ACTIONS:
            held[item["action"]] = held.get(item["action"], 0) + 1
        else:
            kept.append(item)
    entry["delivery_blocked"] = reason
    if held:
        entry["held"] = held
    return kept


def _escalated_map(settings) -> dict[str, dict]:
    """Contacts a human has personally taken over (`cs escalated`). Best-effort
    like every other read of the local ledger: a missing db must degrade to "no
    records", never break a worklist."""
    try:
        from . import state as state_mod

        return state_mod.State(settings.db_path).escalated_to_human()
    except Exception:  # noqa: BLE001
        return {}


def _hold_escalated(entry: dict, items: list[dict], taken: dict[str, dict]) -> list[dict]:
    """Take the DELIVERIES to taken-over contacts out of a campaign worklist,
    and TAG what is left with who owns the conversation.

    A campaign mail landing on a customer the owner is personally writing to is
    the same two-hands failure as a second reply, arriving as a template. The
    observation actions (`handle_reply`, `reconcile`) stay — the reply is real
    and must still be seen — but they carry `escalated_to`, so the tick reports
    them instead of answering them. Held deliveries are counted on the entry;
    nothing vanishes."""
    if not taken:
        return items
    kept, held = [], {}
    for item in items:
        rec = taken.get((item.get("email") or "").strip().lower())
        if rec is None:
            kept.append(item)
            continue
        if item.get("action") in DELIVERY_ACTIONS:
            held[item["action"]] = held.get(item["action"], 0) + 1
            continue
        kept.append({**item, "escalated_to": rec.get("owner") or "the operator"})
    if held:
        entry["escalated_hold"] = held
    return kept


def pending(settings, name: Optional[str] = None, *, dedup_days: Optional[int] = None,
            now: Optional[datetime] = None) -> dict:
    """Per-campaign worklist for the skills. DATA ONLY — sends nothing, mutates
    nothing. Every settings.excluded_campaign_set name is skipped. Fixed-template entries
    carry their PACK name (or null + pack_error): an action with no pack is
    visible here and will be refused by the handlers.

    A campaign whose pack says it is OVER (status done, or past `ends_on`)
    yields NO delivery items — the entry carries `delivery_blocked` with the
    reason and the date, plus `held` counting what was withheld. Its
    `handle_reply` / `reconcile` items still come through.

    A contact a human has TAKEN OVER (`cs escalated`) yields no delivery item
    either — counted in `escalated_hold` — and its observation items carry
    `escalated_to`, naming who owns the conversation."""
    now = now or _time.now_utc()
    dd = settings.dedup_days if dedup_days is None else dedup_days
    taken = _escalated_map(settings)
    camps = list_campaigns(settings)
    if name:
        camps = [c for c in camps if c["name"] == name]
    out = []
    for camp in camps:
        if camp["name"] in settings.excluded_campaign_set:
            continue
        contacts = rpc.call_sync(settings, "campaign.contacts", {"campaign_id": camp["id"]})
        kind = kind_of(contacts)
        entry = {"campaign": camp["name"], "id": camp["id"], "kind": kind,
                 "counts": camp.get("contacts_by_state")}
        # Resolved for BOTH lifecycles: a composed-draft campaign ends too, and
        # `send_draft`/`queue_draft` are delivery paths like any other.
        pack, pack_error = _resolve_pack(camp["name"])
        if pack_error:
            entry["pack_error"] = pack_error
        if kind == "composed-draft":
            items = _composed_draft_items(settings, contacts, dd)
        else:
            entry["pack"] = pack.name if pack else None
            items = _fixed_template_items(settings, contacts, now, pack)
        blocked = _finished_refusal(settings, pack, now)
        if blocked:
            items = _hold_deliveries(entry, items, blocked)
        elif pack is not None:
            note = pack.undeclared_end_note()
            if note:
                entry["pack_note"] = note
        items = _hold_escalated(entry, items, taken)
        entry["items"] = items
        out.append(entry)
    return {"now": now.isoformat(), "dedup_days": dd, "campaigns": out}


# ---------------------------------------------------------------- mutations


def reconcile(settings, contact_id: str, *, commit: bool = False) -> dict:
    """Mark an already-sent composed-draft contact `sent` (the mail went out
    out-of-band; the row is stale). Records the Sent thread in the dossier.
    REFUSES if no Sent thread is found — never invents a send. Mails nothing."""
    c = _get_contact(settings, contact_id)
    if c is None:
        return {"ok": False, "error": "contact not found"}
    if c["state"] == "sent":
        return {"ok": True, "noop": "already sent", "email": c["email"]}
    threads, unreadable = _sent_threads_to(settings, c["email"], settings.dedup_days)
    if not threads:
        # A found thread is found whatever else could not be read, so the
        # evidence check only guards the NEGATIVE: "no Sent thread" is a claim
        # about every mailbox, and it cannot be made from a partial read.
        blocked = _evidence_refusal(c["email"], unreadable, "decide this was never sent")
        if blocked:
            return blocked
        return {"ok": False, "email": c["email"],
                "error": "no Sent thread — not actually sent; refusing to reconcile"}
    dossier = dict(c.get("dossier") or {})
    dossier["reconciled"] = True
    dossier["thread_id"] = _thread_id(threads[0])
    params = {"contact_id": contact_id, "state": "sent", "dossier": dossier}
    if not commit:
        return {"ok": True, "dry_run": True, "email": c["email"], "would_set": params}
    res = rpc.call_sync(settings, "campaign.update_contact", params)
    return {"ok": True, "email": c["email"], "result": res}


def mark(settings, contact_id: str, *, state: Optional[str] = None,
         dossier_patch: Optional[dict] = None, commit: bool = False) -> dict:
    """Set state and/or merge dossier keys on a contact (fetch-merge, since
    update_contact replaces the dossier wholesale)."""
    c = _get_contact(settings, contact_id)
    if c is None:
        return {"ok": False, "error": "contact not found"}
    dossier = dict(c.get("dossier") or {})
    if dossier_patch:
        dossier.update(dossier_patch)
    params: dict = {"contact_id": contact_id, "dossier": dossier}
    if state:
        params["state"] = state
    if not commit:
        return {"ok": True, "dry_run": True, "email": c["email"], "would_set": params}
    res = rpc.call_sync(settings, "campaign.update_contact", params)
    return {"ok": True, "email": c["email"], "result": res}


# ------------------------------------------------------------------- sends


def _pause_active(settings) -> bool:
    """Global kill-switch: <state_dir>/CS_PAUSE present → do nothing."""
    return settings.pause_path.exists()


def _escalation_block(settings, email: str) -> Optional[dict]:
    """Refusal when a human has personally taken this contact over.

    `pending()` already withholds the delivery item, but a caller can reach a
    sender with a contact_id it got anywhere — so the check lives on the send
    path too, where it cannot be routed around. Same shape as the CS_PAUSE
    refusal: a `blocked` string, so every existing caller already reports it."""
    rec = _escalated_map(settings).get((email or "").strip().lower())
    if rec is None:
        return None
    who = rec.get("owner") or "the operator"
    return {"ok": False, "email": email,
            "blocked": f"escalated — {who} has taken this contact over "
                       f"(release it with `escalated <email> --undo --commit`)"}


def _record_send(settings, *, contact_id, email, subject, message_id) -> None:
    from . import state as state_mod
    state_mod.State(settings.db_path).record(
        category="campaign", key=contact_id, email=email, subject=subject,
        message_id=message_id, status="sent", dry_run=False,
    )


def _finished_send_refusal(settings, c: dict, now: Optional[datetime]) -> Optional[dict]:
    """The composed-draft paths' end-of-campaign gate.

    They reach a contact by id and never touch `pending()`, so without this a
    finished campaign still mails through them. Unlike the fixed-template
    senders they do NOT require a pack (their copy is on the contact row), so a
    campaign with no pack passes — but a pack that exists and cannot be LOADED
    refuses: an unreadable pack is not evidence that the campaign is running."""
    camp_name = c.get("_campaign_name") or ""
    pack, pack_error = _resolve_pack(camp_name)
    if pack_error:
        return {"ok": False, "email": c["email"], "error": f"pack error: {pack_error}"}
    finished = _finished_refusal(settings, pack, now)
    if finished:
        return {"ok": False, "email": c["email"], "finished": True, "error": finished}
    return None


def send_draft(settings, contact_id: str, *, commit: bool = False,
               now: Optional[datetime] = None) -> dict:
    """Composed-draft outreach: surface the pre-written mail for review
    (CS_TRIAGE_MODE=draft → the operator's Gmail Drafts) or send it (=send →
    cs-SMTP).

    DEDUP FIRST against the Sent archive — if the mail is already there (the
    contact was mailed, even out-of-band) REFUSE and flag reconcile; never
    re-mail. A campaign whose pack says it is over refuses before any of that,
    and so does a contact a human has taken over (`cs escalated`). CS_PAUSE
    blocks everything."""
    c = _get_contact(settings, contact_id)
    if c is None:
        return {"ok": False, "error": "contact not found"}
    email = c["email"]
    over = _finished_send_refusal(settings, c, now)
    if over:
        return over
    if not _has_draft(c):
        return {"ok": False, "email": email, "error": "no draft_subject/body on contact"}
    # dedup truth: never re-mail what is already in Sent — in ANY of this
    # company's mailboxes, and never on evidence that could not read them all.
    threads, unreadable = _sent_threads_to(settings, email, settings.dedup_days)
    if c["state"] == "sent" or threads:
        return {"ok": False, "email": email, "next": "reconcile",
                "error": "already in Sent archive — reconcile, do NOT re-send"}
    blocked = _evidence_refusal(email, unreadable, "send")
    if blocked:
        return blocked
    taken = _escalation_block(settings, email)
    if taken:
        return taken
    if _pause_active(settings):
        return {"ok": False, "email": email, "blocked": "CS_PAUSE active"}

    subject = c.get("draft_subject") or ""
    body = c.get("draft_body") or ""
    mode = (settings.cs_triage_mode or "draft").lower()
    dossier = dict(c.get("dossier") or {})

    if mode != "send":  # draft mode — review surface, idempotent per contact
        if dossier.get("gmail_draft_pushed"):
            return {"ok": True, "email": email, "noop": "draft already in Gmail Drafts"}
        if not commit:
            return {"ok": True, "dry_run": True, "email": email, "mode": "draft",
                    "would": "append to the operator's Gmail Drafts for review"}
        from . import gmail_drafts
        # `body` is the same MODEL-COMPOSED draft_body the send-mode branch
        # below gates with send_guard via send_mail.send(body_md=body) — mark
        # it here too so a tell logs a WARNING and comes back as
        # guard_warnings; the draft is the review surface, so it is appended
        # either way, never blocked.
        folder, guard_warnings = gmail_drafts.append_draft(
            settings, email, subject, body, body_md=True)
        dossier["gmail_draft_pushed"] = True
        dossier["gmail_draft_day"] = _time.local_date(_time.now_utc(), settings.timezone)
        rpc.call_sync(settings, "campaign.update_contact",
                      {"contact_id": contact_id, "dossier": dossier})
        out = {"ok": True, "email": email, "mode": "draft", "pushed_to": folder}
        if guard_warnings:
            out["guard_warnings"] = guard_warnings
        return out

    # send mode (CS_TRIAGE_MODE=send) — autonomous send
    if not commit:
        return {"ok": True, "dry_run": True, "email": email, "mode": "send",
                "would": "cs-SMTP send + mark sent"}
    from . import send_guard, send_mail
    # The Sent-archive dedup above is the double-send backstop (a crash after the
    # send is caught next run as 'already in Sent' → reconcile), so send then mark.
    #
    # `body` is a MODEL-COMPOSED draft, so send_mail gates it (cs/send_guard.py).
    # A refusal is caught HERE only to report it in this verb's own JSON shape —
    # every state write is below the call, so the draft stays, the contact stays
    # out of 'sent', and no `sends` row appears, exactly as with any other refusal.
    try:
        mid = send_mail.send(settings, email, subject, body_md=body,
                             cc=settings.email_address or None)
    except send_guard.SendGuardRefusal as e:
        return {"ok": False, "email": email, "refused": "send_guard",
                "tells": list(e.tell_names), "error": str(e),
                "next": "review the draft by hand — the composed body did not "
                        "read as a message to the customer"}
    rpc.call_sync(settings, "campaign.update_contact",
                  {"contact_id": contact_id, "state": "sent", "message_id": mid})
    _record_send(settings, contact_id=contact_id, email=email, subject=subject, message_id=mid)
    return {"ok": True, "email": email, "mode": "send", "message_id": mid}


def queue_draft(settings, contact_id: str, *, commit: bool = False,
                now: Optional[datetime] = None) -> dict:
    """Headless-SAFE outreach: surface a composed-draft contact's pre-written
    mail in the operator's Gmail Drafts for review. NEVER sends — not via SMTP,
    not regardless of CS_TRIAGE_MODE. (The send-capable path is `send_draft`,
    deliberately kept out of the headless allow-list.)
    Dedup-first: refuses + flags reconcile if the address is already in Sent,
    and refuses outright for a contact a human has taken over (`cs escalated`)
    — a draft one keystroke from the wire is a delivery path.
    Idempotent per contact (won't push a second Gmail draft).

    A finished campaign is refused here too. This verb sends nothing, but what
    it produces is a message addressed to a customer sitting one keystroke from
    the wire — that is a delivery path, not a report."""
    c = _get_contact(settings, contact_id)
    if c is None:
        return {"ok": False, "error": "contact not found"}
    email = c["email"]
    over = _finished_send_refusal(settings, c, now)
    if over:
        return over
    if not _has_draft(c):
        return {"ok": False, "email": email, "error": "no draft_subject/body on contact"}
    threads, unreadable = _sent_threads_to(settings, email, settings.dedup_days)
    if c["state"] == "sent" or threads:
        return {"ok": False, "email": email, "next": "reconcile",
                "error": "already in Sent archive — reconcile, do NOT re-send"}
    # A queued draft is a message to a customer one keystroke from the wire, so
    # it fails closed on incomplete evidence exactly like a send.
    blocked = _evidence_refusal(email, unreadable, "queue a draft")
    if blocked:
        return blocked
    taken = _escalation_block(settings, email)
    if taken:
        return taken
    if _pause_active(settings):
        return {"ok": False, "email": email, "blocked": "CS_PAUSE active"}
    dossier = dict(c.get("dossier") or {})
    if dossier.get("gmail_draft_pushed"):
        return {"ok": True, "email": email, "noop": "draft already in Gmail Drafts"}
    if not commit:
        return {"ok": True, "dry_run": True, "email": email,
                "would": "append to the operator's Gmail Drafts for review (no send)"}
    from . import gmail_drafts
    # Same draft_body a send-mode send_draft() would gate with send_guard —
    # mark it body_md=True so a tell logs a WARNING and comes back as
    # guard_warnings; queue_draft never sends, so it never blocks on one.
    folder, guard_warnings = gmail_drafts.append_draft(
        settings, email, c.get("draft_subject") or "", c.get("draft_body") or "",
        body_md=True)
    dossier["gmail_draft_pushed"] = True
    dossier["gmail_draft_day"] = _time.local_date(_time.now_utc(), settings.timezone)
    rpc.call_sync(settings, "campaign.update_contact",
                  {"contact_id": contact_id, "dossier": dossier})
    out = {"ok": True, "email": email, "queued_to": folder}
    if guard_warnings:
        out["guard_warnings"] = guard_warnings
    return out


# --------------------------------------------- fixed-template pack senders


def _pack_send_preamble(settings, contact_id: str, *, now: Optional[datetime] = None):
    """Shared gates for the pack senders. Returns (contact, pack, error_dict);
    error_dict is None when clear to proceed."""
    c = _get_contact(settings, contact_id)
    if c is None:
        return None, None, {"ok": False, "error": "contact not found"}
    email = c["email"]
    camp_name = c.get("_campaign_name") or ""
    if camp_name in settings.excluded_campaign_set:
        return c, None, {"ok": False, "email": email,
                         "error": f"campaign '{camp_name}' is excluded from the general operator"}
    pack, pack_error = _resolve_pack(camp_name)
    if pack_error:
        return c, None, {"ok": False, "email": email, "error": f"pack error: {pack_error}"}
    if pack is None:
        # The loud skip: a fixed-template action with NO pack never sends.
        return c, None, {
            "ok": False, "email": email, "skipped": True,
            "error": (f"NO CAMPAIGN PACK for '{camp_name}' — fixed-template sends need "
                      "campaigns/<pack>/ (campaign.toml + templates or builders.py); "
                      "REFUSING to send. See cs/campaign_pack.py."),
        }
    # The campaign is over: refuse before any window/cap gate, so the reason the
    # operator reads is "this campaign ended", not "it is before the SMS hour".
    finished = _finished_refusal(settings, pack, now)
    if finished:
        return c, pack, {"ok": False, "email": email, "finished": True, "error": finished}
    if c["state"] != "sent":
        return c, pack, {"ok": False, "email": email,
                         "error": f"contact state '{c['state']}' — pack senders apply to contacts in 'sent'"}
    taken = _escalation_block(settings, email)
    if taken:
        return c, pack, taken
    if _pause_active(settings):
        return c, pack, {"ok": False, "email": email, "blocked": "CS_PAUSE active"}
    return c, pack, None


def send_reminder(settings, contact_id: str, *, commit: bool = False,
                  now: Optional[datetime] = None) -> dict:
    """Fixed-template reminder from the campaign's PACK (template or builders
    → send_mail). Gates: pack required (loud skip), campaign not finished
    (pack status / ends_on), reply-check on Gmail ground truth, once/day +
    cap, window hour, CS_PAUSE.

    STAMP-BEFORE-SEND: the once-per-day dossier stamp is the ONLY dedup a
    reminder has (there is legitimately prior Sent history with the contact),
    so it is written BEFORE the SMTP send — a crash in between skips one
    reminder (safe); send-then-stamp would double-send on the next run."""
    now = now or _time.now_utc()
    c, pack, err = _pack_send_preamble(settings, contact_id, now=now)
    if err:
        return err
    email = c["email"]
    tz = settings.timezone
    today = _time.local_date(now, tz)
    d = dict(c.get("dossier") or {})
    rah, _smsh, rmax = _pack_windows(settings, pack)
    if _time.local_hour(now, tz) < rah:
        return {"ok": False, "email": email,
                "blocked": f"before the reminder window (local hour < {rah})"}
    if d.get("last_reminder_sent_day") == today:
        return {"ok": True, "email": email, "noop": "reminder already sent today"}
    if d.get("reminders", 0) >= rmax:
        return {"ok": False, "email": email,
                "blocked": f"reminder cap reached ({d.get('reminders', 0)}/{rmax})"}
    after = _parse_dt(c.get("sent_at")) or _parse_dt(c.get("created_at"))
    replies, unreadable = _inbound_since(settings, email, after)
    if replies:
        return {"ok": False, "email": email, "next": "handle_reply",
                "error": "they replied — handle the reply, do NOT remind"}
    # Both refusals run BEFORE the stamp-before-send below, so neither leaves
    # half-advanced state: nothing is written until the reply gate has read
    # every mailbox it claims to have read.
    blocked = _evidence_refusal(email, unreadable, "send a reminder")
    if blocked:
        return blocked
    row = {**d, "email": email}
    try:
        subject, plain, html = pack.build_reminder(row)
    except campaign_pack.PackError as e:
        return {"ok": False, "email": email, "error": f"pack render failed: {e}"}
    if not commit:
        return {"ok": True, "dry_run": True, "email": email, "pack": pack.name,
                "subject": subject,
                "would": "stamp dossier (reminders+1, day) THEN cs-SMTP reminder"}
    d["reminders"] = d.get("reminders", 0) + 1
    d["last_reminder_sent_day"] = today
    rpc.call_sync(settings, "campaign.update_contact",
                  {"contact_id": contact_id, "dossier": d})
    from . import send_mail
    mid = send_mail.send(settings, email, subject, plain=plain, html=html,
                         cc=settings.email_address or None)
    d["last_reminder_mid"] = mid
    rpc.call_sync(settings, "campaign.update_contact",
                  {"contact_id": contact_id, "dossier": d})
    _record_send(settings, contact_id=contact_id, email=email, subject=subject, message_id=mid)
    return {"ok": True, "email": email, "pack": pack.name, "message_id": mid,
            "reminders": d["reminders"]}


def send_first(settings, contact_id: str, *, commit: bool = False,
               now: Optional[datetime] = None) -> dict:
    """First-notice fixed-template send from the campaign's PACK
    (builders.build → send_mail HTML). The counterpart to send_reminder for the
    INITIAL contact: the fixed-template lifecycle otherwise assumes contacts are
    already in 'sent' (the first notice sent out-of-band by a prep step). This
    verb sends that first notice in the pack's own HTML — dial codes are `tel:`
    links, which a markdown composed-draft (`send_draft`) would mangle — and
    marks the contact 'sent'.

    CS_TRIAGE_MODE=draft → push the rendered mail to the operator's Gmail Drafts
    for review (idempotent, never sends); =send → cs-SMTP send then mark 'sent'.

    Gates: pack required (loud refusal), campaign not finished (pack status /
    ends_on), contact NOT taken over by a human (`cs escalated`), contact NOT
    already `sent` (the idempotency guard — once the notice goes out the state
    flips to `sent` and a re-run refuses), CS_PAUSE.

    Unlike composed-draft `send_draft`, this does NOT dedup against the whole
    Sent archive: a fixed-template first notice is a deliberate action to a
    curated contact list (a migration warning to KNOWN customers), so unrelated
    recent Sent history with the address must not silently skip a legitimate
    target. Idempotency is the contact `state`, send-then-mark (the crash window
    between SMTP send and the state flip is sub-second and, for a one-time
    notice, a rare duplicate is far less bad than silently skipping a warning).

    THEREFORE IT IS ALSO OUTSIDE THE CROSS-MAILBOX GATE. Every other sender here
    refuses when a mailbox could not be read, because each one asks "have we
    already written / have they replied" and must not answer it from a partial
    read. This verb asks neither question of the archive at all, so there is no
    evidence for an unreadable mailbox to make incomplete — deliberate, and
    stated here so nobody reads "the gates read every mailbox" as covering this
    path. What guards it is the contact `state` and the curated list."""
    c = _get_contact(settings, contact_id)
    if c is None:
        return {"ok": False, "error": "contact not found"}
    email = c["email"]
    camp_name = c.get("_campaign_name") or ""
    if camp_name in settings.excluded_campaign_set:
        return {"ok": False, "email": email,
                "error": f"campaign '{camp_name}' is excluded from the general operator"}
    pack, pack_error = _resolve_pack(camp_name)
    if pack_error:
        return {"ok": False, "email": email, "error": f"pack error: {pack_error}"}
    if pack is None:
        # The loud skip: a fixed-template action with NO pack never sends.
        return {"ok": False, "email": email, "skipped": True,
                "error": (f"NO CAMPAIGN PACK for '{camp_name}' — fixed-template sends need "
                          "campaigns/<pack>/ (campaign.toml + templates or builders.py); "
                          "REFUSING to send. See cs/campaign_pack.py.")}
    finished = _finished_refusal(settings, pack, now)
    if finished:
        return {"ok": False, "email": email, "finished": True, "error": finished}
    taken = _escalation_block(settings, email)
    if taken:
        return taken
    if _pause_active(settings):
        return {"ok": False, "email": email, "blocked": "CS_PAUSE active"}
    # idempotency: once the first notice has gone out the state is 'sent' — never re-send
    if c["state"] == "sent":
        return {"ok": False, "email": email, "next": "reconcile",
                "error": "contact already 'sent' — the first notice already went out"}
    row = {**(c.get("dossier") or {}), "email": email}
    try:
        subject, plain, html = pack.build(row)
    except campaign_pack.PackError as e:
        return {"ok": False, "email": email, "error": f"pack render failed: {e}"}
    mode = (settings.cs_triage_mode or "draft").lower()
    dossier = dict(c.get("dossier") or {})

    if mode != "send":  # draft mode — review surface in Gmail Drafts, idempotent
        if dossier.get("gmail_draft_pushed"):
            return {"ok": True, "email": email, "noop": "draft already in Gmail Drafts"}
        if not commit:
            return {"ok": True, "dry_run": True, "email": email, "mode": "draft",
                    "subject": subject,
                    "would": "append the first-notice mail (HTML) to the operator's Gmail Drafts"}
        from . import gmail_drafts
        # plain/html are pack-rendered fixed-template copy, not model output —
        # body_md stays at its default (False): never inspected, matching the
        # send-mode branch below, which never gates this content with send_guard.
        folder, _guard_warnings = gmail_drafts.append_draft(
            settings, email, subject, plain, html=html, cc=settings.email_address or None)
        dossier["gmail_draft_pushed"] = True
        dossier["gmail_draft_day"] = _time.local_date(_time.now_utc(), settings.timezone)
        rpc.call_sync(settings, "campaign.update_contact",
                      {"contact_id": contact_id, "dossier": dossier})
        return {"ok": True, "email": email, "mode": "draft", "pushed_to": folder}

    # send mode (CS_TRIAGE_MODE=send) — autonomous send
    if not commit:
        return {"ok": True, "dry_run": True, "email": email, "mode": "send",
                "subject": subject, "would": "cs-SMTP send the first notice + mark 'sent'"}
    from . import send_mail
    mid = send_mail.send(settings, email, subject, plain=plain, html=html,
                         cc=settings.email_address or None)
    rpc.call_sync(settings, "campaign.update_contact",
                  {"contact_id": contact_id, "state": "sent", "message_id": mid})
    _record_send(settings, contact_id=contact_id, email=email, subject=subject, message_id=mid)
    return {"ok": True, "email": email, "mode": "send", "message_id": mid}


def send_sms(settings, contact_id: str, *, commit: bool = False,
             now: Optional[datetime] = None) -> dict:
    """Fixed-template SMS nudge from the campaign PACK's sms.txt, via the
    [sms] proxy (cs/sms.py). Same gates as send_reminder (pack required,
    campaign not finished, reply-check, once/day, evening window, CS_PAUSE) +
    the SMS capability itself must be on. STAMP-BEFORE-SEND, same rationale."""
    now = now or _time.now_utc()
    c, pack, err = _pack_send_preamble(settings, contact_id, now=now)
    if err:
        return err
    email = c["email"]
    d = dict(c.get("dossier") or {})
    phone = d.get("phone")
    if not _is_it_mobile(phone):
        return {"ok": False, "email": email, "error": "no mobile number in the contact dossier"}
    if not settings.sms_enabled:
        return {"ok": False, "email": email,
                "error": "[sms] capability off — set [sms].enabled = true in manifest.toml"}
    if not settings.sms_proxy_base:
        # The endpoint is a kernel default, so an empty one was declared on
        # purpose. Naming the two conditions apart keeps the message true:
        # the old single line told the operator to set a proxy_base that the
        # wizard does not ask for and that they almost never need.
        return {"ok": False, "email": email,
                "error": "[sms] endpoint declared empty — `cs config` names the layer that did it"}
    tz = settings.timezone
    today = _time.local_date(now, tz)
    _rah, smsh, _rmax = _pack_windows(settings, pack)
    if _time.local_hour(now, tz) < smsh:
        return {"ok": False, "email": email,
                "blocked": f"before the SMS window (local hour < {smsh})"}
    if d.get("last_sms_sent_day") == today:
        return {"ok": True, "email": email, "noop": "SMS already sent today"}
    after = _parse_dt(c.get("sent_at")) or _parse_dt(c.get("created_at"))
    replies, unreadable = _inbound_since(settings, email, after)
    if replies:
        return {"ok": False, "email": email, "next": "handle_reply",
                "error": "they replied — handle the reply, do NOT nudge"}
    blocked = _evidence_refusal(email, unreadable, "send an SMS")
    if blocked:
        return blocked
    row = {**d, "email": email}
    try:
        text = pack.sms_text(row)
    except campaign_pack.PackError as e:
        return {"ok": False, "email": email, "error": f"pack render failed: {e}"}
    if not commit:
        return {"ok": True, "dry_run": True, "email": email, "pack": pack.name,
                "phone": phone, "sms": text,
                "would": "stamp dossier (sms day/count) THEN SMS via the proxy"}
    d["last_sms_sent_day"] = today
    d["sms_count"] = d.get("sms_count", 0) + 1
    rpc.call_sync(settings, "campaign.update_contact",
                  {"contact_id": contact_id, "dossier": d})
    from . import sms as sms_mod
    try:
        sms_mod.send(settings, phone, text)
    except sms_mod.SmsError as e:
        # The stamp already burned today's slot — surface it loudly; no retry
        # today by design (stamp-before-send: never risk a double nudge).
        return {"ok": False, "email": email, "pack": pack.name,
                "error": f"SMS send failed AFTER stamp: {e} — no retry today (stamp-before-send)"}
    _record_send(settings, contact_id=contact_id, email=email,
                 subject=f"[sms] {text[:60]}", message_id=None)
    return {"ok": True, "email": email, "pack": pack.name, "phone": phone,
            "sms_count": d["sms_count"]}
