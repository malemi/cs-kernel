# Contact history across mailboxes — brief

## The binding constraint — mailbox owners contribute nothing

The people whose mailboxes must be read answer customers from their own
accounts and will not stand up an engine profile, run a daemon, or maintain
anything, ever. A design is admissible only if the sum of what it asks from
them going forward is zero. Actions by the operator or the domain admin are
acceptable; recurring actions per mailbox owner are not. The app passwords for
these mailboxes already exist, so the credential needs nobody's cooperation.

## Problem

Every clone's `CLAUDE.md` makes it a NEVER: no cold mail to an address that
already has a thread, no re-contact inside `DEDUP_DAYS`. Both rest on knowing
whether the company has already written to a person — and a company writes
from several mailboxes, while the operator's evidence is scoped to one.

`cs contacted`, `cs thread` and `cs ask` share that bound, so when they agree,
the agreement reads as three sources corroborating each other and is one
absence reported three times.

Incident, 2026-09-01, `124-cs`. A prospect submitted a private-label request on
2026-07-02. All three verbs reported no contact; four unsent drafts to her sat
in the engine store; `/cs-review` listed her at 61 days waiting and composed a
reply apologising for two months of silence. She had been answered the next
day, by a co-founder writing from his own mailbox. The operator mailbox is on
no header of that message, so it exists in no surface the operator reads. The
apology was caught before sending.

Since `v0.37.0` the kernel fans out over every account in `CS_ACCOUNTS`,
reports a mailbox it cannot read as `unreadable` rather than absent, and prints
the scope it actually read. That machinery is correct and stays. What it cannot
do is reach the mailboxes that matter here: on `124-cs`, two of the three
mailboxes that must be read — including the one that answered — have no engine
profile, and under the constraint above they never will.

## Design

**One fan-out, two credential sources.** The fan-out, the `unreadable` outcome
and the scope line are the existing `cs/mailboxes.py`. What this brief adds is
where a credential for a profile-less mailbox comes from.

**Plain IMAP with an app password, by the operator's decision (2026-09-02).**
IMAP is a shared standard that has worked for decades and binds the kernel to
no vendor; a delegated Google credential would weld the mechanism to one
provider's service accounts, admin console and token endpoints — a moat
wearing a security badge. The kernel therefore speaks the standard protocol it
already speaks: `v0.37.0`'s `_imap(settings, credential=…)`, `sent_to_on` and
`inbound_since_on` take an explicit credential today, so this design adds no
new read path and no new dependency. When the providers agree on a shared,
standard protocol with real scoping, IMAP is abandoned with pleasure — not
before.

**The mailboxes are declared, addresses only, no secrets in any repo.** A
manifest list — `read_mailboxes` — of plain addresses, with the same guard as
`CS_ACCOUNTS`: an address outside the company's own mail domain fails loud at
config load, and a malformed entry is an error, never a silent drop. The
credential for each declared address lives in the clone's env file
(`~/.<company>-cs/.env`, outside every repo — where `EMAIL_PASSWORD` already
lives), parsed **strictly**: a malformed pair fails config load loud, and a
declared address with no credential renders as
`unreadable — no credential configured for <address>`, never as an absence.
The silent-drop parser that killed the first version of this idea is a code
defect, not a property of app passwords.

**The accepted trade-off, stated once.** An app password can send and does not
expire; read-only is a property of our calling code, not of the credential.
Accepted by the operator with that stated. The handling rules that contain it:
the credential exists only in the clone env, is redacted in every error path
(the `v0.37.0` redaction), never becomes a Settings field `cs config` could
print, and is never passed to any send path — `send_mail` logs in with the
operator mailbox's own credential and nothing else. Revocation is one action
in the provider's account settings.

**The read stays narrow.** The same two questions as today, headers only: does
Sent mail to this address exist, and has this address written since a date. It
is not a general read of somebody's mail, and describing it accurately is what
makes the owners' consent real.

**`unreadable` extends, with the fix in the message.** A declared mailbox whose
credential is missing or refused reports it by name — never an empty result —
and the scope line counts declared mailboxes in its denominator.

**The gates read everything, always.** Phase 2 — the four gating call sites
(`campaign.py:108`, `:120`, `cli.py:797`, `draft_state.py:290`) — reads the
union of profile mailboxes and declared mailboxes. No flag chooses the
evidence scope; that flag is the dedup-source knob the charter forbids. A send
gate that meets `unreadable` refuses and names the mailbox: fail-open is the
incident at machine speed.

**Charter fit.** Identity and sending are untouched: the read credential never
reaches a send path by construction. Gmail Sent remains the dedup ground
truth; it becomes the company's Sent instead of one box's. The addresses are
manifest data, the credentials are clone-env data (rule 2), and the mechanism
— read a declared mailbox over standard IMAP — is provider-neutral kernel
code, so the rule of two is met by the mechanism, not by one company's
topology or one vendor's API.

## Deliberately out of scope

Existence only. Whether a message needed an answer, was an auto-reply, or
settled a thread stays the engine's judgement, per § 0b.

How a given provider issues an IMAP credential (a Google app password, another
provider's equivalent, a plain password on self-hosted mail) is clone
operations, documented, not kernel code.

## Rejected approaches

**A Google service account with domain-wide delegation (`gmail.readonly`).**
The one shape whose credential cannot send — and it welds the kernel's
mechanism to one vendor: a GCP service account, the Workspace admin console
and Google token endpoints, for mailboxes that only need a decades-stable
standard protocol. Rejected by the operator, 2026-09-02: vendor coupling
dressed as security. Reconsidered the day a shared, standard protocol offers
the same scoping.

**An engine profile per mailbox.** Asks the most from the owners — a daemon, a
login, an identity each — to answer a read-only question. Rejected by the
operator in exactly those terms; it was this brief's first executed shape, and
covering only profile-holding mailboxes is the spec change this rewrite
reverts.

**Asking humans to always CC the operator mailbox.** A convention that must
hold on every device forever; the first reply typed from a phone silently
drops a customer out of view. Worth doing; worthless to rely on.

## Acceptance

- With `read_mailboxes` declared and the credentials placed in the `124-cs`
  env, `cs history <the prospect's address>` reports the co-founder's
  2026-07-03 reply and names the mailbox it was found in.
- A declared mailbox with a missing or refused credential renders as
  `unreadable`, named, with the fix in the message — in the printed line, the
  exit status, and JSON. A malformed credential entry fails config load loud.
- No secret for any of these mailboxes exists in any repo file; `cs config`
  prints none of them; no error path echoes one.
- The read credential is demonstrably absent from every send path.
- The phase-2 gates read profiles ∪ declared mailboxes, and the scope line's
  denominator counts both.
