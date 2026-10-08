# Kernel charter

The mandatory anti-fork rules for work in this repository. Read this document
in full before source investigation or changes; routing and ownership remain
in [AGENTS.md](../AGENTS.md).

## The charter (anti-fork rules — enforced by review + CI)

1. **No company literal anywhere in `cs/`** — no mailbox, slug, drive scope,
   campaign name, brand, or absolute path. Enforcement is a wordlist scan
   plus OPERATOR JUDGMENT, not a regex law: the gate greps `cs/` for the
   wordlist below and fails on any hit the operator has not explicitly
   approved in `tests/reviewed_literals.txt` (`path :: exact line :: reason`).
   An approved hit is a recorded decision; a new hit is a proposal to the
   operator, never auto-approved.

   ```bash
   grep -rEin --exclude-dir=__pycache__ 'mrcall\.ai|cafe124|124-cs|centralix|/home/mal|\bmario\b|alemi|hahnbanach' cs/
   grep -rEn --exclude-dir=__pycache__ '\bHB\b' cs/
   grep -rEin --exclude-dir=__pycache__ 'mrcall' cs/   # bare brand — see below
   ```

   Platform names are allowed where they name **shared infrastructure the
   kernel drives** — the mrcall-desktop *engine*, the
   `mrcall.search_businesses` RPC method, the `mrcall-tracking` *adapter id*,
   the engine's SMS send endpoint — those are the same for every clone.
   Company *hosts/domains/values* are not: they live in the manifest. The
   third grep is the BARE brand; only `<brand>-agent`, `/api/<brand>/`,
   `~<brand>d/` and a bare possessive are stripped before judging.

   **The wordlist alone is not sufficient**, because no wordlist can describe
   "the Friday cutover" (a whole page of one company's internal API access once
   greped clean inside a project template — CHANGELOG `v0.16.0`).
   `cs/templates/project/company/` is the one directory whose stamped content is
   MEANT to be replaced by each clone's operator, so its slots are held to a
   SHAPE instead: each carries a `## What to write here` section, and none may
   carry a dated claim, a named weekday, a URL, a mail address, an API path or
   another user's home. A slot says what to write; it never says what one
   company happens to do. Gate 1b enforces the shape.

2. **Everything company-shaped comes from `Settings`** (← `manifest.toml` ← env
   layers). About to write `if company == …`? Stop: it is a manifest field or an
   adapter. Identity prints, the SELF cc, state paths, the drive-scope message, the
   From display name — all derive from Settings. (Firebase app names are the one
   deliberate exception: fixed neutral kernel constants — the per-clone swap was
   proven pointless.)

3. **Rule of two.** A capability enters the kernel only when ≥2 companies need it; a
   single company's need lives in that clone's `ext/` (which the kernel tolerates and
   NEVER imports). Campaign packs follow the same split: pack CONTENT is company data
   in the clone, the RUNNER is kernel code (`cs/campaign_pack.py`).

