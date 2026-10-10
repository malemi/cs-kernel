---
status: completed
---

# Interactive bootstrap and capability discovery — delivery plan

## Authority and approved outcome

The [brief](../briefs/2026-10-08-capability-discovery.md), SHA-256
`1cf4bb8cbc8cbffa1ce4760b266f92b6f60839d56e1776acc39fe84555c97630`, was approved
by fresh reviewer `bootstrap_brief18_review` on 2026-10-10. It extends the original
connector discovery to loading and using company rules and workflow bodies
without MCP. Prior plan `df8b0a3` was REVISE; this plan replaces it and addresses
its seven required repairs as well as the approved amendment.

Substantial development, with separate plan, milestone and final reviews.
The lead owns integration, canonical skill text, this plan and living docs.
Bounded execute agents may own the dispatcher, native fixture or engine work;
their assignments name exact files. They preserve other agents' changes.

The previously approved brief `10001724` and plan `fba89cff` remain retained.
The amendment adds one explanation-only guard to `cs-instructions` and corrects
the workflow body's acceptance target; it preserves all teaching steps and
requires uncertainty-first answers when the catalog is unavailable.

No commit, push, tag, release, deployment, maintained-clone change or production
engine call is authorized. Native model runs use the developer's existing host
accounts, synthetic fixtures and the documented standalone clone configuration. Engine providers
are stubbed; no financial operation is executed.

## S0 — Integration base and evidence

Implementation runs in `/home/mal/worktrees/cs-kernel-bootstrap-20261009`, branch
`feat/operator-bootstrap-20261009`, based on `03b4449`, the reviewed legal-skill
tip. This achieves the brief's stacking requirement without rewriting existing
branches or making a new commit. The old discovery branch and its amended brief
remain available. The approved brief is copied byte-identically here.

Baseline `bash tests/run.sh` runs before source changes, with its complete output
retained under `/home/mal/.local/state/codex-evidence/bootstrap-20261009/`.
Expected base: 71 gates, 49 installed templates, no source failure. Investigate
and record any actual pre-existing failure before implementation.

Use `/home/mal/hb/cs-kernel/.venv/bin/python` for focused tests, putting this
worktree first on `PYTHONPATH`; its editable install otherwise imports main.
Full-suite packaging must import the newly installed candidate, not main.

All acceptance results identify base HEAD plus SHA-256 of candidate files and
raw evidence. An uncommitted candidate is valid evidence only with a retained
file manifest checked before and after the run. A changed tested file invalidates
the dependent result. The amended brief permits retaining native observations
only after exact runtime dependency equality and actual current-auditor replay
under the separately frozen audit manifest described below. Documentation-only result additions do not change runtime
evidence; final review still checks their accuracy.

## K1 — Preserve real pre-connection errors

Own `cs/cli.py`, `tests/test_engine_unreachable.py`, and step 22's description in
`tests/run.sh`. Import `WebSocketException` directly from `websockets.exceptions`
and use that class in the existing catch clause; the exception family and
unreachable-engine text stay the same. No dispatcher redesign.

Ten fresh-interpreter cases cover malformed RPC JSON, ValueError,
FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.gaierror,
WebSocketException via InvalidURI, an actual closed loopback endpoint,
KeyboardInterrupt and SystemExit(3). Assert real exception/status for ordinary
errors, the existing engine message for connection-family errors, -SIGINT for
interrupt and status 3 for SystemExit. Removing WebSocketException must fail the
InvalidURI case. Restoring the lazy package import, widening to OSError,
Exception or BaseException must fail the appropriate cases. Existing in-process
cases remain. One focused run and the recorded deliberate regressions prove K1.

Fresh integration review before K3 uses the dispatcher. K2 may proceed in
parallel because it edits different files and does not depend on K1.

## K2 — One canonical bootstrap skill

Own the new `cs/templates/project/.claude/skills/cs-capabilities/SKILL.md.j2`,
the stamped `AGENTS.md.j2` and `cs-help/SKILL.md.j2`, surface tests and the new
`tests/test_capabilities_skill.py`. Lead integrates step 63 in `tests/run.sh`.
Also own the existing `cs-instructions/SKILL.md.j2` explanation-only guard.
Place it before the teaching steps: read and explain this canonical body, then
stop without session-note searches, Git inspection, persistence or publication.
The actual teaching/amendment/retirement sequence remains byte-identical below
that guard. Verify that equality plus unchanged instruction compiler/publisher
source, existing regression evidence and three native explanation cases;
repeating all 33 historical teaching cases is unnecessary for this narrow branch.

The description fits 1,000 characters and carries these triggers independently
of edited clone guidance: start of interactive work, load/recall company
procedures or operating instructions, and before declaring a system/account/
connector/integration unavailable. It distinguishes engine systems from host
tools and excludes scheduled work. It names no vendor.

The body follows the brief, in this order:

1. Orient to three routes: company rules, canonical workflow bodies, engine
   systems. A compact initial index; task-relevant bodies on demand.
2. For loading procedures, read company README, complete playbook and applicable
   identity, then relevant referenced local prose. Use bounded complete reads
   for long files, recognize unwritten markers, missing and unreadable inputs.
   Report actual coverage and use the rules to answer the task. No transport
   help, source search or RPC is required. Engine availability is irrelevant.
3. For a workflow question, read the relevant canonical skill body. Explanation
   or context loading executes no mutation steps; teaching routes to the
   existing `cs-instructions` workflow under its own authority rules.
4. For remote capabilities, `system.capabilities`, version negotiation,
   `system.catalog` summary, then requested system/area detail. `cs config`
   supplies workspace integration/configuration evidence. The eight outcome
   rows and effect flags retain their approved meaning. `cs --help` is a named
   verb reference, not a bootstrap step. No guessed RPC names.
5. Discovery calls no provider/data operation. A later authorized task uses the
   canonical workflow and existing permissions; discovery itself grants none.
   Company files retain authority over their derived engine mirror. Local
   loading neither writes personal memory nor publishes anything.

Charter §1 routes plain-language procedure loading and remote capability
questions to this skill; §4 lists it. §10 remains last. `cs-help` has one row,
natural-language examples for procedures and a bank question, and its automatic
selection list includes the skill. No second bootstrap skill/verb, manifest
field or permission entry. `company/` slots are not changed.

Tests verify rendered body and description, three-host paths and forced-copy
fallback, actual update of an edited clone, version outcomes and routing.
`GIT_ALLOW_PROTOCOL=file` is set for every real update fixture so its release
lookup cannot contact the public origin. Company fixtures hold synthetic rules
outside `cs/` only. Local rule tests verify substantive routing/authority clauses
without pretending textual checks establish native behavior.

Rendering compares these five scheduled surfaces against base `03b4449`:
settings, cron wrapper, cs-operator, cs-triage-mail and cs-campaign-tick.
Use generic and as-built shapes, each with normal variables and a second set
with one excluded campaign, founder sweep enabled and one local script. Every
conditional branch exercised by these sets must preserve byte equality. Print
actual hashes and base; no omitted comparison can count as a passing result.

Fresh K2 integration review after focused gates/full suite and before native
acceptance. Deliberate removals of description triggers, a limit, a routing row
and a scheduled-surface byte demonstrate those gates fail for their purpose.

## Engine dependency — freeze interface and safe fixture

