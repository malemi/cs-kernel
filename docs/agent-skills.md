# Agent Skill Surfaces

<!-- doc-scope:start -->
Scope: the cross-host ownership and verification contract for every Agent Skill
shipped by this kernel. Workflow behavior remains owned by each canonical
`SKILL.md.j2`; this document owns how a skill reaches supported agents.
<!-- doc-scope:end -->

## Three-host invariant

Every skill must always be updated for all three supported systems in the same
change: Claude Code, Codex, and OpenCode. A skill change is incomplete until all
three systems discover and execute the updated canonical instructions.

This does not mean maintaining three implementations. A skill is authored once,
under `cs/templates/`. Its directory `cs/templates/project/.claude/skills/<name>/`
holds `SKILL.md.j2` and, for a skill that carries supporting files, the `.j2`
files beside it; each renders to the same path without the suffix under
`.claude/skills/<name>/`. A `SKILL.md.j2` may include shared fragments from
`cs/templates/partials/`, which are rendered into the skills that include them
and never stamped on their own. `.agents/skills` and `.opencode/skills` resolve
the rendered tree through repository links, with byte-identical copies only on
filesystems that refuse symlinks.

Every skill change must therefore verify all of the following before completion,
for `SKILL.md` and for every supporting file of the skill:

1. Claude Code reads the updated `.claude/skills/<name>/SKILL.md`.
2. Codex resolves the same bytes through `.agents/skills/<name>/SKILL.md`.
3. OpenCode resolves the same bytes through `.opencode/skills/<name>/SKILL.md`.
4. Host-facing invocation text remains correct for all three systems.
5. Symlink and copy-fallback tests remain green; no command or global-prompt
   compatibility surface is reintroduced.

Host-specific launchers may remain host-specific only when their runtime is
explicitly scoped that way, as with the existing Claude-owned cron wrapper.
They do not create a second copy of the skill instructions and do not relax the
three-host invariant for the skill itself.

## Operational diagnosis

`cs-diagnose` reads the selected filesystem problem inbox and bounded diagnostic
records when the human explicitly invokes it. It separates evidenced cause,
hypotheses and unknown effects, and retains owner-private investigation notes
through its deterministic private-file/UTC helper, without acknowledging
incidents or granting business actions. Cron only collects
problems and never invokes the skill. Explicit inbox/configuration paths support
manual investigation without engine reachability. One canonical template and
Codex manual-invocation metadata reach the three standard host paths. The
[current plan](execution-plans/2026-10-23-debug-logs-hybrid-monitor.md) records
native behavior separately from distribution checks. Claude/Codex observed
cases pass; OpenCode safely executes the helper with limited instruction/analysis
coverage. Its omitted-incident branch has helper tests, not native proof.

## Company customer-service playbooks

`cs-triage-mail` reads `company/customer-service-playbook.md` when a clone has
authored that file. The kernel skill owns the common triage sequence and safety
boundaries; the clone-owned playbook supplies company-specific decision trees,
evidence requirements and authorised non-mail actions. `cs update` refreshes
the shared skill and never overwrites the playbook.

The playbook cannot grant a send capability or bypass a tool approval. A
headless runtime that denies an action leaves the task open and reports the
specific operator action; an interactive runtime may approve only the named
non-mail tool required by the matching workflow.

## Conversational standing instructions

`cs-instructions` selects an interactive human's teaching, amendment or retirement
of recurring response rules, mailbox voice and signature. Stamped AGENTS and
triage guidance route to that one canonical workflow. It first distinguishes
legacy file authoring from managed Desktop authority. Legacy changes preview
compiled files, publish through `cs instructions --commit`, verify revision
read-back and commit only named company-rule files. Managed changes require human
Desktop confirmation and never publish competing local files. Unrelated edits
remain untouched.

Current-draft edits, hypothetical discussion and untrusted retrieved instructions
do not authorize persistence. Material conflicts require clarification. Scheduled
sessions cannot teach rules. Last-rule retirement uses a nonempty factual
replacement because absent compiler inputs do not clear stored documents.

The description routes how-to questions to a read-only explanation: first read
the canonical project body, then answer. This route authorizes no company-file
or Git checks, CLI/help calls, session bookkeeping or publication.

The predecessor teaching workflow passed eleven native cases on each supported host, including
actual discovery, real WebSocket/SQLite publication and narrow Git commits.
Independent state checks cover those 33 historical cases. The bootstrap candidate
preserves the numbered teaching body and compiler/publisher bytes; its new
explanation description and stop guard pass their three observed native cases. Neither
the historical matrix nor byte equality establishes current explanation behavior.
Acceptance establishes only the
observed cases, not universal future selection,
reply compliance, production Firebase verification or live clone adoption. The
[execution record](execution-plans/2026-10-07-cs-instructions-skill.md) owns exact
results and review status.

