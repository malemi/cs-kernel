---
status: active
started: 2026-09-01
brief: ../briefs/2026-09-01-contact-history-across-mailboxes.md
---

# Contact history across mailboxes — execution plan

<!-- doc-scope:start -->
Scope: the ordered steps that make "has this company ever written to this
person" answerable across every mailbox the kernel can read, and how each step
is verified. The what and why are in the
[brief](../briefs/2026-09-01-contact-history-across-mailboxes.md); the charter
they must obey is [`CLAUDE.md`](../../CLAUDE.md).
<!-- doc-scope:end -->

**Status: phase 1 shipped as `v0.37.0`, phase 1b as `v0.38.0` — live-accepted on `124-cs` twice.**
Phase 1 (steps 0–5, 7, 8) is the fan-out, the `unreadable` outcome, the scope
line and `cs history`. Phase 1b (1b.1–1b.3) adds the mailboxes that hold no
engine profile.

**Phase 2 — steps 6 and 9 — is built and uncommitted**: every prior-contact
gate reads the union scope and refuses when a mailbox cannot be read
(`cs/campaign.py`, `cs/cli.py`'s dossier verdict, `cs/draft_state.py`), and the
six stamped surfaces that said the evidence was one mailbox now say what it is,
including the refusal outcome (`CLAUDE.md.j2`, `cs-operator`, `cs-customer`,
`cs-triage-mail`, `cs-campaign-tick`, `docs/ARCHITECTURE.md.j2`,
`docs/projects/README.md.j2`). Gate 46 holds it. No version bump: this is the
FULL-tier release, and the tag plus the two clone upgrades are the work that
remains.

## Shape

Kernel code change, in `cs/mailboxes.py` (the credential handover, the session
cache and the fan-out), `cs/gmail_archive.py`, `cs/gmail_drafts.py`,
`cs/config.py` (`load(engine_owner_uid=…)`, which is how one process speaks to
a second engine profile without mutating its own environment), `cs/cli.py` and
the four gating call sites. Two credential sources, one fan-out: an account
with an engine profile hands its own password over (no env key, no new
registry), and a mailbox with no profile is declared in the manifest
(`[operator].read_mailboxes`) with its IMAP password in the clone's env
(`CS_READ_MAILBOX_PASSWORDS`) — one field and one key, both loud when
malformed. The fan-out itself is not optional.

**The fan-out is not a knob.** The charter's dedup invariant says Gmail Sent is
the ground truth and that no dedup-source knob exists. A flag that let a clone
gate on one mailbox while another gated on five would be that knob wearing a
different name, so no such flag is added.

What the readable set *is*, stated honestly: every account in `CS_ACCOUNTS`
plus every address in `[operator].read_mailboxes`. Both are configuration,
edited for other reasons, so the scope is coupled to lists nobody maintains
with dedup in mind. The kernel therefore **prints the scope it actually read**
on every answer. A scope that can silently narrow is the incident; a scope that
narrows visibly is a fact the operator can act on.

## Two releases, not one

Steps 0–5, 7 and 8 ship first and touch **no send gate**: they build the
fan-out, the `unreadable` outcome and the CLI surface, so a human can ask "has
this company ever written to this person" and get an answer that names its own
scope. Useful on the day it lands, below FULL, and it puts humans through the
fan-out before any machine depends on it.

Step 6 — moving the gates — and step 9 wait for the prerequisite below. Shipped
before it, that half buys autonomous behaviour change on both clones plus the
fail-closed halt risk, for no coverage gain on the clone that actually had the
incident. It is the FULL-tier release and it is a separate decision.

## Phase 1b — reach the profile-less mailboxes (rewritten 2026-09-02)

The brief's binding constraint is that mailbox owners contribute nothing, so
"stand up a profile per mailbox" is not a prerequisite — it is a rejected
approach. The mailboxes without a profile are reached over **plain IMAP with
app passwords the operator already holds** (the operator's decision,
2026-09-02: the standard protocol over a vendor API). The read path already
exists — `_imap(settings, credential=…)`, `sent_to_on`, `inbound_since_on` —
so 1b adds configuration and wiring, not a new protocol client:

- **1b.1 — manifest field `read_mailboxes`** — BUILT. A TOML list of plain
  addresses under `[operator]` (`cs/manifest.py:64`), flattened to the
  comma-separated form every other multi-value setting uses
  (`settings_overrides`) and surfaced as `Settings.read_mailboxes` +
  `read_mailbox_list`. `CS_READ_MAILBOXES` layers over it like any other
  setting — the key exists in the field already, and a field without the alias
  would have ignored it in silence. Same-domain guard as `CS_ACCOUNTS`, a
  shallow address check, a refusal of the clone's OWN operator address (already
  read first-class; declared again it is a second credential for the identity
  mailbox and a double count in the scope line) and a refusal of an
  `address:password` value with the password withheld — all LOUD at config load
  (`cs/config.parse_read_mailboxes`). Stamped as `read_mailboxes = []` with its
  operator doc in `cs/templates/project/manifest.toml.j2`, and both env keys are
  documented in `cs/templates/project/.env.example.j2`. New manifest field ⇒ the
  release is at least MINOR.
