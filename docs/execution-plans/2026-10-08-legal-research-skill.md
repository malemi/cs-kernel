---
status: active
---

# Legal-research kernel skill execution plan

Approved brief: [2026-10-08-legal-research-skill.md](../briefs/2026-10-08-legal-research-skill.md).
Brief review: first pass REVISE on `5158e14`; re-review APPROVED on
`db85607`, reviewed brief SHA-256
`3d66735c3caa11342a369d93788c2d7fc47aa8dfd7b166eb345488ccb16fc1ba`.
Acceptance 7 was amended at `17bab69` after this plan's first review
(SHA-256 `399175052e1c0f8ec25f3c73e3e48848a2f23d865a4493e16c952f5407d40d84`):
Codex reports a linked skill root by its target, and discovery is taken from
what each host reports. The brief's reviewer re-reviewed the amendment:
APPROVED.
Plan review: first pass REVISE on `5567483` with three required changes;
second pass REVISE on `95f094c` with one. All four are applied here.

## Classification and ownership

Substantial development: a new stamped skill changes the operator surface of
every clone. It is not a fast-path change.

The lead owns the skill text, routing, tests, documentation and reviews. The
work is seven small template files and edits to seven existing files, so
implementation is not delegated; gate runs and native acceptance run inline.
Each review gate uses a fresh reviewer.

All changes land on branch `feat/legal-research-skill` in the worktree
`/home/mal/worktrees/cs-kernel-legal-research`. Commits by explicit path on
that branch are part of the work. No push, tag, release, clone upgrade or
change outside this worktree is authorized.

## Dependencies and baseline evidence

- Base: `origin/main` at `9780920` (`v0.51.0` plus two documentation commits).
- `bash tests/run.sh` on the unmodified branch: 70 gates, all green. The
  golden-pack gate is skipped by design; it is env-driven.
- Baseline render of the base with `_FULL_INIT_DATA`, generic shape. SHA-256 of
  the three surfaces that must not change:
  - `.claude/skills/cs-triage-mail/SKILL.md` `3bcf71668e55d7d7f7e9c1d44cb5c9317c4f90c7c9c629d8c9a859819dc0c64d`
  - `.claude/settings.json` `58f5ada0513b2607f115ccf80528436c533939760280917eb096bca0251a91e0`
  - `bin/cs_operator_cron.sh` `00aaea8be348579cd9fce61d02d8dd15903ba005f12d26dbb7ed3b7503319da9`
- Interpreters: `tests/run.sh` builds its own environment with `pip install`.
  Focused tests run with `/home/mal/hb/cs-kernel/.venv/bin/python`, which holds
  `cs-kernel` 0.45.0; the tests import the worktree source through their own
  `sys.path` insert, and any leg that needs the installed package runs only
  under `tests/run.sh`.
- Native hosts on the acceptance machine: Claude Code, Codex and OpenCode are
  installed. Claude Code updates itself, so each host's version is recorded at
  run time under Results. Codex also loads user-level skills.
- The user-level Codex original `~/.codex/skills/ricerca-giuridica-it/` stays
  in place for the whole of this plan, as the brief states. M1's review
  compares the templates with it, and M2 reports it as the other legal skill
  Codex lists. Its removal is a separate operator decision and no step here.
- Source skill `~/.codex/skills/ricerca-giuridica-it/`, SHA-256:
  - `SKILL.md` `b0b665c5437664c61e8ae0f299d7a4daaa021586c9fdd002dc2bb5f2f1062083`
  - `PROVENANCE.md` `6a55ad3c2010685cc22db1150e67878055375248f02ace2fc27d3d20e3f52340`
  - `references/administrative-remedies.md` `e5f41994199e19a6f248b38da43cec40de0177f647ad5fc4d8eedbca5ddc465b`
  - `references/deadlines.md` `d2f9ee5a2d4be07d0ae7d2d236f958721e74da40084e04b4667495d899e3dd86`
  - `references/evidence.md` `ec693466f0d91bc749516147d659f443ac4e03b25f198f31d2cab5d9977e7a99`
  - `references/sources.md` `46639a4e2e50bf677f8dffd39f2f3fa007a6afdb45c90e2d4d710a5893075c37`
  - `scripts/count_days.py` `1fac35e1e3bf1ffedc49bcb3df256ba8f06d968b481e814261862a4fe908cb07`
