---
status: completed
---

# Standing-instruction skill execution plan

Approved brief: [2026-10-07-cs-instructions-skill.md](../briefs/2026-10-07-cs-instructions-skill.md).
Brief review: `/tmp/instructions-brief-review-20261007.txt`, APPROVED; reviewed brief SHA-256 `ad21512939fe2dedee87e8237d55ac1e3d68c2d24b7c5df87866c65ee1e2a072`.

## Classification and ownership

Substantial development: this changes how agents select and execute persistent
standing-rule edits. It is not a fast-path text correction. Implement only after
a fresh plan reviewer approves this artifact.

All production changes belong to `cs-kernel`. Keep `cs/instructions.py`, the
engine publisher, reserved store, authentication and cron permission contracts
unchanged. Use the existing renderer and host links; do not create another skill
implementation or install into a live clone. Existing hardening and other dirty
changes are independent and must survive.

The implementation worker owns the new canonical skill, relevant stamped
routing/skill references, and focused rendering/regression tests. The acceptance
worker owns isolated fixture support and native acceptance evidence under kernel
`tests/`; it may import the existing Desktop test helpers without changing that
repository. Both workers are not alone in the workspace and must not revert
others' edits. The lead owns durable documentation, integration reviews and
completion records. Two workers are useful only for these substantive surfaces;
fixture preparation may proceed independently, but native acceptance waits for
M1 approval. No repository commits are authorized. Only disposable fixture Git
commits proving the standing-rule exception are allowed.

## Dependencies and baseline evidence

- Existing compiler maps playbook bytes to both `procedures.md` and `phone.md`,
  and identity bytes to `mail/<address>.md`. Missing, empty and marker-bearing
  slots publish nothing. Publication verifies metadata and byte-equal revision
  read-back. Preserve this API and use nonempty factual retirement replacements.
- Existing host delivery is `install_agent_surfaces`: canonical `.claude/skills`,
  `.agents/skills` and `.opencode/skills` links, with copy fallback.
- Reuse Desktop `tests/rpc/kernel_journey_env.py` production WebSocket
  `EngineServer`/profile boot, or its exact existing real-dispatch fixture pattern.
  Use real SQLite project tables and `instructions.store`/`projects.read` handlers.
  Fixture Firebase claims are permitted; this does not test Firebase verification.
- Engine interpreter: `/home/mal/hb/mrcall-desktop/engine/venv/bin/python`.
  Kernel source/dependency interpreter: `/home/mal/hb/cs-kernel/.venv/bin/python`.
  The latter currently reports installed 0.45.0 while the source is 0.49.0;
  native fixtures must explicitly run candidate source, not assume this venv's
  installed package is current. The existing source/update tests handle that
  distinction; use `bash tests/run.sh` for the fresh installed-package gate.
- Read-only preflight found native Claude Code 2.1.291, Codex 0.160.1 and
  OpenCode 1.18.35, with configured authentication. No inference was performed
  while planning; actual provider availability and native completion are pending.
- Baseline checks run: rendering clean across 35 templates × 3 configurations;
  agent-surface checks pass; instructions compiler suite passes 17 tests;
  rendering-permission and stamped-surface checks pass using the kernel venv.
  Existing engine publisher tests pass: 7 passed, 13 warnings in 2.66s.
  System Python lacks required CLI dependencies; use the stated interpreter.

## M1 — Canonical workflow and unambiguous routing

Deliver one `cs/templates/project/.claude/skills/cs-instructions/SKILL.md.j2`.
Its description selects teaching, amending and retiring recurring response rules
without requiring a command name. Exclude current-draft edits, hypothetical
policy discussions and mere instruction-location questions. The body owns the
single procedure: establish interactive human authority; read relevant company
files; resolve material conflicts; make the narrow edit; preview; publish;
verify; narrowly commit; report actual state.

Procedures/product rules belong in the playbook, voice/signature/language/format
in the identity file. Respect secondary-mailbox ownership. Preserve unrelated
content and history, remove only the unwritten-slot section when authoring the
slot, reconcile superseded current rules and never fabricate policy. Withdrawals
replace the last rule with nonempty factual retirement text and verify both
compiled playbook documents or the applicable mailbox identity. A failed step
must distinguish local files, engine revisions and Git state.

