---
status: active
started: 2026-09-03
brief: ../briefs/2026-09-03-memory-layer-map.md
---

# The memory layer map — execution plan

<!-- doc-scope:start -->
Scope: the ordered milestones that ship `cs memory` (the ten-store map as a
read-only verb), charter § 10, and the set-agreement gate — and how each is
verified. The what and why are in the
[brief](../briefs/2026-09-03-memory-layer-map.md); the charter they must obey
is [`AGENTS.md`](../../AGENTS.md).
<!-- doc-scope:end -->

## Shape

Three milestones, strictly ordered. M1 is the verb and is independently
shippable to review; M2 is the stamped surfaces plus the gate that locks them
to the verb, and depends on M1's store identifiers; M3 is the release, and is
where the operator's explicit ok gates every push. Design decisions the brief
left to planning are fixed in M1/M2 below, each with its rationale.

## M1 — the verb

**1. `cs/memory_report.py`**, mirroring `cs/config_report.py`'s module shape
(docstring stating why the kernel answers this question itself; pure-data
registry; a render function the CLI calls).

- The registry is a module-level `STORES` tuple — one entry per store, each
  carrying a stable slug `id`, the authority sentence, read surface(s), write
  surface(s), and a `resolve(settings)` returning `(location, presence)`.
  The ten ids, fixed here so M2 and the gate have something to agree on:
  `engine-memory`, `user-notes`, `gmail-sent`, `ledger`, `company-notes`,
  `dossiers`, `campaign-packs`, `operator-log`, `template-manifest`,
  `cc-memory`. The registry is data, not prose: the gate in M2 reads it.
- Filesystem rows resolve their path from `Settings` (`db_path`, `log_path`,
  clone root) and report `present` / `absent`. Git-prose rows (`company/`,
  `docs/projects/`, `campaigns/`) resolve relative to the clone root and
  report `present` / `absent` by directory existence — never contents.
- The `gmail-sent` row's location is the mailbox scope (profile accounts plus
  `[operator].read_mailboxes`), stated as identifiers; no IMAP connection is
  opened. Presence is `declared`, with `cs history` named as the verb that
  proves readability — this row maps, it does not probe, because probing N
  mailboxes is `cs history`'s job and would make `cs memory` slow and
  credential-hungry.
- The `engine-memory` row resolves `engine_ws_url` + `/ws/<owner_uid>` and
  probes reachability with one TCP connect to the URL's host:port
  (timeout ~2s). No WebSocket handshake, no token, no RPC method. Four
  verdicts: `reachable` / `unreachable: <errno text>` / `unknown:
  engine_ws_url not configured` / `unknown: engine_ws_url not parseable` —
  the fourth for a configured value the URL parser cannot split into
  host:port (the manifest does not validate the field's shape, so this is
  reachable from operator input; a value that cannot be probed must not be
  reported with the not-configured verdict beside its own location). The row
  prints, beside the verdict, that reachable ≠ authorized and `cs whoami` is
  the authenticated proof.