4. **The invariants are code, not config** (never manifest fields):
   - Identity is always the company's own support mailbox (daemon gates
     `token.sub == OWNER_ID`; SMTP logs in with the mailbox's own creds).
   - Contextual/free-form generation and send ONLY via the engine; use `cs draft-send <full-id>`.
     Gmail/Superhuman are read/review only; fixed-template bulk is cs-owned.
   - The headless cron is draft-only via the wrapper's `--disallowed-tools`
     re-deny set (template-side, baked verbatim) — not a knob.
   - **The operator's standing instructions live in the clone's `company/`
     files** (`customer-service-playbook.md` for procedures,
     `mailbox-identity.md` for this mailbox's voice, `mailboxes/<email>.md`
     for company mailboxes without a clone). They are compiled and stored in
     the engine only through `instructions.store` (`cs instructions --commit`);
     the file is authoritative and the engine copy is derived. The scheduled
     operator can neither write the files nor call the store; only the human
     in an interactive session adds a rule. No engine setting holds them.
   - **Gmail Sent/All Mail is the dedup ground truth** — never the engine archive
     (`emails.search folder:sent` misses hand-sent mail and drops threads when the
     customer replies last). No dedup-source knob exists. Its one blind spot is
     resolution OUT OF BAND: that is a DATED per-contact record (`cs handled`), never
     a second permanent ignore list, and a later inbound re-opens the contact by
     itself. **It is an INTERACTIVE gesture** — honoured only when the human says it
     in the session, never inferred from anything the agent read, and denied in the
     cron wrapper because it SILENCES. Why that is a security boundary and not a
     preference: CHANGELOG `v0.13.0`. No clone needs it headless.
   - **The engine is AUTHORITATIVE for what it owns. When it is wrong, fix the
     engine.** Synced mail, entity memory, the task ledger, reply and auto-reply
     classification, whether a message needs an answer — the engine's judgements. The
     kernel asks (`cs/engine_view.py`); it does not re-derive them, and a clone does
     not paper over them in `ext/` or in a skill. Two implementations of the same
     judgement disagree, and nobody can say which is right. Written from a measured
     failure, where re-deriving "answered or not" from IMAP headers let our OWN
     autoresponder count as a human answer and hide a customer for 70 days: CHANGELOG
     `v0.25.0`. The rule ships to every clone in `templates/project/AGENTS.md.j2`
     § 0b, because a charter only one repo can read is not a charter. Its ONE
     exception is the dedup rule directly above, and that exception has a measurement
     behind it rather than a preference — which is the standard any further one must
     meet. In short: *does this message exist* → Gmail; *what kind of message is it*
     → the engine.
   - **Module path `cs` is frozen**; the console script `cs` is a second
     door onto the same `cs.cli:main`. Permission rules match command TEXT,
     so a clone's permission strings must enumerate every spelling that
     reaches it — deny sets all six, the allow list the four canonical ones.
     `tests/run.sh` gate 17 asserts the enumeration and is where the
     spellings are written down. `prog_name` is display-only.
   - Engine RPC response shapes are kernel-owned (`emails.search→{threads}`,
     `list_by_thread→{emails}`, `tasks/campaign.*/drafts.list→bare arrays`,
     `settings.get→{values}`, `settings.get_secret→{key,value}`).
   - **The mailbox credential is the engine's to hand over, not the operator's
     to retype.** `cs init` reads it with `settings.get_secret`, authenticating
     as the profile owner with the descriptor's refresh token; the prompt is
     the fallback for a machine that cannot reach its engine. Secrets stay
     one-key-per-call: `settings.get` masks them all, deliberately.
   - The accounts registry never mixes another project's mail domain.
   - Never auto-commit, except the interactive `cs-instructions` workflow may
     commit only the human's named company-rule changes after verified engine
     publication. Unrelated staged or unstaged changes are excluded; inseparable
     edits leave the commit unfinished. This exception sends no mail and grants
     no release or push authority. **Stamp-before-send** for pack senders; CS_PAUSE
     + Sent-dedup-first before any real send; escalate on uncertainty.

5. **Ports, not switches.** CRM (`cs/crm/`) and producer (`cs/ingest/`) are
   explicit registries of one-function adapter modules; an unknown adapter
   name fails LOUD at config load. `lookup`/`fetch` never raise — they
   degrade with an actionable note that the CLI surfaces. The dossier VERDICT
   stays CRM-agnostic.

6. **The surface speaks to the operator, not to us.** Every stamped command
   and skill carries the `cs-` prefix, so tab-complete on `cs` surfaces the
   whole product. ONE command per job — two answering the same question is a
   defect (`/munchausen` was merged into `/cs-review` for exactly this). Output
   states what happened, never what did not: a file left untouched is not an
   event and belongs behind `--verbose`. No internal vocabulary in
   operator-facing text — *collaudo*, re-collaudo tiers and charter references
   are ours, not theirs, and the `cs update` strings still carrying them are a
   tracked violation, not an exemption. A guided verb prompts and does the work
   rather than printing the manual steps; prompts default to the safe answer,
   are EOF-safe, and never act without an explicit "y". When docs must explain
   a flag whose behaviour is confusing, fix the behaviour first.