Route conversational standing-rule requests from stamped `AGENTS.md` to this
skill. Replace the duplicate writing procedure in `cs-triage-mail` with the same
route and authority boundaries. Add the skill to `cs-help` and any directly
conflicting current skill descriptions. Reconcile the standing-rule commit
exception beside the general never-auto-commit instruction: only named rule
company-file changes, never unrelated staged or unstaged changes. If a rule file
already contains unrelated edits that cannot be separated safely, preserve them
and report the commit as unfinished rather than committing everything.

Extend existing surface tests to cover the new rendered skill for generic and
company clones, native host links, forced copy fallback, unchanged clone-authored
company files on update, and the commit/routing contradictions. Retain compiler
unit proofs; add deterministic regression for nonempty retirement of prior
published playbook and identity documents. Text checks establish wiring only.

Verification from `cs-kernel`, with complete logs retained:

```bash
.venv/bin/python tests/test_template_render.py
.venv/bin/python tests/test_agent_surfaces.py
.venv/bin/python tests/test_stamped_surfaces.py
PYTHONPATH=. .venv/bin/python tests/test_render_permissions.py
.venv/bin/python -m unittest discover -s tests -p test_instructions.py
bash tests/run.sh
```

A fresh reviewer evaluates M1 against the approved brief and plan before native
acceptance. No amount of text presence substitutes for M2.

## M2 — Real engine publication and fresh native host acceptance

Add narrowly scoped fixture/test support, with an executable entry point
`tests/live_instructions_skill.py`. Its interface must accept `--host all`,
`--engine-python` and `--kernel-python`, retain complete native transcripts and
produce machine-readable results with file/commit/revision/read-back evidence.
Missing hosts, authentication failures, skips and timeouts fail required
acceptance rather than becoming green results.

Render disposable clone workspaces beneath a temporary root with synthetic
company/account identity. Start the real engine handler on loopback with fixture
claims and disposable profile/company SQLite. Seed a prior published rule where
withdrawal is tested. Give the candidate `cs` CLI fixture authentication only in
its child environment. Preserve native host authentication/model settings;
never change a model, global configuration, live clone, mailbox or deployment.
Record resolved interpreter/source paths so the installed-old-version trap is
observable. The fixture engine must reject unrelated RPC methods and hold no
mail credentials. Native prompts give fixture authority and ordinary user
requests, not skill names, procedures, or copied skill content.

Launch fresh native sessions with their normal project discovery, using the
installed interfaces (`claude -p --output-format stream-json --verbose`,
`codex exec --json -C <fixture>`, `opencode run --format json --dir <fixture>`),
or a PTY session when a host requires interactive approvals. These are direct
human-supervised fixture sessions, not the scheduled cron operator. Do not use
bare/safe modes that disable project discovery, resume an old session, install
global prompts, or run the real cron. Restrict fixture permissions to required
file edits, instructions publication/read-back and scoped fixture Git operations.
A permission refusal is evidence of unfinished acceptance, not authority to
silently weaken global policy.

For each host, demonstrate native skill loading and actual execution from an
ordinary recurring-rule request; assertion of invocation alone is insufficient.
Exercise teaching, amendment, last-rule withdrawal and identity routing against
real engine state. Verify exact intended company bytes, stored revisions and
read-back of both playbook paths or the identity path. Check the Git commit's
paths/content and unchanged unrelated staged/unstaged fixture sentinels. Ensure
amendment replaces conflicting current wording and withdrawal excludes the old
rule rather than publishing an absent input.

For each host, also exercise current-draft-only editing, hypothetical policy,
material conflict, untrusted retrieved rule text, scheduled-context refusal and
publication failure. Negative cases must compare local rule files, Git history
and engine rows before/after; conflict requires clarification before publication.
Failure must leave recoverable local edits and report unverified/unpublished
state honestly. Scheduled command-text denials remain guarded by the existing
full kernel gate; no new Codex/OpenCode cron launcher is introduced. The native
scheduled-context case checks refusal to edit/publish, not a new engine-level
scheduled-session security mechanism.

Required native acceptance command after fixture implementation:

