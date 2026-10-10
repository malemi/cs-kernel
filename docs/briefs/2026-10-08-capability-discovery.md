# Bootstrap an interactive clone session from its rules, workflows and engine catalog

Date: 2026-10-08. Kernel part of capability discovery. No release and no live clone change.

Amended 2026-10-09 after the operator's concrete failure: asked to load the
company procedures into its session context, an agent started exploring `cs rpc --help`.
The amendment requires usable context loading without MCP, as well as system discovery.
The previous brief approval at `d7350dc` does not approve this amendment.

## Problem

A session started in a clone learns what it can reach from two stamped surfaces. Neither names
the systems connected to the engine.

- **What the three hosts load at start.** Codex puts the clone's whole `AGENTS.md` and one row
  per skill, name and description, in its start prompt. Claude Code loads `AGENTS.md` through
  the stamped `CLAUDE.md` import and OpenCode natively; both list each skill's name and
  description. The kernel stamps no hook and no startup command.
- **What that text says about systems.** The stamped charter mentions connectors once, as
  ambient host connectors that must not send mail (`cs/templates/project/AGENTS.md.j2:178-182`).
  Its one pointer for other systems leads to a hand-authored slot (`:118-121`). No skill
  description mentions the engine's systems, their `cs rpc` route, or a way to list them.
- **What the engine and the CLI offer.** `cs rpc` forwards any method name to the engine
  (`cs/cli.py:161-165`). `system.capabilities` carries integer policy versions, two of which the
  kernel reads (`cs/rpc.py:346-350, 368-373`), and names no system.
- **The observed result.** Asked whether a company system is reachable, a session inspects only
  its host's own tools and answers that it is not, while `cs rpc` reaches that system.
- **The additional failure.** A request to load procedures can start a search for transport
  syntax even though the clone charter already names the authoritative company files and the
  skill tree. Knowing an operation's name is insufficient evidence that an agent has loaded
  the instructions it needs to work.

## Intended outcome

After `cs init` or `cs update` on a kernel carrying this change, a fresh interactive session on
Claude Code, Codex or OpenCode can orient and perform the requested read through the clone's
files and CLI, with no MCP connection or technical hint from the operator. It knows three
routes: company rules in `company/`, operating workflows in the canonical skill tree, and
remote systems in the engine catalog. The initial orientation is compact; full relevant
instructions and operation details are loaded when the task requires them.

Asked to load company procedures into memory, it reads the authoritative instructions into
the current conversation, identifies what it read and any missing or unreadable sources,
and can answer a concrete question from those instructions. It neither republishes nor
persists anything merely because the operator said "load into memory". An unavailable engine
does not prevent loading authored local rules.

Before declaring a system unavailable it reads the engine's catalog and `cs config`, reports
the state the engine gives and names the `cs rpc` route. It concludes no absence from an
incomplete catalog. The separately developed remote MCP interface is an additional access
path, not a prerequisite of this acceptance or a second authority for company rules.

## Dependency on the engine

The engine owns the catalog. Its contract is the engine brief, `mrcall-desktop`
`docs/briefs/2026-10-08-system-catalog.md`; the cross-repository decision is the meta-repository's
`docs/briefs/2026-10-08-capability-discovery.md`. The kernel holds no copy of the list. It depends
on one method, `system.catalog`, which `system.capabilities` advertises as `system_catalog: 1`:

- **Two forms.** With no parameter: the result `version`, one compact row per external system,
  the internal engine areas' identifiers and the profile served. With a system or area id: its
  operations, each with method, summary, required and optional parameter names and effect.
- **Four states**, each with a fixed safe sentence and, where the engine holds one, the account.
  `connected`: the engine records that the system worked, with no live check. `not_configured`:
  it holds no configuration for it. `denied`: it holds a recorded refusal. `unverified`:
  everything else. A system the engine does not have is not in the list, and neither is one
  reachable only inside the engine's own chat: the list covers JSON-RPC methods.
