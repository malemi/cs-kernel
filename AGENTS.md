<!-- mrcall-ai-kit:delivery:start -->
## Documentation lifecycle (harness v9)
This repository's managed protocol lives here in AGENTS.md; no CLAUDE.md read is
required. Use this v9 entry instead of any older kit instruction to load CLAUDE.md.
When repository `.agents/skills/` provides doc-start/doc-end/doc-critic, load those
copies; do not select same-named older global workflows.

The lead, before source reads, searches, diagnosis, edits, or delegation for ANY repository
request (including questions, fast-path fixes, briefs, and reviews), invoke
`doc-start`: load its current workflow and execute it. The lead personally reads
AGENTS.md, docs/README.md, docs/active-context.md, and relevant durable docs in full.
Reuse exact documents already present in context. Bounded installation/profile
checks may precede orientation; source exploration may not. Reload affected
orientation after repository/worktree/instruction changes or context loss, not
ordinary source edits. Never substitute a worker summary for these lead reads.
Workers use the lead's scoped handoff; reload only required context they lack.

Act as the senior engineer and project manager reporting to the human CTO.
Resolve routine reversible decisions from evidence; deliver verified outcomes.
Ask only for unresolved intent, authority, material risk, or irreversible/external
action. Match effort to risk; fix in-scope problems. Delegate bounded substantive
work only when its parallelism, expertise, or isolation exceeds coordination cost.

Classify the request and preserve its scope:
- Explanation/read-only diagnosis: orient, investigate, answer with uncertainty;
  no required edits, trace, consolidation, baseline advancement, or release.
- Brief-only/review-only: orient and deliver only the requested artifact/verdict;
  no automatic plan, implementation, migration, baseline advancement, or release.
- Fast path requires ALL: local, obvious, reversible; no public contract, behavior
  boundary, persistent data, security, dependency graph, or migration change;
  no decomposition/delegation; one focused real check proves it. Implement and
  check; state documentation impact. If none, justify it. If docs are affected,
  invoke `doc-end` for proportionate reconciliation and verification.
- Documentation-only: invoke `doc-end` before completion, including lead-owned
  reconciliation, mechanical gate, `doc-critic`, and living-context shape check.
- Substantial development: follow the ordered reviews below, then `doc-end`
  before final approval. Generic code review never substitutes for `doc-critic`.

Substantial work starts with docs/briefs/YYYY-MM-DD-<slug>.md (intent, scope,
constraints, acceptance, assumptions) and then docs/execution-plans/YYYY-MM-DD-<slug>.md
(status frontmatter, dependencies, ownership, verification, relevant rollback).
Order: brief → fresh reviewer APPROVED → plan → fresh reviewer APPROVED →
implementation → milestone integration review before dependent work → separate
final review through the final-user path. Review the brief's framing first.
Repair REVISE with the same reviewer; use a fresh reviewer for each new gate.
Verdicts: APPROVED, REVISE, FAST_PATH (prove every criterion), BLOCKED (unresolved
intent/risk/authority). Reviews are internal gates, not human approval prompts.
Relay each verdict and its evidence in your own words; never paste the report.
Without fresh-review capability, perform a separate pass and report the limitation.

Closure: the lead identifies affected docs, including unchanged docs and missing
coverage; reconciles current knowledge; preserves historical narrative verbatim
in docs/active-context-archive.md; runs the mechanical gate and explicitly invokes
`doc-critic` over affected docs plus active-context shape even when untouched.
Repair STALE, preserve UNVERIFIABLE, and recheck affected changes. Final review
must REVISE missing/stale required evidence. For applicable closure, use
`doc-check.py --completion check`, then `--completion finalize` for baseline.
Fast-path no-impact closure stays proportionate; release needs authorization.
Keep actual result references and pending obligations across delegation/resumption;
attestations and mechanical success alone do not prove semantic or runtime enforcement.
<!-- mrcall-ai-kit:delivery:end -->

# AGENTS.md — cs-kernel

**Stack**: Python 3.11 (import package `cs`)
**Entry point**: `cs.cli:main` (console script `cs`)
**Test**: `bash tests/run.sh`
**Do not break**: No company literal anywhere in `cs/` (wordlist-gated); everything company-shaped comes from `Settings`/`manifest.toml` — never `if company == …`

