# A ready-made customer-service operator

cs-kernel is an agentic platform that runs your customer service.
It reads your inbox(es), whatsapp, or any other channel, answers in
your company's voice, runs periodic loops, and manages campaigns end
to end — with a memory of every relationship that no human team keeps.

What it actually does is adding a powerful harness on top of **[mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop)**, leveraging also on external platforms like Claude Code or Open Code. 

One real requirement: you must be able to use the terminal. CS is terminal-based. 

### What a morning looks like

While you slept, the operator worked: it triaged everything that came
in, wrote every reply — in your company's voice, with each
correspondent's full history in mind — and advanced the campaigns that
were due. You open Claude Code (or OpenCode) in your project folder,
and the session in front of you is not a generic chatbot: it **is**
your customer service. It holds every relationship, every open task,
every promise and its date — the total recall no human operator
sustains across hundreds of threads.

```text
> what's new today?

support@acme.com ✓ · overnight: 11 mails handled · 9 replies written · 2 campaigns advanced

Ready to go — in Gmail → Drafts:
  studio.bianchi@example.it    Re: number unreachable after the migration
  academy@example.com          Re: calendar integration
  … 7 more

Brought to you (1):
  pms@example.com — third report of the same bug, and on Aug 11 we
  promised a fix. A template apology would make this worse: they need
  a date, or a call. Say the word and the reply goes out.

> the fix ships Friday — write it straight, and offer them a call

Done: in the thread, in your voice. Anything else from the list?
```

That is the product: **everything handled** — and the one case where
another apology would have burned the customer, it understood the
situation and brought it to you with a recommendation. On day one every
reply waits in Gmail Drafts for your send: the operator's judgment is on
trial, not in charge. When what you read keeps matching what you would
have written, open the autonomy dial and it sends on its own — the dial,
and the kill-switch, stay in your hand.

---

## What you get

A complete customer-service operator, not an autocomplete:

1. **Triage and replies** for your whole inbox, in your company's voice,
   grounded in each correspondent's history — it answers what it can
   defend and brings you the rest with a recommendation
2. **Campaigns and follow-ups** advanced on schedule, with hard dedup
   and rate caps
3. **Memory that compounds**: every mail synced and every session worked
   makes the next answer better — no retraining, no CRM data entry
4. A **cron wrapper** so all of the above runs unattended, plus the
   autonomy dial: draft-first on day one, autonomous send when you say so

---

## Prerequisites

What you need:

