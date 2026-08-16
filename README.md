# cs-kernel

**A ready-made customer-service operator for your company mailbox.**

Typical path:

1. **Interactive first** — open Claude Code or OpenCode in the project folder,
   work in natural language (“load this customer”, “draft a reply…”).  
2. **Memory fills up** — mrcall-desktop syncs mail and stores relationship
   state; the more you use it, the less you re-explain.  
3. **Optional automation** — when you trust the drafts, turn on a small
   cron tick that prepares the next batch for you (still draft-first by default).

Under the hood it talks to **[mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop)**
(the engine that syncs mail, keeps memory, and can draft/send). This package
is the thin setup + skills layer in front of that engine — not a mail server
by itself.

You need a mrcall-desktop profile for the mailbox you want to operate.

---

## What you get

1. A small project folder (e.g. `acme-cs/`) configured for **your** company  
2. Skills the AI can run: load a customer, triage mail, advance campaigns, …  
3. Safety defaults: **draft first**, review before anything is sent  
4. An optional **cron wrapper** so the same operator can tick unattended  

Voice and product policy live in the engine profile, not in this repo.

---

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (fast installer)  
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Claude Code** or **OpenCode** (the TUI/session you work in)
- A **mrcall-desktop** engine profile for your support mailbox — see
  **Step 0** below; signing in there writes everything `cs init` and
  `cs login` need, so you never have to look up a WebSocket URL or a
  Firebase uid by hand.
- **Gmail or Google Workspace** for the operator mailbox — dedup and Gmail
  Drafts read Gmail's own Sent/All Mail folders over IMAP; other IMAP
  providers are not supported today.
- Mailbox password / app password for that address (IMAP/SMTP)

Without the engine and secrets, setup still creates the folder, but the AI
cannot load real mail or memory yet.

---

## Setup (copy & paste) — example: ACME

Imagine your operator address is `support@acme.example`.

### 0. Install mrcall-desktop and sign in

**mrcall-desktop** is a separate desktop app: it holds the mailbox sync,
the relationship memory and the task list, and it runs a small local
daemon (the "engine") that everything below actually talks to. **`cs` must
run on the same machine as that app and its daemon** — there is no
remote/cloud engine to point `cs` at instead.

- **macOS / Windows:** install the mrcall-desktop app.
- **Linux:** there is no packaged desktop build yet; run the engine from
  source — see the [mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop)
  repo for build/run instructions.

Open the app and sign in with the Google account for your support mailbox.
Signing in writes a profile descriptor to
`~/.zylch/profiles/<uid>/cs-descriptor.json`; `cs login` (step 5 below)
reads that file, which is why you never have to hunt down a WebSocket URL
or a Firebase uid yourself.

You need a mrcall-desktop release **newer than v0.1.29** (2026-05-05):
that public build predates the file above. If a later step reports no
descriptor found and you are sure you are signed in, update the app first.

### 1. Install the toolkit (once)

```bash
mkdir -p ~/work && cd ~/work
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
# Install the current operational pin recorded in CHANGELOG.md, never a branch.
uv pip install "cs-kernel @ git+https://github.com/malemi/cs-kernel@v0.6.0"
```

### 2. Create your company project

```bash
cs init
```

Several prompts are required — pressing Enter on an empty value just
re-asks ("Please provide a value.") — so have these ready before you
start: the **operator email**, and, if Step 0's sign-in was **not**
auto-detected, the **engine WS URL** and the **engine owner uid** (`cs
init` prefills both from the mrcall-desktop sign-in when it can). Most
other prompts — IMAP/SMTP host and port, timezone, cron schedule,
dedup/rate-limit knobs, CRM/producer/SMS/Drive — have sensible defaults;
here is what to expect for ACME:

| Question | Example |
|---|---|
| Company name | `ACME Corp` |
| Display name | `ACME` |
| From name for emails | `ACME` |
| Short slug | type **`acme`** explicitly — the wizard's own default for "ACME Corp" is `acme-corp`, which would put your state under `~/.acme-corp-cs/` instead and silently break every `~/.acme-cs/...` command below |
| Operator email | `support@acme.example` (required) |
| Engine URL + owner uid | prefilled from Step 0's sign-in if it found exactly one profile; otherwise required — from your mrcall-desktop setup |
| Default account | `support` + that same uid |
| CRM / producer / SMS / Drive | leave defaults unless you know you need them |
| Destination folder | `acme-cs` |

