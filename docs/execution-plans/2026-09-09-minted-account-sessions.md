---
status: active
---

# Minted account sessions — execution plan

Brief: [`../briefs/2026-09-09-minted-account-sessions.md`](../briefs/2026-09-09-minted-account-sessions.md),
approved at its gate on 2026-09-09 (fourth pass). Criteria are cited by the brief's own
wording and never restated here.

## Guard order — decided, and load-bearing

Registry → tty → email → confirmation → mint → the existing store-and-prove path.

Every refusal that can be reached without a credential comes before every refusal that
cannot, so each one is observable headlessly and lives in `tests/run.sh`. The tty check
sits second, not last, precisely so it needs no key, no network and no email-bearing
uid to exercise — it is the guard that actually protects, and a guard reachable only
through a live Firebase round trip is a guard nobody runs. The brief requires only that
the tty be checked before any `input()`; this order satisfies it. Email resolution comes
after, because it is the first step that spends a credential.

## Status (2026-09-10)

- **M1 done** — `6fcad5f`. Mint source + cache-retirement fix. Integration review APPROVED.
- **M2 done** — `c2a08df`. `--mint` on both spellings, guard chain, end-to-end proof on
  the live host. Integration review found one escape (resolver exceptions leaking as
  tracebacks); fixed, gated (`19b` resolver-error wrap), re-verified.
- **M3 done** — `70b6930`. The two stamped surfaces reconciled; rendered wrapper is valid
  bash. Suite green (57 gates).
- **M4 release authorized 2026-09-10; consumer migration remains pending** — v0.43.0, MINOR, **FULL tier** (auth boundary + permission
  surface). CHANGELOG entry drafted (scratchpad). The CTO authorized the tag, push and live-clone upgrades;
  the coordinated rollout is tracked in `2026-09-10-desktop-workspace-setup.md`. Then the clone-side work: Ivan and Riccardo into 124's `CS_ACCOUNTS`,
  mint their sessions, prove `--full` returns bodies, retire the app passwords
  (password entry before mailbox entry — the reverse fails every verb at config load).

## Milestones

### M1 — The mint source, no CLI surface

Own function: uid in, a synthesized descriptor out, handled errors otherwise. Registry
refusal (`settings.account_map`), `resolve_email` with a refusal on `None`, custom token
signed from `settings.firebase_sa_path`, exchange at `accounts:signInWithCustomToken`
with the clone's own `firebase_web_api_key`. Error handling mirrors
`cs/auth.py::_exchange` — one handled line per failure, never a traceback.

**Storing a session invalidates the cached id token.** `auth._write_refresh`
(`cs/auth.py:101-116`) writes the refresh token and never touches the cache, while
`get_id_token` returns the cache first (`:188-193`). So a new session leaves the old id
token in force until it expires — which means `cs login`'s proof call has always been
able to succeed on the session it just replaced. This is a defect in the surface being
extended, it is fixed here, and fixing it is what makes M2's end-to-end proof mean
anything: without it the proof exercises the previous token and passes vacuously.

The email resolver is an injectable seam, not a hard import, so the no-email refusal is
a pure unit test needing neither a key nor an email-less Firebase user to exist.

Verification — **no env-skipped gate may be a milestone's only proof.** A skipped gate
prints `OK` and is indistinguishable from a passing one (measured: `test_golden_pack`
with its env unset exits 0 and `tests/run.sh:298` reports `OK`). So M1 lands with two
gates that always run: the registry refusal, which the guard order puts before any
credential use, and the no-email refusal through the injected resolver. Each asserts the
REASON it refused, never merely a non-zero exit — every failure of this verb exits
non-zero, including the feature not being wired at all.

### M2 — The CLI surface

`--mint` on `login` and on `cs --account <name> login`. Guards in the order above. The
tty check reads `sys.stdin.isatty()` before any `input()`. Confirmation defaults to no,
echoes account name, uid and resolved email. Refusal text names `--mint` and the
registry; it never tells the operator to pick a descriptor that does not exist
(`cs/login.py:184-189`, `:196-202` say that today). `EOFError` is handled in the mint
branch, which carries none today (`:294-329`).

Depends on M1.

**`cmd_login_stub` rebuilds its argv from `--descriptor` alone** (`cs/cli.py:1683-1690`).
A `--mint` declared on the parser but not forwarded there is silently dropped, and the
verb then behaves exactly as it does today. Forwarding it is part of this milestone, and
the gate below is written so that failing to forward it fails the gate.

