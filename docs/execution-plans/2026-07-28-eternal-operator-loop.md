---
title: "From the Giada campaign loop to an eternal support operator — analysis and proposed changes"
status: blocked
created: 2026-07-28
updated: 2026-08-03 — moved from mrcall-cs (2026-07-31); BLOCKED on the
  task-ledger contract per the 2026-08-01 operator-redesign decision (a 3-agent
  evaluation found this plan never engages the engine task system — it needs a
  task-first rewrite before any build)
owner: mrcall-cs
decides: nothing yet — this is a proposal, no code is written and no loop is started
supersedes: nothing
---

# 0. What was asked, and what this is

Mario asked to turn `giada.py` — the batch-2 Centralix→Vonage conversational
loop — into an **eternal loop, always running**, and named five directions:
clean up the prompts, use memory heavily, write a good analysis of each email
back into memory (noting the mrcall-desktop DB holds only ~3 months), move the
CRM into the database, and redesign "the table".

This document is the analysis behind those five, plus the loop design they add
up to. **Nothing here is built.** Every number below was measured on the live
system on 2026-07-28, not inferred from the docs.

One ambiguity I could not resolve from the request and did not want to guess:
*"the structure of the table must be better"* has two plausible referents — the
migration schedule CSV, or the `sends` ledger in `cs.db`. §2.3 proposes a schema
that subsumes both, and §4 asks the question explicitly.

---

# 1. Findings

## 1.1 The loop's spine is a closed roster, and that is why it went silent

`giada.py` (1905 lines) is organised around a **finite roster with a terminal
state**: 73 rows in a CSV, states `NOT_ANSWERED → IN_CONVERSATION → AGREED →
CONFIRM → CLOSED`, and a deadline that ends the campaign. Every run iterates the
roster, and `main()` skips any owner group whose state is `CLOSED`.

An eternal operator has the opposite shape: an **open, unbounded worklist with no
terminal state**. The mailbox is never "closed".

This is not a theoretical distinction — it is exactly the live defect recorded in
`active-context.md`. After the cutover, 72 of 73 rows are `CLOSED`, so every pass
reports *"nothing to do"* while the mailbox has real customers waiting. Running
the loop more often changes nothing, because the worklist is the roster and the
roster is finished.

**So the single most important structural change is not "run forever". It is:
the worklist stops being a campaign roster and becomes the mailbox.**

The piece that already does that deterministically exists and Giada never used
it: `cs unanswered` (kernel `cs/unanswered.py`) — enumerate recent inbound from
Gmail, subtract every sender we have since written to (Gmail Sent = ground
truth), no LLM anywhere in discovery. It replaced a non-deterministic `cs ask`
discovery in the triage skill for precisely this reason.

The eternal loop is therefore: **`unanswered` for discovery + Giada's per-contact
machinery for the work + a durable per-contact state table to remember across
ticks.** The campaign roster becomes one *workstream* among several, not the
loop's skeleton.

## 1.2 About 40% of `giada.py` is already the generic loop

Splitting the file by what survives the campaign:

| Generic — the loop skeleton (kernel candidates) | Campaign-specific — dies with Centralix |
|---|---|
| `Log`, run lock, `CS_PAUSE` re-check per send, digest mail | `GROUNDING`, `GROUNDING_DONE`, `GROUNDING_PENDING` |
| `Ctx.may_send_to` (pause / DNC / self / rate cap) and `Ctx.send` | `_forwarded_clause`, `_next_slot`, `MIGRATOR_SLOT_MIN` |
| `_already_answered`, `_is_bulk`, `_last_reminder_day` | the whole of `schedule.py` (CSV, states, backstop, clamp) |
| `_history`, `_sent_since`, `_sent_today` | `_phones`, `_mobile`, `PHONES_JSON` |
| `_engine` (empty allow-list turn), `sendable` + `BANNED` + placeholder guard | `CAMPAIGN_START`, `BULK_SUBJECT_PREFIXES` |
| `_para_html`, `_insert_after_greeting`, `_refs` | the verdict prompt's `STATO`/`DATETIME` grammar |
| `_memory`, `_remember` | `_backstop_words`, and `_calendar`'s end date |
| `Sidecar` (superseded by §2.3, but its *contract* is generic) | `_group_state`, `_live`, `_group_when` (roster-shaped) |

