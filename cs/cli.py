"""cs CLI — a CLI front-end to the operator mailbox's mrcall-desktop engine.

The engine daemon (zylch-server@<uid> on the host) is the body: mail
archive, entity memory, tasks, trained writing voice, draft/send. Claude
Code is the brain. These verbs are thin transport:

  plan       ingest + self-filter + suppression; who the producer suggests.
  whoami     verify the engine session (account.who_am_i).
  rpc        generic JSON-RPC call: cs rpc <method> ['{"json": "params"}'].
  thread     all email threads exchanged with one address (both directions).
  contacted  did the operator write to this address in the last N days? (dedup)
  history    has this company EVER exchanged mail with this address, from any
             mailbox it can open — and which mailboxes it could not read.
  unanswered inbound still awaiting a human reply (deterministic, Sent-anchored).
  handled    record that a contact was resolved OUT OF BAND (phone, WhatsApp,
             in person) — their mail up to that moment stops being open work.
  escalated  record that a HUMAN has personally taken a contact over — still
             open, still owed an answer, but nobody else writes to them.
  tasks      open tasks on the engine; `tasks create` / `tasks close` write
             the engine task ledger (upsert on event_id / complete).
  business   CRM lookup by email (adapter from manifest [crm]).
  dossier    thread + contacted + tasks + CRM for one address, in one shot.
  config     the settings actually IN FORCE and which layer declares each —
             the answer to "is this operator in draft or send mode", so it
             never has to be re-derived from the files.
  chat       one engine-chat turn (drafting surface; destructive tools
             denied unless --allow'ed).
  project    `project new <slug>` stamps a project's written memory under
             docs/projects/ (index + status + timeline + meetings/).

Writing/sending NEVER happens here: contextual drafts are composed by the
engine (memory + trained voice + threading) and reviewed before any send;
only fixed-template campaign bulk uses the gated cs-SMTP/SMS paths.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import websockets

from . import _time, config, crm, ingest, rpc
from ._version import kernel_version
from . import campaign as campaign_mod
from . import filter as filt
from . import login
from . import manifest as manifest_mod
from . import state as state_mod
from . import project_init, project_update
from . import project_memory as project_memory_mod
from . import cron as cron_mod


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _self_label(settings) -> str:
    """The operator identity used in human-readable prints — ALWAYS derived
    from Settings (manifest → env), never a literal."""
    return settings.email_address or "the operator"


def _fmt_local(dt: datetime, tz_name: str) -> str:
    """A stored instant as the operator's own clock reads it (market timezone
    from the manifest) — a UTC string here would be read as local and be wrong
    by an hour or two exactly when it matters."""
    return f"{_time.to_local(dt, tz_name):%Y-%m-%d %H:%M %Z}"


# ---------------------------------------------------------------------- plan


def cmd_plan(args) -> int:
    settings = config.load()
    st = state_mod.State(settings.db_path)
    payload = ingest.fetch(settings, period=args.period)
    wl = filt.build_worklist(payload, settings, st)
    tc = wl["to_contact"]

    print(f"{settings.prog_name} plan — window {payload.get('window')} — {payload.get('generated_at')}")
    if payload.get("note"):
        print(f"producer note: {payload['note']}")
    print(
        f"raw:        leads={len(payload.get('leads', []))} "
        f"signups={len(payload.get('signups', []))} "
        f"cancellations={len(payload.get('cancellations', []))}"
    )
    print(
        f"candidates: leads={len(tc['lead'])} "
        f"signups={len(tc['signup'])} "
        f"cancellations={len(tc['cancellation'])}"
    )
    reasons = Counter((s["category"], s["reason"]) for s in wl["skipped"])
    if reasons:
        print("skipped:")
        for (cat, reason), n in sorted(reasons.items()):
            print(f"  {cat:13} {reason:11} x{n}")
    if args.verbose:
        print("\n-- candidates detail --")
        for l in tc["lead"]:
            print(
                f"  lead    {l.get('uid_prefix')}  {l.get('country')}  "
                f"pv={l.get('pageviews')}  hint={l.get('hint')}"
            )
        for b in tc["signup"]:
            print(
                f"  signup  {b.get('email_address')}  {b.get('country_alpha2')}  "
                f"{b.get('template')}"
            )
        for b in tc["cancellation"]:
            print(
                f"  cancel  {b.get('email_address')}  {b.get('country_alpha2')}  "
                f"{b.get('template')}"
            )
    print(
        "\nNOTE: this is the producer worklist only. Per-candidate truth "
        "(existing thread, memory, open tasks, recent contact) comes from "
        "the engine: use `cs dossier <email>`."
    )
    return 0


# ----------------------------------------------------------------- engine ro


def cmd_whoami(args) -> int:
    settings = config.load()
    res = rpc.call_sync(settings, "account.who_am_i")
    if getattr(args, "json", False):
        _print_json(res)
        return 0
    # Human-readable by default: braces and colons confuse exactly the
    # reader the quick-start sends here. `--json` keeps the raw shape.
    if not isinstance(res, dict) or "signed_in" not in res:
        _print_json(res)  # unknown shape: show the truth, never re-narrate it
        return 0
    if not res.get("signed_in"):
        print("not signed in — run cs login")
        return 0
    print(f"signed in as {res.get('email') or '<unknown email>'}")
    print(f"uid: {res.get('uid') or '?'}")
    ms = res.get("expires_at_ms")
    if ms:
        dt = datetime.fromtimestamp(ms / 1000).astimezone()
        print(f"session valid until {dt:%Y-%m-%d %H:%M %Z} (auto-renews)")
    for k, v in res.items():
        if k not in ("signed_in", "email", "uid", "expires_at_ms"):
            print(f"{k}: {v}")
    return 0


def cmd_rpc(args) -> int:
    settings = config.load()
    params = json.loads(args.params) if args.params else {}
    _print_json(rpc.call_sync(settings, args.method, params, timeout=args.timeout))
    return 0


def _search_threads(settings, query: str, limit: int) -> list[dict]:
    res = rpc.call_sync(
        settings, "emails.search", {"query": query, "folder": "all", "limit": limit}
    )
    return res.get("threads", []) if isinstance(res, dict) else []


def _threads_for(settings, email: str, limit: int = 50) -> list[dict]:
    """Threads exchanged with `email` in either direction, deduped."""
    seen, out = set(), []
    for q in (f"from:{email}", f"to:{email}", f"cc:{email}"):
        for t in _search_threads(settings, q, limit):
            tid = t.get("thread_id") or t.get("id")
            if tid not in seen:
                seen.add(tid)
                out.append(t)
    return out


def cmd_thread(args) -> int:
    if getattr(args, "full", False) and not args.json:
        print("--full requires --json", file=sys.stderr)
        return 2
    settings = config.load()
    threads = _threads_for(settings, args.email, args.limit)
    if getattr(args, "full", False):
        enriched = []
        for summary in threads:
            row = dict(summary)
            thread_id = summary.get("thread_id") or summary.get("id")
            if not thread_id:
                row["emails"] = []
                row["emails_error"] = "thread summary carries no thread_id"
            else:
                try:
                    res = rpc.call_sync(
                        settings,
                        "emails.list_by_thread",
                        {"thread_id": thread_id},
                        timeout=120,
                    )
                    row["emails"] = (
                        res.get("emails", []) if isinstance(res, dict) else []
                    )
                except Exception as e:  # noqa: BLE001 — one thread may degrade
                    row["emails"] = []
                    row["emails_error"] = f"{type(e).__name__}: {e}"
            enriched.append(row)
        _print_json(enriched)
        return 0
    if args.json:
        _print_json(threads)
        return 0
    if not threads:
        print(f"no email threads with {args.email}")
        return 0
    for t in threads:
        print(
            f"  {t.get('last_date') or t.get('date') or '?':25.25} "
            f"{(t.get('subject') or '(no subject)'):60.60} "
            f"msgs={t.get('message_count', '?')} thread_id={t.get('thread_id') or t.get('id')}"
        )
    return 0


def cmd_contacted(args) -> int:
    # DEDUP TRUTH = Gmail's own Sent folder (IMAP), NOT the engine. The engine's
    # `emails.search folder:sent` drops a thread the moment the customer replies
    # last (storage latest-sender bug) and can miss mail entirely — so it is
    # blind to replies we sent by hand. Read Gmail directly. See cs/gmail_archive.py.
    #
    # ONE mailbox and ONE window, and the output says so. This verb is the
    # re-contact gate ("may we write again within DEDUP_DAYS"), not the
    # company's contact history: it cannot see a colleague who answered from
    # his own mailbox, and a line ending on an unqualified "ground truth" was
    # read as a verdict on the company. `cs history` is that wider question.
    settings = config.load()
    from . import mailboxes

    prog = settings.prog_name or "cs"
    try:
        fan = mailboxes.sent_to_here(settings, args.email, days=args.days)
    finally:
        # Symmetric with `history`: the session cache is process-wide, so a verb
        # that has finished answering hands the mailbox back rather than leaving
        # a logged-in socket for whatever runs next in the same process.
        mailboxes.close_sessions()
    if not fan.complete:
        # THE THIRD OUTCOME. A mailbox that could not be opened must never
        # render as "nobody wrote": exit 1 means a real, read absence, and a
        # failed login answering with it is the exact inversion this verb is
        # relied on to prevent.
        print(
            f"UNKNOWN — {_self_label(settings)}'s Gmail Sent could not be read, "
            f"so whether {args.email} was written to in the last {args.days} "
            f"days is UNANSWERED. This is not a 'no'."
        )
        for u in fan.unreadable:
            print(f"  {u.describe()}")
        print(fan.scope_line())
        return 3
    msgs = fan.rows
    print(
        f"{'YES' if msgs else 'no'} — {_self_label(settings)} wrote to {args.email} "
        f"in the last {args.days} days ({len(msgs)} message(s)) [Gmail Sent]"
    )
    for m in msgs:
        print(f"  {m['date']}: {m['subject']}")
    print(fan.scope_line())
    print(
        f"  ONE mailbox, {args.days} days: this is the re-contact gate, not this "
        f"company's contact history. Ask that with `{prog} history {args.email}`."
    )
    return 0 if msgs else 1


def cmd_history(args) -> int:
    """Has this company EVER been in touch with this address — from ANY mailbox?

    The question `contacted` (one mailbox, one window), `thread` (the engine's
    archive of that same mailbox) and `dossier` (both, per contact) cannot
    answer, because they share one bound: mail that never passed through the
    operator mailbox exists in none of them.
    """
    settings = config.load()
    from . import gmail_archive, mailboxes

    email = args.email
    try:
        fan = mailboxes.merge_directions(
            mailboxes.sent_to_across(settings, email),
            mailboxes.inbound_since_across(settings, email),
        )
    finally:
        mailboxes.close_sessions()

    rows = sorted(
        fan.rows,
        key=lambda r: gmail_archive._parse_date(r.get("date"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    sent = [r for r in rows if r["direction"] == "sent"]
    inbound = [r for r in rows if r["direction"] == "in"]
    # Found is found: a positive answer stands whatever else could not be read.
    # Only a NEGATIVE one depends on the scope being complete, which is why the
    # exit status splits three ways instead of two.
    if rows:
        code = 0
    elif fan.complete:
        code = 1
    else:
        code = 3

    if getattr(args, "json", False):
        payload = fan.as_dict()
        payload["rows"] = rows
        payload["email"] = email
        payload["found"] = bool(rows)
        payload["sent"] = len(sent)
        payload["inbound"] = len(inbound)
        _print_json(payload)
        return code

    print(f"=== contact history: {email} ===\n")
    if rows:
        print(
            f"YES — {len(sent)} message(s) sent to them, {len(inbound)} received "
            f"from them, in {len({r['mailbox'] for r in rows})} of the "
            f"{len(fan.read)} mailbox(es) read. No window: this is 'ever', not "
            f"'recently'."
        )
    elif fan.complete:
        print(f"no — no mailbox in scope has ever exchanged mail with {email}.")
    else:
        print(
            f"UNKNOWN — nothing found in the mailboxes that could be read, and "
            f"at least one could NOT be. This is not a 'no'."
        )
    if rows:
        print("\nper mailbox:")
        for box in fan.read:
            s = sum(1 for r in sent if r["mailbox"] == box)
            i = sum(1 for r in inbound if r["mailbox"] == box)
            print(f"  {box:38.38} sent {s:>3}   received {i:>3}")
        print("\nmessages, newest first:")
        for r in rows[:20]:
            tag = "SENT" if r["direction"] == "sent" else "IN  "
            print(
                f"  [{tag}] {str(r.get('date') or '?'):31.31} "
                f"{r['mailbox']:28.28} {(r.get('subject') or '')[:40]}"
            )
        if len(rows) > 20:
            print(f"  … {len(rows) - 20} older not shown")
    print(f"\n{fan.scope_line()}")
    if not fan.complete:
        print(f"  {mailboxes.INCOMPLETE}")
    return code


def cmd_unanswered(args) -> int:
    # DETERMINISTIC replacement for the flaky LLM discovery query. Enumerate
    # recent inbound (Gmail All Mail, Date-header windowed) and subtract every
    # CONVERSATION we've since answered (Gmail Sent = dedup ground truth). No LLM
    # in the discovery loop — see cs/unanswered.py. What KIND of message it is
    # (autoresponder or not) is the engine's judgement, asked for, never
    # re-derived here.
    if getattr(args, "all_buckets", False) and not args.json:
        print("--all-buckets requires --json", file=sys.stderr)
        return 2
    settings = config.load()
    from . import unanswered as unanswered_mod

    d = unanswered_mod.sweep(settings, days=args.days)
    rows, held, mine = d["open"], d["handled"], d["escalated"]
    resumed, automatic = d.get("resumed") or [], d.get("automatic") or []
    courtesy = d.get("courtesy") or []
    crm_note = None
    if getattr(args, "crm", False):
        # One lookup per open sender through the CRM port. Opt-in because it
        # costs a round trip per row and the triage skill does not need it;
        # the review bootstrap does, because "who here is a paying customer"
        # is the first thing a human re-derives by hand otherwise.
        crm_note = unanswered_mod.crm_annotate(settings, rows)
    if args.json:
        if getattr(args, "all_buckets", False):
            d["crm_note"] = crm_note
            _print_json(d)
            return 0
        # The open list, exactly as before: this is the triage skill's PRIMARY
        # candidate feed and its shape is a contract. The out-of-band and
        # taken-over sections below are for the human — a machine reader wants
        # the work it may do, not the explanation of what was left out (and for
        # the taken-over rows the whole point is that it may NOT do them).
        _print_json(rows)
        return 0
    if not rows:
        # The re-labelled rows below ARE unanswered inbound, so an unqualified
        # "none" above a list of them would read as a contradiction.
        extra = len(mine) + len(held) + len(resumed) + len(automatic) + len(courtesy)
        print(f"no unanswered inbound in the last {args.days} days"
              + (f" beyond the {extra} listed below" if extra else ""))
    elif crm_note is not None or not getattr(args, "crm", False):
        # Plain sweep — the shape the triage skill has always parsed. A CRM
        # lookup that degraded prints here too: a half-filled column would
        # read as "these are not customers", which is the one wrong answer.
        print(f"{'EMAIL':38} {'WAIT':>5}  SUBJECT")
        for r in rows:
            print(f"{r['email']:38.38} {r['days_waiting']:>4}d  {(r['subject'] or '')[:60]}")
        print(f"\ntotal: {len(rows)} unanswered (oldest first)")
        if crm_note:
            print(f"  (CRM unavailable: {crm_note})")
    else:
        # Customers first, and SEPARATELY — same rows, same order, grouped by
        # the one fact that decides whose morning this is.
        known = [r for r in rows if r.get("crm_known")]
        rest = [r for r in rows if not r.get("crm_known")]
        if known:
            print(f"customers (in CRM) — {len(known)}:")
            print(f"{'EMAIL':38} {'WAIT':>5}  {'CRM':22} SUBJECT")
            for r in known:
                print(f"{r['email']:38.38} {r['days_waiting']:>4}d  "
                      f"{(r.get('crm') or ''):22.22} {(r['subject'] or '')[:42]}")
        if rest:
            print(f"{chr(10) if known else ''}not in CRM — {len(rest)}:")
            print(f"{'EMAIL':38} {'WAIT':>5}  SUBJECT")
            for r in rest:
                print(f"{r['email']:38.38} {r['days_waiting']:>4}d  "
                      f"{(r['subject'] or '')[:60]}")
        print(f"\ntotal: {len(rows)} unanswered (oldest first)")
    if mine:
        # NOT filtered away: re-labelled. These are open threads a human owns,
        # so they are still work — printed with the age of the takeover, which
        # is the number that says whether one has been forgotten.
        # "a human", not "you": most of these are the operator's own, but a row
        # can name a colleague, and a header that says otherwise would be wrong
        # for exactly the row he did not expect to see.
        print(f"\nwith a human — still open, not the operator's to answer "
              f"({len(mine)}):")
        for r in mine:
            who = r.get("escalated_owner") or "you"
            why = f" — {r['escalated_reason']}" if r.get("escalated_reason") else ""
            days = r.get("days_escalated")
            since = "" if days is None else f" for {days}d"
            print(
                f"  {r['email']:38.38} waiting {r['days_waiting']:>3}d  "
                f"with {who}{since}{why}"
            )
        print(f"  (hand one back: {settings.prog_name or 'cs'} escalated <email> "
              f"--undo --commit)")
    if held:
        # Say WHY these are not in the list. A contact that silently stops being
        # raised looks like a bug and gets reported as one.
        print(f"\nhandled out of band — not raised ({len(held)}):")
        for r in held:
            why = f" — {r['handled_reason']}" if r.get("handled_reason") else ""
            print(
                f"  {r['email']:38.38} resolved "
                f"{_fmt_local(r['handled_at'], settings.timezone)}{why}"
            )
        print(f"  (put one back: {settings.prog_name or 'cs'} handled <email> --undo)")
    if resumed:
        # NOT filtered away: re-labelled, like every other section here. We
        # answered in this conversation and they wrote again after — usually a
        # thank-you closing a finished job, which is not work and must not head
        # the queue. Sometimes a real follow-up, which is why it is printed with
        # its age and subject and not swallowed.
        print(f"\nanswered, then they wrote again — read, do not assume "
              f"({len(resumed)}):")
        for r in resumed:
            print(f"  {r['email']:38.38} {r['days_waiting']:>4}d  "
                  f"{(r['subject'] or '')[:52]}")
    if automatic:
        # The ENGINE classified their newest message as machine-generated; this
        # verb does not have an opinion about it. Named as the engine's call, so
        # a row the operator disagrees with is reported where it can be fixed.
        print(f"\nautomatic reply, per the engine — nobody is waiting "
              f"({len(automatic)}):")
        for r in automatic:
            print(f"  {r['email']:38.38} {r['days_waiting']:>4}d  "
                  f"{(r['subject'] or '')[:52]}")
    if courtesy:
        # We answered, they said thank you. The ENGINE decided that, per
        # message, and its own words for why ride on the row — so a verdict the
        # operator disagrees with is both VISIBLE and reportable where the
        # judgement lives. Printed last and never dropped: this is the section
        # whose whole purpose is that the queue above it stopped carrying them.
        print(f"\nclosing courtesy, per the engine — nothing owed "
              f"({len(courtesy)}):")
        for r in courtesy:
            why = (r.get("reason") or "").strip()
            print(f"  {r['email']:38.38} {r['days_waiting']:>4}d  "
                  f"{(r['subject'] or '')[:36]}"
                  + (f"  — {why[:44]}" if why else ""))
    if d.get("note"):
        # Say it. A sweep whose engine was asleep read every conversation the
        # way it did before it could ask — every message needing a reply, no
        # autoresponder recognised — which silently re-merges exactly the rows
        # the sections above exist to separate.
        print(f"\n  (engine unavailable: {d['note']} — no autoresponder was "
              f"recognised, so every message reads as needing a reply)")
    return 0


def cmd_tasks(args) -> int:
    settings = config.load()
    res = rpc.call_sync(
        settings,
        "tasks.list",
        {"include_completed": args.all, "limit": args.limit},
        timeout=120,
    )
    if args.json:
        _print_json(res)
        return 0
    rows = res if isinstance(res, list) else res.get("tasks", [])
    for t in rows:
        print(
            f"  [{(t.get('urgency') or '?'):8.8}] {(t.get('contact_email') or t.get('contact_phone') or '?'):38.38} "
            f"{(t.get('title') or t.get('summary') or '')[:70]}"
        )
    print(f"total: {len(rows)}")
    return 0


def cmd_tasks_create(args) -> int:
    # Write path into the ENGINE task ledger (tasks.create upserts on
    # owner_id+event_type+event_id — idempotent, never duplicates). Used when
    # the deterministic sweep (`cs unanswered`) catches an inbound the engine's
    # own detection missed, so the desktop UI sees it too. `sources` carries the
    # originating message id(s) (+ thread_id when known) so the task links back.
    settings = config.load()
    sources = {"emails": [args.event_id]}
    if args.thread_id:
        sources["thread_id"] = args.thread_id
    params = {
        "contact_email": args.email,
        "title": args.title,
        "event_id": args.event_id,
        "event_type": args.event_type,
        "action_required": True,
        "sources": sources,
        "urgency": args.urgency,
    }
    if args.name:
        params["contact_name"] = args.name
    if args.phone:
        params["contact_phone"] = args.phone
    if args.reason:
        params["reason"] = args.reason
    if args.suggested_action:
        params["suggested_action"] = args.suggested_action
    res = rpc.call_sync(settings, "tasks.create", params, timeout=120)
    if args.json:
        _print_json(res)
    else:
        res = res or {}
        print(f"ok={res.get('ok')} task_id={res.get('task_id')} created={res.get('created')}")
    return 0


def cmd_tasks_close(args) -> int:
    # Close (complete) a task in the engine ledger. The triage sweep treats a
    # CLOSED task for a contact as "already handled" (possibly answered from a
    # personal mailbox the Sent-anchored sweep can't see) and SKIPS it.
    settings = config.load()
    note = (args.note or "").strip()
    params = {
        "task_id": args.task_id,
        "actor": "operator",
        "why": note or "closed by the cs operator via `cs tasks close`",
    }
    if note:
        params["note"] = note
    res = rpc.call_sync(settings, "tasks.complete", params, timeout=120)
    if args.json:
        _print_json(res)
    else:
        res = res or {}
        print(f"ok={res.get('ok')}")
    return 0


# ---------------------------------------------------------------- handled
#
# THE MISSING CONCEPT (2026-08). A customer wrote on 17 July; the owner
# telephoned him and resolved it. Gmail Sent — the dedup ground truth, and
# rightly so — has no record of a phone call, so `cs unanswered` re-discovered
# that thread on every single tick and told the owner to write to him, daily,
# for over a month. The only filter the sweep had was `ignore`: permanent and
# undated, i.e. exactly wrong for a customer we want to keep talking to.
#
# `cs handled <email>` records the resolution WITH A TIMESTAMP: nothing they
# sent before that moment is open work, and a later message re-opens them by
# itself, with nothing to remember. `--undo` removes the record: this is a
# judgment an operator can type by mistake, so it must not be a one-way door.

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _print_handled_records(settings, records: dict) -> None:
    for email, r in sorted(records.items(), key=lambda kv: kv[1]["handled_at"], reverse=True):
        why = f" — {r['reason']}" if r.get("reason") else ""
        print(f"  {email:38.38} {_fmt_local(r['handled_at'], settings.timezone)}{why}")


def cmd_handled(args) -> int:
    settings = config.load()
    st = state_mod.State(settings.db_path)
    records = st.handled_out_of_band()

    if not args.email:  # bare `cs handled` = what is currently on record
        if not records:
            print("nothing recorded as handled out of band")
            return 0
        print(f"handled out of band ({len(records)}) — their mail up to that "
              f"moment is not open work:")
        _print_handled_records(settings, records)
        return 0

    # `--account` switches the ENGINE profile only, but this record is read by
    # surfaces that are all about the operator's OWN mailbox — recording it
    # against another account's engine would file the truth in the wrong place.
    if getattr(args, "account_switched", False):
        print(
            f"`handled` records against {_self_label(settings)}'s own open-work "
            f"ledger, which is what `unanswered` / `dossier` / `review` read; "
            f"--account switches only the engine profile, so the record would "
            f"not mean what it says. Run it without --account.",
            file=sys.stderr,
        )
        return 2

    email = (args.email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        # A clean refusal, not a traceback: this verb takes one address and
        # nothing else, and a typo must not write a row nobody will ever match.
        print(f"not an email address: {args.email!r}", file=sys.stderr)
        return 2
    existing = records.get(email)

    if args.undo:
        if not existing:
            print(f"no out-of-band record for {email} — nothing to undo")
            return 1
        st.unmark_handled(email)
        print(f"removed the out-of-band record for {email} "
              f"(was {_fmt_local(existing['handled_at'], settings.timezone)}"
              f"{' — ' + existing['reason'] if existing['reason'] else ''}).")
        print("  their earlier mail is open work again. Engine tasks closed at "
              "the time stay closed — reopen those in the desktop app if needed.")
        return 0

    if args.at:
        try:
            moment = _time.parse_moment(args.at, settings.timezone)
        except ValueError as e:
            print(f"--at: {e}", file=sys.stderr)
            return 2
        # A moment in the future would settle mail they have not sent yet —
        # a permanent ignore wearing a date, which is exactly what this is not
        # (that is `do_not_contact`). Today is legitimate: a date-only value
        # resolves to the END of its day, so allow a day of headroom and refuse
        # the mistyped year that would silently retire a customer.
        if moment > _time.now_utc() + timedelta(days=1):
            print(
                f"--at: {_fmt_local(moment, settings.timezone)} is in the future. "
                f"That would settle mail they have not sent yet — record when it "
                f"was ACTUALLY resolved, or leave --at out for now.",
                file=sys.stderr,
            )
            return 2
    else:
        moment = _time.now_utc()
    reason = (args.why or "").strip()

    # Read before the write: mark_handled clears any takeover record (a thread
    # cannot be both over and still being written), and a state change the
    # operator is not told about is the same invisible-filter problem this
    # ledger exists to solve.
    was_escalated = st.escalated_to_human().get(email)
    st.mark_handled(email, reason=reason, handled_at=moment)
    when = _fmt_local(moment, settings.timezone)
    if existing:
        # Idempotent by design: re-running is a no-op-shaped update, never an
        # error — the operator should not have to remember whether he already did it.
        print(f"updated: {email} handled out of band on {when}"
              f"{' — ' + reason if reason else ''} "
              f"(was {_fmt_local(existing['handled_at'], settings.timezone)})")
    else:
        print(f"recorded: {email} handled out of band on {when}"
              f"{' — ' + reason if reason else ''}")
    print("  nothing they sent before that moment is open work; a later "
          "message re-opens them on its own.")
    if was_escalated:
        print(f"  the takeover record is cleared "
              f"(they were with {was_escalated.get('owner') or 'you'} since "
              f"{_fmt_local(was_escalated['escalated_at'], settings.timezone)}).")

    # The task ledger is the OTHER place stale work piles up, so close it here
    # too — one command per real-world event, not two. actor="human" because a
    # human really did resolve it, and the rest of the system treats a human
    # close as final, which is exactly the intent.
    why = f"handled out of band — {reason}" if reason else \
        "handled out of band (resolved outside email)"
    res = rpc.call_sync(
        settings, "tasks.list", {"include_completed": False, "limit": 500}, timeout=120
    )
    rows = res if isinstance(res, list) else res.get("tasks", [])
    mine = [t for t in rows if (t.get("contact_email") or "").strip().lower() == email]
    closed = 0
    for t in mine:
        # `tasks.list` returns `id`; `tasks.complete` takes `task_id`. That
        # mismatch has already cost one bug — read both, skip a row with neither
        # rather than send the engine a null id.
        tid = t.get("id") or t.get("task_id")
        if not tid:
            continue
        rpc.call_sync(
            settings,
            "tasks.complete",
            {"task_id": tid, "actor": "human", "why": why, "note": why},
            timeout=120,
        )
        closed += 1
    print(f"engine tasks closed for this contact (actor=human): {closed}")
    return 0


# --------------------------------------------------------------- escalated
#
# THE SIBLING OF `handled`, and the difference is the whole point. `handled`
# says RESOLVED — off-email, thread over. This one says NOT resolved: still
# open, still owed an answer, but a named human has personally taken it over.
#
# What went wrong without it: the owner was mid-conversation with two customers
# — writing to them himself, one of them a case he wanted to finish before
# answering — and both the two-hourly headless operator (which answers
# customers itself) and `cs unanswered` still counted them as unanswered work.
# Two hands writing to the same customer is the tone-deaf failure this operator
# is built to avoid, and the only states on offer were "resolved" (a lie) and
# "nothing" (the collision).
#
# WHO MAY WRITE IT. Same rule as `handled`, for a sharper reason. `handled` is
# interactive-only because honouring "consider this closed" in an inbound mail
# would let anyone bury their own request. Here the sentence recorded is an
# assertion ABOUT A HUMAN — "he is personally handling this" — which no machine
# can make on that human's behalf, and which the review then repeats back to
# him as "you are on this one". A false one is worse than a false close: it
# does not merely hide the item, it tells the owner he has already got it.
#
# The asymmetry with the skills' own "DEFAULT ON UNCERTAINTY = ESCALATE" is
# real and is resolved by observing that the machine's escalation ALREADY has a
# home, so this verb does not need to serve both: a triage escalation is an
# OPEN engine task plus a line in the tick report, and a campaign escalation is
# the contact's `escalated` dossier flag (`cs campaign mark`). Both mean
# "somebody must look at this" and both correctly stay in the work list. This
# ledger means the opposite — "somebody IS looking at it" — and takes the
# contact OUT of the machine's work. One field with a `source` column would put
# the two on one row and make every reader responsible for branching on it;
# the first reader that forgot would hand a machine's guess the authority of
# the owner's word. They are different facts, so they are different stores.
#
# `--commit`, where `handled` writes straight away: a handled record is scoped
# by a timestamp and expires itself the moment the contact writes again, so a
# wrong address there costs one tick. This record has NO expiry by design, so a
# wrong address silences a real customer until a human notices — the one thing
# worth a preview.


def _print_escalated_records(settings, records: dict) -> None:
    now = _time.now_utc()
    for email, r in sorted(
        records.items(), key=lambda kv: kv[1]["escalated_at"]  # oldest first: the rotting ones
    ):
        who = r.get("owner") or "you"
        why = f" — {r['reason']}" if r.get("reason") else ""
        days = (now - r["escalated_at"]).days
        print(
            f"  {email:38.38} with {who} for {days}d "
            f"(since {_fmt_local(r['escalated_at'], settings.timezone)}){why}"
        )


def cmd_escalated(args) -> int:
    settings = config.load()
    st = state_mod.State(settings.db_path)
    records = st.escalated_to_human()

    if not args.email:  # bare `cs escalated` = who is with a human right now
        if not records:
            print("nobody is recorded as taken over by a human")
            return 0
        print(f"taken over by a human ({len(records)}) — still open, not the "
              f"operator's to answer:")
        _print_escalated_records(settings, records)
        return 0

    # Same reasoning as `handled`: the surfaces that read this ledger are all
    # about the operator's OWN mailbox, so recording it against another
    # account's engine profile would file the truth where nothing reads it.
    if getattr(args, "account_switched", False):
        print(
            f"`escalated` records against {_self_label(settings)}'s own open-work "
            f"ledger, which is what `unanswered` / `dossier` / `review` read; "
            f"--account switches only the engine profile, so the record would "
            f"not mean what it says. Run it without --account.",
            file=sys.stderr,
        )
        return 2

    email = (args.email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        print(f"not an email address: {args.email!r}", file=sys.stderr)
        return 2
    existing = records.get(email)
    who = (args.who or "").strip()
    reason = (args.why or "").strip()

    if args.undo:
        if not existing:
            print(f"no escalation record for {email} — nothing to release")
            return 1
        held = _fmt_local(existing["escalated_at"], settings.timezone)
        if not args.commit:
            print(f"DRY RUN — would release {email} back to the operator "
                  f"(taken over {held}). Nothing written; re-run with --commit.")
            return 0
        st.unmark_escalated(email)
        print(f"released {email} — the operator may work them again "
              f"(was taken over {held}).")
        return 0

    if not args.commit:
        # The preview names the address back, which is the check that matters:
        # this verb is typed about "these two", and resolving the wrong "these"
        # is how a customer goes quiet.
        print(f"DRY RUN — would record {email} as taken over by "
              f"{who or 'you'}{' — ' + reason if reason else ''}.")
        if existing:
            print(f"  (replaces the record of "
                  f"{_fmt_local(existing['escalated_at'], settings.timezone)})")
        print("  they would stop being offered as work to answer, and would be "
              "listed as yours, with an age, in `unanswered` / `review` / "
              "`dossier`. Nothing written; re-run with --commit.")
        if not reason:
            print("  no --why given: the record would carry only the date.")
        return 0

    st.mark_escalated(email, owner=who, reason=reason)
    print(f"recorded: {email} is with {who or 'you'}"
          f"{' — ' + reason if reason else ''}")
    print("  the operator will not draft or write to them, and no campaign "
          "will deliver to them, until you release it:")
    print(f"  release with `{settings.prog_name or 'cs'} escalated {email} "
          f"--undo --commit`, or close it with `{settings.prog_name or 'cs'} "
          f"handled {email} --why \"…\"` once it is resolved.")
    # Deliberately NO engine write. `handled` closes the contact's tasks
    # because the work is over; here it is not, and closing the task would
    # delete the only durable trace that somebody still owes this customer an
    # answer. The task stays open and the contact stays visible — re-labelled,
    # not removed.
    return 0


def cmd_business(args) -> int:
    # CRM lookup through the port (cs/crm): the adapter is chosen by the
    # manifest ([crm].adapter), never by an if-company switch. Never raises.
    settings = config.load()
    _print_json(crm.lookup(settings, args.email).as_dict())
    return 0


def _print_crm_section(settings, email: str) -> None:
    # CRM is AUXILIARY intel — the port never raises (degraded lookups carry a
    # note), and the verdict below never depends on it (CRM-agnostic verdict).
    res = crm.lookup(settings, email)
    print(f"\n-- CRM [{res.source}] ({len(res.rows)}) --")
    for row in res.rows:
        facts = "  ".join(f"{k}={row.facts.get(k, '')}" for k in res.render_hints)
        print(f"  {row.id}  {row.label}  {facts}")
    if res.note:
        print(f"  ({res.note})")


def cmd_dossier(args) -> int:
    settings = config.load()
    from . import gmail_archive, mailboxes

    email = args.email
    me = _self_label(settings)
    print(f"=== dossier: {email} ===\n")

    # --- Gmail correspondence = GROUND TRUTH. The engine search misses mail sent
    # by hand and collapses replied-to threads out of folder:sent, so dedup must
    # read Gmail itself, not the engine. See cs/gmail_archive.py. ---
    corr = gmail_archive.correspondence(settings, email)
    sent_us = [m for m in corr if m["direction"] == "sent"]
    inbound = [m for m in corr if m["direction"] == "in"]
    print(
        f"-- Gmail correspondence ({len(corr)}): {len(sent_us)} sent by {me}, "
        f"{len(inbound)} inbound [ground truth, drafts excluded] --"
    )
    for m in sorted(corr, key=lambda x: x.get("date") or "", reverse=True)[:12]:
        tag = "SENT" if m["direction"] == "sent" else "IN  "
        print(f"  [{tag}] {str(m.get('date') or '?'):31.31} {(m.get('subject') or '')[:46]}")
    if len(corr) > 12:
        print(f"  … {len(corr) - 12} older not shown")

    # The dedup gate — the one line of this dossier a caller acts on — reads
    # EVERY mailbox this company answers from, not only the operator's. A
    # colleague's reply from his own address is on no header of the mailbox
    # above, so the correspondence section can be empty while the company has
    # been talking to this person for months.
    #
    # UNBOUNDED, and the window applied here in memory. "Have we ever written
    # to them" is the question the verdict below needs; the 30-day window
    # answers only "may we write again today", and a 61-day-old reply from a
    # colleague — with nothing wrong anywhere — read as `cold contact` is the
    # incident's own shape surviving inside the check that exists to prevent
    # it. The read costs the same either way: `sent_to` fetches every matching
    # UID's header and filters by Date afterwards.
    fan = mailboxes.sent_to_across(settings, email, days=None)
    ever = fan.rows
    cutoff = _time.now_utc() - timedelta(days=args.dedup_days)
    dated = [(gmail_archive._parse_date(m.get("date")), m) for m in ever]
    recent = [m for dt, m in dated if dt is not None and dt >= cutoff]
    print(
        f"\n-- contacted in last {args.dedup_days}d (Gmail Sent, every mailbox "
        f"in scope): {'YES — do not cold-contact' if recent else 'no'} --"
    )
    for m in recent:
        print(f"  [{m.get('mailbox') or '?'}] {m['date']}: {m['subject']}")
    older = len(ever) - len(recent)
    if older:
        # Outside the window is NOT outside the history: this is the line that
        # says the contact is not cold even when the dedup answer is "no".
        print(f"  … plus {older} older message(s) to them — `{settings.prog_name or 'cs'} "
              f"history {email}` for all of it")
    print(f"  {fan.scope_line()}")
    if not fan.complete:
        print(f"  {mailboxes.INCOMPLETE}")
    # No IMAP below this line: hand the mailboxes back rather than leaving
    # logged-in sockets open for the rest of the verb (same as `history`).
    mailboxes.close_sessions()

    # --- is a human already writing to them? (cs escalated) The dossier is the
    # mandatory step before any contact, so this is the chokepoint where an
    # agent that never heard of the verb still learns to keep its hands off. ---
    st_ = state_mod.State(settings.db_path)
    taken = st_.escalated_to_human().get(email.strip().lower())
    print("\n-- taken over by a human (still open, not ours to answer) --")
    if not taken:
        print("  no record")
    else:
        who = taken.get("owner") or "you"
        why = f" — {taken['reason']}" if taken.get("reason") else ""
        days = (_time.now_utc() - taken["escalated_at"]).days
        print(f"  YES — with {who} since "
              f"{_fmt_local(taken['escalated_at'], settings.timezone)} ({days}d){why}")
        print("  → do NOT draft, do NOT write, do NOT deliver a campaign to them")

    # --- resolved off-email? The one thing Gmail cannot know (cs handled). ---
    rec = st_.handled_out_of_band().get(email.strip().lower())
    print("\n-- handled out of band (phone / WhatsApp / in person) --")
    if not rec:
        print("  no record")
    else:
        why = f" — {rec['reason']}" if rec.get("reason") else ""
        print(f"  YES — {_fmt_local(rec['handled_at'], settings.timezone)}{why}")
        # These rows carry the RAW Date header, so parse with the same module's
        # parser (tz-aware, naive read as UTC) before comparing with the record.
        dates = [d for d in (gmail_archive._parse_date(m.get("date")) for m in inbound) if d]
        last_in = max(dates, default=None)
        if last_in is not None and last_in <= rec["handled_at"]:
            print("  → their last message predates it: NOT open work "
                  "(the sweeps stop raising it; a newer message re-opens them)")
        elif last_in is not None:
            print("  → they have written SINCE: open work again")

    res = rpc.call_sync(settings, "tasks.list", {"limit": 500}, timeout=120)
    rows = res if isinstance(res, list) else res.get("tasks", [])
    mine = [t for t in rows if (t.get("contact_email") or "").lower() == email.lower()]
    print(f"\n-- open engine tasks for this contact ({len(mine)}) --")
    for t in mine:
        print(f"  [{t.get('urgency')}] {(t.get('title') or t.get('summary') or '')[:80]}")

    _print_crm_section(settings, email)

    if taken:
        # First, ahead of the dedup window: this one is not a timing rule that
        # will lapse, it is somebody else's conversation.
        verdict = (
            f"STOP — taken over by {taken.get('owner') or 'you'}; still open, "
            f"but a human is answering it"
        )
    elif recent:
        who = ", ".join(dict.fromkeys(m.get("mailbox") or "?" for m in recent))
        verdict = f"STOP — already written to within the dedup window, from {who}"
    elif ever:
        # Older than the window, and therefore NOT a dedup block — but equally
        # not a cold contact. The verdict names where and when, because that is
        # what the reader needs in order not to open with an apology for
        # silence that never happened.
        last = max(dated, key=lambda p: p[0] or datetime.min.replace(tzinfo=timezone.utc))
        when = str(last[1].get("date") or "an unknown date")
        verdict = (
            f"REPLY IN THREAD — {last[1].get('mailbox') or 'a mailbox here'} "
            f"already wrote to them ({when}); older than the {args.dedup_days}d "
            f"window, so not a dedup block, but NOT a cold contact"
        )
    elif not fan.complete:
        # Fail-closed, like every send gate: this verdict is the mandatory
        # pre-contact check, and "cold contact" read off a partial mailbox
        # scan is precisely the sentence that produced an apology for two
        # months of silence that had not happened.
        verdict = (
            "STOP — evidence incomplete: "
            + "; ".join(u.describe() for u in fan.unreadable)
            + ". Nobody can say this contact is cold until that mailbox is "
              "readable again."
        )
    elif sent_us or inbound:
        verdict = "REPLY IN THREAD — real history exists (not cold)"
    else:
        verdict = "cold contact — needs operator sign-off"
    print(f"\nverdict: {verdict}")
    return 0


def cmd_chat(args) -> int:
    settings = config.load()
    allow = {t.strip() for t in (args.allow or "").split(",") if t.strip()}
    out = asyncio.run(
        rpc.chat(settings, args.message, allow_tools=allow, timeout=args.timeout)
    )
    res = out["result"] or {}
    text = res.get("response") or res.get("text") or res
    if isinstance(text, (dict, list)):
        _print_json(text)
    else:
        print(text)
    if out["approvals"]:
        print("\n-- tool approvals --")
        for a in out["approvals"]:
            print(f"  {a['tool']}: {a['mode']}")
    return 0


# ----------------------------------------------------------------- campaign


def cmd_campaign_list(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.list_campaigns(settings))
    return 0


def cmd_campaign_pending(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.pending(settings, name=args.name))
    return 0


def cmd_campaign_reconcile(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.reconcile(settings, args.contact_id, commit=args.commit))
    return 0


def cmd_campaign_mark(args) -> int:
    settings = config.load()
    patch = json.loads(args.dossier) if args.dossier else None
    _print_json(
        campaign_mod.mark(
            settings, args.contact_id, state=args.state, dossier_patch=patch, commit=args.commit
        )
    )
    return 0


def cmd_campaign_send_draft(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.send_draft(settings, args.contact_id, commit=args.commit))
    return 0


def cmd_campaign_queue_draft(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.queue_draft(settings, args.contact_id, commit=args.commit))
    return 0


def cmd_campaign_send_first(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.send_first(settings, args.contact_id, commit=args.commit))
    return 0


def cmd_campaign_send_reminder(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.send_reminder(settings, args.contact_id, commit=args.commit))
    return 0


def cmd_campaign_send_sms(args) -> int:
    settings = config.load()
    _print_json(campaign_mod.send_sms(settings, args.contact_id, commit=args.commit))
    return 0


def cmd_campaign_packs(args) -> int:
    # Read-only pack discovery — the "have we ever done something like this?"
    # verb. Precedent lives in the clone's campaigns/ directory.
    from . import campaign_pack

    try:
        packs = campaign_pack.list_packs()
    except campaign_pack.PackError as e:
        print(f"pack error: {e}", file=sys.stderr)
        return 1
    if args.json:
        _print_json([p.summary() for p in packs])
        return 0
    if not packs:
        print("no campaign packs (campaigns/<name>/campaign.toml). "
              "Past-campaign precedent lives there — see cs/campaign_pack.py.")
        return 0
    # The EFFECTIVE status, not the declared one: a pack still saying "active"
    # past its own ends_on prints "ended", because that is what the send paths
    # will do with it and a listing that disagrees with them is a trap.
    today = datetime.now(timezone.utc).date()
    for p in packs:
        print(f"  {p.name:34.34} {p.kind:15.15} {p.effective_status(today):8.8} "
              f"{(p.dates or ''):18.18} {p.description}")
    return 0


def cmd_ask(args) -> int:
    # Read-only query to the engine's PROCESSED state — the engine ingests
    # every 5 min and maintains memory + tasks + handled-state. Use THIS to
    # learn "what did the client write / what have we already replied / is it
    # handled", NOT a raw emails.list_by_thread re-parse (a flat thread can't
    # see an out-of-band reply, a closed task, or what memory marks handled).
    # allow_tools empty → structurally read-only (cannot send), composes nothing.
    settings = config.load()
    out = asyncio.run(rpc.chat(settings, args.question, allow_tools=set(), timeout=args.timeout))
    res = out["result"] or {}
    text = res.get("response") or res.get("text") or res
    _print_json(text) if isinstance(text, (dict, list)) else print(text)
    return 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _engine_stamp(value) -> datetime | None:
    """An engine timestamp as tz-aware UTC. The engine serialises UTC without
    an offset, so a naive value is read as UTC — the same convention as
    `cs/_time.py` and `cs/draft_state.py`."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _composed_key(draft: dict) -> str:
    return draft.get("created_at") or draft.get("updated_at") or ""


