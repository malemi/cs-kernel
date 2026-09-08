---
status: active
started: 2026-09-08
brief: ../briefs/2026-09-08-clone-harness-v8-shape.md
---

# Clones stamp the v8 doc-harness shape — execution plan

<!-- doc-scope:start -->
Scope: the ordered milestones that move the stamped charter to `AGENTS.md`,
reduce the kernel's claim on `CLAUDE.md` to a one-time bootstrap, release the
result, and migrate the two maintained clones — and how each step is verified.
The what and why are in the [brief](../briefs/2026-09-08-clone-harness-v8-shape.md);
the charter it must obey is [`AGENTS.md`](../../AGENTS.md).
<!-- doc-scope:end -->

## Shape

Five milestones, strictly ordered. M1 is the mechanism and its gates, shippable
to review on its own. M2 is prose: every stamped surface and this kernel's own
documents re-pointed. M3 is the release. M4 is the two clones, each with its own
verification. M5 is the final end-to-end review against the brief's acceptance
criteria. Nothing is pushed anywhere in any milestone; the push commands are the
last lines of the report.

Two design decisions the brief left to planning:

- **The one-shot supersession is a general rule, not a `CLAUDE.md` special
  case.** The ledger only ever stores the checksum of the kernel's own render
  (`project_update.py:655,760,763`; `project_init.py:1004-1007`), so a
  clone-authored path whose file on disk is byte-identical to its ledger entry
  has never been authored — it is still the kernel's default, on any path —
  and the new default may replace it, once. Only a path that *was* ledgered
  and is *now* clone-authored can match. Today that is `CLAUDE.md` on every
  clone stamped before this release. The residual case is named, not hidden:
  a clone that has not run `cs update` since before `v0.16.0` still ledgers
  `company/*` and `docs/active-context.md` (`project_init.py:874-879`), and an
  untouched default among them would be rewritten once with today's default —
  nothing an operator wrote can match, because nothing an operator wrote is in
  the ledger. No such clone exists on this machine; both maintained clones
  dropped those entries at their next update. After the run the path is out of
  the ledger and the rule can never fire on it again. Both stamping paths
  apply it: `cs update` from `old_checksums`, `cs init` from the
  `template-manifest.json` already in `dest_dir` when one exists.
- **The legacy symlink is replaced at write time, and the bootstrap waits for
  the charter.** `unlink_if_symlink(path)` runs inside both writers, right
  before a render lands, so a symlink at a render target is replaced and never
  written through — and a render that fails replaces nothing.
  `bootstrap_may_land(root, out_rel)` gates every write of `CLAUDE.md` on
  `AGENTS.md` being a regular file beside it; both walks are sorted so
  `AGENTS.md` is visited first, and when its render fails the old `CLAUDE.md`
  is kept with its ledger entry, so the next run can still finish the move.
  (The plan's first draft retired the link before the walk; the integration
  review showed that a failed charter render then left a clone with no
  instruction file at all, exit 0.)

## M1 — mechanism and gates

1. `git mv cs/templates/project/CLAUDE.md.j2 cs/templates/project/AGENTS.md.j2`.
   Inside it: title `# AGENTS.md`; the cross-reference to the kernel's own
   charter becomes `` `cs-kernel` `AGENTS.md` ``; § "Editing this clone" lists
   `AGENTS.md` (this charter) and `CLAUDE.md` (the bootstrap import, written
   once, owned afterwards by whoever manages it — a documentation harness's
   `/doc-create` may replace it) among the template-owned files, and states
   that `docs/.doc-profile` belongs to that harness, never to the kernel. The
   file ends in two newlines so the render keeps one.
   **Charter rule 1 binds every byte under `cs/`:** gate 1 greps the bare
   brand over `cs/` and blesses only `mrcall-desktop`, `mrcall-tracking` and
   `mrcall.search_businesses`. Neither this template nor the stub below names
   the harness's repository or any URL — only `/doc-create`. The repository
   name appears once, in the kernel `README.md` (M2.2), outside `cs/`.
2. New `cs/templates/project/CLAUDE.md` (plain, no Jinja): first line exactly
   `@AGENTS.md`, then one HTML comment saying what the file is and that a
   documentation harness's `/doc-create` replaces it. No brand, no URL.
3. `cs/project_init.py`: `CLONE_AUTHORED_PREFIXES` gains `"CLAUDE.md"`;
   `unlink_if_symlink()`; `bootstrap_may_land()`;
   `stamped_default_untouched(path, ledger_sum)`; `render_templates()` walks
   sorted, reads an existing `template-manifest.json` ledger when present,
   replaces a symlink at write time, and applies the supersession and landing
   rules in its clone-authored branch; `install_agent_surfaces()` loses the
   `AGENTS.md` link (lines 1195-1197), its docstring and closing print say
   only what it still does.