When you confirm, you get a folder **`acme-cs/`**.

### 3. Put secrets outside the repo

```bash
mkdir -p ~/.acme-cs
cp acme-cs/.env.example ~/.acme-cs/.env
```

Edit `~/.acme-cs/.env` (any text editor) and fill at least:

- mailbox password  
- Firebase / engine keys as in the example file  
- `CS_ACCOUNTS=support:<your-uid>`  

Never commit this file.

### 4. Install the project pin

```bash
cd acme-cs
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 5. Sign in

```bash
cs login
```

This reads the profile descriptor mrcall-desktop wrote in Step 0, prints
`email (uid)` for you to confirm, stores a refresh-token session under
`~/.acme-cs/`, and proves it with one live call.

If it also prints a line starting with `note: … FIREBASE_WEB_API_KEY=…`,
paste that exact line into `~/.acme-cs/.env` and run `cs login` again — it
means the key currently in your `.env` is missing or does not match the
one mrcall-desktop is using.

If instead it prints `cs login: no profile descriptor found under
~/.zylch/profiles/ — sign in to the mrcall-desktop app first…`, go back to
Step 0: you are not signed in on this machine, or your mrcall-desktop
build predates the descriptor writer.

### 6. Check the engine

```bash
cs whoami
```

This is the proof: it makes one real call through the engine and prints
back the identity it authenticated as. `not signed in — run cs login`
means step 5 was skipped or did not complete; anything else is covered
under Troubleshooting below.

### 7. Open the TUI and work

Still inside `acme-cs/` with the venv active:

```bash
# pick one:
claude
# or
opencode
```

You’re in a chat UI in **this project**. The AI loads skills from `.claude/`
(and OpenCode config if present). Talk normally, for example:

- *“Load customer Northwind”* → uses the **customer** skill: reads
  `docs/customers/…` **and** queries **mrcall-desktop memory** for that
  relationship (not just the markdown file).
- *“What’s still open in support mail?”* → triage / review skills  
- *“Draft a reply to …”* → grounded draft; **nothing is sent** until you
  review and approve through the normal gates  
- *“Advance campaigns”* → campaign tick skill (draft-oriented by default)

You do **not** need to memorize CLI subcommands day to day. The skills are
the product surface; the CLI is plumbing the AI (and you, if you want) can call.

---

## Troubleshooting

- **`not signed in — run cs login`** — the exact line every engine-backed
  verb prints when no session is stored yet, or the stored one does not
  match this clone's configured uid. Run `cs login` (step 5 above).
- **Connection refused / the engine seems unreachable** — the daemon is
  not answering at the configured WebSocket URL. During `cs login` this
  is caught and printed as one line (`cs login: stored the session, but
  the proof call to '<url>' failed: …`); on other verbs (`cs whoami` and
  friends) it currently surfaces as a raw Python traceback ending in
  something like `ConnectionRefusedError: [Errno 111] Connect call
  failed…`. Either way, it means the mrcall-desktop app is not running,
  or it is running on a **different machine** than the one you're typing
  `cs` on — `cs` only ever talks to the daemon on the machine it runs on
  (see Step 0).
- **`cs login: no profile descriptor found under ~/.zylch/profiles/ —
  sign in to the mrcall-desktop app first (it writes the descriptor at
  sign-in)`** — you have not signed in to mrcall-desktop on this machine
  yet, or your build predates the v0.1.29 descriptor writer (Step 0).
  Sign in (or update the app), then re-run `cs login`.
- **Nothing shows up in Gmail Drafts after a tick** — first check
  `~/.<slug>-cs/CS_PAUSE`: if that file exists, the kill-switch is on and
  every automated tick is a deliberate no-op (`rm` it to resume). If it
  is absent, read the tail of `~/.<slug>-cs/cs_operator.log` for what the
  last tick actually did.

---

## Day-to-day mental model

```text
You  →  Claude / OpenCode (in acme-cs/)  →  skills  →  cs CLI  →  mrcall-desktop
                                                              →  Gmail (when needed)
         (later) cron → same /cs-operator skill, draft-only by default