<!-- orientation ends -->
<!-- doc-scope:start -->
Scope: the thin routing and ownership index of this kernel. Mandatory anti-fork
rules live in `docs/kernel-charter.md`. Per-tag detail is `CHANGELOG.md`, volatile state
`docs/active-context.md`, the release steps `docs/release-procedure.md`.
<!-- doc-scope:end -->
Shared kernel of `<company>-cs` operators: distribution `cs-kernel`, import
package `cs`. Clones contain no `cs/` source: they pip-install a git tag from
`requirements.txt`. Upgrade by pin bump + install, never cherry-pick.
Design: meta-repo `docs/briefs/cs-kernel-manifest-separation.md`. Both maintained
clones are permanent equivalence fixtures (`kernel + manifest(X) ≡ X`, brief §6).

## AI execution boundaries

Clone cron launches Claude Code (`claude -p`); engine RPC generation and kernel
send-guard classifiers use separate API clients/models/auth. The engine daily
budget covers neither Claude reasoning nor direct classifiers. Clone `CS_PAUSE`
blocks new guarded ticks, not engine work or a running Claude. See
[operator runtime and controls](docs/operator-runtime.md) before model/cost/pause advice.

## Mandatory kernel charter

Before source investigation or changes, read the complete
[kernel charter](docs/kernel-charter.md). Its six rules govern every change:
company-neutral code, Settings-owned company data, the rule of two, fixed
invariants, adapter registries, and operator-facing surfaces.

## Layout — who owns what

Every module in `cs/` carries its own docstring saying what it is and why; read
those, not a tree duplicated here. `cs/crm/` and `cs/ingest/` are the two
adapter registries (rule 5), and each registry module IS the list of valid
adapter names.

**Three template roots**: `templates/project/` is stamped once per CLONE by
`cs init` / `cs update`, `templates/project_memory/` once per PROJECT by
`cs project new`, `templates/partials/` is `{% include %}`d at render time and
never stamped. Each needs its own `package-data` glob (see `pyproject.toml`).

**`.claude/skills/` is the ONE rendered workflow surface** — `.agents/skills` and `.opencode/skills` point
into it; `install_agent_surfaces` owns those links and the exact legacy cleanup. A clone's `AGENTS.md` is
the rendered charter (`templates/project/AGENTS.md.j2`), and its `CLAUDE.md` is a bootstrap the kernel
writes once — the `@AGENTS.md` import Claude Code follows — and never touches again
(`CLONE_AUTHORED_PREFIXES`), so a documentation harness that manages `CLAUDE.md` owns it without a drift
report. Never render the same workflow twice (incident: CHANGELOG `v0.10.0`; gate 27 holds it).

**Clone-owned, never kernel source**, shipped only as `.j2` under `cs/templates/project/`: `.claude/`,
`bin/cs_operator_cron.sh`, `company/*.md`, `manifest.toml`, `requirements.txt`. `company/**` is
create-if-missing, never overwritten, never prompted about (`CLONE_AUTHORED_PREFIXES`; the prompt-fatigue
failure it prevents is CHANGELOG `v0.16.0`). Never in this repo in ANY form: `campaigns/` pack content,
`docs/customers`, `ext/`.

## Versioning & release

**The executable procedure is [docs/release-procedure.md](docs/release-procedure.md)
— follow it, never reconstruct it from memory.** It owns the ordered release
and clone-upgrade steps, the version-claim inventory and the mandatory sweep.
Two rules stay here, because that file points back at this one for them.

Semver tags `v0.MINOR.PATCH`; clones pin **tags only**, never branches. The version describes the INTERFACE:
PATCH = behavior-identical fix; MINOR = new manifest field / adapter / new or changed CLI surface. A verb
that stops prompting, or a flag that did not exist, is a MINOR even when the diff is small — an operator
reading "patch" is entitled to expect nothing observable changed.

**The re-collaudo tier is a separate judgement, decided by what the release TOUCHES — never inferred from
the version digit.** FULL on both clones when it touches send paths, `campaign`, `gmail_archive`,
`send_mail`, the auth boundary or the permission surface (the same list invariant 4 escalates on), and FULL
means the collaudo suite runs on BOTH clones before the tag ships. Otherwise declared per entry — static
when the only observable surface is the help tree or stamped prose, `read` when a live engine call could
plausibly differ. Every tag gets a CHANGELOG entry naming what changed, **which clones must re-collaudo**,
at which tier, and — when the tier is below FULL for a MINOR — one line of why that is safe (brief §6.6).
Bending this rule silently rots it; bending it in writing does not. Never push without the operator's
explicit ok.

## Tests

`bash tests/run.sh` — each `step` line in the script names the gate it runs and what it proves, including
the env-driven golden-pack gate that keeps clone copy out of this repo. Semantic tests only, no mock
theatre.