def _all_but_newest(drafts: list[dict]) -> list[dict]:
    newest = max(drafts, key=_composed_key)
    return [d for d in drafts if d is not newest]


def _touched_since(drafts: list[dict], since: datetime) -> list[dict]:
    """Drafts the engine wrote to at or after `since`.

    The engine's `create_draft` is idempotent: composing the same mail twice
    returns the EXISTING row and stamps its `updated_at`. That stamp is the
    only signal an outside caller gets, because no new id appears — see the
    module docstring of the engine's `rpc/draft_queries.py`.
    """
    out = []
    for d in drafts:
        stamp = _engine_stamp(d.get("updated_at"))
        if stamp is not None and stamp >= since:
            out.append(d)
    return out


def cmd_draft_reply(args) -> int:
    # Like `chat` but with NO `--allow` option: allow_tools is hardcoded empty,
    # so the engine denies send_draft whatever the message says. Structurally
    # incapable of sending — this is the verb the headless operator may run.
    #
    # CRITICAL: the engine's compose step auto-runs create_draft (non-destructive,
    # so it is NOT gated by allow_tools) and stores the draft in the ENGINE draft
    # store — which is NOT the operator's Gmail Drafts, the surface where review
    # and sending actually happen. Without mirroring, the draft is invisible in
    # Gmail and the operator (rightly) concludes "nothing was drafted". So we diff
    # the engine draft store around the compose call and APPEND the freshly composed
    # draft into Gmail Drafts via IMAP (same mechanism as `campaign queue-draft`).
    # Guarded by tests/test_draft_reply.py + the run.sh grep gate — do NOT remove
    # the append_draft call: that reintroduces the "draft not in Gmail" regression.
    settings = config.load()
    from . import gmail_drafts

    turn_started = _utcnow()
    before = {d.get("id") for d in
              (rpc.call_sync(settings, "drafts.list", {}, timeout=args.timeout) or [])}
    out = asyncio.run(rpc.chat(settings, args.message, allow_tools=set(), timeout=args.timeout))
    res = out["result"] or {}
    text = res.get("response") or res.get("text") or res
    if isinstance(text, (dict, list)):
        _print_json(text)
    else:
        print(text)

    after = rpc.call_sync(settings, "drafts.list", {}, timeout=args.timeout) or []
    fresh = [d for d in after if d.get("id") not in before]
    if not fresh:
        # No NEW id. Two very different things look like this, and the engine
        # distinguishes them through `updated_at`: composing the same mail
        # twice returns the existing draft (and stamps it) instead of writing
        # a duplicate, so an id that moved during this turn IS the reply that
        # was asked for. It is NOT re-mirrored: the run that first composed it
        # already appended it to Gmail Drafts, and a second append is the very
        # duplicate this de-duplication exists to prevent.
        reused = _touched_since(after, turn_started)
        if reused:
            print("\n[gmail-drafts] engine reused an existing draft "
                  f"({', '.join(str(d.get('id')) for d in reused)}) — identical "
                  "to one already composed, so nothing new was mirrored. "
                  "Review it in Gmail Drafts, or edit the instruction to "
                  "compose a different reply.", file=sys.stderr)
            return 0
        # Engine asked a clarifying question / escalated instead of composing.
        print("\n[gmail-drafts] engine composed no new draft — nothing to mirror.",
              file=sys.stderr)
        return 0
    if len(fresh) > 1:
        # ONE turn, several new drafts: only the newest is mirrored, so the
        # others would leave the engine store silently and never reach the
        # surface the operator reviews on. Name them — an unmirrored draft the
        # operator cannot see is exactly how duplicate replies accumulate.
        print(f"\n[gmail-drafts] WARNING: the engine composed {len(fresh)} drafts "
              f"in one turn; mirroring the newest only. Not mirrored: "
              f"{', '.join(str(d.get('id')) for d in _all_but_newest(fresh))}. "
              f"Retire the extras with `cs draft-delete`, or review them with "
              f"`cs review`.", file=sys.stderr)
    d = max(fresh, key=_composed_key)
    to = ", ".join(d.get("to_addresses") or [])
    if not to or not (d.get("body") or "").strip():
        print("\n[gmail-drafts] ERROR: composed draft has no recipient/body; "
              "NOT appended to Gmail Drafts.", file=sys.stderr)
        return 1
    # `body` is the engine's freshly composed reply — always model output —
    # so body_md=True: send_guard's deterministic tells run and, on a hit,
    # log a WARNING and come back here to print, never to block the append.
    folder, guard_warnings = gmail_drafts.append_draft(
        settings,
        to=to,
        subject=d.get("subject") or "",
        body=d.get("body") or "",
        in_reply_to=d.get("in_reply_to"),
        references=d.get("references"),
        cc=", ".join(d.get("cc_addresses") or []) or None,
        body_md=True,
    )
    print(f"\n[gmail-drafts] draft appended to Gmail Drafts ({folder}): "
          f"{d.get('subject')} -> {to}")
    if guard_warnings:
        print(f"[gmail-drafts] send-guard tell(s) — review before sending: "
              f"{'; '.join(guard_warnings)}")
    return 0