- The `cc-memory` row resolves `~/.claude/projects/<encoded>/memory/` by
  encoding the clone root the way Claude Code does — both `/` and `.` map to
  `-` (verified against this machine's own `~/.claude/projects/` entries);
  `absent` is a normal answer. Authority line verbatim from the brief:
  nothing that leaves this desk.
- The `user-notes` row's location is the RPC surface (`settings.get
  USER_NOTES`), not a path; presence is not probed (that would need an
  authenticated session, which the verb refuses to open).
- Secrets discipline identical to `cs config`: no contents, no PII, output
  safe in a cron transcript.

**2. Registration**: `memory` subparser in `cs/cli.py` beside `config`
(`:1930`). Flags: `--json` only, mirroring `cs config --json`; neither
`--all` nor `--strict` crosses over (both are about setting layers, which
stores do not have). Help line answers "where does this operator's knowledge
live" in one sentence.

**3. Gate 4's verb list** (`tests/run.sh:269`) gains `memory`, so the help
tree covers it. `memory` has no sub-verbs; that one addition is the whole
job.

**Verification (M1)**: the assertions land in `tests/test_memory_report.py`
written in this suite's house style — a plain script with `main()` plus
assertions, like every other `tests/test_*.py` — and a new `step` line in
`tests/run.sh` invokes it from `$VENV` (the pattern of `test_login.py` at
`:634`). No pytest: nothing in this repo runs pytest, and a module nothing
invokes passes vacuously. The assertions: with no engine reachable the engine
row degrades honestly (`unknown`/`unreachable`, never a path); no store
contents in the output; all ten ids print. After wiring, `bash tests/run.sh`
green is the verification precisely because it now executes them.

**Integration review** before M2 begins.

## M2 — the stamped surfaces and the gate

**1. Charter § 10** in `cs/templates/project/CLAUDE.md.j2`, appended after
§ 9 (file currently ends at 226; nothing renumbered — `SKILL.md.j2:35` and
`docs/projects/README.md.j2:122` cite § 9 by number). Contents, and nothing
else: the membership rule (one sentence plus the four exclusions compressed
to one line each), the ten store slugs as a backticked list in registry
order, the pointer to `cs memory`, and the Claude Code boundary rule. Two
wording constraints carried from brief review: § 10 must not read as
contradicting § 9's "dossier files (secondary)" — one clause says the map
ranks authority per question while § 9 ranks the read order for facts; and
the boundary rule states where project knowledge goes instead (engine or
`docs/`), not only where it must not go.

**2. Permission surface**: `cs/templates/project/.claude/settings.json.j2`
gains the four canonical `cs memory` spellings in the allow list, adjacent to
the `cs config` block (`:9-12`). No deny entries: the verb is read-only and
the cron may run it.

**3. The set-agreement gate**, appended to `tests/run.sh` as gate 48 — 47 is
M1's test step, which took the next free slot. It
imports `cs.memory_report` from `$VENV` — the venv gate 3 (`:243`) builds
from the working tree, which every later gate already uses — and reads the
slug set straight off `STORES`; the backticked slug set comes from § 10 of
`CLAUDE.md.j2`. The gate fails on any symmetric difference, printing the
offending slugs. Importing beats grep-ing a multi-line Python tuple: the set
the gate checks is the set the verb actually ships. No count literal anywhere
in the gate. It also asserts the four allow spellings exist in
`settings.json.j2` — the same one-file-forgotten failure gate 17 exists to
catch, on the allow side.

**Verification (M2)**: `bash tests/run.sh` green including gate 48; mutate a
slug in either file and watch the gate fail (run locally, not committed);
render the template pair in the golden-pack path and confirm § 10 appears
once and `AGENTS.md`-side routing is untouched.

**Integration review** before M3 begins.

## M3 — release and clone upgrades

Per `docs/release-procedure.md`, in its order — release commit (pyproject
bump + CHANGELOG `v0.40.0` entry + active-context tag claims), tag
immediately, gates at the tag, sweep, push. **MINOR; re-collaudo tier FULL on
both clones** — the permission surface changed. The CHANGELOG entry names the
verb, § 10, the settings delta, both clones, and the FULL tier.

Named costs, decided now: `mario124-cs` is pinned at `v0.35.0`, so its FULL
run crosses four tags of drift — budgeted as part of this milestone, not
discovered during it. `mrcall-cs/CLAUDE.md` renders ~15-20 lines longer and
its thin-index gate (already failing at 247 > 221) keeps failing — that
clone's charter consolidation is separate work and this release does not
wait for it.

Then each clone: `cs update` (applies `settings.json` regardless, local saved
as `*.local-bak`), sweep, `cs whoami`, FULL collaudo, commit by explicit
path. After BOTH pass: move the CHANGELOG operational-pin marker.

**Verification (M3)**: on each clone post-upgrade, `cs memory` runs headless
under the stamped permission set without a prompt; the engine row is
`reachable` on the machine that hosts the engine; collaudo suite passes at
FULL on both. Every push and the tag wait for the operator's explicit ok.

## Risks

- **The TCP probe can mislead on a proxied host** (port open, engine dead
  behind it). Accepted: the verdict claims reachability of the endpoint, and
  the printed reachable-≠-authorized line plus `cs whoami` is the escalation
  path. No retry logic — one connect, one answer.
- **The CC-memory path encoding could drift from Claude Code's scheme.** The
  row's resolver is one small function with its own test; if the scheme
  changes upstream the row reports `absent`, which is a wrong-but-safe
  answer, and the fix is local.
- **Rollback**: M1/M2 are kernel-side and revert cleanly pre-tag. Post-tag, a
  defect is fixed forward in a PATCH per the procedure (a published tag never
  moves); clones can re-pin the previous tag with `cs update --pin v0.39.0`.

## Out of scope

The `mrcall-cs` quality audit (the brief's stated follow-on), the `mrcall-cs`
charter consolidation, and any write path — the verb writes nothing and no
write surface changes.
