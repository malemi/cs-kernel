# Memory-first for outbound facts — brief

## Problem

The template `CLAUDE.md.j2` § 9 is titled "Customer knowledge" and states that a
question about a customer, prospect or integration needs both layers, engine
memory first and the `docs/projects/` dossier second. The rule routes questions
*about an entity* to memory and says nothing about anything else.

A customer-facing message is mostly not made of entity facts. It carries dial
codes, phone-number formats, prices, plan limits, procedures, and statements
about what the product can and cannot do. For those the operator has no declared
source of truth, so it reaches for whichever artifact is nearest.

Incident, 2026-09-01, `mrcall-cs`. Composing a reply about landline call
forwarding, the session searched Sent mail for precedent, found none, and then
derived the codes from `mrcall-dashboard/src/utils/PhoneOperators.js`. That file
holds a `proceduresFixedLine` map covering two Italian carriers and strips the
`+39` prefix before building the dial string, so the draft told the customer
`*22*0286882559#`.

Engine memory holds the answer, recorded dozens of times: the universal code is
`*004*[number]#` from a landline and `**004*[number]#` from a mobile, removal is
`#004#`; `*22*` / `*23*` / `*24*` are classified there as *fallback* codes, not
the primary instruction; every worked example from a real migration carries the
`+39` (`*004*+390286882245#`); and eight style patterns record how these mails
are written. Memory was never queried. The draft was caught before sending.

Two separate defects produced it:

- **Category error.** Memory is understood as a per-entity store, so a question
  about a procedure never routes to it. "What do we know about this customer"
  and "what is the forwarding code" were treated as different kinds of question,
  and only the first one reached memory.
- **Fallback on empty.** A search that returned nothing triggered a *substitute
  source* rather than a second search. Source code is not a weaker version of
  memory; it describes one implementation of one surface, while memory records
  what has been learned from sending these messages for two years.

The second defect is the more dangerous of the two, because it converts every
gap in one source into an invented fact rather than an unanswered question.

## Decision

Two rules, both stated in the template `CLAUDE.md`, both worded so that neither
is scoped to customers.

**1. Memory is the first source for any fact that will appear in an outbound
message.** Not only entity facts: codes, numbers, formats, prices, limits,
procedures, capabilities. The order is engine memory, then Sent-mail precedent,
then the `docs/projects/` dossier. Repository source code is not a source for a
customer-facing fact. It is the shape of one surface, not a record of what we
know, and it is frequently narrower than memory — as it was here, two carriers
against a universal code.

**2. An empty search obliges a second source, never a derivation.** When a
source returns nothing, the next step is another source. When every source
returns nothing, the message says we do not have that answer, or the question
goes to the operator. Reconstructing the fact from an adjacent artifact is the
failure this rule exists to stop.

## One text, three surfaces — the partial

Both rules are the same prose everywhere they bind. Pasting them into three
files would ship the kernel's own duplication failure, so they live in one new
partial, `cs/templates/partials/outbound-fact-sourcing.md.j2`, `{% include %}`d
by each surface that needs them. The render environment already carries the
partials root on its search path for the whole project template
(`cs/project_init.py:933`), so `CLAUDE.md.j2` can include it exactly as the
skills include `desk-preamble.md.j2`.

The rules ship **abstract**. The kernel states the *class* of fact that must
come from memory — codes, number formats, prices, plan limits, procedures,
capability claims — and never a concrete instance of one. The dial codes of the
incident are an Italian carrier fact that every non-Italian clone would inherit
as false; concrete values stay in engine memory and in the clone's own
`company/*.md`. This is charter rule 1, and it is why the fix cannot be "write
the right codes down somewhere in `cs/`".

## Where the rules are rendered

- `cs/templates/project/CLAUDE.md.j2` § 9 — heading retitled so it no longer
  reads as customer-only, including the partial. The section **keeps the
  number 9**: `cs-customer/SKILL.md.j2:35` cross-references it by number.
- `cs-triage-mail` § 2b — already states memory-first and "never invent
  mechanics, prices, steps". It is **amended**, not replaced: the section
  delegates to the partial and keeps only what is specific to triage.
