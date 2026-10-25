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
second source of truth that drifts. The charter rule is in `AGENTS.md`: when the
engine's classification is wrong, the engine is what gets fixed.

That one deferral is what re-opens the case above. Our own auto-acknowledgement
lands in Gmail Sent seventeen seconds after the customer's mail, so by pure
existence it IS "a message from us, after theirs". The engine knows it is not an
answer. Now the sweep does too, and an outbound the engine flags automatic no
longer closes a conversation.

Scope stays narrow: it does NOT read intent, and it never learned to. Whether
"Va bene, la ringrazio tanto" closes a job or opens one is a judgement about
what a person MEANT, in whatever language they wrote it, and a gratitude keyword
list here would be exactly the local heuristic the charter forbids — a second
opinion, in the wrong repo, drifting from the engine's. So that question is
asked, not answered: `emails.needs_reply` (engine `zylch/utils/reply_need.py`),
through `cs/engine_view.py`, once per sweep. The engine decides; this module
decides only what to do with the answer, which is to move the row into its own
section and keep printing it. An open conversation goes to one of four places:

  open      nobody of ours ever wrote a real answer here. This is the queue.
  resumed   we DID answer, they wrote again, and the engine says that message
            still needs something from us. A real follow-up on a thread that
            already has history — not the headline, but work.
  courtesy  we answered, they wrote again, and the ENGINE says nothing is owed:
            a closing thank-you on a finished job. Twenty-two of these once sat
            in `resumed`, which is how a queue of eleven real jobs arrived
            thirty-three rows long.
  automatic the engine classified their newest message as machine-generated.

Nothing is dropped. All four print, each with its reason, because a contact that
silently stops being raised looks like a bug and gets reported as one — and
because `resumed`, `courtesy` and `automatic` are the buckets that would cost a
real customer if the classification were wrong. A row in the wrong bucket is one
line further down the page; a row deleted is gone. A NEW message from the same
person is a new message: it is judged on its own and the previous verdict never
covers it, which is what makes the whole thing reversible without a ledger.

The default everywhere is NEEDS A REPLY. An engine that is asleep, that predates
the method, that cannot classify one conversation, or that returns a verdict this
module cannot pin to a specific message, all produce the same reading the sweep
gave before it could ask — loud, and with a note saying so.

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

import hashlib
import json
import time
from datetime import datetime, timezone

from .addr_match import AddrSet
from .config import Settings


#: Bucket precedence when one address has several open conversations. An
#: address is reported at the strongest thing true of it: a conversation nobody
#: answered outranks one they came back to, which outranks a robot, which
#: outranks a thank-you. The ordering is the whole safety property of the
#: roll-up — a customer with one unanswered thread and five courtesies must be
#: reported as unanswered.
_RANK = {"open": 0, "resumed": 1, "automatic": 2, "courtesy": 3}


def _thread_state(msgs: list[dict], outs: list[dict], view, settled=None
                  ) -> tuple[str, dict] | None:
    """State of ONE conversation: `(bucket, latest inbound)` or None if answered.

    `msgs` are its inbound messages, `outs` ours, `view` the engine's reading of
    it (or None when the engine could not be asked — in which case no message is
    treated as automatic, which is exactly the behaviour before this existed),
    `settled` the engine's verdict that this conversation's newest inbound needs
    no reply (or None, which means one is owed).

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
        # TWO independent preconditions have to hold before a message may be
        # called a closing courtesy, and they are checked in different places on
        # purpose. Here: a real, non-automatic message of ours precedes it in
        # THIS conversation, computed from Gmail. There: the engine ran its own
        # `answered_before` over its own archive before it would even consider
        # the question. Either one alone can be wrong; both wrong the same way
        # on the same thread is the case this does not defend against, and it is
        # the reason the row still prints.
        if settled is not None and not settled.needs_reply(last.get("date")):
            return ("courtesy", last)
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
    settled: dict | None = None,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """(open, held out of band, taken over by a human, resumed, automatic,
    courtesy) — one pass, so the public views below never disagree about who is
    where. Every sender that still has an open conversation lands in exactly one
    of the six.

    `views` maps a thread key to the engine's reading of that conversation
    (`cs/engine_view.py`). Absent or empty, every message is treated as written
    by a person, which is what the sweep assumed before it could ask. `settled`
    maps a thread key to the engine's verdict that its newest inbound needs no
    reply; absent or empty, every message needs one — again the older reading.
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
    # The sender's newest message that still OWES something, across every
    # conversation. The two operator ledgers are keyed to this and not to
    # whichever thread the split below picks: `handled` means "resolved out of
    # band, and a later message re-opens them", and the message that re-opens
    # them can arrive on any thread. Reading an OLDER thread's date there let a
    # record written last night hold back a customer who wrote again this
    # morning — the one direction that loses a customer, caught on the live
    # queue rather than reasoned about.
    #
    # "That owes something" is the correction the engine made possible, and it
    # is the same bug in its other costume. The record said the operator had
    # phoned this customer and closed it; she then wrote "Va bene, la ringrazio
    # tanto", and a thank-you re-opened a resolved contact for ever. A record is
    # a statement about the CONTACT, so only a message that actually asks us for
    # something may overturn it. When the engine says every message since is a
    # courtesy the record stands; when it says nothing (asleep, older build,
    # unclassifiable) every message owes something and the record expires
    # exactly as it used to.
    latest_overall: dict[str, dict] = {}  # newest of theirs, whatever it says
    latest_owed: dict[str, dict] = {}  # newest of theirs that needs an answer
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
        sv = (settled or {}).get(key)
        if sv is not None and not sv.needs_reply(m.get("date")):
            continue
        cur = latest_owed.get(e)
        if cur is None or m["date"] > cur["date"]:
            latest_owed[e] = m

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
                              (views or {}).get(key), (settled or {}).get(key))
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
    courtesy: list[dict] = []
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
            "reason": (
                getattr((settled or {}).get((m.get("thread_key") or "").strip() or e), "reason", "")
                if bucket == "courtesy" else ""
            ),
        }
        # The ledger rows answer a question about the CONTACT, not about one of
        # their conversations, so they are dated by the contact's newest message
        # that still owes an answer — which is the message a `handled` record is
        # about. With no engine verdict that is the newest message full stop, the
        # number these rows have always carried.
        newest = latest_owed.get(e) or latest_overall.get(e) or m
        ledger_row = {
            **row,
            "last_inbound_date": newest["date"],
            "subject": newest.get("subject") or "",
            "days_waiting": (now - newest["date"]).days,
            "thread_key": (newest.get("thread_key") or "").strip() or e,
        }
        h = handled_at.get(e)
        if h is not None and newest["date"] <= h:
            # Resolved off-email BEFORE they last asked for anything → not open
            # work. The comparison is against their latest OWED message, on ANY
            # thread: one sent after the call is new, and lands in `out` on its
            # own; a thank-you sent after the call is not a new request and
            # leaves the record standing.
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
        elif bucket == "courtesy":
            courtesy.append(row)
        elif bucket == "resumed":
            resumed.append(row)
        else:
            out.append(row)
    for bucket_rows in (out, held, mine, resumed, automatic, courtesy):
        bucket_rows.sort(key=lambda r: r["last_inbound_date"])  # oldest first
    return out, held, mine, resumed, automatic, courtesy


