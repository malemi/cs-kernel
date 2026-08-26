"""Deterministic 'still awaiting a human reply' sweep — Sent-anchored.

WHY THIS EXISTS: the triage skill used to discover open customer mail by asking
the engine LLM ("elenca la posta ancora senza risposta"). That is
NON-DETERMINISTIC — two runs of the same query returned different sets and
missed real unanswered customer mail 6–13 days old that had no engine task
(incident 2026-07-16). This module answers the binary deterministically:
enumerate recent inbound, subtract every sender we've since written to (Gmail
Sent = the dedup ground truth), no LLM in the discovery loop.

Sent is the ground truth deliberately, and it has ONE blind spot: a thread
resolved OUT OF BAND — by phone, WhatsApp, or face to face — leaves no Sent
message, so the sender stayed open for ever and every tick re-raised them
(a month of daily false alarms, 2026-07/08). The fix is a dated record per
contact (`State.handled_out_of_band`, written by `cs handled`): a sender whose
latest inbound PREDATES their handled moment is not open work, and a later
message re-opens them with no further action. The record is passed IN, so the
open-logic stays pure and unit-testable.

The second blind spot is a thread a HUMAN has personally taken over while it is
still open (`State.escalated_to_human`, written by `cs escalated`). Sent cannot
know that either, so the sweep kept handing the owner two customers he was
mid-conversation with — and the headless operator, which answers customers
itself, kept preparing a second reply to them. Those senders come back in their
OWN bucket, never merged into `open` and never dropped: they are real work, they
are simply not the machine's to do. Unlike a handled record this one does NOT
expire on a newer message — the customer replying to the human who took the
thread over is that same conversation continuing, so expiring there would re-arm
the collision on the very event that causes it.

THE UNIT IS THE CONVERSATION, NOT THE ADDRESS. It used to be the address, and
that is wrong in both directions at once. Too tight: a thread answered to its
principal with a colleague in Cc left the colleague on the queue for 28 days,
because nothing had been sent to *that address*. Too loose: answering somebody
on a NEW thread silently marked their older, still-unanswered thread as done —
which is how four product questions from 2026-06-15 stayed invisible while the
same person got helpful answers on two later threads. Both disappear once the
sweep groups by `cs/thread_key.py`, the same RFC-5322 key the engine stores as
its `thread_id`; the headers it needs were already in the one FETCH.

WHAT THE SWEEP DECIDES AND WHAT IT ASKS. It decides EXISTENCE — is there a
message from us, in this conversation, after their last one — from Gmail, which
is the dedup ground truth and stays that way (the engine archive was measured
asserting a send Gmail does not have). It does NOT decide KIND. Whether a
message is an autoresponder is the engine's judgement, asked for through
`cs/engine_view.py`, because the engine has classified every synced message
since the auto-ack incidents of 2026-06/07 and a second opinion here would be a
second source of truth that drifts. The charter rule is in `CLAUDE.md`: when the
engine's classification is wrong, the engine is what gets fixed.

That one deferral is what re-opens the case above. Our own auto-acknowledgement
lands in Gmail Sent seventeen seconds after the customer's mail, so by pure
existence it IS "a message from us, after theirs". The engine knows it is not an
answer. Now the sweep does too, and an outbound the engine flags automatic no
longer closes a conversation.

Scope stays narrow: it does NOT read intent. It cannot tell a question from
"thank you, that's sorted" and it does not try — a keyword list for gratitude is
exactly the kind of local heuristic the charter forbids. What it CAN say without
judging anybody's words is whether a human of ours ever answered in this
conversation at all, and that turns out to separate the queue cleanly. So an
open conversation goes to one of three places:

  open      nobody of ours ever wrote a real answer here. This is the queue.
  resumed   we DID answer, and they wrote again afterwards. Somebody who
            replies to a completed job is not the same event as somebody nobody
            has answered, and printing the two together is how a queue of
            fifteen turns out to be one item of work.
  automatic the engine classified their newest message as machine-generated.

None of the three is dropped. All three print, each with its reason, because a
contact that silently stops being raised looks like a bug and gets reported as
one — and because `resumed` and `automatic` are the two buckets that would cost
a real customer if the classification were wrong. A row in the wrong bucket is
one line further down the page; a row deleted is gone.

The ignore list is matched as LITERALS PLUS fnmatch PATTERNS (`cs/addr_match.py`,
shared with the suppression list), because the loudest robots cannot be
enumerated: a bounce daemon's sending host rotates per message, so one customer's
undeliverable address produced seven distinct `mail-daemon@<host-NN>.<domain>`
senders in six days and an exact list was stale on the next bounce. `fnmatch`
keeps the decision deterministic and offline — no LLM decides who is a person.
What it must never do is widen: a pattern is a pattern only when the entry
carries a wildcard, so an address written before patterns existed still takes the
exact-match path.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .addr_match import AddrSet
from .config import Settings


#: Bucket precedence when one address has several open conversations. An
#: address is reported at the strongest thing true of it: a conversation nobody
#: answered outranks one they merely came back to, which outranks a robot. The
#: ordering is the whole safety property of the roll-up — a customer with one
#: unanswered thread and five courtesies must be reported as unanswered.
_RANK = {"open": 0, "resumed": 1, "automatic": 2}


def _thread_state(msgs: list[dict], outs: list[dict], view) -> tuple[str, dict] | None:
    """State of ONE conversation: `(bucket, latest inbound)` or None if answered.

    `msgs` are its inbound messages, `outs` ours, `view` the engine's reading of
    it (or None when the engine could not be asked — in which case no message is
    treated as automatic, which is exactly the behaviour before this existed).

    An outbound the engine calls automatic is not an answer. That single line is
    the difference between a customer's four questions being closed by our own
    acknowledgement and being raised.
    """
    if not msgs:
        return None
    last = max(msgs, key=lambda m: m["date"])
    human_out = [o for o in outs if not (view is not None and view.is_auto(o.get("date")))]
    if any(o["date"] > last["date"] for o in human_out):
        return None  # a real answer, after their last word → settled
    if view is not None and view.is_auto(last.get("date")):
        return ("automatic", last)
    # A human of ours did write here, just not last. They came back afterwards:
    # still open, but a different kind of open, and not the queue's headline.
    if human_out:
        return ("resumed", last)
    return ("open", last)


def _partition(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """(open, held out of band, taken over by a human, resumed, automatic) — one
    pass, so the public views below never disagree about who is where. Every
    sender that still has an open conversation lands in exactly one of the five.

    `views` maps a thread key to the engine's reading of that conversation
    (`cs/engine_view.py`). Absent or empty, every message is treated as written
    by a person, which is what the sweep assumed before it could ask.
    """
    self_addrs = {a.strip().lower() for a in self_addrs if a}
    # `self_addrs` stays exact on purpose: it is a list of identities we own,
    # not of robots we recognise, and a wildcard there would silently hide a
    # customer whose address resembles one of ours.
    # Idempotent: callers that already hold an AddrSet re-split a set of the
    # same entries, and a plain set (every unit test, every older caller) is
    # upgraded here rather than at each call site.
    ignore = AddrSet(ignore)
    handled_at: dict[str, datetime] = {}
    for a, d in (handled or {}).items():
        a = (a or "").strip().lower()
        if not a or d is None:
            continue
        # A naive record is read as UTC (same convention as cs/_time.py):
        # comparing it with a tz-aware message date would otherwise raise.
        handled_at[a] = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    taken: dict[str, dict] = {
        (a or "").strip().lower(): (r or {})
        for a, r in (escalated or {}).items()
        if (a or "").strip()
    }

    # Group both directions by conversation. A message with no usable thread key
    # keys on the address instead, which reproduces the pre-threading behaviour
    # exactly — including for every caller (and every unit test) that passes
    # plain dicts with no headers at all.
    inbound_by_thread: dict[tuple[str, str], list[dict]] = {}
    threads_of: dict[str, set[tuple[str, str]]] = {}
    # The sender's NEWEST message, across every conversation. The two operator
    # ledgers are keyed to this and not to whichever thread the split below
    # picks: `handled` means "resolved out of band, and a later message re-opens
    # them", and the message that re-opens them can arrive on any thread. Reading
    # an OLDER thread's date there let a record written last night hold back a
    # customer who wrote again this morning — the one direction that loses a
    # customer, caught on the live queue rather than reasoned about.
    latest_overall: dict[str, dict] = {}
    for m in inbound:
        e = (m.get("email") or "").strip().lower()
        if not e or e in self_addrs or e in ignore:
            continue
        if m.get("date") is None:
            continue
        key = (m.get("thread_key") or "").strip() or e
        inbound_by_thread.setdefault((e, key), []).append(m)
        threads_of.setdefault(e, set()).add((e, key))
        cur = latest_overall.get(e)
        if cur is None or m["date"] > cur["date"]:
            latest_overall[e] = m

    # Ours, keyed the same way. A Sent message with a thread key belongs to that
    # conversation and to no other — deliberately NOT also to each recipient's
    # address bucket. Counting it twice would restore the exact leak this
    # change removes: a helpful answer on a new thread marking an older,
    # untouched thread answered.
    outs_by_thread: dict[tuple[str, str], list[dict]] = {}
    for s in sent:
        d = s.get("date")
        if d is None:
            continue
        tkey = (s.get("thread_key") or "").strip()
        recipients = {(a or "").strip().lower() for a in s.get("to", [])}
        recipients.discard("")
        if tkey:
            for e in threads_of:
                if (e, tkey) in inbound_by_thread:
                    outs_by_thread.setdefault((e, tkey), []).append(s)
        for a in recipients:
            if (a, a) in inbound_by_thread:
                outs_by_thread.setdefault((a, a), []).append(s)

    # Per address, the strongest open conversation it has (see _RANK); an
    # address whose every conversation is settled is not reported at all.
    picked: dict[str, tuple[int, dict, str]] = {}
    for (e, key), msgs in inbound_by_thread.items():
        state = _thread_state(msgs, outs_by_thread.get((e, key), []),
                              (views or {}).get(key))
        if state is None:
            continue
        bucket, last_msg = state
        rank = _RANK[bucket]
        cur = picked.get(e)
        # Strongest bucket wins; within a bucket the OLDEST conversation is the
        # one worth naming — it is the one that has been waiting.
        if cur is None or (rank, last_msg["date"]) < (cur[0], cur[1]["date"]):
            picked[e] = (rank, last_msg, bucket)

    out: list[dict] = []
    held: list[dict] = []
    mine: list[dict] = []
    resumed: list[dict] = []
    automatic: list[dict] = []
    for e, (_rank, m, bucket) in picked.items():
        last = m["date"]
        row = {
            "email": e,
            "name": m.get("name") or "",
            "last_inbound_date": last,
            "subject": m.get("subject") or "",
            "days_waiting": (now - last).days,
            "thread_key": (m.get("thread_key") or "").strip() or e,
            "state": bucket,
        }
        # The ledger rows answer a question about the CONTACT, not about one of
        # their conversations, so they are dated by the contact's newest message
        # — the same number these rows have always carried.
        newest = latest_overall.get(e) or m
        ledger_row = {
            **row,
            "last_inbound_date": newest["date"],
            "subject": newest.get("subject") or "",
            "days_waiting": (now - newest["date"]).days,
            "thread_key": (newest.get("thread_key") or "").strip() or e,
        }
        h = handled_at.get(e)
        if h is not None and newest["date"] <= h:
            # Resolved off-email BEFORE they last wrote → not open work. The
            # comparison is against their LATEST message, on ANY thread: one
            # sent after the call is new, and lands in `out` on its own.
            held.append({**ledger_row, "handled_at": h})
            continue
        # Checked AFTER handled, and the order is a decision: "resolved" beats
        # "somebody is on it", so closing a thread you had taken over settles
        # it here even if the release was forgotten. The reverse order would
        # keep printing "with you" on a thread that is over.
        rec = taken.get(e)
        if rec is not None:
            at = rec.get("escalated_at")
            if at is not None and at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            mine.append({
                **ledger_row,
                "escalated_at": at,
                "escalated_owner": rec.get("owner") or "",
                "escalated_reason": rec.get("reason") or "",
                # Days the HUMAN has had it, which is the number that decides
                # whether an escalation has quietly rotted; `days_waiting` is
                # the customer's wait and answers a different question.
                "days_escalated": (now - at).days if at is not None else None,
            })
            continue
        # `handled` and `escalated` are checked FIRST and for every bucket: a
        # record the operator wrote by hand outranks anything derived, and a
        # thread a colleague has taken over must not resurface as "automatic"
        # because the customer's mailer answered it last.
        if bucket == "automatic":
            automatic.append(row)
        elif bucket == "resumed":
            resumed.append(row)
        else:
            out.append(row)
    for bucket_rows in (out, held, mine, resumed, automatic):
        bucket_rows.sort(key=lambda r: r["last_inbound_date"])  # oldest first
    return out, held, mine, resumed, automatic


def compute_open(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
) -> list[dict]:
    """Pure open-logic — no IMAP, unit-testable on plain dicts.

    - group `inbound` by `email`, keep each sender's LATEST message (max date);
    - a sender is OPEN if NO `sent` message addressed to that email has
      date > that latest inbound date;
    - drop any sender whose email is in `self_addrs`, or matches `ignore` —
      whose entries are literal addresses AND fnmatch patterns such as
      `mail-daemon@*` (an entry without a wildcard is matched exactly, as it
      always was);
    - drop any sender whose latest inbound is at or before their `handled`
      moment (resolved out of band — see the module docstring);
    - drop any sender in `escalated` (a human took the thread over; the row
      comes back from `compute_escalated`, never merged in here);
    - drop any sender whose only open conversations are `resumed` or
      `automatic` — those come back from `compute_resumed` / `compute_automatic`,
      never merged in here, for the same reason `escalated` does not merge:
      re-labelled, not deleted;
    - return OPEN senders oldest-first (by latest_inbound date), each row
      {email, name, last_inbound_date, subject, days_waiting, thread_key, state}.

    Rows carrying a `thread_key` are grouped by conversation; rows without one
    fall back to the sender's address, which is exactly what this function did
    before threading existed.
    """
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views)[0]


def compute_handled(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
) -> list[dict]:
    """The senders `compute_open` held back BECAUSE of an out-of-band record —
    the same rows plus `handled_at`. The other half of the pair, so a caller
    can SAY why somebody is missing from the open list: silence that looks like
    a bug gets reported as one. (`sweep()` returns both in one pass; this is
    for a caller that already has the plain dicts.)"""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views)[1]


def compute_escalated(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
) -> list[dict]:
    """The senders a HUMAN has taken over — the same rows plus `escalated_at`,
    `escalated_owner`, `escalated_reason` and `days_escalated`. Still open work,
    still owed an answer; just not the machine's to answer. A caller that
    prints `compute_open` and not this one has re-created the silent drop."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views)[2]


