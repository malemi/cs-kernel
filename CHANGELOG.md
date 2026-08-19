# Changelog — cs-kernel


Clones pin **tags only**. Every entry states which clones must re-collaudo
and at which tier (design brief §6.6: static / +live read-only / full).

**Current operational pin** (both clones, static tier, 2026-08-19): `v0.8.1`.
`mrcall-cs` and `124-cs` each pin `@v0.8.1` and have `0.8.1` installed
(`cs --version` verified on both). Static-tier evidence recorded at re-pin:
`.claude/settings.json` and `bin/cs_operator_cron.sh` byte-identical before
and after `cs update`, live `cs whoami` proof call OK on both engines.
Operators are un-paused; 124-cs's operator cron is installed and ticking,
mrcall-cs's is not installed (open item in `docs/active-context.md`).

`v0.5.2` and every earlier tag mint the auth token from a locally-held
Firebase service-account credential (`firebase-sa.json`) that only the
vendor can issue — a new customer cannot complete onboarding on those tags
and must not be pointed at them; `v0.6.0` is the first tag a new customer
can install end to end.

## v0.8.1 — 2026-08-19

### Fixed — `v0.8.0` installs as `0.7.1` (tag cut without the release commit)
- **Why:** `v0.8.0` was tagged and pushed directly from the feature commit,
  skipping the release commit, so `git show v0.8.0:pyproject.toml` still
  says `0.7.1`: a clone pinned at `v0.8.0` runs the right code but reports
  the wrong number from `cs --version` and `pip show` — the v0.6.1/v0.7.0
  incident again, and a published tag is immutable.
- **What:** `pyproject.toml` moves to `0.8.1`; `v0.8.0` is recorded in
  `TAG_VERSION_EXCEPTIONS` and its object pinned in `IMMUTABLE_TAG_TARGETS`
  (operator decision, 2026-08-19). No runtime change of any kind —
  `v0.8.1` is `v0.8.0` under its true name.
- **Migration note:** a clone pinned at `v0.8.0` works; re-pin with
  `cs update --pin v0.8.1` when convenient to make the reported version
  true again.
- **Re-collaudo:** **static tier, both clones** — metadata-only; `cs/` is
  untouched apart from the version string.

## v0.8.0 — 2026-08-19

### Added — `cs init` writes the secrets file itself
- **Why:** README Step 3 told a (often non-technical) operator to
  mkdir/cp/hand-edit a dotenv whose values the wizard already knew — the
  worst step of the onboarding walk.
- **What:** the wizard's last prompt is the mailbox app password
  (`getpass`, Enter to skip) and `cs init` writes `~/.<slug>-cs/.env` onto
  the rendered `.env.example`'s own anchor lines: `CS_ACCOUNTS` from the
  accounts registry, `FIREBASE_WEB_API_KEY` from the Step-0 descriptor,
  file mode 0600 in a 0700 state dir regardless of umask. An existing
  `.env` is operator-owned and never touched; EOF/^C on the prompt writes
  `EMAIL_PASSWORD` blank and prints the decision (the v0.5.2 EOF
  contract). Gate 24 (`tests/test_state_env.py`) proves all of it on the
  real template.
- **Also in this tag:** the README quick-start cut to size (uv
  de-emphasised, steps 5–7 terse, day-to-day model before Troubleshooting,
  a "The `cs` CLI" verb map under Reference); the README install snippets
  resolve the newest tag at run time and a literal `cs-kernel@vX.Y.Z`
  install pin in README is now a gate failure; `cs init`'s wizard default
  for a new clone's pin follows the operational pin.
- **Known defect:** the tag installs as `0.7.1` — no release commit
  preceded it; recorded and fixed forward by `v0.8.1` above.
- **Re-collaudo:** **static tier, both clones** — nothing here touches a
  send path, the auth boundary, a manifest field or a permission byte; the
  secrets writer fires only on a fresh `cs init`, and an existing clone's
  `.env` is by contract never touched.

## v0.7.1 — 2026-08-16

### Fixed — a published tag installed under the previous version number
- **Why:** `v0.6.1` and `v0.7.0` were both cut without bumping
  `pyproject.toml`, which still said `0.6.0`. A clone pinned at either tag
  installs a package that reports `0.6.0` — from `pip show`, from
  `cs update --version`, and from the brand-new `cs --version` that
  `v0.7.0` exists to provide. The collaudo's "Installed" column would have
  recorded the same wrong number. Nothing misbehaves at runtime; the
  package simply lies about which release it is, which is exactly the kind
  of quiet untruth this repo's release gate exists to prevent — and did
  not, because it only ever checked the pyproject version against the
  CHANGELOG and the active context, never against the tag being cut.
- **What:** `pyproject.toml` moves to `0.7.1`. The release gate
  (`tests/test_release_consistency.py`) gains `check_tag_versions`: for
  every semver tag, `git show <tag>:pyproject.toml` must declare that same
  version. The three tags that cannot comply — `v0.5.0` (historical) and
  `v0.6.1` / `v0.7.0` (this incident) — are listed in
  `TAG_VERSION_EXCEPTIONS` with the reason inline, because a published tag
  is immutable and a recorded mistake is worth more than a hidden one. A
  NEW mismatch fails the suite: it is a release bug to fix before tagging,
  never an entry to append.
- **Migration note:** none for behaviour. A clone pinned at `v0.6.1` or
  `v0.7.0` has the right code under the wrong version string; re-pinning to
  `v0.7.1` makes the reported version true again. Anyone reading an
  "Installed 0.6.0" from a clone that declares `v0.7.0` is looking at this
  bug, not at a failed upgrade.
- **Re-collaudo:** **static tier, both clones** — a version-string fix plus
  a test-only addition. No runtime code path changes; `cs/` is untouched
  apart from the metadata version.

## v0.7.0 — 2026-08-16

### Added — top-level `cs --version`
- **Why:** `cs --version` used to exit 2 with an argparse usage dump
  demanding a subcommand — the version was reachable only as `cs init
  --version` / `cs update --version`, neither discoverable from a bare
  invocation, and it is the first thing a newcomer or an operator
  verifying a re-pin actually types. It also made its way into a release
  runbook as a wrong command, twice (backlog item filed 2026-08-16).
- **What:** `cs/cli.py`'s root `argparse.ArgumentParser` now registers
  `--version`, sourced from a new single-purpose module `cs/_version.py`
  (`kernel_version()` / `kernel_version_bare()`, both reading
  `importlib.metadata` live off the installed `cs-kernel` distribution).
  `cs/project_init.py`'s `cs init --version` and `cs/project_update.py`'s
  `cs update --version` are refactored onto the same helper, retiring the
  two near-identical local `try/except PackageNotFoundError` blocks that
  used to exist independently — one shared source instead of three copies
  of the same import, and `cs update --check` (below) reuses the "bare"
  half of the same helper for its installed-vs-latest comparison. Works on
  a bare install with no manifest anywhere, exactly like `--help` already
  did (proven by `tests/test_version.py`, which runs it from an empty
  directory).
- **Migration note:** none — additive CLI surface, no state, no config.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Added — `cs login` auto-selects the descriptor it already knows; no more picking from a menu of wrong answers
- **Why:** with `--account`, or on any stamped clone, the target engine uid
  is already fully determined before `cs login` ever runs — yet it still
  printed the full numbered list of every descriptor found on the machine
  and let the operator choose, including the wrong ones, which were only
  refused AFTERWARDS by the identity cross-check, with a message
  ("fix manifest.toml [engine].owner_uid deliberately") that reads like a
  manifest misconfiguration for what was simply a menu the operator should
  never have been shown. On a machine with several signed-in profiles —
  the normal case for a founder-sweep secondary account — that menu is a
  trap, not a convenience (backlog item filed 2026-08-16, Mario signing in
  a secondary account and picking the primary's descriptor by habit).
- **What:** `cs/login.py::cmd_login` now branches on whether
  `settings.engine_owner_uid` is already configured. When it is, the
  descriptor whose uid matches is auto-selected and printed
  (`selected: <email> (<uid>)`) with NO prompt at all; when none of the
  descriptors found match that uid, `cs login` fails immediately —
  `no descriptor for uid <uid> [(account '<name>')] — sign in to the
  mrcall-desktop app as that account` — instead of offering a list in
  which every option is wrong. The numbered picker (and the single-profile
  `Proceed? [Y/n]` confirm) survives untouched for the one case that is
  genuinely ambiguous: no engine identity configured yet, e.g. a brand-new
  clone before `cs init` has stamped one. `_identity_conflict` — the
  post-pick cross-check that actually decides whether a session gets
  stored — is completely unchanged; this only changes WHICH descriptor is
  ever offered, never what is accepted.
- **Migration note:** none — behavior-only fix to an interactive verb, no
  state, no config. An operator who was used to seeing (and ignoring) the
  full menu will now see either a one-line auto-select confirmation or an
  immediate, clearer refusal.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Added — `cs update --check` / `cs update --pin <tag>`: the discovery half of the upgrade path
- **Why:** nothing told an operator that a newer kernel tag had shipped —
  the only way to find out was reading the CHANGELOG in another repo, and
  re-pinning was a hand-edit of `requirements.txt` (in practice a `sed`).
  A clone could sit on an old kernel indefinitely with no signal (backlog
  item filed 2026-08-16, mid a `v0.6.0` re-pin).
- **What:** two new opt-in flags on `cs/project_update.py`'s argparse
  layer; bare `cs update` is completely unchanged. `--check` parses the
  kernel origin straight off `requirements.txt`'s own pin line (`cs-kernel
  @ git+<url>@<tag>` — the URL is READ, never hardcoded), runs `git
  ls-remote --tags <url>` against it, and prints installed (the actually
  `pip`-installed version, via `cs._version.kernel_version_bare()`),
  pinned, and latest. When a newer tag exists it also prints that tag's
  own re-collaudo tier when it can determine it — read straight off the
  newer tag's OWN `CHANGELOG.md` via `git show <tag>:CHANGELOG.md`,
  attempted ONLY when the origin is something git can read off the local
  filesystem (a `file://` remote or a local path some kernel-developer
  clone may legitimately pin to); a real customer clone pinned to a remote
  GitHub URL has no local copy of the kernel's tree to read the tag's
  CHANGELOG from, which is the common case, and the command degrades to
  printing just the tag name rather than guessing or fetching raw content
  over an assumed host shape. `--check` WRITES NOTHING, ever — including
  when the origin is unreachable, which prints one handled line naming it
  and exits 1, never a traceback. `--pin <tag>` rewrites ONLY the kernel
  pin line in `requirements.txt` (every other byte, including comments,
  is untouched), prints the exact before/after line, and says installing
  it is a separate, deliberate step (`pip install -r requirements.txt`).
  Neither flag auto-bumps the pin: `requirements.txt` is the operator's
  own pin (the `v0.5.2` decision — "`cs update` never touches it"), and
  every kernel upgrade owes a re-collaudo (CLAUDE.md, Versioning &
  release) — `--check`'s own output says so, and so does the code comment
  above `--pin`'s implementation. A `--check` that rewrote the pin itself
  would not be a pin anymore.
