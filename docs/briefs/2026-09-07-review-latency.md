# Brief — `cs review`: a contact who is also a mailbox costs 21,637 round trips

## Intent

`cs review --json` does not return within a usable time. On the `124-cs` clone
it was killed after ~14 minutes having emitted zero bytes. It is step 4c of the
`/cs-operator` bootstrap, so an unattended tick cannot report which waiting
drafts are still right and which the conversation has moved past — the one
question that step exists to answer.

Make the pass complete in a time an operator will wait for, and fix the three
wrong verdicts found while measuring it.

## Scope of the reference clone

51 engine drafts + 12 Gmail drafts → **54 logical rows, 25 unique recipients,
38 thread keys, 4 readable mailboxes** (`production@`, `mario.alemi@`,
`ivan.marchese@`, `riccardo.cargnel@`).

## Root cause — one contact is also one of the mailboxes

**`riccardo.cargnel@cafe124.it` is both a draft recipient and one of the 4
fan-out mailboxes.** Measured on his All Mail folder (scratchpad
`probe_anomaly.py`):

```
messages in folder (ALL):                 35,944
FROM riccardo.cargnel@cafe124.it:         21,637   ← his own entire sent history
all 24 other contacts combined:               49
```

`inbound_since_on(M, "riccardo.cargnel@cafe124.it", after)` run against
riccardo's **own** mailbox searches `FROM riccardo` (`cs/gmail_archive.py:276`,
unbounded — no `SINCE`) and matches every message he has ever sent, then issues
**one `_hdr()` FETCH round trip per UID** (`:279-280`, literally
`for uid in ids: h = _hdr(M, uid)`).

**The `after` argument does not help.** It is applied at `:292`, *after* the
`_hdr()` call at `:280` — a post-filter on the parsed Date header. So all 21,637
headers are fetched one at a time no matter how recent the draft is. That single
(contact, mailbox) pair is the 14 minutes; nothing else in `reconcile` is close.

The function's own docstring (`:269-271`) states the safety argument that fails
here: *"Fannable across mailboxes because it names no self: it matches FROM the
contact and reads nothing from `settings.email_address`."* True as written — it
hardcodes no self — but the fan includes mailboxes that ARE contacts, and for
those the read degenerates into "everything this person ever sent".

### It is a wrong verdict, not only a slow one

Each of those 21,637 messages satisfies "wrote again after this draft was
composed", so the draft is marked `overtaken` (`cs/draft_state.py:399-401`)
because riccardo mailed *somebody* — not because he replied to us. `overtaken`
exists to ask whether the contact has written **to us**; a person's own outbox
cannot answer that. Any draft to a colleague whose mailbox is in scope is
therefore essentially always `overtaken`, on evidence that means nothing.

### Why excluding the contact's own mailbox loses no evidence

The exclusion is safe, not merely fast, and this is the reasoning that makes it
so. A message from riccardo that is genuinely "written to us" is held by the
**recipient's** All Mail as well as by his own, and every in-scope recipient is
already in the fan. So the exclusion drops only:

- self-addressed mail (not "written to us");
- mail to an in-scope mailbox that could not be opened — already covered by
  `evidence_incomplete`;
- mail sent *out* of scope, which is precisely not "written to us".

**The exclusion applies to both folders, not only All Mail.** An earlier draft
left the `sent` side alone on the grounds that it "touches the side the send
gates read" — that reason died with the location decision below: `reconcile`
gets its own reader and never touches the gates. And the measured design
already excludes self on both (`probe_bulk2.py` shows riccardo's Sent read at
24 addresses). So `sent_to_on(M_riccardo, riccardo)` goes too: a self-addressed
message passes the date re-filter at `cs/draft_state.py:411-416` and yields a
false `superseded`. That is a **third** verdict correction, and criterion 2
accounts for it explicitly.

### The measured post-fix shape

One `SINCE`-bounded `OR`-composed SEARCH per (mailbox, folder), whose **address
list omits that mailbox's own address**, then one chunked `_fetch_headers` over
the result, bucketed by address in memory. Measured end to end
(`probe_bulk2.py`, `SINCE` = oldest draft − 3d = 79 days back, uncapped):