def compute_resumed(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
) -> list[dict]:
    """Senders we DID answer in this conversation, who then wrote again.

    Still unanswered by the letter of the sweep — their message is the newest —
    but a fundamentally different event from a conversation nobody has touched,
    and mixing the two is what made a fifteen-row queue read as fifteen jobs.
    Printed, never dropped: this bucket is where a real follow-up question lands
    if it arrives after a reply, so nobody may treat it as noise."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views)[3]


def compute_automatic(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
) -> list[dict]:
    """Senders whose newest message the ENGINE classified as machine-generated.

    Not a kernel opinion and not a sender list: the engine flagged that exact
    message, from its headers and its own body markers. Still printed, because a
    vacation notice can land on the same conversation as a real request and a
    silent drop would bury the request — and because a classification the
    operator disagrees with is a bug report for the ENGINE, which he can only
    file if he can see the row."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views)[4]


def sweep(settings: Settings, days: int) -> dict:
    """IMAP-backed sweep: {"open", "handled", "escalated", "resumed",
    "automatic", "note"}. `handled` rows carry `handled_at` + `handled_reason`;
    `escalated` rows carry `escalated_at`, `escalated_owner`, `escalated_reason`
    and `days_escalated`; `note` is non-None only when the engine could not
    classify some conversation, in which case those threads are read exactly as
    they were before the engine was ever asked."""
    from . import engine_view, gmail_archive

    inbound = gmail_archive.inbound_recent(settings, days)
    sent = gmail_archive.sent_recent(settings, days)

    self_addrs = set(settings.self_email_set)
    if settings.email_address:
        self_addrs.add(settings.email_address.strip().lower())

    ignore = set(settings.system_sender_set)
    records: dict[str, dict] = {}
    taken: dict[str, dict] = {}
    try:
        from .state import State

        st = State(settings.db_path)
        # Suppression joins the ignore list, and both halves read a typed entry
        # the same way (`cs/addr_match.py`): a wildcard suppression that quietens
        # this sweep also blocks the outreach runner, which is the only version
        # of "do not contact" worth having.
        ignore |= st.do_not_contact_set()
        records = st.handled_out_of_band()
        taken = st.escalated_to_human()
    except Exception:
        pass  # suppression is best-effort; a missing db must not break discovery

    # Ask the engine about the conversations this sweep is actually about, and
    # only those: one cheap archive read each, no LLM, and none at all for the
    # mail already filtered out as self / ignored / suppressed.
    self_lc = {a.strip().lower() for a in self_addrs if a}
    ignore_set = AddrSet(ignore)
    keys = {
        (m.get("thread_key") or "").strip()
        for m in inbound
        if (m.get("email") or "").strip().lower() not in self_lc
        and (m.get("email") or "").strip().lower() not in ignore_set
    }
    keys.discard("")
    views, note = engine_view.classify(settings, sorted(keys))

    open_rows, held, mine, resumed, automatic = _partition(
        inbound,
        sent,
        self_addrs,
        ignore,
        datetime.now(timezone.utc),
        {e: r["handled_at"] for e, r in records.items()},
        taken,
        views,
    )
    for row in held:
        row["handled_reason"] = (records.get(row["email"]) or {}).get("reason", "")
    return {"open": open_rows, "handled": held, "escalated": mine,
            "resumed": resumed, "automatic": automatic, "note": note}