- **Migration note:** none — additive CLI surface; `requirements.txt`'s
  format is unchanged and `--check`/`--pin` are both opt-in.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Re-collaudo (this release)
- **STATIC tier, both clones.** This is the first release to apply the
  amended charter rule (CLAUDE.md, Versioning & release, changed
  2026-08-16 while scoping this very candidate): the version digit
  describes the INTERFACE, and the re-collaudo tier is a separate
  judgement decided by what the release TOUCHES. This candidate is
  therefore a MINOR — new CLI surface (a root flag, two `cs update`
  flags, a changed `cs login` interaction shape), and a verb that stops
  prompting is not something an operator reading "patch" should discover
  on their own — while carrying NO
  new manifest field and touches none of the charter's escalation
  triggers: no send path (`cs/send_mail.py`, `cs/campaign.py`'s pack
  senders), no `cs/gmail_archive.py`, no `cs/send_guard.py`, no engine RPC
  shape, and — proven by gate 17's own byte-for-byte token check, which
  stays green unmodified — no permission bytes in either
  `.claude/settings.json.j2` or `bin/cs_operator_cron.sh.j2`. The only
  collaudo-visible surface any of the three changes touch is the `--help`
  tree and two interactive verbs' console output, and the STATIC tier
  (gate 4's full `--help` walk plus the three new/expanded test files —
  `tests/test_version.py`, the `--check`/`--pin` guards folded into
  `tests/test_project_update.py`, the known-uid auto-select guards folded
  into `tests/test_login.py`) already exercises every one of those real
  code paths end to end, several of them as REAL subprocesses against a
  real local git repo standing in for the kernel's remote origin. The
  reasoning is on record here, and the tier is stated per entry as the
  amended rule now requires, precisely so the next MINOR that DOES touch a
  send path, the auth boundary or a manifest field cannot point at this
  entry as precedent for skipping FULL.

## v0.6.1 — 2026-08-16

### Fixed — the public README still walked a new reader onto the retired `v0.5.2` install pin and skipped `cs login` entirely
- **Why:** an adversarial UX review of the README as a fresh, competent
  reader with no prior context on this project found it breaking at
  installation and at first use. The install pin, the Versioning section's
  pin and the "Current release" line all still named `v0.5.2` — the tag
  from *before* the `v0.6.0` auth rewrite — so a reader who followed the
  README to the letter installed the vendor-only-service-account mint path
  and dead-ended on a `FileNotFoundError: firebase-sa.json` traceback for a
  file only the vendor can issue. `cs login`, the verb `v0.6.0` actually
  introduced to turn a desktop sign-in into a usable session, was entirely
  absent from the document (`grep login README.md` matched nothing), so the
  reader had no path from "toolkit installed" to "`cs whoami` succeeds."
  Prerequisites told the reader to look up "the engine WebSocket URL and the
  profile's Firebase uid" by hand — both now unobtainable that way, since
  `v0.6.0` derives them from the desktop app's own sign-in descriptor. The
  document also never used the word "daemon" and never said `cs` has to run
  on the same machine as the mrcall-desktop app, never stated the Gmail /
  Google Workspace requirement `cs/gmail_archive.py`'s IMAP special-use
  folder selection actually has, told the reader "defaults are fine when
  unsure" when several `cs init` prompts are hard-required (an empty answer
  loops on "Please provide a value."), and its own worked example silently
  diverged from the wizard's real behaviour: the table said the slug for
  "ACME Corp" is `acme`, but `project_init.get_company_slug()` derives
  `acme-corp`, so a reader who accepted that default would get a state
  directory every later command in the same README — including the
  `CS_PAUSE` kill-switch — then misses.
- **What:** the README gained a new Step 0 ("Install mrcall-desktop and
  sign in") ahead of the toolkit install, stating plainly what the app and
  its local daemon do, that `cs` must run on the same machine, the
  macOS/Windows-vs-Linux-from-source split, that sign-in writes the profile
  descriptor `cs login` reads, and that a release newer than the public
  `v0.1.29` (2026-05-05) is required. The now-false "you'll need the engine
  WebSocket URL and the profile's Firebase uid" line is removed from
  Prerequisites. `cs login` is now its own numbered step between installing
  the project pin and `cs whoami`, explaining the `email (uid)` confirm
  prompt, the stored session, the `FIREBASE_WEB_API_KEY=` note to paste into
  `.env` on a key mismatch, and what `cs whoami` proves. A new
  Troubleshooting section right after the setup steps quotes the tool's real
  message text — verified against `cs/auth.py` and `cs/login.py` rather than
  paraphrased — for "not signed in", connection-refused / engine-unreachable
  (naming the asymmetry: `cs login` catches this as one line, other verbs
  still surface a raw traceback), "no profile descriptor found", and nothing
  landing in Drafts (`CS_PAUSE` and `cs_operator.log`). Prerequisites gained
  the Gmail / Google Workspace requirement with its one-line reason. The
  setup-prompts prose now names which answers must be ready before starting
  instead of claiming defaults are always safe, and the worked example tells
  the reader to type `acme` explicitly, spelling out why the wizard's own
  default (`acme-corp`) would silently break the rest of the walkthrough.
  The cron section now leads with the `cs cron install`/`status`/`uninstall`
  verb, keeping the manual `crontab -e` route as the documented fallback
  rather than the only path. All three stale `v0.5.2` install lines move to
  `v0.6.0`, the released tag. This changelog's own top-of-file pin paragraph
  is rewritten to `v0.6.0` (FULL collaudo signed on both clones 2026-08-16)
  with a sentence warning that `v0.5.2` and earlier require the vendor-only
  service-account file, so a new customer must not be installed onto them;
  and the `v0.6.0` heading below drops the stale "candidate" wording now
  that the tag is cut and pushed.
- **Migration note:** documentation-only; no operator action.
- **Re-collaudo:** none by itself — see the shared reasoning at the bottom
  of this entry.

### Fixed — `cs init` stamped a clone that could not run, and left its own cron entry silently dead
- **Why:** three defects surfaced together while walking `cs init`'s output
  end to end: the rendered `bin/*.sh` scripts came out of the Jinja render
  at mode `0644`, so a freshly stamped clone's cron wrapper was not
  executable — the exact crontab line this README documents
  (`… bin/cs_operator_cron.sh …`) then failed silently under cron, with
  nothing in `cs_operator.log` to explain why, which is the single defect
  most likely to make a new operator conclude the product does nothing. The
  wizard's own kernel-version default for the generated
  `requirements.txt.j2` pin still read `0.5.2` — the pre-auth-rewrite tag —
  so a clone stamped with the wizard's own suggested answer would re-hit the
  same vendor-only service-account wall the README fix above describes.
  Separately, the stamped clone templates themselves still carried
  operator-visible defects: a hardcoded `wss://desktop.example.com`
  placeholder where the real engine URL belongs, a "this is the mother
  clone" sentence told to every company regardless of which clone it was,
  CRM/producer/excluded-campaign bullets that printed even when the
  operator had chosen the `none` adapter, prose left in Italian in at least
  one template, and stale references to a `cs-template`/`copier` mechanism
  that does not exist in this project.
- **What:** rendered `bin/` scripts are now created with the executable bit
  set, in both `cs init`'s render path and `cs update`'s re-render path, via
  a shared `is_executable_target` helper so the two can never drift apart
  on which files qualify. The
  wizard's kernel-version default moves off `0.5.2` (now tracking the
  release being cut). The stamped templates are corrected: the engine-URL
  placeholder renders from the real configured value, the mother-clone
  sentence is removed from the generic template, CRM/producer/excluded-campaign
  bullets are guarded so a `none` adapter omits them entirely instead of
  printing an empty or misleading line, the Italian strings are translated
  to English, and the `cs-template`/`copier` references are corrected to
  describe this project's actual `cs init`/`cs update` mechanism.
- **Migration note:** affects what `cs init` stamps and the file mode of the
  rendered scripts going forward. An already-stamped clone is unaffected
  until it runs `cs update`, which re-renders the touched templates and
  restores the intended file mode on `bin/`; no state, no send path, no
  auth boundary changes underneath it.
- **Re-collaudo:** none by itself — see the shared reasoning below.

### Re-collaudo (this release)
- **PATCH — static, picked up at the next `cs init` / `cs update`.** Every
  item above changes what `cs init` STAMPS into a new clone, the file mode
  of rendered scripts, or documentation; none of it touches a code path a
  clone already running `v0.6.0` depends on — the auth boundary, the send
  chokepoint, the campaign lifecycles and the engine RPC shapes are
  untouched. A full collaudo is not required to adopt this tag; re-running
  `cs init` on a fresh clone (or `cs update` plus a `chmod +x bin/*.sh`
  sanity check) is enough to confirm the fix landed.

## v0.6.0 — 2026-08-15

