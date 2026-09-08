---
status: completed
brief: docs/briefs/2026-09-07-review-latency.md
---

# Plan — `cs review` latency and the three wrong verdicts

Four milestones. An earlier draft of this plan split the cache fixes from the
bulk read; that split was wrong and is corrected below — they are one change
seen twice.

## Dependencies

| Milestone | Depends on | Why |
|---|---|---|
| M1 | — | Self-contained: the `_fetch_headers` change, the `BCC` field, and the `FakeIMAP` extension that tests them |
| M2 | **M1** | Consumes `_fetch_headers` through the new bulk reader, and needs M1's `FakeIMAP` chunked-FETCH support to test anything |
| M3 | **M2** *(for its latency gate only)* | `sent_body_match`'s code is independent — it runs through the `delivered` seam (`cs/draft_state.py:308`), keyed `(addr, body)` at `:338`, not through either address-keyed cache M2 removes. But its latency gate measures the total against M1–M2's ~14s, so Step 4 cannot run before M2 lands |
| M4 | — | Independent |

Criterion 1 is owned by **M3 Step 4** and by nothing else. § Verification of the
whole re-runs it as the final end-to-end check; that is confirmation, not a
second owner.

## M1 — DONE — `_fetch_headers` reports a failed chunk instead of discarding 200 messages

**Correcting this plan's earlier justification.** An earlier draft claimed M1
must land first because M3 moves the dedup gates' readers onto `_fetch_headers`,
making a chunk drop a § 5 fail-open. **That move does not happen.** The brief is
explicit that `sent_to_on` and `inbound_since_on` stay exactly as they are —
they back the unbounded "have we ever written" gates — and `_fetch_headers` has
exactly two callers today, `inbound_recent` (`cs/gmail_archive.py:347`) and
`sent_recent` (`:580`). `sent_to_on` fetches per UID via `_hdr` (`:112`) and
keeps doing so. So the dedup gates are never exposed to the chunk drop, and
criterion 7b's clause about `sent_to_across` failing "because a chunk failed" is
**unassertable and must be reworded**.

**The fix is still required**, for the new bulk reader M2 introduces: a chunk
drop there silently removes up to 200 messages from `reconcile`'s evidence,
which the brief's ban on silent limits forbids and which would let a draft read
`ready` on an absence nobody established.

**Change.**
1. `cs/gmail_archive.py:66-67` — **raise** on a non-OK FETCH instead of
   `continue`. The shape is specified here because the two candidates are not
   equivalent:
   - *Returning* a count or tuple breaks `for h in _fetch_headers(M, ids)` at
     both `:347` and `:580`, and neither caller has a note channel to put it in
     — both return plain lists (`:367`, `:598`). The failure would be swallowed
     one level up, recreating the silent drop this milestone exists to remove.
   - *Raising* reaches the verbs, which is the point.
2. **`cs review` degrades as it already does.** `cs/review.py:87-91` wraps the
   call and turns a failure into a local note with no shared meaning. Nothing to
   change beyond confirming it still holds.
3. **`cs unanswered` needs a NEW degradation channel — reusing `note` fails
   open.** `cs/unanswered.py:520-521` calls `inbound_recent` and `sent_recent`
   **bare** inside `sweep()` (`:510`), and `cs/cli.py:380` calls `sweep()` with
   **no `try`**, so M1 would otherwise turn a silent narrowing into a traceback.
   But routing the failure into the existing `note` is worse than the traceback,
   not better:

   `note` is a contract with one meaning. Its docstring (`:515-517`) says it is
   non-None *only* when the engine could not answer, "in which case those
   threads are read exactly as they were before the engine was ever asked —
   every message needing a reply", and `cs/cli.py:501-507` **hardcodes** that
   cause: `(engine unavailable: {note} — no autoresponder was recognised, so
   every message reads as needing a reply)`.

   Engine-down **over**-reports: fail-closed, which is what that sentence
   promises. A failed mailbox read **under**-reports: messages are absent from
   the sweep entirely. Putting the second into the first prints a reassuring,
   conservative-sounding explanation over a list that is silently short — on the
   one verb whose whole output is who is still waiting. That is
   `cs/mailboxes.py:1-16` and § 5's "an unreadable mailbox is not a 'no'", and
   it is worse than a traceback because a traceback is honest.

   So M1 adds: a **distinct key**, not `note`; a renderer branch in `cs/cli.py`
   whose printed cause matches what actually happened; an explicit refusal to
   present the open list as complete; and the `:515-517` docstring corrected so
   the contract still describes reality.