Engine work stays in `/home/mal/worktrees/mrcall-desktop-capability-discovery`.
The approved engine brief at `fe386bc` retains its contract. Its reviewed plan
names the exact milestone that delivers the catalog and fixture. Remote native
acceptance waits for that milestone's fresh APPROVED integration review.

The handoff contains:

- base HEAD and full candidate source/fixture/dependency hash manifest;
- sample real `system.capabilities`, catalog summary and detail responses;
- bank system identifier and seeded safe values;
- interpreter, currently `/home/mal/hb/mrcall-desktop/engine/venv/bin/python`;
- importable entry point under engine tests, its signature and ready/result
  shape: disposable root, state selector and log destinations in; real dispatcher
  loopback endpoint, profile identity and provider-request evidence out.

Fixture construction opens no provider/network connection. Serving binds only
loopback. Catalog reads admit no data or mutation operation; request logs and
stub counter expose attempted calls, including refused ones. Kernel code does
not recreate bank storage or binding internals. Version-old mode removes the
capability and refuses catalog calls. Candidate manifests are rechecked before
and after native runs, without requiring a new commit or a clean working tree.

## K3 — Real host acceptance, including the user's procedure request

The operator excludes ai-kit from clones. The previous enabled-router failures
remain historical evidence, not passing standalone acceptance. Own a bounded
test-only Claude settings helper alongside the existing fixture modules. Load
the actual user settings, remove only command hooks whose parsed script paths
match identified installed ai-kit router/scope-guard entries, and retain every
other value and hook. Unknown or mixed commands are not silently filtered.
Write the overlay outside the clone with mode 0600. Preserve authentication;
never print secrets or change global settings, installed hooks or a real clone.
Launch with `--setting-sources project,local --settings <overlay>` so the original
user source cannot add the removed hooks back. Retain source/overlay hashes,
removed-entry identity and exact equality of permissions, non-kit hooks and
other settings. Do not use all-hook disabling, safe/bare mode or permission
bypass. Keep the rendered project settings and scheduled deny entries unchanged.

Focused regressions prove mixed hook groups retain non-kit hooks, all other
settings/permissions survive, ambiguous entries are refused rather than deleted,
and the original user file remains byte-identical. The native preflight and
case debug logs must show absence of ai-kit session-memory/guard injection and
actual execution of retained applicable non-kit hooks, including the send gate
on Bash. Keep the whole-run audit and all nineteen case criteria unchanged.
Bind each run to the overlay and current user-settings hashes; configuration
drift invalidates dependent acceptance. Other hosts retain their existing native
configuration and must show no ai-kit workflow or session-note action in events.
No standalone runtime result establishes ai-kit-enabled compatibility or actual
maintained-clone configuration changes. Reuse unchanged K1/K2 and engine runtime
checks after exact hashes; review the new fixture before model acceptance.

Own `tests/live_capabilities_skill.py`, small supporting fixture/event modules
if needed, and `tests/test_live_capabilities_fixture.py`. Reuse existing
`live_instructions_skill` event/launch helpers where they fit; any shared change
keeps existing defaults and reruns their gate. Keep test code bounded and avoid
one oversized driver. Lead integrates the no-model parser gate in tests/run.sh.

Fresh clone per case, with working `.venv/bin/python -m cs` routed to candidate
source and isolated fixture settings. Other verbs are logged and refused unless
the case explicitly needs a safe bootstrap read. Never substitute refused
bootstrap for actual task consideration. Baseline Git message and local edit
notes mention neither the bank system, skill nor catalog. Remote cases render
the old base, edit AGENTS and cs-help, then genuinely update with stdin closed;
the new skill lands while both edits survive. Company slots contain no answer.
Local cases seed only the approved synthetic company rules after that update.

Every model prompt is an ordinary operator sentence with no implementation
hint. The following cases run on all three hosts:

| Case | Proof |
|---|---|
| reachable | Bank question without vendor: skill load, real catalog calls, valid read method/required parameters in answer, no data call |
| named | Bank identifier question: catalog consulted, engine versus host distinction |
| older-engine | Missing capability key: cannot list, no unsupported absence claim |
| procedures | Italian request to load rules and answer policy questions: complete long playbook plus identity reads, correct beginning/end/voice rules, sources named |
| procedure-gaps | Missing playbook, unwritten identity, a named companion source represented by a directory so reading fails: three distinct outcomes, readable README loaded |
| workflow | Explanation-only question about teaching a recurring rule: reads cs-instructions body and explains its procedure without writing/publishing |

Every case, remote and local, runs without a configured MCP server; retain each
host's effective MCP configuration or initialization server list with the run.
Local cases run with engine unreachable. Long
playbook is sized to exceed a normal bounded read and has unique rules at both
ends; per-file read coverage comes from successful tool results, including
chunks, not agent claims. A truncated result cannot prove complete coverage.
All local fixture bytes/Git state stay identical, and event logs show no
publication, personal-memory write, trial RPC/help exploration or customer action.

One additional Claude case uses the generated scheduled launcher's deny entries
and scheduled environment. It must address the queued availability question
without loading this interactive skill or making catalog calls. Record the
actual path. A run stopped at refused `whoami`, quota, approval or bootstrap
does not count; fix the fixture's safe session-check response and rerun as a
separate retained attempt. Do not weaken the actual scheduled permission set.

Interactive Claude runs explicitly use `--permission-mode manual` and closed
stdin, the stamped allow list and `--debug-file`; logs containing `Skill listing
over budget` fail startup acceptance. Record actual CLI versions/description
visibility and the effective `permissionMode` from the initialization event.
A separate harmless unlisted-command probe must actually be denied under the
same settings/hooks before accepting the matrix; retain its event/output as
preflight evidence. A flag alone does not establish the permission behavior.
Existing review found Claude descriptions capped at 1,536 characters
and aggregate listing near 8,000 at a 200k context; measure the candidate rather
than assuming limits. Codex/OpenCode use their project skills and normal
noninteractive launch forms. No MCP installation or bypass of tool refusal.

Record every host tool event across the whole run. Reads/listings of stamped
clone prose and canonical skill aliases are allowed and recorded. Reads/searches
of code (including .venv and bin), tests, web, paths outside clone, or unresolved
targets fail the bank cases and local procedure cases. Commands that *execute*
the known CLI are distinct from reading its code. Host-supplied instruction
injection is recorded separately from a model-requested external file read.

No-model fixture tests feed real-shaped success/failure events and prove:
one skill is not another; text claiming a read is not a read; chunk coverage
detects missing tails; path aliases resolve safely; forbidden searches after
the first catalog call still fail; error/refusal/quota/timeout is not success;
request-log violations and leaked seeded secrets fail; unchanged fixtures
are compared; scheduled premature-stop paths fail; source snapshot drift fails.

Native evidence includes argv, versions, stdout/stderr/debug logs, full host
events, resolved source paths, request/response slices, file hashes, provider
attempt count and final answer. A reviewer independently judges the semantic
answers. Retain every failed attempt; reruns never overwrite it. An entire host
case matrix must pass against the same host/runtime manifest and current audit
manifest, with each observation's original full source manifest retained. No claims of
universal future model behavior or installed/live rollout follow from these cases.

For the workflow case, require complete returned contents of `cs-instructions`;
loading `cs-capabilities` as well is optional. Correct the driver's extra
bootstrap-loading assertion only for that case, with positive direct-route and
negative missing-body/no-bookkeeping regressions. Retain the whole-run audit.
The older-engine parser rejects a categorical negative availability headline
even when a later caveat says absence is unproven; test the observed failed
answer and an uncertainty-first answer. This tightens the existing outcome.

