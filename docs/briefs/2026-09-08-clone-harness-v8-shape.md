# Brief — clones still stamp the pre-v5 doc-harness shape

## Intent

The mrcall-ai-kit doc harness reached `harness_version = 8`, which splits the two
roles a single `CLAUDE.md` used to hold: `AGENTS.md` is the project-owned index
(the charter a human and every agent reads), and `CLAUDE.md` is a managed file
replaced byte-for-byte with the harness template, whose whole content is
`@AGENTS.md` plus the harness's own delivery contract.

This repo migrated itself on 2026-09-02 — `docs/.doc-profile` here says
`index_file = AGENTS.md`, `harness_file = CLAUDE.md`, and root `CLAUDE.md` is
byte-identical to `~/.config/mrcall-ai-kit/CLAUDE.template.md`. **The project
template was not migrated.** Clones therefore keep stamping the old shape: the
charter into `CLAUDE.md`, plus an `AGENTS.md` symlink pointing back at it.

Move the stamped charter to `AGENTS.md`, and reduce the kernel's claim on
`CLAUDE.md` to a one-time bootstrap it never touches again.

## Why this is not cosmetic

The old shape puts two owners on one path. `cs update` renders `CLAUDE.md` from
`cs/templates/project/CLAUDE.md.j2`; the doc harness wants the same path
replaced with its template and reports it as a gate failure until it is. There
is no arrangement in which both are satisfied while the charter lives in
`CLAUDE.md`.

The cost is already being paid, in writing, in both clones:

- `124-cs` is stuck at `harness_version = 3`. Its gate fails on
  `[HARNESS TEMPLATE] CLAUDE.md: managed harness file differs from the installed
  template`, and `doc-start` / `doc-end` refuse to advance the baseline.
- `mrcall-cs` is stuck at `harness_version = 4`, and its `docs/.doc-profile`
  carries a hand-written note recording the same wall: trimming `CLAUDE.md` in a
  clone "would be overwritten by the next `cs update`". It works around the
  thin-index check with `index_max_lines = 221`.

A third clone, `~/124/mario124-cs` (`mario.alemi@cafe124.it`, pinned
`v0.35.0`, no commits, no remote), has the same symlink and a `CLAUDE.md` that
matches its own `v0.35.0` ledger entry. It is not upgraded by this work — the
kernel's active-context records that its history starts when its operator
starts it — but its shape is the third instance of the same wall, and the
migration must be correct for it whenever `cs update` is run there.

Three clones, one shape, same wall — the rule of two, exceeded. Migrating any
clone locally would fork the charter: `AGENTS.md` would freeze at the pinned
kernel version and need a hand merge at every re-pin, in repos whose recent
history is almost entirely re-pins.

## The ownership decision — the kernel bootstraps `CLAUDE.md`, then never touches it

Two candidates were rejected before the third.

**Ship a copy of the harness template.** Rejected: `doc-check.py:398-433`
byte-compares a clone's `CLAUDE.md` against the harness template installed *on
the machine*, never against anything the kernel ships. A kernel-shipped copy
would go red in every clone on each mrcall-ai-kit bump until a kernel release
plus a re-pin carried a file the kernel neither owns nor can change — the same
two-owner disease, with a release-cadence coupling on top.

**Ship nothing at all.** Rejected on a fact that outranks the tidiness: this
kernel is a **public** product (`README.md:106` publishes a `uvx … cs init`
install path; `github.com/malemi/cs-kernel` is public), and mrcall-ai-kit is a
separate repo the kernel never mentions. Claude Code does not load `AGENTS.md`
natively — it reaches the project file through `CLAUDE.md`'s `@AGENTS.md`
(`mrcall-ai-kit/shared/commands/doc-start.md:51`). So a clone with no
`CLAUDE.md` starts every Claude Code session with **no project instructions at
all**: no identity, no § 5 safety NEVERs, no engine-authority rule. For every
operator who installs the public wizard and does not have an unadvertised second
repo, that is the permanent state, and nothing announces it.

