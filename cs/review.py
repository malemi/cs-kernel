"""Operator review digest — what the headless operator prepared / left for you.

Read-only aggregation, run when you open a session (`cs review`):
  - DRAFTS, each with a VERDICT computed at read time (`cs/draft_state.py`):
    `ready`, or one of `duplicate` / `overtaken` / `superseded` / `settled`,
    which mean the draft has to be re-decided before it is sent — `duplicate`
    because the customer already has that exact text, the other three because
    the conversation moved on.
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

from . import observability
from contextlib import nullcontext

import sys
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
from contextvars import ContextVar
from pathlib import Path
import time
from contextlib import contextmanager
from typing import Optional

from . import _time, campaign, draft_state, engine_view, gmail_drafts, rpc

# Two calls inside `gather()` are excluded, on purpose, from the 90s wall M3
# owns (see `docs/execution-plans/2026-09-07-review-latency.md` § Verification
# of the whole): `campaign.contacts`, looped once per campaign with a fresh
# connect/disconnect per call (`cs/rpc.py:226-230`), and `engine_view.settled`,
# whose own docstring admits the engine may make a model call to answer it.
# Both used to run under whatever default happened to sit on the callee —
# `rpc.call_sync`'s unstated 60s, `engine_view.settled`'s own 120s — which is
# invisible until one of those defaults changes. Naming them here does not
# shrink either budget (that is M2/M3's job, not this one); it pins today's
# effective values so a slow engine degrades with a clear line instead of
# looking exactly like the 25-minute run this fix was written from.
CAMPAIGN_CONTACTS_TIMEOUT_SECONDS = 60
ENGINE_SETTLED_TIMEOUT_SECONDS = 120
TOTAL_SECONDS = 2715
WORK_SECONDS = 2700
CLEANUP_SECONDS = 10
MAX_CHECKPOINT_BYTES = 32 * 1024 * 1024
_CONTEXT = ContextVar("review_context", default=None)


def _remaining(normal):
    context = _CONTEXT.get()
    if context is None or context["deadline"] is None:
        return normal
    remaining = context["deadline"] - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("review work deadline exhausted")
    return min(normal, remaining)


def _checkpoint(phase):
    context = _CONTEXT.get()
    if context is not None:
        context["phase"] = phase
        context["checkpoint"](context["out"], phase)


def _progress(msg: str) -> None:
    """One line of `gather()` progress. Stderr only, and flushed immediately.

    `cs review --json` stdout is parsed (the cron's own bootstrap step 4c), so
    it has to stay exactly what it always printed — nothing in this module
    ever reaches stdout through here. The incident this exists for: the
    operator watched `cs review` emit zero bytes for fourteen minutes and
    could not tell a slow run from a hang; an instrumented run later showed it
    still going past 25 minutes.
    """
    print(f"[review] {msg}", file=sys.stderr, flush=True)


@contextmanager
def _stage(name: str):
    """Bracket one `gather()` stage with a start line and a timed end line.

    A stage that raises is timed too, and marked FAILED rather than done: how
    long the thing that broke took is exactly what tells a slow engine apart
    from one that never answers at all. Every caller inside `gather()` still
    catches its own exception right after — this only adds the stderr trail
    around that existing degradation, it changes no return value.
    """
    context = _CONTEXT.get()
    stages = context.setdefault("stages", []) if context is not None else []
    stages.append(name)
    try:
        _checkpoint(name)
        _remaining(TOTAL_SECONDS)
        _progress(f"{name}: starting")
        t0 = time.monotonic()
        try:
            yield
        except Exception:
            _progress(f"{name}: FAILED ({time.monotonic() - t0:.1f}s)")
            raise
        else:
            _progress(f"{name}: done ({time.monotonic() - t0:.1f}s)")
            _checkpoint(name)
    finally:
        stages.pop()
        if stages:
            _checkpoint(stages[-1])


def _settled_with_timeout(settings, thread_ids):
    """`draft_state.reconcile`'s injectable `settled` seam, given an explicit
    timeout and its own line on the progress trail.

    `reconcile` calls its `settled` argument with no timeout of its own
    (`cs/draft_state.py:324`), so left at its default this silently inherits
    whatever `engine_view.settled` happens to declare. Worth naming: its own
    docstring admits the engine may make a model call to answer
    (`cs/engine_view.py:164-168`), which makes it the one RPC in `gather()`
    least safe to assume is fast.
    """
    with _stage("engine_view.settled"):
        try:
            return engine_view.settled(settings, thread_ids,
                                       timeout=_remaining(ENGINE_SETTLED_TIMEOUT_SECONDS))
        except TimeoutError as e:
            # `reconcile` turns whatever this raises into a note via
            # `f"{type(e).__name__}: {e}"` (`cs/draft_state.py:326`), and a
            # bare `asyncio.TimeoutError` stringifies to "" — name the bound
            # so the note says something instead of just its own class.
            raise TimeoutError(
                f"engine_view.settled exceeded {ENGINE_SETTLED_TIMEOUT_SECONDS}s"
            ) from e


def _campaign_contacts(settings, camp: dict) -> list:
    """One `campaign.contacts` call, explicitly timed and bounded.

    Looped once per campaign (`gather`'s § 3), each call a fresh
    `asyncio.run` plus connect/disconnect (`cs/rpc.py:226-230`) — the same
    invisible-hang shape as `engine_view.settled` above, multiplied by however
    many campaigns are configured, and previously with no timeout of its own
    before `rpc.call_sync`'s unstated 60s default.
    """
    with _stage(f"campaign.contacts {camp['name']}"):
        try:
            return rpc.call_sync(settings, "campaign.contacts",
                                 {"campaign_id": camp["id"]},
                                 timeout=_remaining(CAMPAIGN_CONTACTS_TIMEOUT_SECONDS))
        except TimeoutError as e:
            raise TimeoutError(
                f"campaign.contacts for {camp['name']!r} exceeded "
                f"{CAMPAIGN_CONTACTS_TIMEOUT_SECONDS}s"
            ) from e


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


def _record_roots(out, roots, source):
    sources = out.setdefault("_root_sources", {})
    for root in roots:
        if root:
            categories = sources.setdefault(root, [])
            if source not in categories:
                categories.append(source)
    out["_known_roots"] = list(dict.fromkeys(out.get("_known_roots", []) + list(sources)))


def _root_coverage(out, *, owner_uid=None):
    from . import task_assignment
    completed = out.get("_completed_projections", {})
    order = list(dict.fromkeys(out.get("_projection_order", []) + out.get("_known_roots", [])))
    return {"requested_order": out.get("_projection_order", []), "roots": [
        {"thread_key": root, "sources": out.get("_root_sources", {}).get(root, []),
         "projection": completed.get(root, task_assignment._unknown(root, "review projection unavailable", owner_uid=owner_uid))}
        for root in order]}


def _aggregate(settings, *, deadline=None, owned_process_group=None, checkpoint=lambda out, phase: None) -> dict:
    out: dict = {"review_coverage": {"assignment_listing": "unknown", "mailbox_discovery": "unknown"}}
    token = _CONTEXT.set({"deadline": deadline, "out": out, "checkpoint": checkpoint})
    try:
        return _gather(settings, out, deadline, owned_process_group)
    finally:
        _CONTEXT.reset(token)


def _gather(settings, out, deadline, owned_process_group) -> dict:

    # 1a. Gmail Drafts — cs-SMTP outreach queued via `campaign queue-draft`
    #     (IMAP review surface; you review + send these). Each row carries its
    #     `uid` — the handle `draft-delete` takes to remove a bad one.
    with _stage("Gmail draft listing"):
        try:
            out["gmail_drafts_observation"] = {}
            out["gmail_drafts"] = gmail_drafts.list_drafts(settings, observation=out["gmail_drafts_observation"])
            _record_roots(out, [root for row in out["gmail_drafts"]
                if (root := draft_state._gmail_row(row)["thread_key"])], "gmail_draft")
        except Exception as e:  # noqa: BLE001 — a mailbox hiccup must not kill the digest
            out["gmail_drafts"] = []
            out["gmail_drafts_error"] = f"{type(e).__name__}: {e}"

    # 1b. Engine drafts — reply/compose drafts the engine composed (memory +
    #     trained voice + threading) via the chat `create_draft` tool, stored
    #     in the engine DB. Exposed by the read-only `drafts.list` RPC.
    with _stage("engine drafts.list"):
        try:
            res = rpc.call_sync(settings, "drafts.list", {}, timeout=_remaining(60))
            # campaign.list/tasks.list return bare arrays; handle a wrapper too.
            if isinstance(res, list):
                drafts = res
            elif isinstance(res, dict) and set(res) == {"drafts"} and isinstance(res["drafts"], list):
                drafts = res["drafts"]
            else:
                raise ValueError("drafts.list inventory shape is incomplete or unknown")
            if any(not isinstance(row, dict) for row in drafts):
                raise ValueError("drafts.list contains malformed rows")
            out["engine_drafts"] = drafts
            _record_roots(out, [root for row in drafts
                if (root := draft_state._engine_row(row)["thread_key"])], "engine_draft")
        except Exception as e:  # noqa: BLE001
            out["engine_drafts"] = []
            out["engine_drafts_error"] = f"{type(e).__name__}: {e}"

    # 1c. The two stores reconciled into ONE list, every row carrying a verdict
    #     computed from Gmail (and, when the engine answers, its reading of the
    #     conversation). This is what makes the digest say "this draft answers a
    #     question the customer has already withdrawn" instead of listing it as
    #     ready. Never raises: a mailbox hiccup is a note, and the raw listings
    #     above are still there.
    with _stage("draft reconcile"):
        try:
            rows, notes = draft_state.reconcile(
                settings, out["gmail_drafts"], out["engine_drafts"],
                settled=_settled_with_timeout,
            )
            out["drafts"] = rows
            out["drafts_notes"] = notes
        except Exception as e:  # noqa: BLE001
            out["drafts"] = []
            out["drafts_notes"] = [f"{type(e).__name__}: {e}"]
            out["drafts_reconcile_error"] = True

    out["drafts_inventory"] = draft_state.inventory_proof(
        out["gmail_drafts"], out["engine_drafts"], out["drafts"],
        out.get("gmail_drafts_observation"))
    if out.get("gmail_drafts_error") or out.get("engine_drafts_error") or out.get("drafts_reconcile_error"):
        out["drafts_inventory"]["complete"] = False

    # 2. Open engine tasks (triage escalations + general inbound needing a human)
    with _stage("tasks.list"):
        try:
            res = rpc.call_sync(settings, "tasks.list", {"limit": 200}, timeout=_remaining(120))
            tasks = res if isinstance(res, list) else res.get("tasks", [])
            out["tasks"] = [_task_row(t) for t in tasks]
            _record_roots(out, [root for t in tasks if (root := t.get("thread_key") or t.get("thread_id")
                    or (t.get("sources") or {}).get("thread_id"))], "task")
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
    with _stage("per-campaign loop"):
        try:
            for c in campaign.list_campaigns(settings):
                contacts = _campaign_contacts(settings, c)
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

    from . import task_assignment
    listed_roots = []
    observed_roots = out.get("_known_roots", [])
    try:
        with _stage("assignment listing"):
            assignments = task_assignment.listing(settings, **({"deadline": deadline} if deadline is not None else {}))
            listed_roots = [row["thread_key"] for row in assignments["items"]]
            _record_roots(out, listed_roots, "company_assignment")
            out["review_coverage"] = {"assignment_listing": "complete", "mailbox_discovery": "unknown"}
    except Exception as exc:
        out["assignments"] = []
        out["assignments_error"] = f"Assignment authority UNKNOWN ({type(exc).__name__}); no absence established"

    from . import unanswered
    try:
        def discovered(phase, roots):
            if phase == "inbound projection roots":
                out["_projection_order"] = list(roots)
            else:
                _record_roots(out, roots, "inbound")
            _checkpoint(phase)
        def projected(projections):
            out["_completed_projections"] = projections
            out["assignments"] = [task_assignment.provenance(projections.get(root, task_assignment._unknown(root, "review projection unavailable", owner_uid=getattr(settings, "engine_owner_uid", None))), None) for root in listed_roots]
            _checkpoint("inbound assignment projection")
        sweep = unanswered.sweep(settings, days=14, deadline=deadline, owned_process_group=owned_process_group,
                                 progress=discovered, listed_roots=observed_roots + listed_roots, projection_observer=projected)
        out.setdefault("review_coverage", {})["mailbox_discovery"] = "incomplete" if sweep.get("read_incomplete") else "complete"
        out["human_work"] = sweep.get("human_work", [])
        out["assignment_audit"] = sweep.get("assignment_audit", [])
        if sweep.get("assignment_incomplete"):
            out["assignments_error"] = "Assignment authority UNKNOWN in current thread scope; held work stays visible"
    except Exception as exc:
        out["human_work"] = []
        out["assignments_error"] = f"Current assignment work UNKNOWN ({type(exc).__name__}); no absence established"
        _incomplete(out, "current assignment discovery interrupted", owner_uid=getattr(settings, "engine_owner_uid", None))

    # 4. Last cron tick
    out["last_tick"] = _last_log_lines(settings)
    out.setdefault("review_coverage", {}).setdefault("aggregation", "complete")
    _checkpoint("complete")
    return out


def _handles(row: dict) -> str:
    """Both handles of one logical draft, in the form the operator retires it
    by. A row with two copies needs both; a count needs neither, which is why
    neither is ever collapsed into one."""
    parts = []
    if row.get("gmail_uid"):
        parts.append(f"uid {row['gmail_uid']}")
    if row.get("engine_id"):
        parts.append(f"engine {row['engine_id']}")
    if row.get("identity_evidence"):
        parts.append(row["identity_evidence"])
    if row.get("identity_conflict"):
        parts.append("identity conflict")
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
        # INLINE, under the row it qualifies. `ready` means "nothing overtook
        # this draft", and when a mailbox could not be read that is an absence
        # nobody established — the operator is about to press send on this
        # line, so it cannot live in a footer below the next block.
        for gap in r.get("evidence_incomplete") or []:
            L.append(f"      ! ready on INCOMPLETE evidence — {gap}")
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

    from . import task_assignment
    L.append("\nEngine thread assignments / closed audit:")
    rendered_threads = set()
    escalation_records = {item["email"]: item for item in d.get("escalated", [])}
    for item in d.get("human_work", []):
        detail = task_assignment.render(item["assignment"])
        escalation = escalation_records.get(item["email"])
        if escalation and any(origin["basis"] == "address_escalation" for origin in item["assignment"].get("provenance", [])):
            detail += (f"; with {escalation.get('owner') or 'you'} for {escalation.get('days')}d "
                       f"({escalation.get('escalated_on') or '?'}); release: `cs escalated <email> --undo --commit`")
        L.append("  " + item["email"] + ": " + detail)
        rendered_threads.add(item["thread_key"])
    for item in d.get("assignments", []):
        if item["thread_key"] not in rendered_threads:
            L.append("  " + task_assignment.render(item))
    if d.get("assignments_error"):
        L.append("  " + d["assignments_error"])
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
    surfaced = {item["email"] for item in d.get("human_work", [])
                if any(origin["basis"] == "address_escalation" for origin in item["assignment"].get("provenance", []))}
    taken = [item for item in d.get("escalated", []) if item["email"] not in surfaced]
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
        L.append(f"\nLocal out-of-band records — engine closure requires acknowledgement ({len(handled)}), "
                 f"most recent first:")
        held_addresses = {item["email"] for item in d.get("human_work", []) if item["assignment"]["hold_auto_reply"]}
        for h in handled[:5]:
            L.append(f"  - {(h.get('email') or '?'):30.30} {h.get('handled_on') or '?'}  "
                     f"{h.get('reason') or ''}")
            if h.get("email") in held_addresses:
                L.append("      engine assignment remains HELD / unconfirmed; local record does not settle it")
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

def _save_checkpoint(path, value):
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    if len(raw) > MAX_CHECKPOINT_BYTES:
        raise ValueError("review checkpoint capacity exceeded")
    fd, name = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _read_checkpoint(path, binding):
    from .operator_health import private
    private(path)
    if path.stat().st_size > MAX_CHECKPOINT_BYTES:
        raise ValueError("review checkpoint capacity exceeded")
    record = json.loads(path.read_bytes())
    if (record.get("binding") != binding or not isinstance(record.get("out"), dict)
            or not isinstance(record.get("phase"), str) or type(record.get("complete")) is not bool):
        raise ValueError("review checkpoint binding invalid")
    return record


def _incomplete(out, reason, *, cleanup_complete=True, owner_uid=None):
    from . import task_assignment
    out.setdefault("gmail_drafts", [])
    out.setdefault("engine_drafts", [])
    out.setdefault("drafts", [])
    if not cleanup_complete or "drafts_inventory" not in out:
        out["drafts_inventory"] = {"version": 1, "complete": False}
        out["drafts_reconcile_error"] = True
        for row in out["drafts"]:
            row.setdefault("workset_hold_reasons", []).append("mailbox_unreadable")
    out["review_incomplete"] = reason
    out["assignments_error"] = "Review interrupted; undiscovered coverage UNKNOWN; no absence established"
    out.setdefault("review_coverage", {}).update(aggregation="incomplete", cleanup_complete=cleanup_complete)
    existing = {row["thread_key"] for row in out.get("assignments", [])}
    out.setdefault("assignments", []).extend(task_assignment.provenance(out.get("_completed_projections", {}).get(root, task_assignment._unknown(root, reason, owner_uid=owner_uid)))
        for root in out.get("_known_roots", []) if root not in existing)
    return out


def _public(out, *, owner_uid=None):
    public = {key: value for key, value in out.items() if not key.startswith("_")}
    public["assignment_coverage"] = _root_coverage(out, owner_uid=owner_uid)
    return public


def _supervise(settings, *, worker_command=None, total_seconds=TOTAL_SECONDS,
               work_seconds=WORK_SECONDS, cleanup_seconds=CLEANUP_SECONDS):
    from .operator_health import identity
    from .operator_dossier import _stop
    started = time.monotonic()
    if not 0 < work_seconds < work_seconds + cleanup_seconds < total_seconds:
        raise ValueError("invalid review lifecycle")
    work_deadline = started + work_seconds
    cleanup_deadline = work_deadline + cleanup_seconds
    configuration = settings.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    binding = {"attempt": secrets.token_hex(32), "owner_uid": settings.engine_owner_uid,
               "configuration_sha256": digest}
    out = {}
    phase = "setup"
    complete = False
    clean = False
    proc = None
    stamp = None
    with tempfile.TemporaryDirectory(prefix="cs-review-") as directory:
        path = Path(directory) / "checkpoint.json"
        try:
            command = worker_command or (sys.executable, "-B", "-m", "cs.review", "--worker")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       CS_DIAGNOSTIC_CONTEXT=json.dumps(observability.current_context()))
            with tempfile.TemporaryFile() as stdout:
                proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout,
                                        stderr=None, start_new_session=True, env=env)
                stamp, _ = identity(proc.pid)
                binding["worker"] = stamp
                payload = {"settings": configuration, "binding": binding, "path": str(path),
                           "deadline": work_deadline}
                try:
                    proc.communicate(json.dumps(payload).encode(), timeout=max(.001, work_deadline-time.monotonic()))
                except subprocess.TimeoutExpired:
                    pass
                finally:
                    clean = _stop(proc, stamp, cleanup_deadline)
            record = _read_checkpoint(path, binding)
            out, phase = record["out"], record["phase"]
            complete = record["complete"] and proc.returncode == 0 and clean
        except Exception:
            if proc is not None and proc.poll() is None:
                clean = _stop(proc, stamp, cleanup_deadline)
        if not complete:
            _progress(f"{phase}: incomplete (deadline, worker or checkpoint failure); cleanup {'complete' if clean else 'incomplete'}")
            out = _incomplete(out, "review deadline or worker failure during " + phase, cleanup_complete=clean, owner_uid=getattr(settings, "engine_owner_uid", None))
        return _public(out, owner_uid=getattr(settings, "engine_owner_uid", None))


def gather(settings) -> dict:
    return _supervise(settings)


def _worker(payload):
    from .config import Settings
    from .operator_health import identity
    settings = Settings.model_validate(payload["settings"])
    binding = payload["binding"]
    digest = hashlib.sha256(json.dumps(settings.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    path = Path(payload["path"])
    if (binding["worker"] != identity(os.getpid())[0] or os.getpgrp() != os.getpid()
            or binding["owner_uid"] != settings.engine_owner_uid
            or binding["configuration_sha256"] != digest or path.parent.resolve() != path.parent):
        raise ValueError("review worker identity changed")
    def checkpoint(out, phase):
        _save_checkpoint(path, {"binding": binding, "out": out, "phase": phase, "complete": False})
    from .observability_producers import inherited_context
    metadata = inherited_context()
    diagnostic = {key: value for key in ("trace_id", "span_id", "parent_span_id", "run_id", "attempt_id")
                  if (value := observability.diagnostic_id(metadata.get(key))) is not None}
    with (observability.context({**diagnostic, "parent_span_id": diagnostic.get("span_id"), "span_id": None})
          if diagnostic else nullcontext()):
        out = _aggregate(settings, deadline=payload["deadline"], owned_process_group=os.getpid(), checkpoint=checkpoint)
    _save_checkpoint(path, {"binding": binding, "out": out, "phase": "complete", "complete": True})
    return 0


def main():
    if sys.argv[1:] != ["--worker"]:
        return 3
    try:
        payload = json.loads(sys.stdin.buffer.read(MAX_CHECKPOINT_BYTES + 1))
        return _worker(payload)
    except Exception:
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