4. `cs/project_update.py`: `_write_clone_file` replaces a symlink at write
   time; the clone-authored branch applies the supersession and landing rules
   with a one-line print naming the file and why, and keeps the ledger entry
   when the bootstrap cannot land yet; the drift-report text at `:795-800`
   cites `AGENTS.md`.
5. `cs init`'s closing block gains one line: the project instructions are
   `AGENTS.md`, `CLAUDE.md` imports them for Claude Code.
6. Gates. `tests/test_agent_surfaces.py`: the fixture writes a real
   `AGENTS.md`; the symlink assertion becomes three — a legacy symlink is
   retired, a real `AGENTS.md` survives `install_agent_surfaces()`, and the
   helper never creates one. `tests/test_stamped_surfaces.py:84` names
   `AGENTS.md`. `tests/run.sh:877` and `:1089,1106` read `AGENTS.md.j2`;
   `:726` describes the new guard; the comments at `run.sh:875,1078,1106` and
   `cs/project_update.py:601` name `AGENTS.md.j2`. New
   `tests/test_charter_shape.py`, run as a new `step` in `run.sh`. It borrows
   only `_clean_env`, `_run_update`, `_checksum` and `_FULL_INIT_DATA` from
   `test_project_update.py` — `_stamp_clean_clone` cannot build the fixture
   (it renders `<rel>.j2`, and `CLAUDE.md` has no template after the rename)
   and `_minimal_manifest` overwrites the ledger — so the legacy clone is
   hand-built: `CLAUDE.md` with chosen content, the `AGENTS.md` symlink, a
   minimal `.claude/skills` tree, and a ledger whose `CLAUDE.md` entry is
   `_checksum()` of chosen content. Today's charter render comes from
   `build_jinja_env(TPL).get_template("AGENTS.md.j2")` with `TEMPLATE_DEFAULTS`
   under `_FULL_INIT_DATA`, independently of the code under test:
   - fresh render: `AGENTS.md` real and carrying the charter with a trailing
     newline, `CLAUDE.md` equal to the stub whose first line is exactly
     `@AGENTS.md` (the mechanical evidence for AC 2), no symlink, `CLAUDE.md`
     absent from the returned checksums;
   - real `python -m cs update` on a legacy clone (symlink + ledgered pristine
     `CLAUDE.md`): charter in `AGENTS.md`, `CLAUDE.md` equal to the stub, ledger
     without `CLAUDE.md`, and a second run that prints nothing about either;
   - the same on a clone whose `CLAUDE.md` differs from its ledger entry (a
     harness template, a hand edit): untouched on both runs;
   - a ledger checksum from an older render than the current template (the
     `mario124-cs` case): still supersedes, because the rule compares disk to
     ledger, never to today's render;
   - `render_templates` over the legacy shape with a manifest present: same
     result as the update path — the charter is not lost; with no manifest,
     `CLAUDE.md` is kept, because nothing proves it is the kernel's;
   - the two helpers: `retire_legacy_agents_link` unlinks a symlink, reports
     it, and never touches a regular file; `install_agent_surfaces` never
     replaces a real `AGENTS.md` and never creates one.
7. `bash tests/run.sh` green. Integration review of M1 before M2 begins.

## M2 — stamped surfaces and this kernel's documents

1. The nineteen `CLAUDE.md` mentions under `cs/templates/project/` listed in
   the brief's § Scope item 2 become `AGENTS.md`; `README.md.j2` adds one line
   under § Map saying what `CLAUDE.md` is.
2. Kernel `README.md`: after the setup steps, a short paragraph — `AGENTS.md`
   is the project's instructions, `CLAUDE.md` imports it for Claude Code, and a
   repository using the documentation harness at
   `github.com/malemi/mrcall-ai-kit` lets `/doc-create` manage `CLAUDE.md`.
   Not a required step.
3. Kernel `AGENTS.md` § Layout: the two sentences named in the brief;
   `docs/active-context.md`: the § 9 / § 10 pointers say `AGENTS.md.j2`, the
   trailing-newline item leaves § Unresolved.
4. `grep -rn 'CLAUDE\.md' cs/templates/` returns only the stub's own body and
   prose about that file. `bash tests/run.sh` green. Integration review.

## M3 — release `v0.42.0`

Per `docs/release-procedure.md`, in order, with the release diff reviewed
**before** the release commit (the procedure tags immediately after that
commit and calls the gap red, so the review sits ahead of it, not inside it):
`pyproject.toml` → `0.42.0`;
`CHANGELOG.md` `## v0.42.0 — 2026-09-09 (MINOR)` — the release commit's own
date in the repo's timezone (Europe/Rome), one day after this plan started —
with why, what, the clone
migration as it will be observed, tier **static** on both clones and the one
line of why that is safe (no send path, no auth, no permission surface — the
files that move are prose and an import); `docs/active-context.md` claims the
tag; release commit by explicit path; `git tag v0.42.0`; `bash tests/run.sh`
at the tag; post-tag commit (`untagged`, `IMMUTABLE_TAG_TARGETS["v0.42.0"]`);
the sweep grep on the kernel. **No push.**