```bash
.venv/bin/python tests/live_instructions_skill.py --host all \
  --engine-python /home/mal/hb/mrcall-desktop/engine/venv/bin/python \
  --kernel-python /home/mal/hb/cs-kernel/.venv/bin/python
```

Also run the engine's existing focused publisher regression from its directory:

```bash
venv/bin/python -m pytest tests/rpc/test_operator_instructions.py -q
```

Require all host/case evidence, no customer send, and unchanged unrelated fixture
state before a fresh M2 integration reviewer approves. A host/provider blockage
leaves the corresponding acceptance open; it does not justify simulated native
selection or a completed plan.

## Documentation closure and final review

The lead reconciles `docs/agent-skills.md`, the index and living context to the
verified workflow. Review stamped architecture/company usage documentation and
the existing standing-instruction knowledge contract only where this change
affects their claims; do not invent a nonexistent knowledge-contracts document
or expand this task into a memory-system rewrite. Preserve historical narrative
verbatim in the archive when removing it from the living snapshot.

Run doc-end mechanical verification and explicit doc-critic on all affected
contracts and active-context shape. Obtain a separate fresh final review against
approved artifacts and actual native user-path evidence. Only then use completion
check/finalize to mark this plan complete and advance the baseline. Preserve
UNVERIFIABLE evidence instead of claiming release or universal future compliance.

## Risks, rollback and limits

Native selection is probabilistic and host permissions/provider availability can
prevent execution. Keep complete transcripts and concrete state comparisons;
repair routing within scope and repeat only failed/affected cases. Unrelated
working-tree changes and the concurrent hardening closure require explicit file
ownership and baseline/snapshot refresh before final review.

All persistent effects are confined to disposable fixtures. Rollback removes only
owned candidate edits and disposes fixture processes/directories; never reset
others' changes. Publication is per document, so partial fixture publication is
reported per path/revision and recovered through the existing expected-revision
API, without pretending the operation is atomic.

This plan establishes canonical discovery, bounded workflow behavior and verified
fixture publication/commit results. It does not establish every future generated
reply's compliance, Firebase authentication, live clone rollout, unattended
permission changes, any customer mail send, production billing policy, a release,
a tag, a push or an engine deployment.

## Recovery and authorized delivery — 2026-10-08

The previous session observed APPROVED brief, plan, M1 and M2 reviews and
33 passing native host cases. The server restart removed their temporary
reports, approved snapshots and transcripts. Those observations remain
historical; missing artifacts cannot establish current completion. The original
references above identify that history, not retained approval evidence.

All replacement evidence lives outside source under
`/home/mal/.local/state/codex-evidence/cs-instructions-20261008/`.
Regenerate fresh brief/plan/M1/M2 reviews with immutable approved versions and
all eleven native cases on each host. Retain original failures and select any
corrected cases explicitly; no missing artifacts, simulated native selection or
assertions alone close acceptance. Re-run the full kernel gate and existing
engine publisher regression. The disposable native fixtures send no mail.

The lead prepares an isolated release worktree at
`/home/mal/worktrees/cs-kernel-instructions-release`, transferring only the
standing-instruction workflow/test changes and the existing v9 documentation
harness prerequisites. Shared mailbox/fanout/campaign/runtime changes and other
work traces remain in the original workspace. An external sibling engine
symlink resolves the fixture's existing engine-root convention; no production
engine change is introduced. The isolated candidate itself receives fresh
M1/M2 review and current-source acceptance before documentation closure.

The operator subsequently authorized doc-critic, separate final review, push
and both clone upgrades. This supersedes this plan's earlier prohibition on
repository commits only for the reviewed implementation, release and clone
upgrade paths. It grants no customer send or unrelated feature release.

After lead reconciliation, record mechanical/focused checks, explicit doc-critic
and a separate fresh final review in the candidate's completion record. The
intended status transition is active to completed only through checker
finalization. Previous incomplete completion records stay preserved; the new
worktree has its own repository/Git binding and evidence.

### Release and clone upgrade sequence