The right destination for the left column is `cs-kernel` (rule of two: the
eternal loop and any future campaign both want it), the right column is a
campaign pack. `giada.py` should end up as the pack's `handlers.py` — a few
hundred lines — not as the loop.

Note that four of the hardest-won behaviours are in the left column and must not
be re-derived: stamp-before-send, persist-the-schedule-before-the-mail, re-read
state immediately before acting, and check the kill switch before *every* send
rather than once per run. Each of those exists because of a specific incident.

## 1.3 The memory did work, then broke on a specific date — and the corpus still carries it

Mario's recollection is literally correct, and the engine's own source records
the event. The timeline, from `git log` and the rotated engine logs:

| when | what |
|---|---|
| until June | small corpus, merge gate working |
| June | a prompt-cache refactor (`58f392a`) put only the one-line preamble into the cached system prompt and dropped the entire rule set — including the rule that lets the model REFUSE to merge. The gate was **broken open**: across 859 merges it refused 0 times, and the first PERSON blob became a universal sink that absorbed 400+ unrelated contacts, each one's specifics discarded |
| **2026-06-28** | fix `5adad4b` *"merge gate was broken-open — every contact merged into one blob"*, plus a canary (`merge_gate_selfcheck`) — and a **mass rebuild: 1269 of today's 1535 entity blobs were created that single day** |
| 23 Jun – 2 Jul (log.3) | 1302 MERGE vs 217 INSERT — 14% refusal, the rebuild running |
| 2 – 23 Jul (log.2) | 96 MERGE vs 94 INSERT |
| 23 Jul – now | 235 MERGE vs 234 INSERT — ~50% refusal, canary green |

The June incident was the merge **judgment** breaking *open* (everything
merged). Re-measuring on 2026-07-30 shows the opposite failure is running right
now: candidate **recall** breaks *closed* (the right blob is never found), so
the corpus keeps fragmenting. **116 blobs created after the 28-Jun rebuild
duplicate a name that already existed** — accelerating exactly with campaign
traffic (14 on 23 Jul, 15 on 25 Jul, 32 on 28 Jul). The gate's judgment is
healthy; the problem no longer reaches it.

### The mechanism, caught live in the log

`_upsert_entity` (`workers/memory.py`) picks merge candidates two ways — blobs
sharing an extracted identifier, plus blobs above a hybrid-similarity threshold
(0.65) — then asks an LLM, per candidate, "are these the same entity?". When no
candidate is found, it inserts a new blob. **Nothing anywhere is a key.**

The `ambulatorio cavoretto` duplication of 2026-07-28 00:21 shows each link of
the chain failing, verbatim in the engine log:

1. A blob for this customer **already existed** (since 28 Jun), complete with
   its `email` identifier row — findable by key.
2. The extractor read the new mail and emitted a stub entity **without the
   sender's address**: `Name: Ambulatorio Cavoretto | Website: (none) |
   Address: (none) | VAT: (none)`. No email extracted → the identifier lookup
   had nothing to key on.
3. Hybrid search then ranked candidates for that stub — and returned **three
   unrelated businesses** (`Studio Pusceddu` 0.637, `Into the wild dog village`
   0.612, `Studio Ruzzon` 0.584), with the real Ambulatorio Cavoretto nowhere:
   the text-search terms literally include the scaffolding tokens `entity`,
   `type:`, `company`, `(none)`, which dilute the two tokens that matter.
4. `Found 0 candidates above threshold 0.65` → **new blob created** — itself
   identifier-less, making the next lookup for this customer worse. The failure
   compounds.

The same customer was duplicated *again* twenty minutes later (00:41), through
the identical sequence. An exact match on the name — one indexed lookup — would
have found the 28-Jun blob instantly, with no LLM and no threshold involved.

The state of the corpus (support@ profile DB, re-measured 2026-07-30):

| | count |
|---|---|
| `user:` blobs (entity dossiers) | 1548 |
| distinct `Name:` values among them | **632** |
| names appearing more than once | 233, covering **1131 blobs** |
| — of which multi-word names (almost surely the same real entity) | **174 names, 856 blobs (55%)** |
| — one-word first names (may legitimately be different people) | 59 names, 275 blobs |
| blobs with NO `person_identifiers` row | **1209 (78%)** |
| blobs whose prose states an `Email:` but that have no identifier row | **143 of 392** |
| blobs describing OUR OWN outbound mail, not a customer | **164 (10%)** |
| `facts:` blobs | 738, **0** linked to any contact, **243** containing a `+39` number |

The worst cluster is the whole argument in one example. **`Tandoori Villa
Postipuisto` exists 25 times.** All 25 were created inside two minutes on
2026-06-28, from 25 different inbound emails; **24 carry no identifier at all and
no `Email:` line**; every one has the byte-identical `Name:` line; and each is a
slightly different paraphrase of the same fact — *"is a Finnish restaurant
(likely Indian cuisine)"*, *"is a Finnish Indian restaurant"*, *"is a business
(likely a restaurant) in Finland"*.

Three consequences worth naming separately:

**(a) The `facts:` namespace is a global keyless bag holding customer-specific
data.** Verbatim rows: `Category: MrCall setup | Key: Call forwarding number |
+390289040647`, and `Category: MrCall call forwarding | Key: Call forwarding
activation code | **004*+390289040645#`. These are facts about *one* customer
stored as facts about *nobody* — 243 of them carry a phone number, and not one of
the 738 is linked to a contact.