**Scope extension, stated rather than sprung at review.** This makes M1 edit
`cs/unanswered.py` and `cs/cli.py`, which the brief's § Scope does not list. The
work follows from the brief's own contract change, which never traced its
consumers — but the extension is recorded here rather than arriving as a
surprise.
4. `BCC` added to `_fetch_headers`'s field list (`:64`). It lands here, not in
   M2, because it is **provably inert for both existing callers**:
   `inbound_recent` never reads `To`/`Cc`/`Bcc` (`:348-364`) and `sent_recent`
   buckets on a hard-coded `getaddresses([To, Cc])` (`:586`), which a new header
   cannot leak into.
5. **Extend `FakeIMAP` for chunked and non-OK FETCH.** Today its FETCH branch
   parses a single sequence id — `i = int(args[0].decode()) - 1`
   (`tests/test_send_gates_fanout.py:148`) — against `_fetch_headers`'s
   comma-joined batch (`cs/gmail_archive.py:60`), and returns `"OK"`
   unconditionally (`:157`). Without this M1 cannot test its own change, so the
   double extension belongs to the milestone that first needs it, not to M2.

**Verification.** Criterion 7b, reworded to its assertable form: a `FakeIMAP`
test drives a non-OK FETCH through `_fetch_headers` and asserts the affected
messages surface as a degradation rather than vanishing. The `sent_to_across`
clause is dropped, because that path does not use `_fetch_headers`.

**Plus one test per consumer**, since asserting only on `_fetch_headers` covers
neither. Each asserts the **printed cause**, not merely that nothing raised —
the whole defect above is a correct-looking degradation carrying the wrong
explanation, which a "did not raise" assertion passes:
- `cs review` still degrades to its local note.
- `cs unanswered` does not raise out of `cs/cli.py:380`, does not print the
  `engine unavailable … every message reads as needing a reply` line, and does
  say that the open list is incomplete because a mailbox read failed.

**Risk.** Low. Two callers, both in-repo, and the added field is inert for both.

**Landed, with two defects found by adversarial review after the first pass
was already green:**
- The `--json` path — the CRON's path — printed only the `open` rows and
  returned 0, so `read_incomplete` never reached `cs-triage-mail`. A failed
  read produced `[]` with a success code: the original bug surviving in the one
  consumer that runs unattended, and worse than before, since the pre-M1 list
  was partial rather than empty. Fixed: stdout keeps its bare-JSON-list
  contract, the cause goes to stderr, and the verb exits `3`.
- Gate 46b asserted the renderer over a hand-built dict, so the real `except`
  was never driven and flipping `read_incomplete` to `note` still passed.
  Fixed: a test now drives the real `sweep()` with a raising reader.
- Both new gates were then proven to fail when the defect is reintroduced.
- The text path also printed `no unanswered inbound in the last N days` above
  the `!!` footer retracting it; the confident headline is now suppressed.

## M2 — DONE — `reconcile`'s evidence path: bulk read, self-exclusion, and the per-row date filter

**Why this is one milestone and not two.** The earlier draft had the cache bugs
as a separate, independent milestone. They are not independent, and shipping
them separately would be wasted work at best:

- The bulk reader takes an **address list**, and criterion 3 forbids per-contact
  reads — so it rewrites the exact statements a cache-only fix would edit
  (`cs/draft_state.py:385-387`, `:404-406`). The fix would be deleted by the
  next milestone.
