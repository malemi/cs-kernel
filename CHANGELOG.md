# Changelog — cs-kernel

Clones pin **tags only**. Every entry states which clones must re-collaudo
and at which tier (design brief §6.6: static / +live read-only / full).

## v0.4.0 — 2026-07-30

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

  It also documents two traps found while using the verbs on a real prospect:
  `--account` switches the ENGINE profile only, so `cs contacted` / `cs unanswered`
  answer for the operator's own mailbox whatever account is passed (a false
  "never contacted", exit 1) while `cs thread` / `cs ask` do honour it; and `cs`
  must run from the clone root, since the manifest and env chain resolve from the
  working directory.

  Templates live in a root of their own (`templates/project_memory/`, with its own
  `package-data` glob) because they are stamped per project by this verb, not once
  per clone by `cs init`. New gate `tests/run.sh` step 11 runs the verb against
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
- **Known-red gate, pre-existing:** `tests/run.sh` step 1 fails on
  `cs/templates/project/CLAUDE.md.j2:52`, which hardcodes an engine host instead
  of deriving it from the manifest. Present before this change and untouched by
  it; it belongs with the in-flight de-companyisation of the skill templates.

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
