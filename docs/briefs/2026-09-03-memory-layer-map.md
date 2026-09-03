# The memory layer map — brief

## Problem

The memory layer works in `mrcall-cs` because one operator holds it in his
head. Nothing carries it to the next clone. That is the driver: the same
mechanism has to exist, legible, in every `<company>-cs` clone, and the only
place that can put it there is the kernel.

The evidence that head-knowledge is the current medium: an operator asked to
explain "how we handle memory here" to a second agent, and the honest answer
could not be pointed at. It had to be assembled by hand, and the version the
operator arrived with was three stores, one of them misdescribed.

Whether the current `mrcall-cs` handling is itself well done is explicitly out
of this brief's scope: the map is the precondition for that audit, because a
set that cannot be enumerated cannot be audited.

The kernel already teaches the memory *doctrine*. It does not anywhere state
the memory *map*. Those are different artifacts, and only the first one exists:

- `CLAUDE.md.j2:213` § 9 gives the read order for a fact — engine memory, then
  Sent-mail precedent, then the `docs/projects/` dossier — and the included
  `outbound-fact-sourcing.md.j2` partial makes it bind for any outbound fact,
  not only entity facts.
- `CLAUDE.md.j2:88-92` names `USER_NOTES` and calls it the biggest per-company
  artifact, in the section about where the machinery is written down.
- `CLAUDE.md.j2:178` names the SQLite ledger in a Conventions bullet, beside
  config layering and autonomy knobs.
- `CLAUDE.md.j2:76` and `:160` establish that dedup ground truth is Gmail's own
  Sent/All Mail, never the engine archive.

A reader who wants the whole picture must visit four unrelated sections and
infer that they describe one system. Nothing states what counts as a store,
how many there are, which is authoritative for what, or which verb writes to
each. The result is predictable: the set gets reconstructed from whichever
sections were read, and the reconstruction is wrong in a way that reads as
confident.

Three defects sit underneath, and they are separable.

**The set has no membership rule, so it cannot be enumerated.** § 9 discusses
two stores because it answers a question about facts. `USER_NOTES` appears
under machinery. The ledger appears under Conventions. None of them is wrong;
none is a map, and without a stated rule for what belongs in the map, any
enumeration is taste. A reader cannot tell from any of them whether the set is
complete.

**Two axes are routinely collapsed into one.** *What do we know* and *does
this message exist* are answered by different systems, and the charter already
keeps them apart — the engine owns the first, Gmail's own Sent/All Mail owns
the second, across every mailbox in scope. `cmd_contacted` states it in its
own first line: "DEDUP TRUTH = Gmail's own Sent folder (IMAP), NOT the engine"
(`cs/cli.py:233`). But the separation is stated in prose, in two places, and
never as structure — and the collapse is easy to make, because `cs contacted`
and `cs history` sound like ledger queries while neither reads the ledger at
all: both go to Gmail over IMAP.

**One store is absent from the kernel entirely.** Claude Code keeps a
per-user, per-machine store at `~/.claude/projects/<encoded-path>/memory/`. It
is not in git, not shared with the team, not portable between machines.
Grepping `cs/`, `docs/` and `AGENTS.md` for it returns nothing. The meta-repo
`hb/CLAUDE.md` carries a Memory discipline section governing it, but that file
is meta-repo-specific and no clone inherits it. Every `<company>-cs` clone
therefore ships an operator with a writable memory store its charter never
mentions — including the rule that matters most, that it is authoritative for
nothing that leaves the desk.

The third defect is the most dangerous. An unenumerated store still behaves
correctly when its own section is read. An ungoverned store accumulates
project knowledge on one developer's laptop, where it is invisible to the
team, absent from the next clone, and — because it is injected into context as
background — quotable by a future session as though the repo had said it.

## The membership rule

The rule comes first; the set falls out of it. A **memory store** is:

> a durable body of records — content that outlives any single run — that at
> least one kernel verb or stamped workflow step reads as input.

A **record** is a statement of what is the case or what happened. Four clauses
say what is therefore NOT a store, and they do the excluding, not taste:

- **No records, no store.** A location whose entire content is a credential or
  its own presence answers no question and is recreatable without information
  loss. This excludes the token and refresh caches
  (`cs/config.py:478-487`) and the `CS_PAUSE` flag (`cs/config.py:450-453`) —
  operational posture belongs to `cs config`'s question, not to the map.