- **1b.2 — the credential map, strict** — BUILT. ONE env key,
  `CS_READ_MAILBOX_PASSWORDS`, holding `address:password` pairs in the clone's
  own `.env` beside `EMAIL_PASSWORD` and in no repo file
  (`cs/config.parse_read_credentials`). Every malformed shape fails config load
  loud: no colon, empty password, mangled address, a credential for an
  undeclared mailbox, one mailbox declared twice. A password containing the
  list separator is refused rather than truncated. A declared address with no
  entry does NOT fail load — it is `unreadable — no credential configured for
  <address>`, with the fix in the message. The value is a `Settings` field, and
  therefore in `config_report.SECRET_FIELDS`, so `cs config` reports presence
  and never the value; error paths are redacted by the existing `_redact`; it
  reaches no send path, and `cs/send_mail.py` cannot even name it.
- **1b.3 — wire into `cs/mailboxes.py`** — BUILT. `readable()` appends the
  declared mailboxes after the profile accounts, deduped by address, each
  session-cached like any other; both fan-outs and therefore `cs history` see
  them with no new flag, and the scope line's denominator counts profiles ∪
  declared.
- **1b.4 — prove it on `124-cs`** — NOT DONE, and not kernel work: place the
  credentials, then
  `cs history <the prospect's address>` must report the co-founder's 2026-07-03
  reply and name the mailbox. This is the acceptance test the incident
  defines, and it asks nothing of any mailbox owner.

Step 6 (the gates) then reads profiles ∪ declared mailboxes and is unblocked by
1b alone.

## Steps

### 0. Prove the credential is actually retrievable

Before any code: for each account that must be gated, run
`cs --account <name> rpc settings.get_secret '{"key":"EMAIL_PASSWORD"}'` and
confirm it returns. The handover needs a stored session, a running daemon for
that profile, and `EMAIL_PASSWORD` genuinely present in that profile's `.env`.
The third decides whether the rest of this plan is buildable at all.

**Done, and it works.** On `mrcall-cs`, the non-default account
`mario.alemi@mrcall.ai` returns its own `EMAIL_PASSWORD` through that call. So
the kernel can obtain a second mailbox's credential unattended, without an env
key and without anyone retyping a secret — which is the premise every step below
rests on.

Still to run before step 6 gates anything: the same call on each `124-cs`
account, where the prerequisite above is unmet anyway.

*Verify*: a real call per account. A profile that cannot hand its password over
is a blocked prerequisite, not a step to code around.

### 1. `_imap` takes an explicit credential

`_imap(settings)` (`gmail_drafts.py:40`) grows an optional `(address,
password)`. Omitted, it behaves exactly as today, so no existing caller changes.

*Verify*: existing gates covering drafts and archive stay green with no call
site edited.

### 2. Retrieve another mailbox's credential from the engine

A helper that, given an account from `CS_ACCOUNTS`, returns that mailbox's
address and password through owner-authenticated engine calls, the same path
`cs init` uses (`project_init.py:155-190`). Cache per process: this runs inside
send gates and must not make one RPC per candidate.