def cmd_draft_delete(args) -> int:
    # Take ONE bad draft out of the review queue. Destructive, so it follows the
    # campaign verbs' contract exactly: dry-run unless --commit, and the result
    # dict is printed verbatim (what matched, what would move where) rather than
    # re-narrated. Exit 1 on a refusal so a script cannot read "nothing matched"
    # as "deleted".
    settings = config.load()
    from . import gmail_drafts

    out = gmail_drafts.delete_draft(
        settings, uid=args.uid, message_id=args.message_id, commit=args.commit
    )
    _print_json(out)
    return 0 if out.get("ok") else 1


def cmd_catchup(args) -> int:
    """Bring the ENGINE's state up to date, and report what changed.

    Everything the engine owns — synced mail, entity memory, the task ledger,
    the `needs_reply` verdict — is only as fresh as the last pass of its own
    headless auto-update loop. Reading a stale ledger is how a review shows work
    that is already done, so `/cs-review` offers this pass when the last one is
    older than the interval that engine is configured for.

    It DRIVES the engine's own surfaces and re-implements none of them:
    `sync.run` fetches new mail, then `update.run` runs memory extraction plus
    task detection — the same pipeline the scheduled loop runs, including the
    pass that CLOSES a task when an inbound message resolves it. That loop and
    this verb are the same single-flight pipeline, so a pass already in progress
    answers `busy` and this one reports that instead of waiting or retrying.

    It drafts nothing and sends nothing. It is the engine pass, not the operator
    pass, and it therefore runs while `CS_PAUSE` is present: the switch stops
    customer-facing work, and refusing a read-and-classify pass would leave a
    paused clone permanently unable to show fresh state.

    A NAMED verb rather than two `cs rpc` calls, because permission rules match
    command TEXT: the stamped settings allow `cs rpc:*` broadly, so a pass that
    spends real LLM budget has to be its own gateable command.

    Prints the task diff `update.run` returns — created / closed / updated ids —
    so the caller reports what the pass CHANGED instead of narrating that it
    ran.

    `--check` answers whether the pass is WARRANTED and writes nothing: it
    compares the newest inbound in the mailbox against what the engine holds
    (`review.engine_freshness`). It is the read a review runs every time, which
    is why it is a flag on this verb and not a second one — and why the stamped
    permissions allow `catchup --check` while leaving the pass itself to ask."""
    settings = config.load()
    if getattr(args, "check", False):
        from . import review as review_mod

        st = review_mod.engine_freshness(settings)
        if args.json:
            _print_json(st)
        else:
            print(("catch-up warranted: " if st["stale"] else "engine is current: ")
                  + (st.get("reason") or ""))
            if st.get("note"):
                print(f"  ! {st['note']}")
        return 0

    out: dict = {}
    try:
        res = rpc.call_sync(settings, "sync.run", {}, timeout=args.timeout)
        out["sync"] = res if isinstance(res, dict) else {"result": res}
    except Exception as e:  # noqa: BLE001 — the second pass is still worth running
        out["sync"] = {"success": False, "error": f"{type(e).__name__}: {e}"}
    try:
        res = rpc.call_sync(settings, "update.run", {}, timeout=args.timeout)
        out["update"] = res if isinstance(res, dict) else {"result": res}
    except Exception as e:  # noqa: BLE001
        out["update"] = {"success": False, "error": f"{type(e).__name__}: {e}"}

    # The engine runs the SAME pipeline on its own schedule and answers a
    # second caller with `{"busy": true, "success": false}` and an empty diff
    # rather than queueing. That is a correct outcome, not a failure: the pass
    # this verb wanted is already happening. Say so, exit 0, and never retry —
    # a loop here would spend the budget the single-flight guard exists to save.
    busy = bool(out["update"].get("busy"))
    if args.json:
        _print_json(out)
    else:
        sync = out["sync"]
        print(f"sync.run: {sync.get('summary') or sync.get('error') or 'done'}")
        upd = out["update"]
        diff = upd.get("updated_tasks") or {}
        if busy:
            print("update.run: engine busy — a pass is already running; "
                  "nothing to report from this one")
        elif upd.get("error"):
            print(f"update.run: {upd['error']}")
        else:
            print(f"update.run: {len(diff.get('created') or [])} task(s) created, "
                  f"{len(diff.get('closed') or [])} closed, "
                  f"{len(diff.get('updated') or [])} updated")
        for label in ("created", "closed", "updated"):
            for tid in (diff.get(label) or []):
                print(f"  {label}: {tid}")
    ok = out["sync"].get("success") is not False and (
        busy or out["update"].get("success") is not False)
    return 0 if ok else 1