- **A setting is not a record.** A declared value has a declaring layer, a
  precedence chain and an env override; it says how this operator is
  configured, not what is the case. This excludes `manifest.toml` and the
  accounts registry (`CS_ACCOUNTS` → `settings.account_map`,
  `cs/cli.py:1414-1425`), and it is the same distinction that keeps `cs
  config` and `cs memory` two verbs rather than one: every row `cs config`
  prints carries a provenance that no store row has.
- **A description is not a record.** A file that describes a system whose
  ground truth lies elsewhere is not authoritative for its own content: when
  the two disagree, the thing described wins and the file is simply wrong.
  This excludes the clone's `docs/ARCHITECTURE.md` and `README.md`
  (`CLAUDE.md.j2:84-86` routes readers to them, and the code is the truth they
  describe), the stamped `.claude/skills/*` and the charter, which `cs update`
  re-renders from kernel templates — losing them costs nothing. It is the
  clause that does the real work, because the excluded files and four admitted
  stores — `USER_NOTES`, `company/*.md`, the dossiers, the packs — are all
  authored prose. What separates them is authority, the same column the map
  is built on: nothing else holds `USER_NOTES` or a dossier, so losing one
  loses information, while an architecture doc can be rewritten from the code
  it describes. *How to act* is not the test — `USER_NOTES` is policy and is a
  store, because the engine composes from it and no other copy of it exists.
- **Queues are not stores.** A location whose items exist to be consumed by
  the next action is work-in-flight, and its durable trace lands in a real
  store. This excludes Gmail Drafts: a draft ends as a Sent record (store) or
  a discard (nothing), and dedup deliberately reads Sent, never Drafts.

The clauses sort whole bodies, not files. A store is classified by the
question its body answers; a `campaigns/<pack>/` holding send templates and a
`builders.py` beside its status and dates is one store answering *what did
this campaign say and how did it go*, not three fragments to sort separately.

Applied to the running system, the rule admits **ten** stores. Four of them
are admissions the rule forces and prose habit would have skipped: Gmail
Sent/All Mail is a store, not an annotation — `cs contacted`, `cs history` and
the pre-send dedup check source decisions from it; `campaigns/` pack content
is a store — `cs campaign packs` exists precisely so "have we ever done
something like this?" is answered by reading the packs
(`cs/campaign_pack.py:1-12`); the operator log is a store — `cs review`
reads its tail as evidence (`cs/review.py:49-54`) and `cs cron status` reads
the last tick from it (`cs/cron.py:191`); and `template-manifest.json` is a
store — `cs init` writes it (`cs/project_init.py:1324-1334`) and `cs update`
reads it (`cs/project_update.py:103`) to learn which stamped files the
operator has hand-edited. The count is a consequence of the rule, never a
constant to defend: an eleventh store that satisfies the rule joins the map,
and the gate below asserts agreement, not a number.

## The constraint that shapes the fix

The charter cannot absorb the map as prose, and not because of any one
clone's line budget. The budgets are clone-local: `mrcall-cs` declares
`index_max_lines = 221` and renders `CLAUDE.md` at 247, with the mechanical
gate failing on it today; the 124 clone (`mario124-cs`) renders 198 lines and
declares no budget at all — it has no `docs/.doc-profile`. What is
kernel-shaped about the objection is staleness: the content that matters most
— resolved paths, endpoints, reachability — is per-clone
(`~/.<slug>-cs/cs.db`, `cs/config.py:463`) and per-machine (the engine behind
its RPC endpoint; the CC memory directory keyed by an encoded repo path), and
whether each store is reachable is runtime state, not a documentable constant.
A rendered snapshot of any of it is a claim about the day it was stamped.

This is the same shape as the configuration problem, and the kernel has
already solved that one. `cs/config_report.py:1-11` records why: two
consecutive headless ticks on 2026-08-23 concluded the operator was in `draft`
mode because no `CS_TRIAGE_MODE` environment variable existed, while
`manifest.toml` declared `send` and `config.load()` returned `send`. Neither
tick read the manifest. The conclusion drawn there is the one that applies
here — *the kernel answers the question itself instead of leaving it to be
re-derived* — and `CLAUDE.md.j2:177` now spends a single clause on it: "only
`cs config` resolves the layers."

## Decision

Ship the map as a verb, and spend a few lines of charter prose on the rule and
the boundary the verb cannot enforce.

**1. A new read-only verb, `cs memory`, prints the store map.** For each store
it reports what it is authoritative for, the surface that reads it, the
surface that writes it, its resolved location on this machine (a path, an
IMAP mailbox, or an RPC endpoint), and presence or reachability where that is
checkable — in the shape `cs config` already uses for secrets: present or
absent, never contents.