Retrieval (`engine/zylch/memory/hybrid_search.py`) is owner-scoped cosine top-k
plus a LIKE over the `#IDENTIFIERS` section. Nothing in it scopes a fact to the
customer it came from. Today the default agent context searches only the `user:`
namespace (`base_agent._gather_context`, `limit=10`) and `facts:` is reached
through the separate `get_facts_by_category` tool — so I am **not** claiming a
leak has happened. I am claiming that "use memory heavily" is exactly the change
that makes it reachable, and the failure mode is handing customer A customer B's
forwarding number, in writing, from an autonomous loop.

**(b) Identifier extraction fails on a third of the blobs that state the address
in their own text.** 392 blobs have an `Email:` line in the prose; 143 of those
have no `person_identifiers` row. So even the keyed path is only partly keyed,
and the gap compounds: a blob created without an identifier can never be *found*
by identifier, so the next observation of that entity inserts again.

**(c) A tenth of "entity memory" is not entities.** 164 blobs are
`Entity type: STYLE` — memories of our own templates, e.g. *"Subscription expiry
win-back email (AI-generated)"* — and dozens more are named *"number migration
reminder (Italian)"* (×40) or *"number migration notification to subscriber"*
(×14). They sit in the same retrieval pool as customers and compete for the
top-k slots.

**So Mario's instinct is right, and it can now be stated as a symmetry: the two
memory incidents are opposite failures of the same keyless design.** In June the
merge *judgment* broke open and everything collapsed into one blob; since then
candidate *recall* breaks closed and everything fragments — the same customer
inserted twice in twenty minutes because a stub with `Website: (none)` could not
find a blob that was sitting there with its email indexed. Identity resolution
by embedding similarity plus an LLM judgement is the correct tool when you have
no identifiers — a personal assistant reading a stranger's mail. That is not our
situation. Every customer has a `business_id`, an email address, a phone number
and a service number sitting in the CRM. We discarded the keys, then paid an LLM
to guess them back — twenty-five times, for one restaurant. No tuning of the
threshold or the merge prompt fixes both directions at once; a key fixes both.

## 1.4 The engine holds ~3.7 months of mail — and it is not the archive

1833 messages, oldest `2026-04-08`, newest today. By month: Apr 289, May 291, Jun
505, Jul 748. 1798 of 1833 have been through the memory worker (35 pending).

This is not a rolling retention window — nothing purges — it is simply
"everything since the first sync" (`sync_service` full-sync default is
`days_back=30`, incremental thereafter). It will keep growing, but **everything
before April 2026 exists only in Gmail**, which is why `gmail_archive.py` exists
and why both deterministic sweeps read IMAP rather than the engine.

Consequence for "update memory with a good analysis of email": there are two
different jobs and they should not be the same code.

- **Forward (in the loop):** after each handled contact, write one structured
  entity update. Giada already does this (`_remember`), and it is prose. It should
  become a **structured** update against a fixed dossier shape, so the next read is
  a row, not a paragraph.