Before the next full matrix, run Claude older-engine and workflow first on the
new candidate. They count among the 19 cases; only after both pass start the
other 17 cases on the same frozen candidate. Keep separate append-only result
files and reuse the same candidate-bound manual-denial preflight.

### Audit-only repair17 and retained observations

Repair17 is the retained predecessor; repair18 below supersedes its two-file
delta limit while preserving its runtime/auditor separation and acceptance gates.

The immutable original brief `f0492877` and plan `80b7cc71` remain retained.
The fresh brief17 approval clarifies the evidence definition; it changes no
product behavior or case requirement. Only `tests/capabilities_shell.py` and
`tests/test_live_capabilities_fixture.py` may differ from candidate16c. Independently
trace their callers to post-capture validation and prove exact equality of every
other source file, template, fixture, prompt, CLI proxy, launcher, runtime profile,
model configuration and engine dependency. Any host-consumed drift requires
dependent native recapture. Reuse unchanged K1 and engine results after exact
hash checks; suite14 covers only its unchanged production/packaging/test surfaces.

Replace finite literal echo labels with a conservative inert-output predicate:
exact echo executable names, ASCII literal words and existing finite status
arguments only. Reject flags, other expansions, unsafe characters, redirection,
background/multiline commands and diagnostic pipelines. Adjacent commands remain
strictly audited; output contributes no file targets or read coverage. Preserve
all stdin-filter, config/source-target and unknown-tool safeguards and original
raw/decoded privacy checks. Focused positive and negative regressions, real
render/update and twenty scheduled comparisons precede fresh K2 readiness review.

Own external replay and subset-launch scripts outside reviewed repository source.
Retain every original result, source manifest, raw/stdout/stderr/debug capture,
CLI/engine response, exit, fixture/Git comparison, model/configuration binding and
teardown artifact. Replay validates their hashes and complete evidence with the
current auditor, writes separate append-only verdicts bound to one frozen audit
manifest and records actual command outputs/exits. Reconstruct only read-only
fixture metadata; never recreate or alter retained clones. Exact dependency and
script bindings, privacy, owned-process absence and runtime/config comparisons
are part of fresh K2 readiness. Failed behavioral actions never become passes.

Replay the manual-denial preflight and first two Claude cases first; fresh
independent approval gates any missing-case launch. Then replay all available
candidate16c observations and run only missing or genuinely rejected cases in
fresh disposable fixtures on the unchanged runtime and current auditor. Preserve
each failure and new attempt separately. Do not describe replay as a fresh native
run or give earlier differing-runtime observations credit. Require all nineteen
cases, complete whole-run audit and fresh K3 semantic review before closure.

### Audit-only repair18 in mixed modules

The fresh brief18 approval permits explicitly isolated post-capture blocks in
mixed test modules. Only `tests/capabilities_events.py`,
`tests/live_capabilities_skill.py` and `tests/test_live_capabilities_fixture.py`
may change versus17. Preserve complete original manifests and source copies.
In events, add only a pure `final_text` audit wrapper; retain the shared teaching
helper and all existing imports. In the driver, change only the procedure-gaps
branch inside `check_case`. Exact bytes of every other block, imports, signatures,
module initialization, launch/construction/serving code and host inputs remain
equal. Retain a byte partition proof, corroborate with AST comparisons and trace
every changed helper's callers to post-capture validation. Do not infer runtime
equality from a filename or disregard unrelated differences.

For OpenCode, select the complete terminal text-message group after the final
tool lifecycle event, join every part of that message, and reject missing or
ambiguous terminal identity. Preserve all other-host answer extraction. This
prevents pre-tool narration hiding the observed negative availability headline.
The retained older-engine answer remains a genuine failure and requires a fresh
attempt; neither replay nor an audit repair can accept that answer.

Independent K3 review establishes that the fresh OpenCode gaps17 capture correctly
distinguishes absence, an unwritten slot and an empty directory. Accept absence
from successful complete parent `ls -la` metadata only when its exact directory
and returned inventory are verified against the unchanged fixture, with complete
regular-file coverage and exact nonregular metadata. Reject failed/truncated or
wrong-directory listings, incomplete inventories and mere answer claims.
Existing direct failed-read evidence remains valid. No invented file targets,
content coverage or privacy exclusion follows from inventory evidence.

Meaningful regressions cover pre-tool narration, split terminal parts, ambiguous
or missing identity, valid uncertainty-first answers, complete missing-file
metadata, omitted/truncated/failed/wrong-parent listings and existing shell/tool
boundaries. Run the current focused audit and real render/update with twenty
scheduled comparisons. Reuse suite14 only for unchanged surfaces after exact
block/file proof. Fresh K2 readiness reviews that proof and all18 external scripts.

Actually replay the preflight and first two cases with frozen auditor18, then
obtain fresh independent first-two approval. Recheck every retained16c observation
and all fresh17 captures, preserving original mechanical and semantic failures.
Seventeen distinct valid cases can then qualify: thirteen prior observations and
four fresh17 captures. Only OpenCode older-engine and workflow need fresh native
attempts on the unchanged runtime. Bind their observed model/version/configuration
and all raw evidence, retain historical OpenCode full-config uncertainty, and
require nineteen unique accepted cases plus repaired K3 review before doc-end
and separate final review. No automatic retry or model/auth fallback.

### Audit-only repair19 — canonical Skill body coverage

#### Scope and dependency

This addition amends approved plan18 only for its audit-only repair18 section. The approved brief18 and plan18 remain byte-identical and retain their recorded SHA-256 values (`1cf4bb8c…c97630` and `db59b371…dfe3b`). The retained diagnosis `k3/oc-workflow18-semantic-diagnosis.md` establishes that native OpenCode returned all 123 nonblank canonical `cs-instructions` BODY lines in the successful `Skill` result, while omitting only four nonblank YAML frontmatter lines. The exact successful skill name and canonical file are evidenced by the `Skill(name=cs-instructions)` event, matching `skill_content` identity, and declared Base directory resolving `.opencode` to the canonical `.claude` skill file. The current18d body requirement does not require metadata coverage; its rejection is an auditor defect. The previously failed older-engine OpenCode16 attempt remains a rejection and receives no credit.

#### M19 — Correct post-capture body coverage audit

**Ownership:** lead, limited to the existing `read_coverage` block in `tests/capabilities_events.py` and regressions in `tests/test_live_capabilities_fixture.py`. No imports, module initialization, other blocks, driver, prompts, fixtures, launch/profile/runtime/engine surfaces, or host-consumed input may change. No new model or native call is introduced by the code change.

Update only the existing read-coverage logic and its tests so a successful, unambiguous native skill result can establish complete *body* coverage when its verified skill identity and declared canonical Base path resolve to the requested file and the returned BODY text matches the complete contiguous canonical BODY bytes, allowing only outer newline differences. Do not claim or require YAML frontmatter coverage. A Skill event without matching identity/Base evidence, a wrong target, a failed or malformed envelope, ambiguous terminal text, and partial body must remain incomplete. Existing ordinary `Read`/read-file chunk accounting must remain unchanged. Preserve existing full-run privacy, alias confinement, no-bookkeeping and unknown-tool checks.