- Worse, and this is the load-bearing part: today `inbound_since_on`
  post-filters `dt <= after` (`cs/gmail_archive.py:292`), which is *why* the
  consumer at `cs/draft_state.py:392-402` is a bare `if later_in:` with no date
  test of its own. The bulk read is one `SINCE min(composed_at) − 3d` query,
  **wider than any individual row's `composed_at`**. Bucketing without adding a
  consumer-side date filter therefore converts today's *order-dependent* false
  `overtaken` into an *unconditional* one — a regression, delivered by the
  milestone meant to fix it.

So the per-row date filter is not a detail of the cache fix; it is what replaces
the post-filter the bulk read removes. One milestone owns both.

**Change.**
1. New `Fanout` outcome for a deliberate skip, distinct from `read` and
   `unreadable` (`cs/mailboxes.py:121-123`), surfaced in `scope_line()`
   (`:129-142`) and in `reconcile`'s `notes`.
2. New `reconcile`-only bulk reader per the brief's entry point and row shape,
   with a docstring forbidding send-gate callers.
3. `cs/draft_state.py` consumes it: buckets on `To`+`Cc` with `Bcc` as a
   reporting guard, applies a **per-row `date > composed_at` filter** on both
   the inbound and sent sides, and drops both address-keyed caches — with the
   bulk read done once per run, there is nothing left to cache.

**The `SINCE` bound is `min(composed_at) − 3d`, uncapped — stated here because
the trap is in the file being edited.** `MAX_LOOKBACK_DAYS = 120`
(`cs/draft_state.py:88`) and `_lookback_days` (`:224`) sit in `draft_state.py`
with a docstring inviting reuse. Applying that cap to the bulk `SINCE` would
narrow a 200-day-old draft's window to 120 days and turn a real `overtaken` into
`ready`. The cap is a legitimate POST-filter and an illegitimate PRE-filter; do
not reuse it here.

**The existing fan-out guard must be engaged, not evaded.**
`tests/test_contact_history.py:462-467` asserts that exactly two `*_across`
readers exist, because "readers that decide nothing from 'is this us'" are the
only ones safe to fan out. The new reader **does** use identity — it excludes a
mailbox when the contact is that mailbox — so the guard's rationale genuinely
applies to it. Renaming the function to fall outside the guard's pattern would
make the test pass while retiring the protection, which is the wrong fix.
Instead: extend the guard to include the new reader **and** assert its docstring
carries the send-gate prohibition, so the guard protects the new invariant too.

**Mechanism caveat, or the instruction is satisfiable by doing nothing.** The
guard is a *name scan* — `{n for n in dir(mailboxes) if n.endswith("_across")}`
(`tests/test_contact_history.py:462`). "Extend the guard to include the new
reader" therefore only has force if the new reader **carries the `_across`
suffix**. Name it accordingly; otherwise it silently falls outside the scan and
the guard is retired by omission rather than by decision — the exact outcome
this paragraph exists to prevent.

**Verification.** Criteria 2 (all three corrections), 3, 4, 5, 6, 7, 7c.
- Criterion 5 needs a new fixture whose contact is also a mailbox — none exists
  (`tests/test_send_gates_fanout.py:82`, `tests/test_contact_history.py:94`) —
  asserting **neither** own-mailbox read happens.
- Correction (c) needs two draft rows, since `overtaken` is tested first
  (`cs/draft_state.py:399-402`) and outranks `superseded` (`:72`).
- Criterion 2's "no other row moves" clause is owned here: a regression test
  over the existing fixtures asserting unchanged verdicts, notes and order.
- `FakeIMAP` needs extending for `OR`-composed SEARCH
  (`tests/test_send_gates_fanout.py:136-140`, which handles only
  `SEARCH <key> <value>`). Its chunked/non-OK FETCH support comes from M1.