- **Backfill (one-off, offline):** walk the Gmail archive per contact, build one
  dossier per contact from the full history, write it once. ~1170 distinct
  customer addresses (§1.5). This is a batch job with its own budget and its own
  model choice, and it must never run inside an hourly tick.

## 1.5 The CRM is a per-contact live RPC; there is no local customer table

`cs dossier` reaches the CRM through `crm/starchat.py` → the engine's
`mrcall.search_businesses` RPC → StarChat, **one call per contact, 60 s timeout,
on an out-of-team service**. For a loop that touches contacts continuously this
is the wrong shape: it is slow, it fails in ways we do not control, and it
produces nothing we can query, join, or count.

Prod Postgres is directly reachable from this host — `migrator.py` already uses
it (`kubectl` → `starchat-db` secret → `psql`). Measured there today
(`WHERE delete=false`):

| | count |
|---|---|
| businesses | 1268 |
| distinct `email_address` | 1170 |
| `TEST` | 1009 |
| `ACTIVE` | 152 |
| `FREE` | 60 |
| `PAST_DUE` | 17 |
| `EXPIRING` | 9 |
| `EXTERNAL` | 9 |
| `TRIALING` | 7 |
| `CANCELED` | 5 |

So the real customer universe the loop serves is **~245 businesses, not 1268** —
the other 1009 are TEST. That number matters: it is what makes an eternal loop
affordable, and it is invisible today because nothing counts it.

**Recommendation: yes, cache it.** A `crm_business` table in `cs.db`, refreshed by
its own cheap verb on its own cron (`cs crm sync`, every 15–60 min, one `psql`
read), and read by the loop with zero RPC. The `crm` port stays exactly as it is —
this is a new *adapter* backed by the cache, not a new seam. One rule: **the cache
may inform a message, never authorise a production write.** The migrator's
guarded `UPDATE … WHERE service_number=<old> RETURNING` pattern stays as it is.

## 1.6 State lives in three places, and none of them is a table

| store | what it holds | how it fails |
|---|---|---|
| `elenco_migrazione_centralix_TUTTI.csv` | when + conversational state, per business | **tracked in git AND live runtime state** — a `git reset --hard` on 2026-07-28 rewound it three hours before the cutover and made 68 already-migrated rows read as due |
| `~/.mrcall-cs/giada_state.json` | last inbound seen, last replied msgid, reminder/SMS day, conversation start | a JSON blob keyed by email; not queryable; 68 entries today |
| `cs.db` `sends` | append-only ledger, 748 campaign rows | the only real table, and it is a *log*, not state |

The CSV's fatal property is that it is deliberately both: in git so a human can
read and override it, and live so the loops can act on it. That combination is
what made a routine git operation a production write, and nothing warns about it.

The fix is not "stop tracking it". It is **invert the direction**: state lives in
`cs.db` (never in git), and the human-readable table is *generated on demand*
(`cs loop status --csv`) rather than maintained as the source. A human override
becomes a command, not a file edit — auditable, and impossible to perform by
accident with a checkout.

## 1.7 What the loop actually costs, per the engine's own meter

From `llm_usage` in the engine DB:

| day | calls | est. USD |
|---|---|---|
| 2026-07-25 (go-live sweep) | 385 | 20.06 |
| 2026-07-26 | 211 | 6.47 |
| 2026-07-27 (cutover) | 390 | 20.03 |
| 2026-07-28 (to 16:00) | 439 | 11.41 |

The driver is **calls per handled contact, not tick frequency**: each reply is
three engine turns (memory + verdict + compose), each a full LLM round trip of
1–4 minutes. A tick that finds nothing due costs one IMAP header fetch and
nothing else.

That gives the cost lever directly: replacing the memory turn with a keyed blob
read (§1.3) removes a third of the per-reply cost *and* its nondeterminism, and
the verdict turn is a classification that does not need the same model as the
compose turn.

## 1.8 Two open defects that the eternal loop must not inherit

- **The five-field verdict.** Live on 2026-07-28 the model answered
  `AGREED|ASAP|-|SI|…` — `ASAP` *and* a datetime — and `parse_verdict`, which
  splits on the first three pipes, read `"SI|…"` as `RISPONDERE` and refused the
  whole verdict. It refused correctly; the customer still went unanswered. This is
  a prompt-versioning failure: a paragraph appended to a Python string constant
  changed the output grammar and no test guarded the grammar. **Still in the tree.**
