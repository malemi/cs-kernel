# Agent skills only — brief

## Problem

The kernel currently publishes the same operator product through two different
abstractions:

- five `.claude/commands/*.md` workflows (`cs-account`, `cs-campaign`,
  `cs-cron`, `cs-help`, and `cs-review`);
- five `.claude/skills/*/SKILL.md` workflows used by the unattended operator
  and customer work.

`install_agent_surfaces()` then copies the distinction outward. OpenCode gets
both a command mirror and a skill link; Codex gets home-global deprecated
custom prompts under `~/.codex/prompts`. The Codex prompt namespace can point
at only one clone at a time, so installing a second clone creates an ownership
prompt and one clone necessarily loses its operator workflows.

This split no longer reflects the products. Claude Code and Codex both support
project-scoped Agent Skills. A workflow that has a name, activation description,
instructions, and a safety boundary is a skill; keeping a second command form
adds lifecycle and discovery behavior without adding a capability.

The operator is the only user and explicitly does not want compatibility files
retained. A migration that merely stops generating commands is insufficient:
old stamped commands, OpenCode mirrors, and Codex prompt links would survive in
existing clones and continue to appear as live product surface.

## Decision

Make `.claude/skills/` the only rendered workflow surface.

The five former commands become:

```text
.claude/skills/cs-account/SKILL.md
.claude/skills/cs-campaign/SKILL.md
.claude/skills/cs-cron/SKILL.md
.claude/skills/cs-help/SKILL.md
.claude/skills/cs-review/SKILL.md
```

Each carries standards-compatible `name` and `description` frontmatter. Their
workflow bodies and current authorization boundaries remain intact except for
agent-neutral wording and invocation examples.

On filesystems with symlink support, other agents receive links to the same
directory rather than a second rendered source:

```text
.agents/skills   -> ../.claude/skills
.opencode/skills -> ../.claude/skills
AGENTS.md        -> CLAUDE.md
```

On Windows filesystems that refuse symlinks, the existing disclosed fallback
creates byte-identical repository copies so stamping remains usable.

Codex therefore discovers the clone-local skills as `$cs-review`, `$cs-cron`,
and so on. Claude Code discovers the same source as `/cs-review`, `/cs-cron`,
and so on. Two clones can coexist because discovery starts from each repository
rather than a shared home prompt directory.

## Deletion and migration contract

Fresh clones contain no `.claude/commands`, `.opencode/commands`, or
kernel-created `~/.codex/prompts/cs-*.md` entries.

On an existing clone, `cs update` removes exactly the five retired generated
command paths and removes them from `template-manifest.json`. It also removes
the five matching entries from the obsolete `.opencode/commands` mirror (and
the directory only when empty) plus the five legacy Codex prompt paths. This is
an intentional destructive migration requested by the sole operator; no
`.local-bak` command compatibility copy is retained.

The deletion scope is closed and enumerated. It does not remove arbitrary
files from `.claude/commands`, arbitrary prompts from `~/.codex/prompts`, or
clone-authored company files. It does not alter `.claude/settings.json`, the
cron wrapper, engine state, mail, drafts, tasks, or campaign data.

## Canonical ownership

- Jinja templates under `.claude/skills/*/SKILL.md.j2` own workflow content.
- `install_agent_surfaces()` owns only repository links and legacy cleanup.
- `project_update` owns retirement of paths previously recorded in the template
  manifest.
- No prompt or command file is a second source of workflow instructions.

`install_agent_surfaces()` must be skill-led: its current early return when no
`.claude/commands` directory exists is itself retired. A fresh skills-only clone
must still wire `.agents/skills`, `.opencode/skills`, and `AGENTS.md`.

The existing shared partials remain shared. In particular, the attention
decision contract continues to be included exactly once by the `cs-review`
skill and by the independent semantic replay.

## Invocation and automation

Interactive invocation becomes native to each host:

- Claude Code: `/cs-review`;
- Codex: `$cs-review`;
- OpenCode: its skill invocation surface.

The existing Claude headless cron continues to invoke `/cs-operator`, which is
already a skill. Replacing the scheduled runtime with `codex exec` is a separate
workstream: it requires an explicit network/sandbox profile and live operational
verification, not merely a file-layout migration.

## Out of scope

- changing the headless runtime from Claude to Codex;
- changing any workflow's business behavior;
- changing send permissions, cron permissions, or the kill-switch;
- adding a plugin or MCP server;
- releasing a tag or upgrading a real clone.

## Acceptance

1. A fresh render has ten `cs-*` skill directories and no command directory.
2. Every rendered skill validates as an Agent Skill and has a unique name.
3. Claude, Codex, and OpenCode resolve the same `SKILL.md` bytes from the
   repository; no home-global Codex prompt is created.
4. Updating a stamped legacy fixture deletes the five retired command files,
   its OpenCode command mirror, and the five legacy Codex prompt entries while
   leaving unrelated files untouched.
5. `/cs-review`'s attention contract and all other workflow-specific safety
   boundaries remain present after conversion.
6. The complete kernel suite stays green, including fresh-init and update
   paths on a filesystem that refuses symlinks.
