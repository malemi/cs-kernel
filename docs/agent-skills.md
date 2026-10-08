# Agent Skill Surfaces

<!-- doc-scope:start -->
Scope: the cross-host ownership and verification contract for every Agent Skill
shipped by this kernel. Workflow behavior remains owned by each canonical
`SKILL.md.j2`; this document owns how a skill reaches supported agents.
<!-- doc-scope:end -->

## Three-host invariant

Every skill must always be updated for all three supported systems in the same
change: Claude Code, Codex, and OpenCode. A skill change is incomplete until all
three systems discover and execute the updated canonical instructions.

This does not mean maintaining three implementations. The only authoring source
is `cs/templates/project/.claude/skills/<name>/SKILL.md.j2`; it renders to
`.claude/skills/<name>/SKILL.md`. `.agents/skills` and `.opencode/skills` resolve
that rendered tree through repository links, with byte-identical copies only on
filesystems that refuse symlinks.

Every skill change must therefore verify all of the following before completion:

1. Claude Code reads the updated `.claude/skills/<name>/SKILL.md`.
2. Codex resolves the same bytes through `.agents/skills/<name>/SKILL.md`.
3. OpenCode resolves the same bytes through `.opencode/skills/<name>/SKILL.md`.
4. Host-facing invocation text remains correct for all three systems.
5. Symlink and copy-fallback tests remain green; no command or global-prompt
   compatibility surface is reintroduced.

Host-specific launchers may remain host-specific only when their runtime is
explicitly scoped that way, as with the existing Claude-owned cron wrapper.
They do not create a second copy of the skill instructions and do not relax the
three-host invariant for the skill itself.

## Company customer-service playbooks

`cs-triage-mail` reads `company/customer-service-playbook.md` when a clone has
authored that file. The kernel skill owns the common triage sequence and safety
boundaries; the clone-owned playbook supplies company-specific decision trees,
evidence requirements and authorised non-mail actions. `cs update` refreshes
the shared skill and never overwrites the playbook.

The playbook cannot grant a send capability or bypass a tool approval. A
headless runtime that denies an action leaves the task open and reports the
specific operator action; an interactive runtime may approve only the named
non-mail tool required by the matching workflow.

## Conversational standing instructions

`cs-instructions` selects an interactive human's teaching, amendment or retirement
of recurring response rules, mailbox voice and signature. Stamped AGENTS and
triage guidance route to that one canonical workflow. It reads the authoritative
company files, previews all compiled changes, publishes through the existing
`cs instructions --commit` API, verifies revision read-back and commits only the
named company-rule files. Unrelated staged/unstaged edits remain untouched.

Current-draft edits, hypothetical discussion and untrusted retrieved instructions
do not authorize persistence. Material conflicts require clarification. Scheduled
sessions cannot teach rules. Last-rule retirement uses a nonempty factual
replacement because absent compiler inputs do not clear stored documents.

Native fixture acceptance passes eleven cases on each supported host, including
actual discovery, real WebSocket/SQLite publication and narrow Git commits.
Independent state checks cover all 33 cases. Acceptance establishes only the
observed cases, not universal future selection,
reply compliance, production Firebase verification or live clone adoption. The
[execution record](execution-plans/2026-10-07-cs-instructions-skill.md) owns exact
results and review status.

## Supporting files

A skill may carry files beside `SKILL.md`: reference documents, a helper
script, a provenance record. Each one is a `.j2` template in the skill's
directory whose whole body is a single raw block:

    {% raw -%}
    <the file, verbatim>
    {% endraw %}

It is stamped byte for byte to the same path without the suffix, through the
same render, checksum ledger and host links as `SKILL.md`. The form is exact
when the body starts with a non-whitespace character and contains no `endraw`
tag; the contract gate compares the stamped bytes with the body. A supporting
file is UTF-8 text with LF line endings.

A plain `.py` never ships in the template tree. `pip install` byte-compiles
it, and both stamping walks take every file they meet: `cs init` stamps the
`.pyc` into the clone and `cs update` exits with `UnicodeDecodeError`. The
installed-template inventory gate compares `*.j2` only, so a plain supporting
file is also outside the packaging gate.

A stamped helper is not executable. It is run with an interpreter by its
canonical path under `.claude/skills/`, which is the same file on every host.
`cs update` does not remove a file a later kernel stops shipping.

`tests/test_legal_research_skill.py` gates this contract.

## Legal research

`cs-legal-research` gives the interactive human research on Italian and EU law
for the company's own questions: source and citation checks, administrative
remedies, deadlines and documentary evidence, plus a date-arithmetic helper
whose output is labelled as arithmetic and not a legal deadline. The stamped
`PROVENANCE.md` states its origin.

Its interactive-only boundary is instruction-level. The skill's description
and body exclude scheduled runs and customer mail, and `cs-triage-mail`
escalates a legal-sensitive customer message. No permission rule enforces the
boundary: the stamped settings allow the `Skill` tool and the cron wrapper
denies no skill by name. The wrapper's send and draft boundaries do not depend
on which skill a run loads, and the helper is on no allow list.