### Changed — auth exchanges a refresh token via the Secure Token API; the service-account credential exits the mint path
- **Why:** the v0.5.2 blind onboarding probe (both clones, 2026-08-09) proved
  the wall a new customer actually hits at the terminal step is the
  vendor-only service-account credential the old mint path required
  (`firebase-sa.json`, obtainable only from inside the vendor's own console)
  plus the raw tracebacks every layer beneath it threw once that credential
  existed but the exchange still failed — see the two "Known" entries
  directly below, both opened the same day.
- **What:** `cs/auth.py` is rewritten end to end. It no longer mints a
  Firebase custom token locally with a service-account private key and
  exchanges it via identitytoolkit `signInWithCustomToken`; instead it reads
  the refresh token written by the desktop app's own sign-in descriptor —
  the surface `cs login` (below) consumes — and exchanges it for a
  short-lived ID token through Google's Secure Token API, mirroring the
  engine's own headless refresh
  (`mrcall-desktop/engine/zylch/auth/refresh.py::exchange_refresh_token`)
  request shape. The service-account file exits the auth path entirely:
  `firebase_sa_path` remains in `Settings` only for the optional
  Drive/lead-resolve surfaces (`cs/drive.py`, `cs/resolve.py`,
  `scripts/find_profile_uid.py`), which still need the Admin SDK and are
  untouched here. Every auth-boundary failure — not signed in, a stored
  session for the wrong uid, an HTTP or network failure from the exchange, a
  malformed response, an identity mismatch on the exchanged token — is now a
  single handled `ConfigError` line; none of the failure branches propagate
  a raw traceback. New derived setting `refresh_token_path` (empty →
  `<state_dir>/refresh_token-<uid>.json` — see the per-account entry below)
  backs a new uid-tagged, mode-`0600` JSON file managed by
  `_read_refresh`/`_write_refresh`. `cs/sms.py` and `cs/rpc.py` are
  unchanged — both call `auth.get_id_token` and only ever use its return
  value, so nothing downstream of the token needed to know the mint
  mechanism changed underneath it. `cs login` (`cs/login.py`) is the new
  human-run verb that actually produces that stored session: it finds the
  profile descriptor (scanned under `~/.zylch/profiles/<uid>/cs-descriptor.json`,
  or given directly via `--descriptor`), confirms — or, with more than one
  profile present, numbered-picks — with the operator, refuses strictly (no
  `--force`) on any mismatch between the descriptor's identity and this
  clone's own configured `engine_owner_uid` — plus `email_address`, but that
  half applies to the clone's PRIMARY identity only (see the per-account
  entry below) — stores the refresh token through the `_write_refresh`
  above, and proves the session
  with one live `account.who_am_i` call; it carries no cron/allow-list entry
  of its own. `cs --help` (bare, no subcommand) now lists `init`, `update`
  and `login` as real subparsers — normally bypassed by the early dispatch
  that actually runs them, registered only so the help tree tells the
  truth — closing the onboarding-probe finding below that `cs --help` did
  not list `init`/`update` at all. This batch closes the remaining
  onboarding-probe gaps: `cs init` now autodetects a mrcall-desktop profile
  already signed in on this machine — new `project_init.descriptor_defaults()`
  scans the same `~/.zylch/profiles/*/cs-descriptor.json` tree via
  `login.descriptor_root`/`scan_descriptors`/`parse_descriptor` and, when
  EXACTLY ONE valid descriptor is found, prefills the wizard's `Operator
  email`, `Engine WS URL`, `Engine owner UID` and default-account-UID
  prompts from it (printing which profile it used); the operator still sees
  and can override every value, and zero or more than one descriptor leaves
  the wizard neutral — picking among several signed-in profiles stays `cs
  login`'s job. The wizard's `Git remote URL` prompt now defaults to empty
  ("local-only, add one later with `git remote add`") instead of being
  required with no default — the finding below — since its sole consumer,
  `manifest.toml.j2`'s template-only `[repo].git_remote` field, was already
  safe with an empty value (valid TOML, never parsed back into `Settings`).
  `cs update` gains the same minimal argparse treatment as `cs init` — a
  real `prog='cs update'` parser, `--version` off the installed package
  metadata, identical `SystemExit` code propagation — so `cs update --help`
  now prints usage and exits 0 instead of falling through into a live
  template-merge walk against the current directory. The stamped-clone docs
  catch up: `CLAUDE.md.j2`'s "Auth chain (headless)" paragraph now describes
  the desktop app writing the profile descriptor, `cs login` storing the
  refresh token (state dir, mode `0600`), every verb exchanging it via the
  Secure Token API for a cached short-lived ID token, and the engine
  verifying RS256 and gating `token.sub == OWNER_ID` — unchanged; and
  `.env.example.j2`'s `FIREBASE_WEB_API_KEY`/`FIREBASE_SA_PATH` comments no
  longer describe the service account as the auth credential, naming it
  optional and scoped to the Drive/lead-resolution surfaces instead.
- **Migration note:** a clone re-pinned to this version has no stored
  session for `cs login` to overwrite. A stale `~/.<slug>-cs/id_token.json`
  from the v0.5.2 mint path is now simply ignored — the per-uid derivation
  the entry directly below this one adds reads `id_token-<uid>.json`, a
  filename the old path never wrote, so the false-green scenario this
  paragraph used to warn about (a cached token from the old path silently
  keeping every verb "working" for up to ~1h) is now structurally
  impossible. Deleting the stale file (`rm ~/.<slug>-cs/id_token.json`) is
  hygiene, not a correctness step. Every engine verb prints the handled
  "not signed in — run `cs login`" line until the operator runs `cs login`
  once.
- **Re-collaudo:** **full, both clones** — this changes the auth boundary
  every RPC call, SMS send and engine WebSocket connect goes through
  (`cs/rpc.py`, `cs/sms.py` call the same `get_id_token` signature, but what
  runs underneath it is entirely new). Prove a real refresh-token exchange
  against the live engine Firebase project on both clones before this ships.
  The per-uid filename (see the entry directly below) makes the old
  false-green risk — a cached `id_token.json` from the v0.5.2 mint path
  silently passing the suite — structurally impossible, since the new code
  never reads that filename once an engine identity is configured; deleting
  the stale file first is optional hygiene, not a precondition for a
  trustworthy result.

### Changed — session files are per account uid (`--account` keeps working)
- **Why:** the founder-inbox sweep — a daily, read-only check of a second
  configured mailbox alongside the operator's own (the F3 decision) — needs
  `cs --account <secondary> …` to keep working across repeated logins. The
  refresh-token rewrite in the entry directly above stored exactly ONE
  session per clone (`<state_dir>/refresh_token.json`,
  `<state_dir>/id_token.json`), so a second `cs --account <secondary> login`
  silently overwrote the first: signing in to the founder mailbox clobbered
  the primary operator mailbox's own session file, regressing
  `cs --account <secondary>` the moment two accounts were both signed in.
  Fixing that surfaced a second, discovered-by-recon bug:
  `login._identity_conflict` also compared the clone's configured
  `email_address` (the primary operator mailbox) against the descriptor's
  own email, and for a secondary account's descriptor — the founder's own
  mailbox, never the operator's — that comparison ALWAYS mismatches, so
  `cs --account <name> login` was refused outright before the per-clone
  session file could even become the practical problem.
- **What:** `token_cache_path` and `refresh_token_path` (`cs/config.py`)
  now derive as `<state_dir>/id_token-<uid>.json` and
  `<state_dir>/refresh_token-<uid>.json`, where `<uid>` is the resolved
  `engine_owner_uid` — the same uid `cs --account <name>` swaps into
  `CS_ENGINE_OWNER_UID` before `config.load()` runs, so the derivation
  follows whichever account is selected for that invocation. An empty uid
  (no engine identity configured at all) keeps the legacy un-suffixed
  names, since `cs/auth.py` raises its own "uid not set" `ConfigError`
  before either file is ever read or written. An explicit
  `token_cache_path`/`refresh_token_path` set in the environment is
  untouched, exactly as before — derivation only ever fills in an EMPTY
  field. `cs/auth.py`'s id-token cache read/write now also strips the
  configured uid before tagging or comparing it, so a whitespace-bearing
  configured uid no longer thrashes the cache between the default and
  `--account` paths. `cs login`'s identity cross-check
  (`login._identity_conflict`) now takes an `account_switched` flag,
  threaded from `cli.main()`'s `--account` handling through the new
  `cmd_login_stub` signature: the uid checks (empty configured uid, uid
  mismatch against the descriptor) stay unconditionally active — uid
  equality with the `CS_ACCOUNTS` registry entry IS the identity statement
  for a secondary account — but the operator-mailbox email comparison now
  binds the clone's PRIMARY profile only, and is skipped exactly when
  `--account` actually switched the uid away from the clone's default. The
  email-mismatch refusal message also gains a pointer for the legitimate
  secondary case: "…or pick the matching descriptor; for a registered
  secondary account run `cs --account <name> login` instead." The
  operator-mailbox cross-check was always an independent second opinion,
  never the sole guard: for a switched `--account` login the invariant now
  rests on the unconditional uid check against the operator-written
  `CS_ACCOUNTS` registry, plus the interactive confirm every `cs login` run
  requires (`cs login` prints `email (uid)` and stores nothing without an
  explicit yes). This diff also fixes an operator-visible CLI parsing
  defect it would otherwise have shipped un-exercised:
  `cs --account <name> login --descriptor PATH` now actually parses —
  before, it exited 2 with argparse's own "unrecognized arguments:
  --descriptor" (the login stub's argv passthrough used a REMAINDER
  positional, which cannot coexist with an unrecognized flag anywhere in
  its subparser); the stub (`cs/cli.py::cmd_login_stub`) now mirrors
  `cs login`'s real `--descriptor` option instead, and `cs/cli.py` records
  the resulting maintenance rule that any new `cs login` option must be
  added to both parsers.
- **Migration note:** any clone that configures a founder-sweep (or other
  secondary) account has no stored session for it yet. Once per clone: sign
  in to the mrcall-desktop app AS the secondary mailbox — that sign-in
  writes the secondary profile's own descriptor under
  `~/.zylch/profiles/<uid>/cs-descriptor.json` — then run
  `cs --account <name> login` once. That stores the secondary account's
  session under its own per-uid path and never touches the primary
  account's session, which needs no migration step of its own beyond the
  one already described in the entry directly above.
- **Re-collaudo:** covered by the same full-both-clones requirement as the
  refresh-token-exchange entry directly above — this changes the same auth
  boundary — plus one additional live proof per clone that configures a
  secondary account: `cs --account <name> login` followed by
  `cs --account <name> whoami` must succeed without disturbing the default
  account's own `cs whoami`.

### Known — the auth boundary still tracebacks below the env-key layer
- **Resolved for the auth path by the candidate above:** the service-account
  load this note describes no longer exists in `cs/auth.py` — the file load
  (and therefore its `FileNotFoundError` / `ValueError: Invalid service
  account certificate…` failure modes) is gone from the mint path, and the
  403-on-exchange case is now a handled `ConfigError` line naming the
  API-key-restriction possibility instead of a bare
  `urllib.error.HTTPError` traceback. The historical observation immediately
  below is kept for the record; `firebase_sa_path` and its own failure modes
  still apply wherever `cs/resolve.py` / `cs/drive.py` /
  `scripts/find_profile_uid.py` load it directly for the Admin SDK.
- v0.5.2's `ConfigError` covers the two missing env keys; every layer beneath
  still crashes raw. Observed live 2026-08-09 (both clones + the blind
  onboarding probe): a refused custom-token exchange prints
  `urllib.error.HTTPError: HTTP Error 403: Forbidden` (root cause found the
  same evening: an HTTP-referrer restriction on the shared engine-project web
  API key blocks all no-referer server-side calls — a console/config matter,
  not kernel code; the kernel's job is only to print it as one line); a missing
  `firebase-sa.json` prints `FileNotFoundError`; an invalid one prints
  `ValueError: Invalid service account certificate…`. Wrap the exchange call
  and the service-account load in the same handled one-line error path,
  naming the artifact and what it is. Target: v0.5.3.

### Known — two onboarding-probe findings on `cs init` (2026-08-09 blind run)
- `cs --help` does not list `init`/`update` (they dispatch before argparse):
  a customer sanity-checking the tool concludes `init` does not exist.
- The wizard's "Git remote URL" prompt is required, has no default and is
  absent from the README's prompts table; needs a local-only default or
  documentation. Target: v0.5.3.

## v0.5.2 — 2026-08-09

### Added — the `cs` console script, finished across the permission surface
- **Why:** `pyproject.toml` now declares `[project.scripts] cs = "cs.cli:main"`,
  so `cs` reaches the exact same code as `.venv/bin/python -m cs`. Claude
  Code's permission rules match the literal command TEXT typed on the Bash
  tool, not the program that ends up running, so a deny rule written for
  only the old spelling leaves the new one — and the plain `python -m cs` /
  `python3 -m cs` aliases — wide open. That is a live send-guard hole, not a
  cosmetic gap.
- **What:** every permission template now enumerates every spelling that
  reaches the entry point. The cron wrapper's `--disallowed-tools` re-deny
  set carries six spellings (`.venv/bin/python -m cs`,
  `.venv/bin/python3 -m cs`, `.venv/bin/cs`, `python -m cs`, `python3 -m cs`,
  `cs`) across the four surfaces it must block (`chat`, `rpc chat`,
  `campaign send-draft`, `rpc settings.update`) — 24 deny entries plus the 4
  non-cs keeps (`Write`, `Edit`, `rm`, `git push`). `.claude/settings.json`'s
  `permissions.deny` carries the same six spellings for `campaign
  send-draft`; its `permissions.allow` carries the four canonical spellings
  (module path and console script, `venv`-prefixed and bare — deliberately
  no `python3` alias there) across the 15 read/draft-only verbs.
  `CLAUDE.md`'s "module path is frozen" invariant is rewritten: the console
  script is a second door onto the same `cs.cli:main`, and clone permission
  strings must enumerate every spelling, not assume one. `tests/run.sh` step
  17 gates the enumeration by PLACEMENT — deny vs. allow, not just
  file-wide presence — and by exact, order-preserving token equality on the
  cron's list, so a spelling that greps true from the wrong list, a
  commented-out line, or a deleted flag all still fail loudly.

### Fixed — customer onboarding walls
- **Why:** walking the README's own setup path on a machine with no prior
  clone hit a wall at nearly every step: the install URL named the
  operator's private org; the doc told a new user to type `python -m cs
  init` when the console script makes `cs init` the natural spelling; `cs
  whoami` with no engine configured raised a bare `RuntimeError` traceback
  instead of saying what to fix; `cs init` given a closed stdin (piped,
  headless, or a stray Ctrl-C) died the same way; the wizard's kernel-version
  default and the shipped `requirements.txt` template both pointed at a
  stale pin over an SSH URL a customer has no key for; and the wizard's
  example company and two templates still carried the operator's own brand
  or private repo.
- **What:** the README's install line and its "Versioning" pin both point
  at the public `malemi/cs-kernel` repository, and every `python -m cs …`
  example in prose is now the bare `cs …`. `cs whoami` and every other verb
  whose auth resolution hits a missing `CS_ENGINE_OWNER_UID` /
  `FIREBASE_WEB_API_KEY` now raises the new `cs.config.ConfigError`, caught
  at dispatch in `cs/cli.py` and printed as one stderr line with exit 1 — no
  traceback. `cs init` catches `EOFError` (exhausted stdin) and
  `KeyboardInterrupt` around the prompt loop, exiting 1 / 130 with a
  one-line message; its own argparse `SystemExit` is now propagated by its
  real code instead of being flattened to 1, so `--help`/`--version`
  correctly exit 0. `--version` reads the installed package's own metadata
  instead of a string hardcoded at `0.2.0`. The generated `requirements.txt`
  installs over anonymous HTTPS from the public repo instead of SSH, the
  wizard's kernel-version default tracks the release being cut, the
  wizard's example company is now the neutral `Acme Corp`, and the two
  templates that named the operator's product or private repo now render
  from `company_name` or say "your private repository" instead.

### Changed — the charter's literal gate becomes a reviewed registry
- **Why:** the anti-fork grep in `tests/run.sh` step 1 was all-or-nothing:
  any wordlist hit failed the gate outright, with no way to record that a
  hit is there on purpose — the kernel's own public install URL has to name
  `malemi` somewhere, and the old gate had no way to say so without
  weakening the pattern itself.
- **What:** step 1 runs the same wordlist scan (now also catching
  `hahnbanach`, the operator's GitHub org, found in a stale
  `requirements.txt.j2` URL and a private-repo mention in the projects
  README — both fixed) but a hit is no longer an automatic failure. Every
  hit is checked against the new `tests/reviewed_literals.txt`, a versioned
  registry of `path :: exact line :: reason` entries the operator has
  explicitly approved; an unmatched hit prints as `NEEDS REVIEW` and still
  fails the gate, as a proposal rather than a silent pass. The registry
  currently holds one entry: `malemi` in `requirements.txt.j2`'s install
  URL, approved because it names the kernel's own public home, identical
  for every clone.

### Changed — `cs update` no longer touches the operator's pin or silently overwrites security-critical templates
- **Why:** `cs update` used to treat `requirements.txt` as an ordinary
  render target, but it is the operator's own installed pin, not
  kernel-owned state ("upgrades are a pin bump + pip install, never a
  cherry-pick" — CLAUDE.md's Versioning & release section). And two of the
  rendered files carry the draft-only send-guard invariant itself
  (`.claude/settings.json`, `bin/cs_operator_cron.sh`); gating their update
  behind the same interactive "overwrite?" prompt as any other template
  means a headless run, or an operator answering "no" out of habit, can
  leave a clone running a stale deny list.
- **What:** `cs update` now reports that `requirements.txt` exists and
  leaves it alone unconditionally — never rewriting or re-pinning it. The
  two security-critical templates apply the new render unconditionally on
  conflict, back up the operator's previous local version next to it, and
  print what changed so the operator can re-apply any local edit by hand,
  replacing the ordinary conflict prompt for exactly these two files.

### Fixed — `cs update` no longer crashes at a conflict prompt without a tty
- **Why:** the template-conflict prompt (`Overwrite? [y/N/diff]`) read its
  answer with a bare `input()`. A headless run (agent, cron,
  `stdin </dev/null`) has no tty: `input()` raised EOFError and the whole
  `cs update` died with a traceback mid-run — hit live 2026-08-04 during the
  v0.5.1 re-pins (worked around by piping `N`). Depending on file order the
  crash could leave a clone half-updated.
- **What:** both conflict prompts resolve EOF to the default the prompt
  itself declares — `n`, keep the local file — and print the decision
  (`(no tty — keeping local file)`). Gate 16 (`tests/test_project_update.py`)
  characterizes the helper AND proves the real `python -m cs update`
  subprocess with closed stdin against a manufactured conflict: exit 0,
  local file byte-identical, decision named in the output.
- **Re-collaudo:** **static, every clone** — only the clone-maintenance
  verb's prompt handling changes; no operator surface, no send path. Picked
  up at the next re-pin.

### Re-collaudo (this release)
- **Full, both clones.** Any one of the four items above touching the
  permission surface — the deny/allow spelling enumeration, the charter's
  reviewed-literal registry, or the security-critical apply-on-conflict
  path — is enough to require it on its own; together they put `v0.5.2`
  squarely behind the charter's full-tier bar for a behavior change. It
  does not go operational on either clone until the full collaudo suite is
  green on both — the same bar the two known clones cleared for `v0.5.1`.

## v0.5.1 — 2026-08-03 (corrective release)

### Fixed — cs task closes carry the external operator audit identity
- **Why:** the engine RPC accepts additive `actor`/`why` fields, but
  `cs tasks close` still sent only `task_id`/`note`; every operator close was
  therefore stored as the engine's backward-compatible default actor `human`.
- **What:** the kernel consumer now sends `actor="operator"` and a non-empty
  `why` on every close. A supplied `--note` remains the display note and is also
  the audit reason; a no-note close uses a stable kernel-owned reason. The
  consumer gate asserts the exact payload in both shapes.
- **Compatibility:** requires engine commit `677e319` plus the follow-up close
  history repair `1367e71` — both deployed to the five live daemons 2026-08-03.
  The older strict engine rejects `actor`/`why` as unknown parameters; rollout
  is engine first, kernel second, operators last.
- **Re-collaudo:** **full, every clone** — exercise a task close through the real
  engine and verify `close_actor="operator"` plus the persisted close reason.

### Fixed — release metadata agrees before the next tag
- **Why:** tag `v0.5.0` was cut while `pyproject.toml` still declared `0.4.5`,
  the active context still called `v0.4.0` the tip, and this changelog's
  `v0.5.0` entry was a placeholder. An install from that tag would therefore
  report the old package version. The two known clones remain independently
  verified at declared/locked/local-installed `v0.4.5`; their live daemon
  revisions are still unknown.
- **What:** package metadata advances to `0.5.1`, and a release-consistency gate
  (`tests/test_release_consistency.py`) asserts four things instead of describing
  them: the pyproject version owns a changelog section with a real body and a
  re-collaudo tier; the company-literal grep `tests/run.sh` **executes** carries
  every charter token plus the case-sensitive `\bHB\b` leg (a token left in a
  comment no longer counts); `docs/active-context.md` separately names the latest
  semver release and current HEAD's tagged/untagged state; and every
  `cs-kernel@vX.Y.Z` line in `README.md` is either the package version or the
  operational pin recorded at the top of this file. It reads repo files plus
  local git refs — no network. The published `v0.5.0` target is pinned by commit
  id so a force-move fails even if prose moves with it.
- **Re-collaudo:** same as `v0.5.0` below. Metadata and docs alone are static,
  but the cumulative upgrade crosses the model-output send chokepoint and
  therefore requires **full collaudo** on every clone before adoption.

## v0.5.0 - 2026-08-01

### Fixed — model output is guarded at the send chokepoint
- **Why:** a campaign path could pass model deliberation/meta text to SMTP.
  Guarding one caller was insufficient because another model-composed path
  could reach the same wire.
- **What:** deterministic register/tell checks now run in `send_mail.send` for
  model-composed bodies before any SMTP connection opens. The optional LLM
  register judgment degrades loudly to deterministic checks if unavailable;
  deterministic refusals never degrade. Fixed human-authored templates retain
  their existing path.
- **Draft behavior:** model-composed Gmail drafts are not blocked, because the
  draft is the review surface. They carry explicit guard warnings through the
  verb's JSON response; human/template drafts do not invoke the judgment leg.
- **Also fixed:** `classify_detailed` forwards the requested temperature.
- **Re-collaudo:** **full, every clone** — this changes the final send boundary
  and draft response surface. Prove refusal opens no SMTP socket, legitimate
  replies still reach the fake transport, warnings reach draft output, and the
  clone's pause/rate/dedup/stamp invariants remain green. No automated real send.

## v0.4.5 — 2026-07-31

### Fixed — memory-write docs authorized a tool the engine never calls
- **Why:** the engine's write call for memory is `update_memory`, but three
  templates (clone `CLAUDE.md` §9, the `customer` skill, `docs/projects/README.md`)
  prescribed `cs chat --allow create_memory` alone. `--allow` matches by exact
  name, so the gate denied the write with a polite conversational refusal — no
  error, no non-zero exit — and the fact was silently lost. Hit live 2026-07-31
  on the reference clone; verified both ways (single name → `update_memory ->
  deny`, nothing written; both names → write lands and `cs ask` reads it back).
- **What:** every prescription becomes `--allow create_memory,update_memory`,
  and the `customer` skill states the failure mode explicitly: a wrong tool name
  does not raise, so never trust the absence of an error — always verify with
  `cs ask`. Placeholders on the touched lines moved to English.
- **Re-collaudo:** static, every clone — three templates, picked up by
  `cs update`. The reference clone (mrcall-cs) is already hand-patched, because
  its `.claude/` adoption is deferred and `cs update` would not re-render those
  files there.

## v0.4.4 — 2026-07-31

### Fixed — the clone CLAUDE.md did not know two of its own verbs
- **Why:** §2 is the verb list every agent session loads, and it still ended at
  `cron`. `project` (v0.4.1) and `llm` (v0.4.0) were missing, so the capability a
  session needs in order to write a project's memory was invisible to the very
  file that is supposed to advertise it — the same failure mode the project-memory
  work exists to prevent. The `--account` refusal added in v0.4.1 was also absent,
  leaving an agent to discover it by hitting the exit-2.
- **What:** §2 lists both verbs and states the `--account` constraint plainly:
  the Gmail-IMAP verbs refuse on a non-default account, `thread` / `ask` are the
  engine-backed alternatives.
- **Re-collaudo:** static, every clone — one template, picked up by `cs update`.

## v0.4.3 — 2026-07-30

### Fixed — `cs update` stripped a clone's runtime ignores and staged its lock files
- **Why:** `cs update` rewrites `.gitignore` wholesale from the template. A clone
  that had added its own ignores for runtime artefacts — flock sidecars written
  next to a state file, and an acceptance-test fixture — lost them on the next
  update, and those files then showed up staged for commit. Hit on a real clone
  2026-07-30, where a schedule CSV's `.lock` and a test fixture were about to be
  committed as if they were project data.
- **What:** the patterns move into the template, where `cs update` preserves them:
  `*.csv.lock` for the sidecars, and `_*.csv` for the underscore-prefixed fixture
  convention (a file that must never be mistaken for real state).
- **Re-collaudo:** static, every clone. `.gitignore` only.

## v0.4.2 — 2026-07-30

### Fixed — templates recommended the very call the new `--account` guard refuses
- **Why:** v0.4.1 made `contacted` / `unanswered` / `dossier` / `draft-reply`
  refuse a non-default `--account` instead of answering about the operator's own
  mailbox. That exposed two templates telling an agent to do exactly that: the
  clone `CLAUDE.md` §9 and the `customer` skill both used
  `cs --account <other> dossier <email>` as their key-contacts step, which is now
  an exit-2 dead end on the account where most business relationships actually
  live.
- **What:** both use `thread` there — engine-backed, honours `--account` — and
  say plainly that `dossier` is the fuller check but only on the operator's own
  mailbox. Adds the `company/team-conventions.md` slot the triage skill
  references, so that pointer is no longer dangling: it records who replies from
  which mailbox, i.e. what the Sent-archive checks structurally cannot see.
- **Re-collaudo:** static, every clone. Template-only plus one new prose slot;
  no code path changes.

## v0.4.1 — 2026-07-30

### Added — `cs project new`: the per-project written memory, identical in every clone
- **Why:** every clone keeps a folder per company under `docs/projects/`, and that
  folder is the operator's memory of the relationship — what is agreed, what we
  owe, what happened, who these people are. Until now its shape was a paragraph
  of prose in `docs/projects/README.md`, and prose drifts the moment somebody is
  in a hurry. The failure that prompted this: a live prospect whose folder held a
  dossier and nothing else. Three weeks of drift sat outside it — two further
  meetings, a new counterpart who had become the project manager, a first project
  that had moved to a different business unit, and three deliverables with a
  deadline. All of it existed only in one person's head and in an unread mail. A
  convention cannot fail loudly; a missing folder structure looks exactly like a
  quiet project.
- **What:** a new verb group, `cs project new <slug> [--title …]`, stamping four
  artifacts from `cs/templates/project_memory/`:
  - `README.md` — what the project is, plus the index of its own files
  - `status.md` — the ONLY file describing the present: agreed scope, what we owe
    with dates, who decides, live risks. One home for state, so two files cannot
    disagree about it
  - `timeline.md` — what happened, when, and how we know, one source per entry;
    append-only, because a timeline's value is showing what we believed at the time
  - `meetings/` — one file per meeting, append-only with dated addenda, plus a
    `.gitkeep` so the append-only half of the scaffold survives a commit

  Every stamped file opens with front matter and an `## Abstract`, mirroring the
  `docs/` harness so a reader decides in ten seconds whether to read on. Bodies
  are HTML comments saying what belongs where rather than prose pretending to be
  content: an empty section is honest, invented content is not.

  `docs/projects/README.md.j2` is rewritten to specify the shape, the reliability
  markers (`[confirmed] [mail] [meeting] [inferred] [reported] [to verify]`), the
  append-only rule, and the division of labour between the files and engine
  memory — the engine owns live mail and is ground truth for it; the files own
  judgment, which never arrives by mail and therefore exists only if written
  down. New sibling `docs/projects/_meeting-template.md.j2` is the copy-me shape
  for a meeting note, including a "Not recorded here" section, because a note
  that hides its own gaps gets mistaken for the whole truth.

  It also records one trap found while using the verbs on a real prospect: `cs`
  must run from the clone root, since the manifest and env chain resolve from the
  working directory. The other trap that session surfaced — `--account` on the
  Gmail-IMAP verbs — is fixed in code below rather than documented.

  Templates live in a root of their own (`templates/project_memory/`, with its own
  `package-data` glob) because they are stamped per project by this verb, not once
  per clone by `cs init`. New gate `tests/run.sh` step 13 runs the verb against
  the fresh-venv install — proving the templates are packaged — and asserts
  abstract-first front matter, zero unrendered Jinja reaching a clone, the date
  taken from the manifest timezone rather than UTC, the founder-sweep mailbox
  owning the project when that sweep is on, refusal of a non-slug name, refusal
  outside a clone root, and refusal on an existing folder **without modifying it**
  (clobbering a project folder destroys the only copy of a judgment).