The authority split is the payload:

| Store | Authoritative for | Read | Write |
|---|---|---|---|
| Engine memory — behind the engine RPC endpoint | Entity memory, synced mail, the task ledger, reply and auto-reply classification, the trained voice. *What a message IS.* Primary and live. | `cs ask` — empty tool set, cannot write memory (`cs/cli.py:1153`) | `cs chat --allow create_memory,update_memory` — approval-gated (`cs/rpc.py:272`), denied on the cron in twelve spellings (`cs_operator_cron.sh.j2:100-111`) |
| `USER_NOTES` on the engine profile | Outreach and reply policy: declared-AI identity, signature, recipient-language rule, the LLM-ism ban list. The biggest per-company artifact (`CLAUDE.md.j2:88-92`). | `cs rpc settings.get` | `cs rpc settings.update` — its own six-spelling cron deny block (`cs_operator_cron.sh.j2:118-123`) |
| Gmail Sent/All Mail, per mailbox in scope | *Does this message exist* — dedup ground truth, across every mailbox (`CLAUDE.md.j2:76`, `:160`). Never "what we know". | `cs contacted` (one mailbox, one window), `cs history` (every mailbox, unbounded), the pre-send dedup check — all over IMAP, none touching the ledger | every real send, including hand-sent mail — which is exactly why it is the ground truth |
| SQLite ledger, `~/.<slug>-cs/cs.db` (`cs/state.py:1`) | Its own records only: suppression, the dedup window, and the two records the mailbox cannot hold — `handled` and `escalated`. Out-of-band process records that gate sends, not knowledge. | `cs plan`, `cs dossier`, `cs review`, `cs unanswered`, the campaign runner (`State(settings.db_path)`, nine call sites) | `cs handled`, `cs escalated`, `--commit` |
| `company/*.md`, in git, clone-owned | Company facts and any other system this identity may reach (`CLAUDE.md.j2:93-96`). | the files | the operator, via git |
| Dossiers, `docs/projects/<name>/`, in git | History and judgement about a project (`docs/projects/README.md.j2`). Secondary — never "what we know" on its own. | the files, `/cs-customer` | `cs project new`, then the operator via git |
| Campaign packs, `campaigns/<pack>/`, in git, clone-owned | What each campaign is, says, and its status and dates — the record that answers "have we done something like this?" (`cs/campaign_pack.py:1-12`). Content only; the runner is kernel code. | `cs campaign packs`, the campaign runner | the operator, via git (copy-and-edit) |
| Operator log, `~/.<slug>-cs/cs_operator.log` (`cs/config.py:456-457`) | What the operator process did and when. Never anything about a contact. | `cs review` (tail, as evidence), `cs cron status` (last tick) | the cron wrapper, append-only |
| `template-manifest.json`, clone root | How this clone was built: which kernel template rendered each stamped file, at which checksum, and the kernel version `cs init` froze. Never anything about a contact. | `cs update`, to name every stamped file the operator has hand-edited (`cs/project_update.py:103`) | `cs init` (`cs/project_init.py:1324-1334`), `cs update`, `cs update --pin` |
| Claude Code memory, `~/.claude/projects/<encoded>/memory/` | **Nothing that leaves this desk.** Working style and per-developer preference only. Per-user, per-machine, not in git, not portable. | injected into every session's context — which is exactly why it must be governed | the local agent |

**2. The engine row reports an endpoint and a liveness verdict, never a
filesystem path.** The engine store lives under the engine service user's own
home on the engine host — a disk the kernel does not own and cannot see, and
`CLAUDE.md.j2:167` is explicit that only that copy is the truth. So the row
resolves the RPC endpoint the kernel actually uses — `engine_ws_url` plus
`/ws/<owner_uid>` (`cs/rpc.py:73-79`, manifest `[engine].ws_url`,
`cs/config.py:327`) — and probes it at connection level. `CS_ZYLCH_ROOT` plays
no part: it is the descriptor root (`cs/login.py:61-70`), where the desktop
app writes profile descriptors — it locates a login artifact, never the store,
and printing any local path here would report a stale copy as the store, the
exact error the charter forbids.