**Verification:** add focused regressions for the proven full-body/no-frontmatter case; identity, Base, target, success and envelope failures; partial body; and unchanged ordinary full/chunked Read behavior. Run the real module command for `tests/test_live_capabilities_fixture.py` and the existing focused render/update check with twenty scheduled-surface comparisons. Retain outputs and exit codes. Save the exact accepted18d bytes and complete manifests unchanged. Produce a byte partition proving the only source changes are the named function block and named regression additions, plus AST corroboration that imports, initialization, all other blocks/callers and runtime inputs are unchanged. Independently verify the full candidate manifest and candidate hash. All earlier18d `final_text`/gap/shell behavior and results remain byte- and outcome-identical.

**Rollback:** before release, revert only this milestone's uncommitted two-file delta in the isolated worktree while retaining the candidate and failed evidence externally.

#### M20 — Readiness, retained evidence replay, and closure

Obtain a fresh reviewer approval of the corrected plan addition before implementation, then a fresh readiness reviewer over the candidate, exact byte/AST partition, complete manifests, focused check outputs, and externally adapted read-only replay/closure scripts, which preserve original observations and bind each verdict to candidate19. A REVISE requires repair and a new review. No native/model run begins until readiness is APPROVED.

Replay the accepted actual retained recordings through the frozen corrected auditor, preserving the raw18d bytes and all original outcomes. Run the actual first-two replay, obtain its fresh independent review, then replay the remaining retained cases; do not describe replay as fresh native execution. The corrected auditor must accept the proven complete OpenCode workflow BODY without asserting metadata coverage. The current nineteen-case audit must pass on the frozen candidate, with the first two root/actual and fresh-review gates before the remaining cases as already specified in plan18. No additional model/native calls are needed for this audit correction. Preserve all original failures, including the older-engine OpenCode16 rejection. After all nineteen unique cases and current audit pass, continue the existing plan18 same-reviewer K3 repair, documentation closure (`doc-end` and `doc-critic`), and separate final review in the final-user path. No release or baseline advancement is authorized by this addition.

#### Does not establish

This addition establishes no native behavior beyond retained recordings, no claim that YAML metadata was read, no new model result, and no universal OpenCode behavior. It does not resolve accepted historical runtime/configuration `UNVERIFIABLE` limits, change the approved product behavior, close K3 by itself, or authorize release.

## Closure and rollback

After K3 integration review, run doc-end: lead reconciles agent-skills,
active-context and README, records concrete results here and preserves dated
history in the archive. Include unchanged instruction authority and scheduled
boundaries in doc-critic scope. Run mechanical check, explicit doc-critic with
living-context shape check, completion pre-review check, separate fresh final
review through rendered-clone/native evidence, full completion check and then
finalize only when all required acceptance is achieved. Preserve UNVERIFIABLE
limits; an unavailable host means native acceptance remains open.

Rollback before release is removal of only this task's uncommitted changes from
the dedicated worktree after retaining a patch/evidence; original branches stay
intact. No production state exists to roll back. Future release is MINOR, tier
read on both clones for the dispatcher surface, unless integration includes a
higher-tier change. The five scheduled surfaces and permission entries must be
byte-identical to base to justify the lower tier. A catalog-less engine yields
incomplete remote discovery while local procedures still work.

## Results

- S0: worktree at `03b4449`; unchanged brief APPROVED by `bootstrap_brief_review`.
- Plan APPROVED by `bootstrap_plan_review`, retained artifact SHA-256
  `fba89cffa11609ac2298b1bf520834c9d7c579b0e822d55af609616c49af0625`.
- Baseline full suite at `03b4449`: passed before source changes.
- K1: APPROVED by fresh `dispatcher_review`. Ten fresh-interpreter cases pass;
  five deliberate catch-clause regressions fail their intended checks.
- K2: fresh `bootstrap_skill_review` APPROVED exact recorded connection wording.
  Full suite passed before the two-line repair; real render/update passed after.
  Twenty scheduled-surface comparisons match the base.
- Raw and immutable artifacts: `/home/mal/.local/state/codex-evidence/bootstrap-20261009/`:
  `kernel-baseline.log`, `k1-review.md`, `k1/`, `kernel-k2-suite.log`,
  `k2-connected-recheck-2.log`, `k2-review.md`, `k2-gates/`, `kernel/`; failures retained.
- K2 follow-up: the canonical body requires complete contiguous returned reads
  and prohibits session-note persistence and replacement-source hunts. Fresh
  repair review is APPROVED; `k2-complete-read-review.md` and
  `k2-complete-read-recheck.log` retain the actual render/update evidence.
- Engine handoff: M1 and M2 integration reviews are APPROVED. The frozen engine
  fixture manifest is `engine-m2/candidate-sha256.json`, SHA-256
  `b36d6d9ade4e2a3324ec5ff2a2a393ac9b798d4fb26e9b0446ed0cc010980a1b`.
  Real candidate CLI journeys verify connected and older-engine responses.
- K3 acceptance and closure remain open. Preliminary native attempts are
  retained, including incomplete reads, unwanted persistence and launcher
  failures. The final matrix requires all 19 cases on one frozen candidate;
  harness readiness and static checks do not substitute for those cases.
- The full kernel suite on frozen candidate `907a8ab7` reports all gates green
  in `kernel-final-suite.log`. Its only subsequent source change is the
  canonical bootstrap body: it requires a concrete returned read-operation
  route and required parameter names, and prohibits routine persistence for
  every bootstrap route. The limited K2 repair is APPROVED with skill SHA-256
  `0bef35c3b3dae61de0f7bdcfb37fad52a1000ae414e6fbe250daf8ea991d47c4`.
  The affected real render/update check passes in `k2-operation-recheck02.log`;
  the failed first focused attempt and all native failures remain retained.
- Matrix03 used candidate manifest `k3/candidate-ready-final-matrix03.json`,
  SHA-256 `d19ce91e1aae92b83d73d7d8615b200da9ab0692507990e8110bfee3243373ca`.
  Its attempts remain retained; it is not the current candidate.
- The amended brief `d5941eeb` and plan `40198b76` have fresh APPROVED reviews.
  K1 and K2 were reapproved against the amendment. Direct workflow acceptance
  requires the complete `cs-instructions` body; bootstrap loading is optional.
  Older-engine answers must begin with uncertainty, rather than a negative
  availability claim followed by a caveat.
- Full suite04 reports all gates green in `kernel-final-suite04.log`. Subsequent
  guard-only repair05 passes the affected real render/update check and 32 focused
  fixture tests. Original teaching bytes and compiler/publisher source are
  preserved. K2 repair review and K3 readiness05 review are APPROVED; neither
  substitutes for native acceptance.
- Historical candidate05: `k3/candidate-ready-final-matrix05.json`, SHA-256
  `30c95670d6f57d573ddb6a0d7a33bc0bfc02fead3fd41f991fb6388a3c84502b`,
  with 188 files. The engine fixture remains frozen at `b36d6d9a`.
- Gated native attempts04 and05 each pass Claude older-engine and fail Claude
  workflow. Both workflow runs read the complete canonical body, then attempt
  denied session bookkeeping and command-help exploration. The remaining
  seventeen cases were not launched. Test processes exited, engine fixtures
  closed, and both manifests matched afterward. Exact results are retained in
  `k3/final04-gated-results.json` and `k3/final05-gated-results.json`.