- **Re-collaudo:** static, every clone. No send path, no engine call and no
  campaign code is touched; the verb only writes files under `docs/projects/`.
  Clones pick the convention up with `cs update`, which adds
  `_meeting-template.md` and refreshes `docs/projects/README.md` (asking first if
  the local copy was modified).

### Fixed — `--account` no longer answers about the wrong mailbox
- **Why:** `--account` switches the ENGINE profile and nothing else, but four
  verbs read or write the operator's own Gmail over IMAP on a single credential:
  `contacted`, `unanswered`, `dossier` and `draft-reply`. Passed another account
  they answered anyway, about the operator's mailbox. `cs --account <other>
  contacted <addr>` returned a confident "no" with exit code 1 — which reads as
  "never contacted", and that is the exact check that gates outreach. The same
  flag sent `draft-reply`'s Gmail Drafts APPEND to the wrong mailbox. Observed
  live 2026-07-30 while working a real prospect whose relationship sits on a
  non-default account.
- **What:** those four parsers are marked `reads_operator_mailbox=True`, and
  `main()` refuses before dispatch when `--account` resolves to a uid other than
  the configured owner — naming the constraint and pointing at `thread` / `ask`,
  which are engine-backed and do honour the flag. The default account is
  untouched, so the cron and every existing invocation behave exactly as before.
  Documenting the trap was the wrong fix: prose does not stop a wrong answer
  being acted on. Gate 13 asserts all four refuse with exit 2 and that the
  default account is not over-blocked.

- **On the ordering:** this work was written and committed before v0.4.0 landed
  on `main`, and carried the v0.4.0 number until the two met. It is renumbered
  here rather than the other way round because v0.4.0's changelog had already
  claimed that number, and because a tag cut from `main` after this merge
  contains both — the numbers describe the merge order, not two independent
  lines. While it stood alone on `main` it also carried a known-red gate 1
  (`cs/templates/project/CLAUDE.md.j2` hardcoded an engine host); v0.4.0's
  literal purge removes exactly that, so the gate is green again in the merged
  tree.

## v0.4.0 — 2026-07-30

### Added — the kernel can make its own LLM calls, and the provider is config
- **Why:** the kernel made **zero** LLM calls of its own: every generation went
  through the engine (`rpc.chat` → `chat.send`), whose provider is decided
  downstream and whose spend is the company's own Anthropic bill. That is right
  for anything a customer reads, and pure waste for a mechanical call — the
  batch-2 campaign pays a customer-facing model, routed through the engine's
  agent loop, to emit one structured line. Measured on the 61 real customer
  replies of that campaign against the prompt production actually runs
  (full method and per-item results in the A/B record, which quotes customer
  mail and therefore lives with the operator's own docs, never in this repo):
  on the calls both sides completed, `z-ai/glm-5.2` through a gateway matches
  the engine's accuracy exactly (56/58 each) at **3.1 s** instead of the
  engine's **33 s** median, for **$1.17 per 1000 calls** — while answering all
  61 calls where the engine's transport failed 3 of them (a 502 and two dropped
  connections), and never once writing a schedule the customer did not agree
  to, which the engine does once (a bare "ok" read as "now", scheduling a
  migration seven hours before the moment the customer was told).
- **What:** four new modules, no required dependency added.
  - `cs/model_catalog.py` — the model catalog is **fetched, not hardcoded**.
    `GET /v1/models` (no API key needed) gives every id, its ship date and its
    real per-token prices; 17 curated *families* map a product line to a glob,
    and `@family` resolves to that line's newest member at call time. Disk cache
    with a 24 h TTL, stale cache preferred over no catalog, static snapshot last.
    A hardcoded list is wrong within weeks: measured 2026-07-28, an
    eight-day-old curated list already named three superseded models and priced
    one of them 37% wrong.
  - `cs/model_config.py` — `Provider` / `Tier` / `Role` (exactly ONE role today,
    `CLASSIFIER`), `ROLE_TIER`, `TIER_FAMILIES` per provider, `model_for(role)`
    (`MODEL_<ROLE>` → `MODEL_<TIER>` → provider default, each of which may be a
    pinned id or an `@family`), `resolve_spec()`, `llm_env()` endpoint
    resolution over the SAME env chain as `Settings`, `route_direct()`,
    `token_rates` (live prices; unknown id → `None`, never a fallback price),
    `call_cost`, `check_connection`, `read_env`/`write_env`/`mask_key`.
  - `cs/llm_client.py` — `build_client()`: credential onto `api_key=`
    (`X-Api-Key`) for Anthropic vs `auth_token=` (Bearer) for a gateway, `""`
    base_url collapsed to `None`, `base_url` always passed explicitly, and the
    unchosen credential attribute nulled after construction so behaviour does
    not depend on the SDK version's env-resolution. `extract_text()` selects
    text blocks (never `content[0]`, which a leading `ThinkingBlock` breaks);
    `text_of()` checks `stop_reason == "max_tokens"` BEFORE reading the text —
    without which a reasoning model that spends its whole budget thinking
    returns a silent default instead of an error.
  - `cs/worker_llm.py` — `call` / `complete` / `classify` for single-shot
    mechanical work. No prompt text and no model id lives here: the caller
    supplies the prompt, the role resolves the model. Raises `LLMConfigError`
    *before* sending when a gateway-style id meets the Anthropic-direct wire,
    which otherwise surfaces as a bare 404 naming a model that exists and is fine.
  - `cs/rpc.py` — `chat(..., role=)`. A role-declared call MAY be served
    directly by the configured provider instead of the engine. Response shape
    unchanged. An empty `allow_tools` is deliberately NOT the signal: the
    campaign reply-composer and `cs draft-reply` also run tool-free and write
    the words a customer reads, so inferring "safe to route" from tool-freedom
    would route exactly the traffic the charter keeps on the engine.
  - `cs/cli.py` — `cs llm` (what the kernel resolves to now), `cs llm models`
    (the menu: family, newest member, ship date, real price, what it is for),
    `cs llm set <role|tier> <@family|id>` (validates before writing), `cs llm
    test`. Non-interactive so the same verbs work from a cron wrapper.
  - `cs/config.py` — `env_file_chain()` split out of `load()` so the dotenv
    layers have ONE definition, shared with `model_config.env_layers()`.
- **Charter:** the tier split *is* the safety boundary — worker only. Contextual
  and customer-facing generation stays an engine call (invariant §4), and no
  send path, `CS_PAUSE` check, or deny-list changes because a model got cheaper.
  No company literal enters `cs/`: model ids and family names are the same for
  every clone, and the endpoint, credential and per-role model come from env.
- **Config:** all optional, and **routing is off unless asked for**.
  `CS_LLM_ROUTE=direct` opts a clone into the provider path and is the kill
  switch (set it back to `engine` and the next cron tick is on the old path —
  no code change, no re-pin). On the direct path errors are LOUD by design:
  a broken provider config raises instead of silently falling back to the
  engine, so it cannot hide behind the very spend this path avoids. `CS_LLM_PROVIDER`, `CS_LLM_BASE_URL` (for
  OpenRouter this is `https://openrouter.ai/api` — the SDK appends
  `/v1/messages`; `/api/v1` 404s on an HTML page), `CS_LLM_API_KEY`,
  `MODEL_<ROLE>`, `MODEL_<TIER>`. With nothing set but an `OPENROUTER_API_KEY`
  present, the worker tier goes to OpenRouter.
