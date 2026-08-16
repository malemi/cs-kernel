"""cs CLI — a CLI front-end to the operator mailbox's mrcall-desktop engine.

The engine daemon (zylch-server@<uid> on the host) is the body: mail
archive, entity memory, tasks, trained writing voice, draft/send. Claude
Code is the brain. These verbs are thin transport:

  plan       ingest + self-filter + suppression; who the producer suggests.
  whoami     verify the engine session (account.who_am_i).
  rpc        generic JSON-RPC call: cs rpc <method> ['{"json": "params"}'].
  thread     all email threads exchanged with one address (both directions).
  contacted  did the operator write to this address in the last N days? (dedup)
  unanswered inbound still awaiting a human reply (deterministic, Sent-anchored).
  tasks      open tasks on the engine; `tasks create` / `tasks close` write
             the engine task ledger (upsert on event_id / complete).
  business   CRM lookup by email (adapter from manifest [crm]).
  dossier    thread + contacted + tasks + CRM for one address, in one shot.
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
import socket
import sys
from collections import Counter

import websockets

from . import config, crm, ingest, rpc
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
    _print_json(rpc.call_sync(settings, "account.who_am_i"))
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
    settings = config.load()
    threads = _threads_for(settings, args.email, args.limit)
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
    settings = config.load()
    from . import gmail_archive

    msgs = gmail_archive.sent_to(settings, args.email, days=args.days)
    print(
        f"{'YES' if msgs else 'no'} — {_self_label(settings)} wrote to {args.email} "
        f"in the last {args.days} days ({len(msgs)} message(s)) [Gmail Sent, ground truth]"
    )
    for m in msgs:
        print(f"  {m['date']}: {m['subject']}")
    return 0 if msgs else 1


def cmd_unanswered(args) -> int:
    # DETERMINISTIC replacement for the flaky LLM discovery query. Enumerate
    # recent inbound (Gmail All Mail, Date-header windowed) and subtract every
    # sender we've since written to (Gmail Sent = dedup ground truth). No LLM in
    # the discovery loop — see cs/unanswered.py. Over-inclusion of an
    # autoresponder is acceptable; the skill filters with judgment downstream.
    settings = config.load()
    from . import unanswered as unanswered_mod

    rows = unanswered_mod.open_threads(settings, days=args.days)
    if args.json:
        _print_json(rows)
        return 0
    if not rows:
        print(f"no unanswered inbound in the last {args.days} days")
        return 0
    print(f"{'EMAIL':38} {'WAIT':>5}  SUBJECT")
    for r in rows:
        print(f"{r['email']:38.38} {r['days_waiting']:>4}d  {(r['subject'] or '')[:60]}")
    print(f"\ntotal: {len(rows)} unanswered (oldest first)")
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
    from . import gmail_archive

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

    recent = gmail_archive.sent_to(settings, email, days=args.dedup_days)
    print(
        f"\n-- contacted by {me} in last {args.dedup_days}d (Gmail Sent): "
        f"{'YES — do not cold-contact' if recent else 'no'} --"
    )
    for m in recent:
        print(f"  {m['date']}: {m['subject']}")

    res = rpc.call_sync(settings, "tasks.list", {"limit": 500}, timeout=120)
    rows = res if isinstance(res, list) else res.get("tasks", [])
    mine = [t for t in rows if (t.get("contact_email") or "").lower() == email.lower()]
    print(f"\n-- open engine tasks for this contact ({len(mine)}) --")
    for t in mine:
        print(f"  [{t.get('urgency')}] {(t.get('title') or t.get('summary') or '')[:80]}")

    _print_crm_section(settings, email)

    if recent:
        verdict = f"STOP — {me} already wrote within dedup window (Gmail Sent)"
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
    for p in packs:
        print(f"  {p.name:34.34} {p.kind:15.15} {p.status:8.8} "
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
        # Engine asked a clarifying question / escalated instead of composing.
        print("\n[gmail-drafts] engine composed no new draft — nothing to mirror.",
              file=sys.stderr)
        return 0
    d = max(fresh, key=lambda x: x.get("created_at") or x.get("updated_at") or "")
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
    pt.set_defaults(func=cmd_thread)

    pc = sub.add_parser("contacted", help="did the operator write to this address recently?")
    pc.add_argument("email")
    pc.add_argument("--days", type=int, default=30)
    # Gmail-IMAP backed: reads the operator's own Sent folder, so --account
    # cannot redirect it (see the guard in main()).
    pc.set_defaults(func=cmd_contacted, reads_operator_mailbox=True)

    pun = sub.add_parser(
        "unanswered",
        help="inbound still awaiting a human reply (deterministic, Gmail-Sent-anchored)",
    )
    pun.add_argument("--days", type=int, default=14)
    pun.add_argument("--json", action="store_true")
    pun.set_defaults(func=cmd_unanswered, reads_operator_mailbox=True)

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

    prv = sub.add_parser(
        "review",
        help="operator digest: drafts waiting + open tasks + campaign flags + last tick (read-only)",
    )
    prv.add_argument("--json", action="store_true")
    prv.set_defaults(func=cmd_review)

    pdrv = sub.add_parser(
        "drive",
        help="read-only Google Drive (Shared Drives via the cs service-account): "
        "`drive ls [id] | cat <fileId>`",
    )
    pdrv.add_argument("drive_args", nargs=argparse.REMAINDER, help="ls [id] | cat <fileId>")
    pdrv.set_defaults(func=cmd_drive)

    pac = sub.add_parser("accounts", help="list configured multi-account names (CS_ACCOUNTS)")
    pac.set_defaults(func=cmd_accounts)

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
        crs = crsub.add_parser("status", help="show if the cron entry is installed + manifest intent")
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
        # `--account` switches the ENGINE profile and nothing else. The Gmail
        # IMAP identity is the operator's single credential, so a verb that
        # reads or writes that mailbox cannot honour the flag — and used to
        # answer anyway, about the wrong mailbox: `cs --account other contacted
        # <addr>` returned a confident "no" with exit 1, which reads as "never
        # contacted" and is exactly the check that gates outreach. Refuse
        # instead of lying; the engine-backed verbs below do honour --account.
        if uid != settings.engine_owner_uid and getattr(
            args, "reads_operator_mailbox", False
        ):
            print(
                f"`{args.cmd}` reads {_self_label(settings)}'s own Gmail over IMAP, and "
                f"--account switches only the engine profile — there is one mail "
                f"credential, not one per account.\n"
                f"Answering anyway would report on the wrong mailbox. Use an "
                f"engine-backed verb, which does honour --account:\n"
                f"  {settings.prog_name or 'cs'} --account {args.account} thread <email>\n"
                f"  {settings.prog_name or 'cs'} --account {args.account} ask \"<question>\"",
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