- `cs-campaign-tick` — its hard rule "NEVER invent facts" (`:42-43`) gains the
  partial, which is the missing half: it names no memory-read verb today.
- `docs/projects/README.md.j2` reads at first glance like the opposite order —
  dossier first, then engine memory — but it is not a competing rule. It answers
  a question *about a project*, demands both layers, and splits authority by
  question type: the files win on history and judgement, the engine wins on
  mail. Its file-first step is orientation that supplies the names the later
  `ask` is tuned with, and `cs-customer` calls that order "the map". It gains
  one scoping clause — a fact destined for an outbound message follows § 9 —
  and its numbered order is left intact.

`cs-review` gets no edit. It is read-only by declaration
(`cs-review/SKILL.md.j2:13-16`), "prepare a reply" appears in it only as a
prohibition (`:188`), and it has no Posture section. It reaches the rules the
way it reaches every other invariant — step 1, "Read `CLAUDE.md` in full".

## Scope

No change to `cs` code and no new verb. The read-only path already exists —
**`cs ask`**, which passes an empty tool set (`cs/cli.py:973`) and is in the
clone allow list. It is not `cs chat`: that is the drafting surface, and the
cron wrapper denies it in all six spellings, so a headless skill instructed to
use it would state a rule the cron cannot execute. What is missing is the
instruction to take the path, not the path.

This strengthens the existing "the engine is authoritative for what it owns"
rule rather than competing with it: entity memory is the engine's, and these
rules say to ask it more often, not less. It also stays on the *content* side
of an existing boundary — `cs-triage-mail:64-67` forbids `cs ask` for the
answered/not-answered binary, which the engine owns. Memory supplies what a
message says, never whether a message exists.

Dedup ground truth is untouched. Gmail's Sent folder remains the answer to
*does this message exist*.

## Rejected approaches

**Copy the forwarding codes into the clone** (`company/claude-extra.md`, or a
campaign pack). Rejected: memory already holds them, in a richer and
better-maintained form. A second copy is the anti-fork failure wearing different
clothes, and it would drift the moment a carrier changed.

**Widen `PhoneOperators.js` to cover more carriers.** Rejected: it belongs to
`mrcall-dashboard`, and fixing it would not have prevented this. The error was
consulting a source-code file for a customer-facing fact at all.

**A pre-send lint that greps drafts for dial-code patterns.** Rejected: it
catches one shape of fact out of many, and to know a code is wrong it would have
to encode the knowledge memory already holds.

**Pasting the rules into each surface instead of a partial.** Rejected: three
copies of one rule drift, and the kernel exists to stop exactly that. No gate
would have caught it either — gate 42's single-source check is hard-coded to
the preamble text.

## Acceptance

- The partial `cs/templates/partials/outbound-fact-sourcing.md.j2` exists,
  states both rules abstractly, names `cs ask`, and carries no concrete code,
  price, number or carrier.
- Template `CLAUDE.md.j2` § 9 includes it, is still numbered 9, and its heading
  is not scoped to customers.
- `cs-triage-mail` and `cs-campaign-tick` include it, and `cs-triage-mail` § 2b
  no longer restates what the partial says.
- `docs/projects/README.md.j2` scopes outbound facts to § 9 without changing its
  own order.
- A gate holds the single-source property, on two independent marks: the HTML
  comment `<!-- outbound-fact-sourcing -->` and the prose sentence "Repository
  source code is never a source for a customer-facing fact." each exist exactly
  once in `cs/`, in the partial, and each surface that must carry the rule
  includes the partial by name and shows both marks once, in the rendered
  clone. Two marks rather than one because the comment alone only catches a
  surface that includes the partial; a fourth surface that pastes the rule's
  TEXT in by hand, without the comment, would otherwise pass. No existing gate
  did this before.
- `bash tests/run.sh` is green — in particular gates 1, 1b, 12, 36, 42, 43.
- A clone stamped from the template shows the new wording, once per surface, and
  a real `cs update` on an existing clone renders the new include host cleanly.
- The 2026-09-01 case re-run: a session asked for landline forwarding
  instructions reaches the code from memory rather than from source code, and a
  session whose first search comes back empty opens a second source instead of
  deriving.