- **Defaults:** LEAD `@claude-opus`, WORKER `@claude-sonnet`. Choosing a
  smaller model to save money is a decision that must be EARNED by a
  measurement on that role's real task; the A/B earns it for `CLASSIFIER`
  (`@glm`) and nothing else.
- **Dependency:** `anthropic>=0.107` is an **extra** (`pip install
  "cs-kernel[llm]"`), imported lazily — a clone that makes no kernel-side LLM
  call does not grow a dependency, and every other verb works without it.
- **Re-collaudo:** static for both clones — this adds modules, changes no
  existing behaviour, and nothing calls it yet (`role=` is opt-in and
  `CS_LLM_ROUTE` defaults to the engine). It becomes a full re-collaudo the
  moment a call site is wired, which is a SEPARATE, reviewed change.

### Fixed — the project templates carried the mother company's operator
- **Why:** the anti-fork gate greps for company hosts and slugs, but the
  operator's NAME is company data too, and it was invisible to the pattern.
  Found 2026-07-30: the founder's first name in 20+ places across the project
  templates (skills, README, `.env.example`), his personal mailbox as a search
  example, a real customer's name inside an incident note, and the engine host
  as a literal in `CLAUDE.md.j2` — every clone stamped for another company
  shipped all of it. Separately, four templates shared a
  `… | reject(…) | first` expression that CRASHES `cs init` under
  StrictUndefined for any clone with a single account: the minimal clone could
  not render its own CLAUDE.md.
