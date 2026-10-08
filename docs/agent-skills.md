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