**The shape that is actually built:** the kernel ships
`cs/templates/project/CLAUDE.md`, a minimal bootstrap whose body is the
`@AGENTS.md` import, and adds `CLAUDE.md` to `CLONE_AUTHORED_PREFIXES`. A
clone-authored path is written once when the clone has none and then never
re-stamped and never checksummed (`cs/project_init.py:965-969, 1000-1002`;
`cs/project_update.py:632-645`, which `continue`s before
`new_checksums[str_out_rel]` is ever assigned). So:

| Path | Bootstrapped by | Owned by |
|---|---|---|
| `AGENTS.md` | — | cs-kernel (`AGENTS.md.j2`), every update |
| `CLAUDE.md` | cs-kernel, exactly once | the doc harness, via `/doc-create` |
| `docs/.doc-profile` | — | the doc harness, via `/doc-create` |

The kernel is a bootstrap default here, not an owner: it writes the file when
nothing else will, and its ledger never claims it. An operator with the harness
runs `/doc-create`, which replaces the stub with the full harness template and
owns it from then on. `doc-check` reds the stub until that happens — one command
away, for the only people who can see the gate at all.

**One-shot migration for the two existing clones.** They already hold a
`CLAUDE.md` containing the old charter, which the clone-authored rule would
leave in place — a stale duplicate that Claude Code would load in preference to
the real one. `cs update` therefore replaces `CLAUDE.md` with the bootstrap stub
in exactly one case: when the file on disk is byte-identical to the charter this
kernel itself stamped there, proven by the `CLAUDE.md` checksum still in the
clone's ledger at the moment of the run. Anything else is the operator's file
and is left alone.

## Scope

### Kernel

1. `cs/templates/project/CLAUDE.md.j2` → `cs/templates/project/AGENTS.md.j2`.
   The `{% include "outbound-fact-sourcing.md.j2" %}` partial travels with it.
2. Re-point every stamped surface that names the clone's charter by filename.
   Verified inventory — all of these say `CLAUDE.md` and must say `AGENTS.md`:
   `README.md.j2:10,97` · `AGENTS.md.j2:1,34,43` (its own title, the kernel
   cross-reference, and the template-owned list) ·
   `.claude/skills/cs-review/SKILL.md.j2:24` ·
   `.claude/skills/cs-help/SKILL.md.j2:60` ·
   `.claude/skills/cs-operator/SKILL.md.j2:134` ·
   `.claude/skills/cs-customer/SKILL.md.j2:35,41` ·
   `.claude/skills/cs-triage-mail/SKILL.md.j2:56` ·
   `company/README.md.j2:21` · `company/claude-extra.md.j2:6,7` ·
   `company/clone-notes.md.j2:33` · `docs/ARCHITECTURE.md.j2:62,72` ·
   `docs/projects/README.md.j2:122,154`.
   `cs-review/SKILL.md.j2:24` is the sharpest: "Read `CLAUDE.md` in full. It owns
   identity, source authority, safety…" would send every review session to a
   two-line stub.
   Two of these assert an auto-load, not just a location —
   `docs/projects/README.md.j2:154` ("loaded on every agent session") and
   `company/claude-extra.md.j2:9` ("an agent reads at the start of every
   session"). Both stay true under this design, because `CLAUDE.md` exists and
   imports `AGENTS.md`; they need the filename re-pointed, and nothing more.
3. The operator-facing text at `cs/project_update.py:795-800` cites
   `CLAUDE.md, "Editing this clone"` as the rule's home — re-point to `AGENTS.md`.
4. `install_agent_surfaces()` (`cs/project_init.py:1168`) stops creating the
   `AGENTS.md` → `CLAUDE.md` symlink; `.agents/skills` and `.opencode/skills`
   are untouched. Its docstring and its closing print change with it.
5. **Both** stamping paths remove a legacy `AGENTS.md` symlink *before* they
   write templates — `cs update`'s walk (`cs/project_update.py`, the walk that
   ends at `:807`) and `cs init`'s `render_templates`
   (`cs/project_init.py:942`, called at `:1319`).