**Risk.** The largest change, and the one touching a file the gates import. The
mitigation is that the existing per-address functions are untouched, the new one
is never called from a gate, and both facts are asserted by the extended guard
rather than assumed.

## M3 — DONE — `sent_body_match`: shared session, and fewer bytes

**Opens with a measurement whose abort condition is concrete enough to fire.**

**Step 1, fidelity.** Sample: **every message in production's Sent folder that
any current draft's duplicate check would scan** — the real population, not a
synthetic one — spanning `multipart/alternative`, `multipart/mixed` with
attachments, and single-part plain. For each, compare the `_normalise` output of
(a) the current `BODY.PEEK[]` full fetch through `_body_and_attachments`
(`cs/gmail_archive.py:447-469`) against (b) a `BODYSTRUCTURE`-located text-part
fetch. **"Reproduces" means byte-equal on every sampled message**, because the
comparison at `:211` is exact equality and a single divergence is a missed
`duplicate` — or, if it diverges the other way, a false one.

Note what (b) must replicate: `_body_and_attachments` **joins all plain parts**
and falls back to tag-stripped HTML when there is no plain part. A naive
"fetch part 1" does neither.

**Step 1 must report the structure classes it actually observed, and an absent
class is UNKNOWN — never a pass.** Defining the population by reachability is
reproducible; *asserting* it spans `multipart/alternative`, `multipart/mixed`
and single-part plain is a hope about a population nobody has inspected. The
highest-risk class is the one Step 3 exists for: **no plain part at all**, where
`_body_and_attachments` falls back to tag-stripped HTML
(`cs/gmail_archive.py:467-468`). If the sample happens to contain none, Step 1
passes vacuously, the abort never fires, and the fallback ships unmeasured.

This is the same error the brief already caught in itself: `probe_bcc.py` found
no `Bcc` anywhere in 153 messages and the brief refused to read that absence as
evidence. Apply the same rule here — report the observed classes, and route any
class the sample does not contain to Step 3's degradation path as an unknown.

**Abort condition.** If any sampled message diverges, stop. Do not ship a
degraded comparison. Report the divergence class and renegotiate criterion 1.

**Step 1 re-runs against the shipped code, not against a prototype.** Nothing
binds Step 2's implementation to whatever was measured beforehand, so the
fidelity check is written as an executable test over the real
`sent_body_match` and run again after Step 2.

**Step 2, implement — and the text-part fetch is the point of this milestone.**
Two changes, not one:
1. **Replace `BODY.PEEK[]` (`cs/gmail_archive.py:206`) with a
   `BODYSTRUCTURE`-located text-part fetch.** This is the change that delivers
   the margin. An earlier draft of this plan listed only the shared session in
   this step, which was self-invalidating: Step 1 validates the text-part fetch,
   the brief states criterion 1 is unreachable without it, and the work is
   byte-bound — 7,251 KiB moved either way — so sharing the session alone
   removes 1.22s per call and leaves the other ~1.5s per body untouched.
2. Shared session via `mailboxes.session()` instead of `_imap(settings)` +
   `logout()` (`:198`, `:222-226`).

**Step 3, degradation.** An unexpected MIME structure must produce a **reported
miss, never a false `duplicate`** — the brief's requirement, and the direction
that matters: a missed duplicate costs a re-read, a false one suppresses a reply
the customer is waiting for.

**Step 4, latency — the sole owner of criterion 1.** Fidelity passing does not
imply the target is met, so this is a separate gate run *after* Step 2. Measure
`sent_body_match` across every contact with a draft and confirm the total, added
to M1–M2's measured ~14s, lands under 90s. Requires M2 to have landed.

**One shared-connection constraint, since M2 and M3 both use `session()`.**
`mailboxes.session()` keeps **one connection per address per process**
(`cs/mailboxes.py:312`), so M2's bulk reader and M3's `sent_body_match` share
it and SELECT different folders on it. That is safe only because the bulk read
runs **once, before** the row loop, while `delivered` is called **inside** it
(`cs/draft_state.py:365-383`). Any future change that interleaves them — a
re-read per row, a lazy bulk fetch — makes the two fight over the selected
folder. Do not interleave; if a later change needs to, it needs its own
connection, not a re-SELECT.