def compute_open(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
    settled: dict | None = None,
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
    - drop any sender whose only open conversations are `resumed`, `automatic`
      or `courtesy` — those come back from `compute_resumed` /
      `compute_automatic` / `compute_courtesy`, never merged in here, for the
      same reason `escalated` does not merge: re-labelled, not deleted;
    - return OPEN senders oldest-first (by latest_inbound date), each row
      {email, name, last_inbound_date, subject, days_waiting, thread_key, state}.

    Rows carrying a `thread_key` are grouped by conversation; rows without one
    fall back to the sender's address, which is exactly what this function did
    before threading existed.
    """
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views, settled)[0]


def compute_handled(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
    settled: dict | None = None,
) -> list[dict]:
    """The senders `compute_open` held back BECAUSE of an out-of-band record —
    the same rows plus `handled_at`. The other half of the pair, so a caller
    can SAY why somebody is missing from the open list: silence that looks like
    a bug gets reported as one. (`sweep()` returns both in one pass; this is
    for a caller that already has the plain dicts.)"""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views, settled)[1]


def compute_escalated(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
    settled: dict | None = None,
) -> list[dict]:
    """The senders a HUMAN has taken over — the same rows plus `escalated_at`,
    `escalated_owner`, `escalated_reason` and `days_escalated`. Still open work,
    still owed an answer; just not the machine's to answer. A caller that
    prints `compute_open` and not this one has re-created the silent drop."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views, settled)[2]


def compute_resumed(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
    settled: dict | None = None,
) -> list[dict]:
    """Senders we DID answer in this conversation, who then wrote again.

    Still unanswered by the letter of the sweep — their message is the newest —
    but a fundamentally different event from a conversation nobody has touched,
    and mixing the two is what made a fifteen-row queue read as fifteen jobs.
    Printed, never dropped: this bucket is where a real follow-up question lands
    if it arrives after a reply, so nobody may treat it as noise."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views, settled)[3]


def compute_automatic(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
    settled: dict | None = None,
) -> list[dict]:
    """Senders whose newest message the ENGINE classified as machine-generated.

    Not a kernel opinion and not a sender list: the engine flagged that exact
    message, from its headers and its own body markers. Still printed, because a
    vacation notice can land on the same conversation as a real request and a
    silent drop would bury the request — and because a classification the
    operator disagrees with is a bug report for the ENGINE, which he can only
    file if he can see the row."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views, settled)[4]


def compute_courtesy(
    inbound: list[dict],
    sent: list[dict],
    self_addrs: set[str],
    ignore: set[str],
    now: datetime,
    handled: dict[str, datetime] | None = None,
    escalated: dict[str, dict] | None = None,
    views: dict | None = None,
    settled: dict | None = None,
) -> list[dict]:
    """Senders we answered, who wrote back, and whose message the ENGINE says
    needs nothing from us — a closing thank-you on a finished job.

    The verdict is the engine's and the reason it gave rides on the row, because
    an operator who disagrees needs to see WHICH message was read this way and
    file it where the judgement lives. Printed like every other re-labelled
    bucket and never dropped: the whole point of the split is that the queue's
    headline stops carrying these, not that they disappear. A `settled` mapping
    that is absent or empty makes this list empty and puts every row back in
    `compute_resumed`, which is the reading before the engine could be asked."""
    return _partition(inbound, sent, self_addrs, ignore, now, handled, escalated,
                      views, settled)[5]


def sweep(settings: Settings, days: int, *, deadline=None, owned_process_group=None, progress=None, listed_roots=None, projection_observer=None, checkpoint=None, completion_deadline=None) -> dict:
    """IMAP-backed sweep: {"open", "handled", "escalated", "resumed",
    "automatic", "courtesy", "note", "read_incomplete"}. `handled` rows carry
    `handled_at` + `handled_reason`; `escalated` rows carry `escalated_at`,
    `escalated_owner`, `escalated_reason` and `days_escalated`; `courtesy` rows
    carry the engine's own `reason`.

    **The two degradation channels mean opposite things and must never be
    merged.**

    `note` is non-None only when the ENGINE could not answer for some
    conversation, in which case those threads are read exactly as they were
    before the engine was ever asked — every message needing a reply. That
    OVER-reports: the list is too wide, and the renderer says so.

    `read_incomplete` is non-None when the MAILBOX could not be read in full —
    a batched FETCH failed and some messages never entered the sweep at all.
    That UNDER-reports: the list is too short, and somebody waiting for an
    answer may simply be missing from it. Routing this into `note` would print
    the reassuring "every message reads as needing a reply" over a silently
    short list, which is the opposite of what happened and the dangerous
    direction — `cs/mailboxes.py:1-16`, and "an unreadable mailbox is not a
    'no'"."""
    from . import engine_view, gmail_archive

    from .review import _stage
    def observed(phase, rows):
        if progress is not None:
            progress(phase, [row.get("thread_key") for row in rows if row.get("thread_key")])
    observation = {"inbound": [], "sent": [], "inbound_complete": False,
                   "sent_complete": False, "roots": [], "assignment": {}}
    def retained(phase, **values):
        observation.update(values)
        if checkpoint is not None:
            checkpoint(observation, phase)
    def check_time():
        if checkpoint is not None and deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("discovery observation deadline")
    read_incomplete = None
    inbound, sent = [], []
    check_time()
    retained("inbound discovery")
    try:
        with _stage("inbound discovery"):
            inbound = gmail_archive.inbound_recent(settings, days)
            retained("inbound discovered", inbound=inbound, inbound_complete=True)
            observed("inbound discovered", inbound)
        check_time()
        retained("sent discovery")
        with _stage("sent discovery"):
            sent = gmail_archive.sent_recent(settings, days)
            retained("sent discovered", sent=sent, sent_complete=True)
    except gmail_archive.ChunkFetchFailed as e:
        # Degrade, do not raise: `cs/cli.py` calls sweep() with no try, and a
        # traceback helps nobody. Degrade into `read_incomplete`, never `note`
        # — see the docstring. With the read short we cannot say who is
        # waiting, so we say that, rather than printing a confidently empty
        # queue.
        read_incomplete = str(e)
        if checkpoint is None:
            inbound, sent = [], []

    check_time()
    retained("local state")
    self_addrs = set(settings.self_email_set)
    if settings.email_address:
        self_addrs.add(settings.email_address.strip().lower())

    from .operational_fixture import admit_originals

    operational_fixture_discovery = []
    inbound, self_addrs = admit_originals(settings, inbound, self_addrs,
                                          discovery=operational_fixture_discovery)

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
    latest = {}
    for message in inbound:
        email = (message.get("email") or "").strip().lower()
        key = (message.get("thread_key") or "").strip()
        date = message.get("date")
        if not email or email in self_lc or email in ignore_set or not key or date is None:
            continue
        date = date if date.tzinfo else date.replace(tzinfo=timezone.utc)
        latest[key] = max(latest.get(key, date), date)
    ordered = sorted(latest, key=lambda key: (-latest[key].timestamp(), key))
    retained("eligible roots", inbound=inbound, self_addrs=sorted(self_addrs), ignore=sorted(ignore),
             records=records, taken=taken, roots=ordered,
             operational_fixture_discovery=operational_fixture_discovery)
    check_time()
    with _stage("inbound classification"):
        remaining = None if deadline is None else max(0, deadline - time.monotonic())
        if remaining == 0:
            views, note = {}, "classification deferred: review deadline"
        elif remaining is None:
            views, note = engine_view.classify(settings, ordered)
        else:
            views, note = engine_view.classify(settings, ordered,
                timeout=min(60, remaining / 4), deadline=time.monotonic() + remaining / 4,
                owned_process_group=owned_process_group)
    retained("classification complete")
    check_time()
    # The second question, in ONE call for the whole sweep: which of these
    # conversations owes nothing. Asked about the same set — the engine screens
    # the structural cases itself and only adjudicates what is left, so asking
    # about a conversation nobody answered is free.
    with _stage("inbound settlement"):
        remaining = None if deadline is None else max(0, deadline - time.monotonic())
        if remaining == 0:
            settled, owed_note = {}, "settlement deferred: review deadline"
        elif remaining is None:
            settled, owed_note = engine_view.settled(settings, ordered)
        else:
            settled, owed_note = engine_view.settled(settings, ordered, timeout=min(120, remaining / 4))
    if owed_note:
        note = f"{note}; {owed_note}" if note else owed_note

    retained("settlement complete")
    check_time()
    from . import task_assignment
    messages = {key: [] for key in ordered}
    outbound = {key: [] for key in ordered}
    for message in inbound:
        key = (message.get("thread_key") or "").strip()
        email = (message.get("email") or "").strip().lower()
        if key in messages and email and email not in self_lc and email not in ignore_set and message.get("date") is not None:
            messages[key].append(message)
    for message in sent:
        key = (message.get("thread_key") or "").strip()
        if key in outbound and message.get("date") is not None:
            outbound[key].append(message)
    useful = {}
    for key in ordered:
        state = _thread_state(messages[key], outbound[key], views.get(key), settled.get(key))
        useful[key] = state is not None and state[0] in {"open", "resumed"}
    ordered.sort(key=lambda key: not useful[key])
    observed("eligible inbound roots", [{"thread_key": key} for key in ordered])
    if listed_roots is not None:
        ordered = list(dict.fromkeys(ordered + list(listed_roots)))
    retained("inbound projection roots", roots=ordered)
    check_time()
    observed("inbound projection roots", [{"thread_key": key} for key in ordered])
    with _stage("inbound assignment projection"):
        assignment = task_assignment.projections(settings, ordered,
            **({"deadline": deadline} if deadline is not None else {}),
            **({"owned_process_group": owned_process_group} if owned_process_group is not None else {}))
        assignment = {key: assignment.get(key, task_assignment._unknown(key, "review projection unavailable", owner_uid=settings.engine_owner_uid))
                      for key in ordered}
        retained("projection complete", assignment=assignment)
        if projection_observer is not None:
            projection_observer(assignment)
    if completion_deadline is None:
        check_time()
    elif time.monotonic() >= completion_deadline:
        raise TimeoutError("discovery completion deadline")
    retained("rendering")
    normal_inbound, human_work, assignment_audit, reopened = task_assignment.split_inbound(
        inbound, assignment, taken, self_lc, ignore, datetime.now(timezone.utc),
        owner_uid=settings.engine_owner_uid
    )
    open_rows, held, mine, resumed, automatic, courtesy = _partition(
        normal_inbound,
        sent,
        self_addrs,
        ignore,
        datetime.now(timezone.utc),
        {e: r["handled_at"] for e, r in records.items()},
        taken,
        views,
        settled,
    )
    open_rows.extend(reopened)
    open_rows.sort(key=lambda row: row["last_inbound_date"])
    # Scheduling revisions identify current work; they never cache permission
    # to answer it. Every selected root still passes the ordinary action guards.
    for row in open_rows + resumed:
        key = row.get("thread_key")
        identities = [{field: message.get(field) for field in (
            "message_id", "provider_folder", "provider_uidvalidity", "provider_uid", "date"
        )} for message in messages.get(key, [])]
        identities.sort(key=lambda item: json.dumps(item, sort_keys=True, default=str))
        snapshot = assignment.get(key, {})
        revision = [settings.engine_owner_uid, key, identities,
                    snapshot.get("route_digest"), snapshot.get("current_message_ids")]
        row["_workset_revision"] = hashlib.sha256(json.dumps(
            revision, sort_keys=True, default=str, separators=(",", ":")
        ).encode()).hexdigest()
    for row in held:
        row["handled_reason"] = (records.get(row["email"]) or {}).get("reason", "")
    return {"open": open_rows, "handled": held, "escalated": mine,
            "operational_fixture_discovery": operational_fixture_discovery,
            "human_work": human_work, "assignment_audit": assignment_audit,
            "assignment_incomplete": any(not row["complete"] for row in assignment.values()) or any(
                not row["assignment"]["complete"] for row in human_work),
            "resumed": resumed, "automatic": automatic, "courtesy": courtesy,
            "note": note, "read_incomplete": read_incomplete}


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


def _discovery_encode(value):
    if isinstance(value, datetime):
        return {"__cs_datetime__": value.isoformat()}
    if isinstance(value, dict):
        return {key: _discovery_encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_discovery_encode(item) for item in value]
    if isinstance(value, str):
        return str(value)
    if value is None or type(value) in (int, float, bool):
        return value
    raise ValueError("unsupported discovery checkpoint type")


def _discovery_decode(value):
    if isinstance(value, dict):
        if set(value) == {"__cs_datetime__"}:
            return datetime.fromisoformat(value["__cs_datetime__"])
        return {key: _discovery_decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_discovery_decode(item) for item in value]
    return value


def _discovery_configuration(settings):
    return {"owner_uid": settings.engine_owner_uid,
            "sha256": hashlib.sha256(json.dumps(settings.model_dump(mode="json"),
                sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def _discovery_record(record):
    out = _discovery_decode(record["out"])
    if set(out) - {"configuration", "observation", "result", "code"}:
        raise ValueError("unknown discovery checkpoint field")
    configuration = out.get("configuration")
    if (not isinstance(configuration, dict) or set(configuration) != {"owner_uid", "sha256"}
            or not isinstance(configuration["owner_uid"], str)
            or not isinstance(configuration["sha256"], str) or len(configuration["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in configuration["sha256"])):
        raise ValueError("discovery configuration binding missing")
    observation = out.get("observation", {})
    if not isinstance(observation, dict):
        raise ValueError("discovery observation malformed")
    for key in ("inbound_complete", "sent_complete"):
        if type(observation.get(key)) is not bool:
            raise ValueError("discovery enumeration binding missing")
    for key in ("inbound", "sent"):
        if not isinstance(observation.get(key), list) or any(not isinstance(row, dict) for row in observation[key]):
            raise ValueError("discovery rows malformed")
        for row in observation[key]:
            if row.get("date") is not None and not isinstance(row["date"], datetime):
                raise ValueError("discovery date provenance malformed")
    if (not isinstance(observation.get("roots"), list)
            or any(not isinstance(root, str) for root in observation["roots"])
            or len(set(observation["roots"])) != len(observation["roots"])
            or not isinstance(observation.get("assignment"), dict)):
        raise ValueError("discovery root coverage malformed")
    if record["complete"]:
        value = out.get("result")
        if (not observation["inbound_complete"] or not observation["sent_complete"]
                or not isinstance(value, dict) or type(out.get("code")) is not int
                or out["code"] not in (0, 3)
                or type(value.get("assignment_incomplete")) is not bool
                or any(not isinstance(value.get(key), list) for key in
                    ("open", "handled", "escalated", "human_work", "assignment_audit",
                     "operational_fixture_discovery", "resumed", "automatic", "courtesy"))
                or out["code"] != (3 if value.get("read_incomplete") or value["assignment_incomplete"] else 0)):
            raise ValueError("discovery terminal result malformed")
    return out


def _discovery_incomplete(out, reason):
    from . import task_assignment
    observed = out.get("observation", {})
    owner_uid = (out.get("configuration") or {}).get("owner_uid")
    inbound = observed.get("inbound", [])
    roots = list(dict.fromkeys(observed.get("roots", []) + [row["thread_key"] for row in inbound
        if isinstance(row.get("thread_key"), str) and row["thread_key"]]))
    assignment = {root: observed.get("assignment", {}).get(root,
        task_assignment._unknown(root, reason, owner_uid=owner_uid)) for root in roots}
    normal, held, audit, reopened = task_assignment.split_inbound(inbound, assignment,
        observed.get("taken", {}), set(observed.get("self_addrs", [])),
        set(observed.get("ignore", [])), datetime.now(timezone.utc), owner_uid=owner_uid)
    buckets = _partition(normal, observed.get("sent", []), set(observed.get("self_addrs", [])),
        set(observed.get("ignore", [])), datetime.now(timezone.utc), {}, observed.get("taken", {}))
    value = dict(zip(("open", "handled", "escalated", "resumed", "automatic", "courtesy"), buckets))
    value["open"].extend(reopened)
    value.update(human_work=held, assignment_audit=audit,
        operational_fixture_discovery=observed.get("operational_fixture_discovery", []),
        assignment_incomplete=True, note=reason, read_incomplete=reason, crm_note=None)
    return value


def _scheduled_discovery(*, worker_command=None, observation_seconds=510,
                        cleanup_seconds=10, publication_seconds=5, final_seconds=5,
                        total_seconds=540):
    import os
    from pathlib import Path
    import secrets
    import subprocess
    import sys
    import tempfile
    from .operator_health import ARGV, identity
    from .operator_dossier import _stop
    from .review import _read_checkpoint, _save_checkpoint
    started = time.monotonic()
    if not (0 < observation_seconds and 0 < cleanup_seconds and 0 < publication_seconds
            and 0 < final_seconds and observation_seconds + cleanup_seconds
            + publication_seconds + final_seconds <= total_seconds <= 540):
        raise ValueError("invalid discovery lifecycle")
    observation_deadline = started + observation_seconds
    cleanup_deadline = observation_deadline + cleanup_seconds
    publication_deadline = cleanup_deadline + publication_seconds
    final_deadline = publication_deadline + final_seconds
    binding = {"version": 1, "attempt": secrets.token_hex(32), "uid": os.getuid(),
               "parent": identity(os.getpid())[0], "argv": ARGV}
    out = {}
    phase = "configuration"
    clean = False
    normal = False
    proc = None
    stamp = None
    with tempfile.TemporaryDirectory(prefix="cs-discovery-") as directory:
        path = Path(directory) / "checkpoint.json"
        request_read, request_write = os.pipe()
        try:
            command = (worker_command(request_read) if callable(worker_command) else worker_command) or (sys.executable, "-B", "-m", "cs.unanswered", "--worker", str(request_read))
            with tempfile.TemporaryFile() as stdout:
                proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout,
                    stderr=None, pass_fds=(request_read,), start_new_session=True,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                stamp = identity(proc.pid)[0]
                binding["worker"] = stamp
                request = {"binding": binding, "path": str(path),
                           "deadline": observation_deadline - min(10, observation_seconds / 10),
                           "completion_deadline": observation_deadline}
                encoded = json.dumps(request, separators=(",", ":")).encode()
                if len(encoded) > 4096:
                    raise ValueError("discovery request capacity")
                os.close(request_read)
                request_read = None
                with os.fdopen(request_write, "wb") as stream:
                    request_write = None
                    stream.write(encoded)
                try:
                    proc.wait(timeout=max(.001, observation_deadline - time.monotonic()))
                    normal = proc.returncode in (0, 3) and time.monotonic() < observation_deadline
                except subprocess.TimeoutExpired:
                    pass
                finally:
                    clean = _stop(proc, stamp, min(cleanup_deadline, time.monotonic() + cleanup_seconds))
            record = _read_checkpoint(path, binding)
            phase = record["phase"]
            out = _discovery_record(record)
            normal = normal and clean and record["complete"] and proc.returncode == out.get("code")
        except Exception:
            normal = False
            if proc is not None and proc.poll() is None:
                clean = _stop(proc, stamp, min(cleanup_deadline, time.monotonic() + cleanup_seconds))
        finally:
            for descriptor in (request_read, request_write):
                if descriptor is not None:
                    os.close(descriptor)
        cleanup_finished = time.monotonic()
        publication_deadline = min(publication_deadline, cleanup_finished + publication_seconds)
        final_deadline = min(final_deadline, publication_deadline + final_seconds)
        if time.monotonic() >= publication_deadline:
            normal = False
        if normal:
            value, code = out["result"], out["code"]
        else:
            reason = "scheduled discovery incomplete during " + phase
            print(reason + "; cleanup " + ("complete" if clean else "incomplete"), file=sys.stderr, flush=True)
            value, code = _discovery_incomplete(out, reason), 3
        return {"value": value, "code": code, "normal": normal, "cleanup_complete": clean,
                "observation": out.get("observation"),
                "configuration": out.get("configuration"), "binding": binding,
                "started": started, "cleanup_finished": cleanup_finished, "observation_deadline": observation_deadline,
                "cleanup_deadline": cleanup_deadline, "publication_deadline": publication_deadline,
                "final_deadline": final_deadline}


def scheduled_component(*, argv):
    from .operator_health import ARGV
    if argv != ARGV:
        raise ValueError("scheduled component requires exact canonical arguments")
    return _scheduled_discovery()


_PUBLICATION_PATHS = ("discovery.json", "inventory-view.jsonl", "inventory-view-envelope.json", "inventory-view-progress.json")


def _publication_snapshot(directory, expected, names=_PUBLICATION_PATHS):
    import os
    import stat
    from .operator_inventory_view import read_private
    snapshots = {}
    for name in names:
        path = directory / name
        try:
            before = path.lstat()
        except FileNotFoundError:
            continue
        raw = read_private(path)
        after = path.lstat()
        fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        if (any(getattr(before, field) != getattr(after, field) for field in fields)
                or raw != expected.get(name) or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1):
            raise ValueError("publication ownership unproven: " + name)
        snapshots[name] = (tuple(getattr(after, field) for field in fields), hashlib.sha256(raw).hexdigest())
    return snapshots


def _publication_withdraw(directory, directory_identity, expected, snapshots, deadline, *, exclusive_writer=False, names=_PUBLICATION_PATHS):
    import os
    from .operator_inventory_view import read_private
    if not exclusive_writer or time.monotonic() >= deadline:
        return False
    try:
        info = directory.lstat()
        if directory.is_symlink() or (info.st_dev, info.st_ino) != directory_identity:
            return False
        fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        for name in reversed(names):
            if time.monotonic() >= deadline:
                return False
            path = directory / name
            if name not in snapshots:
                if path.exists() or path.is_symlink():
                    return False
                continue
            info = path.lstat()
            raw = read_private(path)
            current = (tuple(getattr(info, field) for field in fields), hashlib.sha256(raw).hexdigest())
            if current != snapshots[name] or raw != expected[name]:
                return False
            path.unlink()
        return all(not (directory / name).exists() and not (directory / name).is_symlink()
                   for name in names)
    except (OSError, ValueError):
        return False


from contextlib import contextmanager


@contextmanager
def _publication_lock(directory):
    import fcntl
    import os
    from .operator_health import private
    private(directory, True)
    before = directory.lstat()
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError("publication directory changed")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def _publish_discovery(result):
    import os
    import sys
    from pathlib import Path
    from . import config, operator_health, operator_inventory_view as view
    from .operator_workset import reserve
    if not result["normal"] or not result["cleanup_complete"]:
        raise ValueError("discovery worker incomplete")
    deadline = result["publication_deadline"]
    def remaining():
        if time.monotonic() >= deadline:
            raise TimeoutError("discovery publication deadline")
    remaining()
    settings = config.load()
    remaining()
    if _discovery_configuration(settings) != result["configuration"]:
        raise ValueError("discovery configuration changed")
    context = json.loads(os.environ["CS_OPERATOR_HEALTH_CONTEXT"])
    if (context.get("workset_enabled") is not True or context.get("owner_uid") != settings.engine_owner_uid
            or sys.argv[1:] != operator_health.ARGV):
        raise ValueError("discovery canonical context differs")
    directory = view.directory(context)
    with _publication_lock(directory):
        return _publish_discovery_locked(result, settings, context, directory)


def _publish_discovery_locked(result, settings, context, directory):
    import os
    import sys
    from . import operator_health, operator_inventory_view as view
    from .operator_workset import reserve
    deadline = result["publication_deadline"]
    def remaining():
        if time.monotonic() >= deadline:
            raise TimeoutError("discovery publication deadline")
    metadata = directory.lstat()
    directory_identity = (metadata.st_dev, metadata.st_ino)
    for name in _PUBLICATION_PATHS:
        path = directory / name
        if path.exists() or path.is_symlink():
            raise ValueError("publication preimage is not absent: " + name)
    from . import operator_discovery_receipt as legacy
    legacy_directory = None
    legacy_name = None
    legacy_identity = None
    legacy_expected = {}
    legacy_snapshots = {}
    if os.environ.get("CS_OPERATOR_ACCEPTANCE_RECEIPT"):
        legacy_directory = legacy.directory_path()
        descriptor = legacy.private_dir(legacy_directory, create=True)
        try:
            info = os.fstat(descriptor)
            legacy_identity = (info.st_dev, info.st_ino)
        finally:
            os.close(descriptor)
        stamp = operator_health.identity(os.getpid())[0]
        legacy_name = str(stamp["pid"]) + "-" + str(stamp["started_ticks"]) + ".json"
        target = legacy_directory / legacy_name
        if target.exists() or target.is_symlink():
            raise ValueError("legacy publication preimage is not absent")
    value = result["value"]
    remaining()
    value["triage_workset"] = reserve(settings, value)
    remaining()
    if not isinstance(value["triage_workset"], dict) or value["triage_workset"].get("complete") is not True:
        raise ValueError("discovery reservation incomplete")
    code = result["code"]
    output = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n").encode()
    chain = []
    pid = os.getpid()
    for _ in range(32):
        row, pid = operator_health.identity(pid)
        chain.append(row)
        if row == context["supervisor"]:
            break
    else:
        raise ValueError("discovery supervisor differs")
    expected = {"discovery.json": json.dumps({"nonce": context["nonce"],
        "owner_uid": settings.engine_owner_uid, "ancestry": chain, "exit_code": code,
        "output_sha256": hashlib.sha256(output).hexdigest(), "discovery": value},
        ensure_ascii=False, default=str).encode()}
    from . import operator_inventory_material as material
    raw = expected["discovery.json"]
    record = material.parse(raw)
    binding = view.binding_for(raw, record, context)
    text = view.produce(record, binding)
    records, sources = material.load_sources(directory, context, record["discovery"], view.read_private)
    raw_view = material.append(text, records).encode()
    envelope = {"schema": "cs.semantic_inventory.envelope.v2", **binding,
        "supervisor": context["supervisor"], "view_sha256": hashlib.sha256(raw_view).hexdigest(),
        "view_bytes": len(raw_view), "page_plan": [view._page_text(directory / "inventory-view.jsonl", begin, end)
            for begin, end in view._pages(raw_view)], "workset_sources": sources}
    expected["inventory-view.jsonl"] = raw_view
    expected["inventory-view-envelope.json"] = view.envelope_bytes(envelope)
    expected["inventory-view-progress.json"] = json.dumps(view.progress_value(
        envelope, directory / "inventory-view.jsonl", 0, raw_view)).encode()
    snapshots = {}
    try:
        remaining()
        operator_health.capture(output, value, code, settings.engine_owner_uid)
        snapshots = _publication_snapshot(directory, expected)
        remaining()
        loaded_path, raw_view, envelope = view.load(context)
        expected["inventory-view.jsonl"] = raw_view
        expected["inventory-view-envelope.json"] = view.envelope_bytes(envelope)
        expected["inventory-view-progress.json"] = json.dumps(view.progress_value(
            envelope, directory / "inventory-view.jsonl", 0, raw_view)).encode()
        snapshots = _publication_snapshot(directory, expected)
        if set(snapshots) != set(_PUBLICATION_PATHS) or loaded_path != directory:
            raise ValueError("discovery publication incomplete")
        remaining()
        if legacy_directory is not None:
            legacy_error = None
            try:
                legacy.capture(output, value, code, settings.engine_owner_uid)
            except Exception as exc:
                legacy_error = exc
            raw = view.read_private(legacy_directory / legacy_name)
            record = json.loads(raw)
            ancestry = record.get("ancestry")
            if (record.get("nonce") != os.environ.get("CS_OPERATOR_ACCEPTANCE_NONCE")
                    or record.get("owner_uid") != settings.engine_owner_uid
                    or record.get("argv") != operator_health.ARGV
                    or record.get("cli_identity") != operator_health.identity(os.getpid())[0]
                    or record.get("supervisor_identity") != json.loads(os.environ["CS_OPERATOR_DISCOVERY_SUPERVISOR"])
                    or record.get("kernel_source_digest") != legacy.package_digest()
                    or record.get("output") != output.decode() or record.get("output_length") != len(output)
                    or record.get("output_sha256") != hashlib.sha256(output).hexdigest()
                    or record.get("exit_code") != code or record.get("discovery") != json.loads(output)
                    or not isinstance(ancestry, list) or not 4 <= len(ancestry) <= 32
                    or {key: ancestry[0][key] for key in ("pid", "started_ticks")} != record["cli_identity"]
                    or {key: ancestry[2][key] for key in ("pid", "started_ticks")} != record.get("native_identity")
                    or {key: ancestry[-1][key] for key in ("pid", "started_ticks")} != record["supervisor_identity"]
                    or any(ancestry[index]["ppid"] != ancestry[index+1]["pid"] for index in range(len(ancestry)-1))
                    or record.get("wrapper") != legacy.extract_wrapper(ancestry[1]["argv"])
                    or record.get("claude_sha256") != legacy.CLAUDE_SHA256
                    or record.get("claude_version") != legacy.CLAUDE_VERSION):
                raise ValueError("legacy discovery record binding differs")
            worker = record.get("capture_worker_identity")
            if not isinstance(worker, dict) or set(worker) != {"pid", "started_ticks"}:
                raise ValueError("legacy capture worker identity missing")
            try:
                actual_worker = operator_health.identity(worker["pid"])[0]
            except FileNotFoundError:
                actual_worker = None
            if actual_worker == worker:
                raise ValueError("legacy capture worker cleanup incomplete")
            legacy_expected[legacy_name] = raw
            legacy_snapshots = _publication_snapshot(legacy_directory, legacy_expected, (legacy_name,))
            if legacy_error is not None:
                raise ValueError("legacy capture raised after publication") from legacy_error
            remaining()
        if time.monotonic() >= result["final_deadline"]:
            raise TimeoutError("discovery final deadline")
        return (output.decode() if legacy_directory is not None else output.decode() + "Ordinary discovery artifact: " + str(directory / "discovery.json") + "\n"), code
    except Exception as exc:
        try:
            snapshots = _publication_snapshot(directory, expected)
        except Exception:
            pass
        legacy_contained = True
        if legacy_directory is not None:
            legacy_contained = _publication_withdraw(legacy_directory, legacy_identity,
                legacy_expected, legacy_snapshots, result["final_deadline"], exclusive_writer=True,
                names=(legacy_name,))
        contained = _publication_withdraw(directory, directory_identity, expected, snapshots,
            result["final_deadline"], exclusive_writer=True) and legacy_contained
        print("Scheduled discovery publication failed; containment " +
              ("complete" if contained else "UNVERIFIED; retain exact run artifacts in " + str(directory)),
              file=sys.stderr, flush=True)
        raise ValueError("discovery publication failed") from exc


def scheduled_command():
    import sys
    result = _scheduled_discovery()
    if result["normal"]:
        try:
            text, code = _publish_discovery(result)
            sys.stdout.write(text)
            sys.stdout.flush()
            return code
        except Exception:
            pass
    value = dict(result.get("value") or _discovery_incomplete({}, "scheduled discovery publication incomplete"))
    value.update(read_incomplete="scheduled discovery publication incomplete", assignment_incomplete=True)
    if "triage_workset" in value:
        value["triage_workset"] = {"complete": False, "limit": 2, "selected": [],
            "reason": "scheduled_workset_incomplete"}
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    return 3


def _discovery_worker(payload):
    import os
    from pathlib import Path
    from . import config
    from .operator_health import ARGV, identity, private
    from .review import _save_checkpoint
    binding = payload["binding"]
    path = Path(payload["path"])
    private(path.parent, True)
    if (set(binding) != {"version", "attempt", "uid", "parent", "argv", "worker"}
            or binding["version"] != 1 or binding["uid"] != os.getuid()
            or not isinstance(binding["attempt"], str) or len(binding["attempt"]) != 64
            or binding["argv"] != ARGV or binding["worker"] != identity(os.getpid())[0]
            or binding["parent"] != identity(os.getppid())[0]
            or Path(f"/proc/{os.getppid()}").stat().st_uid != os.getuid()
            or os.getpgrp() != os.getpid() or path.parent.resolve() != path.parent
            or path.name != "checkpoint.json"):
        raise ValueError("discovery worker identity differs")
    deadline = payload["deadline"]
    if type(deadline) not in (float, int) or not time.monotonic() < deadline <= time.monotonic() + 510:
        raise ValueError("discovery worker deadline differs")
    context_raw = os.environ.get("CS_OPERATOR_HEALTH_CONTEXT")
    if context_raw:
        context = json.loads(context_raw)
        if not isinstance(context, dict) or context.get("workset_enabled") is not True:
            raise ValueError("scheduled discovery context malformed")
    settings = config.load()
    out = {"configuration": _discovery_configuration(settings)}
    def checkpoint(observation, phase):
        out["observation"] = observation
        _save_checkpoint(path, {"binding": binding, "out": _discovery_encode(out),
                               "phase": phase, "complete": False})
    completion_deadline = payload["completion_deadline"]
    if type(completion_deadline) not in (float, int) or not deadline < completion_deadline <= time.monotonic() + 510:
        raise ValueError("discovery completion bound differs")
    value = sweep(settings, 14, deadline=deadline, owned_process_group=os.getpid(),
                  checkpoint=checkpoint, completion_deadline=completion_deadline)
    if time.monotonic() >= completion_deadline:
        raise TimeoutError("discovery rendering deadline")
    value["crm_note"] = None
    out.update(result=value, code=3 if value.get("read_incomplete") or value.get("assignment_incomplete") else 0)
    json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if time.monotonic() >= completion_deadline:
        raise TimeoutError("discovery output deadline")
    _save_checkpoint(path, {"binding": binding, "out": _discovery_encode(out), "phase": "complete", "complete": True})
    return out["code"]


def _discovery_main():
    import os
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != "--worker":
        return 3
    try:
        descriptor = int(sys.argv[2])
        with os.fdopen(descriptor, "rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            return 3
        return _discovery_worker(json.loads(raw))
    except Exception:
        return 3


if __name__ == "__main__":
    raise SystemExit(_discovery_main())
