#!/usr/bin/env python3
"""A draft carries a verdict, and the verdict comes from the mailbox.

The incident this gate is written from: a reply sat in the review queue, the
customer had written again in the meantime, and `/cs-review` presented the draft
as ready to send. Nothing in the pipeline could have caught it — `cs review`
listed both draft stores raw, and `/cs-triage-mail`'s candidate feed
(`cs unanswered`) drops a conversation as soon as a real message of ours follows
the customer's last one, so the thread was not a candidate anywhere.

Asserted here, over fixture dicts (no engine, no mailbox, no network):

  A. The three signals fire on the right side of the draft's own timestamp: a
     LATER inbound is `overtaken`, an EARLIER one is not; a LATER send of ours
     is `superseded`, an earlier one is not; the engine's settled verdict is
     `settled`; nothing at all is `ready`.
  B. Precedence: the customer having written since outranks everything, because
     it is the one signal that can change what the answer should be.
  C. Two copies of ONE logical draft — the engine composed it, `cs draft-reply`
     mirrored it into Gmail — are ONE row carrying BOTH handles, and the
     comparison uses the EARLIER of the two timestamps (the mirror lands seconds
     later, and a message that arrived in between must not read as older).
  D. Degradation is a note, never an exception, and never a verdict: an engine
     that will not answer, a mailbox read that raises, a draft with no date —
     each leaves the row `ready` (nothing is silently retired) and says so.
  E. `review.gather` carries the verdict into `--json` and `review.render`
     prints the two blocks with the handles, in English.
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cs import draft_state, review  # noqa: E402

fails = 0
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def check(cond, msg: str) -> None:
    global fails
    if not cond:
        print(f"  FAIL: {msg}")
        fails += 1


def at(hours: int) -> datetime:
    return NOW - timedelta(hours=hours)


def hdr(dt: datetime) -> str:
    return format_datetime(dt)


def gmail(uid="101", to="cust@example.test", subject="Re: invoice",
          when=None, key="<t1@example.test>"):
    return {"uid": uid, "to": to, "subject": subject,
            "date": hdr(when or at(6)), "message_id": "<d1@local>",
            "references": key, "in_reply_to": key, "thread_key": key}


BODY = ("Buongiorno, la fattura è stata emessa ieri e le arriva in giornata. "
        "Le confermo anche il rinnovo.")


def engine(id="eng-1", to="cust@example.test", subject="Re: invoice",
           when=None, key="<t1@example.test>", body=None):
    return {"id": id, "to_addresses": [to], "subject": subject,
            "created_at": (when or at(6)).replace(tzinfo=None).isoformat(),
            "thread_id": key, "in_reply_to": key, "references": [key],
            "body": body if body is not None else BODY}


def run(gmail_rows, engine_rows, *, inbound=None, sent=None, settled=None,
        delivered=None):
    return draft_state.reconcile(
        None, gmail_rows, engine_rows,
        inbound=inbound or (lambda s, a, after=None: []),
        sent=sent or (lambda s, a, days=None: []),
        settled=settled or (lambda s, keys: ({}, None)),
        # Never the real reader: a test that reaches IMAP is not a test.
        # `(match, note)` is the module's degradation shape, same as `settled`.
        delivered=delivered or (lambda s, a, b: (None, None)),
        now=NOW,
    )


class Settled:
    def __init__(self, at_ts, reason="they thanked us"):
        self.at = at_ts
        self.reason = reason


# ------------------------------------------------------------------ A + B

def _verdicts() -> None:
    rows, notes = run([gmail()], [])
    check(rows[0]["verdict"] == "ready",
          f"no signal is ready, got {rows[0]['verdict']}")
    check(not notes, f"a clean run carries no note, got {notes}")

    # An inbound AFTER the draft: the reader is told what it is and when.
    rows, _ = run([gmail()], [],
                  inbound=lambda s, a, after=None: [{"date": hdr(at(2))}])
    check(rows[0]["verdict"] == "overtaken",
          f"a later inbound is overtaken, got {rows[0]['verdict']}")
    check("wrote again" in (rows[0]["signal"] or ""),
          f"the signal says what happened, got {rows[0]['signal']!r}")
    check((rows[0]["signal_at"] or "").startswith("2026-08-27T10:00"),
          f"the signal is dated, got {rows[0]['signal_at']!r}")

    # `inbound_since` filters by `after` itself — an EARLIER message never
    # reaches this module, and an empty list must stay `ready`.
    rows, _ = run([gmail()], [], inbound=lambda s, a, after=None: [])
    check(rows[0]["verdict"] == "ready",
          "an inbound older than the draft is not a signal")

    # A send of ours AFTER it: somebody answered another way.
    rows, _ = run([gmail()], [],
                  sent=lambda s, a, days=None: [{"date": hdr(at(1))}])
    check(rows[0]["verdict"] == "superseded",
          f"a later send is superseded, got {rows[0]['verdict']}")
    # And one BEFORE it is not — `sent_to` windows by days, not by the draft.
    rows, _ = run([gmail()], [],
                  sent=lambda s, a, days=None: [{"date": hdr(at(30))}])
    check(rows[0]["verdict"] == "ready",
          f"a send older than the draft is not a signal, got {rows[0]['verdict']}")

    # The engine's own reading, keyed by thread.
    rows, _ = run([gmail()], [],
                  settled=lambda s, keys: (
                      {"<t1@example.test>": Settled(int(at(5).timestamp()))}, None))
    check(rows[0]["verdict"] == "settled",
          f"the engine verdict lands as settled, got {rows[0]['verdict']}")
    check("they thanked us" in (rows[0]["signal"] or ""),
          f"the engine's own reason is carried, got {rows[0]['signal']!r}")
    # A verdict about ANOTHER conversation never reaches this draft.
    rows, _ = run([gmail()], [],
                  settled=lambda s, keys: ({"<other@example.test>": Settled(0)}, None))
    check(rows[0]["verdict"] == "ready",
          "a settled verdict on a different thread is not this draft's")

    # Precedence: their own message outranks both of the others.
    rows, _ = run([gmail()], [],
                  inbound=lambda s, a, after=None: [{"date": hdr(at(2))}],
                  sent=lambda s, a, days=None: [{"date": hdr(at(1))}],
                  settled=lambda s, keys: (
                      {"<t1@example.test>": Settled(int(at(5).timestamp()))}, None))
    check(rows[0]["verdict"] == "overtaken",
          f"the customer writing since outranks the rest, got {rows[0]['verdict']}")


# ---------------------------------------------------------------------- C

def _pairing() -> None:
    """One logical draft, two stores, one row — and the earlier timestamp."""
    rows, _ = run([gmail(when=at(5))], [engine(when=at(5) - timedelta(minutes=2))])
    check(len(rows) == 1, f"the two copies are ONE row, got {len(rows)}")
    check(rows[0]["gmail_uid"] == "101" and rows[0]["engine_id"] == "eng-1",
          f"the row carries both handles, got {rows[0]}")

    # A message that arrived BETWEEN the engine's compose and the Gmail mirror
    # is later than the engine copy: with the wrong timestamp it reads as older
    # than the draft and no signal fires.
    between = at(5) - timedelta(minutes=1)
    rows, _ = run([gmail(when=at(5))], [engine(when=at(5) - timedelta(minutes=2))],
                  inbound=lambda s, a, after=None: (
                      [{"date": hdr(between)}] if after and between > after else []))
    check(rows[0]["verdict"] == "overtaken",
          "the comparison uses the EARLIER of the two timestamps")

    # Two DIFFERENT drafts to the same contact stay two rows: one has a handle
    # the other does not, and a merged row loses one of them.
    rows, _ = run([gmail(uid="101", key="<t1@example.test>"),
                   gmail(uid="102", key="<t2@example.test>")], [])
    check(sorted(r["gmail_uid"] for r in rows) == ["101", "102"],
          f"two conversations are two rows, got {rows}")


# ---------------------------------------------------------------------- D

def _degradation() -> None:
    def boom(*a, **kw):
        raise RuntimeError("mailbox on fire")

    rows, notes = run([gmail()], [], inbound=boom)
    check(rows[0]["verdict"] == "ready",
          "a failed read never invents a verdict — the draft stays as it was")
    check(any("mailbox on fire" in n for n in notes),
          f"and the failure is a NOTE, got {notes}")

    rows, notes = run([gmail()], [],
                      settled=lambda s, keys: ({}, "Method not found"))
    check(rows[0]["verdict"] == "ready", "an engine that cannot answer costs no verdict")
    check(any("Method not found" in n for n in notes),
          f"the engine degradation is named, got {notes}")

    no_date = gmail()
    no_date["date"] = None
    rows, notes = run([no_date], [])
    check(rows[0]["verdict"] == "ready" and notes,
          f"a draft with no date is reported, not judged: {rows[0]}, {notes}")

    ready, re_decide = draft_state.split(
        [{"verdict": "ready"}, {"verdict": "overtaken"}, {"verdict": "settled"},
         {"verdict": "duplicate"}])
    check(len(ready) == 1 and len(re_decide) == 3,
          f"split() groups the two blocks, got {len(ready)}/{len(re_decide)}")


# ------------------------------------------------------------- duplicates

def _duplicates() -> None:
    """A draft whose text is already in Sent is a SECOND COPY, not a draft the
    conversation moved past. It is the case that made 15 stale drafts on one
    mailbox unreadable: every one of them was labelled `overtaken`."""
    def delivered_hit(s, a, b):
        return {"date": hdr(at(3)), "subject": "Re: invoice",
                "message_id": "<sent-1@local>"}, None

    rows, notes = run([], [engine()], delivered=delivered_hit)
    check(rows[0]["verdict"] == "duplicate",
          f"an already-delivered body is duplicate, got {rows[0]['verdict']}")
    check("already delivered" in (rows[0]["signal"] or ""),
          f"the signal says what happened, got {rows[0]['signal']!r}")
    check((rows[0]["signal_at"] or "").startswith("2026-08-27T09:00"),
          f"the signal is dated from the delivered copy, got {rows[0]['signal_at']!r}")
    check(not notes, f"a clean duplicate run carries no note, got {notes}")

    # The whole point of the rank: on a thread the customer has replied to,
    # BOTH fire, and "they already have this text" is the one to act on.
    rows, _ = run([], [engine()], delivered=delivered_hit,
                  inbound=lambda s, a, after=None: [{"date": hdr(at(2))}],
                  sent=lambda s, a, days=None: [{"date": hdr(at(1))}])
    check(rows[0]["verdict"] == "duplicate",
          f"duplicate outranks overtaken, got {rows[0]['verdict']}")

    # A one-line courtesy repeats honestly; matching it would call every
    # second thank-you a duplicate.
    seen = []
    rows, _ = run([], [engine(body="Grazie!")],
                  delivered=lambda s, a, b: (seen.append(b), delivered_hit(s, a, b))[1])
    check(rows[0]["verdict"] == "ready" and not seen,
          f"a body under the floor is never compared, got {rows[0]['verdict']}")

    # Headers-only Gmail rows carry no text: no body, no comparison, no read.
    asked = []
    rows, _ = run([gmail()], [],
                  delivered=lambda s, a, b: (asked.append(a), (None, None))[1])
    check(not asked, "a Gmail-only draft has no body to compare — do not read")

    # A limit the reader hit is REPORTED. A silent cap reads as "checked
    # everything" when it did not, and the operator would take a missing
    # `duplicate` for a clean bill.
    rows, notes = run([], [engine()],
                      delivered=lambda s, a, b: (None, "read the newest 20 of 57"))
    check(rows[0]["verdict"] == "ready" and any("newest 20" in n for n in notes),
          f"a truncated scan must say so: {notes}")

    # A mirrored draft is ONE row, and the engine copy's body must survive the
    # pairing or the pair silently loses the check.
    rows, _ = run([gmail()], [engine()], delivered=delivered_hit)
    check(len(rows) == 1 and rows[0]["verdict"] == "duplicate",
          f"a paired row keeps the engine body, got {rows}")

    # A body at the normalisation cap is not compared at all: two long mails
    # sharing a 4000-character prefix normalise equal, and a false `duplicate`
    # on a draft that only STARTS like a delivered mail is worse than none.
    from cs import gmail_archive

    long_body = "x" * (gmail_archive.BODY_MAX + 50)
    match, note = gmail_archive.sent_body_match(None, "cust@example.test", long_body)
    check(match is None and note and "too long to compare" in note,
          f"an over-cap body must be refused and reported, got {note!r}")

    # Degradation is a note, never an exception and never a verdict.
    def boom(s, a, b):
        raise OSError("imap said no")

    rows, notes = run([], [engine()], delivered=boom)
    check(rows[0]["verdict"] == "ready" and notes,
          f"a failed body read is a note, not a verdict: {rows[0]}, {notes}")

    # One read per (contact, body), not one per draft.
    calls = []
    run([], [engine(id="eng-a"), engine(id="eng-b")],
        delivered=lambda s, a, b: (calls.append(a), (None, None))[1])
    check(len(calls) == 1, f"the read is cached per contact+body, got {calls}")


# ---------------------------------------------------------------------- E

def _review_surface() -> None:
    settings = types.SimpleNamespace(
        excluded_campaign_set=set(), db_path="/nonexistent/cs.db",
        timezone="Europe/Rome", log_path=Path("/nonexistent/cs_operator.log"))

    g, e = [gmail()], [engine(id="eng-9", key="<t9@example.test>")]

    def _list_drafts(_s):
        return g

    def _call_sync(_s, method, params=None, **kw):
        if method == "drafts.list":
            return e
        raise RuntimeError("no engine in this test")

    real_reconcile = draft_state.reconcile

    def _reconcile(_s, gd, ed, **kw):
        return real_reconcile(
            None, gd, ed,
            inbound=lambda s, a, after=None: [{"date": hdr(at(1))}],
            sent=lambda s, a, days=None: [], settled=lambda s, keys: ({}, None),
            now=NOW)

    orig = (review.gmail_drafts.list_drafts, review.rpc.call_sync,
            review.draft_state.reconcile, review.campaign.list_campaigns)
    review.gmail_drafts.list_drafts = _list_drafts
    review.rpc.call_sync = _call_sync
    review.draft_state.reconcile = _reconcile
    review.campaign.list_campaigns = lambda _s: []
    try:
        d = review.gather(settings)
    finally:
        (review.gmail_drafts.list_drafts, review.rpc.call_sync,
         review.draft_state.reconcile, review.campaign.list_campaigns) = orig

    check("drafts" in d, "gather() carries the reconciled list into --json")
    check(all("verdict" in r for r in d["drafts"]),
          f"EVERY draft row carries a verdict: {d['drafts']}")
    check({r["verdict"] for r in d["drafts"]} == {"overtaken"},
          f"the verdict is the computed one, got {d['drafts']}")
    check(len(d["gmail_drafts"]) == 1 and len(d["engine_drafts"]) == 1,
          "the raw store listings are still there for the callers that need them")

    out = review.render(d)
    check("Drafts ready to send (0)" in out,
          f"an overtaken draft is NOT in the ready block:\n{out}")
    check("Drafts to re-decide (2)" in out,
          f"both rows land in the re-decide block:\n{out}")
    check("uid 101" in out and "engine eng-9" in out,
          f"each row prints the handle it is retired by:\n{out}")
    check("overtaken:" in out, f"the row states which signal fired:\n{out}")
    for italian in ("Bozze", "servono te", "Campagne", "Ultimo tick"):
        check(italian not in out, f"the kernel digest is English, found {italian!r}")


_verdicts()
_duplicates()
_pairing()
_degradation()
_review_surface()

if fails:
    print(f"test_draft_state: {fails} assertion(s) FAILED")
    sys.exit(1)
print("test_draft_state: all assertions passed")