The probe is defined narrowly: a TCP connect to the endpoint host. No
WebSocket handshake, no token, no RPC method, no chat turn. "Reachable"
therefore means the endpoint accepts connections, not that this identity is
authorized — the authenticated proof is `cs whoami`, and the row says so.
With no `ws_url` configured, the row reports `UNKNOWN` naming the reason.
This is what lets `cs memory` answer on a machine that cannot yet
authenticate, which is the onboarding case it exists for.

**3. The charter states the rule and the boundary the verb cannot enforce.**
A short § 10: the membership rule, the names of the stores it admits, the
pointer to `cs memory`, and the Claude Code boundary — that layer is
authoritative for nothing that reaches a customer, so project knowledge goes
to the engine or to `docs/`, never there. Everything else the verb says
better.

## Scope

New section `## 10` in `cs/templates/project/CLAUDE.md.j2`, appended after
§ 9, currently the last section (`:213`, file ends at 226). **No section is
renumbered**: `cs-customer/SKILL.md.j2:35` and `docs/projects/README.md.j2:122`
cross-reference § 9 by number.

New module `cs/memory_report.py` and its verb registration, mirroring
`cs/config_report.py` and the `config` verb at `cs/cli.py:1931`.

**`cs/templates/project/.claude/settings.json.j2` gains the four `cs memory`
spellings** (gate 17's four-canonical rule; `cs config` occupies four entries
at `:9-12`, `cs ask` four at `:61-64`). The list carries no bare `cs:*`, so an
unlisted verb is not covered — it does hold a sub-verb wildcard (`cs rpc:*`,
`:89-92`) and one narrower-than-verb entry (`cs catchup --check`, `:25-28`).
An unlisted verb prompts interactively in a session and cannot run at all
headless; the headless case is the onboarding agent's case, so the spellings
ship with the verb.

**Gate 4's hand-maintained verb list** (`tests/run.sh:269`) gains `memory`.

**A gate asserts the verb's printed store set and § 10's named set agree** —
adding a store to one without the other fails. The gate compares identifiers
and carries no count literal: the rule is the invariant, the number is a
consequence.

Read-only, and structurally so. `cs memory` issues no RPC method call and
opens no engine session; its one network action is the connection-level probe
above. It prints no store contents — the discipline that keeps `cs config`
safe to paste into a cron transcript is the same here, and for a stronger
reason: the engine store holds customer PII.

No change to any write path. All ten stores already exist and every gated
write path stays exactly as gated. Introducing a second way to write memory is
the parallel-implementation failure the anti-fork charter exists to prevent.

No change to § 9, the `outbound-fact-sourcing.md.j2` partial, or the read
order for facts. This brief adds the map; the doctrine shipped on 2026-09-01
and is correct.

**Note on the charter file's name** (a note, not a dependency): a doc-harness
ownership decision is pending in `mrcall-cs`
(`docs/sessions/56a429a1-169a-4e73-8049-a189dc4a4ea0.md`) over whether the
clone charter stamps as `CLAUDE.md` or `AGENTS.md`. `mrcall-cs/AGENTS.md` is
already a symlink to `CLAUDE.md`, so the kernel-side edit target is the same
file either way; landing both changes in one tag is preferable, not required.

## Release cost

This is a **MINOR**: a new CLI surface (`AGENTS.md` § Versioning — a flag or
verb that did not exist is a MINOR even when the diff is small). And it
touches `.claude/settings.json.j2`, the permission surface, which sits on the
FULL re-collaudo trigger list: **the collaudo suite runs on BOTH clones —
`mrcall-cs` and `mario124-cs`.**

The order is `docs/release-procedure.md`'s, and it puts the push first
because a clone can only pin a published tag: release commit, immediate tag,
gates run AT the tag, sweep, push (Release 1-7). Each clone then takes the tag
via `cs update`, which applies the new `settings.json` regardless (local saved
as `*.local-bak`), and re-collaudos at the CHANGELOG's declared tier (Upgrade
1-6). What closes the release is the last step: the CHANGELOG operational-pin
marker moves only after BOTH clones have passed. A published tag never moves,
so a FULL run that fails is fixed forward in the next tag.

Two costs this carries, named rather than discovered later. `mario124-cs` is
pinned at `v0.35.0` (`docs/active-context.md:63`), so its FULL re-collaudo
crosses four tags of drift, not one. And § 10 adds fifteen to twenty lines —
an estimate from the content it must carry, not a measurement — to a
template that already renders 26 lines over `mrcall-cs`'s declared budget —
the gate there fails today and will keep failing until that clone's charter is
consolidated, which is its own work and not this brief's.