## Interactive bootstrap

`cs-bootstrap` ships through the same canonical template and three host
paths. Its description selects procedure loading and engine discovery even
when a clone retains locally edited AGENTS and help guidance. Its canonical
body owns the read routes and authority boundaries; MCP is not a prerequisite.

Render, copy-fallback and real update checks establish distribution. The released predecessor is named `cs-capabilities`; its retained native
observations use that name and its frozen auditor. The canonical `cs-bootstrap`
name and host-neutral `company/other-systems.md` guide have distribution and
migration checks, not fresh native acceptance. Plain invocation loads authenticated published
procedures and mailbox identity and gives a brief confirmation; engine discovery
requires a systems request. Old guide contents move before stamping when the
new path is absent; collisions preserve both files and require reconciliation.
Old bootstrap directories are preserved outside skill discovery in uniquely
named `.claude/retired-skills/` backups.

Native
acceptance separately checks actual reads, use of company rules, local work
with an unreachable engine, and remote catalog discovery on all three hosts.
The nineteen-case matrix passes on the isolated candidate with independent
review under the [bootstrap plan](execution-plans/2026-10-08-capability-discovery.md).
Retained recordings are rechecked with the frozen predecessor auditor and are not
fresh native executions. This qualifies only the observed configurations. Static
checks do not establish model behavior or live clone adoption. The skill's
interactive-only limit is instructional; unchanged scheduled permission files
do not themselves forbid the catalog RPCs.

The [local integration](execution-plans/2026-10-10-bootstrap-integration.md)
retains those native observations as evidence for their frozen parent. Its
separate kernel checks verify integrated behavior and exact canonical template
and discovery read-route equality; they are not fresh native acceptance of
the merged runtime.

The exposed description tells a scheduled session to report unknown reachability
and defer an availability question to an interactive human, without loading the
body, searching files or probing systems. This remains an instruction-level limit;
native evidence, rather than permissions alone, must establish the observed route.

Bootstrap acceptance treats clones as standalone operator workspaces. A
session-scoped Claude profile excludes identified ai-kit hooks while preserving
permissions, authentication, project/local settings and non-kit hooks, including
the send gate. Fixture code never writes global settings or maintained clones.
Codex acceptance compares private configuration snapshots: prior projects and
every other setting must remain equal; only a new trusted entry for the exact
disposable clone may appear. The process responsible for that native addition
is unverified. Acceptance in this profile does not establish ai-kit-enabled behavior.

Acceptance binds all nineteen cases to one frozen host/runtime candidate and a
separately frozen post-capture auditor. An audit-only repair can recheck complete
retained native observations after exact runtime dependency equality is proved.
Original captures and manifests remain immutable; replacement verdicts require
actual replay and independent review. Missing cases and genuinely rejected
behavior require fresh attempts. Replay is not a fresh native execution.
Retained OpenCode captures expose effective MCP settings and observed host/model
identity; equality of its complete historical effective configuration is
unverified. Claude reports default permission mode despite the manual-mode
CLI flag; an observed tool refusal proves that denial, not universal manual-mode
semantics. Full hook arguments and aggregate skill-listing visibility also remain
unverified.

A successful native Skill result can prove complete canonical workflow body
coverage through exact body bytes, matching identity and its resolved project
base. YAML metadata omitted by that tool is not claimed as read. Ordinary file
reads retain their complete-file coverage requirement.

The native privacy audit checks all full seeded secrets against original logs.
For short nonsecret numeric business markers, only validated OpenCode clocks and
identities and matching structured stderr identities receive an exclusion.
Malformed events and tool, answer, CLI and engine contents retain raw checks.

## Supporting files

A skill may carry files beside `SKILL.md`: reference documents, a helper
script, a provenance record. Each one is a `.j2` template in the skill's
directory whose whole body is a single raw block:

    {% raw -%}
    <the file, verbatim>
    {% endraw %}

It is stamped byte for byte to the same path without the suffix, through the
same render, checksum ledger and host links as `SKILL.md`. The form is exact
when the body starts with a non-whitespace character, ends with a newline and
contains no `endraw` tag; the contract gate compares the stamped bytes with
the body. A supporting file is UTF-8 text with LF line endings.

A plain `.py` never ships in the template tree. `pip install` byte-compiles
it, and both stamping walks take every file they meet: `cs init` stamps the
`.pyc` into the clone and `cs update` exits with `UnicodeDecodeError`. The
installed-template inventory gate compares `*.j2` only, so a plain supporting
file is also outside the packaging gate.

