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

**Status: phase 1 is built.** Steps 0–5, 7 and 8 are code in the tree —
`cs/mailboxes.py` (new), `cs/gmail_drafts.py`, `cs/gmail_archive.py`,
`cs/config.py`, `cs/cli.py`, `tests/test_contact_history.py` and `tests/run.sh`
gate 44 — uncommitted, no version bump, not released. Steps 6 and 9 are
outstanding and carry the FULL tier with them.

## Shape

Kernel code change, in `cs/mailboxes.py` (the credential handover, the session
cache and the fan-out), `cs/gmail_archive.py`, `cs/gmail_drafts.py`,
`cs/config.py` (`load(engine_owner_uid=…)`, which is how one process speaks to
a second engine profile without mutating its own environment), `cs/cli.py` and
the four gating call sites. No new env key and no new manifest field: the
credential comes from the engine's existing handover, and the fan-out is not
optional.

**The fan-out is not a knob.** The charter's dedup invariant says Gmail Sent is
the ground truth and that no dedup-source knob exists. A flag that let a clone
gate on one mailbox while another gated on five would be that knob wearing a
different name, so no such flag is added.

What the readable set *is*, stated honestly: every account in `CS_ACCOUNTS`.
That is configuration, edited for engine reasons, so the scope is coupled to a
list nobody maintains with dedup in mind. The kernel therefore **prints the
scope it actually read** on every answer. A scope that can silently narrow is
the incident; a scope that narrows visibly is a fact the operator can act on.

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

## Prerequisite — a profile per mailbox that must be read

This plan reaches exactly the mailboxes with an engine profile, because that is
what makes a credential retrievable. On `124-cs` the reply that was missed came
from a founder mailbox that has **no** profile, and two of the three mailboxes
that clone needs read have none either. So without this prerequisite the plan
ships a FULL-tier change to send gating that does not fix the incident that
motivated it.

The clone's own brief already names "a profile per mailbox" as its default
option, and that is the prerequisite here: the mailboxes a clone needs gated
must exist as engine profiles before step 6 changes any gate. Standing them up
is the clone operator's action, not the kernel's. Until then the kernel is
honest about what it could not see — which is the whole point of step 5 — but
it does not pretend the incident is closed.

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

### 6. Move the real gating call sites onto the fan-out

The sites that actually gate on `sent_to`: `campaign.py:108`, its reply gate
`campaign.py:120`, `cli.py:797`, and `draft_state.py:290`. These are what let a
machine compose four drafts to someone already answered.

Three sites named in the first draft of this plan are **not** part of it.
`unanswered.py:520-521` and `review.py:86` go through `inbound_recent` /
`sent_recent`, which step 4 deliberately excludes because they decide "is this
us" from `settings.email_address`; extending them is separate work with its own
correctness question. `cli.py:856` is a print, not a gate.

*Verify*: this is the step that changes autonomous behaviour on both clones, so
it is what sets the release's re-test tier — see below.

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

### 9. Re-stamp the prose that this makes false

Six stamped surfaces tell the operator that prior-contact evidence is one
mailbox: `CLAUDE.md.j2:190-191`, `cs-operator/SKILL.md.j2:133-135`,
`ARCHITECTURE.md.j2:101-105`, `cs-customer:113-117`, `cs-triage-mail:57,109`,
`docs/projects/README.md.j2:148`. They go false at step 6, so the release is a
`cs update` re-stamp on both clones and not only a library upgrade. The new
`unreadable` outcome from step 5 is documented in that same pass — skills read
the printed line, so an outcome nobody described is an outcome nobody handles.
`cs history` itself is described here too; phase 1 stamps only its permission
entries (step 7), never prose about what it means.

### 10. Gates and tier

Semantic gates only, per house style. This release touches send gating on both
clones, which is the charter's FULL list: **the re-test tier is FULL, both
clones, and FULL means the suite runs on both before the tag ships.** The
version is at least **MINOR** — the CLI surface grows a verb, an outcome and a
changed refusal message.

## Risks

- **The prerequisite does not land.** If a clone does not stand up profiles for
  the mailboxes it needs gated, step 6 changes send gating without closing the
  incident. That is the largest risk here and it is not a kernel risk.
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

- A mailbox with no engine profile, and domain-wide delegation. Both wait on the
  rule of two — but note this is exactly what `124-cs` needs, so the prerequisite
  above is how that clone gets covered without the kernel growing a
  single-company mechanism.
- `inbound_recent` / `sent_recent` and the surfaces built on them.
- Any change to what the engine judges: existence only.
