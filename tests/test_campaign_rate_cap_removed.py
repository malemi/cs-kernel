#!/usr/bin/env python3
"""`send_draft()` no longer blocks on RATE_CAP — anti-regression for the
2026-08-23 removal (see mrcall-cs docs/briefs/2026-08-23-rate-cap-silently-
drops-customers.md): a per-day send quota did not prevent the failure it
existed for, it scaled it down — at the cap the kernel returned a per-contact
refusal and the run carried on, so real contacts were skipped in silence. The
kill-switch (CS_PAUSE) plus contradiction-triggered pause replace it; no
volume-based throttle remains on any send path.

We stub `cs.rpc.call_sync` (engine transport) and the mailbox fan-out
(the Sent-archive dedup ground truth) — no live engine, no live Gmail — and
drive `campaign.send_draft()` directly in CS_TRIAGE_MODE=send, dry-run
(commit=False), for a contact who has never been mailed. Before the removal
this call went through `_rate_capped()`, which read
`state.State(settings.db_path).sent_today()` — a real sqlite db this test
deliberately does NOT provide on the fake settings object, so if the cap
check were still wired in, this call would raise (missing `db_path`) rather
than return cleanly; either way proves the mechanism is gone.
"""
from __future__ import annotations

import types
from pathlib import Path

from cs import campaign, rpc
from cs import mailboxes as mailboxes_mod

def _fan(rows=()):
    """The cross-mailbox fan-out's shape: rows plus the scope they came from.
    The gates below moved onto `cs/mailboxes.py` when prior-contact evidence
    stopped being one mailbox; the scope is complete here, because what these
    cases vary is never the mailbox."""
    from cs import mailboxes as mailboxes_mod

    return mailboxes_mod.Fanout(rows=list(rows), read=["ops@example.test"],
                                unreadable=[])



def main() -> int:
    calls: list[tuple] = []

    def fake_call_sync(settings, method, params, timeout=None):
        calls.append((method, params))
        if method == "campaign.list":
            return [{"id": "camp-1", "name": "trial-campaign"}]
        if method == "campaign.contacts":
            return [{
                "id": "contact-1", "email": "person@example.test",
                "state": "drafted", "draft_subject": "Hello",
                "draft_body": "A hand-written note.", "dossier": {},
            }]
        raise AssertionError(f"unexpected RPC call in a dry run: {method} {params}")

    rpc.call_sync = fake_call_sync
    # never mailed before, from any mailbox in scope
    mailboxes_mod.sent_to_across = lambda settings, email, days=None: _fan()

    settings = types.SimpleNamespace(
        dedup_days=30,
        pause_path=Path("/nonexistent-cs-pause-test-dir/CS_PAUSE"),  # CS_PAUSE inactive
        cs_triage_mode="send",
        # deliberately NO db_path: proves _rate_capped()'s State(db_path) read
        # is no longer on this path at all.
    )

    out = campaign.send_draft(settings, "contact-1", commit=False)

    assert out.get("ok") is True, f"send_draft refused: {out}"
    assert out.get("mode") == "send", out
    assert out.get("dry_run") is True, out
    assert "blocked" not in out, f"send_draft still blocks: {out}"
    assert not hasattr(campaign, "_rate_capped"), \
        "_rate_capped() should be fully removed from cs/campaign.py"

    assert ("campaign.list", {}) in calls, calls

    print("test_campaign_rate_cap_removed: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