- **`CS_SYSTEM_SENDERS` is unset.** `cs unanswered --days 10` right now returns 12
  items, **8 of them `mail-daemon@…aruba.it` bounces**. An eternal loop built on
  this sweep would spend LLM calls classifying bounces every tick. Deterministic
  pre-filter, not judgment.

---

# 2. The design

## 2.1 The five components

| Component | Decision |
|---|---|
| **Trigger** | A tick every 10 minutes, plus the `due_at` gate (§2.3) — *not* a long-lived daemon. Rationale below. |
| **Goal** | Machine-verifiable: **after a tick, no contact has `state='WAITING_US'` with `due_at <= now`** — i.e. `cs loop status --json` reports `overdue: 0`. Anything the loop cannot answer moves to `ESCALATED`, which is a terminal state *for the loop* and a queue *for the human*, and is counted separately. |
| **Actions** | Read: Gmail IMAP (read-only), `cs.db`, the engine over RPC with an **empty tool allow-list**, the CRM cache. Write: `cs.db`, the engine memory (`create_memory`/`update_memory` only), outbound mail via cs-SMTP, SMS via the MrCall proxy. **Write perimeter: `~/.mrcall-cs/` and nothing in the repo.** Do-not-touch: prod Postgres (the migrator owns every production write), git, `.env`, the engine profile settings. |
| **Verification** | Deterministic and outside the doer: (1) the sweep itself — a contact we replied to disappears from `unanswered` on the next tick, and if it does not, that is the alarm; (2) `sendable()` grammar guards on every composed reply; (3) the ledger cross-check (`sends`) before any second contact; (4) a nightly reconcile that compares `thread_state` against Gmail and reports every disagreement. The model never reports its own success. |
| **Memory** | On disk, three layers: `cs.db` `thread_state` (what we owe whom, and when), `sends` (append-only ledger, dedup truth of record), `loop_run` (the resume log — one row per tick with counts and evidence paths). Engine memory holds *customer knowledge*, never loop control state. |

**Why a tick and not a daemon.** Everything that makes this loop safe is built
around a process that starts and ends: the flock, the atomic writes, the
stamp-before-send, the config re-read. A daemon weakens the kill switch — a hung
daemon holds the run lock indefinitely, which has already happened once (a sweep
launched on the same minute as the migrator "held the run lock for the best part
of an hour"). With the `due_at` gate an empty tick is nearly free, so "always
running" is bought by frequency, not by a resident process. Event triggers (IMAP
IDLE, Gmail push) can be added later as an *accelerator* on top of the timer,
never as a replacement for it.

## 2.2 The level

**Level 1 (ralph loop), not Level 4.** One agent, one unit of work per iteration
(one contact), context reset each time, state on disk, a deterministic driver in
Python. The phases here do not genuinely differ — every contact goes through the
same pipeline — so an orchestrating LLM would add a failure mode and buy nothing.
The existing `giada.py` is already this shape; it needs its worklist and its
state store replaced, not its control flow.

## 2.3 The table

One SQLite file, `~/.mrcall-cs/cs.db`, WAL. **Never in git.**

```sql
-- Who. One row per address we have ever dealt with.
CREATE TABLE contact (
  email            TEXT PRIMARY KEY,       -- lowercased, the join key everywhere
  name             TEXT,
  company          TEXT,
  language         TEXT,                   -- reply language, from the CRM or observed
  first_seen_at    REAL,
  last_inbound_at  REAL,
  last_outbound_at REAL,
  suppressed       INTEGER NOT NULL DEFAULT 0,
  suppress_reason  TEXT
);

-- What we owe them, per workstream. THE table the loop iterates.
CREATE TABLE thread_state (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  email               TEXT NOT NULL REFERENCES contact(email),
  workstream          TEXT NOT NULL,       -- 'support' | a campaign slug
  state               TEXT NOT NULL,       -- WAITING_US | WAITING_CUSTOMER | ESCALATED | DONE
  intent              TEXT,                -- classified once, cheap model, see §2.5
  due_at              REAL,                -- the scheduler primitive: act at/after this
  last_inbound_msgid  TEXT,
  last_inbound_at     REAL,
  last_replied_msgid  TEXT,
  last_outbound_at    REAL,
  attempts            INTEGER NOT NULL DEFAULT 0,
  escalation          TEXT,                -- why a human is needed; NULL otherwise
  note                TEXT,
  updated_at          REAL NOT NULL,
  UNIQUE(email, workstream)
);
CREATE INDEX ix_thread_due ON thread_state(state, due_at);

-- The CRM cache (§1.5). Refreshed by `cs crm sync`, never authoritative for a write.
CREATE TABLE crm_business (
  business_id         TEXT PRIMARY KEY,
  email               TEXT,
  company_name        TEXT,
  service_number      TEXT,
  business_phone      TEXT,
  subscription_status TEXT,
  template            TEXT,
  language_country    TEXT,
  created_at          REAL,
  synced_at           REAL NOT NULL
);
CREATE INDEX ix_crm_email ON crm_business(lower(email));

-- The resume log. One row per tick — what a fresh process reads to continue.
CREATE TABLE loop_run (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  REAL NOT NULL,
  finished_at REAL,
  due         INTEGER,  handled INTEGER,  replied INTEGER,
  escalated   INTEGER,  errors  INTEGER,
  stopped_why TEXT,
  digest_path TEXT
);
```