**TWO calls, not one.** `settings.get_secret` serves SECRET keys only and
refuses anything else (engine `rpc/methods.py:1924`), so it yields the password
and cannot yield the address; the address is the non-secret `EMAIL_ADDRESS` in
`settings.get`'s `{values}`. Both shapes are charter-listed. Secrets stay
one-key-per-call — `settings.get` masks them deliberately, which is exactly why
the password needs its own named call.

Authenticating as the OTHER profile is `config.load(engine_owner_uid=<uid>)`:
the uid enters as an init value (the highest settings source), so
`_derive_paths` derives that uid's own token/refresh files and the handshake
presents that profile's token. `cs --account` achieves the same thing for a
whole invocation by swapping the env key; a fan-out speaks to several profiles
in ONE run, and mutating the process environment per account would leak into
everything the tick does next.

*Verify*: a credential is never read from the environment, and never logged.

**What this buys, stated plainly**: provenance and revocability, not a smaller
capability. After this step the cron process holds another person's
send-capable password, fetched under that person's own identity. That is
strictly better than the same secret pasted into an env file — it is auditable,
it is revoked by revoking the profile, and nobody retypes it — but it is not
read-only, and the eventual `gmail.readonly` service account is what would make
it so.

### 3. One connection per mailbox per process

The cost is not the window. `sent_to` fetches every matching UID's header and
filters by date afterwards (`gmail_archive.py:104-118`), so `days=None` costs
what `days=30` costs and the unbounded read multiplies nothing. `_fetch_headers`
is already in use (`:229`, `:458`), so there is no unused batching win to
collect.

The real cost is per-call TLS, LOGIN, LIST and SELECT, and `campaign.py:185`
pays it once per drafted contact (also `:358`, `:462`, `:548`). Multiplying that
by N mailboxes is what would make this unusable. So: reuse one IMAP session per
mailbox per process. If that is not enough, the fallback is a per-run
address→last-sent index built once and queried in memory.

*Verify*: **not measurable in phase 1** — the count per campaign run needs step
6, which is what puts a gate on the fan-out, and nothing in `campaign.py` calls
it yet. The property is held by proxy instead, in gate 44: two fan-outs over two
mailboxes open TWO IMAP sessions, not four, and a session that died between
calls is reopened rather than raised. The per-run count against the real runner
belongs to step 6 and is recorded there.

### 4. `sent_to_across()` — the fan-out

Iterates the operator mailbox plus every other account, calls
`sent_to(..., days=None)` on each, returns rows tagged with their mailbox and a
separate set of mailboxes that could not be read. `thread_with` and
`inbound_recent` are NOT part of this: they decide "is this us" from
`settings.email_address` (`gmail_archive.py:381,221`) and would answer wrongly
for another mailbox. They stay single-mailbox and say so.

The fan-out covers `inbound_since` as well as `sent_to`. `inbound_since`
(`gmail_archive.py:167-200`) is safe to fan out because it uses no self-address
— unlike `thread_with` and `inbound_recent`, it decides nothing from "is this
us". This is what makes `campaign.py:120`'s reply gate reachable in step 6.

*Verify*: one mailbox deliberately given a bad credential appears as unreadable
and never as an empty result.

### 5. `unreadable` has to survive into every shape

Two existing behaviours block it. `cmd_contacted` signals "no" by exiting 1
(`cli.py:245`), so a failed login currently reads as "never contacted" — the
exact inversion this work exists to prevent; it needs a third outcome. And the
machine-readable shapes (`unanswered --json`, the dossier verdict) carry no
degraded-source field; the existing convention to follow is the surfaced note
(`cli.py:271,298-299`).

*Verify*: a gate asserting that a mailbox which cannot be opened never renders
as absence, in the printed line, in the exit status, and in JSON.

**What a send gate does with `unreadable`: it refuses and says why.** This is
the decision the first draft of this plan left open, and it has only one answer
consistent with the charter, whose invariant is to escalate on uncertainty.
Fail-open reproduces the incident at machine speed — the whole point is that an
absence of evidence was read as evidence of absence. Fail-closed can halt
outreach on one dead profile, which is the real cost and is accepted: a contact
not written to today is recoverable, a second cold mail to someone a founder
answered two months ago is not. The run stops sending, names the mailbox it
could not read, and leaves reading and drafting untouched.

