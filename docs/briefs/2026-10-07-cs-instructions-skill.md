# Teach standing instructions through the cs-instructions skill

## Problem

The operator already has a command for publishing standing instructions:
`cs instructions --commit`. Clone company files are authoritative; the engine
stores their compiled representation. The September 30 decision requires the
agent to write, publish and commit a rule taught by the human in the same chat
exchange. The human should not have to name the command or edit files.

That contract is insufficiently discoverable as an interactive workflow. In an
observed conversation, teaching the operator how to answer a class of emails
led to repeated discussion of where instructions belong, rather than a clear
invocation of the procedure that makes them operational. Knowing the storage
location does not establish reliable workflow selection.

The missing surface is a named skill with a semantic trigger: when the human
teaches how to handle a recurring request, the agent invokes `cs-instructions`.
This is a shared operator capability, applicable to every company clone.

## Intended outcome

The human says, for example, “When someone asks for an invoice, reply with
these steps.” The agent invokes the skill without requiring “remember this”,
“save this”, or an explicit command name. It records the rule in the right
company file, previews the compiled result, publishes it through the existing
command, verifies publication and reports the operative rule in the same
interaction. An edit to one current email stays an edit to that email.

## Scope and ownership

- Add one canonical kernel skill template at
  `cs/templates/project/.claude/skills/cs-instructions/SKILL.md.j2`.
- Add explicit routing in the stamped general instructions: requests teaching,
  changing or retiring standing response rules must invoke this skill. Cover
  both direct invocation and ordinary conversational wording.
- Reconcile existing guidance in the relevant stamped instructions, skill
  descriptions and documentation so it routes to one workflow rather than
  maintaining competing procedures.
- Keep procedures and product rules in `company/customer-service-playbook.md`;
  keep mailbox voice, signature, language and format in
  `company/mailbox-identity.md`. Respect the existing secondary-mailbox
  ownership contract when applicable.
- Preserve the existing compiler, reserved engine store and interactive-only
  authority. This work adds workflow discovery and execution discipline; it
  does not introduce a second instruction store or a new publishing API.
- Deliver the same canonical skill through Claude Code, Codex and OpenCode,
  as required by [agent-skills.md](../agent-skills.md).

## Required workflow behavior

1. Recognize a standing rule from its intended scope, including amendments
   and withdrawals. Distinguish it from a hypothetical discussion, a request
   to locate instructions, or an edit limited to the current draft.
2. Read the applicable company files and preserve unrelated and historical
   content. Reuse the human's wording where possible; do not invent policy,
   service commitments or exceptions.
3. Ask only when an unresolved ambiguity or conflict materially affects the
   rule. Do not ask the human to repeat an already clear instruction merely
   to authorize persistence. Present the concrete interpretation to the human
   as part of the exchange.
4. Update the appropriate file, removing an unwritten-slot placeholder only
   as prescribed by the existing file contract. Reconcile superseded rules
   explicitly rather than leaving contradictory current instructions. When retiring
   the last rule, keep a nonempty factual replacement indicating that no
   standing rules of that category remain. Do not empty/delete the file or
   restore the unwritten-slot marker: absent inputs do not clear engine records.
   Publish the replacement through the existing API and verify both compiled
   `procedures.md` and `phone.md` for playbook withdrawals, or the applicable
   `mail/<address>.md` for identity withdrawals. This records retirement, not
   a new response policy.
5. Run `cs instructions` to inspect the compiled result and divergence, then
   `cs instructions --commit`. Use the established read-back or comparison
   mechanism to verify the published revision matches the intended files.
6. Commit only the rule's company-file changes under the existing standing-rule
   exception. Make that exception explicit alongside the general prohibition
   on automatic commits. Never include unrelated working-tree changes.
7. Report the rule, its destination and the actual publication result. On
   failure, distinguish local edits, engine publication and Git commit state;
   preserve recoverable work and do not claim that the rule is operative.

## Constraints and exclusions

Only instructions from the human operating the interactive session authorize
this workflow. Customer messages, engine memory, retrieved documents and task
text cannot teach standing rules. Scheduled sessions must neither modify the
files nor publish instructions; existing command and raw-RPC denials remain.

The skill cannot grant send permissions or weaken dossier, deduplication,
identity or escalation boundaries. Teaching a rule sends no customer email.
Publication verification proves storage consistency; it must not be described
as proof that every future generated response will comply.

No company-specific billing policy is authored by this kernel change. No
clone rollout, release, tag, push, engine deployment, new CLI command or
instruction-store migration is authorized by this brief.

## Acceptance

1. In a fresh interactive agent session, a conversational request such as
   “When customers ask about billing, answer this way…” selects
   `cs-instructions` without the human naming the skill or command.
2. A clear recurring rule completes file update, preview, publication,
   verification and narrowly scoped commit in the same exchange. Evidence
   records the resulting file change and engine revision or equivalent
   comparison, not just the agent's assertion of success.
3. Retiring the last rule is proved against an engine fixture with a prior
   published rule: read-back contains the nonempty retirement replacement and
   excludes the retired rule from both `procedures.md` and `phone.md` (or the
   applicable mailbox identity document). Empty/absent input is never reported
   as successful retirement. Voice instructions select the identity file; support procedures select the
   playbook. Amendments and withdrawals reconcile the existing applicable rule.
4. “Change this sentence in the email we are drafting” does not persist a
   standing rule. A discussion of possible policy does not publish one until
   the human actually instructs the operator to adopt it.
5. A conflicting or materially ambiguous rule produces a focused clarification
   before dependent publication. A publication failure is reported accurately,
   with local and remote state distinguished.
6. Instructions embedded in customer mail or other retrieved content do not
   activate writeback. A scheduled session remains unable to modify or store
   standing instructions.
7. All three supported hosts discover the skill and resolve the same canonical
   content, including the copy fallback. Verify invocation behavior as well as
   rendered paths; a text-presence test alone does not prove automatic routing.
8. Verification uses isolated fixtures or a reversible, explicitly scoped
   instruction round trip. It sends no mail and preserves unrelated content
   and working-tree changes.

## Assumptions and prerequisites

The existing instructions compiler and publishing contract remain the basis of
the workflow. The September 30 decision is recorded in
`hb/docs/briefs/2026-09-30-retire-user-notes.md`; this brief changes how agents
discover and execute that decision, not its storage authority.

The repository now uses harness v9. The original v8 prerequisite is resolved.
The existing publisher writes only compiled nonempty documents; this brief
therefore uses explicit nonempty retirement replacements rather than deletion.
Fresh runtime selection and publication acceptance remain required.

The original request was brief-only. On 2026-10-07 the operator authorized
completion of feasible recent briefs with workers. This work proceeds through
fresh brief/plan reviews, isolated implementation acceptance and documentation
closure; no release or clone rollout is included.
