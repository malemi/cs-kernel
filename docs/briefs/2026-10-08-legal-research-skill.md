# Ship legal research as a kernel skill

## Problem

Company operator workspaces have no legal-research workflow. One exists as a
user-level Codex skill, `ricerca-giuridica-it`, under `~/.codex/skills/` on one
machine. Claude Code and OpenCode sessions do not load that folder, no clone
carries the skill, and no repository versions it.

`cs-kernel` is the one source every clone is stamped from, and its skills
already reach Claude Code, Codex and OpenCode from a single canonical tree
([agent-skills.md](../agent-skills.md)). On 2026-10-08 the operator decided
that shared skills live here. That decision is the charter's rule-of-two
judgement for this capability; this brief records it and does not re-examine it.

## Intended outcome

After `cs init` or `cs update` on a kernel carrying this change, every clone
has `cs-legal-research`. The human in an interactive session asks a legal
question — a dispute with a public administration, a grant exclusion, access to
records, which remedy is available and by when — and the agent on any of the
three hosts loads the same instructions, the same four reference documents and
the same date-arithmetic helper.

## Scope and ownership

- Add `cs/templates/project/.claude/skills/cs-legal-research/` with
  `SKILL.md.j2`, `references/sources.md`,
  `references/administrative-remedies.md`, `references/deadlines.md`,
  `references/evidence.md`, `scripts/count_days.py` and `PROVENANCE.md`.
- The content is the existing skill's, moved without re-authoring its method.
  Edits are limited to what the move requires: the `cs-` name, the interactive
  boundary below, the helper's invocation path inside a clone, and the
  provenance file's description of this copy.
- This is the first kernel skill that carries supporting files. Both stamping
  paths already copy non-template files and the host links already expose the
  whole canonical tree. Record that contract in `docs/agent-skills.md` and gate
  it; do not add a second delivery mechanism.
- Route to the skill from the stamped `AGENTS.md` skill list and from
  `cs-help`.
- Add focused tests, wire them into `tests/run.sh`, and reconcile the affected
  documentation.

All changes belong to `cs-kernel`. No clone, engine or kit change is part of
this work.

## Required behavior

1. **Interactive only.** The skill is selected when the human operating an
   interactive session asks a legal question. The scheduled operator never
   invokes it, and it is never used to compose a reply to a customer. A
   customer message that raises a legal matter keeps following the existing
   triage rule, which escalates it.
2. **One canonical copy on three hosts.** `.agents/skills` and
   `.opencode/skills` resolve byte-identical `SKILL.md`, references, helper and
   provenance, through links and through the copy fallback.
3. **The helper only does arithmetic.** `count_days.py` behaves exactly as the
   existing helper does: forward calendar-day counting with explicitly supplied
   exclusions and expiry adjustments, a result labelled as arithmetic and not a
   legal deadline, and a refusal for the unsupported rule interaction.
4. **English text.** Italian appears only as legal terms of art, statute names
   and source titles. The stamped tree passes the existing Italian gate.
5. **No permission change.** The helper runs under ordinary interactive
   approval. No allow entry, deny entry or cron-wrapper token is added.

## Constraints and exclusions

- No company literal and no clone content enters `cs/`.
- `agents/openai.yaml` is not shipped. It is Codex-only presentation metadata
  with Italian display strings, and the three-host contract keeps one host-neutral
  skill.
- The user-level Codex original stays where it is. It serves directories that
  are not clones; removing it is a separate decision.
- No CLI verb, manifest field, engine call or `cs/*.py` behavior changes.
- No release, tag, push, clone upgrade or re-collaudo is part of this brief.
  Publication of the skill text happens only with a separately authorized push.
- Other user-level skills are out of scope.
- The legal content is not re-validated here. The skill's own rule stands:
  links and statutory markers are research leads to be reopened at each use.
- The kernel is public and MIT-licensed. `PROVENANCE.md` travels with the skill
  and states its origin: an independent implementation written after a review
  of a CC BY-NC-ND 4.0 collection, redistributing none of that collection.

## Acceptance

1. The render gate reports `cs-legal-research` in the skill set of all three
   account configurations, with valid frontmatter.
2. A real `render_templates` run and a real `cs update` run each deliver
   `SKILL.md`, the four references, the helper and the provenance file. For
   every one of those files `.agents/skills` and `.opencode/skills` resolve the
   canonical bytes, and the forced copy fallback delivers them too.
3. The stamped helper, executed through each of the three host paths,
   reproduces every arithmetic case of the existing helper's test suite,
   including the refusals.
4. The rendered `AGENTS.md` and `cs-help` name the skill. The rendered
   `cs-triage-mail`, `.claude/settings.json` and `bin/cs_operator_cron.sh` are
   byte-identical to their renders before this change.
5. `bash tests/run.sh` reports all gates green.
6. In a rendered fixture, Claude Code, Codex and OpenCode each discover
   `cs-legal-research` and read one reference document through their own skill
   path. This establishes the observed discovery on each host, not future
   automatic selection or the quality of any legal answer.

## Assumptions and prerequisites

- `render_templates` copies a non-`.j2` template file byte for byte, `cs update`
  reads it as text and writes it, and `install_agent_surfaces` links the whole
  `.claude/skills` directory. Verified in `cs/project_init.py` and
  `cs/project_update.py` before this brief.
- `templates/project/.claude/**/*` in `pyproject.toml` already packages nested
  files under a skill directory.
- Work happens on branch `feat/legal-research-skill`, created from `origin/main`
  at `9780920` (`v0.51.0` plus two documentation commits), in a dedicated
  worktree.
- A new stamped skill is a MINOR at the next release. Its re-collaudo tier is
  `static`: stamped prose and one side-effect-free helper, with no send path,
  campaign, mailbox, auth or permission surface touched.