- **What:** all operator/customer/host literals replaced with neutral prose or
  existing template variables (`engine_ws_url` was already prompted — the
  literal was just never converted); the single-account crash fixed in all four
  templates (with one account, the default account is the fallback). Two gates
  so neither returns: the step-1 grep now also matches the operator's name and
  mailbox (pattern updated in `CLAUDE.md` too — the two must stay identical),
  and a new step 12 renders EVERY template under `cs init`'s own jinja env in
  both account shapes and sweeps the RENDERED output for literals — the source
  grep cannot see a literal the template engine assembles.
- **Re-collaudo:** static, plus one `cs update` dry-run per clone to confirm
  the re-stamped skills read correctly. Behaviour of running clones is
  untouched — these files are only read at `init`/`update` time.

## v0.3.7 — 2026-07-25

### Fixed — an approved tool call deadlocked the client and hung every caller
- **Why:** `EngineClient._recv_loop` is the only consumer of the WebSocket, and
  it awaited the notification handler inline. `chat()`'s handler answers a
  `chat.pending_approval` notification by issuing `chat.approve`, and `call()`
  ends in `await asyncio.wait_for(fut, …)` — on a future only the receive loop
  can resolve. So the approve request went out, the engine really did run the
  tool, and every frame after it was buffered and never dispatched. Sixty
  seconds later the inner `wait_for` raised `TimeoutError` *inside* the receive
  loop; the `except (ConnectionClosed, CancelledError)` clause did not catch it,
  the receive task died silently, and the outer `chat.send` future was never
  resolved nor failed — the caller blocked until something killed it.
  Measured against the live engine 2026-07-25: `chat.send` returned in 43.2 s and
  the client, still not listening, was killed 106 s later. This is why
  `cs chat --allow send_draft` "sends but never returns", and why it also hit
  `cs ask` / `cs draft-reply`: the handler calls `chat.approve` even to DENY, so
  the deadlock fires on any gated tool regardless of the allow-set. It also left
  the engine holding a zombie turn per abandoned call.