`sends` stays exactly as it is: append-only, the dedup truth of record.

Four properties worth stating, because each one is a lesson already paid for:

1. **`due_at` is what makes "eternal" cheap.** A tick's worklist is
   `WHERE state='WAITING_US' AND due_at <= now`, not "every customer". Reminder
   cadence, silence heals and backoff all become one column instead of three
   scattered rules.
2. **`thread_state` is a cache, and is rebuildable.** Everything in it can be
   reconstructed from Gmail plus `sends`. That is what made losing
   `giada_state.json` survivable, and it should be an explicit, tested property
   (`cs loop rebuild`), not an accident.
3. **`workstream` is what lets one loop serve support *and* campaigns.** The
   Centralix roster becomes rows with `workstream='centralix-vonage-migration'`;
   support mail is `workstream='support'`. `CLOSED` on one workstream can no
   longer silence a contact on another — which is the exact defect of §1.1.
4. **A human override becomes a command, not a file edit.** `cs loop set <email>
   --state … --due …`, logged. The git/production hazard disappears because the
   state is no longer a tracked file.

Migration path: the 73 CSV rows import once into `thread_state`; the CSV stays in
git as a **frozen historical artefact** with a header line saying so.

## 2.4 Memory — three layers, and the CRM is the spine

The redesign follows directly from §1.3: **stop asking an LLM to answer questions
that a key answers.** Split what is today one undifferentiated blob pool into
three layers, by whether the thing has a key and whether it has a schema.

| layer | what it holds | keyed by | how it is written | how it is read |
|---|---|---|---|---|
| **1. Identity** | company, contact, phones, `service_number`, subscription status, template, language | `business_id`, normalised email, E.164 phone | **synced from the CRM** (§1.5); never authored by a model | a row read (join) |
| **2. Dossier** | what we know about this customer that the CRM does not: what they bought, what is open, tone to use, known constraints | the same keys | a model proposes a **structured delta**, code applies it field by field | a row read |
| **3. Episodic** | the genuinely unstructured residue: *"Michela Fiorese is over-reactive — do not over-index on the dramatic complaints"* | attached to a key, with embeddings for search **within** that contact | a model writes prose, appended, never rewritten | keyed first; similarity only inside the contact's own episodes |

Three consequences, and they are the point of the whole redesign:

- **Similarity search stops deciding identity.** It only ranks episodes *inside*
  an already-identified contact. `Tandoori Villa` becomes one row because its key
  is one key, not because a model was persuaded.
- **The merge gate keeps its job but loses its power to corrupt.** It still
  reconciles two descriptions, but only when both are already known to be the
  same keyed entity. It can no longer create a sink (June) or a fan-out
  (28 June), because it never decides who is who.
- **Cross-customer contamination becomes structurally impossible**, not merely
  unlikely: a fact with no owner has nowhere to live. The 243 phone-bearing
  `facts:` rows either acquire an owner or are dropped.

**Read path, per contact.** CRM row + dossier row by key, handed to the compose
turn verbatim; episodes only if the compose needs colour. This replaces the
`_memory()` LLM turn in `giada.py` — one fewer LLM call per reply, no run-to-run
variance, and a recall path an operator can inspect.

