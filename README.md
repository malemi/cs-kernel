# A ready-made customer-service operator

cs-kernel is an agentic platform for managing your customer service 
workflow. It reads your inbox(es), whatsapp, or any other channel, and it 
prepares replies, setup loops for periodic tasks, organizes campaigns.

What it actually does is adding a powerful harness on top of **[mrcall-desktop](https://github.com/hahnbanach/mrcall-desktop)**, leveraging also on external platforms like Claude Code or Open Code. 

One real requirement: you must be able to use the terminal. CS is terminal-based. 

### What a morning looks like

You open Claude Code (or OpenCode) in your project folder. This is not a
generic chatbot: the session in front of you **knows your customer
service** — every correspondent's history, the open tasks, the campaigns,
what was promised and when.

```text
> what’s new today? 

support@acme.com ✓ · 3 drafts ready · 2 open tasks · 1 escalation

DRAFTS — waiting in Gmail → Drafts. You read, you send.
  studio.bianchi@example.it    Re: number unreachable after the migration
  academy@example.com          Re: calendar integration

ESCALATION
  pms@example.com — angry customer, third report of the same bug.
  No draft written: this needs a decision from you, not a reply.

> what's the story with pms?

Three reports of the same missed-call bug: Aug 2, Aug 11, yesterday —
tone degrading, and on Aug 11 we promised a fix. There's an open task
from that promise. I wouldn't send an apology template: they need a
date, or a call.

> ok — draft an honest reply: the fix ships Friday, and offer them a call

Done. The draft is in the thread, in your voice, in Gmail Drafts —
subject "Re: missed calls not logged". You read, you send.
```

The escalation block is the point. The operator drafts what it can defend
and **stops** where it cannot — an escalation is the system refusing to
answer, not a failure. And nothing above was sent: drafts sit in Gmail
until you send them.

---

## What you get

1. A small project folder (e.g. `acme-cs/`) configured for **your** company  
2. Skills the AI can run: load a customer, triage mail, advance campaigns, …  
3. A **cron wrapper** so the same operator can tick unattended  

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
| Short slug | type **`acme`** explicitly — the wizard's own default for "ACME Corp" is `acme-corp`, which would put your state under `~/.acme-corp-cs/` instead and silently break every `~/.acme-cs/...` command below |
| Operator email | `support@acme.example` (required) |
| Engine URL + owner uid | prefilled from Step 1's sign-in; if asked, redo Step 1 and re-run |
| Default account | `support` + that same uid |
| CRM / producer / SMS / Drive | leave defaults unless you know you need them |
| Destination folder | `acme-cs` |
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

```json
{
  "signed_in": true,
  "uid": "AbC123dEf456gHi789jKl012mNo3",
  "email": "support@acme.example",
  "expires_at_ms": 1787150583000
}
```

`not signed in — run cs login` → redo step 4. Anything else:
Troubleshooting below.

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

When interactive use feels solid and drafts look right, you can let the
operator prepare work on a schedule. **Default remains draft-only**: the tick
triages inbound mail and advances campaigns into **drafts for your review**;
it does not freely email customers unless you later change mode and permissions
on purpose.

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

Sending without review is a **later, deliberate** step (config + permissions),
not what you get on day one.

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