- Constraints verified before planning: a plain `.py` in the template tree is
  byte-compiled by `pip install` and breaks `cs update`; under the kernel's
  Jinja environment `{% raw -%}` + newline + body + `{% endraw %}` + newline
  renders the body byte for byte, while an opener without the dash leaves a
  leading newline. The form is exact only when the body starts with a
  non-whitespace character and contains no `endraw` tag: the dash also strips
  leading blank lines and indentation, and an `endraw` inside the body is a
  template syntax error. The contract gate therefore compares rendered bytes
  with the body.
- With all seven files as `.j2`, the installed-template inventory gate counts
  49 templates: the 42 of the base plus these seven.

## M1 — Skill, routing and gates

**Templates.** Add under
`cs/templates/project/.claude/skills/cs-legal-research/`:

| Template | Content |
|---|---|
| `SKILL.md.j2` | The source `SKILL.md` with four edits: `name: cs-legal-research`; a description that confines selection to the interactive human's own question and excludes the scheduled operator and customer mail; a `## When this skill applies` section stating the same and pointing legal customer mail at the Escalate branch of `cs-triage-mail`; the closing provenance sentence without "local". No Jinja variable. |
| `references/sources.md.j2` | Source file in one raw block. Renders byte-identical to the source. |
| `references/administrative-remedies.md.j2` | Same. |
| `references/evidence.md.j2` | Same. |
| `references/deadlines.md.j2` | Source file in one raw block with the helper named and invoked by its path inside a clone: `.venv/bin/python .claude/skills/cs-legal-research/scripts/count_days.py`. |
| `scripts/count_days.py.j2` | Source helper in one raw block. Renders byte-identical to the source. |
| `PROVENANCE.md.j2` | The source provenance in one raw block, restated for this copy: same upstream repository, commit, directory, licence and review date; "newly written"; no session narrative. |

`agents/openai.yaml` is not added.

**Routing.** In `cs/templates/project/AGENTS.md.j2` § 4 add the skill to the
interactive list with its boundary. In
`cs/templates/project/.claude/skills/cs-help/SKILL.md.j2` add a table row, one
"Or just ask" example and the name in the closing skill list.

**Gates.**

- `tests/test_template_render.py`: add `cs-legal-research` to
  `expected_skills`.
- New `tests/test_legal_research_skill.py`, exporting the file list the other
  gates import: no Python source or bytecode in the template roots; the skill's
  templates are exactly the seven `.j2`; each supporting template is one raw
  block of LF-ended UTF-8 text; a rendered clone holds exactly the seven files,
  all in the checksum ledger and resolved identically by `.agents` and
  `.opencode`, with each of the six supporting files byte-identical to its raw
  block; every relative link resolves; the
  description confines selection; the stamped helper reproduces ten arithmetic
  cases and six refusals through each of the three host paths; settings and
  cron wrapper name neither the skill nor its helper; triage still carries the
  Escalate branch; `AGENTS.md` and `cs-help` route to the skill. Under
  `tests/run.sh` it also renders from the pip-installed package and asserts the
  seven files and no bytecode in the clone.
- `tests/test_agent_surfaces.py`: the real rendered clone and the forced
  copy fallback resolve every file of the skill for both linked hosts.
- `tests/test_stamped_surfaces.py`: the real `cs update` run adds the seven
  files to a clone that predates the skill, with both hosts resolving them.
- `tests/run.sh`: step 62 runs the new test.

**Documentation owned by M1.** `docs/agent-skills.md` gains the
supporting-file contract and the legal-research section with its
instruction-level boundary.

**Verification**, from the worktree, logs retained in the session scratch
directory:

```bash
PY=/home/mal/hb/cs-kernel/.venv/bin/python
$PY tests/test_template_render.py
$PY tests/test_legal_research_skill.py
$PY tests/test_agent_surfaces.py
$PY tests/test_stamped_surfaces.py
rm -rf build && bash tests/run.sh
```