## M4 — the two maintained clones

For `124-cs` then `mrcall-cs`, each started outside its tick windows
(`124-cs`: `0 6-18/2`; `mrcall-cs`: `:20` hourly and `:50` every second hour):

1. Install the tag from the local checkout into the clone's venv:
   `uv pip install --python .venv/bin/python "cs-kernel @ git+file:///home/mal/hb/cs-kernel@v0.42.0"`;
   `.venv/bin/python -m cs --version` prints `0.42.0`.
2. `.venv/bin/python -m cs update --pin v0.42.0` (pin line + manifest
   `init_data`), then bare `cs update` with stdin closed, so an unexpected
   conflict keeps the local file and is reported rather than answered blind.
   Expected: `+ AGENTS.md`, the `CLAUDE.md` supersession line, refreshed skill
   files, no prompt.
3. Verify: `AGENTS.md` is a regular file equal to the render; `CLAUDE.md` equals
   the stub; `template-manifest.json` has no `CLAUDE.md` key; `git status`
   shows the symlink→file typechange.
4. `requirements.lock` regenerated from the venv (`uv pip freeze`), the kernel
   line rewritten to its GitHub form at the tag's commit; proven by installing
   the lock alone into a throwaway `uv venv` with the URL substituted to the
   local checkout — the GitHub resolution itself is unprovable until the push,
   and the report says so.
5. The `/doc-create` v8 migration, by hand and to its letter: `docs/.doc-profile`
   → `harness_version = 8`, `index_file = AGENTS.md`, `harness_file =
   CLAUDE.md`, `index_max_lines` above the charter with the reason in a
   comment; `CLAUDE.md` replaced by the installed harness template and proven
   with `cmp`; `docs/README.md`'s index pointer says `AGENTS.md`;
   `docs/ARCHITECTURE.md` pin row and the active-context pin line say
   `v0.42.0`. `124-cs` only: a `doc-scope` block in `docs/README.md` and
   `docs/active-context.md` (`mrcall-cs` already has both), and the session
   file without `status` frontmatter gets one.
   `python3 ~/.config/mrcall-ai-kit/doc-check.py --repo .` clean.
6. `cs whoami` proof call. Static collaudo: diff of every refreshed stamped
   file against its pre-update copy, recorded in the commit message.
7. Commit by explicit path, the list taken from `git status` after the
   update rather than from memory. Expected: `AGENTS.md`, `CLAUDE.md`,
   `README.md` and `docs/projects/README.md` (both ledgered, both pristine,
   both templates change in M2), `docs/.doc-profile`, `docs/README.md`,
   `docs/active-context.md`, `docs/ARCHITECTURE.md`, `requirements.txt`,
   `requirements.lock`, `template-manifest.json`, the refreshed
   `.claude/skills/*` — never the operator's own uncommitted work (`124-cs`:
   `company/*`, `docs/briefs/`, `docs/projects/<name>/`; `mrcall-cs`:
   `docs/owner-actions.md`, `.head-ac.tmp`). Integration review of the two
   clone diffs before either commit.
8. After both: kernel `CHANGELOG.md` operational-pin marker → `v0.42.0`, one
   more kernel commit. `mario124-cs` untouched, named in the report.

## M5 — final end-to-end review

A fresh reviewer checks the brief's nine acceptance criteria against the real
kernel tree, the tag, and both clones — not against this plan. Findings are
repaired on main before the report. Then this plan's status becomes
`completed`, the kernel and clone session files are closed, and the report
opens with the unpushed state.

## Risks

- **Writing through the legacy symlink.** Covered by the retire helper running
  before either walk and by the update-path and init-path tests in M1.6.
- **The supersession rule firing on an operator's file.** It requires a
  byte-exact match with the ledger's own checksum; a file the operator changed
  by one byte does not match. Covered by the "differs from ledger" test.
- **`_offer_release_upgrade` before the push.** It reads GitHub's tags, finds
  `v0.41.0` as latest, compares to the pinned `v0.42.0`, and proceeds quietly
  (`_tag_key(latest) <= _tag_key(pinned)`). Verified by reading; observed in
  M4.2.
- **A cron tick during a clone update.** Updates take seconds and are timed
  between ticks; a tick reads whole files, and every file it reads is consistent
  before and after.
- **Rollback.** Kernel: `git reset --hard 2186827` and `git tag -d v0.42.0` —
  nothing is published. Clone: `git checkout -- <paths>` by path — `AGENTS.md`
  (back to the tracked symlink), `CLAUDE.md`, `README.md`,
  `docs/projects/README.md`, the skills, the pin files — restores every stamped
  file; `uv pip install` of the `v0.41.0` pin restores the venv.

## Out of scope

`docs/.doc-profile` as a kernel template; the environment-wide
`keep_trailing_newline`; `mario124-cs`; the two meta-repos' service tables.