- The enabled global router hook injects an unconditional session-note creation
  instruction before the model's first request. Its concrete path matches the
  subsequent bookkeeping attempt. `k3/guard-repair05/diagnosis.md` preserves the
  timing and exact output; provider message-role priority remains unverified.
  Repeated skill-text guards do not establish compliance. A proposed correction
  to the separate kit hook is retained in `router-hook-fix-proposal.md`; no hook
  source or installed configuration has been changed. The operator subsequently
  excluded ai-kit from clones; that separate correction is not pursued here.
- Engine catalog closure is finalized with qualified independent final approval
  under completion task `engine-bootstrap-20261009`. Its source remains
  uncommitted and unreleased. Kernel K3, documentation closure and final review
  remain open; no kernel baseline has advanced.
- Standalone amendment: the brief `f0492877` and plan `80b7cc71` have fresh
  APPROVED reviews. K1 and K2 are reapproved against this configuration with
  unchanged production bytes; neither establishes native standalone behavior.
- Candidate06 freezes 189 files in
  `k3/candidate-ready-final-matrix06-final.json`, SHA-256
  `e597c7a0777b20ae3ae4d7129935b5989b3b9f00f4ffa8b58434a901793f3bbe`.
  Its test-only helper removes four identified kit hook entries from a private
  session settings copy, preserves permissions and non-kit controls, and binds
  runtime settings and retained scripts. The 36 focused fixture checks and
  actual render/update/configuration proofs pass. Native preflight and all
  nineteen cases remain pending; `k3/standalone06/readiness06.md` retains proof.
- Full suite06 exits 0 with `RESULT: all gates green`, including all 36 native
  fixture checks; exact output is retained in `kernel-final-suite06.log`.
- Standalone06 preflight, workflow and older-engine pass independent review in
  `k3/first2-standalone06-review.md`. The extra allowed company README read and
  abbreviated native hook argument array remain explicit evidence limits.
- Claude has five mechanical passes; its procedure-gaps attempt exits 1 with
  API 429 `usage_limit_reached`, resetting at 16:20 UTC on 2026-10-09. Scheduled
  acceptance is not started. No account, billing or model substitution is used.
  The partial06 matrix has twelve independently accepted cases, two failed
  attempts and five unstarted cases. OpenCode named fails for an unbounded
  search before skill loading, plus a distinct unavailable-tool attempt.
  `k3/partial-standalone06-review.md` is REVISE for whole-K3 acceptance.
- Description-only repair07 requires skill loading before exploration for any system question.
  K2 and K3 readiness APPROVED; manifest `k3/candidate-ready-final-matrix07.json`:
  SHA-256 `14cc3c07d1f42736272c9d5505a83342c5aec6405d83036d8b40ee45c4c1d4fb` (189 files).
  Named diagnostic review `k3/probe07-review.md` passes outside acceptance; all nineteen cases remain required.
- Resumed on 2026-10-10 with Claude and non-Luna models; six Luna07 attempts pass named/workflow only.
  Session inputs prove historical cwd behind ENOENT. Repair review approves explicit catalog stops,
  a clone-relative skill path and cwd audit; evidence `/home/mal/.local/state/codex-evidence/bootstrap-20261010/`.
- Claude08 preflight passes; workflow fails with body Read and prohibited help in one assistant response.
  Independent diagnosis justifies explanation-only selection in `cs-instructions` description before tools.
  The complete body remains identical; the byte-invariant test now compares body separately from frontmatter.
  Candidate09b freezes 190 files; manifest `k3/candidate09b.json`, SHA-256
  `64f49eeb72bb9367251081649265ea0d443050161c862f9c7562693d1ba0c5da`.
- Candidate09b full suite passes. Independent first2 Claude review is APPROVED;
  four further interactive cases pass mechanically. Scheduled Claude fails real
  root/source searches. OpenCode's raw secret audit falsely matches only numeric
  host timestamp metadata; decoded tool and engine content contains no match.
  Codex stops before launch on configuration drift; no global setting is edited.
  All groups close with fixture/Git/source/runtime/engine intact and no providers.
  Exact evidence is in `k3/matrix09b-partial-closure.json`; native acceptance stays open.
- Fresh repair-plan review10 is APPROVED. Candidate10 changes only the bootstrap
  description's scheduled deferral and the test-only OpenCode clock audit, with
  strict envelope/path/numeric bounds and no exemption for tool/business data.
  Forty-six audit regressions and real render/update pass; all twenty scheduled
  comparisons equal the base. Its 190-file manifest `k3/candidate10.json` has SHA-256
  `356b4c5b5c709dd709c6a5149e7c99103bc36c56e4799b6f760a5a0c58f84d02`.
- Candidate10 K2/readiness review is APPROVED. The first full-suite launch fails
  only the installed-package origin check because the lead supplied source
  `PYTHONPATH`; its raw log is retained. The corrected full run removes that
  environment override and uses a separate `kernel-suite10-correct-env.log`.
- Corrected full suite10 exits 0 with all gates green; its lead-owned exit
  receipt binds session 84018 and exact log SHA-256. Candidate10 native acceptance
  begins with a fresh manual-denial preflight, workflow and older-engine cases.
- Candidate10's first two cases pass independent review. The partial matrix has
  twelve mechanical passes, two failed cases and five unstarted cases; its Codex
  group is rejected on raw configuration drift. Claude procedure-gaps attempts
  denied variable Bash loops. OpenCode named matches a nonsecret four-digit
  business marker only inside native message IDs and matching stderr metadata.
  All original attempts remain under `k3/matrix10-partial-closure.json`.
- One separate Codex workflow diagnostic records exactly one new owned-clone
  `projects` entry with sole `trust_level = "trusted"`; prior entries and all
  other settings remain equal. The write-owning process is unverified. This
  diagnostic and the historical six Codex passes earn no current matrix credit.
- Fresh repair11 framing is APPROVED. Its bootstrap description requires Claude
  `Read` for local rules. Test-only privacy checks always scan raw full secrets;
  short nonsecret numeric markers exclude only validated native metadata. Typed
  private configuration snapshots admit only additive trust for exact owned
  fixture paths. Fifty-eight regressions and real render/update checks pass,
  including twenty unchanged scheduled render comparisons. Candidate11 freezes
  191 files in `k3/candidate11.json`, SHA-256
  `15f23b64016f599817f5e588d37a9b7e22d9520e69be3e73b3692c1063ae16a4`.
- Candidate11 full suite exits 0, but its fresh readiness review is REVISE:
  malformed OpenCode text envelopes still receive metadata exclusions. No
  candidate11 native case starts. Repair12 validates the complete known event
  schema before normalization; malformed/unknown events stay raw. Fifty-nine
  focused regressions and real render/update checks pass. Its 191-file manifest
  `k3/candidate12.json` has SHA-256
  `51b62e2e3a9f67e601e1bac896689674977532a2329f947bf7718f8adfa551f7`.
- Candidate12 full suite exits 0; readiness remains REVISE for duplicate JSON
  keys and escaped full secrets. Candidate13 rejects ambiguous native JSON,
  checks original and decoded unnormalized values for full secrets, and
  preserves every business/diagnostic JSON string during privacy scanning.
  Sixty-one focused regressions and real render/update pass. No candidate12
  native case starts. Candidate13's 191-file manifest `k3/candidate13.json`
  has SHA-256 `488be2a4350aaf8186c3b8d144d4f2c6a1008f05f7c5bdb42fb2f38e89ca308b`.