Then render the branch with the baseline's variables and compare the three
SHA-256 values above.

A fresh reviewer evaluates M1 against the brief and this plan before M2.

## M2 — Native three-host acceptance

Render a fixture clone from the branch into a scratch directory, with a company
slug nothing else on the machine uses, and initialize a git repository there.
No mail, no engine, no clone and no network service other than each host's own
model provider is involved.

Discovery is taken from what the host reports and the read from the host's
event stream. An agent's own sentence about what it loaded is not evidence.
Every host command writes to a file: through a pipe `opencode debug skill`
stops at 65,536 bytes and its output no longer parses.

| Host | Discovery evidence | Read evidence |
|---|---|---|
| Codex | `codex debug prompt-input`, run inside the fixture; it makes no model call. The skill list names `cs-legal-research` with its file under a root alias, and the alias legend places that root inside the fixture. Codex resolves the `.agents/skills` link, so the root it prints is `.claude/skills`. In a copy of the fixture without `.agents/skills` the same command lists no `cs-` skill. | `codex exec --json --sandbox read-only`: the event that reads `references/sources.md` under the fixture's skill directory, with its output. |
| OpenCode | `opencode debug skill`, run inside the fixture; no model call. `cs-legal-research` is registered at a location inside the fixture. OpenCode reads `.opencode/skills`, `.agents/skills` and `.claude/skills`, which are one tree here, and reports one of them. | `opencode run --format json`: the tool event that reads the reference, with its path. |
| Claude Code | `claude -p` with `--output-format stream-json --verbose` and only `Read`, `Glob`, `Grep` and `Skill` allowed: the `Skill` tool call and its result, and the init event's skill list where the stream carries one. | Same stream: the `Read` call on `.claude/skills/cs-legal-research/references/sources.md` and its result. |

Each model run gets one prompt: load the project skill `cs-legal-research`,
read its sources reference through the skill's own directory, reply with that
reference's first heading, and do nothing else.

Results record, per host: the command lines, the host version, the exit
statuses, the decisive event lines, and the SHA-256 and path of each raw
transcript kept in the session scratch directory. One observed discovery per
host is what this establishes.

## Closure

`doc-end` first: reconcile `docs/active-context.md`, `docs/README.md` and
`docs/agent-skills.md`, run the mechanical gate and `doc-critic`, then
`doc-check.py --completion check`. Then the final review by a fresh reviewer
through the final-user path: a rendered clone and the acceptance evidence, not
the diff alone. After APPROVED, `doc-check.py --completion finalize`.

## Rollback

Revert the branch commits; nothing outside this worktree is touched before a
release. After a release, a clone that received the skill keeps its seven files
when a later kernel drops them, because `cs update` does not remove a file the
template stopped shipping; removing them is a `git rm` in that clone.

## Note for the next release

This plan releases nothing. When a tag is authorized, the change is a MINOR: a
new stamped skill. Re-collaudo: both maintained clones, tier `static`. Why that
is safe for a MINOR: the change is stamped prose and one side-effect-free
helper; no send path, campaign, mailbox read, auth boundary or permission
surface is touched and no `cs/*.py` changes.

## Results

### M1 — committed as `915d7b4`

- `bash tests/run.sh` in the worktree, after `rm -rf build`: 71 gate headers,
  `RESULT: all gates green`. Step 3 prints `OK: 49 installed templates match
  source paths and bytes`, against 42 on the base. Step 62 ran from the
  pip-installed package without skipping its installed-build leg: 141 checks.
- Focused runs with the kernel venv interpreter: the render gate prints
  `43 templates x 3 configs: ALL RENDER CLEAN`; `test_legal_research_skill`,
  `test_agent_surfaces` and `test_stamped_surfaces` pass. Under that
  interpreter the installed-build leg is skipped with its note, as designed.
- Render of the branch with the baseline's variables: 44 stamped files against
  37. Changed: `AGENTS.md` and `.claude/skills/cs-help/SKILL.md`. New: the seven
  files of the skill. `cs-triage-mail/SKILL.md`, `.claude/settings.json` and
  `bin/cs_operator_cron.sh` carry the three baseline SHA-256 values above.