- **Python 3.11+** and **[uv](https://github.com/astral-sh/uv)**
- **Claude Code** or **OpenCode** (the TUI/session you work in)
- A **mrcall-desktop** engine profile
- Email IMAP for the operator mailbox (supported Google Mail at the moment)

---

## Setup example: ACME

Imagine your operator address is `support@acme.example`.

### 1. Install [mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop) and sign in

**[mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop)** is a separate desktop app: it holds the mailbox sync,
the memory and the task list, and it fronts the **engine** — the daemon
that does the mail work.

Launch MrCall Desktop, sign in with the Google account for your support
mailbox, and click **Activate** in the sidebar: that provisions your
engine, which then runs continuously — your operator does not stop when
your laptop sleeps. Run `cs` on a machine where you have signed in to
the app (that sign-in is what the next step reads its configuration
from).

### 2. Create your company project

Copy-paste this whole block into the terminal. Nothing to install first:
it fetches the latest release and runs the setup wizard directly.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # once, if uv is missing
# Resolve the newest release tag and run the wizard from it — always a tag, never a branch.
TAG=$(git ls-remote --tags --refs https://github.com/malemi/cs-kernel 'v*' | sed 's|.*refs/tags/||' | sort -V | tail -1)
uvx --from "cs-kernel @ git+https://github.com/malemi/cs-kernel@${TAG}" cs init
```

The `cs init` wizard prompts various questions to setup your agentic customer service
platform. It should not be difficult, as all technical questions
are prefilled.

Remember: if the wizard asks for the **engine WS URL** and **engine owner uid**
and no value is prefilled, it means you haven't signed in to mrcall-desktop. Do it!

Here is what to expect for ACME:

| Question | Example |
|---|---|
| Company name | `ACME Corp` |
| Display name | `ACME` |
| From name for emails | `ACME` |
| Short slug | names your project (`acme` → `acme-cs/`); the wizard suggests one, Enter accepts |
| Operator email | `support@acme.example` (required) |
| Engine URL + owner uid | prefilled from Step 1's sign-in; if asked, redo Step 1 and re-run |
| Default account | `support` + that same uid |
| CRM / producer / SMS / Drive | leave defaults unless you know you need them |
| Mailbox app password | You need your gmail [app password](https://support.google.com/mail/answer/185833?hl=en) |

When you confirm, you get a folder **`acme-cs/`**.

If you are interested, `cs init` wrote all the info into `~/.acme-cs/.env`.

One last prompt: `Install the project now (creates acme-cs/.venv and
installs the pinned kernel)? [y/N]`. Say **y** and step 3 below is
already done for you — skip straight to step 4.

### 3. Install the project pin (only if you said no above)

Your project has its own private copy of the tool, pinned in
`requirements.txt` — upgrades happen when *you* decide, per project.
Do this only if you skipped the wizard's own install prompt:

```bash
cd acme-cs
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 4. Sign in

Either way you got here, this shell isn't in the project yet:

```bash
cd acme-cs
source .venv/bin/activate          # Windows: .venv\Scripts\activate
cs login
```

It picks up Step 1's sign-in (`selected: email (uid)`), stores a session
under `~/.acme-cs/` and proves it with one live call. When something is
off it tells you exactly what to do — paste a `FIREBASE_WEB_API_KEY` line
into `~/.acme-cs/.env`, or go back to Step 1 — do that and re-run it.

### 5. Check the engine

```bash
cs whoami
```

One real call through the engine. Expected:

```text
signed in as support@acme.example
uid: AbC123dEf456gHi789jKl012mNo3
session valid until 2026-08-21 12:54 CEST (auto-renews)
```

`not signed in — run cs login` → redo step 4. Anything else:
Troubleshooting below. (Raw JSON, if you want it: `cs whoami --json`.)

### 6. Open the TUI and work

Still inside `acme-cs/` with the venv active:

```bash
# pick one:
claude
# or
opencode
```

First thing to type: **`/cs-review`** — the one review bootstrap, zero
side effects: what the operator prepared for you (drafts waiting in
Gmail Drafts, open tasks, campaign flags) and, when a lead source is
configured, the day's outreach candidates with one dossier each. Or
just talk:

- *"What's still open in support mail?"* → triage review
- *"Load customer Northwind"* → customer skill (docs + engine memory)
- *"Draft a reply to …"* → grounded draft; **nothing is sent** until you
  review and approve it

Lost at any point? **`/cs-help`** shows the whole map. The skills are
the product surface; the CLI is plumbing the AI (and you, if you want)
can call — map in [The `cs` CLI](#the-cs-cli) under Reference.

---

## Day-to-day mental model

Three pieces:

1. **The engine** — the always-on daemon behind mrcall-desktop. It holds
   the synced mailbox, the relationship memory, the tasks, and a writing
   voice trained on your own sent mail. It keeps working when your
   laptop doesn't.
2. **Your session** — Claude Code / OpenCode opened in `acme-cs/`, with
   the pre-built skills (`/cs-review`, `/cs-account`, …) that read and
   drive the engine. This is where you talk to your customer service —
   and where you build on it.
3. **Your automations** — the cron ticks *you* choose to run: the
   ready-made operator (type `/cs-cron` in a session — triage +
   campaigns, unattended) and any recurring job you invent.

Pieces 1 and 2 come ready from this kit; piece 3 is yours — and piece 2
is how you build it, with a workflow command for each move: `/cs-cron`
installs, pauses or removes the operator tick from inside the session;
`/cs-campaign` designs a new campaign and produces the whole automation —
the **pack** (`campaigns/<name>/` — copy, timing, playbook), wired so
the regular tick advances it. That
is how we run our own migration campaigns: designed in a session one
afternoon, then ticking on their own schedule for weeks — and months
later "have we ever done something like this?" is answered by
`cs campaign packs`, and re-running one is copy-and-edit.

| You care about | What happens |
|---|---|
| Customer context | Skill loads dossier files + **engine memory** |
| Memory over time | Engine keeps relationships as mail is synced and you work |
| Replies | Written end-to-end; land in Drafts until you open the autonomy dial |
| Campaigns | Templates/packs advanced as drafts unless you opt into send mode |
| “Stop everything” | Create pause file: `touch ~/.acme-cs/CS_PAUSE` |

### How memory gets rich

You don’t “train a model” by hand. You:

- work interactively (customers, drafts, questions)  
- let mrcall-desktop **sync the mailbox** into entities/memory/tasks  
- optionally write durable facts the AI should keep (when you ask it to)  

Next sessions — interactive or cron — start from that memory instead of a blank page.

---

## Troubleshooting

- **`not signed in — run cs login`** — the exact line every engine-backed
  verb prints when no session is stored yet, or the stored one does not
  match this clone's configured uid. Run `cs login` (step 4 above).
- **Connection refused / the engine seems unreachable** — the daemon is
  not answering at the configured WebSocket URL. During `cs login` this
  is caught and printed as one line (`cs login: stored the session, but
  the proof call to '<url>' failed: …`); on other verbs (`cs whoami` and
  friends) it currently surfaces as a raw Python traceback ending in
  something like `ConnectionRefusedError: [Errno 111] Connect call
  failed…`. Either way, it means the mrcall-desktop app is not running,
  or it is running on a **different machine** than the one you're typing
  `cs` on — `cs` only ever talks to the daemon on the machine it runs on
  (see Step 1).
- **`cs login: no profile descriptor found under ~/.zylch/profiles/ —
  sign in to the mrcall-desktop app first (it writes the descriptor at
  sign-in)`** — you have not signed in to mrcall-desktop on this machine
  yet, or your build predates the v0.1.29 descriptor writer (Step 1).
  Sign in (or update the app), then re-run `cs login`.
- **Nothing shows up in Gmail Drafts after a tick** — first check
  `~/.<slug>-cs/CS_PAUSE`: if that file exists, the kill-switch is on and
  every automated tick is a deliberate no-op (`rm` it to resume). If it
  is absent, read the tail of `~/.<slug>-cs/cs_operator.log` for what the
  last tick actually did.

---

You’re set up. Everything from here on is reference material for when you
need it, not more onboarding.

---

## Reference

### The `cs` CLI

`cs --help` is the reference: one line per verb there, details under
`cs <verb> --help`. The map — **setup**: `init`, `update`, `login`,
`accounts`, `cron`; **read-only**: `review`, `plan`, `dossier`, `ask`,
`whoami`, `thread`, `contacted`, `unanswered`, `tasks`, `business`,
`drive`, `llm`; **gated writing**: `draft-reply` / `chat` (drafts only,
never send), `campaign` (Sent-dedup, rate cap, pause file), `tasks
create`/`close`; **plumbing**: `rpc`, `project`.

### The kernel's own model calls

Three different things spend model tokens, and only the middle one is the
engine:

| Who | On what | Paid by |
|---|---|---|
| Your session (Claude Code / OpenCode) | your conversation with the project | your own plan |
| The **engine** (mrcall-desktop) | replies and campaign copy — memory + trained voice | the engine's account |
| The **`cs` kernel itself** | the send guard's register judgment; classification a skill routes directly | a provider key in `~/.<slug>-cs/.env` |

That third one is small but real. Set `OPENROUTER_API_KEY` (or
`ANTHROPIC_API_KEY`) in your `.env` and the kernel talks straight to the
provider; leave it unset and those checks degrade to deterministic rules —
the guard still refuses, it just judges less. `cs llm` prints what your
configuration resolves to; `cs llm test` makes one real call.

### Optional: run it automatically (cron)

This is where the operator takes over the routine entirely: on a
schedule, unattended, it triages inbound mail and advances campaigns —
the same work as your sessions, without you in the room. Out of the box
each tick lands its replies in Gmail Drafts (draft mode); flipping to
autonomous send is one deliberate change of mode + permissions, once
the drafts have earned it.

#### What’s already in the project

After `cs init`, you have:

- `bin/cs_operator_cron.sh` — one headless tick  
- skill `/cs-operator` — `/cs-triage-mail` + `/cs-campaign-tick`, then stop  
- kill-switch: `touch ~/.acme-cs/CS_PAUSE` (any slug: `~/.<slug>-cs/CS_PAUSE`)  
- log: `~/.<slug>-cs/cs_operator.log`  

The wrapper re-denies send surfaces so a cron run cannot “accidentally” send.

You need the **Claude Code CLI** available to cron (default path
`~/.local/bin/claude`, overridable with `CLAUDE_BIN`).

#### Try one tick by hand

```bash
cd acme-cs
source .venv/bin/activate
./bin/cs_operator_cron.sh
# then inspect Gmail Drafts / run your review skill in the TUI
```

#### Install a schedule (when you’re ready)

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

Autonomous send is the destination; day one is draft mode. Opening that
dial is one deliberate step (config + permissions) — yours to take, and
yours to close again.

### Upgrading later

One command:

```bash
cd acme-cs
source .venv/bin/activate
cs update
```

It looks at the pinned origin first; when a newer release exists it asks —
`Found new tag (vX.Y.Z). Update? [y/N]` — and on **y** it re-pins,
installs, and re-runs itself on the new kernel before refreshing the
stamped files (your edits are kept, except the two security-critical
files — `settings.json` and the cron wrapper — which are applied with
your version saved as `*.local-bak`). Anything but an explicit **y**
changes nothing: a pin that updates itself is not a pin. Offline, the
check is skipped in one line and the refresh proceeds.

That is the whole upgrade — three things happen behind that one **y**:
the pin in `requirements.txt` moves, the new kernel is installed into
your `.venv`, and the stamped files are re-rendered from it.

**`--pin` is the escape hatch, not the normal path.** `cs update` only
ever offers the *newest* tag, so name a version explicitly when you want
a different one — above all to **go back**:

```bash
cs update --pin v0.9.1      # roll back (or jump to a specific tag)
uv pip install -r requirements.txt   # --pin rewrites the pin; it never installs
cs update                   # re-stamp the files from that kernel
```

And to look before leaping, writing nothing at all:

```bash
cs update --check           # installed vs latest, plus the re-collaudo tier
```

Every kernel upgrade owes a re-collaudo per the new tag's CHANGELOG
entry — the prompt names the tier when the entry declares one. Then
reopen `claude` / `opencode` in that folder.

### Safety (defaults)

- **Draft first** — automated paths are not free-fire send.  
- No cold outreach without a proper contact check.  
- Contact history uses **Gmail’s own Sent mail** as ground truth.  
- `~/.<your-slug>-cs/CS_PAUSE` stops automated ticks immediately.

Turning on autonomous send is a deliberate later choice, not the default.

### Versioning

Install a **version tag**, not a floating branch. The snippet resolves the
newest release tag at install time, so it never goes stale:

```bash
TAG=$(git ls-remote --tags --refs https://github.com/malemi/cs-kernel 'v*' | sed 's|.*refs/tags/||' | sort -V | tail -1)
uv pip install "cs-kernel @ git+https://github.com/malemi/cs-kernel@${TAG}"
```

See [CHANGELOG.md](CHANGELOG.md) for what each release changes.

### License & status

MIT. Public setup kit for operators that sit in front of **mrcall-desktop**.
You still need engine access, credentials, and human review in draft mode.

The install snippets above resolve the newest release tag at run time. See
[CHANGELOG.md](CHANGELOG.md) for what each release changes, the current
operational pin of the live clones, and the re-collaudo each release
requires.
