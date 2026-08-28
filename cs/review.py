"""Operator review digest — what the headless operator prepared / left for you.

Read-only aggregation, run when you open a session (`cs review`):
  - DRAFTS, each with a VERDICT computed at read time (`cs/draft_state.py`):
    `ready`, or one of `overtaken` / `superseded` / `settled`, which mean the
    conversation moved on and the draft has to be re-decided before it is sent.
    Both stores are reconciled into one list, so the two copies of a mirrored
    draft are one row carrying both handles;
  - the same drafts as the two RAW store listings (the queue you review + send);
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

from . import _time, campaign, draft_state, gmail_drafts, rpc


def _task_row(task: dict) -> dict:
    """One engine task as review evidence, without throwing context away.

    ``render`` only needs email/title/urgency, but ``review --json`` is also the
    headless operator's evidence feed. The previous three-field projection
    discarded the task id, the detector's reason, its proposed action, source
    conversation, and timestamps — precisely what a current-attention
    judgement needs in order to disagree with a stale ledger item honestly.

    Keep the engine fields intact and add the two normalized display aliases.
    This is read-only data shaping; no task state is changed.
    """
    row = dict(task)
    row["email"] = task.get("contact_email") or task.get("contact_phone")
    row["title"] = (task.get("title") or task.get("summary") or "")[:90]
    return row


def _last_log_lines(settings, n: int = 6) -> list[str]:
    log = settings.log_path  # ~/.<slug>-cs/cs_operator.log (derived from Settings)
    if not log.exists():
        return []
    lines = log.read_text(errors="replace").splitlines()
    return lines[-n:]


def engine_freshness(settings, days: int = 3) -> dict:
    """Has the newest mail in the mailbox reached the engine yet?

    Everything the engine owns — the task ledger, entity memory, the
    `needs_reply` verdict — is only as fresh as its last pass, and the engine
    exposes neither the timestamp of that pass nor the interval it is
    configured for. What it does answer is whether it holds a given
    conversation, so freshness is measured directly instead of inferred from a
    clock: take the newest inbound Gmail has (`gmail_archive.inbound_recent`,
    the same Date-header-windowed read the sweep uses), and ask the engine for
    that conversation (`emails.list_by_thread`, keyed by the RFC-5322 thread
    key both sides already agree on). A message the engine cannot show is a
    message it has not ingested, and `cs catchup` is what fixes that.

    The join is by whole-second UTC timestamp — the engine returns its own
    UUIDs, never the `Message-ID` header — which is the convention
    `cs/engine_view.py` already uses for the same reason.

    Returns `{stale, reason, newest_inbound_at, newest_subject, note}`.
    `stale` is False whenever the question cannot be answered (no recent
    inbound, an engine that will not talk, an unthreadable message): the only
    thing `stale` triggers is an offer to spend real LLM budget, so an
    unanswerable question must never produce one.
    """
    from datetime import timezone

    from . import gmail_archive

    out = {"stale": False, "reason": "", "newest_inbound_at": None,
           "newest_subject": None, "note": None}
    try:
        recent = gmail_archive.inbound_recent(settings, days=days)
    except Exception as e:  # noqa: BLE001 — a mailbox hiccup is never an offer
        out["note"] = f"could not read the mailbox: {type(e).__name__}: {e}"
        return out
    if not recent:
        out["reason"] = f"no inbound mail in the last {days} day(s) to ingest"
        return out

    newest = max(recent, key=lambda m: m["date"])
    out["newest_inbound_at"] = newest["date"].isoformat()
    out["newest_subject"] = newest.get("subject") or ""
    key = newest.get("thread_key")
    if not key:
        out["reason"] = "the newest message carries no usable thread key"
        return out

    try:
        res = rpc.call_sync(settings, "emails.list_by_thread", {"thread_id": key},
                            timeout=60)
    except Exception as e:  # noqa: BLE001
        out["note"] = f"could not ask the engine: {type(e).__name__}: {e}"
        return out

    from .engine_view import _parse as _parse_engine_date

    want = int(newest["date"].astimezone(timezone.utc).timestamp())
    seen = set()
    for m in ((res or {}).get("emails") or []):
        when = _parse_engine_date(m.get("date"))
        if when is not None:
            seen.add(int(when.timestamp()))
    if want in seen:
        out["reason"] = "the engine holds the newest message in the mailbox"
        return out
    out["stale"] = True
    out["reason"] = (f"the newest message in the mailbox "
                     f"({out['newest_inbound_at']}) has not reached the engine")
    return out


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

    # 1c. The two stores reconciled into ONE list, every row carrying a verdict
    #     computed from Gmail (and, when the engine answers, its reading of the
    #     conversation). This is what makes the digest say "this draft answers a
    #     question the customer has already withdrawn" instead of listing it as
    #     ready. Never raises: a mailbox hiccup is a note, and the raw listings
    #     above are still there.
    try:
        rows, notes = draft_state.reconcile(
            settings, out["gmail_drafts"], out["engine_drafts"]
        )
        out["drafts"] = rows
        out["drafts_notes"] = notes
    except Exception as e:  # noqa: BLE001
        out["drafts"] = []
        out["drafts_notes"] = [f"{type(e).__name__}: {e}"]

    # 2. Open engine tasks (triage escalations + general inbound needing a human)
    try:
        res = rpc.call_sync(settings, "tasks.list", {"limit": 200}, timeout=120)
        tasks = res if isinstance(res, list) else res.get("tasks", [])
        out["tasks"] = [_task_row(t) for t in tasks]
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


def _handles(row: dict) -> str:
    """Both handles of one logical draft, in the form the operator retires it
    by. A row with two copies needs both; a count needs neither, which is why
    neither is ever collapsed into one."""
    parts = []
    if row.get("gmail_uid"):
        parts.append(f"uid {row['gmail_uid']}")
    if row.get("engine_id"):
        parts.append(f"engine {str(row['engine_id'])[:8]}")
    return ", ".join(parts) or "no handle"


def render(d: dict) -> str:
    """Human digest — English, like every other line of kernel code.

    The clone's own voice is a STAMPED-SURFACE property (`operator_voice` in
    its `manifest.toml`), and it applies to what the agent writes to the
    operator, never to what a kernel verb prints. Skimmable; the numbers are the
    point, not prose."""
    L = []
    rows = d.get("drafts", [])
    ready, re_decide = draft_state.split(rows)

    L.append(f"Drafts ready to send ({len(ready)}) — you review and send:")
    for r in ready:
        L.append(f"  - [{_handles(r)}] {(r.get('to') or '?'):32.32} "
                 f"{(r.get('subject') or '(no subject)')[:60]}")
    L.append(f"\nDrafts to re-decide ({len(re_decide)}) — the conversation "
             f"moved on since they were written:")
    for r in re_decide:
        L.append(f"  - [{_handles(r)}] {(r.get('to') or '?'):32.32} "
                 f"{(r.get('subject') or '(no subject)')[:50]}")
        L.append(f"      {r.get('verdict')}: {r.get('signal') or '?'}"
                 f"{'  (' + r['signal_at'] + ')' if r.get('signal_at') else ''}")
    for note in d.get("drafts_notes") or []:
        L.append(f"  ! {note}")
    L.append(f"  (stores: {len(d.get('gmail_drafts', []))} in Gmail Drafts, "
             f"{len(d.get('engine_drafts', []))} in the engine)")
    if d.get("gmail_drafts_error"):
        L.append(f"  ! reading Gmail Drafts failed: {d['gmail_drafts_error']}")
    if d.get("engine_drafts_error"):
        L.append(f"  ! drafts.list failed: {d['engine_drafts_error']}")

    tasks = d.get("tasks", [])
    L.append(f"\nOpen engine tasks ({len(tasks)}) — these need you:")
    for t in tasks:
        L.append(f"  - [{(t.get('urgency') or '?'):6.6}] {(t.get('email') or '?'):28.28} {t.get('title') or ''}")
    if d.get("tasks_error"):
        L.append(f"  ! tasks.list failed: {d['tasks_error']}")

    # Printed right after the open tasks and BEFORE the resolved ones: it is the
    # counterweight to "these need you" — the same question ("what is there to
    # do") answered with "these are already yours". Never omitted while a record
    # exists, and always with the age.
    taken = d.get("escalated", [])
    if taken:
        # A per-row name: most rows are the operator's own, but one can name a
        # colleague, and a header saying "you" would be wrong for exactly the
        # row he did not expect to see.
        L.append(f"\nTaken over by a human — open, but not ours to answer "
                 f"({len(taken)}), oldest first:")
        for t in taken:
            who = t.get("owner") or "you"
            why = f"  {t.get('reason')}" if t.get("reason") else ""
            L.append(f"  - {(t.get('email') or '?'):30.30} with {who} for "
                     f"{t.get('days')}d ({t.get('escalated_on') or '?'}){why}")
        L.append("  (to put one back in the queue: "
                 "`cs escalated <email> --undo --commit`)")
    if d.get("escalated_error"):
        L.append(f"  ! reading the taken-over records failed: {d['escalated_error']}")

    handled = d.get("handled_out_of_band", [])
    if handled:
        L.append(f"\nResolved out of band — no longer raised ({len(handled)}), "
                 f"most recent first:")
        for h in handled[:5]:
            L.append(f"  - {(h.get('email') or '?'):30.30} {h.get('handled_on') or '?'}  "
                     f"{h.get('reason') or ''}")
        L.append("  (to put one back on the list: `cs handled <email> --undo`)")
    if d.get("handled_out_of_band_error"):
        L.append(f"  ! reading the out-of-band records failed: "
                 f"{d['handled_out_of_band_error']}")

    L.append("\nCampaigns:")
    for c in d.get("campaigns", []):
        tail = "  [excluded — a dedicated process owns it]" if c.get("excluded") else ""
        outcomes = c.get("outcomes") or {}
        results = ("  outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items()))
                   if outcomes else "")
        L.append(f"  {c['campaign']}: {c.get('counts')}{results}{tail}")
        for f in c.get("flagged", []):
            tag = "ESCALATION" if f.get("escalated") else (f.get("outcome") or "?")
            L.append(f"    · {f['email']:30.30} [{tag}] {f.get('reason') or ''}")
    if d.get("campaigns_error"):
        L.append(f"  ! reading the campaigns failed: {d['campaigns_error']}")

    tick = d.get("last_tick", [])
    if tick:
        L.append("\nLast scheduled run:")
        for ln in tick:
            L.append(f"  {ln}")
    return "\n".join(L)
