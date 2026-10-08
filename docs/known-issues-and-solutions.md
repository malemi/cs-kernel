# Known Issues and Solutions

Issues with a confirmed fix, kept because the symptom is misleading enough that
the next person would re-diagnose it from scratch.

## 2026-10-06 — Self-owner history was mistaken for a colleague reply

**Local candidate fix; release pending.** A fan-out asking a colleague's own
mailbox for messages from that colleague reads their outbox to third parties as
reply evidence. It can falsely report prior company contact, permanently block
a colleague contact and generate one header FETCH per message.

**Operator decision, 2026-10-06 (original quotation).** “non capisco. se un
collega umano ha risposto, il thread diventa suo e il kernel lo deve mettere
come non più suo. metti nel brief che bisogna capire come fare, ovviamente
la cosa più normale sarebbe avere i task assegnati alle persone”. Only a real
answer is reply evidence; human thread ownership has a separately reviewed
[design](2026-10-07-human-thread-ownership-design.md). Explicit engine task
assignment is now implemented in the compatible release candidate; production
trust installation and clone acceptance remain release obligations. The
quotation records the original authority.

**Guard.** One shared self-owner filter skips normalized owner/address pairs
before opening IMAP. Single-address and bulk readers use it; merged scope names
read, unreadable and skipped mailboxes. Deliberate skips alone remain complete,
while unreadable evidence refuses applicable sends. Batched shared readers use
200-UID BODY.PEEK chunks and raise on non-OK SEARCH/FETCH. Dossier names unknown
correspondence and preserves independent sections instead of deriving a verdict
from an unread result. Fixtures preserve genuine exchanges and non-owner gate
ASKED sets/verdicts, and prove the original false YES becomes no.

**Explicitly excluded SEARCH-status holes.** `headers_for_addresses_on`,
`sent_body_match`, `inbound_recent` and `sent_recent` still have non-OK SEARCH
paths that can look like absence. This work does not fix their reconcile,
duplicate-check or sweep semantics. Live per-chunk latency, both maintained
clones' FULL acceptance and clone-owned direct wrapper callers remain release
obligations in the [local plan](execution-plans/2026-10-06-fanout-bounded-reads.md).
No tag, clone upgrade or live send is part of this candidate.

## A gated engine tool "hangs the engine" — it was our own client deadlocking

**Fixed in `v0.3.7`.**

**Symptom.** `cs chat --allow send_draft` composes and sends — the mail really
lands in Gmail Sent — and then never returns; the caller is killed at its own
timeout (SIGTERM/143). Same for every `update_memory` write-back. The natural
reading is "the engine hung after the tool ran", and that reading is wrong.

**Root cause, client-side, in `cs/rpc.py`.** `EngineClient._recv_loop` is the
only consumer of the WebSocket and it `await`ed the notification handler inline.
`chat()`'s handler answers a `chat.pending_approval` by calling
`await client.call("chat.approve", …)`, which ends in
`await asyncio.wait_for(fut, …)` — on a future only the receive loop can
resolve. The approve *request* goes out (the send completes before the await), so
the engine approves and the tool genuinely runs; every frame after that is
buffered and never dispatched. Sixty seconds later the inner `wait_for` raises
`TimeoutError` **inside** `_recv_loop`, the `except (ConnectionClosed,
CancelledError)` clause does not catch it, the receive task dies silently, and
the outer `chat.send` future is never resolved *nor failed*.

**Blast radius is wider than it looks.** The handler calls `chat.approve`
unconditionally, including `mode="deny"` — so `cs ask` and `cs draft-reply`,
both of which pass `allow_tools=set()`, hang identically whenever the model
merely *attempts* a gated tool. An empty allow-set is not protection here.

**Evidence it was never the engine.** Daemon journal, 2026-07-25: `chat.approve`
delivered 09:14:07, SMTP sent 09:14:09, `chat.send` **returned in 43.2 s** at
09:14:14 — and the client was killed at 09:16:00 having never consumed a result
delivered 106 s earlier. It also left the engine holding a zombie turn per
abandoned call (one ran 18m49s after the client was gone, burning tokens).

**Fix.** Never await the handler inline: spawn it with `asyncio.create_task` into
a tracked set, cancelled in `__aexit__`. Plus defence in depth — `_recv_loop`
now fails every pending future on ANY exception, not only on connection close,
so a dead reader surfaces as an error instead of an indefinite hang, and a failed
handler is reported on stderr rather than at garbage-collection time.

**How it was verified** (2026-07-27, live, against the support@mrcall.ai engine —
not a unit test): a turn containing **two** gated `update_memory` calls returned
in 50 s with both applied; pre-fix only the first ever landed. The daemon journal
shows `chat.send -> result` followed by a clean `CLOSE 1000` in both directions,
so no zombie turn is left behind. Reproduced first against a fake engine replaying
the live frame timing, where the approve path and the deny path both hang on
`v0.3.6` and both return on `v0.3.7`.

## `send_mail` opened a new thread for every reply

**Fixed across `v0.3.5` + `v0.3.6`.**

`build_mime()` set no `In-Reply-To`/`References`, so a reply to a customer arrived
as a fresh thread — invisible as an answer to them, and untraceable by any
"did we already answer this?" check that reads `References` back. Adding the
headers in `v0.3.5` was not enough: those two fields are absent from
`email.policy.default`'s header registry, so they fold as unstructured text and
any Message-ID too long for one 78-column line came out RFC2047 encoded-word
mangled. Measured on a live mailbox, 2 of 25 repliers had inbound Message-IDs
over 78 characters, so `v0.3.5` threading silently did nothing for them.
`v0.3.6` builds the message with `policy.default.clone(max_line_length=998)`;
verified in delivered mail on a 105-character id, reproduced verbatim.

Mapping the two headers to `MessageIDHeader` in a cloned `header_factory` was
tried and rejected: it fixes `In-Reply-To` and silently truncates a multi-id
`References` to the first id.
