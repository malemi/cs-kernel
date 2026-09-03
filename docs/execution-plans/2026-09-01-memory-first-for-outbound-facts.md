---
status: completed
started: 2026-09-01
brief: ../briefs/2026-09-01-memory-first-for-outbound-facts.md
---

# Memory-first for outbound facts — execution plan

<!-- doc-scope:start -->
Scope: the ordered steps that render the two outbound-fact rules onto the clone
template surfaces, and how each step is verified. The what and why are in the
[brief](../briefs/2026-09-01-memory-first-for-outbound-facts.md); the charter
they must obey is [`AGENTS.md`](../../AGENTS.md).
<!-- doc-scope:end -->

## Shape

Documentation-surface change plus one new gate. No `cs/` Python module is
edited, no CLI verb is added or altered, no manifest field appears. The rules
live once, in a new partial, and every surface includes it — and a test holds
that property, because no existing gate does.

The include host works: rendering a probe partial through
`cs.project_init.render_templates` put its text into the rendered `CLAUDE.md`
with no unrendered Jinja, and `cs update` shares that loader
(`project_update.py:553` → `project_init.py:933`). One boundary: the
`project_memory` render (`project_memory.py:71`) builds a single-root
environment that would **not** resolve a partial. Nothing in this plan renders
through it.

## Steps

### 1. Write the partial

New file `cs/templates/partials/outbound-fact-sourcing.md.j2`. It states, in
operator language and abstractly:

- Memory is the first source for **any** fact that will appear in an outbound
  message — not only facts about an entity. Codes, number formats, prices, plan
  limits, procedures, capability claims. The read path is `cs ask`.
- The order is engine memory, then Sent-mail precedent, then `docs/projects/`,
  with the two `emails.search folder:sent` / `list_by_thread` RPC calls that
  make step two takeable. They live here rather than in one skill: a surface
  that names a source without a way to reach it states a step nobody can take.
- Repository source code is never a source for a customer-facing fact. It is
  the shape of one surface, routinely narrower than what memory holds.
- An empty search obliges a **second source**, never a derivation. When every
  source is empty, the message says we do not have the answer, or the question
  goes to the operator.

Constraints on the text. It carries **no heading** — it is included inside § 9
and inside skill sections, so a `##` would open a sibling section and break the
host's structure. It names no concrete code, price, number, carrier, domain or
absolute path (naming the `docs/projects/` directory as a source is fine; it is
a kernel-owned location, not a company literal). No company literal of any
kind. No internal vocabulary — *collaudo*, *charter*, *re-collaudo* are ours,
not the operator's. It uses no Jinja variable, so it renders byte-identical for
every clone. It opens with an HTML comment marker
`<!-- outbound-fact-sourcing -->`, and step 6's gate holds **both** that marker
and a prose sentence from the body — a marker alone is defeated by pasting the
text without the comment, which was demonstrated rather than assumed.

*Verify*: gates 1 and 1b by inspection of the written text, then by the suite in
step 7.

### 2. `CLAUDE.md.j2` § 9

Retitle so it is not scoped to customers, keep the number **9**
(`cs-customer/SKILL.md.j2:35` cites it by number), keep the existing
customer/dossier paragraph, and `{% include "outbound-fact-sourcing.md.j2" %}`
the new rules into it.

*Verify*: the rendered `CLAUDE.md` carries the marker exactly once and the
section is still `## 9.`. Gate 38 proves nothing here — it matches its terms
file-wide against § 0b, which this step does not touch.

### 3. `cs-triage-mail` — amend § 2b, do not duplicate

§ 2b already states half of this, so it delegates rather than repeats. The
include replaces the source-ordering lines, the "NEVER invent mechanics, prices,
steps" prohibition, and the Sent-search RPC block that now lives in the partial.
Two things survive, because the abstract partial cannot carry them: the pointer
to the clone's own `company/triage-domain-examples.md` slot, and the
"after you draft, update memory" write-back with the incident behind it. The
heading becomes "source it, don't guess" — "search past mail" under-describes a
section that now opens with the general rule.