Verification: a gate asserting the non-tty refusal names its reason and runs **under a
timeout well below the wrapper's**, so a guard that waits on input rather than checking
the tty fails here instead of in production; and asserting the reason rather than the
exit code is what makes a dropped flag visible, since an unrecognised `--mint` also
exits non-zero. Refusal-text assertions for the `--mint`-naming rule.

**End-to-end proof, owned here and by nothing else**: mint a session for a SECONDARY
uid and prove `account.who_am_i` against THAT profile's own daemon. The study probe
minted against the clone's own identity with tokens discarded — it proves the signature
and the exchange, never that another profile's daemon accepts a minted token.

Two conditions make this proof real rather than decorative:

- It depends on M1's cache invalidation. Without it the proof call returns the cached id
  token and succeeds without ever exchanging the minted one.
- The only registered secondary uid on this host is 124's `mario` account, and it holds
  a LIVE session the cross-mailbox fan-out uses. Both of its token files are copied
  aside before the run and restored after — preserving 0600, which nothing re-checks —
  so the proof neither destroys a working
  session nor depends on re-minting to put one back. The brief's own wording — an
  account with *no stored session* — describes Ivan and Riccardo, who are not in
  `CS_ACCOUNTS` yet; that exact case is proven in M4, on the registry the operator
  edits there. M2 proves the mechanism, M4 proves the intended case.

Until both run, the feature is unproven whatever the gates say.

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

Tag and upgrade **per [`../release-procedure.md`](../release-procedure.md), executed
from that file rather than from this one**. This plan deliberately lists no step order:
an earlier draft paraphrased the procedure and dropped four of its steps
(`requirements.lock` regeneration, the per-clone version sweep, `cs whoami`, and the
kernel CHANGELOG operational-pin marker written after both clones are up). Paraphrase is
how those steps go missing. Then the clone-side work this was built for: add Ivan and Riccardo to 124's `CS_ACCOUNTS`, mint their sessions, prove
`cs --account <name> thread <address> --full` returns bodies, and retire their entries
from `CS_READ_MAILBOXES` / `CS_READ_MAILBOX_PASSWORDS`.

**Retirement order, and it is not a preference.** The password entry goes first, the
mailbox entry second. `parse_read_credentials` (`cs/config.py:198-206`) refuses a
declared mailbox whose credential is missing, and that refusal happens at config load —
so dropping `CS_READ_MAILBOXES` first leaves a password with no mailbox and fails every
verb, `--help` included, until the second edit lands. On a live clone with a cron that
fires every two hours, that window is an outage.

A session-less window during the edit is already handled, not a risk: `mailboxes`
reports such an account `unreadable` with an actionable reason and the fan-out continues
per account rather than failing.

Depends on M3. **Requires the operator's explicit ok**: the tag, any push, and the live
edit of a running clone's environment are all his, not mine.

## Risk and rollback

- A minted session persists as **two** 0600 files, not one: the refresh token and the
  id-token cache (`cs/auth.py::_write_cache`). `get_id_token` reads the cache BEFORE the
  refresh file (`:188-193`), so deleting only the refresh token leaves a usable session
  until the cached token expires. Rollback deletes both, and the plan says so because
  the obvious half-rollback looks complete and is not.
- Restoring a session the proof run displaced is a file restore from the copies taken
  before it, never a re-mint: a re-mint would prove the thing under test rather than
  return the account to where it was.
- The `</dev/null` edit is the only change with reach outside this feature. If a tick
  verb turns out to depend on inherited stdin, the symptom is an immediate EOF rather
  than a hang, and reverting is one token.
- Retiring 124's declared-mailbox passwords is the last step for a reason: until the
  minted sessions are proven to answer, those passwords are the only way the fan-out
  reaches Ivan's and Riccardo's mailboxes. Removing them earlier would trade a working
  path for an unproven one.

## Carried notes

- **A skipped gate is indistinguishable from a passing one** — `tests/run.sh` prints
  `OK` on exit 0 whether the gate ran or opted out. That is a harness defect wider than
  this work; it belongs in `docs/harness-backlog.md`, not in this milestone.

- The tick's allow list holds 102 `Bash(...)` entries and no interpreter, so today it
  can run neither Python nor `cs login --mint`. Gate 17's allow-purity check would not
  object if a clone ever added `Bash(cs login:*)` (`tests/run.sh:486-490` keys only on
  chat/send-draft shapes). Worth a harness-backlog line, not work here.
- `isatty()` refuses the operator's own agent session and `ssh` without `-t`. That makes
  the refusal text load-bearing: it must say to run the command in a terminal.