def cmd_review(args) -> int:
    settings = config.load()
    from . import review as review_mod

    d = review_mod.gather(settings)
    _print_json(d) if args.json else print(review_mod.render(d))
    return 0


def cmd_drive(args) -> int:
    # Read-only Google Drive via the cs service-account (Shared Drives shared
    # with the SA). Delegates to cs.drive.main so this verb and the
    # `python -m cs.drive` self-test share one implementation. Lazy import:
    # google-auth / requests load only when the verb is actually used.
    from . import drive as drive_mod

    return drive_mod.main(args.drive_args)


def cmd_accounts(args) -> int:
    # List the configured multi-account registry (name -> uid) for THIS project.
    settings = config.load()
    amap = settings.account_map
    if not amap:
        print("no accounts configured. Set CS_ACCOUNTS in this project's cs env, e.g.\n"
              "  CS_ACCOUNTS=<name>:<uid>,<name2>:<uid2>")
        return 0
    default = settings.engine_owner_uid
    for name, uid in amap.items():
        print(f"  {name:12} {uid}{'  (default)' if uid == default else ''}")
    return 0


def cmd_config(args) -> int:
    # What this operator is ACTUALLY configured to do, and which file declares
    # each value. Six value layers resolve into one setting, and reading the
    # files cannot answer the question without mentally executing the
    # precedence rules — which is where readers, human and headless, get it
    # wrong. Read-only, network-free, and it never prints a secret value, so
    # it is safe to run first thing in any tick and to paste into a report.
    from . import config_report

    rep = config_report.build(config.load(), include_all=args.all)
    _print_json(rep) if args.json else print(config_report.render(rep))
    # Exit 0 even when a setting is declared twice: this is a READ verb, and a
    # reader (human or agent) who asked "what am I configured to do" and got a
    # non-zero exit reads it as "the question failed", not as "here is your
    # answer plus a defect". The duplicate is loud in the output and in
    # `--json`; `--strict` is the hook for a wrapper or a CI step that wants
    # the failure as an exit code.
    return 1 if (args.strict and rep["duplicates"]) else 0