```

| You care about | What happens |
|---|---|
| Customer context | Skill loads dossier files + **engine memory** |
| Memory over time | Engine keeps relationships as mail is synced and you work |
| Replies | Drafts prepared for review; send is gated |
| Campaigns | Templates/packs advanced as drafts unless you opt into send mode |
| “Stop everything” | Create pause file: `touch ~/.acme-cs/CS_PAUSE` |

### How memory gets rich

You don’t “train a model” by hand. You:

- work interactively (customers, drafts, questions)  
- let mrcall-desktop **sync the mailbox** into entities/memory/tasks  
- optionally write durable facts the AI should keep (when you ask it to)  

Next sessions — interactive or cron — start from that memory instead of a blank page.

---

## Optional: run it automatically (cron)

When interactive use feels solid and drafts look right, you can let the
operator prepare work on a schedule. **Default remains draft-only**: the tick
triages inbound mail and advances campaigns into **drafts for your review**;
it does not freely email customers unless you later change mode and permissions
on purpose.

### What’s already in the project

After `cs init`, you have:

- `bin/cs_operator_cron.sh` — one headless tick  
- skill `/cs-operator` — triage + campaign-tick, then stop  
- kill-switch: `touch ~/.acme-cs/CS_PAUSE` (any slug: `~/.<slug>-cs/CS_PAUSE`)  
- log: `~/.<slug>-cs/cs_operator.log`  

The wrapper re-denies send surfaces so a cron run cannot “accidentally” send.

You need the **Claude Code CLI** available to cron (default path
`~/.local/bin/claude`, overridable with `CLAUDE_BIN`).

### Try one tick by hand

```bash
cd acme-cs
source .venv/bin/activate
./bin/cs_operator_cron.sh
# then inspect Gmail Drafts / run your review skill in the TUI
```

### Install a schedule (when you’re ready)

The CLI has a `cron` verb that reads `[cron].schedule` from your
`manifest.toml`, builds the crontab line with the absolute path to your
clone, and installs it idempotently:

```bash
cs cron install    # cs cron status | cs cron uninstall
```

If you'd rather manage it by hand instead, edit the crontab directly (adjust
the schedule to taste):

```bash
crontab -e
```

```cron
0 6-18/2 * * 2-5  /home/YOU/work/acme-cs/bin/cs_operator_cron.sh
```

Use the **absolute path** to your clone. Pause anytime with:

```bash
touch ~/.acme-cs/CS_PAUSE
# resume:
rm ~/.acme-cs/CS_PAUSE
```

Sending without review is a **later, deliberate** step (config + permissions),
not what you get on day one.

---

## Upgrading later

```bash
cd acme-cs
source .venv/bin/activate
# if the pin in requirements.txt changed:
uv pip install -r requirements.txt
cs update    # refreshes skills/templates; keeps your edits, except the two
             # security-critical files (settings.json, cron wrapper): those are
             # applied, with your version saved next to them as *.local-bak
```

Then reopen `claude` / `opencode` in that folder.

---

## Safety (defaults)

- **Draft first** — automated paths are not free-fire send.  
- No cold outreach without a proper contact check.  
- Contact history uses **Gmail’s own Sent mail** as ground truth.  
- `~/.<your-slug>-cs/CS_PAUSE` stops automated ticks immediately.

Turning on autonomous send is a deliberate later choice, not the default.

---

## Versioning

Install a **version tag**, not a floating branch:

```bash
uv pip install "cs-kernel @ git+https://github.com/malemi/cs-kernel@v0.6.0"
```

See [CHANGELOG.md](CHANGELOG.md) for what each release changes.

---

## License & status

MIT. Public setup kit for operators that sit in front of **mrcall-desktop**.
You still need engine access, credentials, and human review in draft mode.

**Current release:** `v0.6.0` — see [CHANGELOG.md](CHANGELOG.md) for what it
changes and the re-collaudo it requires.