- Candidate13 full suite exits 0; readiness remains REVISE for actual decoded
  string scanning, escaped Claude/Codex business markers and numeric JSON
  overflow. Repair14 scans decoded values directly and rejects nonfinite JSON
  numbers recursively. Sixty-three focused regressions and real render/update
  pass. No candidate13 native case starts. Candidate14 freezes 191 files in
  `k3/candidate14.json`, SHA-256
  `cd05e901118cf6a7d44c590ed729a74bbf7e0769eb20a4572e9ab614382b0e7c`.
- Candidate14 full suite exits 0 with all gates green; the lead's receipt binds
  session 75546 and log SHA-256. K2/readiness review14 is APPROVED. Historical
  OpenCode archives pass the repaired audit without matrix credit or changed
  raw bytes. Fresh native acceptance starts with Claude manual-denial preflight,
  workflow and older-engine cases before independent review of that first pair.
- Fresh candidate14 Claude preflight, workflow and older-engine complete with
  driver and closure checker exit 0. Source/runtime/engine and clone/Git state
  remain equal; the older engine closes with zero provider calls and all owned
  fixture/hook processes absent. `k3/final-claude-14-01/first2-results.json`
  has SHA-256 `f40473653ef00b1da4bcd537d2691e32a9c610ed1b1870e5cf7fba96241c774f`.
- First2 review14 is APPROVED exactly 2/19. Remaining14 finishes with eleven
  mechanical passes, two failures and six unstarted cases. Codex passes all
  six cases, actual gpt-6.1-sol/medium and exact-owned trust/config comparisons.
  Claude reachable follows the correct discovery route, but its audit rejects
  two `echo "--- exit $?"` diagnostics in a readonly CLI chain. OpenCode passes
  the three remote cases and fails procedures on an actual unavailable-tool
  attempt. Neither failure is waived. The coordinating agent reaches its own
  usage limit after the groups finish; the lead resumes and runs the closure
  checker, exit 0, confirming unchanged source/runtime/engine/clone/Git,
  zero providers/forbidden requests and no active owned processes. Evidence:
  `k3/matrix14-closure.json`. A bounded test-parser repair15 is under review.
- Repair-plan15 is APPROVED. Candidate15 permits only exact unpiped previous-exit
  diagnostics; all other expansion/loop/command limits remain. Its 65 focused
  regressions and real render/update pass. Only the parser and its regression
  file differ from14, so the approved verification reuses suite14 solely for
  unchanged production/packaging/other tests. It does not claim a full suite15.
  Historical Claude14 whole-tool re-audit passes without matrix credit. The
  191-file manifest `k3/candidate15.json` has SHA-256
  `2ff54c5e22e8f5bd0c0a69a98cc081a3ba173c3975aab4256547673e55a0d268`.
- Candidate15 readiness is REVISE for a prelaunch hash-suffix substitution
  bypass in the test lexer. No native15 case starts. Repair15b disables lexer
  comment stripping and covers attached and separated hash/substitution cases.
  All 65 focused regressions and real render/update pass. The two-file delta
  from14 remains exact; reused suite14 covers unchanged surfaces only.
  Candidate15b manifest SHA-256 is
  `19112e5ca0d3d626ffe330a09f736d9ddacba90d37bf7e3dc65d60072e98164a`;
  focused receipt SHA-256 is
  `e5d7174b17ecc2d6ef94930aca6e17335c772fb13bfc9ae70da2f318732ffaaa`.
  The same readiness reviewer independently reproduces rejection and returns
  APPROVED in `k3/k2-readiness-review15b.md`, SHA-256
  `caaf6281385ebc0c47e09cba1f2c9b5c4b4902ff25d06bf47a69ad36b4a3ed72`.
  Fresh first-two Claude acceptance is authorized; remaining17 still requires
  independent first-two approval. Earlier native results receive no matrix credit.
- Fresh candidate15b Claude manual-denial preflight, workflow and older-engine
  pass; runner and closure checker exit 0. Both gate cases complete, remaining17
  has not started, source/runtime/engine remain equal and no owned process stays
  active. `k3/final-claude-15b-01/first2-results.json` SHA-256 is
  `e273d94a57e62104c6897b178019c38096a6135762c7dd03fed7b8d4cd01b540`.
  Independent semantic review of this fresh pair is pending.
- First2 review15b is APPROVED exactly 2/19. Its independent evidence checks
  pass actual denial, full canonical reads, semantic answers, privacy, hooks,
  bindings and teardown. Report `k3/first2-review15b.md` SHA-256 is
  `0db770b8c5ec6584afc769b0df02945e5a90d67dc04128e38715a9ddd0313f67`.
  Full hook argv and aggregate listing visibility retain their accepted
  nonblocking UNVERIFIABLE limits. Remaining17 is authorized on candidate15b
  with fresh Codex intent and exact-owned private configuration comparisons.
- Matrix15b closes with nine mechanical passes, two failures and eight unstarted
  cases. Codex passes all six cases with actual model/config checks; OpenCode
  reachable passes. Claude reachable fails on literal `echo ---`. OpenCode named
  fails on `EXIT=$?`/`EXIT=${PIPESTATUS[0]}` diagnostics and also requires a
  stdout-only config grep audit. Both failures remain retained. Claude/OpenCode
  exit 1, Codex exits 0 and the closure checker exits 0. Source/runtime/engine are unchanged; provider
  and forbidden requests are zero and all owned processes are absent.
  `k3/matrix15b-closure.json` SHA-256 is
  `ba2c52b8a4973023521962480793af550f6f5d71ed23b8dccb43bf8dd4a386d0`.
  A bounded test-only repair16 has initial exact-separator approval; its
  additional observed output forms require renewed review before implementation.
- Repair16c plan is APPROVED after rejecting piped `rg --files` and retaining
  the actual `ls manifest.toml` violation. The implementation changes only the
  parser and regressions: finite inert echo/status forms and audited stdout-only
  grep/rg add no file targets or read coverage. Sixty-seven focused tests and
  real render/update pass; twenty scheduled comparisons remain equal. An initial
  test command named two nonexistent modules and exits 1; its log is retained,
  and the corrected actual module command exits 0. The complete Claude15b
  re-audit passes without matrix credit. OpenCode15b remains rejected on its
  configuration target. Candidate16 manifest SHA-256 is
  `6d9d09ce1dac7a54d851e60249c44bcfd1c1f2b2360eaa1efa9b3940db3bb4dc`;
  focused receipt SHA-256 is
  `4cc122a7c48df8dec12c3ad187aab7f5b21e350ded9dd8e753a45ddac81744ae`.
  Only the same two test files differ from14; suite14 is reused solely for
  unchanged surfaces. Fresh K2/readiness16 review is pending before any model run.
- Readiness16 is REVISE: unquoted glob/brace patterns in the new stdin-only
  filter can expand into file operands. An isolated real Bash reproduction
  reads a synthetic source file. No native16 case starts. Repair16b rejects
  expansion-capable filter arguments conservatively, including glob, brace,
  tilde and parenthesis forms; observed constant filters remain supported.
  All 67 focused tests and real render/update pass again. Candidate16b manifest
  SHA-256 is `0fe2cee2a9d31aa824438ebfecc71664694ab9e143ad9fabaf409f4314b7de5c`;
  focused receipt SHA-256 is
  `92a8f8d1a2e43f318923f97f2a66eabb463c2feb44102bdfca101b7a6d7849be`.
  The same two-file delta and historical re-audit outcomes remain. Renewed
  readiness review is pending; prior manifest, proof and REVISE report are preserved.