Leave `:64-67` untouched: it forbids `cs ask` for the answered / not-answered
binary, which the engine owns. Memory supplies what a message says, never
whether a message exists.

*Verify*: no gate asserts § 2b's text and nothing cross-references "2b", so the
check is step 6's gate plus reading the section rendered — specifically that the
surviving paragraph still attaches to the partial's last one, which the
paragraph-merge defect below broke on the first attempt.

### 4. `cs-campaign-tick` — include at the hard rule

Its `NEVER invent facts` rule (`:42-43`) names no memory-read verb. Add the
include there, next to the existing prohibition.

*Verify*: rendered skill names `cs ask` and carries the marker once.

### 5. `docs/projects/README.md.j2` — scope it, do not reverse it

The first read of this passage was wrong and the step it produced is dropped.
`:112-137` is not a competing rule about outbound facts: it answers a question
*about a project or customer*, it demands both layers, and it splits authority
by question type — the files win on history and judgement, the engine wins on
mail. Its file-first order is deliberate orientation, because the dossier
supplies the names that make the subsequent `ask` worth asking, and
`cs-customer:61,73` calls that order "the map for step 2-3". Reversing it would
destroy a real division of labour and put § 9 in conflict with `cs-customer`.

The correct edit is one scoping clause near `:119`: a fact destined for an
outbound message follows § 9. The numbered order stays exactly as it is.

*Verify*: `cs-customer`'s "map for step 2-3" wording still describes what the
README says.

### 6. A gate that holds single-source

Nothing today would catch a fourth surface pasting the rule in by hand:
`test_stamped_surfaces.py:67,132-138` hard-codes its single-source check to the
preamble's marker. Extend that test the same way, for the new marker:

- the marker **and a prose sentence from the body** each exist exactly once in
  `cs/` — the marker alone is not enough, because pasting the rule's text
  without the HTML comment defeats it, which was demonstrated;
- every surface that must carry the rule includes the partial by name;
- the rendered clone shows both marks once per including surface and nowhere
  else — on the `cs init` render **and** on the real `cs update` render, whose
  existing leg checked only the preamble and so did not cover the new hosts.

Without this the plan's central property is an intention, not an invariant.

### 7. Run the suite

`bash tests/run.sh`. Gates with a stake here: 1 and 1b (literals, slot shape),
**12** (`test_template_render.py` — the one that catches a StrictUndefined slip
in a new partial), 36 and 43 (`cs-review`; untouched by this plan, so a failure
means a surface was edited that should not have been), 42 (stamped surfaces),
and the new gate from step 6.

### 8. Render a throwaway clone, and upgrade one

Stamp a disposable clone into the scratchpad and read the rendered surfaces as
an operator would: rules present once each, no Jinja artifact, no dangling
include, no internal vocabulary.

Then run a real `cs update` against a disposable existing clone. `CLAUDE.md.j2`
is newly an include host, and the update path is the one that historically
breaks — the init render passing is not evidence that the upgrade render does.

*Verify*: this is the acceptance criterion no gate can express.

## Out of scope

- No release tag. This is a MINOR when published (stamped operator-facing
  wording changes), and publishing is a separate explicit operator action.
- No clone upgrade. `mrcall-cs` and `mario124-cs` pick the wording up on their
  next `cs update`, when their operator chooses.
- No change to dedup ground truth, to `cs` code, or to `PhoneOperators.js` in
  `mrcall-dashboard`.

## Risks

- **An `{% include %}` swallows the blank line after it.** `trim_blocks` eats it,
  so the partial's last paragraph and whatever follows render as one paragraph.
  Every include of this partial therefore carries **two** blank lines after the
  tag. The same quirk exists on the older `desk-preamble` includes and is not
  addressed here.
- **Renumbering § 9 breaks a cross-reference.** Mitigated by keeping the number
  and changing only the title.
- **The include lands in a skill that must stay read-only.** `cs-review` is
  deliberately excluded; if a diff touches it, the step was done wrong.
- **Abstract prose is unusable.** If the rule cannot be followed without an
  example, the example belongs in the clone's `company/*.md`, never here. Step 8
  is where that shows up.
