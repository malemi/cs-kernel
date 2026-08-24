#!/usr/bin/env bash
# Semantic gates for the cs kernel — the only tests that matter.
# Run from anywhere: resolves the repo root itself. CI runs exactly this.
#
#   1. grep gate           zero company literals in the package (charter §)
#   2. boundary greps      SMTP only in send_mail.py; drafts path SMTP-free
#   3. clean install       pip install into a FRESH venv; `python -m cs`
#                          resolves from site-packages with NO source dir
#                          on the path (the permission-string invariant)
#   4. full --help tree    every verb / sub-verb answers --help
#   5. config semantics    manifest + sandbox HOME -> derived paths, layering
#   6. pack loader         neutral trial pack: templates, builders, refusals
#   7. golden pack         env-driven byte-equality vs a clone's builders
#                          (CS_GOLDEN_REF_BUILDERS + CS_GOLDEN_PACK_DIR;
#                          skipped when unset — company data stays out of
#                          this repo)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0

step() { printf '\n== %s ==\n' "$*"; }

step "1. grep gate: zero company literals in cs/"
# Company / customer / product names — case-insensitive (catches CAFE124, Centralix, …).
# The wordlist below finds CANDIDATES, nothing more — it does not judge them.
# The operator's judgment, recorded with a reason in tests/reviewed_literals.txt,
# decides: an approved hit is green. Any hit NOT in that registry is a PROPOSAL
# for the operator's review and fails loudly until he approves it there or
# removes the literal. The registry is versioned, so every admission is a
# recorded decision, never a silent pass.
# \bmario\b|alemi: the operator's name and mailbox are company data like any other —
# they were found baked into 20+ places across the project templates (2026-07-30),
# invisible to the old pattern. A clone stamped for another company must not ship
# them without an on-record reason.
CI_HITS="$(grep -rEin --exclude-dir=__pycache__ 'mrcall\.ai|cafe124|124-cs|centralix|/home/mal|\bmario\b|alemi|hahnbanach' cs/ || true)"
# The 'HB' shared-drive literal is UPPERCASE — match it case-SENSITIVELY so the gate
# does not false-positive on the lowercase 'hb' path segment (e.g. ~/hb/…), which is
# a filesystem path, not the drive token. Same registry, same judgment pass as the
# case-insensitive wordlist above: an HB hit is a proposal too, not an auto-fail.
CS_HITS="$(grep -rEn --exclude-dir=__pycache__ '\bHB\b' cs/ || true)"
ALL_HITS="$(printf '%s\n%s\n' "$CI_HITS" "$CS_HITS")"
if ! ALL_HITS="$ALL_HITS" REVIEWED_LITERALS="$ROOT/tests/reviewed_literals.txt" python3 - <<'PYEOF'
import os

hits_raw = os.environ.get("ALL_HITS", "")
reviewed_path = os.environ["REVIEWED_LITERALS"]

hits = []
for line in hits_raw.splitlines():
    if not line:
        continue
    path, _, rest = line.partition(":")
    _lineno, _, content = rest.partition(":")
    hits.append((path, content))