6. New `cs/templates/project/CLAUDE.md` — a plain file, no variables — holding
   the `@AGENTS.md` import and one line saying a doc-harness user's
   `/doc-create` replaces it. `CLAUDE.md` joins `CLONE_AUTHORED_PREFIXES`
   (`cs/project_init.py:883`), plus the one-shot ledger-proven replacement in
   `cs update` described in § The ownership decision.
   `README.md.j2` gains one line on what `CLAUDE.md` is; the kernel's own
   `README.md` names `github.com/malemi/mrcall-ai-kit` as the optional doc
   harness that takes the file over. Neither makes it a required setup step —
   a bare `cs init` must produce a working clone on its own.
7. Gates, by name: `tests/run.sh:877` (gate 38 — hard-codes
   `cs/templates/project/CLAUDE.md.j2`), `tests/run.sh:1089,1106` (gate 48 —
   same path, would raise `FileNotFoundError`), `tests/run.sh:726` (gate text
   "AGENTS.md resolves to CLAUDE.md"), `tests/test_agent_surfaces.py:83-84`
   (asserts the symlink), `tests/test_stamped_surfaces.py:84`
   (`OUTBOUND_SURFACES` names `"CLAUDE.md"`, used at `:186`, `:236-249`, `:366`).
8. This kernel's own charter and state carry two sentences the change makes
   false — `AGENTS.md` § Layout ("while `AGENTS.md` points to `CLAUDE.md`";
   "ships to every clone in `templates/project/CLAUDE.md.j2` § 0b") — and
   `docs/active-context.md` names `CLAUDE.md.j2` as the home of § 9 and § 10.
   Present-tense corrections, nothing more.
9. The rendered charter regains its trailing newline. `docs/active-context.md`
   § Unresolved lists it as "fix rides the next release": the Jinja environment
   has no `keep_trailing_newline`, so a template ending in a single `\n` renders
   without one. The fix is scoped to the file this work already renames —
   `AGENTS.md.j2` ends the way the five templates that keep their newline
   already do. The environment-wide flag is **not** flipped: it would change
   the checksum of some twenty-seven stamped files in every clone, the cron
   wrapper among them, for whitespace.
10. Release per `docs/release-procedure.md`. MINOR — the stamped shape changes.

### Per clone, after the release

`124-cs` and `mrcall-cs`: `cs update` + re-pin, then `/doc-create` to install
`CLAUDE.md` and move `docs/.doc-profile` to v8. The profile bump must also raise
`index_max_lines` past the charter's 278 lines (`mrcall-cs` already carries the
same knob and its reasoning at 221). `mario124-cs` is left as it is and named
in the report.

Two operational constraints on that step:

- **The tag is not pushed until the operator says so**, and `cs update`
  discovers tags with `git ls-remote` against the GitHub origin in the
  clone's pin line. Until the push, the clone venvs are installed from the
  local checkout at the tag (`git+file://…@v0.42.0`); `requirements.txt` and
  `requirements.lock` are written in their normal GitHub form, because the
  tag's commit hash is the same on both remotes. That leaves each clone pinned
  to a tag GitHub does not yet hold — safe for the installed venv and the cron,
  wrong for anything that rebuilds a venv from `requirements.txt` before the
  push. It is the first line of the report.
- `mrcall-cs` runs live crons at `:20` every hour and `:50` every second hour;
  `124-cs` ticks at `0 6-18/2`. Each clone's `cs update` runs outside a tick
  window; the update itself takes seconds.

## Out of scope

`docs/.doc-profile` is not stamped by the kernel: `index_max_lines`, `build` and
their comments are per-clone tuning a template render would flatten, and
`/doc-create` already owns its migration.

The two meta-repos' service tables (`~/hb/AGENTS.md:48`, `~/124/CLAUDE.md`)
link each clone's `CLAUDE.md` as its instruction file. After the migration the
link still resolves but the charter is `AGENTS.md`. Other repos, one line each;
reported, not edited here.

## Constraints — and the failure mode, corrected

`_write_clone_file` (`cs/project_update.py:122`) uses `write_text`, which
follows a symlink; `sorted(rglob("*"))` visits `AGENTS.md.j2` before
`CLAUDE.md.j2`. Both verified. What follows from that differs by entry point,
and the difference matters because a test written to the wrong failure mode
asserts the wrong thing:

