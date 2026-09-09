---
status: planned
---

# Minted account sessions — execution plan

Brief: [`../briefs/2026-09-09-minted-account-sessions.md`](../briefs/2026-09-09-minted-account-sessions.md),
approved at its gate on 2026-09-09 (fourth pass). Criteria are cited by the brief's own
wording and never restated here.

## Guard order — decided, and load-bearing

Registry → email → tty → confirmation → mint → the existing store-and-prove path.

The registry and email refusals come FIRST so both stay observable headlessly and can
live in `tests/run.sh`. A tty-first order would make them unreachable without a
terminal and push every refusal into hand-run collaudo, which is how a guard stops
being tested. Nothing is weakened by the order: a headless caller with a valid uid
still meets the tty refusal one step later.

## Milestones

### M1 — The mint source, no CLI surface

Own function: uid in, a synthesized descriptor out, handled errors otherwise. Registry
refusal (`settings.account_map`), `resolve_email` with a refusal on `None`, custom token
signed from `settings.firebase_sa_path`, exchange at `accounts:signInWithCustomToken`
with the clone's own `firebase_web_api_key`. Error handling mirrors
`cs/auth.py::_exchange` — one handled line per failure, never a traceback.

Verification: the registry and no-email refusals as gates, using the repo's
env-driven skipped-when-unset pattern (`tests/run.sh:15-17`, `:297`) so a machine
without a key skips rather than fails. The successful mint is proven live by the
operator; it already was, once, during the study.

### M2 — The CLI surface

`--mint` on `login` and on `cs --account <name> login`. Guards in the order above. The
tty check reads `sys.stdin.isatty()` before any `input()`. Confirmation defaults to no,
echoes account name, uid and resolved email. Refusal text names `--mint` and the
registry; it never tells the operator to pick a descriptor that does not exist
(`cs/login.py:184-189`, `:196-202` say that today). `EOFError` is handled in the mint
branch, which carries none today (`:294-329`).

Depends on M1.

Verification: a gate asserting the non-tty refusal exits non-zero **under a timeout well
below the wrapper's**, so a guard that waits on input instead of checking the tty fails
here rather than in production. Refusal-text assertions for the `--mint`-naming rule.

### M3 — Reconciling the surfaces this falsifies

Three edits, no logic:

1. `templates/project/docs/ARCHITECTURE.md.j2:90-91` — the service-account key stops
   being described as outside the auth chain.
2. `templates/project/bin/cs_operator_cron.sh.j2:160` — add `</dev/null` to the
   `claude -p` call. The wrapper redirects stdout and stderr and leaves stdin alone, so
   a hand-run tick can hand a Bash child the operator's own terminal: a prompt would be
   invisible in the log while `input()` ate the operator's keystrokes. **Blast radius
   beyond this work**: it closes that seam for every prompting verb under the tick, not
   only for `--mint`. That is the intent, and it is why it is called out rather than
   slipped in.
3. CHANGELOG entry: MINOR, **FULL re-test tier on both clones**, naming the posture
   change (the key becomes an authentication credential) as the reason.

Depends on M2.

### M4 — Release and the first consumer

Tag per [`../release-procedure.md`](../release-procedure.md) — followed, not
reconstructed. Re-pin both clones, FULL collaudo on both. Then the clone-side work this
was built for: add Ivan and Riccardo to 124's `CS_ACCOUNTS`, mint their sessions, prove
`cs --account <name> thread <address> --full` returns bodies, and retire their entries
from `CS_READ_MAILBOXES` / `CS_READ_MAILBOX_PASSWORDS`.

Depends on M3. **Requires the operator's explicit ok**: the tag, any push, and the live
edit of a running clone's environment are all his, not mine.

## Risk and rollback

- A minted session is one 0600 file at a known per-account path. Rollback is deleting
  it; nothing else persists.
- The `</dev/null` edit is the only change with reach outside this feature. If a tick
  verb turns out to depend on inherited stdin, the symptom is an immediate EOF rather
  than a hang, and reverting is one token.
- Retiring 124's declared-mailbox passwords is the last step for a reason: until the
  minted sessions are proven to answer, those passwords are the only way the fan-out
  reaches Ivan's and Riccardo's mailboxes. Removing them earlier would trade a working
  path for an unproven one.

## Carried notes

- The tick's allow list holds 102 `Bash(...)` entries and no interpreter, so today it
  can run neither Python nor `cs login --mint`. Gate 17's allow-purity check would not
  object if a clone ever added `Bash(cs login:*)` (`tests/run.sh:486-490` keys only on
  chat/send-draft shapes). Worth a harness-backlog line, not work here.
- `isatty()` refuses the operator's own agent session and `ssh` without `-t`. That makes
  the refusal text load-bearing: it must say to run the command in a terminal.