```
production@cafe124.it     Sent  TO    25 addrs     34 uids   0.7s + 0.3s
production@cafe124.it     All   FROM  25 addrs     36 uids   0.7s + 0.2s
mario.alemi@cafe124.it    Sent  TO    25 addrs     62 uids   0.6s + 0.6s
mario.alemi@cafe124.it    All   FROM  25 addrs     89 uids   0.5s + 0.3s
ivan.marchese@cafe124.it  Sent  TO    25 addrs     38 uids   0.6s + 0.2s
ivan.marchese@cafe124.it  All   FROM  25 addrs    101 uids   0.6s + 0.8s
riccardo.cargnel@…        Sent  TO    24 addrs      3 uids   0.4s + 0.1s  ← self excluded
riccardo.cargnel@…        All   FROM  24 addrs     31 uids   0.4s + 0.2s  ← self excluded

TOTAL: 7.2s
```

**394 UIDs across all eight reads**, against 21,686 for the same union. Round
trips are bounded by (mailbox × folder), not by contacts or drafts, which is
what criterion 3 requires.

**Two changes produce that reduction, not one.** The self-exclusion removes
riccardo's 21,637; the uncapped `SINCE` removes a further slice — in his All
Mail the other 24 contacts go from 49 UIDs unbounded to 31 under the 79-day
bound. Do not attribute the whole drop to the exclusion.

**The bucketing predicate is `To` + `Cc`, and this was settled by measurement
after a wrong guess.** Moving from `SEARCH TO` to in-memory bucketing moves the
predicate from the server to our own parse, so the two must be shown to agree.
Two read-only probes established what the server actually does:

- **Loose matching is refuted** (`probe_match_semantics.py`). Searching for a
  substring of each contact's address matched **0 messages for 0 of 25
  contacts**, so a superstring address or a display name containing the address
  does not silently count today.
- **But `SEARCH TO` already matches `Cc`** (`probe_where.py`). Across every
  `SEARCH TO` hit in production's Sent folder, the address was found in
  **To: 37, Cc: 14, Bcc: 0, nowhere: 0**. Twenty-seven percent of hits have the
  contact only in Cc.

So an earlier draft of this brief was wrong: it chose `To` only, reasoning that
this matched the server predicate, and that choice would have **narrowed the
evidence by 27%** — dropping real `superseded` signal, which is the dangerous
direction. `sent_recent`'s `getaddresses([To, Cc])` (`:584-588`) is the correct
precedent after all, and copying it is faithful reproduction, not widening.

**The inbound side is measured too, not reasoned about.** An earlier draft
dismissed it with "`FROM` is a single header" — which is the same RFC-based
reasoning that had just been refuted on the `TO` side, and therefore worth
nothing. Once Gmail is shown not to follow RFC field semantics on `TO`, the RFC
stops being evidence about `FROM`, and `Sender:`, `Reply-To:` and
`Return-Path:` become live candidates. `probe_from.py` measured it across two
mailboxes' All Mail: **133 hits, 133 in `From`** — zero in `Sender`,
`Reply-To`, `Return-Path`, `To`, `Cc`, `Bcc`, and zero unaccounted. Bucketing on
`From` reproduces `SEARCH FROM` exactly.

**`BCC` is fetched, but the bucket keys on `To`+`Cc` and `Bcc` is a guard.**
`_fetch_headers` requests `DATE FROM TO CC SUBJECT MESSAGE-ID REFERENCES
IN-REPLY-TO` (`cs/gmail_archive.py:64`) — no `BCC` — so the legitimacy argument
above was true only of fields we actually retrieve. `BCC` is therefore added to
the field list. But fetching a field does not say what the bucket keys on, and
here the two answers have opposite signs:

- key on `To`+`Cc`: the fetched `Bcc` is never consulted, and the gap survives
  for a new reason;
- key on `To`+`Cc`+`Bcc`: **wider than the server**, if Gmail's `SEARCH TO` does
  not match `Bcc` — which would mint `superseded` for Bcc-only recipients, a
  fourth verdict-change class.