- Readiness16b is REVISE on explicit brace-expanded operands: the guard only
  covers empty parsed target lists. The reviewer reproduces a real synthetic
  source read. No native16b case starts. Repair16c checks every piped grep/rg
  argument before either branch, with explicit operand regressions for both
  verbs. All 67 focused tests and real render/update pass. Candidate16c manifest
  SHA-256 is `69323284a435dff9fe62de684f06b0c1a1415933c2ce6e2861442dfa98630ba0`;
  focused receipt SHA-256 is
  `8bba3628c728355e679953dde0a152319cd2f723ac37b6097d9c859d08a4f4b3`.
  Two-file delta and historical re-audit outcomes stay exact. Renewed readiness
  review is pending; earlier evidence remains immutable.
- Readiness16c is APPROVED: independent regressions reject both reproduced
  expansion bypasses; source/focused/runtime/engine and all four script bindings
  match. Report `k3/k2-readiness-review16c.md` SHA-256 is
  `57d1d9a37f1060aa7271e6d73df048880a15aff31aa23ecd970b434a13ced57a`.
  Fresh manual-denial preflight and first-two Claude cases are authorized;
  independent approval of that pair still gates remaining17.
- Fresh candidate16c preflight, workflow and older-engine pass; runner and
  closure checker exit 0. Both gate cases complete, remaining17 is unstarted,
  source/runtime/engine remain equal and all owned processes are absent.
  `k3/final-claude-16c-01/first2-results.json` SHA-256 is
  `1cc109e8fac12dc3367d36bae615286134fa9dc729b6585abef17844367fefab`.
  Independent first-two review16c is pending.
- First2 review16c is APPROVED exactly 2/19. Independent checks exit 0 and
  confirm canonical reads, semantic answers, uncertainty-first STOP, privacy,
  retained hooks, bindings and teardown. Report `k3/first2-review16c.md`
  SHA-256 is `4909ae47424bf94313021a9405837dc487c6e7a7176ab1c25f47d00b85c08059`.
  Accepted hook-argv and aggregate-visibility limits remain. Remaining17 is
  authorized on frozen16c with fresh Codex intent and exact-owned private
  configuration comparisons; no historical result counts.
- Matrix16c closes with thirteen mechanical passes, two failures and four
  unstarted cases. Codex passes all six with actual model/config checks;
  OpenCode passes its first four. Claude named fails on literal echo output;
  OpenCode procedure-gaps lacks the required target-level missing-file evidence,
  despite a correct answer from a parent listing. Both failures remain retained.
  Closure exits 0, source/runtime/engine stay unchanged and no owned process
  remains. `k3/matrix16c-closure.json` SHA-256 is
  `5ed68b4a81c758bb7be6bf4cd6d70850b6ce45a46470d3479054d5f4f77aec24`.
- Repair17 framing is initially REVISE: runtime/auditor separation changes the
  explicit acceptance definition. Fresh brief17 review APPROVED the narrow
  clarification, artifact `a8de687a`; the repaired plan17 is APPROVED, artifact
  `46733c0a`. Both original approved artifacts remain immutable. All nineteen
  cases and behavioral criteria remain mandatory; retained observations require
  actual current-auditor replay and independent dependency/semantic review.
- Candidate17 changes only the two post-capture audit/regression files versus16c
  and14. Literal echo labels contribute no file targets or read coverage;
  expansion, flag, pipeline and adjacent-command negatives remain rejected.
  All 69 focused tests and real render/update pass, including twenty unchanged
  scheduled comparisons. Manifest SHA-256 is
  `0e11eaa8392fad6b2427c0a1a4358bc107c84d75ab9b9cf89837d9231df2a152`;
  focused receipt SHA-256 is
  `74599712b0e73d85b7c5731688488d2a616fd232cc0f4acc2eb143b2ab1a0e25`.
  Suite14 is reused only for unchanged surfaces. Fresh K2 readiness, replay,
  first-two review and all nineteen-case acceptance remain pending.
- K2/readiness17 is APPROVED after independent source/dependency, grammar,
  original observation-binding and subset guard checks. Report SHA-256 is
  `c793b5a98da78ccfb97f36008447bfc464510fa38db5900e13fcb2a892538f74`.
  Script smoke results are explicitly not acceptance. Failed script attempts
  remain retained. Full historical OpenCode effective configuration remains
  UNVERIFIABLE; observed host/model identity and effective MCP settings are bound.
- Actual current-auditor first-two replay exits 0. Its result SHA-256 is
  `a4a32610b687af86b9d96d9aba8bf03a4e22b60ed2cb13bdd06b740e96e9920e`.
  Fresh independent first-two review17 is APPROVED exactly 2/19, report SHA-256
  `9cbd17592f8f7606334e33a8062696e8cdf8cb1647e337ab9d8f60c350c19766`.
  These are retained16c native observations with actual17 re-audit, not fresh
  native17 executions. Complete reads, semantic answers, uncertainty-first STOP,
  denial, privacy, configuration, hooks and teardown pass independent checks.
  Accepted hook-argv and aggregate-visibility limits remain. Approved available
  replay and five fresh cases are authorized; whole-K3 and closure remain open.
- Fresh17 Claude procedures, gaps and scheduled cases pass. OpenCode gaps exits
  successfully but its audit rejects the absence evidence; workflow remains
  unstarted. Both groups preserve runtime/source/engine and teardown. Result
  SHA-256 values are `8bee971e9f8aa70acc633605b8c8c4405bafe901fdb88f15951ed836f5abbcc2`
  and `1dbbd66e4c10afebe996bc56cdd2ba3491547bb53489ff523148dcc37878c375`.
  Initial invocation errors occur before host launch and remain retained.
- Whole-K3 review17 is REVISE. Independent semantic inspection rejects the
  retained OpenCode older-engine answer: its final negative headline is hidden
  from the mechanical first-line check by pre-tool narration. A fresh native
  attempt remains required. Independent inspection confirms fresh OpenCode gaps17
  correctly reports the missing playbook, unwritten identity and empty companion
  directory and completely reads all ten regular company files. Successful exact
  parent metadata is sufficient evidence of absence; current replay is required
  after repairing the over-narrow audit. Original failures remain immutable.
- Fresh brief18 and plan18 reviews approve isolation of post-capture function
  blocks in mixed modules. Their immutable approved SHA-256 values are
  `1cf4bb8cbc8cbffa1ce4760b266f92b6f60839d56e1776acc39fe84555c97630` and
  `db59b371ec3ddfbbf1542b6a0d6cd4216945b720be688a37babe70b8b48dfe3b`.
  Candidate18 changes only events, the driver gaps branch and regressions versus17;
  exact byte partitions, AST comparisons and post-capture caller checks pass.
  Seventy-five focused regressions and real render/update pass, including twenty
  unchanged scheduled comparisons. Candidate18 SHA-256 is
  `bab92b97c8cf78d8f83bb45b5869c808ee876949e7946eaa992d864d3bf2fea8`;
  focused receipt is `bde6736c248f0d2bb9997791c422ab562dad5dc536a85e6d757551b2d4291301`;
  partition proof is `a383132e2f0282e9e54fab71e1e5173530b1039b2aedf282d3aa28656fb860e8`.
  Suite14 applies only to unchanged surfaces. K2 readiness18, current replay,
  the two fresh OpenCode cases and final closure remain pending.