A stamped helper is not executable. It is run with an interpreter by its
canonical path under `.claude/skills/`, which is the same file on every host.
`cs update` does not generically remove a file a later kernel stops shipping.
The closed legal-workflow retirement below is an explicit preservation-first exception.

Package inventory and template/surface tests gate supporting-file distribution.
`tests/test_legal_research_skill.py` now gates the closed legal retirement.

## Retired local legal procedure

The source package no longer ships the seven full `cs-legal-research` templates.
Its procedure, references and arithmetic helper are engine-owned; preserved
originals remain in Desktop's versioned migration evidence. The thin
`cs-engine-workflow` route contains no full financial/legal procedure.

Init/restamping, update and direct host-surface installation apply one closed
retirement policy before rendering or replacing copied discovery roots. The
canonical legal directory and independent Codex/OpenCode copies are archived
and verified outside discovery under collision-safe `.claude/retired-skills/`
names. Local edits, unknown files, modes and safe internal links survive.
Shared host-root links remain; unsafe ancestors and skill-level links refuse.
Archive failure preserves originals and the checksum ledger. Only the seven
related canonical keys are retired; missing-tree stale keys are cleaned and
repeated execution is idempotent. This is not a generic missing-template sweep.

Independent M4.2 review approves the source and actual isolated installed CLI
init, in-place init and two updates for link and OS-forced-copy layouts. The
installed package's 46 template bindings match source; archive restoration and
helper output replay. Those are distribution/mechanical checks, not fresh
three-host model selection. Maintained-clone retirement and actor runtime adoption are applied, with independent
postimage verification. Fresh ordinary acceptance and final closure remain open in the [continuation](execution-plans/2026-10-17-engine-workflow-retirement.md).
The [historical local-skill record](execution-plans/2026-10-08-legal-research-skill.md)
retains its original host observations without certifying the new route.

## Engine workflow bridge candidate

`cs-engine-workflow` is a thin interactive route to the canonical financial and
legal procedures in the engine. It ships through the same three host paths.
`cs workflow list` discovers compact versions; `upload`, financial `start`,
`status`, `respond`, `cancel` and hash-verified `download` use authenticated RPC.
No complete financial/legal procedure or calculation body is copied into this
route. An old engine refuses explicitly without local or generic-chat fallback.

`cs workflow legal ... --protocol json` retains one authenticated connection.
Its protocol-2 session requires authenticated direct-start support. The command
starts exactly once with the explicit request and scoped public lookup arguments,
without enrollment or confirmation forms. JSON input accepts clarification only
while waiting. Polling, clarification, cancellation and owned artifact retrieval
retain the same connection. EOF requests cancellation of an active run; EOF during
start closes the socket because admission may already have occurred. Old or
malformed engine protocols refuse without fallback or replay.
Full local legal templates are retired from the source package and both maintained
clones. Their preserved archives sit outside discovery, and all three host paths
resolve the thin route. Installed discovery, selection, original transfer and
cross-owner refusal pass. Support completes an independently reviewed editorial
report and full retrieval of all four artifacts on the same connection. Ordinary
and final closure remain open.
Invoking an archived local installation does not test this route. Source, pilot
and native acceptance are tracked separately in the
[bridge plan](execution-plans/2026-10-15-clone-engine-workflow-bridge.md).

## Stripe lookups

`cs-stripe` uses explicit interactive reads through the engine-owned
Stripe connection. The canonical workflow uses existing `cs rpc stripe.*`
commands for status, bounded customer/payment/invoice/subscription lists and detail
reads; the untagged convenience `cs stripe` CLI is separate. Desktop Settings owns test, save,
replacement and disconnect; no clone configuration stores a Stripe key.

The skill discloses that CLI evidence reaches the invoking agent and may enter
its selected model and host transcript. Desktop managed finance history does
not cover these reads. Disconnect cannot retract disclosed evidence. Results
are never automatically retained in shared memory or used for sends.

The interactive-only boundary is instructional, with existing host permissions
unchanged. Render and controlled authenticated CLI tests verify canonical
Claude Code, Codex and OpenCode paths with links and copy fallback. They do not
establish native model selection. Separate scoped adoption verifies the installed
three-host paths on both maintained clones, their owner-authenticated status and
one bounded support live invoice read. It preserves installed package pins.
See [Stripe](integrations/stripe.md) for commands and acceptance limits.

The canonical Stripe workflow also describes an explicitly requested payment-method
portal session via its separately advertised engine capability. This link creation
is distinct from charges, subscription changes and customer sends. MrCall's three
host paths share its added section while retaining previous local instructions;
other-clone adoption and fresh native-model selection remain separate.