**Whether Gmail's `SEARCH TO` matches `Bcc` is unmeasured, and cannot be
measured here.** `probe_bcc.py` scanned production's entire Sent folder — 153
messages — and found **no message carrying a `Bcc` header at all**. The earlier
`Bcc: 0` was therefore not evidence: those probes examined hits, never misses,
and a folder with no Bcc anywhere is consistent with either answer.

So the bucket keys on **`To`+`Cc`** — faithful to the server on everything that
has been measured — and the fetched `Bcc` is used as a **guard**: a message
whose *only* match is via `Bcc` is reported as a note rather than silently
included or silently dropped. That is what this brief's own ban on silent limits
requires when the honest answer is "unknown", and it converts the open question
into a fact the operator will see the first time it occurs.

## The other measured costs

Stage timings from an instrumented `review.gather` (scratchpad
`probe_gather.py`):

```
   2.9s  1a gmail_drafts.list_drafts       12 Gmail drafts
   0.1s  1b rpc drafts.list                51 engine drafts
   3.8s  1c-i engine_view.settled          38 thread keys, 0 views returned
>1490s  1c-ii draft_state.reconcile        ← killed by a 1500s timeout, never finished
```

**The defect is worse than reported.** The operator killed `cs review` at ~14
minutes; this instrumented run gave `reconcile` alone more than **25 minutes**
and it still had not returned. Everything before it completes in under 7
seconds combined.

**SEARCH is not a bottleneck.** 25 separate searches cost 4.0s; one
`OR`-composed search over all 25 costs 0.2s (`probe_search.py`). An earlier
draft of this brief proposed `OR`-batching as the main fix; that was wrong by
measurement, and it also has an attribution problem — one `OR` search returns
UIDs with no record of which address matched which.

**`sent_body_match` is byte-bound, and chunking will not fix it.** It bypasses
`mailboxes.session()` (`_imap(settings)` at `:198`, `M.logout()` in the
`finally` at `:222-226`), but the login is not its main cost. Measured against
the deepest contacts in production's Sent (`probe_residual.py`):

```
domi.farrar@gmail.com          8 uids   13.47s
violeta@metaview.ai            6 uids   12.85s
riccardo.cargnel@cafe124.it    6 uids   12.66s
```

~1.5s per body. Then the decisive measurement (`probe_chunked_bodies.py`):
fetching those 8 bodies individually costs 17.43s; ONE chunked FETCH over the
same 8 costs 11.69s — only 1.5× — because both move **7,251 KiB**. ~900 KB per
message. `BODY.PEEK[]` (`:206`) downloads the entire MIME tree including
attachments in order to compare a text body that `_normalise` truncates at
`BODY_MAX = 4000` characters (`:436`).

The fix is to **fetch fewer bytes** — locate the `text/plain` part via
`BODYSTRUCTURE` and fetch only that. This is the opposite of the header path's
fix and the two must not be conflated.

**The batched surface for headers already exists:**
`gmail_archive._fetch_headers` (`:54-71`) does chunked FETCH, one round trip per
200 UIDs, and is already used by `inbound_recent` (`:347`) and `sent_recent`
(`:580`). `sent_to_on` and `inbound_since_on` are the two readers that never
moved onto it.

Measured cost of the same bulk shape *without* the self-exclusion and *without*
a `SINCE` bound — i.e. still carrying the pathological 21,686-UID read: **35.3s**
(`probe_bulk.py`). That figure is the intermediate state, not the target; the
target shape is the 7.2s measured above. Both are recorded because the
difference between them is exactly what the self-exclusion buys.

## Two cache bugs

Both per-contact caches in `reconcile` are keyed by address alone while being
parameterised by the current row's `composed_at`. The first row processed fixes
the answer for every later row to that contact, and row order comes from `_pair`
(`:186-220`) — Gmail UID order then `drafts.list` order, arbitrary with respect
to date.

