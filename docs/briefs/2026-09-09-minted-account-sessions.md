# Minted account sessions — brief

## Intent

Let a clone open a session for a colleague's engine profile without a human signing
into that profile. Today wiring a second account requires a `cs-descriptor.json` that
only an interactive desktop sign-in writes; the profiles a clone actually needs are
provisioned headless and have no descriptor, so the accounts registry cannot grow.

## What already exists — the surfaces this extends

Named first, because the work is one new SOURCE feeding an existing pipeline.

- `cs/login.py` resolves a descriptor, refuses an identity conflict (`:360-365`),
  stores the refresh token (`auth._write_refresh`, `:368`), prints config-drift
  advisories without mutating operator files (`:371-382`), then proves the session with
  a live `account.who_am_i` (`:385`). Everything after the descriptor is
  source-agnostic.
- `cs/auth.py::_exchange` (`:119`) already POSTs to Google's Secure Token API with
  `settings.firebase_web_api_key`, one handled `ConfigError` per failure, no traceback.
- `cs/resolve.py::resolve_email` already turns a uid into an email through the Admin
  SDK with the same key (`settings.firebase_sa_path`).
- `firebase-admin>=6.5` is already a dependency (`pyproject.toml:14`).

Nothing here is new machinery. What is missing is a way to obtain the refresh token
when no descriptor exists.

**The store-then-prove order is deliberate and is preserved.** `cs/login.py:393-403`
keeps a stored session when the proof call fails, because the commonest cause is a
profile the vendor engine has not provisioned yet — precisely the population `--mint`
targets. A prove-before-store surface does exist elsewhere (`cs/project_init.py:172-189`
driving `rpc.call_sync(..., id_token=…)`, `cs/rpc.py:55-64,82`); it is deliberately NOT
adopted here, because inverting the order would discard exactly the sessions this brief
is built to create.

## Decision

**A minted session is a descriptor the clone builds for itself.**

`cs login --mint` and `cs --account <name> login --mint` assemble the same five fields
`cs/login.py` already consumes, from sources the clone already holds:

- `refresh_token` — Admin SDK `create_custom_token(uid)` signed locally with
  `settings.firebase_sa_path`, exchanged at `accounts:signInWithCustomToken` for an
  `idToken` + `refreshToken`, using the clone's own `firebase_web_api_key`.
- `email` — `resolve.resolve_email(uid)`, same service account.
- `uid` — the account's uid from the registry.
- `engine_ws_url`, `firebase_web_api_key` — the clone's own settings.

From there the existing path runs unchanged, store-then-prove order included.

**The registry bounds the code path.** `--mint` refuses any uid not declared in this clone's `CS_ACCOUNTS`
(`settings.account_map`), naming the uid and the registry; `--account` already resolves
through that map and refuses an unknown name (`cs/cli.py:2186-2192`). It is also the ONLY guard: `_identity_conflict` cannot help,
because a synthesized descriptor's uid is the registry's own uid, making that check a
self-comparison, and under `--account` it returns at `cs/login.py:179-180` before the
email check ever runs. What the registry refusal buys is
precise and worth stating plainly: kernel code cannot be pointed at a uid the operator
has not written into the clone's own configuration. What it does not buy: `CS_ACCOUNTS`
is environment (`cs/config.py:336-338`) and process env outranks the dotenv file
(`:573-588`), so whoever can set the clone's environment can widen the registry — and
that party can already read the service-account key itself. The check is also mint-time
while the minted file is permanent: a uid later removed from the registry leaves its
stored session behind, exactly as a descriptor-born one would.

**Minting is refused unless a human is at the keyboard.** `--mint` checks
`sys.stdin.isatty()` BEFORE any `input()` call and refuses when it is false, then
confirms through a prompt defaulting to no, echoing the account name, the uid and the
resolved email. Deciding on the tty rather than on an `EOFError` is deliberate: what
file descriptor a headless tick hands a Bash child is a runtime property this repo does
not pin, and on a pipe `input()` would block inside a flock the wrapper holds for the
whole tick. The mint branch (`cs/login.py:294-329`) carries no exception handling today
— the `EOFError` path at `:350-355` belongs to the no-configured-uid branch — so both
the tty check and an `EOFError` guard are NEW code here, not a reuse.

A deny-set entry cannot express this: gate 17 builds tokens as
`Bash(<interpreter spelling> <verb>:*)` (`tests/run.sh:542`, SPELLINGS `:431-438`), so
`Bash(cs login:*)` cannot match `cs --account <name> login --mint`, the one form that
mints a secondary account. A partial deny that looks complete is worse than none, so
none is added.

**What that guardrail is, and is not.** It stops mistakes and confused-deputy use: a
skill, a script or an operator reaching the verb without meaning to. It is NOT a
security boundary against code execution, and the brief does not claim one. Anything
that can run arbitrary commands in the clone can compose env, stdin and arguments in a
single line, and — more to the point — can skip the verb entirely: the service-account
key, `firebase-admin` and the network are all present, and forty lines of Python mint a
session for any uid in the project. That was demonstrated during this study. So `--mint`
adds convenience, never capability, and every claim in this brief is scaled to that.

