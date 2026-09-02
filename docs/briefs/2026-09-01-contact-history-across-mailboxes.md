# Contact history across mailboxes — brief

Rewritten 2026-09-02. The first version of this brief was executed only for
mailboxes that hold an engine profile, which covers neither of the two
mailboxes that caused the incident. That was a spec change dressed as a
delivery, and this rewrite reverts it: the constraint below is the spec.

## The binding constraint — mailbox owners contribute nothing

The people whose mailboxes must be read answer customers from their own
accounts and will not stand up an engine profile, run a daemon, generate an app
password, or hand over anything, ever. A design is admissible only if the sum
of what it asks from them is zero. One admin action by the domain
administrator is acceptable; one action per mailbox owner is not.

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

**A service account with domain-wide delegation, scope `gmail.readonly`.** The
domain admin authorises the service account's client ID for exactly that scope
in the Workspace admin console — once, for the whole domain. The mailbox
owners do nothing, install nothing, hand over nothing. The credential
**cannot send**: the scope is enforced by Google at token issue, not by a
convention in our calling code, which is the property no app password can
have. `cs/drive.py` already loads this kind of credential (`firebase_sa_path`,
read-only Drive scope); the manifest names the key file for mail, defaulting
to the same one.

**The mailboxes are declared, addresses only, no secrets.** A manifest list —
`read_mailboxes` — of plain addresses. It carries the same guard as
`CS_ACCOUNTS`: an address outside the company's own mail domain fails loud at
config load, and a malformed entry is an error, never a silent drop. There is
no password to parse because there is no password: the token is minted per
mailbox from the service account with `with_subject(address)`.

**The read path.** A delegated token for the target mailbox, then the same
narrow question as today: does Sent mail to this address exist, headers only —
via the Gmail API (`messages.list`, `q="in:sent to:<address>"`) or IMAP
XOAUTH2 with the same token; whichever is built, the credential story is
identical. Worth recording for whoever discusses this with the mailbox owners:
it is not a general read of somebody's mail, and describing it accurately is
what makes the authorisation real.

**`unreadable` extends, with the fix in the message.** A declared mailbox whose
delegation is not authorised reports `unreadable — delegation not authorised
for <address>; authorise client ID <id> for scope gmail.readonly`, never an
empty result. The scope line counts declared mailboxes in its denominator.

**The gates read everything, always.** Phase 2 — the four gating call sites
(`campaign.py:108`, `:120`, `cli.py:797`, `draft_state.py:290`) — reads the
union of profile mailboxes and declared mailboxes. No flag chooses the
evidence scope; that flag is the dedup-source knob the charter forbids. A send
gate that meets `unreadable` refuses and names the mailbox: fail-open is the
incident at machine speed.

**Charter fit.** Identity and sending are untouched — this credential cannot
reach them. Gmail Sent remains the dedup ground truth; it becomes the
company's Sent instead of one box's. The addresses are manifest data (rule 2),
the mechanism is kernel code, and both clones are Google Workspace with
founders who answer from their own boxes, so the rule of two is met by the
mechanism, not by one company's topology.

## Deliberately out of scope

Existence only. Whether a message needed an answer, was an auto-reply, or
settled a thread stays the engine's judgement, per § 0b.

The mechanism is Google-specific. A clone on another mail provider declares no
read mailboxes and keeps today's behaviour; if that clone ever exists, the
provider seam follows the CRM/producer registry pattern, not a knob.

## Rejected approaches

**`address:app-password` pairs in an env key.** Requires each mailbox owner to
generate and hand over a secret — the exact cooperation the constraint rules
out — and an app password has no scope, does not expire, and can send; nothing
in the kernel could take that back. Its natural parser also drops a malformed
pair silently, turning a typo into an absence.

**An engine profile per mailbox.** Asks the most from the owners — a daemon, a
login, an identity each — to answer a read-only question. Rejected by the
operator in exactly those terms; it was this brief's first executed shape, and
covering only profile-holding mailboxes is the spec change this rewrite
reverts.

**Asking humans to always CC the operator mailbox.** A convention that must
hold on every device forever; the first reply typed from a phone silently
drops a customer out of view. Worth doing; worthless to rely on.

## Acceptance

- With delegation authorised and `read_mailboxes` declared on `124-cs`,
  `cs history <the prospect's address>` reports the co-founder's 2026-07-03
  reply and names the mailbox it was found in.
- A declared mailbox with delegation missing renders as `unreadable` with the
  admin action in the message — in the printed line, the exit status, and JSON.
- No secret for any of these mailboxes exists in any env file or repo.
- The token is asserted to carry exactly `gmail.readonly` at acquisition;
  broader fails loud.
- The phase-2 gates read profiles ∪ declared mailboxes, and the scope line's
  denominator counts both.