**Write path, per handled exchange.** The model returns a structured delta
(fields it wants to set, plus an episode if it has one), validated before it
lands. `_remember()`'s current *"salva un ricordo conciso"* produces a paragraph
whose quality nobody can check; a typed delta can be checked, diffed and undone.

**The engine-side work is a separate workstream in a separate repo.** The
key-first resolution redesign, the upstream stop-loss on keyless stubs, and the
one-off cleanup of the support@ corpus are specified in **mrcall-desktop
`engine/docs/execution-plans/memory-entity-keys.md`** — that doc is the source
of truth for everything that touches the engine's memory machinery; this plan
no longer carries it.

**Where the code lives.** Layers 1 and 2 are `cs.db` tables (§2.3), which
`mrcall-cs` owns and can change this week. Layer 3 is the engine's existing blob
machinery, improved per the doc above — a change to *what we put in it and how
we ask*, not a rewrite of `mrcall-desktop`. That boundary matters: the engine
also serves the public desktop product, where there is no CRM and identity
genuinely must be inferred from prose. **The blob design is not wrong; it is
right for a case that is not ours** — and the key-first fix is engine-generic,
so both products benefit.

**Backfill (one-off, separate job).** ~1170 addresses, built from the Gmail
archive rather than the engine's 3.7-month window (§1.4). Own script, own budget,
own model, re-runnable per contact. Explicitly **not** part of the tick.

## 2.5 Prompts

Today there are six prompt blocks as Python string constants inside a 1905-line
file, mixing three different kinds of content and versioned only by `git log` on
the whole file. Split them by lifetime:

| layer | lives where | changes |
|---|---|---|
| **Identity and voice** | the engine profile's `USER_NOTES` (already) | rarely; do **not** duplicate it into the repo |
| **Task prompts** (classify / verdict / compose) | `prompts/<name>.md` in the kernel, clone-overridable | when we improve the loop |
| **Grounding facts** | *generated from data* — the CRM row, `thread_state`, the numbers | every message |

Two hard rules, both from §1.8's live bug:

- **Structured output, not a delimited line.** The verdict moves from
  `STATO|DATETIME|RISPONDERE|MOTIVO` to a schema the engine returns as JSON. A
  prose edit then cannot desynchronise the parser, which is exactly what happened
  when the `ASAP` paragraph was appended.
- **Every task prompt ships with golden cases.** A small file of real inbound
  messages and their expected structured verdict, runnable offline against the
  parser and online against the engine. The `ASAP` regression would have been
  caught by one line in that file.

Third rule, from the campaign's own scar tissue: **anything a model gets wrong
often enough to hurt a customer is computed in Python and handed over finished**
— weekdays, dates, dial codes, the "he already set his forwarding" decision. That
principle is already in `giada.py` and must survive the rewrite intact.

## 2.6 Send posture — the one genuinely blocking decision