**`inbound_cache` (`:385-387`) is the worse of the two.** Its consumer applies
no date filter at all — `:392-402` is a bare `if later_in:`. A cache populated
for an older draft is reused wholesale for a newer one, and any message in it
fires `overtaken`. A too-wide cache produces a **false `overtaken`**, which
outranks `superseded` (`:72`) and masks the true verdict.

**`sent_cache` (`:404-406`)** has the same shape, but its consumer does
re-filter by date (`:411-416`), so it fails only in the narrowing direction — a
missed `superseded`, read as `ready`.

## Where the exclusion lives — a decision, not an open question

**It goes in a `reconcile`-only reader — never in the shared
`sent_to_across` / `inbound_since_across` path the send gates call.**

The file it lives in is not the point; the *call graph* is. A new function may
sit in `cs/mailboxes.py` beside the existing two (see § entry point below)
provided the existing two are left exactly as they are.

Putting it in the shared fan-out would change the campaign send gates and
`cs history`. The send-gate consequence is mechanical, not hypothetical:
`cs/campaign.py:281-286` and `:304-310` both run `if replies: handle_reply`,
which short-circuits the `elif … send_sms` / `elif … send_reminder` branches
below. Emptying `replies` for a colleague contact moves it **from no-send to
send**. Widening a send path is a `124-cs/CLAUDE.md` § 5 decision and must never
happen as a side effect of a latency fix.

So `reconcile` gets the narrower reader.

**The justification is risk-asymmetry, not question-difference.** The question
is identical on both surfaces — "has this contact written to us". What differs
is the cost of being wrong: `reconcile` is read-only and human-supervised
(`cs/draft_state.py:284-287`), while the gate is unattended, mutating, and
fail-closed, so its current wrongness errs toward a visible, recoverable *stop*.
Do not read `sent_to_here` (`cs/mailboxes.py:508-516`) as the precedent here —
that one justifies itself by the caller asking a genuinely different question,
which is not the case now.

This is also not two implementations: `inbound_since_across` stays single, and
`reconcile` adds a caller-side pair filter. The same pathology in the campaign
path is recorded below as its own decision.

## The new bulk reader — entry point and row shape

Stated so the implementer does not invent them and the next caller does not
inherit a guess.

**Entry point:** one function in `cs/mailboxes.py`, alongside
`inbound_since_across` / `sent_to_across`, taking the **address list**, the
folder selector, and the `SINCE` bound, and returning a `Fanout`. It applies the
per-mailbox self-exclusion by removing that mailbox's own address from the list
before searching it. The existing per-address functions stay exactly as they
are — they back the unbounded dedup gates and this brief does not touch their
behaviour.

**No send gate may call it — and the risk is that it looks safe to.** It sits
beside the readers the gates already use and returns the same `Fanout` type they
already consume, so it will read as a drop-in. It is not one: it applies the
self-exclusion, and inside a gate that exclusion empties `replies` for a
colleague contact and moves them from no-send to send
(`cs/campaign.py:281-286`, `:304-310`) — the § 5 widening this whole location
decision exists to prevent. The function's own docstring must say so, in those
terms, because § Recorded anticipates a second caller and a future reader will
have none of this context.

**Row shape:** every row carries `date`, `subject`, `message_id`, the
`mailbox` it came from (as `_fan` already adds, `cs/mailboxes.py:481`), and the
**matched address**, which is what makes in-memory bucketing possible at all.

`message_id` is included deliberately. The two existing readers disagree —
`sent_to_on` rows carry it (`cs/gmail_archive.py:126-127`),
`inbound_since_on` rows do not (`:294`) — and `cs/campaign.py:127` consumes it
off the sent fan-out. `reconcile` itself needs only `date`
(`cs/draft_state.py:394`, `:413`), so carrying it costs nothing here and stops
the divergence being propagated into a third reader.

## Scope

In scope, `cs-kernel` only:

- `cs/draft_state.py` — exclude the contact's own mailbox from **both** reads
  (their All Mail for `inbound`, their Sent Mail for `sent`);
  bulk-read-then-bucket on `To`+`Cc`; fix **both** `inbound_cache` and
  `sent_cache`; surface the skip in `notes`.