Sharing the session **cannot** change which bytes come back, so the fidelity
check is not invalidated by it: the payload of `BODY.PEEK[<spec>]` for a given
(mailbox, UID, spec) is a property of the message, `sent_body_match` re-SELECTs
(`cs/gmail_archive.py:200-201`) and re-SEARCHes (`:202`) inside every call so it
never carries a UID across a session boundary, and `readonly=True` plus PEEK
mutate no flags.

**Risk.** The only milestone that can fail on its own premise, isolated so that
failure costs a renegotiated criterion rather than a rollback.

## M4 — DONE — progress output and explicit timeouts

**Change.** `cs review` emits progress to **stderr**; `--json` on stdout stays
clean (criterion 9). `campaign.contacts` (`cs/review.py:239`) and
`engine_view.settled` get explicit timeouts and appear in that output
(criterion 8).

**Why not optional.** The operator watched this verb emit zero bytes for
fourteen minutes and could not distinguish a slow run from a hang. It was in
fact neither — an instrumented run exceeded 25 minutes without finishing.

## Verification of the whole

Criterion 1 is owned by M3 Step 4. This section re-runs it end to end as
confirmation, not as a second owner: reference clone, cold start,
`cs review --json` under 90 seconds excluding `campaign.contacts` and
`engine_view.settled`. Baseline for comparison: a run that did not finish in
25 minutes.

`bash tests/run.sh` green, including its grep gates.

## Not gated by any criterion, and deliberately so

The brief forbids collapsing the Sent/All-Mail folder split (unsent drafts in
All Mail carry `\Draft` only as an X-GM-LABEL, so `UNDRAFT` will not exclude
them). Criterion 4 permits widening, so it cannot catch this; the protection is
the constraint text and this note. If a future change collapses the two reads,
`superseded` starts being minted from mail nobody received.

## Out of scope, tracked elsewhere

`cs ask` exiting 0 on engine failure has its own brief
(`docs/briefs/2026-09-07-engine-error-exit-code.md`). The engine-side prompt
budget and the campaign-path own-mailbox read are in the brief's § Recorded.


## Outcome — measured on the reference clone

| Stage | `draft_state.reconcile`, 51 rows |
|---|---|
| before | **>1490s — killed by a 1500s timeout, never finished** |
| after M2 (bulk read + self-exclusion + per-row date filter) | 212.7s |
| after M3 step 1 (bounded body prefix) | 104.6s |
| after M3 step 2 (batched body scan) | **54.3s** |

Criterion 1 (under 90s excluding `campaign.contacts` and `engine_view.settled`)
is met. Verdict counts were identical across all three post-M2 runs — 1
`duplicate`, 20 `overtaken`, 14 `superseded`, 16 `ready` — so M3 changed timing
and nothing else, which is what it promised.

**M3's fidelity gate, and what it cost to pass honestly.** Two reconstruction
approaches were measured and both FAILED the abort condition at 120 mismatches
of 120: fetching MIME part 1 alone (an HTML-only message came back as raw markup
treated as plain text — 172 characters became 1633), and fetching it together
with its own MIME header (multipart messages then yielded nothing at all). The
approach that passed reconstructs nothing: fetch a bounded PREFIX of the whole
message and run the existing parser over it unchanged. **0 mismatches of 120**,
1.8% of the bytes, and the truncation it can suffer produces a reported miss
rather than a false `duplicate`, because the comparison is exact equality.

Then the profile inverted: with the bytes small, the 20 per-contact body fetches
became round-trip-bound again, and batching them into one FETCH took 104.6s to
54.3s. The lesson worth keeping is that the same code was byte-bound before the
prefix and round-trip-bound after it, and the fix for each is the opposite of
the fix for the other.