- Against the source skill: `references/sources.md`,
  `references/administrative-remedies.md`, `references/evidence.md` and
  `scripts/count_days.py` are stamped byte-identical. `SKILL.md`,
  `PROVENANCE.md` and `references/deadlines.md` carry the planned edits.
- The new gate fails by name on each of these deliberate breaks, tried on a
  scratch copy: a plain `.py` in the template tree, a CRLF supporting template,
  a deleted reference, a deleted `SKILL.md.j2`, helper arithmetic off by one, a
  helper that prints on a refusal, a helper that drops an output key, a
  description without its confinement sentence, the helper named in
  `settings.json`, a raw opener without the dash, a triage skill without its
  Escalate branch.

### M1 review

APPROVED by a fresh reviewer on `915d7b4`, with no required change: the commit
holds exactly the fifteen planned files, the four verbatim files are
byte-identical to the source, every other difference is one of the four kinds
the brief allows, and each recorded number reproduced. Two of its remarks are
applied in `186c367`: the `cs-help` check now holds the table row, the example
and the closing list separately, and the bytecode comment in the
stamped-surfaces gate says what it catches. A third, the exact condition under
which a raw block renders verbatim, is corrected in `docs/agent-skills.md` at
closure.

### M2 — native discovery on the three hosts, kernel at `186c367`

Fixture: a clone rendered from the branch with the slug `legalfixture`, a git
repository, `.agents/skills` and `.opencode/skills` linking to
`../.claude/skills`. Raw transcripts are in the session scratch directory
`scratchpad/m2/`; their SHA-256 values are below. Prompt of each model run:
"Load the project skill named cs-legal-research. Then read the file
references/sources.md inside that skill's own directory and reply with only its
first heading line. Do nothing else: no web access, no other files, no other
commands."

| Host | Discovery, from the host | Read, from the event stream |
|---|---|---|
| Codex `codex-cli 0.161.0` | `codex debug prompt-input`, exit 0, no model call: `cs-legal-research … (file: r3/cs-legal-research/SKILL.md)` with `r3` = `<fixture>/.claude/skills`. In a copy without `.agents/skills`: no `cs-` skill listed. Transcripts `3afdfb01…` and `40f074da…`. | `codex exec --json --sandbox read-only -C <fixture>`, exit 0: `command_execution` of `cat .claude/skills/cs-legal-research/references/sources.md`, output beginning `# Source retrieval and legal validation`. Transcript `cd16c1e8…`. |
| OpenCode `1.18.35` | `opencode debug skill`, exit 0, no model call: registered at `<fixture>/.opencode/skills/cs-legal-research/SKILL.md`, bytes equal to the canonical file. Transcript `3de45e0f…`. | `opencode run --format json --dir <fixture>`, exit 0: tool `skill` with `name: cs-legal-research` completed, then tool `read` of `<fixture>/.opencode/skills/cs-legal-research/references/sources.md`. Transcript `e96594a8…`. |
| Claude Code `2.1.294` | `claude -p … --allowedTools Read,Glob,Grep,Skill --output-format stream-json --verbose`, exit 0: the init event lists the skill (skills, slash_commands); `Skill` tool call with `skill: cs-legal-research`, answered with `Base directory for this skill: <fixture>/.claude/skills/cs-legal-research`. | Same stream: `Read` of `<fixture>/.claude/skills/cs-legal-research/references/sources.md`, result line 1 `# Source retrieval and legal validation`. Transcript `8c9abc36…`. |

The canonical `SKILL.md` of the fixture is SHA-256 `d903fcf1…` and
`references/sources.md` is `46639a4e…`, the source skill's own value.

Codex listed one other legal skill in every run, the user-level original:
`ricerca-giuridica-it … (file: r0/ricerca-giuridica-it/SKILL.md)` with `r0` =
`~/.codex/skills`. Its root is outside the fixture.

This establishes one observed discovery and one reference read per host. It
does not establish automatic selection from a plain-language question,
scheduled-run behavior or the quality of a legal answer.

### Closure

Pending.