- `cs/mailboxes.py` — the third `Fanout` outcome (`:121-123`) and its
  appearance in `scope_line()` (`:129-142`). **Behaviour of the shared fan-out
  is unchanged; its shape and its printed output are not.** `scope_line()` feeds
  `cs history` and `cs dossier`, so this edit is visible there
  (`tests/test_contact_history.py:482`, `:533`, `:546`, `:626`, `:668`, `:706`).
- `cs/gmail_archive.py` — make `_fetch_headers` surface a failed chunk instead
  of dropping 200 messages (`:66-67`); add `BCC` to its field list (`:64`); give
  `sent_body_match` the shared session and a `BODYSTRUCTURE` text-part fetch.
- `cs/review.py` — progress output; explicit timeouts per criterion 8.
- `tests/` — new fixtures and assertions per criteria 2–7c, including the
  contact-is-a-mailbox fixture (5), the failed-chunk gate (7b) and the
  `Bcc`-only guard (7c).

## Constraints

- **Evidence may not narrow, except where narrowing is the fix.** The sanctioned
  exclusion is the (contact, own-mailbox) read on **both** folders — the
  `inbound` read of their All Mail and the `sent` read of their Sent Mail —
  justified above. Everything else — mailboxes, windows, message sets — stays as
  wide as today or wider.
- **`_fetch_headers` must stop dropping whole chunks silently — this is a § 5
  fix, not a refactor.** It currently does `if typ != "OK" or not data: continue`
  (`cs/gmail_archive.py:66-67`) with `chunk: int = 200` (`:54`), so one non-OK
  FETCH discards up to **200 messages**. Today `sent_to_on` drops exactly one
  message on the same failure (`:112-114`). `sent_to_on` backs `sent_to_across`,
  which is the dedup gate at `cs/campaign.py:126` and `cs/cli.py:929`. Moving
  that reader onto `_fetch_headers` as written would let a single transient
  error erase 200 Sent messages from "have we ever written to this address" and
  return a real prior contact as absent — **fail-open**, the exact incident
  `cs/mailboxes.py:1-16` exists to prevent, and a `124-cs/CLAUDE.md` § 5
  violation. So `_fetch_headers` surfaces the failed chunk instead of skipping
  it, and the caller turns that into an `unreadable`/note. This brief protects
  the gates against a narrowed SEARCH; changing their FETCH mechanism carries
  its own § 5 consequence and it must be closed in the same change.
- **The folder split is load-bearing and must not be collapsed.** `TO` is read
  from Sent and `FROM` from All Mail, and both readers are draft-free *by
  construction* because of that: `sent_to_on` reads Sent, where "drafts live in
  Drafts, never Sent" (`cs/gmail_archive.py:232`), and `inbound_since_on`
  matches FROM the contact, which "can never match" a draft (`:233-234`). The
  obvious next optimisation from "one read per (mailbox, folder)" is "All Mail
  contains Sent too, so why two folders" — **that is a trap and it is already
  documented**: All Mail also holds unsent drafts, draft-ness there is only the
  `\Draft` X-GM-LABEL, the IMAP FLAG is not set, and `UNDRAFT` therefore does
  not exclude them (`:480-482`, verified 2026-07-25). Collapsing the two reads
  would bucket our own undelivered drafts as sends and mint `superseded`
  verdicts from mail nobody ever received.
- **The skip is a THIRD outcome, never an `Unreadable`.** `Fanout` today has
  only `read` / `unreadable` (`cs/mailboxes.py:121-123`). Recording a deliberate
  skip as `unreadable` would: make `_evidence_refusal` (`cs/campaign.py:165`)
  refuse every campaign send to a colleague's address forever via `_unjudgeable`
  (`:181-191`, `EVIDENCE_ACTION` at `:64`); land a spurious gap on every `ready`
  row through `_across_inbound` (`cs/draft_state.py:236-243`, `:447`); and make
  `scope_line()` (`cs/mailboxes.py:135`) print "3 of 3" where 4 is expected —
  the invisible narrowing that module exists to prevent (`:12`, `:20-22`). A
  skipped mailbox is neither read nor unreadable and must be reported as
  skipped, with its reason.
