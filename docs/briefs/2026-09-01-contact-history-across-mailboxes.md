# Contact history across mailboxes — brief

## Problem

Every clone's `CLAUDE.md` makes it a NEVER: no cold mail to an address that
already has a thread, no re-contact inside `DEDUP_DAYS`. Both rest on the
operator knowing whether the company has already written to a person. The kernel
ships no verb that answers that.

It ships three that answer narrower questions, and they are easy to mistake for
it. `cs contacted` reads the operator mailbox's Gmail Sent folder over a rolling
window, 30 days by default. `cs thread` reads the engine archive for the same
mailbox. `cs ask` reads the engine's processed state over that same archive. All
three are bounded by one mailbox, and the first by a window as well.

Sharing a bound means sharing a blind spot. When they agree, the agreement reads
as three sources corroborating each other; it is one absence reported three
times.

Incident, 2026-09-01, `124-cs`. A prospect submitted a private-label request on
2026-07-02 through the company's web configurator. `cs thread` returned no
threads for her address, `cs ask` reported nothing in the archive, and
`cs contacted` printed `no — 0 message(s) [Gmail Sent, ground truth]`. Four
unsent drafts to her sat in the engine store. `/cs-review` concluded she had
never been answered, listed her at 61 days waiting, and composed a reply opening
with an apology for two months of silence.

She had been answered on 2026-07-03 — the next day — by a co-founder writing from
his own company mailbox, To: her, Cc: a shared alias. The operator mailbox is on
no header of that message, so it exists in no surface the operator reads. The
apology was caught before sending.

The four drafts were not independent evidence either. The engine composed them
under the same bound, which is why they exist: the same error, upstream, counted
a fourth time.

## Why the near-miss fixes are not the fix

`EMAIL_ALIASES` on the engine profile is what let the operator see a *different*
founder's out-of-mailbox replies in three other threads and correctly read them
as answers. It is genuinely load-bearing and the clone should keep it current.
But an alias declares "this sender is us"; it does not make a message appear in a
mailbox that never received it. It fixes attribution for mail that passes through
the operator mailbox and reaches nothing else.

Widening `DEDUP_DAYS` reaches it even less. The prospect above was at 61 days; a
60-day gate misses her by one. There is no correct window, because "have we ever"
has no natural horizon. And `DEDUP_DAYS` is the re-contact policy — moving it
changes when the operator may write again, which is a commercial decision in the
clone, not a fix for an evidence gap in the kernel.

Asking humans to always copy the operator mailbox is a convention that must hold
every time, on every device, forever. The first reply typed from a phone drops a
customer out of view, silently. Worth doing; worthless to rely on.

## Root cause

A company answers customers from several mailboxes. The operator's evidence is
scoped to one of them. The question it actually needs answered is unimplemented,
so it gets reconstructed by hand from partial sources and eventually
reconstructed wrong.

One contributing factor is a label. `cs contacted` prints
`{YES|no} — {mailbox} wrote to {addr} in the last {N} days ({n} message(s))
[Gmail Sent, ground truth]`. It already names its window and its mailbox; what
it never says is that this is the *only* mailbox it can see. "Ground truth"
sitting at the end of that line reads as a verdict on the company, and in the
incident it was read as one.

**The gap is not only in what a human can ask.** The places where the kernel
gates on prior contact are single-mailbox: the campaign runner
(`campaign.py:108`) and its reply gate (`:120`), the CLI send path
(`cli.py:797`) and draft state (`draft_state.py:290`). A verb that only a human
invokes leaves every one of them unchanged — which is why the incident produced
four machine-composed drafts before any human looked. Any fix that stops at a
new verb fixes the reading and not the writing.

## Design

**Credentials come from the engine, never from the operator's environment.**
Invariant 4 of the charter already settles this: *the mailbox credential is the
engine's to hand over, not the operator's to retype.* `cs init` reads a
mailbox's own password with owner-authenticated `settings.get_secret`
(`project_init.py:155-190`), and the kernel already holds a per-uid refresh
token (`config.py:286-289`). That is the surface to extend. A second env key
holding `address:app-password` pairs would invert the invariant, and an app
password carries send capability that nothing in the kernel could revoke —
`send_mail.py:165-168` logs in with whatever pair Settings holds, so
"read-only" would be a convention in the calling code and nothing more.

Extending the existing handover also removes the need for a new registry — at
the price of a requirement rather than a fact: the kernel reaches a mailbox
only if that mailbox has an engine profile, because that is what makes its
credential retrievable. Which mailboxes have one, and what follows when they
do not, is under Deliberately out of scope.

**A credential argument on the IMAP path.** `_imap(settings)`
(`gmail_drafts.py:40`) logs in with the single `settings.email_address` /
`settings.email_password` pair. It takes an explicit `(address, password)`,
today's behaviour staying the default so no caller changes. Only `sent_to` is
reached this way: `thread_with` (`:381`) and `inbound_recent` (`:221`) decide
"is this us" from `settings.email_address` and would answer wrongly for another
mailbox, so they stay single-mailbox until they are given the same treatment.