def cmd_memory(args) -> int:
    # Where this operator's knowledge lives: the ten durable stores the
    # membership rule admits, each with its authority, read/write surface,
    # and resolved location + reachability on THIS machine. Read-only,
    # network-free apart from the engine row's one connection-level probe,
    # and it never prints store contents, so it is safe to run first thing
    # in any tick and to paste into a report.
    from . import memory_report

    rep = memory_report.build(config.load())
    _print_json(rep) if args.json else print(memory_report.render(rep))
    return 0


def cmd_llm(args) -> int:
    # The kernel's own LLM configuration: what it resolves to now, what else is
    # on offer, and how to change it. Non-interactive on purpose — the same
    # verbs have to work from a cron wrapper and from a human's terminal, and a
    # prompt loop only works for one of those.
    from . import model_catalog, model_config

    action = getattr(args, "llm_action", None) or "show"

    if action == "show":
        cfg = model_config.current_config()
        print(f"  provider   {cfg['provider']}  ({cfg['source']})")
        print(f"  base_url   {cfg['base_url']}")
        print(f"  api key    {cfg['api_key']}")
        print("  models")
        for role, model in cfg["models"].items():
            rates = model_config.token_rates(model)
            price = f"${rates[0]:.2f}/${rates[1]:.2f} per 1M" if rates else "price unknown"
            print(f"    {role:<12} {model:<38} {price}")
        return 0

    if action == "models":
        rows = model_catalog.menu(model_catalog.FAMILIES, refresh=args.refresh)
        if not rows:
            print("catalog unavailable (no network, no cache)")
            return 1
        offline = [r for r in rows if not r["live"]]
        print(f"{'family':<18} {'resolves to':<36} {'shipped':<11} "
              f"{'in/out per 1M':<17} note")
        for r in rows:
            price = f"${r['input_per_m']:.2f}/${r['output_per_m']:.2f}"
            print(f"  @{r['family']:<16} {r['model']:<36} {r['shipped']:<11} "
                  f"{price:<17} {r['note']}")
        if offline:
            print(f"\n  {len(offline)} row(s) from the offline snapshot — "
                  "prices and ids may be stale.")
        print("\nSet one with:  cs llm set <role|tier> @<family>   (or a pinned model id)")
        return 0

    if action == "set":
        key = args.key.strip().upper()
        known = ({r.value.upper() for r in model_config.Role}
                 | {t.value.upper() for t in model_config.Tier})
        if key not in known:
            print(f"unknown role/tier {args.key!r}; known: {', '.join(sorted(known))}")
            return 2
        spec = args.spec.strip()
        # Validate BEFORE writing: a family typo that only surfaces on the next
        # cron run is a config file that looks fine and a loop that does not.
        try:
            resolved = model_catalog.resolve(spec)
        except KeyError as e:
            print(str(e))
            return 2
        settings = config.load()
        # Without a slug the state dir is ~/.cs, but env_file_chain() only
        # includes ~/.<slug>-cs/.env when a slug exists — the write would
        # succeed and then never be read, which is worse than refusing.
        if not settings.slug:
            print("no manifest slug resolved: there is no clone env file to "
                  "write. Run from a clone, or set MODEL_" + key +
                  " in the environment instead.")
            return 2
        env_path = settings.state_dir / ".env"
        model_config.write_env(env_path, {f"MODEL_{key}": spec})
        print(f"  MODEL_{key}={spec}  ->  {resolved}")
        print(f"  written to {env_path}")
        return 0

    if action == "test":
        endpoint = model_config.llm_env()
        model = args.model or model_config.model_for(model_config.Role.CLASSIFIER)
        result = model_config.check_connection(
            endpoint.base_url, endpoint.api_key, model
        )
        status = "ok" if result["success"] else "FAILED"
        print(f"  {status}  {model} via {endpoint.base_url}  "
              f"({result['latency_ms']:.0f} ms)")
        if not result["success"]:
            print(f"  {result['error']}")
            return 1
        return 0

    return 2


