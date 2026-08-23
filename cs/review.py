"""Operator review digest — what the headless operator prepared / left for you.

Read-only aggregation, run when you open a session (`cs review`):
  - DRAFTS waiting in the operator's Gmail Drafts (the queue you review + send);
  - open ENGINE TASKS needing a human answer (triage escalations live here);
  - per-CAMPAIGN state + contacts flagged escalated / engaged / declined;
  - the last cron tick from the log.

The headless operator only ever DRAFTS (draft-only by permission); THIS is
where you review and authorise. Mutates nothing.
"""
from __future__ import annotations

from typing import Optional

from . import campaign, gmail_drafts, rpc


def _last_log_lines(settings, n: int = 6) -> list[str]:
    log = settings.log_path  # ~/.<slug>-cs/cs_operator.log (derived from Settings)
    if not log.exists():
        return []
    lines = log.read_text(errors="replace").splitlines()
    return lines[-n:]


def gather(settings) -> dict:
    out: dict = {}

    # 1a. Gmail Drafts — cs-SMTP outreach queued via `campaign queue-draft`
    #     (IMAP review surface; you review + send these). Each row carries its
    #     `uid` — the handle `draft-delete` takes to remove a bad one.
    try:
        out["gmail_drafts"] = gmail_drafts.list_drafts(settings)
    except Exception as e:  # noqa: BLE001 — a mailbox hiccup must not kill the digest
        out["gmail_drafts"] = []
        out["gmail_drafts_error"] = f"{type(e).__name__}: {e}"

    # 1b. Engine drafts — reply/compose drafts the engine composed (memory +
    #     trained voice + threading) via the chat `create_draft` tool, stored
    #     in the engine DB. Exposed by the read-only `drafts.list` RPC.
    try:
        res = rpc.call_sync(settings, "drafts.list", {}, timeout=60)
        # campaign.list/tasks.list return bare arrays; handle a wrapper too.
        out["engine_drafts"] = res if isinstance(res, list) else res.get("drafts", [])
    except Exception as e:  # noqa: BLE001
        out["engine_drafts"] = []
        out["engine_drafts_error"] = f"{type(e).__name__}: {e}"

    # 2. Open engine tasks (triage escalations + general inbound needing a human)
    try:
        res = rpc.call_sync(settings, "tasks.list", {"limit": 200}, timeout=120)
        tasks = res if isinstance(res, list) else res.get("tasks", [])
        out["tasks"] = [
            {"email": t.get("contact_email") or t.get("contact_phone"),
             "title": (t.get("title") or t.get("summary") or "")[:90],
             "urgency": t.get("urgency")}
            for t in tasks
        ]
    except Exception as e:  # noqa: BLE001
        out["tasks"] = []
        out["tasks_error"] = f"{type(e).__name__}: {e}"

    # 3. Campaigns + flagged contacts (escalated / outcome)
    camps = []
    try:
        for c in campaign.list_campaigns(settings):
            contacts = rpc.call_sync(settings, "campaign.contacts", {"campaign_id": c["id"]})
            flagged = []
            for ct in contacts:
                d = ct.get("dossier") or {}
                if d.get("escalated") or d.get("outcome"):
                    flagged.append({
                        "email": ct["email"], "state": ct["state"],
                        "escalated": bool(d.get("escalated")),
                        "reason": d.get("escalate_reason"),
                        "outcome": d.get("outcome"),
                    })
            camps.append({"campaign": c["name"], "counts": c.get("contacts_by_state"),
                          "flagged": flagged})
    except Exception as e:  # noqa: BLE001
        out["campaigns_error"] = f"{type(e).__name__}: {e}"
    out["campaigns"] = camps

    # 4. Last cron tick
    out["last_tick"] = _last_log_lines(settings)
    return out


def render(d: dict) -> str:
    """Human digest (Italian, founders' register). Skimmable; the numbers are
    the point, not prose."""
    L = []
    gdrafts = d.get("gmail_drafts", [])
    L.append(f"Bozze outreach in Gmail Drafts (cs-SMTP, da rivedere + inviare): {len(gdrafts)}")
    for dr in gdrafts:
        # uid first: it is what `draft-delete <uid>` takes, and a draft the
        # operator wants gone is unnameable without it.
        L.append(f"  - [uid {(dr.get('uid') or '?'):>6.6}] "
                 f"{(dr.get('to') or '?'):32.32} {(dr.get('subject') or '(no subj)')[:60]}")
    if d.get("gmail_drafts_error"):
        L.append(f"  ! lettura Gmail Drafts fallita: {d['gmail_drafts_error']}")

    edrafts = d.get("engine_drafts", [])
    L.append(f"\nBozze engine (risposta/compose, store engine + desktop app): {len(edrafts)}")
    for dr in edrafts:
        to = (dr.get("to_addresses") or [])
        to = to[0] if to else "?"
        kind = "reply" if (dr.get("in_reply_to") or dr.get("thread_id")) else "compose"
        L.append(f"  - [{kind:7.7}] {to:32.32} {(dr.get('subject') or '(no subj)')[:55]}")
    if d.get("engine_drafts_error"):
        L.append(f"  ! drafts.list fallita: {d['engine_drafts_error']}")

    tasks = d.get("tasks", [])
    L.append(f"\nTask engine aperti (servono te): {len(tasks)}")
    for t in tasks:
        L.append(f"  - [{(t.get('urgency') or '?'):6.6}] {(t.get('email') or '?'):28.28} {t.get('title') or ''}")
    if d.get("tasks_error"):
        L.append(f"  ! tasks.list fallita: {d['tasks_error']}")

    L.append("\nCampagne:")
    for c in d.get("campaigns", []):
        L.append(f"  {c['campaign']}: {c.get('counts')}")
        for f in c.get("flagged", []):
            tag = "ESCALATION" if f.get("escalated") else (f.get("outcome") or "?")
            L.append(f"    · {f['email']:30.30} [{tag}] {f.get('reason') or ''}")
    if d.get("campaigns_error"):
        L.append(f"  ! campagne fallite: {d['campaigns_error']}")

    tick = d.get("last_tick", [])
    if tick:
        L.append("\nUltimo tick:")
        for ln in tick:
            L.append(f"  {ln}")
    return "\n".join(L)