- **Effect declarations.** Five flags per method: it changes state, contacts an external
  provider, is paid (it can spend the engine's model budget or its telephony credits), is
  destructive, or returns a secret (its result can carry a credential, token or key in clear).
- **A read and nothing else.** Building the catalog sends no provider request, activates and
  writes nothing, and puts no secret in any field.
- **An unknown contract** is a `system_catalog` value or a result `version` other than `1`.

**Gate.** The engine milestone that delivers the catalog and freezes this interface passes its
integration review before the kernel's native acceptance starts. Skill text that names a catalog
field is final only against the frozen interface.

## Scope and ownership

- **`cs/templates/project/.claude/skills/cs-capabilities/SKILL.md.j2`**, new. Every file of the
  skill is a `.j2`; a supporting file follows "Supporting files" in
  [agent-skills.md](../agent-skills.md) on the branch this work is stacked on.
- **`cs/templates/project/.claude/skills/cs-instructions/SKILL.md.j2`**: an explicit
  explanation-only stop before the teaching steps. An agent may correctly load
  this workflow directly without loading the bootstrap body. Its explanation
  reads the canonical body, describes the existing teaching procedure and
  performs no session-note discovery, persistence, Git inspection or publication.
  The actual teaching/amendment/retirement procedure and permissions stay the same.
- **`cs/templates/project/AGENTS.md.j2`**: one sentence routing to the skill, in § 1 beside the
  existing pointer for other systems (`:118-121`), and the skill's name in § 4's list of
  interactive skills (`:155-159`). § 10 stays the last section.
- **`cs/templates/project/.claude/skills/cs-help/SKILL.md.j2`**: a row in the skills table
  (`:27-35`), one example under "Or just ask" (`:39-48`), and the skill's name in the sentence
  listing the skills that fire on their own (`:50-53`).
- **`cs/cli.py`**: the dispatcher's `except` clause (`:2650-2651`).
- **Tests.** `tests/test_template_render.py`, `tests/test_agent_surfaces.py` and
  `tests/test_stamped_surfaces.py` for the new skill and the charter sentences; a new contract
  test for the skill, wired into `tests/run.sh`; fresh-interpreter cases in
  `tests/test_engine_unreachable.py`; a native driver like `tests/live_instructions_skill.py`.
- **Documents.** A section in `docs/agent-skills.md`; `docs/active-context.md`; `docs/README.md`.

**No `cs` verb, no entry in `.claude/settings.json.j2`, no token in `bin/cs_operator_cron.sh.j2`
and no manifest field is added.** A verb would answer a question the engine answers, and:

- `cs rpc` is allowed in the four canonical spellings (`settings.json.j2:93-96`) and allow rules
  match by prefix, so Claude Code runs `cs rpc system.catalog` without a prompt today.
- A verb that runs without a prompt needs four allow spellings. The scheduled run uses the same
  allow list (`cs/operator_recovery.py:58-71`), so keeping the verb out of it needs six deny
  spellings and an entry in the deny-enumeration gate (gate 17, `tests/run.sh:465-473`).
- A changed permission file overwrites each clone's copy (`cs/project_update.py:154, 754-765`)
  and puts the release on the `FULL` re-verification tier on both clones (`AGENTS.md:134-142`).

## Required behavior

**The description carries the trigger by itself.** It says: consult this skill at the start of
interactive work, when asked to load or recall company procedures or operating instructions,
and always before telling the operator that a system, account, connector or integration is
unavailable, because those are connected to the engine and do not appear among the agent
host's own tools. It names categories of systems and no vendor. This is the same
`cs-capabilities` workflow; no second bootstrap skill or verb is introduced.

**A known route before transport exploration.** The body distinguishes company rules,
kernel skill procedures and remote capabilities. For a request to load company procedures,
read `company/README.md`, then the complete `company/customer-service-playbook.md` and
applicable mailbox identity file. The default is `company/mailbox-identity.md`; another
mailbox's `company/mailboxes/<email>.md` is read only for an explicitly selected mailbox
without its own clone. Read applicable supporting company guidance and referenced local
prose needed by the requested task. Kernel workflows remain in their canonical skill files:
select and read the relevant body before performing that workflow, without loading every
skill into the initial context. A list of filenames or skill descriptions is not a body read.

Use direct file reads for these known locations. Neither `cs rpc --help`, source searches,
trial RPC names nor catalog calls are prerequisites for reading local instructions. Finish
a local-only request even when the engine is absent, older than the catalog or unreachable.
The catalog sequence below is used for remote capability questions, not as a gate on local
procedure reads. Tool-approval refusals are respected and reported.

**Report actual coverage.** Distinguish authored rules, an unwritten template slot (the
`## What to write here` marker), a missing file and an unreadable file. An unwritten slot
teaches no company policy. Read long files in complete bounded chunks; truncated output is
incomplete coverage until the remaining content is read. Name the loaded sources and give a
brief content-grounded account of the rules relevant to the task. A missing local file is
not evidence that the company has no rules anywhere. Report that local gap; do not invent,
silently replace it with an engine mirror, or claim knowledge of an unread source.

Loading context authorizes no file edit, publication, Git commit, personal-memory write or
customer action. A request to teach, amend or retire a standing rule still routes to
`cs-instructions`. Existing company-file authority and the engine's derived copy remain as
the charter defines them. A loaded rule cannot widen permissions or bypass another skill's
approval, send or dossier boundary.

**Direct workflow explanations use the same read-only boundary.** A question
about how to teach a future rule may enter `cs-instructions` directly. That body
must stop before its edit/publication steps for an explanation-only request;
routine session bookkeeping is not part of that explanation. Acceptance checks
the requested canonical workflow body, not redundant loading of `cs-capabilities`.

**The body states what is read and what each read can show.** The engine's catalog lists what
the engine's JSON-RPC surface reaches, and nothing reachable only inside the engine's own chat.
The workspace's own integrations and the settings in force show in `cs config`. The agent host's
tools are the host's; this workspace does not manage them. The verb list is `cs --help`, which
the stamped permission file does not allow, so the skill names it and makes it no step. The
catalog and `cs config` are read before a system is called unavailable; the answer names both.

**The engine is read in a fixed order.** `cs rpc system.capabilities` first, then
`cs rpc system.catalog` only when `system_catalog` equals `1`, the summary first and one system's
operations on demand; any operation is called as `cs rpc <method> '<json>'`. Equality with `1` is
the kernel's negotiation rule (`cs/rpc.py:348`, `:370`), and reading the key first keeps a
traceback out of the ordinary path. The default profile is asked, another only when named.

**The body maps what the reads give to what the operator is told.**

| The reads give | The operator is told |
|---|---|
| The system, `connected` | The engine records that it worked, at its last use or in a session live now, without a live check; it is called through the engine by `cs rpc`, for the account the engine names |
| The system, `not_configured` | The engine has it and it is not set up for this profile |
| The system, `denied` | The engine has it and holds a recorded refusal: the credential was rejected, the connection was suspended or its session expired, in the engine's own sentence |
| The system, `unverified` | The engine has it; whether it works could not be verified |
| A catalog without the system | This engine's catalog does not list it. The catalog covers the engine's RPC operations; this workspace's own integrations are read with `cs config`, and the host's tools are separate |
| No `system_catalog` key in `system.capabilities`, or "method not found" for either call | This engine is older than the catalog; its systems cannot be listed from here, and absence is not concluded |
| A `system_catalog` value other than `1`, or a result `version` other than `1` | The catalog follows a contract this skill does not know; the systems cannot be listed reliably from here, and absence is not concluded |
| A catalog read that fails for any other reason, such as an unreachable engine | The catalog could not be read; neither presence nor absence is concluded |

For incomplete or unknown catalog evidence, the answer begins with the actual
uncertainty. It does not answer a reachability question with a categorical "no"
and then try to repair that conclusion with a later caveat.

**The limits are stated and widen nothing.** Discovery calls `system.capabilities` and
`system.catalog` and no other operation. Every other operation the catalog lists is called only
on the operator's explicit request in the session, with its declared effect stated first. An
operation that connects, tests, syncs or sets up a system is never part of discovery.

**The body states what the session may do, as three facts.** The engine admits the profile owner
to every operation it lists and sets no per-operation limit, so the declared effect is what tells
a plain read from the rest. On Claude Code the clone's `.claude/settings.json` decides what runs
unprompted, and as stamped it allows `cs rpc`; a scheduled session is bounded by the launcher
that starts it (`AGENTS.md.j2:166-176`). Codex and OpenCode follow their own configuration.

**Interactive sessions only, at instruction level.** The description and the body confine the
skill to a session with a human present. No permission rule enforces it.

**The dispatcher.** A verb that fails before the first engine connection, with an exception other
than `ConfigError`, ends today in a second traceback, `AttributeError: module 'websockets' has no
attribute 'exceptions'`; a malformed JSON argument to `cs rpc` shows it. After the fix such a
failure ends with its own exception, unless it is a connection, name-resolution or timeout error,
which prints the unreachable-engine message. Exit status is 1 before and after.

## Constraints

- **A changed template does not reach a clone file that was edited.** `cs update` asks and
  defaults to the local file (`cs/project_update.py:766-796`); a new file always lands
  (`:803-808`). One maintained clone edits its `AGENTS.md` and its `cs-help`.
- **The charter and a description have size budgets.** Codex 0.161.0 keeps the first 32,768
  bytes of a clone's `AGENTS.md` and about the first 1,024 characters of a skill description
  (`codex debug prompt-input` on a rendered clone). At the released tag a rendered charter is
  about 20,500 bytes and the longest description about 430 characters.
- **The charter is an index**: "it routes, it does not teach" (`AGENTS.md.j2:36-37`). Its § 10
  stays the last section, which the memory-map gate assumes (gate 48, `tests/run.sh:1181-1185`).
- **One command per job, and the engine is authoritative for what it owns**
  ([kernel charter](../kernel-charter.md), `:119-123`, `:77-90`). No list of systems is in `cs/`.
- **Every skill change is verified on Claude Code, Codex and OpenCode in the same change**
  (`docs/agent-skills.md:11-28`); `.claude/skills/` is the one rendered surface.
- **The re-verification tier follows what the release touches** (`AGENTS.md:134-142`).

## Release classification

The next release carrying this change is a MINOR: a new stamped operator workflow
(`AGENTS.md:129-132`; precedent `CHANGELOG.md:86-89`). Its re-verification tier is `read` on both
maintained clones. The stamped part alone is `static`. The `cs/cli.py` fix raises the tier: it
changes what a verb prints when it fails before connecting, which no render shows. The clause
wraps every verb, send verbs included. The tier stays below `FULL` because the clause acts only
after a verb has raised: exit status is 1 before and after, no send code runs differently, and
`cs/auth.py` and the permission surface are untouched.

## Acceptance

Each item names what the gates of `tests/run.sh` and the native runs prove. A native run is a
fresh session wired to a loopback fixture that runs the engine's own `system.catalog` handler at
the frozen commit, admits `system.capabilities` and `system.catalog` and records every request.
For items 1, 3 and 6 the clone is rendered from the base, its `AGENTS.md` and `cs-help` are then
edited by hand, and a real `cs update` with closed standard input upgrades it to the candidate:
it holds the new skill and neither the charter sentences nor the `cs-help` lines, so the
description works alone. The clone carries a working `.venv/bin/python -m cs`, and the prompt is
the operator's question: it names no skill, command, engine, `cs` or catalog. Loading and calling
are taken from host events and the request log (`tests/live_instructions_skill.py:286-306`),
never from the agent's own sentence (`tests/test_live_instructions_fixture.py:11-14`).

1. **Discovers without a hint.** Gates: the skill renders in all three account shapes, is
   byte-identical on the three host paths and in the copy fallback, and a real `cs update` adds
   it to a clone whose `AGENTS.md` and `cs-help` are edited, keeping both. Native, on each host,
   two cases: asked whether the company's bank account is reachable and what can be read, with no
   vendor named; and asked only whether it has the bank connector, by the name the catalog gives
   it. In both the session loads the skill and the request log shows `system.catalog`. Host
   events show, in the whole run, no search or read of source code, of tests, of any file
   outside the clone or of the web. A read or a listing of the clone's own stamped guidance —
   `AGENTS.md`, a skill, a `company/` file — is recorded and does not fail the case: the base
   charter itself sends a session to `company/claude-extra.md` for other systems. The clone
   holds only what the render, the two edits, the update and the launcher put there: its
   `company/` files are the stamped slots, and neither they nor the two edits name the bank
   system, the skill or the catalog.
2. **Four distinctions.** Gates: the rendered skill gives a distinct sentence for each of the
   four states, for a system the catalog does not list, for an engine without the capability
   key, for an unknown contract version and for a catalog that could not be read. Native: against
   a handler whose `system.capabilities` lacks the key the answer is "cannot be listed" and
   claims no absence. Driving a system through the four states is the engine's test.
3. **Planes not confused.** Gates: the rendered skill says what each of the three reads can show
   and gives the call route; it requires the catalog and `cs config` to be read before a system
   is called unavailable, and the answer to name what was read. Native: the answer attributes the
   bank system to the engine and gives the `cs rpc` route.
4. **Activates nothing, exposes nothing, widens nothing.** Native: the provider stub records no
   request, the request log holds only the two admitted methods, and a fixture secret appears in
   no transcript. Gates: the rendered `.claude/settings.json` and `bin/cs_operator_cron.sh` are
   byte-identical to renders of the base with the same variables.
5. **Reflects the real system.** Gates: the rendered skill names no vendor, and no stamped file
   lists the engine's systems. Native: the older-engine run of item 2.
6. **Representative proof.** Native: the run ends with the agent naming a valid read operation
   of the bank system, its required parameters and the `cs rpc` route, and the request log shows
   no call to that system's data operations.
7. **The scheduled run's skills and permission files are byte-identical.** Gates: the rendered
   `cs-operator`, `cs-triage-mail` and `cs-campaign-tick` skills equal the base, and item 4's two
   files show no permission entry added or removed. Native, on Claude Code only, the scheduled
   runtime: a session whose prompt states a scheduled context and names a system (model:
   `tests/live_instructions_skill.py:374`) does not load the skill and sends no engine request.
8. **The dispatcher.** Gates, each in a fresh interpreter: a malformed JSON argument to `cs rpc`
   ends with its own exception and not with `AttributeError`; a connection or timeout error
   raised before any engine connection, and an unreachable engine, each exit 1 with the
   unreachable-engine message: no traceback, the engine address and the application named.
9. **The workspace's own capabilities.** Gates: the rendered skill names `cs config` as the read
   for the workspace's integrations and settings, and `cs --help` as the verb list, not a step.
10. **The session's effective authorizations.** Gates: the rendered skill states the three facts
    about what the session may do and the limit that discovery calls the two methods only.
11. `bash tests/run.sh` reports all gates green.
12. **Loads and uses procedures without MCP.** Native on all three hosts, with fresh
    sessions, no configured MCP server and no instruction in the prompt naming a skill,
    file, command, catalog or engine. These are separate fixtures from the bank cases;
    their authored company files contain no catalog answer.
    - Authored rules: the operator asks in ordinary Italian to load company procedures
      and answer a concrete policy question. The fixture has a playbook long enough to
      exercise bounded reads, a rule near its beginning and a different rule near its
      end, plus a mailbox voice rule. Host tool results establish complete reads of the
      playbook and identity, and the answer correctly uses all three fixture rules and
      names their sources. A claim to have read them is insufficient.
    - Incomplete rules: a missing playbook, an unwritten identity slot and an unreadable
      referenced local source are reported separately. No template instructions become
      company policy, no contents of the unreadable source are invented, and no absence
      of company policy outside the clone is inferred. The readable guidance is still
      loaded. The fixture controls the unreadable condition independently of Unix mode
      bits so a privileged host cannot accidentally turn it into a readable file.
    - Workflow route: asked how to teach a future recurring rule, explicitly for an
      explanation only, the session reads the relevant canonical workflow body and
      explains the actual route without editing or publishing anything. This distinguishes
      loading procedures from invoking their mutation steps.
    In all three cases the engine is unreachable and the requested local work completes.
    The transcripts contain no help-tree exploration, source/test/web search, trial RPC
    call, or read outside the clone. Fixture file hashes and Git state remain unchanged;
    there are no publication, personal-memory-write or customer-action calls. A model
    start failure, refusal before considering the task, or empty answer is not a pass.

For item 12 a read through any canonical host skill path counts when it resolves to the
same rendered bytes. Verification preserves failed attempts and names the actual coverage;
static routing checks alone do not satisfy native acceptance. Model-based acceptance uses
the developer's existing host accounts and isolated synthetic data, never a maintained clone.

## Exclusions

- No release, tag, push, clone upgrade or engine deployment.
- No change to the scheduled run's skills, wrapper or permission file.
- **A scheduled session can read the catalog, and this work adds no permission rule against
  it.** It loads the skill's row and the charter sentences like any session. Once a clone's
  engine serves the catalog it can read the name and parameters of every engine operation, those
  its wrapper does not deny included, through the already allowed `cs rpc`
  (`settings.json.j2:93-96`); the wrapper denies neither method
  (`bin/cs_operator_cron.sh.j2:109-224`).
- No verb or wrapper for an individual system, and no kernel-side list of systems.
- No MCP requirement, implementation or configuration change. Remote MCP delivery and
  its own authentication and client acceptance remain in their separate workstream.
- No migration of company-rule authority, engine-mirror fallback, eager loading of all
  skills, or automatic publication/persistence from a request to load session context.
- **Outside this work, as facts.** The scheduled run shares the interactive allow list and its
  wrapper denies eleven methods by name. No gate compares that list with the engine, so by the
  text of the files a scheduled run may call any other engine method. The scheduled triage skill
  runs `cs assignment status` (`cs-triage-mail/SKILL.md.j2:106`), which the allow list lacks.

## Assumptions and prerequisites

- **Standalone clones.** The operator clarified that clones do not need
  ai-kit. Native acceptance therefore uses the clone's own instructions and
  permissions without ai-kit hook injection. Preserve the existing host
  account, authentication and non-kit controls, including the send gate; do
  not disable all hooks or relax permissions. For Claude, a session-scoped
  settings overlay may copy the current user settings and remove only
  explicitly identified ai-kit hook entries, while loading project/local
  settings normally. Record the exact filtered entries, unchanged permissions
  and non-kit hooks, settings hashes and actual effective hook behavior.
  Never modify the installed kit or global user settings for the test. This
  is a stated acceptance configuration, not proof of operation with ai-kit
  enabled or of configuration changes in maintained clones. All nineteen
  cases must use one frozen host/runtime candidate and documented configuration.
  The post-capture auditor is frozen and hashed separately. An audit-only repair
  may replace dependent audit verdicts by actually rechecking retained complete
  observations, provided exact hashes prove that host-consumed source, templates,
  fixture construction, prompts, launchers, profiles, model configuration and
  engine dependencies are unchanged. Preserve each original source manifest,
  raw capture, process exit, fixture/configuration comparison and teardown
  evidence; bind every replacement verdict to the current auditor manifest and
  replay output. Independent review must verify this dependency proof before
  acceptance. Do not describe retained observations as fresh native runs.
  In a test module containing both launch/fixture code and audit code, a repair
  may change only explicitly identified post-capture function blocks. Preserve
  exact bytes of every other block, imports and module initialization; prove
  the changed blocks cannot affect launching, construction, serving or host
  inputs. New helpers must be pure post-capture definitions with no new startup
  effects. Freeze and retain both the complete file manifests and this block
  partition proof. A filename alone cannot establish an audit-only dependency.
  All nineteen cases remain required on that same frozen runtime; missing cases
  and genuine rejected behavior require separate fresh attempts. Runtime or
  configuration drift invalidates dependent observations. Privacy, complete
  read coverage, tool boundaries and semantic acceptance are unchanged.
- **Stacking.** This branch is rebased onto `feat/legal-research-skill` before implementation.
  Both edit the stamped `AGENTS.md` and `cs-help`, and that branch records the rule that every
  file of a stamped skill is a `.j2`. The base named in the acceptance is that branch's tip; its
  permission file and cron wrapper equal `v0.51.0`.
- Hosted engines carry the catalog only after a separately authorized engine release; until then
  their clones report "cannot be listed".

## Open for the plan

- **How the native driver finds the engine checkout.** The existing driver assumes sibling
  repositories (`tests/live_instructions_skill.py:19`); this work runs in worktrees.
- **The catalog field names the skill quotes** are final only against the engine's frozen
  interface.