# --------------------------------------------------------------------- main


# init/update/login are normally intercepted by the early dispatch in
# main() below, before this module's argparse tree is even built — so these
# three wrappers are never actually invoked in ordinary use. They exist so
# `cs --help` (bare, no subcommand) lists all three "human verbs" truthfully
# instead of the tree silently ending at `plan`, and so `cs login` (etc.)
# still has a working path if the early dispatch is ever bypassed or
# reordered by a future change.
#
# `login` is the one stub route real invocations DO take: `cs --account
# <name> login …` puts `--account` at argv[0], so the early dispatch above
# (which only fires on a bare argv[0] in ("init","update","login")) never
# triggers — this is the founder-sweep migration path, one `cs --account
# <name> login` per secondary account. That is why the login stub mirrors
# `cs/login.py`'s own options explicitly (`--descriptor PATH`) instead of
# using `nargs=argparse.REMAINDER` the way init/update's stubs do: an
# UNKNOWN option-looking token (anything starting with "-") inside a
# subparser's REMAINDER escapes to the parent parser as "unrecognized
# arguments" — verified directly, and it has NOTHING to do with a preceding
# top-level optional: `cs update --version`, with no `--account` at all,
# fails the exact same way. A token the subparser DECLARES explicitly
# parses fine, REMAINDER elsewhere in the same subparser or not. So `cs
# --account X login --descriptor P` used to die inside `parse_args` itself
# with "unrecognized arguments: --descriptor" (exit 2), before dispatch
# ever ran, purely because `--descriptor` was REMAINDER-swallowed instead
# of declared — declaring it here fixes that. init/update never hit this in
# practice because their real invocations always take the early dispatch
# above (bare `cs init`/`cs update`, argv[0] matches); a through-the-tree
# invocation of their stubs with an unrecognized flag fails the identical
# way (e.g. `cs --account X update --version` still exits 2 today), which
# is acceptable because `--account` is meaningless for init/update anyway —
# login is the one stub real invocations actually take. Maintenance rule:
# any new `cs login` option must be added BOTH to `cs/login.py`'s own
# parser AND on this stub — the failure mode of forgetting is LOUD
# (argparse exit 2 here), never a silent drop.
def cmd_init_stub(args) -> int:
    return project_init.cmd_init(args.init_args)


def cmd_update_stub(args) -> int:
    return project_update.cmd_update(args.update_args)


def cmd_login_stub(args) -> int:
    rest = ["--descriptor", args.descriptor] if args.descriptor else []
    return login.cmd_login(
        rest,
        account_switched=getattr(args, "account_switched", False),
        account_name=getattr(args, "account", None),
    )