- **What:** notification handlers are spawned with `asyncio.create_task` and
  tracked, never awaited inside the receive loop (the module docstring already
  promised exactly this: "a second call can be issued while a long-running one
  is still in flight"). Defence in depth: the receive loop now fails every
  pending future on ANY exception, not only on connection close, so a dead
  reader surfaces as an error instead of an indefinite hang; a failed handler is
  reported on stderr instead of at garbage-collection time; and `__aexit__`
  cancels outstanding handler tasks.
- **Re-collaudo:** full, every clone. This is the shared RPC path — `ask`,
  `draft-reply`, `chat`, and every campaign loop that talks to the engine.

## v0.3.6 — 2026-07-25

### Fixed — threading headers survived only for short Message-IDs
- **Why:** `In-Reply-To` / `References` are not in `email.policy.default`'s
  header registry, so they are folded as unstructured text: any Message-ID too
  long for one 78-column line came out RFC2047 encoded-word-mangled
  (`In-Reply-To: =?utf-8?q?=3C!=26!AAAA…?=`). The receiving client then saw no
  valid reference at all — the reply opened a NEW thread and our outbound
  carried no trace of the customer's message, which also breaks any
  "did we already answer this?" check that reads `References` back. Measured on
  the live support@ mailbox: 2 of the 25 batch-2 contacts who wrote have an
  inbound Message-ID over 78 chars (105 and 85), so v0.3.5's threading silently
  did nothing for them.
- **What:** `build_mime()` builds the message with
  `email.policy.default.clone(max_line_length=998)` (the RFC 5322 hard maximum).
  Both headers now come out verbatim on one line; `Subject` is still RFC2047-
  encoded for accents. Mapping the two headers to `MessageIDHeader` in a cloned
  `header_factory` was tried and rejected: it fixes `In-Reply-To` and silently
  truncates a multi-id `References` to the first id.

### Fixed — a delivered mail could be reported to the caller as a failed send
- **Why:** `send()` mirrors the message into Gmail Sent over a second IMAP
  session AFTER SMTP has accepted it. Only the `typ != "OK"` case was soft; an
  exception (IMAP login failure, throttling, a dropped connection) propagated
  out of `send()`, so a mail the customer had already received was reported as
  a failure. In a campaign loop that means the state write that follows a
  successful send is skipped, the operator is told the customer was not
  answered, and the next run sends a duplicate.
- **What:** the mirror moved into `_mirror_to_sent()`, which never raises —
  every failure writes one stderr warning saying the mail WAS delivered. Only
  the SMTP phase may raise, which is what the docstring always promised.

### Re-collaudo
- Every clone that sends mail: static tier. `mrcall-cs`: full — it is the clone
  whose conversational loop depends on both fixes.

## v0.3.5 — 2026-07-25

### Added — RFC threading headers on the cs-SMTP send path
- **Why:** every mail `send_mail.send()` produced was a NEW thread. A campaign
  loop that answers a customer's reply therefore opened a second conversation in
  their mailbox instead of replying inside theirs (live defect: the batch-2
  acknowledgement mails). Any clone whose operator answers customers wants this —
  rule of two, so it belongs here and not in a clone.
- **What:** `build_mime()` and `send()` take optional `in_reply_to` and
  `references`. `In-Reply-To` is set verbatim (the value is already an
  angle-bracketed `Message-ID`); `References` is set to `references`, falling back
  to `in_reply_to` when empty. Passing neither is byte-identical to v0.3.4 — no
  existing caller changes.

### Added — `gmail_archive.thread_with()`: the ground-truth conversation reader
- **Why:** the loop that decides what to answer must read the mailbox itself. The
  engine's search could not surface the body of a real customer reply for 31+
  hours (`emails.search` depends on sync state), which froze a live campaign
  contact. IMAP has no such dependency. The existing readers return headers only,
  so nothing in the kernel could hand a customer's actual words to the composer.
- **What:** `thread_with(settings, addr, limit=20) -> list[dict]`, newest first,
  one read-only IMAP session (`BODY.PEEK`) over All Mail, matching `OR FROM TO`
  so it covers both directions. Each row carries
  `date / from_addr / outbound / subject / message_id / references / body /
  attachments`. `text/plain` wins; an HTML-only mail is tag-stripped with the
  stdlib `html.parser` (never a regex — the text is fed to a model that then
  answers a customer); bodies are whitespace-normalised and truncated at 4000
  chars; attachment parts contribute FILENAMES only, never base64.
- **DRAFT-FREE:** All Mail also holds unsent drafts, and Gmail marks them only
  with the `\Draft` X-GM-LABEL — the IMAP `\Draft` FLAG is NOT set, so an
  `UNDRAFT` search does not exclude them (verified 2026-07-25 against the mother
  clone's mailbox). They are dropped: a queued draft is a mail the customer never
  received, and feeding it back as something "we wrote" would ground a reply in a
  conversation that never happened. On a non-Gmail IMAP server the labelled FETCH
  degrades to a plain one instead of failing.

### Changed — header FETCH now asks for `REFERENCES` and `IN-REPLY-TO`
- `_hdr()` and `_fetch_headers()` add both fields, so a caller can thread a reply
  from any of the existing header readers, not only from `thread_with`.

- **Re-collaudo:** `mrcall-cs` (batch-2 Centralix→Vonage conversational loop) —
  full (live send + live IMAP read). Other clones: static — the two send-path
  parameters are optional and default to the v0.3.4 behaviour, and `thread_with`
  is purely additive.
- **Known pre-existing gate failure (not introduced here):** `tests/run.sh` step 1
  (company-literal grep) has been red since v0.3.2 — `cs/templates/project/
  CLAUDE.md.j2:52` names the mother clone's engine host. Every other step passes.

## v0.3.4 — 2026-07-22

### Fixed — `send-first` no longer dedups against the whole Sent archive
- **Why:** v0.3.3 shipped `send-first` with the composed-draft `send-draft`
  dedup (refuse if the address has ANY Sent thread within `dedup_days`). Wrong
  for a fixed-template first notice: that targets a **curated contact list** (a
  migration warning to KNOWN customers, many of whom have recent support threads
  with us), so the archive dedup would silently skip legitimate targets.
- **What:** `send-first` drops the `_sent_threads_to` check. Idempotency is now
  the contact `state` alone — once the notice goes out the state flips to `sent`
  and a re-run refuses; send-then-mark (the sub-second crash window is far less
  bad than skipping a warning). No change to `send-draft`/`send-reminder`.
- **Re-collaudo:** `mrcall-cs` (batch-2 campaign) — full (live send). Others: none
  (only the just-added `send-first` changes).

## v0.3.3 — 2026-07-22

### Added — `campaign send-first`: the first-notice sender the fixed-template lifecycle was missing
- **Why:** the fixed-template lifecycle (`send-reminder` / `send-sms`) only ever
  drove contacts **already in `sent`** — the *first* notice was sent by a prep
  one-off (June's `migration_loop.py`), never by a kernel verb. `send-draft`
  (composed-draft) can't stand in: it renders the body as **markdown**, which
  mangles call-forwarding dial codes (`**004*<num>#` → bold). So a campaign
  whose first mail needs real HTML had no sanctioned kernel path.
- **What:** `cs campaign send-first <contact_id> [--commit]` →
  `campaign.send_first`. Mirrors `send_reminder` but renders the PACK's
  `builders.build()` (first-notice copy, hand-built HTML) and marks the contact
  `sent`. `CS_TRIAGE_MODE=draft` → append the rendered mail (HTML) to the
  operator's Gmail Drafts for review (idempotent, never sends); `=send` →
  cs-SMTP send then mark `sent`. Gates: pack required (loud refusal), contact
  NOT already `sent`, **Sent-archive dedup first** (never re-mail), `CS_PAUSE`,
  `RATE_CAP` (send path).
- **Re-collaudo:** `mrcall-cs` (batch-2 Centralix→Vonage campaign uses it) — full
  (live send). Other clones: static (new additive verb, no behaviour change to
  existing verbs).

## v0.3.2 — 2026-07-21

### Fixed — the hidden templates (`.claude/*`, `.env.example`, `.gitignore`) were broken stubs; re-derived from the reference clone
- **Why:** v0.3.1 shipped the hidden templates into the wheel, but they were
  stripped/corrupt stubs from the initial extraction:
  - `.claude/settings.json.j2` rendered **invalid JSON** (a literal `n` where
    `\n` belonged);
  - `.gitignore.j2` **dropped the secret-ignore patterns** (`firebase-sa.json`,
    `*-sa.json`, `*.pem`, `*.key`, `*.db`) — a real security risk if adopted;
  - `.env.example.j2` concatenated two vars onto one line and dropped
    `SELF_UIDS`/`SELF_EMAILS` + guidance comments;
  - `.claude/commands/cs-review.md.j2` had a `.venv`→`.venor` typo + a hardcoded
    title; `munchausen.md.j2` was a placeholder stub;
  - `.claude/skills/triage-support-mail/SKILL.md.j2` had **lost §1 (the
    deterministic `cs unanswered` Sent-anchored sweep) and §1b (engine
    task-ledger reconcile)** + mangled headers;
  - `.claude/skills/{customer,find-document}/SKILL.md.j2` rendered an **empty
    `--account`** for founder_sweep-off clones (unconditional
    `{{ founder_sweep_account }}`).
- **What:** re-derived all 11 hidden templates from the reference clone
  (`mrcall-cs`), parameterised by flat config keys + a `founder_sweep`-gated
  `nondefault_account`. Verified: `render(kernel, manifest(mrcall-cs)) ≡ mrcall-cs`
  **byte-for-byte** for 9/11 (customer/find-document intentionally keep neutral
  example placeholders — see residuals), `settings.json` is valid JSON for both
  clones, `.gitignore` carries every secret pattern, triage §1/§1b restored, and
  both reference clones render with **zero StrictUndefined**. Independently
  reviewed (adversarial pass): **GO**. Also fixed the `keep_trailing_newline=False`
  gotcha (templates end with a double newline to emit one).
- **Known residuals (non-blocking, tracked):** `customer`/`find-document` keep
  neutral example placeholders — baking the mother clone's real customer names
  into the shared template would leak them to every clone; `campaign-tick` still
  emits the `Ciao MrCaller!` product-autoresponder example in a non-mother
  render (needs a future `manifest` field for company autoresponder signatures).
- **Clones must re-collaudo:** full tier — this makes `.claude/` safely
  template-ownable. Re-pin to `v0.3.2`, `cs update` to adopt `.claude/`
  (reconcile skill content as with CLAUDE.md), re-verify.

## v0.3.1 — 2026-07-18

### Fixed — hidden templates (`.claude/`, `.env.example`, `.gitignore`) were missing from the wheel
- **Why:** `[tool.setuptools.package-data] cs = ["templates/project/**/*"]` — the
  `**/*` glob does not match dot-prefixed files/dirs, so a wheel-installed kernel
  shipped `templates/project/` **without** `.claude/` (skills/commands/settings),
  `.env.example.j2`, `.gitignore.j2`. A clone stamped via `cs init` from the wheel
  would be missing its skills/commands/settings + `.env.example`/`.gitignore`, and
  `cs update` could not manage them (they aren't in the installed package).
- **What:** add explicit `templates/project/.*` + `templates/project/.claude/**/*`
  package-data patterns. Verified the built wheel now contains all 9 `.claude/*`
  templates + the two root dotfiles.
- **Clones must re-collaudo:** static tier (packaging-only; no code behavior change).
  Re-pin to `v0.3.1`; to bring `.claude/` under `cs update`, re-run `cs update` (it
  will now surface the `.claude` templates — reconcile skill content as with CLAUDE.md).

## v0.3.0 — 2026-07-17

### Added — the clone `CLAUDE.md` is now templated; `docs/customers` → `docs/projects`
- **Why:** the clone `CLAUDE.md` was NOT templated — each clone hand-maintained
  it, so it drifted from the kernel and a shared change had to be copied into
  every clone by hand. And `docs/customers/` is really "per-project working
  folders", not only customer dossiers.
- **What:**
  - New `cs/templates/project/CLAUDE.md.j2` — the clone operator manual is now
    kernel-owned and parameterised (flat config keys). Company-specific
    engine/API notes stay in the `company/claude-extra.md` slot (CLAUDE.md points
    to it; NOT inlined — `cs update` renders with `from_string`/no loader, so
    `{% include %}` is unavailable). Adds an **"Editing this clone —
    template-owned vs clone-owned"** section.
  - Template dir `docs/customers/` → `docs/projects/`; its README rewritten in
    English; the `customer` skill + `docs/ARCHITECTURE.md.j2` reference
    `docs/projects/`.
  - New config key `repo_docs_shape` (`collect_config` prompt, default
    `generic`) — distinguishes the mother clone from stamped children in the
    intro line.
  - Founder-sweep clause no longer appends a stray `@` (account names are full
    mailbox addresses).
- **Verified:** rendered `CLAUDE.md.j2` for BOTH reference clones with the real
  `project_init` Jinja env (`StrictUndefined`) — zero errors;
  `kernel + manifest(mrcall-cs)` is byte-equivalent to the mother's current
  CLAUDE.md except the intended changes; `kernel + manifest(124)` renders 124's
  values with no MrCall literals leaked.
- **Clones must re-collaudo:** full tier — CLAUDE.md/docs become template-owned.
  Adoption also needs each clone onboarded to template management
  (`template-manifest.json`); neither reference clone has one yet, so
  `cs update` cannot pull this until that follow-up lands.

## v0.2.3 — 2026-07-17

### Added — `cs tasks create` / `cs tasks close` + triage reconciles the sweep against the engine ledger
- **Why:** the deterministic `cs unanswered` sweep only sees support@'s own
  Gmail Sent folder, so an item answered from a DIFFERENT mailbox (e.g. Mario's
  personal `mario.alemi@` account) still gets re-flagged as unanswered
  (incident 2026-07-17: Eva Fani). And when the engine's own detection never
  turned a real inbound into a task, the operator had no write-path to record it.
  We need a place to record "handled" / "seen" that the sweep can reconcile
  against: the engine task ledger.
- **What:** `cs tasks` becomes a verb-with-subactions. Bare `cs tasks` is
  unchanged (the open-task list). New:
  - `cs tasks create --email E --title T --event-id ID [--event-type email]
    [--name N] [--phone P] [--urgency medium] [--reason R] [--suggested-action S]
    [--thread-id TID] [--json]` → `tasks.create` (upsert on
    owner_id+event_type+event_id — idempotent; `sources` carries the event id(s)
    and, when given, `thread_id`).
  - `cs tasks close TASK_ID [--note NOTE] [--json]` → `tasks.complete`.
- **Triage skill:** `triage-support-mail` now reconciles each sweep survivor
  against the ledger by `contact_email`: OPEN task → work it; CLOSED task →
  SKIP (already handled, possibly elsewhere); NO task → `cs tasks create` so the
  desktop sees it, then work it. `cs tasks --json` returns OPEN tasks only; the
  operator passes `cs rpc tasks.list '{"include_completed":true}'` to see closed.
- **Guard:** `tests/test_tasks_verbs.py` (gate 10 in `tests/run.sh`) pins the
  RPC method + params for both subactions; the help tree gate now covers
  `cs tasks create|close --help`.
- **Engine dependency:** relies on the engine RPCs `tasks.create` /
  `tasks.complete` (already live + tested on the support@ daemon).
- **Clones must re-collaudo:** full tier — this adds verbs the triage skill now
  depends on. Re-pin to `v0.2.3` and run one live `cs tasks create` +
  `cs tasks close` round-trip against the clone's engine.

## v0.2.2 — 2026-07-16

### Added — deterministic `cs unanswered` sweep (replaces a flaky LLM discovery)
- **Why:** the triage skill discovered "customer mail still needing a human
  reply" by asking the engine LLM (`cs ask "elenca la posta … senza risposta"`).
  That is NON-DETERMINISTIC — two runs of the same query returned different sets
  and missed real unanswered customer mail 6–13 days old that had no engine task
  (incident 2026-07-16). We need a sweep anchored to the Gmail Sent archive, no
  LLM in the discovery loop.
- **What:** new `cs unanswered [--days 14] [--json]`. Enumerates recent inbound
  (Gmail All Mail, **Date-header** windowed — never INTERNALDATE, which the
  engine sync re-touches and which made prior queries flip between runs) and
  subtracts every sender we've since written to (Gmail Sent = the dedup ground
  truth). A sender is OPEN iff no Sent message to them is dated after their last
  inbound. Excludes self (`SELF_EMAILS` + operator address), the new
  `CS_SYSTEM_SENDERS` ignore-list, and the `do_not_contact` suppression table.
  Returns oldest-first. It does NOT classify intent / autoresponders — that
  stays the LLM's job; over-inclusion is acceptable and filtered downstream.
- **New code:** `cs/gmail_archive.py` bulk readers `inbound_recent` /
  `sent_recent` (one IMAP session, batched header FETCH, read-only); pure,
  unit-testable `cs/unanswered.compute_open` + IMAP-backed `open_threads`;
  `cs unanswered` verb in `cs/cli.py`.
- **New config:** `CS_SYSTEM_SENDERS` (comma-separated no-reply/system addresses
  to ignore), layered env/manifest like the other knobs, default empty. The
  clone declares its own system addresses in env/manifest — NEVER hardcoded in
  the kernel (charter grep gate).
- **Guard:** `tests/test_unanswered.py` (wired as gate 9 in `tests/run.sh`)
  exercises the open-logic on synthetic dicts.
- **Clones must re-collaudo:** full tier — this adds a verb the triage skill now
  depends on. Re-pin to `v0.2.2`, set `CS_SYSTEM_SENDERS` for the clone, and run
  one live `cs unanswered --days 14`, cross-checking a couple of hits against
  `cs contacted <email>`.

### Fixed — `cs init` crash, fake-optional prompts; `drive.py` i18n; license
- `python -m cs init` raised `NameError: name 're' is not defined` on every
  invocation — `re`/`sys` were imported only inside the `if __name__ ==
  "__main__"` guard, which the real `cli.py` entry point never executes.
  Moved both to top-level imports. Verified end-to-end in a clean venv: the
  full init flow now completes and renders the project.
- `prompt_input`'s `default=""` was overloaded to mean both "no default"
  (required) and "optional, blank is fine" — five prompts labeled
  `(optional)` / "or empty" actually rejected blank input and looped
  forever. `default=None` is now the "required" sentinel; `default=""`
  means what it says. Verified the same fields now accept blank input and
  the flow completes.
- Removed the stale `doc-startsession` / `doc-endsession` / `doc-intrasession`
  command templates so new clones stop inheriting commands retired
  kernel-wide (superseded by the globally-installed `mrcall-ai-kit`
  `doc-start` / `doc-end`).
- Translated `cs/drive.py`'s Italian CLI help/error strings to English.
- Added the MIT `LICENSE` (was undeclared despite the "License & status"
  README heading) and declared it in `README.md` + `pyproject.toml`.
- `cs init`'s Engine WS URL default is now a generic placeholder instead of
  `wss://desktop.mrcall.ai` (charter grep gate — this was the last company
  literal in `cs/`; the gate is green again).
- **Clones must re-collaudo:** static tier only — no behavior change on any
  operator verb; `cs init` / `cs update` and `cs.drive` output text are the
  only surfaces touched.

## v0.2.1 — 2026-07-16

### Fixed — `draft-reply` now lands in the operator's Gmail Drafts (was invisible)
- **Root cause:** `cmd_draft_reply` only ran the engine compose. The engine's
  `create_draft` is non-destructive, so it auto-executes even with the empty
  `allow_tools`, storing the draft in the ENGINE draft store (visible via
  `cs rpc drafts.list` / the desktop app) — but **never in the operator's Gmail
  Drafts**, the surface where review and sending happen. The operator saw an
  empty Gmail Drafts and concluded "nothing was drafted". Recurring bug: prior
  fixes only touched an installed copy, never this source, so `pip install` /
  re-pin wiped them every time.
- **Fix:** `cmd_draft_reply` now diffs the engine draft store around the compose
  call and APPENDs the freshly composed draft into Gmail Drafts via IMAP
  (`gmail_drafts.append_draft`, the same mechanism as `campaign queue-draft`),
  with the draft's real `to`/`subject`/`body`/`in_reply_to`/`references`. It
  fails loud (rc=1) if the composed draft has no recipient/body, and is a no-op
  mirror when the engine composed nothing (clarifying question / escalation).
- **Guard:** new `tests/test_draft_reply.py` (wired as gate 8 in `tests/run.sh`)
  fails the moment the Gmail-Drafts append is removed.
- **Clones must re-collaudo:** full tier — this changes the Phase-1 review
  surface. Re-pin to `v0.2.1` and re-run one live `draft-reply`, verifying the
  draft appears in the operator's Gmail Drafts (not just `cs rpc drafts.list`).

## v0.2.0 — 2026-07-12

### Added — project template + `cs init` / `cs update`
- `cs/templates/project/` — Jinja2 project skeleton (skills, commands, company
  prose slots, docs, bin, manifest, requirements). Includes the generic
  `/customer` skill.
- `cs init` — interactive clone generator: prompts → render → `git init` →
  writes `template-manifest.json` (init_data + sha256 checksums).
- `cs update` — selective re-apply of template changes; asks on local
  modifications; same Jinja env as init (`trim_blocks`/`lstrip_blocks`).
- Dependency: `jinja2>=3.1`. Package data ships templates with the wheel.

### Added — `cs cron`
- `cs cron install` / `uninstall` / `status` — manage the operator's crontab
  entry directly from the CLI (`cs/cron.py`), instead of hand-editing crontab
  per clone. (Documented 2026-07-14; shipped in the tagged v0.2.0 commit but
  missing from this changelog until now.)

### Collaudo (this release)
- StrictUndefined render of all 30 templates: 0 failures.
- init→update no-op on a throwaway clone: 0 updated / 0 skipped / 0 added.
- Existing verbs still resolve via editable install (`cs --help`).

### Re-pin impact
- Clones that only run operator verbs: optional re-pin (new surface only).
- Anyone adopting `init`/`update` or a fresh clone: pin `@v0.2.0`.
- Full collaudo tier: static (help tree grows by `init`/`update` early exit;
  they bypass manifest load). Live read-only verbs unchanged.

## v0.1.0 — 2026-07-09

Initial extraction of the shared kernel from the two specimens — A (the
mother clone) and B (the first child) — per the design brief
`cs-kernel-manifest-separation.md` (§5.1 winners table, §5.1b packs,
§3 ports, §4 manifest).

### Winners merged (debt variance resolved, one version survives)
- `campaign.py` — **A**: Gmail-Sent/All-Mail ground-truth dedup
  (`_sent_threads_to` / `_inbound_since` read IMAP via `gmail_archive`);
  B's engine-search dedup is deleted as fork drift (it is blind to
  hand-sent mail and drops threads when the customer replies last).
  B's generic excluded-campaign guard SHAPE kept; the value moved to
  `settings.excluded_campaign` (manifest).
- `gmail_archive.py` — **A (superset)**: `inbound_since()` + Message-ID
  fetch/emission restored for everyone.
- `send_mail.py` — **B shape**: From display name from
  `settings.email_from_name` (manifest `[company].from_name`); falls back
  to the bare address when unset.
- `config.py` — fused: B's 3-level env-file loader (platform → home →
  repo, later wins; platform path from the manifest), ONE
  `settings.state_dir` derived from the slug (kills the hardcoded path
  scatter: db, token cache, SA key, CS_PAUSE, operator log, Shopify token
  cache), `<PREFIX>_`/bare Shopify alias convention generalized
  (`[crm.shopify].env_prefix`).
- `cli.py` — A base; CRM block replaced by the port call; `prog=` and all
  identity prints from Settings.
- `rpc.py`, `filter.py`, `gmail_drafts.py`, `__main__.py` — byte-identical
  in both clones, adopted as-is (rpc gains a loud error on unconfigured
  ws_url, now that the kernel default is empty).
- `_time.py` — same helpers, timezone now a knob
  (`[knobs].timezone` → `local_hour/local_date/past_local_noon`).
- `auth.py`, `resolve.py` — Firebase app names fixed to neutral kernel
  constants (`cs-kernel-*`); docstrings de-branded.
- `state.py`, `review.py`, `drive.py` — paths/scope messages derived from
  Settings.
- `scripts/find_profile_uid.py` — **B**, generalized (SA key discovered by
  glob over `~/.*-cs/`, or `--sa`).

### New kernel modules
- `manifest.py` — `manifest.toml` (brief §4.2 schema) → pydantic →
  Settings overrides; `$CS_MANIFEST` override for sandboxes; missing
  manifest tolerated (bare `--help` works), invalid manifest fails LOUD.
- `crm/` — the CRM port (brief §3): `CrmCtx`/`CrmRow`/`CrmResult` envelope
  with `render_hints`; explicit registry (`starchat`, `shopify`, `none`);
  unknown adapter = loud startup error; `lookup` never raises; verdict
  stays CRM-agnostic. `starchat` = A's inline RPC refactored;
  `shopify` = B's `crm.py` generalized (token cache under
  `settings.state_dir`, env prefix from the manifest).