approvals = []  # (path, content_stripped, raw_line)
try:
    with open(reviewed_path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = line.split(" :: ", 2)
            if len(parts) != 3:
                continue
            a_path, a_content, _reason = parts
            approvals.append((a_path.strip(), a_content.strip(), line))
except FileNotFoundError:
    pass

unapproved = []
matched_raws = set()
approved_hits = 0
for path, content in hits:
    content_stripped = content.strip()
    hit_match = None
    for a_path, a_content, a_raw in approvals:
        if a_path == path and a_content == content_stripped:
            hit_match = a_raw
            break
    if hit_match is None:
        unapproved.append((path, content_stripped))
    else:
        approved_hits += 1
        matched_raws.add(hit_match)

stale = [a_raw for (_, _, a_raw) in approvals if a_raw not in matched_raws]
for a_raw in stale:
    print("note: stale approval — %s" % a_raw)

if unapproved:
    for path, content in unapproved:
        print("NEEDS REVIEW: %s :: %s" % (path, content))
    print(
        "FAIL: %d unreviewed company-shaped literal(s) in cs/ — these are "
        "PROPOSALS, not confirmed violations: approve each by adding a "
        "'path :: line :: reason' entry to tests/reviewed_literals.txt, "
        "or remove the literal." % len(unapproved)
    )
    raise SystemExit(1)

print(
    "OK: no unreviewed company-shaped literals (%d approved hits in "
    "tests/reviewed_literals.txt)" % approved_hits
)
PYEOF
then
  FAIL=1
fi

step "2. boundary greps"
BAD="$(grep -rl --include='*.py' 'smtplib' cs/ | grep -v 'cs/send_mail.py' || true)"
if [ -n "$BAD" ]; then echo "FAIL: smtplib outside cs/send_mail.py: $BAD"; FAIL=1; else echo "OK: SMTP only in send_mail.py"; fi
if grep -q 'smtplib' cs/gmail_drafts.py; then echo "FAIL: gmail_drafts.py must be SMTP-free"; FAIL=1; else echo "OK: gmail_drafts.py SMTP-free"; fi

step "3. fresh venv install (python -m cs resolves from site-packages)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
VENV="$TMP/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" -q install --upgrade pip >/dev/null
if ! "$VENV/bin/pip" -q install "$ROOT"; then echo "FAIL: pip install"; exit 1; fi
EMPTY="$TMP/empty"; mkdir -p "$EMPTY"
if (cd "$EMPTY" && "$VENV/bin/python" -m cs --help >/dev/null 2>&1); then
  echo "OK: python -m cs --help from an empty dir"
else
  echo "FAIL: python -m cs --help"; (cd "$EMPTY" && "$VENV/bin/python" -m cs --help); FAIL=1
fi
# The suite otherwise only ever invokes `python -m cs`; the `cs` console
# script is a second entry point (pyproject.toml [project.scripts]) that
# resolves at invocation time, so a typo'd target (e.g. `cs.cli:mian`)
# installs fine and every other gate stays green. Exercise it directly.
if (cd "$EMPTY" && "$VENV/bin/cs" --help >/dev/null 2>&1); then
  echo "OK: cs --help (console script) from an empty dir"
else
  echo "FAIL: cs --help (console script)"; (cd "$EMPTY" && "$VENV/bin/cs" --help); FAIL=1
fi

step "4. full --help tree (every verb / sub-verb)"
HELPLOG="$TMP/help_tree.txt"
tree_fail=0
for v in init update login plan whoami rpc thread contacted unanswered tasks business dossier ask draft-reply draft-delete review drive accounts config chat campaign project; do
  if ! (cd "$EMPTY" && "$VENV/bin/python" -m cs "$v" --help >>"$HELPLOG" 2>&1); then
    echo "FAIL: cs $v --help"; tree_fail=1
  fi
done
for cv in list pending reconcile mark send-draft queue-draft send-reminder send-sms packs; do
  if ! (cd "$EMPTY" && "$VENV/bin/python" -m cs campaign "$cv" --help >>"$HELPLOG" 2>&1); then
    echo "FAIL: cs campaign $cv --help"; tree_fail=1
  fi
done
for tv in create close; do
  if ! (cd "$EMPTY" && "$VENV/bin/python" -m cs tasks "$tv" --help >>"$HELPLOG" 2>&1); then
    echo "FAIL: cs tasks $tv --help"; tree_fail=1
  fi
done
for pv in new; do
  if ! (cd "$EMPTY" && "$VENV/bin/python" -m cs project "$pv" --help >>"$HELPLOG" 2>&1); then
    echo "FAIL: cs project $pv --help"; tree_fail=1
  fi
done
if [ "$tree_fail" -eq 0 ]; then echo "OK: $(grep -c '^usage:' "$HELPLOG") usage screens"; else FAIL=1; fi

step "5. config + manifest resolution (sandbox HOME)"
if "$VENV/bin/python" "$ROOT/tests/test_config.py"; then echo "OK"; else FAIL=1; fi

step "6. campaign pack loader"
if "$VENV/bin/python" "$ROOT/tests/test_pack.py"; then echo "OK"; else FAIL=1; fi

step "7. golden pack equivalence (env-driven)"
if "$VENV/bin/python" "$ROOT/tests/test_golden_pack.py"; then echo "OK"; else FAIL=1; fi

step "8. draft-reply mirrors composed draft into Gmail Drafts (anti-regression)"
# The engine composes into its own draft store, NOT the operator's Gmail Drafts.
# cmd_draft_reply MUST APPEND the composed draft into Gmail Drafts or it is
# invisible to the operator ("draft not in Gmail" — a recurring regression).
if "$VENV/bin/python" "$ROOT/tests/test_draft_reply.py"; then echo "OK"; else echo "FAIL: draft-reply no longer appends to Gmail Drafts"; FAIL=1; fi

step "9. unanswered open-logic (deterministic Sent-anchored sweep)"
# `cs unanswered` replaced a NON-DETERMINISTIC LLM discovery query (incident
# 2026-07-16). This guards the pure open-logic: Sent-after-inbound closes a
# sender, Sent-before does not, self/ignore excluded, oldest-first ordering.
if "$VENV/bin/python" "$ROOT/tests/test_unanswered.py"; then echo "OK"; else echo "FAIL: unanswered open-logic regressed"; FAIL=1; fi

step "10. tasks create/close verbs write the engine ledger (params guard)"
# `cs tasks create` / `cs tasks close` are the triage sweep's reconciliation
# write-path (create-on-miss, close-on-handled). This pins the RPC method +
# params so a refactor can't drop sources / the event_id key / the close note.
if "$VENV/bin/python" "$ROOT/tests/test_tasks_verbs.py"; then echo "OK"; else echo "FAIL: tasks create/close params regressed"; FAIL=1; fi

step "11. provider swap (auth header, base_url, response shape, pricing)"
# The kernel's OWN LLM calls: credential on the right kwarg, no second auth
# header from an ambient env var, "" base_url not read as a custom gateway,
# ThinkingBlock skipped, max_tokens checked before the text is read, unknown
# model priced as None. Asserted against the ACTUAL installed anthropic SDK —
# "no new dependency" is not the same as "version-independent behaviour".
# Installing the [llm] extra here also proves the extra resolves.
if "$VENV/bin/pip" -q install "$ROOT[llm]" >/dev/null 2>&1; then
  if "$VENV/bin/python" "$ROOT/tests/test_llm_client.py"; then echo "OK"; else echo "FAIL: provider-swap semantics regressed"; FAIL=1; fi
else
  echo "SKIP: could not install the [llm] extra (offline?)"
fi

step "12. template render gate (StrictUndefined, single- and multi-account)"
# Every .j2 must render with cs init's own jinja env in BOTH account shapes —
# the single-account clone is the one that crashed — and the RENDERED output
# must carry no company literal (the source grep in step 1 cannot see a
# literal the template engine assembles).
if "$VENV/bin/python" "$ROOT/tests/test_template_render.py"; then echo "OK"; else echo "FAIL: template render gate"; FAIL=1; fi

step "13. project memory scaffold (cs project new)"
# The per-project memory shape is only uniform across clones because a generator
# stamps it. Guards: abstract-first + front matter on every stamped file, no
# unrendered Jinja reaching a clone, market-local date, and a REFUSAL on an
# existing folder (clobbering it destroys the only copy of a judgment).
# Runs against the fresh venv, so it also proves the templates are PACKAGED —
# templates/project_memory/ is a SECOND template root and gate 12 only walks the
# first one, so this is the only thing standing between it and shipping empty.
if "$VENV/bin/python" "$ROOT/tests/test_project_memory.py"; then echo "OK"; else echo "FAIL: project memory scaffold regressed"; FAIL=1; fi

step "14. model-output send guard (send_mail.send with body_md=)"
# The 2026-07-28 incident: a campaign loop mailed a customer the model's own
# meta-deliberation — deliberation paragraph, "here is the reply:", the reply
# between --- rules, and a closing question to the OPERATOR naming the
# customer's address. The gate asserts the offending body opens NO SMTP
# connection while a legitimate reply reaches the socket, so the guard is
# provably the only thing between generated text and the wire.
# Offline: the register-judgment leg runs against stubs; the LIVE provider leg
# is opt-in (CS_SEND_GUARD_LIVE=1) so this suite never spends a cent.
if "$VENV/bin/python" "$ROOT/tests/test_send_guard.py"; then echo "OK"; else echo "FAIL: model-output send guard regressed"; FAIL=1; fi

step "15. release metadata and docs consistency"
if "$VENV/bin/python" "$ROOT/tests/test_release_consistency.py"; then echo "OK"; else echo "FAIL: release metadata/docs drift"; FAIL=1; fi

step "16. cs update — EOF-safe conflict prompt (no tty crash); --check / --pin (discovery + explicit re-pin)"
# 2026-08-04: a headless `cs update` (agent, cron, `stdin </dev/null`) hit a
# template conflict and died with an EOFError traceback instead of applying
# the prompt's own declared default (keep the local file). Guards the helper
# AND a real `python -m cs update` subprocess against a manufactured conflict.
# Also guards two other conflict-branch decisions cmd_update makes headlessly:
# requirements.txt is the operator's pin and is always skipped, never asked
# about; SECURITY_CRITICAL templates (.claude/settings.json,
# bin/cs_operator_cron.sh) are never gated behind the prompt at all — the new
# render is applied and the local version backed up to <file>.local-bak.
# 2026-08-16 (Task 3): `cs update --check` / `--pin <tag>`, against a REAL
# local git repo standing in for the kernel's remote origin (git ls-remote
# and git show behave identically against a local path) — installed-vs-
# latest, the newer tag's re-collaudo tier read off ITS OWN CHANGELOG.md
# (never hardcoded), up-to-date and unreachable-origin both write NOTHING,
# --pin rewrites ONLY the pin line, and bare `cs update` is unaffected.
# 2026-08-21: a file whose stored checksum is stale but whose CONTENT already
# matches today's render (brought in sync by something other than cs update
# itself) used to hit the same "modified locally AND template changed" ask —
# confirmed live: the operator typed "diff" and saw NOTHING, since the diff
# is empty by construction. Now recognized and reconciled silently, no
# prompt at all.
if "$VENV/bin/python" "$ROOT/tests/test_project_update.py"; then echo "OK"; else echo "FAIL: cs update crashes on closed stdin at a template conflict, or --check/--pin regressed"; FAIL=1; fi

step "17. deny-enumeration gate (six command-text spellings, same deny)"
# Claude Code permission rules match command TEXT, not behaviour: the console
# script `cs` and the `python3` aliases invoke the exact same cs.cli:main as
# `.venv/bin/python -m cs`, so a deny-listed verb spelled only one way leaves
# the other five doors open. Presence alone is not enough — a spelling can
# grep true from the wrong list (allow instead of deny), from a line that got
# commented out, or after the --disallowed-tools flag itself was deleted, and
# all three still pass a file-wide `grep -qF`. This gate checks PLACEMENT:
# settings.json.j2 membership under permissions.deny (and nothing
# chat/send-draft-shaped under permissions.allow), and the cron's
# --disallowed-tools argument list compared for exact, order-preserving
# equality against the 24 deny entries + 4 keeps.
CRON_TPL="$ROOT/cs/templates/project/bin/cs_operator_cron.sh.j2"
SETTINGS_TPL="$ROOT/cs/templates/project/.claude/settings.json.j2"
if ! python3 - "$SETTINGS_TPL" "$CRON_TPL" <<'PYEOF'
import json, re, sys

SETTINGS_PATH, CRON_PATH = sys.argv[1], sys.argv[2]

SPELLINGS = [
    ".venv/bin/python -m cs",
    ".venv/bin/python3 -m cs",
    ".venv/bin/cs",
    "python -m cs",
    "python3 -m cs",
    "cs",
]
VERBS = ["chat", "rpc chat", "campaign send-draft", "rpc settings.update"]

problems = []

try:
    with open(SETTINGS_PATH) as f:
        settings = json.load(f)
except (OSError, json.JSONDecodeError) as exc:
    problems.append("FAIL: settings.json.j2 unreadable/invalid JSON: %s" % exc)
    settings = {}

deny = settings.get("permissions", {}).get("deny", [])
allow = settings.get("permissions", {}).get("allow", [])

for spelling in SPELLINGS:
    entry = "Bash(%s campaign send-draft:*)" % spelling
    if entry not in deny:
        problems.append("FAIL: settings.json permissions.deny missing %s" % entry)

for entry in allow:
    if "chat" in entry or "send-draft" in entry:
        problems.append(
            "FAIL: settings.json permissions.allow carries a send-capable entry: %s" % entry
        )

try:
    with open(CRON_PATH) as f:
        lines = f.readlines()
except OSError as exc:
    problems.append("FAIL: cron template unreadable: %s" % exc)
    lines = []

start = next((i for i, l in enumerate(lines) if "--disallowed-tools" in l), None)
if start is None or lines[start].strip().startswith("#"):
    problems.append("FAIL: cron template --disallowed-tools flag line missing or commented out")
else:
    end = next((i for i in range(start + 1, len(lines)) if '>>"$LOG"' in lines[i]), None)
    if end is None:
        problems.append('FAIL: cron template closing >>"$LOG" line not found after --disallowed-tools')
    else:
        tokens = []
        for line in lines[start:end]:
            if line.strip().startswith("#"):
                continue
            tokens.extend(re.findall(r'"([^"]*)"', line))
        expected = ["Bash(%s %s:*)" % (sp, v) for v in VERBS for sp in SPELLINGS]
        expected += ["Write", "Edit", "Bash(rm:*)", "Bash(git push:*)"]
        if tokens != expected:
            problems.append(
                "FAIL: cron --disallowed-tools token list mismatch (got %d, expected %d)"
                % (len(tokens), len(expected))
            )
            missing = [t for t in expected if t not in tokens]
            extra = [t for t in tokens if t not in expected]
            if missing:
                problems.append("FAIL:   missing: %s" % ", ".join(missing))
            if extra:
                problems.append("FAIL:   extra:   %s" % ", ".join(extra))
            if tokens != expected and not missing and not extra:
                problems.append("FAIL:   same members present, but order differs")

if problems:
    for p in problems:
        print(p)
    sys.exit(1)

print("OK: settings.json deny membership + allow purity; cron --disallowed-tools 28-entry order verified")
sys.exit(0)
PYEOF
then
  FAIL=1
fi

step "18. auth boundary — refresh-token exchange (handled ConfigError, cache short-circuit)"
# cs/auth.py mints via a Firebase refresh-token exchange (Secure Token API),
# not a locally-signed service-account custom token. Guards: a missing/
# mismatched refresh file raises a handled ConfigError naming `cs login`
# (never a raw traceback below the env-key layer); `_write_refresh` writes
# mode 0600; a still-valid cached id_token short-circuits before the
# refresh/exchange path is ever touched (proved by pointing
# refresh_token_path at a nonexistent directory); token-cache and
# refresh-token paths are now derived PER ACCOUNT UID, so a second account's
# session (`cs --account <name> login`) coexists with the primary's under
# the same state dir instead of overwriting it.
if "$VENV/bin/python" "$ROOT/tests/test_auth_boundary.py"; then echo "OK"; else echo "FAIL: auth boundary regressed"; FAIL=1; fi

step "19. cs login — descriptor parsing, profile scan, known-uid auto-select, identity cross-check, no-descriptor path"
# cs/login.py is the human verb that produces what cs/auth.py consumes (the
# stored refresh-token session). Guards, all network-free (the who_am_i
# proof call needs a live engine and is out of scope here): parse_descriptor
# accepts a valid fixture and rejects bad JSON / wrong version / each
# missing field by name; scan_descriptors finds real descriptors under a
# CS_ZYLCH_ROOT-rooted temp tree and does not choke on an invalid one next
# to them; a real `python -m cs login` subprocess with zero descriptors
# found exits 1 naming the mrcall-desktop app (closed stdin, never blocks);
# 2026-08-16 (Task 2): when the engine uid is already known, the matching
# descriptor among several is auto-selected with NO prompt (both prompt
# helpers stubbed to raise if called), and a known uid with no matching
# descriptor fails immediately naming the uid — never the numbered picker
# offering only wrong answers; the identity cross-check refuses a uid
# mismatch naming BOTH uids (built directly against a hand-built Settings,
# no config.load(), no network) and never relaxes it for `account_switched`;
# the email cross-check binds the PRIMARY profile only and is skipped
# exactly when `cs --account <name> login` deliberately selected a
# secondary account — proved end-to-end by a real `python -m cs --account
# founder login` subprocess that auto-selects and stores the session at
# that account's own per-uid path, contrasted with the same descriptor
# refused (known-uid no-match, nothing written) without --account.
if "$VENV/bin/python" "$ROOT/tests/test_login.py"; then echo "OK"; else echo "FAIL: cs login regressed"; FAIL=1; fi

step "20. rendered bin/ scripts are executable (cs init AND cs update)"
# A rendered file under bin/ (or sourced from a *.sh.j2 template) is a shell
# script the operator's crontab is told to invoke directly. render_templates
# used to write it with a bare write_text/write_bytes and never chmod —
# bin/cs_operator_cron.sh came out 0644, and the crontab line the docs tell
# the operator to install then failed SILENTLY with "Permission denied" (cron
# does not mail a traceback for a non-executable script). Guards both write
# paths: cs init's render_templates on a fresh render, and cs update
# restoring the executable bit on an existing clone whose wrapper had
# regressed to 0644.
if "$VENV/bin/python" "$ROOT/tests/test_render_permissions.py"; then echo "OK"; else echo "FAIL: rendered bin/ scripts are not executable"; FAIL=1; fi

step "21. rendered README hygiene (no example.com, no empty-var artifact, no Italian)"
# An adversarial UX review (2026-08) found the stamped clone's own README
# hardcoded desktop.example.com instead of {{ engine_ws_url }}, rendered
# visible garbage for the common case (excluded_campaign="" -> the literal
# 'The `` campaign is carved out...'), and shipped Italian strings ('Bozze',
# 'invia la bozza per X') inside an English-only artifact. Renders
# README.md.j2 through cs init's own jinja env in both the defaults shape
# and a fully-populated shape, and asserts none of the three families reach
# the render (and that the populated shape still renders the real bullets —
# the guard is a visibility toggle, not a silent feature delete).
if "$VENV/bin/python" "$ROOT/tests/test_readme_hygiene.py"; then echo "OK"; else echo "FAIL: rendered README carries a kernel-authoring leftover"; FAIL=1; fi

step "22. engine-unreachable — one clean line, never a raw traceback"
# Every engine-backed verb but `cs login` let ConnectionRefusedError escape
# cli.main() as a raw traceback when the mrcall-desktop app is not running —
# verified live: 'ConnectionRefusedError: [Errno 111] Connect call failed
# (127.0.0.1, 1)'. Configuration/environment absence is a product state, not
# a bug (charter). Guards: `cs whoami` against a closed local port (no real
# network egress) exits non-zero with ONE line naming the configured engine
# URL and the mrcall-desktop app, no "Traceback" on stderr; and the caught
# family stays narrow (OSError + websockets.exceptions.WebSocketException,
# never bare Exception) — a non-connection exception injected into the same
# verb still propagates uncaught, proving the fix cannot mask a real bug.
if "$VENV/bin/python" "$ROOT/tests/test_engine_unreachable.py"; then echo "OK"; else echo "FAIL: engine-unreachable error handling regressed"; FAIL=1; fi

step "23. cs --version — the top-level flag (Task 1)"
# Before this fix, `cs --version` exited 2 with an argparse usage dump
# demanding a subcommand — the version was only reachable as `cs init
# --version` / `cs update --version`, neither discoverable, and it is the
# first thing a newcomer or an operator verifying a re-pin actually types.
# Guards, real `python -m cs …` subprocesses, no manifest anywhere (must
# work on a bare install, exactly like --help already does): exits 0,
# prints "cs-kernel X.Y.Z" with no "usage:" fallthrough and no traceback;
# the string is byte-identical across the root flag and the two subcommand
# stubs — cs/_version.py is the one shared source, never a third copy of
# the same importlib.metadata try/except.
if "$VENV/bin/python" "$ROOT/tests/test_version.py"; then echo "OK"; else echo "FAIL: cs --version regressed"; FAIL=1; fi

step "24. cs init writes ~/.<slug>-cs/.env — one password typed, zero files hand-edited"
# README Step 3 used to be mkdir/cp/hand-edit a dotenv whose values the wizard
# already knew — the worst onboarding step for a non-technical operator.
# Guards on the REAL rendered .env.example: anchors filled (EMAIL_PASSWORD via
# getpass, FIREBASE_WEB_API_KEY from the Step-0 descriptor, CS_ACCOUNTS from
# the registry), file 0600 / state dir 0700 regardless of umask, an existing
# .env NEVER touched (operator-owned, no prompt shown), EOF on the prompt
# writes EMAIL_PASSWORD blank and prints the decision (v0.5.2 EOF contract).
if "$VENV/bin/python" "$ROOT/tests/test_state_env.py"; then echo "OK"; else echo "FAIL: cs init secrets writer regressed"; FAIL=1; fi

step "25. cs init offers to install the project — venv + pinned kernel, on explicit y"
# README step 3 used to be a hand-typed cd/uv venv/source/uv pip install —
# the wizard already has dest_dir and requirements.txt right there. Guards,
# subprocess.run stubbed (hermetic, no real venv/network): EOF/^C/"n" skip
# with the manual fallback printed and ZERO subprocess calls (the v0.5.2 EOF
# contract: never install without an explicit "y"); "y" runs uv venv then
# uv pip install --python <venv>/bin/python -r requirements.txt, in that
# order, both cwd=dest_dir; a failed venv step stops before the install call.
if "$VENV/bin/python" "$ROOT/tests/test_init_install_offer.py"; then echo "OK"; else echo "FAIL: cs init install offer regressed"; FAIL=1; fi

step "26. manifest.toml is clone-owned — never a cs update render target, never a bare-key break"
# Confirmed live 2026-08-21: manifest.toml went through the normal
# diff/overwrite flow like any template output, so an operator's "y"
# silently destroyed hand-authored comments — and the bare re-render was
# INVALID TOML the moment an account name was an email (`@` illegal in a
# bare key; the shape the kernel's own docs recommend). Guards: manifest.toml
# is now exempt from cs update exactly like requirements.txt (byte-identical,
# absent from updated file_checksums, "clone-owned" message printed);
# toml_quote() round-trips every key/value shape through a real TOML parser;
# the render gate's new email-account fixture proves manifest.toml.j2 itself
# renders valid TOML for that shape, not just that toml_quote is correct in
# isolation.
if "$VENV/bin/python" "$ROOT/tests/test_toml_quote.py"; then echo "OK"; else echo "FAIL: toml_quote regressed"; FAIL=1; fi

step "27. every agent reads the same commands (.claude → .opencode, AGENTS.md, Codex)"
# Found live 2026-08-21: a clone's .opencode/commands/ was a tracked COPY
# frozen in July, still offering /munchausen and the other pre-cs- names
# weeks after .claude/commands/ was renamed — the kernel rendered only
# .claude/, so nothing kept them in step. Now cs init AND cs update point
# every other surface into .claude/ by symlink (a copy is a second source,
# and it drifts). Guards: same names/bytes in .opencode/, a renamed command
# does not survive there, AGENTS.md resolves to CLAUDE.md, Codex's
# home-global prompt dir is never silently hijacked from another clone (EOF
# → No, v0.5.2 contract), and a symlink-less filesystem still gets copies.
if "$VENV/bin/python" "$ROOT/tests/test_agent_surfaces.py"; then echo "OK"; else echo "FAIL: agent surfaces drifted"; FAIL=1; fi

step "28. RATE_CAP fully removed (send_draft no longer blocks on it)"
# 2026-08-23: a per-day send quota did not prevent the failure it existed for,
# it scaled it down — at the cap the kernel returned a per-contact refusal and
# the run carried on, so real contacts were skipped in silence (see mrcall-cs
# docs/briefs/2026-08-23-rate-cap-silently-drops-customers.md). CS_PAUSE plus
# contradiction-triggered pause replace it; no volume-based throttle remains
# on any send path. Guards: send_draft() in CS_TRIAGE_MODE=send returns a
# clean dry-run with no "blocked" key, and _rate_capped() no longer exists.
if "$VENV/bin/python" "$ROOT/tests/test_campaign_rate_cap_removed.py"; then echo "OK"; else echo "FAIL: RATE_CAP mechanism regressed"; FAIL=1; fi

step "29. draft-delete removes ONE named draft, to Trash, or refuses"
# Deleting a draft deletes a person's mail. Guards: dry-run (the default)
# selects read-only and writes nothing; zero / several / mismatched matches
# refuse instead of picking one; no \Drafts folder and no \Trash folder both
# refuse rather than guess or expunge; a commit issues exactly ONE UID MOVE of
# the identified uid into Trash (recoverable 30 days) and never \Deleted +
# EXPUNGE; the CLI verb exits non-zero on a refusal and --account refuses it.
if "$VENV/bin/python" "$ROOT/tests/test_gmail_draft_delete.py"; then echo "OK"; else echo "FAIL: draft-delete guards regressed"; FAIL=1; fi

step "30. cs config — resolved value + provenance, duplicate flag, no secret printed"
# Two consecutive headless ticks read "no CS_TRIAGE_MODE env var" as "so the
# default draft applies" while manifest.toml declared send — the layering was
# sound, the RESOLVED value was invisible. Guards: the winning layer is named
# down to the TOML table+key / the env KEY; an env layer that overrides the
# manifest is reported as the winner and BOTH declarations are surfaced (a
# duplicate is a defect even when the two agree today); a knob absent from
# manifest.toml reports "kernel default", never the manifest; two alias
# spellings in one file are flagged; and no secret value reaches the text
# report, --json or --all.
if "$VENV/bin/python" "$ROOT/tests/test_config_report.py"; then echo "OK"; else echo "FAIL: cs config provenance regressed"; FAIL=1; fi

echo
if [ "$FAIL" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: all gates green"