- **The `SINCE` bound is derived and UNCAPPED.** `SINCE min(composed_at) − 3d`,
  with **no** `MAX_LOOKBACK_DAYS` cap. `inbound` has no cap today
  (`cs/draft_state.py:387` passes `after=composed_at` with no `days`;
  `inbound_since_on` searches unbounded), so a 200-day-old draft is compared
  over 200 days. A 120-day `SINCE` would lose 80 of them and turn a real
  `overtaken` into `ready`. The cap's own rationale (`cs/draft_state.py:85-88`)
  justifies it because "the per-message Date filter answers it exactly" — true
  of a POST-filter, false of a PRE-filter, which can never recover what it
  excluded.
- **`sent_to_on` and `inbound_since_on` stay unbounded.** They back the "have we
  EVER written to this address" dedup gates — `cs/cli.py:929` passes
  `days=None`; `:297-298`, `cs/campaign.py:126`, `:146` are the other callers.
  Pushing a `SINCE` into them silently narrows the pre-send dedup check, a § 5
  NEVER. The bound belongs to `reconcile`'s new bulk reader alone.
- Degradation stays a note, never an exception, never a dropped row
  (`cs/draft_state.py:433-457`). Silent limits are banned; any cap reports what
  it did not read, as `sent_body_match` already does at `:217-220`.
- Kernel change; reaches `124-cs` via `cs update` + reinstall. No compensating
  heuristic in the clone or `ext/`. Read-only throughout.

## Acceptance criteria

1. `cs review --json` on the reference clone completes in **under 90 seconds**
   from a cold start, measured — excluding `campaign.contacts` and
   `engine_view.settled`, bounded separately by criterion 8.

   Grounded in the measured post-fix components: bulk header reads **7.2s**,
   `gmail_drafts.list_drafts` 2.9s, `engine_view.settled` 3.8s,
   `rpc drafts.list` 0.1s — about 14s before `sent_body_match`. **The whole
   margin is `sent_body_match`.** If the `BODYSTRUCTURE` text-part fetch does
   not land, the target is not reachable — 25 contacts × ~2 bodies × 1.5s
   already exceeds it — and must be renegotiated, not quietly missed.
2. Verdicts are unchanged except for **three** corrections, each with a test
   over the injected seams that **fails before and passes after**:

   - **(c) the own-mailbox reads.** For a contact who is also a mailbox: the
     `inbound` read of their own All Mail currently mints a false `overtaken`
     (their entire sent history), and the `sent` read of their own Sent Mail
     currently mints a false `superseded` (a self-addressed message passing the
     re-filter at `:411-416`). Both disappear. This is the third correction, and
     it is a consequence of the primary fix rather than a separate change.

     **(c) needs two draft rows, not one.** `reconcile` tests inbound first and
     `continue`s on `overtaken` (`:399-402`), and `overtaken` outranks
     `superseded` (`:72`), so a single row would show only the first half and
     the `superseded` correction would be masked. Two rows, or two seam
     configurations.

     It also needs a **different fixture world from criterion 5**: criterion 5
     asserts the absence of I/O, while (c) asserts a verdict flip, so (c)'s
     world must contain poison that criterion 5's does not need.

   The two cache corrections:
   - `sent_cache`: two drafts to one contact, both from the **engine** store so
     `_pair` (`:199-217`) cannot merge them; ages satisfying
     `age₁ + 2 < age_send < age₂` with `age₁ < 118`; newer processed first; the
     `sent` seam **must honour its `days` argument**
     (`tests/test_draft_state.py:84` returns a constant, and a constant seam
     cannot fail-before); `inbound` empty so `overtaken` does not win;
     `delivered` returning no hit so `duplicate` does not `continue` at
     `:378-383`. Currently `ready`, correctly `superseded`.
   - `inbound_cache`: same construction with the `inbound` seam honouring
     `after`. Currently a false `overtaken`, correctly `ready`.
