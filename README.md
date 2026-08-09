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
- A **mrcall-desktop** engine profile for your support mailbox  
  (you’ll need the engine WebSocket URL and the profile’s Firebase uid)
- Mailbox password / app password for that address (IMAP/SMTP)

Without the engine and secrets, setup still creates the folder, but the AI
cannot load real mail or memory yet.

---

## Setup (copy & paste) — example: ACME

Imagine your operator address is `support@acme.example`.

### 1. Install the toolkit (once)

```bash
mkdir -p ~/work && cd ~/work
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
# Install the current operational pin recorded in CHANGELOG.md, never a branch.
uv pip install "cs-kernel @ git+https://github.com/malemi/cs-kernel@v0.5.2"
```

### 2. Create your company project

```bash
cs init
```

Answer the prompts (defaults are fine when unsure). It asks more than
this table shows — IMAP/SMTP host and port, timezone, cron schedule,
dedup/rate-limit knobs, and a few others — all with sensible defaults;
here are the ones you actually need to think about. For ACME you might
enter:

| Question | Example |
|---|---|
| Company name | `ACME Corp` |
| Display name | `ACME` |
| From name for emails | `ACME` |
| Short slug | `acme` → state lives under `~/.acme-cs/` |
| Operator email | `support@acme.example` |
| Engine URL + owner uid | from your mrcall-desktop setup |
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

### 4. Install the project pin and check the engine

```bash
cd acme-cs
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
cs whoami
```

If `whoami` shows you signed in as the right mailbox, the body is alive.

### 5. Open the TUI and work

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

Example: every 2 hours during business hours, weekdays (adjust to taste):

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
uv pip install "cs-kernel @ git+https://github.com/malemi/cs-kernel@v0.5.2"
```

See [CHANGELOG.md](CHANGELOG.md) for what each release changes.

---

## License & status

MIT. Public setup kit for operators that sit in front of **mrcall-desktop**.
You still need engine access, credentials, and human review in draft mode.

**Current release:** `v0.5.2` — see [CHANGELOG.md](CHANGELOG.md) for what it
changes and the re-collaudo it requires.
