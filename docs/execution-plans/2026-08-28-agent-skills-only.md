---
status: completed
---

# Agent skills only — execution plan

Brief: [`../briefs/2026-08-28-agent-skills-only.md`](../briefs/2026-08-28-agent-skills-only.md)

## Outcome

Every operator workflow is a project-scoped Agent Skill. Claude reads the
canonical `.claude/skills` tree; Codex and OpenCode resolve it from repository
links, with byte-identical copies only on filesystems that refuse symlinks.
Commands and home-global Codex prompts are removed from new and upgraded clones.

## Phase 1 — Convert the five workflows

- [x] Move `cs-account`, `cs-campaign`, `cs-cron`, `cs-help`, and `cs-review`
  from `.claude/commands/<name>.md.j2` to
  `.claude/skills/<name>/SKILL.md.j2`.
- [x] Add `name: <name>` to each frontmatter and keep descriptions focused on
  activation, behavior, and authorization boundaries.
- [x] Make host-facing wording agent-neutral while preserving Claude's native
  `/cs-*` invocation and Codex's `$cs-*` invocation in orientation text.
- [x] Rewrite skill-to-skill composition as agent-neutral skill invocation in
  the existing `cs-operator`, `cs-triage-mail`, and `cs-customer` instructions;
  leave the explicitly Claude-owned headless wrapper unchanged.
- [x] Preserve every workflow-specific safety rule, the shared desk preamble,
  and the one-copy review attention contract.
- [x] Delete all five command templates; do not add compatibility shims.

Verification:

```bash
python3 tests/test_template_render.py
python3 tests/test_review_bootstrap.py
python3 tests/test_review_attention.py
```

## Phase 2 — Replace global prompt wiring with repository skills

- [x] Rewrite `install_agent_surfaces()` so `.claude/skills` is the required
  source and absence of `.claude/commands` is normal.
- [x] Link `.agents/skills` and `.opencode/skills` to `.claude/skills`; retain
  `AGENTS.md -> CLAUDE.md`.
- [x] Remove the `.opencode/commands` creation path and the home-global Codex
  prompt ownership question.
- [x] Enumerate the five legacy names once and delete only those entries from
  `.opencode/commands` and `~/.codex/prompts`, removing an empty legacy
  directory but preserving unrelated entries.
- [x] Handle missing files and broken legacy symlinks idempotently; if an exact
  retired name has unexpectedly become a directory, preserve it rather than
  broadening deletion semantics.
- [x] Preserve `_link_or_copy`'s Windows fallback and prove both agent skill
  trees receive byte-identical copies when symlinks are unavailable.

Verification:

```bash
python3 tests/test_agent_surfaces.py
```

## Phase 3 — Retire generated command files during update

- [x] Teach `cs update` to delete the five retired `.claude/commands` paths
  before rewriting the manifest, without a prompt or backup, using the same
  closed name set as surface cleanup.
- [x] Remove empty `.claude/commands` after the exact paths are retired, but
  retain unrelated command files and a non-empty directory.
- [x] Let the normal new manifest omit retired checksums; assert that no stale
  checksum survives.
- [x] Exercise a stamped legacy fixture whose commands include an edited file:
  all five are removed as explicitly requested, while manifest, company files,
  unrelated commands, unrelated OpenCode entries, and unrelated Codex prompts
  remain untouched.
- [x] Confirm a second update is idempotent and reports no retired paths again.

Verification:

```bash
python3 tests/test_project_update.py
python3 tests/test_stamped_surfaces.py
```

## Phase 4 — Reconcile every documented and tested surface

- [x] Update the kernel charter and stamped `CLAUDE.md` / architecture docs so
  skills, not commands, own workflows.
- [x] Confirm `.claude/settings.json` already authorizes the native `Skill`
  tool and avoid changing permissions that do not need migration.
- [x] Update help/orientation content to show Claude `/cs-*` and Codex `$cs-*`
  without presenting two implementations.
- [x] Rewrite gates that currently assert command names, command paths, or
  `~/.codex/prompts` ownership.
- [x] Add one gate that renders a fresh clone, proves exactly ten unique
  `cs-*` skills and zero command directories, and validates every rendered
  `SKILL.md` frontmatter.
- [x] Run `skill-creator`'s `quick_validate.py` against all ten rendered skills
  as an independent format check.
- [x] Sweep current code/templates/docs for live references to the retired
  surfaces; historical CHANGELOG and incident narratives remain historical.

Verification:

```bash
git diff --check
bash tests/run.sh
python3 /home/mal/.config/mrcall-ai-kit/doc-check.py --repo .
```

## Phase 5 — Disposable real-clone migration proof

- [x] Copy `mario124-cs` to a disposable directory without its venv or git
  metadata.
- [x] Run the source candidate's `cs update` using the real clone's interpreter
  only as a dependency environment; do not install or modify the real clone.
- [x] Verify the five skills land, both repository skill links resolve to the
  canonical bytes, all retired command/prompt entries disappear, and
  clone-authored company/configuration files remain byte-identical.
- [x] Do not run a mailbox workflow: this change is discovery/layout only, and
  the previous release already owns review semantics.

## Release boundary

This changes the visible agent invocation surface and update deletion behavior,
so a future release is MINOR. It does not touch the mandatory FULL paths: no
send, campaign, Gmail dedup, authentication, permission file, or cron-wrapper
content changes. Static re-test on both rendered clone shapes is appropriate.
This execution does not tag, push, install, or upgrade a real clone.
