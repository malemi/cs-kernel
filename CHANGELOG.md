# Changelog — cs-kernel


Clones pin **tags only**. Every entry states which clones must re-collaudo
and at which tier (design brief §6.6: static / +live read-only / full).

**Current operational pin** (2026-08-27): **`v0.28.0` on both clones**.
Verified from inside each clone after the re-pin: `requirements.txt`,
`template-manifest.json` `init_data`, the ARCHITECTURE "Kernel pin" row and
`cs --version` all say `v0.28.0`; both `requirements.lock` files resolve the tag
to `76f6656`, and each lock was installed ALONE into a fresh `uv venv` —
resolving `cs-kernel 0.28.0` — rather than assumed to. The static + live
read-only collaudo the entry demands was run on both: `cs whoami` signs in on
each profile (`support@mrcall.ai`, `production@cafe124.it`), `cs config`
reports **no setting declared in more than one place** on either, and the
rendered `CLAUDE.md` was read on each to confirm it still interpolates that
clone's own identity rather than the other's. `.claude/skills/cs-triage-mail/
SKILL.md` § 2 carries the new heading ("Read the customer's own words before
you decide anything") on both, with no literal Jinja left in any of the three
re-rendered files. Nothing was written and nothing was sent.

**`124-cs`'s own git history had fallen four minor releases behind what was
actually installed and rendered on it.** Its last committed re-pin was
`v0.23.0`; `v0.24.0` through `v0.27.0` had each been applied and verified live
on the clone by earlier sessions — this file's own entries record the
collaudo — but the corresponding commits on the `124-cs` side were never made.
`cs --version` and every stamped file already agreed on `v0.27.0` before this
release touched anything, so nothing was lost; the gap is closed as its own
commit on `124-cs`, kept separate from the `v0.27.0 → v0.28.0` commit this
release owns, so the two are not laundered into one. `124-cs` also still
carries an unrelated, pre-existing uncommitted business-dossier edit; this
release does not touch it.

**The engine now carries `emails.needs_reply` and the paragraph this replaces
said it did not.** That claim was true when it was written and false by the next
morning, which is why it is corrected here rather than left to age: the deployed
checkout `/home/mrcalld/mrcall-desktop` is at `810d7a4`, all five
`zylch-server@` units are active, and
`cs rpc emails.needs_reply '{"thread_ids": []}'` answers
`{"threads": {}, "asked": 0, "note": null}` instead of `-32601 Method not
found`. Measured on the live host, not inferred from a git log. So `v0.26.0`'s
fourth section is no longer inert: `cs unanswered` gets real verdicts.

`cs update` clobbered NOTHING on either clone. `v0.27.0` changes exactly one
template, `CLAUDE.md.j2`, and `CLAUDE.md` matched its stored checksum on both
clones beforehand — so the render applied with no conflict prompt, and the two
`SECURITY_CRITICAL` files were never render targets at all.
`bin/cs_operator_cron.sh` and `.claude/settings.json` are byte-identical to
their pre-update copies on both; `mrcall-cs` keeps its clone-owned
`bin/mrcall_business.py` deny line and nothing needed restoring, and its
`ext/cs_operator_send_cron.sh` — the wrapper its live crontab actually runs, and
which the kernel does not own — is byte-identical too.

**`mrcall-cs`'s poisoned `docs/ARCHITECTURE.md` ledger entry is GONE**, after
five releases of reporting that file as locally modified. It was declined once
under `v0.21.0`, which recorded the stale template checksum; this run the clone's
content and the fresh render agreed, so `cs update` printed `already current` and
re-recorded the correct checksum. The file now matches its stored checksum, and
the next template change to it will produce a real prompt instead of a phantom
conflict. Its "Kernel pin" row is still hand-edited at re-pin — that is by
design for a row stamped from the manifest.

**`cs update` clobbered NOTHING this time, and the reason is worth writing
down rather than counting as luck.** `bin/cs_operator_cron.sh` is
`SECURITY_CRITICAL`, so its render is applied without asking and the local file
is kept as `*.local-bak` — which is how `mrcall-cs`'s clone-owned
`bin/mrcall_business.py` deny line has been lost at three previous re-pins. This
release does not change that template, so the file was never a render target;
it is byte-identical to its pre-update copy and still carries the deny line.
The other `SECURITY_CRITICAL` file, `.claude/settings.json`, WAS re-rendered on
both clones, and diffing each against its pre-update copy shows exactly the
fourteen added read-only allow entries and nothing removed. On `mrcall-cs`
`docs/ARCHITECTURE.md` still reports as locally modified against its stored
checksum (the poisoned-ledger case from `v0.21.0`), so its conflict prompt
resolved to keep-local under a closed stdin and its "Kernel pin" row was
edited by hand.

Two claims this re-pin found false in the paragraph it replaces, both worth
naming because they are the drift class the sweep exists to catch. The `v0.22.0`
marker said the derived claims "all say `v0.20.0`" — they did, and that was the
defect, not the verification: on **both** clones `template-manifest.json` and
the ARCHITECTURE row were still on `0.20.0` while `requirements.txt` said
`v0.22.0`. And both `requirements.lock` files still resolved `13a91f1`, which is
**`v0.19.0`**, not the `612b5d3` the marker claimed — the lock had gone stale
through two re-pins. All five claims are aligned on both clones now.

**`v0.20.0`'s tier is FULL and the suite WAS run**, on both clones: `whoami`,
`config` (zero duplicate declarations on each), `plan`, `unanswered`, `campaign
packs`, `campaign pending`, bare `handled`, bare `escalated`, a dry-run
`escalated` that wrote nothing, `draft-delete` without `--commit`, `review`,
plus `mrcall-cs`'s own 191-test extension suite. `cs update` clobbered
`mrcall-cs`'s clone-owned deny line for `bin/mrcall_business.py` again — the
known trap — and it was restored.

**`v0.19.0`'s tier is FULL and the suite was NOT run.** The operator waived
it. That is a real gap, recorded rather than dressed up: this tag changes send
capability and shipped without the collaudo its own entry demands. The
targeted checks that WERE made, on each clone's real manifest through the
installed kernel: `124-cs` — the clone the change had to not break — still
reports `sms_enabled = False` and `sms.send` still refuses with "[sms].enabled
is false"; `mrcall-cs` resolves to the same endpoint it always declared
explicitly; the pre-`v0.19.0` stamped shape (`enabled = true` with
`proxy_base = ""`) now resolves to the working endpoint instead of failing;
and an endpoint blanked in the env layer still trips the guard, with the new
wording. No live engine call was made, and no SMS was sent.

`v0.18.0`'s own static-tier evidence, unchanged: `cs config` resolves on both
clones with NO setting declared in more than one place, and on `124-cs` still
shows `~/124/.env.local` as layer 3 of six — the check that matters, because
the same audit proposed deleting the key that builds that layer. Across both
upgrades the `cs update` output held: `docs/ARCHITECTURE.md` applied
**silently** (`✓`, no prompt), `manifest.toml` and `requirements.txt` reported
as clone-owned and left alone, not one `company/` prompt, and **no
`! failed to render manifest.toml.j2`** even though neither clone's frozen
`init_data` carries the knob keys the template gained.

Both clones also had `v0.18.0`'s six dead fields deleted from their own
`manifest.toml`, with `posture_note` kept as a comment rather than destroyed:
on `mrcall-cs` that sentence is the only written explanation of why the two
Centralix campaigns are excluded. `mrcall-cs` keeps its explicit
`[sms].proxy_base` declaration, which now duplicates the kernel default —
left in place deliberately, since it is the mechanism for pointing one clone
at a different proxy.

**`mrcall-cs` is PAUSED and the pause was NOT cleared** — `cs config` still
reports `CS_PAUSE PRESENT` after the re-pin. It stopped itself on 2026-08-24
because `cs chat --allow send_draft` ignored the draft id it was given twice
and sent a different draft to a different recipient. The content that went out
was correct for the address that received it, so no customer got the wrong
mail, but the mechanism picks a draft on its own and nine drafts were sitting
in that mailbox. That is a live defect on a send path, untouched by this
release; resuming is the operator's decision and the pause file carries the
detail. `124-cs` is not paused.

**One overwrite cost content; `v0.17.0` is the fix.** `docs/ARCHITECTURE.md`
was template-owned with a last section hand-authored by the template's own
declaration ("This section is NOT stamped"). Taking the new render on `124-cs`
during the `v0.16.0` re-pin — the right call for the stamped table above it —
deleted 59 authored lines. They were restored from git the same session, then
migrated verbatim into `company/clone-notes.md` when `v0.17.0` removed the
section from the template. No clone file is half-generated any more.

**A skipped conflict is never offered again.** Answering `N` to
"modified locally AND template changed" still records today's render checksum
in `template-manifest.json`, so the next `cs update` compares equal, reports
nothing, and the clone keeps a stale file for ever with no further prompt.
Seen live on `mrcall-cs`: one `N`, and the follow-up run said `0 updated, 0
skipped, 0 added` on a file that was genuinely behind. Not fixed here — the
file was brought to the current render by hand. Real defect, open.

`v0.5.2` and every earlier tag mint the auth token from a locally-held
Firebase service-account credential (`firebase-sa.json`) that only the
vendor can issue — a new customer cannot complete onboarding on those tags
and must not be pointed at them; `v0.6.0` is the first tag a new customer
can install end to end.

## Unreleased

**MINOR, and a SECURITY BOUNDARY.** A clone can now name its own executables
in `manifest.toml` and have the cron wrapper deny them, in every command-text
spelling. It changes the permission surface and the cron wrapper — two of the
six triggers — so there is no lower tier available.
**Re-collaudo: FULL, both clones.**

### Fixed — a clone's own executables had no owned way to stay out of the tick

A clone may keep scripts in its repo that exist for one company and would mean
nothing in another. Some of them must be unreachable from the headless tick,
which reads untrusted inbound mail; until now the kernel offered no way to say
so, and the mother clone said it by hand-editing `bin/cs_operator_cron.sh` —
a `SECURITY_CRITICAL` stamped file, re-rendered from the template on every
`cs update`. That deny had been lost at three re-pins and re-applied by hand
each time, which `v0.30.0`'s divergence report finally surfaced as the one
true finding on that clone.

It was also a single spelling of many. The hand edit denied
`Bash(.venv/bin/python bin/mrcall_business.py:*)` and nothing else, while the
script itself is mode 0775 with a `#!/usr/bin/env python3` shebang — so
`bin/mrcall_business.py` and `./bin/mrcall_business.py` execute it with no
interpreter word at all and matched no rule. `python3 bin/…`, `python bin/…`
and the venv's `python3` matched nothing either. The script's own docstring
asserted the opposite ("the headless cs-operator can NEVER reach this file"),
and it does CRUD on phone assistants with an admin-resolved token that is
honoured cross-owner. That docstring's claim is now true for the first time,
and it is true for a general reason rather than a lucky one.

**The kernel owns the mechanism; the clone owns the data.** `[local_scripts]
cron_denied` in `manifest.toml` is a list of repo-relative paths, and
`bin/cs_operator_cron.sh.j2` expands each into fourteen deny entries: seven
ways to name an interpreter (none at all, the venv's `python` and `python3`,
a bare `python` and `python3`, `bash`, `sh`) times the two path forms a
command line uses (`bin/x`, `./bin/x`). The interpreter-less pair is the one
that matters most — a shebang plus the executable bit needs no interpreter
word — and it is the pair the hand edit never had. No filename of any clone
appears anywhere in this kernel: charter rule 2, a command that makes sense in
one clone only does not live in shared code.

**Declaring nothing is the normal case, and it renders the kernel's own list
byte for byte.** Most clones have no local executables; an absent or empty key
produces exactly the previous 52-entry argument list. The key is template-only
like `[surface]` and `[cron]`, read off the raw TOML at stamp time, and it is
re-read on every `cs update` rather than trusted from the freeze — so an
existing clone gets it by editing `manifest.toml` and running `cs update`,
with no `cs init` re-run and no hand edit to a stamped file ever again.

**What a deny list cannot do, stated rather than assumed.** A permission rule
matches the literal text of a command. An absolute path, a flag before the
script (`python3 -u bin/x`), a `cd` or `env` prefix, an interpreter not in the
seven, and anything wrapped in `sh -c '…'` all reach the same code through
text this list does not contain — as was already true of the `Bash(rm:*)`
entry and of the six `cs` spellings. This raises the cost of reaching a
surface by accident or by injected instruction; it is not a sandbox, and the
wrapper now says so in its own comments. A script that must be unreachable
whatever happens should not be executable by the user the tick runs as.

### Changed — gate 17 reads the render, not the template source

The wrapper's deny list is no longer a fixed text, so asserting on the `.j2`
would assert on Jinja rather than on what a clone receives. Gate 17 renders
the template through the kernel's own `build_jinja_env` and compares the
`--disallowed-tools` argument list for exact, order-preserving equality in two
scenarios: no local scripts declared (52 entries — the normal case, gated as a
first-class path, because a stray token there would reach every clone) and one
declared (66). The expansion is rebuilt independently inside the gate rather
than imported from the kernel, so the gate cannot agree with the template
about a wrong answer, and the sample path is invented (`bin/example_tool.py`)
so that no clone's data lives in a kernel fixture. Gate 42 covers the other
half end to end: a REAL `cs update` against a clone whose frozen `init_data`
predates the key, asserting all fourteen spellings land in the stamped
wrapper. `tests/run.sh`: 43 gates, `RESULT: all gates green`.

### Migration — the deny is GONE until the clone declares it

This is the one risky window and it is not optional reading. `cs update` will
overwrite `bin/cs_operator_cron.sh` (`SECURITY_CRITICAL`, applied without a
prompt), and with it the hand-edited line. If `manifest.toml` does not yet
carry the key, the clone re-pins to a wrapper that denies that executable in
**no** spelling at all — strictly worse than the one spelling it had. So on
the mother clone, add the key BEFORE running `cs update`:

```toml
[local_scripts]
cron_denied = ["bin/mrcall_business.py"]
```

Then `cs update`, then read the stamped `bin/cs_operator_cron.sh` and confirm
fourteen `bin/mrcall_business.py` entries are present. A clone with no local
executables needs no edit and sees no change.

## v0.31.0 — 2026-08-27

**MINOR**: `cs review`'s output shape changes, two CLI surfaces are new
(`cs catchup`, `cs cron status --json`), a new `manifest.toml` field decides
what language the stamped surfaces speak, and the cron wrapper's deny set grows
two verbs. It touches the review surface, the permission surface and the draft
path.
**Re-collaudo: FULL, both clones.**

### Fixed — a draft had no lifecycle, and `/cs-review` presented stale ones as ready

`cs review` enumerated two draft stores and annotated neither: Gmail Drafts as
a raw IMAP header listing, the engine's as an `owner_id + status='draft'`
filter. Neither reads the thread the draft answers, so a reply written for a
question the customer has since withdrawn — or already had answered another way
— was listed as ready to send. `/cs-triage-mail` could not correct it either:
its candidate feed (`cs unanswered`) drops a conversation the moment a real
message of ours follows the customer's last one, so a resolved-and-thanked
thread is, by construction, not a candidate anywhere.

`cs/draft_state.py` now gives every draft a verdict, computed at read time and
stored nowhere. Two signals are Gmail-anchored and cannot degrade — `overtaken`
(the contact wrote after the draft was composed) and `superseded` (we wrote to
them after it was composed) — and one is the engine's own reading of the
conversation, `settled`, via `emails.needs_reply`. A draft with no signal is
`ready`. The charter split holds: *does this message exist* → Gmail, *what kind
of message is it* → the engine; an engine that cannot be asked costs a note and
the two Gmail comparisons still fire.

One logical draft can exist twice — `cs draft-reply` has the engine compose and
mirrors the result into Gmail Drafts — so copies are paired by thread key plus
recipient and reported as ONE row carrying both handles, compared against the
EARLIER of the two timestamps. `cs review --json` carries `drafts[]` with the
verdict, the signal and its date; the digest prints two blocks, ready and
to-re-decide. The raw store listings stay in the JSON for the callers that
read them.

**Nothing is ever retired automatically.** Removing a draft destroys a prepared
answer no human has seen, on a judgement made while reading untrusted mail —
the class of `cs handled`, which this kernel already holds to be an interactive
gesture. The cron wrapper now denies BOTH halves of it in all six command-text
spellings: `cs draft-delete` (the Gmail copy, moved to Trash) and
`cs rpc drafts.discard` (the engine's, which DELETES the row). The second is
load-bearing for the same reason as the `cs rpc chat` deny — the stamped
`settings.json` allows the broad `cs rpc:*`.

### New — `cs catchup`, and a review that knows whether anything is running

Everything the engine owns is only as fresh as its last pass, and a review that
computes verdicts from a stale ledger moves the cost onto the reader.
`cs catchup` drives the engine's own surfaces and re-implements none of them:
`sync.run`, then `update.run`, printing the task diff so the caller reports what
the pass CHANGED rather than that it ran. It drafts nothing and sends nothing,
and therefore runs while `CS_PAUSE` is present: the switch stops customer-facing
work, and refusing a read-and-classify pass would leave a paused clone
permanently unable to show fresh state. When the engine is already running that
same pipeline it answers `busy`, which this verb reports as the clean outcome it
is — no wait, no retry.

`cs catchup --check` answers whether the pass is WARRANTED and writes nothing:
it compares the newest inbound in the mailbox against what the engine can show
for that conversation. The engine exposes neither the timestamp of its last pass
nor the interval it is configured for, so freshness is MEASURED rather than
inferred from a clock — and every unanswerable case (no recent inbound, an
engine that will not talk, an unthreadable message) answers "not stale", because
the only thing `stale` triggers is an offer to spend LLM budget.

`cs cron status --json` reports `installed` / `paused` / `last_tick_at` /
`last_tick_action` / `schedule` / `state`, where `state` distinguishes the three
situations whose remedies differ — `absent`, `paused`, `stale` (installed, not
paused, and the log quiet for longer than the schedule implies) — from
`ticking`. The staleness threshold is read off the crontab schedule; no interval
constant enters the kernel. `/cs-review` states those facts on the
last-scheduled-run line that already existed, asks ONE question when the state
warrants it ("want me to run the catch-up now?"), and never offers to lift the
pause. The stamped permissions allow `cs catchup --check` and leave bare
`cs catchup` to ask — the human gate is a permission prompt, not a convention.

### Changed — the kernel default speaks English, and each clone declares its voice

Eight literals across seven stamped surfaces instructed the agent to address the
operator in "Italian, founders' register", the greeting shapes carried Italian
copy inline, and `cs review`'s digest was Italian in kernel Python. That is one
company's preference frozen into shared code, which charter rule 2 forbids, and
the product is sold into the US.

The voice is now `[surface] operator_voice` in each clone's own
`manifest.toml` — free text pasted into the greeting instruction, defaulting to
`"American English, professional and direct"`. `[surface]` is template-only,
exactly like `[cron]` and `[repo]`: no `Settings` field, read off the raw TOML
when the kernel stamps. Every stamped shape now labels its slots in English and
tells the agent to render them in the declared voice; `cs review`'s digest is
English like every other line of kernel code, and so are `cs unanswered`'s CRM
grouping headers.

Two mechanics make that reach an existing clone, and both were required before
any template could read the variable: `cs update` now merges the clone's own
`manifest.toml` over the `init_data` frozen at `cs init` time (so editing the
manifest reaches the stamp without re-running the wizard), and a
`TEMPLATE_DEFAULTS` floor answers a variable no older clone ever froze.

### New — one role-framing preamble, included three times

`/cs-review` and the `cs-triage-mail` / `cs-operator` skills open with one
shared text: the agent is taking over a desk other assistants worked at, the
world moved while nobody was there, and its first duty is to orient before
acting on what it inherited. It steers the judgement the pipeline does not
enumerate — a `re-decide` row whose right answer is neither "send" nor "delete"
— and it never replaces a computed verdict.

It lives in a new template root, `cs/templates/partials/`, a SIBLING of
`templates/project/` because `render_templates` stamps everything it walks: a
partial inside would land in every clone as an orphan `.claude/` file and be
checksummed. Three things had to land with it, and all three are gated:
`cs init`'s loader takes both roots; `cs update` — which built its Jinja
environment with NO loader and rendered from a string — now loads by name
through the same environment, or every existing clone would fail on the first
`{% include %}` while a fresh `cs init` succeeded; and `pyproject.toml` grows
the `templates/partials/**/*` package-data glob, without which the partial ships
absent and every stamp fails on a clean install.

### Engine surfaces this release assumes

`drafts.discard` (owner-scoped, one id per call, deletes the row — a `sending`
or `sent` draft is refused, a `failed` one is discardable) and the pipeline's
single-flight guard (`update.run` answering `{busy: true}` instead of running a
second pass) are mrcall-desktop's, landed alongside this tag. A kernel running
against an older engine degrades rather than breaks: `drafts.discard` answers
"method not found" and the Gmail half of a retirement still works, and an engine
with no guard simply never answers `busy`.

### Re-collaudo — FULL, both clones

It touches the review surface, the permission surface (two new denies) and the
draft path — the list the release rules escalate on. Per clone: `cs --version`
reports the tag · `cs whoami` signs in as that clone's own mailbox ·
`cs cron status --json` reports the fields and matches `crontab -l` ·
`cs review --json` carries a `verdict` on every draft row · `cs catchup` returns
a task diff and leaves Gmail Drafts byte-identical · the preamble is present in
all three stamped files · the stamped greeting reads in the declared voice · a
`/cs-review` run prints the scheduled-run line and asks the single question.
Before `cs update` on `mrcall-cs`, add its `[surface] operator_voice` line —
the update reads the manifest, so the line must be there first; `124-cs`
declares none and takes the US-English default.

## v0.30.0 — 2026-08-27

**MINOR**: one stamped file changes class. `docs/active-context.md` stops
being a template `cs update` maintains and becomes what it has always been in
practice — the clone's own document. A verb that stops prompting about a file
is a MINOR whatever the diff size. No send path, no `campaign`, no
`gmail_archive`, no `send_mail`, no auth boundary, no permission surface.
**Re-collaudo: static, both clones.**

### Fixed — the kernel stops claiming a checksum for the clone's state document

`docs/active-context.md.j2` is a seven-line SEED: three empty headings and
`doc_baseline_commit: INITIAL`. Its entire purpose is to be replaced by the
clone's live state on day one, which means a checksum recorded for it asserts
a match no clone can ever hold again. Two consequences, one old and one new:

- Old, and the sharper of the two: the divergence was a conflict, so any
  release that reworded the seed asked "modified locally AND template changed.
  Overwrite? [y/N/diff]" about it — a prompt whose `y` deletes the operator's
  state document.
- New: `v0.29.0`'s drift report named it, on a plain run, on every clone, for
  ever. A report that always contains the same untrue-in-spirit line is a
  report an operator learns to skip, which is exactly the mechanism the
  `company/` slots were pulled out of tracking to avoid (`v0.16.0`).

It joins `CLONE_AUTHORED_PREFIXES`: created when the clone has none, then never
written, never prompted about, never checksummed, with the stale entry dropped
on the next `cs update`. The kernel has nothing to push into that file; it only
has to make sure a new clone starts with one. Members are matched with
`startswith`, so the set now holds either a directory prefix (`company/`) or
one whole path (`docs/active-context.md`), and the two "company prose" messages
read "clone-authored", which is what the class is.

### Re-collaudo — both clones, tier **static**

Measured before the tag, against a copy of a real clone's tree rather than a
fixture: `cs update` now names exactly ONE file in its drift report,
`bin/cs_operator_cron.sh` — the clone-owned `bin/mrcall_business.py` deny line
that `v0.28.0`'s entry records as lost at three previous re-pins. That is the
report's whole content on a clone that is otherwise in step, and it is true.

On each clone the check is the update itself: `docs/active-context.md` is
byte-identical afterwards, absent from the drift report, and gone from
`template-manifest.json`'s `file_checksums`. `bash tests/run.sh` — 39 gates,
`RESULT: all gates green`. Gate 16 carries the scenario, verified to FAIL
against `v0.29.0` on the prompt assertion.

## v0.29.0 — 2026-08-27

**MINOR**: `cs update` prints a report it never printed, restores a stamped
file it used to skip for ever, and `cs update --pin` writes a second file. All
three are observable, and an operator reading "patch" is entitled to expect
that none of them are. No send path, no `campaign`, no `gmail_archive`, no
`send_mail`, no auth boundary, no permission surface.
**Re-collaudo: static, both clones.**

### Fixed — a stored checksum that describes nothing on disk is no longer silent

`template-manifest.json`'s `file_checksums` records, per stamped path, the
render `cs update` last left in the clone. One branch of the walk wrote such an
entry without ever reading the file it names: when today's render equals the
stored value — "template unchanged" — it skipped straight to the next path. A
hand edit to a stamped file therefore left the ledger describing content nobody
had, while the run reported `0 updated, 0 skipped, 0 added` and exited 0.

Nothing downstream can tell that entry from a true one. At the next release
that changes that template, the divergence surfaces as "modified locally AND
template changed"; a headless run answers the declared `N`; the old checksum is
put back; and the file has left template maintenance without anyone deciding
that it should. `v0.21.0` is that failure with a measurement attached —
`mrcall-cs`'s `docs/ARCHITECTURE.md` reported as locally modified for five
releases. `v0.21.0` added the recovery (a clone whose content already matches
today's render is reconciled silently) and that is why the file healed at
`v0.27.0`, but recovery is not prevention: the same shape reappeared on BOTH
clones at the `v0.28.0` re-pin, on the same file, whose "Kernel pin" row is
hand-edited every time.

That branch now reads the file, and answers both states it can be in:

- **Missing** — restored from the render its own stored checksum already
  blesses. There is no operator content to lose (the render *is* that content),
  and every other branch of the walk already re-adds a template file the clone
  lacks. Only this one did not, and only a template CHANGE could ever have
  brought the file back.
- **Present but different** — nothing is written and the stored checksum stays
  the TEMPLATE's. Recording the local content instead would make the next real
  template change read as "clone is original" and overwrite the operator's edit
  with no prompt at all. What changes is that the path is listed at the end of
  the run, under what the divergence means for the next release.

The ledger holds ONE checksum per path and answers two different questions with
it — *did the template change* and *did the clone change*. Those questions
have the same answer only while the clone equals the render, so a divergence
can legitimately exist (a declined conflict deliberately keeps the template's
value, or the conflict is never offered again). The contract this release
establishes is therefore not "the ledger always matches disk" but the one that
is achievable without changing the manifest format: **every entry that does not
describe its file was reported by the run that left it that way.**

### Fixed — `cs update --pin` owns `init_data.repo_kernel_version`

`docs/ARCHITECTURE.md.j2` renders its "Kernel pin" row from that field
(`cs-kernel@v{{ repo_kernel_version }}`). While `--pin` rewrote only
`requirements.txt`, the field stayed on the previous release, and every re-pin
required the operator to hand-edit a GENERATED file to state the version he had
just pinned — which is where the hand edits above come from. `--pin` now
re-stamps it, prints the before/after, and is a silent no-op outside a stamped
clone (`--pin` still works against a bare `requirements.txt`). The value is the
bare number: every template that reads the field writes the `v` itself, and a
stored `"v0.3.0"` — a real clone carried one for five releases — renders
`cs-kernel@vv0.3.0`, so the prefix is stripped whatever the caller passes.

The accepted upgrade offer inside bare `cs update` goes through the same
function, so the re-exec'd walk renders the new row itself and records its
checksum in the same pass.

### Migration — one hand step at THIS re-pin, none after it

The pin verb that runs during an upgrade TO `v0.29.0` is still the old one, so
this release cannot bump its own `init_data`. Once `v0.29.0` is installed, run
`cs update --pin v0.29.0` again — now on the new kernel — and then bare
`cs update`: the first re-stamps the field, the second re-renders the "Kernel
pin" row and records its checksum. From the next release on, the ordinary
upgrade does both by itself.

Expect the new report on a first run against an existing clone. It lists what
was already true and unreported — on `mrcall-cs`, `bin/cs_operator_cron.sh`
carries a clone-owned `bin/mrcall_business.py` deny line that is re-applied
after each `SECURITY_CRITICAL` overwrite, so it diverges from its render by
design. Naming it is the point: that is the file whose local edit has been lost
at three previous re-pins.

### Re-collaudo — both clones, tier **static**

Nothing in the FULL list is touched. The whole change is inside `cs update`,
which is the upgrade verb itself: no live engine call behaves differently, so
`live read-only` earns nothing here either. What must be checked on each clone
is the re-pin it is already doing — `cs update --pin` reports the
`repo_kernel_version` before/after, the following `cs update` re-renders
`docs/ARCHITECTURE.md`'s pin row rather than leaving it to a hand edit, and
`template-manifest.json`'s checksum for that file agrees with the file
afterwards. `cs --version` and `cs config` confirm the pin.

Guards run before the tag: `bash tests/run.sh` — 39 gates, `RESULT: all gates
green`. Gate 16 carries three new scenarios, each verified to FAIL against the
preceding commit: the hand edit is named by the run, the lost file is restored,
and `--pin` re-stamps the field including the legacy `v`-prefixed shape. The
first two assert the invariant rather than a message — for every path in the
manifest, the stored checksum either matches the file on disk or the run named
it — so a fix that only changed the wording would not pass them.

## v0.28.0 — 2026-08-27

**MINOR**: `cs-triage-mail`'s § 2 body-read is no longer conditional on draft
intent — every candidate that survives step 1/1b, escalate-bound or
draft-bound, gets its thread read before the operator ever sees its name, and
a task `reason` field is named explicitly as non-provenance. `/cs-review` and
`/cs-help` drop the operator greeting's last two internal-vocabulary spots
(`tick` becomes the scheduled run, in plain Italian) and gain a fifth greeting
rule requiring every label the operator reads to be a plain Italian noun for
the thing itself, plus a "Preparato:" line that states whether the last
scheduled run actually ran or was skipped instead of a bare timestamp.
**Re-collaudo: static + live read-only, both clones.**

### Fixed — an escalation named a customer without ever reading their thread

A `/cs-triage-mail` run (session `ae8b19cc`, 15:24) read a stale unsent draft
that *quoted* a customer's five-day-old symptom
(`INBOUND_WELCOME_MESSAGE_PROMPT`, 22/8) and wrote it into a new engine task's
`reason` field as present-tense state, without ever calling
`emails.list_by_thread` on that customer's thread. A later run (session
`65df4f07`, 15:54) inherited that task, treated its `reason` as evidence,
grafted an unrelated same-day fix (given to a *different* customer,
`pcrapide.be`) onto the inherited clause, and escalated
`info@fortunatoassicurazioni.it` to the operator on a claim his own mail never
made. The 22/8 thread was only opened at 16:22 — after the operator
challenged the escalation — and it was closed: our 22/8 11:16 reply was the
last message in it, the customer never re-raised it, and both engine tasks on
it were completed by `detect.email.user_replied`. The customer's live, open
ask (a call-transfer question, 25/8) was real; the reasoning attached to the
escalation was not.

Root cause was `.claude/skills/cs-triage-mail/SKILL.md` § 2's own gate: "For a
candidate that survived the Sent-archive check (genuinely unanswered) **AND
you intend to draft**, read the real bodies." An item headed for ESCALATE sat
outside that condition, so the skill permitted naming a customer to the
operator on a task title alone. The asymmetry is provable in the same run:
the other candidate that day (GB Dental) *was* draft-bound, so the skill
called `emails.list_by_thread` three times, read the bodies, and judged
correctly — the gate is what made the difference, not the model or the
customer. The rewritten § 2 removes the condition: every survivor gets its
thread read before the draft/escalate fork, and the section now says plainly
that a `reason` field carries no provenance — it may have been typed by an
earlier tick of this same skill, so reading it back is confirming the skill's
own prior output, not corroborating it. This closes the § 2 gate that let the
error through; § 1b's "OPEN task → work it" amplifier (no re-validation of a
task's `reason` against the thread's current state) is unchanged by this
release, and a candidate reached through it is covered by the same new rule:
the reason it carries is not a source to read the thread from.

### `cs-review`/`cs-help` stop teaching the operator our own words

Rule 5 in `/cs-review`'s greeting instructions: every label the operator
reads is a plain Italian noun for the thing itself, never internal
vocabulary, a coined word, or an English term of art carried over from the
code — `tick`, `sweep`, `dossier` as a bare heading, `producer`, `escalation`
used as a verb all name a mechanism the reader does not have to know exists.
`cs-help.md.j2` and `cs-review.md.j2` apply it at the two remaining `tick`
spots: the command map now reads "the scheduled unattended run", and the
kill-switch line reads "stops every scheduled run". The "Preparato:" line
splits the last scheduled run onto its own line and states the outcome in one
neutral word (`ha girato` / `saltato`) instead of a bare timestamp — a bare
timestamp reads as "the run happened", which is false on a skipped run, and
the operator has already misread it that way once.

### Why the tier is static + live read-only, not full

Design brief §6.6 ties the tier to what the release TOUCHES, not to diff
size. This release touches zero send paths, `campaign`, dedup,
`gmail_archive`, `send_mail`, permissions or the cron wrapper — the six
triggers that force FULL — so FULL is not warranted. It is not bare static
either: both changed files are rendered skills/commands (§6.2 item 4 on its
own), but § 2's entire content is a mandate to make MORE live engine reads
before naming a candidate, which is exactly the "read paths" row of the
tier table. Certifying a fix whose whole point is "read the live thread
before you act" with a check that never talks to the live engine would be
the same failure this release exists to close. **Static** (§6.2): the
rendered templates hunk only at the declared prose, `cs config` resolves
with no setting declared twice, the CLI surface is unchanged. **+ live
read-only** (§6.3): `cs whoami` against the real engine, proving the sign-in
path the fix depends on still works. No campaign/dedup/send collaudo is
owed, and none was run.

### Migration

`cs update` re-renders three templates:
`.claude/skills/cs-triage-mail/SKILL.md.j2`,
`.claude/commands/cs-help.md.j2` and `.claude/commands/cs-review.md.j2`. A
clone with no local edits to any of the three takes the new render with no
conflict prompt. Confirm after the update that § 2's heading reads "Read the
customer's own words before you decide anything" and that no literal Jinja
survives the render — `{{ email_address }}` must resolve to the clone's own
address. No manifest field, no CLI verb, no permission-surface change; the
cron wrapper and `.claude/settings.json` are untouched.

Guards run before the tag: `bash tests/run.sh` — 39 gates green, unchanged
from the state the § 2 fix (`6386bf0`) already reached.

## v0.27.0 — 2026-08-27

**MINOR**: the stamped clone `CLAUDE.md` now carries a `doc-scope` declaration —
the routing statement the `/doc-*` documentation harness requires of an index
file from `harness_version = 4` on. Stamped prose only: no verb, no flag, no
manifest field, no default changes. **Re-collaudo: static, both clones.** It is
a MINOR because a stamped file an operator reads is observably different, and
static is safe for it because the release touches no send path, no `campaign`,
no `gmail_archive`, no `send_mail`, no auth boundary and no permission surface —
`git show v0.26.0..v0.27.0 --stat` reaches exactly one template, one gate script
and this file, and nothing under `cs/` that runs.

**Why the kernel has to ship this at all.** A clone's `CLAUDE.md` is
template-owned: it is rendered from `cs/templates/project/CLAUDE.md.j2` and a
local edit is silently reverted by the next `cs update`. The harness's v4 gate
requires a `doc-scope` block in the configured index file, so a clone that
edited its own copy would pass the gate once and fail it again after the next
re-pin, with no diff to explain why. The block therefore belongs where every
other line of that file belongs, and both clones inherit it from one place.

**What the block says, and why it is not company-specific.** It states what the
index is FOR — the thin router: what the clone is, which files are template-owned
versus clone-owned, the safety NEVERs, and where every other subject is written
down — and then names the four places it routes to (`cs --help`, `cs config`,
`docs/ARCHITECTURE.md`, the per-skill/command files), plus the rule that volatile
state lives in `docs/active-context.md`. The only interpolation is
`{{ company_prog_name }}`; there is no company literal, so charter rule 1 is
unaffected and the same text is correct for a clone that is not the mother clone.

**Gate 38 no longer greps line by line, and that is a real defect it was hiding.**
The gate proves the engine-authority rule reaches every clone by looking for
`authoritative`, `fix the engine` and the Gmail-Sent exception in both charter
files. It used `grep -qi`, which matches within ONE line — so on 2026-08-27 a
documentation consolidation reflowed the kernel's own `CLAUDE.md`, split *fix
the engine* across a line break, and the gate reported the rule as MISSING while
the rule itself was untouched. The suite was red at `HEAD` before this release
began. A gate a rewrap can defeat does not measure whether a rule is written
down, so the three checks now run against the file with all whitespace collapsed
to single spaces. Verified in both directions: green on the current files, and
still FAIL when *fix the engine* is actually removed from the template.

**One more claim the same consolidation broke.**
`docs/active-context.md` must carry the sentences *Latest release tag:* and
*Current HEAD status:* verbatim — `tests/test_release_consistency.py` parses
those two sentences as the release inventory's anchor. The consolidation
rephrased them into prose and gate 15 went red. The sentences are restored, with
a line next to them saying they are machine-read and that only the value may
change. Neither of these two repairs alters kernel behaviour; they are what makes
the suite able to certify this tag at all.

**Migration for a clone**: none beyond the normal re-pin. `cs update` re-renders
`CLAUDE.md`; on both clones the file matched its stored checksum beforehand, so
the render applied without a conflict prompt. A clone that has locally edited its
`CLAUDE.md` will be asked, and should take the new render — the local edit was
already going to be lost.

## v0.26.0 — 2026-08-26

**MINOR**: `cs unanswered` gains a fourth section — **closing courtesy, per the
engine — nothing owed** — and an out-of-band `handled` record is no longer
expired by a thank-you. Rows move between sections; nothing is dropped; the
headline queue is unchanged. **Re-collaudo: FULL, both clones** — it touches
`gmail_archive`'s consumer and the `handled` ledger, and the failure class is a
real customer's mail. **Requires engine `mrcall-desktop` `1139da2` or later**;
against an older engine the verb degrades to exactly the `v0.25.0` reading and
says so.

**Why.** `v0.25.0` split the queue and put twenty-two rows in *answered, then
they wrote again*, which the operator was then expected to read in full. He
read one and asked the question this release answers: *"l'ultimo messaggio suo
è 'Va bene, la ringrazio tanto'. Da quando si risponde ai ringraziamenti per
un task completato?"* A bucket of twenty-two somebody must eyeball is the same
failure the split was supposed to fix, wearing a different label.

**Where the fix went, and why not here.** The kernel could see that we had
already answered in that conversation. It could not see that nothing was left
to say, because that is a judgement about what a person MEANT — in Italian,
Spanish, French or English — and the charter forbids the kernel from having an
opinion about it. A gratitude keyword list in `cs/` would have been a second
source of truth, in the wrong repo, drifting from the engine's. So the
capability was BUILT IN THE ENGINE (`zylch/utils/reply_need.py`, RPC
`emails.needs_reply`, mrcall-desktop `1139da2`) and the kernel only asks —
`cs/engine_view.settled`, one batched call per sweep. That is the
engine-authority rule from `v0.25.0` being obeyed rather than restated.

**What the engine decides and what stays here.** *Does this message exist* →
Gmail, unchanged. *What KIND of message is it* → the engine, both for
autoresponders and now for "does this need a reply". *What to do with the
answer* → here, and it is only ever to move a row into its own section and keep
printing it, with the engine's own reason on the line so a verdict the operator
disagrees with is visible AND traceable to where it can be fixed.

**The kernel keeps its own precondition, deliberately.** A verdict can only
re-label a conversation the kernel has independently established that WE
answered, from Gmail. The engine has its own `answered_before` over its own
archive; either can be wrong, and requiring both is what makes a single mistake
survivable. A conversation nobody of ours ever answered stays in the headline
queue whatever the verdict says (gate 39 pins it).

**A stale verdict cannot reach a newer message.** The engine's archive can be
BEHIND Gmail: it may have judged the thank-you that was newest when it synced
while a real request has since arrived on the same thread. The verdict is joined
to its message by whole-second timestamp — the same join `ThreadView.is_auto`
already uses — so the stale case falls back to "needs a reply" by itself. A
thread-level "settled" flag would have silenced that request.

**`handled` no longer expires on a thank-you, and that is the same bug in its
other costume.** The record means "resolved out of band", and any later inbound
re-opened it. The operator phoned `cinziacamorali.er@gmail.com` and recorded it
at 19:58; she wrote *"Va bene, la ringrazio tanto"* the next morning, and the
record expired on a courtesy — putting her back on the queue the day after it
was closed. A record is a statement about the CONTACT, so it is now dated
against the contact's newest message that actually OWES something. A real
request still re-opens the contact exactly as before, and with no engine answer
every message owes something, so the rule reverts to the old one on its own.

**Measured on the live 45-day queue, read-only, with a same-moment control**
(the mailbox is live; a before/after taken minutes apart is not an experiment
unless the control is re-run against the same snapshot):

- headline **11 → 11**, byte-identical rows. Nothing entered the queue and
  nothing left it.
- *answered, then they wrote again* **22 → 9**. Eleven moved to the new
  section — `studioconsulenza.pusceddu`, `info@guitaracademy.it`,
  `dantonioordinazioni`, `spedicato1986`, `studiodentisticofoli`,
  `info@maxpho.com`, `valerio.tavolazzi`, `andrea.inverardi`, `lucianobaldetti`,
  `direzione@acquos.it`, `info@mediaship.it` — each one a bare "ok" or a
  thank-you after our answer. `stefanoappiano@gmail.com` moved to *automatic*
  instead: his courtesy thread stopped being his strongest, and an
  `Auto-Submitted` holiday notice on another thread took its place, which is the
  roll-up working. `cinziacamorali.er@gmail.com` moved to *handled out of band*,
  where the operator's own phone call had put her.
- the rows that DESERVE an answer did not move, and the ones kept in *resumed*
  are kept for a stated reason: a question mark (`studiocasavecchia`,
  `info@labaitacase`), a request with a date (`avv.vincenzorusso`,
  `luragoderba`, `info@clinicaborgarello`), a body over the length bound
  (`amministrazioni.lamonica`, `info@gildapotenza`, `studiominozzi`), an
  attachment (`amedeo.lauritano`). The last two classes include courtesies the
  screen refuses to judge — a false POSITIVE, which costs a glance.
- at `--days 90` the headline is **30 → 30**, also byte-identical, and
  `direzione@acquos.it` stays at **71d** on "Richiesta informazioni sulle nuove
  funzionalità". His June thread is decided by the deterministic screen, reason
  `no_prior_answer`, with no model involved: our own autoresponder is not an
  answer, so nothing there is eligible to be called a courtesy. At `--days 45`
  that thread is outside the window and his only in-window conversation IS the
  August courtesy, so he moves — the window, not the classifier, is what decides
  which acquos row you see.

**Cost.** The classification measured **15.4 s** at `--days 45` (121
conversations, 93 of them decided by the engine's deterministic screen and never
sent to a model, 28 in ONE batched call) and **21.6 s** at `--days 90` (207
conversations, 39 adjudicated). It is one extra RPC round trip, not one per
thread. End to end the sweep should go from 18.0 s to roughly the mid-thirties
at `--days 45`; that figure is an ESTIMATE and is marked as one — it cannot be
measured until the engine change is deployed. An operator who wants it cheaper
pins the engine's `MODEL_REPLY_NEED` to a smaller model; unset, it uses the
engine default.

**Degradation is the `v0.25.0` behaviour, deliberately.** An engine that is
asleep, that predates the method (`-32601 Method not found`), that cannot read
a conversation, or that returns a verdict this kernel cannot pin to a message,
all produce the same reading as before — every message needing a reply — and
the verb prints `engine non consultabile: … ogni messaggio risulta da
rispondere`. Verified live against the currently deployed engine, which does not
carry the method: the output is identical to the `v0.25.0` output apart from
that one line.

**Migration.** None for a clone. `cs unanswered --json` is unchanged in shape
(still the open list, the triage skill's contract). `compute_courtesy` is new
alongside the four existing `compute_*` views; `_partition` returns six lists
where it returned five, and every public wrapper takes one new optional
`settled=` argument, so an existing caller keeps its behaviour.

## v0.25.0 — 2026-08-26

**MINOR**: `cs unanswered` reads CONVERSATIONS, not addresses, and ASKS the
engine what kind of message something is instead of re-deriving it from IMAP
headers. Two new output sections; rows move between sections; nothing is
dropped. **Re-collaudo: FULL, both clones** — it touches `gmail_archive`, and
the failure class either way is a real customer's mail.

**Why.** The operator, on finding a customer's *"Va bene, la ringrazio tanto"*
raised as work needing an answer: *"guarda che questa cosa è stata risolta in
Desktop all'inizio… che facciamo, continuiamo con le stesse cazzate?"* He is
right. The engine has classified auto-replies since the auto-ack incidents of
2026-06/07 — `zylch/utils/auto_reply_detector.py`, and every consumer already
treats a user-from auto-reply as NOT engagement (`task_creation_email.py`,
`thread_presenter.py`, `task_hygiene.py`). The kernel was re-deriving that
judgement from headers, badly, and getting a different answer.

**Measured on the live queue, and each of the four is a named row.**

- *Our own autoresponder counted as an answer.* An English auto-acknowledgement
  landed in Gmail Sent **17 seconds** after a customer's four product questions
  (2026-06-15 18:06:33 → 18:06:50 UTC). By pure existence it is "a message from
  us, after theirs", so the sweep called him answered for **71 days**. The
  engine's `is_auto_reply` on that exact message is `True`. Now an outbound the
  engine flags automatic does not close a conversation, and he surfaces at 71d
  with the right subject.
- *Answered in the thread, to somebody else.* A colleague who was only in Cc sat
  on the queue **28 days** while the thread's principal had been answered on
  2026-07-28. Per-thread grouping closes him. No extra IMAP work: `_fetch_headers`
  already asked for MESSAGE-ID, REFERENCES and IN-REPLY-TO on both sides.
- *A later thread closed an older one.* Helping somebody today marked an older,
  never-answered conversation of theirs as done. On the live mailbox this was
  hiding genuine work at 19–36 days from four contacts, one of them a "richiesta
  contatto telefonico" nobody ever replied to.
- *A closing courtesy headed the queue.* Reported now under **answered, then
  they wrote again** — and this is NOT intent detection. There is no keyword
  list for gratitude and there must not be: the sweep only asks whether a human
  of ours ever answered in this conversation, which it can see without reading a
  word.

**The division of labour, and it is the point of the release.** *Does this
message exist* → Gmail, unchanged, because the engine archive was measured
asserting a 2026-07-28 send that Gmail Sent does not contain. *What KIND of
message is it* → the engine, through the new `cs/engine_view.py`. The thread key
(`cs/thread_key.py`) is the engine's own rule transcribed — an ADDRESS, not a
judgement — and it is what lets the kernel ask about the same conversation: on
today's queue it resolved **39 of 39** threads to an engine thread with messages.

**Charter.** New invariant, in `CLAUDE.md` AND in
`cs/templates/project/CLAUDE.md.j2` § 0b so every clone inherits it through
`cs update`: **the engine is authoritative for what it owns; when it is wrong,
fix the engine** — not a second reading in `cs`, not a heuristic in `ext/`. Its
one exception is the Gmail-Sent dedup rule, which has a measurement behind it
rather than a preference. Gate 38 checks both files carry it.

**Degradation is the old behaviour, deliberately.** An engine that cannot be
reached leaves every conversation read exactly as before, and the verb SAYS so
on its last line. Nothing here fails closed.

**What did NOT change, and why.** Two live autoresponders (`gildains@…`,
`info@stufasmart.it`) stay in the headline: their mail carries **no**
`Auto-Submitted` / `X-Autoreply` / `Precedence` / `Return-Path` — verified
against raw Gmail headers — so there is nothing for the engine to classify and
nothing the kernel may invent. Per the charter that is an ENGINE question
(content classification; `detect_vacation_responder` exists at
`auto_reply_detector.py:175` with **zero** production callers, and would not
have caught either of these). No `mrcall-desktop` change ships in this tag.

**Known limitation, named rather than discovered later.** A sender whose client
strips `Message-ID`/`References` (Gmail rewrites these as
`…SMTPIN_ADDED_BROKEN@mx.google.com`) cannot be threaded to the message it
replies to, so such a reply reads as `open` rather than `resumed`. That is
over-inclusion — the safe direction — but it is why a bulk-outreach reply wave
appears in the queue rather than beside its own broadcast.

**Migration**: none. `cs unanswered --json` is unchanged (still the open list,
the triage skill's contract); rows gain `thread_key` and `state`. Callers of
`compute_open` see senders they already answered once move to `compute_resumed`
— `tests/test_unanswered.py` pins both halves of that.

## v0.24.0 — 2026-08-26

**MINOR**: `/cs-review` becomes the ONE command an operator types when he sits
down — it answers the questions he used to have to ask, and it stops treating
his own kill-switch as an incident. New `cs unanswered --crm`; `cs config`
gains the `system_senders` section; `cs review`'s campaign block counts plain
outcomes instead of listing them; the project permission set allows the
read-only verbs the bootstrap runs. Re-collaudo **FULL on both clones**: this
is the operator's primary surface, and the failure it produces is not a
traceback — it is a morning where a real reply waiting for a named customer is
invisible because it was folded into a number.

### It answered three of eight questions, and warned him about his own decision

Measured on a real morning: `6m38s`, 44 lines, zero side effects. What it left
out was not obscure — the support queue, what changed in the repo, what is
blocked on the owner, the contacts deliberately taken OUT of the queue, and
every draft's identity. And what it *did* say about the kill-switch it said by
accident: no step read the switch, but the six-line cron log tail happened to
be all `paused … skip`, so the greeting inferred a warning from it — including
the span "all the ticks of the last twelve hours", which was wrong by 4x
because six lines of a two-hourly log ARE twelve hours whatever the real gap.
Then it offered clearing the switch as the first suggested next step, without
mentioning that `cs_triage_mode` is `send`: it proposed resuming an operator
that answers customers by itself, and did not say so.

**The kill-switch is a standing decision, not news.** The operator's own
ruling, and the rule the command now follows: it appears exactly once, as one
neutral field of state in the header (`invii: in pausa (decisione tua) · modo:
send`), in the same register as the kernel version — never an alarm word, never
`⚠`, never repeated in a second section, and **never with a suggestion to lift
it**. Gate 36 asserts all four mechanically against the rendered command,
including that the closing options mention neither the pause nor the tick, and
that the file never contains a command to remove the switch file.

### What the one command now covers

- **`cs config` is a step** (0.4s). It is the only source for the triage mode
  and the switch; nothing may be inferred from a log tail again. A derived
  claim a fixed-length tail cannot support is banned outright.
- **`cs unanswered --days 45 --crm`** — the support queue was never run. The
  new `--crm` flag attaches each open sender's CRM record through the port
  (`cs/crm`, so a clone on another backend gets its own adapter's facts) and
  prints customers as their own group: the queue's size is not its workload,
  and separating it is what the operator otherwise re-does by hand every
  morning. Opt-in, because it costs one lookup per row (`+4.5s` on 15 rows) and
  the triage skill does not need it — without the flag the table is byte-for-
  byte what it always was. A degraded backend labels **nothing** and prints one
  note: a half-filled column reads as "these are not customers".
- **`cs --version` + `git log`** — the kernel pin actually installed, and what
  changed since he last sat down. Live values beat prose everywhere: the
  clone's own notes may be older than the tree, so they are quoted as the TITLE
  of something waiting on him, never as a fact about the present.
- **`docs/owner-actions.md`**, digested to a handful of open headings when the
  file exists — the "without me saying where to look" half of the ask. A clone
  without that file falls back to its unresolved section.
- **Per-draft rows with their uid**, and the out-of-band records. Both were
  already in `cs review`'s output and the greeting threw them away: a draft to
  a contact outside the candidate table cannot be recovered from `+1`, and a
  contact deliberately out of the queue gets re-raised from memory unless the
  greeting says why it is missing.

### Paid for by a campaign block that had stopped earning its lines

37 lines, 31 of them identical `[engaged]` rows for one pack. An escalation
exists to fetch a human and keeps its address and its reason; a plain outcome
is a fact about work already done and is now a count (`esiti: engaged 31`). A
campaign a dedicated process owns is labelled `esclusa`, not hidden — hiding it
would hide its escalations too. Same information, 37 lines → 5.

### `cs config` prints `system_senders`

The verb whose whole job is "the settings actually in force" was silent about
the list that decides who is never a customer — and since `v0.23.0` one entry
can be a pattern hiding a whole domain. An invisible filter is
indistinguishable from a bug, and gets reported as one.

### Migration

Nothing to do beyond `cs update`. `.claude/settings.json` is applied
regardless (local kept as `*.local-bak`) and now allows `cs review`,
`cs unanswered`, `cs --version`, `git log` and `git status` — all read-only,
none send-capable, and gate 17's allow-purity check still passes. On
`mrcall-cs`, `cs update` is known to drop the clone-owned deny line for
`bin/mrcall_business.py` from `bin/cs_operator_cron.sh`; restore it after the
update, as at every re-pin.

## v0.23.0 — 2026-08-25

**MINOR**: `CS_SYSTEM_SENDERS` entries may be fnmatch patterns, and the
`do_not_contact` suppression table is matched the same way — so a typed entry
means the same thing on both lists. Re-collaudo **FULL on both clones**. The
tier is not about diff size: every change here decides who the operator is
never shown and who is never written to, and the failure it can produce is a
rule hiding a real customer's mail. That is the one outcome this operator
exists to prevent, so it gets the tier that matches the consequence.

### The bounce daemon that cannot be listed

`cs unanswered` matched its ignore list by exact address. One customer's
undeliverable address made the provider's mail daemon answer from a **rotating
host** — seven distinct `mail-daemon@<host-NN>.<domain>` senders in six days,
all the same bounce — so the list was stale on the next bounce and the operator
was handed a robot to answer. Measured on a live 45-day sweep: 8 of 22 open
rows were not a person waiting.

An ignore entry is now a literal address **unless it contains `*`, `?` or `[`**,
and then it is an `fnmatch` pattern: `mail-daemon@*`, `mailer-daemon@*`,
`postmaster@*`, `*@notify.<domain>`. Deterministic and offline — no LLM decides
who is a person.

The wildcard test is what makes this safe to ship onto lists already in
production: no existing entry contains one, so every list splits entirely into
literals and computes the identical set. Verified rather than argued — a
differential harness ran the old and new partition over 3000 randomised
literal-only cases (blank entries, self addresses, handled and escalated
records included) and they agree exactly. `SELF_EMAILS` deliberately stays
exact: it is a list of identities we own, and a wildcard there would hide a
customer whose address resembles one of ours.

### The same change made suppression fail OPEN, and that is the real fix

Teaching operators to type wildcards while `cs/filter.py` still compared
suppression exactly would have made `cs suppress '*@<domain>'` do half its job:
the domain disappears from the queue, the producer worklist keeps mailing it,
and the operator can see protection that is not there. A suppression that fails
open is worse than no suppression.

Both lists now read a typed entry through one matcher, `cs/addr_match.py`
(`AddrSet`, a `__contains__` type — so `email in dnc` at every call site was
upgraded rather than each site having to remember to ask differently). Proved
on the send side, not only in the sweep: with `*@blocked.example` suppressed,
the pre-change worklist still offered the address for outreach and the new one
does not.

**Scope, stated precisely:** suppression gates the producer worklist (`cs plan`
→ `cs/filter.py`). Campaign packs never consulted `do_not_contact` at all —
pre-existing, unchanged here, and worth its own decision.

### Not built: autoresponder detection

Considered and deferred with a reason. No address rule can express it — the
three autoresponder rows in the same sweep are real customer addresses that
also write real mail. The cheap deterministic signal is four headers
(`AUTO-SUBMITTED`, `X-AUTOREPLY`, `X-AUTORESPOND`, `PRECEDENCE`) added to the
single FETCH list in `gmail_archive._fetch_headers`, at no extra round trip —
but the rule it must obey is **tag, never drop**: a vacation notice can arrive
on the same thread as a real request, and dropping it would bury the request.

### Clone-side

Nothing is required. Patterns are opt-in: a clone that adds none behaves
exactly as before. `manifest.toml.j2` documents the syntax.

**Correction, made the moment the code was read rather than left standing:**
this entry first said `cs update` would offer that comment on an existing
clone's `manifest.toml` as a conflict prompt. It does not. `manifest.toml` is
decided *before* the render and skipped outright (`cs/project_update.py`, next
to `requirements.txt`) — written once by `cs init` and never a render target
again. So the comment costs existing clones no prompt, and reaches only clones
stamped from `v0.23.0` onward. For an existing clone the discoverable surface
is this entry and the `Settings.system_sender_set` docstring; a clone that
wants the syntax written next to the value must paste the comment into its own
`manifest.toml`, which is a clone-owned file it may edit freely.

Gate 35 in `tests/run.sh`.

## v0.22.0 — 2026-08-25

**MINOR**: `cs update` starts asking again about a file it had stopped asking
about. No prose, no template, no send path. The tier below is **static**, with
one specific check named.

### Fixed — declining an overwrite no longer means never being asked again

`cs update` recorded the freshly-rendered checksum for every template at the
top of its loop, before deciding anything. For a file in the "modified locally
AND template changed" state, answering `N` therefore stored today's render as
the file's checksum anyway. The next run compared that stored value with the
same render, concluded "template unchanged", and skipped the file without a
word. The conflict was never offered again, and the clone kept a stale copy in
silence — permanently, and with no output anywhere saying so.

A decision to skip once is not a decision to stop being asked. Both decline
branches — a plain `N`, and `N` after `diff` — now put the OLD checksum back,
so the same conflict is offered on the next run and every run after it until
someone resolves it.

**Reproduced live on `mrcall-cs` before the fix**, which is how it was found:
two declines printed `2 skipped`, and the run immediately after printed
`0 updated, 0 skipped, 0 added`.

Guarded by three new end-to-end scenarios in `tests/test_project_update.py`,
each driving a real `python -m cs update` subprocess: plain decline, decline
after `diff`, and — the property that must not regress — accept, which still
records the new checksum so the file is *not* re-offered. The suite was proved
non-vacuous rather than assumed to be: with the fix removed in a scratch copy
of `cs/`, the decline tests fail with the exact live symptom.

### Existing clones need a repair this fix does not perform

The fix prevents new corruption. It does not repair a ledger already advanced:
a file that was declined under `v0.21.0` or earlier has today's render stored
against it, so `cs update` still considers it unchanged. On a clone where that
happened, the entry must be removed from `template-manifest.json`'s
`file_checksums`, or the file brought in sync by hand, before `cs update` can
see the conflict again.

### Re-collaudo — both clones, tier **static**

No send surface, no `campaign`, no `gmail_archive`, no `send_mail`, no auth
boundary, no permission surface. The check that matters is behavioural: on each
clone, put a template-owned file into conflict, decline, and confirm the very
next `cs update` offers the same conflict rather than reporting nothing to do.

## v0.21.0 — 2026-08-25

**MINOR**: no code changes at all. Two templates change the documents every
clone renders, and an operator reading "patch" would be entitled to expect
nothing observable changed. The tier below is **static** — the only surface
this touches is stamped prose.

### Changed — the clone index stops teaching, and the architecture doc stops recounting

`mrcall-cs`'s rendered `CLAUDE.md` had reached 220 lines against its own
`index_max_lines = 221`. One line of headroom is not a margin: the next edit to
that index would have failed its own gate. The cause was not that clone's — the
template had been accumulating mechanism prose for releases, and every clone
rendered the same overweight index.

`CLAUDE.md.j2` is now the slim index it claims to be, at 162 rendered lines. It
routes and it does not teach: the engine daemon, headless per-account auth, the
RPC wrapper-key table, the `--account` engine-versus-Gmail-IMAP split, the
daily pipeline, and why the two mailbox records exist all move to
`docs/ARCHITECTURE.md` § How it works, which is where an as-built description
belongs. Every `NEVER` rule stays in the index, which is what an index is for,
and one was **restored**: "dedup ground truth is Gmail's own Sent folder, never
the engine archive" is charter invariant 4 and had survived only inside the
prose that moved out.

The first attempt at this fix was made in the clone rather than the template,
and it is worth recording why that was wrong, because it is the trap this
release closes. `docs/ARCHITECTURE.md` declares in its own header that every
`cs update` replaces it wholesale. Prose hand-written there is destroyed at the
next render. A clone is not where a template's shape is decided.

### Changed — `## How it works` describes the system, and nothing else

Three passages did not survive the move, and were deleted rather than
relocated. Why `RATE_CAP` was removed in `v0.12.0`; the account of a phase
sentence that "already talked two headless ticks out of sending mail"; and a
parenthetical about one customer who stayed on a list a month after the owner
had phoned him. All three recount what happened. This file is a CHANGELOG and
it already holds them, which is the point: an architecture document says what
the system **is**, and a document that accumulates history has become a log
whatever its title says.

Two smaller edits followed from the move. The section's old opening described
itself as hand-written and asked the reader to mirror edits into the template —
false once the section is generated — and is replaced by two lines saying what
the section is. The closing paragraph's "The declared configuration above is
generated" reverts to "Everything above is generated", true again now that
nothing in the file is hand-written.

### Re-collaudo — both clones, tier **static**

No code path changed: no send surface, no `campaign`, no `gmail_archive`, no
`send_mail`, no auth boundary, no permission surface. What must be checked on
each clone is that `cs update` renders the two documents and that the rendered
index is the slim one. `cs --version` and `cs config` confirm the pin.

Guards run before the tag: `bash tests/run.sh` — 35 gates green. The company-
literal guard reports no unreviewed company-shaped literals, with the same
three approved hits already in `tests/reviewed_literals.txt` and no new
approvals. Gate 12 renders 32 templates against 3 configs clean. Both render
paths were exercised — `cs init`'s FileSystemLoader and `cs update`'s
`from_string` — into a directory outside every repository. No new Jinja
variable is introduced by either template, so an older clone's frozen
`init_data` cannot fail `StrictUndefined`.

## v0.20.0 — 2026-08-25

Written at implementation time so the release did not have to reconstruct it.
**MINOR**: a new CLI verb, a new skip reason in `cs plan`, a new refusal on
four campaign delivery paths, and a permission surface that grows by six
entries. The tier below is FULL.

### Added — `cs escalated`: NOT resolved, but a human has taken it over

The owner was personally mid-conversation with two customers. Gmail Sent — the
dedup ground truth — showed no reply from us yet, correctly, so `cs unanswered`
counted both as unanswered work and the two-hourly headless operator, which
answers customers itself, kept preparing a second reply to each. Two hands
writing to the same customer is the tone-deaf failure this operator exists to
avoid, and the only two states on offer were `handled` (a lie — nothing was
resolved) and nothing at all (the collision).

`cs escalated <email> --why "…" [--who NAME] --commit` records that a named
human owns the thread. Its sibling `cs handled` says the conversation is over;
this one says the opposite — still open, still owed an answer — and the three
properties that follow are the design:

- **No expiry.** `handled` is scoped by a timestamp because a later message is
  a NEW conversation. Here a later message is the SAME conversation, the
  customer replying to the human who took it over, so an expiry would re-arm
  the collision on the very event that causes it. The record holds until a
  human releases it (`--undo --commit`) or closes it (`cs handled`, which
  clears it in the store, so no caller can leave a "with you" label ageing on
  a thread that is over).
- **It may never become invisible.** An un-expiring suppression that shows
  nothing is the silent drop the whole ledger was built to end, so every
  surface that takes an escalated contact out of open work also PRINTS it, aged
  and re-labelled: `cs unanswered` gains a "with a human — still open, not the
  operator's to answer" section, `cs review` a "Presi in carico — aperti, ma non
  li lavoro io" block sorted oldest-first, `cs dossier` a section
  plus a `verdict: STOP`, `cs plan` a counted `escalated` skip reason, and
  `campaign pending` an `escalated_hold` count with `escalated_to` on the
  observation items it keeps.
- **Only a human may write it, and the cron denies the verb** in all six
  command-text spellings. `handled` is interactive-only because honouring
  "consider this closed" from an inbound mail would let anyone bury their own
  request; this is the sharper version of that rule, because the sentence
  recorded is an assertion ABOUT A HUMAN which the review then repeats back to
  him as "you are on this one". A false one is worse than a false close: it
  does not merely hide the item, it tells him he already has it.

**The skills' own "DEFAULT ON UNCERTAINTY = ESCALATE" is a different state and
stays where it was.** A machine-written escalation is legitimate and expected,
and it already has a home: an OPEN engine task plus a line in the tick report
for triage, and the contact's `escalated` dossier flag for campaigns. Both mean
"somebody must look at this" and both correctly keep the contact IN the work
list. This ledger means "somebody IS looking at it" and takes the contact OUT.
Modelling them as one field with a `source` column would put the two facts on
one row and make every reader responsible for branching on it — the first
reader that forgot would hand a machine's guess the authority of the owner's
word. Different facts, different stores. The stamped skills, `CLAUDE.md` and
`/cs-review` now say which is which at every point the word appears.

**Dry-run until `--commit`, where `handled` writes straight away.** Not
decoration: a handled record expires itself the moment the contact writes
again, so a wrong address there costs one tick, while this record has no expiry
and a wrong address silences a real customer until somebody notices. `--undo`
is gated the same way, and its dry run says so loudly; a forgotten `--commit`
is self-correcting because the contact stays listed either way.

**No engine write.** `handled` closes the contact's open tasks because the work
is done. Here it is not, and closing the task would delete the only durable
trace that somebody still owes this customer an answer.

`send_draft`, `queue_draft`, `send_first` and `_pack_send_preamble` (covering
`send_reminder` / `send_sms`) refuse independently of the worklist, because a
caller can reach a sender with a contact id it got anywhere.

- **Re-collaudo: FULL on both clones.** It touches the campaign delivery paths
  and the permission surface (the cron deny set grows from 34 to 40 entries),
  which is the list invariant 4 escalates on.
- New gate 34 (`tests/test_escalated.py`) and gate 17's deny enumeration now
  covers `escalated`; gate 4's help tree covers the verb.
- A clone picks the verb up on `cs update` for `bin/cs_operator_cron.sh`,
  `CLAUDE.md`, `.claude/commands/cs-review.md`, `.claude/commands/cs-help.md`
  and the two operator skills. The SQLite table is created by the additive
  `CREATE TABLE IF NOT EXISTS` replay on the next command — no migration step.

## v0.19.0 — 2026-08-24

### Fixed — `cs init` could produce an SMS configuration that cannot send

`cs init` asks "Enable SMS?" and the template hardcoded `proxy_base = ""`, on
the reasoning that the proxy is fixed infrastructure with nothing per-clone to
configure. That reasoning was right and the conclusion was wrong: it left the
operator answering yes to a capability whose endpoint nobody supplies, so the
first send raised `SmsError`. A wizard should not be able to emit a
configuration that is dead on arrival.

The endpoint is now a **kernel default**:
`https://zylch.mrcall.ai/api/desktop/sms/send`, the mrcall-desktop engine's
SMS send path. `[sms].enabled` is the whole switch. A clone that never touches
the field gets a working endpoint, and the `enabled = true` +
`proxy_base = ""` combination can no longer be produced.

**The seam is the Settings default, not the `Sms` manifest model's.**
`settings_overrides` skips empty strings, so a manifest that declares
`proxy_base = ""` — which is what every clone stamped to date literally
contains — falls through to the Settings default and lands on the working
endpoint. Defaulting the manifest model would not have fixed those clones: an
explicit `""` in the file still resolves to `""`. This is the only seam where
"left blank" and "never mentioned" both reach the same working value.

`manifest.toml.j2` stops emitting the key entirely. Emitting `proxy_base = ""`
would make `cs config` flag every clone, because it reads declaration presence
from the raw TOML: a declared `""` against a resolved URL is a winner that
does not explain the resolved value, printed as `?` with a provenance note.

**Both guards stay, and both were reworded.** `cs/sms.py` and
`cs/campaign.py`'s `send_sms` still refuse on an empty endpoint — a clone can
deliberately blank it in the env layer and must still fail loudly rather than
post nowhere. What changed is what they say: telling an operator to set
`[sms].proxy_base` was correct when the field was required and is misleading
now that the wizard never asks about it. Reaching either guard means something
DECLARED the endpoint empty, so the messages say that and point at `cs config`
to name the layer. `send_sms`'s single compound condition is split in two so
the message names which of the two actually fired.

**Charter.** This puts a MrCall host inside `cs/`, and the rule-1 grep gate
caught it as a proposal, which is the gate working. It is recorded in
`tests/reviewed_literals.txt` as shared infrastructure the kernel drives — the
same category the charter already blesses for the mrcall-desktop engine and
the `mrcall.search_businesses` RPC. SMS bills against the platform credit pool
whichever clone sent it, so there is nothing per-company in the value. The
gate was not weakened.

### Migration — one clone-visible change, and it is not automatic

No clone's SMS state flips by itself. `[sms].enabled` is unchanged everywhere
and is still the only switch.

An existing clone whose manifest carries `proxy_base = ""` now resolves to the
kernel endpoint instead of an empty string. That is the fix, and it is only
observable if that clone ALSO has `enabled = true` — in which case it could
not send before and can now. Both current clones are unaffected: `mrcall-cs`
declares the real endpoint explicitly and resolves to the same value it always
did, and `124-cs` has `enabled = false`, verified after the upgrade.

To turn the endpoint off deliberately, declare it empty in the env layer
(`SMS_PROXY_BASE=`); the manifest layer can no longer express "blank" because
an empty string there means "not declared".

### Re-collaudo — FULL on both clones

This one is FULL and the tier is not softened to match what was actually run.

Two of the six triggers are touched by name: `cs/sms.py` and `cs/campaign.py`.
More importantly the release changes **send capability** — a clone with
`enabled = true` and a blank endpoint was inert and is now able to send. That
is precisely the class of change FULL exists to catch, and no argument from
"the control flow is identical" survives it. Every refusal that existed still
exists and only two message strings and one compound condition changed, but
the resolved VALUE of a send-path setting is different, which is the part that
matters.

**The collaudo suites were NOT run — the operator waived them.** Recording
the tier honestly means recording that this tag shipped without the suite its
own tier calls for. What was verified instead is stated in the operational-pin
note above: static-tier evidence plus four targeted checks on the real clone
manifests — `124-cs` stays off, `mrcall-cs` resolves unchanged, the previously
broken combination now resolves to a working endpoint, and a deliberately
blanked endpoint still trips the guard.

## v0.18.0 — 2026-08-24

### Why one release does two opposite things

This tag both DELETES configuration and ADDS it, and that is deliberate.

A manifest field has three lives — it can exist in the schema
(`cs/manifest.py`), be stamped into a clone's `manifest.toml` by the
template, and be read by code. Nothing in the kernel forced the three to
agree, so they drifted in both directions at once. Five fields were stamped
and read by nothing: a knob the operator can see and turn with no effect is
the worst kind of interface, because it advertises control that does not
exist. Three fields were read on every tick and stamped nowhere: working
machinery the operator cannot discover, because nothing in their
`manifest.toml` says it is there.

Shipping those as two releases would have described one inconsistency twice
and left the file half-true in between. The single sentence this release is
meant to leave with a reader is: **`manifest.toml` is now the list of knobs
that exist.** Removals and additions are the same edit seen from two sides.

### Removed — five stamped fields that no code path read

- **`[knobs].dry_run` and `[knobs].autonomous`.** Neither ever gated
  anything. Dry-run is the `commit` argument on every send function, fed by
  the `--commit` CLI flag; the `dry_run` keys returned throughout
  `cs/campaign.py` are output labels, not reads of a setting. Autonomy is
  `cs_triage_mode` plus the clone's `.claude/settings.json` permission
  surface. An operator who set `dry_run = false` expecting live sends got
  nothing, and `cs config` reported a control that does not exist.
- **`[repo].kernel_version`.** The `Manifest` model has no `[repo]` field, so
  the table is dropped at load; `_load_existing` reaches into the raw TOML for
  `git_remote` and nothing else. A version claim no code reads and no gate
  verifies is right only when somebody remembers. `requirements.txt` is the
  pin and the only answer worth reading. `docs/release-procedure.md` loses the
  row telling you to maintain it by hand.
- **`[skills]` and `[extensions]`.** Stamped as fully hardcoded literals —
  not even a Jinja variable in them — with no field on the model and no
  reader. `[skills]` in particular read as a live indirection layer pointing
  at the `company/*.md` slots. It was not one: repointing a path there
  changed nothing.
- **`[campaigns].posture_note`.** Prose that reached one rendered line and no
  code. Its sibling `excluded_campaign` is what actually enforces a carve-out,
  and that is untouched.

Also gone, invisible to operators: three render variables `cs project new`
computed that no `project_memory` template consumes
(`company_display_name`, `email_address`, `accounts_default`), and the
`firebase_sa_path` **init_data key**, which no `.j2` file reads because
`manifest.toml.j2` writes `sa_path = ""` as a literal. The **Settings field**
`firebase_sa_path` is untouched and still loads the service-account
credential for `cs/drive.py` and `cs/resolve.py`.

### Added — the three knobs the code reads on every tick

`[knobs].system_senders`, `[knobs].send_guard_min_chars` and
`[knobs].send_guard_banned_phrases` are now stamped, with comments saying
what they do. All three are read by live code — `cs/unanswered.py` excludes
system senders from the open-work sweep, `cs/send_guard.py` reads both guard
knobs — and until now were settable only through their env aliases.

The proof that this was a real gap rather than a tidy-up: **both clones
already declare `CS_SYSTEM_SENDERS` in their state-dir `.env`** and neither
had it anywhere in `manifest.toml`. The knob was in use and invisible in the
file the charter calls the one place values change.

Each is stamped at the kernel default, which means a clone stamped today
pins that default: if a future release changes it, this clone keeps the old
value until the operator edits the line. That is the same property
`dedup_days`, `sms_hour` and `reminder_max` have always had, and it is the
price of the value being visible at all.

`_load_existing` now carries all three, so re-running `cs init` in an
existing clone cannot silently reset them. That failure was real:
`posture_note` held genuine prose on both clones while `collect_config`
hardcoded it back to `""` and `_load_existing` did not return it at all.

### Not done — two proposals refused, with the reason

Two fields were proposed for removal in the same audit and are **kept**.
`founder_sweep_enabled` and `platform_env_path` were called dead by grepping
for attribute access on the settings object. That method stopped being
sufficient in `v0.13.0`: `cs/config_report.py` reads every field in
`type(settings).model_fields` in a loop, so no field is reader-less any more
and the question becomes whether what it reports is TRUE. For these two it
is — a founder sweep that is really on or off, an env layer `124-cs` really
loads through `[env].platform_env_path`. For `dry_run` it was not. That is
the line this release draws, and it is why the two lists differ.

`platform_env_path` additionally must stay in `settings_overrides`:
`env_file_chain` reads it out of the overrides dictionary, not off Settings,
and dropping it would silently delete a configuration layer from a live
clone.

Two further findings from the same audit are refuted and must not be
re-proposed. **`sms_proxy_base` is not orphaned** — it is read at
`cs/sms.py:30`, `:43` and `cs/campaign.py:708`, and the mother clone holds a
real endpoint. **`repo_docs_shape == 'generic'` is not a dead branch** — it
is the live discriminator between the mother clone and a company instance,
holds a different value on each of the two fixtures, and branches
`README.md.j2`, `CLAUDE.md.j2` and `docs/ARCHITECTURE.md.j2`. Acting on
either would break the mother clone.

There is one real defect nearby, filed and NOT fixed here: `cs init` prompts
"Enable SMS?" while `manifest.toml.j2` hardcodes `proxy_base = ""`, so
answering yes produces a manifest whose first send raises
`SmsError("[sms].proxy_base not set in manifest.toml")`. Loud and
actionable, but the wizard should not be able to emit it.

### Fixed — `cs update` rendered two files it was about to leave alone

`requirements.txt` and `manifest.toml` are clone-owned; the loop rendered
each and discarded the result. That render runs against the clone's frozen
`init_data`, so the moment a template grows a variable an older clone never
froze — exactly what this release does to `manifest.toml.j2` — it raises,
and every `cs update` prints `! failed to render manifest.toml.j2` about a
file it was never going to write. Both skips now sit above the render.

### Migration — no clone needs editing

A `dry_run`, `autonomous`, `posture_note`, `kernel_version`, `[skills]` or
`[extensions]` line surviving in an existing clone's `manifest.toml` is
inert: `Settings` and every manifest table are `extra="ignore"`. `cs update`
never re-renders `manifest.toml`, so nothing rewrites those files; delete
the dead lines at leisure, or at the next re-pin.

One visible change to existing clones: `docs/ARCHITECTURE.md` is re-rendered,
so its Knobs row loses the `dry_run` / `autonomous` cells and the
**Campaign posture** line disappears. On `mrcall-cs` that line was already
publishing a stale sentence — the frozen `init_data` held an older note than
`manifest.toml` did — which is the argument against the field rather than for
it. A clone that wants campaign-governance prose in its docs should put it in
a clone-authored `company/` slot, which is read by the operator agent, not in
a manifest key nothing reads.

Frozen `init_data` keys for the removed fields stay in
`template-manifest.json` and are harmless: Jinja tolerates an unused render
variable, and no template references them any more.

### Re-collaudo — STATIC on both clones

Not FULL. The six triggers in `CLAUDE.md` are send paths, `campaign`,
`gmail_archive`, `send_mail`, the auth boundary and the permission surface.
None is touched: `cs/campaign.py`, `cs/sms.py`, `cs/send_mail.py`,
`cs/send_guard.py`, `cs/gmail_archive.py`, `cs/auth.py` and
`.claude/settings.json.j2` are byte-identical in this release. Not `read`
either — no engine RPC, no live call can differ.

The two send-guard knobs are newly STAMPED but their stamped values are the
kernel defaults, and the env layer still outranks the manifest, so no
existing clone's guard changes: existing clones never get a re-rendered
`manifest.toml` at all.

Static tier here means one thing beyond the usual `cs config` / `cs --help`
checks, and it is the reason the tier is argued rather than assumed:
`cs update`'s render-and-skip ORDER changed, so the re-stamp itself must be
observed — `docs/ARCHITECTURE.md` applied, `manifest.toml` and
`requirements.txt` reported as clone-owned and left alone, and not one
`company/` prompt.

## v0.17.0 — 2026-08-24

### Fixed — `docs/ARCHITECTURE.md` carried hand-authored prose inside a template-owned file
- **Why:** the template declared its own last section "NOT stamped" and invited
  the operator to write there — the engine-profile provenance, what was
  authored into `USER_NOTES`, the send boundary as it actually stands, the
  checks that exist because something once went wrong, the known gaps. That put
  a clone's only durable record of how it was really built inside a file every
  `cs update` offers to replace, where taking the offer is the RIGHT answer for
  the stamped configuration table above it. That is what makes it a trap rather
  than a mistake: on `124-cs`, during the `v0.16.0` re-pin, the correct-looking
  answer deleted 59 authored lines, and they came back only because git had
  them. Restoring them at each release patches the symptom; a file that is
  half-generated and half-authored will keep eating the authored half.
- **What:** the section is gone from `docs/ARCHITECTURE.md.j2`. That file is now
  100% generated and always safe to overwrite. Its content belongs in
  `company/`, which since `v0.16.0` is created once and never touched again, so
  a new slot **`company/clone-notes.md`** holds it — a new slot rather than an
  existing one because the seven that were there are all skill-facing (what a
  support mail is about, who replies from where, what the unattended tick must
  escalate) and this is repo-facing prose about the clone itself.
  `ARCHITECTURE.md`'s tail now says what it cannot tell you and points at the
  slot, so a reader who expected the notes there is told where they went. The
  slot satisfies gate 1b like every other: 9 slots, all instructions.
- **Migration:** `cs update` creates `company/clone-notes.md` if the clone has
  none and will never touch it afterwards. **Existing authored content must be
  moved by hand BEFORE the update** — copy the "Clone-specific notes" section
  out of `docs/ARCHITECTURE.md` into the new slot, then let the update replace
  the file. Both live clones were migrated this way: `124-cs`'s eight
  paragraphs moved verbatim; `mrcall-cs`'s tail was byte-identical to the
  unfilled stub, so it had nothing to move and receives the instructions.
- **Re-collaudo:** **static tier, every clone.** Stamped prose and one new
  stamped file; no `cs/` behaviour changed at all — no send path, no
  `campaign`, no `gmail_archive`, no `send_mail`, no auth boundary, no
  permission surface. MINOR rather than PATCH because a clone gains a file and
  loses a section of another, which is observable. **The suites were NOT run
  for this tag** — the operator waived them; the tier is the requirement, not a
  record of a passed collaudo.

## v0.16.0 — 2026-08-24

### Fixed — one company's operational facts shipped inside the project templates
- **Why:** the charter forbids a company literal anywhere in `cs/`, and
  `cs/templates/project/` is inside `cs/`. Its `company/*.md.j2` slots are
  stamped into every clone and then authored per company — and what they
  carried was the mother clone's own operational record. `claude-extra.md.j2`
  was 23 lines of one company's internal configurator API, complete with base
  URLs, endpoint table and two dated "verified live on production" claims.
  `operator-out-of-scope.md.j2` told every clone's unattended operator not to
  touch a legacy migration cron and not to perform a specific Friday
  `service_number` cutover. `campaign-product-notes.md.j2` was a single
  Italian line. Two more of the same class sat outside `company/`:
  `cs-triage-mail`'s two worked examples named four real customers of the
  mother clone, and the stamped `CLAUDE.md` named that company's engine
  service-user home. Every clone of every other company received all of it as
  fact.
- **What the gate missed, and why:** `cs/templates/` was never excluded from
  the scan — it is walked, and both existing approvals in
  `tests/reviewed_literals.txt` are template files. The wordlist simply had no
  term for any of this. It carried the mailbox *domain* and never the bare
  brand, so `<brand>-agent`, `/api/<brand>/` and `~<brand>d/` all greped clean;
  and no wordlist can describe "the Friday cutover". The gate now has two more
  legs. It greps the **bare brand**, with the charter's own three
  shared-infrastructure forms (the mrcall-desktop engine, the mrcall-tracking
  adapter id, the `mrcall.search_businesses` RPC method) stripped **by
  pattern** before judging — ~50 lines identical for every clone, which line-by
  -line entries would only bury the real proposals in and which would go stale
  on the next reword; every other use of the brand still reaches the operator
  as a proposal. And a new **gate 1b** holds `company/` slots to a shape
  instead of a vocabulary: each must carry a `## What to write here` section,
  and none may carry a dated claim, a named weekday, a URL, a mail address, an
  API path or another user's home. Run against the pre-fix templates, today's
  gate reports 10 unreviewed literals and 17 slot violations and exits 1.
- **What else changed:** all eight slots are rewritten as instructions — what
  to write there, which skill reads it, and what goes wrong while it is empty.
  Three of them (`operator-out-of-scope`, `campaign-product-notes`,
  `drive-visible-note`) were orphans that nothing read, so `/cs-operator` step
  5 and `/cs-campaign-tick` now point at them; that pointer is also what
  replaced the company facts those two skills had hardcoded. No new per-line
  approval was needed in `tests/reviewed_literals.txt`: every literal was
  removed rather than admitted.
- **Migration:** none to run. `cs update` restamps nothing under `company/`
  (see the entry below), so a clone that has already authored its slots keeps
  them untouched; a clone that never authored one now receives instructions
  where it used to receive another company's facts.
- **Re-collaudo:** **static tier, every clone.** The only observable change is
  stamped prose plus the `cs update` output. No send path, no `campaign`, no
  `gmail_archive`, no `send_mail`, no auth boundary, no permission surface.
  **The suites were NOT run for this tag** — the operator waived them; the
  tier above is the requirement, not a record of a passed collaudo.

### Changed — `company/**` is create-if-missing, never overwritten, never prompted about
- **Why:** the operator is *told* to author those slots, so an authored slot
  diverges from its stored checksum permanently. They were checksum-tracked
  like any other render, which meant every release that reworded one asked
  "modified locally AND template changed. Overwrite? [y/N/diff]" about all of
  them, in every clone — a prompt whose only correct answer is always No,
  which is exactly the kind an operator learns to answer without reading, and
  where one wrong "y" destroys prose no template can regenerate. This release,
  which rewords all eight, is the one that would have asked eight times per
  clone: verified against a copy of a live clone's real manifest and authored
  slots, old logic + new templates gives 8 prompts, the fix gives 0.
- **What:** `CLONE_AUTHORED_PREFIXES` (`cs/project_init.py`) marks the class.
  `cs update` creates a slot only when the clone has none, and otherwise leaves
  it alone silently — `-v` reports what it left, since a file that was not
  touched is not an event. `cs init` re-run in place (the documented restamp,
  `dest_dir "."`) no longer overwrites an authored slot either, which it did
  silently before. Neither writes a `company/` path into `file_checksums`.
  Same class as `requirements.txt` and `manifest.toml`.
- **Migration:** none. The stale `company/` checksum entries both clones carry
  are dropped from `template-manifest.json` on the next `cs update`, and
  nothing reads them before that — the new branch returns before the stored
  checksums are consulted at all.
- **Re-collaudo:** **static tier, every clone** — the evidence is the `cs
  update` output itself (no `company/` prompt, authored slots byte-identical,
  no `company/` keys left in `template-manifest.json`). MINOR rather than
  PATCH because a verb that stops prompting is observable, and an operator
  reading "patch" is entitled to expect nothing observable changed. **The
  suites were NOT run for this tag** — the operator waived them.

## v0.15.0 — 2026-08-24

### Changed — the clone index is an index again
- **Why:** a stamped clone's `CLAUDE.md` had grown to 290 lines against a
  221-line thin-index limit that had already been raised once from the
  200-line default, so the doc-harness gate failed inside the clone. Raising
  the limit a second time would have conceded the point: the file had drifted
  from an index into a manual — a verb catalogue restating `cs --help`, the
  auth chain's internals, the three-move `handled` procedure, the
  customer-load steps.
- **What:** the index now routes instead of restating. The verb catalogue
  defers to `cs --help` (a list copied into prose goes stale on the next
  kernel pin), the auth-chain internals to the installed kernel's
  `cs/auth.py` docstring, the `handled` procedure to
  `.claude/commands/cs-review.md` § Posture, the customer-load detail to the
  `cs-customer` skill — which already owns the memory write-back path too.
  Kept verbatim, because nothing else reachable from a clone says them: the
  safety NEVERs, the template-owned/clone-owned split, the dossier-mandatory
  pipeline step, `--account`'s exit-2 refusal on the Gmail-IMAP verbs, and
  `cs config`'s primacy over any value written into a document. The RPC
  wrapper-key table stays for the same reason — two of its four shapes
  (`emails.list_by_thread` → `{emails}`, and the `campaign.*` writes that
  return a dict rather than the bare array their siblings return) have no
  other owner a clone can reach, and a wrong key returns 0 rows silently.
  `cs/templates/project/CLAUDE.md.j2` goes 301 → 192 lines; a stamped clone
  renders 290 → 187 by the gate's own `len(text.splitlines())` counter.
- **Migration:** none to run — `cs update` applies it. A clone whose
  `CLAUDE.md` still matches what it was stamped with takes the new file
  silently; a clone that edited its own copy is asked before anything is
  overwritten, and that file is template-owned anyway, so the edit belongs in
  the kernel template.
- **Re-collaudo:** **static tier, every clone** — stamped prose only. No
  `cs/` code changed: no send path, no `campaign`, no `gmail_archive`, no
  `send_mail`, no auth boundary, no permission surface. MINOR rather than
  PATCH because 103 lines leaving every clone's stamped index is observable,
  and an operator reading "patch" is entitled to expect nothing observable
  changed. **The suites were NOT run for this tag** — the operator waived
  them; the tier above is the requirement, not a record of a passed collaudo.

### Fixed — per-session agent memory was committable, here and in every clone
- **Why:** `docs/sessions/<session-id>.md` is per-machine, per-session agent
  memory that names clones, hosts and absolute paths. The doc-harness writes
  its `docs/sessions/` ignore line only when it BOOTSTRAPS a repo
  (`/doc-create` step 3); no later command adds it. So a repo bootstrapped
  before that step existed never received the line — this repo did not, and
  one session file had already been committed into a public tree. No stamped
  clone received it either: a clone's `.gitignore` is rendered from
  `cs/templates/project/.gitignore.j2`, which carried no such line, and the
  file is template-owned — a line added inside a clone is a local edit to a
  file the next template change offers to overwrite, so it is not the durable
  place for the fix.
- **What:** the `docs/sessions/` entry is now in this repo's `.gitignore` and
  in `.gitignore.j2`, each with the reason written beside it. The one session
  file that had been committed here is untracked and kept on disk.
- **Migration:** none. Existing session files stay where they are and leave
  `git status`; nothing is deleted.
- **Re-collaudo:** **static tier, every clone** — a `.gitignore` line. It
  reaches a clone on its next `cs update` and touches no `cs/` code, no send
  path and no permission surface. **The suites were NOT run for this tag**
  (see above).

## v0.14.0 — 2026-08-24

### Added — a finished campaign delivers NOTHING, on any path
- **Why:** on 2026-08-23 the autonomous `mrcall-cs` operator was handed 26
  `send_sms` items for a campaign that had ended on 31 July. The SMS would
  have told 26 real customers that their phone number changes at a moment
  three weeks in the past. The pack said the campaign was over twice —
  `status` was never flipped after the campaign closed, and
  `dates = "2026-07-22..31"` was documented in the loader as "prose: when it
  ran" — and **nothing in the kernel read either field**. The tick noticed
  the contradiction itself and wrote `CS_PAUSE`; the kill switch worked, but
  the work should never have been offered. The sibling pack had said
  `status = "done"` since June and would have delivered identically, saved
  only by being excluded BY NAME in that clone's `manifest.toml` — a
  per-clone workaround for a runner with no notion of a campaign being over.
- **What:** two declarations in `[pack]` (`cs/campaign_pack.py`), both now
  enforced. **`status`** is `active` or `done` and nothing else; an
  unrecognised value is a `PackError` at LOAD, because a field that decides
  whether a campaign may deliver at all does not get to be guessed. Only an
  ABSENT key defaults to `active`. **`ends_on`** is a NEW TYPED field: a date
  past which the pack refuses to deliver **even while `status = "active"`** —
  the backstop for the day the human forgets, which is the case that actually
  bit. It takes a TOML date literal (`ends_on = 2026-07-31`), the same date
  as an ISO string, or the word `"never"` for a campaign with no end;
  anything else refuses at load, because "cannot parse it, so assume no
  limit" is exactly how this class of bug survives.
- **`dates` is deliberately NOT parsed.** It legitimately holds free prose (a
  live pack reads `continuous from 2026-08`), so a parser over it would
  either half-work on a send path or refuse a value never meant to be a date
  and break a running campaign. Typed field and prose field, one job each.
- **An undeclared end is an advisory, never an expiry.** A pack with no
  `ends_on` at all still delivers indefinitely — the open-ended onboarding
  loop must not acquire an expiry by accident — and carries
  `Pack.undeclared_end_note()`, surfaced by the worklist as `pack_note`. This
  keeps "nobody declared an end" distinguishable from "this campaign has no
  end"; only the second is a decision.
- **Guarded at every delivery site, not just the worklist.** `pending()`,
  `send_first`, `_pack_send_preamble` (so `send_reminder` + `send_sms`) and
  the composed-draft `send_draft` / `queue_draft` — each of the last four is
  reachable with a contact id **without** going through `pending()`, so a gate
  only on the worklist would have left every one of them firing. The gate
  compares against the operator's MARKET calendar day (`_market_today`), the
  same clock the reminder and SMS windows use: a campaign ends at the close of
  a business day where the business is, not at midnight UTC. A pack that
  EXISTS but cannot be LOADED now refuses those paths too — an unreadable pack
  is not evidence that the campaign is running.
- **`queue_draft` is gated even though it sends nothing.** What it produces is
  a message addressed to a customer sitting one keystroke from the wire. That
  is a delivery path, not a report.
- **Refusals are visible, never silent drops.** `pending()` reports
  `delivery_blocked` (reason + date) plus `held` (counts per withheld action)
  instead of quietly shortening the worklist; each sender returns the same
  sentence with `finished: true`; and `cs campaign packs` prints the
  EFFECTIVE status, so a pack past its own `ends_on` reads `ended` rather than
  the `active` its file still claims — a listing that disagrees with the send
  paths is a trap. `handle_reply` and `reconcile` deliberately SURVIVE a
  finished campaign: a customer who wrote to us is owed an answer whether or
  not the campaign that prompted the mail is over, and reconciling a stale row
  sends nothing.
- **Stamped surface:** `/cs-campaign` now ASKS when the campaign ends and
  writes the answer into `ends_on`; `/cs-campaign-tick` is told that
  `delivery_blocked` is not to be worked around — report the reason, and a
  campaign you believe is still running is an escalation, never your own call;
  `campaigns/README.md` gains a "When the campaign is over" section.
- **Migration note:** nothing breaks. A pack with no `ends_on` and no
  `status`, or `status = "active"`, behaves exactly as before and delivers;
  the only new outcome is the `pack_note` advisory. A pack already saying
  `status = "done"` STOPS delivering, which is the point. Before upgrading,
  check each clone's `campaigns/*/campaign.toml` for a `status` value that is
  neither `active` nor `done` (e.g. `"paused"`, `"draft"`, an empty string) —
  that is now a load-time refusal, and the fix is to write one of the two
  words.

### Gates
- Gate 33 (`tests/test_campaign_finished.py`) covers the whole surface:
  `status` validation at load, `ends_on` accepting a date literal / an ISO
  string / `"never"` and refusing everything else, `dates` staying unparsed,
  the last-day boundary, an active pack delivering on all five paths, `done`
  and expired refusing on all five, a pack with no end date delivering
  indefinitely, `pending()` holding the sends while keeping the replies, the
  advisory for an undeclared end, an unloadable pack refusing every delivery
  path, and a campaign with NO pack behaving exactly as before. 33 gates, all
  green at the tag.
- **Re-collaudo: FULL, both clones (`mrcall-cs`, `124-cs`).** It touches
  `cs/campaign.py` and every send path, which the standing rule (CLAUDE.md
  invariant 4 / Tests section) escalates to FULL regardless of diff size. It
  earns the tier on its own terms too: a bug here fails in the direction of
  refusing a campaign that should deliver, and `mrcall-cs`'s
  `new-signup-onboarding` pack is mailing real customers hourly — a false
  refusal is a silent outage of the only running campaign, and a load-time
  `PackError` on any pack breaks `cs campaign pending` for the whole tick.
  Neither is observable except by loading the real packs.

## v0.13.0 — 2026-08-24

### Added — `cs config`: the settings actually in force, and which file declares each
- **Why:** six value layers resolve into one setting, and nothing printed the
  result. A reader — human or headless — had to mentally execute the
  precedence rules over `manifest.toml` and the `.env` chain, and two
  consecutive `mrcall-cs` ticks got it wrong in the expensive direction: they
  observed "no `CS_TRIAGE_MODE` in the environment", concluded "so the default
  `draft` applies", and declined to send mail the operator had deliberately
  authorised in `manifest.toml`. The layering was correct throughout; the
  resolved value was simply invisible.
- **What:** `cs config [--all] [--json] [--strict]` (`cs/config_report.py`,
  wired at `cs/cli.py`). For every behaviour-deciding setting it prints the
  value IN FORCE and the layer that declares it, named down to the TOML
  table+key or the env KEY, and reports `kernel default` when nothing declares
  it. A setting declared in more than one place is surfaced as a
  `DUPLICATE DECLARATIONS` block with the winner named — a duplicate is a
  defect even when the two copies agree today. Read-only and network-free, and
  no secret value reaches the text report, `--json` or `--all`. Exit stays 0 on
  a duplicate (a read verb that answers the question must not look like it
  failed); `--strict` is the hook for a wrapper that wants the exit code.
- **Stamped surface:** `/cs-operator` gains step 2b — read `cs config` before
  acting and carry `cs_triage_mode` AND its source into the tick report; the
  skill is now explicit that the mode is never inferred and that "no env var"
  is not "so the default applies". `cs config` is added to the four
  permission-allow spellings, to `/cs-help`'s deeper-reading list, and to
  `CLAUDE.md` / `README.md` / `docs/ARCHITECTURE.md`. `.env.example` stops
  pre-writing `CS_TRIAGE_MODE` / `CS_DRIVE` values, which made the file a
  second declaration site by default.

### Added — `cs draft-delete`: take ONE bad draft out of Gmail Drafts
- **Why:** a draft is a loaded gun until somebody removes it. On 2026-08-23 an
  engine compose invented a quoted sentence and attributed it to a customer who
  had never written it; the operator wrote a clean replacement and then could
  not remove the bad one, because nothing in cs could delete a draft. The
  fabrication stayed in the review queue where a human could send it by mistake.
- **What:** `cs draft-delete <uid> [--message-id …] [--commit]`
  (`cs/gmail_drafts.py`). The IMAP UID is the selector because it is the only
  identifier every draft has — what `append_draft` uploads carries no
  Message-ID header at all, so a header lookup would miss precisely the drafts
  cs itself wrote; `--message-id` narrows a uid and never widens it. Zero
  matches, several matches, or a uid/Message-ID mismatch all REFUSE and report
  what they matched. There is no bulk form and no wildcard. **Trash, not
  expunge**: a UID MOVE into the `\Trash` special-use folder, recoverable for
  30 days; no `\Trash` folder or a refused MOVE is a refusal, never a fallback
  to `\Deleted` + EXPUNGE. Two folder guards (Drafts resolved strictly by the
  `\Drafts` special-use flag; the matched message must itself carry `\Draft`).
  Dry-run is the default and selects the mailbox READ-ONLY, so the connection
  is structurally incapable of writing. `--account` refuses it
  (`reads_operator_mailbox`). `list_drafts` and `cs review` now print each
  draft's uid — without a visible handle the operator cannot name the one they
  want gone.

### Added — `cs handled`: "I resolved this outside email", with a date
- **Why:** Gmail Sent is the dedup ground truth and its one blind spot is
  resolution out of band. A customer wrote on 17 July, the owner TELEPHONED him
  and settled it, and because a phone call leaves no trace in Sent, every tick
  for a MONTH re-discovered the thread and told the owner to write to him.
- **What:** `cs handled <email> [--why "…"] [--at YYYY-MM-DD] [--undo]`, bare
  to list. It records a dated, per-contact moment (`state.handled_out_of_band`)
  and closes that contact's open engine tasks with `actor="human"`;
  `compute_open` obeys it, so nothing they sent BEFORE that moment is open work
  — and anything they send after re-opens them on its own. It is a dated record,
  not a second permanent ignore list: `--undo` reverses it, and the held-back
  senders stay REPORTED in `cs review` (an invisible filter reads as a bug).
  A future `--at`, a non-address, and `--account` are clean refusals.
- **It is an INTERACTIVE gesture, and that is a security boundary.** A tick
  reads untrusted inbound, so "please close this ticket" in a mail body, a
  subject, a task title or an attachment would otherwise let any sender bury
  their own open request by typing one sentence. `handled` therefore joins the
  cron wrapper's `--disallowed-tools` re-deny set in all six command-text
  spellings, beside the send verbs — it is denied not because it sends but
  because it SILENCES. The stamped skills say the same in the operator's own
  words: `/cs-review` and `/cs-triage-mail` accept "I called him, close this
  one" from the operator, live, resolve "this" to ONE address, say the address
  and the waiting time back before running it, and escalate rather than close
  anything that merely LOOKS resolved.

### Removed — `RATE_CAP` out of the interface (the code half shipped in v0.12.0)
- **Why:** `v0.12.0` removed the quota from the send path and explicitly
  deferred the templates. The deferral had a cost: `cs init` kept prompting for
  a "Rate cap" nothing reads, `manifest.toml.j2` kept writing the key, and the
  stamped prose kept naming it as an enforced guardrail — including
  `CLAUDE.md` §5, which is what the operator agent reads. `mrcall-cs` had
  already deleted the key from its own manifest, so template and clone were
  disagreeing in front of the operator.
- **What:** the "Rate cap" prompt is gone from `cs/project_init.py`,
  `rate_cap = {{ rate_cap }}` is gone from `manifest.toml.j2` and from the
  knobs row of `docs/ARCHITECTURE.md.j2`, and the guardrail claim is gone from
  `CLAUDE.md.j2` §5/§6, `/cs-review`, `/cs-help`, `/cs-campaign` and
  `campaigns/README.md.j2` — replaced by what is true: dedup is hard, `CS_PAUSE`
  is the stop, there is no per-day quota. The kernel's own `README.md` loses its
  "rate caps" claim and gains `config` and `draft-delete` in the verb map.
- **Migration note:** unchanged from `v0.12.0` — a `rate_cap` line surviving in
  an existing clone's `manifest.toml`, or `RATE_CAP` in its env, is inert
  (`extra="ignore"`) and can be deleted at leisure. `cs update` will simply
  stop re-stamping it. A clone's frozen `template-manifest.json` may still
  carry a `rate_cap` init_data key; it is now an unused render variable, which
  Jinja tolerates, so no clone needs editing for this release.

### Changed — §7 Rollout no longer tells a clone which phase it is in
- **Why:** the stamped `CLAUDE.md` §7 asserted "Phase 1 (now) —
  operator-in-the-loop, `CS_TRIAGE_MODE=draft`". False on `mrcall-cs` since
  2026-08-23, and an agent reads a stamped sentence as ground truth: it is part
  of why two headless ticks declined to send. No rollout narrative can know
  which phase its reader is in — a `cs update`, an env layer or one manifest
  edit moves it and the prose does not follow.
- **What:** §7 now describes the draft phase and the send phase, asserts
  neither, and directs the reader to `cs config` for the resolved
  `cs_triage_mode` and the file it comes from. `README.md.j2` and
  `docs/ARCHITECTURE.md.j2` get the same treatment: the architecture table is
  labelled "Declared, not resolved", because every cell in it is stamped from
  `manifest.toml`, which is one layer of six.

### Changed — `[campaigns].excluded_campaign` holds MORE THAN ONE campaign
- **Why:** a clone finished two related campaigns — one and its `-batch2`
  sibling — and the field was a single string matched with `==`. Only the
  first was excluded, so for a month the general operator kept picking up the
  second one's `handle_reply` actions on a campaign nobody was running. There
  is no way to close a campaign instead: the engine registers `create`,
  `list`, `add_contact`, `contacts` and `update_contact` and no
  `campaign.close`, and the kernel filters on no `status` anywhere. The
  exclusion list is the only lever, so it has to hold more than one name.
- **What:** the field is now comma-separated, parsed by
  `Settings.excluded_campaign_set` — the same shape as every other
  multi-value knob in `cs/config.py` (`self_emails`, `system_senders`,
  `send_guard_banned_phrases`). All three call sites move together
  (`campaign.pending`, `_pack_send_preamble`, `send_first`): a contact reached
  by id never passes through `pending`, so a list honoured only there would
  leave both pack senders firing into a finished campaign. `cs config` prints
  several names with a space after each comma.
- **Matching stays EXACT, per name.** A prefix rule would be a shorter diff
  and would then silently swallow every future `<name>-anything` campaign —
  this bug, inverted. Two explicit names is the honest configuration.
- **Migration note: none. Nothing to edit in any clone.** A single bare name
  is the one-element case and behaves exactly as before; the key is not
  renamed, so no stamped clone breaks and no alias is needed. Empty,
  whitespace and `","` all mean "exclude nothing" — `""` is never a member of
  the set, so a contact whose campaign-name lookup comes back blank is still
  not treated as excluded. A clone that wants two campaigns excluded writes
  them into its own `manifest.toml`; `cs update` never touches that file.

### Gates
- Gate 32 covers the exclusion list: one bare name (the old shape), several
  names, empty/whitespace/`","`, the prefix trap at all three call sites, the
  manifest→override→single-parse path, and the `cs config` rendering.
- `tests/run.sh` grows gate 30 (`handled`: dated suppression, re-open on a
  newer inbound, held-back senders still reported, idempotent + undoable,
  `actor="human"` task close reading `id` and not `task_id`, and `sweep()`
  actually feeding the ledger into the open-logic) and gate 31 (`cs config`:
  the winning layer named down to table+key / env KEY, an env override
  reported as winner with BOTH declarations surfaced, "kernel default" for an
  undeclared knob, alias-spelling duplicates flagged, and no secret in the
  text report / `--json` / `--all`). Gate 29 covers `draft-delete`. Gate 17,
  the deny-enumeration gate, now compares 30 deny entries + 4 keeps for exact,
  order-preserving equality across the six spellings. `cs config` joins the
  full `--help` tree in gate 4. 32 gates, all green at the tag.
- **Re-collaudo: FULL, both clones (`mrcall-cs`, `124-cs`)** — this changes
  the **permission surface**: `bin/cs_operator_cron.sh.j2`'s
  `--disallowed-tools` set and `.claude/settings.json.j2`'s allow list both
  move, which the standing rule (CLAUDE.md invariant 4 / Tests section)
  escalates to FULL regardless of diff size. `cs/campaign.py` changes too
  (the exclusion list), which is on the same list independently. `124-cs` is
  on `v0.9.6` and crosses four minor versions to get here.

## v0.12.0 — 2026-08-23

### Removed — `RATE_CAP`, the per-day send quota that silently dropped contacts
- **Why:** a quota does not prevent the failure it exists for — it scales it
  down. If a send loop is working, there is no reason to stop it helping
  customers; if it is broken, twenty-five wrong emails is an incident just
  the same as two hundred, and the quota bought nothing but a smaller number
  on the incident report. The cost was paid every day: at the cap the kernel
  returned a per-contact refusal and the run carried on, so real contacts
  were skipped in silence — worst in a discovery-driven loop, where a
  contact skipped at the cap does not come back with priority tomorrow, it
  competes with the same cap again, and once it ages out of a producer's
  trailing window it is never seen again. The mechanism also lied about
  itself: its own message said "stop, do not partial-blast" and never
  stopped anything — stopping was left to a caller with no idea it was
  supposed to. Full rationale in mrcall-cs
  `docs/briefs/2026-08-23-rate-cap-silently-drops-customers.md`.
- **What:** `_rate_capped()` and every call site are gone —
  `campaign.send_draft`, `send_reminder`, `send_first`, `send_sms`
  (`cs/campaign.py`), and the separate copy in `cs/sms.py`. `[knobs].rate_cap`
  is removed from the manifest schema (`cs/manifest.py`) and from `Settings`
  (`cs/config.py`); a `rate_cap` key surviving in an existing clone's
  `manifest.toml`, or a `RATE_CAP` value surviving in its env, is now inert —
  ignored at load (`extra="ignore"`), never validated, never read. Nothing
  replaces it on the send path: the correct response to something anomalous
  is the kill-switch (`CS_PAUSE`), not a quota — stop everything and tell a
  human, rather than continuing at a reduced rate. `State.sent_today()` and
  `_record_send()` — the send ledger the cap read but never owned — are
  UNCHANGED; dedup is untouched by this release.
- **Migration note:** no manifest edit is required for an existing clone —
  a stale `rate_cap =` line in `manifest.toml`, or `RATE_CAP` in its env, is
  now harmless and can be removed at leisure, never enforced either way.
  `cs init`'s "Rate cap" wizard prompt and the `rate_cap` line it still
  writes into a freshly rendered `manifest.toml` are untouched by this
  release — they are now fully inert on both new and existing clones and
  are tracked as follow-up cleanup of the kernel's own templates
  (`cs/project_init.py`, `manifest.toml.j2`, `docs/ARCHITECTURE.md.j2`, and
  the `.j2` prose still naming `RATE_CAP` as a live guardrail), not shipped
  in this release.
- **Re-collaudo: FULL, both clones (`mrcall-cs`, `124-cs`)** — touches the
  send paths directly (`cs/campaign.py`, `cs/sms.py`), which is FULL
  regardless of diff size per the standing rule (CLAUDE.md invariant 4 /
  Tests section).

## v0.11.1 — 2026-08-22

### Added — `cs init` wizard refactor documented (hotfix: omitted from v0.11.0)
- **What:** `cs init` wizard refactored: 6-phase essential-by-default
  prompting, `--advanced` flag for full control, existing-manifest prefill,
  MrCall-managed fields hardcoded (SMS, producer adapter, campaign
  exclusions, cron schedule, drive scope, Firebase SA path, kernel version,
  docs shape). Behavior unchanged; UI only.
- **Scope:** init wizard, templates (`manifest.toml.j2`, `.env.example.j2`,
  `docs/ARCHITECTURE.md.j2`), `project_init.py`.
- **Re-collaudo:** **static tier, both clones (`mrcall-cs`, `124-cs`)** — no
  send paths, campaign, gmail_archive, send_mail, auth, or permissions
  touched.

## v0.11.0 — 2026-08-22

### Fixed — `cs cron status` only reported half of what stops a send
- **Why:** the command printed whether the crontab tag was installed, but
  said nothing about `CS_PAUSE` — an independent kill-switch that blocks
  every send even while the crontab entry IS installed. The reverse gap is
  just as misleading the other way: an installed pause file alone says
  nothing about whether cron is even wired. An operator reading only one
  of the two signals could reasonably, and wrongly, conclude the operator
  is fully idle or fully live.
- **What:** `cmd_cron_status` now reports both signals, independently:
  `Crontab: installed` / `Crontab: not installed. Run: cs cron install`,
  and `Pause: active (<path> exists — operator will not send). Run: rm
  <path> to resume` / `Pause: not active (<path> absent)`, read directly
  from `settings.pause_path`. The manifest-schedule line is unchanged.
- **Migration note:** none — output only; no state or config is touched.
- **Re-collaudo:** **static tier, both clones (`mrcall-cs`, `124-cs`)** —
  a UI enhancement to one status verb's printed output; zero behavior
  change to any send path, campaign lifecycle, or permission surface.

## v0.10.0 — 2026-08-21

### Added — every agent reads the same commands; `.claude/` is the one source
- **Why:** a clone's `.opencode/commands/` was a git-tracked COPY of the
  commands, frozen in July, still offering `/munchausen` and the other
  pre-`cs-` names weeks after `.claude/commands/` had been renamed — found
  by an operator opening OpenCode and seeing the old menu. The kernel only
  ever rendered `.claude/`, so nothing kept the two in step. A second copy
  is a second source, and it drifts.
- **What:** `cs init` AND `cs update` now point every other agent surface
  into `.claude/` — `.opencode/commands/*.md`, `.opencode/skills`,
  `AGENTS.md` → `CLAUDE.md` (the file both OpenCode and Codex read as
  project instructions), and `~/.codex/prompts/*.md`. Symlinks, so
  divergence is impossible by construction; a filesystem that refuses them
  (Windows without Developer Mode) falls back to copies and says so.
  No new verb: the operator already runs these two.
- **The one question it asks:** Codex has no project-level prompt
  directory — its prompts are per-USER, one namespace shared by every
  clone on the machine. Pointing them at this clone would take `/cs-*`
  away from another, so when they already belong elsewhere it asks, and
  a closed stdin resolves to No (the v0.5.2 EOF contract).
- **Migration note:** an existing clone picks all of this up on its next
  `cs update`. If its `.opencode/` holds hand-edited copies, they are
  replaced by links to `.claude/` — the whole point — so lift anything
  worth keeping into the kernel template first.
- **Re-collaudo:** **static tier, both clones** — no send path, auth
  boundary or permission byte changes; the rendered `.claude/` set is
  byte-identical, only the other surfaces gain links to it. Do look at
  the Codex question on the SECOND clone stamped: that is the one that
  gets asked.

## v0.9.6 — 2026-08-21

### Changed — the CLASSIFIER default is the model we measured, three weeks late
- **Why:** the 2026-07-28 A/B measured `@glm` on the classifier's REAL task
  (61 live replies, engine baseline, hand-adjudicated gold, scored through
  the clone's own parser): ties the engine's accuracy on the calls both
  completed (56/58), zero unagreed schedule writes, answered 61/61 where the
  engine's transport failed 3, 3.1s vs 33s median, $1.17/1k calls. The
  recommendation was written down and never wired: with `MODEL_CLASSIFIER`
  unset, the role fell through to `Tier.WORKER = @claude-sonnet`, so every
  classification billed a frontier model at $2/$10 per 1M. Caught by an
  operator reading `cs llm` and asking why.
- **What:** new `ROLE_FAMILIES` — a role-level default consulted before the
  tier's, per provider. `Role.CLASSIFIER` → `@glm` on OpenRouter (and on
  `custom`, which borrows OpenRouter's ids). Anthropic direct is listed
  explicitly as EMPTY and keeps `@claude-sonnet`: `@glm` is not served on
  that wire. Env precedence is unchanged — `MODEL_CLASSIFIER` /
  `MODEL_WORKER` still win.
- **Caught while building it:** the first cut let ANY unlisted provider
  borrow OpenRouter's role table, which resolved `z-ai/glm-*` on the
  Anthropic-direct wire — a default that cannot resolve, the same class as
  the `CS_LLM_PROVIDER=custom` typo this module already refuses. Now every
  known provider is listed explicitly, empty included, and four new
  assertions in `tests/test_llm_client.py` hold that line.
- **Migration note:** a clone on OpenRouter with no `MODEL_CLASSIFIER` set
  changes model on its next re-pin — cheaper and ~10x faster, on the
  measured task. Pin the old behaviour with `MODEL_CLASSIFIER=@claude-sonnet`
  if you want to compare.
- **Re-collaudo:** **static tier, both clones** — no send path, auth boundary
  or permission byte changes. NOTE for whoever runs it: this default also
  reaches the send guard's register judgment, whose task is NOT what the A/B
  measured (that was reply classification). Read a few real guard verdicts
  after the first re-pin before trusting it unattended.

## v0.9.5 — 2026-08-21

### Fixed — the LLM client was an undocumented optional extra a safety path depends on
- **Why:** `anthropic` shipped as the optional extra `cs-kernel[llm]`,
  named nowhere a reader would look (only in a cold-storage archive
  entry). Meanwhile `cs/send_guard.py`'s register judgment calls
  `worker_llm.classify` on the model-composed send path. A clone that
  installed the normal way therefore ran that SAFETY check in degraded
  mode, and said so only in a log line nobody reads. A dependency a
  safety path reaches for is a dependency, not an extra.
  **Measured 2026-08-21, not assumed** (`llm_available()` in each clone):
  `mrcall-cs` = True — SDK present and `OPENROUTER_API_KEY` set in its
  `.env`, so its register judgment has been LIVE, not degraded;
  `124-cs` = False, SDK missing. The split is exactly the accident this
  entry removes.
- **What:** `anthropic>=0.107` moves into the base dependencies —
  installed always. The `[llm]` extra stays as a no-op alias so any
  existing `cs-kernel[llm]` install line still resolves. `llm_available()`
  stops advising the extra and says the install is broken. The clone's
  `.env.example` gains the block that was missing entirely: what the
  kernel's own model calls are, which key to set
  (`OPENROUTER_API_KEY` / `ANTHROPIC_API_KEY`), what happens without one,
  and the `cs llm` / `cs llm test` verbs. The README gains the
  three-payers table (your session / the engine / the kernel).
- **Migration note:** re-pinning installs `anthropic` automatically.
  Runtime effect depends on whether that clone already has a provider
  key: with none, nothing changes (the guard degrades exactly as before);
  with one, the register judgment starts running — which for `124-cs`
  means its first re-pin turns it on, since its `.env` question is now
  the only thing standing between it and the live judgment.
- **Re-collaudo:** **static tier, both clones** — a new base dependency
  plus documentation. No code path changes shape; the guard's behaviour
  with no key is byte-identical to before.

## v0.9.4 — 2026-08-21

### Fixed — `cs update` stops talking to itself
- **Why:** every run ended with three lines written for the kernel's own
  maintainers, not for the operator: "Remember the re-collaudo per the
  new tag's CHANGELOG entry before un-pausing operators" (internal
  vocabulary — *collaudo* is our verification procedure, meaningless to
  anyone else), plus two `· … never touches it` notices announcing files
  that had NOT been touched. A file that was not touched is not an event.
- **What:** the re-collaudo sentence is gone from the upgrade path. The
  two "left alone" notices move behind a new `-v` / `--verbose` flag,
  and say something a reader can act on when asked for
  ("requirements.txt is yours (the version pin) — left alone").
  A normal `cs update` now prints only what it actually did.
- **Re-collaudo:** **static tier, both clones** — output only.

## v0.9.3 — 2026-08-21

### Fixed — `cs update --check` recommended the wrong upgrade path
- **Why:** `--check` still ended with "Re-pin explicitly with `cs update
  --pin <tag>`, then `pip install -r requirements.txt`" — the manual
  three-step from before `v0.9.2` made bare `cs update` do the whole
  upgrade on one "y". The command was telling operators to do by hand
  what it now does for them (and naming `pip`, which a uv-made venv does
  not have).
- **What:** `--check` now says: run `cs update` and answer y (re-pins,
  installs, re-stamps in one go); `--pin <tag>` is presented as the
  specific-version / rollback hatch. Every other `pip install` mention in
  this module's help and messages says `uv pip install`. The `--check`
  gate asserts the new guidance instead of the old string.
- **Re-collaudo:** **static tier, both clones** — output strings only, no
  behavior change.

## v0.9.2 — 2026-08-21

### Fixed — `cs update` is now genuinely one command, and stops asking unanswerable questions
- **The upgrade offer could not install.** Answering "y" to `Found new
  tag … Update? [y/N]` rewrote the pin and then died with `No module
  named pip`: it shelled out to `python -m pip`, but a venv created
  exactly per this kernel's own README (`uv venv .venv`) contains no pip
  module at all. The clone was left in the worst state — pin bumped,
  kernel NOT installed — sending the operator back to the manual steps
  the offer exists to remove. Now uses `uv pip install --python <this
  interpreter>` (the form `cs init`'s own install offer already used);
  `uv` is already a hard prerequisite. Verified end to end on a real uv
  venv: pinned `v0.9.0` + one `cs update` + one "y" → installed `0.9.1`,
  pin at `v0.9.1`, templates re-stamped.
- **`manifest.toml` is clone-owned and is never touched again.** It went
  through the normal diff/overwrite flow like any rendered template, so a
  "y" at the conflict prompt silently replaced a hand-authored manifest
  with a bare re-render from frozen `init_data` — deleting comments, and
  producing INVALID TOML: account keys rendered unquoted, and an
  email-shaped account name (the documented recommended shape) contains
  `@`, illegal in a bare TOML key. Now exempt exactly like
  `requirements.txt` (the charter always said so; the code never enforced
  it), plus a `toml_quote` filter applied to every account key and value
  so a future `cs init` render cannot repeat it either.
- **No more conflict prompts with an empty diff.** A file whose content
  already equals today's render, but whose STORED checksum is stale, hit
  the "modified locally AND template changed" ask; choosing `diff`
  printed nothing, leaving the operator with no way to decide. Now
  recognized and reconciled silently (`✓ <file> (already current)`).
- **Gates:** 26 (`test_toml_quote.py`), `test_template_render.py` gains an
  email-account fixture and parses `manifest.toml.j2`'s render with
  `tomllib`, `test_project_update.py` gains the `manifest.toml`
  never-touched proof, the already-current no-prompt proof, and asserts
  the install argv never shells out to `python -m pip`.
- **Re-collaudo:** **static tier, both clones** — bug fixes in `cs
  update`'s own flow; no send path, auth boundary or permission byte
  touched. The `manifest.toml` exemption makes an existing clone's next
  update strictly *less* invasive than before.

## v0.9.1 — 2026-08-21

### Added — `cs init` offers to install the project itself
- **Why:** README step 3 was a hand-typed `cd`/`uv venv`/`source`/`uv pip
  install` right after the wizard already knows `dest_dir` and has
  rendered `requirements.txt` — one more manual step for exactly the
  reader this quick-start is written for.
- **What:** `cs init` closes with `Install the project now (creates
  <dir>/.venv and installs the pinned kernel)? [y/N]`. EOF/^C/"n" skip
  with the manual fallback printed and **zero** subprocess calls (the
  v0.5.2 EOF contract: never installs without an explicit "y"); "y"
  runs `uv venv .venv` then `uv pip install --python <venv>/bin/python
  -r requirements.txt`, stopping before the install call if venv
  creation fails. Gate 25 (`tests/test_init_install_offer.py`) proves
  the call shape with `subprocess.run` stubbed — hermetic, no real
  venv or network in the suite.
- **README:** step 2 documents the prompt; step 3 (manual install)
  becomes the explicit fallback for a "no"; step 4 gains the
  `cd`+`source` the "yes" path still needs — the offer installs into
  the new venv but does not activate it for the caller's shell.
- **Re-collaudo:** **static tier, both clones** — `cs init` runs once,
  at clone creation; nothing here touches a send path, the auth
  boundary, or a permission byte. An existing clone's next `cs update`
  is unaffected (the offer lives in `cmd_init`, not `cmd_update`).

## v0.9.0 — 2026-08-21

### Added — the session is the product surface, and the surface says so
- **One review bootstrap:** `/munchausen` is merged into `/cs-review`,
  which now shows both what the operator prepared (drafts, tasks, flags,
  last tick) and — where a producer is wired — the day's outreach
  candidates with a dossier each. Reply-only clones get no dead steps.
- **`cs-` prefix on every stamped skill and command:** `/cs-account`
  (was `analyze-account`), `cs-triage-mail`, `cs-campaign-tick`,
  `cs-customer`, `cs-find-document`. Tab-complete on `cs` surfaces the
  whole product; the permission files never named the skills, so the
  permission surface is untouched.
- **Workflow commands:** `/cs-cron` (manage the unattended tick from a
  session: status, install/remove on explicit confirmation,
  pause/resume), `/cs-campaign` (design a campaign in-session — pack per
  the loader contract, engine wiring, one queued draft to judge, no
  dedicated cron by default), `/cs-help` (orientation map, zero calls).
- **`cs update` offers the pending release:** bare `cs update` first
  checks the pinned origin; a newer tag prompts
  `Found new tag (vX.Y.Z). Update? [y/N]` — default No, EOF/^C resolves
  to No with the decision printed; on yes it re-pins, installs into the
  clone venv and re-execs on the new kernel before refreshing templates.
  Offline: one skip line, the refresh proceeds. Three hermetic gates in
  `tests/test_project_update.py`.
- **`cs whoami` speaks human** (`signed in as … / uid / session valid
  until …`); `--json` returns the raw `account.who_am_i` response.
- **Wizard:** suggests the short slug ("ACME Corp" → `acme`); the clone
  pin default derives from `kernel_version_bare()` instead of a
  hand-maintained literal (which went stale twice in one day).
- **README:** quick-start via `uvx` (no bootstrap venv), steps 1–6, the
  three-piece mental model, capability-first framing.
- **Migration note:** nothing breaking. The old skill/command names are
  gone from the stamped surface; both live clones were already
  re-stamped in place (2026-08-19/21), so their re-pin is a no-op on
  files. New clones simply stamp the new names.
- **Re-collaudo:** **static tier, both clones** — nothing here touches a
  send path, the auth boundary, `gmail_archive`/`send_mail`, or a
  permission byte. The largest behavior change, the update offer,
  defaults to No, is EOF-safe by gate, and rewrites nothing without an
  explicit yes.

## v0.8.1 — 2026-08-19

### Fixed — `v0.8.0` installs as `0.7.1` (tag cut without the release commit)
- **Why:** `v0.8.0` was tagged and pushed directly from the feature commit,
  skipping the release commit, so `git show v0.8.0:pyproject.toml` still
  says `0.7.1`: a clone pinned at `v0.8.0` runs the right code but reports
  the wrong number from `cs --version` and `pip show` — the v0.6.1/v0.7.0
  incident again, and a published tag is immutable.
- **What:** `pyproject.toml` moves to `0.8.1`; `v0.8.0` is recorded in
  `TAG_VERSION_EXCEPTIONS` and its object pinned in `IMMUTABLE_TAG_TARGETS`
  (operator decision, 2026-08-19). No runtime change of any kind —
  `v0.8.1` is `v0.8.0` under its true name.
- **Migration note:** a clone pinned at `v0.8.0` works; re-pin with
  `cs update --pin v0.8.1` when convenient to make the reported version
  true again.
- **Re-collaudo:** **static tier, both clones** — metadata-only; `cs/` is
  untouched apart from the version string.

## v0.8.0 — 2026-08-19

### Added — `cs init` writes the secrets file itself
- **Why:** README Step 3 told a (often non-technical) operator to
  mkdir/cp/hand-edit a dotenv whose values the wizard already knew — the
  worst step of the onboarding walk.
- **What:** the wizard's last prompt is the mailbox app password
  (`getpass`, Enter to skip) and `cs init` writes `~/.<slug>-cs/.env` onto
  the rendered `.env.example`'s own anchor lines: `CS_ACCOUNTS` from the
  accounts registry, `FIREBASE_WEB_API_KEY` from the Step-0 descriptor,
  file mode 0600 in a 0700 state dir regardless of umask. An existing
  `.env` is operator-owned and never touched; EOF/^C on the prompt writes
  `EMAIL_PASSWORD` blank and prints the decision (the v0.5.2 EOF
  contract). Gate 24 (`tests/test_state_env.py`) proves all of it on the
  real template.
- **Also in this tag:** the README quick-start cut to size (uv
  de-emphasised, steps 5–7 terse, day-to-day model before Troubleshooting,
  a "The `cs` CLI" verb map under Reference); the README install snippets
  resolve the newest tag at run time and a literal `cs-kernel@vX.Y.Z`
  install pin in README is now a gate failure; `cs init`'s wizard default
  for a new clone's pin follows the operational pin.
- **Known defect:** the tag installs as `0.7.1` — no release commit
  preceded it; recorded and fixed forward by `v0.8.1` above.
- **Re-collaudo:** **static tier, both clones** — nothing here touches a
  send path, the auth boundary, a manifest field or a permission byte; the
  secrets writer fires only on a fresh `cs init`, and an existing clone's
  `.env` is by contract never touched.

## v0.7.1 — 2026-08-16

### Fixed — a published tag installed under the previous version number
- **Why:** `v0.6.1` and `v0.7.0` were both cut without bumping
  `pyproject.toml`, which still said `0.6.0`. A clone pinned at either tag
  installs a package that reports `0.6.0` — from `pip show`, from
  `cs update --version`, and from the brand-new `cs --version` that
  `v0.7.0` exists to provide. The collaudo's "Installed" column would have
  recorded the same wrong number. Nothing misbehaves at runtime; the
  package simply lies about which release it is, which is exactly the kind
  of quiet untruth this repo's release gate exists to prevent — and did
  not, because it only ever checked the pyproject version against the
  CHANGELOG and the active context, never against the tag being cut.
- **What:** `pyproject.toml` moves to `0.7.1`. The release gate
  (`tests/test_release_consistency.py`) gains `check_tag_versions`: for
  every semver tag, `git show <tag>:pyproject.toml` must declare that same
  version. The three tags that cannot comply — `v0.5.0` (historical) and
  `v0.6.1` / `v0.7.0` (this incident) — are listed in
  `TAG_VERSION_EXCEPTIONS` with the reason inline, because a published tag
  is immutable and a recorded mistake is worth more than a hidden one. A
  NEW mismatch fails the suite: it is a release bug to fix before tagging,
  never an entry to append.
- **Migration note:** none for behaviour. A clone pinned at `v0.6.1` or
  `v0.7.0` has the right code under the wrong version string; re-pinning to
  `v0.7.1` makes the reported version true again. Anyone reading an
  "Installed 0.6.0" from a clone that declares `v0.7.0` is looking at this
  bug, not at a failed upgrade.
- **Re-collaudo:** **static tier, both clones** — a version-string fix plus
  a test-only addition. No runtime code path changes; `cs/` is untouched
  apart from the metadata version.

## v0.7.0 — 2026-08-16

### Added — top-level `cs --version`
- **Why:** `cs --version` used to exit 2 with an argparse usage dump
  demanding a subcommand — the version was reachable only as `cs init
  --version` / `cs update --version`, neither discoverable from a bare
  invocation, and it is the first thing a newcomer or an operator
  verifying a re-pin actually types. It also made its way into a release
  runbook as a wrong command, twice (backlog item filed 2026-08-16).
- **What:** `cs/cli.py`'s root `argparse.ArgumentParser` now registers
  `--version`, sourced from a new single-purpose module `cs/_version.py`
  (`kernel_version()` / `kernel_version_bare()`, both reading
  `importlib.metadata` live off the installed `cs-kernel` distribution).
  `cs/project_init.py`'s `cs init --version` and `cs/project_update.py`'s
  `cs update --version` are refactored onto the same helper, retiring the
  two near-identical local `try/except PackageNotFoundError` blocks that
  used to exist independently — one shared source instead of three copies
  of the same import, and `cs update --check` (below) reuses the "bare"
  half of the same helper for its installed-vs-latest comparison. Works on
  a bare install with no manifest anywhere, exactly like `--help` already
  did (proven by `tests/test_version.py`, which runs it from an empty
  directory).
- **Migration note:** none — additive CLI surface, no state, no config.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Added — `cs login` auto-selects the descriptor it already knows; no more picking from a menu of wrong answers
- **Why:** with `--account`, or on any stamped clone, the target engine uid
  is already fully determined before `cs login` ever runs — yet it still
  printed the full numbered list of every descriptor found on the machine
  and let the operator choose, including the wrong ones, which were only
  refused AFTERWARDS by the identity cross-check, with a message
  ("fix manifest.toml [engine].owner_uid deliberately") that reads like a
  manifest misconfiguration for what was simply a menu the operator should
  never have been shown. On a machine with several signed-in profiles —
  the normal case for a founder-sweep secondary account — that menu is a
  trap, not a convenience (backlog item filed 2026-08-16, Mario signing in
  a secondary account and picking the primary's descriptor by habit).
- **What:** `cs/login.py::cmd_login` now branches on whether
  `settings.engine_owner_uid` is already configured. When it is, the
  descriptor whose uid matches is auto-selected and printed
  (`selected: <email> (<uid>)`) with NO prompt at all; when none of the
  descriptors found match that uid, `cs login` fails immediately —
  `no descriptor for uid <uid> [(account '<name>')] — sign in to the
  mrcall-desktop app as that account` — instead of offering a list in
  which every option is wrong. The numbered picker (and the single-profile
  `Proceed? [Y/n]` confirm) survives untouched for the one case that is
  genuinely ambiguous: no engine identity configured yet, e.g. a brand-new
  clone before `cs init` has stamped one. `_identity_conflict` — the
  post-pick cross-check that actually decides whether a session gets
  stored — is completely unchanged; this only changes WHICH descriptor is
  ever offered, never what is accepted.
- **Migration note:** none — behavior-only fix to an interactive verb, no
  state, no config. An operator who was used to seeing (and ignoring) the
  full menu will now see either a one-line auto-select confirmation or an
  immediate, clearer refusal.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Added — `cs update --check` / `cs update --pin <tag>`: the discovery half of the upgrade path
- **Why:** nothing told an operator that a newer kernel tag had shipped —
  the only way to find out was reading the CHANGELOG in another repo, and
  re-pinning was a hand-edit of `requirements.txt` (in practice a `sed`).
  A clone could sit on an old kernel indefinitely with no signal (backlog
  item filed 2026-08-16, mid a `v0.6.0` re-pin).
- **What:** two new opt-in flags on `cs/project_update.py`'s argparse
  layer; bare `cs update` is completely unchanged. `--check` parses the
  kernel origin straight off `requirements.txt`'s own pin line (`cs-kernel
  @ git+<url>@<tag>` — the URL is READ, never hardcoded), runs `git
  ls-remote --tags <url>` against it, and prints installed (the actually
  `pip`-installed version, via `cs._version.kernel_version_bare()`),
  pinned, and latest. When a newer tag exists it also prints that tag's
  own re-collaudo tier when it can determine it — read straight off the
  newer tag's OWN `CHANGELOG.md` via `git show <tag>:CHANGELOG.md`,
  attempted ONLY when the origin is something git can read off the local
  filesystem (a `file://` remote or a local path some kernel-developer
  clone may legitimately pin to); a real customer clone pinned to a remote
  GitHub URL has no local copy of the kernel's tree to read the tag's
  CHANGELOG from, which is the common case, and the command degrades to
  printing just the tag name rather than guessing or fetching raw content
  over an assumed host shape. `--check` WRITES NOTHING, ever — including
  when the origin is unreachable, which prints one handled line naming it
  and exits 1, never a traceback. `--pin <tag>` rewrites ONLY the kernel
  pin line in `requirements.txt` (every other byte, including comments,
  is untouched), prints the exact before/after line, and says installing
  it is a separate, deliberate step (`pip install -r requirements.txt`).
  Neither flag auto-bumps the pin: `requirements.txt` is the operator's
  own pin (the `v0.5.2` decision — "`cs update` never touches it"), and
  every kernel upgrade owes a re-collaudo (CLAUDE.md, Versioning &
  release) — `--check`'s own output says so, and so does the code comment
  above `--pin`'s implementation. A `--check` that rewrote the pin itself
  would not be a pin anymore.
- **Migration note:** none — additive CLI surface; `requirements.txt`'s
  format is unchanged and `--check`/`--pin` are both opt-in.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Re-collaudo (this release)
- **STATIC tier, both clones.** This is the first release to apply the
  amended charter rule (CLAUDE.md, Versioning & release, changed
  2026-08-16 while scoping this very candidate): the version digit
  describes the INTERFACE, and the re-collaudo tier is a separate
  judgement decided by what the release TOUCHES. This candidate is
  therefore a MINOR — new CLI surface (a root flag, two `cs update`
  flags, a changed `cs login` interaction shape), and a verb that stops
  prompting is not something an operator reading "patch" should discover
  on their own — while carrying NO
  new manifest field and touches none of the charter's escalation
  triggers: no send path (`cs/send_mail.py`, `cs/campaign.py`'s pack
  senders), no `cs/gmail_archive.py`, no `cs/send_guard.py`, no engine RPC
  shape, and — proven by gate 17's own byte-for-byte token check, which
  stays green unmodified — no permission bytes in either
  `.claude/settings.json.j2` or `bin/cs_operator_cron.sh.j2`. The only
  collaudo-visible surface any of the three changes touch is the `--help`
  tree and two interactive verbs' console output, and the STATIC tier
  (gate 4's full `--help` walk plus the three new/expanded test files —
  `tests/test_version.py`, the `--check`/`--pin` guards folded into
  `tests/test_project_update.py`, the known-uid auto-select guards folded
  into `tests/test_login.py`) already exercises every one of those real
  code paths end to end, several of them as REAL subprocesses against a
  real local git repo standing in for the kernel's remote origin. The
  reasoning is on record here, and the tier is stated per entry as the
  amended rule now requires, precisely so the next MINOR that DOES touch a
  send path, the auth boundary or a manifest field cannot point at this
  entry as precedent for skipping FULL.

## v0.6.1 — 2026-08-16

### Fixed — the public README still walked a new reader onto the retired `v0.5.2` install pin and skipped `cs login` entirely
- **Why:** an adversarial UX review of the README as a fresh, competent
  reader with no prior context on this project found it breaking at
  installation and at first use. The install pin, the Versioning section's
  pin and the "Current release" line all still named `v0.5.2` — the tag
  from *before* the `v0.6.0` auth rewrite — so a reader who followed the
  README to the letter installed the vendor-only-service-account mint path
  and dead-ended on a `FileNotFoundError: firebase-sa.json` traceback for a
  file only the vendor can issue. `cs login`, the verb `v0.6.0` actually
  introduced to turn a desktop sign-in into a usable session, was entirely
  absent from the document (`grep login README.md` matched nothing), so the
  reader had no path from "toolkit installed" to "`cs whoami` succeeds."
  Prerequisites told the reader to look up "the engine WebSocket URL and the
  profile's Firebase uid" by hand — both now unobtainable that way, since
  `v0.6.0` derives them from the desktop app's own sign-in descriptor. The
  document also never used the word "daemon" and never said `cs` has to run
  on the same machine as the mrcall-desktop app, never stated the Gmail /
  Google Workspace requirement `cs/gmail_archive.py`'s IMAP special-use
  folder selection actually has, told the reader "defaults are fine when
  unsure" when several `cs init` prompts are hard-required (an empty answer
  loops on "Please provide a value."), and its own worked example silently
  diverged from the wizard's real behaviour: the table said the slug for
  "ACME Corp" is `acme`, but `project_init.get_company_slug()` derives
  `acme-corp`, so a reader who accepted that default would get a state
  directory every later command in the same README — including the
  `CS_PAUSE` kill-switch — then misses.
- **What:** the README gained a new Step 0 ("Install mrcall-desktop and
  sign in") ahead of the toolkit install, stating plainly what the app and
  its local daemon do, that `cs` must run on the same machine, the
  macOS/Windows-vs-Linux-from-source split, that sign-in writes the profile
  descriptor `cs login` reads, and that a release newer than the public
  `v0.1.29` (2026-05-05) is required. The now-false "you'll need the engine
  WebSocket URL and the profile's Firebase uid" line is removed from
  Prerequisites. `cs login` is now its own numbered step between installing
  the project pin and `cs whoami`, explaining the `email (uid)` confirm
  prompt, the stored session, the `FIREBASE_WEB_API_KEY=` note to paste into
  `.env` on a key mismatch, and what `cs whoami` proves. A new
  Troubleshooting section right after the setup steps quotes the tool's real
  message text — verified against `cs/auth.py` and `cs/login.py` rather than
  paraphrased — for "not signed in", connection-refused / engine-unreachable
  (naming the asymmetry: `cs login` catches this as one line, other verbs
  still surface a raw traceback), "no profile descriptor found", and nothing
  landing in Drafts (`CS_PAUSE` and `cs_operator.log`). Prerequisites gained
  the Gmail / Google Workspace requirement with its one-line reason. The
  setup-prompts prose now names which answers must be ready before starting
  instead of claiming defaults are always safe, and the worked example tells
  the reader to type `acme` explicitly, spelling out why the wizard's own
  default (`acme-corp`) would silently break the rest of the walkthrough.
  The cron section now leads with the `cs cron install`/`status`/`uninstall`
  verb, keeping the manual `crontab -e` route as the documented fallback
  rather than the only path. All three stale `v0.5.2` install lines move to
  `v0.6.0`, the released tag. This changelog's own top-of-file pin paragraph
  is rewritten to `v0.6.0` (FULL collaudo signed on both clones 2026-08-16)
  with a sentence warning that `v0.5.2` and earlier require the vendor-only
  service-account file, so a new customer must not be installed onto them;
  and the `v0.6.0` heading below drops the stale "candidate" wording now
  that the tag is cut and pushed.
- **Migration note:** documentation-only; no operator action.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Fixed — `cs init` stamped a clone that could not run, and left its own cron entry silently dead
- **Why:** three defects surfaced together while walking `cs init`'s output
  end to end: the rendered `bin/*.sh` scripts came out of the Jinja render
  at mode `0644`, so a freshly stamped clone's cron wrapper was not
  executable — the exact crontab line this README documents
  (`… bin/cs_operator_cron.sh …`) then failed silently under cron, with
  nothing in `cs_operator.log` to explain why, which is the single defect
  most likely to make a new operator conclude the product does nothing. The
  wizard's own kernel-version default for the generated
  `requirements.txt.j2` pin still read `0.5.2` — the pre-auth-rewrite tag —
  so a clone stamped with the wizard's own suggested answer would re-hit the
  same vendor-only service-account wall the README fix above describes.
  Separately, the stamped clone templates themselves still carried
  operator-visible defects: a hardcoded `wss://desktop.example.com`
  placeholder where the real engine URL belongs, a "this is the mother
  clone" sentence told to every company regardless of which clone it was,
  CRM/producer/excluded-campaign bullets that printed even when the
  operator had chosen the `none` adapter, prose left in Italian in at least
  one template, and stale references to a `cs-template`/`copier` mechanism
  that does not exist in this project.
- **What:** rendered `bin/` scripts are now created with the executable bit
  set, in both `cs init`'s render path and `cs update`'s re-render path, via
  a shared `is_executable_target` helper so the two can never drift apart
  on which files qualify. The
  wizard's kernel-version default moves off `0.5.2` (now tracking the
  release being cut). The stamped templates are corrected: the engine-URL
  placeholder renders from the real configured value, the mother-clone
  sentence is removed from the generic template, CRM/producer/excluded-campaign
  bullets are guarded so a `none` adapter omits them entirely instead of
  printing an empty or misleading line, the Italian strings are translated
  to English, and the `cs-template`/`copier` references are corrected to
  describe this project's actual `cs init`/`cs update` mechanism.
- **Migration note:** affects what `cs init` stamps and the file mode of the
  rendered scripts going forward. An already-stamped clone is unaffected
  until it runs `cs update`, which re-renders the touched templates and
  restores the intended file mode on `bin/`; no state, no send path, no
  auth boundary changes underneath it.
- **Re-collaudo:** none by itself — see the shared reasoning below.

### Re-collaudo (this release)
- **PATCH — static, picked up at the next `cs init` / `cs update`.** Every
  item above changes what `cs init` STAMPS into a new clone, the file mode
  of rendered scripts, or documentation; none of it touches a code path a
  clone already running `v0.6.0` depends on — the auth boundary, the send
  chokepoint, the campaign lifecycles and the engine RPC shapes are
  untouched. A full collaudo is not required to adopt this tag; re-running
  `cs init` on a fresh clone (or `cs update` plus a `chmod +x bin/*.sh`
  sanity check) is enough to confirm the fix landed.

## v0.6.0 — 2026-08-15

### Changed — auth exchanges a refresh token via the Secure Token API; the service-account credential exits the mint path
- **Why:** the v0.5.2 blind onboarding probe (both clones, 2026-08-09) proved
  the wall a new customer actually hits at the terminal step is the
  vendor-only service-account credential the old mint path required
  (`firebase-sa.json`, obtainable only from inside the vendor's own console)
  plus the raw tracebacks every layer beneath it threw once that credential
  existed but the exchange still failed — see the two "Known" entries
  directly below, both opened the same day.
- **What:** `cs/auth.py` is rewritten end to end. It no longer mints a
  Firebase custom token locally with a service-account private key and
  exchanges it via identitytoolkit `signInWithCustomToken`; instead it reads
  the refresh token written by the desktop app's own sign-in descriptor —
  the surface `cs login` (below) consumes — and exchanges it for a
  short-lived ID token through Google's Secure Token API, mirroring the
  engine's own headless refresh
  (`mrcall-desktop/engine/zylch/auth/refresh.py::exchange_refresh_token`)
  request shape. The service-account file exits the auth path entirely:
  `firebase_sa_path` remains in `Settings` only for the optional
  Drive/lead-resolve surfaces (`cs/drive.py`, `cs/resolve.py`,
  `scripts/find_profile_uid.py`), which still need the Admin SDK and are
  untouched here. Every auth-boundary failure — not signed in, a stored
  session for the wrong uid, an HTTP or network failure from the exchange, a
  malformed response, an identity mismatch on the exchanged token — is now a
  single handled `ConfigError` line; none of the failure branches propagate
  a raw traceback. New derived setting `refresh_token_path` (empty →
  `<state_dir>/refresh_token-<uid>.json` — see the per-account entry below)
  backs a new uid-tagged, mode-`0600` JSON file managed by
  `_read_refresh`/`_write_refresh`. `cs/sms.py` and `cs/rpc.py` are
  unchanged — both call `auth.get_id_token` and only ever use its return
  value, so nothing downstream of the token needed to know the mint
  mechanism changed underneath it. `cs login` (`cs/login.py`) is the new
  human-run verb that actually produces that stored session: it finds the
  profile descriptor (scanned under `~/.zylch/profiles/<uid>/cs-descriptor.json`,
  or given directly via `--descriptor`), confirms — or, with more than one
  profile present, numbered-picks — with the operator, refuses strictly (no
  `--force`) on any mismatch between the descriptor's identity and this
  clone's own configured `engine_owner_uid` — plus `email_address`, but that
  half applies to the clone's PRIMARY identity only (see the per-account
  entry below) — stores the refresh token through the `_write_refresh`
  above, and proves the session
  with one live `account.who_am_i` call; it carries no cron/allow-list entry
  of its own. `cs --help` (bare, no subcommand) now lists `init`, `update`
  and `login` as real subparsers — normally bypassed by the early dispatch
  that actually runs them, registered only so the help tree tells the
  truth — closing the onboarding-probe finding below that `cs --help` did
  not list `init`/`update` at all. This batch closes the remaining
  onboarding-probe gaps: `cs init` now autodetects a mrcall-desktop profile
  already signed in on this machine — new `project_init.descriptor_defaults()`
  scans the same `~/.zylch/profiles/*/cs-descriptor.json` tree via
  `login.descriptor_root`/`scan_descriptors`/`parse_descriptor` and, when
  EXACTLY ONE valid descriptor is found, prefills the wizard's `Operator
  email`, `Engine WS URL`, `Engine owner UID` and default-account-UID
  prompts from it (printing which profile it used); the operator still sees
  and can override every value, and zero or more than one descriptor leaves
  the wizard neutral — picking among several signed-in profiles stays `cs
  login`'s job. The wizard's `Git remote URL` prompt now defaults to empty
  ("local-only, add one later with `git remote add`") instead of being
  required with no default — the finding below — since its sole consumer,
  `manifest.toml.j2`'s template-only `[repo].git_remote` field, was already
  safe with an empty value (valid TOML, never parsed back into `Settings`).
  `cs update` gains the same minimal argparse treatment as `cs init` — a
  real `prog='cs update'` parser, `--version` off the installed package
  metadata, identical `SystemExit` code propagation — so `cs update --help`
  now prints usage and exits 0 instead of falling through into a live
  template-merge walk against the current directory. The stamped-clone docs
  catch up: `CLAUDE.md.j2`'s "Auth chain (headless)" paragraph now describes
  the desktop app writing the profile descriptor, `cs login` storing the
  refresh token (state dir, mode `0600`), every verb exchanging it via the
  Secure Token API for a cached short-lived ID token, and the engine
  verifying RS256 and gating `token.sub == OWNER_ID` — unchanged; and
  `.env.example.j2`'s `FIREBASE_WEB_API_KEY`/`FIREBASE_SA_PATH` comments no
  longer describe the service account as the auth credential, naming it
  optional and scoped to the Drive/lead-resolution surfaces instead.
- **Migration note:** a clone re-pinned to this version has no stored
  session for `cs login` to overwrite. A stale `~/.<slug>-cs/id_token.json`
  from the v0.5.2 mint path is now simply ignored — the per-uid derivation
  the entry directly below this one adds reads `id_token-<uid>.json`, a
  filename the old path never wrote, so the false-green scenario this
  paragraph used to warn about (a cached token from the old path silently
  keeping every verb "working" for up to ~1h) is now structurally
  impossible. Deleting the stale file (`rm ~/.<slug>-cs/id_token.json`) is
  hygiene, not a correctness step. Every engine verb prints the handled
  "not signed in — run `cs login`" line until the operator runs `cs login`
  once.
- **Re-collaudo:** **full, both clones** — this changes the auth boundary
  every RPC call, SMS send and engine WebSocket connect goes through
  (`cs/rpc.py`, `cs/sms.py` call the same `get_id_token` signature, but what
  runs underneath it is entirely new). Prove a real refresh-token exchange
  against the live engine Firebase project on both clones before this ships.
  The per-uid filename (see the entry directly below) makes the old
  false-green risk — a cached `id_token.json` from the v0.5.2 mint path
  silently passing the suite — structurally impossible, since the new code
  never reads that filename once an engine identity is configured; deleting
  the stale file first is optional hygiene, not a precondition for a
  trustworthy result.

### Changed — session files are per account uid (`--account` keeps working)
- **Why:** the founder-inbox sweep — a daily, read-only check of a second
  configured mailbox alongside the operator's own (the F3 decision) — needs
  `cs --account <secondary> …` to keep working across repeated logins. The
  refresh-token rewrite in the entry directly above stored exactly ONE
  session per clone (`<state_dir>/refresh_token.json`,
  `<state_dir>/id_token.json`), so a second `cs --account <secondary> login`
  silently overwrote the first: signing in to the founder mailbox clobbered
  the primary operator mailbox's own session file, regressing
  `cs --account <secondary>` the moment two accounts were both signed in.
  Fixing that surfaced a second, discovered-by-recon bug:
  `login._identity_conflict` also compared the clone's configured
  `email_address` (the primary operator mailbox) against the descriptor's
  own email, and for a secondary account's descriptor — the founder's own
  mailbox, never the operator's — that comparison ALWAYS mismatches, so
  `cs --account <name> login` was refused outright before the per-clone
  session file could even become the practical problem.
- **What:** `token_cache_path` and `refresh_token_path` (`cs/config.py`)
  now derive as `<state_dir>/id_token-<uid>.json` and
  `<state_dir>/refresh_token-<uid>.json`, where `<uid>` is the resolved
  `engine_owner_uid` — the same uid `cs --account <name>` swaps into
  `CS_ENGINE_OWNER_UID` before `config.load()` runs, so the derivation
  follows whichever account is selected for that invocation. An empty uid
  (no engine identity configured at all) keeps the legacy un-suffixed
  names, since `cs/auth.py` raises its own "uid not set" `ConfigError`
  before either file is ever read or written. An explicit
  `token_cache_path`/`refresh_token_path` set in the environment is
  untouched, exactly as before — derivation only ever fills in an EMPTY
  field. `cs/auth.py`'s id-token cache read/write now also strips the
  configured uid before tagging or comparing it, so a whitespace-bearing
  configured uid no longer thrashes the cache between the default and
  `--account` paths. `cs login`'s identity cross-check
  (`login._identity_conflict`) now takes an `account_switched` flag,
  threaded from `cli.main()`'s `--account` handling through the new
  `cmd_login_stub` signature: the uid checks (empty configured uid, uid
  mismatch against the descriptor) stay unconditionally active — uid
  equality with the `CS_ACCOUNTS` registry entry IS the identity statement
  for a secondary account — but the operator-mailbox email comparison now
  binds the clone's PRIMARY profile only, and is skipped exactly when
  `--account` actually switched the uid away from the clone's default. The
  email-mismatch refusal message also gains a pointer for the legitimate
  secondary case: "…or pick the matching descriptor; for a registered
  secondary account run `cs --account <name> login` instead." The
  operator-mailbox cross-check was always an independent second opinion,
  never the sole guard: for a switched `--account` login the invariant now
  rests on the unconditional uid check against the operator-written
  `CS_ACCOUNTS` registry, plus the interactive confirm every `cs login` run
  requires (`cs login` prints `email (uid)` and stores nothing without an
  explicit yes). This diff also fixes an operator-visible CLI parsing
  defect it would otherwise have shipped un-exercised:
  `cs --account <name> login --descriptor PATH` now actually parses —
  before, it exited 2 with argparse's own "unrecognized arguments:
  --descriptor" (the login stub's argv passthrough used a REMAINDER
  positional, which cannot coexist with an unrecognized flag anywhere in
  its subparser); the stub (`cs/cli.py::cmd_login_stub`) now mirrors
  `cs login`'s real `--descriptor` option instead, and `cs/cli.py` records
  the resulting maintenance rule that any new `cs login` option must be
  added to both parsers.
- **Migration note:** any clone that configures a founder-sweep (or other
  secondary) account has no stored session for it yet. Once per clone: sign
  in to the mrcall-desktop app AS the secondary mailbox — that sign-in
  writes the secondary profile's own descriptor under
  `~/.zylch/profiles/<uid>/cs-descriptor.json` — then run
  `cs --account <name> login` once. That stores the secondary account's
  session under its own per-uid path and never touches the primary
  account's session, which needs no migration step of its own beyond the
  one already described in the entry directly above.
- **Re-collaudo:** covered by the same full-both-clones requirement as the
  refresh-token-exchange entry directly above — this changes the same auth
  boundary — plus one additional live proof per clone that configures a
  secondary account: `cs --account <name> login` followed by
  `cs --account <name> whoami` must succeed without disturbing the default
  account's own `cs whoami`.

### Known — the auth boundary still tracebacks below the env-key layer
- **Resolved for the auth path by the candidate above:** the service-account
  load this note describes no longer exists in `cs/auth.py` — the file load
  (and therefore its `FileNotFoundError` / `ValueError: Invalid service
  account certificate…` failure modes) is gone from the mint path, and the
  403-on-exchange case is now a handled `ConfigError` line naming the
  API-key-restriction possibility instead of a bare
  `urllib.error.HTTPError` traceback. The historical observation immediately
  below is kept for the record; `firebase_sa_path` and its own failure modes
  still apply wherever `cs/resolve.py` / `cs/drive.py` /
  `scripts/find_profile_uid.py` load it directly for the Admin SDK.
- v0.5.2's `ConfigError` covers the two missing env keys; every layer beneath
  still crashes raw. Observed live 2026-08-09 (both clones + the blind
  onboarding probe): a refused custom-token exchange prints
  `urllib.error.HTTPError: HTTP Error 403: Forbidden` (root cause found the
  same evening: an HTTP-referrer restriction on the shared engine-project web
  API key blocks all no-referer server-side calls — a console/config matter,
  not kernel code; the kernel's job is only to print it as one line); a missing
  `firebase-sa.json` prints `FileNotFoundError`; an invalid one prints
  `ValueError: Invalid service account certificate…`. Wrap the exchange call
  and the service-account load in the same handled one-line error path,
  naming the artifact and what it is. Target: v0.5.3.

### Known — two onboarding-probe findings on `cs init` (2026-08-09 blind run)
- `cs --help` does not list `init`/`update` (they dispatch before argparse):
  a customer sanity-checking the tool concludes `init` does not exist.
- The wizard's "Git remote URL" prompt is required, has no default and is
  absent from the README's prompts table; needs a local-only default or
  documentation. Target: v0.5.3.

## v0.5.2 — 2026-08-09

### Added — the `cs` console script, finished across the permission surface
- **Why:** `pyproject.toml` now declares `[project.scripts] cs = "cs.cli:main"`,
  so `cs` reaches the exact same code as `.venv/bin/python -m cs`. Claude
  Code's permission rules match the literal command TEXT typed on the Bash
  tool, not the program that ends up running, so a deny rule written for
  only the old spelling leaves the new one — and the plain `python -m cs` /
  `python3 -m cs` aliases — wide open. That is a live send-guard hole, not a
  cosmetic gap.
- **What:** every permission template now enumerates every spelling that
  reaches the entry point. The cron wrapper's `--disallowed-tools` re-deny
  set carries six spellings (`.venv/bin/python -m cs`,
  `.venv/bin/python3 -m cs`, `.venv/bin/cs`, `python -m cs`, `python3 -m cs`,
  `cs`) across the four surfaces it must block (`chat`, `rpc chat`,
  `campaign send-draft`, `rpc settings.update`) — 24 deny entries plus the 4
  non-cs keeps (`Write`, `Edit`, `rm`, `git push`). `.claude/settings.json`'s
  `permissions.deny` carries the same six spellings for `campaign
  send-draft`; its `permissions.allow` carries the four canonical spellings
  (module path and console script, `venv`-prefixed and bare — deliberately
  no `python3` alias there) across the 15 read/draft-only verbs.
  `CLAUDE.md`'s "module path is frozen" invariant is rewritten: the console
  script is a second door onto the same `cs.cli:main`, and clone permission
  strings must enumerate every spelling, not assume one. `tests/run.sh` step
  17 gates the enumeration by PLACEMENT — deny vs. allow, not just
  file-wide presence — and by exact, order-preserving token equality on the
  cron's list, so a spelling that greps true from the wrong list, a
  commented-out line, or a deleted flag all still fail loudly.

### Fixed — customer onboarding walls
- **Why:** walking the README's own setup path on a machine with no prior
  clone hit a wall at nearly every step: the install URL named the
  operator's private org; the doc told a new user to type `python -m cs
  init` when the console script makes `cs init` the natural spelling; `cs
  whoami` with no engine configured raised a bare `RuntimeError` traceback
  instead of saying what to fix; `cs init` given a closed stdin (piped,
  headless, or a stray Ctrl-C) died the same way; the wizard's kernel-version
  default and the shipped `requirements.txt` template both pointed at a
  stale pin over an SSH URL a customer has no key for; and the wizard's
  example company and two templates still carried the operator's own brand
  or private repo.
- **What:** the README's install line and its "Versioning" pin both point
  at the public `malemi/cs-kernel` repository, and every `python -m cs …`
  example in prose is now the bare `cs …`. `cs whoami` and every other verb
  whose auth resolution hits a missing `CS_ENGINE_OWNER_UID` /
  `FIREBASE_WEB_API_KEY` now raises the new `cs.config.ConfigError`, caught
  at dispatch in `cs/cli.py` and printed as one stderr line with exit 1 — no
  traceback. `cs init` catches `EOFError` (exhausted stdin) and
  `KeyboardInterrupt` around the prompt loop, exiting 1 / 130 with a
  one-line message; its own argparse `SystemExit` is now propagated by its
  real code instead of being flattened to 1, so `--help`/`--version`
  correctly exit 0. `--version` reads the installed package's own metadata
  instead of a string hardcoded at `0.2.0`. The generated `requirements.txt`
  installs over anonymous HTTPS from the public repo instead of SSH, the
  wizard's kernel-version default tracks the release being cut, the
  wizard's example company is now the neutral `Acme Corp`, and the two
  templates that named the operator's product or private repo now render
  from `company_name` or say "your private repository" instead.

### Changed — the charter's literal gate becomes a reviewed registry
- **Why:** the anti-fork grep in `tests/run.sh` step 1 was all-or-nothing:
  any wordlist hit failed the gate outright, with no way to record that a
  hit is there on purpose — the kernel's own public install URL has to name
  `malemi` somewhere, and the old gate had no way to say so without
  weakening the pattern itself.
- **What:** step 1 runs the same wordlist scan (now also catching
  `hahnbanach`, the operator's GitHub org, found in a stale
  `requirements.txt.j2` URL and a private-repo mention in the projects
  README — both fixed) but a hit is no longer an automatic failure. Every
  hit is checked against the new `tests/reviewed_literals.txt`, a versioned
  registry of `path :: exact line :: reason` entries the operator has
  explicitly approved; an unmatched hit prints as `NEEDS REVIEW` and still
  fails the gate, as a proposal rather than a silent pass. The registry
  currently holds one entry: `malemi` in `requirements.txt.j2`'s install
  URL, approved because it names the kernel's own public home, identical
  for every clone.

### Changed — `cs update` no longer touches the operator's pin or silently overwrites security-critical templates
- **Why:** `cs update` used to treat `requirements.txt` as an ordinary
  render target, but it is the operator's own installed pin, not
  kernel-owned state ("upgrades are a pin bump + pip install, never a
  cherry-pick" — CLAUDE.md's Versioning & release section). And two of the
  rendered files carry the draft-only send-guard invariant itself
  (`.claude/settings.json`, `bin/cs_operator_cron.sh`); gating their update
  behind the same interactive "overwrite?" prompt as any other template
  means a headless run, or an operator answering "no" out of habit, can
  leave a clone running a stale deny list.
- **What:** `cs update` now reports that `requirements.txt` exists and
  leaves it alone unconditionally — never rewriting or re-pinning it. The
  two security-critical templates apply the new render unconditionally on
  conflict, back up the operator's previous local version next to it, and
  print what changed so the operator can re-apply any local edit by hand,
  replacing the ordinary conflict prompt for exactly these two files.

### Fixed — `cs update` no longer crashes at a conflict prompt without a tty
- **Why:** the template-conflict prompt (`Overwrite? [y/N/diff]`) read its
  answer with a bare `input()`. A headless run (agent, cron,
  `stdin </dev/null`) has no tty: `input()` raised EOFError and the whole
  `cs update` died with a traceback mid-run — hit live 2026-08-04 during the
  v0.5.1 re-pins (worked around by piping `N`). Depending on file order the
  crash could leave a clone half-updated.
- **What:** both conflict prompts resolve EOF to the default the prompt
  itself declares — `n`, keep the local file — and print the decision
  (`(no tty — keeping local file)`). Gate 16 (`tests/test_project_update.py`)
  characterizes the helper AND proves the real `python -m cs update`
  subprocess with closed stdin against a manufactured conflict: exit 0,
  local file byte-identical, decision named in the output.
- **Re-collaudo:** **static, every clone** — only the clone-maintenance
  verb's prompt handling changes; no operator surface, no send path. Picked
  up at the next re-pin.

### Re-collaudo (this release)
- **Full, both clones.** Any one of the four items above touching the
  permission surface — the deny/allow spelling enumeration, the charter's
  reviewed-literal registry, or the security-critical apply-on-conflict
  path — is enough to require it on its own; together they put `v0.5.2`
  squarely behind the charter's full-tier bar for a behavior change. It
  does not go operational on either clone until the full collaudo suite is
  green on both — the same bar the two known clones cleared for `v0.5.1`.

## v0.5.1 — 2026-08-03 (corrective release)

### Fixed — cs task closes carry the external operator audit identity
- **Why:** the engine RPC accepts additive `actor`/`why` fields, but
  `cs tasks close` still sent only `task_id`/`note`; every operator close was
  therefore stored as the engine's backward-compatible default actor `human`.
- **What:** the kernel consumer now sends `actor="operator"` and a non-empty
  `why` on every close. A supplied `--note` remains the display note and is also
  the audit reason; a no-note close uses a stable kernel-owned reason. The
  consumer gate asserts the exact payload in both shapes.
- **Compatibility:** requires engine commit `677e319` plus the follow-up close
  history repair `1367e71` — both deployed to the five live daemons 2026-08-03.
  The older strict engine rejects `actor`/`why` as unknown parameters; rollout
  is engine first, kernel second, operators last.
- **Re-collaudo:** **full, every clone** — exercise a task close through the real
  engine and verify `close_actor="operator"` plus the persisted close reason.

### Fixed — release metadata agrees before the next tag
- **Why:** tag `v0.5.0` was cut while `pyproject.toml` still declared `0.4.5`,
  the active context still called `v0.4.0` the tip, and this changelog's
  `v0.5.0` entry was a placeholder. An install from that tag would therefore
  report the old package version. The two known clones remain independently
  verified at declared/locked/local-installed `v0.4.5`; their live daemon
  revisions are still unknown.
- **What:** package metadata advances to `0.5.1`, and a release-consistency gate
  (`tests/test_release_consistency.py`) asserts four things instead of describing
  them: the pyproject version owns a changelog section with a real body and a
  re-collaudo tier; the company-literal grep `tests/run.sh` **executes** carries
  every charter token plus the case-sensitive `\bHB\b` leg (a token left in a
  comment no longer counts); `docs/active-context.md` separately names the latest
  semver release and current HEAD's tagged/untagged state; and every
  `cs-kernel@vX.Y.Z` line in `README.md` is either the package version or the
  operational pin recorded at the top of this file. It reads repo files plus
  local git refs — no network. The published `v0.5.0` target is pinned by commit
  id so a force-move fails even if prose moves with it.
- **Re-collaudo:** same as `v0.5.0` below. Metadata and docs alone are static,
  but the cumulative upgrade crosses the model-output send chokepoint and
  therefore requires **full collaudo** on every clone before adoption.

## v0.5.0 - 2026-08-01

### Fixed — model output is guarded at the send chokepoint
- **Why:** a campaign path could pass model deliberation/meta text to SMTP.
  Guarding one caller was insufficient because another model-composed path
  could reach the same wire.
- **What:** deterministic register/tell checks now run in `send_mail.send` for
  model-composed bodies before any SMTP connection opens. The optional LLM
  register judgment degrades loudly to deterministic checks if unavailable;
  deterministic refusals never degrade. Fixed human-authored templates retain
  their existing path.
- **Draft behavior:** model-composed Gmail drafts are not blocked, because the
  draft is the review surface. They carry explicit guard warnings through the
  verb's JSON response; human/template drafts do not invoke the judgment leg.
- **Also fixed:** `classify_detailed` forwards the requested temperature.
- **Re-collaudo:** **full, every clone** — this changes the final send boundary
  and draft response surface. Prove refusal opens no SMTP socket, legitimate
  replies still reach the fake transport, warnings reach draft output, and the
  clone's pause/rate/dedup/stamp invariants remain green. No automated real send.

## v0.4.5 — 2026-07-31

### Fixed — memory-write docs authorized a tool the engine never calls
- **Why:** the engine's write call for memory is `update_memory`, but three
  templates (clone `CLAUDE.md` §9, the `customer` skill, `docs/projects/README.md`)
  prescribed `cs chat --allow create_memory` alone. `--allow` matches by exact
  name, so the gate denied the write with a polite conversational refusal — no
  error, no non-zero exit — and the fact was silently lost. Hit live 2026-07-31
  on the reference clone; verified both ways (single name → `update_memory ->
  deny`, nothing written; both names → write lands and `cs ask` reads it back).
- **What:** every prescription becomes `--allow create_memory,update_memory`,
  and the `customer` skill states the failure mode explicitly: a wrong tool name
  does not raise, so never trust the absence of an error — always verify with
  `cs ask`. Placeholders on the touched lines moved to English.
- **Re-collaudo:** static, every clone — three templates, picked up by
  `cs update`. The reference clone (mrcall-cs) is already hand-patched, because
  its `.claude/` adoption is deferred and `cs update` would not re-render those
  files there.

## v0.4.4 — 2026-07-31

### Fixed — the clone CLAUDE.md did not know two of its own verbs
- **Why:** §2 is the verb list every agent session loads, and it still ended at
  `cron`. `project` (v0.4.1) and `llm` (v0.4.0) were missing, so the capability a
  session needs in order to write a project's memory was invisible to the very
  file that is supposed to advertise it — the same failure mode the project-memory
  work exists to prevent. The `--account` refusal added in v0.4.1 was also absent,
  leaving an agent to discover it by hitting the exit-2.
- **What:** §2 lists both verbs and states the `--account` constraint plainly:
  the Gmail-IMAP verbs refuse on a non-default account, `thread` / `ask` are the
  engine-backed alternatives.
- **Re-collaudo:** static, every clone — one template, picked up by `cs update`.

## v0.4.3 — 2026-07-30

### Fixed — `cs update` stripped a clone's runtime ignores and staged its lock files
- **Why:** `cs update` rewrites `.gitignore` wholesale from the template. A clone
  that had added its own ignores for runtime artefacts — flock sidecars written
  next to a state file, and an acceptance-test fixture — lost them on the next
  update, and those files then showed up staged for commit. Hit on a real clone
  2026-07-30, where a schedule CSV's `.lock` and a test fixture were about to be
  committed as if they were project data.
- **What:** the patterns move into the template, where `cs update` preserves them:
  `*.csv.lock` for the sidecars, and `_*.csv` for the underscore-prefixed fixture
  convention (a file that must never be mistaken for real state).
- **Re-collaudo:** static, every clone. `.gitignore` only.

## v0.4.2 — 2026-07-30

### Fixed — templates recommended the very call the new `--account` guard refuses
- **Why:** v0.4.1 made `contacted` / `unanswered` / `dossier` / `draft-reply`
  refuse a non-default `--account` instead of answering about the operator's own
  mailbox. That exposed two templates telling an agent to do exactly that: the
  clone `CLAUDE.md` §9 and the `customer` skill both used
  `cs --account <other> dossier <email>` as their key-contacts step, which is now
  an exit-2 dead end on the account where most business relationships actually
  live.
- **What:** both use `thread` there — engine-backed, honours `--account` — and
  say plainly that `dossier` is the fuller check but only on the operator's own
  mailbox. Adds the `company/team-conventions.md` slot the triage skill
  references, so that pointer is no longer dangling: it records who replies from
  which mailbox, i.e. what the Sent-archive checks structurally cannot see.
- **Re-collaudo:** static, every clone. Template-only plus one new prose slot;
  no code path changes.

## v0.4.1 — 2026-07-30

### Added — `cs project new`: the per-project written memory, identical in every clone
- **Why:** every clone keeps a folder per company under `docs/projects/`, and that
  folder is the operator's memory of the relationship — what is agreed, what we
  owe, what happened, who these people are. Until now its shape was a paragraph
  of prose in `docs/projects/README.md`, and prose drifts the moment somebody is
  in a hurry. The failure that prompted this: a live prospect whose folder held a
  dossier and nothing else. Three weeks of drift sat outside it — two further
  meetings, a new counterpart who had become the project manager, a first project
  that had moved to a different business unit, and three deliverables with a
  deadline. All of it existed only in one person's head and in an unread mail. A
  convention cannot fail loudly; a missing folder structure looks exactly like a
  quiet project.
- **What:** a new verb group, `cs project new <slug> [--title …]`, stamping four
  artifacts from `cs/templates/project_memory/`:
  - `README.md` — what the project is, plus the index of its own files
  - `status.md` — the ONLY file describing the present: agreed scope, what we owe
    with dates, who decides, live risks. One home for state, so two files cannot
    disagree about it
  - `timeline.md` — what happened, when, and how we know, one source per entry;
    append-only, because a timeline's value is showing what we believed at the time
  - `meetings/` — one file per meeting, append-only with dated addenda, plus a
    `.gitkeep` so the append-only half of the scaffold survives a commit

  Every stamped file opens with front matter and an `## Abstract`, mirroring the
  `docs/` harness so a reader decides in ten seconds whether to read on. Bodies
  are HTML comments saying what belongs where rather than prose pretending to be
  content: an empty section is honest, invented content is not.

  `docs/projects/README.md.j2` is rewritten to specify the shape, the reliability
  markers (`[confirmed] [mail] [meeting] [inferred] [reported] [to verify]`), the
  append-only rule, and the division of labour between the files and engine
  memory — the engine owns live mail and is ground truth for it; the files own
  judgment, which never arrives by mail and therefore exists only if written
  down. New sibling `docs/projects/_meeting-template.md.j2` is the copy-me shape
  for a meeting note, including a "Not recorded here" section, because a note
  that hides its own gaps gets mistaken for the whole truth.

  It also records one trap found while using the verbs on a real prospect: `cs`
  must run from the clone root, since the manifest and env chain resolve from the
  working directory. The other trap that session surfaced — `--account` on the
  Gmail-IMAP verbs — is fixed in code below rather than documented.

  Templates live in a root of their own (`templates/project_memory/`, with its own
  `package-data` glob) because they are stamped per project by this verb, not once
  per clone by `cs init`. New gate `tests/run.sh` step 13 runs the verb against
  the fresh-venv install — proving the templates are packaged — and asserts
  abstract-first front matter, zero unrendered Jinja reaching a clone, the date
  taken from the manifest timezone rather than UTC, the founder-sweep mailbox
  owning the project when that sweep is on, refusal of a non-slug name, refusal
  outside a clone root, and refusal on an existing folder **without modifying it**
  (clobbering a project folder destroys the only copy of a judgment).
- **Re-collaudo:** static, every clone. No send path, no engine call and no
  campaign code is touched; the verb only writes files under `docs/projects/`.
  Clones pick the convention up with `cs update`, which adds
  `_meeting-template.md` and refreshes `docs/projects/README.md` (asking first if
  the local copy was modified).

### Fixed — `--account` no longer answers about the wrong mailbox
- **Why:** `--account` switches the ENGINE profile and nothing else, but four
  verbs read or write the operator's own Gmail over IMAP on a single credential:
  `contacted`, `unanswered`, `dossier` and `draft-reply`. Passed another account
  they answered anyway, about the operator's mailbox. `cs --account <other>
  contacted <addr>` returned a confident "no" with exit code 1 — which reads as
  "never contacted", and that is the exact check that gates outreach. The same
  flag sent `draft-reply`'s Gmail Drafts APPEND to the wrong mailbox. Observed
  live 2026-07-30 while working a real prospect whose relationship sits on a
  non-default account.
- **What:** those four parsers are marked `reads_operator_mailbox=True`, and
  `main()` refuses before dispatch when `--account` resolves to a uid other than
  the configured owner — naming the constraint and pointing at `thread` / `ask`,
  which are engine-backed and do honour the flag. The default account is
  untouched, so the cron and every existing invocation behave exactly as before.
  Documenting the trap was the wrong fix: prose does not stop a wrong answer
  being acted on. Gate 13 asserts all four refuse with exit 2 and that the
  default account is not over-blocked.

- **On the ordering:** this work was written and committed before v0.4.0 landed
  on `main`, and carried the v0.4.0 number until the two met. It is renumbered
  here rather than the other way round because v0.4.0's changelog had already
  claimed that number, and because a tag cut from `main` after this merge
  contains both — the numbers describe the merge order, not two independent
  lines. While it stood alone on `main` it also carried a known-red gate 1
  (`cs/templates/project/CLAUDE.md.j2` hardcoded an engine host); v0.4.0's
  literal purge removes exactly that, so the gate is green again in the merged
  tree.

## v0.4.0 — 2026-07-30

### Added — the kernel can make its own LLM calls, and the provider is config
- **Why:** the kernel made **zero** LLM calls of its own: every generation went
  through the engine (`rpc.chat` → `chat.send`), whose provider is decided
  downstream and whose spend is the company's own Anthropic bill. That is right
  for anything a customer reads, and pure waste for a mechanical call — the
  batch-2 campaign pays a customer-facing model, routed through the engine's
  agent loop, to emit one structured line. Measured on the 61 real customer
  replies of that campaign against the prompt production actually runs
  (full method and per-item results in the A/B record, which quotes customer
  mail and therefore lives with the operator's own docs, never in this repo):
  on the calls both sides completed, `z-ai/glm-5.2` through a gateway matches
  the engine's accuracy exactly (56/58 each) at **3.1 s** instead of the
  engine's **33 s** median, for **$1.17 per 1000 calls** — while answering all
  61 calls where the engine's transport failed 3 of them (a 502 and two dropped
  connections), and never once writing a schedule the customer did not agree
  to, which the engine does once (a bare "ok" read as "now", scheduling a
  migration seven hours before the moment the customer was told).
- **What:** four new modules, no required dependency added.
  - `cs/model_catalog.py` — the model catalog is **fetched, not hardcoded**.
    `GET /v1/models` (no API key needed) gives every id, its ship date and its
    real per-token prices; 17 curated *families* map a product line to a glob,
    and `@family` resolves to that line's newest member at call time. Disk cache
    with a 24 h TTL, stale cache preferred over no catalog, static snapshot last.
    A hardcoded list is wrong within weeks: measured 2026-07-28, an
    eight-day-old curated list already named three superseded models and priced
    one of them 37% wrong.
  - `cs/model_config.py` — `Provider` / `Tier` / `Role` (exactly ONE role today,
    `CLASSIFIER`), `ROLE_TIER`, `TIER_FAMILIES` per provider, `model_for(role)`
    (`MODEL_<ROLE>` → `MODEL_<TIER>` → provider default, each of which may be a
    pinned id or an `@family`), `resolve_spec()`, `llm_env()` endpoint
    resolution over the SAME env chain as `Settings`, `route_direct()`,
    `token_rates` (live prices; unknown id → `None`, never a fallback price),
    `call_cost`, `check_connection`, `read_env`/`write_env`/`mask_key`.
  - `cs/llm_client.py` — `build_client()`: credential onto `api_key=`
    (`X-Api-Key`) for Anthropic vs `auth_token=` (Bearer) for a gateway, `""`
    base_url collapsed to `None`, `base_url` always passed explicitly, and the
    unchosen credential attribute nulled after construction so behaviour does
    not depend on the SDK version's env-resolution. `extract_text()` selects
    text blocks (never `content[0]`, which a leading `ThinkingBlock` breaks);
    `text_of()` checks `stop_reason == "max_tokens"` BEFORE reading the text —
    without which a reasoning model that spends its whole budget thinking
    returns a silent default instead of an error.
  - `cs/worker_llm.py` — `call` / `complete` / `classify` for single-shot
    mechanical work. No prompt text and no model id lives here: the caller
    supplies the prompt, the role resolves the model. Raises `LLMConfigError`
    *before* sending when a gateway-style id meets the Anthropic-direct wire,
    which otherwise surfaces as a bare 404 naming a model that exists and is fine.
  - `cs/rpc.py` — `chat(..., role=)`. A role-declared call MAY be served
    directly by the configured provider instead of the engine. Response shape
    unchanged. An empty `allow_tools` is deliberately NOT the signal: the
    campaign reply-composer and `cs draft-reply` also run tool-free and write
    the words a customer reads, so inferring "safe to route" from tool-freedom
    would route exactly the traffic the charter keeps on the engine.
  - `cs/cli.py` — `cs llm` (what the kernel resolves to now), `cs llm models`
    (the menu: family, newest member, ship date, real price, what it is for),
    `cs llm set <role|tier> <@family|id>` (validates before writing), `cs llm
    test`. Non-interactive so the same verbs work from a cron wrapper.
  - `cs/config.py` — `env_file_chain()` split out of `load()` so the dotenv
    layers have ONE definition, shared with `model_config.env_layers()`.
- **Charter:** the tier split *is* the safety boundary — worker only. Contextual
  and customer-facing generation stays an engine call (invariant §4), and no
  send path, `CS_PAUSE` check, or deny-list changes because a model got cheaper.
  No company literal enters `cs/`: model ids and family names are the same for
  every clone, and the endpoint, credential and per-role model come from env.
- **Config:** all optional, and **routing is off unless asked for**.
  `CS_LLM_ROUTE=direct` opts a clone into the provider path and is the kill
  switch (set it back to `engine` and the next cron tick is on the old path —
  no code change, no re-pin). On the direct path errors are LOUD by design:
  a broken provider config raises instead of silently falling back to the
  engine, so it cannot hide behind the very spend this path avoids. `CS_LLM_PROVIDER`, `CS_LLM_BASE_URL` (for
  OpenRouter this is `https://openrouter.ai/api` — the SDK appends
  `/v1/messages`; `/api/v1` 404s on an HTML page), `CS_LLM_API_KEY`,
  `MODEL_<ROLE>`, `MODEL_<TIER>`. With nothing set but an `OPENROUTER_API_KEY`
  present, the worker tier goes to OpenRouter.
- **Defaults:** LEAD `@claude-opus`, WORKER `@claude-sonnet`. Choosing a
  smaller model to save money is a decision that must be EARNED by a
  measurement on that role's real task; the A/B earns it for `CLASSIFIER`
  (`@glm`) and nothing else.
- **Dependency:** `anthropic>=0.107` is an **extra** (`pip install
  "cs-kernel[llm]"`), imported lazily — a clone that makes no kernel-side LLM
  call does not grow a dependency, and every other verb works without it.
- **Re-collaudo:** static for both clones — this adds modules, changes no
  existing behaviour, and nothing calls it yet (`role=` is opt-in and
  `CS_LLM_ROUTE` defaults to the engine). It becomes a full re-collaudo the
  moment a call site is wired, which is a SEPARATE, reviewed change.

### Fixed — the project templates carried the mother company's operator
- **Why:** the anti-fork gate greps for company hosts and slugs, but the
  operator's NAME is company data too, and it was invisible to the pattern.
  Found 2026-07-30: the founder's first name in 20+ places across the project
  templates (skills, README, `.env.example`), his personal mailbox as a search
  example, a real customer's name inside an incident note, and the engine host
  as a literal in `CLAUDE.md.j2` — every clone stamped for another company
  shipped all of it. Separately, four templates shared a
  `… | reject(…) | first` expression that CRASHES `cs init` under
  StrictUndefined for any clone with a single account: the minimal clone could
  not render its own CLAUDE.md.
- **What:** all operator/customer/host literals replaced with neutral prose or
  existing template variables (`engine_ws_url` was already prompted — the
  literal was just never converted); the single-account crash fixed in all four
  templates (with one account, the default account is the fallback). Two gates
  so neither returns: the step-1 grep now also matches the operator's name and
  mailbox (pattern updated in `CLAUDE.md` too — the two must stay identical),
  and a new step 12 renders EVERY template under `cs init`'s own jinja env in
  both account shapes and sweeps the RENDERED output for literals — the source
  grep cannot see a literal the template engine assembles.
- **Re-collaudo:** static, plus one `cs update` dry-run per clone to confirm
  the re-stamped skills read correctly. Behaviour of running clones is
  untouched — these files are only read at `init`/`update` time.

## v0.3.7 — 2026-07-25

### Fixed — an approved tool call deadlocked the client and hung every caller
- **Why:** `EngineClient._recv_loop` is the only consumer of the WebSocket, and
  it awaited the notification handler inline. `chat()`'s handler answers a
  `chat.pending_approval` notification by issuing `chat.approve`, and `call()`
  ends in `await asyncio.wait_for(fut, …)` — on a future only the receive loop
  can resolve. So the approve request went out, the engine really did run the
  tool, and every frame after it was buffered and never dispatched. Sixty
  seconds later the inner `wait_for` raised `TimeoutError` *inside* the receive
  loop; the `except (ConnectionClosed, CancelledError)` clause did not catch it,
  the receive task died silently, and the outer `chat.send` future was never
  resolved nor failed — the caller blocked until something killed it.
  Measured against the live engine 2026-07-25: `chat.send` returned in 43.2 s and
  the client, still not listening, was killed 106 s later. This is why
  `cs chat --allow send_draft` "sends but never returns", and why it also hit
  `cs ask` / `cs draft-reply`: the handler calls `chat.approve` even to DENY, so
  the deadlock fires on any gated tool regardless of the allow-set. It also left
  the engine holding a zombie turn per abandoned call.
- **What:** notification handlers are spawned with `asyncio.create_task` and
  tracked, never awaited inside the receive loop (the module docstring already
  promised exactly this: "a second call can be issued while a long-running one
  is still in flight"). Defence in depth: the receive loop now fails every
  pending future on ANY exception, not only on connection close, so a dead
  reader surfaces as an error instead of an indefinite hang; a failed handler is
  reported on stderr instead of at garbage-collection time; and `__aexit__`
  cancels outstanding handler tasks.
- **Re-collaudo:** full, every clone. This is the shared RPC path — `ask`,
  `draft-reply`, `chat`, and every campaign loop that talks to the engine.

## v0.3.6 — 2026-07-25

### Fixed — threading headers survived only for short Message-IDs
- **Why:** `In-Reply-To` / `References` are not in `email.policy.default`'s
  header registry, so they are folded as unstructured text: any Message-ID too
  long for one 78-column line came out RFC2047 encoded-word-mangled
  (`In-Reply-To: =?utf-8?q?=3C!=26!AAAA…?=`). The receiving client then saw no
  valid reference at all — the reply opened a NEW thread and our outbound
  carried no trace of the customer's message, which also breaks any
  "did we already answer this?" check that reads `References` back. Measured on
  the live support@ mailbox: 2 of the 25 batch-2 contacts who wrote have an
  inbound Message-ID over 78 chars (105 and 85), so v0.3.5's threading silently
  did nothing for them.
- **What:** `build_mime()` builds the message with
  `email.policy.default.clone(max_line_length=998)` (the RFC 5322 hard maximum).
  Both headers now come out verbatim on one line; `Subject` is still RFC2047-
  encoded for accents. Mapping the two headers to `MessageIDHeader` in a cloned
  `header_factory` was tried and rejected: it fixes `In-Reply-To` and silently
  truncates a multi-id `References` to the first id.

### Fixed — a delivered mail could be reported to the caller as a failed send
- **Why:** `send()` mirrors the message into Gmail Sent over a second IMAP
  session AFTER SMTP has accepted it. Only the `typ != "OK"` case was soft; an
  exception (IMAP login failure, throttling, a dropped connection) propagated
  out of `send()`, so a mail the customer had already received was reported as
  a failure. In a campaign loop that means the state write that follows a
  successful send is skipped, the operator is told the customer was not
  answered, and the next run sends a duplicate.
- **What:** the mirror moved into `_mirror_to_sent()`, which never raises —
  every failure writes one stderr warning saying the mail WAS delivered. Only
  the SMTP phase may raise, which is what the docstring always promised.

### Re-collaudo
- Every clone that sends mail: static tier. `mrcall-cs`: full — it is the clone
  whose conversational loop depends on both fixes.

## v0.3.5 — 2026-07-25

### Added — RFC threading headers on the cs-SMTP send path
- **Why:** every mail `send_mail.send()` produced was a NEW thread. A campaign
  loop that answers a customer's reply therefore opened a second conversation in
  their mailbox instead of replying inside theirs (live defect: the batch-2
  acknowledgement mails). Any clone whose operator answers customers wants this —
  rule of two, so it belongs here and not in a clone.
- **What:** `build_mime()` and `send()` take optional `in_reply_to` and
  `references`. `In-Reply-To` is set verbatim (the value is already an
  angle-bracketed `Message-ID`); `References` is set to `references`, falling back
  to `in_reply_to` when empty. Passing neither is byte-identical to v0.3.4 — no
  existing caller changes.

### Added — `gmail_archive.thread_with()`: the ground-truth conversation reader
- **Why:** the loop that decides what to answer must read the mailbox itself. The
  engine's search could not surface the body of a real customer reply for 31+
  hours (`emails.search` depends on sync state), which froze a live campaign
  contact. IMAP has no such dependency. The existing readers return headers only,
  so nothing in the kernel could hand a customer's actual words to the composer.
- **What:** `thread_with(settings, addr, limit=20) -> list[dict]`, newest first,
  one read-only IMAP session (`BODY.PEEK`) over All Mail, matching `OR FROM TO`
  so it covers both directions. Each row carries
  `date / from_addr / outbound / subject / message_id / references / body /
  attachments`. `text/plain` wins; an HTML-only mail is tag-stripped with the
  stdlib `html.parser` (never a regex — the text is fed to a model that then
  answers a customer); bodies are whitespace-normalised and truncated at 4000
  chars; attachment parts contribute FILENAMES only, never base64.
- **DRAFT-FREE:** All Mail also holds unsent drafts, and Gmail marks them only
  with the `\Draft` X-GM-LABEL — the IMAP `\Draft` FLAG is NOT set, so an
  `UNDRAFT` search does not exclude them (verified 2026-07-25 against the mother
  clone's mailbox). They are dropped: a queued draft is a mail the customer never
  received, and feeding it back as something "we wrote" would ground a reply in a
  conversation that never happened. On a non-Gmail IMAP server the labelled FETCH
  degrades to a plain one instead of failing.

### Changed — header FETCH now asks for `REFERENCES` and `IN-REPLY-TO`
- `_hdr()` and `_fetch_headers()` add both fields, so a caller can thread a reply
  from any of the existing header readers, not only from `thread_with`.

- **Re-collaudo:** `mrcall-cs` (batch-2 Centralix→Vonage conversational loop) —
  full (live send + live IMAP read). Other clones: static — the two send-path
  parameters are optional and default to the v0.3.4 behaviour, and `thread_with`
  is purely additive.
- **Known pre-existing gate failure (not introduced here):** `tests/run.sh` step 1
  (company-literal grep) has been red since v0.3.2 — `cs/templates/project/
  CLAUDE.md.j2:52` names the mother clone's engine host. Every other step passes.

## v0.3.4 — 2026-07-22

### Fixed — `send-first` no longer dedups against the whole Sent archive
- **Why:** v0.3.3 shipped `send-first` with the composed-draft `send-draft`
  dedup (refuse if the address has ANY Sent thread within `dedup_days`). Wrong
  for a fixed-template first notice: that targets a **curated contact list** (a
  migration warning to KNOWN customers, many of whom have recent support threads
  with us), so the archive dedup would silently skip legitimate targets.
- **What:** `send-first` drops the `_sent_threads_to` check. Idempotency is now
  the contact `state` alone — once the notice goes out the state flips to `sent`
  and a re-run refuses; send-then-mark (the sub-second crash window is far less
  bad than skipping a warning). No change to `send-draft`/`send-reminder`.
- **Re-collaudo:** `mrcall-cs` (batch-2 campaign) — full (live send). Others: none
  (only the just-added `send-first` changes).

## v0.3.3 — 2026-07-22

### Added — `campaign send-first`: the first-notice sender the fixed-template lifecycle was missing
- **Why:** the fixed-template lifecycle (`send-reminder` / `send-sms`) only ever
  drove contacts **already in `sent`** — the *first* notice was sent by a prep
  one-off (June's `migration_loop.py`), never by a kernel verb. `send-draft`
  (composed-draft) can't stand in: it renders the body as **markdown**, which
  mangles call-forwarding dial codes (`**004*<num>#` → bold). So a campaign
  whose first mail needs real HTML had no sanctioned kernel path.
- **What:** `cs campaign send-first <contact_id> [--commit]` →
  `campaign.send_first`. Mirrors `send_reminder` but renders the PACK's
  `builders.build()` (first-notice copy, hand-built HTML) and marks the contact
  `sent`. `CS_TRIAGE_MODE=draft` → append the rendered mail (HTML) to the
  operator's Gmail Drafts for review (idempotent, never sends); `=send` →
  cs-SMTP send then mark `sent`. Gates: pack required (loud refusal), contact
  NOT already `sent`, **Sent-archive dedup first** (never re-mail), `CS_PAUSE`,
  `RATE_CAP` (send path).
- **Re-collaudo:** `mrcall-cs` (batch-2 Centralix→Vonage campaign uses it) — full
  (live send). Other clones: static (new additive verb, no behaviour change to
  existing verbs).

## v0.3.2 — 2026-07-21

### Fixed — the hidden templates (`.claude/*`, `.env.example`, `.gitignore`) were broken stubs; re-derived from the reference clone
- **Why:** v0.3.1 shipped the hidden templates into the wheel, but they were
  stripped/corrupt stubs from the initial extraction:
  - `.claude/settings.json.j2` rendered **invalid JSON** (a literal `n` where
    `\n` belonged);
  - `.gitignore.j2` **dropped the secret-ignore patterns** (`firebase-sa.json`,
    `*-sa.json`, `*.pem`, `*.key`, `*.db`) — a real security risk if adopted;
  - `.env.example.j2` concatenated two vars onto one line and dropped
    `SELF_UIDS`/`SELF_EMAILS` + guidance comments;
  - `.claude/commands/cs-review.md.j2` had a `.venv`→`.venor` typo + a hardcoded
    title; `munchausen.md.j2` was a placeholder stub;
  - `.claude/skills/triage-support-mail/SKILL.md.j2` had **lost §1 (the
    deterministic `cs unanswered` Sent-anchored sweep) and §1b (engine
    task-ledger reconcile)** + mangled headers;
  - `.claude/skills/{customer,find-document}/SKILL.md.j2` rendered an **empty
    `--account`** for founder_sweep-off clones (unconditional
    `{{ founder_sweep_account }}`).
- **What:** re-derived all 11 hidden templates from the reference clone
  (`mrcall-cs`), parameterised by flat config keys + a `founder_sweep`-gated
  `nondefault_account`. Verified: `render(kernel, manifest(mrcall-cs)) ≡ mrcall-cs`
  **byte-for-byte** for 9/11 (customer/find-document intentionally keep neutral
  example placeholders — see residuals), `settings.json` is valid JSON for both
  clones, `.gitignore` carries every secret pattern, triage §1/§1b restored, and
  both reference clones render with **zero StrictUndefined**. Independently
  reviewed (adversarial pass): **GO**. Also fixed the `keep_trailing_newline=False`
  gotcha (templates end with a double newline to emit one).
- **Known residuals (non-blocking, tracked):** `customer`/`find-document` keep
  neutral example placeholders — baking the mother clone's real customer names
  into the shared template would leak them to every clone; `campaign-tick` still
  emits the `Ciao MrCaller!` product-autoresponder example in a non-mother
  render (needs a future `manifest` field for company autoresponder signatures).
- **Clones must re-collaudo:** full tier — this makes `.claude/` safely
  template-ownable. Re-pin to `v0.3.2`, `cs update` to adopt `.claude/`
  (reconcile skill content as with CLAUDE.md), re-verify.

## v0.3.1 — 2026-07-18

### Fixed — hidden templates (`.claude/`, `.env.example`, `.gitignore`) were missing from the wheel
- **Why:** `[tool.setuptools.package-data] cs = ["templates/project/**/*"]` — the
  `**/*` glob does not match dot-prefixed files/dirs, so a wheel-installed kernel
  shipped `templates/project/` **without** `.claude/` (skills/commands/settings),
  `.env.example.j2`, `.gitignore.j2`. A clone stamped via `cs init` from the wheel
  would be missing its skills/commands/settings + `.env.example`/`.gitignore`, and
  `cs update` could not manage them (they aren't in the installed package).
- **What:** add explicit `templates/project/.*` + `templates/project/.claude/**/*`
  package-data patterns. Verified the built wheel now contains all 9 `.claude/*`
  templates + the two root dotfiles.
- **Clones must re-collaudo:** static tier (packaging-only; no code behavior change).
  Re-pin to `v0.3.1`; to bring `.claude/` under `cs update`, re-run `cs update` (it
  will now surface the `.claude` templates — reconcile skill content as with CLAUDE.md).

## v0.3.0 — 2026-07-17

### Added — the clone `CLAUDE.md` is now templated; `docs/customers` → `docs/projects`
- **Why:** the clone `CLAUDE.md` was NOT templated — each clone hand-maintained
  it, so it drifted from the kernel and a shared change had to be copied into
  every clone by hand. And `docs/customers/` is really "per-project working
  folders", not only customer dossiers.
- **What:**
  - New `cs/templates/project/CLAUDE.md.j2` — the clone operator manual is now
    kernel-owned and parameterised (flat config keys). Company-specific
    engine/API notes stay in the `company/claude-extra.md` slot (CLAUDE.md points
    to it; NOT inlined — `cs update` renders with `from_string`/no loader, so
    `{% include %}` is unavailable). Adds an **"Editing this clone —
    template-owned vs clone-owned"** section.
  - Template dir `docs/customers/` → `docs/projects/`; its README rewritten in
    English; the `customer` skill + `docs/ARCHITECTURE.md.j2` reference
    `docs/projects/`.
  - New config key `repo_docs_shape` (`collect_config` prompt, default
    `generic`) — distinguishes the mother clone from stamped children in the
    intro line.
  - Founder-sweep clause no longer appends a stray `@` (account names are full
    mailbox addresses).
- **Verified:** rendered `CLAUDE.md.j2` for BOTH reference clones with the real
  `project_init` Jinja env (`StrictUndefined`) — zero errors;
  `kernel + manifest(mrcall-cs)` is byte-equivalent to the mother's current
  CLAUDE.md except the intended changes; `kernel + manifest(124)` renders 124's
  values with no MrCall literals leaked.
- **Clones must re-collaudo:** full tier — CLAUDE.md/docs become template-owned.
  Adoption also needs each clone onboarded to template management
  (`template-manifest.json`); neither reference clone has one yet, so
  `cs update` cannot pull this until that follow-up lands.

## v0.2.3 — 2026-07-17

### Added — `cs tasks create` / `cs tasks close` + triage reconciles the sweep against the engine ledger
- **Why:** the deterministic `cs unanswered` sweep only sees support@'s own
  Gmail Sent folder, so an item answered from a DIFFERENT mailbox (e.g. Mario's
  personal `mario.alemi@` account) still gets re-flagged as unanswered
  (incident 2026-07-17: Eva Fani). And when the engine's own detection never
  turned a real inbound into a task, the operator had no write-path to record it.
  We need a place to record "handled" / "seen" that the sweep can reconcile
  against: the engine task ledger.
- **What:** `cs tasks` becomes a verb-with-subactions. Bare `cs tasks` is
  unchanged (the open-task list). New:
  - `cs tasks create --email E --title T --event-id ID [--event-type email]
    [--name N] [--phone P] [--urgency medium] [--reason R] [--suggested-action S]
    [--thread-id TID] [--json]` → `tasks.create` (upsert on
    owner_id+event_type+event_id — idempotent; `sources` carries the event id(s)
    and, when given, `thread_id`).
  - `cs tasks close TASK_ID [--note NOTE] [--json]` → `tasks.complete`.
- **Triage skill:** `triage-support-mail` now reconciles each sweep survivor
  against the ledger by `contact_email`: OPEN task → work it; CLOSED task →
  SKIP (already handled, possibly elsewhere); NO task → `cs tasks create` so the
  desktop sees it, then work it. `cs tasks --json` returns OPEN tasks only; the
  operator passes `cs rpc tasks.list '{"include_completed":true}'` to see closed.
- **Guard:** `tests/test_tasks_verbs.py` (gate 10 in `tests/run.sh`) pins the
  RPC method + params for both subactions; the help tree gate now covers
  `cs tasks create|close --help`.
- **Engine dependency:** relies on the engine RPCs `tasks.create` /
  `tasks.complete` (already live + tested on the support@ daemon).
- **Clones must re-collaudo:** full tier — this adds verbs the triage skill now
  depends on. Re-pin to `v0.2.3` and run one live `cs tasks create` +
  `cs tasks close` round-trip against the clone's engine.

## v0.2.2 — 2026-07-16

### Added — deterministic `cs unanswered` sweep (replaces a flaky LLM discovery)
- **Why:** the triage skill discovered "customer mail still needing a human
  reply" by asking the engine LLM (`cs ask "elenca la posta … senza risposta"`).
  That is NON-DETERMINISTIC — two runs of the same query returned different sets
  and missed real unanswered customer mail 6–13 days old that had no engine task
  (incident 2026-07-16). We need a sweep anchored to the Gmail Sent archive, no
  LLM in the discovery loop.
- **What:** new `cs unanswered [--days 14] [--json]`. Enumerates recent inbound
  (Gmail All Mail, **Date-header** windowed — never INTERNALDATE, which the
  engine sync re-touches and which made prior queries flip between runs) and
  subtracts every sender we've since written to (Gmail Sent = the dedup ground
  truth). A sender is OPEN iff no Sent message to them is dated after their last
  inbound. Excludes self (`SELF_EMAILS` + operator address), the new
  `CS_SYSTEM_SENDERS` ignore-list, and the `do_not_contact` suppression table.
  Returns oldest-first. It does NOT classify intent / autoresponders — that
  stays the LLM's job; over-inclusion is acceptable and filtered downstream.
- **New code:** `cs/gmail_archive.py` bulk readers `inbound_recent` /
  `sent_recent` (one IMAP session, batched header FETCH, read-only); pure,
  unit-testable `cs/unanswered.compute_open` + IMAP-backed `open_threads`;
  `cs unanswered` verb in `cs/cli.py`.
- **New config:** `CS_SYSTEM_SENDERS` (comma-separated no-reply/system addresses
  to ignore), layered env/manifest like the other knobs, default empty. The
  clone declares its own system addresses in env/manifest — NEVER hardcoded in
  the kernel (charter grep gate).
- **Guard:** `tests/test_unanswered.py` (wired as gate 9 in `tests/run.sh`)
  exercises the open-logic on synthetic dicts.
- **Clones must re-collaudo:** full tier — this adds a verb the triage skill now
  depends on. Re-pin to `v0.2.2`, set `CS_SYSTEM_SENDERS` for the clone, and run
  one live `cs unanswered --days 14`, cross-checking a couple of hits against
  `cs contacted <email>`.

### Fixed — `cs init` crash, fake-optional prompts; `drive.py` i18n; license
- `python -m cs init` raised `NameError: name 're' is not defined` on every
  invocation — `re`/`sys` were imported only inside the `if __name__ ==
  "__main__"` guard, which the real `cli.py` entry point never executes.
  Moved both to top-level imports. Verified end-to-end in a clean venv: the
  full init flow now completes and renders the project.
- `prompt_input`'s `default=""` was overloaded to mean both "no default"
  (required) and "optional, blank is fine" — five prompts labeled
  `(optional)` / "or empty" actually rejected blank input and looped
  forever. `default=None` is now the "required" sentinel; `default=""`
  means what it says. Verified the same fields now accept blank input and
  the flow completes.
- Removed the stale `doc-startsession` / `doc-endsession` / `doc-intrasession`
  command templates so new clones stop inheriting commands retired
  kernel-wide (superseded by the globally-installed `mrcall-ai-kit`
  `doc-start` / `doc-end`).
- Translated `cs/drive.py`'s Italian CLI help/error strings to English.
- Added the MIT `LICENSE` (was undeclared despite the "License & status"
  README heading) and declared it in `README.md` + `pyproject.toml`.
- `cs init`'s Engine WS URL default is now a generic placeholder instead of
  `wss://desktop.mrcall.ai` (charter grep gate — this was the last company
  literal in `cs/`; the gate is green again).
- **Clones must re-collaudo:** static tier only — no behavior change on any
  operator verb; `cs init` / `cs update` and `cs.drive` output text are the
  only surfaces touched.

## v0.2.1 — 2026-07-16

### Fixed — `draft-reply` now lands in the operator's Gmail Drafts (was invisible)
- **Root cause:** `cmd_draft_reply` only ran the engine compose. The engine's
  `create_draft` is non-destructive, so it auto-executes even with the empty
  `allow_tools`, storing the draft in the ENGINE draft store (visible via
  `cs rpc drafts.list` / the desktop app) — but **never in the operator's Gmail
  Drafts**, the surface where review and sending happen. The operator saw an
  empty Gmail Drafts and concluded "nothing was drafted". Recurring bug: prior
  fixes only touched an installed copy, never this source, so `pip install` /
  re-pin wiped them every time.
- **Fix:** `cmd_draft_reply` now diffs the engine draft store around the compose
  call and APPENDs the freshly composed draft into Gmail Drafts via IMAP
  (`gmail_drafts.append_draft`, the same mechanism as `campaign queue-draft`),
  with the draft's real `to`/`subject`/`body`/`in_reply_to`/`references`. It
  fails loud (rc=1) if the composed draft has no recipient/body, and is a no-op
  mirror when the engine composed nothing (clarifying question / escalation).
- **Guard:** new `tests/test_draft_reply.py` (wired as gate 8 in `tests/run.sh`)
  fails the moment the Gmail-Drafts append is removed.
- **Clones must re-collaudo:** full tier — this changes the Phase-1 review
  surface. Re-pin to `v0.2.1` and re-run one live `draft-reply`, verifying the
  draft appears in the operator's Gmail Drafts (not just `cs rpc drafts.list`).

## v0.2.0 — 2026-07-12

### Added — project template + `cs init` / `cs update`
- `cs/templates/project/` — Jinja2 project skeleton (skills, commands, company
  prose slots, docs, bin, manifest, requirements). Includes the generic
  `/customer` skill.
- `cs init` — interactive clone generator: prompts → render → `git init` →
  writes `template-manifest.json` (init_data + sha256 checksums).
- `cs update` — selective re-apply of template changes; asks on local
  modifications; same Jinja env as init (`trim_blocks`/`lstrip_blocks`).
- Dependency: `jinja2>=3.1`. Package data ships templates with the wheel.

### Added — `cs cron`
- `cs cron install` / `uninstall` / `status` — manage the operator's crontab
  entry directly from the CLI (`cs/cron.py`), instead of hand-editing crontab
  per clone. (Documented 2026-07-14; shipped in the tagged v0.2.0 commit but
  missing from this changelog until now.)

### Collaudo (this release)
- StrictUndefined render of all 30 templates: 0 failures.
- init→update no-op on a throwaway clone: 0 updated / 0 skipped / 0 added.
- Existing verbs still resolve via editable install (`cs --help`).

### Re-pin impact
- Clones that only run operator verbs: optional re-pin (new surface only).
- Anyone adopting `init`/`update` or a fresh clone: pin `@v0.2.0`.
- Full collaudo tier: static (help tree grows by `init`/`update` early exit;
  they bypass manifest load). Live read-only verbs unchanged.

## v0.1.0 — 2026-07-09

Initial extraction of the shared kernel from the two specimens — A (the
mother clone) and B (the first child) — per the design brief
`cs-kernel-manifest-separation.md` (§5.1 winners table, §5.1b packs,
§3 ports, §4 manifest).

### Winners merged (debt variance resolved, one version survives)
- `campaign.py` — **A**: Gmail-Sent/All-Mail ground-truth dedup
  (`_sent_threads_to` / `_inbound_since` read IMAP via `gmail_archive`);
  B's engine-search dedup is deleted as fork drift (it is blind to
  hand-sent mail and drops threads when the customer replies last).
  B's generic excluded-campaign guard SHAPE kept; the value moved to
  `settings.excluded_campaign` (manifest).
- `gmail_archive.py` — **A (superset)**: `inbound_since()` + Message-ID
  fetch/emission restored for everyone.
- `send_mail.py` — **B shape**: From display name from
  `settings.email_from_name` (manifest `[company].from_name`); falls back
  to the bare address when unset.
- `config.py` — fused: B's 3-level env-file loader (platform → home →
  repo, later wins; platform path from the manifest), ONE
  `settings.state_dir` derived from the slug (kills the hardcoded path
  scatter: db, token cache, SA key, CS_PAUSE, operator log, Shopify token
  cache), `<PREFIX>_`/bare Shopify alias convention generalized
  (`[crm.shopify].env_prefix`).
- `cli.py` — A base; CRM block replaced by the port call; `prog=` and all
  identity prints from Settings.
- `rpc.py`, `filter.py`, `gmail_drafts.py`, `__main__.py` — byte-identical
  in both clones, adopted as-is (rpc gains a loud error on unconfigured
  ws_url, now that the kernel default is empty).
- `_time.py` — same helpers, timezone now a knob
  (`[knobs].timezone` → `local_hour/local_date/past_local_noon`).
- `auth.py`, `resolve.py` — Firebase app names fixed to neutral kernel
  constants (`cs-kernel-*`); docstrings de-branded.
- `state.py`, `review.py`, `drive.py` — paths/scope messages derived from
  Settings.
- `scripts/find_profile_uid.py` — **B**, generalized (SA key discovered by
  glob over `~/.*-cs/`, or `--sa`).

### New kernel modules
- `manifest.py` — `manifest.toml` (brief §4.2 schema) → pydantic →
  Settings overrides; `$CS_MANIFEST` override for sandboxes; missing
  manifest tolerated (bare `--help` works), invalid manifest fails LOUD.
- `crm/` — the CRM port (brief §3): `CrmCtx`/`CrmRow`/`CrmResult` envelope
  with `render_hints`; explicit registry (`starchat`, `shopify`, `none`);
  unknown adapter = loud startup error; `lookup` never raises; verdict
  stays CRM-agnostic. `starchat` = A's inline RPC refactored;
  `shopify` = B's `crm.py` generalized (token cache under
  `settings.state_dir`, env prefix from the manifest).
- `ingest/` — the producer port (brief §3.6): `mrcall-tracking` (A's
  subprocess; script/python paths from the manifest, no absolute paths in
  the kernel) + `none` (B's reply-only stub); `fetch` degrades to an
  empty well-formed worklist with a surfaced note.
- `campaign_pack.py` + generic senders (brief §5.1b, decided 2026-07-08,
  driver: the upcoming ~70-user migration): pack loader
  (`campaigns/<name>/campaign.toml` + `mail_first.md`/`mail_reminder.md`
  with a `Subject:` first line + `sms.txt` + optional `builders.py` hook +
  `playbook.md`), `cs campaign packs` discovery verb, and the
  `send_reminder`/`send_sms` handlers: pack template/builders →
  `send_mail`/`sms`, **stamp-before-send**, reply-check on Gmail ground
  truth, once/day + cap + window gates, CS_PAUSE, RATE_CAP. A
  fixed-template action with NO pack is refused loudly — the kernel never
  invents copy.
- `sms.py` — generic SMS via the manifest `[sms].proxy_base` proxy +
  `SMS_BUSINESS_ID`; raises `SmsError` with the reason (no silent False,
  unlike the one-off it replaces).

### Declared behavior deltas vs the specimens (for the migration registers)
- Dossier CRM section prints generically from `render_hints`
  (`-- CRM [starchat] (n) --` instead of the per-company header).
- `cs plan` surfaces a producer failure as a printed note over an empty
  worklist instead of a traceback.
- Identity strings in `contacted`/`dossier`/verdict lines derive from
  `settings.email_address` (same rendered bytes once the manifest is in).
- Reminder/SMS senders stamp the dossier BEFORE the send (the old one-off
  sent first); crash direction is now "skip one", never "send twice".
- New verbs: `campaign send-reminder`, `campaign send-sms`,
  `campaign packs`.

### Collaudo required
Both clones, FULL tier (send paths, campaign, gmail_archive, send_mail
all touched) — brief §6.6. B additionally lands the pre-declared B1/B2
dedup ground-truth switch.
