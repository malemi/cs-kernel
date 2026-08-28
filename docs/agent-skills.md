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