3. IMAP **round trips** during one `reconcile` are bounded by the number of
   mailboxes in scope, not by contacts or drafts. Asserted on `FakeIMAP`, which
   already counts connections (`tests/test_send_gates_fanout.py:107`, `:112`) —
   extend it to count round trips. Counting LOGINs alone is insufficient:
   sessions are already cached, so a login count passes while the wall stands.
4. **Over verdict-relevant messages** — those with `date > composed_at`, the
   only ones any verdict can turn on — the set considered is **unchanged or
   wider for every (contact, mailbox) pair EXCEPT (contact, own-mailbox), which
   must be empty.** Asserted directly on the fake, not inferred from equal
   verdicts.

   Both qualifications are load-bearing, and each exists because the plain form
   forbids something the constraints mandate:
   - the own-mailbox carve-out, because the primary fix empties **both** of that
     contact's own-mailbox reads — the All Mail one goes from 21,637 messages to
     zero, the Sent one from 42 to zero;
   - the `date > composed_at` restriction, because the derived `SINCE` bound
     legitimately drops older messages — 49 UIDs unbounded versus 31 bounded in
     riccardo's All Mail for the other 24 contacts. None of those 18 can change
     a verdict: each predates `min(composed_at) − 3d` and so cannot satisfy
     `date > composed_at`. A raw-UID assertion would fail on them with no
     licence to relax it, which is exactly the trap this criterion is meant to
     set for a narrowing implementation, not for the intended one.
5. **A fixture exists whose contact is also a mailbox**, and a test asserts that
   **neither** (contact, own-mailbox) read happens — not the All Mail `FROM`
   read and not the Sent `TO` read. Asserting only one absence passes while the
   other regresses, and this is the primary fix's only regression gate, so half
   a gate is the whole hole. No current fixture has this —
   `CONTACT = "prospect@customer.example"` in both
   `tests/test_send_gates_fanout.py:82` and `tests/test_contact_history.py:94` —
   so without it the primary fix has no regression gate at all and criterion 1
   would catch a regression only as live wall-clock on one clone.
6. **The skip is visible on both surfaces, and `reconcile` is the one that
   matters.**
   - In `reconcile`'s `notes`, because `reconcile` never calls `scope_line()`:
     `_across_inbound` / `_across_sent` (`cs/draft_state.py:236-243`, `:247-258`)
     consume only `fan.unreadable` and `fan.rows` and discard `fan.read`, while
     `render` surfaces only `evidence_incomplete` (`cs/review.py:300`) and
     `drafts_notes` (`:309`). Without this, a colleague's draft flips
     `overtaken` → `ready` with nothing on the page saying a mailbox was
     skipped — the exact invisible narrowing `cs/mailboxes.py:12`, `:20-22`
     exists to prevent, and a violation of this brief's own constraint.
   - In `scope_line()` output as a skip, distinct from both read and unreadable,
     with `tests/test_contact_history.py`'s denominator assertions (`:448`,
     `:482`, `:533`, `:546`, `:597`, `:626`, `:668`, `:706`) updated
     deliberately rather than left passing by accident.
7. An unreadable mailbox still produces its note and still marks every `ready`
   row `evidence_incomplete` (`tests/test_send_gates_fanout.py:441-465` must
   still pass).
7b. **A failed FETCH chunk is reported, never skipped.** A test drives a non-OK
   FETCH through `FakeIMAP` and asserts that the affected messages surface as a
   degradation rather than vanishing — and specifically that
   `sent_to_across`, the dedup gate's reader, cannot return "no prior contact"
   because a chunk failed. Without this the § 5 fail-open above has no gate.
7c. **A `Bcc`-only match is reported as a note.** A test constructs a message
   whose searched address appears only in `Bcc` and asserts the guard fires,
   since whether the server matches it is unknown and this brief refuses to
   resolve an unknown silently in either direction.
8. `campaign.contacts` (`cs/review.py:239`, looped, no explicit timeout, fresh
   `asyncio.run` per call at `cs/rpc.py:226-230`) and `engine_view.settled`
   (model call possible per `cs/engine_view.py:164-168`, 120s timeout at `:157`)
   each carry an explicit timeout and appear in progress output, so a slow engine
   is visible rather than indistinguishable from a hang.
