"""Operator review digest — what the headless operator prepared / left for you.

Read-only aggregation, run when you open a session (`cs review`):
  - DRAFTS waiting in the operator's Gmail Drafts (the queue you review + send);
  - open ENGINE TASKS needing a human answer (triage escalations live here);
  - contacts a HUMAN HAS TAKEN OVER (`cs escalated`) — still open, still owed
    an answer, but yours: shown with the age of the takeover, so the answer to
    "what is there to do" says "you are on these" instead of handing them back;
  - contacts recorded as HANDLED OUT OF BAND (`cs handled`) — why some mail
    stopped being raised, with the date and the reason;
  - per-CAMPAIGN state + contacts flagged escalated / engaged / declined;
  - the last cron tick from the log.

The headless operator only ever DRAFTS (draft-only by permission); THIS is
where you review and authorise. Mutates nothing.
"""
from __future__ import annotations

from typing import Optional

from . import _time, campaign, gmail_drafts, rpc


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

    # 2a2. Contacts a human has TAKEN OVER (`cs escalated`). Read from the
    #      ledger rather than from the mail sweep, so a takeover on a thread
    #      with no recent inbound is here too: this list is the promise that an
    #      escalation cannot rot unseen, and a list that only shows the noisy
    #      ones does not keep it. Oldest first — the top row is the one most
    #      likely to have been forgotten.
    try:
        from .state import State

        taken = State(settings.db_path).escalated_to_human()
        now = _time.now_utc()
        out["escalated"] = [
            {
                "email": e,
                "owner": r["owner"],
                "reason": r["reason"],
                "escalated_at": r["escalated_at"],
                "escalated_on": _time.local_date(r["escalated_at"], settings.timezone),
                "days": (now - r["escalated_at"]).days,
            }
            for e, r in sorted(taken.items(), key=lambda kv: kv[1]["escalated_at"])
        ]
    except Exception as e:  # noqa: BLE001
        out["escalated"] = []
        out["escalated_error"] = f"{type(e).__name__}: {e}"

    # 2b. Contacts resolved OUT OF BAND (`cs handled`) — the reason some mail
    #     is no longer raised anywhere. Shown so the operator can SEE the
    #     decision and undo it; an invisible filter is indistinguishable from a
    #     bug, and gets reported as one.
    try:
        from .state import State

        recs = State(settings.db_path).handled_out_of_band()
        out["handled_out_of_band"] = [
            {
                "email": e,
                "handled_at": r["handled_at"],
                # the operator's own calendar day: render() has no timezone,
                # and a late-evening record would print yesterday in UTC
                "handled_on": _time.local_date(r["handled_at"], settings.timezone),
                "reason": r["reason"],
            }
            for e, r in sorted(
                recs.items(), key=lambda kv: kv[1]["handled_at"], reverse=True
            )
        ]
    except Exception as e:  # noqa: BLE001
        out["handled_out_of_band"] = []
        out["handled_out_of_band_error"] = f"{type(e).__name__}: {e}"

    # 3. Campaigns + flagged contacts (escalated / outcome)
    #
    # Escalations are listed one by one; plain outcomes are COUNTED, not
    # listed. A contact flagged `engaged` is a fact about work already done,
    # and a pack mid-run produces dozens of them — thirty-one identical
    # `[engaged]` lines pushed everything else off the operator's screen and
    # bought him nothing. An escalation is the opposite: it exists because a
    # human is wanted, so it keeps its address and its reason.
    excluded = getattr(settings, "excluded_campaign_set", set()) or set()
    camps = []
    try:
        for c in campaign.list_campaigns(settings):
            contacts = rpc.call_sync(settings, "campaign.contacts", {"campaign_id": c["id"]})
            flagged = []
            outcomes: dict[str, int] = {}
            for ct in contacts:
                d = ct.get("dossier") or {}
                if d.get("escalated"):
                    flagged.append({
                        "email": ct["email"], "state": ct["state"],
                        "escalated": True,
                        "reason": d.get("escalate_reason"),
                        "outcome": d.get("outcome"),
                    })
                elif d.get("outcome"):
                    o = str(d["outcome"])
                    outcomes[o] = outcomes.get(o, 0) + 1
            camps.append({"campaign": c["name"], "counts": c.get("contacts_by_state"),
                          "flagged": flagged, "outcomes": outcomes,
                          # A campaign a dedicated process owns is still shown —
                          # hiding it would make its escalations invisible — but
                          # labelled, so nobody works it by mistake.
                          "excluded": c["name"] in excluded})
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

    # Localized digest (see the docstring): these blocks follow the surrounding
    # Italian, it is not a second language creeping into the kernel.
    #
    # Printed right after the open tasks and BEFORE the resolved ones: it is the
    # counterweight to "servono te" — the same question ("what is there to do")
    # answered with "these are already yours". Never omitted while a record
    # exists, and always with the age.
    taken = d.get("escalated", [])
    if taken:
        # "presi in carico" and a per-row name: most rows are the operator's
        # own, but one can name a colleague, and a header saying "tu" would be
        # wrong for exactly the row he did not expect to see.
        L.append(f"\nPresi in carico — aperti, ma non li lavoro io "
                 f"({len(taken)}), dal più vecchio:")
        for t in taken:
            who = t.get("owner") or "te"
            why = f"  {t.get('reason')}" if t.get("reason") else ""
            L.append(f"  - {(t.get('email') or '?'):30.30} con {who} da "
                     f"{t.get('days')}g ({t.get('escalated_on') or '?'}){why}")
        L.append("  (per rimetterne uno in lavorazione: "
                 "`cs escalated <email> --undo --commit`)")
    if d.get("escalated_error"):
        L.append(f"  ! lettura dei presi in carico fallita: {d['escalated_error']}")

    handled = d.get("handled_out_of_band", [])
    if handled:
        L.append(f"\nGestiti fuori mail — non più segnalati ({len(handled)}), "
                 f"i più recenti:")
        for h in handled[:5]:
            L.append(f"  - {(h.get('email') or '?'):30.30} {h.get('handled_on') or '?'}  "
                     f"{h.get('reason') or ''}")
        L.append("  (per rimetterne uno in lista: `cs handled <email> --undo`)")
    if d.get("handled_out_of_band_error"):
        L.append(f"  ! lettura dei gestiti fuori mail fallita: {d['handled_out_of_band_error']}")

    L.append("\nCampagne:")
    for c in d.get("campaigns", []):
        tail = "  [esclusa — la gestisce un processo dedicato]" if c.get("excluded") else ""
        outcomes = c.get("outcomes") or {}
        esiti = ("  esiti: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items()))
                 if outcomes else "")
        L.append(f"  {c['campaign']}: {c.get('counts')}{esiti}{tail}")
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