- K2/readiness18 is REVISE after offline fresh17 replay reproduces an additional
  metadata issue: the complete successful company-directory section is rejected
  because another literal operand is absent. The original command exits 2 and
  reports that separate absence. Candidate18b isolates the verified complete
  parent section, accepting only exact diagnostics for independently missing
  other operands; target errors, unknown diagnostics and incomplete inventories
  remain rejected. A real Bash regression exercises that exit-2 command and its
  negative variants. All 76 focused tests, real render/update and byte/AST/caller
  partition proof pass. Candidate18b SHA-256 is
  `fb7dddb39e3b9d048f344b375054eb6c262703ed88401f672659fef9ad66870e`;
  focused receipt is `2c5a9f82c6946db6be68a5927cba8b17178b356aa4923d393cf93d643dfbc40d`;
  partition proof is `42ff58c8a6c334b2d6ed5297d1910ed7cab3807e10baa494dd08807e6c4407d0`.
  Original18 manifests, smokes and REVISE report remain retained. No native18
  execution starts before repaired readiness and fresh first-two approval.
- K2/readiness18b is REVISE on a reproduced broken-symlink operand: resolving
  first loses its original symlink identity. Candidate18c rejects symlinks in
  original operands and their ancestors before resolution. Direct and ancestor
  broken-symlink regressions use real Bash; all 77 focused tests and render/update
  pass, with unchanged scheduled comparisons and exact block partitions.
  Candidate18c SHA-256 is
  `96848f3d490cc4e83b58e94216ca9ff0261efbec1faedcd19be8a2e434267ae3`;
  focused receipt is `f15bf427aa6c45b92163e0bd95bbc2bac833522ca0925a204dbd903a848a4567`;
  partition proof is `0cd4fd128d0a93d632bd7fa7566f3cc09195f75626526c09e985eb2032370fb2`.
  Earlier candidate manifests, smokes and REVISE reports remain retained.
- K2/readiness18c is REVISE on an absolute parent-traversal spelling that
  bypasses lexical symlink checks. Candidate18d conservatively rejects parent
  traversal and expansion-capable literal patterns before path construction,
  requires original operands inside the exact clone prefix and checks original
  symlink components before resolution. Real Bash regressions cover absolute,
  relative and doubled-slash spellings and unmatched wildcard operands. The
  independent final batch rejects nine reproduced variants. All 78 focused tests,
  real render/update and byte/AST partition checks pass. Candidate18d SHA-256 is
  `48fa328d52d7e7249e214d90aae54c9473647b9859c1cfec84affff625e6afca`;
  focused receipt is `3fc9a5acb45755d83bde6def09cd68d3c9c99b1d904f36104721efd2105578d4`;
  partition proof is `8d2895cdce32a1b8ed329e79ac6929705a73d44f9e53e70a8a18e6c7754a2e48`.
  Earlier evidence remains immutable. External script review additionally
  requires smoke-credit and exact verdict/binding rejection before approval.
- Repaired K2/readiness18d is APPROVED. Independent checks verify all 191
  current source hashes, exact mixed-module partitions and final script bindings;
  complete smoke evidence checks cover 627/21079/4476 original files. Real strict
  gate probes reject smoke credit, a stale review hash, a quoted approval and a
  genuine correctly hashed earlier first-two approval. Report SHA-256 is
  `c600c577fc2c23a400fa39ad609e3c4f74a3faa86f2b3ddb452ed061c30d0bc2`.
  Actual current first-two replay exits 0; result SHA-256 is
  `476dc3c9976ba1ba873a276c3fb874af8808f19b9e3bcff43074f15a659c6b70`.
  These retained16c observations receive no fresh-run claim. Fresh independent
  first-two review remains pending before any native18d execution.
- Fresh first-two review18d is APPROVED exactly 2/19. Report SHA-256 is
  `2174025cb360f71697abb3be1c1875482e64ae25ccd85bede66fcbdb8ae185bd`. Complete canonical workflow coverage,
  uncertainty-first older-engine STOP, actual permission denial, whole-run
  privacy, retained non-kit hooks and source/runtime/engine bindings pass review.
  Full hook argv and aggregate listing visibility remain UNVERIFIABLE. Official
  retained and fresh17 replays are authorized; only the two missing OpenCode
  cases may start after those actual replays establish seventeen unique cases.
- Official retained16c and fresh17 replays each exit 0 with current auditor18d.
  Retained replay checks thirteen rows and accepts eleven, preserving both old
  OpenCode failures. Fresh17 replay accepts all four; with the reviewed pair this
  establishes seventeen unique cases. Result SHA-256 values are
  `787c6af4d977d337df87840bc12b5c5c6843178f82d4ee771c1a9bcba1dbaa5e` and
  `61641c90275ff573d299bca912de558e5974e6a5b56b7a3dca30b3dbe9349402`. Only the authorized fresh
  OpenCode older-engine and workflow cases start; whole-K3 remains pending.

- Fresh OpenCode18d older-engine ended with host exit 0 and current audit pass.
  Workflow also ended with host exit 0, but its original audit rejected coverage
  123/127: the successful native Skill returned the complete canonical body and
  omitted only four YAML metadata lines. Independent K3 diagnosis confirms the
  answer and explanation-only boundaries. Original failed group and all raw
  evidence remain immutable; repair19 has no additional native/model calls.

- Repair19 is frozen as candidate `a217aec3164e28e441f5be1bd6174737e4b7a4e0efc6947c0cd53a91e1cbaafe`.
  Only the named post-capture coverage block and two regression methods differ
  from18d; exact outside-block bytes and AST, imports, initialization and argument
  shapes remain equal. Current 80 audit tests and real render/update with twenty
  scheduled comparisons exit0. Suite14 is reused only for unchanged surfaces.
  Fresh readiness19 and first-two review approve the actual current replay.
- Actual remaining replay19 produces eleven accepted retained cases, four fresh17
  observations and two fresh18d observations, in addition to the first two.
  These are retained native recordings, not fresh native19 runs. Original
  OpenCode16c older-engine and gaps failures remain excluded and immutable.
- Original aggregate19 assembly stops on a missing retained-result partition
  field. Its failed command/output remains preserved. A separately reviewed
  closure-only correction verifies the actual focused-receipt partition binding
  and retains all original approvals, replays and script bytes. The corrected
  root invocation exits0 and qualifies nineteen distinct cases; no model/native
  call or source change follows from that correction.
- Actual aggregate: evidence `bootstrap-20261010/k3/audit-replay19/matrix19-closure.json`,
  SHA-256 `6709a404d3da9adf44ef20260d052f883518062aa7970ffcd775f2845859f7ba`.
  Independent K3 approval `k3/k3-review19.md`, SHA-256
  `70d09a3386a6915db01082705826044ddf9ff99b080fb117ddbec1d50c5c8dd6`,
  checks all nineteen semantics, full raw bindings, exact source/engine equality,
  fixture/Git state and owned-process teardown. The OpenCode workflow proves
  body123/123 and file123/127; omitted YAML metadata receives no read credit.
- Qualified limits remain: full hook arguments and aggregate listing visibility,
  Codex native configuration-writer attribution, and historical full OpenCode
  effective configuration are unverified. Claude reports default permission mode
  despite the manual CLI flag; observed denial proves only that refusal. These
  limits do not waive the required observed behavior. No universal compliance,
  kit-enabled profile, production Firebase or maintained-clone adoption is proved.
  Documentation closure and separate final review follow this integration gate;
  checker finalization owns the declared active-to-completed status transition.