def open_threads(settings: Settings, days: int) -> list[dict]:
    """Just the open senders (the sweep's headline list)."""
    return sweep(settings, days)["open"]


def crm_annotate(settings, rows: list[dict], lookup=None) -> str | None:
    """Attach a compact CRM label to each row, IN PLACE, and return the first
    degradation note (or None).

    WHY: the queue's size is not its workload. A sweep that prints a paying
    customer's outage next to a conference invitation and a bounce gives the
    same weight to both, and the operator re-does that separation by hand every
    morning. The CRM already knows which sender is a customer, so the sweep can
    say it — through the port (`cs/crm`), never a company switch, so a clone on
    a different backend gets the same column from its own adapter.

    Each row gains `crm` (the adapter's own facts for that address, rendered
    through its `render_hints` — never a lowest-common-denominator label the
    kernel invents) and `crm_known` (a record exists). No record and a degraded
    backend both leave `crm` empty, but only the second sets `crm_known` False
    for a reason worth printing — hence the returned note: ONE line in the
    caller, not one per address.

    `lookup` is injectable so the grouping is testable without a backend; the
    default is the port's own, which NEVER raises.
    """
    if lookup is None:
        from . import crm as _crm

        lookup = _crm.lookup
    note: str | None = None
    for row in rows:
        try:
            res = lookup(settings, row["email"])
        except Exception as e:  # noqa: BLE001 — the port promises not to, belt and braces
            row["crm"], row["crm_known"] = "", False
            note = note or f"{type(e).__name__}: {e}"
            continue
        if not res.ok and note is None and res.note:
            note = res.note
        if not res.rows:
            row["crm"], row["crm_known"] = "", False
            continue
        first = res.rows[0]
        facts = [str(first.facts.get(k, "")).strip() for k in (res.render_hints or [])]
        label = "/".join(f for f in facts if f) or (first.label or res.source)
        if len(res.rows) > 1:
            label = f"{label} (+{len(res.rows) - 1})"
        row["crm"], row["crm_known"] = label, True
    return note