**The standing exposure this work does not create and does not remove.** The cron
wrapper's own comment names the threat it defends against as "a skill bug or a
prompt-injection in inbound mail" (`templates/project/bin/cs_operator_cron.sh.j2:42-43`).
Under that model, a clone running an unattended agent while holding a service-account
key that authenticates as any uid in the Firebase project — customers included — is a
standing exposure, present before this change and after it. The operator has decided
the key's reach stays as it is. It is recorded here so the decision keeps its reasons
attached, not reopened.

## What does not change

- The daemon's auth boundary. A minted token carries `sub == <that account's uid>` and
  meets the same gate a descriptor-born token meets. No delegation.
- Where a session is stored and its mode: `auth._write_refresh`, per-account path, 0600.
- The descriptor path stays first choice and stays documented; `--mint` answers for a
  profile no human will sign into.
- `cs login` still never writes `.env` or `manifest.toml`. Growing the registry stays an
  operator edit, which is what keeps the wall operator-owned.
- Identity for sending: the operator's own mailbox, always.

## Scope

In: the mint source; the registry refusal and its gate; the interactive confirmation
and its EOF refusal; `--mint` on both spellings of `login`; refusal text that names
`--mint` rather than a descriptor that does not exist (`cs/login.py:184-189`, `:196-202`
currently say "pick the matching descriptor"); the stamped clone text that this
falsifies (`templates/project/docs/ARCHITECTURE.md.j2:90-91` states the service-account
key "is NOT part of this chain"); the CHANGELOG entry at FULL re-test tier.

Out: minting from any verb other than `login`; any change to which uids a clone
declares; any narrowing of the service account's own scope, which the operator has
decided stays as it is; the clone-side follow-on for 124 (wiring Ivan and Riccardo,
retiring their declared-mailbox passwords), which is operation once this ships.

## Rule of two

Both maintained clones carry a two-entry `CS_ACCOUNTS` and both answer customers from
more mailboxes than they have registered. Neither can grow its registry without a
desktop sign-in on a headless profile, so this is a shared need, not one company's.

## Constraints

- Touches the auth boundary ⇒ **FULL re-test tier on both clones**, whatever the digit.
- New CLI surface ⇒ MINOR.
- No company literal in `cs/`. The mint reads the project id from the key file, never
  from a constant.

## Acceptance

Each criterion names an observable a broken implementation fails.

- `cs --account <name> login --mint`, for a registry account with no stored session,
  ends with the same "signed in" line the descriptor path prints, and a 0600
  refresh-token file exists at that account's own path — not the operator's.
- Immediately afterwards, `cs --account <name> thread <address> --full` returns message
  bodies from that account's archive. This is the point of the work.
- `--mint` for a uid absent from `CS_ACCOUNTS` refuses, exits non-zero, names the uid
  and the registry, and leaves no file behind. Proven with a uid that genuinely exists
  in the Firebase project, so the refusal is the registry's and not Firebase's.
- A mint whose proof call fails behaves exactly as the descriptor path does today: the
  session stays stored and one line says the proof failed and why. Asserted against
  `cs/login.py:393-403` so a future inversion of that order is caught here.
- Minting a secondary account never overwrites the operator's own session: the
  operator's stored uid is unchanged afterwards.
- `--mint` with a non-tty stdin refuses and exits non-zero before prompting, storing
  nothing — asserted by a subprocess run, and holding for
  `cs --account <name> login --mint`, the spelling no permission string can reach.
- The refusal happens without blocking: the assertion runs under a timeout well below
  the wrapper's, so a guard that waited on input instead of checking the tty fails here.
- `--mint` for a uid whose Firebase user carries no email refuses and exits non-zero.
  It never prints a session line naming an empty identity (`cs/resolve.py:32` returns
  `None`, and nothing downstream validates it today).
- Operator-facing refusals from the mint path name `--mint` and the registry; none of
  them tells the operator to pick a descriptor that does not exist.
- Every failure — unreadable key, uid with no Firebase user, refused exchange,
  unreachable engine — prints one handled line, never a traceback.

## Consequence for verification

A SUCCESSFUL mint cannot be exercised by subprocess, because the tty check refuses one
(`tests/test_login.py:242-260` already drives `cmd_login` with `stdin=DEVNULL`). The
success criteria are therefore operator-run collaudo on a real terminal; every refusal
criterion stays automatable and belongs in `tests/run.sh`. Splitting them that way is
the point — the automatable half is the half that guards.

## Material assumptions

- **Proven, not assumed**: a locally-signed custom token is accepted. Probed live from
  `124-cs` against its own identity on 2026-09-09 — `create_custom_token` signs from the
  key with no IAM round trip, `signInWithCustomToken` returns both tokens, and the id
  token's subject equals the uid. Session file, § "Mint feasibility".
- **This is a posture change and is recorded as one.** The service-account key stops
  being a read-only accessory and becomes an authentication credential for any uid in
  the Firebase project. The operator has decided the key's reach stays as it is; the
  registry refusal is what keeps kernel code inside a narrower circle than the
  credential, and the stamped clone text must stop claiming the key is outside the auth
  chain.
- Minting is rare and human-run — twice, for the first consumer. Nothing in the
  product wants it automated, which is what makes an interactive confirmation the right
  guardrail rather than a friction to engineer around.
- The colleagues whose profiles are minted have agreed. The kernel encodes no consent
  mechanism and this brief proposes none.