- `ingest/` — the producer port (brief §3.6): `mrcall-tracking` (A's
  subprocess; script/python paths from the manifest, no absolute paths in
  the kernel) + `none` (B's reply-only stub); `fetch` degrades to an
  empty well-formed worklist with a surfaced note.
- `campaign_pack.py` + generic senders (brief §5.1b, decided 2026-07-08,
  driver: the upcoming ~70-user migration): pack loader
  (`campaigns/<name>/campaign.toml` + `mail_first.md`/`mail_reminder.md`
  with a `Subject:` first line + `sms.txt` + optional `builders.py` hook +
  `playbook.md`), `cs campaign packs` discovery verb, and the
  `send_reminder`/`send_sms` handlers: pack template/builders →
  `send_mail`/`sms`, **stamp-before-send**, reply-check on Gmail ground
  truth, once/day + cap + window gates, CS_PAUSE, RATE_CAP. A
  fixed-template action with NO pack is refused loudly — the kernel never
  invents copy.
- `sms.py` — generic SMS via the manifest `[sms].proxy_base` proxy +
  `SMS_BUSINESS_ID`; raises `SmsError` with the reason (no silent False,
  unlike the one-off it replaces).

### Declared behavior deltas vs the specimens (for the migration registers)
- Dossier CRM section prints generically from `render_hints`
  (`-- CRM [starchat] (n) --` instead of the per-company header).
- `cs plan` surfaces a producer failure as a printed note over an empty
  worklist instead of a traceback.
- Identity strings in `contacted`/`dossier`/verdict lines derive from
  `settings.email_address` (same rendered bytes once the manifest is in).
- Reminder/SMS senders stamp the dossier BEFORE the send (the old one-off
  sent first); crash direction is now "skip one", never "send twice".
- New verbs: `campaign send-reminder`, `campaign send-sms`,
  `campaign packs`.

### Collaudo required
Both clones, FULL tier (send paths, campaign, gmail_archive, send_mail
all touched) — brief §6.6. B additionally lands the pre-declared B1/B2
dedup ground-truth switch.
