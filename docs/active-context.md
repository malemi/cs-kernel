---
doc_baseline_commit: 819bc78
doc_baseline_date: 2026-07-27
---

# Active Context — cs-kernel

Volatile state for the shared kernel of the `<company>-cs` operators. The
durable reference is [`CLAUDE.md`](../CLAUDE.md) (the anti-fork charter, layout,
release rules) and [`CHANGELOG.md`](../CHANGELOG.md) (what each tag changed and
which clones must re-collaudo). This file tracks only what is *current*.

## Released and in use

**`v0.3.7` is the tip, and the two clones have diverged.** `mrcall-cs` runs it
(`requirements.txt`, `requirements.lock` and `manifest.toml` all `v0.3.7`,
installed, `cs whoami` verified). **`124-cs` is pinned to `v0.3.2`**, five
releases back, so it has none of the arc below — including the RPC deadlock fix,
which means any gated engine call from that clone still hangs.

The 2026-07-22..25 arc was driven entirely by one clone's need — the batch-2
Centralix migration in `mrcall-cs` — but every piece of it is rule-of-two
material that any clone answering a customer wants:

- **`v0.3.7` — the re-entrancy deadlock in `rpc.py`.** `EngineClient._recv_loop`
  is the only WebSocket consumer and it awaited the notification handler inline,
  while that handler answers `chat.pending_approval` by issuing `chat.approve` —
  a call whose response only the receive loop can deliver. The approve went out
  and the tool really ran; every later frame was buffered and never dispatched.
  The inner `wait_for` then raised `TimeoutError` *inside* the loop, uncaught, so
  the reader died silently and the caller blocked on a future nobody would
  resolve. Handlers now run as tracked tasks, the loop fails all pending futures
  on any exception, and `__aexit__` cancels them. This had been hanging `cs chat
  --allow send_draft`, every `update_memory` write-back, and even `cs ask` /
  `cs draft-reply` whenever the model merely *attempted* a gated tool — the
  handler calls `chat.approve` even to DENY, so the allow-set does not protect
  you. **Verified live 2026-07-27** against the support@mrcall.ai engine: a turn
  with two `update_memory` approvals returned in 50 s with both applied (pre-fix
  only the first landed), and the daemon journal shows `chat.send -> result`
  followed by a clean `CLOSE 1000` in both directions — no zombie turn left
  burning tokens.
- **`v0.3.6`** — two defects an adversarial review found in the new send path:
  `In-Reply-To`/`References` were RFC2047-mangled for any Message-ID longer than
  one 78-column line (fixed with `policy.default.clone(max_line_length=998)`;
  confirmed in delivered mail on a 105-char id), and a failed Sent-mirror could
  report an already-**delivered** mail as a failed send — which in a loop means
  the state write is skipped and the next run duplicates.
- **`v0.3.5`** — `in_reply_to`/`references` on the cs-SMTP send path (before it,
  every mail `send_mail.send()` produced opened a NEW thread, so operator acks
  never appeared as replies), and `gmail_archive.thread_with()`, a ground-truth
  conversation reader over IMAP returning decoded bodies plus attachment
  filenames. It skips Gmail `\Draft`-labelled messages: the IMAP `\Draft` flag is
  unset on them so `UNDRAFT` does not exclude them, and a queued draft is a
  conversation that never happened.
- **`v0.3.4`** — `campaign send-first` dropped its whole-Sent-archive dedup: a
  curated first notice must not skip a target merely because they have a recent
  support thread. Idempotency is the contact `state`.

## Failing gate — `tests/run.sh` gate 1 is RED

`bash tests/run.sh` exits 1. Gates 2–10 pass; **gate 1 (zero company literals in
`cs/`) fails**:

```
cs/templates/project/CLAUDE.md.j2:52: On `desktop.mrcall.ai` a dedicated user `mrcalld` runs one engine per profile
```

This is a real charter violation, not a false positive. Charter rule 1 allows
platform *names* that denote shared infrastructure (the mrcall-desktop engine,
the `mrcall.search_businesses` RPC) but explicitly excludes company
*hosts/domains/values*, which belong in the manifest — and `desktop.mrcall.ai`
plus the `mrcalld` daemon user and the `/run/mrcalld/<uid>.sock` path are
MrCall's own infrastructure. The paragraph around them is otherwise correctly
parameterised (`{{ engine_ws_url }}`, `{{ email_address }}`,
`{{ engine_owner_uid }}`, `{{ company_slug }}`), so this is an oversight, not a
design decision.

**It is pre-existing**, introduced with the template itself in `v0.3.0`
(`4a17dd3`) and red at every tag since — including the `v0.3.2` re-derivation
that was supposed to fix the hidden templates. Consequence today: a clone stamped
for another company renders MrCall's host and daemon user into its own
`CLAUDE.md`. `124-cs` carries it.

Fixing it means new manifest fields (engine host, daemon user, socket path) plus
a re-render, i.e. a MINOR bump and a re-collaudo of both clones — deliberately
not done inside a documentation pass.

## Immediate next steps

- **Fix gate 1** as above, or state in the charter why a deployment host is
  exempt. Leaving a permanently-red gate trains everyone to ignore the suite,
  which is worse than either outcome.
- **Bring `124-cs` from `v0.3.2` to `v0.3.7`.** It is five releases behind and is
  missing the RPC deadlock fix, so any gated engine call from that clone hangs.
  Full re-collaudo: the arc touches send paths and `gmail_archive`.
- **Promote the batch-2 loop's reusable parts.** `mrcall-cs` holds a per-business
  schedule store with an flock'd atomic read-modify-write and a backstop clamp
  (`schedule.py`), a deterministic prod migrator with read-only preflight and a
  guarded `UPDATE … RETURNING` (`migrator.py`), and an IMAP attachment reader
  (`ext/attachments.py` — the engine indexes filenames but stores no bytes and
  exposes no fetch RPC). All three are kernel candidates once that campaign
  settles; the attachment reader is the clearest, since every clone's
  `/find-document` wants it.