**A fan-out over `sent_to`.** `gmail_archive.sent_to()` already treats
`days=None` as "no window" (`gmail_archive.py:88,102`), so the unbounded read
exists and only the CLI bounds it. The new function iterates the operator
mailbox plus every other readable account, calls `sent_to(..., days=None)` on
each, and returns rows tagged with the mailbox they came from.

The window is not what this costs. `sent_to` fetches every matching UID's header
and filters by date afterwards (`:104-118`), so an unbounded read costs what a
30-day read costs. What multiplies is the per-call TLS, LOGIN, LIST and SELECT,
and the campaign runner pays that once per drafted contact at `campaign.py:185`,
plus once per call at `:358`, `:462` and `:548`. Times N mailboxes, that is the number that decides
whether this is usable, so the fan-out holds one session per mailbox per
process.

**A mailbox that cannot be read reports `unreadable`, never an empty result.**
This is the property the whole brief exists for: if a failed login and a genuine
absence render the same, the verb reproduces the incident inside the fix. Two
consequences the current CLI cannot express and that this work must build. The
existing `cmd_contacted` signals "no" by exiting 1 (`cli.py:245`), so a failed
login would read as "never contacted" — the exact inversion. And a degraded
source must survive into the machine-readable shapes, not only the printed line;
the existing convention for that is the surfaced note (`cli.py:271,298-299`).

**A send gate that meets `unreadable` refuses, and says which mailbox.** The
charter's standing instruction is to escalate on uncertainty. Fail-open
reproduces the incident at machine speed; fail-closed can halt outreach on one
dead profile, which is the accepted cost — a contact not written to today is
recoverable, a second cold mail to someone a founder answered two months ago is
not. Reading and drafting continue; only sending stops.

**The gating call sites, not only a new verb.** The four single-mailbox gates
listed under Root cause are what actually stopped a machine from knowing. They
move to the fan-out, or the fix addresses the reading and leaves the writing
exactly as it was. `unanswered` and `review` are not among them: they read
through `inbound_recent` / `sent_recent`, which decide "is this us" from the
operator's own address and would answer wrongly for another mailbox. Extending
those is separate work with its own correctness question.

**A CLI surface** printing per mailbox, with unreadable sources named. And
`cmd_contacted` states its own scope in its own output — one mailbox, N days, a
dedup gate — rather than ending on an unqualified "ground truth". Leave
`--days` at 30; it is the dedup gate and is correct as it is.

## Deliberately out of scope

This answers existence only. Whether a message needed an answer, whether it was
an auto-reply, whether a thread is settled — all remain the engine's judgement,
per `§ 0b` of the clone charter. The verb must not grow a second opinion about
any of that.

**A mailbox with no engine profile.** The design above reaches every mailbox the
kernel can already retrieve a credential for, which is every mailbox in
`CS_ACCOUNTS`. A mailbox with no profile is out of scope — and this matters more
than it sounds, because the `124-cs` mailbox whose reply was missed is one of
them, and two of the three mailboxes that clone needs read have no profile
either. The kernel does not grow a mechanism for that. The clone's own brief
already names "a profile per mailbox" as its default option, and that is the
prerequisite: profiles first, then the gates change. Building a profile-less
path in the kernel for one company would be the rule of two broken in the exact
way the charter names; the shape it should take when a second company needs it
is the service account below, not an env registry.

**Domain-wide delegation.** The stronger credential is a service account with
delegation restricted to `gmail.readonly`: the admin authorises once, no mailbox
owner generates or hands over anything, and it cannot send. `cs/drive.py`
already loads a service account from `firebase_sa_path` with a read-only Drive
scope and records in its header that delegation is not enabled. The cost is that
delegation runs through the Gmail API, so it needs a read path alongside
`imaplib`. That is the right answer for the profile-less case above and it does
not block anything here.

Worth recording for whoever discusses this with mailbox owners: the query is
`UID SEARCH TO <address>` against the Sent folder, fetching headers. It is not a
general read of somebody's mail, and describing it accurately is what makes the
authorisation real.

## Rejected approaches

**`CS_READ_MAILBOXES`, an env key of `address:app-password` pairs.** Rejected on
three counts. What the engine handover wins is provenance and revocability, not
a smaller capability: the process still ends up holding a send-capable password
for another mailbox. It is auditable, it is revoked by revoking the profile, and
nobody retypes it — and the `gmail.readonly` service account below is what would
actually remove the send capability. It inverts invariant 4, which puts the mailbox credential in the
engine's hands rather than the operator's. An app password has no scope and does
not expire, so it grants send capability that no kernel code path could take
away. And parsing it "exactly like `Settings.account_map`" would inherit that
parser's silent drop of a malformed pair (`config.py:336-341`): a typo would
render a mailbox as an absence, which is precisely the failure this brief
exists to prevent. A password-bearing Settings field would also need adding to
`SECRET_FIELDS`, or `cs config` prints it (`config_report.py:79-88`).

**Widening the `--account` refusal instead.** `cs` today refuses per-account
work on the ground that "there is one mail credential, not one per account"
(`cli.py:1811-1831`). That becomes false the moment the kernel retrieves a
second profile's password, so the refusal's message is corrected as part of this
work rather than the refusal being widened into a second mechanism.