- **`cs update` — a silent non-migration, not a lost charter.** The rendered
  charter is written through the symlink into `CLAUDE.md`. The clone then holds
  a `CLAUDE.md` carrying the charter and an `AGENTS.md` symlink pointing at it —
  the shape it started in. The next run reads the same bytes back through the
  symlink, finds they match, and `continue`s: the non-migration is invisible on
  every later run, not just this one.
- **`cs init` in-place restamp — a genuinely lost charter.** `render_templates`
  walks `template_dir.rglob('*')` **unsorted** (`cs/project_init.py:954`) and
  `install_agent_surfaces` runs after it (`:1351`). On the documented restamp
  (`:965-969`) the writes land in filesystem order, with no prompt and no ledger
  entry to fall back on.

Removing the symlink before either walk is what makes both correct.

Other constraints:

- Codex and OpenCode read `AGENTS.md`. After the change they read a real file
  holding the charter — the same bytes they resolve today through the symlink.
- Ordering is fixed: `cs update` first, `/doc-create` second. The one-shot
  replacement is what keeps the window between them safe — without it the clone
  holds two charters and Claude Code loads the stale one.
- Never push without the operator's explicit ok.

## Acceptance criteria

### Kernel

1. A fresh `cs init` produces `AGENTS.md` as a real file holding the charter, a
   `CLAUDE.md` holding the bootstrap import, no `AGENTS.md` symlink, and
   `.agents/skills` / `.opencode/skills` symlinks unchanged.
2. **The operator who has no doc harness is covered.** After a bare `cs init`
   with mrcall-ai-kit absent, a Claude Code session opened in the clone loads
   the charter — the § 5 safety NEVERs among it — through `CLAUDE.md`'s
   `@AGENTS.md`. This is the criterion the "ship nothing" design failed.
3. `cs update` on a clone in the old shape (pristine `CLAUDE.md`, `AGENTS.md`
   symlink) ends with the charter in a real `AGENTS.md`, the symlink gone,
   `CLAUDE.md` holding the bootstrap import, and no `CLAUDE.md` entry in
   `template-manifest.json`.
4. `cs update` on a clone whose `CLAUDE.md` is anything other than the charter
   this kernel stamped — a harness template already installed by `/doc-create`,
   or an operator's own edit — leaves that file untouched, and keeps leaving it
   untouched on every later run.
5. `cs init` restamped in place over the old shape does not lose the charter.
6. `install_agent_surfaces()` is idempotent and never overwrites a real
   `AGENTS.md`.
7. `grep -rn 'CLAUDE\.md' cs/templates/` returns **zero** hits that point a
   reader at a clone `CLAUDE.md` for charter content. The kernel's own charter is
   now `cs-kernel`'s `AGENTS.md`, so `docs/ARCHITECTURE.md.j2:62` re-points too;
   the only surviving mentions are the bootstrap file's own body and prose about
   what that file is.
8. `bash tests/run.sh` green, and the release sweep in
   `docs/release-procedure.md` clean.

### Per clone

9. `[PROFILE]` and `[HARNESS TEMPLATE]` violations gone from `doc-check` in both
   clones, at `harness_version = 8`. A fully clean gate additionally needs the
   `index_max_lines` bump named in § Scope, and in `124-cs` two missing
   `doc-scope` blocks and one session file without `status` frontmatter — none
   of which this kernel release can reach.

## Material assumptions

- `template-manifest.json` `file_checksums` keys the ledger by output path.
  `AGENTS.md` is absent from both clones' ledgers today, so it lands via the
  "new template file" branch; `CLAUDE.md`'s entry disappears because a
  clone-authored path is never written into `new_checksums`, and
  `cs/project_update.py:779` assigns that dict outright rather than merging.
  Verified by reading, not yet by running.
- The one-shot replacement needs the OLD `CLAUDE.md` checksum, which is in the
  clone's ledger when the run starts and gone when it ends. It must therefore be
  read before the ledger is rewritten — an ordering constraint the plan owns.
- Both clones' `CLAUDE.md` is pristine — disk sha256 equals the stored checksum
  — so neither operator faces a conflict prompt. Verified.
- Re-collaudo tier: this touches no send path, no `campaign`, no
  `gmail_archive`, no `send_mail`, no auth boundary, no permission surface. It
  changes stamped prose and the file it lands in. Tier `static`, both clones.
