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
the memory and the task list, and it runs a local engine that everything below actually talks to.

`cs` and MrCall Desktop must run on the same machine. 

Launch MrCall Desktop and sign in with the Google account for your support mailbox.

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

### 3. Install the project pin

Your project has its own private copy of the tool, pinned in
`requirements.txt` — upgrades happen when *you* decide, per project:

```bash
cd acme-cs
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 4. Sign in

```bash
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

The skills are the product surface; the CLI is plumbing the AI (and you,
if you want) can call — map in [The `cs` CLI](#the-cs-cli) under Reference.

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

First find out whether there is anything to upgrade TO — `cs update --check`
reads the kernel origin already pinned in your `requirements.txt`, checks it
for newer tags, and prints installed vs. latest (plus that tag's re-collaudo
tier, when it can determine one). It writes nothing:

```bash
cd acme-cs
source .venv/bin/activate
cs update --check
```

If a newer tag is what you want, re-pin explicitly — this never happens on
its own; a pin that updates itself is not a pin:

```bash
cs update --pin vX.Y.Z      # the tag --check just showed you; rewrites ONLY
                            # the pin line and prints the before/after
```

Then install it and refresh the stamped templates:

```bash
uv pip install -r requirements.txt
cs update    # refreshes skills/templates; keeps your edits, except the two
             # security-critical files (settings.json, cron wrapper): those are
             # applied, with your version saved next to them as *.local-bak
```

Every kernel upgrade owes a re-collaudo per the new tag's CHANGELOG entry —
`cs update --check`'s own output says so.

Then reopen `claude` / `opencode` in that folder.

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