9. `cs review` emits progress to **stderr**; `--json` on stdout stays clean.

## Testability

`reconcile` already injects `inbound`, `sent`, `settled`, `delivered`
(`cs/draft_state.py:267-277`), and `tests/test_draft_state.py:79-90` drives all
four over fixtures with no network. `tests/test_send_gates_fanout.py:102-160`
replaces `imaplib.IMAP4_SSL` with `FakeIMAP` and drives the real readers
end-to-end (`:434`); `_test_one_login_per_mailbox_per_process` (`:362-374`) is
criterion 3's existing shape.

Known cost: `FakeIMAP.uid` handles only a single sequence id per FETCH (`:141-142`)
and only `SEARCH <key> <value>` (`:136-140`). Chunked `_fetch_headers` and a
`BODYSTRUCTURE` fetch both need the double extended.

## Open assumption

That a `BODYSTRUCTURE` text-part fetch reproduces `_normalise`'s output for the
messages that matter, and degrades to a **reported miss — never a false
`duplicate`** — when the structure is unexpected. The plan must prove this
before criterion 1 can be claimed.

## Recorded, not fixed here

- **The same silent-drop defect survives on the PER-UID readers, untouched.**
  M1 fixed the batched path (`_fetch_headers` now raises), but `_hdr`
  (`cs/gmail_archive.py:105-113`) still returns `None` on a non-OK FETCH and
  `sent_to_on` still `continue`s past it (`:112-114`), dropping one message
  silently. That is the same fail-open class on the reader that backs the
  **dedup gates** — `sent_to_across` ← `cs/campaign.py:126`, `cs/cli.py:929`.
  Lower blast radius per failure (one message, not 200) but the same wrong
  answer in kind: a prior contact read as absent. Deliberately out of scope
  here because this brief forbids changing those readers; it needs its own
  decision.

- **Row shape divergence between the two readers.** `sent_to_on` rows carry
  `message_id` (`cs/gmail_archive.py:126-127`); `inbound_since_on` rows do not
  (`:294`). `reconcile` needs only `date` (`cs/draft_state.py:394`, `:413`), so
  this brief is unaffected — but Scope puts a bulk reader in `cs/mailboxes.py`,
  and `cs/campaign.py:127` reads `message_id` off the sent fan-out. Whoever adds
  the second caller will expect a field the inbound side has never provided.
- **The same pathological read exists in the campaign send-gate path**
  (`cs/campaign.py:146` uses the shared fan-out). Not fixed here because
  narrowing evidence in a send gate can *permit* a send that is currently
  blocked — a § 5 decision, not a latency fix.
- **`engine_view.settled` returned 0 views for 38 thread keys.** Not necessarily
  wrong: `settled` emits a view only where `needs_reply is False`
  (`cs/engine_view.py:186`), so an engine judging all 38 to need a reply
  correctly yields none. The discriminator is whether `res["threads"]` (`:185`)
  came back empty — pointing at a thread-key namespace mismatch between
  `:140-141` and `:160` — or populated with `needs_reply: true`. Engine-side
  either way per `124-cs/CLAUDE.md` § 0b.
- **`cs ask` exits 0 when the engine fails.** The engine reports failure as
  `metadata.error` inside a successful JSON-RPC result and `cmd_ask` prints
  `result.response`, which carries the error text. Reproduced: a 502 printed
  with `EXIT=0`. `cmd_draft_reply` (`cs/cli.py:1222`) shares the same
  `rpc.chat` path and the same shape. This is why a months-long grounding outage
  on `production@` stayed invisible to every tick. Separate brief, kernel-owned.
- `.claude/skills/cs-operator/SKILL.md:167-170` and its template
  `cs/templates/project/.claude/skills/cs-operator/SKILL.md.j2:167-170` omit
  `duplicate` from the verdict list, which `cs/draft_state.py:72` ranks
  strongest.