Today an IMAP failure is not fail-open, it is fail-ugly: a bad LOGIN raises
`imaplib.IMAP4.error` which `cli.py:1838-1868` does not catch, so it surfaces
as a traceback, and a connection-level failure is misreported as "cannot reach
the engine at wss://…". The per-mailbox failure message must be produced by
the fan-out itself and must never reach that handler.

`pending` must surface a contact it cannot judge as its own item, not drop it.
A contact that silently disappears from a list is the same class of error as
an absence read as a fact.

`campaign.send_first` (`campaign.py:675-700`) deliberately does not dedup
against Sent, so it stays uncovered by this work. Say so rather than leaving a
reader to assume every send path is gated.

### 6. Move the real gating call sites onto the fan-out — BUILT

`campaign._sent_threads_to` and `campaign._inbound_since` return
`(rows, unreadable)` from the fan-out; every caller acts on both halves.
`_evidence_refusal` is the shared fail-closed refusal (the `blocked` shape the
CS_PAUSE and escalation refusals already use, so every caller reports it
unchanged), and `_unjudgeable` is the worklist item for a contact that could
not be judged. Sites: `_composed_draft_items`, `_fixed_template_items`,
`reconcile`, `send_draft`, `queue_draft`, `send_reminder`, `send_sms`; the
dossier's read and verdict in `cli.cmd_dossier`; and `draft_state`'s default
`inbound`/`sent` reads. `send_first` stays uncovered by design and its
docstring now says so.

Two of those sites needed more than the fan-out to be honest:

- **The dossier verdict is about "have we EVER", not about the window.** It
  reads `sent_to_across(days=None)` and applies `--dedup-days` in memory for
  the dedup line only. Bounded, a colleague's 61-day-old reply — with every
  mailbox readable — still came back as `cold contact`, which is the incident's
  own shape surviving inside the check meant to prevent it. The read costs the
  same: `sent_to` fetches every matching UID's header and filters by Date
  afterwards. When history exists outside the window the verdict says so and
  names the mailbox and the date.
- **The review qualifies the row, not the digest.** Every row carries
  `evidence_incomplete` — populated only for `ready`, the one verdict that
  rests on an absence — and the ready block prints it INLINE under the row.
  The run-level note stays, but a footer below the next block is read after the
  decision, if at all. This keeps the review's contract intact: nothing is
  retired, no verdict state is invented, the row is qualified.

Three sites named in the first draft of this plan are **not** part of it.
`unanswered.py:520-521` and `review.py:86` go through `inbound_recent` /
`sent_recent`, which step 4 deliberately excludes because they decide "is this
us" from `settings.email_address`; extending them is separate work with its own
correctness question. `cli.py:856` is a print, not a gate.

*Verify*: gate 46. Every sender and `reconcile` refuse on an unreadable
mailbox, naming it, with every mutation path (SMTP, SMS, the Gmail draft
append, `campaign.update_contact`) wired to fail the test if reached; `pending`
surfaces the unjudgeable contact instead of dropping it; a colleague's message
in another mailbox stops a send the operator mailbox alone would have allowed;
ONE login per mailbox per process across a 4-contact run (2, not 8); the
dossier verdict fails closed AND does not call a two-month-old colleague reply
a cold contact; the review carries the gap on the ready row, prints it inline,
and never retires anything. This is the
step that changes autonomous behaviour on both clones, so it is what sets the
release's re-test tier — see below.

### 7. The CLI surface

The verb is **`cs history <email>`**: unbounded, both directions, printed per
mailbox, naming every unreadable source, `--json` carrying the same scope and a
degraded-source note. `cs contacted` states its own scope in its own line — one
mailbox, N days, a dedup gate — instead of ending on an unqualified "ground
truth". `--days` stays 30.