def main(argv=None) -> int:
    # --- init/update/login: dispatched before the argparse tree is even
    # built. init/update must work WITHOUT a manifest (a brand-new machine
    # has none yet); login DOES need one (it runs from a clone root) but
    # loads it itself (see login.cmd_login) so it can be exercised the same
    # way in isolation. See the "human verbs" stub subparsers below for why
    # all three are ALSO registered on the real argparse tree. ---
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] in ("init", "update", "login"):
        cmd = argv[0]
        rest = argv[1:]
        if cmd == "init":
            return project_init.cmd_init(rest)
        elif cmd == "update":
            return project_update.cmd_update(rest)
        elif cmd == "login":
            return login.cmd_login(rest)

    try:
        settings = config.load()
    except manifest_mod.ManifestError as e:
        # Loud startup error (bad manifest / unknown adapter) — per design,
        # this fails EVERY verb including --help until the manifest is fixed.
        print(f"manifest error: {e}", file=sys.stderr)
        return 2
    except config.ConfigError as e:
        # A declaration that is present but unusable — a read mailbox on a
        # foreign domain, a malformed credential entry. Same treatment as the
        # manifest errors above and for the same reason: it is a product state
        # with an actionable fix, so it prints as ONE line. The dispatch handler
        # below cannot cover it — this failure happens before any verb exists.
        print(f"cs: {e}", file=sys.stderr)
        return 2

    p = argparse.ArgumentParser(prog=settings.prog_name or "cs")
    p.add_argument(
        "--version",
        action="version",
        version=kernel_version(),
        help="print the installed cs-kernel version and exit",
    )
    p.add_argument(
        "--account",
        help="target a configured account by name (CS_ACCOUNTS); default = CS_ENGINE_OWNER_UID. "
        "This project's accounts only — never another project's.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # --- the "human verbs" (init/update/login): registered here ONLY so
    # `cs --help` tells the truth about what exists — see the double
    # registration comment on the cmd_*_stub wrappers above. Real
    # invocations never reach these; main()'s early dispatch (top of this
    # function) has already returned by the time argparse would.
    pin = sub.add_parser(
        "init", help="interactively generate a new company clone from the templates"
    )
    pin.add_argument("init_args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    pin.set_defaults(func=cmd_init_stub)
    pup = sub.add_parser(
        "update", help="selectively merge template changes into this clone"
    )
    pup.add_argument("update_args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    pup.set_defaults(func=cmd_update_stub)
    plg = sub.add_parser(
        "login",
        help="sign in via the mrcall-desktop profile descriptor (stores the "
        "session, proves it with account.who_am_i)",
    )
    plg.add_argument(
        "--descriptor",
        metavar="PATH",
        help="use this cs-descriptor.json directly, skipping the ~/.zylch profile scan",
    )
    plg.set_defaults(func=cmd_login_stub)

    pp = sub.add_parser("plan", help="producer worklist: who to consider today")
    pp.add_argument("--period", default="7d")
    pp.add_argument("--verbose", "-v", action="store_true")
    pp.set_defaults(func=cmd_plan)

    pw = sub.add_parser("whoami", help="verify the engine session")
    pw.add_argument("--json", action="store_true",
                    help="print the raw account.who_am_i response")
    pw.set_defaults(func=cmd_whoami)

    pr = sub.add_parser("rpc", help="generic JSON-RPC call to the engine")
    pr.add_argument("method")
    pr.add_argument("params", nargs="?", help="JSON object of params")
    pr.add_argument("--timeout", type=float, default=60)
    pr.set_defaults(func=cmd_rpc)

    pt = sub.add_parser("thread", help="email threads with an address (both directions)")
    pt.add_argument("email")
    pt.add_argument("--limit", type=int, default=50)
    pt.add_argument("--json", action="store_true")
    pt.add_argument(
        "--full",
        action="store_true",
        help="with --json, resolve every thread summary to its full chronological messages",
    )
    pt.set_defaults(func=cmd_thread)

    pc = sub.add_parser(
        "contacted",
        help="the re-contact gate: did the OPERATOR mailbox write to this "
        "address in the last N days? Exit 0 = yes, 1 = no, 3 = the mailbox "
        "could not be read (which is not a no). For every mailbox, `history`.",
    )
    pc.add_argument("email")
    pc.add_argument("--days", type=int, default=30)
    # Gmail-IMAP backed: reads the operator's own Sent folder, so --account
    # cannot redirect it (see the guard in main()).
    pc.set_defaults(func=cmd_contacted, reads_operator_mailbox=True)

    pht = sub.add_parser(
        "history",
        help="has this company EVER exchanged mail with this address, from ANY "
        "mailbox it can open? Unbounded, both directions, per mailbox, and it "
        "names the mailboxes it could NOT read. Exit 0 = yes, 1 = never, "
        "3 = evidence incomplete.",
    )
    pht.add_argument("email")
    pht.add_argument(
        "--json",
        action="store_true",
        help="rows + the scope actually read + a degraded-source note",
    )
    # Reads the operator mailbox AND every account's, each with its own
    # engine-held credential — so --account can neither widen nor narrow it.
    pht.set_defaults(func=cmd_history, reads_every_mailbox=True)

    pun = sub.add_parser(
        "unanswered",
        help="inbound still awaiting a human reply (deterministic, Gmail-Sent-anchored)",
    )
    pun.add_argument("--days", type=int, default=14)
    pun.add_argument("--json", action="store_true")
    pun.add_argument(
        "--all-buckets",
        action="store_true",
        help="with --json, return open/resumed/automatic/courtesy/handled/escalated plus notes; bare --json stays the open list",
    )
    pun.add_argument(
        "--crm",
        action="store_true",
        help="group the open rows by CRM record (customers first) and show each "
        "one's CRM facts — one lookup per row through the [crm] adapter",
    )
    pun.set_defaults(func=cmd_unanswered, reads_operator_mailbox=True)

    phd = sub.add_parser(
        "handled",
        help="record that a contact was resolved OUT OF BAND (phone, WhatsApp, "
        "in person): their mail up to that moment stops being raised as open "
        "work, a later message re-opens them. Bare `handled` lists the records.",
    )
    phd.add_argument(
        "email", nargs="?", help="the contact; omit to list every record on file"
    )
    phd.add_argument(
        "--why",
        help="how/where it was resolved — printed wherever the record is surfaced",
    )
    phd.add_argument(
        "--at",
        metavar="ISO",
        help="when it was resolved (default: now). YYYY-MM-DD means the END of "
        "that day in the operator's timezone; a time may be given as "
        "YYYY-MM-DDTHH:MM",
    )
    phd.add_argument(
        "--undo",
        action="store_true",
        help="remove the record — the contact's earlier mail becomes open work "
        "again (engine tasks closed at the time stay closed)",
    )
    phd.set_defaults(func=cmd_handled)

    pes = sub.add_parser(
        "escalated",
        help="record that a HUMAN has personally taken this contact over: NOT "
        "resolved (that is `handled`) — still open and still owed an answer, but "
        "nobody else drafts, writes or delivers to them until it is released. "
        "Bare `escalated` lists who is with a human, and for how long.",
    )
    pes.add_argument(
        "email", nargs="?", help="the contact; omit to list every record on file"
    )
    pes.add_argument(
        "--why",
        help="why it was taken over, in the operator's own words — printed "
        "wherever the record is surfaced",
    )
    pes.add_argument(
        "--who",
        metavar="NAME",
        help="the human who has it (default: the operator running this, shown "
        "as 'you')",
    )
    pes.add_argument(
        "--undo",
        action="store_true",
        help="release the contact — they become ordinary open work again",
    )
    pes.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    pes.set_defaults(func=cmd_escalated)

    pk = sub.add_parser(
        "tasks",
        help="engine tasks: bare = open-task list; `create`/`close` write the ledger",
    )
    pk.add_argument("--all", action="store_true", help="include completed")
    pk.add_argument("--limit", type=int, default=200)
    pk.add_argument("--json", action="store_true")
    pk.set_defaults(func=cmd_tasks)  # bare `cs tasks` = the open-task list
    ksub = pk.add_subparsers(dest="kaction")
    kc = ksub.add_parser(
        "create",
        help="create a task the engine's detection missed (upsert on event_id — idempotent)",
    )
    kc.add_argument("--email", required=True, help="contact_email")
    kc.add_argument("--title", required=True)
    kc.add_argument("--event-id", required=True, help="idempotency key (e.g. the message-id)")
    kc.add_argument("--event-type", default="email")
    kc.add_argument("--name", help="contact_name")
    kc.add_argument("--phone", help="contact_phone")
    kc.add_argument("--urgency", default="medium")
    kc.add_argument("--reason")
    kc.add_argument("--suggested-action")
    kc.add_argument("--thread-id", help="when given, added to sources as thread_id")
    kc.add_argument("--json", action="store_true")
    kc.set_defaults(func=cmd_tasks_create)
    kx = ksub.add_parser("close", help="complete a task (tasks.complete)")
    kx.add_argument("task_id")
    kx.add_argument("--note", help="free-text closing reason (shown in the Closed view)")
    kx.add_argument("--json", action="store_true")
    kx.set_defaults(func=cmd_tasks_close)

    pb = sub.add_parser("business", help="CRM lookup by email (adapter from manifest [crm])")
    pb.add_argument("email")
    pb.set_defaults(func=cmd_business)

    pd = sub.add_parser("dossier", help="thread+contacted+tasks+CRM for one address")
    pd.add_argument("email")
    pd.add_argument("--dedup-days", type=int, default=30)
    # its `contacted` half is Gmail-IMAP backed — same constraint
    pd.set_defaults(func=cmd_dossier, reads_operator_mailbox=True)

    ph = sub.add_parser(
        "chat",
        help="one engine-chat turn (drafting surface). Destructive tools are "
        "DENIED unless explicitly --allow'ed.",
    )
    ph.add_argument("message")
    ph.add_argument(
        "--allow",
        help="comma-separated tool names to approve (e.g. send_draft) — "
        "use only after operator review",
    )
    ph.add_argument("--timeout", type=float, default=600)
    ph.set_defaults(func=cmd_chat)

    pas = sub.add_parser(
        "ask",
        help="read-only query to the engine's processed state (memory + tasks + "
        "handled-state). Use this to learn what's handled — never re-derive from raw threads.",
    )
    pas.add_argument("question")
    pas.add_argument("--timeout", type=float, default=600)
    pas.set_defaults(func=cmd_ask)

    pdr = sub.add_parser(
        "draft-reply",
        help="compose a reply via the engine as a DRAFT only — never sends (no --allow). "
        "The headless-safe reply path.",
    )
    pdr.add_argument("message")
    pdr.add_argument("--timeout", type=float, default=600)
    # APPENDS the composed draft into the operator's own Gmail Drafts
    pdr.set_defaults(func=cmd_draft_reply, reads_operator_mailbox=True)

    pdd = sub.add_parser(
        "draft-delete",
        help="remove ONE named draft from Gmail Drafts — moved to Trash "
        "(recoverable 30 days), never expunged; dry-run unless --commit",
    )
    pdd.add_argument(
        "uid",
        nargs="?",
        help="IMAP UID of the draft, as printed by `review --json` (gmail_drafts[].uid)",
    )
    pdd.add_argument(
        "--message-id",
        help="Message-ID: a cross-check on the uid when both are given, and the "
        "selector of last resort when it is given alone (drafts written by this "
        "tool carry no Message-ID)",
    )
    pdd.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    # Writes the operator's own Gmail over IMAP — --account cannot redirect it.
    pdd.set_defaults(func=cmd_draft_delete, reads_operator_mailbox=True)

    prv = sub.add_parser(
        "review",
        help="operator digest: every draft with a verdict + open tasks + "
        "campaign flags + last tick (read-only)",
    )
    prv.add_argument("--json", action="store_true")
    prv.set_defaults(func=cmd_review)

    pcu = sub.add_parser(
        "catchup",
        help="bring the engine up to date (sync.run then update.run) and print "
        "the task diff — drafts nothing, sends nothing, runs while paused",
    )
    pcu.add_argument(
        "--check",
        action="store_true",
        help="say whether the engine is behind the mailbox and exit — reads "
        "only, runs no pass, spends nothing",
    )
    pcu.add_argument("--json", action="store_true")
    # Well above the 60s default of `cs rpc`: this is a mail fetch plus the
    # engine's extraction/detection pipeline, minutes on a real mailbox, and a
    # timeout mid-pass leaves the operator unable to tell what ran.
    pcu.add_argument("--timeout", type=float, default=1800)
    # `--check` reads the operator's own Gmail over IMAP, and the pass ingests
    # into that same identity's engine profile, so --account cannot redirect
    # either half without answering about a different mailbox.
    pcu.set_defaults(func=cmd_catchup, reads_operator_mailbox=True)

    pdrv = sub.add_parser(
        "drive",
        help="read-only Google Drive (Shared Drives via the cs service-account): "
        "`drive ls [id] | cat <fileId>`",
    )
    pdrv.add_argument("drive_args", nargs=argparse.REMAINDER, help="ls [id] | cat <fileId>")
    pdrv.set_defaults(func=cmd_drive)

    pac = sub.add_parser("accounts", help="list configured multi-account names (CS_ACCOUNTS)")
    pac.set_defaults(func=cmd_accounts)

    pcf = sub.add_parser(
        "config",
        help="the settings actually in force + which file declares each one",
    )
    pcf.add_argument("--json", action="store_true", help="the report as data")
    pcf.add_argument(
        "--all",
        action="store_true",
        help="every setting, not just the ones that decide behaviour",
    )
    pcf.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when a setting is declared in more than one place",
    )
    pcf.set_defaults(func=cmd_config)

    pmm = sub.add_parser(
        "memory",
        help="where this operator's knowledge lives — the ten durable "
        "stores, their authority, and their reachability right now",
    )
    pmm.add_argument("--json", action="store_true", help="the report as data")
    pmm.set_defaults(func=cmd_memory)

    pcm = sub.add_parser("campaign", help="campaign follow-up verbs")
    csub = pcm.add_subparsers(dest="caction", required=True)
    cml = csub.add_parser("list", help="campaigns + per-state counts")
    cml.set_defaults(func=cmd_campaign_list)
    cmp_ = csub.add_parser("pending", help="per-campaign worklist (data only, sends nothing)")
    cmp_.add_argument("--name", help="restrict to one campaign name")
    cmp_.set_defaults(func=cmd_campaign_pending)
    cmr = csub.add_parser(
        "reconcile", help="mark an already-sent composed-draft contact 'sent' (Sent-archive dedup)"
    )
    cmr.add_argument("contact_id")
    cmr.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    cmr.set_defaults(func=cmd_campaign_reconcile)
    cmm = csub.add_parser("mark", help="set state / merge dossier keys on a contact")
    cmm.add_argument("contact_id")
    cmm.add_argument("--state", help=f"one of {sorted(['drafted','approved','sent','replied','bounced','skipped'])}")
    cmm.add_argument("--dossier", help="JSON dict merged into the contact dossier")
    cmm.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    cmm.set_defaults(func=cmd_campaign_mark)
    cmd_ = csub.add_parser(
        "send-draft",
        help="composed-draft outreach: CS_TRIAGE_MODE=draft → Gmail Drafts, =send → cs-SMTP; dedup-first",
    )
    cmd_.add_argument("contact_id")
    cmd_.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    cmd_.set_defaults(func=cmd_campaign_send_draft)
    cmq = csub.add_parser(
        "queue-draft",
        help="composed-draft outreach → the operator's Gmail Drafts ONLY (never sends); dedup-first",
    )
    cmq.add_argument("contact_id")
    cmq.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    cmq.set_defaults(func=cmd_campaign_queue_draft)
    csf = csub.add_parser(
        "send-first",
        help="fixed-template FIRST notice from the campaign's PACK (builders.build → HTML); "
        "CS_TRIAGE_MODE=draft → Gmail Drafts, =send → cs-SMTP; dedup/pause/rate gated",
    )
    csf.add_argument("contact_id")
    csf.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    csf.set_defaults(func=cmd_campaign_send_first)
    csr = csub.add_parser(
        "send-reminder",
        help="fixed-template reminder from the campaign's PACK (campaigns/<name>/); "
        "stamp-before-send; window/cap/reply/pause/rate gated",
    )
    csr.add_argument("contact_id")
    csr.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    csr.set_defaults(func=cmd_campaign_send_reminder)
    css = csub.add_parser(
        "send-sms",
        help="fixed-template SMS from the campaign's PACK via the [sms] proxy; "
        "stamp-before-send; same gates",
    )
    css.add_argument("contact_id")
    css.add_argument("--commit", action="store_true", help="apply (default: dry-run)")
    css.set_defaults(func=cmd_campaign_send_sms)
    cpk = csub.add_parser(
        "packs",
        help="list campaign packs (campaigns/<name>/) — reusable precedent, read-only",
    )
    cpk.add_argument("--json", action="store_true")
    cpk.set_defaults(func=cmd_campaign_packs)

    # --- llm: the kernel's own provider/model configuration ---
    pl = sub.add_parser(
        "llm",
        help="the kernel's own LLM config: what it resolves to, what else exists",
    )
    pl.set_defaults(func=cmd_llm)  # bare `cs llm` = show the current config
    lsub = pl.add_subparsers(dest="llm_action")
    lm = lsub.add_parser(
        "models",
        help="the model menu: every family, its newest member, price, what it is for",
    )
    lm.add_argument("--refresh", action="store_true",
                    help="re-fetch the catalog instead of using the cached copy")
    lm.set_defaults(func=cmd_llm)
    ls = lsub.add_parser(
        "set", help="pin a role or tier to a family (@deepseek-pro) or an exact id"
    )
    ls.add_argument("key", help="a role (classifier) or a tier (lead, worker)")
    ls.add_argument("spec", help="@<family> or an exact model id")
    ls.set_defaults(func=cmd_llm)
    lt = lsub.add_parser("test", help="one minimal round trip against the configured endpoint")
    lt.add_argument("--model", default="", help="override the model to test")
    lt.set_defaults(func=cmd_llm)

    # --- project: the written memory of one company, under docs/projects/ ---
    # A generator rather than a documented convention: the shape only stays the
    # same across clones if getting it right is the path of least effort.
    ppj = sub.add_parser("project", help="per-project written memory (docs/projects/)")
    pjsub = ppj.add_subparsers(dest="paction", required=True)
    pjn = pjsub.add_parser(
        "new", help="stamp a new project folder: index + status + timeline + meetings/"
    )
    pjn.add_argument("name", help="folder slug, lowercase-with-hyphens (e.g. acme-corp)")
    pjn.add_argument(
        "--title", help="human title for the headings (default: derived from the slug)"
    )
    pjn.set_defaults(func=project_memory_mod.cmd_project_new)

    # --- cron: manage crontab entry (requires manifest) ---
    try:
        pcr = sub.add_parser("cron", help="manage the operator crontab entry")
        crsub = pcr.add_subparsers(dest="caction", required=True)
        cri = crsub.add_parser("install", help="install/update the crontab entry from manifest [cron].schedule")
        cri.set_defaults(func=cron_mod.cmd_cron_install)
        cru = crsub.add_parser("uninstall", help="remove the crontab entry")
        cru.set_defaults(func=cron_mod.cmd_cron_uninstall)
        crs = crsub.add_parser(
            "status",
            help="is the entry installed, is the switch on, when did it last "
            "run — and, with --json, the same as data",
        )
        crs.add_argument(
            "--json",
            action="store_true",
            help="machine-readable state (installed / paused / last_tick_at / "
            "schedule / state) — what /cs-review reads",
        )
        crs.set_defaults(func=cron_mod.cmd_cron_status)
    except Exception:
        # If manifest is missing or invalid, cron commands will fail later with a clear error
        pass

    args = p.parse_args(argv)
    if getattr(args, "account", None):
        amap = settings.account_map
        uid = amap.get(args.account)
        if not uid:
            print(f"unknown --account '{args.account}'. Configured: "
                  f"{sorted(amap) or '(none — set CS_ACCOUNTS)'}", file=sys.stderr)
            return 2
        # `--account` switches the ENGINE profile and nothing else. Two families
        # of verb cannot honour it, for opposite reasons, and both used to
        # answer anyway about the wrong mailbox: `cs --account other contacted
        # <addr>` returned a confident "no" with exit 1, which reads as "never
        # contacted" and is exactly the check that gates outreach.
        #
        # These verbs speak to ONE mailbox — this clone's own — over IMAP. The
        # kernel CAN now open another account's mailbox (`cs/mailboxes.py`
        # retrieves each profile's own credential from its own engine), so the
        # ground is not "there is a single credential"; it is that the ANSWER
        # these verbs give is about the operator mailbox specifically, and
        # relabelling it as another account's would report on the wrong one.
        if uid != settings.engine_owner_uid and getattr(
            args, "reads_operator_mailbox", False
        ):
            print(
                f"`{args.cmd}` answers about {_self_label(settings)}'s own mailbox, "
                f"read over IMAP, and --account switches only the engine profile.\n"
                f"Answering anyway would report on the wrong mailbox. Ask a wider "
                f"or an engine-backed question instead:\n"
                f"  {settings.prog_name or 'cs'} history <email>"
                f"   — every mailbox this kernel can open, in one answer\n"
                f"  {settings.prog_name or 'cs'} --account {args.account} thread <email>\n"
                f"  {settings.prog_name or 'cs'} --account {args.account} ask \"<question>\"",
                file=sys.stderr,
            )
            return 2
        # And this family already reads EVERY account's mailbox, each under its
        # own profile's credential. `--account` could only change which engine
        # profile the retrieval starts from; it can neither widen nor narrow
        # the scope, and pretending it selects one would be the evidence-scope
        # knob the charter forbids.
        if uid != settings.engine_owner_uid and getattr(
            args, "reads_every_mailbox", False
        ):
            print(
                f"`{args.cmd}` already reads EVERY account in this project's "
                f"registry — the operator mailbox plus each engine profile's own "
                f"— and prints the scope it read.\n"
                f"--account switches only the engine profile, so it cannot narrow "
                f"or widen that scope. Run it without the flag; to ask about one "
                f"account's engine archive instead:\n"
                f"  {settings.prog_name or 'cs'} --account {args.account} thread <email>",
                file=sys.stderr,
            )
            return 2
        os.environ["CS_ENGINE_OWNER_UID"] = uid  # config.load() reads env first
        # `cs --account X login` must skip the operator-mailbox cross-check: a
        # deliberately selected secondary profile's mailbox is by definition not
        # the clone's own operator mailbox. Only an actual switch relaxes it —
        # `--account <the-default-account>` stays strict.
        args.account_switched = uid != (settings.engine_owner_uid or "").strip()
    try:
        return args.func(args)
    except config.ConfigError as e:
        print(f"{settings.prog_name or 'cs'}: {e}", file=sys.stderr)
        return 1
    except (ConnectionError, socket.gaierror, socket.timeout,
            websockets.exceptions.WebSocketException) as e:
        # Configuration/environment absence is a product state, not a bug: the
        # commonest cause by far is the mrcall-desktop app simply not running
        # yet, or its engine living on another machine. `websockets.connect`
        # raises ConnectionRefusedError straight out of the TCP handshake in
        # that case — a raw traceback here is the first thing a new customer
        # sees, and it reads as "the product is broken" rather than "start the
        # app".
        #
        # Catch ConnectionError, NOT OSError: FileNotFoundError and
        # PermissionError are OSError subclasses too, so the wider net would
        # announce "cannot reach the engine" for a missing file in any verb —
        # a confidently wrong diagnosis, which is worse than the traceback it
        # replaced. ConnectionError covers refused/reset/aborted connections;
        # gaierror and timeout cover an unresolvable or silent host. Anything
        # else (a real bug) still surfaces as a traceback.
        print(
            f"{settings.prog_name or 'cs'}: cannot reach the engine at "
            f"{settings.engine_ws_url!r}: {type(e).__name__}: {e}\n"
            "  The mrcall-desktop app is probably not running, or its engine "
            "is on another machine — start it there, or point [engine].ws_url "
            "in manifest.toml at the machine that is running it.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