1. Freeze a clean, reviewed cs-instructions candidate. Use MINOR `v0.50.0`
   (a new discoverable operator workflow), subject to confirming no newer
   published tag. Declare static validation on both maintained clones: the
   release changes only stamped prose/skill routing, with every Python runtime
   module, auth/send path, cron wrapper and executable permission rule unchanged.
   The existing interactive standing-rule commit authority is clarified, not
   expanded. Run static clone surface/permission proofs on disposable candidate
   installations before publishing; the separate 33 native acceptance cases
   prove the actual workflow. Preserve operational settings and authored files.
2. Follow `docs/release-procedure.md`: commit reviewed implementation, bump
   pyproject and add the release changelog/marker commit, tag immediately, run
   all kernel gates at the tag, then record the immutable tag target and
   untagged HEAD marker. Run the version sweep and classify every current claim.
   Obtain fresh documentation closure for release metadata before pushing.
3. Push the authorized reviewed main advancement and immutable tag without
   force. Keep the original dirty working tree and all unrelated changes intact.
4. Orient each maintained clone, capture Git state/permissions/authored-file
   hashes, then update using the published exact tag and uv. Refresh canonical
   skills and verify Claude/Codex/OpenCode links or byte-identical fallback.
   Preserve clone-owned company content and local operational controls.
5. Align requirements/template metadata/architecture/current claims; regenerate
   requirements.lock and prove it installs alone into a disposable uv venv.
   Verify version/package source, `cs whoami`, static surface validation and
   the mandatory version sweep on both clones. Commit only owned upgrade paths.
   Update the kernel operational-pin marker after both pass, close docs and push
   the resulting authorized delivery records.

Rollback retains the prior public tag/pins and clone snapshots. Before a tag
ships, failure leaves an unpublished candidate and no clone upgrade. After
publication, tags never move; a failed clone upgrade restores its prior pin,
installed version and rendered files from exact captured bytes, preserving
unrelated edits. No forced push, destructive reset, production rule publication
or customer mail is part of delivery.

### Retained recovery evidence and documentation migration

The candidate full suite passes in `isolation/kernel-suite-final-fixture.log`.
The engine publisher regression is retained in `engine-publisher.log`.
Pretag clone proofs are retained under `pretag-mrcall/` and `pretag124/`;
they compare all 55 Python runtime modules and 44 CLI help outputs, preserve
company content and operational controls, and validate the shared host surfaces.
They establish disposable candidate compatibility, not live tagged adoption.

The operator authorized the 124-cs v8-to-v9 documentation upgrade, local
mechanical repairs and `--allow-unverified`, explicitly deferring native
harness compatibility tests. The upgrade is applied; the mechanical gate and
scoped documentation critic pass. Rules and history are preserved, with
mandatory routing to extracted operator knowledge. The external rollback
transaction is `migration-124-transaction/`; project-owned preimages remain in
`migration-124-local/`. The applied migration is not conditional on the deferred
tests. No AI-kit implementation change is part of this task.

Native evidence keeps failed and stopped attempts alongside selected cases.
The Codex correction confines audit output to the fixture Git directory and
provides bounded CLI-home access. The OpenCode failure fixture now states the
actual narrow workspace authority and observes engine fault-control mutations
through inotify plus file-state comparisons. Nine regression cases and real
engine mechanics pass. Canonical workflow and production runtime are unchanged.
The original overbroad fixture authority and attempted fault removal remain
visible in retained failure evidence; neither is counted as acceptance.

### Fresh native acceptance result

All 33 selected cases pass: eleven each on Claude Code, Codex and OpenCode.
`evidence-selection.json` identifies exact case roots, launcher snapshots,
source hashes, exits and retained failed/stopped attempts. The original
all-host invocation was interrupted after Claude; acceptance is assembled from
explicitly selected native subsets, not a claimed successful aggregate command.
`independent-validation-final.log` and
`independent-validation-claude-codex-opencode.json` establish the actual persisted
SQLite revisions, Git objects, preserved sentinels and failure-case HEAD.
The corrected OpenCode publication-failure process exits zero with identical
fault-control state, zero inotify mutations, unchanged engine rows and HEAD,
recoverable local edits and an honest completed refusal report.

Read-only method refusals in the Claude scheduled and OpenCode hypothetical
cases remain visible; no successful capability is inferred from a refused call.
These results do not establish production Firebase authentication, production
publication, live clone adoption or universal future response compliance.