**Rule 6, decided: a new verb, not a fold.** `contacted` is the re-contact GATE
(one mailbox, one window, exit 1 = a read absence); `thread` is the engine's
archive of that same mailbox; `dossier` composes both per contact. Folding the
fan-out into `dossier` was the closest call and is rejected on two grounds: its
`sent_to` call (`cli.py:797`) IS one of step 6's gate sites, so widening it
there moves a gate ahead of the prerequisite; and short of that, `dossier`
would print a company-wide history section above a verdict still computed from
one mailbox — two answers to one question in one output. A `contacted
--anywhere` flag was rejected too: it gives one exit code two meanings, and the
stamped skills read that verb's printed line. Each verb instead names its own
scope on every answer, which is what makes two neighbouring questions safe to
have.

No `cs-` prefix: that convention is for stamped skills and commands
(`cs-review`, `cs-triage-mail`), while kernel verbs are already `cs <verb>`.

**One stamped edit is taken here, by exception**: the four canonical `history`
spellings are added to the clone allow list in `.claude/settings.json.j2`.
Strictly additive, it cannot break a clone that has not re-stamped, and without
it phase 1 ships a verb that prompts for permission on the surface it was built
for. Everything else stamped stays in step 9.

### 8. Correct the `--account` refusal

`cli.py:1811-1831` refuses per-account work because "there is one mail
credential, not one per account". That becomes untrue the moment step 2
retrieves a second profile's password. Correct the message.

### 9. Re-stamp the prose that this makes false — BUILT

Seven stamped surfaces now state the union scope and the refusal outcome, so
the release is a `cs update` re-stamp on both clones and not only a library
upgrade. `CLAUDE.md.j2` § 5 (the dedup NEVERs, plus "an unreadable mailbox is
not a no") and § 8 (what the scope is, and where the passwords live);
`cs-operator` § 4b (the founder sweep is the one step that WORKS another
mailbox, not the only one that sees one); `docs/ARCHITECTURE.md.j2` (the
`--account` section, `history`'s own refusal, a section on the evidence scope,
and the pipeline's dossier line); `cs-customer` (the dossier's prior-contact
half and its `STOP — evidence incomplete` verdict); `cs-triage-mail` §§ 1 and
2b (the answered-check across mailboxes, and `UNKNOWN` is not "no");
`cs-campaign-tick` (the new `evidence_incomplete` worklist action, with its own
branch); `docs/projects/README.md.j2` (the `--account` paragraph).

An outcome nobody described is an outcome nobody handles: the skills read
printed lines and worklist JSON, so both the refusal and the new action are
documented where they are read, in operator terms.

### 10. Gates and tier

Semantic gates only, per house style. This release touches send gating on both
clones, which is the charter's FULL list: **the re-test tier is FULL, both
clones, and FULL means the suite runs on both before the tag ships.** The
version is at least **MINOR** — the CLI surface grows a verb, an outcome and a
changed refusal message.

## Risks

- **The read credential can send.** An app password has no scope and does not
  expire; read-only is a property of our calling code. Accepted by the
  operator with that stated; contained by the 1b.2 handling rules, and the
  acceptance test asserts the credential is absent from every send path.
- **A revoked or rotated app password.** The mailbox turns `unreadable`, named,
  with the fix in the message — and under step 5's fail-closed rule that stops
  sending until the operator updates the env. Loud by design.
- **Per-call connection cost at gate time.** Step 3 owns it. If session reuse is
  not enough, the fallback is a per-run index — never a per-clone flag, which is
  the forbidden knob.
- **Fail-closed halts outreach.** One unreadable profile stops sending for the
  whole run. Accepted deliberately in step 5; it must be loud and specific
  enough that the operator knows within one run which mailbox to fix.
- **An engine that cannot hand over a credential.** Every such mailbox becomes
  unreadable rather than empty, which is correct, but combined with fail-closed
  it means a stopped daemon stops outreach. Step 0 is what stops that being a
  surprise.

`founder_sweep` is NOT a risk here and NOT the forbidden knob: it surfaces
inbound mail through engine reads, a different question, and disabling it
changes no gate.

## Out of scope

- `inbound_recent` / `sent_recent` and the surfaces built on them.
- How a provider issues an IMAP credential (Google app password, another
  provider's equivalent, a plain password on self-hosted mail): clone
  operations, documented, never kernel code. The kernel speaks IMAP and stays
  provider-neutral.
- Any change to what the engine judges: existence only.