Rule of two, satisfied and named: both existing clones ship the identical
store machinery — every one of the ten is a kernel surface, a template
surface, or shared engine infrastructure, none is company variance — and both
carry `company/` and `docs/projects/` today. The intent this brief serves is
precisely that the next clone's operator gets the map without one person's
head as the medium.

## Rejected approaches

**Prose only, no verb.** Rejected on staleness and per-machine runtime state:
resolved paths and reachability are exactly what a stamped snapshot
misreports, and the line-budget situation is clone-local (one clone over its
own budget, the other with no budget at all), so prose could not even claim a
uniform home. This is the argument `config_report.py` already won.

**Extend `cs config` instead of adding a verb.** The strongest rejected
option, and the one this kernel's own "extend before you build" rule demands
be considered: `cs config` already resolves the state directory and already
prints a provenance table. Rejected on charter rule 6, "ONE command per job —
two answering the same question is a" defect (`AGENTS.md:129`). These are two
questions: `cs config` answers *what is this operator configured to do*, and
every row it prints is a setting with a declaring layer. A store is not a
setting, has no precedence chain, and is not overridable by an env var.
Folding them would make one verb answer two questions and make the
duplicate-declaration check meaningless over half its rows.

**Concrete paths written into the template.** Rejected on staleness, not on
the charter: rule 1 does bless the engine as shared infrastructure the kernel
drives, and the template already renders slug-templated state paths at `:178`
and `:181`. But the Claude Code path is keyed by an encoded repo path that
differs per machine and per checkout, and reachability is not renderable at
all. The verb resolves; the template names.

**Copy the meta-repo Memory discipline section into the kernel.** Rejected: it
governs the meta-repo's own hygiene, routes to `docs/` and sub-repo paths no
clone has, and is written for a tree of repositories rather than for an
operator. The one rule inside it that binds every clone — CC memory is
per-developer and authoritative for nothing shared — is small enough to state
directly, and is item 3 of the decision.

**A skill rather than a verb.** Rejected: skills resolve through
`.claude/skills` and `.agents/skills`, so a skill answers for Claude Code and
Codex but not for a shell, a cron transcript, or an operator at a terminal.
`cs config` is a verb for the same reason, and a verb is the only form a gate
can assert against.

**Make `cs memory` write too**, as a convenience wrapper over `cs chat --allow
update_memory`. Rejected twice over: it would put a second write surface on a
store the cron deliberately denies in twelve spellings, and the deny set
matches on the `chat` verb — a wrapper under a different verb name would walk
straight through it.

**A count-freezing gate.** Rejected: a gate over a number asserts taste, and
the number is not the invariant — the membership rule is. The gate that ships
asserts that the verb and the charter § 10 name the same set, which is the
rule's application made checkable.

## Acceptance

- `cs memory` exists, is registered beside `config`, and prints every store
  the membership rule admits — ten today — each with authority, read surface,
  write surface, resolved location, and presence or reachability where
  checkable.
- The engine row reports the resolved RPC endpoint and a connection-level
  liveness verdict. No filesystem path appears in it, and `CS_ZYLCH_ROOT` has
  no effect on it.
- The verb issues no RPC method call and opens no engine session; it runs to
  completion, with the engine row degraded honestly, on a machine that has no
  token cache and cannot authenticate.
- The two axes are visible in the authority column: the Gmail row owns
  existence and names `cs contacted` and `cs history`; the engine row owns
  classification; the ledger row claims neither verb.
- It prints no store contents and no PII; its output is safe to paste into a
  report or a cron transcript.
- The four `cs memory` spellings are in `.claude/settings.json.j2`, and the
  verb runs under a stamped clone's permission set without an interactive
  prompt, headless included.
- Template § 10 exists, is numbered 10, renumbers nothing, and carries no more
  than the membership rule, the store names, the pointer to `cs memory`, and
  the Claude Code boundary rule.
- The Claude Code store is named in the kernel for the first time, with its
  authority stated as none for anything that leaves the desk.
- A gate asserts that the store set printed by the verb and the set named in
  § 10 agree; the gate contains no count literal.
- Gate 4's verb list includes `memory`; `bash tests/run.sh` is green.
- The change ships as a MINOR tag whose CHANGELOG entry declares FULL
  re-collaudo on both clones, and the CHANGELOG operational-pin marker moves
  only after both clones have taken the tag and passed at that tier.
- The onboarding case that triggered this: an agent asked how memory works
  here runs one verb and gets the rule, the stores and the authority split,
  instead of assembling three stores from prose and getting one of them wrong.