Giada sends autonomously (Mario's explicit call for that campaign). The general
support operator is draft-only by charter, and Phase 2 was always "designed, not
enabled". An eternal loop cannot be both, and **an eternal loop that drafts
forever while nobody reviews is worse than no loop** — the drafts pile up and the
customer waits exactly as long as before.

Proposal: **autonomous send gated on a whitelisted intent set, everything else
drafts and escalates.** Concretely, `intent` is classified once per thread
(cheap model, structured output) and only these send without a human:

- call-forwarding instructions and dial codes (fully determined by the CRM row);
- "has the number changed / did you get my mail" status answers;
- credit and top-up mechanics (mechanics we already answer identically every time);
- acknowledgements that answer no question.

Everything else — billing disputes, cancellations, anything angry, anything
whose answer is not grounded in thread + memory + CRM — is drafted and escalated.
This is the "confidence + scope gate" Phase 2 always referred to, made concrete.
It is Mario's decision, not mine (§4).

## 2.7 Guardrails

| guardrail | value |
|---|---|
| Iteration cap | 40 contacts per tick; everyone skipped is named in the digest (never a silent truncation) |
| No-progress detection | a contact whose `attempts` reaches 3 without its state changing goes to `ESCALATED`, not to a fourth try |
| Rate cap | `RATE_CAP` as today (25 default; the campaign wrapper's 400 does **not** carry over to an eternal loop) — stop the whole run and log, never partial-blast |
| Budget | a daily USD ceiling read from `llm_usage`; reaching it **stops** the loop and reports. It never downgrades the model — cut frequency, never quality |
| Kill switch | `CS_PAUSE`, checked in the wrapper, at start-up, and **before every single send** — as today |
| Human gate | nothing outside the whitelisted intents reaches a customer without review |
| Failure policy | first semantic red stops that contact and escalates it; only infrastructural failures (network, timeout, quota) retry, at most once |

One detector that does not exist yet and should: the engine's own Anthropic spend
cap returns its refusal *as the chat response*, so from `cs` an outage looks like
an unparseable model answer. On 2026-07-27 that left 8 customers unanswered for
three hours and was only visible by reading the escalation text. An eternal loop
must recognise it and halt loudly.

---

# 3. Proposed sequence

Each phase is independently useful and independently abandonable.

**Phase 0 — stop the bleeding (hours).** Set `CS_SYSTEM_SENDERS` so the sweep
stops returning bounces. Fix the verdict grammar bug (§1.8) at the prompt, with a
golden case. Neither depends on anything below.

**Phase 1 — the table (1 day).** `contact` / `thread_state` / `loop_run` in
`cs.db`; import the 73 CSV rows; `cs loop status` and `cs loop set`; `cs loop
rebuild` proving `thread_state` is reconstructible from Gmail + `sends`. No
behaviour change yet — the CSV keeps driving the campaign until this is proven.

**Phase 2 — the CRM cache (half a day).** `crm_business` + `cs crm sync` + a
cache-backed CRM adapter, on its own cron. Immediately useful to `cs dossier`,
independent of the loop.

**Phase 3 — the cs-side memory layers (1–2 days here; the engine work runs as
its own workstream).** The dossier table keyed to the CRM and the keyed read
replacing `_memory()`. The engine-side redesign + corpus cleanup live in
mrcall-desktop `engine/docs/execution-plans/memory-entity-keys.md` and proceed
independently — its Goal counts (`Tandoori Villa` = 1, zero new duplicates on
re-processing) are the acceptance gate before this loop leans harder on memory.

**Phase 4 — the loop (2–3 days).** Lift the generic half of `giada.py` into the
kernel as `cs loop`, driven by `unanswered` + `thread_state`; the Centralix
handlers stay behind as a campaign pack. Ships draft-only regardless of the §2.6
decision, so it can be watched for a few days before anything sends.

**Phase 5 — prompts and structured verdicts (1–2 days).** Externalise the task
prompts, move the verdict to structured output, add golden cases.

**Phase 6 — the memory backfill (1 day of work, then it runs).** The offline
per-contact dossier build from the Gmail archive.

**Phase 7 — send posture.** Only after §4 is answered and Phase 4 has run
draft-only long enough to read its digests.

---

# 4. What I need from Mario

Three questions. The first blocks Phase 7 only; the other two block Phase 1.

1. **Send posture (§2.6).** Whitelisted-intent autonomous send, or draft-only
   forever with a review ritual? My recommendation is the whitelist — draft-only
   at eternal-loop volume just moves the queue.
2. **"The structure of the table" (§0).** I have read it as: the CSV plus the
   JSON sidecar collapse into real tables in `cs.db`, and the CRM joins them.
   Confirm, or point me at the table you actually meant.
3. **Scope of "always running".** My reading is a 10-minute tick over the support
   mailbox for the ~245 non-TEST businesses, with campaigns as workstreams inside
   the same loop. Not: a resident daemon, and not the 1009 TEST businesses.

---

# 5. What this proposal deliberately does not do

- **It does not touch the live campaign.** `CS_PAUSE` is set, and
  `avv.vincenzorusso@gmail.com` still has to migrate on 2026-07-30 19:00 with the
  Centralix lines dying on the 31st at 09:00. That deadline owns the next two days;
  none of the work above should start before it is met.
- **It does not re-derive the reverted `_post_migration` patch.** That fix
  answers migrated customers *within the campaign's shape*. If Phase 4 lands, the
  problem it solved disappears structurally — a `CLOSED` campaign row would no
  longer silence a contact's `support` workstream. If Phase 4 is not going to land
  soon, the patch should be re-derived instead, because customers are waiting now.
- **It writes no code and starts no loop.**
